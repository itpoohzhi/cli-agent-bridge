"""Управляемый пул прогретых standby-воркеров agy-bridge поверх ResidentProcessPool."""

from __future__ import annotations

import collections
import hashlib
import json
import logging
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import cast, final

from core.stdio_resident.process_io import EOF, LINE, ResidentProcessHandle, StdioIoError
from core.stdio_resident.process_pool import (
    PoolClosedError,
    ResidentProcessPool,
    SlotLeaseTimeoutError,
)
from core.stdio_resident.types import SlotAffinityKey

from .persistent_worker_config import PersistentWorkerSettings

__all__ = [
    "AgyStandbyManager",
    "StandbyProfileKey",
    "StandbyReadySlot",
    "standby_argv_digest",
]

_LOGGER = logging.getLogger(__name__)
_OWNER_HASH = "agy-bridge"
_BACKEND_ID = "agy-bridge"
_STANDBY_PREFIX = "__standby__:"
_FORBIDDEN_ARGS = ("--add-dir", "--resume")
_PREWARM_ERRORS = (
    SlotLeaseTimeoutError, PoolClosedError, OSError, StdioIoError, RuntimeError,
)


def standby_argv_digest(argv: Sequence[str]) -> str | None:
    """Хеш launch-argv для изоляции профилей; None если argv содержит --add-dir или --resume."""
    for arg in argv:
        for bad in _FORBIDDEN_ARGS:
            if arg == bad or arg.startswith(f"{bad}="):
                return None
    return hashlib.sha256("\0".join(argv).encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class StandbyProfileKey:
    """Точный профиль совместимости для выдачи прогретого standby-воркера на turn 0."""

    model: str
    effort: str
    cwd: str
    env_digest: str
    review_profile: str
    argv_digest: str = ""


@dataclass(frozen=True)
class StandbyReadySlot:
    """Прогретый слот ResidentProcessPool, уже отдавший событие `init`."""

    standby_chat_key: str
    slot_id: str
    generation: int
    init_line: str
    cid: str
    created_mono: float
    pool_id: int


def _parse_init_line(line: str) -> tuple[bool, str]:
    try:
        raw = cast(object, json.loads(line))
    except ValueError:
        return False, ""
    if not isinstance(raw, dict):
        return False, ""
    ev = cast(dict[str, object], raw)
    if (ev.get("event") or ev.get("type")) != "init":
        return False, ""
    return True, str(ev.get("conversation_id") or ev.get("session_id") or "")


@final
class AgyStandbyManager:
    """Ограниченный фоновый прогрев standby-слотов внутри существующего ResidentProcessPool."""

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._epoch: int = 0
        self._prewarm_seq: int = 0
        self._ready: collections.OrderedDict[StandbyProfileKey, StandbyReadySlot] = collections.OrderedDict()
        self._inflight: dict[StandbyProfileKey, int] = {}
        self._chat_alias: collections.OrderedDict[str, str] = collections.OrderedDict()
        self._standby_hits: int = 0
        self._standby_prewarms: int = 0

    def resolve_alias(self, chat_key: str) -> str:
        with self._lock:
            target = self._chat_alias.get(chat_key)
            if target is not None:
                self._chat_alias.move_to_end(chat_key)
                return target
            return chat_key

    def bind_alias(self, chat_key: str, standby_chat_key: str, max_slots: int) -> None:
        if not chat_key or not standby_chat_key:
            return
        with self._lock:
            cap = max(16, max_slots * 8)
            self._chat_alias[chat_key] = standby_chat_key
            self._chat_alias.move_to_end(chat_key)
            while len(self._chat_alias) > cap:
                _ = self._chat_alias.popitem(last=False)

    def drop_alias(self, chat_key: str) -> None:
        if chat_key:
            with self._lock:
                _ = self._chat_alias.pop(chat_key, None)

    def has_alias(self, chat_key: str) -> bool:
        with self._lock:
            return chat_key in self._chat_alias

    @staticmethod
    def _close_idle_slots(pool: ResidentProcessPool | None, slots: Sequence[StandbyReadySlot]) -> None:
        if pool is None or not slots:
            return
        pid_key = id(pool)
        for slot in slots:
            if slot.pool_id != pid_key:
                continue
            try:
                _ = pool.close_if_idle(slot.slot_id, slot.generation)
            except _PREWARM_ERRORS as exc:
                _LOGGER.debug("standby idle close skipped: %s", exc)

    def close_slot(self, pool: ResidentProcessPool, slot: StandbyReadySlot) -> None:
        self._close_idle_slots(pool, (slot,))

    def _prune_expired_locked(self, now: float, pool_id: int, ttl_s: float) -> list[StandbyReadySlot]:
        expired: list[StandbyReadySlot] = []
        for pkey, slot in list(self._ready.items()):
            if slot.pool_id != pool_id or (now - slot.created_mono) > ttl_s:
                _ = self._ready.pop(pkey, None)
                expired.append(slot)
        return expired

    @staticmethod
    def _affinity_for(chat_key: str, profile_key: StandbyProfileKey) -> SlotAffinityKey:
        return SlotAffinityKey(
            owner_hash=_OWNER_HASH, chat_key=chat_key, backend_id=_BACKEND_ID,
            model=profile_key.model, effort=profile_key.effort, cwd_norm=profile_key.cwd,
            env_digest=profile_key.env_digest, review_profile=profile_key.review_profile,
        )

    def claim_ready(
        self, profile_key: StandbyProfileKey, pool: ResidentProcessPool, cfg: PersistentWorkerSettings
    ) -> StandbyReadySlot | None:
        """Забрать живой standby-слот для turn 0 с глобальной вычисткой протухших записей."""
        if not (cfg.enabled and cfg.standby_enabled) or profile_key.review_profile == "zero-canon":
            return None
        now = time.monotonic()
        with self._lock:
            expired = self._prune_expired_locked(now, id(pool), cfg.standby_ttl_s)
            slot = self._ready.pop(profile_key, None)
        self._close_idle_slots(pool, expired)
        if slot is None:
            return None
        binding = pool.idle_binding(self._affinity_for(slot.standby_chat_key, profile_key))
        if binding is None or binding.slot_id != slot.slot_id or binding.generation != slot.generation:
            self._close_idle_slots(pool, (slot,))
            return None
        with self._lock:
            self._standby_hits += 1
        return slot

    def schedule_prewarm(
        self, profile_key: StandbyProfileKey, pool: ResidentProcessPool,
        argv_builder: Callable[[], list[str]], cwd: str, env: Mapping[str, str],
        cfg: PersistentWorkerSettings,
    ) -> None:
        """Запустить фоновый прогрев standby-слота после глобальной вычистки протухших записей."""
        if not (cfg.enabled and cfg.standby_enabled) or profile_key.review_profile == "zero-canon":
            return
        cap = min(cfg.standby_max_slots, max(0, cfg.max_slots - 2))
        if cap <= 0:
            return
        now = time.monotonic()
        with self._lock:
            expired = self._prune_expired_locked(now, id(pool), cfg.standby_ttl_s)
            start_token: int | None = None
            epoch = self._epoch
            if (
                profile_key not in self._ready
                and profile_key not in self._inflight
                and (len(self._ready) + len(self._inflight)) < cap
            ):
                self._prewarm_seq += 1
                start_token = self._prewarm_seq
                self._inflight[profile_key] = start_token
                self._standby_prewarms += 1
        self._close_idle_slots(pool, expired)
        if start_token is None:
            return
        t = threading.Thread(
            target=self._run_prewarm,
            args=(epoch, start_token, profile_key, pool, argv_builder, cwd, dict(env), cfg.standby_init_timeout_s),
            name="agy-standby-prewarm", daemon=True,
        )
        t.start()

    def _run_prewarm(
        self, epoch: int, token: int, profile_key: StandbyProfileKey, pool: ResidentProcessPool,
        argv_builder: Callable[[], list[str]], cwd: str, env: dict[str, str], init_timeout_s: float,
    ) -> None:
        standby_chat_key = f"{_STANDBY_PREFIX}{uuid.uuid4().hex[:12]}"
        affinity = self._affinity_for(standby_chat_key, profile_key)
        entry = None
        released = False
        try:
            entry = pool.acquire(affinity, argv_builder=argv_builder, cwd=cwd, env=env, is_ephemeral=False)
            init_line, cid = self._await_init(entry.handle, init_timeout_s, epoch)
            with self._lock:
                still_valid = self._epoch == epoch
            if not init_line or not still_valid:
                released = True
                _ = pool.release(entry.slot_id, success=False, cancel=True, lease_id=entry.lease_id)
                return
            released = True
            kept = pool.release(entry.slot_id, success=True, cancel=False, lease_id=entry.lease_id)
            if not kept:
                return
            slot = StandbyReadySlot(
                standby_chat_key=standby_chat_key, slot_id=entry.slot_id,
                generation=entry.handle.generation, init_line=init_line, cid=cid,
                created_mono=time.monotonic(), pool_id=id(pool),
            )
            stale: list[StandbyReadySlot] = []
            with self._lock:
                if self._epoch == epoch:
                    self._ready[profile_key] = slot
                    self._ready.move_to_end(profile_key)
                else:
                    stale.append(slot)
            self._close_idle_slots(pool, stale)
        except _PREWARM_ERRORS as exc:
            _LOGGER.debug("standby prewarm skipped/failed: %s", exc)
        finally:
            if entry is not None and not released:
                try:
                    _ = pool.release(entry.slot_id, success=False, cancel=True, lease_id=entry.lease_id)
                except BaseException:  # noqa: BLE001
                    pass
            with self._lock:
                if self._inflight.get(profile_key) == token:
                    _ = self._inflight.pop(profile_key, None)

    def _await_init(
        self, handle: ResidentProcessHandle, timeout_s: float, epoch: int
    ) -> tuple[str, str]:
        deadline = time.monotonic() + max(0.5, timeout_s)
        while time.monotonic() < deadline:
            with self._lock:
                if self._epoch != epoch:
                    return "", ""
            kind, tagged = handle.read_stdout_line_outcome(timeout_s=min(0.25, max(0.05, deadline - time.monotonic())))
            if kind == LINE and tagged is not None:
                if line := tagged.line.strip():
                    is_init, cid = _parse_init_line(line)
                    if is_init:
                        return line, cid
            elif kind == EOF or not handle.is_alive():
                return "", ""
        return "", ""

    def clear(self, *, drop_aliases: bool = True, pool: ResidentProcessPool | None = None) -> None:
        """Сбросить все готовые standby-записи, отменить in-flight прогревы и закрыть idle standby."""
        evicted: list[StandbyReadySlot] = []
        with self._lock:
            if self._ready or self._inflight:
                self._epoch += 1
            if self._ready:
                evicted = list(self._ready.values())
                self._ready.clear()
            if drop_aliases:
                self._chat_alias.clear()
        self._close_idle_slots(pool, evicted)

    def stats(self) -> tuple[int, int, int]:
        with self._lock:
            return len(self._ready), self._standby_hits, self._standby_prewarms

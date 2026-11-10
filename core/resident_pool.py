from __future__ import annotations

import asyncio
import inspect
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncIterator, Mapping, Sequence


class SlotState(str, Enum):
    NEW = "NEW"
    STARTING = "STARTING"
    WARMING = "WARMING"
    READY = "READY"
    LEASED = "LEASED"
    RECYCLING = "RECYCLING"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SlotKey:
    adapter: str
    backend_id: str
    effort: str | None
    profile: str | None = None
    mode: str = "plain"


@dataclass
class ResidentSlot:
    key: SlotKey
    state: str = SlotState.NEW.value
    handle: Any = None
    created_at: float = 0.0
    last_used_at: float = 0.0
    turns_count: int = 0
    restarts_count: int = 0
    last_reset_at: float = 0.0
    last_error: str | None = None
    pinned: bool = True


@dataclass
class PrewarmReport:
    total_slots: int
    ready_slots: int
    degraded_slots: list[str]
    elapsed_s: float
    details: dict[str, Any]


def _models_mapping(fleet: Mapping[str, Any]) -> Mapping[str, Any]:
    models = fleet.get("models")
    return models if isinstance(models, Mapping) else fleet


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _positive_int(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _optional_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    parsed = float(value)
    if parsed < 0:
        raise ValueError("timeout and TTL values must be non-negative")
    return parsed


async def _await_result(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _with_timeout(value: Any, timeout_s: float | None) -> Any:
    awaitable = _await_result(value)
    if timeout_s is None or timeout_s <= 0:
        return await awaitable
    return await asyncio.wait_for(awaitable, timeout=timeout_s)


def _public_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def _slot_name(key: SlotKey) -> str:
    parts = [key.adapter, key.backend_id]
    if key.effort is not None:
        parts.append(f"effort={key.effort}")
    if key.profile is not None:
        parts.append(f"profile={key.profile}")
    parts.append(f"mode={key.mode}")
    return ":".join(parts)


class ResidentPoolManager:
    def __init__(
        self,
        fleet: Mapping[str, Any],
        adapters: dict[str, Any],
        resident_models_env: str | None = None,
    ) -> None:
        self.fleet = fleet
        self.adapters = adapters
        env_value = (
            resident_models_env
            if resident_models_env is not None
            else os.getenv("BRIDGE_RESIDENT_MODELS")
        )
        self._explicit_resident_models = _csv(env_value)
        self._slots: list[ResidentSlot] = []
        self._condition = asyncio.Condition()
        self._lifecycle_lock = asyncio.Lock()
        self._shutdown_requested = False
        self._unPinned_idle_ttl_s = _optional_float(
            os.getenv("BRIDGE_UNPINNED_IDLE_TTL_S")
        )
        self._reset_timeout_s = _optional_float(os.getenv("BRIDGE_RESET_TIMEOUT_S"))
        self._initialize_slots()

    def _initialize_slots(self) -> None:
        now = time.monotonic()
        for key in self.desired_slots():
            self._slots.append(
                ResidentSlot(
                    key=key,
                    state=SlotState.NEW.value,
                    created_at=now,
                    last_used_at=now,
                    pinned=True,
                )
            )

    def _resident_model_names(self) -> list[str]:
        models = _models_mapping(self.fleet)
        names: list[str] = []
        seen: set[str] = set()

        for name, config in models.items():
            if isinstance(config, Mapping) and _as_bool(config.get("resident", False)):
                text_name = str(name)
                if text_name not in seen:
                    names.append(text_name)
                    seen.add(text_name)

        for name in self._explicit_resident_models:
            if name not in seen:
                names.append(name)
                seen.add(name)

        return names

    def _resolve_config(self, model_name: str) -> Mapping[str, Any]:
        models = _models_mapping(self.fleet)
        current = model_name
        visited: set[str] = set()

        while True:
            if current in visited:
                raise ValueError(f"alias cycle while resolving resident model {model_name!r}")
            visited.add(current)

            if current not in models:
                raise KeyError(f"unknown resident model {model_name!r}")
            raw = models[current]
            if isinstance(raw, str):
                current = raw
                continue
            if not isinstance(raw, Mapping):
                raise TypeError(f"invalid configuration for model {current!r}")

            alias = raw.get("alias")
            if alias is None:
                alias = raw.get("alias_of")
            if isinstance(alias, str) and alias:
                current = alias
                continue
            return raw

    def desired_slots(self) -> list[SlotKey]:
        desired: list[SlotKey] = []
        for model_name in self._resident_model_names():
            config = self._resolve_config(model_name)
            adapter = config.get("adapter")
            backend_id = config.get("backend_id", config.get("id", model_name))
            if not isinstance(adapter, str) or not adapter:
                raise ValueError(f"resident model {model_name!r} has no adapter")
            if not isinstance(backend_id, str) or not backend_id:
                raise ValueError(f"resident model {model_name!r} has no backend_id")

            raw_efforts = config.get("efforts")
            if raw_efforts is None:
                efforts: Sequence[Any] = [config.get("effort")]
            elif isinstance(raw_efforts, str):
                efforts = [raw_efforts]
            elif isinstance(raw_efforts, Sequence):
                efforts = raw_efforts or [None]
            else:
                raise TypeError(f"invalid efforts for resident model {model_name!r}")

            pool_config = config.get("pool_size", 1)
            for raw_effort in efforts:
                effort = None if raw_effort is None else str(raw_effort)
                if isinstance(pool_config, Mapping):
                    size_value = pool_config.get(
                        effort,
                        pool_config.get("default", 1),
                    )
                else:
                    size_value = pool_config
                pool_size = _positive_int(size_value)
                key = SlotKey(
                    adapter=adapter,
                    backend_id=backend_id,
                    effort=effort,
                    profile=(
                        str(config["profile"])
                        if config.get("profile") is not None
                        else None
                    ),
                    mode=str(config.get("mode", "plain")),
                )
                desired.extend(key for _ in range(pool_size))
        return desired

    def adapter_for(self, key: SlotKey) -> Any:
        try:
            return self.adapters[key.adapter]
        except KeyError as exc:
            raise KeyError(f"adapter {key.adapter!r} is not configured") from exc

    def iter_slots(self) -> tuple[ResidentSlot, ...]:
        return tuple(self._slots)

    def idle_timeout_s(self, slot: ResidentSlot) -> float | None:
        if slot.pinned:
            return 0.0
        return self._unPinned_idle_ttl_s

    async def _call(self, adapter: Any, method: str, *args: Any) -> Any:
        callback = getattr(adapter, method, None)
        if callback is None or not callable(callback):
            raise AttributeError(f"adapter does not implement {method}")
        return await _await_result(callback(*args))

    async def _start_slot(self, slot: ResidentSlot) -> None:
        if self._shutdown_requested:
            raise RuntimeError("resident pool is shutting down")

        adapter = self.adapter_for(slot.key)
        slot.state = SlotState.STARTING.value
        slot.last_error = None
        try:
            slot.handle = await self._call(adapter, "start", slot.key)
            await self._call(adapter, "wait_ready", slot.handle)
            await self._call(
                adapter,
                "apply_or_verify_effort",
                slot.handle,
                slot.key.effort,
            )
            slot.state = SlotState.WARMING.value
            await self._call(adapter, "warmup", slot.handle)
            await self._call(adapter, "reset_context", slot.handle)
            now = time.monotonic()
            slot.last_reset_at = now
            slot.last_used_at = now
            slot.state = SlotState.READY.value
        except BaseException as exc:
            slot.state = SlotState.FAILED.value
            slot.last_error = _public_error(exc)
            await self._safe_stop(slot)
            raise
        finally:
            await self._notify_waiters()

    async def _safe_stop(self, slot: ResidentSlot) -> None:
        handle = slot.handle
        slot.handle = None
        if handle is None:
            return
        try:
            adapter = self.adapter_for(slot.key)
            await self._call(adapter, "stop", handle)
        except BaseException as exc:
            if slot.last_error is None:
                slot.last_error = _public_error(exc)

    async def _notify_waiters(self) -> None:
        async with self._condition:
            self._condition.notify_all()

    async def prewarm(
        self,
        concurrency: int = 4,
        timeout_s: float = 180.0,
    ) -> PrewarmReport:
        if concurrency <= 0:
            raise ValueError("concurrency must be positive")
        started_at = time.monotonic()
        semaphore = asyncio.Semaphore(concurrency)

        async def start_one(slot: ResidentSlot) -> None:
            async with semaphore:
                if slot.state == SlotState.READY.value:
                    return
                await self._start_slot(slot)

        tasks = [asyncio.create_task(start_one(slot)) for slot in self._slots]
        timed_out = False
        if tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout_s,
                )
            except asyncio.TimeoutError:
                timed_out = True
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                for slot in self._slots:
                    if slot.state in {
                        SlotState.STARTING.value,
                        SlotState.WARMING.value,
                    }:
                        slot.state = SlotState.FAILED.value
                        slot.last_error = "prewarm timed out"
                        await self._safe_stop(slot)

        degraded = [
            _slot_name(slot.key)
            for slot in self._slots
            if slot.state != SlotState.READY.value
        ]
        ready = sum(slot.state == SlotState.READY.value for slot in self._slots)
        return PrewarmReport(
            total_slots=len(self._slots),
            ready_slots=ready,
            degraded_slots=degraded,
            elapsed_s=time.monotonic() - started_at,
            details={
                "timed_out": timed_out,
                "slots": self.snapshot()["slots"],
            },
        )

    def _resolved_key(self, resolved: Any) -> SlotKey:
        def getter(name: str, default: Any = None) -> Any:
            if isinstance(resolved, Mapping):
                return resolved.get(name, default)
            return getattr(resolved, name, default)

        adapter = getter("adapter")
        backend_id = getter("backend_id", getter("id"))
        if not isinstance(adapter, str) or not adapter:
            raise ValueError("resolved model has no adapter")
        if not isinstance(backend_id, str) or not backend_id:
            raise ValueError("resolved model has no backend_id")
        effort = getter("effort")
        profile = getter("profile")
        return SlotKey(
            adapter=adapter,
            backend_id=backend_id,
            effort=None if effort is None else str(effort),
            profile=None if profile is None else str(profile),
            mode=str(getter("mode", "plain")),
        )

    def _find_ready_slot(self, key: SlotKey) -> ResidentSlot | None:
        return next(
            (
                slot
                for slot in self._slots
                if slot.key == key and slot.state == SlotState.READY.value
            ),
            None,
        )

    async def _acquire_slot(self, key: SlotKey, timeout_s: float) -> ResidentSlot:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        async with self._condition:
            while True:
                if self._shutdown_requested:
                    raise RuntimeError("resident pool is shutting down")
                slot = self._find_ready_slot(key)
                if slot is not None:
                    slot.state = SlotState.LEASED.value
                    return slot
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise TimeoutError(f"no resident slot available for {_slot_name(key)}")
                await asyncio.wait_for(self._condition.wait(), timeout=remaining)

    @asynccontextmanager
    async def lease(
        self,
        resolved: Any,
        wait_timeout_s: float = 60.0,
    ) -> AsyncIterator[Any]:
        key = self._resolved_key(resolved)
        slot = await self._acquire_slot(key, wait_timeout_s)
        recycle_reason: str | None = None
        try:
            adapter = self.adapter_for(slot.key)
            await _with_timeout(
                self._call(adapter, "reset_context", slot.handle),
                self._reset_timeout_s,
            )
            slot.last_reset_at = time.monotonic()
            yield slot.handle
        except BaseException as exc:
            slot.last_error = _public_error(exc)
            slot.state = SlotState.RECYCLING.value
            recycle_reason = slot.last_error
            raise
        finally:
            slot.last_used_at = time.monotonic()
            slot.turns_count += 1
            if recycle_reason is None:
                slot.state = SlotState.READY.value
                await self._notify_waiters()
            else:
                try:
                    await self.recycle_slot(slot, recycle_reason)
                except BaseException:
                    pass

    async def recycle(self, key: SlotKey, reason: str) -> None:
        slot = next((candidate for candidate in self._slots if candidate.key == key), None)
        if slot is None:
            raise KeyError(f"unknown resident slot {_slot_name(key)}")
        await self.recycle_slot(slot, reason)

    async def recycle_slot(self, slot: ResidentSlot, reason: str) -> None:
        async with self._lifecycle_lock:
            if self._shutdown_requested:
                return
            slot.state = SlotState.RECYCLING.value
            slot.last_error = reason
            await self._safe_stop(slot)
            slot.restarts_count += 1
            try:
                await self._start_slot(slot)
            except BaseException:
                slot.state = SlotState.FAILED.value
                await self._notify_waiters()
                raise

    async def evict_idle_unpinned(self) -> None:
        now = time.monotonic()
        for slot in self._slots:
            ttl = self.idle_timeout_s(slot)
            if (
                not slot.pinned
                and ttl is not None
                and ttl > 0
                and slot.state == SlotState.READY.value
                and now - slot.last_used_at >= ttl
            ):
                slot.state = SlotState.RECYCLING.value
                await self._safe_stop(slot)
                slot.state = SlotState.NEW.value
                await self._notify_waiters()

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        slots: list[dict[str, Any]] = []
        for index, slot in enumerate(self._slots):
            slots.append(
                {
                    "slot": index,
                    "adapter": slot.key.adapter,
                    "backend_id": slot.key.backend_id,
                    "effort": slot.key.effort,
                    "profile": slot.key.profile,
                    "mode": slot.key.mode,
                    "state": slot.state,
                    "created_at": slot.created_at,
                    "last_used_at": slot.last_used_at,
                    "idle_s": max(0.0, now - slot.last_used_at),
                    "idle_timeout_s": self.idle_timeout_s(slot),
                    "turns_count": slot.turns_count,
                    "restarts_count": slot.restarts_count,
                    "last_reset_at": slot.last_reset_at,
                    "last_error": slot.last_error,
                    "pinned": slot.pinned,
                }
            )
        ready, not_ready = self.is_ready()
        return {
            "ready": ready,
            "not_ready": not_ready,
            "total_slots": len(self._slots),
            "ready_slots": sum(
                slot.state == SlotState.READY.value for slot in self._slots
            ),
            "slots": slots,
        }

    def is_ready(self) -> tuple[bool, list[str]]:
        not_ready = [
            _slot_name(slot.key)
            for slot in self._slots
            if slot.pinned and slot.state != SlotState.READY.value
        ]
        return not not_ready, not_ready

    async def shutdown(self) -> None:
        self._shutdown_requested = True
        await self._notify_waiters()
        for slot in self._slots:
            await self._safe_stop(slot)
            slot.state = SlotState.NEW.value

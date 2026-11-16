"""Ограниченное обновление model-notes и долговечная публикация снимков."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import math
import os
import sys
import tempfile
import threading
import time
from collections.abc import Mapping
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.model_notes_parse import ModelNotes, parse_model_notes, read_model_notes_file


class SnapshotConflict(ValueError):
    """Снимок изменён другим писателем либо поколение откатилось."""


def nfr_scale(value: object, default: float, minimum: float, maximum: float) -> float:
    """Возвращает конечное число в диапазоне, иначе безопасный fallback."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return default
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return default
    return number if math.isfinite(number) and minimum <= number <= maximum else default


def select_source(env: Mapping[str, object]) -> str:
    """Выбирает первый PRESENT ключ, не подменяя пустое значение."""
    for key in ("MODEL_NOTES_PATH", "BRIDGE_MODEL_NOTES_PATH"):
        if key in env:
            return os.path.expanduser(str(env[key]))
    return str(Path.home() / "Мой диск/Context/model-notes.md")


def _disk(path: Path) -> str | None:
    try:
        return read_model_notes_file(path)
    except ValueError as error:
        if isinstance(error.__cause__, FileNotFoundError):
            return None
        raise


def _version(base: str | None) -> tuple[int, int, str]:
    if base is None:
        return -1, 0, ""
    data: Any = json.loads(base)
    generation, epoch = data["generation"], data["epoch"]
    if type(generation) is not int or type(epoch) is not int:
        raise SnapshotConflict("Некорректный тип версии")
    if min(generation, epoch) < 0 or not isinstance(data["digest"], str):
        raise SnapshotConflict("Некорректная версия")
    return generation, epoch, data["digest"]


def _atomic(path: Path, payload: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class ModelNotesSnapshotManager:
    """Владеет одним daemon-reader; request path только будит таймер."""

    def __init__(self, env: Mapping[str, object] | None = None) -> None:
        self._configure(os.environ if env is None else env)
        self._notes: ModelNotes | None = None
        self._result: ModelNotes | None = None
        self.worker_error: BaseException | None = None
        self._fault_since: float | None = None
        self._usable = False
        self._worker: threading.Thread | None = None
        self._done, self._wake, self._stop = (
            threading.Event(),
            threading.Event(),
            threading.Event(),
        )
        self.stopped = threading.Event()
        self._next_refresh = 0.0
        self._refresh_lock = threading.Lock()
        self._refresh()
        self._timer = threading.Thread(target=self._loop, name="model-notes-timer", daemon=True)
        self._timer.start()

    def _configure(self, config: Mapping[str, object]) -> None:
        self.source = select_source(config)
        self.snapshot_path = (
            Path(str(config.get("BRIDGE_STATE_DIR", "~/.config/cli-agent-bridge"))).expanduser()
            / "model-notes.snapshot.json"
        )
        self.refresh_interval_s = nfr_scale(config.get("MODEL_NOTES_REFRESH_INTERVAL_S"), 30, 5, 300)
        self.read_timeout_s = nfr_scale(config.get("MODEL_NOTES_READ_TIMEOUT_S"), 2, 0.01, 10)
        self.stale_grace_s = nfr_scale(config.get("MODEL_NOTES_STALE_GRACE_S"), 60, 0, 60)
        if self.refresh_interval_s > self.stale_grace_s:
            print(
                "MODEL_NOTES_REFRESH_INTERVAL_S > MODEL_NOTES_STALE_GRACE_S",
                file=sys.stderr,
            )

    @property
    def status(self) -> str:
        """Проверяет grace и EXPIRY без файлового ввода-вывода."""
        notes, fault = self._notes, self._fault_since
        if not self._usable or notes is None:
            return "FAILED_CLOSED"
        if fault is not None and time.monotonic() - fault >= self.stale_grace_s:
            return "FAILED_CLOSED"
        if notes.expires_at is not None and datetime.now(timezone.utc) >= notes.expires_at:
            return "FAILED_CLOSED"
        return "OK"

    @property
    def snapshot(self) -> ModelNotes | None:
        """Возвращает только разрешённый к использованию снимок."""
        return self._notes if self.status == "OK" else None

    @property
    def in_flight_workers(self) -> int:
        """Слот занят до фактического выхода потока, не до done_event."""
        return int(self._worker is not None and self._worker.is_alive())

    def maybe_trigger_refresh_async(self) -> None:
        """Не читает диск, не ждёт reader и не создаёт потоки."""
        if time.monotonic() >= self._next_refresh and not self._stop.is_set():
            self._wake.set()

    def close(self) -> None:
        """Останавливает таймер; зависший daemon-reader не блокирует shutdown."""
        self._stop.set()
        self._wake.set()

    def _loop(self) -> None:
        try:
            while not self._stop.is_set():
                self._wake.wait(max(0.0, self._next_refresh - time.monotonic()))
                self._wake.clear()
                if not self._stop.is_set() and time.monotonic() >= self._next_refresh:
                    self._refresh()
        finally:
            self.stopped.set()

    def _fault(self, error: BaseException) -> None:
        if self._fault_since is None:
            self._fault_since = time.monotonic()
        cause = error.__cause__ if error.__cause__ is not None else error
        transient = isinstance(cause, (OSError, TimeoutError))
        if isinstance(cause, OSError) and cause.errno == errno.ENOENT:
            transient = False
        if not transient:
            self._usable = False

    def _refresh(self) -> None:
        if not self._refresh_lock.acquire(blocking=False):
            return
        try:
            self._next_refresh = time.monotonic() + self.refresh_interval_s
            if self.in_flight_workers:
                self._fault(TimeoutError("reader занят"))
                return
            self._done = threading.Event()
            self._result = None
            self._worker = threading.Thread(target=self._work, name="model-notes-reader", daemon=True)
            self._worker.start()
            if not self._done.wait(self.read_timeout_s):
                self._fault(TimeoutError("model-notes read timeout"))
                return
            if self._result is None:
                self._fault(self.worker_error or RuntimeError("reader завершился без результата"))
                return
            self._notes = self._result
            self._usable, self._fault_since = True, None
        finally:
            self._refresh_lock.release()

    def _work(self) -> None:
        try:
            base = _disk(self.snapshot_path)
            text = read_model_notes_file(self.source)
            notes = parse_model_notes(text)
            self._publish(notes, text, base)
            self._result = notes
        except BaseException as error:
            self.worker_error = error
            self._fault(error)
            if not isinstance(error, Exception):
                raise
        finally:
            self._done.set()

    def _publish(self, notes: ModelNotes, text: str, expected_base: str | None) -> None:
        path = self.snapshot_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_suffix(".json.lock").open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if _disk(path) != expected_base:
                raise SnapshotConflict("expected base изменился")
            generation, epoch, digest = _version(expected_base)
            new_digest = hashlib.sha256(text.encode()).hexdigest()
            next_generation = generation + 1 if notes.generation is None else notes.generation
            if next_generation < generation:
                raise SnapshotConflict("Откат поколения")
            if next_generation == generation and new_digest != digest:
                raise SnapshotConflict("Поколение переиспользовано")
            payload = dict(
                asdict(notes),
                generation=next_generation,
                epoch=epoch + 1,
                digest=new_digest,
            )
            _atomic(path, json.dumps(payload, ensure_ascii=False, default=str))

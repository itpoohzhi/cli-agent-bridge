"""Рантайм-кэш и атомарное хранилище оперативных весов маршрутизации."""

from __future__ import annotations

import fcntl
import json
import os
import stat
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.routing_weights_domain import WeightsOverrideDoc, WeightsValidationError, apply_weight_overrides, validate_weights_document
from core.runtime_env import ConfigError, ConfigSnapshotError, DynamicFlagSource, NumSpec, parse_number, read_config_snapshot

DEFAULT_WEIGHTS_PATH = "~/.config/cli-agent-bridge/routing_weights.json"
_O_NOFOLLOW: int = getattr(os, "O_NOFOLLOW", 0)
_ENABLED_FLAG = DynamicFlagSource("BRIDGE_ROUTING_WEIGHTS_ENABLED", default=True)
_TTL_SPEC = NumSpec(("BRIDGE_ROUTING_WEIGHTS_TTL_S",), 0.5, 0.0, 60.0)
_MAX_BYTES_SPEC = NumSpec(("BRIDGE_ROUTING_WEIGHTS_MAX_BYTES",), 262144, 1024, 1048576, integer=True)
_LOCK_WAIT_SPEC = NumSpec(("BRIDGE_ROUTING_WEIGHTS_LOCK_WAIT_S",), 10.0, 0.1, 120.0)
_LOCK_POLL_SPEC = NumSpec(("BRIDGE_ROUTING_WEIGHTS_LOCK_POLL_S",), 0.05, 0.005, 1.0)
_LOG_INTERVAL_SPEC = NumSpec(("BRIDGE_ROUTING_WEIGHTS_LOG_INTERVAL_S",), 30.0, 1.0, 3600.0)

class WeightsCorruptError(ValueError):
    """Ошибка целостности, схемы или симлинка файла оперативных весов."""
class WeightsLockTimeoutError(TimeoutError):
    """Таймаут ожидания эксклюзивного flock на файле оперативных весов."""
@dataclass(frozen=True, slots=True)
class _CacheEntry:
    checked_at: float
    sig: tuple[int, ...]
    doc: WeightsOverrideDoc | None
def _dynamic_overlay() -> Mapping[str, Any]:
    path = os.environ.get("BRIDGE_DYNAMIC_CONFIG_PATH") or os.path.expanduser("~/.config/cli-agent-bridge/dynamic_config.json")
    try:
        data = read_config_snapshot(path)
    except ConfigSnapshotError:
        return {}
    return data if isinstance(data, Mapping) else {}
def _read_num(spec: NumSpec) -> float:
    key = spec.names[0]
    raw = _dynamic_overlay().get(key)
    return float(parse_number({key: str(raw)} if raw is not None else os.environ, spec))
def default_weights_path() -> Path:
    """Возвращает настроенный путь к SSOT-файлу весов без раскрытия симлинков."""
    raw = _dynamic_overlay().get("BRIDGE_ROUTING_WEIGHTS_PATH") or os.environ.get("BRIDGE_ROUTING_WEIGHTS_PATH", "")
    chosen = raw.strip() if isinstance(raw, str) and raw.strip() else DEFAULT_WEIGHTS_PATH
    return Path(os.path.expanduser(chosen))
def weights_enabled() -> bool:
    """Возвращает состояние kill-switch (fail-closed при битом dynamic_config.json)."""
    return _ENABLED_FLAG.enabled(fallback=False)
def _lstat_regular(target: Path) -> os.stat_result:
    try:
        st = os.lstat(target)
    except OSError as exc:
        if isinstance(exc, FileNotFoundError):
            raise
        raise WeightsCorruptError(str(exc)) from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise WeightsCorruptError("symlink_or_non_regular")
    return st
def _read_doc_nofollow(target: Path, max_bytes: int) -> WeightsOverrideDoc:
    """Читает и строго валидирует файл весов через O_NOFOLLOW и лимит max_bytes."""
    try:
        with os.fdopen(os.open(target, os.O_RDONLY | _O_NOFOLLOW), "rb") as fh:
            fst = os.fstat(fh.fileno())
            if not stat.S_ISREG(fst.st_mode) or fst.st_size > max_bytes:
                raise WeightsCorruptError("file_invalid_or_exceeds_max_bytes")
            raw = fh.read(max_bytes + 1)
    except (FileNotFoundError, WeightsCorruptError):
        raise
    except OSError as exc:
        raise WeightsCorruptError(f"open_failed: {exc}") from exc
    if len(raw) > max_bytes:
        raise WeightsCorruptError("file_exceeds_max_bytes")
    try:
        return validate_weights_document(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError, WeightsValidationError) as exc:
        raise WeightsCorruptError(str(exc)) from exc
class RoutingWeightsCache:
    """Потокобезопасный hot-reload кэш оперативных весов с политикой fail-closed."""
    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._snapshots: dict[Path, _CacheEntry] = {}
        self._last_error_ts: dict[Path, float] = {}
    def invalidate(self, path: Path | None = None) -> None:
        """Сбрасывает кэш целиком или для указанного пути."""
        with self._lock:
            if path is None:
                self._snapshots.clear()
                self._last_error_ts.clear()
                return
            target = Path(os.path.expanduser(str(path)))
            _ = self._snapshots.pop(target, None)
            _ = self._last_error_ts.pop(target, None)
    def get_doc(self, path: Path | None = None) -> WeightsOverrideDoc | None:
        """Возвращает валидный документ весов либо None при отсутствии/отказе."""
        now, target = time.monotonic(), Path(DEFAULT_WEIGHTS_PATH)
        try:
            if not weights_enabled():
                return None
            target = Path(os.path.expanduser(str(path))) if path is not None else default_weights_path()
            ttl_s = _read_num(_TTL_SPEC)
        except (ConfigError, ValueError, OSError) as exc:
            self.fail_closed_config(target, now, f"config_error: {exc}")
            return None
        with self._lock:
            hit = self._snapshots.get(target)
            if hit is not None and ttl_s > 0.0 and (now - hit.checked_at) <= ttl_s:
                return hit.doc
            return self._refresh_locked(target, now, hit)
    def fail_closed_config(self, target: Path, now: float, reason: str) -> None:
        """Фиксирует отказ конфига с rate-limited записью в stderr без падения."""
        with self._lock:
            self._log_fail_closed_locked(target, now, reason)
    def _refresh_locked(self, target: Path, now: float, hit: _CacheEntry | None) -> WeightsOverrideDoc | None:
        sig: tuple[int, ...] = ()
        try:
            st = _lstat_regular(target)
            max_bytes = int(_read_num(_MAX_BYTES_SPEC))
            if st.st_size > max_bytes:
                raise WeightsCorruptError("file_exceeds_max_bytes")
            sig = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_mode)
            doc = hit.doc if hit is not None and hit.sig == sig else _read_doc_nofollow(target, max_bytes)
        except FileNotFoundError:
            self._snapshots[target] = _CacheEntry(now, (), None)
            return None
        except (WeightsCorruptError, ConfigError, ValueError, OSError) as exc:
            return self._fail_closed(target, now, sig, str(exc))
        self._snapshots[target] = _CacheEntry(now, sig, doc)
        return doc
    def _log_fail_closed_locked(self, target: Path, now: float, reason: str) -> None:
        try:
            interval = _read_num(_LOG_INTERVAL_SPEC)
        except (ConfigError, ValueError, OSError):
            interval = _LOG_INTERVAL_SPEC.default
        last_ts = self._last_error_ts.get(target)
        if last_ts is None or (now - last_ts) >= interval:
            self._last_error_ts[target] = now
            print(f"[routing_weights] fail-closed on {target}: {reason}", file=sys.stderr)
    def _fail_closed(self, target: Path, now: float, sig: tuple[int, ...], reason: str) -> None:
        self._snapshots[target] = _CacheEntry(now, sig, None)
        self._log_fail_closed_locked(target, now, reason)
        return None
_DEFAULT_CACHE = RoutingWeightsCache()
def base_model_routing(model: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Возвращает базовую маршрутизацию модели из fleet.json (совместимо с _model_routing)."""
    routing, backend = model.get("routing"), model.get("backend")
    if isinstance(routing, Mapping) and (routing.get("legacy_backend") in (None, backend) or backend == routing.get("disabled_backend")):
        return routing
    if not backend:
        return {}
    b_id = str(backend)
    return {"catalog_hash": "singleton:" + b_id, "routes": [{"route_id": b_id, "backend": b_id, "weight": 100, "priority": 0, "params": model.get("params", {})}]}
def effective_model_routing(model_id: str, model: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Накладывает активные оперативные веса поверх базовой маршрутизации модели."""
    base = base_model_routing(model)
    if not base:
        return base
    try:
        doc = _DEFAULT_CACHE.get_doc()
    except (ConfigError, ValueError, OSError) as exc:
        _DEFAULT_CACHE.fail_closed_config(Path(DEFAULT_WEIGHTS_PATH), time.monotonic(), f"config_error: {exc}")
        return base
    return apply_weight_overrides(model_id, base, doc) if doc is not None else base

def _fsync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def _acquire_flock(lock_path: Path) -> int:
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | _O_NOFOLLOW, 0o600)
    wait_s, poll_s = _read_num(_LOCK_WAIT_SPEC), _read_num(_LOCK_POLL_SPEC)
    deadline = time.monotonic() + wait_s
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0.0:
                    raise WeightsLockTimeoutError(f"flock timeout on {lock_path}") from None
                time.sleep(min(poll_s, remaining))
    except BaseException:
        os.close(fd)
        raise

def _backup_corrupt_path(target: Path) -> Path:
    candidate = target.with_name(f"{target.name}.corrupt")
    if not os.path.lexists(candidate):
        return candidate
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    for idx in range(1000):
        numbered = target.with_name(f"{target.name}.corrupt.{stamp if idx == 0 else f'{stamp}-{idx}'}")
        if not os.path.lexists(numbered):
            return numbered
    raise OSError("unable to allocate unique corrupt backup name")

def _write_doc_atomic(target: Path, doc: WeightsOverrideDoc, max_bytes: int) -> None:
    encoded = (json.dumps(doc.to_dict(), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if len(encoded) > max_bytes:
        raise WeightsValidationError("encoded_document_exceeds_max_bytes")
    fd, tmp_str = tempfile.mkstemp(prefix=f".{target.name}.tmp.", dir=target.parent)
    tmp_path = Path(tmp_str)
    try:
        with os.fdopen(fd, "wb") as fh:
            os.fchmod(fh.fileno(), 0o600)
            _ = fh.write(encoded)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        with suppress(OSError):
            os.unlink(tmp_path)
        raise
    _fsync_dir(target.parent)
    if _read_doc_nofollow(target, max_bytes).to_dict() != doc.to_dict():
        raise WeightsCorruptError("readback_verification_failed")

class RoutingWeightsStore:
    """Безопасное чтение и атомарная мутация файла весов под flock и O_NOFOLLOW."""

    def __init__(self, path: Path | None = None) -> None:
        self._default_path: Path | None = path

    def _resolve_path(self, path: Path | None) -> Path:
        chosen = path if path is not None else self._default_path
        return Path(os.path.expanduser(str(chosen))) if chosen is not None else default_weights_path()

    @contextmanager
    def lock(self, path: Path | None = None) -> Iterator[Path]:
        """Создаёт каталог 0700 и держит эксклюзивный flock на .<name>.lock."""
        target = self._resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = _acquire_flock(target.parent / f".{target.name}.lock")
        try:
            yield target
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def load_strict(self, path: Path | None = None) -> WeightsOverrideDoc:
        """Читает файл весов строго через O_NOFOLLOW; при повреждении бросает WeightsCorruptError."""
        target = self._resolve_path(path)
        try:
            _ = _lstat_regular(target)
        except FileNotFoundError:
            return WeightsOverrideDoc.empty()
        return _read_doc_nofollow(target, int(_read_num(_MAX_BYTES_SPEC)))

    def mutate(self, path: Path | None, mutator: Callable[[WeightsOverrideDoc], WeightsOverrideDoc | Mapping[str, Any]]) -> WeightsOverrideDoc:
        """Атомарно обновляет файл весов под flock; отказывает на битом файле."""
        with self.lock(path) as target:
            raw_next = mutator(self.load_strict(target))
            payload = raw_next.to_dict() if isinstance(raw_next, WeightsOverrideDoc) else raw_next
            next_doc = validate_weights_document(payload)
            _write_doc_atomic(target, next_doc, int(_read_num(_MAX_BYTES_SPEC)))
            return next_doc

    def repair(self, path: Path | None = None) -> Path:
        """Архивирует битый файл/симлинк в .corrupt и атомарно записывает пустой v1 JSON."""
        with self.lock(path) as target:
            backup = target
            if os.path.lexists(target):
                backup = _backup_corrupt_path(target)
                os.replace(target, backup)
                _fsync_dir(target.parent)
            _write_doc_atomic(target, WeightsOverrideDoc.empty(), int(_read_num(_MAX_BYTES_SPEC)))
            return backup

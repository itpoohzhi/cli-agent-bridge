"""Жизненный цикл модели авто-каталога (architecture-spec §4.1).

Модуль содержит:

* закрытую таблицу переходов ``(статус, событие) -> новый статус``;
* pure-функцию :func:`transition` (запись неизменяема, недопустимый переход
  поднимает :class:`LifecycleError` и ничего не меняет);
* :class:`LifecycleRegistry` — хранилище записей с атомарным persist
  (tmp -> fsync -> os.replace под ``flock`` на соседнем lock-файле).

Эксплуатационные параметры (бэкоффы, лимиты) не зашиты в код: они читаются из
env через :meth:`LifecycleConfig.from_env` с безопасными значениями по умолчанию.
Имён вендоров/провайдеров модуль не содержит.
"""

from __future__ import annotations

import dataclasses
import fcntl
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

# --------------------------------------------------------------------------- #
# Статусы
# --------------------------------------------------------------------------- #

STATUS_DISCOVERED = "discovered"
STATUS_QUARANTINE = "quarantine"
STATUS_PROBING = "probing"
STATUS_CONFIRMED = "confirmed"
STATUS_QUARANTINE_FAILED = "quarantine_failed"
STATUS_STALE = "stale"
STATUS_DISABLED = "disabled"
STATUS_REJECTED = "rejected"

STATUSES: Tuple[str, ...] = (
    STATUS_DISCOVERED,
    STATUS_QUARANTINE,
    STATUS_PROBING,
    STATUS_CONFIRMED,
    STATUS_QUARANTINE_FAILED,
    STATUS_STALE,
    STATUS_DISABLED,
    STATUS_REJECTED,
)

# Отдаются как quarantine, допустимы только для открытых ролей.
QUARANTINE_LIKE: Tuple[str, ...] = (
    STATUS_QUARANTINE,
    STATUS_PROBING,
    STATUS_QUARANTINE_FAILED,
    STATUS_STALE,
)
# Статусы, попадающие в скомпилированный каталог.
IN_CATALOG: Tuple[str, ...] = (STATUS_CONFIRMED,) + QUARANTINE_LIKE
# Статусы, для которых доступны открытые роли (worker/explorer/adhoc/probe).
OPEN_ROLE_STATUSES: Tuple[str, ...] = IN_CATALOG

# --------------------------------------------------------------------------- #
# События
# --------------------------------------------------------------------------- #

EVENT_DISCOVERED_OK = "discovered_ok"
EVENT_INVALID_RECORD = "invalid_record"
EVENT_PROBE_START = "probe_start"
EVENT_PROBE_PASS = "probe_pass"
EVENT_PROBE_FAIL = "probe_fail"
EVENT_PROBE_INCONCLUSIVE = "probe_inconclusive"
EVENT_FINGERPRINT_CHANGED = "fingerprint_changed"
EVENT_MISSING = "missing"
EVENT_SEEN = "seen"
EVENT_MANIFEST_CHANGED = "manifest_changed"
EVENT_FORCE = "force"

EVENTS: Tuple[str, ...] = (
    EVENT_DISCOVERED_OK,
    EVENT_INVALID_RECORD,
    EVENT_PROBE_START,
    EVENT_PROBE_PASS,
    EVENT_PROBE_FAIL,
    EVENT_PROBE_INCONCLUSIVE,
    EVENT_FINGERPRINT_CHANGED,
    EVENT_MISSING,
    EVENT_SEEN,
    EVENT_MANIFEST_CHANGED,
    EVENT_FORCE,
)

# Закрытая таблица переходов. Для ``missing`` целевой статус зависит от счётчика
# (см. ``_apply_missing``), в таблице отражена только допустимость пары.
# ``seen`` допустим везде, кроме ``rejected``; вне ``disabled`` статус не меняет.
_TABLE: Dict[Tuple[str, str], str] = {
    (STATUS_DISCOVERED, EVENT_DISCOVERED_OK): STATUS_QUARANTINE,
    (STATUS_DISCOVERED, EVENT_INVALID_RECORD): STATUS_REJECTED,
    (STATUS_QUARANTINE, EVENT_PROBE_START): STATUS_PROBING,
    (STATUS_QUARANTINE_FAILED, EVENT_PROBE_START): STATUS_PROBING,
    (STATUS_STALE, EVENT_PROBE_START): STATUS_PROBING,
    (STATUS_QUARANTINE_FAILED, EVENT_FORCE): STATUS_PROBING,
    (STATUS_PROBING, EVENT_PROBE_PASS): STATUS_CONFIRMED,
    (STATUS_PROBING, EVENT_PROBE_FAIL): STATUS_QUARANTINE_FAILED,
    (STATUS_PROBING, EVENT_PROBE_INCONCLUSIVE): STATUS_QUARANTINE,
    (STATUS_CONFIRMED, EVENT_FINGERPRINT_CHANGED): STATUS_STALE,
    (STATUS_CONFIRMED, EVENT_MISSING): STATUS_CONFIRMED,
    (STATUS_QUARANTINE, EVENT_MISSING): STATUS_QUARANTINE,
    (STATUS_DISABLED, EVENT_SEEN): STATUS_DISCOVERED,
    (STATUS_REJECTED, EVENT_MANIFEST_CHANGED): STATUS_DISCOVERED,
}
for _st in STATUSES:
    if _st not in (STATUS_REJECTED, STATUS_DISABLED):
        _TABLE[(_st, EVENT_SEEN)] = _st

TRANSITIONS: Mapping[Tuple[str, str], str] = dict(_TABLE)

SCHEMA = "model-lifecycle/1"


class LifecycleError(ValueError):
    """Недопустимый переход, некорректный payload или повреждённое состояние."""


# --------------------------------------------------------------------------- #
# Конфигурация
# --------------------------------------------------------------------------- #

ENV_RETRY_BACKOFF = "BRIDGE_PROBE_RETRY_BACKOFF_S"
ENV_RATE_LIMITED_BACKOFF = "BRIDGE_PROBE_RATE_LIMITED_BACKOFF_S"
ENV_MISS_LIMIT = "BRIDGE_DISCOVERY_MISS_LIMIT"
ENV_HISTORY_MAX = "BRIDGE_CATALOG_HISTORY_MAX"

_DEFAULT_RETRY_BACKOFF: Tuple[float, ...] = (300.0, 1800.0, 7200.0)
_DEFAULT_RATE_LIMITED_BACKOFF = 900.0
_DEFAULT_MISS_LIMIT = 3
_DEFAULT_HISTORY_MAX = 20


def _parse_float(raw: Optional[str], default: float) -> float:
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except ValueError:
        return default
    return value if value >= 0 else default


def _parse_int(raw: Optional[str], default: int) -> int:
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip())
    except ValueError:
        return default
    return value if value >= 1 else default


def _parse_backoff(raw: Optional[str], default: Tuple[float, ...]) -> Tuple[float, ...]:
    if raw is None or not str(raw).strip():
        return default
    out: List[float] = []
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = float(part)
        except ValueError:
            return default
        if value < 0:
            return default
        out.append(value)
    return tuple(out) if out else default


@dataclasses.dataclass(frozen=True)
class LifecycleConfig:
    """Параметры жизненного цикла (все настраиваются через env)."""

    retry_backoff_s: Tuple[float, ...] = _DEFAULT_RETRY_BACKOFF
    rate_limited_backoff_s: float = _DEFAULT_RATE_LIMITED_BACKOFF
    miss_limit: int = _DEFAULT_MISS_LIMIT
    history_max: int = _DEFAULT_HISTORY_MAX

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "LifecycleConfig":
        source = os.environ if env is None else env
        return cls(
            retry_backoff_s=_parse_backoff(
                source.get(ENV_RETRY_BACKOFF), _DEFAULT_RETRY_BACKOFF
            ),
            rate_limited_backoff_s=_parse_float(
                source.get(ENV_RATE_LIMITED_BACKOFF), _DEFAULT_RATE_LIMITED_BACKOFF
            ),
            miss_limit=_parse_int(source.get(ENV_MISS_LIMIT), _DEFAULT_MISS_LIMIT),
            history_max=_parse_int(source.get(ENV_HISTORY_MAX), _DEFAULT_HISTORY_MAX),
        )


# --------------------------------------------------------------------------- #
# Запись
# --------------------------------------------------------------------------- #


@dataclasses.dataclass(frozen=True)
class ModelRecord:
    provider_id: str
    model_id: str
    fingerprint_sha256: str
    status: str
    history: Tuple[Mapping[str, Any], ...] = ()
    miss_count: int = 0
    retry_after: float = 0.0
    failures: int = 0
    receipt_sha256: str = ""
    efforts_proven: Tuple[str, ...] = ()
    reason: str = ""

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.provider_id, self.model_id, self.fingerprint_sha256)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "fingerprint_sha256": self.fingerprint_sha256,
            "status": self.status,
            "history": [dict(h) for h in self.history],
            "miss_count": self.miss_count,
            "retry_after": self.retry_after,
            "failures": self.failures,
            "receipt_sha256": self.receipt_sha256,
            "efforts_proven": list(self.efforts_proven),
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelRecord":
        try:
            status = str(data["status"])
            if status not in STATUSES:
                raise LifecycleError("unknown status: %r" % status)
            history = tuple(dict(h) for h in data.get("history", ()))
            return cls(
                provider_id=str(data["provider_id"]),
                model_id=str(data["model_id"]),
                fingerprint_sha256=str(data["fingerprint_sha256"]),
                status=status,
                history=history,
                miss_count=int(data.get("miss_count", 0)),
                retry_after=float(data.get("retry_after", 0.0)),
                failures=int(data.get("failures", 0)),
                receipt_sha256=str(data.get("receipt_sha256", "")),
                efforts_proven=tuple(str(e) for e in data.get("efforts_proven", ())),
                reason=str(data.get("reason", "")),
            )
        except LifecycleError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise LifecycleError("invalid record: %s" % exc) from exc


def new_record(provider_id: str, model_id: str, fingerprint_sha256: str) -> ModelRecord:
    """Новая запись в статусе ``discovered``."""
    return ModelRecord(
        provider_id=provider_id,
        model_id=model_id,
        fingerprint_sha256=fingerprint_sha256,
        status=STATUS_DISCOVERED,
    )


# --------------------------------------------------------------------------- #
# transition
# --------------------------------------------------------------------------- #


def _iso(now: float) -> str:
    return datetime.fromtimestamp(now, tz=timezone.utc).isoformat()


def _append_history(
    record: ModelRecord, new_status: str, event: str, now: float, cap: int
) -> Tuple[Mapping[str, Any], ...]:
    entry = {"from": record.status, "to": new_status, "at": _iso(now), "event": event}
    history = record.history + (entry,)
    if cap > 0 and len(history) > cap:
        history = history[-cap:]
    return history


def probe_due(record: ModelRecord, now: float) -> bool:
    """Истёк ли ``retry_after`` (для планировщика пробника)."""
    return now >= record.retry_after


def transition(
    record: ModelRecord,
    event: str,
    *,
    now: float,
    payload: Optional[Mapping[str, Any]] = None,
    config: Optional[LifecycleConfig] = None,
) -> ModelRecord:
    """Pure-переход по закрытой таблице; недопустимый -> :class:`LifecycleError`."""
    cfg = config if config is not None else LifecycleConfig()
    data: Mapping[str, Any] = payload or {}
    target = _TABLE.get((record.status, event))
    if target is None:
        raise LifecycleError(
            "illegal transition: status=%r event=%r" % (record.status, event)
        )

    def _moved(**changes: Any) -> ModelRecord:
        new_status = changes.pop("status", target)
        if new_status != record.status:
            changes["history"] = _append_history(
                record, new_status, event, now, cfg.history_max
            )
        return dataclasses.replace(record, status=new_status, **changes)

    if event == EVENT_DISCOVERED_OK:
        return _moved(miss_count=0)

    if event == EVENT_INVALID_RECORD:
        return _moved(reason=str(data.get("reason", "")))

    if event in (EVENT_PROBE_START, EVENT_FORCE):
        forced = event == EVENT_FORCE or bool(data.get("force"))
        if (
            record.status == STATUS_QUARANTINE_FAILED
            and not forced
            and not probe_due(record, now)
        ):
            raise LifecycleError(
                "probe_start before retry_after (%.0f < %.0f)"
                % (now, record.retry_after)
            )
        return _moved()

    if event == EVENT_PROBE_PASS:
        receipt = str(data.get("receipt_sha256", "") or "")
        efforts = tuple(str(e) for e in (data.get("efforts_proven") or ()))
        if not receipt or not efforts:
            raise LifecycleError(
                "probe_pass requires receipt_sha256 and non-empty efforts_proven"
            )
        return _moved(
            receipt_sha256=receipt,
            efforts_proven=efforts,
            failures=0,
            retry_after=0.0,
            miss_count=0,
            reason="",
        )

    if event == EVENT_PROBE_FAIL:
        failures = record.failures + 1
        backoff = cfg.retry_backoff_s
        delay = backoff[min(failures - 1, len(backoff) - 1)] if backoff else 0.0
        return _moved(
            failures=failures,
            retry_after=now + delay,
            reason=str(data.get("reason", "")),
        )

    if event == EVENT_PROBE_INCONCLUSIVE:
        rate_limited = bool(data.get("rate_limited"))
        if rate_limited:
            delay = cfg.rate_limited_backoff_s
        else:
            backoff = cfg.retry_backoff_s
            delay = backoff[0] if backoff else cfg.rate_limited_backoff_s
        return _moved(retry_after=now + delay, reason=str(data.get("reason", "")))

    if event == EVENT_FINGERPRINT_CHANGED:
        return _moved(reason=str(data.get("reason", "fingerprint_changed")))

    if event == EVENT_MISSING:
        misses = record.miss_count + 1
        if misses >= cfg.miss_limit:
            return _moved(status=STATUS_DISABLED, miss_count=misses)
        return _moved(miss_count=misses)

    if event == EVENT_SEEN:
        return _moved(miss_count=0)

    if event == EVENT_MANIFEST_CHANGED:
        return _moved(reason="", miss_count=0)

    raise LifecycleError("unhandled event: %r" % event)  # pragma: no cover


# --------------------------------------------------------------------------- #
# Реестр
# --------------------------------------------------------------------------- #

Key = Tuple[str, str, str]


class LifecycleRegistry:
    """Хранилище записей с ключом ``(provider_id, model_id, fingerprint)``."""

    def __init__(
        self,
        records: Optional[Iterable[ModelRecord]] = None,
        config: Optional[LifecycleConfig] = None,
    ) -> None:
        self.config = config if config is not None else LifecycleConfig()
        self._records: Dict[Key, ModelRecord] = {}
        for rec in records or ():
            self._records[rec.key] = rec

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, key: object) -> bool:
        return key in self._records

    def get(self, key: Key) -> Optional[ModelRecord]:
        return self._records.get(key)

    def register(
        self, provider_id: str, model_id: str, fingerprint_sha256: str
    ) -> ModelRecord:
        """Вернуть существующую запись либо создать ``discovered``."""
        key = (provider_id, model_id, fingerprint_sha256)
        rec = self._records.get(key)
        if rec is None:
            rec = new_record(provider_id, model_id, fingerprint_sha256)
            self._records[key] = rec
        return rec

    def apply(
        self,
        key: Key,
        event: str,
        now: float,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> ModelRecord:
        rec = self._records.get(key)
        if rec is None:
            raise LifecycleError("unknown record: %r" % (key,))
        new = transition(rec, event, now=now, payload=payload, config=self.config)
        self._records[key] = new
        return new

    def current_status(
        self, provider_id: str, model_id: str, current_fingerprint: str
    ) -> Optional[str]:
        rec = self._records.get((provider_id, model_id, current_fingerprint))
        return rec.status if rec is not None else None

    def records(self) -> List[ModelRecord]:
        return [self._records[k] for k in sorted(self._records)]

    # -- persistence ------------------------------------------------------- #

    def to_json(self) -> str:
        doc = {"schema": SCHEMA, "records": [r.to_dict() for r in self.records()]}
        return json.dumps(doc, sort_keys=True, ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_json(
        cls, text: str, config: Optional[LifecycleConfig] = None
    ) -> "LifecycleRegistry":
        try:
            doc = json.loads(text)
        except ValueError as exc:
            raise LifecycleError("corrupt lifecycle state: %s" % exc) from exc
        if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
            raise LifecycleError("corrupt lifecycle state: bad schema")
        items = doc.get("records")
        if not isinstance(items, list):
            raise LifecycleError("corrupt lifecycle state: records must be a list")
        recs = []
        for item in items:
            if not isinstance(item, dict):
                raise LifecycleError("corrupt lifecycle state: bad record")
            recs.append(ModelRecord.from_dict(item))
        return cls(recs, config=config)

    @classmethod
    def load(
        cls, path: "str | os.PathLike[str]", config: Optional[LifecycleConfig] = None
    ) -> "LifecycleRegistry":
        """Загрузить состояние; нет файла -> пустой реестр; мусор -> LifecycleError."""
        p = os.fspath(path)
        if not os.path.exists(p):
            return cls(config=config)
        with _locked(p, shared=True):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except FileNotFoundError:
                return cls(config=config)
            except (OSError, UnicodeDecodeError) as exc:
                raise LifecycleError("cannot read lifecycle state: %s" % exc) from exc
        return cls.from_json(text, config=config)

    def save(self, path: "str | os.PathLike[str]") -> None:
        """Атомарная запись: tmp -> fsync -> os.replace под flock."""
        p = os.fspath(path)
        directory = os.path.dirname(os.path.abspath(p))
        os.makedirs(directory, exist_ok=True)
        payload = self.to_json().encode("utf-8")
        with _locked(p, shared=False):
            tmp = "%s.tmp.%d" % (p, os.getpid())
            try:
                fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
                try:
                    os.write(fd, payload)
                    os.fsync(fd)
                finally:
                    os.close(fd)
                os.replace(tmp, p)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            _fsync_dir(directory)


class _locked:
    """flock на соседнем ``<path>.lock`` (сам файл состояния заменяется replace)."""

    def __init__(self, path: str, *, shared: bool) -> None:
        self._lock_path = path + ".lock"
        self._shared = shared
        self._fd: Optional[int] = None

    def __enter__(self) -> "_locked":
        directory = os.path.dirname(os.path.abspath(self._lock_path))
        os.makedirs(directory, exist_ok=True)
        self._fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(self._fd, fcntl.LOCK_SH if self._shared else fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            finally:
                os.close(self._fd)
                self._fd = None


def _fsync_dir(directory: str) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)

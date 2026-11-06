"""Карантинный ролевой гейт моста (catalog-lock/1, QT-2, QT-7, QT-10).

Чистый модуль без ввода-вывода в горячем пути: решение принимается по
статусу модели из сайдкара ``catalog.lock.json`` и по роли вызывающего
(часть ``X-Subagent-Id`` до первого ``-``). Имён вендоров и моделей здесь нет:
семейство и статус приходят только из сайдкара.

Правила:
* роль ``open`` (worker, explorer, adhoc, probe) допускается и к карантину;
* всё остальное (в т.ч. ``quorum`` и неизвестные роли) — ``gated``:
  допускается только статус ``confirmed`` (default-deny);
* модель, которой нет в сайдкаре, разрешена (прежнее legacy-поведение).

Классы ролей настраиваются конструктором или env ``POL_ROLE_CLASSES``
(JSON ``{"open": [...], "quorum": [...]}``).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, Mapping, Optional, Union

STATUS_CONFIRMED = "confirmed"
STATUS_QUARANTINE = "quarantine"
STATUS_PROBING = "probing"
STATUS_QUARANTINE_FAILED = "quarantine_failed"
STATUS_STALE = "stale"
STATUS_DISABLED = "disabled"
STATUS_REJECTED = "rejected"

#: Статусы, при которых модель не прошла аттестацию, но не выведена из оборота.
UNCONFIRMED_STATUSES: FrozenSet[str] = frozenset(
    {STATUS_QUARANTINE, STATUS_PROBING, STATUS_QUARANTINE_FAILED, STATUS_STALE}
)
#: Статусы, допустимые для роли класса ``open``.
OPEN_ALLOWED_STATUSES: FrozenSet[str] = (
    frozenset({STATUS_CONFIRMED}) | UNCONFIRMED_STATUSES
)

CLASS_OPEN = "open"
CLASS_QUORUM = "quorum"
CLASS_GATED = "gated"

ROLE_ADHOC = "adhoc"

ENV_ROLE_CLASSES = "POL_ROLE_CLASSES"

DEFAULT_OPEN_ROLES: FrozenSet[str] = frozenset(
    {"worker", "explorer", ROLE_ADHOC, "probe"}
)
DEFAULT_QUORUM_ROLES: FrozenSet[str] = frozenset(
    {"judge", "hats", "answer-review", "council"}
)

DENY_REASON = "model_quarantined"
DENY_HTTP = 403


def _norm_role(role: Optional[str]) -> str:
    return (role or "").strip().lower()


@dataclass(frozen=True)
class RoleClasses:
    """Классификация ролей: open / quorum / gated (всё остальное)."""

    open: FrozenSet[str] = DEFAULT_OPEN_ROLES
    quorum: FrozenSet[str] = DEFAULT_QUORUM_ROLES

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoleClasses":
        def _set(key: str, default: FrozenSet[str]) -> FrozenSet[str]:
            if key not in data:
                return default
            return frozenset(_norm_role(x) for x in data[key] if _norm_role(x))

        return cls(
            open=_set("open", DEFAULT_OPEN_ROLES),
            quorum=_set("quorum", DEFAULT_QUORUM_ROLES),
        )

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "RoleClasses":
        env = os.environ if environ is None else environ
        raw = env.get(ENV_ROLE_CLASSES, "").strip()
        if not raw:
            return cls()
        try:
            data = json.loads(raw)
        except ValueError:
            return cls()
        if not isinstance(data, dict):
            return cls()
        return cls.from_dict(data)

    def class_of(self, role: Optional[str]) -> str:
        """Класс роли. Пустая роль — ``open`` (adhoc); неизвестная — ``gated``."""
        name = _norm_role(role) or ROLE_ADHOC
        if name in self.open:
            return CLASS_OPEN
        if name in self.quorum:
            return CLASS_QUORUM
        return CLASS_GATED

    def is_open(self, role: Optional[str]) -> bool:
        return self.class_of(role) == CLASS_OPEN


def role_from_subagent_id(subagent_id: Optional[str]) -> str:
    """Роль = часть ``X-Subagent-Id`` до первого ``-``; пусто/None => ``adhoc``."""
    value = (subagent_id or "").strip()
    if not value:
        return ROLE_ADHOC
    head = value.split("-", 1)[0].strip().lower()
    return head or ROLE_ADHOC


def status_permitted(status: Optional[str], role_class: str) -> bool:
    """Допустим ли статус модели для класса роли (default-deny)."""
    if status == STATUS_CONFIRMED:
        return True
    if role_class == CLASS_OPEN:
        return status in OPEN_ALLOWED_STATUSES
    return False


class SidecarView:
    """Read-only представление сайдкара ``catalog-lock/1``."""

    def __init__(self, data: Optional[Mapping[str, Any]] = None) -> None:
        self._data: Dict[str, Any] = dict(data or {})
        models = self._data.get("models")
        self._models: Dict[str, Any] = dict(models) if isinstance(models, dict) else {}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SidecarView":
        return cls(data)

    @classmethod
    def from_path(cls, path: Union[str, "os.PathLike[str]"]) -> "SidecarView":
        """Читает сайдкар. Файла нет — пустое представление (legacy: всё разрешено)."""
        try:
            with open(os.fspath(path), "rb") as fh:
                raw = fh.read()
        except FileNotFoundError:
            return cls({})
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("catalog lock must be a JSON object")
        return cls(data)

    @property
    def raw(self) -> Dict[str, Any]:
        return self._data

    @property
    def models(self) -> Dict[str, Any]:
        return self._models

    def has(self, model_id: str) -> bool:
        return model_id in self._models

    def entry(self, model_id: str) -> Optional[Mapping[str, Any]]:
        value = self._models.get(model_id)
        return value if isinstance(value, dict) else None

    def status_of(self, model_id: str) -> Optional[str]:
        entry = self.entry(model_id)
        if entry is None:
            return None
        status = entry.get("status")
        return status if isinstance(status, str) else ""


@dataclass(frozen=True)
class Allow:
    allowed: bool = True


@dataclass(frozen=True)
class Deny:
    model: str
    status: str
    reason: str = DENY_REASON
    http: int = DENY_HTTP
    allowed: bool = False

    def body(self) -> Dict[str, Any]:
        return deny_body(self.model, self.status)


GateDecision = Union[Allow, Deny]


def deny_body(model: str, status: str) -> Dict[str, Any]:
    """Тело ошибки OpenAI-формата для отказа гейта."""
    return {"error": {"type": DENY_REASON, "model": model, "status": status}}


def gate(
    model_id: str,
    subagent_id: Optional[str],
    sidecar: SidecarView,
    role_classes: Optional[RoleClasses] = None,
) -> GateDecision:
    """Решение гейта: ``Allow`` или ``Deny`` (403 ``model_quarantined``)."""
    classes = role_classes if role_classes is not None else RoleClasses.from_env()
    if not sidecar.has(model_id):
        return Allow()
    status = sidecar.status_of(model_id) or ""
    role_class = classes.class_of(role_from_subagent_id(subagent_id))
    if status_permitted(status, role_class):
        return Allow()
    return Deny(model=model_id, status=status)


def roles_summary(classes: RoleClasses) -> Dict[str, Iterable[str]]:
    """Отладочная сводка классов ролей (детерминированный порядок)."""
    return {"open": sorted(classes.open), "quorum": sorted(classes.quorum)}

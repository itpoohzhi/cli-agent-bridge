from __future__ import annotations

from bisect import bisect_left
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import cast

from core.route_health_policy import normalize_model_route

FLAG_EFFORT_CATALOG = "BRIDGE_EFFORT_CATALOG_ENABLED"
EFFORT_LEVELS: tuple[str, ...] = ("minimal", "low", "medium", "high", "xhigh", "max")
EFFORT_ORDER: tuple[str, ...] = ("off", *EFFORT_LEVELS, "ultra")
_RANK = {name: rank for rank, name in enumerate(EFFORT_ORDER)}
DEFAULT_LOG_EFFORT_MAX_CHARS = 32


def clamp_effort_downward(
    candidate: str, allowed: Sequence[str], default: str
) -> tuple[str, bool]:
    """Кламп вниз к allowed; True — был кламп."""
    key = candidate.lower()
    named = {item.lower(): item for item in reversed(allowed)}
    ranked = {_RANK[name]: item for name, item in named.items() if name in _RANK}
    try:
        return named[key], False
    except KeyError:
        pass
    try:
        ranks = sorted(ranked)
        return ranked[ranks[max(bisect_left(ranks, _RANK[key]) - 1, 0)]], True
    except (KeyError, IndexError):
        return default, True


@dataclass(frozen=True, slots=True)
class ModelEffortSpec:
    """Effort записи каталога."""

    efforts: tuple[str, ...] = ()
    default: str | None = None

    @classmethod
    def from_catalog_entry(cls, entry: object) -> ModelEffortSpec:
        """Уровни шкалы без дублей, по рангу."""
        fields = cast(Mapping[str, object], entry if isinstance(entry, Mapping) else {})
        raw = fields.get("efforts")
        listed = cast(Sequence[object], raw if isinstance(raw, (list, tuple)) else ())
        levels = {item.strip().lower() for item in listed if isinstance(item, str)}
        efforts = tuple(sorted(levels & _RANK.keys(), key=_RANK.__getitem__))
        return cls(efforts, _declared_default(fields.get("default_effort"), efforts))

    def pinned_to(self, effort: str) -> ModelEffortSpec:
        """Спека алиаса с одним уровнем."""
        allowed = self.efforts or (effort,)
        fallback = next(filter(None, (self.default, *allowed)), allowed[0])
        level, _ = clamp_effort_downward(effort, allowed, fallback)
        return replace(self, efforts=(level,), default=level)


def _declared_default(raw: object, efforts: tuple[str, ...]) -> str | None:
    name = raw.strip().lower() if isinstance(raw, str) else ""
    return next((item for item in efforts if item == name), None)


@dataclass(frozen=True, slots=True)
class ModelEffortCardFields:
    default_effort: str | None
    supported_efforts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EffortResolution:
    """`apply=False` — дословно."""

    value: str | None = None
    apply: bool = False
    clamped_from: str | None = None


def resolve_model_effort_fields(
    model_id: str, specs: Mapping[str, ModelEffortSpec]
) -> ModelEffortCardFields | None:
    """Поля карточки; `None` — efforts не объявлены."""
    spec = specs.get(model_id, ModelEffortSpec())
    return ModelEffortCardFields(spec.default, spec.efforts) if spec.efforts else None


def resolve_alias_effort(
    raw_id: str,
    catalogue: Mapping[str, object],
    suffixes: Collection[str],
    enabled: bool,
) -> tuple[str, str] | None:
    """`<id>-<effort>` -> `(id, effort)`; точная запись приоритетнее."""
    if not enabled or not raw_id.strip():
        return None
    route = normalize_model_route(raw_id, allowed_suffixes=suffixes)
    known = (
        route.alias_applied
        and raw_id not in catalogue
        and route.canonical_model in catalogue
    )
    return (route.canonical_model, route.reasoning_effort or "") if known else None


def catalog_effort_specs(
    models: object, aliases: Mapping[str, tuple[str, str]]
) -> dict[str, ModelEffortSpec]:
    """Спеки моделей и алиасов `alias -> (base, effort)`."""
    entries = cast(
        Mapping[object, object], models if isinstance(models, Mapping) else {}
    )
    specs = {
        str(k): s
        for k, v in entries.items()
        if (s := ModelEffortSpec.from_catalog_entry(v)).efforts
    }
    without_efforts = entries.keys() - specs.keys()
    pins = {
        alias: specs.get(base, ModelEffortSpec()).pinned_to(effort)
        for alias, (base, effort) in aliases.items()
        if base not in without_efforts
    }
    return {**specs, **pins}


def _clamped_resolution(
    requested: object, alias: str, spec: ModelEffortSpec
) -> EffortResolution:
    """Кламп явного effort либо алиаса."""
    asked = requested.strip() if isinstance(requested, str) else ""
    text = asked or (alias if requested is None else str(requested))
    fallback = next(filter(None, (spec.default, *spec.efforts)))
    value, clamped = clamp_effort_downward(text, spec.efforts, fallback)
    verbatim = requested == value and not clamped
    return (
        EffortResolution()
        if verbatim
        else EffortResolution(value, True, text if clamped else None)
    )


def resolve_passthrough_effort(
    requested: object, alias_effort: str | None, spec: ModelEffortSpec, *, enabled: bool
) -> EffortResolution:
    """Passthrough `reasoning_effort`: кламп за флагом."""
    alias = alias_effort.strip() if isinstance(alias_effort, str) else ""
    if enabled and spec.efforts and (requested is not None or alias):
        return _clamped_resolution(
            requested, alias, spec.pinned_to(alias) if alias else spec
        )
    legacy = alias and requested is None
    return EffortResolution(alias, True) if legacy else EffortResolution()


def sanitize_effort_for_log(
    raw: object, limit: int = DEFAULT_LOG_EFFORT_MAX_CHARS
) -> str:
    """Printable-срез effort до `limit` для журнала."""
    return "".join(filter(str.isprintable, str(raw)[: limit * 2]))[:limit]


def describe_clamp(
    label: str,
    requested: object,
    applied: object,
    model_id: str,
    limit: int = DEFAULT_LOG_EFFORT_MAX_CHARS,
) -> str:
    """Строка журнала о клампе effort."""
    asked, used, model = (
        sanitize_effort_for_log(v, limit) for v in (requested, applied, model_id)
    )
    return f"clamp {label} '{asked}' -> '{used}' for model {model}"

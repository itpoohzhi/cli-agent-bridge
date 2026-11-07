from __future__ import annotations

from bisect import bisect_left
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace

FLAG_EFFORT_CATALOG = "BRIDGE_EFFORT_CATALOG_ENABLED"
EFFORT_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
EFFORT_ORDER = (*EFFORT_LEVELS, "ultra")
_RANK = {name.lower(): rank for rank, name in enumerate(EFFORT_ORDER)}
DEFAULT_LOG_EFFORT_MAX_CHARS = 32

def clamp_effort_downward(candidate: str, allowed: Sequence[str], default: str) -> tuple[str, bool]:
    """Кламп effort вниз к allowed; флаг — был ли кламп."""
    key = candidate.lower()
    exact = next((item for item in allowed if item.lower() == key), None)
    rank = _RANK.get(key)
    if exact is not None:
        return exact, False
    if rank is None:  # уровень вне шкалы: остаётся умолчание
        return default, True
    by_rank: dict[int, str] = {}
    for item in reversed(allowed):
        found = _RANK.get(item.lower())
        if found is not None:
            by_rank[found] = item
    ranks = sorted(by_rank)
    if not ranks:
        return default, True
    near = ranks[max(bisect_left(ranks, rank) - 1, 0)]
    return by_rank[near], True
@dataclass(frozen=True, slots=True)
class ModelEffortSpec:
    """Effort записи каталога: допустимые и умолчание."""
    efforts: tuple[str, ...] = ()
    default: str | None = None

    @classmethod
    def from_catalog_entry(cls, entry: object) -> ModelEffortSpec:
        """Спека из записи каталога: efforts по шкале, умолчание — только из них."""
        fields: Mapping[str, object] = entry if isinstance(entry, Mapping) else {}
        raw = fields.get("efforts")
        listed = tuple(str(item) for item in raw) if isinstance(raw, (list, tuple)) else ()
        ranked = all(item.lower() in _RANK for item in listed)
        ordered = tuple(sorted(dict.fromkeys(listed), key=lambda i: _RANK.get(i.lower(), 0)))
        efforts = ordered if ranked else listed
        return cls(efforts, _declared_default(fields.get("default_effort"), efforts, ranked))

    def pinned_to(self, effort: str) -> ModelEffortSpec:
        """Спека алиаса: единственный уровень, полученный клампом вниз."""
        base = self.efforts if self.efforts else (effort,)
        fallback = self.default if self.default else base[0]
        level, _ = clamp_effort_downward(effort, base, fallback)
        return replace(self, efforts=(level,), default=level)

def _declared_default(raw: object, efforts: tuple[str, ...], ranked: bool) -> str | None:
    """Умолчание записи: строка из объявленных efforts, иначе не заявлено."""
    default = raw if isinstance(raw, str) else None
    allowed = {item.lower() for item in efforts}
    outside = all((ranked, (default or "").lower() not in allowed))
    return None if outside else default
@dataclass(frozen=True, slots=True)
class ModelEffortCardFields:
    """Effort-поля карточки `/v1/models`; `default_effort=None` — умолчание не заявлено."""
    default_effort: str | None
    supported_efforts: tuple[str, ...]
@dataclass(frozen=True, slots=True)
class EffortResolution:
    """Решение passthrough: `apply=False` — дословно, иначе пишется `value`."""
    value: str | None = None
    apply: bool = False
    clamped_from: str | None = None

def resolve_model_effort_fields(model_id: str, specs: Mapping[str, ModelEffortSpec]) -> ModelEffortCardFields | None:
    """Поля карточки из спек; `None` — спеки нет или efforts не объявлены."""
    spec = specs.get(model_id, ModelEffortSpec())
    fields = ModelEffortCardFields(spec.default, spec.efforts)
    return fields if spec.efforts else None

def resolve_alias_effort(raw_id: str, catalogue: Mapping[str, object], suffixes: Collection[str], enabled: bool) -> tuple[str, str] | None:
    """Алиас `<id>-<effort>` -> `(id, effort)`; точная запись приоритетнее."""
    base, _, suffix = raw_id.rpartition("-")
    names = set(catalogue)
    fresh = not names.issuperset({raw_id})
    names.discard(raw_id)
    known = all((enabled, fresh, names.issuperset({base}), set(suffixes).issuperset({suffix})))
    return (base, suffix) if known else None

def canonical_model_id(raw_id: str, catalogue: Mapping[str, object], suffixes: Collection[str], enabled: bool) -> str:
    """Базовый id модели: алиас разворачивается, иначе `raw_id`."""
    found = resolve_alias_effort(raw_id, catalogue, suffixes, enabled)
    return found[0] if found else raw_id

def catalog_effort_specs(models: object, aliases: Mapping[str, tuple[str, str]]) -> dict[str, ModelEffortSpec]:
    """Спеки моделей с efforts и алиасов `alias -> (base, effort)`."""
    entries = models if isinstance(models, Mapping) else {}
    specs = {str(k): s for k, v in entries.items() if (s := ModelEffortSpec.from_catalog_entry(v)).efforts}
    names, declared = set(entries), set(specs)
    pins: dict[str, ModelEffortSpec] = {}
    for alias, (base, effort) in aliases.items():
        orphan = not names.issuperset({base})
        if any((orphan, declared.issuperset({base}))):
            pins[alias] = specs.get(base, ModelEffortSpec()).pinned_to(effort)
    return {**specs, **pins}

def _clamped_resolution(text: str, spec: ModelEffortSpec, requested: object) -> EffortResolution:
    """Кламп явного effort вниз к каталогу; нетронутый effort запроса остаётся дословным."""
    if not spec.efforts:
        return EffortResolution()
    fallback = spec.default if spec.default else spec.efforts[0]
    value, clamped = clamp_effort_downward(text, spec.efforts, fallback)
    asked = requested if isinstance(requested, str) else ""
    same = value.lower() == asked.lower()
    clean = asked.strip() == asked
    result = EffortResolution(value, True, text if clamped else None)
    return result if not all((same, clean, not clamped)) else EffortResolution()

def _legacy_resolution(requested: object, requested_text: str, alias_text: str) -> EffortResolution:
    """Без каталога effort: алиас без явного запроса уходит upstream дословно."""
    legacy = all((alias_text, not requested_text, requested is None))
    return EffortResolution(alias_text, True) if legacy else EffortResolution()

def resolve_passthrough_effort(requested: object, alias_effort: str | None, spec: ModelEffortSpec, *, enabled: bool) -> EffortResolution:
    """Нормализация `reasoning_effort` passthrough: алиас пинится, кламп вниз — за флагом."""
    req_text = requested.strip() if isinstance(requested, str) else ""
    alias_text = alias_effort.strip() if isinstance(alias_effort, str) else ""
    alias = alias_effort or ""
    spec = spec.pinned_to(alias) if all((enabled, alias, spec.efforts)) else spec
    text = req_text if req_text else alias_text
    active = all((enabled, spec.efforts, text))
    clamped = _clamped_resolution(text, spec, requested if req_text else None)
    return clamped if active else _legacy_resolution(requested, req_text, alias_text)
def sanitize_effort_for_log(raw: object, limit: int = DEFAULT_LOG_EFFORT_MAX_CHARS) -> str:
    """Effort для журнала: срез до фильтра управляющих символов, затем `limit`."""
    return "".join(filter(str.isprintable, str(raw)[: limit * 2]))[:limit]
def describe_clamp(label: str, requested: object, applied: object, model_id: str, limit: int = DEFAULT_LOG_EFFORT_MAX_CHARS) -> str:
    """Строка журнала о клампе effort; effort и model_id санитизируются."""
    asked, used = (sanitize_effort_for_log(v, limit) for v in (requested, applied))
    return f"clamp {label} '{asked}' -> '{used}' for model {sanitize_effort_for_log(model_id, limit)}"

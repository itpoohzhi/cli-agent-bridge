"""Этапы валидации манифеста с внедряемыми фабриками legacy DTO."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from re import Pattern
from typing import Generic, Protocol, TypeGuard, TypeVar, cast

from core.backend_adapter import KindConstraints, kind_constraints
from core.routing_schema import RoutingConfig, parse_routing


class _Defaults(Protocol):
    @property
    def priority(self) -> int: ...

    @property
    def max_concurrent(self) -> int: ...

    @property
    def timeout_s(self) -> float: ...


_D = TypeVar("_D", bound=_Defaults)
_R = TypeVar("_R")


@dataclass(frozen=True, slots=True)
class ManifestErrors:
    """Ошибки одного вызова в исходном порядке, без повторов."""

    items: list[str] = field(default_factory=list)

    def add(self, slug: str) -> None:
        if slug not in self.items:
            self.items.append(slug)


@dataclass(frozen=True, slots=True)
class ManifestInput:
    """Вход фасада; окружение захватывается вызывающим слоем."""

    doc: object
    kinds: Mapping[str, object] | None
    filename_stem: str | None
    env: Mapping[str, str]
    schema: Mapping[str, object] | None


@dataclass(frozen=True, slots=True)
class ManifestContext(Generic[_D]):
    """Контекст одного прохода, не сохраняемый между манифестами."""

    doc: Mapping[str, object]
    env: Mapping[str, str]
    defaults: _D
    errors: ManifestErrors


@dataclass(frozen=True, slots=True)
class ManifestHeader:
    """Нормализованная идентичность и ограничения вида провайдера."""

    provider_id: str
    kind: str
    owned_by: str
    enabled: bool
    required: bool
    priority: int
    constraints: KindConstraints
    kind_known: bool


@dataclass(frozen=True, slots=True)
class ManifestLimits:
    """Проверенные значения для фабрики LimitsConfig."""

    max_concurrent: int
    quota_group: str
    pin_required: bool
    timeout_s: float


@dataclass(frozen=True, slots=True)
class ManifestValidationPorts(Generic[_D, _R]):
    """Фабрики и схема передаются снаружи, обратного импорта хоста нет."""

    defaults: Callable[[Mapping[str, str]], _D]
    build: Callable[[ManifestHeader, ManifestContext[_D]], _R]
    result: Callable[[None, tuple[str, ...]], _R]
    load_schema: Callable[[], Mapping[str, object]]
    unknown_keys: Callable[[object, Mapping[str, object]], Sequence[str]]
    provider_id_pattern: Pattern[str]
    manifest_version: int


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def manifest_section(raw: object, errors: ManifestErrors) -> Mapping[str, object]:
    """Сохраняет legacy-семантику отсутствующей/null секции."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        errors.add("provider_manifest_invalid")
        return {}
    return cast(Mapping[str, object], raw)


def _schema_errors(
    request: ManifestInput, context: ManifestContext[_D],
    ports: ManifestValidationPorts[_D, _R],
) -> None:
    try:
        schema = request.schema if request.schema is not None else ports.load_schema()
        unknown = ports.unknown_keys(context.doc, schema)
    except (OSError, ValueError):
        unknown = ()
        context.errors.add("provider_schema_unavailable")
    if unknown:
        context.errors.add("provider_key_unknown")


def _provider_id(
    raw: object, stem: str | None, pattern: Pattern[str], errors: ManifestErrors,
) -> str:
    if (
        not isinstance(raw, str) or not pattern.fullmatch(raw)
        or (stem is not None and raw != stem)
    ):
        errors.add("provider_id_invalid")
    return raw if isinstance(raw, str) else ""


def _kind(
    raw: object, kinds: Mapping[str, object] | None, errors: ManifestErrors,
) -> tuple[str, KindConstraints, bool]:
    # Неизвестный вид: проверки ограничений вида не применимы.
    if not isinstance(raw, str) or not raw:
        errors.add("provider_kind_unknown")
        return "", KindConstraints(), False
    if kinds is not None:
        if raw not in kinds:
            errors.add("provider_kind_unknown")
            return raw, KindConstraints(), False
        return raw, kind_constraints(kinds, raw), True
    return raw, KindConstraints(), True


def _flags(doc: Mapping[str, object], errors: ManifestErrors) -> tuple[bool, bool]:
    flags = []
    for key, default in (("enabled", True), ("required", False)):
        value = doc.get(key, default)
        if not isinstance(value, bool):
            errors.add("provider_manifest_invalid")
            value = default
        flags.append(value)
    return flags[0], flags[1]


def _header(
    request: ManifestInput, context: ManifestContext[_D],
    ports: ManifestValidationPorts[_D, _R],
) -> ManifestHeader:
    doc, errors = context.doc, context.errors
    version = doc.get("manifest_version")
    if not _is_int(version) or version != ports.manifest_version:
        errors.add("provider_manifest_version_unsupported")
    provider_id = _provider_id(
        doc.get("provider_id"), request.filename_stem, ports.provider_id_pattern, errors,
    )
    kind, constraints, known = _kind(doc.get("kind"), request.kinds, errors)
    owned_by = doc.get("owned_by")
    if not isinstance(owned_by, str) or not owned_by:
        errors.add("provider_manifest_invalid")
        owned_by = ""
    enabled, required = _flags(doc, errors)
    priority = doc.get("priority", context.defaults.priority)
    if not _is_int(priority) or not 0 <= priority <= 1000:
        errors.add("provider_manifest_invalid")
        priority = context.defaults.priority
    return ManifestHeader(
        provider_id, kind, owned_by, enabled, required, priority, constraints, known,
    )


def _capacity(
    raw: object, fallback: int, ceiling: int | None, errors: ManifestErrors,
) -> int:
    if not _is_int(raw) or raw < 1 or (ceiling is not None and raw > ceiling):
        errors.add("provider_max_concurrent_invalid")
        return fallback
    return raw


def _quota(
    raw: object, provider_id: str, pattern: Pattern[str], errors: ManifestErrors,
) -> str:
    if not isinstance(raw, str) or not pattern.fullmatch(raw):
        errors.add("provider_quota_group_invalid")
        return provider_id
    return raw


def _pin_timeout(
    raw: Mapping[str, object], fallback: float, errors: ManifestErrors,
) -> tuple[bool, float]:
    pin = raw.get("pin_required", False)
    timeout = raw.get("timeout_s", fallback)
    is_number = isinstance(timeout, (int, float)) and not isinstance(timeout, bool)
    if not isinstance(pin, bool) or not is_number or cast(float, timeout) <= 0:
        errors.add("provider_manifest_invalid")
        return False, fallback
    return pin, float(cast(float, timeout))


def manifest_limits(
    header: ManifestHeader, context: ManifestContext[_D], pattern: Pattern[str],
) -> ManifestLimits:
    """Проверяет лимиты после транспортных парсеров, сохраняя порядок ошибок."""
    defaults, errors = context.defaults, context.errors
    raw = manifest_section(context.doc.get("limits"), errors)
    cap = _capacity(
        raw.get("max_concurrent", defaults.max_concurrent),
        defaults.max_concurrent, header.constraints.max_concurrent_max, errors,
    )
    quota = _quota(
        raw.get("quota_group", header.provider_id), header.provider_id, pattern, errors,
    )
    pin, timeout = _pin_timeout(raw, defaults.timeout_s, errors)
    return ManifestLimits(cap, quota, pin or header.constraints.pin_required, timeout)


def manifest_routing(doc: Mapping[str, object], errors: ManifestErrors) -> RoutingConfig:
    """Явный null не является отсутствием routing в закрытой схеме."""
    try:
        if "routing" in doc and doc["routing"] is None:
            raise ValueError("routing_invalid")
        return parse_routing(doc.get("routing"))
    except ValueError:
        errors.add("provider_routing_invalid")
        return RoutingConfig()


def validate_manifest_stages(
    request: ManifestInput, ports: ManifestValidationPorts[_D, _R],
) -> _R:
    """Выполняет закрытую валидацию и вызывает фабрику прежнего результата.

    Реестр kinds необязателен: без него ограничения вида не применяются.
    Имя файла проверяется по stem, переданному фасадом.
    """
    if not isinstance(request.doc, dict):
        return ports.result(None, ("provider_manifest_invalid",))
    context = ManifestContext(
        cast(Mapping[str, object], request.doc), request.env,
        ports.defaults(request.env), ManifestErrors(),
    )
    _schema_errors(request, context, ports)
    return ports.build(_header(request, context, ports), context)

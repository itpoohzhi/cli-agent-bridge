"""Манифесты провайдеров `providers.d/*.yaml`: загрузка, валидация, смарт-дефолты (слой A).

Манифест пишет человек один раз на бинарник/мост; модели внутри него — забота машины.
Модуль чистый: `validate_manifest` принимает уже распарсенный `dict`, ничего не читает
и не бросает исключений — результат содержит slug'и ошибок класса I (без пользовательских
данных) и нормализованный неизменяемый `ProviderManifest`.

Набор допустимых ключей берётся из JSON Schema
(`providers.d/_schema/provider-manifest.schema.json`): схема закрыта, неизвестный ключ на
любом уровне — `provider_key_unknown`. Вид `kind` разрешается только через реестр,
переданный вызывающим (`adapters.ADAPTER_KINDS`); манифест может лишь *сужать* жёсткие
ограничения вида (`KindConstraints`), но не расширять их.

Защита от инъекций CLI-аргументов (F-001): шаблоны `argv` — списки без shell
(`shell=True` недопустим), разрешены только плейсхолдеры `{model}`, `{slot}`, `{effort}`,
`{prompt}`, `{uuid4}`; `{prompt}` — отдельный элемент; значения подстановок проходят
regex при рендере (`render_argv`); executable — абсолютный путь внутри allowlist
каталогов (`BRIDGE_DIRECT_EXEC_DIRS`) и не shell-интерпретатор.

Эксплуатационные параметры (все — env с безопасными дефолтами):
`BRIDGE_PROVIDERS_DIR`, `BRIDGE_PROVIDER_REMOTE_BASE_URL_ENABLED`,
`BRIDGE_DIRECT_EXEC_DIRS`, `BRIDGE_DIRECT_FORBIDDEN_SHELLS`, `BRIDGE_DIRECT_ARG_PATTERN`,
`BRIDGE_DIRECT_PROMPT_DASH_GUARD`, `BRIDGE_DEFAULT_*` смарт-дефолтов (см. `Defaults`).
"""

from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, cast

from core.backend_adapter import (
    EFFORT_LEVELS,
    AllowEntry,
    KindConstraints,
    _base_url_allowed,
    kind_constraints,
)
from core.param_adapter import GLOBAL_WHITELIST

MANIFEST_VERSION = 1
PROVIDER_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
QUOTA_GROUP_RE = re.compile(r"[a-z0-9-]{1,48}")
LOOPBACK_HOSTS = ("127.0.0.1", "::1")
PLACEHOLDERS = ("model", "slot", "effort", "prompt", "uuid4")
_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")
FAMILY_RULE_TYPES = ("exact_map", "owned_by", "prefix")
DISCOVERY_METHODS = ("http", "cli", "static")
EFFORT_FIELDS = ("reasoning_effort", "effort", "none")
DEFAULT_EXEC_DIRS = (
    "~/.local/bin",
    "~/.config/*-launch",
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
)
DEFAULT_FORBIDDEN_SHELLS = ("sh", "bash", "zsh", "dash", "fish", "csh", "tcsh", "ksh")
DEFAULT_ARG_PATTERN = r"[A-Za-z0-9._:/-]{1,128}"
SCHEMA_RELATIVE = ("providers.d", "_schema", "provider-manifest.schema.json")
_TRUE = ("1", "true", "yes", "on")


class ManifestError(ValueError):
    """Ошибка манифеста; `slug` — короткая причина класса I."""

    def __init__(self, slug: str) -> None:
        super().__init__(slug)
        self.slug = slug


@dataclass(frozen=True)
class Defaults:
    """Смарт-дефолты манифеста; значения по умолчанию переопределяются через env."""

    max_concurrent: int = 1
    timeout_s: float = 180.0
    tool_emulation: bool = True
    priority: int = 100
    refresh_interval_s: float = 900.0
    ondemand_timeout_s: float = 10.0
    discovery_timeout_s: float = 5.0
    efforts: Tuple[str, ...] = ("high",)
    default_effort: str = "high"
    context_window: int = 200000
    max_tokens: int = 32000
    probe_effort_ladder: Tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")
    probe_max_parallel: int = 1
    probe_retry_backoff_s: Tuple[float, ...] = (300.0, 1800.0, 7200.0)
    probe_rate_limited_backoff_s: float = 900.0

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Defaults":
        """Смарт-дефолты с переопределением `BRIDGE_DEFAULT_<ПОЛЕ>` (скаляры)."""
        source = os.environ if env is None else env
        base = cls()
        values: Dict[str, Any] = {}
        for name, current in (
            ("max_concurrent", base.max_concurrent),
            ("timeout_s", base.timeout_s),
            ("priority", base.priority),
            ("context_window", base.context_window),
            ("max_tokens", base.max_tokens),
        ):
            raw = source.get("BRIDGE_DEFAULT_" + name.upper())
            if raw:
                try:
                    values[name] = type(current)(raw)
                except ValueError:
                    pass
        raw_tools = source.get("BRIDGE_DEFAULT_TOOL_EMULATION")
        if raw_tools:
            values["tool_emulation"] = raw_tools.strip().lower() in _TRUE
        return cls(**values)


@dataclass(frozen=True)
class BridgeTransport:
    """Как мост :9882 исполняет ход (компилируется в `backends.<id>`)."""

    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    wrapper: Optional[str] = None
    proxy_port: Optional[int] = None
    options: Mapping[str, Any] = field(default_factory=dict)
    idle_timeout_s: Optional[float] = None
    safety_cap_s: Optional[float] = None


@dataclass(frozen=True)
class DirectCli:
    executables: Tuple[str, ...] = ()
    argv_by_executable: Mapping[str, Tuple[str, ...]] = field(default_factory=dict)
    prompt_via: str = "argv"
    output: Mapping[str, Any] = field(default_factory=lambda: {"format": "text"})


@dataclass(frozen=True)
class TransportDirect:
    """Как потребители вне моста вызывают модель напрямую."""

    type: str = "cli"
    cli: Optional[DirectCli] = None
    http: Optional[Mapping[str, Any]] = None


@dataclass(frozen=True)
class TransportConfig:
    bridge: Optional[BridgeTransport] = None
    direct: Optional[TransportDirect] = None


@dataclass(frozen=True)
class LimitsConfig:
    max_concurrent: int = 1
    quota_group: str = ""
    pin_required: bool = False
    timeout_s: float = 180.0


@dataclass(frozen=True)
class FingerprintConfig:
    binary_path: Optional[str] = None
    binary_sha256: Optional[str] = None
    version: Optional[str] = None
    version_cmd: Optional[Tuple[str, ...]] = None
    http_version_path: Optional[str] = None


@dataclass(frozen=True)
class DiscoveryConfig:
    method: str = "static"
    http: Optional[Mapping[str, Any]] = None
    cli: Optional[Mapping[str, Any]] = None
    static: Tuple[str, ...] = ()
    include: Tuple[str, ...] = ()
    exclude: Tuple[str, ...] = ()
    strip_suffixes: Tuple[str, ...] = ()
    canonical_map: Mapping[str, str] = field(default_factory=dict)
    refresh_interval_s: float = 900.0
    ondemand_timeout_s: float = 10.0
    timeout_s: float = 5.0


@dataclass(frozen=True)
class FamilyRule:
    type: str = "exact_map"
    exact_map: Mapping[str, str] = field(default_factory=dict)
    owned_by: Optional[str] = None
    prefix_verified: bool = False
    prefix_map: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelsDefaults:
    efforts: Tuple[str, ...] = ("high",)
    default_effort: str = "high"
    context_window: int = 200000
    max_tokens: int = 32000
    probe_effort_ladder: Tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")


@dataclass(frozen=True)
class ModelRule:
    """Зафиксированные человеком поля модели (`models_overrides.<id>`)."""

    model_id: str
    fields: Mapping[str, Any] = field(default_factory=dict)

    @property
    def efforts_pin(self) -> Optional[Tuple[str, ...]]:
        pin = self.fields.get("efforts_pin")
        return tuple(pin) if pin else None


@dataclass(frozen=True)
class ParamsConfig:
    effort_field: str = "reasoning_effort"
    effort_map: Mapping[str, Any] = field(default_factory=dict)
    adaptive_whitelist: Tuple[str, ...] = tuple(GLOBAL_WHITELIST)
    strip_always: Tuple[str, ...] = ()
    tool_emulation: bool = True


@dataclass(frozen=True)
class ProbeConfig:
    enabled: bool = True
    max_parallel: int = 1
    retry_backoff_s: Tuple[float, ...] = (300.0, 1800.0, 7200.0)
    rate_limited_backoff_s: float = 900.0


@dataclass(frozen=True)
class ProviderManifest:
    """Нормализованный неизменяемый манифест провайдера."""

    provider_id: str
    kind: str
    owned_by: str
    enabled: bool = True
    required: bool = False
    priority: int = 100
    transport: TransportConfig = field(default_factory=TransportConfig)
    allow_base_url: Tuple[AllowEntry, ...] = ()
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    fingerprint: FingerprintConfig = field(default_factory=FingerprintConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    family_rule: FamilyRule = field(default_factory=FamilyRule)
    models_defaults: ModelsDefaults = field(default_factory=ModelsDefaults)
    models_overrides: Tuple[ModelRule, ...] = ()
    params: ParamsConfig = field(default_factory=ParamsConfig)
    probe: ProbeConfig = field(default_factory=ProbeConfig)
    manifest_version: int = MANIFEST_VERSION

    @property
    def max_concurrent(self) -> int:
        return self.limits.max_concurrent

    @property
    def quota_group(self) -> str:
        return self.limits.quota_group

    def rule_for(self, model_id: str) -> Optional[ModelRule]:
        for rule in self.models_overrides:
            if rule.model_id == model_id:
                return rule
        return None


@dataclass(frozen=True)
class ManifestValidationResult:
    """Итог валидации: манифест (None при ошибках) и slug'и ошибок."""

    manifest: Optional[ProviderManifest]
    errors: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.manifest is not None and not self.errors


# ---- схема: закрытый набор ключей --------------------------------------------------


def schema_path() -> Path:
    base = Path(__file__).resolve().parents[1]
    return base.joinpath(*SCHEMA_RELATIVE)


_SCHEMA_CACHE: Dict[str, Any] = {}


def load_schema(path: Optional[Path] = None) -> Mapping[str, Any]:
    """JSON Schema манифеста (кэшируется по пути)."""
    target = Path(path) if path else schema_path()
    key = str(target)
    if key not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[key] = json.loads(target.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE[key]


def unknown_keys(doc: Any, schema: Mapping[str, Any], path: str = "") -> List[str]:
    """Пути ключей `doc`, которых нет в закрытых узлах `schema` (обход по `properties`)."""
    found: List[str] = []
    if isinstance(doc, Mapping):
        props = cast(Any, schema.get("properties"))
        extra = cast(Any, schema.get("additionalProperties", True))
        for key, value in doc.items():
            where = f"{path}.{key}" if path else str(key)
            if isinstance(props, Mapping) and key in props:
                found.extend(unknown_keys(value, cast(Any, props[key]), where))
            elif extra is False:
                found.append(where)
            elif isinstance(extra, Mapping):
                found.extend(unknown_keys(value, extra, where))
    elif isinstance(doc, list):
        items = schema.get("items")
        if isinstance(items, Mapping):
            for index, value in enumerate(doc):
                found.extend(unknown_keys(value, items, f"{path}[{index}]"))
    return found


# ---- вспомогательные парсеры --------------------------------------------------------


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _str_list(value: Any) -> Optional[Tuple[str, ...]]:
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return tuple(value)
    return None


def _str_map(value: Any) -> Optional[Dict[str, str]]:
    if isinstance(value, Mapping) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in value.items()
    ):
        return cast(Dict[str, str], dict(value))
    return None


def _exec_dirs(env: Mapping[str, str]) -> Tuple[str, ...]:
    raw = env.get("BRIDGE_DIRECT_EXEC_DIRS")
    if raw:
        return tuple(p for p in raw.split(":") if p)
    return DEFAULT_EXEC_DIRS


def _forbidden_shells(env: Mapping[str, str]) -> Tuple[str, ...]:
    raw = env.get("BRIDGE_DIRECT_FORBIDDEN_SHELLS")
    if raw:
        return tuple(p.strip() for p in raw.split(",") if p.strip())
    return DEFAULT_FORBIDDEN_SHELLS


def executable_allowed(path: str, env: Optional[Mapping[str, str]] = None) -> bool:
    """Executable после `expanduser`: абсолютный, нормализованный, в allowlist каталогов."""
    source = os.environ if env is None else env
    expanded = os.path.expanduser(path)
    if not posixpath.isabs(expanded) or posixpath.normpath(expanded) != expanded:
        return False
    if posixpath.basename(expanded) in _forbidden_shells(source):
        return False
    directory = posixpath.dirname(expanded)
    for pattern in _exec_dirs(source):
        if fnmatch.fnmatchcase(directory, os.path.expanduser(pattern)):
            return True
    return False


def argv_placeholders_valid(argv: Sequence[str]) -> bool:
    """Только известные плейсхолдеры; `{prompt}` — отдельный элемент argv."""
    for element in argv:
        names = _PLACEHOLDER_RE.findall(element)
        if any(name not in PLACEHOLDERS for name in names):
            return False
        if "{" in _PLACEHOLDER_RE.sub("", element) or "}" in _PLACEHOLDER_RE.sub(
            "", element
        ):
            return False
        if "prompt" in names and element != "{prompt}":
            return False
    return True


def render_argv(
    template: Sequence[str],
    values: Mapping[str, str],
    *,
    env: Optional[Mapping[str, str]] = None,
) -> List[str]:
    """Подставляет значения в шаблон argv; без shell, `{prompt}` — один элемент.

    `{model}`, `{slot}`, `{effort}` проходят regex `BRIDGE_DIRECT_ARG_PATTERN`.
    Промпт, начинающийся с `-`, получает ведущий пробел (защита от option-injection),
    отключается `BRIDGE_DIRECT_PROMPT_DASH_GUARD=false`.
    """
    source = os.environ if env is None else env
    pattern = re.compile(source.get("BRIDGE_DIRECT_ARG_PATTERN") or DEFAULT_ARG_PATTERN)
    if not argv_placeholders_valid(template):
        raise ManifestError("provider_argv_placeholder_invalid")
    guard = (
        source.get("BRIDGE_DIRECT_PROMPT_DASH_GUARD", "true").strip().lower() in _TRUE
    )
    out: List[str] = []
    for element in template:
        if element == "{prompt}":
            prompt = str(values.get("prompt", ""))
            out.append(" " + prompt if guard and prompt.startswith("-") else prompt)
            continue

        def _sub(match: "re.Match[str]") -> str:
            name = match.group(1)
            if name == "uuid4":
                return str(uuid.uuid4())
            value = values.get(name)
            if not isinstance(value, str) or not pattern.fullmatch(value):
                raise ManifestError("provider_argv_value_invalid")
            return value

        out.append(_PLACEHOLDER_RE.sub(_sub, element))
    return out


def resolve_family(
    manifest: ProviderManifest, model_id: str
) -> Tuple[Optional[str], str]:
    """Семья модели по правилу манифеста: `(family|None, source)`; неоднозначно — `None`."""
    rule = manifest.family_rule
    if rule.type == "exact_map":
        family = rule.exact_map.get(model_id)
        return (family, "exact_map") if family else (None, "unmapped")
    if rule.type == "owned_by":
        return (rule.owned_by, "owned_by") if rule.owned_by else (None, "unmapped")
    if rule.type == "prefix" and rule.prefix_verified:
        families = {
            fam for pre, fam in rule.prefix_map.items() if model_id.startswith(pre)
        }
        if len(families) == 1:
            return next(iter(families)), "prefix"
        return (None, "ambiguous" if families else "unmapped")
    return None, "unmapped"


# ---- валидация ---------------------------------------------------------------------


class _Errors:
    def __init__(self) -> None:
        self.items: List[str] = []

    def add(self, slug: str) -> None:
        if slug not in self.items:
            self.items.append(slug)


def _parse_allow(
    raw: Any, env: Mapping[str, str], err: _Errors
) -> Tuple[AllowEntry, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        err.add("provider_manifest_invalid")
        return ()
    remote_enabled = (
        env.get("BRIDGE_PROVIDER_REMOTE_BASE_URL_ENABLED", "").strip().lower() in _TRUE
    )
    entries: List[AllowEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            err.add("provider_manifest_invalid")
            continue
        scheme, host, port = item.get("scheme"), item.get("host"), item.get("port")
        prefix = item.get("path_prefix", "/v1")
        if (
            scheme not in ("http", "https")
            or not isinstance(host, str)
            or not host
            or not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
            or not isinstance(prefix, str)
            or not prefix.startswith("/")
        ):
            err.add("provider_manifest_invalid")
            continue
        if host not in LOOPBACK_HOSTS:
            if not remote_enabled:
                err.add("provider_allowlist_remote_forbidden")
            if scheme == "http":
                err.add("provider_allowlist_plaintext_remote")
        entries.append(AllowEntry(str(scheme), host, port, prefix))
    return tuple(entries)


def _parse_direct(
    raw: Any, env: Mapping[str, str], err: _Errors
) -> Optional[TransportDirect]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        err.add("provider_manifest_invalid")
        return None
    dtype = raw.get("type", "cli")
    if dtype not in ("cli", "http"):
        err.add("provider_manifest_invalid")
        return None
    cli: Optional[DirectCli] = None
    raw_cli = raw.get("cli")
    if raw_cli is not None:
        execs = (
            _str_list(raw_cli.get("executables")) if isinstance(raw_cli, dict) else None
        )
        argv_map = (
            raw_cli.get("argv_by_executable", {}) if isinstance(raw_cli, dict) else None
        )
        prompt_via = (
            raw_cli.get("prompt_via", "argv") if isinstance(raw_cli, dict) else None
        )
        output = (
            raw_cli.get("output", {"format": "text"})
            if isinstance(raw_cli, dict)
            else None
        )
        if (
            not execs
            or not isinstance(argv_map, dict)
            or prompt_via not in ("argv", "stdin")
            or not isinstance(output, dict)
        ):
            err.add("provider_manifest_invalid")
        else:
            for path in execs:
                if not executable_allowed(path, env):
                    err.add("provider_executable_forbidden")
            parsed_argv: Dict[str, Tuple[str, ...]] = {}
            for key, template in argv_map.items():
                items = _str_list(template)
                if key not in execs or items is None:
                    err.add("provider_manifest_invalid")
                    continue
                if not argv_placeholders_valid(items):
                    err.add("provider_argv_placeholder_invalid")
                parsed_argv[key] = items
            cli = DirectCli(execs, parsed_argv, prompt_via, dict(output))
    http = raw.get("http")
    if http is not None and not isinstance(http, dict):
        err.add("provider_manifest_invalid")
        http = None
    return TransportDirect(dtype, cli, dict(http) if http else None)


def _parse_discovery(raw: Any, defaults: Defaults, err: _Errors) -> DiscoveryConfig:
    if raw is None:
        return DiscoveryConfig(
            refresh_interval_s=defaults.refresh_interval_s,
            ondemand_timeout_s=defaults.ondemand_timeout_s,
            timeout_s=defaults.discovery_timeout_s,
        )
    if not isinstance(raw, dict):
        err.add("provider_manifest_invalid")
        return DiscoveryConfig()
    method = raw.get("method", "static")
    if method not in DISCOVERY_METHODS:
        err.add("provider_discovery_invalid")
        method = "static"
    http, cli = raw.get("http"), raw.get("cli")
    for part in (http, cli):
        if part is not None and not isinstance(part, dict):
            err.add("provider_discovery_invalid")
    if method == "http" and not isinstance(http, dict):
        err.add("provider_discovery_invalid")
    if method == "cli":
        argv = _str_list(cli.get("argv")) if isinstance(cli, dict) else None
        if not argv or not argv_placeholders_valid(argv):
            err.add(
                "provider_argv_placeholder_invalid"
                if argv
                else "provider_discovery_invalid"
            )
    static = _str_list(raw.get("static")) if raw.get("static") is not None else ()
    include = _str_list(raw.get("include", []))
    exclude = _str_list(raw.get("exclude", []))
    canonical = raw.get("canonical_id", {})
    strip = (
        _str_list(canonical.get("strip_suffixes", []))
        if isinstance(canonical, dict)
        else None
    )
    cmap = _str_map(canonical.get("map", {})) if isinstance(canonical, dict) else None
    if None in (static, include, exclude, strip, cmap):
        err.add("provider_discovery_invalid")
        static, include, exclude, strip, cmap = (), (), (), (), {}
    numbers = []
    for key, fallback, floor in (
        ("refresh_interval_s", defaults.refresh_interval_s, 60.0),
        ("ondemand_timeout_s", defaults.ondemand_timeout_s, 0.0),
        ("timeout_s", defaults.discovery_timeout_s, 0.0),
    ):
        value = raw.get(key, fallback)
        if not _is_num(value) or value <= 0 or value < floor:
            err.add("provider_discovery_invalid")
            value = fallback
        numbers.append(float(value))
    return DiscoveryConfig(
        method=method,
        http=dict(http) if isinstance(http, dict) else None,
        cli=dict(cli) if isinstance(cli, dict) else None,
        static=tuple(static or ()),
        include=tuple(include or ()),
        exclude=tuple(exclude or ()),
        strip_suffixes=tuple(strip or ()),
        canonical_map=dict(cmap or {}),
        refresh_interval_s=numbers[0],
        ondemand_timeout_s=numbers[1],
        timeout_s=numbers[2],
    )


def _parse_family(raw: Any, err: _Errors) -> FamilyRule:
    if raw is None:
        return FamilyRule()
    if not isinstance(raw, dict):
        err.add("provider_manifest_invalid")
        return FamilyRule()
    rtype = raw.get("type", "exact_map")
    if rtype not in FAMILY_RULE_TYPES:
        err.add("provider_manifest_invalid")
        rtype = "exact_map"
    exact = _str_map(raw.get("exact_map", {}))
    owned_by = raw.get("owned_by")
    prefix = raw.get("prefix")
    if exact is None or (owned_by is not None and not isinstance(owned_by, str)):
        err.add("provider_manifest_invalid")
        exact = exact or {}
    verified, pmap = False, {}
    if prefix is not None:
        if not isinstance(prefix, dict):
            err.add("provider_manifest_invalid")
        else:
            verified = prefix.get("verified") is True
            parsed = _str_map(prefix.get("map", {}))
            if parsed is None:
                err.add("provider_manifest_invalid")
            else:
                pmap = parsed
    if rtype == "prefix" and not verified:
        err.add("provider_family_rule_unverified")
    if rtype == "owned_by" and not owned_by:
        err.add("provider_manifest_invalid")
    return FamilyRule(rtype, exact, owned_by, verified, pmap)


def _parse_models_defaults(
    raw: Any, defaults: Defaults, err: _Errors
) -> ModelsDefaults:
    base = ModelsDefaults(
        defaults.efforts,
        defaults.default_effort,
        defaults.context_window,
        defaults.max_tokens,
        defaults.probe_effort_ladder,
    )
    if raw is None:
        return base
    if not isinstance(raw, dict):
        err.add("provider_manifest_invalid")
        return base
    efforts = _str_list(raw.get("efforts", list(base.efforts)))
    ladder = _str_list(raw.get("probe_effort_ladder", list(base.probe_effort_ladder)))
    default_effort = raw.get("default_effort", base.default_effort)
    window = raw.get("context_window", base.context_window)
    max_tokens = raw.get("max_tokens", base.max_tokens)
    if (
        not efforts
        or not ladder
        or any(e not in EFFORT_LEVELS for e in efforts + ladder)
        or default_effort not in efforts
        or not _is_int(window)
        or window < 1
        or not _is_int(max_tokens)
        or max_tokens < 1
    ):
        err.add("provider_models_defaults_invalid")
        return base
    return ModelsDefaults(efforts, default_effort, window, max_tokens, ladder)


def _parse_overrides(raw: Any, err: _Errors) -> Tuple[ModelRule, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, dict):
        err.add("provider_manifest_invalid")
        return ()
    rules: List[ModelRule] = []
    for model_id, fields in raw.items():
        if (
            not isinstance(model_id, str)
            or not model_id
            or not isinstance(fields, dict)
        ):
            err.add("provider_manifest_invalid")
            continue
        rules.append(ModelRule(model_id, dict(fields)))
    return tuple(rules)


def _parse_params(
    raw: Any, defaults: Defaults, env: Mapping[str, str], err: _Errors
) -> ParamsConfig:
    base = ParamsConfig(tool_emulation=defaults.tool_emulation)
    if raw is None:
        return base
    if not isinstance(raw, dict):
        err.add("provider_manifest_invalid")
        return base
    field_name = raw.get("effort_field", base.effort_field)
    effort_map = raw.get("effort_map", {})
    whitelist = _str_list(raw.get("adaptive_whitelist", list(base.adaptive_whitelist)))
    strip = _str_list(raw.get("strip_always", []))
    tools = raw.get("tool_emulation", defaults.tool_emulation)
    if (
        field_name not in EFFORT_FIELDS
        or not isinstance(effort_map, dict)
        or strip is None
        or not isinstance(tools, bool)
    ):
        err.add("provider_manifest_invalid")
        return base
    if whitelist is None or any(item not in GLOBAL_WHITELIST for item in whitelist):
        err.add("provider_params_whitelist_invalid")
        return base
    return ParamsConfig(field_name, dict(effort_map), whitelist, strip, tools)


def _parse_probe(raw: Any, defaults: Defaults, err: _Errors) -> ProbeConfig:
    base = ProbeConfig(
        True,
        defaults.probe_max_parallel,
        defaults.probe_retry_backoff_s,
        defaults.probe_rate_limited_backoff_s,
    )
    if raw is None:
        return base
    if not isinstance(raw, dict):
        err.add("provider_manifest_invalid")
        return base
    enabled = raw.get("enabled", True)
    parallel = raw.get("max_parallel", base.max_parallel)
    backoff = raw.get("retry_backoff_s", list(base.retry_backoff_s))
    limited = raw.get("rate_limited_backoff_s", base.rate_limited_backoff_s)
    if (
        not isinstance(enabled, bool)
        or not _is_int(parallel)
        or parallel < 1
        or not isinstance(backoff, list)
        or not backoff
        or not all(_is_num(v) and v > 0 for v in backoff)
        or not _is_num(limited)
        or limited <= 0
    ):
        err.add("provider_manifest_invalid")
        return base
    return ProbeConfig(
        enabled, parallel, tuple(float(v) for v in backoff), float(limited)
    )


def _parse_bridge(raw: Any, err: _Errors) -> Optional[BridgeTransport]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        err.add("provider_manifest_invalid")
        return None
    options = raw.get("options", {})
    if not isinstance(options, dict):
        err.add("provider_options_invalid")
        options = {}
    typed = (
        ("base_url", str),
        ("api_key_env", str),
        ("wrapper", str),
    )
    for key, kind in typed:
        value = raw.get(key)
        if value is not None and (not isinstance(value, kind) or not value.strip()):
            err.add("provider_manifest_invalid")
    port = raw.get("proxy_port")
    if port is not None and (not _is_int(port) or not 1 <= port <= 65535):
        err.add("provider_manifest_invalid")
    for key in ("idle_timeout_s", "safety_cap_s"):
        value = raw.get(key)
        if value is not None and (not _is_num(value) or value <= 0):
            err.add("provider_manifest_invalid")
    return BridgeTransport(
        base_url=raw.get("base_url"),
        api_key_env=raw.get("api_key_env"),
        wrapper=raw.get("wrapper"),
        proxy_port=port,
        options=dict(options),
        idle_timeout_s=raw.get("idle_timeout_s"),
        safety_cap_s=raw.get("safety_cap_s"),
    )


def _parse_fingerprint(raw: Any, err: _Errors) -> FingerprintConfig:
    if raw is None:
        return FingerprintConfig()
    if not isinstance(raw, dict):
        err.add("provider_manifest_invalid")
        return FingerprintConfig()
    cmd = raw.get("version_cmd")
    parsed_cmd = _str_list(cmd) if cmd is not None else None
    sha = raw.get("binary_sha256")
    if cmd is not None and parsed_cmd is None:
        err.add("provider_manifest_invalid")
    if sha is not None and not (
        isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha)
    ):
        err.add("provider_manifest_invalid")
    for key in ("binary_path", "version", "http_version_path"):
        value = raw.get(key)
        if value is not None and not isinstance(value, str):
            err.add("provider_manifest_invalid")
    return FingerprintConfig(
        raw.get("binary_path"),
        sha,
        raw.get("version"),
        parsed_cmd,
        raw.get("http_version_path"),
    )


def validate_manifest(
    doc: Any,
    kinds: Optional[Mapping[str, Any]] = None,
    *,
    filename: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    schema: Optional[Mapping[str, Any]] = None,
) -> ManifestValidationResult:
    """Pure-валидация манифеста: никогда не бросает, ошибки — slug'и класса I.

    `kinds` — реестр видов (`adapters.ADAPTER_KINDS`); без него проверка `kind` и
    ограничений вида пропускается. `filename` — имя файла (`demo.yaml`): `provider_id`
    обязан совпадать со stem.
    """
    source = os.environ if env is None else env
    err = _Errors()
    if not isinstance(doc, dict):
        return ManifestValidationResult(None, ("provider_manifest_invalid",))
    try:
        unknown = unknown_keys(doc, schema if schema is not None else load_schema())
    except (OSError, ValueError):
        unknown = []
        err.add("provider_schema_unavailable")
    if unknown:
        err.add("provider_key_unknown")
    version = doc.get("manifest_version")
    if not _is_int(version) or version != MANIFEST_VERSION:
        err.add("provider_manifest_version_unsupported")
    provider_id = doc.get("provider_id")
    if (
        not isinstance(provider_id, str)
        or not PROVIDER_ID_RE.fullmatch(provider_id)
        or (filename is not None and provider_id != Path(filename).stem)
    ):
        err.add("provider_id_invalid")
        provider_id = provider_id if isinstance(provider_id, str) else ""
    kind = doc.get("kind")
    constraints = KindConstraints()
    kind_known = True  # неизвестный вид: проверки ограничений вида не применимы
    if not isinstance(kind, str) or not kind:
        err.add("provider_kind_unknown")
        kind, kind_known = "", False
    elif kinds is not None:
        if kind not in kinds:
            err.add("provider_kind_unknown")
            kind_known = False
        else:
            constraints = kind_constraints(kinds, kind)
    owned_by = doc.get("owned_by")
    if not isinstance(owned_by, str) or not owned_by:
        err.add("provider_manifest_invalid")
        owned_by = ""
    flags: Dict[str, bool] = {}
    for key, default in (("enabled", True), ("required", False)):
        value = doc.get(key, default)
        if not isinstance(value, bool):
            err.add("provider_manifest_invalid")
            value = default
        flags[key] = value
    defaults = Defaults.from_env(source)
    priority = doc.get("priority", defaults.priority)
    if not _is_int(priority) or not 0 <= priority <= 1000:
        err.add("provider_manifest_invalid")
        priority = defaults.priority

    raw_transport = doc.get("transport", {})
    if raw_transport is None:
        raw_transport = {}
    if not isinstance(raw_transport, dict):
        err.add("provider_manifest_invalid")
        raw_transport = {}
    bridge = _parse_bridge(raw_transport.get("bridge"), err)
    direct = _parse_direct(raw_transport.get("direct"), source, err)
    allow = _parse_allow(doc.get("allow_base_url"), source, err)

    raw_limits = doc.get("limits", {})
    if raw_limits is None:
        raw_limits = {}
    if not isinstance(raw_limits, dict):
        err.add("provider_manifest_invalid")
        raw_limits = {}
    cap = raw_limits.get("max_concurrent", defaults.max_concurrent)
    if (
        not _is_int(cap)
        or cap < 1
        or (
            constraints.max_concurrent_max is not None
            and cap > constraints.max_concurrent_max
        )
    ):
        err.add("provider_max_concurrent_invalid")
        cap = defaults.max_concurrent
    quota = raw_limits.get("quota_group", provider_id)
    if not isinstance(quota, str) or not QUOTA_GROUP_RE.fullmatch(quota):
        err.add("provider_quota_group_invalid")
        quota = provider_id
    pin = raw_limits.get("pin_required", False)
    timeout_s = raw_limits.get("timeout_s", defaults.timeout_s)
    if not isinstance(pin, bool) or not _is_num(timeout_s) or timeout_s <= 0:
        err.add("provider_manifest_invalid")
        pin, timeout_s = False, defaults.timeout_s
    limits = LimitsConfig(
        cap, quota, bool(pin) or constraints.pin_required, float(timeout_s)
    )
    fingerprint = _parse_fingerprint(doc.get("fingerprint"), err)
    if limits.pin_required and not fingerprint.binary_path:
        err.add("provider_technical_ref_missing")

    if bridge is not None and kind_known:
        if bridge.base_url is not None:
            if not constraints.base_url_allowed:
                err.add("provider_base_url_unexpected")
            elif allow:
                if not any(entry.matches(bridge.base_url) for entry in allow):
                    err.add("provider_base_url_invalid")
            elif not _base_url_allowed(provider_id, bridge.base_url, None):
                err.add("provider_base_url_invalid")
        elif constraints.base_url_allowed:
            err.add("provider_base_url_missing")
        if bridge.api_key_env is not None and not constraints.api_key_env_allowed:
            err.add("provider_manifest_invalid")
        if bridge.options:
            schema_opts = constraints.options_schema
            if not schema_opts or set(bridge.options) - set(schema_opts):
                err.add("provider_options_invalid")
            else:
                for opt_key, opt_value in bridge.options.items():
                    if opt_value not in schema_opts[opt_key]:
                        err.add("provider_options_invalid")

    if direct is not None and direct.http:
        direct_url = direct.http.get("base_url")
        if isinstance(direct_url, str):
            if allow:
                if not any(entry.matches(direct_url) for entry in allow):
                    err.add("provider_base_url_invalid")
            elif not _base_url_allowed(provider_id, direct_url, None):
                err.add("provider_base_url_invalid")
        elif direct.type == "http":
            err.add("provider_base_url_missing")

    manifest = ProviderManifest(
        provider_id=provider_id,
        kind=kind,
        owned_by=owned_by,
        enabled=flags["enabled"],
        required=flags["required"],
        priority=priority,
        transport=TransportConfig(bridge, direct),
        allow_base_url=allow,
        limits=limits,
        fingerprint=fingerprint,
        discovery=_parse_discovery(doc.get("discovery"), defaults, err),
        family_rule=_parse_family(doc.get("family_rule"), err),
        models_defaults=_parse_models_defaults(
            doc.get("models_defaults"), defaults, err
        ),
        models_overrides=_parse_overrides(doc.get("models_overrides"), err),
        params=_parse_params(doc.get("params"), defaults, source, err),
        probe=_parse_probe(doc.get("probe"), defaults, err),
    )
    if err.items:
        return ManifestValidationResult(None, tuple(err.items))
    return ManifestValidationResult(manifest, ())


# ---- загрузка с диска --------------------------------------------------------------


@dataclass(frozen=True)
class LoadedProviders:
    """Результат загрузки каталога манифестов."""

    manifests: Tuple[ProviderManifest, ...]
    rejected_providers: Mapping[str, Tuple[str, ...]]
    sha256_by_file: Mapping[str, str]


def providers_dir(env: Optional[Mapping[str, str]] = None) -> Path:
    source = os.environ if env is None else env
    raw = source.get("BRIDGE_PROVIDERS_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[1] / "providers.d"


def read_yaml_file(path: Path) -> Any:
    """`yaml.safe_load` файла; PyYAML подключается лениво."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - зависит от окружения
        raise ManifestError("yaml_unavailable") from exc
    try:
        raw = path.read_bytes()
        return yaml.safe_load(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ManifestError("provider_yaml_invalid") from exc


def manifest_files(directory: Path) -> List[Path]:
    """`*.yaml|*.yml` каталога без служебных `_*` (шапка, схема), в лексикографическом порядке."""
    if not directory.is_dir():
        return []
    return sorted(
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix in (".yaml", ".yml") and not p.name.startswith("_")
    )


def load_manifests(
    directory: Optional[Path] = None,
    kinds: Optional[Mapping[str, Any]] = None,
    *,
    env: Optional[Mapping[str, str]] = None,
) -> LoadedProviders:
    """Загружает и валидирует все манифесты каталога; невалидные — в `rejected_providers`."""
    import hashlib

    base = Path(directory) if directory else providers_dir(env)
    schema = (
        load_schema(base / "_schema" / SCHEMA_RELATIVE[-1])
        if (base / "_schema" / SCHEMA_RELATIVE[-1]).is_file()
        else None
    )
    manifests: List[ProviderManifest] = []
    rejected: Dict[str, Tuple[str, ...]] = {}
    digests: Dict[str, str] = {}
    for path in manifest_files(base):
        digests[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            doc = read_yaml_file(path)
        except ManifestError as exc:
            rejected[path.stem] = (exc.slug,)
            continue
        result = validate_manifest(
            doc, kinds, filename=path.name, env=env, schema=schema
        )
        if result.manifest is None or result.errors:
            rejected[path.stem] = result.errors or ("provider_manifest_invalid",)
        else:
            manifests.append(result.manifest)
    manifests.sort(key=lambda m: (m.priority, m.provider_id))
    return LoadedProviders(tuple(manifests), rejected, digests)

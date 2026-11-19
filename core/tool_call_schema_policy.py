"""Чистая доменная политика схем, канонизации, лимитов и ошибок tool_calls."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Literal, TypeAlias, cast, final, override

JsonMap: TypeAlias = Mapping[str, object]
MutableJsonMap: TypeAlias = dict[str, object]
LimitKind: TypeAlias = Literal["calls", "bytes"]

EXEC_SYNONYMS: frozenset[str] = frozenset(
    {"execute", "run_command", "shell", "terminal"}
)
_SHELL_METADATA_TOOLS: frozenset[str] = frozenset({"bash", "pwsh"})
_COMMAND_ALIASES: tuple[str, ...] = ("cmd", "CommandLine", "script")
_LEGACY_META_KEYS: tuple[str, ...] = ("summary", "toolSummary", "description")
_INTERNAL_SUMMARY_KEYS: tuple[str, ...] = ("summary", "toolSummary")
_UNRESOLVABLE_SCHEMA_KEYS: frozenset[str] = frozenset(
    {"$ref", "anyOf", "oneOf", "allOf", "if", "then", "else", "dependentRequired", "dependentSchemas"}
)


class ToolTurnErrorKind(Enum):
    """Классы терминальных ошибок шага вызова инструментов."""

    NONE = "none"
    REPETITION_LOOP = "upstream_repetition_loop"
    LIMIT_EXCEEDED = "tool_call_limit_exceeded"
    PARSE_ERROR = "tool_call_parse_error"


@final
class ToolCallLimitExceededError(Exception):
    """Превышение лимита количества вызовов или байтового бюджета шага."""

    __slots__ = ("limit", "limit_kind", "observed")

    limit_kind: LimitKind
    observed: int
    limit: int

    @override
    def __init__(
        self,
        limit_kind: LimitKind,
        observed: int,
        limit: int,
        message: str = "",
    ) -> None:
        self.limit_kind = limit_kind
        self.observed = observed
        self.limit = limit
        text = message or (
            f"tool call limit exceeded ({limit_kind}): "
            f"observed {observed}, limit {limit}"
        )
        super().__init__(text)


@dataclass(frozen=True, slots=True)
class ToolTurnErrorSpec:
    """Иммутабельная спецификация HTTP/SSE-ошибки шага инструментов."""

    kind: ToolTurnErrorKind
    message: str
    detail: str
    http_code: int = 502


def _as_map(value: object) -> JsonMap | None:
    return cast("JsonMap", value) if isinstance(value, Mapping) else None


def _as_stripped_str(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def resolve_parameters_schema(
    tool_name: str, tool_schemas: JsonMap | None
) -> MutableJsonMap | None:
    """Извлекает разрешимую JSON-схему ``parameters`` инструмента либо ``None``."""
    schemas = _as_map(tool_schemas)
    if not tool_name or schemas is None:
        return None
    schema_map = _as_map(schemas.get(tool_name))
    if schema_map is None:
        return None
    fn_map = _as_map(schema_map.get("function"))
    holder = fn_map if fn_map is not None else schema_map
    params_map = _as_map(holder.get("parameters"))
    if params_map is None or any(k in params_map for k in _UNRESOLVABLE_SCHEMA_KEYS):
        return None
    return dict(params_map)


def _declared_parameter_names(params: JsonMap) -> set[str]:
    declared: set[str] = set()
    props = _as_map(params.get("properties"))
    if props is not None:
        declared.update(props.keys())
    required = params.get("required")
    if isinstance(required, Sequence) and not isinstance(
        required, (str, bytes, bytearray)
    ):
        declared.update(item for item in required if isinstance(item, str))
    return declared


def _promote_summary_to_description(args: MutableJsonMap) -> None:
    current = args.get("description")
    if isinstance(current, str) and current.strip():
        return
    for key in ("toolSummary", "summary"):
        candidate = args.get(key)
        if isinstance(candidate, str) and candidate.strip():
            args["description"] = candidate
            return


def _has_tool_schema(schemas: JsonMap, target: str) -> bool:
    target_cf = target.casefold()
    return target in schemas or any(isinstance(k, str) and k.casefold() == target_cf for k in schemas)


def _is_required_parameter(params: JsonMap, name: str) -> bool:
    req = params.get("required")
    return isinstance(req, Sequence) and not isinstance(req, (str, bytes, bytearray)) and name in req


def _synthesize_command_description(args: JsonMap) -> str:
    command = _as_stripped_str(args.get("command"))
    first_line = next((ln.strip() for ln in command.splitlines() if ln.strip()), "") if command else ""
    normalized = " ".join(first_line.split())
    if not normalized:
        return "Execute shell command"
    return f"Run: {normalized[:69].rstrip() + '...' if len(normalized) > 72 else normalized}"


def strip_undeclared_bash_metadata(
    args: MutableJsonMap,
    tool_schemas: JsonMap | None,
    tool_name: str = "bash",
    *,
    synthesize_required_description: bool = False,
) -> None:
    """Применяет контракт F5 к ``summary``/``toolSummary``/``description`` (fail-conservative)."""
    params = None if tool_schemas is None else resolve_parameters_schema(tool_name, tool_schemas)
    if params is None or ("properties" not in params and "required" not in params):
        _promote_summary_to_description(args)
        for internal_key in _INTERNAL_SUMMARY_KEYS:
            _ = args.pop(internal_key, None)
        return
    declared = _declared_parameter_names(params)
    if "description" in declared:
        _promote_summary_to_description(args)
        if synthesize_required_description and _is_required_parameter(params, "description") and not _as_stripped_str(args.get("description")):
            args["description"] = _synthesize_command_description(args)
    else:
        _ = args.pop("description", None)
    for internal_key in _INTERNAL_SUMMARY_KEYS:
        if internal_key not in declared:
            _ = args.pop(internal_key, None)


def canonicalize_tool_invocation(
    name: str,
    arguments: JsonMap,
    tool_schemas: JsonMap | None = None,
    *,
    synthesize_required_description: bool = False,
) -> tuple[str, MutableJsonMap]:
    """Канонизирует имя и аргументы вызова инструмента без мутации входа."""
    clean_name = _as_stripped_str(name)
    arg_map = _as_map(arguments)
    args: MutableJsonMap = dict(arg_map) if arg_map is not None else {}
    schemas = _as_map(tool_schemas)
    if clean_name.casefold() in EXEC_SYNONYMS:
        own_declared = schemas is not None and _has_tool_schema(schemas, clean_name) and not _has_tool_schema(schemas, "bash")
        if not own_declared:
            clean_name = "bash"
    if clean_name.casefold() not in _SHELL_METADATA_TOOLS:
        return clean_name, args
    if clean_name in _SHELL_METADATA_TOOLS or schemas is not None:
        if "command" not in args:
            for alias in _COMMAND_ALIASES:
                if alias in args:
                    args["command"] = args.pop(alias)
                    break
        for alias in _COMMAND_ALIASES:
            _ = args.pop(alias, None)
    strip_undeclared_bash_metadata(args, tool_schemas, clean_name, synthesize_required_description=synthesize_required_description)
    return clean_name, args


def _parse_positive_int(raw: object) -> int | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, str):
        text = raw.strip()
        if not text or "_" in text:
            return None
        try:
            parsed = int(text, 10)
        except ValueError:
            return None
        return parsed if parsed > 0 else None
    return None


def resolve_positive_limit(env_raw: object, config_raw: object, default: int) -> int:
    """Возвращает первый валидный положительный лимит: env -> config -> default."""
    for candidate in (env_raw, config_raw):
        parsed = _parse_positive_int(candidate)
        if parsed is not None:
            return parsed
    fallback = _parse_positive_int(default)
    return fallback if fallback is not None else 1


def classify_tool_turn_error(
    error_text: str,
    *,
    is_repetition_loop: bool = False,
    limit_error: ToolCallLimitExceededError | None = None,
) -> ToolTurnErrorSpec:
    """Классифицирует ошибку шага инструментов в ``ToolTurnErrorSpec``."""
    if limit_error is not None:
        msg = (
            f"tool call limit exceeded ({limit_error.limit_kind}): "
            f"observed {limit_error.observed}, limit {limit_error.limit}"
        )
        return ToolTurnErrorSpec(ToolTurnErrorKind.LIMIT_EXCEEDED, msg, error_text)
    if is_repetition_loop or ToolTurnErrorKind.REPETITION_LOOP.value in error_text:
        return ToolTurnErrorSpec(
            ToolTurnErrorKind.REPETITION_LOOP,
            "upstream repetition loop detected",
            error_text,
        )
    return ToolTurnErrorSpec(
        ToolTurnErrorKind.PARSE_ERROR,
        "agy emitted a malformed tool call",
        error_text,
    )


def build_tool_turn_error_body(
    error_text: str,
    *,
    is_repetition_loop: bool = False,
    limit_error: ToolCallLimitExceededError | None = None,
) -> MutableJsonMap:
    """Формирует тело ошибки OpenAI/SSE с честным разделением классов сбоя."""
    spec = classify_tool_turn_error(
        error_text, is_repetition_loop=is_repetition_loop, limit_error=limit_error
    )
    return {
        "message": spec.message,
        "type": spec.kind.value,
        "code": spec.http_code,
        "detail": spec.detail,
    }

"""Чистый домен Zero-Canon для суб-мостов: без I/O и без чтения окружения."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final, cast

REVIEW_PROFILE_HEADER: Final[str] = "X-Review-Profile"
ZERO_CANON_PROFILE: Final[str] = "zero-canon"
STANDARD_PROFILE: Final[str] = "standard"
EXTERNAL_BASE_PREFIX: Final[str] = "/sg-"
EXTERNAL_TRUST_PROFILE: Final[str] = "external"

CODEX_CONFIG_DENY_SECTIONS: Final[tuple[str, ...]] = ("mcp_servers", "plugins", "notify")
CODEX_CONFIG_DENY_EXTRA: Final[tuple[str, ...]] = ("hooks",)
CODEX_CONFIG_FORCED: Final[Mapping[str, Any]] = {"project_doc_max_bytes": 0}

MUSE_SETTINGS_ALLOWLIST: Final[frozenset[str]] = frozenset(
    ("provider", "model", "auth", "api_base", "proxy")
)
MUSE_ZERO_CANON_FLAG: Final[str] = "MUSE_ZERO_CANON_ENABLED"

OPENCODE_ZERO_CANON_FLAG: Final[str] = "OPENCODE_ZERO_CANON_ENABLED"
OPENCODE_DENY_KEYS: Final[tuple[str, ...]] = (
    "mcp", "plugin", "instructions", "agent", "command", "permission",
)
OPENCODE_FORCED_PERMISSION: Final[Mapping[str, str]] = {"*": "ask"}

HUB_ZERO_CANON_ROUTING_FLAG: Final[str] = "HUB_ZERO_CANON_ROUTING_ENABLED"
STDIO_RESIDENT_CLAUDE_CODEX_PROTOCOL_FLAG: Final[str] = (
    "STDIO_RESIDENT_CLAUDE_CODEX_PROTOCOL_ENABLED"
)

__all__ = (
    "REVIEW_PROFILE_HEADER", "ZERO_CANON_PROFILE", "STANDARD_PROFILE",
    "CODEX_CONFIG_DENY_SECTIONS", "CODEX_CONFIG_DENY_EXTRA", "CODEX_CONFIG_FORCED",
    "MUSE_SETTINGS_ALLOWLIST", "MUSE_ZERO_CANON_FLAG",
    "OPENCODE_ZERO_CANON_FLAG", "OPENCODE_DENY_KEYS", "OPENCODE_FORCED_PERMISSION",
    "HUB_ZERO_CANON_ROUTING_FLAG",
    "should_forward_review_profile", "normalize_review_profile",
    "is_zero_canon_profile", "review_profile_from_headers", "filter_codex_config", "filter_muse_settings",
    "filter_opencode_config", "dump_toml",
)


_TRUSTED_LOCAL_SEGMENTS: Final[frozenset[str]] = frozenset(
    ("", "v1", "claude", "claude-a", "claude-b", "agy", "muse", "opencode")
)


def should_forward_review_profile(base_path: str, trust_profile: str) -> bool:
    """Fail-closed сегментный allowlist: True только для локальных суб-мостов (не `/sg-*`, `/go/*`, `/opencode-go`)."""
    if trust_profile == EXTERNAL_TRUST_PROFILE:
        return False
    first_seg = str(base_path or "").strip().strip("/").split("/", 1)[0].lower()
    return first_seg in _TRUSTED_LOCAL_SEGMENTS


def normalize_review_profile(value: str | None) -> str:
    """`zero-canon` для Zero-Canon (без учёта регистра), иначе `standard`."""
    if isinstance(value, str) and value.strip().lower() == ZERO_CANON_PROFILE:
        return ZERO_CANON_PROFILE
    return STANDARD_PROFILE


def review_profile_from_headers(headers: Any) -> str:
    """Нормализованный профиль из mapping/HTTPMessage заголовков (регистр не важен)."""
    items: Any = getattr(headers, "items", None)
    if not callable(items):
        return STANDARD_PROFILE
    wanted = REVIEW_PROFILE_HEADER.lower()
    raw_items = cast(Iterable[tuple[Any, Any]], items())
    return normalize_review_profile(
        next((str(v) for k, v in raw_items if str(k).lower() == wanted), None)
    )


def is_zero_canon_profile(value: str | None) -> bool:
    """Удобный предикат поверх `normalize_review_profile`."""
    return normalize_review_profile(value) == ZERO_CANON_PROFILE


def _clone(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _clone(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_clone(item) for item in value]
    return value


def filter_codex_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Копия config.toml без `mcp_servers`/`plugins`/`notify`/хуков и без AGENTS.md."""
    if not isinstance(raw, Mapping):
        raise TypeError(f"Expected a mapping, got {type(raw).__name__}")
    denied = {*CODEX_CONFIG_DENY_SECTIONS, *CODEX_CONFIG_DENY_EXTRA}
    result = {str(key): _clone(item) for key, item in raw.items() if key not in denied}
    result.update(CODEX_CONFIG_FORCED)
    return result


def filter_muse_settings(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Оставляет только ключи из `MUSE_SETTINGS_ALLOWLIST`."""
    if not isinstance(raw, Mapping):
        raise TypeError(f"Expected a mapping, got {type(raw).__name__}")
    return {str(k): _clone(v) for k, v in raw.items() if k in MUSE_SETTINGS_ALLOWLIST}


def filter_opencode_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Убирает mcp/plugin/instructions и принудительно задаёт `permission={"*": "ask"}`."""
    if not isinstance(raw, Mapping):
        raise TypeError(f"Expected a mapping, got {type(raw).__name__}")
    result = {str(k): _clone(v) for k, v in raw.items() if k not in OPENCODE_DENY_KEYS}
    result["permission"] = dict(OPENCODE_FORCED_PERMISSION)
    return result


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return repr(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return "[" + ", ".join(_toml_scalar(item) for item in value) + "]"
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return '"' + text.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + '"'


def _toml_key(key: str) -> str:
    bare = key and all(ch.isalnum() or ch in "_-" for ch in key)
    return key if bare else _toml_scalar(key)


def _is_table_array(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, Mapping) for item in value)


def _dump_table(
    table: Mapping[str, Any], path: tuple[str, ...], out: list[str], *, emit_header: bool = True
) -> None:
    scalars = [(k, v) for k, v in table.items() if not isinstance(v, Mapping) and not _is_table_array(v)]
    tables = [(k, v) for k, v in table.items() if isinstance(v, Mapping)]
    arrays = [(k, v) for k, v in table.items() if _is_table_array(v)]
    if emit_header and path and (scalars or (not tables and not arrays)):
        out.append("[" + ".".join(_toml_key(part) for part in path) + "]")
    out.extend(f"{_toml_key(k)} = {_toml_scalar(v)}" for k, v in scalars)
    if scalars or (emit_header and path):
        out.append("")
    for key, value in tables:
        _dump_table(value, (*path, str(key)), out)
    for key, items in arrays:
        arr_tuple = (*path, str(key))
        arr_path = ".".join(_toml_key(part) for part in arr_tuple)
        for item in items:
            out.append(f"[[{arr_path}]]")
            _dump_table(item, arr_tuple, out, emit_header=False)


def dump_toml(table: Mapping[str, Any]) -> str:
    """Детерминированный минимальный TOML-сериализатор (скаляры, списки, таблицы)."""
    lines: list[str] = []
    _dump_table(table, (), lines)
    return "\n".join(lines).rstrip("\n") + "\n"

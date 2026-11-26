"""Pure helpers for constructing Codex CLI arguments."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

_DENIED_ZC_CFG = ("mcp_servers", "plugins", "notify", "hooks")


def has_flag(argv: Sequence[str], flag: str) -> bool:
    """Return whether ``argv`` contains an exact flag or ``flag=value``."""
    return any(item == flag or item.startswith(f"{flag}=") for item in argv)


def extract_cfg_arg(argv: Sequence[str], idx: int) -> tuple[str | None, int]:
    """Extract a Codex ``-c``/``--config`` argument and consumed token count."""
    token = argv[idx]
    if token in ("-c", "--config") and idx + 1 < len(argv):
        return argv[idx + 1], 2
    if token.startswith(("-c=", "--config=")):
        return token.split("=", 1)[1], 1
    return None, 1


def append_cli_args(argv: list[str], raw_args: object) -> None:
    """Append user arguments, preserving every config pair and deduplicating flags."""
    if not isinstance(raw_args, (list, tuple)):
        return
    args = [str(raw) for raw in raw_args]
    idx = 0
    while idx < len(args):
        cfg_val, step = extract_cfg_arg(args, idx)
        if cfg_val is not None:
            argv.extend(args[idx : idx + step])
            idx += step
            continue
        arg = args[idx]
        if arg and arg not in argv:
            argv.append(arg)
        idx += 1


def build_codex_argv(base_argv: Sequence[str], options: Mapping[str, Any]) -> list[str]:
    """Build the legacy Codex app-server command line."""
    argv = list(base_argv) if "app-server" in base_argv else [*base_argv, "app-server"]
    append_cli_args(argv, options.get("cli_args"))
    for name, value in options.items():
        if not isinstance(name, str) or not name.startswith("--"):
            continue
        if value is None or value is False or has_flag(argv, name):
            continue
        argv.append(name)
        if value is not True:
            argv.append(str(value))
    return argv


def is_denied_cfg_key(key: str) -> bool:
    """Return whether a config key is forbidden in Zero-Canon mode."""
    return any(key == denied or key.startswith(f"{denied}.") for denied in _DENIED_ZC_CFG)


def zero_canon_overrides(model: str, effort: str) -> dict[str, str]:
    """Return the deterministic Codex Zero-Canon config overrides."""
    overrides = {"project_doc_max_bytes": "0"}
    if model and model != "default":
        overrides["model"] = json.dumps(model)
    if effort and effort != "default":
        overrides["model_reasoning_effort"] = json.dumps(effort)
    return overrides


def build_zero_canon_argv(argv: Sequence[str], model: str = "", effort: str = "") -> list[str]:
    """Apply Zero-Canon overrides while retaining unrelated config pairs."""
    overrides = zero_canon_overrides(model, effort)
    cleaned: list[str] = []
    idx = 0
    while idx < len(argv):
        cfg_val, step = extract_cfg_arg(argv, idx)
        if cfg_val is not None:
            key = cfg_val.split("=", 1)[0].strip()
            if is_denied_cfg_key(key):
                raise ValueError(f"forbidden_codex_zero_canon_config:{key}")
            if key in overrides:
                idx += step
                continue
        cleaned.append(argv[idx])
        idx += 1
    result = cleaned if "app-server" in cleaned else [*cleaned, "app-server"]
    for key, value in overrides.items():
        result.extend(("-c", f"{key}={value}"))
    return result

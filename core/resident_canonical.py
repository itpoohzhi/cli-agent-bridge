from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import re
import struct
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, cast

DEFAULT_SAFE_FWD_ENV_KEYS = frozenset(
    {
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LC_MESSAGES",
        "TERM",
        "COLORTERM",
        "NO_COLOR",
        "FORCE_COLOR",
        "TZ",
        "COLUMNS",
        "LINES",
        "CI",
    }
)
_DENIED_PREFIXES = (
    "LD_", "DYLD_", "PYTHON", "NODE_", "BASH_", "PERL", "RUBY", "GIT_",
    "BRIDGE_", "GLIBC_", "MALLOC_", "PIP_", "CARGO_", "BUN_", "DENO_",
    "NPM_CONFIG_", "XDG_", "UV_", "YARN_", "PNPM_", "ELECTRON_",
    "DOTNET_", "DOCKER_", "OPENSSL_",
)
_DENIED_NAMES = frozenset(
    {
        "PATH", "HOME", "SHELL", "USER", "TMPDIR", "TEMP", "TMP",
        "RUSTC", "CC", "CXX", "MAKEFLAGS", "KUBECONFIG", "SSH_AUTH_SOCK",
    }
)
_SECRET_NAME = re.compile(r"TOKEN|KEY|SECRET|AUTH|PASS")


def _fail_if(cond: object, exc: Exception) -> None:
    if cond:
        raise exc


def _is_dc_inst(obj: object) -> bool:
    return all((dataclasses.is_dataclass(obj), not isinstance(obj, type)))


def _canon_key(val: object) -> str:
    return json.dumps(val, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canon_scalar(obj: object) -> object:
    out: object = {"__float_bits__": struct.pack("!d", obj).hex()} if isinstance(obj, float) else obj
    return out


def _canon_bytes_or_seq(obj: object, depth: int, max_depth: int) -> object:
    descend = depth + 1
    out: object
    if isinstance(obj, bytes):
        out = {"__bytes_b64__": base64.b64encode(obj).decode("ascii")}
    elif isinstance(obj, bytearray):
        out = {"__bytearray_b64__": base64.b64encode(bytes(obj)).decode("ascii")}
    else:
        values = [_canonical(item, descend, max_depth=max_depth) for item in cast(Any, obj)]
        out = values if isinstance(obj, list) else {"__tuple__": values}
    return out


def _canon_set_or_map(obj: object, depth: int, max_depth: int) -> object:
    descend = depth + 1
    out: object
    if isinstance(obj, Mapping):
        pairs = [
            [_canonical(k, descend, max_depth=max_depth), _canonical(v, descend, max_depth=max_depth)]
            for k, v in obj.items()
        ]
        out = {"__map__": sorted(pairs, key=_canon_key)}
    else:
        values = [_canonical(item, descend, max_depth=max_depth) for item in cast(Any, obj)]
        marker = "__frozenset__" if isinstance(obj, frozenset) else "__set__"
        out = {marker: sorted(values, key=_canon_key)}
    return out


def _canon_dataclass(obj: object, depth: int, max_depth: int) -> object:
    typed = cast(Any, obj)
    values = [
        [item.name, _canonical(getattr(typed, item.name), depth + 1, max_depth=max_depth)]
        for item in dataclasses.fields(typed)
    ]
    return {"__dataclass__": [f"{type(obj).__module__}.{type(obj).__qualname__}", values]}


def _check_depth(depth: int, limit: int) -> None:
    _fail_if(depth > limit, ValueError("nesting_too_deep"))


def _canonical(obj: object, _depth: int = 0, *, max_depth: int = 64) -> object:
    _check_depth(_depth, max_depth)
    res: object | None = None
    handled = False
    if isinstance(obj, type(None)):
        res, handled = None, True
    elif isinstance(obj, (bool, int, float, str)):
        res, handled = _canon_scalar(obj), True
    elif isinstance(obj, (bytes, bytearray, list, tuple)):
        res, handled = _canon_bytes_or_seq(obj, _depth, max_depth), True
    elif isinstance(obj, (set, frozenset, Mapping)):
        res, handled = _canon_set_or_map(obj, _depth, max_depth), True
    elif _is_dc_inst(obj):
        res, handled = _canon_dataclass(obj, _depth, max_depth), True
    _fail_if(not handled, TypeError(f"unsupported non-JSON value: {type(obj).__qualname__}"))
    return res


def validate_canonical_depth(obj: object, *, max_depth: int = 63) -> None:
    _ = _canonical(obj, max_depth=max_depth)


def assert_emulate_tools_bool(value: object) -> bool:
    _fail_if(not isinstance(value, bool), TypeError("emulate_tools must be bool"))
    return cast(bool, value)


def _freeze_dataclass(obj: object, depth: int) -> object:
    params = getattr(type(obj), "__dataclass_params__", None)
    _fail_if(not bool(getattr(params, "frozen", False)), TypeError("mutable_dataclass_forbidden"))
    typed = cast(Any, obj)
    clone = object.__new__(type(obj))
    for item in dataclasses.fields(typed):
        object.__setattr__(clone, item.name, deep_freeze(getattr(typed, item.name), depth))
    return clone


def _freeze_collection(obj: object, depth: int) -> object:
    out: object
    if isinstance(obj, Mapping):
        out = MappingProxyType({deep_freeze(k, depth): deep_freeze(v, depth) for k, v in obj.items()})
    elif isinstance(obj, (list, tuple)):
        out = tuple(deep_freeze(item, depth) for item in obj)
    else:
        values = (deep_freeze(item, depth) for item in cast(Any, obj))
        out = tuple(sorted(values, key=lambda item: _canon_key(_canonical(item))))
    return out


def deep_freeze(obj: object, _depth: int = 0) -> object:
    _check_depth(_depth, 64)
    descend = _depth + 1
    out = obj
    if isinstance(obj, bytearray):
        out = bytes(obj)
    elif isinstance(obj, (Mapping, list, tuple, set, frozenset)):
        out = _freeze_collection(obj, descend)
    elif _is_dc_inst(obj):
        out = _freeze_dataclass(obj, descend)
    return out


def thaw_frozen_value(obj: object) -> object:
    out = obj
    if isinstance(obj, MappingProxyType):
        out = {thaw_frozen_value(k): thaw_frozen_value(v) for k, v in obj.items()}
    elif isinstance(obj, tuple):
        out = [thaw_frozen_value(item) for item in obj]
    return out


def compute_tool_contract_fingerprint(
    emulate_tools: bool,
    tool_schemas: Mapping[str, object] | None,
    tool_choice: object = None,
    *,
    max_depth: int = 63,
) -> str:
    invalid = all((not isinstance(tool_schemas, type(None)), not isinstance(tool_schemas, Mapping)))
    _fail_if(invalid, TypeError("tool_schemas must be Mapping or None"))
    payload = {
        "emulate_tools": bool(emulate_tools),
        "tool_choice": _canonical(tool_choice, max_depth=max_depth),
        "schemas": _canonical(tool_schemas if tool_schemas else {}, max_depth=max_depth),
    }
    return hashlib.sha256(_canon_key(payload).encode("ascii")).hexdigest()


def _valid_env_text(value: str) -> bool:
    return all(32 <= ord(c) != 127 and not 0xD800 <= ord(c) <= 0xDFFF for c in value)


def _denied_env_name(name: str, extra_prefixes: tuple[str, ...]) -> bool:
    upper = name.upper()
    prefixes = _DENIED_PREFIXES + tuple(p.upper() for p in extra_prefixes)
    return any((bool({upper} & _DENIED_NAMES), upper.startswith(prefixes), bool(_SECRET_NAME.search(upper))))


def strip_bridge_secrets(clean: Mapping[str, str]) -> dict[str, str]:
    return {k: v for k, v in clean.items() if not _denied_env_name(k, ())}


def _checked_env_pairs(raw_fwd_env: Mapping[object, object] | None) -> list[tuple[str, str]]:
    source: Mapping[object, object] = {} if isinstance(raw_fwd_env, type(None)) else raw_fwd_env
    checked: list[tuple[str, str]] = []
    total = 0
    for rk, rv in source.items():
        _fail_if(not all((isinstance(rk, str), isinstance(rv, str))), TypeError("environment keys and values must be str"))
        key, val = cast(str, rk), cast(str, rv)
        bad = any((not key, bool({"="} & set(key)), not _valid_env_text(key), not _valid_env_text(val)))
        _fail_if(bad, ValueError("invalid_env_value"))
        total += len(key.encode("utf-8")) + len(val.encode("utf-8")) + 2
        checked.append((key, val))
    _fail_if(total > 65536, ValueError("env_too_large"))
    return checked


def normalize_child_env(
    raw_fwd_env: Mapping[object, object] | None,
    *,
    allowed_keys: frozenset[str] = DEFAULT_SAFE_FWD_ENV_KEYS,
    extra_denied_prefixes: tuple[str, ...] = (),
) -> MappingProxyType[str, str]:
    allowed = frozenset(k.upper() for k in allowed_keys)
    clean = {
        k: v for k, v in _checked_env_pairs(raw_fwd_env)
        if all((not _denied_env_name(k, extra_denied_prefixes), bool({k.upper()} & allowed)))
    }
    return MappingProxyType(strip_bridge_secrets(clean))

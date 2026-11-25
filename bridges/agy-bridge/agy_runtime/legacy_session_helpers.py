"""Чистые хелперы legacy-хранилища sessions.json и нормализации входных параметров."""

# pyright: reportExplicitAny=false

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

_TOOLS_FP_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class LegacyLoadSpec:
    """Параметры чтения и валидации снимка legacy sessions.json."""

    version: int
    now: float
    cid_re: re.Pattern[str]
    is_expired: Callable[[dict[str, Any], float], bool]


def session_key_valid(sess_key: tuple[str, ...]) -> bool:
    """Стор принимает только ключ с непустым токеном чата или cwd."""
    if len(sess_key) == 4:
        return bool(sess_key[0].strip())
    if len(sess_key) == 3:
        return bool(sess_key[1].strip())
    return False


def session_key_to_json(key: tuple[object, ...]) -> list[str]:
    """Сериализовать кортеж ключа сессии в список строк для JSON."""
    return [str(part) for part in key]


def _normalized_key_cwd(cwd: str, is_v4: bool) -> str | None:
    stripped = cwd.strip()
    if not stripped:
        return "" if is_v4 else None
    return os.path.normpath(stripped) if os.path.isabs(stripped) else None


def session_key_from_json(raw: object) -> tuple[str, ...] | None:
    """Строковый ключ с токеном чата или cwd; вырожденный ключ -> None."""
    if not isinstance(raw, list):
        return None
    items = cast("list[object]", raw)
    if len(items) not in (3, 4) or not all(isinstance(part, str) for part in items):
        return None
    parts = list(cast("list[str]", items))
    is_v4 = len(parts) == 4
    if is_v4 and not parts[0].strip():
        return None
    cwd_index = 2 if is_v4 else 1
    normalized_cwd = _normalized_key_cwd(parts[cwd_index], is_v4)
    if normalized_cwd is None:
        return None
    parts[cwd_index] = normalized_cwd
    key = tuple(parts)
    return key if session_key_valid(key) else None


def _parse_finite_stamp(data: dict[str, object], name: str) -> float | None:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def session_entry_from_json(
    item: object, now: float, cid_re: re.Pattern[str], is_expired: Callable[[dict[str, Any], float], bool]
) -> dict[str, Any] | None:
    """Проверенная живая запись стора из JSON; битая или протухшая -> None."""
    if not isinstance(item, dict):
        return None
    data = cast("dict[str, object]", item)
    cid = data.get("cid")
    if not isinstance(cid, str) or cid_re.fullmatch(cid) is None:
        return None
    created = _parse_finite_stamp(data, "created")
    last_used = _parse_finite_stamp(data, "last_used")
    if created is None or last_used is None:
        return None
    turns = data.get("turns")
    if isinstance(turns, bool) or not isinstance(turns, int) or turns < 0:
        return None
    tools_fp = data.get("tools_fp", "")
    if not isinstance(tools_fp, str):
        return None
    if tools_fp and _TOOLS_FP_RE.fullmatch(tools_fp) is None:
        return None
    entry: dict[str, Any] = {
        "cid": cid, "created": created, "last_used": last_used,
        "turns": turns, "tools_fp": tools_fp,
    }
    return None if is_expired(entry, now) else entry


def _encode_sessions_payload(version: int, snapshot: dict[tuple[str, ...], dict[str, Any]]) -> bytes:
    records = [
        {
            "key": session_key_to_json(key), "cid": e["cid"], "created": e["created"],
            "last_used": e["last_used"], "turns": e["turns"], "tools_fp": e.get("tools_fp", ""),
        }
        for key, e in snapshot.items()
    ]
    return json.dumps({"version": version, "sessions": records}, ensure_ascii=False).encode("utf-8")


def atomic_write_sessions_json(
    path: Path, version: int, snapshot: dict[tuple[str, ...], dict[str, Any]], log_fn: Callable[[str], None]
) -> None:
    """Атомарно записать снимок стора: temp в том же каталоге + fsync + os.replace."""
    data = _encode_sessions_payload(version, snapshot)
    tmp_name = ""
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=str(path.parent), prefix=".sessions-", suffix=".tmp", delete=False) as fh:
            tmp_name = fh.name
            _ = fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, str(path))
        tmp_name = ""
    except OSError as exc:
        log_fn(f"sessions-persist-error err={type(exc).__name__}")
    finally:
        if tmp_name:
            with suppress(OSError):
                os.unlink(tmp_name)


def _extract_session_items(data: object, version: int) -> list[object]:
    if not isinstance(data, dict):
        return []
    doc = cast("dict[str, object]", data)
    if doc.get("version") != version:
        return []
    items = doc.get("sessions")
    return cast("list[object]", items) if isinstance(items, list) else []


def load_sessions_json_entries(
    path: Path, spec: LegacyLoadSpec, log_fn: Callable[[str], None]
) -> dict[tuple[str, ...], dict[str, Any]]:
    """Загрузить валидные не протухшие записи legacy sessions.json (fail-open)."""
    restored: dict[tuple[str, ...], dict[str, Any]] = {}
    data: object = None
    try:
        data = cast("object", json.loads(path.read_bytes()))
    except FileNotFoundError:
        data = None
    except (OSError, ValueError) as exc:
        log_fn(f"sessions-load-error err={type(exc).__name__} (fail-open)")
    for item in _extract_session_items(data, spec.version):
        if not isinstance(item, dict):
            continue
        item_dict = cast("dict[str, object]", item)
        key = session_key_from_json(item_dict.get("key"))
        entry = session_entry_from_json(item_dict, spec.now, spec.cid_re, spec.is_expired)
        if key is not None and entry is not None:
            restored[key] = entry
    return restored


def validate_clean_cid(
    raw_cid: object, cid_re: re.Pattern[str], log_fn: Callable[[str], None]
) -> tuple[str, bool]:
    """Проверить явный conversation_id; возвращает (cid_clean, force_cold)."""
    if raw_cid is None:
        return "", False
    if not isinstance(raw_cid, str):
        log_fn(f"cid-nonstring-rejected type={type(raw_cid).__name__}")
        return "", True
    val = raw_cid.strip()
    if not val:
        return "", False
    if cid_re.fullmatch(val):
        return val, False
    log_fn(f"cid-malformed-rejected cid={val[:16]!r}")
    return "", True


def _has_forbidden_cwd_chars(val: str) -> bool:
    return "\x00" in val or any(
        ord(ch) < 32 or ord(ch) == 127 or 0xD800 <= ord(ch) <= 0xDFFF for ch in val
    )


def normalize_request_cwd(
    raw_cwd: object, max_len: int, log_fn: Callable[[str], None]
) -> tuple[str, bool]:
    """Нормализовать cwd из запроса; возвращает (cwd, invalid)."""
    if raw_cwd is None:
        return "", False
    if not isinstance(raw_cwd, str):
        log_fn(f"cwd-nonstring-rejected type={type(raw_cwd).__name__}")
        return "", True
    val = raw_cwd.strip()
    if not val:
        return "", False
    if len(val) > max_len or not os.path.isabs(val) or _has_forbidden_cwd_chars(val):
        log_fn(f"cwd-invalid-rejected cwd={val[:32]!r}")
        return "", True
    return os.path.normpath(val), False

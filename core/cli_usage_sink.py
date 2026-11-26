"""Единый межпроцессно-безопасный JSONL-sink usage-телеметрии прямых терминальных CLI (fail-open).

Opt-in (`BRIDGE_CLI_USAGE_SINK_ENABLED`), строгий allowlist скаляров, потолок строки, защита от симлинков,
`flock` + ротация под локом. Любая ошибка записи → `False`, вызывающий процесс не падает.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Final

from core.log_redaction import redact_log_text

DEFAULT_CLI_USAGE_PATH: Final[str] = os.path.expanduser("~/.dsh/telemetry/cli-usage.jsonl")
PATH_ENV: Final[str] = "BRIDGE_CLI_USAGE_LOG_PATH"
ENABLED_ENV: Final[str] = "BRIDGE_CLI_USAGE_SINK_ENABLED"
MAX_SINK_LINE_BYTES: Final[int] = 4096
MAX_STR_CHARS: Final[int] = 256
_TRUTHY: Final[frozenset[str]] = frozenset(("1", "true", "yes", "on"))
_NOFOLLOW: Final[int] = getattr(os, "O_NOFOLLOW", 0)
_CONTROL_RE: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f-\x9f]")

CLI_USAGE_ALLOWLIST: Final[tuple[str, ...]] = (
    "ts", "request_id", "model", "subagent_id", "subagent_role", "route", "backend_id",
    "transport_kind", "stream", "http_status", "elapsed_ms", "prompt_tokens",
    "completion_tokens", "total_tokens", "cached_tokens", "cache_creation_tokens",
    "reasoning_tokens", "usage_present", "usage_missing_reason",
)


@dataclass(frozen=True)
class CliSinkConfig:
    """Параметры ротации и имя env-флага kill-switch."""

    max_bytes: int = 10 * 1024 * 1024
    max_archives: int = 10
    env_flag: str = ENABLED_ENV


def _clean_str(value: str) -> str:
    """Убрать управляющие символы, замаскировать секреты и обрезать до `MAX_STR_CHARS`."""
    text = _CONTROL_RE.sub("", value)[: MAX_STR_CHARS * 8]
    return redact_log_text(text)[:MAX_STR_CHARS]


def _clean_scalar(value: Any) -> bool | int | float | str | None:
    """Допустимы только `None|bool|int|float|str`; нефинитные float и прочие типы → None."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return _clean_str(value)
    return None


def sanitize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Оставить только поля allowlist со скалярными значениями (вложенное и чужие ключи отбрасываются)."""
    clean: dict[str, Any] = {}
    for key in CLI_USAGE_ALLOWLIST:
        value = _clean_scalar(record.get(key))
        if value is not None:
            clean[key] = value
    return clean


def _write_all(fd: int, data: bytes) -> None:
    """Одиночная запись с проверкой, что записаны все байты."""
    if os.write(fd, data) != len(data):
        raise OSError("short write")


class CliUsageSink:
    """Конкурентно-безопасный fail-open JSONL-sink: `write(record) -> bool`."""

    def __init__(self, path: str | None = None, config: CliSinkConfig | None = None) -> None:
        """Путь: аргумент > `BRIDGE_CLI_USAGE_LOG_PATH` > `DEFAULT_CLI_USAGE_PATH`."""
        cfg = config or CliSinkConfig()
        raw = path or os.environ.get(PATH_ENV) or DEFAULT_CLI_USAGE_PATH
        self._path = os.path.expanduser(raw)
        self._lock_path = self._path + ".lock"
        self._max_bytes = cfg.max_bytes
        self._max_archives = cfg.max_archives
        self._env_flag = cfg.env_flag

    def is_enabled(self) -> bool:
        """Kill-switch: включён только при `1|true|yes|on` (default OFF)."""
        return os.environ.get(self._env_flag, "").strip().lower() in _TRUTHY

    def write(self, record: Mapping[str, Any]) -> bool:
        """Дописать запись; `False` при выключенном флаге, переборе размера, симлинке или любой ошибке."""
        if not self.is_enabled():
            return False
        try:
            line = self._encode(record)
            if line is None or self._has_symlink():
                return False
            self._append(line)
            return True
        except Exception:  # fail-open (THREAT-003): телеметрия не роняет вызывающий процесс
            return False

    @staticmethod
    def _encode(record: Mapping[str, Any]) -> bytes | None:
        """Сериализовать санитизированную запись в UTF-8 строку; `None`, если она длиннее потолка."""
        clean = sanitize_record(record)
        clean.setdefault("ts", datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
        text = json.dumps(clean, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        data = (text + "\n").encode("utf-8")
        return data if len(data) <= MAX_SINK_LINE_BYTES else None

    def _has_symlink(self) -> bool:
        """THREAT-004: целевой файл или lock-файл — симлинк."""
        return os.path.islink(self._path) or os.path.islink(self._lock_path)

    def _append(self, line: bytes) -> None:
        """Под эксклюзивным flock: ротация по размеру и единый `os.write` в append-режиме."""
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, mode=0o700, exist_ok=True)
        lock_fd = os.open(self._lock_path, os.O_RDWR | os.O_CREAT | _NOFOLLOW, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            self._rotate_if_needed(len(line))
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | _NOFOLLOW
            fd = os.open(self._path, flags, 0o600)
            try:
                _write_all(fd, line)
            finally:
                os.close(fd)
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)

    def _rotate_if_needed(self, incoming: int) -> None:
        """Сдвинуть цепочку `.N-1 → .N … path → .1`, если `size + incoming > max_bytes`."""
        try:
            size = os.stat(self._path).st_size
        except FileNotFoundError:
            return
        if size == 0 or size + incoming <= self._max_bytes:
            return
        for idx in range(self._max_archives - 1, 0, -1):
            src = f"{self._path}.{idx}"
            if os.path.lexists(src):
                os.replace(src, f"{self._path}.{idx + 1}")
        os.replace(self._path, f"{self._path}.1")


def _anthropic_usage(u: Mapping[str, Any]) -> dict[str, Any]:
    """Anthropic: `input_tokens` без кэша → prompt = input + cache_read + cache_creation."""
    inp, out = _num(u, "input_tokens"), _num(u, "output_tokens")
    read, create = _num(u, "cache_read_input_tokens"), _num(u, "cache_creation_input_tokens")
    return {
        "prompt_tokens": inp + read + create, "completion_tokens": out,
        "cached_tokens": read, "cache_creation_tokens": create,
    }


def _num(src: Mapping[str, Any], key: str) -> int:
    """Неотрицательное целое из словаря (`bool`, нечисла и мусор → 0)."""
    val = src.get(key)
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
        return 0
    return max(int(val), 0)


def _openai_usage(u: Mapping[str, Any]) -> dict[str, Any]:
    """OpenAI/`UsageReport`/codex: `prompt_tokens`/`input_tokens` уже включают кэш."""
    det = u.get("prompt_tokens_details")
    cdet = u.get("completion_tokens_details")
    det, cdet = (det if isinstance(det, Mapping) else {}), (cdet if isinstance(cdet, Mapping) else {})
    prompt = _num(u, "prompt_tokens") or _num(u, "input_tokens")
    cached = _num(u, "cached_tokens") or _num(u, "cached_input_tokens") or _num(det, "cached_tokens")
    reasoning = (
        _num(u, "reasoning_tokens") or _num(u, "reasoning_output_tokens") or _num(cdet, "reasoning_tokens")
    )
    return {
        "prompt_tokens": prompt,
        "completion_tokens": _num(u, "completion_tokens") or _num(u, "output_tokens"),
        "total_tokens": _num(u, "total_tokens"),
        "cached_tokens": cached, "cache_creation_tokens": _num(u, "cache_creation_tokens"),
        "reasoning_tokens": reasoning,
    }


def _normalize_usage(u: Mapping[str, Any]) -> dict[str, Any] | None:
    """Свести usage-словарь любого формата к каноническим полям; `None`, если токенов нет."""
    anthropic = "cache_read_input_tokens" in u or "cache_creation_input_tokens" in u
    out = _anthropic_usage(u) if anthropic else _openai_usage(u)
    if not any(out.values()):
        return None
    if not out.get("total_tokens"):
        out["total_tokens"] = out["prompt_tokens"] + out["completion_tokens"]
    out["usage_present"] = True
    return out


def _from_object(obj: Mapping[str, Any]) -> dict[str, Any] | None:
    """Один JSON-объект: claude `result`, codex `turn.completed`, обёртка `{usage:{…}}` или плоский usage."""
    inner = obj.get("usage")
    source = inner if isinstance(inner, Mapping) else obj
    result = _normalize_usage(source)
    if result is None:
        return None
    for key in CLI_USAGE_ALLOWLIST:  # метаданные UsageReport верхнего уровня (model, request_id, …)
        if key not in result and key in obj and not isinstance(obj[key], (dict, list)):
            result[key] = obj[key]
    duration = obj.get("duration_ms")
    if "elapsed_ms" not in result and isinstance(duration, (int, float)) and not isinstance(duration, bool):
        result["elapsed_ms"] = duration
    return result


def parse_cli_usage_payload(raw_text: str) -> dict[str, Any] | None:
    """Разобрать плоский JSON либо NDJSON (`claude -p stream-json`, `codex exec --json`); `None` — usage нет."""
    text = raw_text.strip()
    candidates: list[Any] = []
    try:
        candidates.append(json.loads(text))
    except ValueError:
        for line in text.splitlines():
            try:
                candidates.append(json.loads(line))
            except ValueError:
                continue
    found: dict[str, Any] | None = None
    for obj in candidates:
        parsed = _from_object(obj) if isinstance(obj, Mapping) else None
        found = parsed or found  # последний usage-событие выигрывает (`result` / `turn.completed`)
    return found

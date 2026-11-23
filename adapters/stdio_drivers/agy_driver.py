"""NDJSON-драйвер `agy` для резидентного stdio-пула (AD-003); дефолт — выключено."""

# pyright: reportAny=false, reportExplicitAny=false
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any, ClassVar, TypeVar, cast, override

# fmt: off
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.protocol_driver import DecodedChunk, DecodedChunk as _Chunk, DriverCapabilities, StreamJsonDriver
__all__ = ["FLAG_AGY_RESIDENT", "AgyResidentConfig", "AgyStreamJsonDriver", "build_agy_pool_config", "load_agy_resident_config"]
# fmt: on
_Num = TypeVar("_Num", int, float)
_Dict = dict[str, Any]
_Map = Mapping[str, Any]
FLAG_AGY_RESIDENT = "AGY_RESIDENT_ENABLED"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on", "y", "t", "enabled"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", "n", "f", "disabled"})
_INTERNAL_CTX_KEYS = frozenset({"turn_sandbox", "cwd", "review_profile"})
_REASONING_KEYS = ("reasoning", "thinking", "thought", "reasoning_content")
_EVENT_KEYS = ("type", "event")
_THINK_TYPES = ("thinking", "reasoning")
_THINK_KEYS = ("thinking", "reasoning", "text")
_TOOL_TYPES = ("tool_use", "tool_call")


@dataclass(frozen=True)
class AgyResidentConfig:
    enabled: bool = False
    max_slots: int = 8
    idle_timeout_s: float = 600.0
    ttl_s: float = 3600.0
    max_rss_mb: int = 1024
    max_turns: int = 100
    lease_wait_timeout_s: float = 30.0


def _raw(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)
    return (value.strip() or None) if value is not None else None


def _parse_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    if (raw := _raw(env, key)) is None:
        return default
    norm = raw.lower()
    if norm in _TRUE_VALUES or norm in _FALSE_VALUES:
        return norm in _TRUE_VALUES
    raise ValueError(f"{key} must be a boolean, got {raw!r}")


def _parse_num(
    env: Mapping[str, str], key: str, conv: Callable[[str], _Num], default: _Num
) -> _Num:
    if (raw := _raw(env, key)) is None:
        return default
    try:
        value = conv(raw)
    except ValueError:
        raise ValueError(f"{key} must be a number, got {raw!r}") from None
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{key} must be finite, got {raw!r}")
    return value


def load_agy_resident_config(
    env: Mapping[str, str], ladder_idle_s: float = 600.0
) -> AgyResidentConfig:
    """Конфиг из явного окружения без `os.environ`; idle — env или лестница (не 180 c)."""
    if not math.isfinite(ladder_idle_s):
        raise ValueError(f"ladder_idle_s must be finite, got {ladder_idle_s!r}")
    d, p = AgyResidentConfig(), _parse_num
    return AgyResidentConfig(
        enabled=_parse_bool(env, FLAG_AGY_RESIDENT, d.enabled),
        max_slots=p(env, "AGY_RESIDENT_MAX_SLOTS", int, d.max_slots),
        idle_timeout_s=p(
            env, "AGY_RESIDENT_IDLE_TIMEOUT_S", float, float(ladder_idle_s)
        ),
        ttl_s=p(env, "AGY_RESIDENT_TTL_S", float, d.ttl_s),
        max_rss_mb=p(env, "AGY_RESIDENT_MAX_RSS_MB", int, d.max_rss_mb),
        max_turns=p(env, "AGY_RESIDENT_MAX_TURNS", int, d.max_turns),
        lease_wait_timeout_s=p(
            env, "AGY_RESIDENT_LEASE_WAIT_S", float, d.lease_wait_timeout_s
        ),
    )


def build_agy_pool_config(cfg: AgyResidentConfig) -> StdioPoolConfig:
    """Маппинг в `StdioPoolConfig`; idle — из лестницы; `max_turns` там нет."""
    return StdioPoolConfig(
        max_slots=cfg.max_slots,
        idle_timeout_s=cfg.idle_timeout_s,
        ttl_s=cfg.ttl_s,
        max_rss_bytes=cfg.max_rss_mb * 1024 * 1024,
        lease_wait_s=cfg.lease_wait_timeout_s,
        enabled=cfg.enabled,
        turn_idle_timeout_s=cfg.idle_timeout_s,
    )


class AgyStreamJsonDriver(StreamJsonDriver):
    _capabilities: ClassVar[DriverCapabilities] = DriverCapabilities(
        "agy-stream-json", supports_soft_cancel=True
    )

    def __init__(self, config: AgyResidentConfig | None = None) -> None:
        self._config: AgyResidentConfig = config or AgyResidentConfig()

    @property
    def config(self) -> AgyResidentConfig:
        return self._config

    @override
    def build_argv(self, base_argv: list[str], options: _Map) -> list[str]:
        argv = list(base_argv)
        self._ensure_pair(argv, "--input-format", "stream-json")
        self._ensure_pair(argv, "--output-format", "stream-json")
        self._ensure_pair(argv, "--print-timeout", "0")
        if model := self._option_str(options, "model"):
            self._ensure_pair(argv, "--model", model)
        if effort := self._option_str(options, "effort"):
            self._ensure_pair(argv, "--effort", effort)
        if cid := self._option_str(options, "conversation", "conversation_id", "cid"):
            self._ensure_pair(argv, "--conversation", cid)
        return argv

    @override
    def encode_turn(self, prompt: str, turn_context: _Map | None = None) -> bytes:
        msg: _Dict = {"role": "user", "content": prompt}
        payload: _Dict = {"type": "user", "event": "user", "message": msg}
        for key, value in (turn_context or {}).items():
            if key not in _INTERNAL_CTX_KEYS and key not in payload:
                payload[key] = value
        return (json.dumps(payload, ensure_ascii=False) + "\n").encode()

    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        if (payload := self._parse_object(raw_line)) is None:
            return None
        event = self._first_str(payload, _EVENT_KEYS)
        if event == "result":
            return self._decode_result(payload)
        step = self._mapping(payload.get("step_update"))
        if step is not None or event == "step_update":
            return self._decode_step(payload, step or {})
        text, think, calls = self._generic_parts(payload)
        return self._chunk(payload, text, think, calls, self._error_text(payload))

    @override
    def is_terminal(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        if decoded is not None and decoded.is_terminal:
            return True
        payload = self._parse_object(raw_line)
        return payload is not None and self._first_str(payload, _EVENT_KEYS) == "result"

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        chunk = decoded if decoded is not None else self.decode_line(raw_line)
        return bool(chunk is not None and chunk.is_tool_stop)

    @override
    def compute_fingerprint(self) -> str:
        cfg = asdict(self._config)
        obj = {"protocol": "agy-stream-json", "version": "v1", "config": cfg}
        raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _decode_result(self, payload: _Dict) -> DecodedChunk:
        raw, fs = payload.get("result"), self._first_str
        inner = self._mapping(raw) or {}
        text = (
            raw if isinstance(raw, str) else fs(inner, ("response", "result", "text"))
        )
        text = text or fs(payload, ("text",))
        err = self._result_error(payload, inner, text)
        think = self._extract_string(payload, _REASONING_KEYS)
        calls = self._extract_tool_calls(payload)
        return replace(
            self._chunk(payload, text, think, calls, err),
            is_terminal=True,
            is_tool_stop=False,
        )

    def _result_error(self, payload: _Dict, inner: _Dict, text: str) -> str | None:
        if (error := self._error_text(inner) or self._error_text(payload)) is not None:
            return error
        status = str(inner.get("status") or payload.get("status") or "").lower()
        return (
            (text or "agy error")
            if (status == "error" or payload.get("is_error") is True)
            else None
        )

    def _decode_step(self, payload: _Dict, step: _Dict) -> DecodedChunk:
        kind = str(step.get("step_type") or step.get("type") or "")
        calls = self._extract_tool_calls(step) or self._extract_tool_calls(payload)
        text, think, calls = self._step_fields(kind, step, calls)
        return self._chunk(
            payload,
            text,
            think,
            calls,
            self._error_text(step) or self._error_text(payload),
        )

    def _step_fields(
        self, kind: str, step: _Dict, calls: list[_Dict]
    ) -> tuple[str, str, list[_Dict]]:
        fs, text, think = self._first_str, "", ""
        if kind == "agent_response":
            text = fs(step, ("text_delta", "text", "content", "delta"))
        elif kind in ("tool", "tool_use", "tool_call") and not calls:
            calls = [dict(step)]
        elif kind in ("reasoning", "thinking", "thought"):
            think = fs(step, ("text_delta", "text", "content"))
        think = think or fs(step, _REASONING_KEYS)
        return text or ("" if calls else fs(step, ("text_delta",))), think, calls

    def _generic_parts(self, payload: _Dict) -> tuple[str, str, list[_Dict]]:
        text = self._extract_string(payload, ("content", "delta", "text", "response"))
        think = self._extract_string(payload, _REASONING_KEYS)
        calls = self._extract_tool_calls(payload)
        if (msg := self._mapping(payload.get("message"))) is not None:
            mt, mr, mc = self._message_parts(msg)
            text, think, calls = text or mt, think or mr, calls or mc
        if (ev := self._mapping(payload.get("event"))) is not None:
            text = text or self._extract_string(ev, ("text", "delta", "content"))
            think = think or self._extract_string(ev, _REASONING_KEYS)
            calls = calls or self._extract_tool_calls(ev)
        return text, think, calls

    def _message_parts(self, message: _Dict) -> tuple[str, str, list[_Dict]]:
        content = message.get("content")
        if isinstance(content, str):
            return content, "", self._extract_tool_calls(message)
        texts, thinks, calls = (
            cast(list[str], []),
            cast(list[str], []),
            cast(list[_Dict], []),
        )
        for item in self._content_items(content):
            kind = item.get("type")
            if kind == "text":
                texts.append(self._first_str(item, ("text",)))
            elif kind in _THINK_TYPES:
                thinks.append(self._first_str(item, _THINK_KEYS))
            elif kind in _TOOL_TYPES:
                calls.append(item)
        return (
            "".join(texts),
            "".join(thinks),
            calls or self._extract_tool_calls(message),
        )

    def _content_items(self, content: Any) -> list[_Dict]:
        blocks = cast(list[object], content) if isinstance(content, list) else []
        return [m for b in blocks if (m := self._mapping(b)) is not None]

    @staticmethod
    def _chunk(
        raw: _Dict, text: str, think: str, calls: list[_Dict], error: str | None
    ) -> DecodedChunk:
        return _Chunk(text, think, calls, error is not None, bool(calls), raw, error)

    @staticmethod
    def _error_text(container: _Map) -> str | None:
        raw = container.get("error")
        if isinstance(raw, str):
            return raw if raw.strip() else None
        if isinstance(raw, dict):
            err = cast(_Dict, raw)
            message = err.get("message") or err.get("error")
            return str(message) if message else "agy error"
        return str(raw) if raw else None

    @staticmethod
    def _first_str(container: _Map, keys: tuple[str, ...]) -> str:
        values = (container.get(key) for key in keys)
        return next((v for v in values if isinstance(v, str) and v), "")

    @staticmethod
    def _option_str(options: _Map, *keys: str) -> str:
        values = (str(v).strip() for k in keys if (v := options.get(k)) is not None)
        return next((v for v in values if v), "")

    @staticmethod
    def _ensure_pair(argv: list[str], flag: str, value: str) -> None:
        if all(i != flag and not i.startswith(f"{flag}=") for i in argv):
            argv.extend((flag, value))

    @staticmethod
    def _mapping(value: Any) -> _Dict | None:
        return cast(_Dict, value) if isinstance(value, dict) else None

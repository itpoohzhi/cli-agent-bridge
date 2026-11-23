"""NDJSON-драйвер `agy` для резидентного stdio-пула (AD-003); дефолт — выключено."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import asdict, replace
from typing import ClassVar, cast, override

from adapters.stdio_drivers.agy_config import (
    FLAG_AGY_RESIDENT,
    AgyResidentConfig,
    build_agy_pool_config,
    encode_json_bytes,
    load_agy_resident_config,
)
from core.stdio_resident.protocol_driver import (
    DecodedChunk,
    DecodedChunk as _Chunk,
    DriverCapabilities,
    StreamJsonDriver,
)

__all__ = [
    "FLAG_AGY_RESIDENT",
    "AgyResidentConfig",
    "AgyStreamJsonDriver",
    "build_agy_pool_config",
    "load_agy_resident_config",
]

_Dict = dict[str, object]
_Map = Mapping[str, object]
_INTERNAL_CTX_KEYS = frozenset({"turn_sandbox", "cwd", "review_profile"})
_REASONING_KEYS = ("reasoning", "thinking", "thought", "reasoning_content")
_EVENT_KEYS = ("type", "event")
_THINK_TYPES = ("thinking", "reasoning")
_THINK_KEYS = ("thinking", "reasoning", "text")
_TOOL_TYPES = ("tool_use", "tool_call")


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
        return encode_json_bytes(payload) + b"\n"

    @override
    def decode_line(self, raw_line: str) -> DecodedChunk | None:
        payload = self._mapping(self._parse_object(raw_line))
        if payload is None:
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
        payload = self._mapping(self._parse_object(raw_line))
        return payload is not None and self._first_str(payload, _EVENT_KEYS) == "result"

    @override
    def is_tool_stop(self, raw_line: str, decoded: DecodedChunk | None) -> bool:
        chunk = decoded if decoded is not None else self.decode_line(raw_line)
        return bool(chunk is not None and chunk.is_tool_stop)

    @override
    def compute_fingerprint(self) -> str:
        obj = {
            "protocol": "agy-stream-json",
            "version": "v1",
            "config": asdict(self._config),
        }
        return hashlib.sha256(encode_json_bytes(obj, sort_keys=True)).hexdigest()

    def _decode_result(self, payload: _Dict) -> DecodedChunk:
        raw, fs = payload.get("result"), self._first_str
        inner = self._mapping(raw) or {}
        text = (
            raw if isinstance(raw, str) else fs(inner, ("response", "result", "text"))
        )
        text = text or fs(payload, ("text",))
        err = self._result_error(payload, inner, text)
        think = self._extract_string(payload, _REASONING_KEYS)
        calls = self._calls(payload)
        chunk = self._chunk(payload, text, think, calls, err)
        return replace(chunk, is_terminal=True, is_tool_stop=False)

    def _result_error(self, payload: _Dict, inner: _Dict, text: str) -> str | None:
        if (error := self._error_text(inner) or self._error_text(payload)) is not None:
            return error
        status = str(inner.get("status") or payload.get("status") or "").lower()
        failed = status == "error" or payload.get("is_error") is True
        return (text or "agy error") if failed else None

    def _decode_step(self, payload: _Dict, step: _Dict) -> DecodedChunk:
        kind = str(step.get("step_type") or step.get("type") or "")
        calls = self._calls(step) or self._calls(payload)
        text, think, calls = self._step_fields(kind, step, calls)
        err = self._error_text(step) or self._error_text(payload)
        return self._chunk(payload, text, think, calls, err)

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
        calls = self._calls(payload)
        if (msg := self._mapping(payload.get("message"))) is not None:
            mt, mr, mc = self._message_parts(msg)
            text, think, calls = text or mt, think or mr, calls or mc
        if (ev := self._mapping(payload.get("event"))) is not None:
            text = text or self._extract_string(ev, ("text", "delta", "content"))
            think = think or self._extract_string(ev, _REASONING_KEYS)
            calls = calls or self._calls(ev)
        return text, think, calls

    def _message_parts(self, message: _Dict) -> tuple[str, str, list[_Dict]]:
        content = message.get("content")
        if isinstance(content, str):
            return content, "", self._calls(message)
        texts: list[str] = []
        thinks: list[str] = []
        calls: list[_Dict] = []
        blocks = cast("list[object]", content) if isinstance(content, list) else []
        for item in (m for b in blocks if (m := self._mapping(b)) is not None):
            kind = item.get("type")
            if kind == "text":
                texts.append(self._first_str(item, ("text",)))
            elif kind in _THINK_TYPES:
                thinks.append(self._first_str(item, _THINK_KEYS))
            elif kind in _TOOL_TYPES:
                calls.append(item)
        return "".join(texts), "".join(thinks), calls or self._calls(message)

    def _calls(self, payload: _Dict) -> list[_Dict]:
        return [dict(c) for c in self._extract_tool_calls(payload)]

    @staticmethod
    def _chunk(
        raw: _Dict, text: str, think: str, calls: list[_Dict], err: str | None
    ) -> DecodedChunk:
        return _Chunk(text, think, calls, err is not None, bool(calls), raw, err)

    @staticmethod
    def _error_text(container: _Map) -> str | None:
        raw = container.get("error")
        if isinstance(raw, str):
            return raw if raw.strip() else None
        if isinstance(raw, dict):
            err = cast("_Dict", raw)
            msg = err.get("message") or err.get("error")
            return str(msg) if msg else "agy error"
        return str(raw) if raw else None

    @staticmethod
    def _first_str(container: _Map, keys: tuple[str, ...]) -> str:
        return next(
            (v for k in keys if isinstance(v := container.get(k), str) and v), ""
        )

    @staticmethod
    def _option_str(options: _Map, *keys: str) -> str:
        return next(
            (
                s
                for k in keys
                if (v := options.get(k)) is not None and (s := str(v).strip())
            ),
            "",
        )

    @staticmethod
    def _ensure_pair(argv: list[str], flag: str, value: str) -> None:
        if all(i != flag and not i.startswith(f"{flag}=") for i in argv):
            argv.extend((flag, value))

    @staticmethod
    def _mapping(value: object) -> _Dict | None:
        return cast("_Dict", value) if isinstance(value, dict) else None

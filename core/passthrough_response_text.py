"""Шовные функции passthrough для текста ответа: choice-вызовы и нормализация.

Вынесено из адаптера (F-001): чистые функции без I/O, адаптер реэкспортирует имена.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any, Mapping, Optional

from core.tool_emulation import (
    DEFAULT_EMULATE_SPEC,
    LiveParserError,
    NormalizerModeSpec,
    NormalizerSinks,
    StreamNormalizer,
    ToolCallParser,
    ToolMode,
    has_any_unnamed_call,
    sanitize_tool_call,
)
from core.tool_mode import check_unexpected_tool_calls

if TYPE_CHECKING:  # pragma: no cover - только типы, без циклического импорта
    from adapters.passthrough_adapter import PassthroughLimits


def new_call_id() -> str:
    return "call_" + uuid.uuid4().hex[:24]


def sanitize_choice_calls(
    calls: list[dict[str, Any]],
    tool_schemas: Optional[dict[str, Any]],
    limits: "PassthroughLimits",
) -> list[dict[str, Any]]:
    """Санитизация вызовов одной choice; `index` меняется только если `parallel` изменил число вызовов."""
    mpc, mpd = limits.max_parallel_calls, limits.max_parallel_depth
    groups = [
        sanitize_tool_call(
            c, tool_schemas, max_parallel_calls=mpc, max_parallel_depth=mpd
        )
        for c in calls
    ]
    flat = [item for group in groups for item in group]
    unpacked = any(
        len(group) != 1 or group[0].get("id") != call.get("id")
        for group, call in zip(groups, calls)
    )
    if not unpacked:
        return flat
    return [
        dict(item, index=i) if "index" in item else item for i, item in enumerate(flat)
    ]


def _check_native(spec: NormalizerModeSpec, calls: Any) -> None:
    try:
        check_unexpected_tool_calls(spec.mode, calls)
    except ValueError:
        raise LiveParserError("unexpected upstream tool calls") from None


def _openai_call(call: Mapping[str, Any]) -> dict[str, Any]:
    args = call.get("arguments")
    arguments = (
        args if isinstance(args, str) else json.dumps(args or {}, ensure_ascii=False)
    )
    return {
        "id": str(call.get("id") or new_call_id()),
        "type": "function",
        "function": {"name": str(call.get("name") or ""), "arguments": arguments},
    }


class _ResponseText:
    """Локальный текстовый шов choice; запрещённые режимы не создают ToolCallParser."""

    def __init__(self, spec: NormalizerModeSpec, schemas: Any, enabled: bool) -> None:
        self.content: list[str] = []
        self.reasoning: list[str] = []
        self.calls: list[dict[str, Any]] = []
        self.parser: ToolCallParser | StreamNormalizer | None = None
        sinks = NormalizerSinks(
            self.content.append, self.reasoning.append, self.calls.append
        )
        if spec.mode is not ToolMode.EMULATE:
            self.parser = StreamNormalizer.for_mode(spec, sinks, strict_live=True)
        elif enabled:
            self.parser = ToolCallParser(
                self.content.append,
                self.calls.append,
                tool_schemas=schemas,
                repetition_guard_enabled=False,
            )

    def _output(self) -> dict[str, str]:
        output = {
            "content": "".join(self.content),
            "reasoning_content": "".join(self.reasoning),
        }
        self.content.clear()
        self.reasoning.clear()
        return {key: text for key, text in output.items() if text}

    def feed(self, delta: dict[str, Any]) -> dict[str, Any]:
        if self.parser is None:
            return dict(delta)
        result = dict(delta)
        text = delta.get("content")
        if isinstance(text, str) and text:
            result.pop("content")
            self.parser.feed(text)
        reasoning = delta.get("reasoning_content")
        if isinstance(reasoning, str) and isinstance(self.parser, StreamNormalizer):
            result.pop("reasoning_content")
            self.parser.feed_thinking(reasoning)
        result.update(self._output())
        return result

    def finish(self) -> dict[str, str]:
        if self.parser is not None:
            self.parser.finish()
        return self._output()


def _merge_parsed_calls(
    raw_calls: Any, parsed: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    valid = isinstance(raw_calls, list) and all(
        isinstance(call, dict) for call in raw_calls
    )
    calls = list(raw_calls) if valid else []
    indexed = any("index" in call for call in calls)
    indices = [call["index"] for call in calls if type(call.get("index")) is int]
    next_index = max(indices, default=len(calls) - 1) + 1
    for call in parsed:
        entry = _openai_call(call)
        if indexed:
            entry["index"] = next_index
            next_index += 1
        calls.append(entry)
    return calls


def _normalize_message(
    message: dict[str, Any],
    schemas: Any,
    limits: "PassthroughLimits",
    options: tuple[NormalizerModeSpec, bool],
) -> bool:
    spec, sanitize = options
    raw_calls = message.get("tool_calls")
    _check_native(spec, raw_calls)
    text = _ResponseText(
        spec, schemas, sanitize and limits.invoke_normalization_enabled
    )
    updated = text.feed(message)
    for key, tail in text.finish().items():
        updated[key] = (updated.get(key) or "") + tail
    calls = _merge_parsed_calls(raw_calls, text.calls)
    if sanitize and calls:
        if has_any_unnamed_call(calls, max_parallel_depth=limits.max_parallel_depth):
            raise LiveParserError("tool call has empty function name")
        updated["tool_calls"] = sanitize_choice_calls(calls, schemas, limits)
    if "content" in message:
        updated.setdefault("content", "")
    if updated == message:
        return False
    message.clear()
    message.update(updated)
    return True


def sanitize_completion_body(
    body: bytes,
    tool_schemas: Optional[dict[str, Any]],
    limits: "PassthroughLimits",
    mode_spec: NormalizerModeSpec = DEFAULT_EMULATE_SPEC,
    *,
    sanitize: bool = True,
) -> bytes:
    """Проверяет режим и нормализует JSON; неизменённый ответ сохраняет исходные байты."""
    try:
        data = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return body
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list):
        return body
    changed = False
    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) else None
        if isinstance(message, dict):
            changed = (
                _normalize_message(message, tool_schemas, limits, (mode_spec, sanitize))
                or changed
            )
    return json.dumps(data, ensure_ascii=False).encode("utf-8") if changed else body

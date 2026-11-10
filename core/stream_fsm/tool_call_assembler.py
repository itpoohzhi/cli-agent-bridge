"""Конечный автомат сборки tool_calls и reasoning_content (ADR-0020)."""

from __future__ import annotations

import json
import re
from typing import List, Optional, Tuple

from core.stream_fsm.types import EmitChunk, EmitToolCall, StreamEffect

MAX_TOOL_CALL_BUFFER = 262144  # S_frame_max (256 KiB)

TOOL_CALL_OPEN_RE = re.compile(r"<tool_call>|<function_call>|<invoke>")
TOOL_CALL_CLOSE_RE = re.compile(r"</tool_call>|</function_call>|</invoke>")
THINK_OPEN_RE = re.compile(r"<think>|<thought>|<reasoning>")
THINK_CLOSE_RE = re.compile(r"</think>|</thought>|</reasoning>")
POTENTIAL_TAG_RE = re.compile(r"</?[a-zA-Z0-9_]*$")


class ToolCallAssembler:
    """Детерминированный сборщик вызовов инструментов и блоков мышления."""

    def __init__(self, max_buffer: int = MAX_TOOL_CALL_BUFFER) -> None:
        self.max_buffer = max_buffer
        self._raw_buffer: list[str] = []
        self._buffer_len = 0
        self._in_tool_call = False
        self._in_reasoning = False
        self._call_counter = 0
        self._pending_tag = ""

    @property
    def in_tool_call(self) -> bool:
        return self._in_tool_call

    @property
    def in_reasoning(self) -> bool:
        return self._in_reasoning

    def reset(self) -> None:
        self._raw_buffer.clear()
        self._buffer_len = 0
        self._in_tool_call = False
        self._in_reasoning = False
        self._call_counter = 0
        self._pending_tag = ""

    def _parse_assembled_tool_call(self, payload: str) -> Optional[EmitToolCall]:
        """Извлекает имя и аргументы функции из JSON или XML содержимого."""
        payload = payload.strip()
        call_id = f"call_{self._call_counter}"
        try:
            parsed = json.loads(payload)
            if isinstance(parsed, dict):
                name = parsed.get("name") or parsed.get("function", "")
                args = parsed.get("arguments") or parsed.get("parameters", {})
                arguments = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
                self._call_counter += 1
                return EmitToolCall(index=self._call_counter - 1, call_id=call_id, name=str(name), arguments=arguments)
        except Exception:
            pass

        name_match = re.search(r"<name>(.*?)</name>", payload, re.DOTALL)
        name = name_match.group(1).strip() if name_match else ""
        args_match = re.search(r"<arguments>(.*?)</arguments>", payload, re.DOTALL)
        arguments = args_match.group(1).strip() if args_match else "{}"

        if name:
            self._call_counter += 1
            return EmitToolCall(index=self._call_counter - 1, call_id=call_id, name=name, arguments=arguments)
        return None

    def _feed_reasoning(self, text: str) -> Tuple[str, List[StreamEffect]]:
        """Обрабатывает текст внутри тега размышлений."""
        close_m = THINK_CLOSE_RE.search(text)
        if close_m:
            pre = text[:close_m.start()]
            eff: List[StreamEffect] = [EmitChunk(text=pre, is_reasoning=True)] if pre else []
            self._in_reasoning = False
            return text[close_m.end():], eff
        tail: List[StreamEffect] = [EmitChunk(text=text, is_reasoning=True)]
        return "", tail

    def _feed_tool_call(self, text: str) -> Tuple[str, List[StreamEffect]]:
        """Накапливает полезную нагрузку tool_call до закрывающего тега."""
        close_m = TOOL_CALL_CLOSE_RE.search(text)
        if close_m:
            pre = text[:close_m.start()]
            self._raw_buffer.append(pre)
            full_payload = "".join(self._raw_buffer)
            self._raw_buffer.clear()
            self._buffer_len = 0
            self._in_tool_call = False
            tc = self._parse_assembled_tool_call(full_payload)
            done: List[StreamEffect] = [tc] if tc else []
            return text[close_m.end():], done
        if self._buffer_len + len(text) <= self.max_buffer:
            self._raw_buffer.append(text)
            self._buffer_len += len(text)
        return "", []

    def _feed_plain_text(self, text: str) -> Tuple[str, List[StreamEffect]]:
        """Обрабатывает обычный текст вне специальных блоков."""
        think_m = THINK_OPEN_RE.search(text)
        tool_m = TOOL_CALL_OPEN_RE.search(text)
        earliest_idx, match_type, match_end = len(text), None, 0

        if think_m and think_m.start() < earliest_idx:
            earliest_idx, match_type, match_end = think_m.start(), "think", think_m.end()
        if tool_m and tool_m.start() < earliest_idx:
            earliest_idx, match_type, match_end = tool_m.start(), "tool", tool_m.end()

        effects: List[StreamEffect] = []
        if match_type == "think":
            pre = text[:earliest_idx]
            effects = [EmitChunk(text=pre, is_reasoning=False)] if pre else []
            self._in_reasoning = True
            return text[match_end:], effects
        if match_type == "tool":
            pre = text[:earliest_idx]
            effects = [EmitChunk(text=pre, is_reasoning=False)] if pre else []
            self._in_tool_call = True
            self._raw_buffer.clear()
            self._buffer_len = 0
            return text[match_end:], effects

        effects = [EmitChunk(text=text, is_reasoning=False)]
        return "", effects

    def feed(self, piece: str) -> List[StreamEffect]:
        """Обрабатывает поступающий фрагмент текста и возвращает список эффектов."""
        if not piece and not self._pending_tag:
            return []

        text = self._pending_tag + piece
        self._pending_tag = ""
        effects: List[StreamEffect] = []

        pot = POTENTIAL_TAG_RE.search(text)
        if pot and len(pot.group(0)) <= 32 and not pot.group(0).endswith(">"):
            self._pending_tag = pot.group(0)
            text = text[:pot.start()]

        while text:
            if self._in_reasoning:
                text, chunk_eff = self._feed_reasoning(text)
            elif self._in_tool_call:
                text, chunk_eff = self._feed_tool_call(text)
            else:
                text, chunk_eff = self._feed_plain_text(text)
            effects.extend(chunk_eff)

        return effects

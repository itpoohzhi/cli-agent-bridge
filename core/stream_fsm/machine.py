"""Чистый конечный автомат управления потоком (ADR-0020, F-FSM-I1..I3)."""

from __future__ import annotations

import codecs
import json
from typing import List, Tuple, Union

from core.stream_fsm.repetition_guard import StreamRepetitionGuard
from core.stream_fsm.tool_call_assembler import ToolCallAssembler
from core.stream_fsm.types import (
    CancelRequested,
    ChunkReceived,
    EmitChunk,
    EmitSSE,
    EmitToolCall,
    ProtocolError,
    RecordMetric,
    StreamEffect,
    StreamEvent,
    StreamState,
    TriggerKillpg,
    UpstreamEOF,
)

SSE_PREFIXES = ("data:", "event:", "id:", ":")


def step(state: StreamState, event: StreamEvent) -> Tuple[StreamState, List[StreamEffect]]:
    """Чистая функция перехода автомата без I/O и глобальных мутаций (F-FSM-I1)."""
    effects: List[StreamEffect] = []

    if isinstance(event, CancelRequested):
        effects.append(TriggerKillpg(pgid=event.pgid, epoch=event.epoch))
        return StreamState.CLOSED, effects

    if isinstance(event, UpstreamEOF):
        effects.append(EmitSSE(event="done", data="[DONE]"))
        return StreamState.COMPLETED, effects

    if isinstance(event, ProtocolError):
        effects.append(EmitSSE(event="error", data=json.dumps({"error": event.message})))
        return StreamState.CLOSED, effects

    if state in (StreamState.COMPLETED, StreamState.CLOSED):
        return state, effects

    if isinstance(event, ChunkReceived):
        new_state = StreamState.STREAMING if state == StreamState.IDLE else state
        return new_state, effects

    return state, effects


class StreamMachine:
    """Координатор потокового автомата с инкрементальным UTF-8 декодером."""

    def __init__(
        self,
        max_repeats: int = 4,
        max_token_len: int = 32,
        session_epoch: int = 1,
    ) -> None:
        self.state = StreamState.IDLE
        self.session_epoch = int(session_epoch)
        self.guard = StreamRepetitionGuard(max_repeats=max_repeats, max_token_len=max_token_len)
        self.assembler = ToolCallAssembler()
        self._utf8_decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._stale_chunks_rejected = 0
        self._buffer = ""
        self._mode = "auto"

    @property
    def loop_detected(self) -> bool:
        return self.guard.detected

    def reset(self, new_epoch: int | None = None) -> None:
        self.state = StreamState.IDLE
        if new_epoch is not None:
            self.session_epoch = int(new_epoch)
        self.guard.reset()
        self.assembler.reset()
        self._utf8_decoder.reset()
        self._buffer = ""
        self._mode = "auto"

    def _parse_sse_payload(self, payload: str, epoch: int) -> List[StreamEffect]:
        """Разбирает тело одного SSE фрейма data: ..."""
        if payload == "[DONE]":
            self.state, done_effects = step(self.state, UpstreamEOF(epoch=epoch))
            return done_effects

        effects: List[StreamEffect] = []
        try:
            parsed = json.loads(payload)
            delta = parsed.get("choices", [{}])[0].get("delta", {})
            reasoning = delta.get("reasoning_content")
            if reasoning:
                _, loop = self.guard.feed(reasoning)
                if loop:
                    self.state, err_eff = step(self.state, ProtocolError(message="Repetition detected", epoch=epoch))
                    return err_eff + [RecordMetric(name="repetition_guard_triggered", value=1.0)]
                effects.append(EmitChunk(text=reasoning, is_reasoning=True))

            for tc in delta.get("tool_calls", []):
                idx = tc.get("index", 0)
                cid = tc.get("id", f"call_{idx}")
                fn = tc.get("function", {})
                effects.append(EmitToolCall(index=idx, call_id=cid, name=fn.get("name", ""), arguments=fn.get("arguments", "{}")))

            content = delta.get("content")
            if content:
                _, loop = self.guard.feed(content)
                if loop:
                    self.state, err_eff = step(self.state, ProtocolError(message="Repetition detected", epoch=epoch))
                    return err_eff + [RecordMetric(name="repetition_guard_triggered", value=1.0)]
                effects.append(EmitChunk(text=content, is_reasoning=False))
        except Exception:
            effects.append(EmitSSE(event="message", data=payload))
        return effects

    def _process_sse_buffer(self, epoch: int) -> List[StreamEffect]:
        """Извлекает и обрабатывает завершенные SSE фреймы, разделенные \\n\\n."""
        effects: List[StreamEffect] = []
        while "\n\n" in self._buffer:
            frame, self._buffer = self._buffer.split("\n\n", 1)
            frame = frame.strip()
            if not frame:
                continue
            if frame.startswith("data:"):
                effects.extend(self._parse_sse_payload(frame[5:].strip(), epoch))
            else:
                effects.extend(self.assembler.feed(frame))
        return effects

    def _detect_mode(self) -> str:
        """Определяет режим входного потока (sse / pending / text)."""
        if any(self._buffer.startswith(p) for p in SSE_PREFIXES):
            return "sse"
        if len(self._buffer) <= 8 and any(p.startswith(self._buffer) for p in SSE_PREFIXES):
            return "pending"
        return "text"

    def feed(self, chunk: Union[str, bytes], epoch: int = 1) -> List[StreamEffect]:
        """Принимает чанк данных и возвращает список доменных эффектов."""
        if int(epoch) < self.session_epoch or self.state in (StreamState.CLOSED, StreamState.COMPLETED):
            self._stale_chunks_rejected += 1
            return []

        text = self._utf8_decoder.decode(chunk, final=False) if isinstance(chunk, bytes) else chunk
        if not text:
            return []

        self.state, base_effects = step(self.state, ChunkReceived(chunk=text, epoch=epoch))
        self._buffer += text

        if self._mode == "auto":
            mode = self._detect_mode()
            if mode == "pending":
                return base_effects
            self._mode = mode

        if self._mode == "sse":
            effects = self._process_sse_buffer(epoch)
        else:
            _, loop = self.guard.feed(text)
            if loop:
                self.state, err_eff = step(self.state, ProtocolError(message="Repetition detected", epoch=epoch))
                return base_effects + err_eff + [RecordMetric(name="repetition_guard_triggered", value=1.0)]
            effects = self.assembler.feed(self._buffer)
            self._buffer = ""

        return base_effects + effects

    def cancel(self, pgid: int = 0, epoch: int = 1, reason: str = "Client disconnected") -> List[StreamEffect]:
        """Идемпотентная отмена с инкрементом эпохи и эмиссией TriggerKillpg."""
        self.session_epoch += 1
        self.state, effects = step(self.state, CancelRequested(epoch=self.session_epoch, reason=reason, pgid=pgid))
        return effects

    def finish(self, epoch: int = 1) -> List[StreamEffect]:
        """Штатное завершение потока."""
        if int(epoch) < self.session_epoch:
            return []
        flushed = self._utf8_decoder.decode(b"", final=True)
        effects: List[StreamEffect] = []
        if flushed:
            self._buffer += flushed
        if self._buffer:
            effects.extend(self.assembler.feed(self._buffer))
            self._buffer = ""
        self.state, done_effects = step(self.state, UpstreamEOF(epoch=epoch))
        return effects + done_effects

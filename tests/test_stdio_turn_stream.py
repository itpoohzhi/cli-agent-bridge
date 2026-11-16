"""Tests for protocol-independent turn stream assembly."""

from __future__ import annotations

import re

from core.stdio_resident.protocol_driver import DecodedChunk
from core.stdio_resident.turn_stream import TurnStreamAssembler


def test_assembler_separates_consecutive_steps() -> None:
    assembler = TurnStreamAssembler()

    first = assembler.process_chunk(DecodedChunk(text="First step."))
    second = assembler.process_chunk(DecodedChunk(text="Second step."))
    combined = first.content + second.content

    assert combined == "First step.\n\nSecond step."
    assert re.findall(r"[a-zа-я]\.[A-ZА-Я]", combined) == []


def test_assembler_isolates_reasoning_when_tool_calls_present() -> None:
    assembler = TurnStreamAssembler()
    tool_calls = [{"id": "call-1", "function": {"name": "lookup"}}]

    delta = assembler.process_chunk(
        DecodedChunk(text="Preparing request", tool_calls=tool_calls)
    )

    assert delta.content == ""
    assert delta.reasoning_content == "Preparing request"
    assert delta.tool_calls == tool_calls


def test_assembler_routes_explicit_reasoning() -> None:
    assembler = TurnStreamAssembler()

    delta = assembler.process_chunk(DecodedChunk(reasoning="Checking inputs"))

    assert delta.reasoning_content == "Checking inputs"
    assert delta.content == ""


def test_assembler_routes_final_text_to_content() -> None:
    assembler = TurnStreamAssembler()

    delta = assembler.process_chunk(DecodedChunk(text="Final answer"))

    assert delta.content == "Final answer"
    assert delta.reasoning_content == ""


def test_assembler_invokes_on_activity_callback() -> None:
    activity_count = 0

    def on_activity() -> None:
        nonlocal activity_count
        activity_count += 1

    assembler = TurnStreamAssembler(on_activity=on_activity)

    _ = assembler.process_chunk(DecodedChunk(text="text"))
    _ = assembler.process_chunk(DecodedChunk(reasoning="reasoning"))
    _ = assembler.process_chunk(DecodedChunk(tool_calls=[{"id": "call-1"}]))
    _ = assembler.process_chunk(DecodedChunk(is_terminal=True))

    assert activity_count == 3

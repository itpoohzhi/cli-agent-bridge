"""Unit tests for ToolCallAssembler (ADR-0020)."""

import json
import pytest

from core.stream_fsm.tool_call_assembler import ToolCallAssembler
from core.stream_fsm.types import EmitChunk, EmitToolCall


def test_tool_call_json_assembly():
    """Тест сборки корректного JSON tool_call из нескольких кусков."""
    assembler = ToolCallAssembler()
    payload = json.dumps({"name": "fetch_user", "arguments": {"id": 42}})
    chunks = ["<tool_call>", payload[:15], payload[15:], "</tool_call>"]

    effects = []
    for c in chunks:
        effects.extend(assembler.feed(c))

    assert len(effects) == 1
    tc = effects[0]
    assert isinstance(tc, EmitToolCall)
    assert tc.name == "fetch_user"
    assert json.loads(tc.arguments) == {"id": 42}


def test_tool_call_xml_fallback():
    """Тест сборки XML function_call при нестандартном формате LLM."""
    assembler = ToolCallAssembler()
    raw = "<function_call><name>read_file</name><arguments>/tmp/test.txt</arguments></function_call>"

    effects = assembler.feed(raw)
    assert len(effects) == 1
    tc = effects[0]
    assert isinstance(tc, EmitToolCall)
    assert tc.name == "read_file"
    assert tc.arguments == "/tmp/test.txt"


def test_reasoning_extraction():
    """Тест извлечения блоков размышления <think>...</think>."""
    assembler = ToolCallAssembler()
    raw = "Начало <think>Анализирую требования</think> Финал"

    effects = assembler.feed(raw)
    assert len(effects) == 3
    assert effects[0] == EmitChunk(text="Начало ", is_reasoning=False)
    assert effects[1] == EmitChunk(text="Анализирую требования", is_reasoning=True)
    assert effects[2] == EmitChunk(text=" Финал", is_reasoning=False)


def test_split_tag_across_chunks():
    """Тест устойчивости к разрезанию открывающего тега между чанками."""
    assembler = ToolCallAssembler()
    effects1 = assembler.feed("Привет <tool_")
    assert effects1 == [EmitChunk(text="Привет ", is_reasoning=False)]
    assert assembler.in_tool_call is False

    payload = json.dumps({"name": "ping", "arguments": {}})
    effects2 = assembler.feed(f"call>{payload}</tool_call>")
    assert len(effects2) == 1
    assert isinstance(effects2[0], EmitToolCall)
    assert effects2[0].name == "ping"


def test_assembler_reset():
    """Тест сброса состояния и буферов ассемблера."""
    assembler = ToolCallAssembler()
    assembler.feed("<tool_call>incomplete")
    assert assembler.in_tool_call is True
    assembler.reset()
    assert assembler.in_tool_call is False
    assert assembler.feed("clean") == [EmitChunk(text="clean", is_reasoning=False)]

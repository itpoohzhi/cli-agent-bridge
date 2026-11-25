"""Тесты канонического рендеринга JSON-схем и вызовов инструментов."""

from __future__ import annotations

import ast
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import cast

_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import core.prompt_rendering as prompt_rendering  # noqa: E402
from core.prompt_rendering import (  # noqa: E402
    _render_assistant,
    _render_message,
    _render_tool_call,
    _render_tool_schema,
    _render_tools_section,
    render_tool_call,
    render_tools_section,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _shuffle_dict_keys(value: object, rng: random.Random) -> object:
    if isinstance(value, dict):
        items = list(cast(dict[str, object], value).items())
        rng.shuffle(items)
        return {key: _shuffle_dict_keys(item, rng) for key, item in items}
    if isinstance(value, list):
        return [_shuffle_dict_keys(item, rng) for item in cast(list[object], value)]
    return value


def _sample_tools() -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "zeta_tool",
                "description": "Инструмент Z",
                "parameters": {
                    "type": "object",
                    "required": ["path"],
                    "properties": {
                        "z_opt": {"type": "boolean", "default": False},
                        "a_nested": {
                            "type": "object",
                            "properties": {"y_field": {"type": "integer"}, "b_field": {"type": "string"}},
                        },
                        "path": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "alpha_tool",
                "description": "Инструмент A1",
                "parameters": {
                    "type": "object",
                    "properties": {"second": {"type": "string"}, "first": {"type": "integer"}},
                },
            },
        },
        {
            "name": "alpha_tool",
            "description": "Инструмент A0",
            "parameters": {"type": "object", "properties": {"aaa": {"type": "string"}}},
        },
    ]


def test_canonical_tools_section_1000_permutations_zero_drift() -> None:
    rng = random.Random(20261125)
    base_tools = _sample_tools()
    digests: set[str] = set()
    for _ in range(1000):
        shuffled_tools = [_shuffle_dict_keys(tool, rng) for tool in base_tools]
        rng.shuffle(shuffled_tools)
        rendered = render_tools_section(shuffled_tools, tool_choice="auto", has_attachments=True, sort_keys=True)
        assert rendered == _render_tools_section(
            shuffled_tools, tool_choice="auto", has_attachments=True, sort_keys=True
        )
        digests.add(_sha256(rendered))
    assert len(digests) == 1


def test_canonical_tool_call_and_message_1000_permutations_zero_drift() -> None:
    rng = random.Random(20261126)
    base_args: dict[str, object] = {
        "z_key": 1,
        "a_key": {"nested_z": True, "nested_a": [{"k2": "v2", "k1": "v1"}, {"b": 2, "a": 1}]},
        "m_key": "тест",
    }
    call_digests: set[str] = set()
    msg_digests: set[str] = set()
    for idx in range(1000):
        shuffled_args = cast(dict[str, object], _shuffle_dict_keys(base_args, rng))
        raw_args: object = json.dumps(shuffled_args, ensure_ascii=False) if idx % 2 == 0 else shuffled_args
        call_item: dict[str, object] = {
            "id": "call_42",
            "type": "function",
            "function": {"name": "search_files", "arguments": raw_args},
        }
        rendered_call = render_tool_call(call_item, sort_keys=True)
        assert rendered_call == _render_tool_call(call_item, sort_keys=True)
        call_digests.add(_sha256(rendered_call))

        message: dict[str, object] = {"role": "assistant", "content": "Проверяю файлы.", "tool_calls": [call_item]}
        is_prefix, rendered_msg = _render_message(message, [0], escape_roles=True, prune_marker="", sort_keys=True)
        assert is_prefix is False
        assert rendered_msg == _render_assistant(message, "Проверяю файлы.", sort_keys=True)
        msg_digests.add(_sha256(rendered_msg))

    assert len(call_digests) == 1
    assert len(msg_digests) == 1


def test_legacy_bypass_sort_keys_false_byte_identical() -> None:
    tools: list[object] = [
        {
            "type": "function",
            "function": {"name": "zeta", "description": "Последний", "parameters": {"z": 1, "a": {"y": 2, "b": 3}}},
        },
        {
            "type": "function",
            "function": {"name": "alpha", "description": "Первый", "parameters": {"second": "two", "first": "one"}},
        },
    ]
    default_rendered = _render_tools_section(tools)
    assert default_rendered == _render_tools_section(tools, sort_keys=False)
    assert default_rendered == render_tools_section(tools)
    assert default_rendered == render_tools_section(tools, sort_keys=False)
    expected_tail = "\n".join(
        (
            "Available tools:",
            "- zeta: Последний",
            '  parameters: {"z": 1, "a": {"y": 2, "b": 3}}',
            "- alpha: Первый",
            '  parameters: {"second": "two", "first": "one"}',
        )
    )
    assert default_rendered.endswith(expected_tail)
    assert _render_tool_schema(tools[0]) == _render_tool_schema(tools[0], sort_keys=False)

    call_item: dict[str, object] = {
        "id": "call_1",
        "function": {"name": "run", "arguments": {"z": 1, "a": {"d": 4, "c": 3}}},
    }
    expected_call = (
        '<tool_call>{"id": "call_1", "name": "run", '
        + '"arguments": {"z": 1, "a": {"d": 4, "c": 3}}}</tool_call>'
    )
    assert _render_tool_call(call_item) == expected_call
    assert render_tool_call(call_item) == expected_call
    assert render_tool_call(call_item, sort_keys=False) == expected_call

    message: dict[str, object] = {"role": "assistant", "content": "", "tool_calls": [call_item]}
    assert _render_message(message, [0], escape_roles=True, prune_marker="") == (False, f"[assistant]\n{expected_call}")


def test_sort_keys_true_handles_non_dict_tool_items() -> None:
    tools: list[object] = [
        "invalid",
        {"name": "b_tool", "parameters": {"b": 1, "a": 2}},
        {"name": "a_tool", "parameters": {"y": 1, "x": 2}},
    ]
    expected_tail = "\n".join(
        ("Available tools:", "- a_tool: ", '  parameters: {"x": 2, "y": 1}', "- b_tool: ", '  parameters: {"a": 2, "b": 1}')
    )
    assert render_tools_section(tools, sort_keys=True).endswith(expected_tail)


def test_prompt_rendering_is_pure_domain_no_os_or_environ() -> None:
    source_path = Path(prompt_rendering.__file__).resolve()
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] != "os"
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] != "os"
        elif isinstance(node, ast.Name):
            assert node.id not in {"os", "environ"}
        elif isinstance(node, ast.Attribute):
            assert node.attr != "environ"
    assert "os" not in vars(prompt_rendering)

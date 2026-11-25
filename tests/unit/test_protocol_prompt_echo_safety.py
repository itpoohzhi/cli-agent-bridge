"""L1: протокольный промпт безопасен при эхо-повторе моделью (malformed tool_call)."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import cast

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.prompt_rendering import (  # noqa: E402
    _TOOL_CALL_MARKER_RE,  # pyright: ignore[reportPrivateUsage]
    TOOL_CALL_FORMAT_LINE,
    render_tools_section,
)
from core.resumed_tools_policy import build_compact_tools_reminder  # noqa: E402
from core.tool_emulation import LiveParserError, StreamNormalizer  # noqa: E402
from core.tool_post_call_policy import PostCallPolicy  # noqa: E402

_OPEN = "<tool_" + "call>"
_CLOSE = "</tool_" + "call>"
_CHOICES: tuple[object, ...] = (
    None,
    "auto",
    "none",
    "required",
    {"type": "function", "function": {"name": "search"}},
)
_TOOLS: list[object] = [
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Search the index",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    },
    {"type": "function", "function": {"name": "lookup", "description": "Look up", "parameters": {}}},
]
_NAMES = ["search", "lookup"]
_FLAGS = ((False, False), (True, True))
_SEEDS = tuple(range(10))
_OLD_PLACEHOLDER = _OPEN + '{"name": "<tool_name>", "arguments": {<json>}}' + _CLOSE


def _call(query: str) -> str:
    body = json.dumps({"name": "search", "arguments": {"q": query}})
    return _OPEN + body + _CLOSE


def _renders(choice: object) -> dict[str, str]:
    """Оба рендера; полный рендер при tool_choice=none пуст по контракту и пропускается."""
    renders = {
        "full": render_tools_section(_TOOLS, choice),
        "compact": build_compact_tools_reminder(_NAMES, choice),
    }
    return {name: text for name, text in renders.items() if text}


def _chunks(text: str, mode: str) -> list[str]:
    if mode == "whole":
        return [text]
    if mode in ("1B", "7B"):
        step = int(mode[:-1])
        return [text[i : i + step] for i in range(0, len(text), step)]
    rng = random.Random(int(mode.removeprefix("seed")))
    out: list[str] = []
    pos = 0
    while pos < len(text):
        step = rng.randint(1, 40)
        out.append(text[pos : pos + step])
        pos += step
    return out


def _calls(norm: StreamNormalizer) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], norm.tool_calls)


def _run(text: str, mode: str, cutoff: bool, repair: bool) -> StreamNormalizer:
    normalizer = StreamNormalizer(strict_live=True)
    normalizer.configure_post_call_policy(PostCallPolicy(cutoff_enabled=cutoff, json_repair_enabled=repair))
    for chunk in _chunks(text, mode):
        normalizer.feed(chunk)
    normalizer.finish()
    return normalizer


_MODES = ("whole", "1B", "7B", *(f"seed{seed}" for seed in _SEEDS))


@pytest.mark.parametrize("choice", _CHOICES, ids=repr)
def test_rendered_protocol_has_no_tool_call_markers(choice: object) -> None:
    for name, text in _renders(choice).items():
        assert _TOOL_CALL_MARKER_RE.search(text) is None, name
        assert _OPEN not in text and _CLOSE not in text, name
        assert "<tool_name>" not in text and "<json>" not in text, name
        assert "tool_call" in text and '"name"' in text and '"arguments"' in text, name
        assert TOOL_CALL_FORMAT_LINE in text, name


def test_format_line_is_marker_free() -> None:
    assert _TOOL_CALL_MARKER_RE.search(TOOL_CALL_FORMAT_LINE) is None
    assert "<tool_name>" not in TOOL_CALL_FORMAT_LINE and "<json>" not in TOOL_CALL_FORMAT_LINE


@pytest.mark.parametrize("cutoff,repair", _FLAGS)
@pytest.mark.parametrize("mode", _MODES)
@pytest.mark.parametrize("choice", _CHOICES, ids=repr)
def test_echo_after_one_call_is_not_malformed(choice: object, mode: str, cutoff: bool, repair: bool) -> None:
    for protocol_text in _renders(choice).values():
        norm = _run(_call("alpha") + "\n" + protocol_text, mode, cutoff, repair)
        calls = _calls(norm)
        assert len(calls) == 1
        assert calls[0]["name"] == "search"


@pytest.mark.parametrize("cutoff,repair", _FLAGS)
@pytest.mark.parametrize("mode", _MODES)
@pytest.mark.parametrize("choice", _CHOICES, ids=repr)
def test_echo_between_two_calls_keeps_both(choice: object, mode: str, cutoff: bool, repair: bool) -> None:
    for protocol_text in _renders(choice).values():
        text = _call("same") + "\n" + protocol_text + "\n" + _call("same")
        norm = _run(text, mode, cutoff, repair)
        calls = _calls(norm)
        assert len(calls) == 2
        assert calls[0]["arguments"] == calls[1]["arguments"]


@pytest.mark.parametrize("mode", ("whole", "1B", "7B", "seed0"))
def test_oracle_negative_control_old_placeholder_still_fails(mode: str) -> None:
    with pytest.raises(LiveParserError, match="malformed tool_call block"):
        _ = _run(_call("alpha") + "\n" + _OLD_PLACEHOLDER, mode, False, False)

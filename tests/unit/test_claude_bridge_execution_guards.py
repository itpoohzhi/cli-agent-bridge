"""L1: запреты публикации вызовов и ранние выходы Claude-моста."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from core.tool_emulation import LiveParserError
from core.tool_mode import ToolMode, build_mode_spec
from tests.unit._claude_bridge_tool_fakes import (
    FakeRun,
    bridge as bridge,
)


def _execution(bridge: Any, mode: ToolMode = ToolMode.EMULATE) -> Any:
    callbacks = bridge._Callbacks(Mock(return_value=True), Mock(), Mock(return_value=True))
    return bridge._Execution(FakeRun([]), callbacks, build_mode_spec(mode), [])


def _handler(bridge: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    handler = object.__new__(bridge.Handler)
    handler.client_address = ("unit", 1)
    handler.headers = {}
    handler._acquire_slot = Mock(return_value="")
    handler._run_staged = Mock()
    monkeypatch.setattr(bridge, "_slots", Mock())
    monkeypatch.setattr(bridge, "_resolve_model", Mock(return_value=("m", None)))
    monkeypatch.setattr(bridge, "_effort", Mock(return_value="low"))
    monkeypatch.setattr(bridge, "_log", Mock())
    return handler


def test_prompt_for_passes_nonempty_images_to_renderer(
    bridge: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    images = [{"name": "image.png", "mime": "image/png", "data": b"image"}]
    render = Mock(return_value="staged image prompt")
    monkeypatch.setattr(bridge, "_messages_to_prompt", render)
    request = {"messages": [{"role": "user", "content": "describe"}]}
    assert bridge._prompt_for(request, [], images, build_mode_spec(ToolMode.EMULATE)) == (
        "staged image prompt"
    )
    render.assert_called_once_with(request["messages"], [], None, images)
    assert render.call_args.args[3] is images


@pytest.mark.parametrize("mode", (ToolMode.OFF, ToolMode.FORBID))
def test_add_call_rejects_non_emulation_mode(bridge: Any, mode: ToolMode) -> None:
    execution = _execution(bridge, mode)
    with pytest.raises(LiveParserError, match="without tool emulation"):
        execution.add_call({"name": "noop", "arguments": {}})
    execution.callbacks.on_tool_call.assert_not_called()
    assert execution.tool_calls == []


def test_add_call_after_client_departure_does_not_publish(bridge: Any) -> None:
    execution = _execution(bridge)
    execution.gone = True
    execution.add_call({"name": "noop", "arguments": {}})
    execution.callbacks.on_tool_call.assert_not_called()
    assert execution.tool_calls == []


def test_parallel_expansion_stops_after_first_rejected_callback(bridge: Any) -> None:
    execution = _execution(bridge)
    execution.callbacks.on_tool_call.return_value = False
    execution.add_call({
        "name": "parallel",
        "arguments": {"tool_uses": [
            {"recipient_name": "first", "parameters": {}},
            {"recipient_name": "second", "parameters": {}},
        ]},
    })
    assert execution.gone is True
    assert len(execution.tool_calls) == 1
    assert execution.tool_calls[0]["function"]["name"] == "first"
    execution.callbacks.on_tool_call.assert_called_once_with(execution.tool_calls[0])


def test_run_once_rejected_model_returns_failure_without_execution(
    bridge: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = _handler(bridge, monkeypatch)
    monkeypatch.setattr(
        bridge, "_resolve_model", Mock(return_value=(None, {"message": "bad model"})),
    )
    out = handler._run_once({"messages": []}, bridge._Callbacks(Mock(), Mock(), Mock()))
    assert (out["state"], out["rc"], out["err"]) == ("bad_model", 1, "bad model")
    assert (out["text"], out["tool_calls"], out["usage"]) == ("", [], {})
    handler._acquire_slot.assert_not_called()
    handler._run_staged.assert_not_called()
    bridge._slots.release.assert_not_called()


@pytest.mark.parametrize("reason", ("client_gone", "busy"))
def test_run_once_unacquired_slot_is_not_released_or_executed(
    bridge: Any, monkeypatch: pytest.MonkeyPatch, reason: str,
) -> None:
    handler = _handler(bridge, monkeypatch)
    handler._acquire_slot.return_value = reason
    callbacks = bridge._Callbacks(Mock(), Mock(), Mock(), Mock())
    out = handler._run_once({"messages": []}, callbacks)
    assert (out["state"], out["rc"], out["err"]) == (reason, 1, "")
    handler._acquire_slot.assert_called_once_with(callbacks.keepalive)
    handler._run_staged.assert_not_called()
    bridge._slots.release.assert_not_called()

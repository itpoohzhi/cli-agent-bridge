"""Tests for Wave 5 resident_runtime deadlines wiring (T-ISO-I3 agent-agnostic + singleton reset)."""

from __future__ import annotations

import socket
import subprocess

import pytest

from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.resident_runtime import ResidentBridgeRuntime
from core.stdio_resident.runtime_types import ResidentTurnOptions
from core.stdio_resident.turn_deadlines import DEFAULT_FIRST_PROGRESS_TIMEOUT_S, _TurnDeadlines


@pytest.fixture(autouse=True)
def _forbid_io_fixture(monkeypatch: pytest.MonkeyPatch):
    def _boom(*_a, **_kw):
        raise AssertionError("network/subprocess I/O is forbidden in T-ISO tests")
    monkeypatch.setattr(subprocess, "Popen", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)


def test_driver_chunks_attaches_turn_deadlines_for_codex_and_generic_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_ctx: list[dict[str, object]] = []

    def _fake_stream(_driver, _handle, _envelope, ctx, on_dispatched):
        captured_ctx.append(ctx)
        on_dispatched()
        return iter(())

    monkeypatch.setattr("core.stdio_resident.resident_runtime.stream_driver_turn", _fake_stream)

    for agent_name in ("codex", "generic-agent"):
        rt = ResidentBridgeRuntime.__new__(ResidentBridgeRuntime)
        rt._config = StdioPoolConfig()
        rt._driver = object()
        state = type(
            "_State",
            (),
            {
                "plan": type("_Plan", (), {"prompt_to_send": "hi"})(),
                "options": ResidentTurnOptions(argv_builder=lambda: ["echo"]),
                "slot": type("_Slot", (), {"handle": object()})(),
                "envelope": type("_Env", (), {"agent": agent_name})(),
                "dispatched": False,
            },
        )()
        list(rt._driver_chunks(state))
        assert state.dispatched is True

    assert len(captured_ctx) == 2
    for ctx in captured_ctx:
        dl = ctx["deadlines"]
        assert isinstance(dl, _TurnDeadlines)
        assert dl.first_progress_deadline - dl.safety_deadline <= 0.0
        assert dl.idle_s == pytest.approx(StdioPoolConfig.idle_timeout_s)
        assert dl.first_progress_deadline > DEFAULT_FIRST_PROGRESS_TIMEOUT_S - 10.0

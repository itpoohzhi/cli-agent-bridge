"""HTTP/SSE contract tests for unified bridge drain responses (VER-002, VER-004, VER-005).

Covers the target contract across `core.drain_response`, `core.lifecycle`,
`core.subbridge_lifecycle`, and hub ingress:
- unified `Retry-After` bounds (`1 <= s <= 60`) across hub JSON, subbridge, and builder;
- SSE terminal drain error framing with `overloaded_error`, code 503, and `retry_after >= 1`;
- `wait_for_drain_hold()` never admitting requests in `STOPPED` (`accepting()` == `READY`);
- single-line key=value drain diagnostics with secret/newline hygiene;
- kill-switch (`BRIDGE_DRAIN_POLICY_ENABLED=0`) preserving `Retry-After >= 1` floor.
"""

from __future__ import annotations

import importlib
import json
import re
import signal
import threading
import time
from typing import Any

import pytest

from core.lifecycle import DrainState, HubLifecycleManager
from core.subbridge_config import SubbridgeDrainConfig
from core.subbridge_lifecycle import SubbridgeLifecycle

RETRY_FLOOR = 1
RETRY_CAP = 60


def _drain_response_mod() -> Any:
    return importlib.import_module("core.drain_response")


def _subbridge_rejection(env: dict[str, str]) -> tuple[int, dict[str, str], dict[str, Any]]:
    cfg = SubbridgeDrainConfig.from_env(env)
    life = SubbridgeLifecycle(cfg)
    life.handle_signal(signal.SIGTERM)
    rejection = life.admission_rejection("/v1/chat/completions")
    assert rejection is not None
    return rejection


def _assert_drain_http_contract(
    resp: tuple[int, dict[str, str], dict[str, Any]],
    *,
    expected_retry: int,
) -> None:
    status, headers, body = resp
    assert status == 503
    assert headers.get("X-Bridge-Draining") == "true"
    assert "Retry-After" in headers
    retry_val = int(headers["Retry-After"])
    assert RETRY_FLOOR <= retry_val <= RETRY_CAP
    assert retry_val == expected_retry
    assert body["error"]["code"] == 503


def test_unified_retry_after_explicit_value_across_hub_subbridge_and_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit BRIDGE_RETRY_AFTER_S=7 produces identical Retry-After=7 across all layers."""
    env = {"BRIDGE_RETRY_AFTER_S": "7"}
    monkeypatch.setenv("BRIDGE_RETRY_AFTER_S", "7")
    builder_resp = _drain_response_mod().build_drain_http_response(env)
    hub_resp = HubLifecycleManager().draining_response(is_subagent=False)
    subbridge_resp = _subbridge_rejection(env)

    for resp in (builder_resp, hub_resp, subbridge_resp):
        _assert_drain_http_contract(resp, expected_retry=7)
    assert (
        builder_resp[1]["Retry-After"]
        == hub_resp[1]["Retry-After"]
        == subbridge_resp[1]["Retry-After"]
        == "7"
    )


@pytest.mark.parametrize("raw_value", ["0", "-5", "not-a-number", ""])
def test_unified_retry_after_zero_and_garbage_fall_back_to_safe_defaults(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
) -> None:
    """Zero/negative/garbage BRIDGE_RETRY_AFTER_S never emits 0 or omits Retry-After."""
    env = {"BRIDGE_RETRY_AFTER_S": raw_value}
    monkeypatch.setenv("BRIDGE_RETRY_AFTER_S", raw_value)
    mod = _drain_response_mod()
    lifecycle = HubLifecycleManager()

    _assert_drain_http_contract(mod.build_drain_http_response(env), expected_retry=5)
    _assert_drain_http_contract(lifecycle.draining_response(is_subagent=False), expected_retry=5)
    _assert_drain_http_contract(_subbridge_rejection(env), expected_retry=5)

    _assert_drain_http_contract(
        mod.build_drain_http_response(env, is_subagent=True), expected_retry=3
    )
    _assert_drain_http_contract(lifecycle.draining_response(is_subagent=True), expected_retry=3)


def test_unified_retry_after_is_clamped_to_upper_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Excessive BRIDGE_RETRY_AFTER_S values are clamped to <= 60 across all layers."""
    env = {"BRIDGE_RETRY_AFTER_S": "999"}
    monkeypatch.setenv("BRIDGE_RETRY_AFTER_S", "999")
    builder_resp = _drain_response_mod().build_drain_http_response(env)
    hub_resp = HubLifecycleManager().draining_response(is_subagent=False)
    subbridge_resp = _subbridge_rejection(env)

    for resp in (builder_resp, hub_resp, subbridge_resp):
        _assert_drain_http_contract(resp, expected_retry=RETRY_CAP)


@pytest.mark.parametrize(
    ("env", "expected_retry"),
    [
        ({"BRIDGE_RETRY_AFTER_S": "7"}, 7),
        ({"BRIDGE_RETRY_AFTER_S": "0"}, 5),
        ({"BRIDGE_RETRY_AFTER_S": "garbage"}, 5),
        ({"BRIDGE_RETRY_AFTER_S": "120"}, 60),
    ],
)
def test_build_drain_sse_error_emits_valid_sse_frame_and_error_payload(
    env: dict[str, str],
    expected_retry: int,
) -> None:
    """build_drain_sse_error formats valid SSE data + [DONE] with overloaded_error 503."""
    msg = "bridge is draining for restart"
    frame = _drain_response_mod().build_drain_sse_error(env, model="m", message=msg)

    assert isinstance(frame, str)
    assert frame.startswith("data: ")
    assert frame.endswith("\n\ndata: [DONE]\n\n")

    blocks = [block for block in frame.split("\n\n") if block]
    assert len(blocks) == 2
    assert blocks[1] == "data: [DONE]"
    payload = json.loads(blocks[0].removeprefix("data: "))
    err = payload["error"]
    assert err["type"] == "overloaded_error"
    assert err["code"] == 503
    assert isinstance(err["retry_after"], int)
    assert RETRY_FLOOR <= err["retry_after"] <= RETRY_CAP
    assert err["retry_after"] == expected_retry
    assert err["message"] == msg


def test_wait_for_drain_hold_zero_timeout_never_admits_in_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With BRIDGE_DRAIN_HOLD_TIMEOUT_S=0.0, wait_for_drain_hold reflects accepting() == READY."""
    monkeypatch.setenv("BRIDGE_DRAIN_HOLD_TIMEOUT_S", "0.0")
    lifecycle = HubLifecycleManager(drain_timeout_s=0.1)
    assert lifecycle.accepting() is True
    assert lifecycle.wait_for_drain_hold(is_subagent=False) is True

    lifecycle.handle_signal(signal.SIGTERM)
    assert lifecycle.accepting() is False
    assert lifecycle.wait_for_drain_hold(is_subagent=False) is False

    lifecycle.run_drain_once()
    assert lifecycle.state == DrainState.STOPPED
    assert lifecycle.accepting() is False
    assert lifecycle.wait_for_drain_hold(is_subagent=False) is False


def test_wait_for_drain_hold_positive_timeout_never_returns_true_in_stopped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even when drain completes into STOPPED during hold wait, wait_for_drain_hold returns False."""
    monkeypatch.setenv("BRIDGE_DRAIN_HOLD_TIMEOUT_S", "0.05")
    lifecycle = HubLifecycleManager(drain_timeout_s=0.02)
    lifecycle.handle_signal(signal.SIGTERM)

    def _finish_drain() -> None:
        time.sleep(0.01)
        lifecycle.run_drain_once()

    worker = threading.Thread(target=_finish_drain, daemon=True)
    worker.start()
    admitted = lifecycle.wait_for_drain_hold(is_subagent=False)
    worker.join(timeout=2.0)

    assert lifecycle.state == DrainState.STOPPED
    assert lifecycle.accepting() is False
    assert admitted is False

    # Even if shutdown_requested were cleared while state is STOPPED, accepting() stays False.
    lifecycle.shutdown_requested.clear()
    assert lifecycle.accepting() is False
    assert lifecycle.wait_for_drain_hold(is_subagent=False) is False


def test_drain_diagnostics_no_secrets() -> None:
    """format_drain_event emits single-line key=value diagnostics without newlines or secrets."""
    mod = _drain_response_mod()
    line = mod.format_drain_event(
        "drain_started",
        signal_num=15,
        active_turns=3,
        retry_after_s=5,
        drain_elapsed_s=1.2,
        source="ingress",
    )

    assert isinstance(line, str) and line.strip() == line
    assert "\n" not in line and "\r" not in line
    assert "drain_started" in line
    for token in (
        "signal_num=15",
        "active_turns=3",
        "retry_after_s=5",
        "source=ingress",
    ):
        assert token in line.split()
    assert re.search(r"\bdrain_elapsed_s=1\.20*\b", line) is not None
    kv_tokens = [tok for tok in line.split() if tok != "drain_started"]
    assert kv_tokens and all("=" in tok for tok in kv_tokens)

    secret = "sk-live-secret-token-9876543210"
    sanitized = mod.format_drain_event(
        "drain_started",
        signal_num=15,
        active_turns=3,
        retry_after_s=5,
        drain_elapsed_s=1.2,
        source=f"Bearer {secret}\nforged=1",
    )
    assert "\n" not in sanitized and "\r" not in sanitized
    assert secret not in sanitized


@pytest.mark.parametrize("retry_raw", [None, "0", "invalid"])
def test_drain_kill_switch_preserves_floor(
    monkeypatch: pytest.MonkeyPatch,
    retry_raw: str | None,
) -> None:
    """BRIDGE_DRAIN_POLICY_ENABLED=0 still enforces Retry-After >= 1 and X-Bridge-Draining: true."""
    env: dict[str, str] = {"BRIDGE_DRAIN_POLICY_ENABLED": "0"}
    monkeypatch.setenv("BRIDGE_DRAIN_POLICY_ENABLED", "0")
    if retry_raw is None:
        monkeypatch.delenv("BRIDGE_RETRY_AFTER_S", raising=False)
    else:
        env["BRIDGE_RETRY_AFTER_S"] = retry_raw
        monkeypatch.setenv("BRIDGE_RETRY_AFTER_S", retry_raw)

    builder_resp = _drain_response_mod().build_drain_http_response(env)
    hub_resp = HubLifecycleManager().draining_response(is_subagent=False)

    for status, headers, body in (builder_resp, hub_resp):
        assert status == 503
        assert headers.get("X-Bridge-Draining") == "true"
        assert "Retry-After" in headers
        assert RETRY_FLOOR <= int(headers["Retry-After"]) <= RETRY_CAP
        assert body["error"]["code"] == 503

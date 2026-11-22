"""Тесты стабилизации agy-bridge: очередь <=4, client_gone/SIGINT, effort/carbon, X-Subagent-Id, anti-/plan."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import yaml

from core.effort_policy import EFFORT_LEVELS
from core.effortless_policy import resolve_request_effort
from core.http_post_routing import prepare_route_request
from core.passthrough_facade import _pin_effort
from core.prompt_rendering import _render_tools_section
from core.slot_acquire import acquire_slot_cancellable, queue_poll_s

ROOT = Path(__file__).resolve().parents[1]
_AGY_PY = ROOT / "bridges" / "agy-bridge" / "server.py"
_AGY_MOD: Any = None


def _load_agy() -> Any:
    global _AGY_MOD
    if _AGY_MOD is not None:
        return _AGY_MOD
    prev_key = os.environ.get("AGY_BRIDGE_KEY")
    if prev_key is None:
        os.environ["AGY_BRIDGE_KEY"] = "test-key-agy-stabilization"
    try:
        spec = importlib.util.spec_from_file_location("agy_bridge_stabilization_sut", _AGY_PY)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        _AGY_MOD = mod
        return mod
    finally:
        if prev_key is None:
            os.environ.pop("AGY_BRIDGE_KEY", None)


def test_agy_concurrency_limits_aligned_to_four() -> None:
    manifest = yaml.safe_load((ROOT / "providers.d/agy.yaml").read_text(encoding="utf-8"))
    assert manifest["limits"]["max_concurrent"] == 128, "RED-AGY128: max_concurrent must be 128"
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    assert fleet["backends"]["agy"]["max_concurrent"] == 128, "RED-AGY128: fleet max_concurrent must be 128"


def test_acquire_slot_cancellable_ok_timeout_and_client_gone() -> None:
    sem = threading.BoundedSemaphore(1)
    assert acquire_slot_cancellable(sem, 1.0, lambda: False, poll_s=0.01) == "ok"
    assert acquire_slot_cancellable(sem, 0.04, lambda: False, poll_s=0.01) == "timeout"
    gone = False
    def _trip() -> None:
        nonlocal gone
        time.sleep(0.03)
        gone = True
    t = threading.Thread(target=_trip, daemon=True)
    t.start()
    t0 = time.monotonic()
    res = acquire_slot_cancellable(sem, 2.0, lambda: gone, poll_s=0.01)
    t.join(timeout=1.0)
    sem.release()
    assert res == "client_gone"
    assert time.monotonic() - t0 < 0.5
    assert queue_poll_s({"BRIDGE_PASSTHROUGH_QUEUE_POLL_S": "0.25"}) == 0.25
    assert queue_poll_s({"BRIDGE_PASSTHROUGH_QUEUE_POLL_S": "bad"}) == 0.1


def test_agy_fair_queue_bounds_concurrency_to_four() -> None:
    agy = _load_agy()
    slots = agy._FairSlotSemaphore(4)
    in_flight, peak, lock = [0], [0], threading.Lock()
    def _worker(_idx: int) -> str:
        assert slots.acquire(timeout=2.0)
        try:
            with lock:
                in_flight[0] += 1
                peak[0] = max(peak[0], in_flight[0])
            time.sleep(0.03)
            return "ok"
        finally:
            with lock:
                in_flight[0] -= 1
            slots.release()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_worker, range(8)))
    assert results == ["ok"] * 8
    assert peak[0] <= 4
    assert slots.active_count == 0 and slots.waiters_count == 0


def test_agy_acquire_slot_aborts_when_client_gone_in_queue() -> None:
    agy = _load_agy()
    slots = agy._FairSlotSemaphore(1)
    assert slots.acquire(blocking=False)
    handler = agy.Handler.__new__(agy.Handler)
    handler._registry_job = None
    handler._t_req_start = None
    handler.connection = object()
    gone_calls = [0]
    def _fake_gone(_conn: Any) -> bool:
        gone_calls[0] += 1
        return gone_calls[0] >= 2
    try:
        with (
            mock.patch.object(agy, "_slots", slots),
            mock.patch.object(agy, "_client_gone", _fake_gone),
            mock.patch.dict(os.environ, {"AGY_BRIDGE_QUEUE_POLL_S": "0.05"}),
        ):
            status = handler._acquire_slot(keepalive=None)
        assert status == "client_gone"
        assert slots.waiters_count == 0
    finally:
        slots.release()


def test_process_supervisor_eperm_and_sigint_before_sigterm() -> None:
    agy = _load_agy()
    sup = agy.ProcessSupervisor(
        agy.ProcessSupervisorConfig(kill_int_grace_s=0.3, kill_term_grace_s=0.3, kill_wait_s=1.0)
    )
    with mock.patch("os.killpg", side_effect=PermissionError("zombie leader")):
        assert sup.group_alive(999999) is False
    code = (
        "import signal, sys, time; "
        "signal.signal(signal.SIGINT, lambda *_: sys.exit(42)); "
        "print('READY', flush=True); time.sleep(30)"
    )
    proc = sup.spawn([sys.executable, "-c", code], stdout=subprocess.PIPE)
    assert proc.stdout is not None and proc.stdout.readline().strip() == b"READY"
    sup.kill_group(proc, send_sigint=True)
    assert proc.returncode == 42


def test_job_registry_detach_cancels_toolless_immediately() -> None:
    agy = _load_agy()
    reg = agy.JobRegistry(orphan_max=5)
    job, owner = reg.attach("toolless-1", "gemini-4-neon", "hello")
    assert owner is True
    killed = threading.Event()
    reg.bind_cancel(job, killed.set)
    reg.detach(job, allow_orphan=False)
    assert job.cancelled.is_set()
    assert killed.is_set()
    assert reg.orphans == 0
    assert agy.slot_and_session.allow_job_orphan(0, {}) is False
    assert agy.slot_and_session.allow_job_orphan(2, {}) is True
    assert agy.slot_and_session.allow_job_orphan(0, {"AGY_BRIDGE_ORPHAN_TOOLLESS_ENABLED": "1"}) is True


def test_effort_contract_carbon_neon_hydrogen_and_no_default_override() -> None:
    agy_fleet = json.loads((ROOT / "bridges/agy-bridge/fleet.json").read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in agy_fleet["models"]}
    assert "1.5.13" in agy_fleet["technical_ref"]["models_source"]
    assert by_id["gemini-4-carbon"]["default_effort"] == "high"
    assert set(by_id["gemini-4-carbon"]["efforts"]) == {"low", "medium", "high", "off"}
    assert by_id["gemini-4-neon"]["efforts"] == ["low", "medium", "high", "xhigh"]
    assert by_id["gemini-4-hydrogen"]["efforts"] == ["low", "medium", "high", "xhigh"]
    for model_id, req_eff, expected in (
        ("gemini-4-neon", "low", "low"),
        ("gemini-4-neon", "medium", "medium"),
        ("gemini-4-hydrogen", "medium", "medium"),
        ("gemini-4-carbon", "high", "high"),
        ("gemini-4-carbon", "off", "off"),
    ):
        dec = resolve_request_effort(req_eff, by_id[model_id], EFFORT_LEVELS)
        assert dec.error is None and dec.effort == expected
    root_fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    root_models = {m["id"]: m for m in root_fleet["models"]}
    for model_id, alias_eff, explicit_eff, expected in (
        ("gemini-4-neon", None, "medium", "medium"),
        ("gemini-4-neon", "low", None, "low"),
        ("gemini-4-hydrogen", "medium", None, "medium"),
        ("gemini-4-carbon", "high", None, "high"),
    ):
        req: dict[str, Any] = {"model": model_id, "messages": [{"role": "user", "content": "hi"}]}
        if explicit_eff is not None:
            req["reasoning_effort"] = explicit_eff
        route = SimpleNamespace(request=req, alias_effort=alias_eff, model=root_models[model_id])
        pinned = _pin_effort(route)
        prepared = prepare_route_request(pinned.request, root_models[model_id], model_id, alias_effort=alias_eff)
        assert prepared["reasoning_effort"] == expected


def test_subagent_id_isolates_sessions_and_fails_closed_on_invalid() -> None:
    agy = _load_agy()
    chat_a, bad_a = agy._request_chat_id({"X-Subagent-Id": "coder-1", "X-Session-Id": "chat-1"}, {"cwd": "/tmp"}, {"tools": [1]})
    chat_b, bad_b = agy._request_chat_id({"X-Subagent-Id": "coder-2", "X-Session-Id": "chat-1"}, {"cwd": "/tmp"}, {"tools": [1]})
    assert not bad_a and not bad_b and "\x00" not in chat_a
    key_a = agy._session_key_for("gemini-4-neon", "/tmp", "high", chat_a)
    key_b = agy._session_key_for("gemini-4-neon", "/tmp", "high", chat_b)
    assert key_a != key_b and agy._session_key_valid(key_a)
    chat_bad, bad_flag = agy._request_chat_id({"X-Subagent-Id": "bad\x00sub"}, {}, {"tools": [1]})
    assert bad_flag is True and chat_bad == ""


def test_tools_protocol_prevents_plan_mode_drift() -> None:
    agy = _load_agy()
    tools = [{"type": "function", "function": {"name": "read_file", "description": "read", "parameters": {}}}]
    core_section = _render_tools_section(tools)
    assert "implementation_plan.md" not in core_section
    agy_prompt = agy._with_tools_protocol("do work", tools, None)
    assert "implementation_plan.md" in agy_prompt
    assert "Never attempt to use built-in tools" in agy_prompt
    assert agy_emulate_mode_check()


def agy_emulate_mode_check() -> bool:
    agy = _load_agy()
    fn = agy.slot_and_session.resolve_cli_mode
    return (
        fn("ask", emulate_tools=True, environ={}) == "plan"
        and fn("emulate", environ={}) == "plan"
        and fn("emulate", environ={"AGY_BRIDGE_EMULATE_CLI_MODE": "  "}) == "plan"
        and fn("ask", emulate_tools=True, environ={"AGY_BRIDGE_EMULATE_CLI_MODE": "auto"}) == "auto"
        and fn("ask", emulate_tools=False, environ={"AGY_BRIDGE_ASK_CLI_MODE": "plan"}) == "plan"
        and fn("agent", emulate_tools=False, environ={}) == "auto"
        and fn("custom", emulate_tools=False, environ={}) == "custom"
    )


def test_slot_helpers_bounds_combine_health_and_dynamic_config_log() -> None:
    agy = _load_agy()
    ss = agy.slot_and_session
    assert queue_poll_s({}) == 0.1
    assert queue_poll_s({"BRIDGE_PASSTHROUGH_QUEUE_POLL_S": "nan"}) == 0.1
    assert queue_poll_s({"BRIDGE_PASSTHROUGH_QUEUE_POLL_S": "0.001"}) == 0.01
    assert queue_poll_s({"BRIDGE_PASSTHROUGH_QUEUE_POLL_S": "99"}) == 5.0
    assert ss.queue_poll_interval_s({}) == 0.5
    assert ss.queue_poll_interval_s({"AGY_BRIDGE_QUEUE_POLL_S": "bad"}) == 0.5
    assert ss.queue_poll_interval_s({"AGY_BRIDGE_QUEUE_POLL_S": "inf"}) == 0.5
    assert ss.queue_poll_interval_s({"AGY_BRIDGE_QUEUE_POLL_S": "0.001"}) == 0.05
    assert ss.kill_int_grace_s({}) == 0.25
    assert ss.kill_int_grace_s({"AGY_BRIDGE_KILL_INT_GRACE_S": "99"}) == 30.0
    assert ss.combine_chat_and_subagent("c1", "") == "c1"
    assert ss.combine_chat_and_subagent("c1", "s1") == "c1|sub:s1"
    assert ss.combine_chat_and_subagent("", "s1") == "subagent:s1"
    long_key = ss.combine_chat_and_subagent("c" * 300, "s" * 300)
    assert long_key.startswith("sub:") and len(long_key) <= 512 and "\x00" not in long_key
    assert ss.continuity_scope("m1", "") == "m1\x00"
    assert ss.continuity_scope("m1", "sub1") == "m1\x00sub1\x00"
    assert ss.append_anti_plan_directive("") == ""
    assert "implementation_plan.md" in ss.append_anti_plan_directive("sec")
    assert ss.health_queue_fields(SimpleNamespace(waiters_count=2, active_count=3)) == {
        "queued": 2,
        "slots_active": 3,
    }
    sem = threading.BoundedSemaphore(1)
    assert acquire_slot_cancellable(sem, 1.0, lambda: True, poll_s=0.01) == "client_gone"
    assert acquire_slot_cancellable(sem, 0.0, lambda: False, poll_s=0.01) == "ok"
    sem.release()


def test_dynamic_config_parse_error_logs(tmp_path: Path) -> None:
    agy = _load_agy()
    bad_cfg = tmp_path / "dynamic_config.json"
    bad_cfg.write_text("{broken", encoding="utf-8")
    logs: list[str] = []
    with (
        mock.patch.object(agy, "DYNAMIC_CONFIG_PATH", bad_cfg),
        mock.patch.object(agy, "_cfg_key", None),
        mock.patch.object(agy, "_cfg_checked_at", None),
        mock.patch.object(agy, "_log", logs.append),
    ):
        agy._runtime_snapshot()
    assert any("dynamic_config parse error:" in line for line in logs)

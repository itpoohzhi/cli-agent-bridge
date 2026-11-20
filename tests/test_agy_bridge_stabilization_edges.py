"""Граничные тесты стабилизации agy-bridge и passthrough runtime (T-ISO-I1 critical sites)."""

from __future__ import annotations

import signal
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest

from core.passthrough_adapter_runtime import RuntimeOptions, handle_request
from core.slot_acquire import acquire_slot_cancellable, queue_poll_s
from tests.test_agy_bridge_stabilization import _load_agy


def test_env_defaults_and_loop_acquire_with_default_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agy = _load_agy()
    ss = agy.slot_and_session
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_QUEUE_POLL_S", "0.02")
    monkeypatch.setenv("AGY_BRIDGE_ORPHAN_TOOLLESS_ENABLED", "1")
    monkeypatch.setenv("AGY_BRIDGE_EMULATE_CLI_MODE", "custom-emul")
    assert queue_poll_s() == 0.02
    assert ss.allow_job_orphan(1, {}) is True
    assert ss.allow_job_orphan(0) is True
    assert ss.resolve_cli_mode("emulate") == "custom-emul"
    sem = threading.BoundedSemaphore(1)
    assert sem.acquire(blocking=False)
    def _rel() -> None:
        time.sleep(0.02)
        sem.release()
    t = threading.Thread(target=_rel, daemon=True)
    t.start()
    assert acquire_slot_cancellable(sem, 1.0, lambda: False) == "ok"
    t.join(timeout=1.0)
    sem.release()


def test_passthrough_handle_request_queue_client_gone_and_timeout() -> None:
    fails: list[tuple[int, str]] = []
    sem = threading.BoundedSemaphore(1)
    assert sem.acquire(blocking=False)
    try:
        adapter = SimpleNamespace(
            config={},
            _slots=sem,
            _lock=threading.Lock(),
            _active=0,
            host=SimpleNamespace(QUEUE_TIMEOUT_S=0.05),
            _fail=lambda _s, code, err, _m, **_kw: fails.append((code, err)),
        )
        ex_gone = SimpleNamespace(
            request={"model": "gemini-4-neon", "stream": True},
            headers={},
            sink=SimpleNamespace(client_gone=lambda: True),
        )
        ex_to = SimpleNamespace(
            request={"model": "gemini-4-neon", "stream": True},
            headers={},
            sink=SimpleNamespace(client_gone=lambda: False),
        )
        fake_rt = lambda *_a, **_kw: SimpleNamespace(open_deadline=time.monotonic() + 1.0)  # noqa: E731
        with mock.patch("core.passthrough_adapter_runtime._RequestRuntime", side_effect=fake_rt):
            handle_request(adapter, ex_gone, RuntimeOptions(queue_timeout_s=0.05))
            assert fails == []
            handle_request(adapter, ex_to, RuntimeOptions(queue_timeout_s=0.02))
        assert fails == [(503, "overloaded")]
    finally:
        sem.release()


def test_agy_server_runtime_build_continuity_detach_and_registered_attempt() -> None:
    agy = _load_agy()
    with mock.patch.object(agy, "_file_sha256", return_value=""):
        fields = agy._runtime_build_fields()
    assert fields["agy_binary_sha256"] == agy.BUILD_UNKNOWN
    assert "queued" in fields and "slots_active" in fields
    req = {"model": "gemini-4-neon", "tools": [1], "messages": [{"role": "user", "content": "hi"}]}
    with (
        mock.patch.object(agy, "_new_flag", return_value=True),
        mock.patch.object(agy._CONTINUITY, "resolve", return_value="cont-1") as res_mock,
    ):
        cid, bad = agy._request_chat_id({"X-Subagent-Id": "coder-1"}, {}, req)
    assert cid == "cont-1" and bad is False
    assert res_mock.call_args[0][1] == "gemini-4-neon\x00coder-1\x00"
    reg = agy.JobRegistry(orphan_max=2)
    job, _ = reg.attach("k-orp", "gemini-4-neon", "p")
    reg.detach(job, allow_orphan=True)
    assert job.orphan is True and reg.orphans == 1
    seen: list[bool] = []
    handler = agy.Handler.__new__(agy.Handler)
    handler._start_job_producer = lambda _c, _j: None
    handler._read_job_events = lambda _j, _cb, *, allow_orphan=True: (seen.append(allow_orphan) or {"state": "done"})
    with mock.patch.object(agy, "_JOB_REGISTRY", agy.JobRegistry(orphan_max=2)):
        handler._run_registered_attempt({"step_job_id": "j0", "model": "m", "full_prompt": "p", "tools_count": 0}, {})
        handler._run_registered_attempt({"step_job_id": "j1", "model": "m", "full_prompt": "p", "tools_count": 1}, {})
    assert seen == [False, True]


def test_sigint_early_return_skips_sigterm() -> None:
    agy = _load_agy()
    sup = agy.ProcessSupervisor(
        agy.ProcessSupervisorConfig(kill_int_grace_s=0.5, kill_term_grace_s=0.3, kill_wait_s=1.0)
    )
    sigs: list[int] = []
    orig = sup._signal_group
    def _spy(pid: int, sig: int) -> None:
        sigs.append(sig)
        orig(pid, sig)
    sup._signal_group = _spy  # type: ignore[method-assign]
    code = "import signal, sys, time; signal.signal(signal.SIGINT, lambda *_: sys.exit(0)); print('R', flush=True); time.sleep(30)"
    proc = sup.spawn([sys.executable, "-c", code], stdout=subprocess.PIPE)
    assert proc.stdout is not None and proc.stdout.readline().strip() == b"R"
    sup.kill_group(proc, send_sigint=True)
    assert sigs == [signal.SIGINT]


def test_run_close_passes_send_sigint_and_acquire_respects_registry_cancel() -> None:
    agy = _load_agy()
    run = agy.Run.__new__(agy.Run)
    run._stop_watch = threading.Event()
    run._proc_done = threading.Event()
    run._tail = SimpleNamespace(
        interrupt_active_query=lambda: None,
        thread=SimpleNamespace(is_alive=lambda: False),
    )
    run.controller = SimpleNamespace(close=lambda: None)
    run.proc = SimpleNamespace(pid=-999999, returncode=0, stdin=None, stdout=None, stderr=None)
    with mock.patch.object(agy, "_kill_group") as kill_mock:
        run.close()
    assert kill_mock.call_args.kwargs.get("send_sigint") is True
    slots = agy._FairSlotSemaphore(1)
    assert slots.acquire(blocking=False)
    handler = agy.Handler.__new__(agy.Handler)
    cancelled = threading.Event()
    cancelled.set()
    handler._registry_job = SimpleNamespace(cancelled=cancelled)
    handler._t_req_start = None
    handler.connection = object()
    try:
        with mock.patch.object(agy, "_slots", slots):
            assert handler._acquire_slot(keepalive=None) == "client_gone"
        assert slots.waiters_count == 0
    finally:
        slots.release()


def test_run_emulate_mode_preserves_disable_slash_commands() -> None:
    agy = _load_agy()
    captured: list[list[str]] = []

    def _fake_spawn(cmd: list[str], **_kwargs: object) -> None:
        captured.append(list(cmd))
        raise RuntimeError("stop-after-cmd")

    with mock.patch.object(agy, "spawn_registered", side_effect=_fake_spawn):
        for mode in ("emulate", "ask", "agent"):
            try:
                agy.Run("p", "gemini-4-neon", "high", "/bin/echo", "", "t", mode=mode)
            except RuntimeError:
                pass
    assert "--disable-slash-commands" in captured[0] and "--mode" in captured[0]
    assert captured[0][captured[0].index("--mode") + 1] == "plan"
    assert "--disable-slash-commands" in captured[1]
    assert "--disable-slash-commands" not in captured[2]


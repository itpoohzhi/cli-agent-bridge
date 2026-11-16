"""Реплеи EV-06/EV-07 через настоящий done/SSE; тело финала синтетическое."""
# pyright: reportPrivateUsage=false
from __future__ import annotations
import importlib.util
import json
import os
import queue
import stat
import sys
import threading
import time
from collections.abc import Callable
from contextlib import nullcontext
from operator import attrgetter
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, TypedDict, cast
import pytest
_ROOT = Path(__file__).resolve().parents[1]
_ERROR = "Your previous response contained an improperly formatted function call: Malformed function call: Failed to parse function call; Function call is empty - no input to parse. Please retry with a properly formatted function call Retries remaining: 3"
_FINAL = "Синтетический финальный ответ после внутреннего ретрая.\n✓ SEAL sha256:synthetic"
_TextCallback = Callable[[str], bool]
_TraceCallback = Callable[[dict[str, object]], bool]
_Case = tuple[dict[str, str] | None, dict[str, str], tuple[str, str], str | None, tuple[str, ...]]
_Delta = TypedDict("_Delta", {"content": str}, total=False)
_Choice = TypedDict("_Choice", {"delta": _Delta, "finish_reason": str | None})
_Chunk = TypedDict("_Chunk", {"choices": list[_Choice], "error": dict[str, object]}, total=False)
_Outcome = TypedDict("_Outcome", {"text": str, "state": str, "rc": int, "err": str})
class _Plan(Protocol):
    mode: str
    base_idx: int
    offset: int
class _Tail(Protocol):
    done_event: threading.Event
    stop_event: threading.Event
    drain_outcome: str
    last_error_step_index: int
    last_planner_step_index: int
    final_planner_content: str
    def _emit_record(self, raw: bytes) -> None: ...
    def _finish(self) -> None: ...
class _Run(Protocol):
    q: queue.Queue[tuple[str, object]]
class _Runner(Protocol):
    stop: Callable[[], bool] | None
    def attempt(self, index: int, budget: float) -> dict[str, object]: ...
    def recovery_snapshot(self) -> str: ...
class _Tool(Protocol):
    error: str
    def feed(self, text: str) -> bool: ...
    def finish(self) -> None: ...
    def turn_complete(self) -> bool: ...
    def recovery_snapshot(self) -> str: ...
class _Handler(Protocol):
    _send: Callable[[int, object], None]
    send_response: Callable[..., object]
    send_header: Callable[..., object]
    end_headers: Callable[[], object]
    _emit: Callable[[str], bool]
    _job_client_gone: Callable[[], bool]
    _execute: Callable[..., _Outcome]
    _run_once_impl: Callable[..., _Outcome]
    _serve_sse: Callable[[dict[str, object]], None]
    _snapshot_done: Callable[..., object]
class _Bridge(Protocol):
    _TurnPlan: Callable[[], _Plan]
    _TranscriptTail: Callable[..., _Tail]
    _ToolTurn: Callable[..., _Tool]
    _done_recovery_aliases_enabled: Callable[[], bool]
    Handler: type[_Handler]
    DYNAMIC_CONFIG_PATH: Path
    DYNAMIC_CONFIG_MAX_BYTES: int
def _accept(*_args: object, **_kwargs: object) -> bool:
    return True
def _load_bridge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Bridge:
    for name in tuple(os.environ):
        if name.startswith(("AGY_", "BRIDGE_CAUSAL_TURN_RECOVERY", "BRIDGE_STREAM_")):
            monkeypatch.delenv(name)
    for name in ("AGY_SELF_HEAL_INTERRUPTED_TURN", "AGY_CAUSAL_RECOVERY_ENABLED", "BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED"):
        monkeypatch.setenv(name, "1")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "global.json"))
    monkeypatch.setenv("AGY_BRIDGE_KEY", "test-key-causal-recovery")
    spec = importlib.util.spec_from_file_location("agy_bridge_server_causal_recovery_under_test", _ROOT / "bridges" / "agy-bridge" / "server.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DYNAMIC_CONFIG_PATH", tmp_path / "local.json")
    return cast(_Bridge, cast(object, module))
def _make_tail(bridge: _Bridge, error_steps: tuple[int, ...], final_step: int) -> _Tail:
    plan = bridge._TurnPlan()
    plan.mode, plan.base_idx, plan.offset = "OFF", 0, 0
    tail = bridge._TranscriptTail(emit=_accept, stop_event=threading.Event(), done_event=threading.Event(), resumed=False, plan=plan, turn_id="causal-replay", emit_content=_accept)
    setattr(tail, "attempt", 0)
    records: tuple[dict[str, object], ...] = (*(dict(type="ERROR_MESSAGE", step_index=step, status="DONE", content=_ERROR) for step in error_steps), dict(type="PLANNER_RESPONSE", step_index=final_step, status="DONE", content=_FINAL, tool_calls=[]))
    for record in records:
        tail._emit_record(json.dumps(record, ensure_ascii=False).encode("utf-8"))
    tail.done_event.set()
    tail.stop_event.set()
    tail.drain_outcome = "complete"
    tail._finish()
    assert (tail.last_error_step_index, tail.last_planner_step_index, tail.final_planner_content) == (error_steps[-1], final_step, _FINAL)
    return tail
def _make_run(tail: _Tail) -> _Run:
    events: queue.Queue[tuple[str, object]] = queue.Queue()
    events.put(("result", result := dict(status="ERROR", error=_ERROR, conversation_id="causal-replay")))
    events.put(("done", (1, _FINAL, result)))
    return cast(_Run, cast(object, SimpleNamespace(q=events, _tail=tail, attempt=0, started=time.monotonic(), got_event=True, content_streaming=True, usage_enabled=False, proc=SimpleNamespace(returncode=1), controller=SimpleNamespace(on_activity=_accept), terminal_drain=lambda _budget: (), reconcile_result=str, _arbiter=SimpleNamespace(last_result_diverged=False), err_box=(), turn_id="causal-replay")))
def _serve_replay(bridge: _Bridge, run: _Run, tool_stop: Callable[[], bool] | None = None, options: dict[str, object] | None = None) -> tuple[list[_Chunk], _Outcome]:
    frames: list[str] = []
    outcomes: list[_Outcome] = []
    handler = bridge.Handler.__new__(bridge.Handler)
    handler.send_response = handler.send_header = handler.end_headers = _accept
    handler._emit = lambda data: frames.append(data) or True
    handler._job_client_gone = lambda: False
    def run_once(ctx: dict[str, object], on_text: _TextCallback, on_trace: _TraceCallback, on_reasoning: _TextCallback, keepalive: Callable[[], bool]) -> _Outcome:
        if not ctx.get("quiet"):
            assert on_reasoning("Синтетическая активность перед terminal done")
        if ctx.get("prelude"):
            assert on_text(str(ctx["prelude"]))
        out = handler._execute(run, on_text, on_trace, on_reasoning, keepalive, ctx.get("tool_stop", tool_stop))
        cast(Callable[[_Outcome], None], ctx["finalize_timeout"])(out)
        outcomes.append(out)
        return out
    handler._run_once_impl = run_once
    sent: list[tuple[int, object]] = []
    handler._send = lambda code, body: sent.append((code, body))
    handler._serve_sse({"model": "causal-replay", "emulate_tools": False} | (options or {}))
    assert len(outcomes) == 1 and run.q.empty()
    assert (frames and frames[-1] == "data: [DONE]\n\n") or (not frames and len(sent) == 1 and sent[0][0] == 502)
    assert bool(sent) == bool(options and options.get("quiet") and outcomes[0]["state"] == "agy_error")
    frames += ["data: " + json.dumps(sent[0][1])] if sent else []
    chunks = [cast(_Chunk, json.loads(frame[6:])) for frame in frames if frame.startswith("data: ") and frame != "data: [DONE]\n\n"]
    return chunks, outcomes[0]
def _assert_final_preserved(chunks: list[_Chunk], out: _Outcome) -> None:
    content = "".join(chunk["choices"][0]["delta"].get("content", "") for chunk in chunks if "choices" in chunk)
    assert content == out["text"] == _FINAL and "✓ SEAL" in content
    assert (out["state"], out["rc"], out["err"]) == ("done", 0, "") and not any("error" in chunk for chunk in chunks)
    assert sum(choice["finish_reason"] == "stop" for chunk in chunks for choice in chunk.get("choices", ())) == 1
@pytest.mark.parametrize("steps", (((218, 321), 370), ((136,), 283)))
def test_recovered_terminal_has_no_sse_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, steps: tuple[tuple[int, ...], int]) -> None:
    bridge = _load_bridge(monkeypatch, tmp_path)
    messages: list[str] = []
    monkeypatch.setattr(bridge, "_log", messages.append)
    _assert_final_preserved(*_serve_replay(bridge, _make_run(_make_tail(bridge, *steps))))
    logs = [cast(dict[str, object], json.loads(line)) for line in messages if line.startswith("{")]
    assert len(logs) == 1 and logs[0]["reason"] == "causal_echo_recovered"
    assert set(logs[0]) == {"reason", "last_error_seq", "last_completion_seq", "rc"}
    assert _ERROR not in "".join(messages) and _FINAL not in "".join(messages)
@pytest.mark.parametrize("veto", ("env", "canonical_env", "json", "canonical_json", "broken", "symlink", "signal", "running", "no_proc_running", "open_tool", "unknown_tool", "live_producer", "incomplete_drain", "fatal", "attempt", "missing_attempt", "unindexed", "Policy violation: connection reset by peer", "content_policy_violation: connection closed", "safety_policy: connection reset"))
def test_recovery_vetoes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, veto: str) -> None:
    bridge = _load_bridge(monkeypatch, tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "_ERROR", veto if ": connection" in veto else _ERROR)
    run, tool_stop = _make_run(_make_tail(bridge, (218, 321), 370)), None
    if veto in ("env", "canonical_env"):
        name = {"env": "AGY_CAUSAL_RECOVERY_ENABLED", "canonical_env": "BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED"}[veto]
        monkeypatch.setenv(name, "false")
    elif veto == "symlink":
        _ = (tmp_path / "target.json").write_text("{}")
        bridge.DYNAMIC_CONFIG_PATH.symlink_to(tmp_path / "target.json")
    elif veto in ("json", "canonical_json", "broken"):
        _ = bridge.DYNAMIC_CONFIG_PATH.write_text({
            "json": '{"causal_recovery_enabled": false}',
            "canonical_json": '{"causal_turn_recovery_enabled": false}', "broken": "{"}[veto])
    elif veto in ("signal", "running", "no_proc_running"):
        monkeypatch.setattr(run, "proc", None if veto == "no_proc_running" else SimpleNamespace(returncode=-9 if veto == "signal" else None))
        monkeypatch.setattr(run, "process_exited", False, raising=False)
    elif veto in ("open_tool", "unknown_tool"):
        tool = bridge._ToolTurn([], _accept, _accept, _accept)
        assert tool.feed('<tool_call>{"name":"unfinished"')
        assert tool.recovery_snapshot() == "open"
        tool_stop = tool.turn_complete if veto == "open_tool" else _accept
    elif veto == "fatal" or ": connection" in veto:
        monkeypatch.setattr(run, "has_fatal_error", veto == "fatal", raising=False)
    elif veto == "live_producer":
        monkeypatch.setattr(cast(_Tail, getattr(run, "_tail")), "thread", SimpleNamespace(is_alive=lambda: True))
    elif veto in ("attempt", "missing_attempt"):
        monkeypatch.setattr(run, "attempt", 2 if veto == "attempt" else -1)
    elif veto == "unindexed":
        cast(_Tail, getattr(run, "_tail"))._emit_record(json.dumps(dict(type="ERROR_MESSAGE", content=_ERROR)).encode())
        cast(_Tail, getattr(run, "_tail"))._emit_record(json.dumps(dict(type="PLANNER_RESPONSE", step_index=371, content=_FINAL)).encode())
    else:
        cast(_Tail, getattr(run, "_tail")).drain_outcome = "timeout"
    chunks, out = _serve_replay(bridge, run, tool_stop)
    assert out["state"] == "agy_error" and out["rc"] != 0 and out["err"] and out["text"] == "" and any("error" in chunk for chunk in chunks) and (": connection" not in veto or out["err"] == veto)
def _assert_attempt_sequence(runner: _Runner, job: bool, fail: bool) -> None:
    """Повторные прямые и job-попытки восстанавливают scope даже при исключении."""
    for index in (2, 3):
        getattr(runner, "s").ctx["step_job_id"] = str(index) if job else ""
        with pytest.raises(RuntimeError, match="attempt failed") if fail and not job else nullcontext():
            assert runner.attempt(index, 1.0) == (dict(state="pump_error", text="", rc=1) if fail else dict(state="done", text="", rc=0, err=""))
        assert getattr(sys.modules["agy_runtime.sse_body_runner"], "current_attempt_index")() == -1
def _start_attempt_tail(bridge: _Bridge, monkeypatch: pytest.MonkeyPatch) -> tuple[object, ...]:
    """Проверять происхождение индекса через настоящие tail.start и parser."""
    owner = SimpleNamespace(attempt=-1)
    tail = bridge._TranscriptTail(emit=_accept, stop_event=threading.Event(), done_event=threading.Event(), resumed=False, run_ref=owner)
    monkeypatch.setattr(getattr(tail, "thread"), "start", lambda: None)
    getattr(tail, "start")()
    tail._emit_record(json.dumps(dict(type="ERROR_MESSAGE", step_index=1, content=_ERROR)).encode())
    tail._emit_record(json.dumps(dict(type="PLANNER_RESPONSE", step_index=2, content=_FINAL)).encode())
    return (owner.attempt, *(getattr(tail, name) for name in ("attempt", "last_error_attempt", "last_completion_attempt")))
@pytest.mark.parametrize("previous,fail", ((None, False), (None, True), (_accept, False), (_accept, True)))
@pytest.mark.parametrize("job", (False, True))
def test_tool_snapshot_is_read_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, previous: Callable[[], bool] | None, fail: bool, job: bool) -> None:
    bridge = _load_bridge(monkeypatch, tmp_path)
    tool, done, clean = (bridge._ToolTurn([], _accept, _accept, _accept) for _ in range(3))
    assert tool.recovery_snapshot() == "closed" and getattr(tool, "_finished") is False
    assert tool.feed('<tool_call>{"name":"unfinished"') and tool.recovery_snapshot() == "open" and getattr(tool, "_finished") is False
    assert done.feed('<tool_call>{"name":"x","arguments":{}}</tool_call>') and done.recovery_snapshot() == "closed"
    done.finish()
    assert done.recovery_snapshot() == "closed" and getattr(done, "_finished") is True
    tool.error = "malformed"
    assert tool.recovery_snapshot() == "open"
    monkeypatch.delattr(tool, "_normalizer")
    tool.error = ""
    assert tool.recovery_snapshot() == "unknown"
    _assert_final_preserved(*_serve_replay(bridge, _make_run(_make_tail(bridge, (218, 321), 370)), clean.turn_complete))
    assert getattr(clean, "_finished") is False
    runner = cast(_Runner, object.__new__(cast(type[object], getattr(sys.modules["agy_runtime.sse_body_runner"], "_SseBodyRunner"))))
    vars(runner).update(s=SimpleNamespace(ctx={"tool_stop": clean.turn_complete, "step_job_id": "job" if job else "", "model": "test", "full_prompt": "test"}, disconnected=False), buffering=False, deadline=float("inf"), time=time, stop=previous)
    observed: list[tuple[object, ...]] = []
    def invoke() -> _Outcome:
        observed.append(_start_attempt_tail(bridge, monkeypatch))
        assert runner.stop == clean.turn_complete
        if fail:
            raise RuntimeError("attempt failed")
        return _Outcome(state="done", text="", rc=0, err="")
    handler = bridge.Handler.__new__(bridge.Handler)
    handler._run_once_impl = lambda *_args: invoke()
    setattr(handler, "connection", None)
    monkeypatch.setattr(bridge, "_client_gone", lambda _conn: False)
    monkeypatch.setattr(runner, "_invoke", lambda: getattr(handler, "_run_once")(getattr(runner, "s").ctx, _accept, _accept, _accept, _accept))
    _assert_attempt_sequence(runner, job, fail)
    assert observed == [(2, 2, 2, 2), (3, 3, 3, 3)]
    assert runner.stop is previous
    assert previous is not None or runner.recovery_snapshot() == "closed"
    assert getattr(sys.modules["agy_runtime.sse_body_runner"], "current_attempt_index")() == -1
@pytest.mark.parametrize("mode", ("off", "retry", "rollback", "both"))
@pytest.mark.parametrize("case", ("clean", "empty", "open", "unknown", "broken", "no_tools"))
@pytest.mark.parametrize("quiet", (False, True))
def test_sse_runner_tool_recovery_join(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mode: str, case: str, quiet: bool) -> None:
    bridge = _load_bridge(monkeypatch, tmp_path)
    monkeypatch.setenv("BRIDGE_STREAM_MIDSTREAM_RETRY_ENABLED", str(mode in ("retry", "both")))
    monkeypatch.setenv("BRIDGE_STREAM_TOOL_ROLLBACK_ENABLED", str(mode in ("rollback", "both")))
    if case in ("unknown", "broken"):
        def snapshot(_self: object) -> str:
            raise RuntimeError("snapshot failed")
        monkeypatch.setattr(bridge._ToolTurn, "recovery_snapshot", None if case == "unknown" else snapshot)
    run = _make_run(_make_tail(bridge, (218, 321), 370))
    options: dict[str, object] = dict(emulate_tools=case != "no_tools", quiet=quiet, prelude={"empty": "<tool_call>", "open": '<tool_call>{"name":"unfinished"'}.get(case, ""))
    chunks, out = _serve_replay(bridge, run, options=options)
    if case in ("clean", "no_tools"):
        _assert_final_preserved(chunks, out)
    else:
        assert out["state"] == "agy_error" and out["rc"] != 0 and out["text"] == ""
        assert any("error" in chunk for chunk in chunks) and not out.get("graceful_done")
        assert _FINAL not in json.dumps(chunks, ensure_ascii=False) and "<tool_call>" not in json.dumps(chunks)
def test_done_recovery_flag_returns_strict_bools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bridge = _load_bridge(monkeypatch, tmp_path)
    for name in ("AGY_SELF_HEAL_INTERRUPTED_TURN", "AGY_CAUSAL_RECOVERY_ENABLED", "BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED"):
        monkeypatch.delenv(name)
    path, limit, enabled = bridge.DYNAMIC_CONFIG_PATH, bridge.DYNAMIC_CONFIG_MAX_BYTES, bridge._done_recovery_aliases_enabled
    keys = ("causal_recovery_enabled", "causal_turn_recovery_enabled", "BRIDGE_CAUSAL_TURN_RECOVERY_ENABLED")
    def verdict(raw: str | None) -> bool:
        path.unlink(missing_ok=True)
        if raw is not None:
            _ = path.write_text(raw)
        return enabled()
    on = json.dumps({keys[0]: True})
    cases = [(None, False), ("{}", False), ("{", False), (on + " " * (limit - len(on)), True), (on + " " * (limit - len(on) + 1), False), (json.dumps(dict.fromkeys(keys, True)), True), (json.dumps(dict.fromkeys(keys, 1)), False)]
    cases += [(json.dumps({key: val}), ok) for key in keys for val, ok in ((True, True), (1, False), (False, False))]
    for raw, expected in cases:
        assert verdict(raw) is expected, (raw or "")[:60]
    with monkeypatch.context() as ctx:
        ctx.setenv("AGY_CAUSAL_RECOVERY_ENABLED", "false")
        assert verdict("{}") is False
    def fake_fstat(_fd: int) -> SimpleNamespace:
        return SimpleNamespace(st_mode=stat.S_IFDIR)
    with monkeypatch.context() as ctx:
        ctx.setattr(os, "fstat", fake_fstat)
        assert verdict("{}") is False
    path.unlink()
    path.symlink_to(tmp_path)
    assert enabled() is False
@pytest.mark.parametrize("case", (({"error": "E" * 600, "status": "ERROR"}, {}, ("E" * 500, "cleared"), "wire", ("E" * 600, "error", "cleared", "wire")), (None, {"error": "R", "status": " Done "}, ("", ""), None, ("R", "done", "", "")), (None, {}, ("fallback", ""), None, ("fallback", "", "", "")),
    ({"error": "P", "status": "ERROR"}, {"error": "R", "status": " Done "}, ("", ""), None, ("R", "done", "", "")), ({"error": "P", "status": "ERROR"}, None, ("", ""), None, ("P", "error", "", "")),))  # request.result_ev приоритетнее payload
def test_snapshot_done_keeps_full_facts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, case: _Case) -> None:
    payload_ev, result_ev, errors, wire, expected = case
    handler = (bridge := _load_bridge(monkeypatch, tmp_path)).Handler.__new__(bridge.Handler)
    run = SimpleNamespace(proc=SimpleNamespace(returncode=1), _tail=None, _content_emitted_wire=wire, attempt=2)
    monkeypatch.setattr(handler, "_attempt", 0, raising=False)
    request = SimpleNamespace(payload=(1, _FINAL, payload_ev), result_ev=result_ev, errors=errors)
    paths = ("text.result_error", "result.result_status", "text.cleared_error", "text.emitted_text", "text.final_text", "result.process_exited")
    ports = SimpleNamespace(state=dict.fromkeys, turn_complete=None)  # fromkeys("", 0) == {}: текста нет
    assert attrgetter(*paths)(handler._snapshot_done(run, request, ports)) == (*expected, _FINAL, True) and attrgetter("result.attempt")(handler._snapshot_done(run, request, ports)) == 2
    monkeypatch.setattr(run, "proc", SimpleNamespace(returncode=None))  # живой proc: exited берётся из returncode
    assert attrgetter("result.process_exited")(handler._snapshot_done(run, request, ports)) is False
    for extra, exited in (({}, False), ({"process_exited": False}, False), ({"process_exited": True}, True)):
        bare = SimpleNamespace(proc=None, _tail=None, _content_emitted_wire=wire, **extra)  # без proc: fail-closed
        assert attrgetter("result.process_exited")(handler._snapshot_done(bare, request, ports)) is exited and attrgetter("result.attempt")(handler._snapshot_done(bare, request, ports)) == -1

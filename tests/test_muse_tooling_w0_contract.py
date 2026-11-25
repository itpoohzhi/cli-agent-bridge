# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false
"""W0 contract for `muse-bridge-tooling`: pre-fix red-repro [F-30]/[F-31]/[F-33]/[F-14], post-fix contract, live MCP spike."""
from __future__ import annotations
import hmac
import json
import os
import queue
import secrets
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast, override
import pytest

from adapters.stdio_drivers.muse_codec import build_initialized_msg, build_session_leave_msg, build_session_start_msg, build_turn_start_msg, uuid7
from adapters.stdio_drivers.muse_env import build_muse_env, prepare_muse_zero_canon_home
from adapters.stdio_resident_delta import _emulate_tools_setup
from core.backend_adapter import TurnContext
from core.backend_routing_models import TranscriptItem
from core.resident_history import ResidentHistoryTracker, build_assistant_transcript_item, plan_history_transition
from core.resident_identity import ResidentIdentity
from core.resident_turn_envelope import ResidentTurnEnvelope
from core.stdio_resident.routed_turn_result import RoutedExecOptions, execute_routed_turn_result
from core.stdio_resident.types import SlotBinding
from core.tool_emulation import sanitize_tool_call  # pyright: ignore[reportUnknownVariableType]

PRE_FIX_RED = os.environ.get("MUSE_W0_ASSERT_PRE_FIX_RED") == "1"
def test_w0_routed_turn_result_preserves_tool_calls() -> None:
    chunk = {"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "call_abc", "type": "function", "function": {"name": "bash", "arguments": '{"cmd":"pwd"}'}}]}, "finish_reason": None}]}
    route = SimpleNamespace(kind="resident", is_ephemeral=False)
    options = RoutedExecOptions(bridge_proxy_fn=cast(Any, None), usage_enabled=False)
    res = execute_routed_turn_result(lambda _request: iter([chunk]), route, {"model": "m", "prompt": "hi"}, None, options)
    if PRE_FIX_RED:
        assert not hasattr(res, "tool_calls")  # [F-30]: delta.tool_calls dropped
        return
    calls = cast(list[Any], getattr(res, "tool_calls", None))
    assert calls is not None and len(calls) == 1
    first = calls[0]
    assert (first["function"]["name"] if isinstance(first, dict) else first.function.name) == "bash"

def test_w0_emulate_tools_live_reasoning_streaming() -> None:
    adapter = SimpleNamespace(_config=SimpleNamespace(max_turn_output_bytes=65536))
    ctx = TurnContext(model="m", effort="low", prompt="hi", emulate_tools=True)
    events: list[tuple[str, str]] = []
    routed_writer, _validator, _keepalive = _emulate_tools_setup(adapter, ctx, lambda kind, value: bool(events.append((kind, value)) or True))
    if PRE_FIX_RED:
        assert routed_writer is None  # [F-31]: live <Think> SSE disabled
        return
    assert routed_writer is not None
    assert routed_writer("reasoning", "thinking step") and ("reasoning", "thinking step") in events

def test_w0_resident_history_rebind_for_tool_calls() -> None:
    if PRE_FIX_RED:
        assert not hasattr(ResidentHistoryTracker, "rebind_assistant_item")  # [F-33]
        return
    def env(items: tuple[TranscriptItem, ...]) -> ResidentTurnEnvelope:
        return ResidentTurnEnvelope(identity=ResidentIdentity("owner", "chat", False, "label", "turn", "", "", "session-key", ""), backend_id="b", model="m", effort="low", cwd_norm="/w", secret=b"0123456789abcdef0123456789abcdef", rpc=cast(Any, SimpleNamespace(items=items, runnable=True)), full_prompt="F")

    user_one = TranscriptItem("user", "U1", "digest:u1")
    binding = SlotBinding("slot", 1)
    tracker = ResidentHistoryTracker()
    _ = tracker.commit("session-key", plan_history_transition(None, env((user_one,))), binding)
    calls = [{"id": "call_1234", "type": "function", "function": {"name": "bash", "arguments": '{"cmd":"pwd"}'}}]
    assert (assistant := build_assistant_transcript_item("", calls)) is not None
    assert callable(getattr(tracker, "rebind_assistant_item", None))
    getattr(tracker, "rebind_assistant_item")("session-key", binding, assistant)
    nxt = plan_history_transition(tracker.get("session-key"), env((user_one, assistant, TranscriptItem("tool", "[tool result call_1234] ok", "digest:tool"))), binding)
    assert nxt.requires_slot_reset is False

def test_w0_sanitize_tool_call_strips_mcp_prefix() -> None:
    schemas: dict[str, Any] = {"bash": {"type": "function", "function": {"name": "bash", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}}
    for prefixed in ("mcp__bridge__bash", "bridge__bash"):
        call = {"id": "call_x", "type": "function", "function": {"name": prefixed, "arguments": '{"command":"pwd"}'}}
        assert len(results := sanitize_tool_call(call, schemas)) == 1
        out = results[0]
        fn = cast(Any, out["function"] if isinstance(out, dict) else out.function)
        name = str(fn["name"])
        resolved = name if name in schemas else name.removeprefix("mcp__bridge__").removeprefix("bridge__").removeprefix("bridge:")
        assert resolved == "bash"
        assert json.loads(str(fn["arguments"]))["command"] == "pwd"

def _bind_wire_scope(mcp_url: str, token: str) -> Any:
    try:
        mcs = __import__("core.stdio_resident.mcp_capture_server", fromlist=("TurnWireSessionScope",))
    except ImportError:
        return None
    spec_cls = cast(Any, getattr(mcs, "TurnMcpSessionSpec", None))
    for kwargs in ({"mcp_url": mcp_url, "bearer_token": token, "developer_prompt": None, "suppress_host_tools": True}, {"mcp_url": mcp_url, "bearer_token": token}):
        try:
            return getattr(mcs, "TurnWireSessionScope").bind(spec_cls(**kwargs))
        except (TypeError, AttributeError):
            continue
    return None

def test_w0_muse_codec_session_start_contract() -> None:
    sid = uuid7()
    msg = json.loads(build_session_start_msg(sid, "muse-ember-1.0", "denyUnmatched"))
    assert msg["jsonrpc"] == "2.0" and msg["method"] == "session/start"
    params = cast(dict[str, Any], msg["params"])
    assert params["sessionId"] == sid and params["modelId"] == "muse-ember-1.0" and params["approvalMode"] == "denyUnmatched"
    if PRE_FIX_RED:
        assert "config" not in params  # [F-14]
        return
    bound = _bind_wire_scope("http://127.0.0.1:1/mcp/spike-nonce", "spike-bearer-token")
    if bound is not None:
        with bound:
            scoped = json.loads(build_session_start_msg(sid, "muse-ember-1.0", "denyUnmatched"))
        assert cast(dict[str, Any], scoped["params"]).get("config", {}).get("mcpServers")

def _next(h: Any, timeout_s: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(timeout_s, 0.0)
    while (left := deadline - time.monotonic()) > 0:
        try:
            line = cast(bytes, h.lines.get(timeout=min(left, 0.25))).decode("utf-8", errors="replace").strip()
            payload = json.loads(line) if line else None
        except (queue.Empty, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        payload = cast(dict[str, Any], payload)
        h.raw.append(line)
        method = payload.get("method")
        if isinstance(method, str):
            h.methods.add(method)
        if payload.get("error") is not None:
            h.errors.append(str(payload["error"])[:200])
        box = cast(Any, payload.get("params") if isinstance(payload.get("params"), dict) else payload.get("result"))
        if not h.turn_id and isinstance(box, dict) and isinstance((tid := cast(Any, box).get("turnId")), str):
            h.turn_id = tid
        return payload
    return None

def _spike_handler(h: Any) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        @override
        def log_message(self, _fmt: str, *_args: Any) -> None:
            return
        def _reply(self, status: int, result: Any, req_id: Any = None) -> None:
            data = b"" if result is None else json.dumps({"jsonrpc": "2.0", "id": req_id, "result": result}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if data:
                _ = self.wfile.write(data)
        def do_POST(self) -> None:
            if self.path != f"/mcp/{h.nonce}" or not hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {h.token}"):
                self.send_error(403)
                return
            try:
                payload = cast(dict[str, Any], json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8")))
            except ValueError:
                payload = {}
            method, req_id = str(payload.get("method") or ""), payload.get("id")
            h.methods.add(method)  # MCP capability-path methods share the seen-methods set with MSP events.
            if method == "initialize":
                self._reply(200, {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "bridge-spike", "version": "1.0"}}, req_id)
            elif method == "tools/list":
                schema = {"type": "object", "properties": {"msg": {"type": "string"}}, "required": ["msg"]}
                self._reply(200, {"tools": [{"name": "echo_probe", "description": "Echo probe tool for bridge test", "inputSchema": schema}]}, req_id)
            elif method == "tools/call":
                params = cast(Any, payload.get("params") if isinstance(payload.get("params"), dict) else {})
                with h.lock:
                    h.captured_calls.append({"name": params.get("name"), "arguments": params.get("arguments")})
                h.called_evt.set()
                h.release_evt.wait(3.0)
                self._reply(200, {"content": [{"type": "text", "text": "captured"}], "isError": False}, req_id)
            else:
                self._reply(202 if method == "notifications/initialized" else 200, {}, req_id)
    return _Handler

def _run_session(proc: subprocess.Popen[bytes], h: Any, mcp_url: str) -> None:
    stdin = cast(Any, proc.stdin)
    def send(data: bytes) -> None:
        try:
            stdin.write(data)
            stdin.flush()
        except (OSError, ValueError):
            pass
    def wait_id(req_id: object, timeout_s: float) -> dict[str, Any] | None:
        for _ in range(max(1, int(timeout_s * 4))):
            payload = _next(h, 0.25)
            if payload is not None and payload.get("id") == req_id:
                return payload
        return None
    # W0 finding: muse 1.4.25 rejects config.mcpServers unless initialize requests the sessionMcp capability.
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "cli_agent_bridge", "version": "1.0.0"}, "capabilities": {"requestedCapabilities": ["sessionMcp"]}}}
    send((json.dumps(init) + "\n").encode("utf-8"))
    assert wait_id(1, 15.0) is not None, "muse did not ack initialize"
    send(build_initialized_msg())
    h.session_id = uuid7()
    # W0 finding: denyUnmatched auto-denies unmatched MCP tools before any approval/decide, so allowAll is required.
    start = {"jsonrpc": "2.0", "id": 2, "method": "session/start", "params": {"commandId": uuid7(), "sessionId": h.session_id, "modelId": "muse-ember-1.0", "approvalMode": "allowAll", "config": {"developerPrompt": None, "mcpServers": {"bridge": {"transport": "streamableHttp", "url": mcp_url, "headers": {"Authorization": f"Bearer {h.token}"}, "mode": "required"}}}}}
    send((json.dumps(start) + "\n").encode("utf-8"))
    assert wait_id(2, 15.0) is not None, "muse did not ack session/start"
    send(build_turn_start_msg(h.session_id, "low", "Call the echo_probe tool right now with msg='spike_ok'. Do not answer in plain text.", uuid7(), 3))
    cancelled, deadline = False, time.monotonic() + 45.0
    while time.monotonic() < deadline:
        payload = _next(h, deadline - time.monotonic())
        if payload is None:
            break
        if h.called_evt.is_set() and not cancelled:
            cancelled = True
            send((json.dumps({"jsonrpc": "2.0", "id": 4, "method": "turn/cancel", "params": {"commandId": uuid7(), "sessionId": h.session_id, "turnId": h.turn_id}}) + "\n").encode("utf-8"))
            h.release_evt.set()
            deadline = min(deadline, time.monotonic() + 3.0)
        elif str(payload.get("method") or "") in {"turn/completed", "run.terminal.completed", "turn/failed", "run.terminal.failed"}:
            break

def _teardown(proc: subprocess.Popen[bytes], server: ThreadingHTTPServer, h: Any) -> None:
    h.release_evt.set()
    stdin = cast(Any, proc.stdin)
    try:
        stdin.write(build_session_leave_msg(h.session_id))
        stdin.flush()
        stdin.close()
    except (OSError, ValueError, AttributeError):
        pass
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(proc.pid), sig)
            _ = proc.wait(timeout=5.0)
            break
        except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
            continue
    server.shutdown()
    server.server_close()

@pytest.mark.live_spike
def test_w0_live_spike_muse_mcp_capture(tmp_path: Path) -> None:
    if os.environ.get("MUSE_LIVE_SPIKE") != "1":
        pytest.skip("MUSE_LIVE_SPIKE!=1")
    bin_path = next((p for p in (os.environ.get("MUSE_BIN"), os.environ.get("MUSE_BIN_PATH")) if p and Path(p).is_file()), "")
    wrapper = Path.home() / ".local" / "bin" / "muse"
    if not bin_path and wrapper.is_file():
        bins = sorted(p for p in wrapper.parent.glob("muse-bin-*") if p.is_file()) if (Path.home() / ".config/muse-launch/muse-cli.sh").is_file() else []
        bin_path = str(bins[-1]) if bins else str(wrapper)
    if not bin_path:
        pytest.fail("muse binary not found")
    h = SimpleNamespace(token=secrets.token_hex(32), nonce=secrets.token_hex(16), lock=threading.Lock(), called_evt=threading.Event(), release_evt=threading.Event(), captured_calls=[], methods=set(), raw=[], errors=[], turn_id="", session_id="", lines=queue.Queue())
    server = ThreadingHTTPServer(("127.0.0.1", 0), _spike_handler(h))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    mcp_url = f"http://127.0.0.1:{server.server_address[1]}/mcp/{h.nonce}"
    home = prepare_muse_zero_canon_home(os.environ.get("HOME") or str(Path.home()), tmp_path / "muse_home")
    env = build_muse_env(None, bin_path, turn_sandbox=str(tmp_path), server_env={**os.environ, "HOME": str(home)})
    argv = [bin_path, "serve", "--provider", "meta", "--preset", "empty", "--disable-write", "--disable-shell", "--disable-request-user-input", "--no-session-log"]
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, start_new_session=True)
    threading.Thread(target=lambda: [h.lines.put(r) for r in iter(cast(Any, proc.stdout).readline, b"")], daemon=True).start()
    try:
        _run_session(proc, h, mcp_url)
    finally:
        _teardown(proc, server, h)
    print(f"SPIKE_METHODS={sorted(h.methods)}\nSPIKE_CAPTURED={h.captured_calls}")
    print(f"SPIKE_EVENTS_COUNT={len(h.raw)}\nSPIKE_ERRORS={h.errors}")
    assert "tools/list" in h.methods and len(h.captured_calls) >= 1
    assert all("unknown tool" not in line and "(none)" not in line for line in h.raw)

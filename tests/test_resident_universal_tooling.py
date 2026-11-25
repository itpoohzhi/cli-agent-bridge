# pyright: reportAny=false, reportExplicitAny=false, reportPrivateUsage=false
"""End-to-end integration tests for universal stdio-resident U3 tooling."""

from __future__ import annotations

import json
import queue
import socket
import stat
import threading
import urllib.parse
import urllib.request
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from adapters.stdio_drivers.muse_codec import build_session_start_msg, decode_msp_line, uuid7
from adapters.stdio_drivers.muse_env import build_muse_env
from adapters.stdio_resident_delta import execute_stdio_turn
from core.backend_adapter import TurnContext
from core.backend_routing_models import TranscriptItem
from core.resident_history import ResidentHistoryTracker, build_assistant_transcript_item, plan_history_transition
from core.resident_identity import ResidentIdentity
from core.resident_turn_envelope import ResidentTurnEnvelope
from core.stdio_resident.claude_driver import ClaudeStreamJsonDriver
from core.stdio_resident.codex_protocol_fsm import EffectKind, EventKind, ProtocolEvent, ProtocolPhase, ProtocolState, transition
from core.stdio_resident.config import mcp_tool_capture_enabled
from core.stdio_resident.mcp_capture_server import TurnMcpSessionSpec, TurnWireSessionScope
from core.stdio_resident.process_io import LINE, TIMEOUT
from core.stdio_resident.runtime_wire import stream_driver_turn
from core.stdio_resident.types import SlotBinding

_BASH_SCHEMAS: dict[str, Any] = {
    "bash": {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run shell command",
            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        },
    }
}


def _http_post_json(url: str, auth_header: str, body: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json", "Authorization": auth_header}, method="POST"
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=3.0) as resp:
        raw = resp.read().decode("utf-8")
        return int(resp.status), cast(dict[str, Any], json.loads(raw)) if raw else {}


class _FakeStdioHandle:
    def __init__(self) -> None:
        self.generation: int = 1
        self.written: list[dict[str, Any]] = []
        self._lines: queue.Queue[str] = queue.Queue()

    def write(self, data: bytes) -> None:
        frame = cast(dict[str, Any], json.loads(data.decode("utf-8")))
        self.written.append(frame)
        if frame.get("method") == "turn/cancel":
            done = {"jsonrpc": "2.0", "method": "turn/completed", "params": {"stopReason": "cancelled"}}
            self._lines.put(json.dumps(done) + "\n")

    def read_line_outcome(self, timeout_s: float = 0.05) -> tuple[str, Any]:
        try:
            return (LINE, SimpleNamespace(line=self._lines.get(timeout=timeout_s), is_stderr=False))
        except queue.Empty:
            return (TIMEOUT, None)


class _FakeMuseMcpDriver:
    def __init__(self, session_id: str) -> None:
        self.session_id: str = session_id
        self.mcp_url: str = ""
        self.start_params: dict[str, Any] = {}
        self.client_results: dict[str, Any] = {}
        self.client_error: BaseException | None = None
        self._thread: threading.Thread | None = None

    def prepare_turn(self, _handle: Any, turn_context: dict[str, Any], *, timeout_s: float = 5.0) -> bool:
        _ = timeout_s
        turn_context["turn_id"] = "turn-mcp-1"
        start_msg = cast(dict[str, Any], json.loads(build_session_start_msg(self.session_id, "muse-ember-1.0", "denyUnmatched")))
        self.start_params = cast(dict[str, Any], start_msg["params"])
        bridge = cast(dict[str, Any], self.start_params["config"]["mcpServers"]["bridge"])
        self.mcp_url = str(bridge["url"])
        auth_header = str(bridge["headers"]["Authorization"])
        self._thread = threading.Thread(target=self._run_mcp_client, args=(self.mcp_url, auth_header), daemon=True)
        self._thread.start()
        return True

    def _run_mcp_client(self, url: str, auth_header: str) -> None:
        try:
            self.client_results["init"] = _http_post_json(url, auth_header, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            self.client_results["list"] = _http_post_json(url, auth_header, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            call_body = {
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "mcp__bridge__bash", "arguments": {"command": "pwd"}},
            }
            self.client_results["call"] = _http_post_json(url, auth_header, call_body)
        except BaseException as exc:  # pragma: no cover
            self.client_error = exc

    def encode_turn(self, prompt: str, _turn_context: Mapping[str, Any]) -> bytes:
        return (json.dumps({"jsonrpc": "2.0", "method": "turn/start", "params": {"prompt": prompt}}) + "\n").encode("utf-8")

    def decode_line(self, raw_line: str) -> Any:
        return decode_msp_line(raw_line)

    def is_terminal(self, _raw_line: str, decoded: Any) -> bool:
        return bool(getattr(decoded, "is_terminal", False))

    def join_client(self) -> None:
        if self._thread is not None:
            self._thread.join(timeout=3.0)


def _assert_port_closed(port: int) -> None:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            raise AssertionError(f"Expected loopback port {port} to be closed")
    except OSError:
        return


def test_loopback_mcp_tool_capture_and_turn_cancel() -> None:
    sid = uuid7()
    driver, handle = _FakeMuseMcpDriver(sid), _FakeStdioHandle()
    envelope = SimpleNamespace(emulate_tools=True, tool_schemas=_BASH_SCHEMAS, tool_choice=None)
    mcp_cfg = SimpleNamespace(
        mcp_tool_capture_enabled=True, suppress_builtin_tools_enabled=True,
        mcp_max_request_bytes=1048576, mcp_cancel_wait_s=1.0, mcp_coalesce_ms=10,
    )
    ctx: dict[str, Any] = {"prompt": "run pwd", "timeouts": (2.0, 3.0), "mcp_config": mcp_cfg}
    dispatched: list[bool] = []
    chunks = list(stream_driver_turn(driver, handle, envelope, ctx, lambda: dispatched.append(True)))
    driver.join_client()

    assert dispatched == [True] and driver.client_error is None
    assert driver.start_params["approvalMode"] == "allowAll"
    no_mcp = cast(dict[str, Any], json.loads(build_session_start_msg(sid, "muse-ember-1.0", "denyUnmatched")))
    assert no_mcp["params"]["approvalMode"] == "denyUnmatched"
    assert driver.client_results["init"][0] == 200
    listed_names = [t["name"] for t in driver.client_results["list"][1]["result"]["tools"]]
    assert listed_names == ["bash"] and driver.client_results["call"][0] == 200
    cancels = [f for f in handle.written if f.get("method") == "turn/cancel"]
    assert len(cancels) == 1 and cancels[0]["params"]["sessionId"] == sid and cancels[0]["params"]["turnId"] == "turn-mcp-1"
    terminal = chunks[-1]
    assert terminal.is_terminal is True and terminal.is_tool_stop is True
    assert len(terminal.tool_calls) == 1 and terminal.tool_calls[0]["function"]["name"] == "bash"
    assert json.loads(terminal.tool_calls[0]["function"]["arguments"]) == {"command": "pwd"}
    _assert_port_closed(int(urllib.parse.urlparse(driver.mcp_url).port or 0))


class _FakeToolAdapter:
    id: str = "muse"
    _config: Any = SimpleNamespace(max_turn_output_bytes=65536)
    _driver: Any = None

    def __init__(self, chunks: list[dict[str, Any]], *, runtime: Any = None, commit_hook: Any = None) -> None:
        self._chunks: list[dict[str, Any]] = chunks
        self._runtime: Any = runtime
        self._commit_hook: Any = commit_hook

    def execute_chat(self, request: Mapping[str, Any], **_kw: Any) -> Iterator[dict[str, Any]]:
        if callable(self._commit_hook):
            _ = self._commit_hook(request)
        return iter(self._chunks)


def test_text_fallback_live_sse_thinking_and_content_flush(monkeypatch: Any) -> None:
    monkeypatch.setenv("BRIDGE_STDIO_MCP_TOOL_CAPTURE_ENABLED", "false")
    assert mcp_tool_capture_enabled() is False

    tool_chunks = [
        {"choices": [{"index": 0, "delta": {"reasoning_content": "Inspecting workspace."}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"content": 'Checking cwd.\n<tool_call>{"name":"bash","arguments":{"command":"pwd"}}</tool_call>'}, "finish_reason": "stop"}]},
    ]
    events_tool: list[tuple[str, str]] = []
    ctx = TurnContext(model="muse-ember-1.0", effort="low", prompt="pwd", emulate_tools=True, tool_schemas=_BASH_SCHEMAS)
    res_tool = execute_stdio_turn(_FakeToolAdapter(tool_chunks), "muse-msp-v1", ctx, lambda k, v: bool(events_tool.append((k, v)) or True))

    assert any(k == "reasoning" and "Inspecting workspace." in v for k, v in events_tool)
    assert "".join(v for k, v in events_tool if k == "content") == ""
    assert len(res_tool.tool_calls) == 1 and res_tool.tool_calls[0].id.startswith("call_")
    assert res_tool.tool_calls[0].function.name == "bash" and res_tool.events is not None

    text_chunks = [
        {"choices": [{"index": 0, "delta": {"reasoning_content": "Formulating reply."}, "finish_reason": None}]},
        {"choices": [{"index": 0, "delta": {"content": "Final plain answer."}, "finish_reason": "stop"}]},
    ]
    events_plain: list[tuple[str, str]] = []
    res_plain = execute_stdio_turn(_FakeToolAdapter(text_chunks), "muse-msp-v1", ctx, lambda k, v: bool(events_plain.append((k, v)) or True))

    assert any(k == "reasoning" and "Formulating reply." in v for k, v in events_plain)
    assert "".join(v for k, v in events_plain if k == "content") == "Final plain answer."
    assert res_plain.text == "Final plain answer." and not res_plain.tool_calls


def test_warm_slot_multi_turn_rebind_no_false_reset() -> None:
    def _env(items: tuple[TranscriptItem, ...]) -> ResidentTurnEnvelope:
        ident = ResidentIdentity("owner", "chat", False, "lbl", "t", "", "", "session-u3", "")
        return ResidentTurnEnvelope(
            identity=ident, backend_id="muse", model="muse-ember-1.0", effort="low", cwd_norm="/w",
            secret=b"0123456789abcdef0123456789abcdef", rpc=cast(Any, SimpleNamespace(items=items, runnable=True)), full_prompt="F",
        )

    user_one = TranscriptItem("user", "Run pwd", "digest:u1")
    raw_assistant = build_assistant_transcript_item('raw preamble <tool_call>{"name":"bash","arguments":{"command":"pwd"}}</tool_call>')
    assert raw_assistant is not None
    binding = SlotBinding("slot-u3", 1)
    tracker = ResidentHistoryTracker()

    def _on_exec(req: Mapping[str, Any]) -> None:
        _ = tracker.commit("session-u3", plan_history_transition(None, _env((user_one,))), binding, raw_assistant)
        cast(list[tuple[str, Any]], req["turn_context"]["_committed_slot_sink"]).append(("session-u3", binding))

    chunks = [{"choices": [{"index": 0, "delta": {"tool_calls": [{"index": 0, "id": "call_raw", "type": "function", "function": {"name": "bash", "arguments": '{"command":"pwd"}'}}]}, "finish_reason": "tool_calls"}]}]
    ctx = TurnContext(model="muse-ember-1.0", effort="low", prompt="Run pwd", emulate_tools=True, tool_schemas=_BASH_SCHEMAS)
    res = execute_stdio_turn(_FakeToolAdapter(chunks, runtime=tracker, commit_hook=_on_exec), "muse-msp-v1", ctx, None)

    assert len(res.tool_calls) == 1 and res.tool_calls[0].id.startswith("call_")
    tc = res.tool_calls[0]
    assistant_t2 = build_assistant_transcript_item("", [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}])
    assert assistant_t2 is not None
    tool_result = TranscriptItem("tool", f"[tool result {tc.id}] /w", "digest:t1")
    assert plan_history_transition(tracker.get("session-u3"), _env((user_one, assistant_t2, tool_result)), binding).requires_slot_reset is False
    _ = tracker.commit("session-u3-raw", plan_history_transition(None, _env((user_one,))), binding, raw_assistant)
    assert tracker.rebind_assistant_item("session-u3-raw", binding, assistant_t2) is True
    assert plan_history_transition(tracker.get("session-u3-raw"), _env((user_one, assistant_t2, tool_result)), binding).requires_slot_reset is False


def test_muse_host_tool_suppression_and_clean_home(tmp_path: Path) -> None:
    sid = uuid7()
    with TurnWireSessionScope.bind(TurnMcpSessionSpec(emulate_tools=True, suppress_host_tools=True)):
        suppressed = cast(dict[str, Any], json.loads(build_session_start_msg(sid, "muse-ember-1.0", "denyUnmatched")))
    assert suppressed["params"]["approvalMode"] == "denyUnmatched" and suppressed["params"]["config"]["developerPrompt"] is None
    with TurnWireSessionScope.bind(TurnMcpSessionSpec(emulate_tools=True, suppress_host_tools=False)):
        baseline = cast(dict[str, Any], json.loads(build_session_start_msg(sid, "muse-ember-1.0", "denyUnmatched")))
    assert "config" not in baseline["params"] and baseline["params"]["approvalMode"] == "denyUnmatched"

    src_home = tmp_path / "src_home"
    (src_home / ".config" / "muse").mkdir(parents=True)
    _ = (src_home / "AGENTS.md").write_text("polluted", encoding="utf-8")
    _ = (src_home / ".config" / "muse" / "AGENTS.md").write_text("polluted", encoding="utf-8")
    _ = (src_home / ".config" / "muse" / "auth.json").write_text('{"token":"ok"}', encoding="utf-8")
    env_on = build_muse_env(None, "/fake/muse", turn_sandbox=str(tmp_path / "sb1"), server_env={"HOME": str(src_home), "BRIDGE_STDIO_CLEAN_CLI_HOME_ENABLED": "1"})
    clean_home = Path(env_on["HOME"])
    assert clean_home != src_home and stat.S_IMODE(clean_home.stat().st_mode) == 0o700
    assert not (clean_home / "AGENTS.md").exists() and not (clean_home / ".config" / "muse" / "AGENTS.md").exists()
    auth_dst = clean_home / ".config" / "muse" / "auth.json"
    assert auth_dst.is_file() and stat.S_IMODE(auth_dst.stat().st_mode) == 0o600
    env_off = build_muse_env(None, "/fake/muse", turn_sandbox=str(tmp_path / "sb2"), server_env={"HOME": str(src_home), "BRIDGE_STDIO_CLEAN_CLI_HOME_ENABLED": "0"})
    assert env_off["HOME"] == str(src_home)


def test_claude_and_codex_builtin_tool_suppression() -> None:
    claude = ClaudeStreamJsonDriver()
    argv_on = claude.build_argv(["claude"], {"suppress_builtin_tools": True})
    argv_off = claude.build_argv(["claude"], {"suppress_builtin_tools": False})
    idx_tools = argv_on.index("--tools")
    assert argv_on[idx_tools + 1] == "" and "--tools" not in argv_off
    assert claude.slot_profile_key({"suppress_builtin_tools": True}) != claude.slot_profile_key({"suppress_builtin_tools": False})

    st, _ = transition(ProtocolState(), ProtocolEvent(EventKind.START_INITIALIZE))
    st, _ = transition(st, ProtocolEvent(EventKind.SERVER_FRAME, {"jsonrpc": "2.0", "id": 1, "result": {"userAgent": "codex"}}))
    st, thr_eff = transition(st, ProtocolEvent(EventKind.START_THREAD, {"suppress_tools": True}))
    thr_params = cast(dict[str, Any], thr_eff[0].payload["params"])
    assert thr_params["sandbox"] == "read-only" and thr_params["approvalPolicy"] == "never" and st.suppress_tools is True
    st, _ = transition(st, ProtocolEvent(EventKind.SERVER_FRAME, {"jsonrpc": "2.0", "id": 2, "result": {"thread": {"id": "thr-1"}}}))
    st, turn_eff = transition(st, ProtocolEvent(EventKind.START_TURN, {"prompt": "hi"}))
    turn_params = cast(dict[str, Any], turn_eff[0].payload["params"])
    assert turn_params["approvalPolicy"] == "never" and turn_params["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    st_fail, err_eff = transition(st, ProtocolEvent(EventKind.SERVER_FRAME, {"jsonrpc": "2.0", "method": "item/tool/call", "params": {"threadId": "thr-1"}}))
    assert st_fail.phase is ProtocolPhase.FAILED and st_fail.error_code == "builtin_tool_event_forbidden"
    assert err_eff[0].kind is EffectKind.EMIT_ERROR and err_eff[0].payload["code"] == "builtin_tool_event_forbidden"

    zc_st, _ = transition(ProtocolState(phase=ProtocolPhase.TURN_ACTIVE, thread_id="thr-z", zero_canon=True, suppress_tools=True), ProtocolEvent(EventKind.SERVER_FRAME, {"jsonrpc": "2.0", "method": "item/tool/call", "params": {"threadId": "thr-z"}}))
    assert zc_st.phase is ProtocolPhase.FAILED and zc_st.error_code == "zero_canon_tool_event_forbidden"

"""Интеграционные и E2E-тесты длинных сессий agy-bridge и egress-границы хаба (W8, D1..D5)."""

from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_AGY_DIR = str(_ROOT / "bridges/agy-bridge")
if _AGY_DIR not in sys.path:
    sys.path.append(_AGY_DIR)

from core.continuity_anchor_policy import BRIDGE_CALL_ID_RE  # noqa: E402
from core.prompt_budget_policy import LazyPromptMaterializer, resolve_ctx_prompt  # noqa: E402
from core.runtime_env import allow_hub_client_response_header  # noqa: E402
from core.tool_turn_settle_policy import decide_session_commit  # noqa: E402


def _load_agy_server():
    cached = sys.modules.get("agy_srv_w8")
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location("agy_srv_w8", _ROOT / "bridges/agy-bridge/server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod.__name__] = mod
    spec.loader.exec_module(mod)
    return mod


def test_tool_turn_mints_bridge_id_and_suppresses_post_call_plan_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    srv = _load_agy_server()
    monkeypatch.setenv("AGY_TOOL_SETTLE_TIMEOUT_S", "0.05")
    monkeypatch.setenv("AGY_TOOL_SETTLE_EOF_GRACE_S", "0.05")
    emitted_text: list[str] = []
    emitted_calls: list[list[dict]] = []
    tools = [{"type": "function", "function": {"name": "read_chunk", "parameters": {"type": "object"}}}]
    tt = srv._ToolTurn(tools, lambda t: (emitted_text.append(t) or True), lambda _r: True, lambda c: (emitted_calls.append(c) or True))
    tt.feed('<tool_call>{"name":"read_chunk","arguments":{"chunk_id":1}}</tool_call>')
    assert len(tt.calls) == 1
    cid = str(tt.calls[0]["id"])
    assert BRIDGE_CALL_ID_RE.fullmatch(cid)
    assert emitted_calls[0][0]["id"] == cid
    ts_before = tt._last_chunk_ts
    # Пост-вызовный plan_leak подавляется и НЕ сбрасывает _last_chunk_ts!
    tt.feed("Now I will enter planning mode and edit implementation_plan.md")
    assert emitted_text == []
    assert tt._last_chunk_ts == ts_before
    # Идемпотентность id после finish()
    tt.finish()
    assert tt.calls[0]["id"] == cid


def test_resolve_chat_context_and_t1_to_t2_continuity_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    srv = _load_agy_server()
    monkeypatch.setenv("AGY_SESSION_CONTINUITY_ENABLED", "1")
    req_t1 = {
        "model": "gemini-4-neon-high",
        "tools": [{"type": "function", "function": {"name": "read_chunk", "parameters": {"type": "object"}}}],
        "messages": [{"role": "system", "content": "sys"}, {"role": "user", "content": "chunk 1"}],
    }
    chat_t1, inv1, scope1 = srv._resolve_chat_context({}, {}, req_t1)
    assert inv1 is False and chat_t1 and scope1
    # Совместимость 2-кортежной сигнатуры _request_chat_id
    c_compat, inv_compat = srv._request_chat_id({}, {}, req_t1)
    assert inv_compat is False and isinstance(c_compat, str)

    call_id = "call_" + "1a2b3c4d5e6f708192a3b4c5"
    assert srv._CONTINUITY.register_post_turn(req_t1["messages"], scope1, chat_t1, [call_id]) is True
    req_t2 = {
        **req_t1,
        "messages": [
            *req_t1["messages"],
            {"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {"name": "read_chunk", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": call_id, "content": "DATA_1"},
        ],
    }
    chat_t2, inv2, scope2 = srv._resolve_chat_context({}, {}, req_t2)
    assert inv2 is False and scope2 == scope1 and chat_t2 == chat_t1


def test_usage_payload_omits_missing_and_preserves_valid() -> None:
    srv = _load_agy_server()
    empty_snap = srv._EMPTY_USAGE_SNAPSHOT
    res_miss = srv._resolve_step_usage({"rc": 0, "state": "done", "usage": {}}, empty_snap, 100000, True)
    assert res_miss["reason"] == "missing_usage"
    assert res_miss["emit_wire_usage"] is False
    assert srv.Handler._usage_payload({}, res_miss) == {}

    res_ok = srv._resolve_step_usage(
        {"rc": 0, "state": "done", "usage": {"input_tokens": 500, "output_tokens": 40, "cache_read_tokens": 200}},
        empty_snap,
        100000,
        False,
    )
    assert res_ok["emit_wire_usage"] is True
    pay = srv.Handler._usage_payload({}, res_ok)
    assert pay["prompt_tokens"] == 700 and pay["prompt_tokens_details"] == {"cached_tokens": 200}


def test_handler_send_clears_pending_headers_and_respects_2arg_compat() -> None:
    srv = _load_agy_server()
    h = srv.Handler.__new__(srv.Handler)
    h._registry_job = None
    h.wfile = io.BytesIO()
    sent: list[tuple[str, str]] = []
    h.send_response = lambda _c: None
    h.send_header = lambda k, v: sent.append((k, v))
    h.end_headers = lambda: None
    h._pending_response_headers = {"X-Agy-Conversation-Id": "12345678-aaaa"}
    h._send(200, {"ok": True})
    assert ("X-Agy-Conversation-Id", "12345678-aaaa") in sent
    assert h._pending_response_headers is None
    # Повторный запрос на keep-alive соединении НЕ утекает заголовок!
    sent.clear()
    h._send(200, {"ok": True})
    assert all(k != "X-Agy-Conversation-Id" for k, _ in sent)


def test_lazy_prompt_direct_mode_and_hub_egress_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    srv = _load_agy_server()
    # AGY_BRIDGE_DIRECT_MODE=inherit сохраняет AGY_DIRECT=0
    monkeypatch.setenv("AGY_DIRECT", "0")
    monkeypatch.delenv("AGY_BRIDGE_DIRECT_MODE", raising=False)
    env = srv._launch_env()
    assert isinstance(env, dict) and env.get("AGY_DIRECT") == "0"

    # LazyPromptMaterializer через resolve_ctx_prompt
    built = [0]
    ctx: dict[str, object] = {"full_prompt": LazyPromptMaterializer(lambda: (built.__setitem__(0, built[0] + 1) or "FULL"))}
    assert built[0] == 0
    assert resolve_ctx_prompt(ctx, "full_prompt") == "FULL" and built[0] == 1

    # Защита hub egress THREAT-001 (loopback vs non-loopback)
    peers = ("127.0.0.1", "::1")
    blocked = frozenset(("connection",))
    assert allow_hub_client_response_header("X-Agy-Conversation-Id", blocked, SimpleNamespace(client_address=("127.0.0.1", 1)), peers) is True
    assert allow_hub_client_response_header("X-Agy-Conversation-Id", blocked, SimpleNamespace(client_address=("192.168.1.5", 1)), peers) is False
    assert decide_session_commit(state="done", rc=0, tool_turn_stop=True, conversation_id="12345678", cid_valid=True) == "invalidate"

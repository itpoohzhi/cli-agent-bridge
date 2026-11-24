"""Fast integration coverage for DSH hot resume, tools and SQLite cleanup."""

from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
import sys
import threading
from email.message import Message
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT, ROOT / "tests", ROOT / "bridges" / "agy-bridge"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

CID = "82188e72-6eca-4f23-a0b3-2257ec43bd60"
SERVER_NAME = "agy_bridge_server_dsh_resume_e2e"


def _load_server() -> ModuleType:
    cached = sys.modules.get(SERVER_NAME)
    if cached is not None:
        return cached
    path = ROOT / "bridges" / "agy-bridge" / "server.py"
    spec = importlib.util.spec_from_file_location(SERVER_NAME, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[SERVER_NAME] = module
    spec.loader.exec_module(module)
    return module


def _tool(index: int) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": f"tool_{index}",
            "description": "deterministic schema " + "d" * 600,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "q" * 180},
                    "limit": {"type": "integer", "minimum": 1},
                },
                "required": ["query"],
            },
        },
    }


def _tools() -> list[dict[str, object]]:
    return [_tool(index) for index in range(30)]


def _create_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE steps (idx integer PRIMARY KEY, step_type integer, "
            "status integer, step_payload blob)"
        )
    assert not Path(f"{path}-wal").exists()


class _Harness:
    def __init__(self, server: ModuleType, db_path: Path) -> None:
        self.server = server
        self.db_path = db_path
        self.contexts: list[dict[str, Any]] = []
        self.logs: list[str] = []
        self.pool_states: list[tuple[int, int]] = []
        self.sent: list[tuple[int, dict[str, object]]] = []
        self.pool = server._sqlite_ro_pool()
        assert self.pool is not None

    def serve(self, ctx: dict[str, Any]) -> None:
        srv = self.server
        cid = str(ctx.get("conversation_id") or CID)
        plan = srv._TurnPlan()
        plan.mode, plan.anchored = "LIVE", True
        tail = srv._TranscriptTail(
            lambda _i, _t, done=None: (done() if done else None) is None,
            threading.Event(),
            threading.Event(),
            bool(ctx["hot_resumed"]),
            plan=plan,
            turn_id=str(ctx["turn_id"]),
        )
        tail.bind(cid)
        assert tail._poll_sqlite() == (0, 0)
        pool = srv._sqlite_ro_pool()
        before = int(pool.snapshot_metrics()["active_conns"])
        tail._finish()
        after = int(pool.snapshot_metrics()["active_conns"])
        assert cid not in srv._active_cid_owners
        self.pool_states.append((before, after))
        srv._session_commit(ctx["sess_key"], cid, str(ctx["tools_fp"]))
        self.contexts.append({**ctx, "result_cid": cid, "sqlite_active": tail.sqlite_active})

    def post(
        self,
        tools: list[dict[str, object]],
        step: int,
        *,
        effort: str = "high",
        subagent: str = "",
    ) -> dict[str, Any]:
        messages: list[dict[str, object]] = [{"role": "system", "content": "stable " + "s" * 800}]
        if step > 1:
            messages.append({"role": "assistant", "content": f"completed {step - 1}"})
        messages.append({"role": "user", "content": f"execute step {step}"})
        body = json.dumps({"model": self.server.MODEL_ID, "reasoning_effort": effort,
                           "messages": messages, "tools": tools}).encode()
        headers = Message()
        headers["Content-Length"] = str(len(body))
        headers["X-Dsh-Chat-Id"] = "dsh-agentic-e2e"
        if subagent:
            headers["X-Subagent-Id"] = subagent
        handler = self.server.Handler.__new__(self.server.Handler)
        handler.path, handler.headers = "/v1/chat/completions", headers
        handler.rfile, handler.client_address = io.BytesIO(body), ("127.0.0.1", 7777)
        handler.close_connection = False
        handler._send = lambda code, payload, **_kw: self.sent.append((code, payload))
        before = len(self.contexts)
        handler.do_POST()
        assert len(self.contexts) == before + 1, self.sent
        return self.contexts[-1]


@pytest.fixture
def e2e(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _Harness:
    srv = _load_server()
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(json.dumps({"SQLITE_REASONING_ENABLED": True,
                               "agy_sqlite_ro_hygiene_enabled": True,
                               "resumed_compact_tools_enabled": True,
                               "AGY_ZERO_CANON_ENABLED": True}))
    db_path = tmp_path / "conversation.db"
    _create_db(db_path)
    srv._reset_sqlite_guards_for_tests()
    srv._session_store.clear()
    srv._in_flight_cids.clear()
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    monkeypatch.setattr(srv, "_sqlite_ro_pool_cached", None)
    monkeypatch.setattr(srv, "_persist_sessions", lambda: None)
    monkeypatch.setattr(srv, "_budget", None)
    monkeypatch.setattr(srv, "_auth_ok", lambda _handler: True)
    monkeypatch.setattr(srv, "_launcher", lambda: object())
    monkeypatch.setattr(srv, "_is_image_fallback_enabled", lambda: False)
    monkeypatch.setattr(srv, "_db_path_for", lambda _cid: db_path)
    monkeypatch.setenv("AGY_SQLITE_RO_POOL_ENABLED", "true")
    monkeypatch.setenv("AGY_SQLITE_REASONING_ENABLED", "1")
    monkeypatch.setenv("AGY_ZERO_CANON_ENABLED", "true")
    monkeypatch.delenv("AGY_SQLITE_RO_HYGIENE_ENABLED", raising=False)
    monkeypatch.delenv("AGY_BRIDGE_RESUMED_COMPACT_TOOLS_ENABLED", raising=False)
    harness = _Harness(srv, db_path)
    monkeypatch.setattr(srv, "_log", harness.logs.append)
    monkeypatch.setattr(srv.Handler, "_serve_json", lambda _handler, ctx: harness.serve(ctx))
    yield harness
    harness.pool.close_all()
    srv._session_store.clear()
    srv._in_flight_cids.clear()
    srv._active_cid_owners.clear()


def test_five_step_dsh_resume_keeps_sqlite_live_and_compacts_tools(e2e: _Harness) -> None:
    tools = _tools()
    turns = [e2e.post(tools, step) for step in range(1, 6)]
    first, resumed = turns[0], turns[1:]
    assert first["tools_count"] == 30 and first["hot_resumed"] is False
    assert first["conversation_id"] == "" and first["result_cid"] == CID
    assert all(turn["hot_resumed"] is True for turn in resumed)
    assert {turn["conversation_id"] for turn in resumed} == {CID}
    assert len(str(resumed[0]["prompt"])) < len(str(first["prompt"])) // 4
    assert "  parameters:" in str(first["prompt"])
    assert "  parameters:" not in str(resumed[0]["prompt"])
    assert all(turn["sqlite_active"] is True for turn in turns)
    assert e2e.pool_states == [(1, 0)] * 5
    assert not [line for line in e2e.logs if line.startswith("sqlite-off")]
    assert e2e.server._active_cid_owners == {}
    entry = e2e.server._session_store[first["sess_key"]]
    assert entry["turns"] == 5 and entry["tools_fp"] == turns[-1]["tools_fp"]
    assert len(str(entry["tools_fp"])) == 64
    assert e2e.server._sqlite_ro_pool().health_tuple()[0] is True


@pytest.mark.parametrize("change", ["schema", "flag"])
def test_hot_resume_sends_full_schemas_on_change_or_disabled(
    e2e: _Harness, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    tools = _tools()
    first = e2e.post(tools, 1)
    next_tools = json.loads(json.dumps(tools))
    if change == "schema":
        next_tools[0]["function"]["parameters"]["properties"]["query"]["maxLength"] = 99
    else:
        monkeypatch.setenv("AGY_BRIDGE_RESUMED_COMPACT_TOOLS_ENABLED", "false")
    second = e2e.post(next_tools, 2)
    assert second["hot_resumed"] is True and second["conversation_id"] == CID
    assert "  parameters:" in str(second["prompt"])
    assert len(str(second["prompt"])) > 20_000
    if change == "schema":
        assert second["tools_fp"] != first["tools_fp"]
    else:
        assert second["tools_fp"] == first["tools_fp"]


def test_effort_subagent_and_zero_canon_do_not_reuse_cid(e2e: _Harness) -> None:
    srv = e2e.server
    req = {"model": srv.MODEL_ID, "tools": _tools(), "messages": []}
    headers = {"X-Dsh-Chat-Id": "dsh-agentic-e2e"}
    base_chat, invalid, _ = srv._resolve_chat_context(headers, {}, req)
    assert not invalid
    base = srv._session_key_for(srv.MODEL_ID, "", "high", base_chat)
    srv._session_commit(base, CID, "a" * 64)
    sub_chat, invalid, _ = srv._resolve_chat_context(
        {**headers, "X-Subagent-Id": "coder-2"}, {}, req
    )
    zc_plan = srv.zero_canon_profile.resolve_turn_plan(
        {**headers, "X-Review-Profile": "Zero-Canon"}, srv.DYNAMIC_CONFIG_PATH
    )
    zc_chat, invalid_zc, _ = srv._resolve_chat_context(
        headers, {}, req, review_profile=zc_plan.profile_tag
    )
    alternatives = (
        srv._session_key_for(srv.MODEL_ID, "", "medium", base_chat),
        srv._session_key_for(srv.MODEL_ID, "", "high", sub_chat),
        srv._session_key_for(srv.MODEL_ID, "", "high", zc_chat,
                             review_profile=zc_plan.profile_tag),
    )
    assert not invalid and not invalid_zc and zc_plan.enabled
    assert all(key != base for key in alternatives)
    assert all(srv._session_claim(key, "adversary") == "" for key in alternatives)
    assert srv._session_claim(base, "owner") == CID


def test_finish_release_failure_still_releases_cid(
    e2e: _Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    srv = e2e.server
    plan = srv._TurnPlan()
    plan.mode = "LIVE"
    tail = srv._TranscriptTail(
        lambda _i, _t, _done=None: True,
        threading.Event(),
        threading.Event(),
        False,
        plan=plan,
        turn_id="finish-failure",
    )
    assert srv._cid_acquire(CID, tail.turn_id)
    tail._owned_cid = CID
    releases: list[tuple[str, str]] = []
    real_release = srv._cid_release

    def release_spy(cid: str, turn: str) -> None:
        releases.append((cid, turn))
        real_release(cid, turn)

    monkeypatch.setattr(srv, "_cid_release", release_spy)

    class _BrokenPool:
        def release_thread(self) -> None:
            raise RuntimeError("release failed")

    monkeypatch.setattr(srv, "_sqlite_ro_pool", lambda: _BrokenPool())
    tail._finish()
    assert tail._finished is True
    assert releases == [(CID, "finish-failure")]
    assert CID not in srv._active_cid_owners

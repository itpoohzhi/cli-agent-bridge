"""L2-интеграционные тесты Explicit Resume, безопасности и изоляции DSH (Wave 3)."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from email.message import Message
import importlib, importlib.util, io, json, os, re, stat, sys, threading  # noqa: E401
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Protocol, cast, final

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "bridges" / "agy-bridge"
for _p in (ROOT, BRIDGE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from core.hot_session_policy import DecisionReason, SlotSnapshot, SlotState  # noqa: E402
from core.prompt_rendering import render_tools_section  # noqa: E402


class _StoreStats(Protocol):
    persist_failures: int


class _StoreProto(Protocol):
    def peek(self, key: str, now_s: float) -> tuple[SlotSnapshot, int]: ...
    def stats(self) -> _StoreStats: ...
    def flush_now(self, timeout_s: float = ...) -> bool: ...


class _StateProto(Protocol):
    handled: bool
    sort_keys: bool
    is_resumed: bool
    conversation_id: str
    allow_commit: bool
    decision_reason: str
    session_key: str
    owner_token_hash: str
    lease_token: str
    supersede: bool
    projected_input: tuple[object, ...]


class _AdapterProto(Protocol):
    def prepare_turn(self, http_meta: object, payload_meta: object, now_s: float | None = ...) -> _StateProto: ...
    def on_hot_failure(self, state: _StateProto, *, post_spawn: bool = ...) -> None: ...
    def finalize_turn(self, state: _StateProto, out: Mapping[str, object], commit_act: str, cid_re: re.Pattern[str]) -> bool: ...
    def release_if_unfinalized(self, state: _StateProto, *, post_spawn: bool = ...) -> None: ...
    def close(self) -> None: ...


class _RouteProto(Protocol):
    location_marker: str


_SRA = importlib.import_module("agy_runtime.session_resume_adapter")
_AdapterCtor = cast("Callable[[Path, Path | None], _AdapterProto]", getattr(_SRA, "ExplicitResumeAdapter"))
_HttpMetaCtor = cast("Callable[..., object]", getattr(_SRA, "TurnHttpMeta"))
_PayloadMetaCtor = cast("Callable[..., object]", getattr(_SRA, "TurnPayloadMeta"))
_classify_route = cast("Callable[..., _RouteProto]", getattr(_SRA, "classify_route"))
_read_flags = cast("Callable[[Path | None], object]", getattr(_SRA, "read_runtime_flags"))
_reset_adapters = cast("Callable[[], None]", getattr(_SRA, "reset_explicit_adapters_for_tests"))

_SERVER_MOD_NAME = "agy_bridge_server_explicit_resume_l2"
_CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
_TOK_A, _TOK_B = "tok-owner-AAAA-1111", "tok-owner-BBBB-2222"
_CID_1, _CID_2 = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
_CID_3, _CID_FOREIGN = "33333333-3333-4333-8333-333333333333", "99999999-9999-4999-8999-999999999999"
_UNSORTED_TOOLS: list[dict[str, object]] = [
    {"type": "function", "function": {"name": "z_tool", "description": "last", "parameters": {"type": "object", "properties": {"z": {"type": "string"}, "a": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "a_tool", "description": "first", "parameters": {"type": "object", "properties": {"b": {"type": "boolean"}, "a": {"type": "string"}}}}},
]


def _store_of(adapter: _AdapterProto) -> _StoreProto | None:
    return cast("_StoreProto | None", getattr(adapter, "_store"))


def _req_store(adapter: _AdapterProto) -> _StoreProto:
    st = _store_of(adapter)
    assert st is not None
    return st


def _load_server() -> ModuleType:
    if (cached := sys.modules.get(_SERVER_MOD_NAME)) is not None:
        return cached
    spec = importlib.util.spec_from_file_location(_SERVER_MOD_NAME, BRIDGE_DIR / "server.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_SERVER_MOD_NAME] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _isolate_explicit_state(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _reset_adapters()
    for key in [k for k in os.environ if k.startswith("BRIDGE_HOT_")] + ["AGY_ZERO_CANON_ENABLED", "AGY_BRIDGE_RESUMED_COMPACT_TOOLS_ENABLED", "AGY_BRIDGE_SESSION_ISOLATION_ENABLED"]:
        monkeypatch.delenv(key, raising=False)
    yield
    _reset_adapters()


def _prep(
    adapter: _AdapterProto, messages: Sequence[object], *, profile: str = "standard",
    chat_id: str | None = "chat-1", token: str | None = _TOK_A, client_host: str = "127.0.0.1",
    tools: Sequence[object] = (), cwd: str = "/tmp/work", raw_cid: object = None, req_extra: Mapping[str, object] | None = None,
) -> _StateProto:
    hdrs: dict[str, str] = {}
    if chat_id is not None:
        hdrs["X-DSH-Chat-Id"] = chat_id
    if token is not None:
        hdrs["Authorization"] = f"Bearer {token}" if token else ""
    req: dict[str, object] = {"model": "gemini-3.8-flash", "messages": list(messages), **(req_extra or {})}
    return adapter.prepare_turn(_HttpMetaCtor(hdrs, client_host, profile, raw_cid), _PayloadMetaCtor(req, {}, "gemini-3.8-flash", "high", cwd, False, list(tools), None, False))


def _commit(adapter: _AdapterProto, state: _StateProto, cid: str, text: str = "a1", *, tool_calls: list[dict[str, object]] | None = None) -> bool:
    out: dict[str, object] = {"conversation_id": cid, "text": text, **({"tool_calls": tool_calls} if tool_calls is not None else {})}
    ok = adapter.finalize_turn(state, out, "commit", _CID_RE)
    if (st := _store_of(adapter)) is not None:
        assert st.flush_now(timeout_s=2.0) is True
    return ok


def _empty_cfg(tmp_path: Path) -> Path:
    cfg = tmp_path / "dynamic_config.json"
    _ = cfg.write_text("{}", encoding="utf-8")
    return cfg


def test_route_matrix_2x2x2_and_dsh_legacy_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg, legacy_dir = _empty_cfg(tmp_path), tmp_path / "legacy_state"
    legacy_ad = _AdapterCtor(legacy_dir, cfg)
    try:
        assert _prep(legacy_ad, [{"role": "user", "content": "hi"}], chat_id="c-off").handled is False and _store_of(legacy_ad) is None
        for env in ("BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED", "BRIDGE_HOT_ZC_PLAIN_ENABLED", "BRIDGE_HOT_ZC_AGENTIC_ENABLED", "BRIDGE_HOT_CANONICAL_TOOLS_ENABLED"):
            monkeypatch.setenv(env, "1")
        for cid_hdr in ("dsh-chat", None):
            st_dsh = _prep(legacy_ad, [{"role": "user", "content": "run"}], chat_id=cid_hdr, tools=_UNSORTED_TOOLS)
            assert st_dsh.handled is False and st_dsh.sort_keys is False
        assert _store_of(legacy_ad) is None and not (legacy_dir / "sessions_explicit.json").exists() and not (legacy_dir / ".owner_hmac_key").exists()
        legacy_tools, canon_tools = render_tools_section(_UNSORTED_TOOLS, sort_keys=False), render_tools_section(_UNSORTED_TOOLS, sort_keys=True)
        assert legacy_tools.index("- z_tool:") < legacy_tools.index("- a_tool:") and legacy_tools.index('"z":') < legacy_tools.index('"a":')
        assert canon_tools.index("- a_tool:") < canon_tools.index("- z_tool:") and canon_tools != legacy_tools
        for prof, tlist in (("standard", ()), ("zero-canon", ()), ("zero-canon", _UNSORTED_TOOLS)):
            assert _prep(legacy_ad, [{"role": "user", "content": "hi"}], profile=prof, chat_id=None, tools=tlist).handled is False
    finally:
        legacy_ad.close()

    ad = _AdapterCtor(tmp_path / "hot_state", cfg)
    try:
        m1 = [{"role": "user", "content": "u1"}]
        s1 = _prep(ad, m1, profile="standard", chat_id="std-plain")
        assert s1.handled is True and s1.is_resumed is False and s1.allow_commit is True
        assert _commit(ad, s1, _CID_1, "a1") and _req_store(ad).peek(s1.session_key, 0.0)[0].state == SlotState.READY
        s2 = _prep(ad, [*m1, {"role": "assistant", "content": "a1"}, {"role": "user", "content": "u2"}], chat_id="std-plain")
        assert s2.is_resumed is True and s2.conversation_id == _CID_1 and s2.decision_reason == DecisionReason.APPEND_ONLY_MATCH.value and _commit(ad, s2, _CID_1, "a2")
        assert _classify_route("zero-canon", 0, "zc-p", "/tmp/turn-aaa", _read_flags(cfg)).location_marker == "zero-canon-ephemeral"
        zc1 = _prep(ad, m1, profile="zero-canon", chat_id="zc-p", cwd="/tmp/turn-aaa")
        assert zc1.handled is True and zc1.is_resumed is False and _commit(ad, zc1, _CID_2, "za1")
        zc2 = _prep(ad, [*m1, {"role": "assistant", "content": "za1"}, {"role": "user", "content": "u2"}], profile="zero-canon", chat_id="zc-p", cwd="/tmp/turn-bbb")
        assert zc2.is_resumed is True and zc2.conversation_id == _CID_2 and zc2.session_key == zc1.session_key and _commit(ad, zc2, _CID_2, "za2")
        tc_emit = [{"id": "call_1", "type": "function", "function": {"name": "z_tool", "arguments": '{"z":"v","a":1}'}}]
        tc_back = [{"id": "call_1", "type": "function", "function": {"name": "z_tool", "arguments": '{"a": 1, "z": "v"}'}}]
        za1 = _prep(ad, m1, profile="zero-canon", chat_id="zc-a", tools=_UNSORTED_TOOLS, cwd="/tmp/turn-1")
        assert za1.handled is True and za1.sort_keys is True and _commit(ad, za1, _CID_3, "", tool_calls=tc_emit)
        m2_ag = [*m1, {"role": "assistant", "content": "", "tool_calls": tc_back}, {"role": "tool", "tool_call_id": "call_1", "content": "ok"}, {"role": "user", "content": "next"}]
        za2 = _prep(ad, m2_ag, profile="zero-canon", chat_id="zc-a", tools=_UNSORTED_TOOLS, cwd="/tmp/turn-2")
        assert za2.is_resumed is True and za2.conversation_id == _CID_3 and za2.sort_keys is True and _commit(ad, za2, _CID_3, "done")
    finally:
        ad.close()


def test_security_threats_zero_cross_owner_and_forgery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED", "1")
    ad = _AdapterCtor(tmp_path / "sec_state", _empty_cfg(tmp_path))
    try:
        u1 = [{"role": "user", "content": "secret"}]
        u1_a1_u2 = [*u1, {"role": "assistant", "content": "ans1"}, {"role": "user", "content": "follow"}]
        sa1 = _prep(ad, u1, chat_id="shared", token=_TOK_A)
        assert _commit(ad, sa1, _CID_1, "ans1")
        sb = _prep(ad, u1_a1_u2, chat_id="shared", token=_TOK_B)
        assert sb.handled is True and sb.is_resumed is False and sb.conversation_id == "" and sb.session_key != sa1.session_key and sb.owner_token_hash != sa1.owner_token_hash
        sb_forged = _prep(ad, u1_a1_u2, chat_id="shared", token=_TOK_B, raw_cid=_CID_1)
        assert sb_forged.decision_reason == DecisionReason.UNOWNED_EXPLICIT_CID.value and sb_forged.allow_commit is False and sb_forged.is_resumed is False
        sa_forged = _prep(ad, u1_a1_u2, chat_id="shared", token=_TOK_A, raw_cid=_CID_FOREIGN)
        assert sa_forged.decision_reason == DecisionReason.UNOWNED_EXPLICIT_CID.value and sa_forged.allow_commit is False and _req_store(ad).peek(sa1.session_key, 0.0)[0].state == SlotState.READY
        for host, tok in (("10.0.0.5", _TOK_A), ("127.0.0.1", "short"), ("127.0.0.1", None)):
            st_bad = _prep(ad, u1_a1_u2, chat_id="shared", token=tok, client_host=host)
            assert st_bad.decision_reason == DecisionReason.MISSING_OWNER_TOKEN.value and st_bad.allow_commit is False
        st_bg = _prep(ad, [{"role": "user", "content": "Generate title"}], chat_id="shared", token=_TOK_A)
        assert st_bg.decision_reason == DecisionReason.NO_ASSISTANT_HISTORY.value and st_bg.allow_commit is False
        assert ad.finalize_turn(st_bg, {"conversation_id": _CID_2, "text": "Title"}, "commit", _CID_RE) is False
        sa2 = _prep(ad, u1_a1_u2, chat_id="shared", token=_TOK_A)
        assert sa2.is_resumed is True and sa2.conversation_id == _CID_1 and _commit(ad, sa2, _CID_1, "ans2")
        assert _commit(ad, _prep(ad, u1, chat_id="tamper", token=_TOK_A), _CID_1, "orig")
        prev_cid = _CID_1
        for i in range(3):
            sup = _prep(ad, [*u1, {"role": "assistant", "content": f"EDITED-{i}"}, {"role": "user", "content": f"q{i}"}], chat_id="tamper", token=_TOK_A)
            assert sup.decision_reason == DecisionReason.HISTORY_DIVERGED_SUPERSEDE.value and sup.is_resumed is False and sup.supersede is True and sup.allow_commit is True
            new_cid = f"aaaa000{i}-1111-4111-8111-111111111111"
            assert new_cid != prev_cid and _commit(ad, sup, new_cid, f"resp-{i}")
            prev_cid = new_cid
        rl = _prep(ad, [*u1, {"role": "assistant", "content": "EDITED-4"}, {"role": "user", "content": "q4"}], chat_id="tamper", token=_TOK_A)
        assert rl.decision_reason == DecisionReason.HISTORY_DIVERGED_RATE_LIMITED.value and rl.allow_commit is False
        assert _prep(ad, u1, chat_id=None, token=_TOK_A, req_extra={"prompt_cache_key": "k1"}).handled is False
    finally:
        ad.close()


def test_context_digest_isolation_and_guard_max_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_HOT_ZC_AGENTIC_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_HOT_CANONICAL_TOOLS_ENABLED", "0")
    ad = _AdapterCtor(tmp_path / "ctx_state", _empty_cfg(tmp_path))
    try:
        m_v1, t_v1 = [{"role": "system", "content": "sys-v1"}, {"role": "user", "content": "u1"}], [_UNSORTED_TOOLS[0]]
        s0 = _prep(ad, m_v1, profile="zero-canon", chat_id="ctx-chat", tools=t_v1)
        assert _commit(ad, s0, _CID_1, "a1")
        s_sys = _prep(ad, [{"role": "system", "content": "sys-v2"}, {"role": "user", "content": "u1"}], profile="zero-canon", chat_id="ctx-chat", tools=t_v1)
        s_tools = _prep(ad, m_v1, profile="zero-canon", chat_id="ctx-chat", tools=_UNSORTED_TOOLS)
        monkeypatch.setenv("BRIDGE_HOT_CANONICAL_TOOLS_ENABLED", "1")
        s_sort = _prep(ad, m_v1, profile="zero-canon", chat_id="ctx-chat", tools=t_v1)
        for st in (s_sys, s_tools, s_sort):
            assert st.session_key != s0.session_key and st.is_resumed is False and st.decision_reason == DecisionReason.SLOT_EMPTY.value
        monkeypatch.setenv("BRIDGE_HOT_CANONICAL_TOOLS_ENABLED", "0")
        s_back = _prep(ad, [*m_v1, {"role": "assistant", "content": "a1"}, {"role": "user", "content": "u2"}], profile="zero-canon", chat_id="ctx-chat", tools=t_v1)
        assert s_back.session_key == s0.session_key and s_back.is_resumed is True and s_back.conversation_id == _CID_1 and _commit(ad, s_back, _CID_1, "a2")
        monkeypatch.setenv("BRIDGE_HOT_GUARD_MAX_BYTES", "1024")
        proj_calls, real_proj = [0], cast("Callable[[Sequence[object]], list[object]]", getattr(_SRA, "project_messages"))

        def _spy_proj(msgs: Sequence[object]) -> list[object]:
            proj_calls[0] += 1
            return real_proj(msgs)

        monkeypatch.setattr(_SRA, "project_messages", _spy_proj)
        huge_msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok", "reasoning_content": "R" * 2048}]
        s_big = _prep(ad, huge_msgs, profile="zero-canon", chat_id="ctx-chat", tools=t_v1)
        assert s_big.decision_reason == DecisionReason.GUARD_BOUND_BYTES.value and s_big.allow_commit is False and s_big.projected_input == () and proj_calls[0] == 0
    finally:
        ad.close()


def test_concurrency_aborts_fault_injection_and_kill_switch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED", "1")
    cfg, ad = _empty_cfg(tmp_path), _AdapterCtor(tmp_path / "fsm_state", _empty_cfg(tmp_path))
    try:
        m1 = [{"role": "user", "content": "u1"}]
        assert _commit(ad, _prep(ad, m1, chat_id="conc"), _CID_1, "a1")
        m2 = [*m1, {"role": "assistant", "content": "a1"}, {"role": "user", "content": "u2"}]
        r1, r2 = _prep(ad, m2, chat_id="conc"), _prep(ad, m2, chat_id="conc")
        assert r1.is_resumed is True and r1.lease_token and r2.decision_reason == DecisionReason.SLOT_IN_FLIGHT.value and r2.allow_commit is False
        assert _commit(ad, r1, _CID_1, "a2") and _req_store(ad).peek(r1.session_key, 0.0)[0].turns == 2
        entered, release, real_fsync = threading.Event(), threading.Event(), os.fsync

        def _gated_fsync(fd: int) -> None:
            if not stat.S_ISDIR(os.fstat(fd).st_mode) and not entered.is_set():
                entered.set()
                assert release.wait(timeout=3.0)
            real_fsync(fd)

        m3 = [*m2, {"role": "assistant", "content": "a2"}, {"role": "user", "content": "u3"}]
        monkeypatch.setattr(os, "fsync", _gated_fsync)
        try:
            u1 = _prep(ad, m3, chat_id="conc")
            assert u1.is_resumed is True and ad.finalize_turn(u1, {"conversation_id": _CID_1, "text": "a3"}, "commit", _CID_RE) and entered.wait(timeout=3.0)
            u2 = _prep(ad, m3, chat_id="conc")
            assert u2.decision_reason == DecisionReason.SLOT_UNCONFIRMED.value and u2.allow_commit is False
        finally:
            release.set()
            monkeypatch.setattr(os, "fsync", real_fsync)
        assert _req_store(ad).flush_now(timeout_s=2.0) and _req_store(ad).peek(u1.session_key, 0.0)[0].state == SlotState.READY
        m4 = [*m3, {"role": "assistant", "content": "a3"}, {"role": "user", "content": "u4"}]
        pre = _prep(ad, m4, chat_id="conc")
        ad.release_if_unfinalized(pre, post_spawn=False)
        assert pre.is_resumed is True and _req_store(ad).peek(pre.session_key, 0.0)[0].state == SlotState.READY
        hot = _prep(ad, m4, chat_id="conc")
        ad.on_hot_failure(hot, post_spawn=True)
        assert _req_store(ad).peek(hot.session_key, 0.0)[0].state == SlotState.EMPTY and hot.is_resumed is False and hot.conversation_id == "" and hot.allow_commit is True
        assert _commit(ad, hot, _CID_2, "a4")
        m5 = [*m4, {"role": "assistant", "content": "a4"}, {"role": "user", "content": "u5"}]
        after_fb = _prep(ad, m5, chat_id="conc")
        assert after_fb.is_resumed is True and after_fb.conversation_id == _CID_2 and _commit(ad, after_fb, _CID_2, "a5")
        m6 = [*m5, {"role": "assistant", "content": "a5"}, {"role": "user", "content": "u6"}]
        monkeypatch.setenv("BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED", "0")
        assert _prep(ad, m6, chat_id="conc").handled is False
        monkeypatch.setenv("BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED", "1")
        st_tog = _prep(ad, m6, chat_id="conc")
        assert st_tog.is_resumed is False and st_tog.decision_reason == DecisionReason.SLOT_EMPTY.value and _commit(ad, st_tog, _CID_3, "a6")
        monkeypatch.setenv("BRIDGE_HOT_EPOCH", "1")
        st_ep = _prep(ad, [*m6, {"role": "assistant", "content": "a6"}, {"role": "user", "content": "u7"}], chat_id="conc")
        assert st_ep.is_resumed is False and st_ep.decision_reason == DecisionReason.SLOT_EMPTY.value
    finally:
        ad.close()

    ro_dir, ro_ad = tmp_path / "ro_state", _AdapterCtor(tmp_path / "ro_state", cfg)
    try:
        st_init = _prep(ro_ad, [{"role": "user", "content": "init"}], chat_id="ro-c")
        ro_store = _req_store(ro_ad)
        ro_dir.chmod(0o500)
        assert ro_ad.finalize_turn(st_init, {"conversation_id": _CID_1, "text": "a1"}, "commit", _CID_RE) is True
        assert ro_store.flush_now(timeout_s=2.0) and ro_store.peek(st_init.session_key, 0.0)[0].state == SlotState.EMPTY and ro_store.stats().persist_failures >= 1
    finally:
        ro_dir.chmod(0o700)
        ro_ad.close()


def _noop(*_a: object, **_k: object) -> None:
    return None


def _const(val: object) -> Callable[..., object]:
    def _fn(*_a: object, **_k: object) -> object:
        return val
    return _fn


@final
class _ServerHarness:
    def __init__(self, srv: ModuleType, workspace: Path, cids: list[str]) -> None:
        self.srv, self.workspace, self.cids = srv, workspace, list(cids)
        self.runs: list[dict[str, object]] = []
        self.responses: list[tuple[int, dict[str, object]]] = []

    def make_run(self, prompt: str, model: str, effort: str, _es: str, cwd: str, _tag: str, **kw: object) -> SimpleNamespace:
        rec: dict[str, object] = {"prompt": prompt, "model": model, "effort": effort, "cwd": cwd, "cwd_existed": Path(cwd).is_dir() if cwd else False, "conversation_id": str(kw.get("conversation_id") or ""), "zero_canon": bool(kw.get("zero_canon"))}
        self.runs.append(rec)
        return SimpleNamespace(proc=SimpleNamespace(pid=0), rec=rec, close=_noop)

    def execute(self, run: SimpleNamespace, on_text: object, *_a: object, **_k: object) -> dict[str, object]:
        rec = cast("dict[str, object]", run.rec)
        cid, reply = str(rec["conversation_id"]) or self.cids.pop(0), f"reply-{len(self.runs)}"
        if callable(on_text):
            _ = on_text(reply)
        return {"state": "done", "rc": 0, "text": reply, "conversation_id": cid, "usage": {}, "response_started": True}

    def post(self, messages: list[dict[str, object]], *, chat_id: str = "srv-chat", tools: list[dict[str, object]] | None = None, review_profile: str | None = None) -> tuple[int, dict[str, object], dict[str, object]]:
        body = json.dumps({"model": cast("str", getattr(self.srv, "MODEL_ID")), "messages": messages, **({"tools": tools} if tools is not None else {})}).encode("utf-8")
        headers = Message()
        headers["Content-Length"], headers["Authorization"], headers["X-DSH-Chat-Id"] = str(len(body)), f"Bearer {_TOK_A}", chat_id
        if review_profile is not None:
            headers["X-Review-Profile"] = review_profile
        handler_cls = cast("type[object]", getattr(self.srv, "Handler"))
        handler = cast("Callable[[type[object]], object]", getattr(handler_cls, "__new__"))(handler_cls)
        for k, v in (("path", "/v1/chat/completions"), ("headers", headers), ("rfile", io.BytesIO(body)), ("client_address", ("127.0.0.1", 7777)), ("close_connection", False), ("connection", object()), ("_registry_job", None), ("_t_req_start", None), ("_flush_deadline", None), ("_client_tag", _const("test")), ("_send", self._record_send)):
            setattr(handler, k, v)
        cast("Callable[[], None]", getattr(handler, "do_POST"))()
        if (st := _store_of(cast("Callable[[], _AdapterProto]", getattr(self.srv, "_explicit_adapter"))())) is not None:
            assert st.flush_now(timeout_s=2.0) is True
        code, payload = self.responses[-1]
        return code, payload, self.runs[-1]

    def _record_send(self, code: int, payload: dict[str, object], *_a: object, **_k: object) -> None:
        self.responses.append((code, payload))


def _setup_server(monkeypatch: pytest.MonkeyPatch, base: Path, cids: list[str]) -> _ServerHarness:
    base.mkdir(parents=True, exist_ok=True)
    srv, ws, cfg, clean_home = _load_server(), base / "workspace", base / "dynamic_config.json", base / "agy-home"
    _ = cfg.write_text(json.dumps({"AGY_ZERO_CANON_ENABLED": True}), encoding="utf-8")
    for name in ("_session_store", "_in_flight_cids", "_active_cid_owners"):
        cast("dict[object, object]", getattr(srv, name)).clear()
    fake_hyg = SimpleNamespace(acquire=_const(SimpleNamespace(admitted=True, ticket_id="t1")), release=_noop, session_commit=_noop, session_invalidate=_noop, handle_disconnect=_noop)
    h = _ServerHarness(srv, ws, cids)
    for attr, val in (("WORKSPACE", ws), ("DYNAMIC_CONFIG_PATH", cfg), ("CLEAN_HOME_DIR", clean_home), ("_auth_ok", _const(True)), ("_client_gone", _const(False)), ("_launcher", _const(object())), ("_budget", None), ("_persist_sessions", _noop), ("_is_image_fallback_enabled", _const(False)), ("_log", _noop), ("_hygiene_rt", _const(fake_hyg)), ("Run", h.make_run)):
        monkeypatch.setattr(srv, attr, val)
    handler_cls = cast("object", getattr(srv, "Handler"))
    monkeypatch.setattr(handler_cls, "_execute", h.execute)
    monkeypatch.setattr(handler_cls, "_attach_resolved_usage", _noop)
    monkeypatch.setattr(cast("object", getattr(srv, "_u_fin")), "ensure_drained_before_usage", _noop)
    return h


def test_server_handler_e2e_plain_legacy_and_zero_canon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for env in ("BRIDGE_HOT_EXPLICIT_PLAIN_ENABLED", "BRIDGE_HOT_ZC_PLAIN_ENABLED", "BRIDGE_HOT_CANONICAL_TOOLS_ENABLED", "AGY_ZERO_CANON_ENABLED"):
        monkeypatch.setenv(env, "1")
    h_leg = _setup_server(monkeypatch, tmp_path / "leg", [_CID_1])
    code, _, run_leg = h_leg.post([{"role": "user", "content": "use tools"}], chat_id="dsh-leg", tools=_UNSORTED_TOOLS)
    leg_ad, leg_prompt = cast("Callable[[], _AdapterProto]", getattr(h_leg.srv, "_explicit_adapter"))(), str(run_leg["prompt"])
    assert code == 200 and _store_of(leg_ad) is None and not (h_leg.workspace / "state" / "sessions_explicit.json").exists()
    assert render_tools_section(_UNSORTED_TOOLS, sort_keys=False) in leg_prompt
    assert leg_prompt.index("- z_tool:") < leg_prompt.index("- a_tool:") and leg_prompt.index('"z":') < leg_prompt.index('"a":')

    h_std = _setup_server(monkeypatch, tmp_path / "std", [_CID_1, _CID_2])
    m1 = [{"role": "system", "content": "SYS_ANCHOR"}, {"role": "user", "content": "FIRST_USER"}]
    c1, p1, r1 = h_std.post(m1, chat_id="std-e2e")
    assert c1 == 200 and r1["conversation_id"] == "" and p1["conversation_id"] == _CID_1 and "SYS_ANCHOR" in str(r1["prompt"]) and "FIRST_USER" in str(r1["prompt"])
    m2 = [*m1, {"role": "assistant", "content": "reply-1"}, {"role": "user", "content": "SECOND_USER"}]
    c2, p2, r2 = h_std.post(m2, chat_id="std-e2e")
    assert c2 == 200 and r2["conversation_id"] == _CID_1 and p2["conversation_id"] == _CID_1 and "SECOND_USER" in str(r2["prompt"]) and "FIRST_USER" not in str(r2["prompt"]) and "SYS_ANCHOR" not in str(r2["prompt"])

    h_zc = _setup_server(monkeypatch, tmp_path / "zc", [_CID_3, _CID_2])
    z1, zp1, zr1 = h_zc.post(m1, chat_id="zc-e2e", review_profile="Zero-Canon")
    cwd1 = Path(str(zr1["cwd"]))
    assert z1 == 200 and zr1["zero_canon"] is True and zr1["conversation_id"] == "" and zp1["conversation_id"] == _CID_3 and zr1["cwd_existed"] is True and cwd1.name.startswith("turn-") and not cwd1.exists()
    z2, zp2, zr2 = h_zc.post(m2, chat_id="zc-e2e", review_profile="Zero-Canon")
    cwd2 = Path(str(zr2["cwd"]))
    assert z2 == 200 and zr2["zero_canon"] is True and zr2["conversation_id"] == _CID_3 and zp2["conversation_id"] == _CID_3 and zr2["cwd_existed"] is True and cwd2.name.startswith("turn-") and cwd2 != cwd1 and not cwd2.exists()
    assert "SECOND_USER" in str(zr2["prompt"]) and "FIRST_USER" not in str(zr2["prompt"])
    assert (tmp_path / "zc" / "agy-zc-cwd").is_dir() and list((tmp_path / "zc" / "agy-zc-cwd").glob("turn-*")) == []

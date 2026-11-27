"""W1: prompt_cache_key resume (flag OFF by default) + effort-reject fallback."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "bridges" / "agy-bridge"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from agy_runtime.chat_key_policy import (  # noqa: E402
    FLAG_HOT_PCK,
    is_prompt_cache_key_enabled,
    resolve_agy_chat_key,
)
from agy_runtime.effort_reject_fallback import (  # noqa: E402
    FLAG_EFFORT_REJECT_FALLBACK,
    clear_effort_rejections_for_tests,
    is_effort_reject_fallback_enabled,
    record_effort_rejection,
    resolve_effort_with_fallback,
    should_fallback_effortless,
)
from agy_runtime.session_resume_adapter import (  # noqa: E402
    ExplicitResumeAdapter,
    TurnHttpMeta,
    TurnPayloadMeta,
)

CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
REJECT_ERR = '--effort is not supported for model "gemini-4-carbon"'
AUTH = {"Authorization": "Bearer tok-aaaaaaaa"}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(FLAG_HOT_PCK, raising=False)
    monkeypatch.delenv(FLAG_EFFORT_REJECT_FALLBACK, raising=False)
    clear_effort_rejections_for_tests()


def _cfg(tmp_path: Path, **flags: bool) -> Path:
    path = tmp_path / "dynamic_config.json"
    path.write_text(json.dumps({"bridge_hot_explicit_plain_enabled": True, **flags}), encoding="utf-8")
    return path


def _http(headers: dict | None = None) -> TurnHttpMeta:
    return TurnHttpMeta(headers=dict(AUTH) if headers is None else headers, client_host="127.0.0.1", profile_tag="standard")


def _payload(msgs: list, *, pck: str | None = "pck-carbon-1", effort: str = "off") -> TurnPayloadMeta:
    req = {"messages": msgs}
    if pck is not None:
        req["prompt_cache_key"] = pck
    return TurnPayloadMeta(req=req, extra={}, model_id="gemini-4-carbon", effort=effort, cwd="", cwd_invalid=False, tools=[])


def _turn(adapter, cfg: Path, msgs: list, now: float, *, headers=None, pck="pck-carbon-1", effort="off"):
    return adapter.prepare_turn(_http(headers), _payload(msgs, pck=pck, effort=effort), now_s=now)


def _commit(adapter, st, out_text: str, cid: str) -> bool:
    ok = adapter.finalize_turn(st, {"conversation_id": cid, "text": out_text}, "commit", CID_RE)
    if (store := getattr(adapter, "_store", None)) is not None:
        assert store.flush_now(timeout_s=2.0) is True
    return ok


def test_chat_key_policy_default_off_ignores_pck(tmp_path):
    cfg = _cfg(tmp_path)
    req = {"prompt_cache_key": "pck-1"}
    assert not is_prompt_cache_key_enabled(cfg)
    assert not resolve_agy_chat_key(req, {}, {}, config_path=cfg).keyed
    assert not resolve_agy_chat_key(req, {}, {}, config_path=tmp_path / "absent.json").keyed


def test_chat_key_policy_flag_on_and_header_priority(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, bridge_hot_prompt_cache_key_enabled=True)
    req = {"prompt_cache_key": "pck-1"}
    assert is_prompt_cache_key_enabled(cfg)
    chat = resolve_agy_chat_key(req, {}, {}, config_path=cfg)
    assert chat.keyed and chat.value == "pck-1" and chat.source == "prompt_cache_key"
    hdr = resolve_agy_chat_key(req, {"X-DSH-Chat-Id": "explicit-1"}, {}, config_path=cfg)
    assert hdr.keyed and hdr.value == "explicit-1" and hdr.source == "x-dsh-chat-id"
    ses = resolve_agy_chat_key(req, {"X-Session-Id": "sess-1"}, {}, config_path=cfg)
    assert ses.keyed and ses.value == "sess-1"
    monkeypatch.setenv(FLAG_HOT_PCK, "1")
    assert is_prompt_cache_key_enabled(tmp_path / "absent.json")
    assert resolve_agy_chat_key(req, config_path=tmp_path / "absent.json").value == "pck-1"


def test_adapter_default_off_not_handled(tmp_path):
    adapter = ExplicitResumeAdapter(tmp_path / "state", _cfg(tmp_path))
    try:
        st = _turn(adapter, _cfg(tmp_path), [{"role": "user", "content": "hi"}], 1000.0)
        assert st.handled is False and st.allow_commit is False
    finally:
        adapter.close()


def test_adapter_flag_on_pck_multiturn_resume(tmp_path):
    cfg = _cfg(tmp_path, bridge_hot_prompt_cache_key_enabled=True)
    adapter = ExplicitResumeAdapter(tmp_path / "state", cfg)
    cid = "11111111-2222-3333-4444-555555555555"
    m1 = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    try:
        st1 = _turn(adapter, cfg, m1, 1000.0)
        assert st1.handled and st1.allow_commit and not st1.is_resumed
        assert _commit(adapter, st1, "hello there", cid)
        m2 = [*m1, {"role": "assistant", "content": "hello there"}, {"role": "user", "content": "more"}]
        st2 = _turn(adapter, cfg, m2, 1010.0)
        assert st2.handled and st2.is_resumed and st2.conversation_id == cid
        adapter.release_if_unfinalized(st2)
    finally:
        adapter.close()


def test_adapter_flag_on_different_token_not_resumed(tmp_path):
    cfg = _cfg(tmp_path, bridge_hot_prompt_cache_key_enabled=True)
    adapter = ExplicitResumeAdapter(tmp_path / "state", cfg)
    cid = "11111111-2222-3333-4444-555555555555"
    m1 = [{"role": "user", "content": "hi"}]
    try:
        st1 = _turn(adapter, cfg, m1, 1000.0)
        assert st1.allow_commit and _commit(adapter, st1, "ok", cid)
        m2 = [*m1, {"role": "assistant", "content": "ok"}, {"role": "user", "content": "more"}]
        st2 = _turn(adapter, cfg, m2, 1010.0, headers={"Authorization": "Bearer tok-bbbbbbbb"})
        assert st2.handled and not st2.is_resumed
        adapter.release_if_unfinalized(st2)
    finally:
        adapter.close()


def test_adapter_flag_on_different_system_prompt_not_resumed(tmp_path):
    cfg = _cfg(tmp_path, bridge_hot_prompt_cache_key_enabled=True)
    adapter = ExplicitResumeAdapter(tmp_path / "state", cfg)
    cid = "11111111-2222-3333-4444-555555555555"
    m1 = [{"role": "system", "content": "sys-A"}, {"role": "user", "content": "hi"}]
    try:
        st1 = _turn(adapter, cfg, m1, 1000.0)
        assert st1.allow_commit and _commit(adapter, st1, "ok", cid)
        m2 = [{"role": "system", "content": "sys-B"}, *m1[1:], {"role": "assistant", "content": "ok"}, {"role": "user", "content": "more"}]
        st2 = _turn(adapter, cfg, m2, 1010.0)
        assert st2.handled and not st2.is_resumed
        adapter.release_if_unfinalized(st2)
    finally:
        adapter.close()


def test_effort_fallback_default_off(tmp_path):
    cfg = _cfg(tmp_path)
    out = {"state": "agy_error", "err": REJECT_ERR}
    assert not is_effort_reject_fallback_enabled(cfg)
    assert should_fallback_effortless(out, "high", already_retried=False, config_path=cfg) is False


def test_effort_fallback_flag_on_positive(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, effort_reject_fallback_enabled=True)
    out = {"state": "agy_error", "err": REJECT_ERR}
    assert is_effort_reject_fallback_enabled(cfg)
    assert should_fallback_effortless(out, "high", already_retried=False, config_path=cfg) is True
    monkeypatch.setenv(FLAG_EFFORT_REJECT_FALLBACK, "true")
    assert should_fallback_effortless(out, "HIGH", already_retried=False, config_path=tmp_path / "absent.json") is True


def test_effort_fallback_flag_on_negative_guards(tmp_path):
    cfg = _cfg(tmp_path, effort_reject_fallback_enabled=True)
    out = {"state": "agy_error", "err": REJECT_ERR}
    assert should_fallback_effortless(out, "high", already_retried=True, config_path=cfg) is False
    assert should_fallback_effortless(out, "off", already_retried=False, config_path=cfg) is False
    assert should_fallback_effortless(out, "  ", already_retried=False, config_path=cfg) is True
    assert should_fallback_effortless({"state": "agy_error", "err": "boom"}, "high", already_retried=False, config_path=cfg) is False
    assert should_fallback_effortless({"state": "done", "err": REJECT_ERR}, "high", already_retried=False, config_path=cfg) is False
    assert should_fallback_effortless({"state": "agy_error"}, "high", already_retried=False, config_path=cfg) is False


def test_effort_rejection_cache_turn2_keeps_hot_resume(tmp_path):
    """F-011: Turn 2+ rejected pair resolves to off without re-failing the hot session."""
    cfg = _cfg(tmp_path, effort_reject_fallback_enabled=True)
    assert resolve_effort_with_fallback("gemini-4-carbon", "high", "default", config_path=cfg) == ("high", "default")
    record_effort_rejection("gemini-4-carbon", "high")
    assert resolve_effort_with_fallback("gemini-4-carbon", " HIGH ", "default", config_path=cfg) == ("off", "effort_reject_fallback")
    (off_cfg := tmp_path / "off.json").write_text("{}", encoding="utf-8")
    assert resolve_effort_with_fallback("gemini-4-carbon", "high", "default", config_path=off_cfg) == ("high", "default")


def test_effort_rejection_cache_bounded_64(tmp_path):
    cfg = _cfg(tmp_path, effort_reject_fallback_enabled=True)
    for i in range(70):
        record_effort_rejection(f"m{i}", "high")
    assert resolve_effort_with_fallback("m0", "high", "d", config_path=cfg) == ("high", "d")
    assert resolve_effort_with_fallback("m69", "high", "d", config_path=cfg) == ("off", "effort_reject_fallback")


class _Stub:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        return lambda *a, **k: None


def test_run_once_transient_then_effort_reject_then_off(tmp_path, monkeypatch):
    """F-008/F-010/F-012: attempt1 503 -> attempt2 effort-reject -> attempt3 off done."""
    import importlib.util
    _spec = importlib.util.spec_from_file_location("_agy_srv_w2", ROOT / "bridges" / "agy-bridge" / "server.py")
    srv = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = srv
    _spec.loader.exec_module(srv)
    cfg = _cfg(tmp_path, effort_reject_fallback_enabled=True)
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    monkeypatch.setattr(srv, "_hygiene_rt", lambda: _Stub(acquire=lambda *a, **k: SimpleNamespace(admitted=True, ticket_id="t", retry_after_s=0.0)))
    monkeypatch.setattr(srv, "_TURN_RESILIENCE", _Stub(take=lambda *a, **k: True, delivered_after_commit=lambda c, o, d: d))
    monkeypatch.setattr(srv, "_lsc", _Stub(usage_drain_settings=lambda **k: (False, 0.0), classify_cloud_mode=lambda e: "test"))
    monkeypatch.setattr(srv, "_u_fin", _Stub())
    monkeypatch.setattr(srv, "_p12_seam", lambda: _Stub())
    for name, val in {"_launcher": lambda: None, "_retry_credit": lambda: None, "_retry_take": lambda: True,
                      "_retry_pause_s": lambda a: 0.0, "_incident_retry_allowed": lambda *a: True,
                      "_is_cli_rejection_outcome": lambda o: False, "_build_timeout_policy": lambda t: None,
                      "should_allow_retry_attempt": lambda **k: (True, ""), "capture_run_identity": lambda r: None,
                      "resolve_run_chat_key": lambda c: "", "_log": lambda *a, **k: None,
                      "calculate_retry_budget": lambda *a, **k: SimpleNamespace(allow_retry=True, attempt_s=0.0)}.items():
        monkeypatch.setattr(srv, name, val)
    efforts = []
    outs = [{"state": "agy_error", "err": "upstream 503", "rc": 1},
            {"state": "agy_error", "err": REJECT_ERR, "rc": 1}, {"state": "done", "text": "ok"}]

    monkeypatch.setattr(srv, "Run", lambda p, m, e, *a, **k: SimpleNamespace(
        effort=e, _persistent_mode=False, proc=SimpleNamespace(pid=0, poll=lambda: None), close=lambda: None))
    cls = next(v for v in vars(srv).values() if isinstance(v, type) and "_run_once_impl" in v.__dict__)

    class _H(cls):
        def __getattr__(self, name):
            return lambda *a, **k: None

    h = _H.__new__(_H)
    h._registry_job = None
    h._acquire_slot = lambda keepalive: ""

    def _execute(run, *a, **k):
        efforts.append(run.effort)
        return dict(outs[len(efforts) - 1])

    h._execute = _execute
    ctx = {"model": "gemini-4-carbon", "effort": "high", "effort_source": "default", "tag": "t1",
           "model_len": 10, "prompt": "hi", "tools_count": 0, "cwd": str(tmp_path),
           "stream_resilience_enabled": False, "conversation_id": "", "turn_id": ""}
    res = h._run_once_impl(ctx, lambda *a: None, lambda *a: None, lambda *a: None, lambda *a: None)
    assert efforts == ["high", "high", "off"]
    assert res["state"] == "done"
    assert ctx["effort"] == "off" and ctx["effort_source"] == "effort_reject_fallback"

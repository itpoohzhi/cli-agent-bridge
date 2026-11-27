"""Wave W1: prompt_cache_key в канонизации идентичности и подписанных директивах."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "bridges" / "agy-bridge"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import adapters.passthrough_adapter as pa  # noqa: E402
import core.session_plane.zc_env_guard as guard  # noqa: E402
from agy_runtime.session_resume_adapter import (  # noqa: E402
    ExplicitResumeAdapter,
    TurnHttpMeta,
    TurnPayloadMeta,
)
from core.session_plane import (  # noqa: E402
    DIRECTIVE_HEADER,
    SessionIdentityError,
    SessionIdentityInput,
    extract_canonical_chat_id,
    is_session_plane_prompt_cache_key_enabled,
    resolve_canonical_identity,
    verify_directive,
)

FLAG = "BRIDGE_SESSION_PLANE_PROMPT_CACHE_KEY_ENABLED"
SIGNED = "BRIDGE_AGY_SIGNED_DIRECTIVE_ENABLED"
PCK, PCK2 = "pck-abcdef123456", "pck-other-99998888"
CID = "11111111-2222-3333-4444-555555555555"
CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
AUTH = {"Authorization": "Bearer tok-aaaaaaaa"}
M1 = [{"role": "user", "content": "hi"}]


def _cfg(tmp_path: Path, payload: dict[str, object], name: str = "dynamic_config.json") -> Path:
    cfg = tmp_path / name
    cfg.write_text(json.dumps(payload), encoding="utf-8")
    return cfg


def test_flag_default_false(tmp_path: Path) -> None:
    assert is_session_plane_prompt_cache_key_enabled({}, config_path=_cfg(tmp_path, {})) is False


def test_flag_env_true(tmp_path: Path) -> None:
    env = {FLAG: "true"}
    assert is_session_plane_prompt_cache_key_enabled(env, config_path=_cfg(tmp_path, {})) is True


def test_flag_config_overrides_env(tmp_path: Path) -> None:
    off = _cfg(tmp_path, {FLAG: False}, "off.json")
    assert is_session_plane_prompt_cache_key_enabled({FLAG: "true"}, config_path=off) is False
    on = _cfg(tmp_path, {FLAG: True}, "on.json")
    assert is_session_plane_prompt_cache_key_enabled({FLAG: "false"}, config_path=on) is True


def test_pck_ignored_by_default() -> None:
    body = {"prompt_cache_key": PCK}
    assert extract_canonical_chat_id(None, body, None) is None
    ident = resolve_canonical_identity(SessionIdentityInput(request_body=body))
    assert ident.canonical_chat_id is None and ident.keyed is False


def test_pck_used_when_allowed() -> None:
    body = {"prompt_cache_key": PCK}
    assert extract_canonical_chat_id(None, body, None, allow_prompt_cache_key=True) == PCK
    ident = resolve_canonical_identity(
        SessionIdentityInput(request_body=body, allow_prompt_cache_key=True)
    )
    assert ident.canonical_chat_id == PCK and ident.keyed is True


def test_explicit_chat_id_wins_over_pck() -> None:
    headers = {"X-DSH-Chat-Id": "chat-explicit-1"}
    body = {"prompt_cache_key": PCK}
    assert extract_canonical_chat_id(headers, body, None, allow_prompt_cache_key=True) == "chat-explicit-1"
    body2 = {"session_id": "sess-explicit-1", "prompt_cache_key": PCK}
    assert extract_canonical_chat_id(None, body2, None, allow_prompt_cache_key=True) == "sess-explicit-1"


def test_explicit_conflict_still_409() -> None:
    with pytest.raises(SessionIdentityError) as ei:
        extract_canonical_chat_id(
            {"x-dsh-chat-id": "chat-aaaa1111"},
            {"session_id": "chat-bbbb2222", "prompt_cache_key": PCK},
            None,
            allow_prompt_cache_key=True,
        )
    assert ei.value.http_status == 409 and ei.value.code == "SESSION_ID_CONFLICT"


@pytest.mark.parametrize("bad", [123, 4.5, "short", "has space123", "bad!chars123", " " * 8, "a" * 129])
def test_invalid_pck_rejected(bad: object) -> None:
    with pytest.raises(SessionIdentityError) as ei:
        extract_canonical_chat_id(None, {"prompt_cache_key": bad}, None, allow_prompt_cache_key=True)
    assert ei.value.http_status == 400 and ei.value.code == "ERR_INVALID_SESSION_ID"


def test_invalid_pck_ignored_when_flag_off() -> None:
    assert extract_canonical_chat_id(None, {"prompt_cache_key": 123}, None) is None


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = _cfg(tmp_path, {"bridge_hot_explicit_plain_enabled": True, "bridge_hot_prompt_cache_key_enabled": True})
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(path))
    monkeypatch.setenv(SIGNED, "1")
    monkeypatch.delenv(FLAG, raising=False)
    monkeypatch.setattr(guard, "_DEFAULT_KEY_PATH", tmp_path / "run" / "directive.key")
    return path


def _pt(monkeypatch: pytest.MonkeyPatch) -> Any:
    adapter = pa.PassthroughAdapter.__new__(pa.PassthroughAdapter)
    adapter.id = "agy-bridge"
    adapter.config = {"base_url": "http://127.0.0.1:9887/v1", "trust_profile": ""}
    adapter._base_path = urlsplit(adapter.config["base_url"]).path.rstrip("/")
    adapter.host = SimpleNamespace()
    monkeypatch.setattr(adapter, "_read_json_headers", lambda: {})
    return adapter


def _body(pck: object = PCK, msgs: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {"model": "m", "messages": list(M1 if msgs is None else msgs), "prompt_cache_key": pck}


def _signed(adapter: Any, body: dict[str, Any]) -> tuple[dict[str, str], Any]:
    out = adapter._upstream_headers(json.dumps(body).encode(), dict(AUTH))
    payload, reason = verify_directive(out[DIRECTIVE_HEADER], guard.load_or_create_directive_key())
    assert payload is not None, reason
    return out, payload


def _turn(resume: ExplicitResumeAdapter, body: dict[str, Any], out: dict[str, str], now: float) -> Any:
    hm = TurnHttpMeta(headers={**AUTH, **out}, client_host="127.0.0.1", profile_tag="standard")
    pm = TurnPayloadMeta(req=body, extra={}, model_id="m", effort="", cwd="", cwd_invalid=False, tools=[])
    return resume.prepare_turn(hm, pm, now_s=now)


def test_e2e_flag_off_directive_chat_mismatch(tmp_path: Path, cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out, payload = _signed(_pt(monkeypatch), _body())
    assert payload.process_directive == "EPHEMERAL_KILL_AFTER_TURN" and payload.chat_id_hash == ""
    resume = ExplicitResumeAdapter(tmp_path / "state", cfg)
    try:
        st = _turn(resume, _body(), out, 1000.0)
        assert st.force_cold is True and st.decision_reason == "directive_chat_mismatch"
    finally:
        resume.close()


def test_e2e_flag_on_warm_multiturn_resume(tmp_path: Path, cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG, "1")
    pt = _pt(monkeypatch)
    out, payload = _signed(pt, _body())
    assert payload.process_directive == "WARM_SLOT_REUSE"
    assert payload.chat_id_hash == hashlib.sha256(PCK.encode()).hexdigest()[:16]
    resume = ExplicitResumeAdapter(tmp_path / "state", cfg)
    try:
        st1 = _turn(resume, _body(), out, 1000.0)
        assert st1.handled is True and st1.force_cold is False
        assert st1.allow_commit is True and st1.decision_reason == "slot_empty"
        assert resume.finalize_turn(st1, {"conversation_id": CID, "text": "hello"}, "commit", CID_RE)
        store = getattr(resume, "_store")
        assert store is not None and store.flush_now(timeout_s=2.0) is True
        m2 = [*M1, {"role": "assistant", "content": "hello"}, {"role": "user", "content": "more"}]
        out2, _ = _signed(pt, _body(msgs=m2))
        st2 = _turn(resume, _body(msgs=m2), out2, 1010.0)
        assert st2.is_resumed is True and st2.conversation_id == CID
        resume.release_if_unfinalized(st2)
    finally:
        resume.close()


def test_e2e_pck_swap_fail_closed(tmp_path: Path, cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG, "1")
    out, _ = _signed(_pt(monkeypatch), _body())
    resume = ExplicitResumeAdapter(tmp_path / "state", cfg)
    try:
        st = _turn(resume, _body(pck=PCK2), out, 1000.0)
        assert st.force_cold is True and st.allow_commit is False
        assert st.decision_reason == "directive_chat_mismatch"
    finally:
        resume.close()


def test_invalid_pck_upstream_fail_closed_ephemeral(cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(FLAG, "1")
    _, payload = _signed(_pt(monkeypatch), _body(pck="bad id!"))
    assert payload.process_directive == "EPHEMERAL_KILL_AFTER_TURN" and payload.chat_id_hash == ""

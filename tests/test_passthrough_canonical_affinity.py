"""W3: canonical affinity и подписанный X-DSH-Session-Directive в passthrough."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

import adapters.passthrough_adapter as pa
from core import session_affinity as sa
from core.session_plane import DIRECTIVE_HEADER, verify_directive

CANON = "BRIDGE_PASSTHROUGH_CANONICAL_AFFINITY_ENABLED"
SIGNED = "BRIDGE_AGY_SIGNED_DIRECTIVE_ENABLED"
CHAT = "chat-session-0001"
BODY = json.dumps({"model": "m", "messages": [{"role": "user", "content": "hi"}]}).encode()


@pytest.fixture(autouse=True)
def _isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BRIDGE_HUB_DYNAMIC_CONFIG", str(cfg))
    monkeypatch.setenv("BRIDGE_SESSION_AFFINITY_SALT", "x" * 32)
    monkeypatch.delenv(sa.FLAG_STABLE_SESSION, raising=False)
    monkeypatch.delenv(CANON, raising=False)
    monkeypatch.delenv(SIGNED, raising=False)
    monkeypatch.setattr(sa, "_SALT", None)


def _hdr(profile: str | None = None, chat: str | None = CHAT) -> dict[str, str]:
    out = {"Authorization": "Bearer t"}
    if chat:
        out["X-DSH-Chat-Id"] = chat
    if profile:
        out["X-Review-Profile"] = profile
    return out


def test_flags_off_keep_legacy_uuid4() -> None:
    first = sa.session_affinity(BODY, _hdr(), "ns")
    assert first != sa.session_affinity(BODY, _hdr(), "ns")
    assert sa.request_scope(BODY, _hdr(), "ns") == ""


def test_canonical_flag_gives_stable_chat_affinity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CANON, "1")
    other_body = json.dumps({"model": "m", "messages": [{"role": "user", "content": "other"}]}).encode()
    one = sa.session_affinity(BODY, _hdr(), "ns")
    assert one == sa.session_affinity(other_body, _hdr(), "ns")
    assert one != sa.session_affinity(BODY, _hdr(chat="chat-session-0002"), "ns")
    assert sa.request_scope(BODY, _hdr(), "ns") != ""


def test_review_profile_never_shares_affinity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CANON, "1")
    std = sa.session_affinity(BODY, _hdr("standard"), "ns")
    zc = sa.session_affinity(BODY, _hdr("zero-canon"), "ns")
    assert std != zc
    assert std == sa.session_affinity(BODY, _hdr(), "ns")
    assert zc == sa.session_affinity(BODY, _hdr("ZERO-CANON"), "ns")


def test_invalid_chat_id_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CANON, "1")
    bad = _hdr(chat="bad id!")
    assert sa.session_affinity(b"{}", bad, "ns") != sa.session_affinity(b"{}", bad, "ns")


def _adapter(base_url: str, monkeypatch: pytest.MonkeyPatch, trust: str = "") -> Any:
    adapter = pa.PassthroughAdapter.__new__(pa.PassthroughAdapter)
    adapter.id = "agy-bridge"
    adapter.config = {"base_url": base_url, "trust_profile": trust}
    adapter._base_path = urlsplit(base_url).path.rstrip("/")
    monkeypatch.setattr(adapter, "_read_json_headers", lambda: {})
    return adapter


@pytest.fixture
def key_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import core.session_plane.zc_env_guard as guard

    path = tmp_path / "run" / "directive.key"
    monkeypatch.setattr(guard, "_DEFAULT_KEY_PATH", path)
    return path


def test_directive_off_by_default(monkeypatch: pytest.MonkeyPatch, key_path: Path) -> None:
    adapter = _adapter("http://127.0.0.1:9887/v1", monkeypatch)
    assert DIRECTIVE_HEADER not in adapter._upstream_headers(BODY, _hdr())


def test_local_subbridge_gets_verifiable_directive(monkeypatch: pytest.MonkeyPatch, key_path: Path) -> None:
    monkeypatch.setenv(SIGNED, "1")
    adapter = _adapter("http://127.0.0.1:9887/v1", monkeypatch)
    out = adapter._upstream_headers(BODY, _hdr("zero-canon"))
    from core.session_plane import load_or_create_directive_key

    payload, reason = verify_directive(out[DIRECTIVE_HEADER], load_or_create_directive_key(key_path))
    assert payload is not None, reason
    assert payload.review_profile == "zero-canon"
    assert payload.process_directive == "WARM_SLOT_REUSE"


def test_external_passthrough_never_gets_directive(monkeypatch: pytest.MonkeyPatch, key_path: Path) -> None:
    monkeypatch.setenv(SIGNED, "1")
    adapter = _adapter("http://127.0.0.1:10830/sg-qwen", monkeypatch)
    assert DIRECTIVE_HEADER not in adapter._upstream_headers(BODY, _hdr())
    ext = _adapter("http://127.0.0.1:9887/v1", monkeypatch, trust="external")
    assert DIRECTIVE_HEADER not in ext._upstream_headers(BODY, _hdr())


def test_conflicting_session_ids_fail_closed(monkeypatch: pytest.MonkeyPatch, key_path: Path) -> None:
    monkeypatch.setenv(SIGNED, "1")
    adapter = _adapter("http://127.0.0.1:9887/v1", monkeypatch)
    body = json.dumps({"model": "m", "session_id": "other-session-9"}).encode()
    out = adapter._upstream_headers(body, _hdr())
    from core.session_plane import load_or_create_directive_key

    payload, _ = verify_directive(out[DIRECTIVE_HEADER], load_or_create_directive_key(key_path))
    assert payload is not None and payload.process_directive == "EPHEMERAL_KILL_AFTER_TURN"
    assert out["X-DSH-Chat-Id"] != CHAT


def test_inbound_directive_is_stripped_on_open(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def fake_open(_a: Any, _p: str, _b: bytes, headers: Any, **_k: Any) -> None:
        seen.update(headers)

    monkeypatch.setattr(pa, "open_request", fake_open)
    adapter = _adapter("http://127.0.0.1:10830/sg-qwen", monkeypatch)
    adapter._open("/chat", b"{}", {"x-dsh-session-directive": "forged", "A": "b"})
    assert seen == {"A": "b"}

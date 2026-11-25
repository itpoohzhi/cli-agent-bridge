from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import core.resident_identity as identity_module
from core.resident_identity import (
    IdentityInputs,
    ResidentAuthError,
    ResidentRequestError,
    resolve_resident_identity,
    turn_ids_and_resident_ctx,
)

_SECRET = b"0123456789abcdef0123456789abcdef"


def _chat_resolution(
    request: dict[str, object],
    **_: object,
) -> SimpleNamespace:
    value = request.get("session_id")
    valid = isinstance(value, str) and bool(value)
    return SimpleNamespace(value=value, keyed=valid, invalid=not valid)


def _inputs(**changes: Any) -> IdentityInputs:
    values: dict[str, Any] = {
        "request": {"session_id": "chat-1"},
        "headers": {},
        "extra": {},
        "secret": _SECRET,
        "trusted_principal_hash": "principal-1",
    }
    values.update(changes)
    return IdentityInputs(**values)


def test_principal_is_part_of_scoped_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    first = resolve_resident_identity(_inputs(trusted_principal_hash="principal-1"))
    second = resolve_resident_identity(_inputs(trusted_principal_hash="principal-2"))
    assert first.scoped_session_id != second.scoped_session_id
    assert not first.ephemeral


@pytest.mark.parametrize("chat_id", ["bad\x01id", "bad\ud800id"])
def test_invalid_chat_tokens_are_ephemeral(
    monkeypatch: pytest.MonkeyPatch,
    chat_id: str,
) -> None:
    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    result = resolve_resident_identity(_inputs(request={"session_id": chat_id}))
    assert result.ephemeral
    assert result.cache_key == ""
    assert result.degradation_reason == "missing_or_invalid_chat_id"


def test_missing_principal_auth_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    with pytest.raises(ResidentAuthError):
        resolve_resident_identity(_inputs(trusted_principal_hash="", require_auth=True))
    first = resolve_resident_identity(_inputs(trusted_principal_hash=""))
    second = resolve_resident_identity(_inputs(trusted_principal_hash=""))
    assert first.degradation_reason == "unauthenticated_ephemeral"
    assert first.scoped_session_id not in {"", "default", second.scoped_session_id}


def test_invalid_principal_fails_before_chat_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*_: object, **__: object) -> object:
        raise AssertionError("chat resolver must not run")

    monkeypatch.setattr(identity_module, "resolve_chat_key", unexpected)
    with pytest.raises(ResidentRequestError) as exc_info:
        resolve_resident_identity(_inputs(trusted_principal_hash="bad\ud800"))
    assert exc_info.value.code == "invalid_principal_hash"


def test_prompt_cache_key_is_not_a_chat_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    result = resolve_resident_identity(_inputs(request={"prompt_cache_key": "shared"}))
    assert result.ephemeral
    assert result.cache_key == ""


def test_secret_validation_and_repr_redaction() -> None:
    with pytest.raises(ValueError, match="invalid_hmac_secret"):
        _inputs(secret=b"short")
    inputs = _inputs(
        request={"session_id": "sensitive"},
        headers={"authorization": "secret"},
        extra={"private": "secret"},
    )
    rendered = repr(inputs)
    assert "sensitive" not in rendered
    assert "authorization" not in rendered
    assert _SECRET.hex() not in rendered


def test_json_framing_avoids_separator_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    first = resolve_resident_identity(_inputs(scope="a,b", subagent_id="c"))
    second = resolve_resident_identity(_inputs(scope="a", subagent_id="b,c"))
    assert first.scoped_session_id != second.scoped_session_id


class _Host:
    def owner_token_hash(self, headers: object) -> str:
        del headers
        return "trusted-owner"

    def validate_turn_id(self, value: object) -> bool:
        return isinstance(value, str)


class _Route:
    def __init__(self) -> None:
        self.host = _Host()
        self.headers: dict[str, str] = {}
        self.request: dict[str, object] = {
            "session_id": "chat-1",
            "owner_hash": "spoofed-owner",
        }
        self.rejections: list[tuple[int, str, str]] = []

    def reject(self, status: int, code: str, message: str) -> None:
        self.rejections.append((status, code, message))


class _Adapter:
    uses_resident_identity = True

    def resident_identity_config(self) -> tuple[bytes, str, bool]:
        return _SECRET, "server-config", True


def test_turn_context_ignores_spoofed_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    route = _Route()
    ctx: dict[str, Any] = {}
    ok = turn_ids_and_resident_ctx(
        route,
        ctx,
        {"turn_id": "turn-1", "resume_turn_id": ""},
        adapter=_Adapter(),
    )
    assert ok
    assert ctx["owner_hash"] == "trusted-owner"
    assert ctx["resident_identity"].principal_hash == "trusted-owner"
    assert not route.rejections


class _PostRouteShape:
    def __init__(self, host: object, headers: dict[str, str]) -> None:
        self.host = host
        self.handler = SimpleNamespace(headers=headers)
        self.request: dict[str, object] = {"session_id": "chat-1"}
        self.rejections: list[tuple[int, str, str]] = []

    def reject(self, status: int, code: str, message: str) -> None:
        self.rejections.append((status, code, message))


class _FallbackOwnerHost:
    def __init__(self, owner: str = "handler-owner") -> None:
        self.owner = owner
        self.received: object = None

    def _owner_token_hash(self, handler: object) -> str:
        self.received = handler
        headers = getattr(handler, "headers")
        assert callable(getattr(headers, "get", None))
        return self.owner

    def validate_turn_id(self, value: object) -> bool:
        return isinstance(value, str)


def test_post_route_handler_headers_resolve_fallback_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    host = _FallbackOwnerHost()
    route = _PostRouteShape(host, {"X-Turn-Owner-Token": "owner-token"})
    ctx: dict[str, Any] = {}
    ok = turn_ids_and_resident_ctx(route, ctx, {}, adapter=_Adapter())
    assert ok
    assert host.received is route.handler
    assert ctx["owner_hash"] == "handler-owner"
    assert ctx["resident_identity"].principal_hash == "handler-owner"
    assert not ctx["resident_identity"].ephemeral


@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "Bearer bearer-owner"},
        {"X-Turn-Owner-Token": "explicit-owner"},
    ],
)
def test_post_route_real_server_owner_hash(
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, str],
) -> None:
    import server

    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    host = SimpleNamespace(
        _owner_token_hash=server._owner_token_hash,
        validate_turn_id=lambda value: isinstance(value, str),
    )
    route = _PostRouteShape(host, headers)
    expected = server._owner_token_hash(route.handler)
    ctx: dict[str, Any] = {}
    ok = turn_ids_and_resident_ctx(route, ctx, {}, adapter=_Adapter())
    assert ok
    assert expected
    assert ctx["owner_hash"] == expected
    assert ctx["resident_identity"].principal_hash == expected
    assert not ctx["resident_identity"].ephemeral


def test_post_route_missing_auth_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    route = _PostRouteShape(_FallbackOwnerHost(""), {})
    ctx: dict[str, Any] = {}
    ok = turn_ids_and_resident_ctx(route, ctx, {}, adapter=_Adapter())
    assert not ok
    assert route.rejections == [(401, "auth_required", "")]


def test_legacy_route_fallback_owner_receives_headers_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_module, "resolve_chat_key", _chat_resolution)
    host = _FallbackOwnerHost("legacy-owner")
    route: Any = _Route()
    route.host = host
    route.headers = {"X-Turn-Owner-Token": "legacy-token"}
    ctx: dict[str, Any] = {}
    ok = turn_ids_and_resident_ctx(route, ctx, {}, adapter=_Adapter())
    assert ok
    assert getattr(host.received, "headers") is route.headers
    assert ctx["owner_hash"] == "legacy-owner"
    assert not ctx["resident_identity"].ephemeral


def test_turn_error_sse_auth_and_permission_types() -> None:
    from core.stdio_resident.turn_error_sse import build_turn_error

    e401 = build_turn_error(ResidentAuthError(401, "auth_required"), 0)
    e403 = build_turn_error(ResidentAuthError(403, "forbidden"), 0)
    assert e401.status == 401 and e401.error_type == "authentication_error"
    assert e403.status == 403 and e403.error_type == "permission_error"


def test_process_pool_release_and_close_if_idle_fencing() -> None:
    import time
    from types import SimpleNamespace
    from core.stdio_resident.config import StdioPoolConfig
    from core.stdio_resident.process_pool import ResidentProcessPool, _SlotEntry
    from core.stdio_resident.types import SlotAffinityKey, SlotState

    pool = ResidentProcessPool(StdioPoolConfig(enabled=True))
    key = SlotAffinityKey("o", "c", "b", "m", "low", "/w", env_digest="d")
    handle = SimpleNamespace(generation=1, is_alive=lambda: True, terminate_gracefully=lambda **_kw: 0, advance_generation=lambda: 1, created_at_mono=time.monotonic(), _pgid_dead=True, pid=99999)
    entry = _SlotEntry("s1", key, handle, SlotState.READY, 0.0, lease_id="lease-a")  # type: ignore[arg-type]
    pool._slots["s1"] = entry
    assert pool.release("missing") is False
    assert pool.release("s1", lease_id="wrong") is False
    assert pool.release("s1", lease_id="lease-a") is True
    assert pool.release("s1", success=True, lease_id=None) is False
    assert pool.close_if_idle("s1", 99) is False
    assert pool.close_if_idle("s1", 1) is True
    pool.shutdown()

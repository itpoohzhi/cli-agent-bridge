"""Wave 4: B-21 header subagent, B-04/B-05/F-001 pck_v1, B-25 affinity key, B-24 unified pool cap."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from adapters.stdio_drivers import (
    CODEX_POOL_UNIFIED_CAP_FLAG,
    _align_codex_v2_pool_slots,
    _total_cap,
    build_affinity_key,
)
from core.resident_identity import (
    CODEX_PCK_V1_FLAG,
    IdentityInputs,
    ResidentIdentity,
    derive_pck_digest,
    populate_resident_ctx,
    resolve_resident_identity,
)
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.types import SlotAffinityKey

_SECRET = b"0123456789abcdef0123456789abcdef"
_RAW_PCK = "raw-prompt-cache-key-SENTINEL-123"


@pytest.fixture(autouse=True)
def _isolated_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent_dynamic_config.json"))
    monkeypatch.delenv(CODEX_PCK_V1_FLAG, raising=False)
    monkeypatch.delenv(CODEX_POOL_UNIFIED_CAP_FLAG, raising=False)


class _Host:
    def owner_token_hash(self, headers: object) -> str:
        del headers
        return "owner-1"


class _Route:
    def __init__(self, request: dict[str, object], headers: dict[str, str] | None = None) -> None:
        self.host = _Host()
        self.headers = headers or {}
        self.request = request


class _Adapter:
    uses_resident_identity = True

    def resident_identity_config(self) -> tuple[bytes, str, bool]:
        return _SECRET, "server-config", True


def _populate(request: dict[str, object], headers: dict[str, str], extra: dict[str, Any] | None = None) -> ResidentIdentity:
    ctx: dict[str, Any] = {}
    populate_resident_ctx(_Route(request, headers), ctx, extra or {}, adapter=_Adapter())
    return ctx["resident_identity"]


def _identity(**changes: Any) -> ResidentIdentity:
    values: dict[str, Any] = {
        "request": {"prompt_cache_key": _RAW_PCK},
        "headers": {},
        "extra": {},
        "secret": _SECRET,
        "trusted_principal_hash": "principal-1",
    }
    values.update(changes)
    return resolve_resident_identity(IdentityInputs(**values))


# --- B-21 / CP-05 -----------------------------------------------------------


def test_b21_header_subagent_id_changes_scoped_session_id() -> None:
    req = {"chat_id": "chat-1"}
    first = _populate(req, {"X-Subagent-Id": "sub-a"})
    second = _populate(req, {"X-Subagent-Id": "sub-b"})
    assert not first.ephemeral
    assert first.subagent_id == "sub-a"
    assert second.subagent_id == "sub-b"
    assert first.scoped_session_id != second.scoped_session_id


def test_b21_explicit_extra_subagent_id_wins_over_header() -> None:
    req = {"chat_id": "chat-1"}
    explicit = _populate(req, {"X-Subagent-Id": "sub-header"}, {"subagent_id": "sub-extra"})
    assert explicit.subagent_id == "sub-extra"


# --- B-04 / B-05 / F-001 ----------------------------------------------------


def test_pck_flag_off_is_ephemeral() -> None:
    result = _identity()
    assert result.ephemeral
    assert result.degradation_reason == "missing_or_invalid_chat_id"
    assert result.cache_key == ""


def test_valid_chat_id_cache_key_is_digest_never_raw() -> None:
    result = _identity(request={"chat_id": "chat-1", "prompt_cache_key": _RAW_PCK})
    assert not result.ephemeral
    assert result.cache_key == derive_pck_digest(_SECRET, _RAW_PCK)
    assert _RAW_PCK not in result.cache_key and _RAW_PCK not in repr(result)


def test_pck_flag_on_gives_deterministic_affinity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CODEX_PCK_V1_FLAG, "true")
    first, second = _identity(), _identity()
    assert not first.ephemeral
    assert first.degradation_reason == "pck_v1_affinity"
    assert first.scoped_session_id == second.scoped_session_id
    assert first.cache_key == derive_pck_digest(_SECRET, _RAW_PCK)


def test_pck_flag_on_without_principal_stays_ephemeral(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CODEX_PCK_V1_FLAG, "true")
    assert _identity(trusted_principal_hash="").ephemeral


def test_pck_different_principals_do_not_collide(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CODEX_PCK_V1_FLAG, "true")
    first = _identity(trusted_principal_hash="principal-1")
    second = _identity(trusted_principal_hash="principal-2")
    assert first.scoped_session_id != second.scoped_session_id


def test_pck_does_not_override_chat_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CODEX_PCK_V1_FLAG, "true")
    req_a = {"chat_id": "chat-a", "prompt_cache_key": _RAW_PCK}
    req_b = {"chat_id": "chat-b", "prompt_cache_key": _RAW_PCK}
    first, second = _identity(request=req_a), _identity(request=req_b)
    assert not first.ephemeral and not second.ephemeral
    assert first.conversation_id == "chat-a"
    assert first.scoped_session_id != second.scoped_session_id


@pytest.mark.parametrize("flag", ["false", "true"])
@pytest.mark.parametrize("request_extra", [{}, {"chat_id": "chat-1"}])
def test_zero_canon_is_always_ephemeral(monkeypatch: pytest.MonkeyPatch, flag: str, request_extra: dict[str, str]) -> None:
    monkeypatch.setenv(CODEX_PCK_V1_FLAG, flag)
    request = {"prompt_cache_key": _RAW_PCK, **request_extra}
    result = _identity(request=request, review_profile="zero-canon")
    assert result.ephemeral
    assert result.degradation_reason == "zero_canon_ephemeral"
    assert result.cache_key == ""


def test_pck_raw_key_never_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CODEX_PCK_V1_FLAG, "true")
    result = _identity()
    assert _RAW_PCK not in repr(result)
    assert _RAW_PCK not in result.cache_key
    assert _RAW_PCK not in result.scoped_session_id
    assert len(result.cache_key) == 16


def test_pck_overlong_key_is_ephemeral(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(CODEX_PCK_V1_FLAG, "true")
    assert _identity(request={"prompt_cache_key": "k" * 513}).ephemeral


# --- B-25 -------------------------------------------------------------------


def test_b25_build_affinity_key_without_env_digest() -> None:
    key = build_affinity_key("o", "c", "b", "m", "e", "/w")
    assert isinstance(key, SlotAffinityKey)
    assert key.env_digest == ""
    assert key.review_profile == "standard"


def test_b25_build_affinity_key_with_env_digest_and_legacy_kwargs() -> None:
    key = build_affinity_key("o", "c", "b", "m", "e", "/w", env_digest="dg", is_ephemeral=True, driver_fingerprint="fp")
    assert key.env_digest == "dg"
    assert key.owner_hash == "o" and key.cwd_norm == "/w"


# --- B-24 -------------------------------------------------------------------


def _pool_env(**extra: str) -> dict[str, str]:
    env = {CODEX_POOL_UNIFIED_CAP_FLAG: "true", "BRIDGE_DYNAMIC_CONFIG_PATH": os.environ["BRIDGE_DYNAMIC_CONFIG_PATH"]}
    env.update(extra)
    return env


def test_b24_unified_cap_flag_on_reads_flat_max_concurrent() -> None:
    env = _pool_env()
    out = _align_codex_v2_pool_slots(StdioPoolConfig.from_env(env), env, {"max_concurrent": 10})
    assert out.max_slots == 10
    assert out.max_ephemeral_slots == 10


def test_b24_unified_cap_flag_on_respects_env_override() -> None:
    env = _pool_env(BRIDGE_STDIO_MAX_SLOTS="3", BRIDGE_STDIO_MAX_EPHEMERAL_SLOTS="5")
    base = StdioPoolConfig.from_env(env)
    out = _align_codex_v2_pool_slots(base, env, {"max_concurrent": 10})
    assert (out.max_slots, out.max_ephemeral_slots) == (base.max_slots, base.max_ephemeral_slots)


def test_b24_unified_cap_flag_on_clamps_to_total_cap() -> None:
    env = _pool_env()
    out = _align_codex_v2_pool_slots(StdioPoolConfig.from_env(env), env, {"max_concurrent": 64})
    assert out.max_slots <= 20 and out.max_ephemeral_slots <= 20


def test_b24_flag_off_keeps_legacy_behavior() -> None:
    env = _pool_env(**{CODEX_POOL_UNIFIED_CAP_FLAG: "false"})
    base = StdioPoolConfig.from_env(env)
    flat = _align_codex_v2_pool_slots(base, env, {"max_concurrent": 10})
    assert (flat.max_slots, flat.max_ephemeral_slots) == (4, 2)
    nested = _align_codex_v2_pool_slots(base, env, {"limits": {"max_concurrent": 6}})
    assert (nested.max_slots, nested.max_ephemeral_slots) == (6, 6)


def test_total_cap_non_ascii_digit_falls_back_to_default() -> None:
    assert _total_cap({"BRIDGE_CODEX_POOL_TOTAL_CAP": "\u00b2"}) == 20


def test_explicit_max_slots_clamps_ephemeral_slots() -> None:
    env = _pool_env(BRIDGE_STDIO_MAX_SLOTS="4")
    out = _align_codex_v2_pool_slots(StdioPoolConfig.from_env(env), env, {"max_concurrent": 20})
    assert out.max_ephemeral_slots == 4 <= out.max_slots == 4

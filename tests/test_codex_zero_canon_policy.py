"""Deterministic L1 corpus for Codex Zero-Canon policy, HTTP guards, redaction, and FS."""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import core.codex_zero_canon_policy as pol  # noqa: E402
import core.zero_canon_fs as zfs  # noqa: E402
import core.zero_canon_http as zhttp  # noqa: E402
from core.stdio_resident.sse_error_bridge import _sanitize_log_text  # noqa: E402
from core.stdio_resident.turn_error_sse import (  # noqa: E402
    build_turn_error,
    sanitize_error_message,
)

SOL, TERRA, V2, ZC = "gpt-6.1-sol", "gpt-6.1-terra", "codex-app-server-v2", "Zero-Canon"
DUMMY_KEY = "sk-dummy-test-000"
DUMMY_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.sig1234567890"
FLAG = "BRIDGE_CODEX_APP_SERVER_V2_ENABLED"
TOOL_ERR = "zero_canon_tool_event_forbidden"
PERR, HERR = pol.CodexZeroCanonPolicyError, zhttp.ZeroCanonHttpError


def test_effort_matrix_immutable_and_rejects_unsupported_without_clamp() -> None:
    """ADR-001 Policy: immutable Sol/Terra effort matrix, no clamp, no 6.2 alias."""
    assert pol.CODEX_EFFORT_MATRIX[SOL] == ("low", "medium", "high", "xhigh", "max")
    assert pol.CODEX_EFFORT_MATRIX[TERRA] == ("low", "medium", "high")
    with pytest.raises(TypeError, match="item assignment"):
        pol.CODEX_EFFORT_MATRIX[SOL] = ("high",)  # type: ignore[index]

    assert pol.validate_codex_model_effort("GPT-6.1-SOL", "MAX") == (SOL, "max")
    assert pol.validate_codex_model_effort(TERRA, None) == (TERRA, "high")
    with pytest.raises(PERR, match="Effort required"):
        pol.validate_codex_model_effort(TERRA, None, default_if_missing=False)

    bad_pairs = (
        (TERRA, "xhigh", "unsupported_model_effort"),
        (TERRA, "max", "unsupported_model_effort"),
        (SOL, "ultra", "unsupported_model_effort"),
        ("gpt-6.2-sol", "high", "unsupported_model"),
    )
    for model, effort, code in bad_pairs:
        with pytest.raises(PERR, match="Unsupported") as exc:
            pol.validate_codex_model_effort(model, effort)
        assert exc.value.code == code and exc.value.http_status == 400


def test_restrictions_request_sanitization_and_tool_event_block() -> None:
    """ADR-001 Policy: read-only/never/ephemeral DTOs, tool strip, fail-closed tool event."""
    dto = pol.build_zero_canon_restrictions(TERRA, "medium")
    assert dto.thread_start_params("/tmp/zc-1") == {
        "model": TERRA,
        "cwd": "/tmp/zc-1",
        "ephemeral": True,
        "sandbox": "read-only",
        "approvalPolicy": "never",
    }
    assert dto.turn_start_params() == {
        "model": TERRA,
        "effort": "medium",
        "approvalPolicy": "never",
        "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
    }
    with pytest.raises(PERR, match="non-empty cwd"):
        dto.thread_start_params("   ")

    req = {"model": SOL, "tools": [{"type": "function"}], "emulate_tools": True}
    assert pol.sanitize_strict_request(req) == {"model": SOL} and "tools" in req

    ok_ev = {"method": "item/agentMessage/delta", "params": {"delta": "PONG"}}
    assert pol.is_upstream_tool_event(ok_ev) is False
    pol.enforce_no_upstream_tool_event(ok_ev, strict=True)

    for bad in (
        {"method": "item/tool/call", "params": {}},
        {"method": "item/started", "params": {"item": {"type": "commandExecution"}}},
        {"is_tool_stop": True},
    ):
        assert pol.is_upstream_tool_event(bad) is True
        with pytest.raises(PERR, match="forbidden") as exc:
            pol.enforce_no_upstream_tool_event(bad, strict=True)
        assert exc.value.code == TOOL_ERR


def test_attestation_receipt_identity_drift_and_header_roundtrip() -> None:
    """ADR-001 Policy: requested!=actual fails; completed requires terminal_status=completed."""
    req = pol.RequestedTurnSpec(SOL, "xhigh")
    obs = pol.ActualTurnObservation(SOL, "xhigh", terminal_status="completed")
    admitted = pol.build_attestation_receipt(req, obs, phase="admitted")
    completed = pol.build_attestation_receipt(req, obs, phase="completed")
    assert admitted.is_complete is False and completed.is_complete is True
    assert completed.to_dict()["route_id"] == V2

    hdr = pol.format_attestation_header(SOL, "xhigh", phase="completed")
    assert pol.parse_attestation_header(hdr) == {
        "profile": "zero-canon",
        "backend": "codex",
        "tools": "off",
        "sandbox": "read-only",
        "approval": "never",
        "model": SOL,
        "effort": "xhigh",
        "phase": "completed",
    }

    drift = pol.ActualTurnObservation(SOL, "high")
    with pytest.raises(PERR, match="Identity mismatch"):
        pol.build_attestation_receipt(req, drift, phase="admitted")
    failed = pol.ActualTurnObservation(SOL, "xhigh", terminal_status="failed")
    with pytest.raises(PERR, match="terminal_status"):
        pol.build_attestation_receipt(req, failed, phase="completed")
    with pytest.raises(PERR, match="Malformed"):
        pol.parse_attestation_header("profile=zero-canon;broken")


def test_error_taxonomy_and_no_replay_after_first_byte() -> None:
    """ADR-001 Error taxonomy: protocol-agnostic classes and bytes_sent>0 prohibition."""
    cases = (
        ("No available accounts", 503, None, "credential_unavailable", True, False),
        ("HTTP 429 Retry-After: 5", 429, None, "rate_limit_transient", True, True),
        ("429 insufficient_quota", 429, None, "quota_exhausted", True, False),
        ("429 mysterious limit", 429, None, "rate_limit_unknown", False, False),
        ("EOF empty done", None, None, "upstream_incomplete_stream", True, False),
        ("malformed json", None, None, "resident_protocol_failed", True, False),
        ("timed out", None, "first_progress", "first_progress_timeout", True, False),
        ("timed out", None, "idle", "idle_timeout", True, False),
        ("timed out", None, "safety_cap", "safety_cap_timeout", True, False),
        (TOOL_ERR, None, None, TOOL_ERR, False, False),
    )
    for msg, status, tkind, cls, pre_fo, pre_retry in cases:
        pre = pol.classify_error(msg, status_code=status, timeout_kind=tkind)
        post = pol.classify_error(
            msg, status_code=status, timeout_kind=tkind, bytes_sent=1
        )
        assert pre.error_class == cls
        assert (pre.allow_same_model_failover, pre.retryable) == (pre_fo, pre_retry)
        assert (post.allow_same_model_failover, post.retryable) == (False, False)
        assert (pre.record_success, pre.clear_penalty) == (False, False)


def test_http_profile_and_provider_filter() -> None:
    """ADR-001 AD-014: strict profile 400 on typos; filter excludes openai-key-3 & V2-off 503."""
    assert zhttp.parse_strict_review_profile(None) == "standard"
    assert zhttp.parse_strict_review_profile("  zero-canon ") == ZC
    with pytest.raises(HERR, match="invalid_review_profile") as exc400:
        zhttp.parse_strict_review_profile("Zero_Canon")
    assert exc400.value.http_status == 400
    mixed = {"X-Review-Profile": "standard", "x-review-profile": ZC}
    with pytest.raises(HERR, match="conflicting"):
        zhttp.parse_review_profile_headers(mixed)

    routes = [
        {"backend": "openai-key-3", "base_url": "https://api.openai.com/v1"},
        {"backend": "sg-openai", "base_url": "http://127.0.0.1:8080/sg-openai/v1"},
        {"backend": "codex", "route_id": V2, "backend_kind": "stdio_resident"},
    ]
    std_kept = zhttp.filter_zero_canon_providers(
        routes, "standard", codex_v2_enabled=False
    )
    assert len(std_kept) == 3
    with pytest.raises(HERR, match="zero_canon_unsupported_by_driver") as exc503:
        zhttp.filter_zero_canon_providers(
            routes, ZC, codex_v2_enabled=False, model_id=SOL
        )
    assert exc503.value.http_status == 503
    kept = zhttp.filter_zero_canon_providers(
        routes, ZC, codex_v2_enabled=True, model_id=SOL
    )
    assert [r["route_id"] for r in kept] == [V2]


def test_http_spoof_strip_and_two_phase_proof() -> None:
    """ADR-001 Cycle 4: strip upstream attestation; two-phase admitted/completed proof."""
    hdrs = {"X-Zero-Canon-Attestation": "spoof", "X-Ok": "1"}
    assert zhttp.strip_upstream_attestation(hdrs) == {"X-Ok": "1"}
    adm = zhttp.ZeroCanonAdmissionProof(
        SOL, "high", "thr-9", "trn-9", clean_home_verified=True, handshake_acked=True
    )
    assert "phase=admitted" in zhttp.build_attestation_header(adm, phase="admitted")
    comp = zhttp.ZeroCanonCompletionProof(
        adm, terminal_status="completed", tool_events_seen=0
    )
    assert "phase=completed" in zhttp.build_attestation_header(comp, phase="completed")
    bad = zhttp.ZeroCanonAdmissionProof(
        SOL, "high", "th-1", "t1", clean_home_verified=True, handshake_acked=True
    )
    with pytest.raises(HERR, match="threadId"):
        zhttp.build_attestation_header(bad)


def test_secret_redaction_and_fs_nofollow_gigarc(tmp_path: Path) -> None:
    """ADR-001 Stream/FS: redact before truncation, O_NOFOLLOW+0o600, GigaRC precedence."""
    raw = f"{TOOL_ERR} Bearer {DUMMY_KEY} apiKey={DUMMY_KEY} jwt={DUMMY_JWT}"
    msg_out = sanitize_error_message(raw, max_chars=50)
    log_out = _sanitize_log_text(raw, extra_code=TOOL_ERR, max_chars=50)
    for out in (msg_out, log_out):
        assert DUMMY_KEY not in out and DUMMY_JWT not in out and TOOL_ERR in out

    mid = build_turn_error(RuntimeError(raw), live_sent=1, max_chars=60)
    assert mid.status == 200 and mid.code == TOOL_ERR
    assert DUMMY_KEY not in mid.sse and DUMMY_JWT not in mid.sse

    auth = tmp_path / "auth.json"
    zfs.write_atomic_0600(auth, json.dumps({"api_key": DUMMY_KEY}).encode("utf-8"))
    assert stat.S_IMODE(auth.stat().st_mode) == 0o600
    assert DUMMY_KEY.encode("utf-8") in zfs.read_regular_file_nofollow(auth)
    link = tmp_path / "auth_link.json"
    link.symlink_to(auth)
    with pytest.raises(OSError, match=".*"):
        zfs.read_regular_file_nofollow(link)
    with pytest.raises(FileExistsError, match=".*"):
        zfs.write_atomic_0600(auth, b"{}")

    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(json.dumps({FLAG: False}), encoding="utf-8")
    env_on = {FLAG: "true"}
    assert zfs.read_gigarc_bool(FLAG, cfg, environ=env_on, default=False) is False
    bad_cfg = tmp_path / "broken.json"
    bad_cfg.write_text("{not-json", encoding="utf-8")
    assert zfs.read_gigarc_bool(FLAG, bad_cfg, environ=env_on, default=False) is False

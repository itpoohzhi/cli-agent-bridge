"""Live-isolated L5 E2E verification for real Codex app-server v2 & Zero-Canon (W3-F)."""

# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false

from __future__ import annotations

import json
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(shutil.which("codex") is None, reason="real codex binary not found in PATH")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import codex_recovery_fsm as rec  # noqa: E402
from core import route_catalog_contract as rcc  # noqa: E402
from core import zero_canon_fs as zfs  # noqa: E402
from core import zero_canon_http as zhttp  # noqa: E402
from core.codex_zero_canon_policy import (  # noqa: E402
    ATTESTATION_HEADER,
    CodexZeroCanonPolicyError,
    validate_codex_model_effort,
)
from core.stdio_resident.process_reaper import is_pgid_alive  # noqa: E402
from tests._codex_l5_helpers import (  # noqa: E402
    ATTEST_LOW,
    EXPECTED_VER,
    PROTECTED_FILES,
    IsolatedL5Stand,
    http_post,
    open_fd_count,
    run_same_model_cli_fallback,
    sha256_file,
    verify_seat_response,
)


def _assert_gpt62_policy_and_unknown_rejected(stand: IsolatedL5Stand) -> None:
    assert "gpt-6.2-sol" in rcc.FORBIDDEN_ALIAS_MODEL_IDS
    rcc.validate_no_forbidden_aliases(json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))["aliases"])
    assert validate_codex_model_effort("gpt-6.2-sol", "high") == ("gpt-6.2-sol", "high")
    assert validate_codex_model_effort("gpt-6.2-sol", None) == ("gpt-6.2-sol", "high")
    with pytest.raises(CodexZeroCanonPolicyError, match="Unsupported Codex model"):
        _ = validate_codex_model_effort("gpt-6.9-unsupported", "high")
    reqs_before = len(stand.upstream_reqs)
    s_bad, h_bad, b_bad = http_post(stand.hub_url, {"model": "gpt-6.9-unsupported", "reasoning_effort": "high", "messages": [{"role": "user", "content": "PONG"}]}, {"X-Review-Profile": "Zero-Canon"})
    assert (s_bad in (400, 404), ATTEST_LOW in h_bad, len(stand.upstream_reqs), bool(b_bad)) == (True, False, reqs_before, True)


def _assert_ports_closed(ports: tuple[int, int]) -> None:
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0


def test_l5_real_codex_version_and_sol_terra_pong(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L5-01: Real codex 0.171.0-alpha.13 app-server Sol/Terra PONG with ephemeral clean-home & attestation."""
    stand = IsolatedL5Stand(tmp_path, monkeypatch)
    try:
        cp = subprocess.run([stand.codex_bin, "--version"], capture_output=True, text=True, timeout=10.0, start_new_session=True, check=False)
        assert (cp.returncode, EXPECTED_VER in cp.stdout) == (0, True)
        hdrs = {"X-Review-Profile": "Zero-Canon"}
        s1, h1, b1 = http_post(stand.hub_url, {"model": "gpt-6.1-sol", "reasoning_effort": "high", "stream": True, "messages": [{"role": "user", "content": "Reply PONG"}]}, hdrs)
        ok1, txt1 = verify_seat_response(s1, h1, b1, ("gpt-6.1-sol", "high", True))
        assert (ok1, "PONG" in txt1, "phase=admitted" in h1[ATTEST_LOW]) == (True, True, True)
        s2, h2, b2 = http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": False, "messages": [{"role": "user", "content": "Reply PONG"}]}, hdrs)
        ok2, txt2 = verify_seat_response(s2, h2, b2, ("gpt-6.1-terra", "medium", False))
        assert (ok2, "PONG" in txt2, "phase=completed" in h2[ATTEST_LOW]) == (True, True, True)
        assert [(b.get("model"), (b.get("reasoning") or {}).get("effort")) for _, b in stand.upstream_reqs] == [("gpt-6.1-sol", "high"), ("gpt-6.1-terra", "medium")]
        assert len(set(stand.spawned_pgids)) == 2
    finally:
        stand.close()
    assert all(not is_pgid_alive(p) for p in stand.spawned_pgids)


def test_l5_terra_arl_r1_d1_medium_and_launch_seat_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L5-02/04: Terra ARL R1->D1 medium through isolated hub + launch_seat/proof atomic receipt."""
    stand = IsolatedL5Stand(tmp_path, monkeypatch)
    try:
        s_bad, _, b_bad = http_post(stand.hub_url, {"model": "gpt-6.1-terra", "messages": [{"role": "user", "content": "x"}]}, {"X-Review-Profile": "Zero_Canon"})
        assert (s_bad, "invalid_review_profile" in b_bad) == (400, True)
        hdrs = {"X-Review-Profile": "Zero-Canon"}
        s_r1, h_r1, b_r1 = http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": True, "messages": [{"role": "user", "content": "ARL_R1"}]}, hdrs)
        ok_r1, txt_r1 = verify_seat_response(s_r1, h_r1, b_r1, ("gpt-6.1-terra", "medium", True))
        assert (ok_r1, "R1_FINDING" in txt_r1) == (True, True)
        s_d1, h_d1, b_d1 = http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": False, "messages": [{"role": "user", "content": f"ARL_D1 {txt_r1}"}]}, hdrs)
        ok_d1, txt_d1 = verify_seat_response(s_d1, h_d1, b_d1, ("gpt-6.1-terra", "medium", False))
        assert (ok_d1, "D1_DECISION: ACCEPT" in txt_d1) == (True, True)
        pdir = tmp_path / "panel_proof"
        zfs.ensure_private_dir(pdir, 0o700)
        zfs.write_atomic_text_0600(pdir / "seat_d1.txt", txt_d1)
        digest = sha256_file(pdir / "seat_d1.txt")
        zfs.write_atomic_text_0600(pdir / "proof_receipt.json", json.dumps({"model": "gpt-6.1-terra", "effort": "medium", "r1": h_r1[ATTEST_LOW], "d1": h_d1[ATTEST_LOW], "sha256": digest}))
        assert stat.S_IMODE((pdir / "proof_receipt.json").stat().st_mode) == 0o600
        assert json.loads(zfs.read_regular_file_nofollow(pdir / "proof_receipt.json").decode())["sha256"] == digest
        assert ATTEST_LOW not in {k.lower() for k in zhttp.strip_upstream_attestation({ATTESTATION_HEADER: "spoof", "X-Ok": "1"})}
    finally:
        stand.close()
    assert all(not is_pgid_alive(p) for p in stand.spawned_pgids)


def test_l5_same_model_bridge_to_cli_fallback_with_pgid_teardown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L5-03: V2-off 503 fails attestation -> proven PGID teardown -> same-model codex CLI fallback."""
    stand = IsolatedL5Stand(tmp_path, monkeypatch)
    cli_pgid = 0
    try:
        stand.v2_enabled = False
        st, hdrs, body = http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": False, "messages": [{"role": "user", "content": "Reply PONG"}]}, {"X-Review-Profile": "Zero-Canon"})
        assert (st, "zero_canon_unsupported_by_driver" in body, ATTEST_LOW in hdrs) == (503, True, False)
        assert verify_seat_response(st, hdrs, body, ("gpt-6.1-terra", "medium", False)) == (False, "zero_canon_attestation_failed")
        assert all(not is_pgid_alive(p) for p in stand.spawned_pgids)
        rc, out_txt, cli_pgid = run_same_model_cli_fallback(stand, "gpt-6.1-terra", "medium", "Reply PONG")
        assert (rc, "PONG" in out_txt) == (0, True)
        assert [(b.get("model"), (b.get("reasoning") or {}).get("effort")) for _, b in stand.upstream_reqs] == [("gpt-6.1-terra", "medium")]
    finally:
        stand.close()
    assert (cli_pgid > 0, is_pgid_alive(cli_pgid)) == (True, False)


def test_l5_recovery_pong_readback_gpt62_negative_and_hygiene(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L5-05/06/07: Recovery PONG receipt read-back, gpt-6.2-sol negative, and zero-leak hygiene."""
    before_hashes, fd_before = {rel: sha256_file(ROOT / rel) for rel in PROTECTED_FILES}, open_fd_count()
    stand = IsolatedL5Stand(tmp_path, monkeypatch)
    ports = (stand.hub_srv.server_address[1], stand.up_srv.server_address[1])
    try:
        exp = rec.ProbeExpectation("gpt-6.1-terra", "medium", "codex", rcc.CODEX_V2_ROUTE_ID, "zero-canon")
        st = rec.create_recovery_state(exp, "cred-l5", rec.RecoveryPhase.BLOCKED, rec.RecoveryPhase.HEALTHY)
        st, _ = rec.transition(st, rec.RecoveryEvent(rec.RecoveryEventKind.SCHEDULE_PROBE, 1.0, rec.HealthDomain.ROUTE))
        st, _ = rec.transition(st, rec.RecoveryEvent(rec.RecoveryEventKind.PROBE_STARTED, 2.0, rec.HealthDomain.ROUTE, probe_id="probe-l5"))
        st_rej, eff_rej = rec.transition(st, rec.RecoveryEvent(rec.RecoveryEventKind.NON_PONG_SIGNAL, 3.0, rec.HealthDomain.ROUTE, evidence_kind=rec.EvidenceKind.HEALTH_200))
        assert (st_rej.is_route_healthy, eff_rej[0].kind) == (False, rec.RecoveryEffectKind.REJECT_TRANSITION)
        code, hdrs, body = http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": False, "messages": [{"role": "user", "content": "Reply PONG"}]}, {"X-Review-Profile": "Zero-Canon"})
        ok, content = verify_seat_response(code, hdrs, body, ("gpt-6.1-terra", "medium", False))
        assert ok
        rcpt_path = tmp_path / "recovery_pong_receipt.json"
        zfs.write_atomic_text_0600(rcpt_path, json.dumps({"probe_id": "probe-l5", "model": "gpt-6.1-terra", "effort": "medium", "attestation": hdrs[ATTEST_LOW], "content": content}))
        rb = json.loads(zfs.read_regular_file_nofollow(rcpt_path).decode("utf-8"))
        pong = rec.PongReceipt(rb["probe_id"], rb["model"], rb["model"], rb["effort"], rb["effort"], "codex", rcc.CODEX_V2_ROUTE_ID, "zero-canon", rb["attestation"], True, True, rb["content"])
        healthy, effs = rec.transition(st, rec.RecoveryEvent(rec.RecoveryEventKind.PONG_RECEIPT, 4.0, rec.HealthDomain.ROUTE, receipt=pong))
        assert healthy.is_healthy
        assert any(e.kind is rec.RecoveryEffectKind.EMIT_RECOVERY_RECEIPT for e in effs)
        _assert_gpt62_policy_and_unknown_rejected(stand)
    finally:
        stand.close()
    assert all(not is_pgid_alive(p) for p in stand.spawned_pgids)
    _assert_ports_closed(ports)
    assert {rel: sha256_file(ROOT / rel) for rel in PROTECTED_FILES} == before_hashes
    assert open_fd_count() <= fd_before + 4

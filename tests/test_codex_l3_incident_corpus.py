"""Sanitized L3 incident corpus for Codex app-server v2 & Zero-Canon (W3-D)."""

from __future__ import annotations

import json
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import codex_recovery_fsm as rec  # noqa: E402
from core import route_catalog_contract as rcc  # noqa: E402
from core import zero_canon_fs as zfs  # noqa: E402
from core import zero_canon_http as zhttp  # noqa: E402
from core.codex_zero_canon_policy import (  # noqa: E402
    ActualTurnObservation,
    CodexZeroCanonPolicyError,
    RequestedTurnSpec,
    build_attestation_receipt,
    classify_error,
)
from core.routing_contract import parse_routes as parse_routing_routes  # noqa: E402
from core.stdio_resident.codex_driver import CodexAppServerV2Driver  # noqa: E402
from core.stdio_resident.process_io import EOF, LINE, TaggedLine  # noqa: E402
from core.stdio_resident.session_manager import StdioSessionManager  # noqa: E402
from core.stdio_resident.sse_error_bridge import (  # noqa: E402
    SseErrorContext,
    handle_sse_stream_exception,
)
from core.stdio_resident.turn_error_sse import (  # noqa: E402
    DONE_FRAME,
    build_turn_error,
    sanitize_error_message,
)
from core.stdio_resident.types import SlotAffinityKey  # noqa: E402
from core.transport_routing import route_order  # noqa: E402
from scripts import sync_codex_catalog  # noqa: E402

DUMMY_KEY = "sk-dummy-test-000"
DUMMY_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJkdW1teSJ9.dummysignature000"


class _FakeHandle:
    """In-memory stdio handle without subprocesses, sockets, or sleeps."""

    def __init__(self, lines: list[TaggedLine]) -> None:
        self._lines, self.written = list(lines), list[dict[str, Any]]()
        self.pid, self.generation, self._pgid_dead = 4242, 0, True

    def write(self, data: bytes) -> None:
        self.written.extend(json.loads(ln) for ln in data.decode("utf-8").splitlines() if ln.strip())

    def read_stdout_line(self, timeout_s: float | None = None) -> TaggedLine | None:
        _ = timeout_s
        while self._lines:
            item = self._lines.pop(0)
            if not item.is_stderr:
                return item
        return None

    def read_line_outcome(self, timeout_s: float | None = None) -> tuple[str, TaggedLine | None]:
        _ = timeout_s
        return (LINE, self._lines.pop(0)) if self._lines else (EOF, None)


@dataclass
class _FakeSlot:
    slot_id: str
    handle: _FakeHandle
    affinity_key: SlotAffinityKey
    lease_id: str = "lease-1"


class _FakePool:
    def __init__(self, handle: _FakeHandle) -> None:
        self._handle = handle
        self.releases: list[tuple[str, bool, bool]] = []

    def acquire(self, key: SlotAffinityKey, *_args: Any, **_kwargs: Any) -> _FakeSlot:
        return _FakeSlot("slot-1", self._handle, key)

    def release(self, slot_id: str, *, success: bool = False, cancel: bool = False, **_kw: Any) -> None:
        self.releases.append((slot_id, success, cancel))


class _FakeLease:
    def __init__(self) -> None:
        self.failures: list[BaseException] = []
        self.discards: list[str] = []

    def record_failure(self, exc: BaseException) -> None:
        self.failures.append(exc)

    def record_discard(self, reason: str) -> None:
        self.discards.append(reason)


def _line(payload: dict[str, Any] | str, *, is_stderr: bool = False) -> TaggedLine:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return TaggedLine(line=raw, generation=0, pid=4242, is_stderr=is_stderr)


def _affinity(profile: str = "standard") -> SlotAffinityKey:
    return SlotAffinityKey("owner", "chat-1", "codex", "gpt-6.1-sol", "high", "/tmp", profile)


def test_incident_empty_sse_eof_fails_with_incomplete_stream_and_blocks_recovery() -> None:
    """L3-01: Empty SSE / EOF before turn/completed yields 502 upstream_incomplete_stream."""
    handle = _FakeHandle([
        _line({"id": 1, "result": {"userAgent": "codex/0.171.0-alpha.13"}}),
        _line({"id": 2, "result": {"thread": {"id": "thr-srv-1"}, "model": "gpt-6.1-sol"}}),
        _line({"id": 3, "result": {"turn": {"id": "trn-srv-1", "status": "inProgress"}}}),
    ])
    pool = _FakePool(handle)
    mgr = StdioSessionManager(pool, CodexAppServerV2Driver())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="ended before the terminal marker") as exc_info:
        mgr.execute_turn(_affinity(), "PONG", lambda: ["codex", "app-server"], "/tmp")
    resp = build_turn_error(exc_info.value, live_sent=0)
    assert (resp.status, resp.code, resp.error_type) == (502, "upstream_incomplete_stream", "upstream_error")
    assert resp.sse.endswith(DONE_FRAME) and pool.releases == [("slot-1", False, True)]

    exp = rec.ProbeExpectation("gpt-6.1-terra", "medium", "codex", "codex-app-server-v2", "zero-canon")
    st = rec.create_recovery_state(exp, "cred-1", rec.RecoveryPhase.PONG_IN_FLIGHT, rec.RecoveryPhase.HEALTHY)
    ev = rec.RecoveryEvent(rec.RecoveryEventKind.NON_PONG_SIGNAL, 10.0, rec.HealthDomain.ROUTE, evidence_kind=rec.EvidenceKind.EMPTY_DONE)
    nxt, effs = rec.transition(st, ev)
    assert nxt.is_route_healthy is False and effs[0].kind is rec.RecoveryEffectKind.REJECT_TRANSITION


def test_incident_typed_503_accounts_and_v2_flag_off_isolation() -> None:
    """L3-02: Typed 503 preserves credential_unavailable and zero_canon_unsupported_by_driver."""
    pre = classify_error("HTTP 503 No available accounts", status_code=503, bytes_sent=0)
    post = classify_error("HTTP 503 No available accounts", status_code=503, bytes_sent=12)
    assert (pre.http_status, pre.error_class, pre.scope, pre.allow_same_model_failover) == (503, "credential_unavailable", "credential", True)
    assert post.allow_same_model_failover is False

    resp_acc = build_turn_error(RuntimeError("503 No available accounts"), live_sent=0)
    assert (resp_acc.status, resp_acc.code, resp_acc.error_type) == (503, "credential_unavailable", "service_unavailable")

    providers = [
        {"route_id": "openai-key-3", "backend": "openai-key-3", "kind": "passthrough", "base_url": "http://127.0.0.1:10830/sg-openai"},
        {"route_id": "codex-app-server-v2", "backend": "codex", "kind": "stdio_resident"},
    ]
    with pytest.raises(zhttp.ZeroCanonHttpError, match="zero_canon_unsupported_by_driver") as err:
        zhttp.filter_zero_canon_providers(providers, "Zero-Canon", codex_v2_enabled=False, model_id="gpt-6.1-sol")
    assert err.value.status_code == 503
    resp_v2 = build_turn_error(err.value, live_sent=0)
    assert (resp_v2.status, resp_v2.code) == (503, "zero_canon_unsupported_by_driver")

    st = rec.create_recovery_state(rec.ProbeExpectation("gpt-6.1-sol"), "cred-1", rec.RecoveryPhase.HEALTHY, rec.RecoveryPhase.HEALTHY)
    nxt, _ = rec.transition(st, rec.RecoveryEvent(rec.RecoveryEventKind.FAILURE, 20.0, error_code="credential_unavailable"))
    assert nxt.is_route_healthy is True and nxt.is_credential_healthy is False


def test_incident_handshake_502_with_stderr_banner_and_redacted_diagnostics() -> None:
    """L3-03: Handshake skips noisy stderr on success, maps RPC error + stderr to redacted 502."""
    ok_driver = CodexAppServerV2Driver()
    ok_handle = _FakeHandle([
        _line(f"WARN startup Bearer {DUMMY_KEY}", is_stderr=True),
        _line({"id": 1, "result": {"userAgent": "codex/0.171.0-alpha.13"}}),
    ])
    assert ok_driver.run_handshake(ok_handle, timeout_s=1.0) is True
    assert [frame.get("method") for frame in ok_handle.written] == ["initialize", "initialized"]

    bad_handle = _FakeHandle([
        _line(f"FATAL stderr api_key={DUMMY_KEY}", is_stderr=True),
        _line({"id": 1, "error": {"code": -32000, "message": f"init failed Bearer {DUMMY_KEY}"}}),
    ])
    mgr = StdioSessionManager(_FakePool(bad_handle), CodexAppServerV2Driver())  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="protocol handshake failed") as exc_info:
        mgr.execute_turn(_affinity(), "PONG", lambda: ["codex", "app-server"], "/tmp")
    resp = build_turn_error(RuntimeError(f"{exc_info.value}; stderr=Bearer {DUMMY_KEY}"), live_sent=0)
    assert (resp.status, resp.code, resp.error_type) == (502, "resident_protocol_failed", "upstream_error")
    assert DUMMY_KEY not in resp.sse and DUMMY_KEY not in resp.message


def test_incident_routing_invalid_and_profile_typo_fail_closed() -> None:
    """L3-04: Malformed routing metadata, secret fields, and profile typos fail closed."""
    bad_model: dict[str, Any] = {"id": "gpt-6.1-sol", "routing": "corrupted"}
    with pytest.raises(ValueError, match="routing_invalid"):
        list(route_order("gpt-6.1-sol", bad_model, "seed-1"))
    with pytest.raises(ValueError, match="routing_invalid"):
        parse_routing_routes(bad_model)
    with pytest.raises(ValueError, match="routing_algorithm_invalid"):
        list(route_order("gpt-6.1-sol", {"routing": {"enabled": True, "algorithm": "bad"}}, "s"))
    raw_secret = {
        "route_id": "codex-app-server-v2",
        "backend": "codex",
        "backend_kind": "stdio_resident",
        "upstream_contract": rcc.CODEX_APP_SERVER_V2_CONTRACT,
        "api_key": DUMMY_KEY,
    }
    with pytest.raises(rcc.RouteCatalogContractError, match="secret_field_forbidden"):
        rcc.VersionedRouteEntry.from_mapping(raw_secret, reject_secrets=True)
    with pytest.raises(zhttp.ZeroCanonHttpError, match="invalid_review_profile") as exc:
        zhttp.parse_strict_review_profile("Zero_Canon")
    assert exc.value.status_code == 400


def test_incident_incomplete_success_never_attests_or_marks_stop() -> None:
    """L3-05: Mid-stream failures, non-completed turns, and tool events never emit stop or attestation."""
    emitted, logs, lease = list[str](), list[str](), _FakeLease()
    handler = type("_H", (), {"_headers_already_sent": True, "_client_write_dead": False, "_response_status": 200})()
    ctx = SseErrorContext(
        handler=handler,
        lease=lease,
        emit=lambda chunk: (emitted.append(chunk), True)[1],
        stream_error_frame=lambda msg, **kw: json.dumps({"error": msg, **kw}),
        log_fn=logs.append,
    )
    handled = handle_sse_stream_exception(RuntimeError(f"zero_canon_tool_event_forbidden Bearer {DUMMY_KEY}"), 42, ctx)
    assert handled is True and len(lease.failures) == 1
    err_payload = json.loads(emitted[0])
    assert err_payload["code"] == "zero_canon_tool_event_forbidden" and err_payload["finish_reason"] is None
    assert emitted[-1] == DONE_FRAME and DUMMY_KEY not in emitted[0] and all(DUMMY_KEY not in ln for ln in logs)

    adm = zhttp.ZeroCanonAdmissionProof("gpt-6.1-sol", "high", "thr-srv-1", "trn-srv-1", clean_home_verified=True, handshake_acked=True)
    with pytest.raises(zhttp.ZeroCanonHttpError, match="zero_canon_attestation_failed"):
        zhttp.build_attestation_header(zhttp.ZeroCanonCompletionProof(adm, terminal_status="failed"), phase="completed")
    with pytest.raises(CodexZeroCanonPolicyError, match="terminal_status"):
        build_attestation_receipt(
            RequestedTurnSpec("gpt-6.1-sol", "high"),
            ActualTurnObservation("gpt-6.1-sol", "high", thread_id="thr-1", turn_id="trn-1", terminal_status="inProgress"),
            phase="completed",
        )


def test_incident_symlink_barriers_fail_closed_across_fs_and_catalog(tmp_path: Path) -> None:
    """L3-06: Symlinks in auth.json, config.toml, atomic writes, and fleet check fail closed."""
    outside = tmp_path / "outside.txt"
    outside.write_text(DUMMY_KEY, encoding="utf-8")
    link = tmp_path / "sym.txt"
    link.symlink_to(outside)
    with pytest.raises(OSError):
        zfs.read_regular_file_nofollow(link)
    with pytest.raises(OSError):
        zfs.write_atomic_0600(link, b"override")
    assert outside.read_text(encoding="utf-8") == DUMMY_KEY

    codex_dir = tmp_path / "home" / ".codex"
    codex_dir.mkdir(parents=True, mode=0o700)
    (codex_dir / "config.toml").symlink_to(outside)
    with pytest.raises(OSError):
        zfs.prepare_codex_zero_canon_home({"HOME": str(tmp_path / "home"), "CODEX_HOME": str(codex_dir)}, tmp_path / "zc-1")

    (codex_dir / "config.toml").unlink()
    (codex_dir / "config.toml").write_text('[hooks]\non_turn = "x"\n', encoding="utf-8")
    (codex_dir / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": DUMMY_KEY}), encoding="utf-8")
    env = zfs.prepare_codex_zero_canon_home({"HOME": str(tmp_path / "home"), "CODEX_HOME": str(codex_dir)}, tmp_path / "zc-ok")
    assert stat.S_IMODE((Path(env["CODEX_HOME"]) / "auth.json").stat().st_mode) == 0o600
    assert "hooks" not in (Path(env["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8")

    fleet_link = tmp_path / "fleet_link.json"
    fleet_link.symlink_to(ROOT / "fleet.json")
    ok, detail = sync_codex_catalog.check_fleet_file(fleet_link, sync_codex_catalog.generate_fleet())
    assert ok is False and "fleet_unreadable" in detail


def test_incident_secret_redaction_before_truncation_and_spoof_strip() -> None:
    """L3-07: Synthetic secrets are redacted before truncation while preserving error codes."""
    raw = f"upstream_incomplete_stream prefix {'x' * 30} Bearer {DUMMY_KEY} jwt={DUMMY_JWT}"
    short = sanitize_error_message(raw, max_chars=70)
    assert "upstream_incomplete_stream" in short
    assert DUMMY_KEY not in short and "sk-dummy" not in short and "eyJhbGci" not in short

    resp = build_turn_error(RuntimeError(raw), live_sent=0, max_chars=70)
    assert resp.code == "upstream_incomplete_stream"
    for blob in (resp.message, resp.sse, json.dumps(resp.body)):
        assert DUMMY_KEY not in blob and DUMMY_JWT not in blob

    cleaned = zhttp.strip_upstream_attestation(
        [("X-Zero-Canon-Attestation", "profile=zero-canon;backend=fake"), ("X-Trace-Id", "t-1")]
    )
    assert cleaned == [("X-Trace-Id", "t-1")]
    with pytest.raises(rcc.RouteCatalogContractError):
        rcc.ModelCapability("bad id!", ("high",), "high")

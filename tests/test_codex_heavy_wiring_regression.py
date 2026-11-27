"""Regression tests for W7/W8/W9 Heavy Path live HTTP/manifest wiring and fail-closed gates."""

from __future__ import annotations

import json
import sys
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.stdio_resident_adapter import StdioResidentAdapter  # noqa: E402
from core.backend_adapter import TurnContext  # noqa: E402
from core.catalog_flags import GatedCatalog  # noqa: E402
from core.gated_registry import gated_catalog  # noqa: E402
from core.stdio_resident.codex_attestation_wire import (  # noqa: E402
    ZeroCanonSseHeaderGate, record_v2_turn_completion, should_defer_zero_canon_sse_headers, wrap_v2_sse_writer,
)
from core.stdio_resident.codex_driver import _build_codex_argv  # noqa: E402
from core.stdio_resident.codex_protocol_fsm import ProtocolPhase, ProtocolState  # noqa: E402
from core.stdio_resident.turn_error_sse import ResidentTurnError, build_turn_error  # noqa: E402
from core.stdio_resident.zero_canon_router import execute_routed_turn  # noqa: E402
from core.zc_admission import TurnProofRecorder  # noqa: E402
from core.zero_canon_attestation_http import ZeroCanonAdmissionProof, ZeroCanonHttpError, build_attestation_header  # noqa: E402

TERRA, DUMMY_KEY = "gpt-6.1-terra", "sk-dummy-test-000"
EXPECTED_ADMITTED = "profile=zero-canon;backend=codex;tools=off;sandbox=read-only;approval=never;model=gpt-6.1-terra;effort=medium;phase=admitted"
EXPECTED_COMPLETED = "profile=zero-canon;backend=codex;tools=off;sandbox=read-only;approval=never;model=gpt-6.1-terra;effort=medium;phase=completed"
_FAKE_CODEX_V2 = (
    "import argparse, json, sys\n"
    "p = argparse.ArgumentParser(); p.add_argument('--mode', default='ok')\n"
    "args, _ = p.parse_known_args()\n"
    "emit = lambda o: (sys.stdout.write(json.dumps(o, separators=(',', ':')) + '\\n'), sys.stdout.flush())\n"
    "tid, turn_id = 'thr-srv-heavy-1', 'trn-srv-heavy-1'\n"
    "for raw in sys.stdin:\n"
    "    if not raw.strip(): continue\n"
    "    msg = json.loads(raw); m, rid, pr = msg.get('method'), msg.get('id'), msg.get('params') or {}\n"
    "    if m == 'initialize': emit({'id': rid, 'result': {'userAgent': 'codex/0.171.0-alpha.13'}})\n"
    "    elif m == 'thread/start': emit({'id': rid, 'result': {'thread': {'id': tid}, 'model': pr.get('model') or 'gpt-6.1-terra'}})\n"
    "    elif m == 'turn/start':\n"
    "        emit({'id': rid, 'result': {'turn': {'id': turn_id, 'status': 'inProgress'}}})\n"
    "        if args.mode == 'tool_event':\n"
    "            emit({'method': 'item/tool/call', 'params': {'threadId': tid, 'turnId': turn_id, 'name': 'sh'}}); break\n"
    "        emit({'method': 'item/agentMessage/delta', 'params': {'threadId': tid, 'turnId': turn_id, 'delta': 'PONG'}})\n"
    "        emit({'method': 'turn/completed', 'params': {'threadId': tid, 'turn': {'id': turn_id, 'status': 'completed'}}})\n"
)


class _StubHandler:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self._zero_canon_admission: Any = None
        self._zero_canon_completion: Any = None


class _StubLease:
    def __init__(self) -> None:
        self.failures: list[BaseException] = []

    def record_failure(self, exc: BaseException) -> None:
        self.failures.append(exc)

    def record_discard(self, _reason: str) -> None:
        return None


def _seed_v2_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home, codex_dir, dyn = tmp_path / "real_home", tmp_path / "real_home" / ".codex", tmp_path / "dynamic_config.json"
    codex_dir.mkdir(parents=True, mode=0o700)
    (codex_dir / "config.toml").write_text('model = "gpt-6.1-terra"\n', encoding="utf-8")
    (codex_dir / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": DUMMY_KEY}), encoding="utf-8")
    dyn.write_text(json.dumps({"BRIDGE_CODEX_APP_SERVER_V2_ENABLED": True}), encoding="utf-8")
    for key, val in {
        "HOME": str(home), "CODEX_HOME": str(codex_dir), "BRIDGE_DYNAMIC_CONFIG_PATH": str(dyn),
        "BRIDGE_STDIO_RESIDENT_ENABLED": "1", "BRIDGE_CODEX_APP_SERVER_V2_ENABLED": "1",
        "BRIDGE_STDIO_CANCEL_GRACE_S": "0.1", "BRIDGE_ZC_STATIC_CWD_PATH": str(tmp_path / "zc-static-cwd"),
    }.items():
        monkeypatch.setenv(key, val)
    script = tmp_path / "fake_codex_v2.py"
    script.write_text(_FAKE_CODEX_V2, encoding="utf-8")
    return script


def test_real_codex_yaml_manifest_builds_clean_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix 1: Real providers.d/codex.yaml yields exact ['codex', 'app-server'] with zero flag pollution."""
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing_dynamic.json"))
    monkeypatch.setenv("BRIDGE_CODEX_APP_SERVER_V2_ENABLED", "1")
    adapter = StdioResidentAdapter("codex", yaml.safe_load((ROOT / "providers.d" / "codex.yaml").read_text(encoding="utf-8")))
    try:
        assert (adapter._protocol, adapter._options, adapter._build_argv()) == ("codex-app-server-v2", {}, ["codex", "app-server"])
    finally:
        adapter.shutdown(timeout_s=0.5)
    opts = {"provider_id": "codex", "kind": "stdio_resident", "limits": {"max_concurrent": 10}, "discovery": {"method": "static"}, "cli_args": ["--extra", "val"], "--flag": "ok", "--toggle": True, "--off": False}
    assert _build_codex_argv(["codex"], opts) == ["codex", "app-server", "--extra", "val", "--flag", "ok", "--toggle"]


def test_execute_turn_wires_v2_admission_and_completion_proofs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix 2: execute_turn sets _zero_canon_admission pre-SSE and _zero_canon_completion post-turn."""
    adapter = StdioResidentAdapter("codex", {}, cli_argv=[sys.executable, str(_seed_v2_env(tmp_path, monkeypatch)), "--mode", "ok"])
    try:
        sse_h, seen_adm, chunks = _StubHandler({"X-Review-Profile": "Zero-Canon"}), list[Any](), list[tuple[str, str]]()
        sse_writer = lambda k, t: (seen_adm.append(sse_h._zero_canon_admission), chunks.append((k, t)), True)[2]  # noqa: E731
        sse_ctx = TurnContext(model=TERRA, effort="medium", prompt="PING", cwd=str(tmp_path), stream=True, handler=sse_h)
        assert adapter.execute_turn(sse_ctx, sse_writer).text == "PONG" and chunks == [("content", "PONG")] and seen_adm[0] is not None
        assert build_attestation_header(seen_adm[0], phase="admitted") == EXPECTED_ADMITTED
        assert build_attestation_header(sse_h._zero_canon_completion, phase="completed") == EXPECTED_COMPLETED
        ns_h = _StubHandler({"X-Review-Profile": "Zero-Canon"})
        assert adapter.execute_turn(TurnContext(model=TERRA, effort="medium", prompt="PING", cwd=str(tmp_path), stream=False, handler=ns_h), None).text == "PONG"
        assert build_attestation_header(ns_h._zero_canon_completion, phase="completed") == EXPECTED_COMPLETED
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_execute_turn_tool_event_never_attaches_completion_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fix 2 fail-closed: forbidden tool event raises ResidentTurnError without completion proof."""
    adapter = StdioResidentAdapter("codex", {}, cli_argv=[sys.executable, str(_seed_v2_env(tmp_path, monkeypatch)), "--mode", "tool_event"])
    try:
        handler = _StubHandler({"X-Review-Profile": "Zero-Canon"})
        with pytest.raises(ResidentTurnError) as ei:
            _ = adapter.execute_turn(TurnContext(model=TERRA, effort="medium", prompt="PING", cwd=str(tmp_path), stream=False, handler=handler), None)
        assert (ei.value.status, ei.value.response.code, handler._zero_canon_completion) == (502, "zero_canon_tool_event_forbidden", None)
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_server_serve_json_body_catches_resident_turn_error() -> None:
    """Fix 3: server.py _serve_json_body sends sanitized HTTP error instead of disconnecting."""
    import server
    err = ResidentTurnError(build_turn_error(RuntimeError(f"upstream failed Bearer {DUMMY_KEY}"), live_sent=0))
    lease, sent = _StubLease(), list[tuple[int, dict[str, Any]]]()
    handler = object.__new__(server.Handler)
    handler._current_lease = lambda: lease  # type: ignore[method-assign]
    handler._send = lambda st, payload, extra_headers=None: sent.append((st, payload))  # type: ignore[method-assign]
    handler._dispatch = lambda _c, _ka: (_ for _ in ()).throw(err)  # type: ignore[method-assign]
    handler._serve_json_body({"model": TERRA})
    assert lease.failures == [err] and sent == [(502, err.response.body)] and DUMMY_KEY not in json.dumps(sent)


def _make_sse_handler(dispatch_fn: Any, profile: str = "Zero-Canon") -> tuple[Any, dict[str, Any]]:
    import server
    rec: dict[str, Any] = {"statuses": [], "headers": {}, "frames": [], "sent": [], "sent_hdr": [], "ended": 0, "lease": _StubLease()}
    conn = type("_Conn", (), {"gettimeout": lambda _s: 30.0, "settimeout": lambda _s, _t: None})()
    h = object.__new__(server.Handler)
    h.connection, h._review_profile, h._headers_already_sent, h._response_status = conn, profile, False, None
    h._zero_canon_admission, h._zero_canon_completion, h._active_managed_turn, h._trace, h._context_pruned = None, None, None, None, None
    h._current_lease = lambda: rec["lease"]  # type: ignore[method-assign]
    h.send_response = lambda code: rec["statuses"].append(code)  # type: ignore[method-assign]
    h.send_header = lambda k, v: rec["headers"].__setitem__(k, v)  # type: ignore[method-assign]
    h.end_headers = lambda: rec.__setitem__("ended", rec["ended"] + 1)  # type: ignore[method-assign]
    h._emit = lambda frame: (rec["frames"].append(frame), True)[1]  # type: ignore[method-assign]
    h._send = lambda st, body, extra_headers=None: (rec["sent_hdr"].append(bool(h._headers_already_sent)), rec["sent"].append((st, body)))[1]  # type: ignore[method-assign]
    h._dispatch = dispatch_fn  # type: ignore[method-assign]
    for fn in ("_telemetry_gone", "_telemetry_note", "_telemetry_error", "_telemetry_usage", "_record_turn_outcome"):
        setattr(h, fn, lambda *_a, **_kw: None)
    h._error_body = h._reserve_delivery = lambda _out: None  # type: ignore[method-assign]
    return h, rec


def test_server_sse_defers_zero_canon_headers_and_streams_pong_once() -> None:
    """W8 Fix 1+2: Zero-Canon Codex SSE defers headers until admission and emits PONG once."""
    proof = ZeroCanonAdmissionProof(TERRA, "medium", "thr-srv-1", "trn-srv-1", clean_home_verified=True, handshake_acked=True)
    saw_pre: list[bool] = []
    def _dispatch(_ctx: dict[str, Any], keepalive: Any, sse_writer: Any) -> dict[str, Any]:
        saw_pre.append(bool(handler._headers_already_sent))
        assert keepalive() is True and not handler._headers_already_sent
        handler._zero_canon_admission = proof
        assert sse_writer("content", "PONG") is True and handler._headers_already_sent is True
        return {"backend_kind": "stdio_resident", "events": [("content", "PONG")], "text": "PONG", "usage": {}}
    handler, rec = _make_sse_handler(_dispatch, profile="Zero-Canon")
    assert should_defer_zero_canon_sse_headers(handler, {"backend": "codex"}) is True
    handler._serve_sse_body({"model": TERRA, "backend": "codex"})
    assert (saw_pre, rec["statuses"], rec["ended"], rec["sent"], rec["headers"].get("X-Zero-Canon-Attestation")) == ([False], [200], 1, [], EXPECTED_ADMITTED)
    payloads = [json.loads(f[6:]) for f in rec["frames"] if f.startswith("data: {")]
    content = "".join(str(p["choices"][0]["delta"].get("content", "")) for p in payloads)
    assert (content, payloads[0]["choices"][0]["delta"].get("role"), rec["frames"][-1]) == ("PONG", "assistant", "data: [DONE]\n\n")


def test_server_sse_pre_admission_error_sends_http_error_json() -> None:
    """W8 Fix 2 fail-closed: pre-admission ResidentTurnError returns HTTP 503 JSON, not 200."""
    err = ResidentTurnError(build_turn_error(RuntimeError(f"credential_unavailable Bearer {DUMMY_KEY}"), live_sent=0))
    handler, rec = _make_sse_handler(lambda _c, _k, _s: (_ for _ in ()).throw(err), profile="zero-canon")
    handler._serve_sse_body({"model": TERRA, "backend": "codex"})
    assert (rec["statuses"], rec["ended"], handler._headers_already_sent, rec["lease"].failures) == ([], 0, False, [err])
    assert (rec["sent"], "X-Zero-Canon-Attestation" in rec["headers"], DUMMY_KEY in json.dumps(rec["sent"])) == ([(503, err.response.body)], False, False)


def test_gpt_6_1_sol_present_in_gated_catalog_when_droid_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """W8 Fix 3: gpt-6.1-sol remains available in GatedCatalog when droid is disabled."""
    import server
    for k, v in (("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json")), ("BRIDGE_DROID_CATALOG_ENABLED", "0"), ("BRIDGE_DROID_ENABLED", "false")):
        monkeypatch.setenv(k, v)
    built: Any = gated_catalog((ROOT / "fleet.json").read_bytes(), server._build_catalog)
    assert isinstance(built, GatedCatalog) and built["backends"]["droid"]["enabled"] is False and "gpt-6.1-sol" in built["models"]


def test_wrap_v2_sse_writer_fails_closed_on_missing_or_local_thread_id() -> None:
    """W9 F-001/F-009: wrap_v2_sse_writer raises 502 and never calls sse_writer without verified proof."""
    local = ProtocolState(phase=ProtocolPhase.TURN_ACTIVE, thread_id="th-local-1", turn_id="trn-1", zero_canon=True)
    for state in (None, local):
        drv = type("_Drv", (), {"protocol_state": state, "last_turn_state": None})()
        handler, calls = _StubHandler(), list[tuple[str, str]]()
        wrapped = wrap_v2_sse_writer(lambda k, t: (calls.append((k, t)), True)[1], drv, handler, TERRA, "medium")
        assert wrapped is not None
        for _ in range(2):
            with pytest.raises(ZeroCanonHttpError) as ei:
                wrapped("content", "PONG")
            assert (ei.value.http_status, ei.value.code) == (502, "zero_canon_attestation_failed")
        assert calls == [] and handler._zero_canon_admission is None


def _assert_fail_closed_502(handler: Any, rec: dict[str, Any], ctx: dict[str, Any] | None = None) -> None:
    assert (rec["statuses"], rec["ended"], rec["frames"], rec["sent_hdr"], handler._headers_already_sent, handler._response_status) == ([], 0, [], [False], True, 502)
    assert (len(rec["sent"]), rec["sent"][0][0]) == (1, 502)
    err = rec["sent"][0][1]["error"]
    assert (err["code"], err["type"], DUMMY_KEY in json.dumps(rec["sent"]), "X-Zero-Canon-Attestation" in rec["headers"]) == ("zero_canon_attestation_failed", "upstream_error", False, False)
    assert (handler._zero_canon_admission, handler._zero_canon_completion) == (None, None)
    if ctx is not None:
        assert ("zero_canon_admission" in ctx, "zero_canon_completion" in ctx) == (False, False)


def test_sse_header_gate_ensure_live_headers_fails_closed_without_admission() -> None:
    """W9 F-001/F-009: ensure_live_headers returns HTTP 502 JSON (never 200) when admission is missing."""
    handler, rec = _make_sse_handler(lambda *_a: {}, profile="Zero-Canon")
    gate = ZeroCanonSseHeaderGate.for_request(handler, {"model": TERRA, "backend": "codex"})
    assert (gate.defer_zc_headers, gate.allow_keepalive(), gate.ensure_live_headers(), gate.allow_keepalive()) == (True, False, False, False)
    _assert_fail_closed_502(handler, rec)


def test_zero_chunk_sse_turn_with_completed_emits_phase_completed() -> None:
    """W9 F-012: 0-chunk SSE turn after ProtocolPhase.COMPLETED emits phase=completed, never phase=admitted."""
    done = ProtocolState(phase=ProtocolPhase.COMPLETED, epoch=2, thread_id="thr-srv-0", turn_id="trn-srv-0", zero_canon=True)
    proof_rec = TurnProofRecorder(handshake_acked=True, clean_home_verified=True, issued_thread_id="thr-srv-0", issued_turn_id="trn-srv-0", turn_epoch=2)
    drv = type("_Drv", (), {"protocol_state": done, "last_turn_state": done, "turn_proof": proof_rec, "last_turn_proof": proof_rec})()

    def _dispatch(_ctx: dict[str, Any], _ka: Any, _sw: Any) -> dict[str, Any]:
        record_v2_turn_completion(drv, handler, model=TERRA, effort="medium", has_sse=True)
        assert handler._zero_canon_admission is None and handler._zero_canon_completion is not None
        return {"backend_kind": "stdio_resident", "events": [], "text": "", "usage": {}}

    handler, rec = _make_sse_handler(_dispatch, profile="Zero-Canon")
    handler._serve_sse_body({"model": TERRA, "backend": "codex"})
    assert (rec["statuses"], rec["ended"], rec["sent"], rec["headers"].get("X-Zero-Canon-Attestation"), rec["frames"][-1]) == ([200], 1, [], EXPECTED_COMPLETED, "data: [DONE]\n\n")


def test_zero_chunk_sse_turn_without_completed_fails_closed_502() -> None:
    """W9 F-001/F-012: 0-chunk SSE turn without ProtocolPhase.COMPLETED fails closed with HTTP 502 and 0 frames."""
    active = ProtocolState(phase=ProtocolPhase.TURN_ACTIVE, thread_id="thr-srv-0", turn_id="trn-srv-0", zero_canon=True)
    drv = type("_Drv", (), {"protocol_state": active, "last_turn_state": None})()

    def _dispatch(_ctx: dict[str, Any], _ka: Any, _sw: Any) -> dict[str, Any]:
        record_v2_turn_completion(drv, handler, model=TERRA, effort="medium", has_sse=True)
        assert (handler._zero_canon_admission, handler._zero_canon_completion) == (None, None)
        return {"backend_kind": "stdio_resident", "events": [], "text": "", "usage": {}}

    handler, rec = _make_sse_handler(_dispatch, profile="Zero-Canon")
    handler._serve_sse_body({"model": TERRA, "backend": "codex"})
    _assert_fail_closed_502(handler, rec)


def test_server_sse_pre_stream_attestation_failure_fails_closed_502() -> None:
    """W10 F-001..F-006: _serve_sse_body returns HTTP 502 (never 200), redacts secrets, clears proofs."""
    local = ProtocolState(phase=ProtocolPhase.TURN_ACTIVE, thread_id="th-local-1", turn_id="trn-1", zero_canon=True)
    req, chunk = {"review_profile": "zero-canon", "backend_id": "codex"}, {"choices": [{"delta": {"content": "PONG"}}]}
    for state, mode in ((None, "direct"), (local, "direct"), (None, "routed"), (local, "routed"), (None, "secret_direct"), (None, "secret_routed")):
        drv = type("_Drv", (), {"protocol_state": state, "last_turn_state": None})()
        ctx: dict[str, Any] = {"model": TERRA, "backend": "codex", "zero_canon_admission": "stale", "zero_canon_completion": "stale"}

        def _dispatch(_c: dict[str, Any], _ka: Any, sw: Any, _d: Any = drv, _m: str = mode) -> dict[str, Any]:
            if _m.startswith("secret"):
                err = ZeroCanonHttpError("zero_canon_attestation_failed", f"missing proof Bearer {DUMMY_KEY}", http_status=502)
                if _m == "secret_routed":
                    raise ResidentTurnError(build_turn_error(err, live_sent=1)) from err
                raise err
            wrapped = wrap_v2_sse_writer(sw, _d, handler, TERRA, "medium")
            assert wrapped is not None
            execute_routed_turn(lambda _r: iter([chunk]), "codex-app-server-v2", req, wrapped) if _m == "routed" else wrapped("content", "PONG")
            return {}

        handler, rec = _make_sse_handler(_dispatch, profile="zero-canon")
        handler._zero_canon_admission, handler._zero_canon_completion = "stale", "stale"
        handler._serve_sse_body(ctx)
        _assert_fail_closed_502(handler, rec, ctx)
        assert len(rec["lease"].failures) == 1

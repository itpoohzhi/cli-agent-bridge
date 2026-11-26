"""W5 sabotage suite: fail-closed Codex v2 attestation wire, clean-home, single-use, HTTP barrier."""

from __future__ import annotations

import io
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stdio_resident import codex_driver as codex_driver_mod  # noqa: E402
from core.stdio_resident.codex_attestation_wire import build_v2_admission_proof, build_v2_completion_proof  # noqa: E402
from core.stdio_resident.codex_protocol_fsm import ProtocolPhase  # noqa: E402
from core.stdio_resident.process_io import LINE, TaggedLine  # noqa: E402
from core.zc_http_barrier import emit_nonstream_headers  # noqa: E402

MODEL, EFFORT, TID, UID = "gpt-6.1-sol", "medium", "thr-srv-1", "trn-srv-1"


class _FakeHandle:
    pid, generation, _pgid_dead = 4242, 0, True

    def __init__(self) -> None:
        self._out: list[str] = []

    def write(self, data: bytes) -> None:
        msg = json.loads(data.decode("utf-8").strip())
        m, rid = msg.get("method"), msg.get("id")
        if m == "initialize":
            self._out.append(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"userAgent": "codex-test/2"}}))
        elif m == "thread/start":
            self._out.append(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"thread": {"id": TID}, "model": MODEL, "reasoningEffort": EFFORT}}))
        elif m == "turn/start":
            self._out.extend([
                json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"turn": {"id": UID, "status": "inProgress"}}}),
                json.dumps({"jsonrpc": "2.0", "method": "turn/started", "params": {"threadId": TID, "turn": {"id": UID}}}),
                json.dumps({"jsonrpc": "2.0", "method": "item/agentMessage/delta", "params": {"threadId": TID, "turnId": UID, "itemId": "i1", "delta": "PONG"}}),
                json.dumps({"jsonrpc": "2.0", "method": "turn/completed", "params": {"threadId": TID, "turn": {"id": UID, "status": "completed"}}}),
            ])

    def read_stdout_line(self, timeout_s: float | None = None) -> TaggedLine | None:
        _ = timeout_s
        return TaggedLine(line=self._out.pop(0), generation=self.generation, pid=self.pid, is_stderr=False) if self._out else None

    def read_stdout_outcome(self, timeout_s: float | None = None) -> tuple[str, TaggedLine | None]:
        return (LINE, self.read_stdout_line(timeout_s))


def _zc_ctx(cwd: object) -> dict[str, Any]:
    return {"model": MODEL, "effort": EFFORT, "review_profile": "Zero-Canon", "cwd": str(cwd)}


def _home(tmp_path: Path) -> dict[str, str]:
    (codex := tmp_path / "home" / ".codex").mkdir(parents=True, exist_ok=True)
    (codex / "auth.json").write_text('{"tokens": {}}', encoding="utf-8")
    (codex / "config.toml").write_text(f'model = "{MODEL}"\n', encoding="utf-8")
    return {"HOME": str(tmp_path / "home"), "CODEX_HOME": str(codex)}


def _clean(tmp_path: Path, name: str) -> tuple[Any, _FakeHandle, dict[str, Any]]:
    zc = tmp_path / name
    zc.mkdir()
    drv = codex_driver_mod.CodexAppServerV2Driver()
    _ = drv.build_zero_canon_env(_home(tmp_path), str(zc))
    handle = _FakeHandle()
    assert drv.run_handshake(handle, timeout_s=5.0) is True
    return drv, handle, _zc_ctx(zc)


def _activate(drv: Any, handle: _FakeHandle, ctx: dict[str, Any]) -> None:
    assert drv.prepare_turn(handle, ctx, timeout_s=5.0) is True
    handle.write(drv.encode_turn("PING", ctx))
    for _ in range(2):  # turn/start result + turn/started -> TURN_ACTIVE
        ln = handle.read_stdout_line(timeout_s=5.0)
        assert ln is not None
        _ = drv.decode_line(ln.line)


def _finish(drv: Any, handle: _FakeHandle) -> str:
    parts: list[str] = []
    while True:
        ln = handle.read_stdout_line(timeout_s=5.0)
        assert ln is not None
        chunk = drv.decode_line(ln.line)
        if chunk is not None and chunk.text:
            parts.append(chunk.text)
        if drv.is_terminal(ln.line, chunk):
            return "".join(parts)


def _make_handler(profile: str) -> tuple[Any, dict[str, Any]]:
    import server

    rec: dict[str, Any] = {"statuses": [], "headers": {}}
    h = object.__new__(server.Handler)
    h._review_profile, h._response_status, h._headers_already_sent = profile, 0, False
    h._zero_canon_admission = h._zero_canon_completion = h._active_managed_turn = h._context_pruned = None
    h._trace, h.wfile = None, io.BytesIO()
    lease = SimpleNamespace(record_failure=lambda _e: None, record_discard=lambda _r: None)
    h._current_lease = lambda: lease  # noqa: E731
    h._dispatch = lambda _c, _k: {"text": "ok", "model": MODEL, "usage": {}}  # noqa: E731
    h.send_response = lambda code: rec["statuses"].append(code)  # noqa: E731
    h.send_header = lambda k, v: rec["headers"].__setitem__(k, v)  # noqa: E731
    h.end_headers = lambda: None  # noqa: E731
    for fn in ("_telemetry_note", "_telemetry_usage", "_telemetry_error", "_telemetry_gone", "_record_turn_outcome"):
        setattr(h, fn, lambda *_a, **_kw: None)
    h._error_body = h._reserve_delivery = lambda _out: None  # noqa: E731
    return h, rec


def test_clean_home_rejects_static_cwd_and_symlinks(tmp_path: Path) -> None:
    """F-110: shared static 0o555 CWD and symlinked auth.json never verify clean home."""
    static = tmp_path / "zc-codex-empty-cwd"
    static.mkdir()
    static.chmod(0o555)
    sym_codex = tmp_path / "zc-sym" / ".codex"
    sym_codex.mkdir(parents=True)
    (sym_codex / "config.toml").write_text(f'model = "{MODEL}"\n', encoding="utf-8")
    target = tmp_path / "auth-target.json"
    target.write_text('{"tokens": {}}', encoding="utf-8")
    (sym_codex / "auth.json").symlink_to(target)
    for cwd in (static, tmp_path / "zc-sym"):
        drv, handle = codex_driver_mod.CodexAppServerV2Driver(), _FakeHandle()
        assert drv.run_handshake(handle, timeout_s=5.0) is True
        _activate(drv, handle, _zc_ctx(cwd))
        assert drv.turn_proof is not None and drv.turn_proof.clean_home_verified is False
        assert build_v2_admission_proof(drv, model=MODEL, effort=EFFORT) is None
    static.chmod(0o755)


def test_clean_home_macos_symlink_parent_and_trailing_slash(tmp_path: Path) -> None:
    """F-005: symlinked parent + trailing slash still verifies a real clean home."""
    zc = tmp_path / "real" / "zc-ok"
    zc.mkdir(parents=True)
    (link_tmp := tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
    drv = codex_driver_mod.CodexAppServerV2Driver()
    _ = drv.build_zero_canon_env(_home(tmp_path), str(zc))
    handle = _FakeHandle()
    assert drv.run_handshake(handle, timeout_s=5.0) is True
    _activate(drv, handle, _zc_ctx(f"{link_tmp}/zc-ok/"))
    assert drv.turn_proof is not None and drv.turn_proof.clean_home_verified is True
    proof = build_v2_admission_proof(drv, model=MODEL, effort=EFFORT)
    assert proof is not None and (proof.thread_id, proof.turn_id) == (TID, UID)


def test_sabotage_unacked_handshake_and_mismatched_ids(tmp_path: Path) -> None:
    """F-001: unacked handshake and tampered thread_id/epoch never yield admission proofs."""
    zc = tmp_path / "zc-unacked"
    zc.mkdir()
    drv = codex_driver_mod.CodexAppServerV2Driver()
    _ = drv.build_zero_canon_env(_home(tmp_path), str(zc))
    handle = _FakeHandle()
    slot = codex_driver_mod._V2SlotState(state=replace(codex_driver_mod.ProtocolState(), phase=ProtocolPhase.INITIALIZED))
    drv._bind_handle_state(handle, slot)  # skip run_handshake: INITIALIZED but never acked
    _activate(drv, handle, _zc_ctx(zc))
    assert slot.handshake_acked is False and build_v2_admission_proof(drv, model=MODEL, effort=EFFORT) is None
    drv2, handle2, ctx2 = _clean(tmp_path, "zc-mismatch")
    _activate(drv2, handle2, ctx2)
    good = drv2._ctx().state
    assert build_v2_admission_proof(drv2, model=MODEL, effort=EFFORT) is not None
    for bad in (replace(good, thread_id="probe"), replace(good, thread_id="thr-other"), replace(good, epoch=good.epoch + 9)):
        drv2._ctx().state = bad
        assert build_v2_admission_proof(drv2, model=MODEL, effort=EFFORT) is None


def test_sabotage_tool_event_and_single_use_completion(tmp_path: Path) -> None:
    """Forbidden tool events block completion; teardown proofs are single-use and 502 fail-closed."""
    drv, handle, ctx = _clean(tmp_path, "zc-tool")
    _activate(drv, handle, ctx)
    _ = drv.decode_line(json.dumps({"jsonrpc": "2.0", "method": "item/tool/call", "params": {"threadId": TID}}))
    assert drv.turn_proof is not None and drv.turn_proof.tool_events_seen >= 1
    _ = _finish(drv, handle)
    assert build_v2_completion_proof(drv, model=MODEL, effort=EFFORT) is None
    drv2, handle2, ctx2 = _clean(tmp_path, "zc-single")
    _activate(drv2, handle2, ctx2)
    assert _finish(drv2, handle2) == "PONG"
    assert drv2.perform_turn_teardown(handle2, ctx2, timeout_s=2.0) is True
    assert build_v2_admission_proof(drv2, model=MODEL, effort=EFFORT) is None  # no last_turn_state replay
    assert build_v2_completion_proof(drv2, model=MODEL, effort=EFFORT) is not None
    assert build_v2_completion_proof(drv2, model=MODEL, effort=EFFORT) is None  # single-use consumed
    h, rec = _make_handler("Zero-Canon")
    assert emit_nonstream_headers(h, 0, (), ("X-Context-Pruned", None), {}) is False
    assert rec["statuses"] == [502] and h._response_status == 502
    assert json.loads(h.wfile.getvalue())["error"]["code"] == "zero_canon_attestation_failed"


def test_usage_guard_hoisted_once_per_turn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HL-ENV/v1: usage-frame guard env flag is read exactly once in prepare_turn, never per line."""
    calls: list[int] = []
    monkeypatch.setattr(codex_driver_mod, "is_codex_usage_frame_guard_enabled", lambda: (calls.append(1), True)[1])
    drv, handle, ctx = _clean(tmp_path, "zc-guard")
    _activate(drv, handle, ctx)
    for _ in range(5):
        ln = handle.read_stdout_line(timeout_s=5.0)
        _ = drv.decode_line(ln.line if ln is not None else "{}")
    assert len(calls) == 1


def test_server_serve_json_body_nonstream_barrier_wiring() -> None:
    """Zero-Canon non-stream JSON without proof sends 502 (never fail-open 200); standard sends 200."""
    h, rec = _make_handler("Zero-Canon")
    h._serve_json_body({"model": MODEL, "backend": "codex"})
    body = h.wfile.getvalue()
    assert rec["statuses"] == [502] and h._response_status == 502
    assert int(rec["headers"]["Content-Length"]) == len(body)
    assert json.loads(body)["error"]["code"] == "zero_canon_attestation_failed"
    h2, rec2 = _make_handler("standard")
    h2._serve_json_body({"model": MODEL, "backend": "codex"})
    body2 = h2.wfile.getvalue()
    assert rec2["statuses"] == [200] and int(rec2["headers"]["Content-Length"]) == len(body2)
    parsed = json.loads(body2)
    assert parsed["object"] == "chat.completion" and parsed["choices"][0]["message"]["content"] == "ok"


def test_mutation_killers_wire_and_driver(tmp_path: Path) -> None:
    """Wire requires zero_canon+CLEAN state, kills proofs on tool events; driver helpers fail closed."""
    from core.stdio_resident.codex_driver import _verify_zc_clean_home
    from core.stdio_resident.codex_protocol_fsm import ProtocolPhase, ProtocolState
    from core.zc_admission import TurnProofRecorder

    assert _verify_zc_clean_home({"zero_canon_root": ""}) is False
    assert _verify_zc_clean_home({"zero_canon_root": str(tmp_path / "plain")}) is False
    assert TurnProofRecorder().inherited_state is False
    active = ProtocolState(phase=ProtocolPhase.TURN_ACTIVE, epoch=2, thread_id="thr-srv-1", turn_id="trn-1", zero_canon=True)
    assert build_v2_admission_proof(type("_D", (), {"protocol_state": active, "turn_proof": None})(), model=MODEL, effort=EFFORT) is None
    done = ProtocolState(phase=ProtocolPhase.COMPLETED, epoch=2, thread_id="thr-srv-1", turn_id="trn-1", zero_canon=True)
    rec_tool = TurnProofRecorder(handshake_acked=True, clean_home_verified=True, issued_thread_id="thr-srv-1", issued_turn_id="trn-1", turn_epoch=2, tool_events_seen=1)
    assert build_v2_completion_proof(type("_D", (), {"protocol_state": done, "last_turn_state": None, "turn_proof": rec_tool})(), model=MODEL, effort=EFFORT) is None
    rec_ok = TurnProofRecorder(handshake_acked=True, clean_home_verified=True, issued_thread_id="thr-srv-1", issued_turn_id="trn-1", turn_epoch=2)
    drv_attr = type("_D2", (), {"protocol_state": None, "last_turn_state": done, "last_turn_proof": rec_ok})()
    assert build_v2_completion_proof(drv_attr, model=MODEL, effort=EFFORT) is not None and drv_attr.last_turn_proof is None
    drv, handle, ctx = _clean(tmp_path, "zc-err")
    _activate(drv, handle, ctx)
    _ = drv.decode_line(json.dumps({"jsonrpc": "2.0", "method": "error", "params": {"threadId": "thr-srv-1", "error": {"message": "boom"}}}))
    assert drv.turn_proof is not None and drv.turn_proof.tool_events_seen == 0
    idle_drv = codex_driver_mod.CodexAppServerV2Driver()
    term_line = json.dumps({"jsonrpc": "2.0", "method": "turn/completed", "params": {"threadId": "t1", "turn": {"id": "u1", "status": "completed"}}})
    assert idle_drv.is_terminal(term_line, None) is True
    assert idle_drv.is_tool_stop(term_line, None) is False


def test_barrier_emits_managed_turn_header() -> None:
    """Non-stream barrier surfaces X-Turn-Id for the active managed turn."""
    h, rec = _make_handler("standard")
    h._active_managed_turn = type("_T", (), {"turn_id": "mt-42"})()
    assert emit_nonstream_headers(h, 2, (), ("X-Context-Pruned", None), {}) is True
    assert rec["headers"].get("X-Turn-Id") == "mt-42"

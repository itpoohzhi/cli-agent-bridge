"""Regression tests for W7 Heavy Path live HTTP/manifest wiring gaps."""

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
from core.stdio_resident.codex_attestation_wire import should_defer_zero_canon_sse_headers  # noqa: E402
from core.stdio_resident.codex_driver import _build_codex_argv  # noqa: E402
from core.stdio_resident.turn_error_sse import ResidentTurnError, build_turn_error  # noqa: E402
from core.zero_canon_attestation_http import ZeroCanonAdmissionProof, build_attestation_header  # noqa: E402

TERRA = "gpt-6.1-terra"
DUMMY_KEY = "sk-dummy-test-000"
EXPECTED_ADMITTED = (
    "profile=zero-canon;backend=codex;tools=off;"
    "sandbox=read-only;approval=never;model=gpt-6.1-terra;effort=medium;phase=admitted"
)
EXPECTED_COMPLETED = (
    "profile=zero-canon;backend=codex;tools=off;"
    "sandbox=read-only;approval=never;model=gpt-6.1-terra;effort=medium;phase=completed"
)

_FAKE_CODEX_V2 = (
    "import argparse, json, sys\n"
    "p = argparse.ArgumentParser()\n"
    "p.add_argument('--mode', default='ok')\n"
    "args, _ = p.parse_known_args()\n"
    "emit = lambda o: (sys.stdout.write(json.dumps(o, separators=(',', ':')) + '\\n'), sys.stdout.flush())\n"
    "tid, turn_id = 'thr-srv-heavy-1', 'trn-srv-heavy-1'\n"
    "for raw in sys.stdin:\n"
    "    if not raw.strip(): continue\n"
    "    msg = json.loads(raw)\n"
    "    m, rid, pr = msg.get('method'), msg.get('id'), msg.get('params') or {}\n"
    "    if m == 'initialize':\n"
    "        emit({'id': rid, 'result': {'userAgent': 'codex/0.171.0-alpha.13'}})\n"
    "    elif m == 'thread/start':\n"
    "        emit({'id': rid, 'result': {'thread': {'id': tid}, 'model': pr.get('model') or 'gpt-6.1-terra'}})\n"
    "    elif m == 'turn/start':\n"
    "        emit({'id': rid, 'result': {'turn': {'id': turn_id, 'status': 'inProgress'}}})\n"
    "        if args.mode == 'tool_event':\n"
    "            emit({'method': 'item/tool/call', 'params': {'threadId': tid, 'turnId': turn_id, 'name': 'sh'}})\n"
    "            break\n"
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
    home = tmp_path / "real_home"
    codex_dir = home / ".codex"
    codex_dir.mkdir(parents=True, mode=0o700)
    (codex_dir / "config.toml").write_text('model = "gpt-6.1-terra"\n', encoding="utf-8")
    (codex_dir / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": DUMMY_KEY}), encoding="utf-8")
    dyn = tmp_path / "dynamic_config.json"
    dyn.write_text(json.dumps({"BRIDGE_CODEX_APP_SERVER_V2_ENABLED": True}), encoding="utf-8")
    for key, val in {
        "HOME": str(home),
        "CODEX_HOME": str(codex_dir),
        "BRIDGE_DYNAMIC_CONFIG_PATH": str(dyn),
        "BRIDGE_STDIO_RESIDENT_ENABLED": "1",
        "BRIDGE_CODEX_APP_SERVER_V2_ENABLED": "1",
        "BRIDGE_STDIO_CANCEL_GRACE_S": "0.1",
    }.items():
        monkeypatch.setenv(key, val)
    script = tmp_path / "fake_codex_v2.py"
    script.write_text(_FAKE_CODEX_V2, encoding="utf-8")
    return script


def test_real_codex_yaml_manifest_builds_clean_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fix 1: Real providers.d/codex.yaml yields exact ['codex', 'app-server'] with zero flag pollution."""
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing_dynamic.json"))
    monkeypatch.setenv("BRIDGE_CODEX_APP_SERVER_V2_ENABLED", "1")
    manifest = yaml.safe_load((ROOT / "providers.d" / "codex.yaml").read_text(encoding="utf-8"))
    adapter = StdioResidentAdapter("codex", manifest)
    try:
        assert adapter._protocol == "codex-app-server-v2"
        assert adapter._options == {}
        assert adapter._build_argv() == ["codex", "app-server"]
    finally:
        adapter.shutdown(timeout_s=0.5)

    built = _build_codex_argv(
        ["codex"],
        {
            "provider_id": "codex",
            "kind": "stdio_resident",
            "limits": {"max_concurrent": 10},
            "discovery": {"method": "static"},
            "cli_args": ["--extra", "val"],
            "--flag": "ok",
            "--toggle": True,
            "--off": False,
        },
    )
    assert built == ["codex", "app-server", "--extra", "val", "--flag", "ok", "--toggle"]


def test_execute_turn_wires_v2_admission_and_completion_proofs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fix 2: execute_turn sets _zero_canon_admission pre-SSE and _zero_canon_completion post-turn."""
    script = _seed_v2_env(tmp_path, monkeypatch)
    argv = [sys.executable, str(script), "--mode", "ok"]
    adapter = StdioResidentAdapter("codex", {}, cli_argv=argv)
    try:
        sse_handler = _StubHandler({"X-Review-Profile": "Zero-Canon"})
        observed_admission_before_first_write: list[Any] = []
        chunks: list[tuple[str, str]] = []

        def sse_writer(kind: str, text: str) -> bool:
            observed_admission_before_first_write.append(sse_handler._zero_canon_admission)
            chunks.append((kind, text))
            return True

        sse_ctx = TurnContext(
            model=TERRA, effort="medium", prompt="PING", cwd=str(tmp_path), stream=True, handler=sse_handler
        )
        sse_res = adapter.execute_turn(sse_ctx, sse_writer)
        assert sse_res.text == "PONG" and chunks == [("content", "PONG")]
        assert observed_admission_before_first_write[0] is not None
        assert build_attestation_header(observed_admission_before_first_write[0], phase="admitted") == EXPECTED_ADMITTED
        assert sse_handler._zero_canon_completion is not None
        assert build_attestation_header(sse_handler._zero_canon_completion, phase="completed") == EXPECTED_COMPLETED

        ns_handler = _StubHandler({"X-Review-Profile": "Zero-Canon"})
        ns_ctx = TurnContext(
            model=TERRA, effort="medium", prompt="PING", cwd=str(tmp_path), stream=False, handler=ns_handler
        )
        ns_res = adapter.execute_turn(ns_ctx, None)
        assert ns_res.text == "PONG"
        assert ns_handler._zero_canon_completion is not None
        assert build_attestation_header(ns_handler._zero_canon_completion, phase="completed") == EXPECTED_COMPLETED
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_execute_turn_tool_event_never_attaches_completion_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fix 2 fail-closed: forbidden tool event raises ResidentTurnError without completion proof."""
    script = _seed_v2_env(tmp_path, monkeypatch)
    argv = [sys.executable, str(script), "--mode", "tool_event"]
    adapter = StdioResidentAdapter("codex", {}, cli_argv=argv)
    try:
        handler = _StubHandler({"X-Review-Profile": "Zero-Canon"})
        ctx = TurnContext(
            model=TERRA, effort="medium", prompt="PING", cwd=str(tmp_path), stream=False, handler=handler
        )
        with pytest.raises(ResidentTurnError) as exc_info:
            _ = adapter.execute_turn(ctx, None)
        assert exc_info.value.status == 502
        assert exc_info.value.response.code == "zero_canon_tool_event_forbidden"
        assert handler._zero_canon_completion is None
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_server_serve_json_body_catches_resident_turn_error() -> None:
    """Fix 3: server.py _serve_json_body sends sanitized HTTP error instead of disconnecting."""
    import server

    err = ResidentTurnError(
        build_turn_error(RuntimeError(f"upstream failed Bearer {DUMMY_KEY}"), live_sent=0)
    )
    lease = _StubLease()
    sent: list[tuple[int, dict[str, Any]]] = []
    handler = object.__new__(server.Handler)
    handler._current_lease = lambda: lease  # type: ignore[method-assign]
    handler._send = lambda status, payload, extra_headers=None: sent.append((status, payload))  # type: ignore[method-assign]

    def _boom(_ctx: dict[str, Any], _keepalive: Any) -> dict[str, Any]:
        raise err

    handler._dispatch = _boom  # type: ignore[method-assign]
    handler._serve_json_body({"model": TERRA})

    assert lease.failures == [err]
    assert len(sent) == 1
    status, body = sent[0]
    assert status == err.status == 502
    assert body == err.response.body
    assert DUMMY_KEY not in json.dumps(body)


def _make_sse_handler(dispatch_fn: Any, profile: str = "Zero-Canon") -> tuple[Any, dict[str, Any]]:
    import server

    rec: dict[str, Any] = {"statuses": [], "headers": {}, "frames": [], "sent": [], "ended": 0, "lease": _StubLease()}
    conn = type("_Conn", (), {"gettimeout": lambda _s: 30.0, "settimeout": lambda _s, _t: None})()
    h = object.__new__(server.Handler)
    h.connection, h._review_profile, h._headers_already_sent = conn, profile, False
    h._zero_canon_admission, h._active_managed_turn, h._trace, h._context_pruned = None, None, None, None
    h._current_lease = lambda: rec["lease"]  # type: ignore[method-assign]
    h.send_response = lambda code: rec["statuses"].append(code)  # type: ignore[method-assign]
    h.send_header = lambda k, v: rec["headers"].__setitem__(k, v)  # type: ignore[method-assign]
    h.end_headers = lambda: rec.__setitem__("ended", rec["ended"] + 1)  # type: ignore[method-assign]
    h._emit = lambda frame: (rec["frames"].append(frame), True)[1]  # type: ignore[method-assign]
    h._send = lambda st, body, extra_headers=None: rec["sent"].append((st, body))  # type: ignore[method-assign]
    h._dispatch = dispatch_fn  # type: ignore[method-assign]
    for fn in ("_telemetry_gone", "_telemetry_note", "_telemetry_error", "_telemetry_usage", "_record_turn_outcome"):
        setattr(h, fn, lambda *_a, **_kw: None)
    h._error_body = lambda _out: None  # type: ignore[method-assign]
    h._reserve_delivery = lambda _out: None  # type: ignore[method-assign]
    return h, rec


def test_server_sse_defers_zero_canon_headers_and_streams_pong_once() -> None:
    """W8 Fix 1+2: Zero-Canon Codex SSE defers headers until admission and emits PONG once."""
    proof = ZeroCanonAdmissionProof(TERRA, "medium", "thr-srv-1", "trn-srv-1", clean_home_verified=True, handshake_acked=True)
    saw_pre_dispatch_sent: list[bool] = []

    def _dispatch(_ctx: dict[str, Any], keepalive: Any, sse_writer: Any) -> dict[str, Any]:
        saw_pre_dispatch_sent.append(bool(handler._headers_already_sent))
        assert keepalive() is True and not handler._headers_already_sent
        handler._zero_canon_admission = proof
        assert sse_writer("content", "PONG") is True
        assert handler._headers_already_sent is True
        return {"backend_kind": "stdio_resident", "events": [("content", "PONG")], "text": "PONG", "usage": {}}

    handler, rec = _make_sse_handler(_dispatch, profile="Zero-Canon")
    assert should_defer_zero_canon_sse_headers(handler, {"backend": "codex"}) is True
    handler._serve_sse_body({"model": TERRA, "backend": "codex"})
    assert (saw_pre_dispatch_sent, rec["statuses"], rec["ended"], rec["sent"]) == ([False], [200], 1, [])
    assert rec["headers"].get("X-Zero-Canon-Attestation") == EXPECTED_ADMITTED
    payloads = [json.loads(f[6:]) for f in rec["frames"] if f.startswith("data: {")]
    content = "".join(str(p["choices"][0]["delta"].get("content", "")) for p in payloads)
    assert (content, payloads[0]["choices"][0]["delta"].get("role"), rec["frames"][-1]) == ("PONG", "assistant", "data: [DONE]\n\n")


def test_server_sse_pre_admission_error_sends_http_error_json() -> None:
    """W8 Fix 2 fail-closed: pre-admission ResidentTurnError returns HTTP 503 JSON, not 200."""
    err = ResidentTurnError(build_turn_error(RuntimeError(f"credential_unavailable Bearer {DUMMY_KEY}"), live_sent=0))

    def _fail(_ctx: dict[str, Any], _ka: Any, _sw: Any) -> dict[str, Any]:
        raise err

    handler, rec = _make_sse_handler(_fail, profile="zero-canon")
    handler._serve_sse_body({"model": TERRA, "backend": "codex"})
    assert (rec["statuses"], rec["ended"], handler._headers_already_sent, rec["lease"].failures) == ([], 0, False, [err])
    assert "X-Zero-Canon-Attestation" not in rec["headers"]
    assert rec["sent"] == [(503, err.response.body)] and DUMMY_KEY not in json.dumps(rec["sent"])


def test_gpt_6_1_sol_present_in_gated_catalog_when_droid_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """W8 Fix 3: gpt-6.1-sol remains available in GatedCatalog when droid is disabled."""
    import server

    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent.json"))
    monkeypatch.setenv("BRIDGE_DROID_CATALOG_ENABLED", "0")
    monkeypatch.setenv("BRIDGE_DROID_ENABLED", "false")
    built: Any = gated_catalog((ROOT / "fleet.json").read_bytes(), server._build_catalog)
    assert isinstance(built, GatedCatalog)
    assert built["backends"]["droid"]["enabled"] is False
    assert "gpt-6.1-sol" in built["models"]

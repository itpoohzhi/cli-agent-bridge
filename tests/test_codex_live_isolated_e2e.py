"""Live-isolated L5 E2E verification for real Codex app-server v2 & Zero-Canon (W3-F)."""

# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false

from __future__ import annotations

import hashlib
import http.server
import json
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from contextlib import suppress
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
    ATTESTATION_HEADER,
    CODEX_EFFORT_MATRIX,
    CodexZeroCanonPolicyError,
    parse_attestation_header,
    validate_codex_model_effort,
)
from core.stdio_resident.codex_driver import CodexAppServerV2Driver  # noqa: E402
from core.stdio_resident.config import StdioPoolConfig  # noqa: E402
from core.stdio_resident.process_pool import ResidentProcessPool  # noqa: E402
from core.stdio_resident.process_reaper import is_pgid_alive  # noqa: E402
from core.stdio_resident.session_manager import SessionTurnMode, StdioSessionManager  # noqa: E402
from core.stdio_resident.types import SlotAffinityKey  # noqa: E402

DUMMY_KEY = "sk-dummy-test-000"
EXPECTED_VER = os.environ.get("CODEX_L5_EXPECTED_VERSION", "0.171.0-alpha.13")
TURN_TIMEOUT_S = float(os.environ.get("CODEX_L5_TURN_TIMEOUT_S", "25.0"))
CANCEL_GRACE_S = float(os.environ.get("CODEX_L5_CANCEL_GRACE_S", "1.5"))
PROTECTED_FILES = ("fleet.json", "providers.d/codex.yaml")
_ATTEST_LOW = ATTESTATION_HEADER.lower()
_POSTURE = ("zero-canon", "codex", "off", "read-only", "never")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _open_fd_count() -> int:
    try:
        return len(os.listdir("/dev/fd"))
    except OSError:
        return 0


def _reap_owned_pgid(proc: subprocess.Popen[Any], pgid: int, grace_s: float = CANCEL_GRACE_S) -> int:
    """Signal owned PGID (SIGTERM -> grace -> SIGKILL) before/after leader reap (F-FSM-I3)."""
    owned = pgid > 1 and pgid != os.getpgrp()
    try:
        if owned:
            with suppress(ProcessLookupError, OSError):
                os.killpg(pgid, signal.SIGTERM)
    finally:
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            if pipe is not None:
                with suppress(OSError):
                    pipe.close()
        rc = proc.wait(timeout=max(2.0, grace_s))
    if owned and is_pgid_alive(pgid):
        deadline = time.monotonic() + grace_s
        while is_pgid_alive(pgid) and time.monotonic() < deadline:
            threading.Event().wait(0.02)
        if is_pgid_alive(pgid):
            with suppress(ProcessLookupError, OSError):
                os.killpg(pgid, signal.SIGKILL)
            deadline = time.monotonic() + 1.0
            while is_pgid_alive(pgid) and time.monotonic() < deadline:
                threading.Event().wait(0.02)
    return rc


def _responses_sse(model: str, text: str) -> bytes:
    msg: dict[str, Any] = {"type": "message", "id": "m1", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": text}]}
    evs: list[dict[str, Any]] = [
        {"type": "response.created", "response": {"id": "r1", "status": "in_progress", "model": model}},
        {"type": "response.output_item.added", "output_index": 0, "item": {**msg, "status": "in_progress", "content": []}},
        {"type": "response.content_part.added", "item_id": "m1", "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""}},
        {"type": "response.output_text.delta", "item_id": "m1", "output_index": 0, "content_index": 0, "delta": text},
        {"type": "response.output_text.done", "item_id": "m1", "output_index": 0, "content_index": 0, "text": text},
        {"type": "response.output_item.done", "output_index": 0, "item": msg},
        {"type": "response.completed", "response": {"id": "r1", "status": "completed", "model": model, "usage": {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12}}},
    ]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in evs).encode("utf-8")


def _http_post(url: str, payload: Mapping[str, Any], headers: Mapping[str, str]) -> tuple[int, dict[str, str], str]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", **headers}, method="POST")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=TURN_TIMEOUT_S) as resp:
            return int(resp.status), {k.lower(): v for k, v in resp.headers.items()}, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return int(err.code), {k.lower(): v for k, v in err.headers.items()}, err.read().decode("utf-8")


def _extract_terminal_meta(chunks: list[Any]) -> tuple[str, str, str]:
    for ch in reversed(chunks):
        raw = getattr(ch, "raw", None)
        if getattr(ch, "is_terminal", False) and isinstance(raw, dict):
            params = raw.get("params") if isinstance(raw.get("params"), dict) else {}
            turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
            return str(params.get("threadId") or ""), str(turn.get("id") or ""), str(turn.get("status") or "")
    return "", "", ""


def _header_valid(status: int, headers: Mapping[str, str], model: str, effort: str) -> bool:
    raw = headers.get(_ATTEST_LOW, "")
    if status != 200 or not raw:
        return False
    try:
        kv = parse_attestation_header(raw)
    except CodexZeroCanonPolicyError:
        return False
    posture = (kv.get("profile"), kv.get("backend"), kv.get("tools"), kv.get("sandbox"), kv.get("approval"))
    return posture == _POSTURE and kv.get("model") == model and kv.get("effort") == effort and kv.get("phase") in {"admitted", "completed"}


def _verify_seat_response(status: int, headers: Mapping[str, str], body: str, expected: tuple[str, str, bool]) -> tuple[bool, str]:
    """Cycle 4 AND conjunction: valid X-Zero-Canon-Attestation AND complete terminal body."""
    model, effort, is_sse = expected
    if not _header_valid(status, headers, model, effort):
        return False, "zero_canon_attestation_failed"
    if not is_sse:
        doc = json.loads(body)
        choice = (doc.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        text = str(msg.get("content") or "")
        ok = bool(text.strip()) and choice.get("finish_reason") == "stop" and not msg.get("tool_calls") and "error" not in doc
        return (ok, text if ok else "zero_canon_attestation_failed")
    parts, finish, done, errs, tools = list[str](), "", False, 0, 0
    for ln in body.splitlines():
        if not ln.startswith("data: "):
            continue
        raw = ln[6:].strip()
        if raw == "[DONE]":
            done = True
            continue
        fr = json.loads(raw)
        errs += int("error" in fr)
        for ch in fr.get("choices") or ():
            parts.append(str((ch.get("delta") or {}).get("content") or ""))
            tools += len((ch.get("delta") or {}).get("tool_calls") or ())
            finish = str(ch["finish_reason"]) if ch.get("finish_reason") else finish
    text = "".join(parts)
    ok = bool(text.strip()) and finish == "stop" and done and errs == 0 and tools == 0
    return (ok, text if ok else "zero_canon_attestation_failed")


class _IsolatedL5Stand:
    """Loopback 127.0.0.1:0 fake OpenAI Responses + isolated Codex v2 Zero-Canon hub."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp, self.v2_enabled = tmp_path, True
        found = shutil.which("codex")
        assert found, "real codex binary not found in PATH"
        self.codex_bin = found
        self.upstream_reqs: list[tuple[str, dict[str, Any]]] = []
        self.spawned_pgids: list[int] = []
        self.up_srv, self.up_thr = self._start_upstream()
        self.src_home, self.src_codex = self._seed_home(self.up_srv.server_address[1])
        for k, v in (
            ("HOME", str(self.src_home)), ("CODEX_HOME", str(self.src_codex)),
            ("XDG_CONFIG_HOME", str(self.src_home / ".config")), ("XDG_DATA_HOME", str(self.src_home / ".local/share")),
            ("XDG_CACHE_HOME", str(self.src_home / ".cache")), ("XDG_STATE_HOME", str(self.src_home / ".local/state")),
            ("OPENAI_API_KEY", DUMMY_KEY), ("BRIDGE_KEY", DUMMY_KEY), ("NO_PROXY", "127.0.0.1,localhost"),
        ):
            monkeypatch.setenv(k, v)
        self.pool = ResidentProcessPool(StdioPoolConfig(handshake_timeout_s=15.0, turn_idle_timeout_s=TURN_TIMEOUT_S, turn_total_timeout_s=TURN_TIMEOUT_S))
        self.hub_srv, self.hub_thr = self._start_hub()
        self.hub_url = f"http://127.0.0.1:{self.hub_srv.server_address[1]}/v1/chat/completions"

    def _start_upstream(self) -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:
        stand = self

        class _Up(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_a: object) -> None:
                return

            def do_POST(self) -> None:
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8")
                body = json.loads(raw) if raw else {}
                stand.upstream_reqs.append((self.path, body))
                txt = "D1_DECISION: ACCEPT" if "ARL_D1" in raw else ("R1_FINDING: zero-canon ok" if "ARL_R1" in raw else "PONG")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                _ = self.wfile.write(_responses_sse(str(body.get("model") or "gpt-6.1-sol"), txt))
                self.wfile.flush()

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Up)
        thr = threading.Thread(target=srv.serve_forever, daemon=True)
        thr.start()
        return srv, thr

    def _seed_home(self, port: int) -> tuple[Path, Path]:
        home, codex_dir = self.tmp / "disposable_home", self.tmp / "disposable_home" / ".codex"
        zfs.ensure_private_dir(home, 0o700)
        zfs.ensure_private_dir(codex_dir, 0o700)
        cfg = (
            'model_provider = "loopback"\nmodel = "gpt-6.1-sol"\nproject_doc_max_bytes = 0\n'
            '[hooks]\non_turn = "echo CANARY"\n[mcp_servers.canary]\ncommand = "false"\n'
            f'[model_providers.loopback]\nname = "Loopback"\nbase_url = "http://127.0.0.1:{port}/v1"\n'
            'env_key = "OPENAI_API_KEY"\nwire_api = "responses"\n'
        )
        zfs.write_atomic_text_0600(codex_dir / "config.toml", cfg)
        zfs.write_atomic_text_0600(codex_dir / "auth.json", json.dumps({"OPENAI_API_KEY": DUMMY_KEY}))
        return home, codex_dir

    def _execute_codex_turn(self, req: Mapping[str, Any]) -> tuple[str, str, zhttp.ZeroCanonCompletionProof]:
        model, effort = validate_codex_model_effort(str(req.get("model") or ""), req.get("reasoning_effort"))
        prompt = str((req.get("messages") or [{}])[-1].get("content") or "Reply PONG")
        driver = CodexAppServerV2Driver()
        mgr = StdioSessionManager(self.pool, driver, self.pool._config)  # pyright: ignore[reportPrivateUsage]
        key = SlotAffinityKey("l5", f"chat-{time.monotonic_ns()}", "codex", model, effort, str(self.tmp), "Zero-Canon")
        res = mgr.execute_turn(key, prompt, lambda: [self.codex_bin, "app-server"], str(self.tmp), turn_context={"model": model, "effort": effort})
        self.spawned_pgids.append(res.pid)
        assert res.mode is SessionTurnMode.EPHEMERAL
        tid, turn_id, status = _extract_terminal_meta(res.chunks)
        adm = zhttp.ZeroCanonAdmissionProof(
            driver.protocol_state.actual_model or model, driver.protocol_state.actual_effort or effort, tid, turn_id,
            clean_home_verified=True, handshake_acked=True, requested_model=model, requested_effort=effort,
        )
        return "".join(c.text for c in res.chunks), model, zhttp.ZeroCanonCompletionProof(adm, terminal_status=status)

    def _start_hub(self) -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:
        stand = self
        provs = [
            {"route_id": "openai-key-3", "backend": "openai-key-3", "kind": "passthrough", "base_url": "http://127.0.0.1:10830/sg-openai"},
            {"route_id": rcc.CODEX_V2_ROUTE_ID, "backend": "codex", "kind": "stdio_resident"},
        ]

        class _Hub(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_a: object) -> None:
                return

            def _send(self, code: int, ctype: str, data: bytes, extra: Mapping[str, str] | None = None) -> None:
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                _ = self.wfile.write(data)
                self.wfile.flush()

            def do_POST(self) -> None:
                req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
                try:
                    profile = zhttp.parse_review_profile_headers(self.headers)
                    mid = str(req.get("model") or "")
                    if mid in rcc.UNAVAILABLE_MODEL_IDS or mid not in CODEX_EFFORT_MATRIX:
                        return self._send(404, "application/json", json.dumps({"error": {"code": "model_not_found"}}).encode())
                    _ = zhttp.filter_zero_canon_providers(provs, profile, codex_v2_enabled=stand.v2_enabled, model_id=mid)
                    text, model, proof = stand._execute_codex_turn(req)
                except (zhttp.ZeroCanonHttpError, CodexZeroCanonPolicyError) as err:
                    return self._send(err.http_status, "application/json", json.dumps({"error": {"code": err.code, "message": str(err)}}).encode())
                if req.get("stream"):
                    hdr = zhttp.build_attestation_header(proof.admission, phase="admitted")
                    sse = f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'content': text}, 'finish_reason': None}]})}\n\ndata: {json.dumps({'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\ndata: [DONE]\n\n"
                    return self._send(200, "text/event-stream", sse.encode(), {ATTESTATION_HEADER: hdr})
                hdr = zhttp.build_attestation_header(proof, phase="completed")
                body = json.dumps({"model": model, "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]}).encode()
                self._send(200, "application/json", body, {ATTESTATION_HEADER: hdr})

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Hub)
        thr = threading.Thread(target=srv.serve_forever, daemon=True)
        thr.start()
        return srv, thr

    def close(self) -> None:
        self.pool.shutdown()
        for srv, thr in ((self.hub_srv, self.hub_thr), (self.up_srv, self.up_thr)):
            srv.shutdown()
            srv.server_close()
            thr.join(timeout=3.0)


def _run_same_model_cli_fallback(stand: _IsolatedL5Stand, model: str, effort: str, prompt: str) -> tuple[int, str, int]:
    zc_dir = stand.tmp / f"cli-fallback-{time.monotonic_ns()}"
    env = zfs.prepare_codex_zero_canon_home(os.environ, zc_dir)
    assert "BRIDGE_KEY" not in env and "hooks" not in (Path(env["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8")
    out_file = zc_dir / "last_msg.txt"
    argv = [stand.codex_bin, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-c", 'approval_policy="never"', "-c", "project_doc_max_bytes=0", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-o", str(out_file), prompt]
    proc = subprocess.Popen(argv, cwd=str(zc_dir / "cwd"), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    pgid = proc.pid
    try:
        _ = proc.communicate(timeout=TURN_TIMEOUT_S)
    finally:
        rc = _reap_owned_pgid(proc, pgid)
    return rc, (out_file.read_text(encoding="utf-8").strip() if out_file.is_file() else ""), pgid


def test_l5_real_codex_version_and_sol_terra_pong(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L5-01: Real codex 0.171.0-alpha.13 app-server Sol/Terra PONG with ephemeral clean-home & attestation."""
    stand = _IsolatedL5Stand(tmp_path, monkeypatch)
    try:
        cp = subprocess.run([stand.codex_bin, "--version"], capture_output=True, text=True, timeout=10.0, start_new_session=True, check=False)
        assert cp.returncode == 0 and EXPECTED_VER in cp.stdout
        hdrs = {"X-Review-Profile": "Zero-Canon"}
        s1, h1, b1 = _http_post(stand.hub_url, {"model": "gpt-6.1-sol", "reasoning_effort": "high", "stream": True, "messages": [{"role": "user", "content": "Reply PONG"}]}, hdrs)
        ok1, txt1 = _verify_seat_response(s1, h1, b1, ("gpt-6.1-sol", "high", True))
        assert ok1 and "PONG" in txt1 and "phase=admitted" in h1[_ATTEST_LOW]
        s2, h2, b2 = _http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": False, "messages": [{"role": "user", "content": "Reply PONG"}]}, hdrs)
        ok2, txt2 = _verify_seat_response(s2, h2, b2, ("gpt-6.1-terra", "medium", False))
        assert ok2 and "PONG" in txt2 and "phase=completed" in h2[_ATTEST_LOW]
        assert [(b.get("model"), (b.get("reasoning") or {}).get("effort")) for _, b in stand.upstream_reqs] == [("gpt-6.1-sol", "high"), ("gpt-6.1-terra", "medium")]
        assert len(set(stand.spawned_pgids)) == 2
    finally:
        stand.close()
    assert all(not is_pgid_alive(p) for p in stand.spawned_pgids)


def test_l5_terra_arl_r1_d1_medium_and_launch_seat_proof(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L5-02/04: Terra ARL R1->D1 medium through isolated hub + launch_seat/proof atomic receipt."""
    stand = _IsolatedL5Stand(tmp_path, monkeypatch)
    try:
        s_bad, _, b_bad = _http_post(stand.hub_url, {"model": "gpt-6.1-terra", "messages": [{"role": "user", "content": "x"}]}, {"X-Review-Profile": "Zero_Canon"})
        assert s_bad == 400 and "invalid_review_profile" in b_bad
        hdrs = {"X-Review-Profile": "Zero-Canon"}
        s_r1, h_r1, b_r1 = _http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": True, "messages": [{"role": "user", "content": "ARL_R1"}]}, hdrs)
        ok_r1, txt_r1 = _verify_seat_response(s_r1, h_r1, b_r1, ("gpt-6.1-terra", "medium", True))
        assert ok_r1 and "R1_FINDING" in txt_r1
        s_d1, h_d1, b_d1 = _http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": False, "messages": [{"role": "user", "content": f"ARL_D1 {txt_r1}"}]}, hdrs)
        ok_d1, txt_d1 = _verify_seat_response(s_d1, h_d1, b_d1, ("gpt-6.1-terra", "medium", False))
        assert ok_d1 and "D1_DECISION: ACCEPT" in txt_d1
        pdir = tmp_path / "panel_proof"
        zfs.ensure_private_dir(pdir, 0o700)
        zfs.write_atomic_text_0600(pdir / "seat_d1.txt", txt_d1)
        digest = _sha256(pdir / "seat_d1.txt")
        zfs.write_atomic_text_0600(pdir / "proof_receipt.json", json.dumps({"model": "gpt-6.1-terra", "effort": "medium", "r1": h_r1[_ATTEST_LOW], "d1": h_d1[_ATTEST_LOW], "sha256": digest}))
        assert stat.S_IMODE((pdir / "proof_receipt.json").stat().st_mode) == 0o600
        assert json.loads(zfs.read_regular_file_nofollow(pdir / "proof_receipt.json").decode())["sha256"] == digest
        assert _ATTEST_LOW not in {k.lower() for k in zhttp.strip_upstream_attestation({ATTESTATION_HEADER: "spoof", "X-Ok": "1"})}
    finally:
        stand.close()
    assert all(not is_pgid_alive(p) for p in stand.spawned_pgids)


def test_l5_same_model_bridge_to_cli_fallback_with_pgid_teardown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L5-03: V2-off 503 fails attestation -> proven PGID teardown -> same-model codex CLI fallback."""
    stand = _IsolatedL5Stand(tmp_path, monkeypatch)
    cli_pgid = 0
    try:
        stand.v2_enabled = False
        st, hdrs, body = _http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": False, "messages": [{"role": "user", "content": "Reply PONG"}]}, {"X-Review-Profile": "Zero-Canon"})
        assert st == 503 and "zero_canon_unsupported_by_driver" in body and _ATTEST_LOW not in hdrs
        assert _verify_seat_response(st, hdrs, body, ("gpt-6.1-terra", "medium", False)) == (False, "zero_canon_attestation_failed")
        assert all(not is_pgid_alive(p) for p in stand.spawned_pgids)
        rc, out_txt, cli_pgid = _run_same_model_cli_fallback(stand, "gpt-6.1-terra", "medium", "Reply PONG")
        assert rc == 0 and "PONG" in out_txt
        assert [(b.get("model"), (b.get("reasoning") or {}).get("effort")) for _, b in stand.upstream_reqs] == [("gpt-6.1-terra", "medium")]
    finally:
        stand.close()
    assert cli_pgid > 0 and not is_pgid_alive(cli_pgid)


def test_l5_recovery_pong_readback_gpt62_negative_and_hygiene(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L5-05/06/07: Recovery PONG receipt read-back, gpt-6.2-sol negative, and zero-leak hygiene."""
    before_hashes, fd_before = {rel: _sha256(ROOT / rel) for rel in PROTECTED_FILES}, _open_fd_count()
    stand = _IsolatedL5Stand(tmp_path, monkeypatch)
    ports = (stand.hub_srv.server_address[1], stand.up_srv.server_address[1])
    try:
        exp = rec.ProbeExpectation("gpt-6.1-terra", "medium", "codex", rcc.CODEX_V2_ROUTE_ID, "zero-canon")
        st = rec.create_recovery_state(exp, "cred-l5", rec.RecoveryPhase.BLOCKED, rec.RecoveryPhase.HEALTHY)
        st, _ = rec.transition(st, rec.RecoveryEvent(rec.RecoveryEventKind.SCHEDULE_PROBE, 1.0, rec.HealthDomain.ROUTE))
        st, _ = rec.transition(st, rec.RecoveryEvent(rec.RecoveryEventKind.PROBE_STARTED, 2.0, rec.HealthDomain.ROUTE, probe_id="probe-l5"))
        st_rej, eff_rej = rec.transition(st, rec.RecoveryEvent(rec.RecoveryEventKind.NON_PONG_SIGNAL, 3.0, rec.HealthDomain.ROUTE, evidence_kind=rec.EvidenceKind.HEALTH_200))
        assert not st_rej.is_route_healthy and eff_rej[0].kind is rec.RecoveryEffectKind.REJECT_TRANSITION
        code, hdrs, body = _http_post(stand.hub_url, {"model": "gpt-6.1-terra", "reasoning_effort": "medium", "stream": False, "messages": [{"role": "user", "content": "Reply PONG"}]}, {"X-Review-Profile": "Zero-Canon"})
        ok, content = _verify_seat_response(code, hdrs, body, ("gpt-6.1-terra", "medium", False))
        assert ok
        rcpt_path = tmp_path / "recovery_pong_receipt.json"
        zfs.write_atomic_text_0600(rcpt_path, json.dumps({"probe_id": "probe-l5", "model": "gpt-6.1-terra", "effort": "medium", "attestation": hdrs[_ATTEST_LOW], "content": content}))
        rb = json.loads(zfs.read_regular_file_nofollow(rcpt_path).decode("utf-8"))
        pong = rec.PongReceipt(rb["probe_id"], rb["model"], rb["model"], rb["effort"], rb["effort"], "codex", rcc.CODEX_V2_ROUTE_ID, "zero-canon", rb["attestation"], True, True, rb["content"])
        healthy, effs = rec.transition(st, rec.RecoveryEvent(rec.RecoveryEventKind.PONG_RECEIPT, 4.0, rec.HealthDomain.ROUTE, receipt=pong))
        assert healthy.is_healthy and any(e.kind is rec.RecoveryEffectKind.EMIT_RECOVERY_RECEIPT for e in effs)
        assert "gpt-6.2-sol" in rcc.UNAVAILABLE_MODEL_IDS
        rcc.validate_no_forbidden_aliases(json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))["aliases"])
        with pytest.raises(CodexZeroCanonPolicyError, match="Unsupported Codex model"):
            _ = validate_codex_model_effort("gpt-6.2-sol", "high")
        reqs_before = len(stand.upstream_reqs)
        s62, h62, b62 = _http_post(stand.hub_url, {"model": "gpt-6.2-sol", "reasoning_effort": "high", "messages": [{"role": "user", "content": "PONG"}]}, {"X-Review-Profile": "Zero-Canon"})
        assert s62 == 404 and "model_not_found" in b62 and _ATTEST_LOW not in h62 and len(stand.upstream_reqs) == reqs_before
    finally:
        stand.close()
    assert all(not is_pgid_alive(p) for p in stand.spawned_pgids)
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            assert sock.connect_ex(("127.0.0.1", port)) != 0
    assert {rel: _sha256(ROOT / rel) for rel in PROTECTED_FILES} == before_hashes and _open_fd_count() <= fd_before + 4

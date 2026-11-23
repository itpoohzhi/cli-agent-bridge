"""Shared isolated stand, PGID teardown, and seat response helpers for L5 Codex E2E tests."""

# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false

from __future__ import annotations

import hashlib
import http.server
import json
import os
import shutil
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any

import pytest

from core import route_catalog_contract as rcc
from core import zero_canon_fs as zfs
from core import zero_canon_http as zhttp
from core.codex_zero_canon_policy import ATTESTATION_HEADER, CODEX_EFFORT_MATRIX, CodexZeroCanonPolicyError, parse_attestation_header, validate_codex_model_effort
from core.stdio_resident.codex_driver import CodexAppServerV2Driver
from core.stdio_resident.config import StdioPoolConfig
from core.stdio_resident.process_pool import ResidentProcessPool
from core.stdio_resident.process_reaper import is_pgid_alive
from core.stdio_resident.session_manager import SessionTurnMode, StdioSessionManager
from core.stdio_resident.types import SlotAffinityKey

DUMMY_KEY, ATTEST_LOW = "sk-dummy-test-000", ATTESTATION_HEADER.lower()
EXPECTED_VER = os.environ.get("CODEX_L5_EXPECTED_VERSION", "0.171.0-alpha.13")
TURN_TIMEOUT_S = float(os.environ.get("CODEX_L5_TURN_TIMEOUT_S", "25.0"))
CANCEL_GRACE_S = float(os.environ.get("CODEX_L5_CANCEL_GRACE_S", "1.5"))
PROTECTED_FILES = ("fleet.json", "providers.d/codex.yaml")
_POSTURE = ("zero-canon", "codex", "off", "read-only", "never")


def sha256_file(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def open_fd_count() -> int:
    try:
        return len(os.listdir("/dev/fd"))
    except OSError:
        return 0


def _wait_pgid_exit(pgid: int, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while is_pgid_alive(pgid) and time.monotonic() < deadline:
        threading.Event().wait(0.02)
    return not is_pgid_alive(pgid)


def _close_pipes(proc: subprocess.Popen[Any]) -> None:
    for pipe in (proc.stdin, proc.stdout, proc.stderr):
        if pipe is not None:
            with suppress(OSError):
                pipe.close()


def reap_owned_pgid(proc: subprocess.Popen[Any], pgid: int, grace_s: float = CANCEL_GRACE_S) -> int:
    """Signal owned PGID (SIGTERM -> grace -> SIGKILL) before/after leader reap (F-FSM-I3)."""
    owned = pgid > 1 and pgid != os.getpgrp()
    try:
        if owned:
            with suppress(ProcessLookupError, OSError):
                os.killpg(pgid, signal.SIGTERM)
    finally:
        _close_pipes(proc)
        rc = proc.wait(timeout=max(2.0, grace_s))
    if owned and not _wait_pgid_exit(pgid, grace_s):
        with suppress(ProcessLookupError, OSError):
            os.killpg(pgid, signal.SIGKILL)
        _wait_pgid_exit(pgid, 1.0)
    return rc


def _responses_sse(model: str, text: str) -> bytes:
    msg: dict[str, Any] = {"type": "message", "id": "m1", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": text}]}
    evs = (
        {"type": "response.created", "response": {"id": "r1", "status": "in_progress", "model": model}},
        {"type": "response.output_item.added", "output_index": 0, "item": {**msg, "status": "in_progress", "content": []}},
        {"type": "response.content_part.added", "item_id": "m1", "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""}},
        {"type": "response.output_text.delta", "item_id": "m1", "output_index": 0, "content_index": 0, "delta": text},
        {"type": "response.output_text.done", "item_id": "m1", "output_index": 0, "content_index": 0, "text": text},
        {"type": "response.output_item.done", "output_index": 0, "item": msg},
        {"type": "response.completed", "response": {"id": "r1", "status": "completed", "model": model, "usage": {"input_tokens": 8, "output_tokens": 4, "total_tokens": 12}}},
    )
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in evs).encode("utf-8")


def http_post(url: str, payload: Mapping[str, Any], headers: Mapping[str, str]) -> tuple[int, dict[str, str], str]:
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
    raw = headers.get(ATTEST_LOW, "")
    if status != 200 or not raw:
        return False
    try:
        kv = parse_attestation_header(raw)
    except CodexZeroCanonPolicyError:
        return False
    posture = (kv.get("profile"), kv.get("backend"), kv.get("tools"), kv.get("sandbox"), kv.get("approval"))
    return posture == _POSTURE and kv.get("model") == model and kv.get("effort") == effort and kv.get("phase") in {"admitted", "completed"}


def _verify_json_seat_body(body: str) -> tuple[bool, str]:
    doc = json.loads(body)
    choice = (doc.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = str(msg.get("content") or "")
    ok = all((text.strip(), choice.get("finish_reason") == "stop", not msg.get("tool_calls"), "error" not in doc))
    return (ok, text if ok else "zero_canon_attestation_failed")


def _accumulate_sse_frame(raw: str, parts: list[str], finish: str) -> tuple[str, int, int]:
    fr = json.loads(raw)
    errs, tools = int("error" in fr), 0
    for ch in fr.get("choices") or ():
        delta = ch.get("delta") or {}
        parts.append(str(delta.get("content") or ""))
        tools += len(delta.get("tool_calls") or ())
        finish = str(ch["finish_reason"]) if ch.get("finish_reason") else finish
    return finish, errs, tools


def _verify_sse_seat_body(body: str) -> tuple[bool, str]:
    parts, finish, done, errs, tools = list[str](), "", False, 0, 0
    for ln in body.splitlines():
        if not ln.startswith("data: "):
            continue
        raw = ln[6:].strip()
        if raw == "[DONE]":
            done = True
            continue
        finish, f_err, f_tools = _accumulate_sse_frame(raw, parts, finish)
        errs, tools = errs + f_err, tools + f_tools
    text = "".join(parts)
    ok = all((text.strip(), finish == "stop", done, errs == 0, tools == 0))
    return (ok, text if ok else "zero_canon_attestation_failed")


def verify_seat_response(status: int, headers: Mapping[str, str], body: str, expected: tuple[str, str, bool]) -> tuple[bool, str]:
    """Cycle 4 AND conjunction: valid X-Zero-Canon-Attestation AND complete terminal body."""
    model, effort, is_sse = expected
    if not _header_valid(status, headers, model, effort):
        return False, "zero_canon_attestation_failed"
    return _verify_sse_seat_body(body) if is_sse else _verify_json_seat_body(body)


def _start_srv(handler_cls: type[http.server.BaseHTTPRequestHandler]) -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thr = threading.Thread(target=srv.serve_forever, daemon=True)
    thr.start()
    return srv, thr


class IsolatedL5Stand:
    """Loopback 127.0.0.1:0 fake OpenAI Responses + isolated Codex v2 Zero-Canon hub."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp, self.v2_enabled = tmp_path, True
        found = shutil.which("codex")
        assert found, "real codex binary not found in PATH"
        self.codex_bin, self.upstream_reqs, self.spawned_pgids = found, list[tuple[str, dict[str, Any]]](), list[int]()
        self.up_srv, self.up_thr = self._start_upstream()
        self.src_home, self.src_codex = self._seed_home(self.up_srv.server_address[1])
        env_map = {
            "HOME": str(self.src_home), "CODEX_HOME": str(self.src_codex), "XDG_CONFIG_HOME": str(self.src_home / ".config"),
            "XDG_DATA_HOME": str(self.src_home / ".local/share"), "XDG_CACHE_HOME": str(self.src_home / ".cache"),
            "XDG_STATE_HOME": str(self.src_home / ".local/state"), "OPENAI_API_KEY": DUMMY_KEY, "BRIDGE_KEY": DUMMY_KEY, "NO_PROXY": "127.0.0.1,localhost",
        }
        for k, v in env_map.items():
            monkeypatch.setenv(k, v)
        self.pool = ResidentProcessPool(StdioPoolConfig(handshake_timeout_s=15.0, turn_idle_timeout_s=TURN_TIMEOUT_S, turn_total_timeout_s=TURN_TIMEOUT_S))
        self.hub_srv, self.hub_thr = self._start_hub()
        self.hub_url = f"http://127.0.0.1:{self.hub_srv.server_address[1]}/v1/chat/completions"

    def _start_upstream(self) -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:
        stand = self

        class _Up(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_a: object) -> None: return
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

        return _start_srv(_Up)

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
        adm = zhttp.ZeroCanonAdmissionProof(driver.protocol_state.actual_model or model, driver.protocol_state.actual_effort or effort, tid, turn_id, clean_home_verified=True, handshake_acked=True, requested_model=model, requested_effort=effort)
        return "".join(c.text for c in res.chunks), model, zhttp.ZeroCanonCompletionProof(adm, terminal_status=status)

    def _start_hub(self) -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:
        stand = self
        provs = [{"route_id": "openai-key-3", "backend": "openai-key-3", "kind": "passthrough", "base_url": "http://127.0.0.1:10830/sg-openai"}, {"route_id": rcc.CODEX_V2_ROUTE_ID, "backend": "codex", "kind": "stdio_resident"}]

        class _Hub(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_a: object) -> None: return
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
                    profile, mid = zhttp.parse_review_profile_headers(self.headers), str(req.get("model") or "")
                    if mid in rcc.UNAVAILABLE_MODEL_IDS or mid not in CODEX_EFFORT_MATRIX:
                        return self._send(404, "application/json", json.dumps({"error": {"code": "model_not_found"}}).encode())
                    _ = zhttp.filter_zero_canon_providers(provs, profile, codex_v2_enabled=stand.v2_enabled, model_id=mid)
                    text, model, proof = stand._execute_codex_turn(req)
                except (zhttp.ZeroCanonHttpError, CodexZeroCanonPolicyError) as err:
                    return self._send(err.http_status, "application/json", json.dumps({"error": {"code": err.code, "message": str(err)}}).encode())
                if req.get("stream"):
                    sse = f"data: {json.dumps({'choices': [{'index': 0, 'delta': {'content': text}, 'finish_reason': None}]})}\n\ndata: {json.dumps({'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\ndata: [DONE]\n\n"
                    return self._send(200, "text/event-stream", sse.encode(), {ATTESTATION_HEADER: zhttp.build_attestation_header(proof.admission, phase="admitted")})
                body = json.dumps({"model": model, "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}]}).encode()
                self._send(200, "application/json", body, {ATTESTATION_HEADER: zhttp.build_attestation_header(proof, phase="completed")})

        return _start_srv(_Hub)

    def close(self) -> None:
        self.pool.shutdown()
        for srv, thr in ((self.hub_srv, self.hub_thr), (self.up_srv, self.up_thr)):
            srv.shutdown()
            srv.server_close()
            thr.join(timeout=3.0)


def run_same_model_cli_fallback(stand: IsolatedL5Stand, model: str, effort: str, prompt: str) -> tuple[int, str, int]:
    zc_dir = stand.tmp / f"cli-fallback-{time.monotonic_ns()}"
    env = zfs.prepare_codex_zero_canon_home(os.environ, zc_dir)
    assert "BRIDGE_KEY" not in env and "hooks" not in (Path(env["CODEX_HOME"]) / "config.toml").read_text(encoding="utf-8")
    out_file = zc_dir / "last_msg.txt"
    argv = [stand.codex_bin, "exec", "--skip-git-repo-check", "--sandbox", "read-only", "-c", 'approval_policy="never"', "-c", "project_doc_max_bytes=0", "-m", model, "-c", f'model_reasoning_effort="{effort}"', "-o", str(out_file), prompt]
    proc = subprocess.Popen(argv, cwd=str(zc_dir / "cwd"), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        _ = proc.communicate(timeout=TURN_TIMEOUT_S)
    finally:
        rc = reap_owned_pgid(proc, proc.pid)
    return rc, (out_file.read_text(encoding="utf-8").strip() if out_file.is_file() else ""), proc.pid

"""Isolated L2 loopback tests for Codex app-server v2 and strict Zero-Canon (W3-C)."""

from __future__ import annotations

import hashlib
import http.client
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.stdio_resident_adapter import StdioResidentAdapter  # noqa: E402
from core import codex_zero_canon_policy as zpol  # noqa: E402
from core import zero_canon_http as zhttp  # noqa: E402
from core.stdio_resident import sse_error_bridge as seb  # noqa: E402
from core.stdio_resident.process_reaper import is_pgid_alive  # noqa: E402
from core.stdio_resident.turn_error_sse import DONE_FRAME, build_turn_error  # noqa: E402
from core.stdio_resident.types import SlotAffinityKey  # noqa: E402
from tests.transport_wire_support import RunningHTTPServer  # noqa: E402

DUMMY_KEY, SOL, TERRA = "sk-dummy-test-000", "gpt-6.1-sol", "gpt-6.1-terra"
V2_FLAG, ZC_HDR = "BRIDGE_CODEX_APP_SERVER_V2_ENABLED", {"X-Review-Profile": "Zero-Canon"}
ATT_HDR = zpol.ATTESTATION_HEADER
CODEX_ROUTE = [{"route_id": "codex-app-server-v2", "backend": "codex", "kind": "stdio_resident"}]

_FAKE_CODEX = (
    "import argparse,json,os,stat,sys\n"
    "p=argparse.ArgumentParser();p.add_argument('--mode',default='ok');p.add_argument('--trace',required=True)\n"
    "a,_=p.parse_known_args();ch=os.environ.get('CODEX_HOME','');ap,cp=os.path.join(ch,'auth.json'),os.path.join(ch,'config.toml')\n"
    "rec={'pid':os.getpid(),'pgid':os.getpgrp(),'home':os.environ.get('HOME',''),'frames':[]}\n"
    "if os.path.exists(ap): rec['auth_mode']=stat.S_IMODE(os.stat(ap).st_mode)\n"
    "if os.path.exists(cp): rec['cfg']=open(cp,encoding='utf-8').read()\n"
    "emit=lambda o:(sys.stdout.write(json.dumps(o,separators=(',',':'))+'\\n'),sys.stdout.flush())\n"
    "save=lambda:open(a.trace,'a',encoding='utf-8').write(json.dumps(rec)+'\\n')\n"
    "tid,turn_id=f'thr-srv-{os.getpid()}','trn-srv-1'\n"
    "for raw in sys.stdin:\n"
    " if not raw.strip(): continue\n"
    " msg=json.loads(raw);rec['frames'].append(msg);m,rid,pr=msg.get('method'),msg.get('id'),msg.get('params') or {}\n"
    " if m=='initialize': sys.stderr.write('WARN Bearer sk-dummy-test-000\\n');sys.stderr.flush();emit({'id':rid,'result':{'userAgent':'codex/0.171.0-alpha.13'}})\n"
    " elif m=='thread/start': emit({'id':rid,'result':{'thread':{'id':tid},'model':pr.get('model') or 'gpt-6.1-sol'}})\n"
    " elif m=='turn/start':\n"
    "  emit({'id':rid,'result':{'turn':{'id':turn_id,'status':'inProgress'}}})\n"
    "  if a.mode=='overflow_frame': sys.stdout.write('{\"x\":\"'+'A'*1024+'\"}\\n');sys.stdout.flush();save();break\n"
    "  emit({'method':'item/reasoning/textDelta','params':{'threadId':tid,'turnId':turn_id,'delta':'chk'}})\n"
    "  if a.mode=='tool_event': emit({'method':'item/tool/call','params':{'threadId':tid,'turnId':turn_id,'name':'sh'}});save();break\n"
    "  emit({'method':'item/agentMessage/delta','params':{'threadId':tid,'turnId':turn_id,'delta':'PONG'}})\n"
    "  if a.mode=='incomplete': save();break\n"
    "  if a.mode=='hang': save();continue\n"
    "  emit({'method':'turn/completed','params':{'threadId':tid,'turn':{'id':turn_id,'status':'completed'}}});save()\n"
    " elif m=='turn/interrupt': save();emit({'id':rid,'result':{}});break\n"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seed_env(tmp_path: Path, mp: pytest.MonkeyPatch, *, v2_on: bool = True) -> tuple[Path, dict[str, str], Path]:
    home = tmp_path / "real_home"
    codex_dir, dsh_dir = home / ".codex", home / ".dsh"
    codex_dir.mkdir(parents=True, mode=0o700)
    dsh_dir.mkdir(parents=True, mode=0o700)
    cfg, auth, dsh, dyn = codex_dir / "config.toml", codex_dir / "auth.json", dsh_dir / "profile.yml", tmp_path / "dynamic_config.json"
    cfg.write_text('model = "gpt-6.1-sol"\n[mcp_servers.x]\ncmd = "echo"\n[hooks]\non_turn = "x"\n', encoding="utf-8")
    auth.write_text(json.dumps({"OPENAI_API_KEY": DUMMY_KEY}), encoding="utf-8")
    dsh.write_text("profile: canary\n", encoding="utf-8")
    dyn.write_text(json.dumps({V2_FLAG: v2_on}), encoding="utf-8")
    env = {"HOME": str(home), "CODEX_HOME": str(codex_dir), "XDG_CONFIG_HOME": str(home / ".config"), "BRIDGE_DYNAMIC_CONFIG_PATH": str(dyn), "BRIDGE_STDIO_RESIDENT_ENABLED": "1", "BRIDGE_STDIO_CANCEL_GRACE_S": "0.1", "BRIDGE_KEY": DUMMY_KEY}
    for k, v in env.items():
        mp.setenv(k, v)
    script = tmp_path / "fake_codex.py"
    script.write_text(_FAKE_CODEX, encoding="utf-8")
    return script, {str(p): _sha256(p) for p in (cfg, auth, dsh)}, dyn


def _make_adapter(script: Path, trace: Path, mode: str = "ok") -> StdioResidentAdapter:
    argv = [sys.executable, str(script), "--mode", mode, "--trace", str(trace)]
    return StdioResidentAdapter("codex", {"bridge": {"options": {"cli_argv": argv}}}, cli_argv=argv)


def _post(port: int, payload: dict[str, Any], headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], str]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        hdrs = {"Content-Type": "application/json", "Authorization": f"Bearer {DUMMY_KEY}", **(headers or {})}
        conn.request("POST", "/v1/chat/completions", body=json.dumps(payload).encode("utf-8"), headers=hdrs)
        resp = conn.getresponse()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read().decode("utf-8")
    finally:
        conn.close()


def _send_json(handler: BaseHTTPRequestHandler, status: int, body: dict[str, Any], extra: list[tuple[str, str]] = []) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    for k, v in extra:
        handler.send_header(k, v)
    handler.end_headers()
    _ = handler.wfile.write(json.dumps(body).encode("utf-8"))


def _make_upstream(status: int, body: dict[str, Any], extra: list[tuple[str, str]]) -> tuple[RunningHTTPServer, list[int]]:
    hits: list[int] = []

    class _Up(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None: return
        def do_POST(self) -> None:
            _ = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            hits.append(1)
            _send_json(self, status, body, extra)

    return RunningHTTPServer(_Up), hits


def _stream_codex(handler: BaseHTTPRequestHandler, first: dict[str, Any], it: Any, adm: zhttp.ZeroCanonAdmissionProof | None) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    zhttp.emit_turn_headers(handler, None, [], ("", None), attestation=(adm, "admitted") if adm else None)
    setattr(handler, "_headers_already_sent", True)
    live = 0
    emit = lambda f: (handler.wfile.write(f.encode("utf-8")), handler.wfile.flush(), True)[2]  # noqa: E731
    try:
        for ch in (first, *it):
            live += 1
            _ = emit(f"data: {json.dumps(ch)}\n\n")
        _ = emit(DONE_FRAME)
    except Exception as exc:
        lease = type("_L", (), {"record_failure": lambda *_: None, "record_discard": lambda *_: None})()
        ctx = seb.SseErrorContext(handler, lease, emit, lambda m, **kw: f"data: {json.dumps({'error': {'message': m, **kw}})}\n\n", lambda _: None)
        _ = seb.handle_sse_stream_exception(exc, live, ctx)


def _collect_non_stream(first: dict[str, Any], it: Any) -> tuple[str, bool]:
    parts = [str(first["choices"][0]["delta"].get("content", ""))]
    done = first["choices"][0]["finish_reason"] == "stop"
    for ch in it:
        parts.append(str(ch["choices"][0]["delta"].get("content", "")))
        done = done or ch["choices"][0]["finish_reason"] == "stop"
    return "".join(parts), done


def _send_codex_json(handler: BaseHTTPRequestHandler, text: str, adm: zhttp.ZeroCanonAdmissionProof, done: bool, is_zc: bool) -> None:
    comp = zhttp.ZeroCanonCompletionProof(adm, terminal_status="completed" if done else "incomplete") if is_zc else None
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    zhttp.emit_turn_headers(handler, None, [], ("", None), attestation=(comp, "completed") if comp else None)
    _ = handler.wfile.write(json.dumps({"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}).encode("utf-8"))


def _run_codex(handler: BaseHTTPRequestHandler, adapter: StdioResidentAdapter, body: dict[str, Any], cwd: Path, is_zc: bool) -> None:
    clean = zpol.sanitize_strict_request(body) if is_zc else dict(body)
    model, effort = str(clean.get("model", SOL)), str(clean.get("reasoning_effort", "high"))
    it = adapter.execute_chat({"model": model, "effort": effort, "cwd": str(cwd), "prompt": "PING", "review_profile": "Zero-Canon" if is_zc else "standard"})
    try:
        first = next(it)
        st = adapter._driver.protocol_state  # type: ignore[attr-defined]
        adm = zhttp.ZeroCanonAdmissionProof(model, effort, st.thread_id or "", st.turn_id or "", clean_home_verified=is_zc, handshake_acked=True, requested_model=model, requested_effort=effort)
        if bool(clean.get("stream", False)):
            return _stream_codex(handler, first, it, adm if is_zc else None)
        text, done = _collect_non_stream(first, it)
    except Exception as exc:
        err = build_turn_error(exc, live_sent=0)
        return _send_json(handler, err.status, {"error": {"code": err.code, "message": err.message}})
    _send_codex_json(handler, text, adm, done, is_zc)


def _make_hub(adapter: StdioResidentAdapter, routes: list[dict[str, Any]], cwd: Path) -> RunningHTTPServer:
    class _Hub(BaseHTTPRequestHandler):
        def log_message(self, *_: object) -> None: return
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
            try:
                profile = zhttp.parse_review_profile_headers(self.headers)
                kept = zhttp.filter_zero_canon_providers(routes, profile, model_id=str(body.get("model", "")))
            except zhttp.ZeroCanonHttpError as exc:
                return _send_json(self, exc.status_code, {"error": {"code": exc.code, "message": str(exc)}})
            if not kept:
                return _send_json(self, 503, {"error": {"code": "route_unavailable", "message": "no route"}})
            chosen = kept[0]
            if chosen.get("kind") == "passthrough":
                st, hdrs, text = _post(int(str(chosen["base_url"]).split(":")[2].split("/")[0]), body)
                self.send_response(st)
                zhttp.emit_passthrough_headers(self, list(hdrs.items()), frozenset(), [], lambda k, _: k != "transfer-encoding")
                self.end_headers()
                _ = self.wfile.write(text.encode("utf-8"))
                return
            _run_codex(self, adapter, body, cwd, profile == zhttp.ZERO_CANON_HEADER_VALUE)

    return RunningHTTPServer(_Hub)


def _assert_runs_clean(trace: Path) -> None:
    runs = [json.loads(ln) for ln in trace.read_text(encoding="utf-8").splitlines()]
    assert (len(runs), runs[0]["pid"] != runs[1]["pid"], runs[0]["home"] != runs[1]["home"]) == (2, True, True)
    for r in runs:
        assert (r["auth_mode"], "hooks" in r["cfg"], "project_doc_max_bytes = 0" in r["cfg"]) == (0o600, False, True)
        t_start = next(f["params"] for f in r["frames"] if f.get("method") == "turn/start")
        assert (t_start["sandboxPolicy"], is_pgid_alive(r["pgid"])) == ({"type": "readOnly", "networkAccess": False}, False)


def test_loopback_zero_canon_two_phase_attestation_tools_off_and_canary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L2-01: Two-phase attestation (admitted/completed), tools-off, clean-home, PGID teardown, canary."""
    script, canary_before, _ = _seed_env(tmp_path, monkeypatch, v2_on=True)
    trace = tmp_path / "trace.jsonl"
    adapter = _make_adapter(script, trace, "ok")
    try:
        with _make_hub(adapter, CODEX_ROUTE, tmp_path) as hub:
            req = {"model": TERRA, "reasoning_effort": "medium", "tools": [{"type": "function"}], "emulate_tools": True}
            st_ns, hdrs_ns, body_ns = _post(hub.port, {**req, "stream": False}, ZC_HDR)
            st_sse, hdrs_sse, body_sse = _post(hub.port, {**req, "stream": True}, ZC_HDR)
        assert (st_ns, st_sse, json.loads(body_ns)["choices"][0]["message"]["content"]) == (200, 200, "PONG")
        assert ("PONG" in body_sse, body_sse.endswith(DONE_FRAME)) == (True, True)
        a_ns, a_sse = zpol.parse_attestation_header(hdrs_ns[ATT_HDR.lower()]), zpol.parse_attestation_header(hdrs_sse[ATT_HDR.lower()])
        assert (a_ns["phase"], a_sse["phase"], a_ns["model"], a_ns["effort"], a_ns["tools"]) == ("completed", "admitted", TERRA, "medium", "off")
        _assert_runs_clean(trace)
        assert {p: _sha256(Path(p)) for p in canary_before} == canary_before
        with pytest.raises(OSError):
            _ = _post(hub.port, req)
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_loopback_flag_off_503_profile_typo_400_and_spoof_strip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L2-02: V2 flag-off -> 503, Zero_Canon typo -> 400, external spoofed attestation stripped."""
    script, _, dyn_cfg = _seed_env(tmp_path, monkeypatch, v2_on=False)
    adapter = _make_adapter(script, tmp_path / "t2.jsonl", "ok")
    up_srv, up_hits = _make_upstream(200, {"choices": [{"message": {"content": "std"}}]}, [(ATT_HDR, "spoof"), ("X-Up", "ok")])
    try:
        with up_srv:
            routes = [{"route_id": "sg-openai", "backend": "openai-key-3", "kind": "passthrough", "base_url": f"http://127.0.0.1:{up_srv.port}/sg-openai"}, *CODEX_ROUTE]
            with _make_hub(adapter, routes, tmp_path) as hub:
                st400, h400, b400 = _post(hub.port, {"model": SOL}, {"X-Review-Profile": "Zero_Canon"})
                st503, h503, b503 = _post(hub.port, {"model": SOL}, ZC_HDR)
                st_std, h_std, _ = _post(hub.port, {"model": SOL}, {"X-Review-Profile": "standard"})
                assert (st400, json.loads(b400)["error"]["code"]) == (400, "invalid_review_profile")
                assert (st503, json.loads(b503)["error"]["code"]) == (503, "zero_canon_unsupported_by_driver")
                assert (ATT_HDR.lower() in h400, ATT_HDR.lower() in h503) == (False, False)
                assert (st_std, ATT_HDR.lower() in h_std, h_std["x-up"], len(up_hits)) == (200, False, "ok", 1)
                dyn_cfg.write_text(json.dumps({V2_FLAG: True}), encoding="utf-8")
                st_zc, h_zc, _ = _post(hub.port, {"model": SOL}, ZC_HDR)
                assert (st_zc, ATT_HDR.lower() in h_zc, len(up_hits)) == (200, True, 1)
    finally:
        adapter.shutdown(timeout_s=1.0)


def test_loopback_tool_event_incomplete_and_failover_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L2-03: Tool event & EOF never attest; 503/429 pre-byte failover allowed, post-byte forbidden."""
    script, _, _ = _seed_env(tmp_path, monkeypatch, v2_on=True)
    tr_t, tr_e, tr_ok = tmp_path / "t.jsonl", tmp_path / "e.jsonl", tmp_path / "ok.jsonl"
    ad_t, ad_e, ad_ok = _make_adapter(script, tr_t, "tool_event"), _make_adapter(script, tr_e, "incomplete"), _make_adapter(script, tr_ok, "ok")
    up_503, hits_503 = _make_upstream(503, {"error": "No available accounts"}, [])
    try:
        with _make_hub(ad_t, CODEX_ROUTE, tmp_path) as ht, _make_hub(ad_e, CODEX_ROUTE, tmp_path) as he, _make_hub(ad_ok, CODEX_ROUTE, tmp_path) as hok, up_503:
            st_t, hdr_t, bt = _post(ht.port, {"model": SOL, "stream": False}, ZC_HDR)
            st_ts, _, bts = _post(ht.port, {"model": SOL, "stream": True}, ZC_HDR)
            st_e, hdr_e, be = _post(he.port, {"model": SOL, "stream": False}, ZC_HDR)
            assert (st_t, json.loads(bt)["error"]["code"], ATT_HDR.lower() in hdr_t, DUMMY_KEY in bt) == (502, "zero_canon_tool_event_forbidden", False, False)
            assert (st_ts, "zero_canon_tool_event_forbidden" in bts, '"finish_reason": "stop"' in bts, bts.endswith(DONE_FRAME)) == (200, True, False, True)
            assert (st_e, json.loads(be)["error"]["code"], ATT_HDR.lower() in hdr_e) == (502, "upstream_incomplete_stream", False)
            st_u, _, bu = _post(up_503.port, {"model": SOL})
            assert (zpol.classify_error(bu, status_code=st_u, bytes_sent=0).allow_same_model_failover, len(hits_503)) == (True, 1)
            assert zpol.classify_error(bu, status_code=st_u, bytes_sent=8).allow_same_model_failover is False
            st_fo, h_fo, b_fo = _post(hok.port, {"model": SOL, "reasoning_effort": "high"}, ZC_HDR)
            assert (st_fo, json.loads(b_fo)["choices"][0]["message"]["content"], ATT_HDR.lower() in h_fo) == (200, "PONG", True)
        for tr in (tr_t, tr_e, tr_ok):
            assert all(not is_pgid_alive(json.loads(ln)["pgid"]) for ln in tr.read_text(encoding="utf-8").splitlines())
    finally:
        for ad in (ad_t, ad_e, ad_ok):
            ad.shutdown(timeout_s=1.0)


def test_loopback_memory_cap_overflow_and_cancel_pgid_teardown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """L2-04: Frame cap overflow returns 502 without attestation; cancel kills own PGID."""
    script, _, _ = _seed_env(tmp_path, monkeypatch, v2_on=True)
    monkeypatch.setenv("BRIDGE_STDIO_FRAME_MAX_BYTES", "256")
    tr_ov, tr_hang = tmp_path / "ov.jsonl", tmp_path / "hang.jsonl"
    ad_ov, ad_hang = _make_adapter(script, tr_ov, "overflow_frame"), _make_adapter(script, tr_hang, "hang")
    try:
        with _make_hub(ad_ov, CODEX_ROUTE, tmp_path) as hub:
            st, hdrs, body = _post(hub.port, {"model": SOL, "stream": False}, ZC_HDR)
        assert (st, json.loads(body)["error"]["code"], ATT_HDR.lower() in hdrs) == (502, "output_limit_exceeded", False)
        assert not is_pgid_alive(json.loads(tr_ov.read_text(encoding="utf-8").splitlines()[0])["pgid"])
        cancel = threading.Event()
        key = SlotAffinityKey("own", "chat-cancel", "codex", SOL, "high", str(tmp_path), "zero-canon")
        stream = ad_hang._session_manager.execute_turn_stream(key, "PING", ad_hang._build_argv, str(tmp_path), cancel_event=cancel, is_ephemeral=True)
        _ = next(stream)
        cancel.set()
        _ = list(stream)
        assert not is_pgid_alive(json.loads(tr_hang.read_text(encoding="utf-8").splitlines()[0])["pgid"])
    finally:
        ad_ov.shutdown(timeout_s=1.0)
        ad_hang.shutdown(timeout_s=1.0)

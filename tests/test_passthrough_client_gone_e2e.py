"""E2E tests for Passthrough client_gone vs upstream_timeout separation (Wave 2)."""

from __future__ import annotations

import http.client
import socket
import threading
import time
from types import SimpleNamespace

from core import passthrough_adapter_runtime as runtime_mod


class _ClientGoneError(Exception):
    pass


def _make_adapter(fails: list[tuple[int, str]], pool_releases: list[bool]):
    sem = threading.BoundedSemaphore(1)
    upstream_sock, peer_sock = socket.socketpair()

    class _Pool:
        def release_connection(self, _h, _p, _conn, *, can_reuse: bool) -> None:
            pool_releases.append(can_reuse)

    def _fail(_sink, code: int, err: str, _msg: str, **_kw) -> None:
        fails.append((code, err))

    def _fail_io(sink, is_timeout: bool, **_kw) -> bool:
        _fail(sink, 504 if is_timeout else 502, "upstream_timeout" if is_timeout else "upstream_unavailable", "err")
        return False

    adapter = SimpleNamespace(
        id="test-adapter", config={"api_key": "k-test"}, _host="127.0.0.1", _port=19999,
        host=SimpleNamespace(QUEUE_TIMEOUT_S=1.0),
        limits=SimpleNamespace(poll_interval_s=0.01, reader_join_timeout_s=0.2),
        _slots=sem, _lock=threading.Lock(), _active=0, _pool=_Pool(),
        _with_body_defaults=lambda b: b, _upstream_headers=lambda _b, h, **_kw: dict(h),
        _client_gone_exc=lambda: _ClientGoneError(), _fail=_fail, _fail_io=_fail_io,
        _respond=lambda *_a, **_kw: True,
    )
    return adapter, upstream_sock, peer_sock


def _close_pair(a: socket.socket, b: socket.socket) -> None:
    for sock in (a, b):
        try:
            sock.close()
        except OSError:
            pass


def _patch_open(monkeypatch, open_fn) -> None:
    monkeypatch.setattr(runtime_mod, "credential_ready", lambda _cfg: True)
    monkeypatch.setattr(runtime_mod.passthrough_precommit, "open_response", open_fn)
    monkeypatch.setattr(runtime_mod.passthrough_precommit, "request_window", lambda w, s: (w, s))
    monkeypatch.setenv("BRIDGE_PASSTHROUGH_ABORT_FSM", "1")


def test_client_gone_does_not_emit_false_504(monkeypatch) -> None:
    fails: list[tuple[int, str]] = []
    adapter, up_sock, peer_sock = _make_adapter(fails, [])
    gone, abort_seen = {"flag": False}, threading.Event()

    def fake_open(_a, _s, _sl, _r, meta):
        meta[1](up_sock)
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            try:
                if not up_sock.recv(1):
                    break
            except OSError:
                break
        abort_seen.set()
        raise http.client.RemoteDisconnected("aborted by watcher")

    _patch_open(monkeypatch, fake_open)
    ex = runtime_mod.PassthroughRequest(request={"model": "gemini-4-neon", "stream": True}, raw_body=b"{}", path="/v1/chat/completions", headers={}, sink=SimpleNamespace(client_gone=lambda: gone["flag"]))
    opts = runtime_mod.RuntimeOptions(queue_timeout_s=0.5, deadlines_fn=lambda _l, _i: (time.monotonic() + 2.0, time.monotonic() + 2.0))
    threading.Thread(target=lambda: (time.sleep(0.05), gone.__setitem__("flag", True)), daemon=True).start()
    try:
        runtime_mod.handle_request(adapter, ex, opts)
    finally:
        _close_pair(up_sock, peer_sock)
    assert abort_seen.is_set() and fails == []


def test_upstream_deadline_still_emits_504(monkeypatch) -> None:
    fails: list[tuple[int, str]] = []
    adapter, up_sock, peer_sock = _make_adapter(fails, [])

    def fake_open(_a, _s, slide, _r, meta):
        meta[1](up_sock)
        while time.monotonic() < slide.deadline_s + 0.15:
            time.sleep(0.01)
        raise OSError("socket shut down on deadline")

    _patch_open(monkeypatch, fake_open)
    ex = runtime_mod.PassthroughRequest(request={"model": "gemini-4-neon", "stream": True}, raw_body=b"{}", path="/v1/chat/completions", headers={}, sink=SimpleNamespace(client_gone=lambda: False))
    opts = runtime_mod.RuntimeOptions(queue_timeout_s=0.5, deadlines_fn=lambda _l, _i: (time.monotonic() + 0.05, time.monotonic() + 0.05))
    try:
        runtime_mod.handle_request(adapter, ex, opts)
    finally:
        _close_pair(up_sock, peer_sock)
    assert fails == [(504, "upstream_timeout")]

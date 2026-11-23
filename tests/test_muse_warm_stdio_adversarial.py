"""W3 adversarial QA: warm stdio MSP + socket probe (VER-007/008/009/012).
Карта фильтров: `socket_probe|handshake_unsupported` (VER-007),
`warm_stdio|vacate|zero_canon|retryable` (VER-008), `fallback|
output_schema_bypass_msp|flag_off` (VER-009), `live_smoke` (VER-012,
только при `MUSE_LIVE_SMOKE=1`). Живой serve-гейт честно скипает поток
сессии, пока `serve`-argv W1-C отклоняется с `requires --listen`
(ASM-005 не подтверждён => `MUSE_WARM_MSP_STDIO_ENABLED` остаётся false).
"""
from __future__ import annotations
import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any
import pytest
UNSUPPORTED = "MUSE_SOCKET_HANDSHAKE_UNSUPPORTED"
PATH_REJECTED, MISSING, BAD = "MUSE_SOCKET_PATH_REJECTED", "MUSE_SOCKET_MISSING", "MUSE_SOCKET_BAD_RESPONSE"
CONNECT_FAILED = "MUSE_SOCKET_CONNECT_FAILED"
CREDENTIAL = "museClient" + "Credential"
LIVE = os.environ.get("MUSE_LIVE_SMOKE") == "1"
live_only = pytest.mark.skipif(not LIVE, reason="VER-012: нужен MUSE_LIVE_SMOKE=1")
def _probe() -> Any:
    return pytest.importorskip("core.stdio_resident.muse_socket_probe")
def _warm() -> Any:
    return pytest.importorskip("core.stdio_resident.muse_warm_client")
class FakeTransport:
    """MSP-пир с очередью запланированных сбоев по методам."""
    def __init__(self, failures: dict[str, list[BaseException]] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False
        self._failures = {k: list(v) for k, v in (failures or {}).items()}
    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((method, dict(params or {})))
        pending = self._failures.get(method)
        if pending:
            raise pending.pop(0)
        return {"ok": True, "method": method}
    def close(self) -> None:
        self.closed = True
    def count(self, method: str) -> int:
        return sum(1 for name, _ in self.calls if name == method)
def _registry(peer: FakeTransport) -> Any:
    return _warm().MuseWarmStdioRegistry(transport_factory=lambda: peer)
def _make_socket(root: Path, dir_mode: int = 0o700, file_mode: int = 0o600) -> dict[str, str]:
    sock_dir = root / "muse" / "session-server"
    sock_dir.mkdir(parents=True)
    sock = sock_dir / "session-server.sock"
    sock.write_text("", encoding="utf-8")
    os.chmod(sock_dir, dir_mode)
    os.chmod(sock, file_mode)
    return {"XDG_DATA_HOME": str(root)}
def test_socket_probe_handshake_unsupported_variants_no_retry(tmp_path: Path) -> None:
    mod = _probe()
    variants = [b'{"' + CREDENTIAL.encode() + b'":"rejected"}\n',
                CREDENTIAL.encode() + b": rejected (plain text)\n",
                b'{"error":"' + CREDENTIAL.encode() + b' rejected by server"}']
    for index, response in enumerate(variants):
        env = _make_socket(tmp_path / f"v{index}")
        seen: list[bytes] = []
        result = mod.probe_well_known_socket(
            environ=env, connector=lambda p, d, r=response: seen.append(d) or r)
        assert (result.ok, result.error_code) == (False, UNSUPPORTED)
        assert len(seen) == 1  # 0 ретраев (AD-004): ровно один initialize
        assert json.loads(seen[0])["method"] == "initialize"
        assert CREDENTIAL not in seen[0].decode("utf-8")  # credential не генерируется
def test_socket_probe_empty_and_connector_errors_fail_closed(tmp_path: Path) -> None:
    mod = _probe()
    env = _make_socket(tmp_path / "empty")
    empty = mod.probe_well_known_socket(environ=env, connector=lambda p, d: b"  ")
    assert (empty.ok, empty.error_code) == (False, BAD)
    for index, error in enumerate([OSError("refused"), TimeoutError("slow")]):
        calls: list[bytes] = []
        def boom(path: Path, data: bytes, _e: BaseException = error) -> bytes:
            calls.append(data)
            raise _e
        result = mod.probe_well_known_socket(environ=_make_socket(tmp_path / f"e{index}"), connector=boom)
        assert (result.ok, result.error_code) == (False, CONNECT_FAILED)
        assert len(calls) == 1
    missing = mod.probe_well_known_socket(environ={"XDG_DATA_HOME": str(tmp_path / "none")},
                                           connector=lambda p, d: b"{}")
    assert (missing.ok, missing.error_code) == (False, MISSING)
def test_socket_probe_path_traversal_variants_rejected_before_io(tmp_path: Path) -> None:
    mod = _probe()
    env = {"XDG_DATA_HOME": str(tmp_path)}
    expected = tmp_path / "muse" / "session-server" / "session-server.sock"
    evil = ["/tmp/evil.sock", str(expected) + ".bak", str(expected.parent),
            str(tmp_path / "muse" / ".." / "evil.sock"), "~/muse.sock"]
    for path in evil:
        with pytest.raises(ValueError):
            mod.validate_socket_path(path, env)
        calls: list[bytes] = []
        result = mod.probe_well_known_socket(socket_path=path, environ=env,
                                              connector=lambda p, d: calls.append(d) or b"{}")
        assert (result.ok, result.error_code) == (False, PATH_REJECTED)
        assert calls == []  # отказ до любого I/O
def _bare_transport(notifications: list[tuple[str, dict[str, Any]]]) -> Any:
    transport = object.__new__(_warm()._StdioMspTransport)
    transport._on_notification = lambda m, p: notifications.append((m, p)) or True
    return transport
def test_warm_stdio_broken_frames_ignored_and_error_codes_preserved() -> None:
    mod, notes = _warm(), []
    transport = _bare_transport(notes)
    for line in ["not json", "", "[]", "123", '"text"', '{"id": 99, "result": {"x": 1}}']:
        assert transport._dispatch_line(line, 1) is None
    assert notes == []
    note = '{"jsonrpc": "2.0", "method": "usage/changed", "params": {"window_used_percent": 7}}'
    assert transport._dispatch_line(note, 1) is None
    assert notes == [("usage/changed", {"window_used_percent": 7})]
    with pytest.raises(mod.MspError) as bad_res:
        transport._dispatch_line('{"jsonrpc": "2.0", "id": 1, "result": [1, 2]}', 1)
    assert bad_res.value.code == -32603
    assert transport._dispatch_line('{"jsonrpc": "2.0", "id": 1, "result": {"ok": true}}', 1) == {"ok": True}
    with pytest.raises(mod.MspError) as caught:
        transport._dispatch_line('{"jsonrpc": "2.0", "id": 1, "error": {"code": -32031, "message": "busy"}}', 1)
    assert (caught.value.code, caught.value.message) == (-32031, "busy")
    with pytest.raises(mod.MspError) as caught_default:
        transport._dispatch_line('{"jsonrpc": "2.0", "id": 1, "error": {}}', 1)
    assert caught_default.value.code == -32000
def test_retryable_storm_stops_after_exactly_one_retry() -> None:
    mod = _warm()
    storm = [mod.MspError(-32001, "a"), mod.MspError(-32031, "b"), mod.MspError(-32001, "c")]
    peer = FakeTransport({"turn/start": storm})
    registry = _registry(peer)
    registry.acquire_session("s1")
    with pytest.raises(mod.MspError) as caught:
        registry.run_turn("s1", "x")
    assert caught.value.code == -32031  # вторая попытка — последняя, шторм не зацикливается
    assert peer.count("turn/start") == 2
    assert mod.is_retryable_msp_error(mod.MspError(-32001)) is True
    assert mod.is_retryable_msp_error(-32001.0) is False  # float не код JSON-RPC
    peer2 = FakeTransport({"usage/read": [mod.MspError(-32001, "busy")]})
    registry2 = _registry(peer2)
    registry2.acquire_session("s1")
    with pytest.raises(mod.MspError):
        registry2.read_usage("s1")  # retry ровно один и только в run_turn
    assert peer2.count("usage/read") == 1
class FakeProc:
    """Процесс serve: умеет игнорировать SIGTERM до SIGKILL."""
    def __init__(self, ignore_term: bool) -> None:
        self.ignore_term, self.signals = ignore_term, []
    def poll(self) -> None:
        return None
    def terminate(self) -> None:
        self.signals.append("term")
    def wait(self, timeout: float | None = None) -> int:
        if self.ignore_term:
            raise subprocess.TimeoutExpired("muse serve", timeout or 0)
        return 0
    def kill(self) -> None:
        self.signals.append("kill")
def test_warm_stdio_sigkill_fallback_when_sigterm_ignored() -> None:
    transport = _bare_transport([])
    stubborn, polite = FakeProc(ignore_term=True), FakeProc(ignore_term=False)
    transport._proc, transport._timeout_s = stubborn, 0.01
    transport.close()
    assert stubborn.signals == ["term", "kill"]  # bounded SIGTERM drain -> SIGKILL
    transport._proc = polite
    transport.close()
    assert polite.signals == ["term"]
def test_vacate_drains_despite_leave_failure_then_reinitializes() -> None:
    mod = _warm()
    peers: list[FakeTransport] = []
    def factory() -> FakeTransport:
        failures = {"session/leave": [mod.MspError(-32001, "gone")]} if not peers else None
        peer = FakeTransport(failures)
        peers.append(peer)
        return peer
    registry = mod.MuseWarmStdioRegistry(transport_factory=factory)
    registry.acquire_session("s1")
    registry.acquire_session("s2")
    registry.vacate()  # сбой одного leave не блокирует drain и close
    assert peers[0].closed is True and registry.active_sessions() == ()
    registry.acquire_session("s3")
    assert len(peers) == 2 and peers[1].count("initialize") == 1
def test_zero_canon_registry_copies_and_session_isolation() -> None:
    peer = FakeTransport()
    first, second = _registry(peer), _registry(FakeTransport())
    snapshot = first.acquire_session("s1")
    snapshot["ok"] = False  # мутация копии не портит реестр
    assert first.acquire_session("s1")["ok"] is True
    assert peer.count("session/start") == 1
    assert second.active_sessions() == ()
    first.handle_notification("usage/changed", {"nested": {"value": 1}})
    leaked = first.last_usage()
    leaked["nested"]["value"] = 99
    assert first.last_usage() == {"nested": {"value": 1}}  # deep copy наружу
    assert first.leave_session("unknown") == {}
    assert peer.count("session/leave") == 0
    workers = [threading.Thread(target=first.acquire_session, args=("shared",)) for _ in range(6)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)
    starts = sum(1 for _, p in peer.calls if p.get("sessionId") == "shared")
    assert starts == 1  # конкурентный acquire — один session/start
def test_fallback_matrix_and_output_schema_bypass_msp() -> None:
    warm, router = _warm(), pytest.importorskip("core.stdio_resident.zero_canon_router")
    on, off = {"MUSE_WARM_MSP_STDIO_ENABLED": "1"}, {}
    cases = [(UNSUPPORTED, on, False, "warm_stdio"), (UNSUPPORTED, off, False, "legacy"),
             (None, on, False, "warm_stdio"), ("ANY_PROBE_ERROR", on, False, "warm_stdio"),
             (UNSUPPORTED, on, True, "exec"), (None, off, True, "exec")]
    for probe_error, env, with_schema, expected in cases:
        assert warm.decide_muse_transport(probe_error, output_schema=with_schema, environ=env) == expected
        assert router.decide_muse_transport(probe_error, output_schema=with_schema, environ=env) == expected
def test_flag_off_defaults_everywhere() -> None:
    assert _probe().probe_enabled({}) is False
    assert _warm().warm_stdio_enabled({}) is False
    assert _warm().warm_stdio_enabled({"MUSE_WARM_MSP_STDIO_ENABLED": "false"}) is False
    telemetry = pytest.importorskip("core.telemetry_usage")
    assert telemetry.build_telemetry_usage({"status": "ok"}, enabled=False) == {
        "enabled": False, "status": "disabled"}  # снимок при выключенном флаге не раскрывается
@live_only
def test_live_smoke_usage_json_schema_v1() -> None:
    client_mod = pytest.importorskip("core.muse_usage_client")
    snapshot = client_mod.MuseUsageClient().get_snapshot()
    assert snapshot.status in {"ok", "exhausted"}  # живой usage --json распознан
    assert snapshot.tier and snapshot.as_of_ms and snapshot.source == "mint"
    assert snapshot.window_used_percent is not None and snapshot.weekly_used_percent is not None
def test_socket_probe_fail_closed_on_malformed_and_rpc_error(tmp_path: Path) -> None:
    env = _make_socket(tmp_path)
    bad = [b"not-json\n", b'{"jsonrpc":"2.0","id":2,"result":{}}\n', b'{"jsonrpc":"2.0","id":true,"result":{}}\n',
           b'{"jsonrpc":"2.0","id":1,"error":{"code":-32600}}\n', b'{"jsonrpc":"2.0","id":1}\n']
    for payload in bad:
        res = _probe().probe_well_known_socket(environ=env, connector=lambda _p, _d, b=payload: b)
        assert res.ok is False and res.error_code
    good = b'{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"muse"}}}\n'
    assert _probe().probe_well_known_socket(environ=env, connector=lambda _p, _d: good).ok is True
def test_warm_stdio_coalesced_notification_and_response() -> None:
    import sys, time
    warm = _warm()
    code = ("import sys; sys.stdin.readline(); "
            "sys.stdout.write('{\"jsonrpc\":\"2.0\",\"method\":\"usage/changed\",\"params\":{\"w\":7}}\\n"
            "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"ok\":true}}\\n'); sys.stdout.flush()")
    seen: list[tuple[str, dict[str, Any]]] = []
    tr = warm._StdioMspTransport([sys.executable, "-c", code], lambda m, p: bool(seen.append((m, p))), 3.0)
    try:
        assert tr.request("initialize", {}) == {"ok": True} and seen == [("usage/changed", {"w": 7})]
        for bad in ('{"jsonrpc":"2.0","id":1}', '{"jsonrpc":"2.0","id":1,"error":null,"result":{}}',
                    '{"jsonrpc":"2.0","id":1,"error":"bad","result":{}}', '{"jsonrpc":"2.0","id":1,"error":{"code":"x"}}'):
            with pytest.raises(warm.MspError): tr._dispatch_line(bad, 1)
    finally: tr.close()
    tr2 = warm._StdioMspTransport([sys.executable, "-c", "import time; time.sleep(5)"], lambda *_: False, 0.15)
    t0 = time.monotonic()
    try:
        with pytest.raises(warm.MspError) as err: tr2.request("turn/start", {"blob": "x" * 262144})
        assert err.value.code == -32001 and time.monotonic() - t0 < 1.0
    finally: tr2.close()
@live_only
def test_live_smoke_warm_stdio_serve_gate() -> None:
    warm = _warm()
    registry = warm.MuseWarmStdioRegistry()
    try:
        registry.acquire_session(warm._uuid7())
        assert isinstance(registry.read_usage(), dict)
    finally:
        registry.vacate()
    assert registry.active_sessions() == ()

"""W0-B red-контракты warm stdio MSP v1 и пробы сокета (VER-007/008/009).

W1-C: `muse_socket_probe` — `well_known_socket_path(environ=None)->Path`,
`validate_socket_path(path, environ=None)`, `probe_enabled(environ=None)`,
`probe_well_known_socket(socket_path=None, environ=None, *, connector=None,
timeout_s=2.0) -> SocketProbeResult{ok,error_code,socket_path,detail}`.
`muse_warm_client` — `MspError{.code,.message}`, `is_retryable_msp_error`,
`warm_stdio_enabled`, `build_serve_argv`, `MuseWarmStdioRegistry(
transport_factory=None, *, wrapper_path=None, environ=None)` с методами
`acquire_session/run_turn/cancel_turn/read_usage/handle_notification/
last_usage/leave_session/active_sessions/vacate`. W2-C:
`zero_canon_router.decide_muse_transport(...)`, `telemetry_usage.
build_telemetry_usage(snapshot=None, *, enabled=False)`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

UNSUPPORTED = "MUSE_SOCKET_HANDSHAKE_UNSUPPORTED"
PATH_REJECTED = "MUSE_SOCKET_PATH_REJECTED"
REJECTED = b'{"museClientCredential":"rejected"}\n'
BARE = "~/" + ".local/" + "bin/" + "mu" + "se"


def _probe_mod() -> Any:
    return pytest.importorskip("core.stdio_resident.muse_socket_probe")


def _warm_mod() -> Any:
    return pytest.importorskip("core.stdio_resident.muse_warm_client")


def _decide() -> Any:
    from core.stdio_resident import zero_canon_router

    return zero_canon_router.decide_muse_transport


def _make_socket(root: Path, dir_mode: int, file_mode: int) -> dict[str, str]:
    sock_dir = root / "muse" / "session-server"
    sock_dir.mkdir(parents=True)
    sock = sock_dir / "session-server.sock"
    sock.write_text("", encoding="utf-8")
    os.chmod(sock_dir, dir_mode)
    os.chmod(sock, file_mode)
    return {"XDG_DATA_HOME": str(root)}


class FakeTransport:
    """Mock stdio MSP-пир: записывает вызовы, умеет запланированные сбои."""

    def __init__(self, failures: dict[str, list[BaseException]] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False
        self._failures = {key: list(value) for key, value in (failures or {}).items()}

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((method, dict(params or {})))
        pending = self._failures.get(method)
        if pending:
            raise pending.pop(0)
        if method == "initialize":
            return {"serverInfo": {"name": "muse", "version": "1.4.25"}}
        if method == "usage/read":
            return {"window_used_percent": 10}
        return {"ok": True, "method": method}

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self.calls.append((method, dict(params or {})))
    def close(self) -> None:
        self.closed = True
    def methods(self) -> list[str]:
        return [method for method, _ in self.calls]
    def params_of(self, method: str) -> dict[str, Any]:
        return next(params for name, params in self.calls if name == method)


def test_socket_probe_handshake_unsupported_no_retry(tmp_path: Path) -> None:
    mod = _probe_mod()
    env = _make_socket(tmp_path, 0o700, 0o600)
    seen: list[bytes] = []

    def connector(path: Path, payload: bytes) -> bytes:
        seen.append(payload)
        return REJECTED

    result = mod.probe_well_known_socket(environ=env, connector=connector)
    assert result.ok is False
    assert result.error_code == UNSUPPORTED
    assert len(seen) == 1
    assert json.loads(seen[0])["method"] == "initialize"
    assert "museClientCredential" not in seen[0].decode("utf-8")


def test_socket_probe_rejects_nonstandard_tmp_path(tmp_path: Path) -> None:
    mod = _probe_mod()
    env = {"XDG_DATA_HOME": str(tmp_path)}
    with pytest.raises(ValueError):
        mod.validate_socket_path("/tmp/evil.sock", env)
    calls: list[bytes] = []
    result = mod.probe_well_known_socket(
        socket_path="/tmp/evil.sock", environ=env,
        connector=lambda path, payload: calls.append(payload) or b"{}")
    assert result.ok is False
    assert result.error_code == PATH_REJECTED
    assert calls == []


def test_socket_probe_rejects_bad_permissions(tmp_path: Path) -> None:
    mod = _probe_mod()
    for dir_mode, file_mode in [(0o755, 0o600), (0o700, 0o644)]:
        env = _make_socket(tmp_path / f"c{dir_mode:o}{file_mode:o}", dir_mode, file_mode)
        calls: list[bytes] = []
        result = mod.probe_well_known_socket(
            environ=env, connector=lambda path, payload: calls.append(payload) or b"{}")
        assert result.ok is False
        assert isinstance(result.error_code, str) and result.error_code
        assert calls == []


def test_socket_probe_well_known_path_and_missing_socket(tmp_path: Path) -> None:
    mod = _probe_mod()
    env = {"XDG_DATA_HOME": str(tmp_path)}
    expected = tmp_path / "muse" / "session-server" / "session-server.sock"
    assert mod.well_known_socket_path(env) == expected

    def forbidden(path: Path, payload: bytes) -> bytes:
        raise AssertionError("connector must not be called for missing socket")

    result = mod.probe_well_known_socket(environ=env, connector=forbidden)
    assert result.ok is False
    assert result.socket_path == str(expected)


def test_warm_stdio_initialize_turn_cancel_leave_and_usage_read() -> None:
    peer = FakeTransport()
    registry = _warm_mod().MuseWarmStdioRegistry(transport_factory=lambda: peer)
    registry.acquire_session("s1")
    registry.acquire_session("s2")
    assert peer.methods().count("initialize") == 1
    assert peer.params_of("initialize")["compatibilityEpoch"] == 0
    assert registry.run_turn("s1", "привет", effort="high")["ok"] is True
    turn = peer.params_of("turn/start")
    assert turn["sessionId"] == "s1" and turn["input"] == [{"type": "text", "text": "привет"}]
    registry.cancel_turn("s1")
    assert peer.params_of("turn/cancel")["sessionId"] == "s1"
    assert registry.read_usage("s1") == {"window_used_percent": 10}
    registry.leave_session("s1")
    assert peer.params_of("session/leave")["sessionId"] == "s1"
    assert registry.active_sessions() == ("s2",)

def test_zero_canon_session_start_clears_developer_prompt() -> None:
    peer = FakeTransport()
    registry = _warm_mod().MuseWarmStdioRegistry(transport_factory=lambda: peer)
    registry.acquire_session("zc1", model_id="muse-wonder-1.0", posture="denyUnmatched")
    params = peer.params_of("session/start")
    assert params["sessionId"] == "zc1" and params["config"] == {"developerPrompt": None}

def test_warm_stdio_usage_changed_updates_snapshot_copy() -> None:
    registry = _warm_mod().MuseWarmStdioRegistry(transport_factory=lambda: FakeTransport())
    assert registry.handle_notification("usage/changed", {"window_used_percent": 42}) is True
    snapshot = registry.last_usage()
    assert snapshot == {"window_used_percent": 42}
    snapshot["window_used_percent"] = 0
    assert registry.last_usage() == {"window_used_percent": 42}
    assert registry.handle_notification("unknown/method", {}) is False

def test_retryable_msp_errors_retried_exactly_once() -> None:
    mod = _warm_mod()
    retryable = (mod.is_retryable_msp_error(-32001), mod.is_retryable_msp_error(-32031))
    assert retryable == (True, True) and mod.is_retryable_msp_error(-32602) is False
    for code in (-32001, -32031):
        peer = FakeTransport({"turn/start": [mod.MspError(code, "busy")]})
        registry = mod.MuseWarmStdioRegistry(transport_factory=lambda p=peer: p)
        registry.acquire_session("s1")
        assert registry.run_turn("s1", "x")["ok"] is True
        assert peer.methods().count("turn/start") == 2
    peer = FakeTransport({"turn/start": [mod.MspError(-32602, "bad params")]})
    registry = mod.MuseWarmStdioRegistry(transport_factory=lambda: peer)
    registry.acquire_session("s1")
    with pytest.raises(mod.MspError):
        registry.run_turn("s1", "x")
    assert peer.methods().count("turn/start") == 1

def test_vacate_on_upgrade_drains_sessions_and_closes() -> None:
    peer = FakeTransport()
    registry = _warm_mod().MuseWarmStdioRegistry(transport_factory=lambda: peer)
    registry.acquire_session("s1")
    registry.acquire_session("s2")
    registry.vacate()
    assert peer.methods().count("session/leave") == 2 and peer.closed is True
    assert registry.active_sessions() == ()

def test_serve_argv_includes_vacate_on_upgrade_and_wrapper() -> None:
    mod = _warm_mod()
    argv = mod.build_serve_argv(environ={"MUSE_CLI_WRAPPER": "/tmp/muse-cli.sh"})
    assert argv[:2] == ["/tmp/muse-cli.sh", "serve"]
    assert "--allow-session-posture" in argv and "--vacate-on-upgrade" in argv
    default = mod.build_serve_argv(environ={})
    assert default[0].endswith(".config/muse-launch/muse-cli.sh")
    assert BARE not in " ".join(default)

def test_fallback_to_warm_stdio_on_handshake_unsupported() -> None:
    env = {"MUSE_WARM_MSP_STDIO_ENABLED": "1"}
    assert _decide()(UNSUPPORTED, environ=env) == "warm_stdio"

def test_output_schema_bypass_msp_never_goes_warm() -> None:
    decide = _decide()
    env = {"MUSE_WARM_MSP_STDIO_ENABLED": "1"}
    assert decide(UNSUPPORTED, output_schema=True, environ=env) == "exec"
    assert decide(None, output_schema=True, environ=env) == "exec"

def test_flag_off_uses_legacy_path() -> None:
    decide = _decide()
    assert decide(UNSUPPORTED, environ={}) == "legacy"
    assert decide(UNSUPPORTED, environ={"MUSE_WARM_MSP_STDIO_ENABLED": "false"}) == "legacy"
    assert _probe_mod().probe_enabled({}) is False
    assert _probe_mod().probe_enabled({"MUSE_UNIX_SOCKET_PROBE_ENABLED": "1"}) is True
    assert _warm_mod().warm_stdio_enabled({}) is False
    assert _warm_mod().warm_stdio_enabled({"MUSE_WARM_MSP_STDIO_ENABLED": "true"}) is True


def test_telemetry_usage_disabled_and_enabled_shapes() -> None:
    mod = pytest.importorskip("core.telemetry_usage")
    assert mod.build_telemetry_usage(None, enabled=False) == {
        "enabled": False, "status": "disabled"}
    snap = SimpleNamespace(status="exhausted", tier="Muse Code Max Usage",
                           window_used_percent=100, weekly_used_percent=24,
                           reset_at=1795446181, as_of_ms=1795436896748, source="mint")
    assert mod.build_telemetry_usage(snap, enabled=True) == {
        "enabled": True, "status": "exhausted", "tier": "Muse Code Max Usage",
        "window_used_percent": 100, "weekly_used_percent": 24,
        "reset_at": 1795446181, "as_of_ms": 1795436896748, "source": "mint"}

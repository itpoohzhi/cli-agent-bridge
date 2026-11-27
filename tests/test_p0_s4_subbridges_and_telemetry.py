"""W3 (P0-S4): adversarial-матрица разрывов клиента 4 саб-мостов + telemetry хаба.

Контракт: flag=true + BrokenPipeError гасит stderr-traceback (одна строка
client_disconnected); не-разрыв и kill-switch=false сохраняют traceback. Hub:
разрыв не-DETACHED доставки не глотается, telemetry 499/record_discard/
qos.release_slot/guard.release сохраняются. Мосты — importlib (T-ISO-I2).
"""

from __future__ import annotations

import errno
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from core import passthrough_facade as facade  # noqa: E402
from core.turn_mode_cancel_policy import TurnMode  # noqa: E402

_BRIDGES = ("agy-bridge", "opencode-zen-bridge", "claude-p-bridge", "muse-bridge")
_ROUTE_DOC = {"route_id": "r1", "backend": "b1", "weight": 1, "priority": 0}
_MATRIX = [
    pytest.param((True, BrokenPipeError(errno.EPIPE, "gone"), False), id="on-gone"),
    pytest.param((True, RuntimeError("backend exploded"), True), id="on-runtime"),
    pytest.param((False, BrokenPipeError(errno.EPIPE, "gone"), True), id="off-gone"),
]


def _isolate_config(monkeypatch, tmp_path, flags: dict) -> None:
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text(json.dumps(flags), encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))


def _load_bridge(monkeypatch, name: str):
    """importlib-изоляция: временная регистрация на exec (dataclasses) и гарантированный
    откат через monkeypatch.setitem — после теста в sys.modules утечки нет (T-ISO-I2)."""
    mod_name = f"p0_s4_w3_{name.replace('-', '_')}"
    assert mod_name not in sys.modules
    path = ROOT / "bridges" / name / "server.py"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, mod_name, mod)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("bridge", _BRIDGES)
@pytest.mark.parametrize("case", _MATRIX)
def test_subbridge_handle_error_disconnect_matrix(monkeypatch, tmp_path, bridge, case):
    enabled, exc, want_tb = case
    flags = {"BRIDGE_SUPPRESS_CLIENT_DISCONNECT_TRACEBACK_ENABLED": enabled}
    _isolate_config(monkeypatch, tmp_path, flags)
    mod = _load_bridge(monkeypatch, bridge)
    logs: list[str] = []
    stderr = io.StringIO()
    monkeypatch.setattr(mod, "_log", logs.append)
    monkeypatch.setattr(sys, "stderr", stderr)
    httpd = mod.Server(("127.0.0.1", 0), mod.Handler)
    try:
        try:
            raise exc
        except type(exc):
            httpd.handle_error(None, ("127.0.0.1", 54321))
    finally:
        httpd.server_close()
    captured = stderr.getvalue()
    lines = [line for line in logs if "client_disconnected" in line]
    if want_tb:
        assert "Traceback (most recent call last):" in captured, (bridge, captured)
        assert type(exc).__name__ in captured, (bridge, captured)
        assert lines == [], logs
    else:
        assert captured == "", (bridge, captured)
        assert len(lines) == 1, logs
        assert "BrokenPipeError" in lines[0], lines
        assert "\n" not in lines[0] and "\r" not in lines[0], lines


def test_disconnect_log_and_config_path_resolution(monkeypatch):
    from core.http_disconnect_policy import format_client_disconnect_log
    from core.http_server_error import resolved_config_path

    exc = BrokenPipeError(errno.EPIPE, "x")
    line = format_client_disconnect_log("127.0.0.1\r\nINJECTED", exc)
    assert (
        "\r" not in line and "\n" not in line and line.count("client_disconnected") == 1
    )
    assert (
        format_client_disconnect_log(("127.0.0.1", 5555), exc)
        == "client_disconnected peer=127.0.0.1:5555 exc=BrokenPipeError"
    )
    monkeypatch.delenv("BRIDGE_DYNAMIC_CONFIG_PATH", raising=False)
    assert resolved_config_path(Path("/tmp/x.json")) == "/tmp/x.json"
    assert resolved_config_path(None).endswith("dynamic_config.json")


class _BrokenClientPipe(io.BufferedIOBase):
    """wfile ушедшего клиента: первая запись ответа даёт BrokenPipeError."""

    def writable(self) -> bool:
        return True

    def write(self, data) -> int:
        raise BrokenPipeError(errno.EPIPE, "client gone")

    def flush(self) -> None:
        return None


@pytest.mark.parametrize("mode", [TurnMode.NON_DETACHED, TurnMode.UNKNOWN])
def test_hub_send_reraises_disconnect_when_not_detached(monkeypatch, mode):
    h = object.__new__(server.Handler)
    h._turn_mode = mode
    h._response_status = 0
    h._trace = None
    h.wfile = _BrokenClientPipe()
    events: list[tuple] = []
    monkeypatch.setattr(
        h,
        "_telemetry_error_response",
        lambda code, *_a: events.append(("telemetry", code)),
        raising=False,
    )
    monkeypatch.setattr(h, "send_response", lambda code: None, raising=False)
    monkeypatch.setattr(h, "send_header", lambda *_a: None, raising=False)
    monkeypatch.setattr(h, "end_headers", lambda: None, raising=False)
    with pytest.raises(BrokenPipeError):
        h._send(200, {"ok": True})
    assert events == [("telemetry", 200)]
    assert h._response_status == 200


class _FakeLease:
    """Контекстный lease: record_discard пишет событие, выход не глотает ошибку."""

    def __init__(self, events: list) -> None:
        self._events = events

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> bool:
        return False

    def record_discard(self, reason: str) -> None:
        self._events.append(("discard", reason))


class _GoneAdapter:
    id = "w3-gone"
    limits: dict = {}

    def handle(self, **_kw):
        _kw["sink"].write(b"partial")  # _HandlerSink -> ClientGone(BrokenPipeError)


class _RawPipeGoneAdapter:
    """Сырой обрыв сокета доставки мимо sink: тоже не должен глотаться."""

    id = "w3-pipe"
    limits: dict = {}

    def handle(self, **_kw):
        raise BrokenPipeError(errno.EPIPE, "delivery socket gone")


def _gone_handler(events: list) -> object:
    h = object.__new__(server.Handler)
    h.path = "/v1/messages"
    h.headers = {}
    h.connection = None
    h._trace = None
    h._telemetry_begin()
    h._resilience_lease = _FakeLease(events)
    h.wfile = _BrokenClientPipe()
    h.send_response = lambda code: None
    h.send_header = lambda *_a: None
    h.end_headers = lambda: None
    return h


def _wire_qos_and_lease(monkeypatch, events: list) -> None:
    qos = SimpleNamespace(
        acquire_slot=lambda **_k: (True, ""),
        release_slot=lambda **kw: events.append(("qos_release", kw)),
    )
    monkeypatch.setattr(server, "get_qos_manager", lambda **_kw: qos)
    lease = _FakeLease(events)
    monkeypatch.setattr(server, "RESILIENCE", SimpleNamespace(acquire=lambda _b: lease))


def test_hub_passthrough_brokenpipe_records_discard_499_and_reraises(monkeypatch):
    """Сырой BrokenPipeError: discard + telemetry 499 + qos.release, re-raise."""
    events: list[tuple] = []
    monkeypatch.setattr(server, "flag_enabled", lambda _flag: False)
    monkeypatch.setattr(server, "_strip_passthrough_env", lambda raw, req: (raw, req))
    _wire_qos_and_lease(monkeypatch, events)
    recorded: list[dict] = []
    monkeypatch.setattr(
        server,
        "REQUEST_TELEMETRY",
        SimpleNamespace(record_request=recorded.append, is_enabled=lambda: True),
    )
    h = _gone_handler(events)
    adapter = _RawPipeGoneAdapter()
    with pytest.raises(BrokenPipeError):
        h._serve_resilient(
            adapter.id,
            lambda: h._serve_passthrough(adapter, b"{}", {"model": "m"}, "m"),
        )
    assert ("discard", "client_disconnected") in events, events
    assert ("qos_release", {"is_interactive": True}) in events, events
    assert len(recorded) == 1, recorded
    assert (recorded[0]["status_code"], recorded[0]["error_type"]) == (
        499,
        "BrokenPipeError",
    ), recorded
    assert h._req_recorded is True
    assert h._resilience_lease is None


def test_hub_resilient_clientgone_releases_qos_and_propagates(monkeypatch):
    """ClientGone(BrokenPipe) не глотается, QoS-слот освобождён, lease сброшен."""
    events: list[tuple] = []
    monkeypatch.setattr(server, "flag_enabled", lambda _flag: False)
    monkeypatch.setattr(server, "_strip_passthrough_env", lambda raw, req: (raw, req))
    _wire_qos_and_lease(monkeypatch, events)
    h = _gone_handler(events)
    adapter = _GoneAdapter()
    with pytest.raises(server.ClientGone) as err:
        h._serve_resilient(
            adapter.id,
            lambda: h._serve_passthrough(adapter, b"{}", {"model": "m"}, "m"),
        )
    assert isinstance(err.value.__cause__, BrokenPipeError)
    assert ("qos_release", {"is_interactive": True}) in events, events
    assert h._resilience_lease is None


def test_hub_run_routes_releases_guard_and_propagates_disconnect(monkeypatch):
    monkeypatch.setattr(facade, "_RUNTIME", facade._RuntimeState())
    monkeypatch.setenv("BRIDGE_ROUTE_CB_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_ROUTE_CB_EVENTS", "0")
    events: list[str] = []
    guard = SimpleNamespace(
        blocked=False,
        quota_refusal=None,
        blocked_key=None,
        record_exception=lambda exc: events.append("exception"),
        release=lambda: events.append("release"),
        succeed=lambda _now: None,
    )
    host = SimpleNamespace(_client_gone=lambda _conn: False, BACKENDS={})
    route = SimpleNamespace(
        model_id="m1",
        model={"routing": {"routes": [_ROUTE_DOC]}},
        request={"messages": []},
        alias_effort=None,
        host=host,
        handler=SimpleNamespace(
            connection=None, _trace=SimpleNamespace(subagent_id=None)
        ),
    )
    spec = SimpleNamespace(backend="b1", provider="p1", credential_ref="c1")
    monkeypatch.setattr(facade, "prepare_post_body", lambda _r: b"{}")
    monkeypatch.setattr(facade, "route_order", lambda *_a: ("b1",))
    monkeypatch.setattr(facade, "_eligible", lambda *_a: True)
    monkeypatch.setattr(facade, "acquire_cb_guard", lambda *_a: guard)

    def fail(*_args) -> None:
        raise BrokenPipeError(errno.EPIPE, "gone on attempt")

    monkeypatch.setattr(facade, "_attempt", fail)
    with pytest.raises(BrokenPipeError):
        facade._run_routes(route, [spec], "seed", None)
    assert events == ["exception", "release"], events

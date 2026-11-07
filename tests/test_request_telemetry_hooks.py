"""Юнит-тесты миксина телеметрии HTTP-обработчика: учёт байт/TTFB, ошибки, событие, идемпотентная запись, топология."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent
for _p in (str(_TESTS), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.telemetry_hooks import (  # noqa: E402
    TelemetryHooksMixin,
    _query_number,
    http_error_type,
    known_model,
    resolve_backend_topology,
    telemetry_note,
)


class _Sink:
    """Стор-заглушка фасада: копит события, по флагу падает."""

    recent_limit = 100

    def __init__(self):
        self.events, self.fail = [], False

    def record_request(self, event):
        if self.fail:
            raise RuntimeError("storage down")
        self.events.append(event)


# Атрибуты фасада: миксин находит их по MRO обработчика (модуль этого теста — «фасад» заглушки).
REQUEST_TELEMETRY = _Sink()
BACKENDS = {"agy": SimpleNamespace(_port=9887)}
LOGS: list[str] = []


def _bridge_env(_name, default=""):
    return default


def _log(msg):
    LOGS.append(msg)


def _err_summary(err, limit=200):
    return str(err)[:limit]


class _Handler(TelemetryHooksMixin):
    headers = {"Authorization": "Bearer s3cret", "User-Agent": "ua/1", "X-Subagent-Role": "coder"}
    command = "POST"
    path = "/v1/chat/completions?x=1"
    client_address = ("10.0.0.7", 5000)
    _response_status = 0

    def _subagent_id(self):
        return "coder-1"


def _begun(**meta):
    handler = _Handler()
    REQUEST_TELEMETRY.events.clear()
    REQUEST_TELEMETRY.fail = False
    handler._telemetry_begin()
    handler._telemetry_meta(**meta)
    return handler


def test_note_accounting_and_ttfb():
    idle = _Handler()
    idle._telemetry_note(5, chunk=True)  # до begin — игнорируется
    idle._telemetry_meta(model="x")
    assert (idle._req_bytes, idle._req_stream_chunks, idle._req_ttfb_ms, idle._req_meta) == (0, 0, None, None)
    h = _begun()
    assert h._req_meta == {"endpoint": "/v1/chat/completions", "route_mode": "rejected"}
    h._telemetry_note("héllo")  # str — по UTF-8; без chunk/first_byte TTFB не ставится
    assert (h._req_bytes, h._req_stream_chunks, h._req_ttfb_ms) == (6, 0, None)
    h._telemetry_note(4, chunk=True)
    ttfb = h._req_ttfb_ms
    assert (h._req_bytes, h._req_stream_chunks) == (10, 1) and ttfb is not None
    h._telemetry_note(first_byte=True)
    assert h._req_ttfb_ms == ttfb and h._req_stream_chunks == 1  # первый байт фиксируется один раз
    h._telemetry_meta(model="m", stream=None)
    h._telemetry_meta(model=None, backend_id="agy")  # None не затирает известное
    assert (h._req_meta["model"], h._req_meta["backend_id"], "stream" in h._req_meta) == ("m", "agy", False)
    h._telemetry_usage({"input_tokens": 11, "output_tokens": 4, "cache_read_tokens": 3})
    h._telemetry_usage(None)
    assert [h._req_meta[k] for k in ("prompt_tokens", "completion_tokens", "cached_tokens")] == [11, 4, 3]
    h._telemetry_meta_request({"stream": 1, "model": 7})
    assert (h._req_meta["stream"], h._req_meta["model"]) == (True, "m")


def test_error_mapping_and_error_responses():
    h = _begun()
    h._telemetry_error(None)
    h._telemetry_error({})
    assert "status_code" not in h._req_meta
    for err, code in (({"code": 429, "type": "rate"}, 429), ({"code": 400}, 400), ({"code": 399}, 502),
                      ({"code": "model_not_found"}, 502)):
        h._telemetry_error(err)
        assert h._req_meta["status_code"] == code, err
    assert h._req_meta["error_type"] == "rate"
    h._telemetry_error_response(399, {"error": {"type": "ignored"}}, b"x")  # успех/редирект не записываются
    assert REQUEST_TELEMETRY.events == [] and h._req_bytes == 0
    h._telemetry_error_response(400, {"error": {"type": "auth_error"}}, b"xyz")
    assert [(e["status_code"], e["error_type"], e["response_bytes"]) for e in REQUEST_TELEMETRY.events] == [(400, "auth_error", 3)]
    other = _begun()
    other._telemetry_error_response(500, ["not a dict"], b"")
    assert REQUEST_TELEMETRY.events[0]["status_code"] == 500 and REQUEST_TELEMETRY.events[0]["error_type"] is None


def test_event_fields_and_single_idempotent_record():
    idle = _Handler()
    REQUEST_TELEMETRY.events.clear()
    idle._record_telemetry()  # без begin записи нет
    assert REQUEST_TELEMETRY.events == []
    h = _begun(backend_id="agy", route_mode="passthrough", model="m-a")
    h._telemetry_queue_done(h._telemetry_queue_start("agy"))
    h._telemetry_usage({"input_tokens": 5, "output_tokens": 2})
    h._record_telemetry(status_code=200)
    h._record_telemetry(status_code=500)  # повторная запись игнорируется
    (event,) = REQUEST_TELEMETRY.events
    assert (event["status_code"], event["model"], event["total_tokens"], event["http_method"]) == (200, "m-a", 7, "POST")
    assert (event["client_ip"], event["client_port"], event["user_agent"]) == ("10.0.0.7", 5000, "ua/1")
    assert (event["subagent_id"], event["subagent_role"], event["auth_mode"]) == ("coder-1", "coder", "bearer")
    assert (event["outbound_target"], event["egress_proxy"], event["request_id"]) == (":9887", ":10820 (xray SOCKS5)", None)
    assert "s3cret" not in repr(event) and event["total_ms"] >= 0.0 and "prompt_tokens" in event
    bare = _begun()
    bare._record_telemetry(status_code=404)
    assert (REQUEST_TELEMETRY.events[0]["outbound_target"], REQUEST_TELEMETRY.events[0]["total_tokens"]) == (None, None)


def test_status_derivation_from_exceptions_and_disconnects():
    def record(raiser=None, **kw):
        h = _begun()
        try:
            if raiser:
                raise raiser
        except Exception:
            h._record_telemetry(**kw)
        else:
            h._record_telemetry(**kw)
        return REQUEST_TELEMETRY.events[-1]

    cases = (
        (record(BrokenPipeError()), 499, "BrokenPipeError"),
        (record(ConnectionResetError()), 499, "ConnectionResetError"),
        (record(ValueError("x")), 500, "ValueError"),
        (record(ValueError("x"), status_code=503), 503, "ValueError"),
        (record(ValueError("x"), error_type="custom"), 499, "custom"),
        (record(client_gone=True), 499, "client_disconnected"),
        (record(), 499, "client_disconnected"),
        (record(error_type="boom"), 499, "boom"),
    )
    assert [(e["status_code"], e["error_type"]) for e, _, _ in cases] == [(c, t) for _, c, t in cases]
    h = _begun()
    REQUEST_TELEMETRY.fail = True
    LOGS.clear()
    h._record_telemetry(status_code=200)  # сбой стора не выходит наружу и пишется в журнал
    assert LOGS and "telemetry_record_failed" in LOGS[0] and "storage down" in LOGS[0]


def test_topology_helpers_and_sink_note(monkeypatch):
    assert resolve_backend_topology(BACKENDS, "agy", "passthrough") == (":9887", ":10820 (xray SOCKS5)")
    assert resolve_backend_topology({"x": SimpleNamespace(_port=1234)}, "x", "passthrough") == (":1234", "direct")
    assert resolve_backend_topology({"x": SimpleNamespace(_port=1234)}, "x", "cli") == ("cli:x", "direct")
    assert resolve_backend_topology({}, "nope", "passthrough") == ("cli:nope", "direct")
    monkeypatch.setenv("BRIDGE_TELEMETRY_BACKEND_TOPOLOGY_JSON", '{"agy": [":1", "d"], "bad": "x", "short": ["a"], "n": 5}')
    assert resolve_backend_topology(BACKENDS, "agy", "cli") == (":1", "d")
    assert resolve_backend_topology(BACKENDS, "bad", "cli") == ("cli:bad", "direct")
    monkeypatch.setenv("BRIDGE_TELEMETRY_BACKEND_TOPOLOGY_JSON", "{not json")
    assert resolve_backend_topology(BACKENDS, "agy", "cli") == (":9887", ":10820 (xray SOCKS5)")
    assert (known_model("unknown"), known_model("m-a")) == (None, "m-a")
    assert (http_error_type(399), http_error_type(400), http_error_type(503)) == (None, "http_400", "http_503")
    h = _begun()
    telemetry_note(h, 3, chunk=True)
    telemetry_note(object(), 3, chunk=True)  # обработчик без миксина — no-op
    assert (h._req_bytes, h._req_stream_chunks) == (3, 1)
    h._telemetry_passthrough_done(404)
    assert [(e["status_code"], e["error_type"]) for e in REQUEST_TELEMETRY.events] == [(404, "http_404")]
    ok = _begun()
    ok._telemetry_passthrough_done(200)
    assert [(e["status_code"], e["error_type"]) for e in REQUEST_TELEMETRY.events] == [(200, None)]


def test_fresh_handler_collects_nothing_before_begin():
    """Состояние класса: без _telemetry_begin ни хвост usage, ни событие не собираются."""
    fresh = _Handler()
    REQUEST_TELEMETRY.events.clear()
    assert (fresh._req_tracking, fresh._req_tail, fresh._req_started_mono) == (False, b"", None)
    fresh._telemetry_tail(b'"usage": {"prompt_tokens": 1}')
    fresh._record_telemetry(status_code=200)
    assert (fresh._req_tail, REQUEST_TELEMETRY.events) == (b"", [])


def test_query_number_rejects_nan_inf_and_nonpositive():
    def window(value):
        return _query_number({"window_hours": [value]}, "window_hours", 24.0, float)

    assert [window(v) for v in ("nan", "inf", "-inf", "-5", "0", "abc", "2.5", "1e12")] == [24.0] * 6 + [2.5, 1e12]
    assert [_query_number({"limit": [v]}, "limit", 100, int) for v in ("-1", "0", "7", "1e3", "1000000000")] == [100, 100, 7, 100, 10**9]
    assert _query_number({}, "limit", 100, int) == 100


def test_serve_get_passes_sane_values_to_store():
    class Reader(_Handler):
        sent: list = []

        def _send(self, code, payload, extra_headers=None):
            self.sent.append((code, payload))

    class Store:
        recent_limit = 100

        def get_telemetry_payload(self, window_hours, limit):
            return {"window_hours": window_hours, "limit": limit}

    global REQUEST_TELEMETRY
    saved, REQUEST_TELEMETRY = REQUEST_TELEMETRY, Store()
    try:
        for query, expected in (("window_hours=nan&limit=-1", (24.0, 100)), ("window_hours=inf&limit=zzz", (24.0, 100)),
                                ("window_hours=3&limit=20", (3.0, 20))):
            handler = Reader()
            handler.sent = []
            handler.path = f"/v1/telemetry?{query}"
            handler._telemetry_serve_get()
            assert handler.sent == [(200, {"window_hours": expected[0], "limit": expected[1]})], query
    finally:
        REQUEST_TELEMETRY = saved


def test_disabled_store_collects_nothing():
    class Off(_Sink):
        def is_enabled(self):
            return False

    global REQUEST_TELEMETRY
    saved, REQUEST_TELEMETRY = REQUEST_TELEMETRY, Off()
    try:
        h = _Handler()
        h._telemetry_begin()
        h._telemetry_tail(b'"usage": {"prompt_tokens": 1}')
        h._telemetry_passthrough_done(200)
        assert REQUEST_TELEMETRY.events == [] and h._req_tail == b"" and h._req_tracking is False
    finally:
        REQUEST_TELEMETRY = saved

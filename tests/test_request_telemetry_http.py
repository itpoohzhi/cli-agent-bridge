"""HTTP-интеграция телеметрии: GET /v1/telemetry, атрибуция do_POST, отказы, топология бэкендов."""

from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent
for _p in (str(_TESTS), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from bridge_testlib import BridgeCase  # noqa: E402
from core.request_telemetry import RequestTelemetryStore  # noqa: E402

import server  # noqa: E402


class TestServerTelemetry(BridgeCase):
    """Сквозные проверки инструментирования Handler на поднятом стенде моста."""

    def setUp(self):
        super().setUp()
        self._tel_dir = tempfile.TemporaryDirectory()
        self._saved_store = server.REQUEST_TELEMETRY
        self.store = RequestTelemetryStore(
            str(Path(self._tel_dir.name) / "bridge_telemetry.duckdb"), force_sqlite=True, autostart=False, enabled=True
        )
        server.REQUEST_TELEMETRY = self.store

    def tearDown(self):
        server.REQUEST_TELEMETRY = self._saved_store
        self.store.close()
        self._tel_dir.cleanup()
        super().tearDown()

    def _chat(self, headers=None, **body):
        payload = {"model": "claude-sonnet-5-5", "messages": [{"role": "user", "content": "hi"}], **body}
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        try:
            hdrs = {"Authorization": "Bearer test-key", "Content-Type": "application/json", **(headers or {})}
            conn.request("POST", "/v1/chat/completions", body=json.dumps(payload), headers=hdrs)
            resp = conn.getresponse()
            return resp.status, resp.read().decode("utf-8")
        finally:
            conn.close()

    def _script_ok(self, usage=None):
        self.hub.legacy(
            [[("text", "hello"), ("result", {"finalText": "", "usage": usage or {}}), ("done", (0, ""))]] * 4
        )

    def test_endpoint_requires_auth(self):
        status, body = self._get("/v1/telemetry", auth=False)
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["type"], "auth_error")

    def test_endpoint_returns_full_schema(self):
        status, payload = self._get("/v1/telemetry")
        self.assertEqual(status, 200)
        for key in (
            "enabled", "engine", "db_path", "window_hours", "generated_at", "dropped_events", "queue_size",
            "summary", "by_model", "by_backend", "by_client", "by_hour", "recent_requests", "architecture_flow",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["engine"], "sqlite3")
        for key in ("tier1_entry_callers", "tier2_l7_bridges", "tier3_l4_egress_proxies"):
            self.assertIn(key, payload["architecture_flow"])

    def test_endpoint_tolerates_bad_query_values(self):
        status, payload = self._get("/v1/telemetry?window_hours=abc&limit=zzz")
        self.assertEqual((status, payload["window_hours"]), (200, 24.0))
        status, payload = self._get("/v1/telemetry?window_hours=2&limit=1")
        self.assertEqual((status, payload["window_hours"]), (200, 2.0))

    def test_endpoint_clamps_nan_inf_and_huge_values(self):
        for query, hours, rows in (("window_hours=nan&limit=-1", 24.0, 100), ("window_hours=inf&limit=1000000000", 24.0, 500),
                                   ("window_hours=1e12&limit=5", 720.0, 5), ("window_hours=-5", 24.0, 100)):
            status, payload = self._get(f"/v1/telemetry?{query}")
            self.assertEqual((status, payload["window_hours"]), (200, hours), query)
            self.assertLessEqual(len(payload["recent_requests"]), rows)

    def test_chat_requests_are_recorded_with_attribution(self):
        self._script_ok({"input_tokens": 11, "output_tokens": 4, "cache_read_tokens": 3})
        self.assertEqual(self._chat(headers={"X-Subagent-Id": "coder-1", "User-Agent": "unit-agent/1"})[0], 200)
        status, stream = self._chat(stream=True)
        self.assertEqual(status, 200)
        self.assertIn("[DONE]", stream)
        self.store.flush()
        status, payload = self._get("/v1/telemetry")
        self.assertEqual(status, 200)
        rows = {r["stream"]: r for r in payload["recent_requests"]}
        sub, inter = rows[False], rows[True]
        self.assertEqual((sub["client_kind"], sub["subagent_role"], sub["subagent_id"]), ("subagent", "coder", "coder-1"))
        self.assertEqual(sub["user_agent"], "unit-agent/1")
        self.assertEqual((inter["client_kind"], inter["subagent_role"]), ("interactive", "interactive"))
        for row in (sub, inter):
            self.assertEqual(row["status_code"], 200)
            self.assertEqual((row["http_method"], row["endpoint"], row["route_mode"]), ("POST", "/v1/chat/completions", "cli"))
            self.assertEqual(row["model"], "claude-sonnet-5-5")
            self.assertTrue(row["backend_id"])
            self.assertGreaterEqual(row["total_ms"], 0.0)
            self.assertGreaterEqual(row["total_ms"], row["ttfb_ms"] or 0.0)
        # cache_read фейковый Droid-стенд не отдаёт; кэш-токены покрыты юнит-агрегацией стора.
        self.assertEqual((sub["prompt_tokens"], sub["completion_tokens"], sub["total_tokens"]), (11, 4, 15))
        self.assertGreaterEqual(inter["stream_chunks"], 1)
        self.assertGreater(inter["response_bytes"], 0)
        self.assertEqual((payload["summary"]["total_requests"], payload["summary"]["subagent_requests"]), (2, 1))

    def test_rejected_requests_are_recorded_and_secrets_not_stored(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request(
            "POST", "/v1/chat/completions", body="{}",
            headers={"Authorization": "Bearer wrong-secret-xyz", "Content-Type": "application/json"},
        )
        self.assertEqual(conn.getresponse().status, 401)
        conn.close()
        self.assertEqual(self._chat(model="no-such-model-123")[0], 404)
        self.store.flush()
        _, payload = self._get("/v1/telemetry")
        codes = {r["status_code"]: r for r in payload["recent_requests"]}
        self.assertEqual((codes[401]["error_type"], codes[404]["error_type"]), ("auth_error", "model_not_found"))
        self.assertEqual(codes[404]["model"], "no-such-model-123")
        self.assertEqual(payload["summary"]["error_requests"], 2)
        dump = json.dumps(payload) + json.dumps(self.store._query("SELECT * FROM bridge_requests"))
        self.assertNotIn("wrong-secret-xyz", dump)
        self.assertNotIn("test-key", dump)
        self.assertEqual(self.store._query("SELECT auth_mode FROM bridge_requests WHERE status_code = 401")[0]["auth_mode"], "bearer")

    def test_telemetry_failure_never_breaks_request(self):
        class Boom:
            recent_limit = 100

            def record_request(self, _event):
                raise RuntimeError("storage down")

        server.REQUEST_TELEMETRY = Boom()
        self._script_ok()
        self.assertEqual(self._chat()[0], 200)

    def test_get_requests_do_not_pollute_telemetry(self):
        self._get("/v1/telemetry")
        self._get("/v1/nonexistent")
        self.store.flush()
        self.assertEqual(self.store.get_telemetry_payload()["summary"]["total_requests"], 0)

    def test_resolve_backend_topology(self):
        self.assertEqual(server._resolve_backend_topology("agy", "passthrough"), (":9887", ":10820 (xray SOCKS5)"))
        self.assertEqual(server._resolve_backend_topology("claude-p", "passthrough")[0], ":9881")
        self.assertEqual(server._resolve_backend_topology("some-cli", "cli"), ("cli:some-cli", "direct"))
        os.environ["BRIDGE_TELEMETRY_BACKEND_TOPOLOGY_JSON"] = json.dumps({"agy": [":1", "direct"], "bad": "x"})
        try:
            self.assertEqual(server._resolve_backend_topology("agy", "passthrough"), (":1", "direct"))
        finally:
            del os.environ["BRIDGE_TELEMETRY_BACKEND_TOPOLOGY_JSON"]

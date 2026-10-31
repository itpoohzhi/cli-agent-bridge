"""VER-004 (automated part): маршрутизация запроса через хаб :9882 с fake-droid.

Реальный bundled-bili spike (VER-004 PRE-CORE) этим модулем НЕ заменяется: здесь только
проверка, что фасад хаба вызывает ядро до адаптера, не даёт раннего контекстного 413
и сохраняет собственный лимит тела.

Запуск: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests python3 -m unittest -v test_context_resilience_routing
"""

import http.client
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import BridgeCase  # noqa: E402
from context_testlib import big, flags, oa, oa_history  # noqa: E402
from core import context_resilience as ctx  # noqa: E402

MODEL = "claude-sonnet-5-5"  # 1_000_000 / 128_000 в fleet.json


class StubFlags:
    def __init__(self, value):
        self.value = value

    def current(self):
        return self.value


OK_TURN = [
    ("text", "ok"),
    ("result", {"finalText": "", "usage": {}}),
    ("done", (0, "")),
]


class HubContextCase(BridgeCase):
    """BridgeCase + управляемые флаги/хранилище эпох ядра, с гарантированным откатом."""

    def setUp(self):
        super().setUp()
        saved = (server.CONTEXT_FLAGS, server.CONTEXT_EPOCHS, server.CONTEXT_ENROLLED)

        def restore():
            server.CONTEXT_FLAGS, server.CONTEXT_EPOCHS, server.CONTEXT_ENROLLED = saved

        self.addCleanup(restore)
        server.CONTEXT_EPOCHS = ctx.EpochStore()
        self.set_flags(False)

    def set_flags(self, pruner, shadow=False):
        server.CONTEXT_FLAGS = StubFlags(flags(pruner, shadow))

    def post_full(self, body, extra_headers=None, timeout=60.0):
        """(status, headers{lower}, text): заголовки читаются до тела."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            headers = {
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
            }
            headers.update(extra_headers or {})
            conn.request(
                "POST", "/v1/chat/completions", body=json.dumps(body), headers=headers
            )
            resp = conn.getresponse()
            hdrs = {k.lower(): v for k, v in resp.getheaders()}
            return resp.status, hdrs, resp.read().decode("utf-8")
        finally:
            conn.close()

    def sent_all(self):
        """Всё, что адаптер отправил droid: replay истории (skipAgentLoop) + финальный turn."""
        return "\n".join(self.hub.sent_texts()[self._mark :])

    def hist(self, turns, size):
        return oa_history(turns, size)

    _mark = 0

    def ask(self, model, history, **extra):
        self._mark = len(self.hub.sent_texts())
        self.hub.legacy([OK_TURN])
        return self.post_full(dict({"model": model, "messages": history}, **extra))


class TestNoEarly413(HubContextCase):
    def test_flags_off_large_body_passes_unchanged_and_no_header(self):
        history = [oa("system", "SYS"), oa("user", "TASK")]
        history += [oa("assistant", "x" + big(100_000)) for _ in range(37)]
        history.append(oa("user", "LAST-USER"))
        status, hdrs, text = self.ask(MODEL, history)
        self.assertEqual(status, 200, text[:300])
        self.assertNotIn(ctx.PRUNED_HEADER.lower(), hdrs)
        sent = self.sent_all()
        self.assertGreater(len(sent), 3_500_000)
        self.assertNotIn(ctx.MARKER_TEXT, sent)

    def test_pruner_on_large_body_within_window_is_not_rejected(self):
        self.set_flags(True)
        history = [oa("system", "SYS"), oa("user", "TASK")]
        history += [oa("assistant", "x" + big(100_000)) for _ in range(5)]
        history.append(oa("user", "LAST-USER"))
        status, hdrs, text = self.ask(MODEL, history)
        self.assertEqual(status, 200, text[:300])
        self.assertEqual(hdrs.get(ctx.PRUNED_HEADER.lower()), "false")
        self.assertNotIn(ctx.MARKER_TEXT, self.sent_all())

    def test_body_cap_of_hub_is_preserved(self):
        self.assertEqual(server.FLEET["image_limits"]["max_body_bytes"], 33554432)
        raw = self._raw_request(b"", cl=33554433)
        buf, _closed = self._raw_exchange(raw)
        code, typ, _ = self._raw_parse(buf)
        self.assertEqual((code, typ), (413, "payload_too_large"))
        self.assertEqual(self.hub.spawns(), [])


class TestHubGate(HubContextCase):
    SMALL = 300  # 300 × ~2 КБ ≈ 0.6 МБ, больше окна 256k

    def _long_history(self):
        return self.hist(40, 4000)

    def test_oversize_history_is_pruned_before_adapter(self):
        self.set_flags(True)
        history = self._long_history()
        status, hdrs, text = self.ask("grok-4.7", history)  # окно 256000, R=32768
        self.assertEqual(status, 200, text[:300])
        self.assertEqual(hdrs.get(ctx.PRUNED_HEADER.lower()), "true")
        sent = self.sent_all()
        self.assertIn(ctx.MARKER_TEXT, sent)
        self.assertIn("LAST-USER", sent)
        self.assertIn("TASK-ANCHOR", sent)
        self.assertNotIn("u0-", sent)
        self.assertLess(len(sent), 256_000 - 32_768 + 20_000)

    def test_stream_header_arrives_before_first_sse_byte(self):
        self.set_flags(True)
        self.hub.legacy([OK_TURN])
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        try:
            conn.request(
                "POST",
                "/v1/chat/completions",
                body=json.dumps(
                    {
                        "model": "grok-4.7",
                        "stream": True,
                        "messages": self._long_history(),
                    }
                ),
                headers={
                    "Authorization": "Bearer test-key",
                    "Content-Type": "application/json",
                },
            )
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.getheader(ctx.PRUNED_HEADER), "true")
            self.assertIn("text/event-stream", resp.getheader("Content-Type"))
            self.assertIn("data:", resp.read().decode("utf-8"))
        finally:
            conn.close()

    def test_stream_unpruned_header_false(self):
        self.set_flags(True)
        self.hub.legacy([OK_TURN])
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=60)
        try:
            conn.request(
                "POST",
                "/v1/chat/completions",
                body=json.dumps(
                    {"model": MODEL, "stream": True, "messages": [oa("user", "hi")]}
                ),
                headers={
                    "Authorization": "Bearer test-key",
                    "Content-Type": "application/json",
                },
            )
            resp = conn.getresponse()
            self.assertEqual(resp.getheader(ctx.PRUNED_HEADER), "false")
            resp.read()
        finally:
            conn.close()

    def test_enrolled_route_rejects_oversize_with_pruner_off_zero_spawn(self):
        server.CONTEXT_ENROLLED = True
        status, hdrs, text = self.ask("grok-4.7", self._long_history())
        self.assertEqual(status, 400, text[:200])
        err = json.loads(text)["error"]
        self.assertEqual(err["type"], "invalid_request")
        self.assertIn(ctx.REASON_REQUIRED_EXCEEDS, err["message"])
        self.assertEqual(self.hub.spawns(), [])
        self.assertEqual(self.hub.admissions(), [])

    def test_enrolled_route_keeps_small_requests_working(self):
        server.CONTEXT_ENROLLED = True
        status, hdrs, text = self.ask(MODEL, [oa("user", "hi")])
        self.assertEqual(status, 200)
        self.assertEqual(hdrs.get(ctx.PRUNED_HEADER.lower()), "false")

    def test_mandatory_overflow_is_400_not_truncation(self):
        self.set_flags(True)
        history = [oa("system", "SYS"), oa("user", big(300_000))]
        status, _hdrs, text = self.ask("grok-4.7", history)
        self.assertEqual(status, 400)
        self.assertIn(ctx.REASON_REQUIRED_EXCEEDS, text)
        self.assertEqual(self.hub.spawns(), [])

    def test_image_without_passport_fails_closed_503(self):
        self.set_flags(True)
        history = [
            oa(
                "user",
                [
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/png;base64,AAAA"},
                    }
                ],
            )
        ]
        status, _hdrs, text = self.ask(MODEL, history)
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(text)["error"]["type"], "launcher_unavailable")
        self.assertEqual(self.hub.spawns(), [])

    def test_shadow_mode_never_changes_traffic(self):
        self.set_flags(False, shadow=True)
        history = self._long_history()
        status, hdrs, text = self.ask("grok-4.7", history)
        self.assertEqual(status, 200)
        self.assertNotIn(ctx.PRUNED_HEADER.lower(), hdrs)
        sent = self.sent_all()
        self.assertNotIn(ctx.MARKER_TEXT, sent)
        self.assertIn("u0-", sent)

    def test_non_list_messages_keep_existing_behaviour(self):
        self.set_flags(True)
        self.hub.legacy([OK_TURN])
        status, _hdrs, text = self.post_full({"model": MODEL, "messages": "oops"})
        self.assertNotIn(status, (413, 503))
        self.assertNotIn(ctx.REASON_REQUIRED_EXCEEDS, text)

    def test_unknown_model_error_is_404(self):
        self.set_flags(True)
        status, _hdrs, text = self.post_full(
            {"model": "nope", "messages": [oa("user", "x")]}
        )
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(text)["error"]["type"], "model_not_found")

    def test_trusted_ids_route_to_epoch_and_no_id_does_not(self):
        self.set_flags(True)
        self.ask("grok-4.7", self._long_history())
        self.assertEqual(
            len(server.CONTEXT_EPOCHS), 0
        )  # без доверенных ID эпоха не хранится
        self.hub.legacy([OK_TURN])
        self.post_full(
            {"model": "grok-4.7", "messages": self._long_history()},
            extra_headers={"x-session-id": "sess-1", "x-dsh-chat-id": "chat-1"},
        )
        self.assertEqual(len(server.CONTEXT_EPOCHS), 1)


class TestHubSwitching(HubContextCase):
    """Смена моделей хаба 1M → 256k → 272k → 1M на одной истории."""

    def test_model_sequence_prunes_per_target_and_returns_to_full(self):
        self.set_flags(True)
        history = self.hist(
            30, 3000
        )  # ≈ 300 КБ: помещается в 1M, не помещается в 256k/272k-R
        # Узкое CLI-окно — тестовая модель: реальные sol/terra принадлежат passthrough.
        server.FLEET["models"]["test-narrow-window"] = dict(
            server.FLEET["models"]["grok-4.7"], id="test-narrow-window",
            context_window=272000, max_tokens=128000,
        )
        self.addCleanup(server.FLEET["models"].pop, "test-narrow-window")
        plan = [
            (MODEL, "false"),
            ("grok-4.7", "true"),
            ("test-narrow-window", "true"),
            (MODEL, "false"),
        ]
        sent_sizes = []
        for model, expected in plan:
            status, hdrs, text = self.ask(model, history)
            self.assertEqual(status, 200, f"{model}: {text[:200]}")
            self.assertEqual(hdrs.get(ctx.PRUNED_HEADER.lower()), expected, model)
            sent_sizes.append(len(self.sent_all()))
        self.assertLess(sent_sizes[1], sent_sizes[0])
        self.assertLess(sent_sizes[2], sent_sizes[1])
        self.assertEqual(sent_sizes[3], sent_sizes[0])  # возврат на 1M: полная история


if __name__ == "__main__":
    unittest.main()

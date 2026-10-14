"""Честный живой SSE-стриминг droid (AD-001..AD-004): инкрементальная доставка,
strict_live-парсер tool_call, fail-close на retract/malformed-блок, usage-чанк
без повторного finish_reason, немедленное освобождение T/L независимо от клиента.

Все сценарии идут через настоящий HTTP-сервер моста и настоящий fake-subprocess
(tests/fake_droid.py), говорящий stream-jsonrpc. Реальный droid и сеть не используются.
"""

import json
import queue
import socket
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import TOOLS, wait_until  # noqa: E402
from rpc_testlib import RpcCase  # noqa: E402

BODY = {"model": "claude-sonnet-5-5"}


def msg(text, role="user"):
    return {"role": role, "content": text}


class LiveStreamCase(RpcCase):
    """RpcCase + сырой таймированный читатель SSE-ответа (нужен для t_first < t_done)."""

    def _timed_sse(self, body: dict, deadline: float = 15.0):
        """(список (t_recv, raw_frame), полный текст тела) — таймстемп на каждый "data: …" кадр.

        Таймстемп кадра — момент, когда recv() впервые принёс байты, замыкающие его
        законченной парой "\\n\\n": достаточно грубо, чтобы отличить "первый контент
        пришёл заметно раньше финала" от "всё одним куском после полного хода" (AD-003).
        """
        payload = json.dumps(dict(body, stream=True)).encode()
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=deadline)
        frames = []
        try:
            sock.sendall(self._raw_request(payload))
            buf = b""
            seen_header = False
            emitted = 0
            started = time.monotonic()
            while time.monotonic() - started < deadline:
                try:
                    sock.settimeout(0.05)
                    chunk = sock.recv(65536)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not chunk:
                    break
                now = time.monotonic()
                buf += chunk
                if not seen_header:
                    if b"\r\n\r\n" not in buf:
                        continue
                    seen_header = True
                    buf = buf.split(b"\r\n\r\n", 1)[1]
                parts = buf.decode("utf-8", "replace").split("\n\n")
                complete = parts[:-1]  # последний элемент — возможно неполный хвост
                for raw in complete[emitted:]:
                    if raw.strip():
                        frames.append((now, raw.strip()))
                emitted = len(complete)
                if raw_endswith_done(complete):
                    break
            full = buf.decode("utf-8", "replace")
        finally:
            sock.close()
        return frames, full

    @staticmethod
    def _frame_json(raw: str):
        if not raw.startswith("data: "):
            return None
        payload = raw[len("data: ") :]
        if payload == "[DONE]":
            return None
        try:
            return json.loads(payload)
        except ValueError:
            return None


def raw_endswith_done(parts) -> bool:
    return any(p.strip() == "data: [DONE]" for p in parts)


class TestIncrementalDelivery(LiveStreamCase):
    """AD-002/AD-003: контент уходит по мере готовности, а не одним куском после полного хода."""

    def test_content_deltas_arrive_incrementally_before_done(self):
        """Между первым куском текста и финалом измеримая пауза -> t_first < t_done строго."""
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": "Hello there", "pause": 0.5},
                        {"op": "text", "text": "World after the pause"},
                    ]
                }
            ]
        )
        frames, full = self._timed_sse(dict(BODY, messages=[msg("hi")]))
        self.assertIn("data: [DONE]", full)
        content_times = [
            t
            for t, raw in frames
            if (j := self._frame_json(raw)) is not None
            and j.get("choices", [{}])[0].get("delta", {}).get("content")
        ]
        finish_times = [
            t
            for t, raw in frames
            if (j := self._frame_json(raw)) is not None
            and j.get("choices", [{}])[0].get("finish_reason")
        ]
        self.assertTrue(content_times, full)
        self.assertTrue(finish_times, full)
        # Контент пришёл раньше финала с заметным (не наносекундным) запасом: это
        # и есть разница между "живьём по мере готовности" и "одним куском под конец".
        self.assertLess(content_times[0], finish_times[0] - 0.2)

    def test_multiple_distinct_content_chunks_not_one_blob(self):
        """Хотя бы 2 разных SSE-кадра с контентом (не всё в одном финальном кадре)."""
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": "first part", "pause": 0.3},
                        {"op": "text", "text": "second part"},
                    ]
                }
            ]
        )
        frames, full = self._timed_sse(dict(BODY, messages=[msg("hi")]))
        content_frames = [
            raw
            for _, raw in frames
            if (j := self._frame_json(raw)) is not None
            and j.get("choices", [{}])[0].get("delta", {}).get("content")
        ]
        self.assertGreaterEqual(len(content_frames), 2, full)


class TestStrictLiveFailClose(LiveStreamCase):
    """AD-001/AD-002: невалидный/незакрытый <tool_call> в живом ходе — ошибка, не текст с XML."""

    def test_malformed_tool_call_block_fails_closed_without_leaking_raw_xml(self):
        self.hub.script(
            [
                {
                    "steps": [
                        {
                            "op": "text",
                            "text": server.TOOL_CALL_OPEN
                            + "not json"
                            + server.TOOL_CALL_CLOSE,
                        }
                    ]
                }
            ]
        )
        status, stream = self._post(
            dict(BODY, stream=True, tools=TOOLS, messages=[msg("hi")])
        )
        self.assertEqual(status, 200)
        self.assertIn("live_prefix_invalidated", stream)
        self.assertNotIn("not json", stream)
        self.assertNotIn(server.TOOL_CALL_OPEN, stream)
        self.assertNotIn('"finish_reason": "stop"', stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))

    def test_well_formed_tool_call_is_unaffected(self):
        """Контрольная проба: валидный вызов живым ходом доходит как обычно (strict_live не мешает)."""
        call = (
            server.TOOL_CALL_OPEN
            + '{"name": "get_weather", "arguments": {"city": "Berlin"}}'
            + server.TOOL_CALL_CLOSE
        )
        self.hub.script([{"steps": [{"op": "text", "text": call}]}])
        status, stream = self._post(
            dict(BODY, stream=True, tools=TOOLS, messages=[msg("hi")])
        )
        self.assertEqual(status, 200)
        self.assertIn('"finish_reason": "tool_calls"', stream)
        self.assertIn("get_weather", stream)
        self.assertNotIn("live_prefix_invalidated", stream)


class TestLiveInvalidatedOnRetraction(LiveStreamCase):
    """AD-001: уже отданный клиенту живой префикс оказался незакоммиченным -> честный fail-close."""

    def test_retract_after_live_delta_invalidates_the_turn(self):
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": "streamed-then-retracted"},
                        {"op": "retract"},
                        {"op": "error", "message": "backend changed its mind"},
                    ],
                    "reason": "model_request_rejected",
                }
            ]
        )
        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertIn("backend changed its mind", stream)
        self.assertNotIn("streamed-then-retracted", stream)
        self.assertNotIn('"finish_reason": "stop"', stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))

    def test_normal_turn_without_retraction_is_unaffected(self):
        """Контрольная проба: без retract ход завершается обычным stop, без live_invalidated."""
        self.hub.script([{"steps": [{"op": "text", "text": "all good"}]}])
        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertIn('"finish_reason": "stop"', stream)
        self.assertNotIn("live_prefix_invalidated", stream)


class TestHonestUsageChunk(LiveStreamCase):
    """AD-004: отдельный usage-чанк после finish — finish_reason там null, не повтор stop/tool_calls."""

    def test_usage_chunk_finish_reason_is_null_not_duplicated_stop(self):
        self.hub.script(
            [
                {
                    "steps": [{"op": "text", "text": "hi"}],
                    "usage": {"inputTokens": 10, "outputTokens": 5},
                }
            ]
        )
        frames, full = self._timed_sse(dict(BODY, messages=[msg("hi")]))
        usage_frames = [
            self._frame_json(raw)
            for _, raw in frames
            if (j := self._frame_json(raw)) is not None and "usage" in j
        ]
        self.assertEqual(len(usage_frames), 1, full)
        self.assertIsNone(usage_frames[0]["choices"][0]["finish_reason"])
        # А более раннему кадру finish всё же есть: честный "stop" ушёл один раз, раньше.
        stop_frames = [
            self._frame_json(raw)
            for _, raw in frames
            if (j := self._frame_json(raw)) is not None
            and j.get("choices", [{}])[0].get("finish_reason") == "stop"
        ]
        self.assertEqual(len(stop_frames), 1, full)


class TestImmediateLockRelease(LiveStreamCase):
    """RW-009 в живом ходе: клиент не читает SSE — вычисление, commit и слот P это не блокирует."""

    def test_non_reading_client_does_not_prevent_commit_or_next_slot(self):
        # FU-207: восстановление гарантировано addCleanup (LIFO, после tearDown, даже
        # при исключении/assertion в самом тесте) — не зависит от того, читает ли кто-то
        # общий _saved родительского BridgeCase, и не оставляет MAX_CONCURRENT=1 соседям.
        self.addCleanup(setattr, server, "MAX_CONCURRENT", server.MAX_CONCURRENT)
        server.MAX_CONCURRENT = 1
        big = "Y" * 2_000_000
        self.hub.script(
            [
                {"steps": [{"op": "text", "text": big}]},
                {"steps": [{"op": "text", "text": "second"}]},
            ]
        )
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        sock.connect(("127.0.0.1", self.port))
        payload = json.dumps(
            dict(BODY, stream=True, prompt_cache_key="never-read", messages=[msg("go")])
        ).encode()
        try:
            sock.sendall(self._raw_request(payload))
            self.assertTrue(
                wait_until(lambda: len(self.hub.admissions()) >= 1, timeout=15)
            )
            time.sleep(
                0.5
            )  # вычисление успело закончиться; никто recv() на этом сокете не вызывал
            # Вычисление заканчивается и чат коммитится READY, даже если никто не читает ответ.
            self.assertTrue(
                wait_until(
                    lambda: self.chat_of("never-read").state in ("READY", "PERSISTED"),
                    timeout=15,
                )
            )
            # MAX_CONCURRENT=1: второй чат получит слот P только если первый его
            # действительно вернул, а не держит из-за непрочитанной живой доставки.
            status, body = self._post_json(
                dict(BODY, prompt_cache_key="second-chat", messages=[msg("hi")])
            )
            self.assertEqual(status, 200)
            self.assertEqual(body["choices"][0]["message"]["content"], "second")
        finally:
            sock.close()


class TestKeepaliveRespectsDeadClient(LiveStreamCase):
    """RW-201: keepalive медленному/мёртвому клиенту ограничен LIVE_WRITE_TIMEOUT_S и не
    повторяется после client_write_dead; L/T освобождаются быстро, следующий ход получает слот."""

    def test_keepalive_bounded_and_skipped_after_write_failure(self):
        self.addCleanup(setattr, server, "MAX_CONCURRENT", server.MAX_CONCURRENT)
        server.MAX_CONCURRENT = 1
        with (
            mock.patch.object(server, "LIVE_WRITE_TIMEOUT_S", 0.3),
            mock.patch.object(server, "KEEPALIVE_S", 0.2),
        ):
            big = "Z" * 2_000_000
            self.hub.script(
                [
                    {
                        "steps": [
                            {"op": "text", "text": big},
                            {"op": "sleep", "s": 1.5},
                            {"op": "text", "text": "ignored"},
                        ]
                    },
                    {"steps": [{"op": "text", "text": "second"}]},
                ]
            )
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            sock.connect(("127.0.0.1", self.port))
            payload = json.dumps(
                dict(
                    BODY,
                    stream=True,
                    prompt_cache_key="dead-client",
                    messages=[msg("go")],
                )
            ).encode()
            started = time.monotonic()
            try:
                sock.sendall(self._raw_request(payload))
                # Чат регистрируется в REGISTRY до первого add_user_message: дождаться этого
                # перед chat_of, иначе предикат может выполниться раньше регистрации.
                self.assertTrue(
                    wait_until(lambda: len(self.hub.admissions()) >= 1, timeout=10)
                )
                # Полный ход (включая 1.5с внутренней паузы droid и несколько тиков
                # KEEPALIVE_S=0.2с на пустой очереди) обязан закончиться за секунды, а не
                # зависнуть на таймауте соединения (300с) — именно это ломала keepalive
                # без собственного таймаута и без проверки client_write_dead (RW-201):
                # каждая попытка записи мёртвому клиенту висела бы до таймаута соединения.
                self.assertTrue(
                    wait_until(
                        lambda: (
                            self.chat_of("dead-client").state in ("READY", "PERSISTED")
                        ),
                        timeout=10,
                    )
                )
                elapsed = time.monotonic() - started
                self.assertLess(elapsed, 8.0)
                # MAX_CONCURRENT=1: следующий ход получает слот без ожидания мёртвого клиента.
                status, body = self._post_json(
                    dict(BODY, prompt_cache_key="second-chat", messages=[msg("hi")])
                )
                self.assertEqual(status, 200)
                self.assertEqual(body["choices"][0]["message"]["content"], "second")
            finally:
                sock.close()


class TestLiveErrorEnvelope(LiveStreamCase):
    """RW-202: fail-close конверт chat.completion.chunk (не плоский {"error": ...}) для
    live_prefix_invalidated — id/created/model совпадают с предыдущими кадрами, finish_reason=null,
    точные type/code/param; успешного stop/usage после такой ошибки нет."""

    def test_malformed_tool_call_error_uses_chat_completion_chunk_envelope(self):
        self.hub.script(
            [
                {
                    "steps": [
                        {
                            "op": "text",
                            "text": server.TOOL_CALL_OPEN
                            + "not json"
                            + server.TOOL_CALL_CLOSE,
                        }
                    ]
                }
            ]
        )
        status, stream = self._post(
            dict(BODY, stream=True, tools=TOOLS, messages=[msg("hi")])
        )
        self.assertEqual(status, 200)
        frames = [
            f for f in (self._frame_json(line) for line in stream.splitlines()) if f
        ]
        error_frames = [f for f in frames if "error" in f]
        self.assertEqual(len(error_frames), 1, stream)
        err_frame = error_frames[0]
        self.assertEqual(err_frame["object"], "chat.completion.chunk")
        self.assertEqual(
            err_frame["choices"], [{"index": 0, "delta": {}, "finish_reason": None}]
        )
        self.assertEqual(err_frame["error"]["type"], "stream_error")
        self.assertEqual(err_frame["error"]["code"], "live_prefix_invalidated")
        self.assertIsNone(err_frame["error"]["param"])
        self.assertTrue(err_frame["error"]["message"])
        other_frames = [f for f in frames if f is not err_frame]
        self.assertTrue(other_frames, stream)
        for f in other_frames:
            self.assertEqual(f["id"], err_frame["id"])
            self.assertEqual(f["created"], err_frame["created"])
            self.assertEqual(f["model"], err_frame["model"])
        self.assertNotIn('"finish_reason": "stop"', stream)
        self.assertNotIn('"usage"', stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))


class TestRunQueuePublishOverflow(unittest.TestCase):
    """RW-204: Run._publish не блокирует producer при переполнении Run.q и не теряет сигнал."""

    @staticmethod
    def _run(maxsize):
        run = server.Run.__new__(server.Run)
        run.q = queue.Queue(maxsize=maxsize)
        run.live_invalidated = False
        run._last_error = ""
        run.active_turn = "turn-x"
        # RW-208: лимит очереди и overflow-инвалидация действуют только у live-хода.
        run.sse_writer = lambda *args: True
        return run

    def test_overflow_sets_live_invalidated_without_blocking(self):
        run = self._run(2)
        self.assertTrue(run._publish(("text", "a")))
        self.assertTrue(run._publish(("text", "b")))
        self.assertFalse(run.live_invalidated)
        # Третья публикация в заполненную очередь — немедленный (неблокирующий) отказ,
        # а не TimeoutError/бесконечное ожидание producer.
        started = time.monotonic()
        ok = run._publish(("text", "c"))
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertFalse(ok)
        self.assertTrue(run.live_invalidated)
        self.assertEqual(run._last_error, "Run.q overflow")
        # Очередь остаётся ограниченного размера -- переполнение не копится в ней.
        self.assertEqual(run.q.qsize(), 2)

    def test_first_overflow_error_message_is_not_overwritten(self):
        run = self._run(1)
        run._publish(("text", "a"))
        run._publish(("text", "b"))
        run._last_error = "earlier real error"
        run._publish(("text", "c"))
        self.assertEqual(run._last_error, "earlier real error")


class TestRunQueueOverflowEndToEnd(LiveStreamCase):
    """RW-204: maxsize=1024 по умолчанию, медленный потребитель + переполненная очередь
    обнаруживаются без зависания producer; усечённый ход не завершается успешным finish/usage,
    ресурсы (слот P) освобождаются."""

    def test_flood_beyond_queue_capacity_fails_closed_without_hang(self):
        self.addCleanup(setattr, server, "MAX_CONCURRENT", server.MAX_CONCURRENT)
        server.MAX_CONCURRENT = 1
        with (
            mock.patch.object(server, "RUN_QUEUE_MAXSIZE", 2),
            self.capture_logs() as lines,
        ):
            # Много отдельных сообщений без пауз (а не "flood" на один messageId: его дельты
            # до create_message копятся в Run._held, а не в Run.q, и overflow не задевают) —
            # producer обгоняет consumer по-настоящему, maxsize=2 переполняется.
            self.hub.script(
                [
                    {
                        "steps": [
                            {"op": "text", "text": f"chunk-{i}"} for i in range(400)
                        ]
                    },
                    {"steps": [{"op": "text", "text": "second"}]},
                ]
            )
            status, stream = self._post(
                dict(
                    BODY,
                    stream=True,
                    prompt_cache_key="flood-chat",
                    messages=[msg("go")],
                ),
                timeout=30,
            )
        self.assertEqual(status, 200)
        self.assertTrue(
            any("run_queue_overflow" in line for line in lines),
            "test did not actually exercise Run.q overflow; stream=%r"
            % (stream[:500],),
        )
        self.assertIn("live_prefix_invalidated", stream)
        self.assertNotIn('"finish_reason": "stop"', stream)
        self.assertNotIn('"usage"', stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
        # MAX_CONCURRENT=1: слот P освобождён -- следующий ход не ждёт watchdog/таймаут.
        status, body = self._post_json(
            dict(BODY, prompt_cache_key="second-chat", messages=[msg("hi")])
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "second")


class TestLivePrefixValidation(LiveStreamCase):
    """RW-205: complete/backfill обязан продолжать уже отправленный live-префикс (AD-001):
    несовпадающий или укороченный complete -> live_invalidated без молчаливого среза
    и без успешного finish/usage; равный текст не дублируется."""

    def test_content_complete_with_mismatching_text_invalidates(self):
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": "Hello wor"},
                        {"op": "complete_mismatch", "text": "Goodbye"},
                    ]
                }
            ]
        )
        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertIn("live_prefix_invalidated", stream)
        self.assertNotIn('"finish_reason": "stop"', stream)
        self.assertNotIn('"usage"', stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))

    def test_content_complete_shorter_than_sent_prefix_invalidates(self):
        """Укороченный complete (валидный текст, но короче уже отправленного) — тоже fail-close."""
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": "Hello world"},
                        {"op": "complete_mismatch", "text": "Hello"},
                    ]
                }
            ]
        )
        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertIn("live_prefix_invalidated", stream)
        self.assertNotIn('"finish_reason": "stop"', stream)

    def test_reasoning_complete_with_mismatching_text_invalidates(self):
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "thinking", "text": "step one", "alone": True},
                        {"op": "thinking_complete_mismatch", "text": "unrelated"},
                    ]
                }
            ]
        )
        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertIn("live_prefix_invalidated", stream)
        self.assertNotIn('"finish_reason": "stop"', stream)

    def test_mismatch_on_second_of_multiple_mids_only_invalidates_once(self):
        self.hub.script(
            [
                {
                    "steps": [
                        # pause: гарантирует, что consumer успевает забрать и отдать
                        # первый mid live-доставкой до того, как второй mid инвалидирует ход.
                        {
                            "op": "text",
                            "text": "first message",
                            "complete_with_text": True,
                            "pause": 0.3,
                        },
                        {"op": "text", "text": "second mess"},
                        {"op": "complete_mismatch", "text": "totally different"},
                    ]
                }
            ]
        )
        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertIn("first message", stream)
        self.assertIn("live_prefix_invalidated", stream)
        self.assertNotIn('"finish_reason": "stop"', stream)

    def test_valid_prefix_extension_is_not_duplicated(self):
        """Контрольная проба: complete, повторяющий уже отправленный префикс -- без
        live_invalidated, и совпадающий хвост не дублируется."""
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": "same text", "complete_with_text": True}
                    ]
                }
            ]
        )
        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertNotIn("live_prefix_invalidated", stream)
        self.assertIn('"finish_reason": "stop"', stream)
        content_frames = [
            f
            for f in (self._frame_json(line) for line in stream.splitlines())
            if f is not None
            and f.get("choices", [{}])[0].get("delta", {}).get("content")
        ]
        joined = "".join(f["choices"][0]["delta"]["content"] for f in content_frames)
        self.assertEqual(joined, "same text")


class TestUtf8DeliveryBudget(LiveStreamCase):
    """RW-206: бюджет живой доставки резервируется в UTF-8 байтах, а не в символах Python."""

    def test_cyrillic_text_is_budgeted_by_utf8_bytes_not_chars(self):
        text = "привет"  # 6 символов, 12 байт UTF-8: бюджет=8 вмещает символы, но не байты.
        self.assertEqual(len(text), 6)
        self.assertEqual(len(text.encode("utf-8")), 12)
        budget = server._ByteBudget(8)
        with mock.patch.object(server, "_DELIVERY_BUDGET", budget):
            self.hub.script([{"steps": [{"op": "text", "text": text}]}])
            status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertIn("delivery memory budget exhausted", stream)
        self.assertNotIn(text, stream)
        self.assertNotIn('"finish_reason": "stop"', stream)
        self.assertTrue(wait_until(lambda: budget._used == 0))

    def test_emoji_text_delivers_fully_with_generous_budget(self):
        """Контрольная проба: многобайтовый (emoji) текст доходит целиком с достаточным бюджетом."""
        text = "🎉🎉 party"
        budget = server._ByteBudget(10_000)
        with mock.patch.object(server, "_DELIVERY_BUDGET", budget):
            self.hub.script([{"steps": [{"op": "text", "text": text}]}])
            status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        self.assertIn('"finish_reason": "stop"', stream)
        content_frames = [
            f
            for f in (self._frame_json(line) for line in stream.splitlines())
            if f is not None
            and f.get("choices", [{}])[0].get("delta", {}).get("content")
        ]
        joined = "".join(f["choices"][0]["delta"]["content"] for f in content_frames)
        self.assertEqual(joined, text)
        self.assertTrue(wait_until(lambda: budget._used == 0))


class TestUsageFinishReasonByBackend(unittest.TestCase):
    """RW-206: finish_reason=null в usage-кадре -- только для живого Droid-стриминга;
    контрольный поток другого бэкенда сохраняет прежний finish_reason в usage."""

    @staticmethod
    def _out(backend_kind: str) -> dict:
        return {
            "state": "done",
            "rc": 0,
            "text": "hi",
            "err": "",
            "backend_kind": backend_kind,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "events": [] if backend_kind == "droid" else [("content", "hi")],
            "tool_calls": [],
        }

    def _frames_from(self, out: dict) -> list:
        h = server.Handler.__new__(server.Handler)
        frames: list = []
        h.send_response = lambda *a, **k: None
        h.send_header = lambda *a, **k: None
        h.end_headers = lambda: None
        h._emit = lambda data: frames.append(data) or True
        h._dispatch = lambda *a: out
        h._reserve_delivery = lambda o: None
        h._serve_sse({"model": "test-model"})
        return [
            json.loads(f[len("data: ") :]) for f in frames if f.startswith("data: {")
        ]

    def test_droid_live_stream_usage_finish_reason_is_null(self):
        frames = self._frames_from(self._out("droid"))
        usage_frames = [f for f in frames if "usage" in f]
        self.assertEqual(len(usage_frames), 1)
        self.assertIsNone(usage_frames[0]["choices"][0]["finish_reason"])

    def test_other_backend_usage_finish_reason_repeats_finish(self):
        frames = self._frames_from(self._out("muse"))
        usage_frames = [f for f in frames if "usage" in f]
        self.assertEqual(len(usage_frames), 1)
        self.assertEqual(usage_frames[0]["choices"][0]["finish_reason"], "stop")


class TestClientWriteDeadSuppressesTerminalFrames(unittest.TestCase):
    """RW-203/FU-212: отказ живой записи виден _serve_sse и после _dispatch (state=done,
    rc=0): мёртвому клиенту не уходят ни stop/tool_calls, ни usage, ни error, ни [DONE];
    следующий запрос на том же Handler не наследует client_write_dead."""

    @staticmethod
    def _handler(frames: list) -> server.Handler:
        h = server.Handler.__new__(server.Handler)
        h.send_response = lambda *args, **kwargs: None
        h.send_header = lambda *args, **kwargs: None
        h.end_headers = lambda: None
        h._emit = lambda data: frames.append(data) or True
        h._reserve_delivery = lambda out: None
        h._client_write_dead = False
        return h

    @staticmethod
    def _done_out(text: str) -> dict:
        return {
            "state": "done",
            "rc": 0,
            "text": text,
            "err": "",
            "usage": {"input_tokens": 7, "output_tokens": 3},
            "events": [],
            "tool_calls": [],
            "backend_kind": "droid",
        }

    def test_write_failure_suppresses_external_terminal_frames(self):
        cases = (
            ("content", '"delta": {"content": "live-piece"}'),
            ("reasoning", '"delta": {"reasoning_content": "live-piece"}'),
        )
        for kind, needle in cases:
            with self.subTest(kind=kind):
                frames: list = []
                h = self._handler(frames)
                left, right = socket.socketpair()
                self.addCleanup(left.close)
                self.addCleanup(right.close)
                h.connection = left

                def emit(data: str) -> bool:
                    if needle in data:
                        return False  # сокет отверг ровно этот живой кадр
                    frames.append(data)
                    return True

                h._emit = emit

                def dispatch(ctx, keepalive, sse_writer, _kind=kind):
                    # как _execute: первый отказ живой записи -> дальнейших попыток нет
                    self.assertFalse(sse_writer(_kind, "live-piece"))
                    return self._done_out("live-piece")

                h._dispatch = dispatch
                h._serve_sse({"model": "test-model"})
                self.assertTrue(h._client_write_dead)
                joined = "".join(frames)
                self.assertEqual(len(frames), 1, joined)  # только role-кадр
                self.assertIn('"role": "assistant"', joined)
                self.assertNotIn('"finish_reason": "stop"', joined)
                self.assertNotIn('"usage"', joined)
                self.assertNotIn("error", joined)
                self.assertNotIn("[DONE]", joined)

                # Следующий запрос на том же Handler: состояние не наследуется.
                h._emit = lambda data: frames.append(data) or True

                def good_dispatch(ctx, keepalive, sse_writer):
                    self.assertTrue(sse_writer("content", "second"))
                    return self._done_out("second")

                h._dispatch = good_dispatch
                h._serve_sse({"model": "test-model"})
                tail = "".join(frames)
                self.assertIn('"finish_reason": "stop"', tail)
                self.assertIn('"usage"', tail)
                self.assertTrue(tail.rstrip().endswith("data: [DONE]"))


class TestLiveFailureEnvelopeAfterPrefix(unittest.TestCase):
    """RW-211/FU-212: терминальный сбой хода/адаптера после уже отданного live-префикса —
    ровно один fail-close chat.completion.chunk с объектом error (вместо плоского
    {"error": ...} или сырого исключения), затем отдельный [DONE]; finish/usage нет."""

    def _serve(self, dispatch) -> list:
        frames: list = []
        h = server.Handler.__new__(server.Handler)
        h.send_response = lambda *args, **kwargs: None
        h.send_header = lambda *args, **kwargs: None
        h.end_headers = lambda: None
        h._emit = lambda data: frames.append(data) or True
        h._reserve_delivery = lambda out: None
        h._client_write_dead = False
        h._dispatch = dispatch
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        h.connection = left
        h._serve_sse({"model": "test-model"})
        return frames

    def _assert_fail_close_envelope(self, frames: list, message_part: str) -> None:
        payloads = [
            json.loads(frame[len("data: ") :])
            for frame in frames
            if frame.startswith("data: {")
        ]
        errors = [p for p in payloads if "error" in p]
        self.assertEqual(len(errors), 1, frames)
        error = errors[0]
        self.assertEqual(error.get("object"), "chat.completion.chunk", frames)
        self.assertEqual(
            error["choices"], [{"index": 0, "delta": {}, "finish_reason": None}]
        )
        self.assertEqual(error["error"]["type"], "stream_error")
        self.assertEqual(error["error"]["code"], "live_prefix_invalidated")
        self.assertIsNone(error["error"]["param"])
        self.assertIn(message_part, error["error"]["message"])
        joined = "".join(frames)
        # Префикс ушёл клиенту ровно один раз; успешного finish/usage после сбоя нет.
        self.assertEqual(joined.count('"delta": {"content": "partial"}'), 1)
        self.assertNotIn('"finish_reason": "stop"', joined)
        self.assertNotIn('"usage"', joined)
        self.assertTrue(joined.rstrip().endswith("data: [DONE]"))
        for payload in payloads:
            self.assertEqual(payload["id"], error["id"])
            self.assertEqual(payload["created"], error["created"])
            self.assertEqual(payload["model"], error["model"])

    def test_error_envelope_sent_on_adapter_failure_after_live_prefix(self):
        def adapter_error(ctx, keepalive, sse_writer):
            self.assertTrue(sse_writer("content", "partial"))
            return {
                "state": "droid_error",
                "rc": 1,
                "text": "partial",
                "err": "adapter went down",
                "usage": {},
                "events": [],
                "tool_calls": [],
                "backend_kind": "droid",
            }

        self._assert_fail_close_envelope(self._serve(adapter_error), "adapter went down")

    def test_error_envelope_on_nonzero_terminal_rc_after_live_prefix(self):
        def nonzero_rc(ctx, keepalive, sse_writer):
            self.assertTrue(sse_writer("content", "partial"))
            return {
                "state": "done",
                "rc": 1,
                "text": "partial",
                "err": "eof before commit",
                "usage": {},
                "events": [],
                "tool_calls": [],
                "backend_kind": "droid",
            }

        self._assert_fail_close_envelope(self._serve(nonzero_rc), "rc=1")

    def test_error_envelope_on_dispatch_exception_after_live_prefix(self):
        def adapter_boom(ctx, keepalive, sse_writer):
            self.assertTrue(sse_writer("content", "partial"))
            raise RuntimeError("adapter exploded")

        self._assert_fail_close_envelope(self._serve(adapter_boom), "adapter exploded")

    def test_healthy_live_turn_keeps_success_frames(self):
        def healthy(ctx, keepalive, sse_writer):
            self.assertTrue(sse_writer("content", "partial"))
            return {
                "state": "done",
                "rc": 0,
                "text": "partial",
                "err": "",
                "usage": {"input_tokens": 5, "output_tokens": 2},
                "events": [],
                "tool_calls": [],
                "backend_kind": "droid",
            }

        frames = self._serve(healthy)
        joined = "".join(frames)
        self.assertNotIn("live_prefix_invalidated", joined)
        self.assertIn('"finish_reason": "stop"', joined)
        self.assertIn('"usage"', joined)
        self.assertTrue(joined.rstrip().endswith("data: [DONE]"))


class TestDoneKindHonorsLiveInvalidation(unittest.TestCase):
    """RW-211/FU-212: событие kind == "done" не обходит run.live_invalidated: успех не
    выдаётся даже при rc=0, ни parser.finish, ни fallback final_text не доставляются."""

    def _execute_done(self, live_invalidated: bool) -> dict:
        run = server.Run.__new__(server.Run)
        run.q = queue.Queue()
        run.q.put(("done", (0, "final text")))
        run.got_event = True
        run.started = time.monotonic()
        run.last_progress = time.monotonic()
        run.err_box = []
        run.live_invalidated = live_invalidated
        run._last_error = "Run.q overflow" if live_invalidated else ""
        h = server.Handler.__new__(server.Handler)
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        h.connection = left
        return h._execute(run, None, True, None)

    def test_done_kind_with_live_invalidated_fails_closed(self):
        out = self._execute_done(True)
        self.assertEqual(out["state"], "live_invalidated")
        self.assertEqual(out["rc"], 1)
        self.assertEqual(out["text"], "")
        self.assertEqual(out["err"], "Run.q overflow")

    def test_done_kind_without_invalidation_stays_success(self):
        out = self._execute_done(False)
        self.assertEqual(out["state"], "done")
        self.assertEqual(out["rc"], 0)
        self.assertEqual(out["text"], "final text")


class TestRunQueueLiveOnlyLimit(unittest.TestCase):
    """RW-208/FU-212: RUN_QUEUE_MAXSIZE и overflow-инвалидация — только у живого
    SSE-хода (sse_writer задан); non-stream buffered очередь неограниченна и не теряет
    события даже при маленьком RUN_QUEUE_MAXSIZE."""

    PLAN = {"path": "ephemeral", "sid": "", "droid_real": 0}

    def _run(self, sse_writer, maxsize: int) -> server.Run:
        with (
            mock.patch.object(server.Run, "_work"),
            mock.patch.object(server, "RUN_QUEUE_MAXSIZE", maxsize),
        ):
            return server.Run(dict(self.PLAN), None, False, sse_writer)

    def test_non_stream_queue_is_unbounded_and_never_drops(self):
        run = self._run(None, 4)
        self.assertEqual(run.q.maxsize, 0)
        for index in range(1500):
            self.assertTrue(run._publish(("text", f"x{index}")))
        self.assertFalse(run.live_invalidated)
        self.assertEqual(run.q.qsize(), 1500)
        self.assertEqual(run._last_error, "")

    def test_live_queue_still_bounded_with_overflow_signal(self):
        run = self._run(lambda *args: True, 4)
        self.assertEqual(run.q.maxsize, 4)
        for index in range(4):
            self.assertTrue(run._publish(("text", f"x{index}")))
        self.assertFalse(run.live_invalidated)
        self.assertFalse(run._publish(("text", "overflow")))
        self.assertTrue(run.live_invalidated)
        self.assertEqual(run._last_error, "Run.q overflow")
        self.assertEqual(run.q.qsize(), 4)


class TestNonStreamBurstBeyondQueueLimit(LiveStreamCase):
    """RW-208/FU-212: non-stream buffered ход с более чем 1024 отдельных terminal-событий
    возвращает полный контент без потерь и без live_invalidated (прежний контракт)."""

    def test_buffered_turn_beyond_1024_events_is_not_truncated(self):
        count = 1100
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": f"part-{index:04d}"}
                        for index in range(count)
                    ]
                }
            ]
        )
        status, body = self._post_json(dict(BODY, messages=[msg("hi")]), timeout=90)
        self.assertEqual(status, 200, body)
        self.assertEqual(
            body["choices"][0]["message"]["content"],
            "\n\n".join(f"part-{index:04d}" for index in range(count)),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Unit test module test_zen_surrogates.py."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from typing import cast
from unittest import mock

import server
from tests.serve_test_base import (
    BaseServeTest,
    FAKE_SERVE,
    MODEL,
    _deltas,
    _fake_result,
)


class TestZenSurrogates(BaseServeTest):


    def test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_in_sse_and_json(
        self,
    ) -> None:
        """Непарные суррогаты дают управляемый отказ; пара остаётся символом."""
        mapper = server._map_serve_event  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
        protocol_error = server.ServeProtocolError
        original_log = cast("Callable[[str], None]", getattr(server, "_log"))
        self._auto_mode()
        for surrogate in ("\ud800", "\udc00"):
            for field in ("reasoning", "text"):
                event: dict[str, object] = {
                    "type": f"session.{field}.delta",
                    "data": {"sessionID": "s", "delta": surrogate},
                }
                with self.assertRaises(protocol_error):
                    _ = mapper(event)
                for stream in (True, False):
                    with self.subTest(
                        surrogate=repr(surrogate), field=field, stream=stream
                    ):
                        _ = server.LOG_PATH.write_text("")
                        logged_exit = threading.Event()

                        def record_log(message: str) -> None:
                            """Сигнализировать после записи финализатором O-EXIT в файл."""
                            original_log(message)
                            if message.startswith("O-EXIT/v1 "):
                                logged_exit.set()

                        self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                        os.environ["OPENCODE_ZEN_BRIDGE_TRANSPORT"] = (
                            "serve" if field == "reasoning" else "auto"
                        )
                        fragment = """
            if not state["prompt_replied"].wait(5): return
            time.sleep(0.05)
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.FIELD.delta","data":{"sessionID":sid,"delta":SURROGATE}})
            time.sleep(0.2)
            return
""".replace("FIELD", field).replace("SURROGATE", repr(surrogate))
                        body = (
                            FAKE_SERVE.replace(
                                '            if "__native_pause__" in prompt:',
                                fragment
                                + '            if "__native_pause__" in prompt:',
                            )
                            .replace(
                                "json.dumps(obj, ensure_ascii=False)",
                                "json.dumps(obj, ensure_ascii=True)",
                            )
                            .replace(
                                "lock = threading.Lock()",
                                'lock = threading.Lock()\nstate["prompt_replied"] = threading.Event()',
                            )
                            .replace(
                                '            self.send_json(200, {"data": {"id": "msg1"}}); return',
                                '            self.send_json(200, {"data": {"id": "msg1"}}); state["prompt_replied"].set(); return',
                            )
                        )
                        _ = self.fake.write_text(body)
                        lease_cls = server._ServeLease  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
                        cleanup = lease_cls.cleanup
                        response_debug = ""
                        with (
                            mock.patch.object(server, "_log", side_effect=record_log),
                            mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                            mock.patch.object(
                                lease_cls, "cleanup", autospec=True, side_effect=cleanup
                            ) as cleaned,
                            mock.patch.object(server.Run, "execute") as legacy,
                            mock.patch.object(server, "_spawn_with_stdin") as spawn,
                        ):
                            if stream:
                                chunks, _ = self.bridge.post_stream_timed("x")
                                response_debug = repr(chunks)
                                self.assertTrue(
                                    any("error" in chunk for _, chunk in chunks), chunks
                                )
                            else:
                                status, reply = self.bridge.post_json(
                                    "x", with_tools=False
                                )
                                response_debug = repr(reply)
                                self.assertEqual(status, 502, reply)
                            self.assertTrue(logged_exit.wait(5), "Нет O-EXIT/v1")
                            cleaned.assert_called_once()
                            legacy.assert_not_called()
                            spawn.assert_not_called()
                        self.assertIn(
                            "exit_reason=invalid_serve_event",
                            server.LOG_PATH.read_text(),
                            response_debug,
                        )
        mapped: object = mapper(
            {
                "type": "session.text.delta",
                "data": {"sessionID": "s", "delta": "\ud83d\ude00"},
            }
        )
        self.assertEqual(mapped, ("text", {"sessionID": "s", "content": "😀"}))
        for field in ("name", "input", "text"):
            tool_data: dict[str, object] = {
                "sessionID": "s",
                "id": "c",
                field: "\ud800",
            }
            with self.assertRaises(protocol_error):
                _ = mapper({"type": "session.tool.called", "data": tool_data})
        fragment = """
            time.sleep(0.05)
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"delta":"\\ud83d\\ude00"}})
            emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":"\\ud83d\\ude00"}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            time.sleep(0.2)
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            ).replace(
                "json.dumps(obj, ensure_ascii=False)",
                "json.dumps(obj, ensure_ascii=True)",
            )
        )
        for stream in (True, False):
            if stream:
                chunks, _ = self.bridge.post_stream_timed("x")
                self.assertEqual(
                    "".join(t for _, t in _deltas(chunks, "content")), "😀"
                )
                self.assertIn(
                    "😀", "".join(t for _, t in _deltas(chunks, "reasoning_content"))
                )
            else:
                status, reply = self.bridge.post_json("x", with_tools=False)
                self.assertEqual(status, 200, reply)
                self.assertIn("😀", json.dumps(reply, ensure_ascii=False))
        for stream in (True, False):
            self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
            calls, patcher = self._patched_attempts(
                [
                    lambda _args: _fake_result(
                        exit_reason="invalid_serve_event", delivered=False
                    )
                ]
            )
            _ = self.fake.write_text(FAKE_SERVE)
            with (
                patcher,
                mock.patch.object(
                    server.Run,
                    "execute",
                    return_value={
                        "text": "резерв",
                        "reasoning": "",
                        "usage": {},
                        "state": "ok",
                        "rc": 0,
                    },
                ) as legacy,
                mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
            ):
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    self.assertIn(
                        "Поздний ответ", json.dumps(chunks, ensure_ascii=False)
                    )
                else:
                    status, _ = self.bridge.post_json("x", with_tools=False)
                    self.assertEqual(status, 200)
                    legacy.assert_called_once()
            self.assertEqual(len(calls), 1)
    def test_serve_long_tool_not_cut_by_idle(self) -> None:
        """RW-003: tool, исполняющийся дольше Idle без токенов, не обрывает serve-попытку."""
        self._auto_mode()
        fragment = """
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"Думаю"}})
            emit({"type":"session.tool.input.started","data":{"sessionID":sid,"assistantMessageID":"m1","id":"lt1","name":"bash"}})
            time.sleep(1.2)
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"lt1","name":"bash","input":{"command":"pwd"}}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            time.sleep(0.2)
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        env = {
            "BRIDGE_ZEN_TIMEOUT_MODELS": MODEL,
            "BRIDGE_ZEN_LARGE_PROMPT_BYTES": "8",
            "BRIDGE_ZEN_TTFT_TIMEOUT_S": "5",
            "BRIDGE_ZEN_IDLE_TIMEOUT_S": "0.4",
            "BRIDGE_ZEN_TOTAL_TIMEOUT_S": "20",
        }
        with (
            mock.patch.dict(os.environ, env),
            mock.patch.object(server.Run, "execute") as legacy,
            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
        ):
            status, body = self.bridge.post_json("длинный запрос с tool")
            self.assertEqual(status, 200, body)
            self.assertIn("tool_calls", json.dumps(body, ensure_ascii=False))
            legacy.assert_not_called()

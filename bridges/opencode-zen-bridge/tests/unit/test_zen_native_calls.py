"""Unit test module test_zen_native_calls.py."""

from __future__ import annotations

import json
import os
from typing import cast
from unittest import mock

import server
from tests.serve_test_base import (
    BaseServeTest,
    FAKE_SERVE,
    MODEL,
    _as_obj_dict,
    _fake_result,
    _tool_names,
)


class TestZenNativeCalls(BaseServeTest):


    def test_serve_tool_without_reasoning_not_cut_by_ttft(self) -> None:
        """RW-001: модель сразу вызывает tool без reasoning/text; TTFT не обрывает генерацию аргументов."""
        self._auto_mode()
        fragment = """
            emit({"type":"session.tool.input.started","data":{"sessionID":sid,"assistantMessageID":"m1","id":"tt1","name":"bash"}})
            time.sleep(1.0)
            emit({"type":"session.tool.input.delta","data":{"sessionID":sid,"assistantMessageID":"m1","id":"tt1","delta":"{}"}})
            time.sleep(1.0)
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"tt1","name":"bash","input":{"command":"pwd"}}})
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
            "BRIDGE_ZEN_TTFT_TIMEOUT_S": "0.4",
            "BRIDGE_ZEN_IDLE_TIMEOUT_S": "0.4",
            "BRIDGE_ZEN_TOTAL_TIMEOUT_S": "20",
        }
        with (
            mock.patch.dict(os.environ, env),
            mock.patch.object(server.Run, "execute") as legacy,
            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
        ):
            status, body = self.bridge.post_json("длинный запрос с tool без reasoning")
            self.assertEqual(status, 200, body)
            self.assertIn("tool_calls", json.dumps(body, ensure_ascii=False))
            legacy.assert_not_called()
    def test_c8_rw002_pre_delivery_surrogate_falls_back_to_run(self) -> None:
        """Битое событие до execution и заголовков prompt допускает резервный run."""
        self._auto_mode()
        for stream, field, surrogate in (
            (True, "reasoning", "\ud800"),
            (False, "text", "\udc00"),
        ):
            self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
            fragment = """
            emit({"type":"session.FIELD.delta","data":{"sessionID":sid,"delta":SURROGATE}})
            return
""".replace("FIELD", field).replace("SURROGATE", repr(surrogate))
            fake = (
                FAKE_SERVE.replace(
                    '            if "__native_pause__" in prompt:',
                    fragment + '            if "__native_pause__" in prompt:',
                )
                .replace(
                    "json.dumps(obj, ensure_ascii=False)",
                    "json.dumps(obj, ensure_ascii=True)",
                )
                .replace(
                    '            state["prompt"] = prompt_text\n',
                    '            state["prompt"] = prompt_text\n            time.sleep(5)\n',
                )
            )
            _ = self.fake.write_text(fake)
            with (
                mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                mock.patch.object(
                    server,
                    "_serve_one_attempt",
                    wraps=server._serve_one_attempt,  # pyright: ignore[reportPrivateUsage] — причина: проверяется реальная попытка serve до барьера
                ) as attempt,
            ):
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    output = json.dumps(chunks, ensure_ascii=False)
                else:
                    status, reply = self.bridge.post_json("x", with_tools=False)
                    self.assertEqual(status, 200, reply)
                    output = json.dumps(reply, ensure_ascii=False)
                self.assertIn("Поздний ответ", output)
                attempt.assert_called_once()
            self.assertIn("transport=run", server.LOG_PATH.read_text())
    def test_c8_rw003_request_deadline_timeout_is_neutral_for_circuit_breaker(
        self,
    ) -> None:
        """Локальный дедлайн нейтрален, фазовые watchdog учитываются breaker."""
        self._auto_mode()
        for stream in (True, False):
            for reason in (
                "startup",
                "timeout",
                "first_token_timeout",
                "stall_timeout",
            ):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
                breaker = self.bridge.httpd.resilience.breaker
                for _ in range(2):
                    calls, patcher = self._patched_attempts(
                        [lambda _args: _fake_result(exit_reason=reason, delivered=True)]
                    )
                    if reason == "startup":
                        patcher = mock.patch.object(
                            server,
                            "_spawn_serve",
                            side_effect=server.ServeStartupDeadlineExceeded("deadline"),
                        )
                    with (
                        patcher,
                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                        mock.patch.object(server.Run, "execute") as legacy,
                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
                    ):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("x")
                            self.assertTrue(
                                any("error" in chunk for _, chunk in chunks), chunks
                            )
                        else:
                            status, reply = self.bridge.post_json("x", with_tools=False)
                            self.assertIn(status, (502, 504), reply)
                        legacy.assert_not_called()
                        spawn.assert_not_called()
                    if reason != "startup":
                        self.assertEqual(len(calls), 1)
                self.assertEqual(
                    breaker._failures,  # pyright: ignore[reportPrivateUsage] — причина: проверяется точное число отказов breaker
                    0 if reason in ("startup", "timeout") else 2,
                )
                self.assertEqual(breaker.state, "CLOSED")
    def test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded(
        self,
    ) -> None:
        """Все вызовы закрываемого шага сохранены один раз, следующий шаг исключён."""
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            for cid, mid, command in [("c1","m1","pwd"),("c2","m1","ls"),("c2","m1","ls"),("foreign","m2","wrong")]:
                if cid == "c2": time.sleep(0.22)
                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":mid,"id":cid,"name":"bash","input":{"command":command}}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":123,"output":45,"reasoning":6,"cache":{"read":10}}}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m2","id":"c3","name":"bash","input":{"command":"wrong"}}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        for stream in (True, False):
            with self.subTest(stream=stream):
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    self.assertEqual(_tool_names(chunks), ["bash", "bash"])
                    output = json.dumps(chunks, ensure_ascii=False)
                    usages = [
                        _as_obj_dict(c["usage"]) for _, c in chunks if "usage" in c
                    ]
                    usage = usages[-1]
                else:
                    status, reply = self.bridge.post_json("x")
                    self.assertEqual(status, 200, reply)
                    output = json.dumps(reply, ensure_ascii=False)
                    choices = cast("list[object]", reply["choices"])
                    message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
                    self.assertEqual(
                        len(cast("list[object]", message["tool_calls"])), 2
                    )
                    usage = _as_obj_dict(reply["usage"])
                self.assertIn("pwd", output)
                self.assertIn("ls", output)
                self.assertNotIn("wrong", output)
                self.assertEqual(usage["prompt_tokens"], 123)
                self.assertEqual(usage["completion_tokens"], 45)
                self.assertEqual(
                    _as_obj_dict(usage["prompt_tokens_details"])["cached_tokens"], 10
                )
                self.assertEqual(
                    _as_obj_dict(usage["completion_tokens_details"])[
                        "reasoning_tokens"
                    ],
                    6,
                )

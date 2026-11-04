"""Unit test module test_zen_security_matrix.py."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import cast
from unittest import mock

import server
from tests.serve_test_base import (
    BaseServeTest,
    FAKE_SERVE,
    _as_obj_dict,
    _callback,
    _fake_result,
)


class TestZenSecurityMatrix(BaseServeTest):


    def test_c12_rw002_json_retry_preserves_partial_output_and_usage(self) -> None:
        """Все внутренние JSON retry сохраняют нормализованный вывод и токены."""
        for reason, marker in (
            (r, m)
            for r in ("stall_timeout", "prompt_status", "transient_error")
            for m in (
                "I was interrupted right before making tool calls.",
                "[opencode-zen-bridge: шаг модели оборвался]",
            )
        ):
            with self.subTest(reason=reason):
                self.bridge.httpd.resilience = type(self.bridge.httpd.resilience)()

                def first(args: tuple[object, ...]) -> dict[str, object]:
                    text = "начало " + marker + '<tool_call>{"name":"bash","arguments":'
                    _callback(args, 4)("мысль-1")
                    _callback(args, 5)(text)
                    return _fake_result(
                        reasonings=["мысль-1"],
                        texts=[text],
                        delivered=True,
                        usage={"input": 10, "output": 5, "cached": 0, "reasoning": 3},
                        exit_reason="stall_timeout"
                        if reason == "stall_timeout"
                        else "",
                        prompt_status=503 if reason == "prompt_status" else None,
                        error={"message": "interrupted", "status": 503}
                        if reason == "transient_error"
                        else None,
                        transient_error=reason == "transient_error",
                    )

                def second(args: tuple[object, ...]) -> dict[str, object]:
                    _callback(args, 4)("мысль-2")
                    _callback(args, 5)("начало продолжение")
                    return _fake_result(
                        reasonings=["мысль-2"],
                        texts=["начало продолжение"],
                        terminal="succeeded",
                        usage={"input": 12, "output": 8, "cached": 0, "reasoning": 4},
                    )

                calls, patcher = self._patched_attempts([first, second])
                with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
                    status, body = self.bridge.post_json("x")
                self.assertEqual(status, 200, body)
                self.assertEqual(len(calls), 2)
                choices = cast("list[dict[str, object]]", body["choices"])
                message = _as_obj_dict(choices[0]["message"])
                self.assertEqual(message["reasoning_content"], "мысль-1мысль-2")
                self.assertEqual(message["content"], "начало продолжение")
                self.assertNotIn("tool_calls", message)
                usage = _as_obj_dict(body["usage"])
                self.assertEqual(
                    (usage["prompt_tokens"], usage["completion_tokens"]), (22, 13)
                )
                self.assertEqual(
                    _as_obj_dict(usage["completion_tokens_details"])[
                        "reasoning_tokens"
                    ],
                    7,
                )
    def test_c12_rw004_unmapped_exhaustion_returns_diagnostic_json(self) -> None:
        """JSON serve совпадает с legacy при исчерпании unmapped без текста."""

        def unmapped(args: tuple[object, ...]) -> dict[str, object]:
            native: dict[str, object] = {
                "type": "tool_use",
                "part": {"id": "c1", "tool": "missing", "input": {}},
            }
            cast("Callable[[dict[str, object]], None]", args[6])(native)
            return _fake_result(
                native_calls=[native], terminal="tool_calls", delivered=True
            )

        calls, patcher = self._patched_attempts([unmapped] * 5)
        with (
            patcher,
            mock.patch.object(server, "NATIVE_RETRY_LIMIT", 1),
            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
        ):
            status, body = self.bridge.post_json("x")
        self.assertEqual(status, 200, body)
        self.assertEqual(len(calls), 2)
        choices = cast("list[dict[str, object]]", body["choices"])
        self.assertEqual(choices[0]["finish_reason"], "stop")
        self.assertEqual(
            _as_obj_dict(choices[0]["message"])["content"],
            "[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент (missing); повторы исчерпаны]",
        )
    def test_c12_rw004_unmapped_exhaustion_transport_matrix(self) -> None:
        """Локальный лимит, общий spawn cap и Retry Budget одинаковы в четырёх путях."""
        fragment = """
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"missing","input":{}}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
            return
"""
        legacy = """#!/usr/bin/env python3
import json,sys
sys.stdin.read()
print(json.dumps({"type":"tool_use","part":{"tool":"missing","state":{"status":"completed","input":{}}}}),flush=True)
print(json.dumps({"type":"step_finish","part":{"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}}),flush=True)
"""
        expected = (
            "[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент (missing); повторы исчерпаны]",
            "stop",
        )
        for budget in ("local", "spawn", "retry"):
            for transport in ("serve", "run"):
                for stream in (False, True):
                    with self.subTest(
                        budget=budget, transport=transport, stream=stream
                    ):
                        self.bridge.httpd.resilience = type(
                            self.bridge.httpd.resilience
                        )()
                        source = (
                            legacy
                            if transport == "run"
                            else FAKE_SERVE.replace(
                                '            if "__native_pause__" in prompt:',
                                fragment
                                + '            if "__native_pause__" in prompt:',
                            )
                        )
                        _ = self.fake.write_text(source)
                        attempts_type = cast(
                            "type[object]", getattr(server, "_RequestAttempts")
                        )
                        allow_retry = cast(
                            "Callable[..., bool]", getattr(attempts_type, "allow_retry")
                        )

                        def retry(
                            owner: object, *args: object, **kwargs: object
                        ) -> bool:
                            return (
                                False
                                if budget == "retry"
                                else allow_retry(owner, *args, **kwargs)
                            )

                        with (
                            mock.patch.dict(
                                os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": transport}
                            ),
                            mock.patch.object(
                                server,
                                "NATIVE_RETRY_LIMIT",
                                0 if budget == "local" else 2,
                            ),
                            mock.patch.object(
                                server,
                                "MAX_TOTAL_SPAWNS",
                                1 if budget == "spawn" else 3,
                            ),
                            mock.patch.object(attempts_type, "allow_retry", retry),
                            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                        ):
                            content, finish = self._c6_response(stream)
                            self.assertEqual((content.strip(), finish), expected)

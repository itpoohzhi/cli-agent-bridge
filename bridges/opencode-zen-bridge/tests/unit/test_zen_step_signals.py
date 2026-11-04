"""Unit test module test_zen_step_signals.py."""

from __future__ import annotations

import json
from typing import cast
from unittest import mock

import server
from tests.serve_test_base import (
    BaseServeTest,
    FAKE_SERVE,
    _as_obj_dict,
    _deltas,
    _tool_names,
)


class TestZenStepSignals(BaseServeTest):


    def test_c10_rw001_drain_error_classification_preserved(self) -> None:
        """RW-001 цикл 10: ошибка в дренаже — 401 без повтора, 429 с повтором serve."""
        counter = self.tmp / "c10-drain-error-count"
        for code, with_step_ended in ((401, True), (429, False)):
            fragment = (
                (
                    """
            counter = Path(COUNTER)
            n = int(counter.read_text()) if counter.exists() else 0
            counter.write_text(str(n + 1))
            if n == 0:
                emit({"type":"session.execution.started","data":{"sessionID":sid}})
                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"AAA"}}})
                emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"message":"boom","status":STATUS}}})
"""
                    + (
                        '                emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})\n'
                        if with_step_ended
                        else ""
                    )
                    + """                return
"""
                )
                .replace("COUNTER", repr(str(counter)))
                .replace("STATUS", str(code))
            )
            _ = self.fake.write_text(
                FAKE_SERVE.replace(
                    '            if "__native_pause__" in prompt:',
                    fragment + '            if "__native_pause__" in prompt:',
                )
            )
            for stream in (True, False):
                with self.subTest(code=code, stream=stream):
                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                    counter.unlink(missing_ok=True)
                    with (
                        mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                    ):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("x")
                            output = json.dumps(chunks, ensure_ascii=False)
                            if code == 401:
                                self.assertTrue(
                                    any("error" in c for _, c in chunks), chunks
                                )
                            else:
                                self.assertIn("Ответ", output)
                            self.assertNotIn("AAA", output)
                        else:
                            status, reply = self.bridge.post_json("x")
                            output = json.dumps(reply, ensure_ascii=False)
                            if code == 401:
                                self.assertEqual(status, 502, reply)
                            else:
                                self.assertEqual(status, 200, reply)
                                self.assertIn("Ответ", output)
                            self.assertNotIn("AAA", output)
                    self.assertEqual(counter.read_text(), "1" if code == 401 else "2")
    def test_c10_rw002_unconfirmed_tool_not_published_retry_b_only(self) -> None:
        """RW-002 цикл 10: EOF без step.ended не публикует A; повтор публикует только B."""
        counter = self.tmp / "c10-rw002-count"
        fragment = """
            counter = Path(COUNTER)
            n = int(counter.read_text()) if counter.exists() else 0
            counter.write_text(str(n + 1))
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            if n == 0:
                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"cA","name":"bash","input":{"command":"AAA"}}})
                return
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"cB","name":"bash","input":{"command":"BBB"}}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":5,"output":3,"reasoning":1,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            return
""".replace("COUNTER", repr(str(counter)))
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        for stream in (True, False):
            with self.subTest(stream=stream):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                counter.unlink(missing_ok=True)
                with (
                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 2),
                    mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                ):
                    if stream:
                        chunks, _ = self.bridge.post_stream_timed("x")
                        output = json.dumps(chunks, ensure_ascii=False)
                        self.assertEqual(_tool_names(chunks), ["bash"])
                    else:
                        status, reply = self.bridge.post_json("x")
                        self.assertEqual(status, 200, reply)
                        output = json.dumps(reply, ensure_ascii=False)
                        choices = cast("list[object]", reply["choices"])
                        message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
                        self.assertEqual(
                            len(cast("list[object]", message["tool_calls"])), 1
                        )
                self.assertIn("BBB", output)
                self.assertNotIn("AAA", output)
                self.assertEqual(counter.read_text(), "2")
    def test_c10_rw003_reasoning_markers_preserved_text_clean(self) -> None:
        """RW-003 цикл 10: оба маркера в reasoning побайтово (целые и split), content чист."""
        marker1 = "I was interrupted right before making tool calls."
        marker2 = (
            "The previous response was interrupted. Continue from where you left off "
            "without repeating completed content."
        )
        cut = 40
        fragment = (
            """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":M1}})
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":M2A}})
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":M2B}})
            emit({"type":"session.text.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":TA}})
            emit({"type":"session.text.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":TB}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":5,"output":3,"reasoning":1,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            return
""".replace("M1", repr(marker1))
            .replace("M2A", repr(marker2[:cut]))
            .replace("M2B", repr(marker2[cut:]))
            .replace("TA", repr("Ответ " + marker1[:20]))
            .replace("TB", repr(marker1[20:] + " хвост"))
        )
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        for stream in (True, False):
            with self.subTest(stream=stream):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                with mock.patch.object(server, "STEP_RECOVERY_ENABLED", False):
                    if stream:
                        chunks, _ = self.bridge.post_stream_timed("x")
                        reasoning = "".join(
                            t
                            for _, t in _deltas(chunks, "reasoning_content")
                            if not t.lstrip("\n").startswith("[мост]")
                        )
                        content = "".join(t for _, t in _deltas(chunks, "content"))
                    else:
                        status, reply = self.bridge.post_json("x", with_tools=True)
                        self.assertEqual(status, 200, reply)
                        choices = cast("list[object]", reply["choices"])
                        message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
                        reasoning_obj: object = message.get("reasoning_content")
                        reasoning = (
                            reasoning_obj if isinstance(reasoning_obj, str) else ""
                        )
                        content_obj: object = message.get("content")
                        content = content_obj if isinstance(content_obj, str) else ""
                self.assertEqual(reasoning, marker1 + marker2)
                self.assertNotIn("interrupted", content)
                self.assertIn("Ответ", content)
                self.assertIn("хвост", content)

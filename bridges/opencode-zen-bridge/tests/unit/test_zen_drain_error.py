"""Unit test module test_zen_drain_error.py."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import cast
from unittest import mock

import server
from tests.serve_test_base import (
    BaseServeTest,
    FAKE_SERVE,
    LEGACY_FAKE,
    _as_obj_dict,
    _deltas,
    _tool_names,
)


class TestZenDrainError(BaseServeTest):



    def test_c11_rw001_drain_text_delivered_once_with_native_tool(self) -> None:
        """RW-001: хвост в дренаже доставляется один раз вместе с native tool."""
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"pwd"}}})
            emit({"type":"session.text.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"хвост"}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
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
                    content = "".join(t for _, t in _deltas(chunks, "content"))
                    self.assertEqual(_tool_names(chunks), ["bash"])
                    finishes = [
                        _as_obj_dict(cast("list[object]", c["choices"])[0]).get(
                            "finish_reason"
                        )
                        for _, c in chunks
                        if c.get("choices")
                    ]
                    self.assertIn("tool_calls", finishes)
                else:
                    status, reply = self.bridge.post_json("x")
                    self.assertEqual(status, 200, reply)
                    choice = _as_obj_dict(cast("list[object]", reply["choices"])[0])
                    message = _as_obj_dict(choice["message"])
                    content = str(message.get("content") or "")
                    self.assertEqual(
                        len(cast("list[object]", message["tool_calls"])), 1
                    )
                    self.assertEqual(choice["finish_reason"], "tool_calls")
                self.assertEqual(content, "хвост")
    def test_c11_rw005_completed_text_preserves_reasoning_without_retry(self) -> None:
        """RW-005: serve/run SSE/JSON сохраняют reasoning и завершают за одну попытку."""
        marker = "I was interrupted right before making tool calls."
        thought = "Начало " + marker + " Конец\n"
        serve_body = (
            FAKE_SERVE.replace('f"Мысль{i} "', repr(thought))
            .replace("range(5)", "range(1)")
            .replace('"Ответ\\n"', '"Привет!"')
        )
        legacy_body = LEGACY_FAKE.replace('"Simple greeting."', repr(thought))
        for transport in ("serve", "run"):
            _ = self.fake.write_text(
                serve_body if transport == "serve" else legacy_body
            )
            for stream in (True, False):
                with (
                    self.subTest(transport=transport, stream=stream),
                    mock.patch.dict(
                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": transport}
                    ),
                    mock.patch.object(server, "STEP_RECOVERY_ENABLED", True),
                    mock.patch.object(
                        server,
                        "_serve_one_attempt",
                        wraps=server._serve_one_attempt,  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
                    ) as attempt,
                    mock.patch.object(
                        subprocess,
                        "Popen",
                        wraps=subprocess.Popen,
                    ) as spawned,
                ):
                    if stream:
                        chunks, _ = self.bridge.post_stream_timed(
                            "x", tool_choice="auto"
                        )
                        reasoning = "".join(
                            t
                            for _, t in _deltas(chunks, "reasoning_content")
                            if not t.lstrip("\n").startswith("[мост]")
                        )
                        content = "".join(t for _, t in _deltas(chunks, "content"))
                    else:
                        status, reply = self.bridge.post_json("x", tool_choice="auto")
                        self.assertEqual(status, 200, reply)
                        message = _as_obj_dict(
                            _as_obj_dict(cast("list[object]", reply["choices"])[0])[
                                "message"
                            ]
                        )
                        reasoning = str(message.get("reasoning_content") or "")
                        content = str(message.get("content") or "")
                    self.assertIn("Привет!", content)
                    self.assertEqual(reasoning.encode(), thought.encode())
                    if transport == "serve":
                        self.assertEqual(attempt.call_count, 1)
                    else:
                        runs = [c for c in spawned.call_args_list if "run" in c.args[0]]
                        self.assertEqual(len(runs), 1)
    def test_c10_rw001_drain_permission_reject_continues_and_reasoning_delivered(
        self,
    ) -> None:
        """RW-001 цикл 10: permission в дренаже — reject без interrupt, reasoning доставлен."""
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"pwd"}}})
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"Думаю в дренаже"}})
            emit({"type":"permission.asked","data":{"id":"per1","sessionID":sid,"action":"bash","resources":["*"]}})
            time.sleep(0.5)
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":" perm=" + ("rejected" if state["rejected"] else "pending") + " interrupted=" + ("yes" if state["interrupted"] else "no")}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":11,"output":7,"reasoning":2,"cache":{"read":3}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
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
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                if stream:
                    chunks, _ = self.bridge.post_stream_timed("x")
                    self.assertFalse(any("error" in c for _, c in chunks), chunks)
                    self.assertEqual(_tool_names(chunks), ["bash"])
                    reasoning = "".join(
                        t for _, t in _deltas(chunks, "reasoning_content")
                    )
                    usages = [
                        _as_obj_dict(c["usage"]) for _, c in chunks if "usage" in c
                    ]
                    usage = usages[-1]
                else:
                    status, reply = self.bridge.post_json("x")
                    self.assertEqual(status, 200, reply)
                    choices = cast("list[object]", reply["choices"])
                    message = _as_obj_dict(_as_obj_dict(choices[0])["message"])
                    self.assertEqual(
                        len(cast("list[object]", message["tool_calls"])), 1
                    )
                    reasoning_obj: object = message.get("reasoning_content")
                    reasoning = reasoning_obj if isinstance(reasoning_obj, str) else ""
                    usage = _as_obj_dict(reply["usage"])
                self.assertIn("Думаю в дренаже", reasoning)
                self.assertIn("perm=rejected", reasoning)
                self.assertIn("interrupted=no", reasoning)
                self.assertEqual(usage["prompt_tokens"], 11)
                self.assertEqual(usage["completion_tokens"], 7)
    def test_c10_rw001_drain_form_created_fails_closed_without_tool(self) -> None:
        """RW-001 цикл 10: form.created своей сессии в дренаже — cancel+interrupt, без tool."""
        record = self.tmp / "rec-c10-form.json"
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"c1","name":"bash","input":{"command":"pwd"}}})
            emit({"type":"form.created","data":{"form":{"id":"form1","sessionID":sid}}})
            time.sleep(0.5)
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":11,"output":7,"reasoning":2,"cache":{"read":3}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
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
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимые защиты сценария
                control = Path(str(record) + ".control")
                control.unlink(missing_ok=True)
                record.unlink(missing_ok=True)
                prompt = f"__record:{record}__ заполни"
                if stream:
                    chunks, _ = self.bridge.post_stream_timed(prompt)
                    self.assertTrue(any("error" in c for _, c in chunks), chunks)
                    self.assertEqual(_tool_names(chunks), [])
                    self.assertNotIn(
                        '"finish_reason": "tool_calls"',
                        json.dumps(chunks, ensure_ascii=False),
                    )
                else:
                    status, reply = self.bridge.post_json(prompt)
                    self.assertEqual(status, 502, reply)
                    self.assertNotIn("tool_calls", json.dumps(reply))
                self.assertTrue(control.exists(), "FakeServe не получил cancel")
                control_text = control.read_text("utf-8")
                self.assertIn("cancelled", control_text)
                self.assertIn("interrupt", control_text)

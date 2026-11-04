"""Unit test module test_zen_rework_bounds.py."""

from __future__ import annotations

import json
import shutil
import os
import socket
import threading
import time
from pathlib import Path
from typing import cast
from unittest import mock

import server
from tests.serve_test_base import (
    BaseServeTest,
    FAKE_SERVE,
    MODEL,
    _as_obj_dict,
    _deltas,
    _tool_names,
)


class TestZenReworkBounds(BaseServeTest):


    def test_c10_rw005_slow_client_bounded_cleanup_and_slot_released(self) -> None:
        """RW-005 цикл 10: клиент не читает после заголовков — ограниченный финиш и cleanup."""
        record = self.tmp / "c10-slow-record.json"
        fragment = """
            emit({"type":"session.execution.started","data":{"sessionID":sid}})
            for _i in range(160):
                emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"x" * 65536}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":5,"output":3,"reasoning":1,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        payload: dict[str, object] = {
            "model": MODEL,
            "stream": True,
            "messages": [
                {"role": "user", "content": f"__record:{record}__ большой вывод"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "bash",
                        "description": "x",
                        "parameters": {
                            "type": "object",
                            "properties": {"command": {"type": "string"}},
                            "required": ["command"],
                        },
                    },
                }
            ],
        }
        body = json.dumps(payload).encode()
        request = (
            b"POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            + f"Authorization: Bearer {server.AUTH_KEY}\r\n".encode()
            + b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        client = socket.socket()
        try:
            client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            client.settimeout(10)
            client.connect(("127.0.0.1", self.bridge.port))
            with mock.patch.object(
                server, "_DOWNSTREAM_WRITE_TIMEOUT_S", 0.5, create=True
            ):
                client.sendall(request)
                received = b""
                while b"\r\n\r\n" not in received:
                    chunk = client.recv(4096)
                    self.assertTrue(chunk, "сервер не прислал заголовки")
                    received += chunk
                self.assertIn(b"200", received.split(b"\r\n", 1)[0])
                started = time.monotonic()
                slots = self.bridge.httpd.resilience.slots
                while time.monotonic() - started < 20.0:
                    if slots.in_use == 0 and record.exists():
                        break
                    time.sleep(0.05)
                elapsed = time.monotonic() - started
                self.assertEqual(slots.in_use, 0, "bulkhead-слот не возвращён")
                self.assertLess(elapsed, 20.0)
                self.assertTrue(record.exists(), "FakeServe не записал record")
                record_obj: object = json.loads(record.read_text())  # pyright: ignore[reportAny] — причина: record FakeServe — динамический JSON
                pgid_obj: object = _as_obj_dict(record_obj).get("pgid")
                self.assertIsInstance(pgid_obj, int)
                pgid = cast(int, pgid_obj)
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline:
                    try:
                        os.killpg(pgid, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.05)
                else:
                    self.fail("группа процессов serve пережила downstream-таймаут")
                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))
        finally:
            client.close()
    def test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation(
        self,
    ) -> None:
        """После резерва токена отмена и дедлайн запрещают legacy spawn и возвращают резерв."""
        for stream in (True, False):
            for cancel in (True, False):
                log_before = (
                    server.LOG_PATH.read_text() if server.LOG_PATH.exists() else ""
                )
                exit_logged = threading.Event()
                original_log = server._log  # pyright: ignore[reportPrivateUsage] — причина: синхронизация с реальной записью O-EXIT

                def observe_log(message: str) -> None:
                    original_log(message)
                    if "O-EXIT/v1" in message:
                        exit_logged.set()

                gone = [False]
                limiter = self.bridge.httpd.resilience.spawn_limiter

                def reserve(*_args: object, **_kw: object) -> bool:
                    if cancel:
                        gone[0] = True
                    else:
                        time.sleep(0.08)
                    return True

                with (
                    mock.patch.object(server, "_log", side_effect=observe_log),
                    mock.patch.dict(
                        os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}
                    ),
                    mock.patch.object(server, "TIMEOUT_S", 0.05),
                    mock.patch.object(
                        server.Handler,
                        "_client_gone_check",
                        side_effect=lambda: gone[0],
                    ),
                    mock.patch.object(limiter, "acquire", side_effect=reserve),
                    mock.patch.object(
                        limiter, "refund", wraps=limiter.refund
                    ) as refund,
                    mock.patch.object(server, "_spawn_with_stdin") as spawn,
                ):
                    if stream:
                        _ = self.bridge.post_stream_timed("x")
                    else:
                        status, _ = self.bridge.post_json("x", with_tools=False)
                        self.assertIn(status, (502, 504))
                    self.assertTrue(exit_logged.wait(3.0), "O-EXIT не записан")
                    spawn.assert_not_called()
                    refund.assert_called_once()
                new_lines = server.LOG_PATH.read_text()[len(log_before) :].splitlines()
                exits = [line for line in new_lines if "O-EXIT/v1" in line]
                self.assertEqual(len(exits), 1, exits)
                self.assertIn(
                    "exit_reason=" + ("client_gone" if cancel else "timeout"), exits[0]
                )
                self.assertIn("total_spawns=0", exits[0])
                self.assertEqual(self.bridge.httpd.resilience.breaker._failures, 0)  # pyright: ignore[reportPrivateUsage] — причина: проверяется нейтральный timeout
                self.assertEqual(self.bridge.httpd.resilience.slots.in_use, 0)
                self.assertFalse(server._STARTUP_LOCK.locked())  # pyright: ignore[reportPrivateUsage] — причина: проверяется приватная граница serve и управление запуском
    def test_ac026_realtime_chunks_before_upstream_end(self) -> None:
        """AC-026: reasoning-чанки приходят, пока апстрим ещё идёт."""
        end_record = self.tmp / "upstream-ended"
        chunks, _elapsed = self.bridge.post_stream_timed(
            f"обычный запрос __end_record:{end_record}__"
        )
        reasoning = _deltas(chunks, "reasoning_content")
        model_reasoning = [
            (at, t) for at, t in reasoning if not t.lstrip("\n").startswith("[мост]")
        ]
        self.assertGreaterEqual(len(model_reasoning), 5, chunks)
        sent_raw = cast(object, json.loads(Path(str(end_record) + ".sent").read_text()))
        sent_times = [float(t) for t in cast("list[float]", sent_raw)]
        recv_times = [self.bridge.stream_started + at for at, _t in model_reasoning]
        self.assertEqual(len(sent_times), len(recv_times))
        for sent_t, recv_t in zip(sent_times, recv_times):
            self.assertGreaterEqual(recv_t - sent_t, 0.0)
            self.assertLess(recv_t - sent_t, 0.25)
        r_times = [at for at, _t in model_reasoning]
        c_times = [at for at, t in _deltas(chunks, "content") if t]
        self.assertTrue(c_times, chunks)
        self.assertLess(r_times[0], c_times[0])
        self.assertGreaterEqual(r_times[-1] - r_times[0], 0.15)
        self.assertLess(max(b - a for a, b in zip(r_times, r_times[1:])), 0.5)
        first_reasoning_t = model_reasoning[0][0]
        upstream_end_t = float(end_record.read_text()) - self.bridge.stream_started
        self.assertLess(first_reasoning_t, upstream_end_t)
        self.assertLess(model_reasoning[-1][0] - model_reasoning[0][0], 2.0)
        joined = "".join(t for _at, t in model_reasoning)
        self.assertEqual(joined, "Мысль0 Мысль1 Мысль2 Мысль3 Мысль4 ")
    def test_dynamic_config_switch_same_server(self) -> None:
        """Тот же Server: false -> run, true -> serve, битый JSON -> false."""
        reader = server._read_dynamic_config_enabled  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        self.assertTrue(reader())
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": False}), "utf-8")
        self.assertFalse(reader())
        _ = self.cfg.write_text("{broken", "utf-8")
        self.assertFalse(reader())
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": "yes"}), "utf-8")
        self.assertFalse(reader())
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
        self.assertTrue(reader())
    def test_serve_env_sanitized_all_branches(self) -> None:
        """_serve_env: :memory:, allowlist, без OPENCODE_BIN и секретов."""
        with mock.patch.dict(
            os.environ, {"SECRET_SENTINEL": "x", "MY_API_KEY": "y"}, clear=False
        ):
            env: dict[str, str] = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        try:
            self.assertEqual(env.get("OPENCODE_DB"), ":memory:")
            self.assertNotIn("OPENCODE_BIN", env)
            self.assertNotIn("SECRET_SENTINEL", env)
            self.assertNotIn("MY_API_KEY", env)
            self.assertTrue(env.get("OPENCODE_SERVER_PASSWORD"))
            self.assertTrue(env.get("XDG_STATE_HOME"))
            self.assertNotEqual(env.get("XDG_DATA_HOME"), env.get("XDG_STATE_HOME"))
        finally:
            shutil.rmtree(env["XDG_STATE_HOME"], ignore_errors=True)
    def test_tool_text_split_across_deltas(self) -> None:
        """ToolCallParser на разрезанных дельтах serve."""
        chunks, _elapsed = self.bridge.post_stream_timed("__tool_text__ вызов")
        self.assertEqual(_tool_names(chunks), ["bash"])
    def test_native_tool_and_permission_reject(self) -> None:
        """permission.asked -> reject, native tool -> DSH tool_call."""
        chunks, _elapsed = self.bridge.post_stream_timed("__native_tool__ сделай")
        self.assertIn("bash", _tool_names(chunks))
    def test_form_missing_title_cancels_without_step2(self) -> None:
        """form.created без title: cancel+interrupt до проверки схемы, без Step2."""
        record = self.tmp / "rec.json"
        chunks, _elapsed = self.bridge.post_stream_timed(
            f"__form_missing_title__ __record:{record}__ заполни"
        )
        content = "".join(t for _at, t in _deltas(chunks, "content"))
        self.assertNotIn("STEP2", content)
        control = Path(str(record) + ".control")
        self.assertTrue(control.exists(), "FakeServe не получил cancel")
        self.assertIn("cancelled", control.read_text("utf-8"))

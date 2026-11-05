"""Unit test module test_zen_drain_permission.py."""

from __future__ import annotations

import http.client
import json
import socket
import time
from typing import cast
from unittest import mock

import server
from tests.serve_test_base import (
    BaseServeTest,
    FAKE_SERVE,
    MODEL,
    _as_obj_dict,
    _tool_names,
)


class TestZenDrainPermission(BaseServeTest):


    def test_c9_rw001_idless_and_unconfirmed_native_step(self) -> None:
        """Без ID сохраняются оба вызова; EOF и окно без step.ended дают ошибку."""
        for scenario in ("idless", "inherited", "eof", "window"):
            fragment = """
            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"Думаю"}})
            emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"c1","name":"bash","input":{"command":"pwd"}}})
            time.sleep(0.22)
            if SCENARIO in ("idless", "inherited"):
                emit({"type":"session.tool.input.started","data":{"sessionID":sid,"id":"c2","name":"bash"}})
                emit({"type":"session.tool.input.ended","data":{"sessionID":sid,"id":"c2","text":'{"command":"ls"}'}})
                if SCENARIO == "idless":
                    emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"c2","name":"bash","input":{"command":"ls"}}})
                emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":123,"output":45,"reasoning":6,"cache":{"read":10}}}})
                emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m2","id":"c3","name":"bash","input":{"command":"wrong"}}})
            if SCENARIO == "window": time.sleep(2)
            return
""".replace("SCENARIO", repr(scenario))
            if scenario == "idless":
                fragment = fragment.replace(',"assistantMessageID":"m1"', "")
            _ = self.fake.write_text(
                FAKE_SERVE.replace(
                    '            if "__native_pause__" in prompt:',
                    fragment + '            if "__native_pause__" in prompt:',
                )
            )
            for stream in (True, False):
                with self.subTest(scenario=scenario, stream=stream):
                    self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: независимый breaker для каждого сценария
                    with mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1):
                        if stream:
                            chunks, _ = self.bridge.post_stream_timed("x")
                            output = json.dumps(chunks, ensure_ascii=False)
                            if scenario in ("eof", "window"):
                                self.assertTrue(
                                    any("error" in c for _, c in chunks), chunks
                                )
                                self.assertNotIn(
                                    '"finish_reason": "tool_calls"', output
                                )
                                self.assertIn(
                                    "exit_reason=invalid_serve_event",
                                    server.LOG_PATH.read_text(),
                                )
                                continue
                            self.assertEqual(_tool_names(chunks), ["bash", "bash"])
                            usage = [
                                _as_obj_dict(c["usage"])
                                for _, c in chunks
                                if "usage" in c
                            ][-1]
                        else:
                            status, reply = self.bridge.post_json("x")
                            if scenario in ("eof", "window"):
                                self.assertEqual(status, 502, reply)
                                self.assertIn(
                                    "exit_reason=invalid_serve_event",
                                    server.LOG_PATH.read_text(),
                                )
                                continue
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
                            _as_obj_dict(usage["prompt_tokens_details"])[
                                "cached_tokens"
                            ],
                            10,
                        )
                        self.assertEqual(
                            _as_obj_dict(usage["completion_tokens_details"])[
                                "reasoning_tokens"
                            ],
                            6,
                        )
    def test_c11_rw003_initial_writes_fail_closed(self) -> None:
        """RW-003: заголовки, role и таймер ограничены одной обёрткой записи."""
        locked_cls = server._LockedWfile  # pyright: ignore[reportPrivateUsage] — причина: инъекции на реальной границе downstream
        write = locked_cls.write
        mark = locked_cls._mark_client_gone  # pyright: ignore[reportPrivateUsage] — причина: проверяется сигнал ухода клиента
        for stage in (b"HTTP/", b'"role"', b'"reasoning_content"'):
            with self.subTest(stage=stage):
                self.bridge.httpd.resilience = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: изолированный bulkhead
                gone: list[bool] = []

                def mark_gone(locked: server._LockedWfile) -> None:  # pyright: ignore[reportPrivateUsage] — причина: spy ограниченной записи
                    mark(locked)
                    sock = locked._sock  # pyright: ignore[reportPrivateUsage] — причина: проверяется закрытие клиентского сокета
                    gone.append(
                        locked.client_gone
                        and (
                            sock is None
                            or bool(cast(object, getattr(sock, "_closed", False)))
                        )
                    )

                def write_failed(locked: server._LockedWfile, data: bytes) -> int:  # pyright: ignore[reportPrivateUsage] — причина: инъекция в ограниченную запись
                    if stage in data:
                        with mock.patch.object(
                            locked._inner,  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
                            "write",
                            side_effect=TimeoutError("blocked initial write"),
                        ):
                            return write(locked, data)
                    return write(locked, data)

                with (
                    mock.patch.object(
                        locked_cls, "write", autospec=True, side_effect=write_failed
                    ),
                    mock.patch.object(
                        locked_cls,
                        "_mark_client_gone",
                        autospec=True,
                        side_effect=mark_gone,
                    ),
                    mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 1.0),
                    mock.patch.object(server, "MAX_TOTAL_SPAWNS", 1),
                    mock.patch.object(
                        server,
                        "_spawn_serve",
                        wraps=server._spawn_serve,  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватную границу моста
                    ) as spawned,
                ):
                    try:
                        _ = self.bridge.post_stream_timed("__silent__", timeout=5.0)
                    except (OSError, http.client.HTTPException):
                        pass
                    cleanup_deadline = time.monotonic() + 6.0
                    while (
                        self.bridge.httpd.resilience.slots.in_use
                        and time.monotonic() < cleanup_deadline
                    ):
                        time.sleep(0.02)
                self.assertTrue(gone, stage)
                self.assertTrue(all(gone))
                self.assertEqual(self.bridge.httpd.resilience.slots.in_use, 0)
                if stage != b'"reasoning_content"':
                    spawned.assert_not_called()
                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))
    def test_c11_rw003_status_socket_timeout_before_model_token(self) -> None:
        """RW-003: полное окно клиента ограничивает status ещё до первого токена."""
        groups: list[int] = []
        lease_cls = server._ServeLease  # pyright: ignore[reportPrivateUsage] — причина: наблюдается реальная группа serve
        cleanup = lease_cls.cleanup

        def cleanup_group(lease: server._ServeLease) -> None:  # pyright: ignore[reportPrivateUsage] — причина: фиксируется PGID убираемой группы
            groups.append(lease.pgid)
            cleanup(lease)

        body = json.dumps(
            {
                "model": MODEL,
                "stream": True,
                "messages": [{"role": "user", "content": "__silent__"}],
            }
        ).encode()
        request = (
            b"POST /v1/chat/completions HTTP/1.1\r\nHost: localhost\r\n"
            + f"Authorization: Bearer {server.AUTH_KEY}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        client = socket.socket()
        try:
            client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
            client.settimeout(3.0)
            client.connect(("127.0.0.1", self.bridge.port))
            with (
                mock.patch.object(
                    server, "STATUS_INITIAL", "[мост] " + "x" * (8 * 1024 * 1024)
                ),
                mock.patch.object(
                    lease_cls, "cleanup", autospec=True, side_effect=cleanup_group
                ),
            ):
                started = time.monotonic()
                client.sendall(request)
                received = b""
                while not received.endswith(b"\r\n\r\n"):
                    received += client.recv(1)
                slots = self.bridge.httpd.resilience.slots
                while time.monotonic() - started < 15.0:
                    if groups and slots.in_use == 0:
                        break
                    time.sleep(0.02)
                self.assertTrue(groups)
                self.assertEqual(slots.in_use, 0)
                for pgid in groups:
                    self.assertFalse(server._pid_alive(-pgid))  # pyright: ignore[reportPrivateUsage] — причина: реальный оракул остановки группы
                self.assertGreaterEqual(time.monotonic() - started, 5.0)
                self.assertLess(time.monotonic() - started, 16.0)
        finally:
            client.close()

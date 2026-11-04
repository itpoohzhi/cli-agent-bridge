"""Unit test module test_zen_security_protocol.py."""

from __future__ import annotations

import http.client
import json
import socket
import threading
import time
from collections.abc import Callable, Mapping
from typing import cast
from unittest import mock

import server
from tests.serve_test_base import (
    BaseServeTest,
    FAKE_SERVE,
)


class TestZenSecurityProtocol(BaseServeTest):


    def test_c13_rw003_disconnect_during_active_drain_sse_json(self) -> None:
        """Отключение при потоке tool delta быстро останавливает drain и cleanup."""
        fragment = """
            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"first","name":"bash","input":{"command":"pwd"}}})
            for i in range(40):
                time.sleep(0.05)
                emit({"type":"session.tool.input.delta","data":{"sessionID":sid,"assistantMessageID":"m1","id":"next","delta":" "}})
            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{}}})
            return
"""
        _ = self.fake.write_text(
            FAKE_SERVE.replace(
                '            if "__native_pause__" in prompt:',
                fragment + '            if "__native_pause__" in prompt:',
            )
        )
        finish = cast("Callable[..., bool]", getattr(server, "_finish_serve_tool_step"))
        attempt = cast(
            "Callable[..., Mapping[str, object]]", getattr(server, "_serve_one_attempt")
        )
        lease = cast("type[object]", getattr(server, "_ServeLease"))
        cleanup = cast("Callable[..., None]", getattr(lease, "cleanup"))
        for stream in (False, True):
            with self.subTest(stream=stream):
                entered: list[float] = []
                published: list[dict[str, object]] = []
                disconnected: list[float] = []
                results: list[Mapping[str, object]] = []
                finished_at: list[float] = []
                finished = threading.Event()

                def draining(*args: object, **kwargs: object) -> bool:
                    entered.append(time.monotonic())
                    return finish(*args, **kwargs)

                def gone() -> bool:
                    value = bool(entered and time.monotonic() - entered[0] >= 0.10)
                    if value and not disconnected:
                        disconnected.append(time.monotonic())
                    return value

                def one_attempt(
                    *args: object, **kwargs: object
                ) -> Mapping[str, object]:
                    kwargs["is_client_gone"] = gone
                    argv = list(args)
                    argv[6] = published.append
                    result = attempt(*argv, **kwargs)
                    results.append(result)
                    finished_at.append(time.monotonic())
                    finished.set()
                    return result

                self.bridge.httpd.resilience = type(self.bridge.httpd.resilience)()
                self._auto_mode()
                with (
                    mock.patch.object(
                        server, "_finish_serve_tool_step", side_effect=draining
                    ),
                    mock.patch.object(
                        server, "_serve_one_attempt", side_effect=one_attempt
                    ),
                    mock.patch.object(
                        lease, "cleanup", autospec=True, side_effect=cleanup
                    ) as cleaned,
                    mock.patch.object(server.Run, "execute") as legacy,
                    mock.patch.object(server, "_STEP_DRAIN_WINDOW_S", 1.0),
                ):
                    if stream:
                        _ = self.bridge.post_stream_timed("x")
                    else:
                        with self.assertRaises(
                            (
                                http.client.RemoteDisconnected,
                                ConnectionError,
                                TimeoutError,
                                socket.timeout,
                            )
                        ):
                            _ = self.bridge.post_json("x", timeout=2.0)
                    self.assertTrue(finished.wait(3.0))
                    legacy.assert_not_called()
                self.assertEqual(len(results), 1)
                result = results[0]
                self.assertTrue(entered)
                self.assertEqual(result["exit_reason"], "client_gone", result)
                self.assertLess(finished_at[0] - entered[0], 6.0)
                self.assertFalse(published)
                self.assertFalse(result["native_calls"])
                cleaned.assert_called_once()
                self.assertFalse(list(server.LEASE_DIR.glob("lease-*.json")))
    def test_c13_rw001_protocol_errors_main_sse_json(self) -> None:
        """Протокольные ошибки control терминальны в основном цикле SSE/JSON."""
        self._c13_security_protocol_matrix(False)
    def test_c13_rw001_protocol_errors_drain_sse_json(self) -> None:
        """Cancel/reply и interrupt в дренаже не теряют security-классификацию."""
        self._c13_security_protocol_matrix(True)
    def test_c12_rw001_control_errors_are_terminal_main_sse_json(self) -> None:
        """Сбой любого security control завершает одну попытку без run/fallback."""
        self._auto_mode()
        http_call = cast(
            "Callable[..., tuple[int, dict[str, object]]]",
            getattr(server, "_serve_http"),
        )
        attempt = cast("Callable[..., object]", getattr(server, "_serve_one_attempt"))
        attempts_type = cast("type[object]", getattr(server, "_RequestAttempts"))
        original_note = cast(
            "Callable[..., None]", getattr(attempts_type, "note_spawn")
        )
        for stream in (False, True):
            for control in ("form", "permission"):
                for failed in ("first", "interrupt"):
                    for error_type in (
                        socket.timeout,
                        ConnectionResetError,
                        http.client.HTTPException,
                        server.ServeUnavailable,
                        None,
                    ):
                        with self.subTest(
                            stream=stream,
                            control=control,
                            failed=failed,
                            error=error_type,
                        ):
                            paths: list[str] = []
                            raised: list[str] = []
                            spawns: list[int] = []
                            self.bridge.httpd.resilience = type(
                                self.bridge.httpd.resilience
                            )()

                            def note_spawn(owner: object) -> None:
                                original_note(owner)
                                spawns.append(cast(int, getattr(owner, "total_spawns")))

                            def control_http(
                                *args: object, **kwargs: object
                            ) -> tuple[int, dict[str, object]]:
                                path = str(args[3])
                                if path.endswith(
                                    ("/reply", "/cancel", "/interrupt")
                                ) and not kwargs.get("skip_body"):
                                    paths.append(path)
                                    if (failed == "interrupt") == path.endswith(
                                        "/interrupt"
                                    ):
                                        if error_type is None:
                                            return 503, {}
                                        raise error_type("control rejected")
                                return http_call(*args, **kwargs)

                            def one_attempt(*args: object, **kwargs: object) -> object:
                                try:
                                    return attempt(*args, **kwargs)
                                except server.ServeSecurityError:
                                    raised.append("security_rejected")
                                    raise

                            with (
                                mock.patch.object(
                                    server, "_serve_http", side_effect=control_http
                                ),
                                mock.patch.object(
                                    server,
                                    "_serve_one_attempt",
                                    side_effect=one_attempt,
                                ),
                                mock.patch.object(
                                    attempts_type, "note_spawn", note_spawn
                                ),
                                mock.patch.object(server.Run, "execute") as legacy,
                                mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
                            ):
                                marker = (
                                    "__form_ok__"
                                    if control == "form"
                                    else "__permission__"
                                )
                                if stream:
                                    chunks, _ = self.bridge.post_stream_timed(marker)
                                    encoded = json.dumps(chunks)
                                else:
                                    status, body = self.bridge.post_json(marker)
                                    self.assertEqual(status, 502, body)
                                    encoded = json.dumps(body)
                                self.assertIn("serve security failure", encoded)
                                legacy.assert_not_called()
                            self.assertEqual(raised, ["security_rejected"])
                            self.assertEqual(spawns, [1])
                            self.assertTrue(
                                any(p.endswith("/interrupt") for p in paths), paths
                            )
    def test_c13_rw002_run_retry_reasoning_concat_no_synthetic_newlines(self) -> None:
        """Внутренний retry сохраняет точные байты reasoning до HTTP-ответа."""
        self._c13_run_retry_http(timings=False)
    def test_c13_rw004_run_retry_retains_first_timings_in_http_oexit(self) -> None:
        """Run и O-EXIT отражают первые 120/250 мс, а не второй retry."""
        self._c13_run_retry_http(timings=True)

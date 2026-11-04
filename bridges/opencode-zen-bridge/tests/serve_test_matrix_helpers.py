from __future__ import annotations

import json
import os
import threading
from typing import Any, Callable, cast
from unittest import mock

import server


def _assert_matrix_results(
    test_case: Any, raised: list[str], spawns: list[int], paths: list[str]
) -> None:
    test_case.assertEqual(raised, ["security_rejected"])
    test_case.assertEqual(spawns, [1])
    test_case.assertTrue(any(p.endswith("/interrupt") for p in paths), paths)


def _send_and_check_matrix_marker(
    test_case: Any, bridge: Any, stream: bool, control: str, legacy: Any
) -> None:
    marker = "__form_ok__" if control == "form" else "__permission__"
    if stream:
        chunks, _ = bridge.post_stream_timed(marker)
        encoded = json.dumps(chunks)
    else:
        status, body = bridge.post_json(marker)
        test_case.assertEqual(status, 502, body)
        encoded = json.dumps(body)
    test_case.assertIn("serve security failure", encoded)
    legacy.assert_not_called()


def _run_matrix_subcase(
    test_case: Any,
    bridge: Any,
    stream: bool,
    control: str,
    failed: str,
    error_type: type[Exception],
    drain: bool,
    http_call: Callable[..., tuple[int, dict[str, object]]],
    attempt: Callable[..., object],
    attempts_type: type[object],
    original_note: Callable[..., None],
) -> None:
    """Выполнить один сценарий матрицы безопасности и проверить отказ без фолбэка."""
    paths: list[str] = []
    raised: list[str] = []
    spawns: list[int] = []
    bridge.httpd.resilience = type(bridge.httpd.resilience)()

    def note_spawn(owner: object) -> None:
        original_note(owner)
        spawns.append(cast(int, getattr(owner, "total_spawns")))

    def control_http(*args: object, **kwargs: object) -> tuple[int, dict[str, object]]:
        path = str(args[3])
        if path.endswith(("/reply", "/cancel", "/interrupt")) and not kwargs.get("skip_body"):
            paths.append(path)
            if drain and control == "permission" and failed == "interrupt" and path.endswith("/reply"):
                return 503, {}
            if (failed == "interrupt") == path.endswith("/interrupt"):
                raise error_type("control rejected")
        return http_call(*args, **kwargs)

    def one_attempt(*args: object, **kwargs: object) -> object:
        try:
            return attempt(*args, **kwargs)
        except server.ServeSecurityError:
            raised.append("security_rejected")
            raise

    with (
        mock.patch.object(server, "_serve_http", side_effect=control_http),
        mock.patch.object(server, "_serve_one_attempt", side_effect=one_attempt),
        mock.patch.object(attempts_type, "note_spawn", note_spawn),
        mock.patch.object(server.Run, "execute") as legacy,
        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
    ):
        _send_and_check_matrix_marker(test_case, bridge, stream, control, legacy)
    _assert_matrix_results(test_case, raised, spawns, paths)


def execute_security_protocol_matrix(
    test_case: Any, drain: bool, fake: Any, bridge: Any, fake_serve: str
) -> None:
    """Сбой любого security control завершает одну попытку без run/fallback."""
    test_case._auto_mode()
    if drain:
        prefix = '            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"first","name":"bash","input":{"command":"pwd"}}})\n'
        _ = fake.write_text(
            fake_serve.replace(
                '            if "__native_pause__" in prompt:',
                prefix + '            if "__native_pause__" in prompt:',
            )
        )
    http_call = cast("Callable[..., tuple[int, dict[str, object]]]", getattr(server, "_serve_http"))
    attempt = cast("Callable[..., object]", getattr(server, "_serve_one_attempt"))
    attempts_type = cast("type[object]", getattr(server, "_RequestAttempts"))
    original_note = cast("Callable[..., None]", getattr(attempts_type, "note_spawn"))
    for stream in (False, True):
        for control in ("form", "permission"):
            for failed in ("first", "interrupt"):
                for error_type in (server.ServeProtocolError,):
                    with test_case.subTest(stream=stream, control=control, failed=failed, error=error_type):
                        _run_matrix_subcase(
                            test_case, bridge, stream, control, failed, error_type,
                            drain, http_call, attempt, attempts_type, original_note,
                        )


def _verify_retry_results(
    test_case: Any, body: dict[str, Any], status: int, counter: list[int],
    captured: list[dict[str, object]], logs: list[str], timings: bool, t0: float
) -> None:
    """Проверить результаты двух внутренних попыток и метрики TTFT."""
    test_case.assertEqual(status, 200, body)
    test_case.assertEqual(counter, [2])
    test_case.assertEqual(len(captured), 1)
    if timings:
        test_case.assertEqual(captured[0]["first_event_at"], t0 + 0.12)
        test_case.assertEqual(captured[0]["first_token_at"], t0 + 0.25)
        test_case.assertIn("first_event_ms=120 ", logs[-1])
        test_case.assertIn("ttft_ms=250 ", logs[-1])
    else:
        expected = "мысль-run-1мысль-run-2"
        test_case.assertEqual(captured[0]["reasoning"], expected)
        choices = cast("list[dict[str, object]]", body["choices"])
        message = cast("dict[str, object]", choices[0]["message"])
        test_case.assertEqual(message["reasoning_content"], expected)
        test_case.assertNotIn("\n\n", str(message["reasoning_content"]))


def execute_run_retry_http(test_case: Any, bridge: Any, *, timings: bool) -> None:
    """Пройти Run.execute и HTTP JSON с двумя внутренними попытками."""
    captured: list[dict[str, object]] = []
    logs: list[str] = []
    done = threading.Event()
    counter = [0]
    t0 = 1000.0
    new_exit = cast("Callable[[], dict[str, object]]", getattr(server, "_new_exit_state"))
    execute = server.Run.execute

    def exit_state() -> dict[str, object]:
        xs = new_exit()
        xs["t0"] = t0
        return xs

    def once(_runner: server.Run) -> dict[str, object]:
        index = counter[0]
        counter[0] += 1
        return {
            "state": "stall_timeout" if index == 0 else "ok",
            "rc": 0, "err": "",
            "text": "" if index == 0 else "ответ",
            "chunks": [] if index == 0 else ["ответ"],
            "reasoning": "мысль-run-1" if index == 0 else "мысль-run-2",
            "first_event_at": t0 + (0.12 if index == 0 else 1.50),
            "first_token_at": t0 + (0.25 if index == 0 else 1.80),
            "usage": {}, "native_calls": [],
        }

    def run(runner: server.Run) -> object:
        out = cast("dict[str, object]", execute(runner))
        captured.append(out)
        return out

    def log(message: str) -> None:
        if "O-EXIT/v1" in message:
            logs.append(message)
            done.set()

    with (
        mock.patch.dict(os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}),
        mock.patch.object(server, "_new_exit_state", side_effect=exit_state),
        mock.patch.object(server.Run, "_execute_once", once),
        mock.patch.object(server.Run, "execute", run),
        mock.patch.object(server, "_log", side_effect=log),
    ):
        status, body = bridge.post_json("x", with_tools=False)
        test_case.assertTrue(done.wait(1.0))
    _verify_retry_results(test_case, body, status, counter, captured, logs, timings, t0)

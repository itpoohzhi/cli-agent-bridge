"""Регрессии квот прокси и повторов транспорта opencode serve."""

from __future__ import annotations

import importlib.util
import io
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    path = Path(__file__).resolve().parents[1] / "bridges/opencode-zen-bridge/server.py"
    spec = importlib.util.spec_from_file_location("zen_quota_test_server", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    # Импорт моста добавляет собственные корни; восстанавливаем sys.path после теста.
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "DEFAULTWORKDIR", tmp_path)
    monkeypatch.setattr(module, "_log", Mock())
    monkeypatch.setattr(module, "_StartupGate", Mock())
    monkeypatch.setattr(module, "FAIL_RETRY_BACKOFF_S", 0)
    monkeypatch.setattr(module, "MAX_TOTAL_SPAWNS", 3)
    monkeypatch.setattr(module, "NATIVE_RETRY_LIMIT", 3)
    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_TRANSPORT", "serve")
    return module


def _handler(bridge: Any) -> Any:
    handler = object.__new__(bridge.Handler)
    handler.wfile = io.BytesIO()
    handler._client_gone_check = Mock(return_value=False)
    handler._send = Mock()
    return handler


def _attempts(bridge: Any, **kwargs: Any) -> Any:
    res = bridge._Resilience()
    res.spawn_limiter = Mock()
    res.spawn_limiter.acquire.return_value = True
    res.breaker.record_failure = Mock(wraps=res.breaker.record_failure)
    res.retry_budget.try_acquire_retry = Mock(return_value=True)
    return bridge._RequestAttempts(res, time.monotonic() + 60, **kwargs)


def _result(**overrides: Any) -> dict[str, Any]:
    result = {
        "texts": [],
        "reasonings": [],
        "native_calls": [],
        "usage": {},
        "error": None,
        "exit_reason": "ok",
        "delivered": False,
        "terminal": "completed",
        "first_event_at": None,
        "first_token_at": None,
        "step_closed": True,
        "first_event_ms": None,
        "ttft_ms": None,
        "prompt_status": None,
        "transient_error": False,
        "proxy_url": None,
    }
    result.update(overrides)
    return result


def _quota_result(**overrides: Any) -> dict[str, Any]:
    return _result(
        error={
            "type": "provider.free-limit",
            "statusCode": 429,
            "message": "Free usage limit reached for this IP",
        },
        transient_error=True,
        **overrides,
    )


def _install_attempts(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
    results: list[dict[str, Any]],
    *,
    select_proxy: bool = False,
) -> Mock:
    queued = iter(results)

    def serve(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = next(queued)
        if select_proxy:
            result["proxy_url"] = bridge._next_standalone_proxy()
        kwargs["on_startup_ready"]()
        for index, key in ((4, "reasonings"), (5, "texts"), (6, "native_calls")):
            for value in result[key]:
                args[index](value)
        return result

    runner = Mock(side_effect=serve)
    monkeypatch.setattr(bridge, "_serve_one_attempt", runner)
    return runner


def _configure_pool(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    offset: int = 0,
) -> tuple[str, str]:
    pool = tmp_path / "pool.txt"
    pool.write_text("u:p@host:10001\nu:p@host:10002\n", encoding="utf-8")
    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY", "pool")
    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE", str(pool))
    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_PROXYRACK_OFFSET", str(offset))
    monkeypatch.setattr(bridge, "_resolve_proxyrack_gateway", lambda: "192.0.2.1")
    return "http://u:p@192.0.2.1:10001", "http://u:p@192.0.2.1:10002"


def _stream(
    handler: Any, attempts: Any, tools: list[dict[str, Any]]
) -> tuple[bool, dict[str, Any], list[str]]:
    texts: list[str] = []
    xs: dict[str, Any] = {"status": 200}
    done = handler._run_serve_stream_attempts(
        "deepseek-v4.1-flash-free",
        "Ответь",
        "high",
        bool(tools),
        tools,
        "chatcmpl-test",
        1,
        "deepseek-v4.1-flash-free",
        texts.append,
        texts.append,
        Mock(),
        attempts,
        attempts.res,
        xs,
        texts,
    )
    attempts.commit()
    return done, xs, texts


def _json(handler: Any, attempts: Any) -> dict[str, Any]:
    xs: dict[str, Any] = {}
    assert handler._serve_json_serve(
        "deepseek-v4.1-flash-free",
        "Ответь",
        "high",
        False,
        [],
        None,
        None,
        attempts.res,
        attempts,
        xs,
    )
    attempts.commit()
    assert handler._send.call_args.args[0] == 200
    return handler._send.call_args.args[1]["choices"][0]["message"]


def test_stream_serve_attempt2_free_quota_error_after_attempt1_reasoning_rotates_proxy(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    handler = _handler(bridge)
    attempts = _attempts(bridge)
    p1, p2 = _configure_pool(bridge, monkeypatch, tmp_path, offset=1)
    results = [
        _result(reasonings=["Планирую вызов"], terminal="incomplete_step"),
        _quota_result(),
        _result(texts=["Ответ"]),
    ]
    runner = _install_attempts(bridge, monkeypatch, results, select_proxy=True)
    signal = Mock(side_effect=[2, 0])
    monkeypatch.setattr(bridge, "_incomplete_step_signal", signal)
    tools = [{"type": "function", "function": {"name": "read", "parameters": {}}}]
    done, xs, texts = _stream(handler, attempts, tools)
    assert done and xs["status"] == 200
    assert runner.call_count == 3
    assert p1 in bridge._proxy_quarantine_until
    assert [result["proxy_url"] for result in results] == [p2, p1, p2]
    assert "".join(texts) == "Ответ"
    assert b'"error"' not in handler.wfile.getvalue()
    assert attempts.quota_rotations == 1
    attempts.res.breaker.record_failure.assert_not_called()
    # Только incomplete_step расходует бюджет; смена выбитого порта — нет.
    assert attempts.res.retry_budget.try_acquire_retry.call_count == 1


def test_stream_serve_attempt_with_emitted_reasoning_does_not_duplicate_on_transient_error(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = _handler(bridge)
    attempts = _attempts(bridge)
    runner = _install_attempts(
        bridge,
        monkeypatch,
        [
            _quota_result(
                reasonings=["Уникальное размышление"], proxy_url="http://p1:10001"
            ),
        ],
    )
    monkeypatch.setattr(bridge, "_incomplete_step_signal", Mock(return_value=0))
    done, _, _ = _stream(handler, attempts, [])
    assert done
    assert runner.call_count == 1
    assert "http://p1:10001" in bridge._proxy_quarantine_until
    assert handler.wfile.getvalue().decode().count("Уникальное размышление") == 1
    assert b'"error"' in handler.wfile.getvalue()
    assert attempts.retries == 0


@pytest.mark.parametrize("free_quota", [True, False])
def test_json_serve_discards_partial_reasoning_and_retries_on_transient_error(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
    free_quota: bool,
) -> None:
    handler = _handler(bridge)
    attempts = _attempts(bridge)
    failed = _quota_result(reasonings=["thinking..."], proxy_url="http://p1:10001")
    if not free_quota:
        failed["error"] = {"statusCode": 503, "message": "Temporarily unavailable"}
    runner = _install_attempts(
        bridge,
        monkeypatch,
        [
            failed,
            _result(texts=["Чистый ответ"], reasonings=["Готовый план"]),
        ],
    )
    message = _json(handler, attempts)
    assert runner.call_count == 2
    assert message["content"] == "Чистый ответ"
    assert message["reasoning_content"] == "Готовый план"
    assert "thinking..." not in str(message)
    assert ("http://p1:10001" in bridge._proxy_quarantine_until) == free_quota
    attempts.res.breaker.record_failure.assert_not_called()


def test_json_serve_no_tools_retries_when_model_calls_builtin_native_tool(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler = _handler(bridge)
    attempts = _attempts(bridge)
    runner = _install_attempts(
        bridge,
        monkeypatch,
        [
            _result(native_calls=[{"part": {"tool": "read"}}], terminal="tool_calls"),
            _result(texts=["Ответ без инструментов"]),
        ],
    )
    prompt_builder = Mock(wraps=bridge._unavailable_tools_prompt)
    monkeypatch.setattr(bridge, "_unavailable_tools_prompt", prompt_builder)
    assert _json(handler, attempts)["content"] == "Ответ без инструментов"
    assert runner.call_count == 2
    assert prompt_builder.call_args.args[2] == ["read"]
    assert prompt_builder.call_args.args[3] == []
    assert "read" in runner.call_args.args[1]


def test_proxy_pool_quarantine_skips_burned_port_and_falls_back_when_all_quarantined(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _configure_pool(bridge, monkeypatch, tmp_path)
    now = [100.0]
    monkeypatch.setattr(bridge.time, "monotonic", lambda: now[0])
    bridge._quarantine_proxy(None)
    bridge._quarantine_proxy("")
    bridge._quarantine_proxy("   ")
    assert not bridge._proxy_quarantine_until
    p1 = bridge._next_standalone_proxy()
    p2 = bridge._next_standalone_proxy()
    assert p1 != p2
    bridge._quarantine_proxy(f" {p1} ", 20)
    assert bridge._next_standalone_proxy() == p2
    bridge._quarantine_proxy(p2, 10)
    assert bridge._next_standalone_proxy() == p2
    now[0] = 110.0
    assert bridge._next_standalone_proxy() == p2
    assert p2 not in bridge._proxy_quarantine_until
    now[0] = 120.0
    assert bridge._next_standalone_proxy() == p1
    assert not bridge._proxy_quarantine_until
    bridge._quarantine_proxy(p1)
    bridge._reset_proxy_pool_for_tests()
    assert not bridge._proxy_quarantine_until


@pytest.mark.parametrize(
    "err, expected",
    [
        ({"type": "provider.free-limit", "message": "Quota"}, True),
        ({"message": "Free usage limit reached"}, True),
        ("USAGE LIMIT REACHED", True),
        ("provider.free-limit", True),
        ("Request quota exhausted.", True),
        ("Request quota exhausted. QUOTA", True),
        ({"message": "subscription quota exhausted"}, True),
        ("QUOTA EXHAUSTED", True),
        ({"message": "Connection lost"}, False),
        (None, False),
    ],
)
def test_is_free_quota_error(bridge: Any, err: object, expected: bool) -> None:
    assert bridge._is_free_quota_error(err) is expected


@pytest.mark.parametrize(
    "ev",
    [
        {"statusCode": 400, "message": "Request quota exhausted."},
        {
            "type": "error",
            "error": {"statusCode": 400, "message": "subscription quota exhausted"},
        },
        {"type": "error", "error": "Request quota exhausted. QUOTA", "status": 400},
    ],
)
def test_quota_stream_error_is_transient_despite_fatal_status(
    bridge: Any, ev: dict[str, Any]
) -> None:
    assert bridge._is_transient_stream_error(ev) is True


def test_fatal_stream_error_without_quota_stays_fatal(bridge: Any) -> None:
    assert (
        bridge._is_transient_stream_error(
            {"statusCode": 400, "message": "invalid request body"}
        )
        is False
    )


def test_map_serve_event_preserves_quota_type(bridge: Any) -> None:
    mapped = bridge._map_serve_event(
        {
            "type": "session.execution.failed",
            "data": {
                "sessionID": "s1",
                "error": {
                    "type": "provider.free-limit",
                    "message": "Quota",
                    "status": 429,
                },
            },
        }
    )
    assert mapped == (
        "error",
        {
            "statusCode": 429,
            "message": "Quota",
            "type": "provider.free-limit",
            "sessionID": "s1",
        },
    )


def test_quota_rotation_extends_spawn_limit_without_charging_retry_budget(
    bridge: Any,
) -> None:
    attempts = _attempts(bridge, max_total=2, max_quota_rotations=1)
    attempts.note_spawn()
    assert attempts.allow_quota_rotation()
    assert attempts.quota_rotations == 1 and attempts.retries == 0
    attempts.res.retry_budget.try_acquire_retry.assert_not_called()
    assert not attempts.allow_quota_rotation()
    attempts.note_spawn()
    assert attempts.can_spawn() and attempts.begin_attempt()
    attempts.note_spawn()
    assert not attempts.can_spawn() and not attempts.begin_attempt()


@pytest.mark.parametrize("denial", ["limit", "deadline", "aux", "blocking", "probe"])
def test_denied_quota_rotation_does_not_change_counters(
    bridge: Any, denial: str
) -> None:
    attempts = _attempts(bridge)
    if denial == "limit":
        attempts.total_spawns = bridge.MAX_TOTAL_SPAWNS
    elif denial == "deadline":
        attempts.deadline = 0
    elif denial == "aux":
        attempts.aux_budget = bridge._AuxIoBudget(budget_s=0)
    elif denial == "blocking":
        attempts.res.breaker.is_blocking = Mock(return_value=True)
    else:
        attempts.res.breaker.allow = Mock(return_value=False)
    assert not attempts.allow_quota_rotation()
    assert attempts.quota_rotations == 0 and attempts.retries == 0
    attempts.res.retry_budget.try_acquire_retry.assert_not_called()


@pytest.mark.parametrize("stream", [True, False])
def test_serve_quota_rotations_can_exceed_base_spawn_limit(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
    stream: bool,
) -> None:
    handler = _handler(bridge)
    attempts = _attempts(bridge, max_quota_rotations=3)
    runner = _install_attempts(
        bridge,
        monkeypatch,
        [
            _quota_result(),
            _quota_result(),
            _quota_result(),
            _result(texts=["Ответ"]),
        ],
    )
    if stream:
        done, _, texts = _stream(handler, attempts, [])
        assert done and "".join(texts) == "Ответ"
        assert b'"error"' not in handler.wfile.getvalue()
    else:
        assert _json(handler, attempts)["content"] == "Ответ"
    assert runner.call_count == 4
    assert attempts.quota_rotations == 3
    attempts.res.retry_budget.try_acquire_retry.assert_not_called()
    attempts.res.breaker.record_failure.assert_not_called()


@pytest.mark.parametrize("explicit_proxy", [None, "http://explicit:10003"])
def test_serve_one_attempt_reports_proxy_and_overrides_all_proxy_vars(
    bridge: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    explicit_proxy: str | None,
) -> None:
    env = {name: "http://inherited:10001" for name in bridge._PROXY_VARS}
    monkeypatch.setattr(bridge, "_serve_env", lambda _model: env)
    spawn = Mock(side_effect=bridge.ServeStartupDeadlineExceeded("test"))
    monkeypatch.setattr(bridge, "_spawn_serve", spawn)
    result = bridge._serve_one_attempt(
        "deepseek-v4.1-flash-free",
        "Ответь",
        "high",
        tmp_path,
        Mock(),
        Mock(),
        Mock(),
        time.monotonic(),
        proxy_url=explicit_proxy,
    )
    assert result["proxy_url"] == (explicit_proxy or "http://inherited:10001")
    assert result["exit_reason"] == "timeout"
    assert {env[name] for name in bridge._PROXY_VARS} == {result["proxy_url"]}
    spawn.assert_called_once()

"""Red-воспроизведение инцидентов `userinfo: EOF` и `Malformed function call` (SCN-01/02/05/06).

Структура входов — из handoff-qa §1.2-§1.4, детерминированный стаб — `tests/agy_stub_agent.py`.
Тесты утверждают ЦЕЛЕВОЕ поведение: на базе `dev` они FAILED; зелёными становятся после
реализации core-модулей и подключения фасада в `bridges/agy-bridge/server.py` (Coder 3).
Факты о базе (зелёные проверки стаба) помечены `test_stub_*`. Не ослаблять.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_REPO = Path(__file__).resolve().parents[1]
for _path in (str(_REPO), str(_REPO / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import agy_stub_agent as stub  # noqa: E402
from core.stream_interruption_recovery import (  # noqa: E402
    evaluate_stream_retry_eligibility,
    is_transient_stream_interruption,
)

_BRIDGE_PY = _REPO / "bridges" / "agy-bridge" / "server.py"
_STUB_PY = Path(stub.__file__).resolve()
_SERVER: ModuleType | None = None
_FLAGS = (
    "BRIDGE_TRANSPORT_FAILURE_CLASSIFIER_ENABLED",
    "BRIDGE_VENDOR_RETRY_PHRASE_MASK_ENABLED",
    "BRIDGE_TOOLCALL_ERROR_RECOVERY_ENABLED",
)


def _server() -> ModuleType:
    """Загрузить фасад agy-bridge один раз на процесс (как остальные тесты моста)."""
    global _SERVER
    if _SERVER is None:
        import os
        import tempfile

        tmp = tempfile.mkdtemp(prefix="red-incident-")  # изоляция вместо conftest (--noconftest)
        os.environ.setdefault("AGY_BRIDGE_KEY", "test-key-red-incident")
        os.environ.setdefault("BRIDGE_TELEMETRY_DB_PATH", os.path.join(tmp, "telemetry.duckdb"))
        os.environ.setdefault("BRIDGE_MODEL_PENALTIES_PATH", os.path.join(tmp, "penalties.json"))
        os.environ.setdefault("BRIDGE_ENV_FILE_PATH", os.path.join(tmp, "hot.env"))
        spec = importlib.util.spec_from_file_location("agy_bridge_server_red_incident", _BRIDGE_PY)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _SERVER = module
    return _SERVER


def _enable_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Включить целевые флаги только через env и пустой изолированный dynamic_config."""
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    for name in _FLAGS:
        monkeypatch.setenv(name, "true")


def _new(module: str) -> Any:
    """Импортировать новый core-модуль лениво: отсутствие = FAILED, а не collect-error."""
    return importlib.import_module(module)


def _stream_text(run: stub.StubRun) -> str:
    return "\n".join(str(event.get("content", "")) for event in run.events)


# ---------------------------------------------------------------- стаб (факты, зелёные)


def test_stub_eof_first_spawn_fails_second_succeeds(tmp_path: Path) -> None:
    """Стаб воспроизводит структуру инцидента №1: spawn0 rc=1 EOF, spawn1 успех."""
    cmd = [sys.executable, str(_STUB_PY), "--scenario", "eof_then_ok", "--state-dir", str(tmp_path)]
    first = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)  # noqa: S603
    second = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=30)  # noqa: S603
    assert (first.returncode, second.returncode) == (1, 0)
    assert stub.USERINFO_EOF in first.stderr
    assert '"status": "SUCCESS"' in second.stdout


def test_stub_malformed_streams_have_incident_shape() -> None:
    """idx4 — 10 блоков, служебная ошибка idx5, idx6 — 10 блоков (9 валидных для 9/10)."""
    valid = stub.build_run("malformed_valid", 0)
    broken = stub.build_run("malformed_nine_ten", 0)
    assert stub.MALFORMED_TEXT in str(valid.events[1]["error"])
    assert _stream_text(valid).count("<tool_call>") == 20
    assert valid.events[-1]["result"]["status"] == "ERROR"  # type: ignore[index]
    assert str(broken.events[2]["content"]).count("</tool_call>") == 10
    assert str(broken.events[2]["content"]).count('"file_path": </tool_call>') == 1


# ---------------------------------------------------------------- SCN-01 / SCN-02: EOF


def test_scn01_base_replay_classifier_is_not_widened_ad001() -> None:
    """AD-001: общее ядро replay НЕ расширяется Go-формами; классификация живёт в новом модуле."""
    assert is_transient_stream_interruption(stub.USERINFO_EOF) is False
    decision = evaluate_stream_retry_eligibility(error_text=stub.USERINFO_EOF, delivered=False)
    assert decision.can_retry is False


def test_scn01_facade_marks_go_eof_transient_only_when_flag_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Фасад: Go `userinfo: EOF` транзиентен при флаге; FM-09 (401) фатален; флаг выкл. → False."""
    facade = _new("core.turn_resilience_facade")
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    assert facade.go_transient(stub.USERINFO_EOF) is False
    monkeypatch.setenv("BRIDGE_TRANSPORT_FAILURE_CLASSIFIER_ENABLED", "true")
    assert facade.go_transient(stub.USERINFO_EOF) is True
    assert facade.go_transient("HTTP 401 Unauthorized: EOF") is False


def test_scn01_facade_retry_gate_allows_pre_content_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Гейт повтора за флагом: до доставки контента повтор разрешён, после — запрещён."""
    facade = _new("core.turn_resilience_facade")
    tracker = _new("core.content_delivery_tracker").ContentDeliveryTracker()
    cfg = tmp_path / "dynamic_config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("BRIDGE_RETRY_WINDOW_PAUSE_ENABLED", "true")
    facade.reset_failure_window()
    ctx: dict[str, Any] = {"delivery_tracker": tracker, "t_req_start": 0.0, "resilience_clock": lambda: 23.0}
    tracker.mark_keepalive()
    assert facade.take(ctx, {"duration_s": 23.0}, lambda: True, lambda _line: None) is True
    tracker.mark_content("текст")
    ctx2 = dict(ctx)
    assert facade.take(ctx2, {"duration_s": 23.0}, lambda: True, lambda _line: None) is False


def test_scn01_new_classifier_marks_go_forms_transient_and_keeps_fatal() -> None:
    """Новый классификатор: Go-формы транзиентны, FM-09 остаётся фатальным."""
    mod = _new("core.transport_failure_classifier")
    contracts = _new("core.transport_failure_contracts")
    kind = contracts.FailureKind
    assert mod.classify_transport_failure(stub.USERINFO_EOF).kind is kind.NETWORK_TRANSIENT
    assert mod.classify_transport_failure("HTTP 401 Unauthorized: EOF").kind is kind.FATAL


def test_scn02_facade_treats_eof_as_transient_when_flag_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Фасад моста `_is_transient_upstream_error` за флагом видит EOF транзиентным."""
    _enable_flags(monkeypatch, tmp_path)
    run = stub.build_run("eof_then_ok", 0)
    assert _server()._is_transient_upstream_error(run.stderr) is True  # pyright: ignore[reportAny]


def test_scn02_keepalive_only_stream_allows_invisible_retry() -> None:
    """Keepalive/пустая role-дельта — не доставка: повтор невидимый, 2 спавна максимум."""
    tracker = _new("core.content_delivery_tracker").ContentDeliveryTracker()
    tracker.mark_keepalive()
    facts = tracker.snapshot()
    policy = _new("core.invisible_retry_policy")
    cfg = _new("core.transport_failure_contracts").RetryBudgetConfig(max_retries=1, retry_total_budget_s=1020.0, client_timeout_s=600.0)
    state = _new("core.transport_failure_contracts").RetryAttemptState(1, 23.0, 23.0)
    decision = policy.may_retry_invisibly(facts, cfg, state)
    assert decision.allowed is True


def test_scn02_all_spawns_fail_terminal_error_bounded() -> None:
    """Оба спавна упали: после исчерпания попыток повтор запрещён (одна терминальная ошибка)."""
    policy = _new("core.invisible_retry_policy")
    facts = _new("core.content_delivery_tracker").ContentDeliveryTracker().snapshot()
    cfg = _new("core.transport_failure_contracts").RetryBudgetConfig(max_retries=1, retry_total_budget_s=1020.0, client_timeout_s=600.0)
    state = _new("core.transport_failure_contracts").RetryAttemptState(2, 60.0, 30.0)
    decision = policy.may_retry_invisibly(facts, cfg, state)
    assert decision.allowed is False


# ---------------------------------------------------------------- SCN-05 / SCN-06: Malformed


def _parse_port() -> Any:
    import json
    import re

    parsed_call = _new("core.transport_failure_contracts").ParsedToolCall

    class _Port:
        def parse_all(self, text: str) -> tuple[Any, ...] | None:
            blocks = re.findall(r"<tool_call>(.*?)</tool_call>", text, re.S)
            if "".join(f"<tool_call>{b}</tool_call>" for b in blocks) != text:
                return None
            try:
                items = [json.loads(b) for b in blocks]
            except ValueError:
                return None
            return tuple(
                parsed_call("", p["name"], json.dumps(p["arguments"], sort_keys=True)) for p in items
            )

    return _Port()


def _recovery_input(run: stub.StubRun) -> Any:
    tracker = _new("core.tool_call_completion_tracker").ToolCallCompletionTracker()
    for event in run.events:
        if event["event"] == "error_message":
            tracker.note_error(int(event["step_idx"]), str(event["error"]))  # type: ignore[call-overload]
        elif event["event"] == "planner":
            tracker.note_planner(int(event["step_idx"]), str(event["content"]))  # type: ignore[call-overload]
    return tracker.snapshot()


def test_scn05_valid_retry_after_malformed_is_recovered_as_tool_calls() -> None:
    """Ошибка functionCall, затем 5 валидных вызовов (пары схлопнуты) → RECOVER."""
    policy = _new("core.tool_call_recovery_policy")
    contracts = _new("core.transport_failure_contracts")
    steps = _recovery_input(stub.build_run("malformed_valid", 0))
    decision = policy.evaluate_recovery(steps, _parse_port())
    assert decision.recovered is True
    assert len(decision.calls) == 5
    assert contracts.ToolCallRecoveryDecision is type(decision)


def test_scn06_nine_of_ten_rejected_fail_closed() -> None:
    """9 валидных + 1 битый блок → REJECT целиком, ни одного вызова не доставлено."""
    policy = _new("core.tool_call_recovery_policy")
    steps = _recovery_input(stub.build_run("malformed_nine_ten", 0))
    decision = policy.evaluate_recovery(steps, _parse_port())
    assert decision.recovered is False
    assert decision.calls == ()


def test_scn05_facade_masks_vendor_retry_phrase_when_flag_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """User-visible тело ошибки не содержит `Retries remaining: N`, диагностика остаётся."""
    _enable_flags(monkeypatch, tmp_path)
    handler = _server().Handler
    body = handler._error_body({"state": "agy_error", "err": stub.MALFORMED_TEXT})  # pyright: ignore[reportAny]
    assert "Retries remaining" not in body["message"]
    assert "Malformed function call" in body["message"]


def test_scn05_new_sanitizer_is_idempotent() -> None:
    """Санитайзер маскирует фразу и идемпотентен."""
    mod = _new("core.vendor_phrase_sanitizer")
    once = mod.mask_vendor_phrases(stub.MALFORMED_TEXT)
    assert "Retries remaining" not in once
    assert mod.mask_vendor_phrases(once) == once

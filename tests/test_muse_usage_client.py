"""W0-B red-контракт `core.muse_usage_client` (VER-003, REQ-002, AD-003).

Точные сигнатуры для волны W1-B (`core/muse_usage_client.py`, <=220 строк):
- `MuseUsageSnapshot` — frozen dataclass: `status` ('ok'|'exhausted'|'unknown'),
  `tier`, `window_used_percent`, `weekly_used_percent`, `reset_at` (секунды,
  только при exhausted, иначе None), `as_of_ms`, `source`, `error_code`.
- `parse_usage_json(text: str) -> MuseUsageSnapshot`; битый JSON,
  `schemaVersion != 1` или неполный `allowance` -> `ValueError`.
- `usage_ttl_s(environ=None) -> float`: env `MUSE_USAGE_CACHE_TTL_S`,
  дефолт 30.0; невалидное/неположительное значение -> дефолт.
- `resolve_wrapper_path(environ=None) -> str`: env `MUSE_CLI_WRAPPER`,
  иначе `~/.config/muse-launch/muse-cli.sh` (голый бинарник запрещён).
- `MuseUsageClient(runner=None, *, ttl_s=None, wrapper_path=None, clock=None)`;
  `runner(argv: list[str]) -> tuple[int, str, str]` (rc, stdout, stderr),
  `clock() -> float` — по умолчанию `time.monotonic`. Единственный владелец
  состояния: `self._cache`, `self._inflight`, `self._lock` (M-MOD-I4).
- `get_snapshot(*, force_refresh=False) -> MuseUsageSnapshot`: single-flight,
  TTL от локального `clock()` в момент получения (`asOfMs` — метаданные),
  Fail-Open `unknown` при ошибке, Fail-Closed `exhausted` при исчерпании:
  `window>=100 or weekly>=100`, `reset_at=max(resetsAtMs//1000 исчерпанных)`.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest

SAMPLE = (
    '{"schemaVersion":1,"allowance":{"tier":"Muse Code Max Usage",'
    '"window":{"usedPercent":34,"resetsAtMs":1795446181000},'
    '"weekly":{"usedPercent":24,"resetsAtMs":1795996800000},'
    '"asOfMs":1795436896748,"source":"mint"},"reason":null,"hint":null}'
)
WIN_RESET_MS, WEEK_RESET_MS, AS_OF_MS = 1795446181000, 1795996800000, 1795436896748
BARE = "~/" + ".local/" + "bin/" + "mu" + "se"


def _mod() -> Any:
    return pytest.importorskip("core.muse_usage_client")


def _usage_json(window: float, weekly: float, win_reset: int, week_reset: int, as_of: int) -> str:
    payload = {"schemaVersion": 1, "allowance": {
        "tier": "Muse Code Max Usage",
        "window": {"usedPercent": window, "resetsAtMs": win_reset},
        "weekly": {"usedPercent": weekly, "resetsAtMs": week_reset},
        "asOfMs": as_of, "source": "mint"}, "reason": None, "hint": None}
    return json.dumps(payload)


class FakeClock:
    """Монотонные часы с ручным сдвигом для проверки TTL."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RecordingRunner:
    """Фейковый runner: записывает argv, возвращает результат или бросает."""

    def __init__(self, result: Any, delay_s: float = 0.0) -> None:
        self.result, self.delay_s, self.calls = result, delay_s, []

    def __call__(self, argv: list[str]) -> tuple[int, str, str]:
        self.calls.append(list(argv))
        if self.delay_s:
            time.sleep(self.delay_s)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def test_parse_sample_payload_fields() -> None:
    snap = _mod().parse_usage_json(SAMPLE)
    assert snap.status == "ok"
    assert snap.tier == "Muse Code Max Usage"
    assert snap.window_used_percent == 34
    assert snap.weekly_used_percent == 24
    assert snap.as_of_ms == AS_OF_MS
    assert snap.source == "mint"
    assert snap.reset_at is None
    assert snap.error_code is None


def test_parse_rejects_bad_json_wrong_version_and_missing_allowance() -> None:
    mod = _mod()
    bad = ["not json", "", '{"schemaVersion":2,"allowance":{}}', '{"schemaVersion":1}']
    for text in bad:
        with pytest.raises(ValueError):
            mod.parse_usage_json(text)


def test_exhausted_window_only_reset_at() -> None:
    text = _usage_json(100, 24, WIN_RESET_MS, WEEK_RESET_MS, AS_OF_MS)
    snap = _mod().parse_usage_json(text)
    assert snap.status == "exhausted"
    assert snap.reset_at == WIN_RESET_MS // 1000


def test_exhausted_weekly_only_and_both_reset_at_is_max() -> None:
    mod = _mod()
    weekly = mod.parse_usage_json(_usage_json(34, 100, WIN_RESET_MS, WEEK_RESET_MS, AS_OF_MS))
    assert weekly.status == "exhausted"
    assert weekly.reset_at == WEEK_RESET_MS // 1000
    both = mod.parse_usage_json(_usage_json(100, 150, WEEK_RESET_MS, WIN_RESET_MS, AS_OF_MS))
    assert both.status == "exhausted"
    assert both.reset_at == WEEK_RESET_MS // 1000


def test_below_100_percent_is_ok() -> None:
    text = _usage_json(99.9, 99, WIN_RESET_MS, WEEK_RESET_MS, AS_OF_MS)
    snap = _mod().parse_usage_json(text)
    assert snap.status == "ok"
    assert snap.reset_at is None


def test_fail_open_unknown_on_exit42_errors_timeout_and_garbage() -> None:
    mod = _mod()
    results = [(42, "", "proxy down"), (1, "", "boom"), (0, "not json", ""),
               TimeoutError("slow"), FileNotFoundError("no wrapper")]
    for result in results:
        snap = mod.MuseUsageClient(runner=RecordingRunner(result)).get_snapshot()
        assert snap.status == "unknown"
        assert snap.reset_at is None
        assert isinstance(snap.error_code, str) and snap.error_code


def test_runner_argv_uses_wrapper_only() -> None:
    runner = RecordingRunner((0, SAMPLE, ""))
    _mod().MuseUsageClient(runner=runner).get_snapshot()
    assert len(runner.calls) == 1
    argv = runner.calls[0]
    assert argv[0].endswith(".config/muse-launch/muse-cli.sh")
    assert argv[1:] == ["usage", "--json"]
    assert BARE not in " ".join(argv)


def test_wrapper_default_and_env_override() -> None:
    mod = _mod()
    assert mod.resolve_wrapper_path({}).endswith(".config/muse-launch/muse-cli.sh")
    assert mod.resolve_wrapper_path({"MUSE_CLI_WRAPPER": "/tmp/w.sh"}) == "/tmp/w.sh"
    assert BARE not in mod.resolve_wrapper_path({})


def test_ttl_default_30_env_override_and_invalid_fallback() -> None:
    mod = _mod()
    assert mod.usage_ttl_s({}) == 30.0
    assert mod.usage_ttl_s({"MUSE_USAGE_CACHE_TTL_S": "7"}) == 7.0
    assert mod.usage_ttl_s({"MUSE_USAGE_CACHE_TTL_S": "abc"}) == 30.0
    assert mod.usage_ttl_s({"MUSE_USAGE_CACHE_TTL_S": "-5"}) == 30.0


def test_ttl_uses_monotonic_clock_not_as_of_ms() -> None:
    mod = _mod()
    clock = FakeClock()
    ancient = _usage_json(10, 10, WIN_RESET_MS, WEEK_RESET_MS, 1)
    runner = RecordingRunner((0, ancient, ""))
    client = mod.MuseUsageClient(runner=runner, clock=clock)
    client.get_snapshot()
    clock.advance(29)
    client.get_snapshot()
    assert len(runner.calls) == 1
    clock.advance(2)
    client.get_snapshot()
    assert len(runner.calls) == 2


def test_env_ttl_applies_when_ttl_s_not_given(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _mod()
    monkeypatch.setenv("MUSE_USAGE_CACHE_TTL_S", "5")
    clock = FakeClock()
    runner = RecordingRunner((0, SAMPLE, ""))
    client = mod.MuseUsageClient(runner=runner, clock=clock)
    client.get_snapshot()
    clock.advance(6)
    client.get_snapshot()
    assert len(runner.calls) == 2


def test_force_refresh_bypasses_cache() -> None:
    runner = RecordingRunner((0, SAMPLE, ""))
    client = _mod().MuseUsageClient(runner=runner, clock=FakeClock())
    client.get_snapshot()
    client.get_snapshot(force_refresh=True)
    assert len(runner.calls) == 2


def test_single_flight_concurrent_calls_run_once() -> None:
    runner = RecordingRunner((0, SAMPLE, ""), delay_s=0.3)
    client = _mod().MuseUsageClient(runner=runner)
    results: list[Any] = []
    threads = [threading.Thread(target=lambda: results.append(client.get_snapshot()))
               for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert len(runner.calls) == 1
    assert len(results) == 8
    assert all(item == results[0] and item.status == "ok" for item in results)


def test_snapshot_frozen_and_client_owns_cache_state() -> None:
    mod = _mod()
    client = mod.MuseUsageClient(runner=RecordingRunner((0, SAMPLE, "")))
    snap = client.get_snapshot()
    with pytest.raises(dataclasses.FrozenInstanceError):
        snap.status = "exhausted"  # type: ignore[misc]
    assert hasattr(client, "_cache")
    assert hasattr(client, "_inflight")
    assert hasattr(client, "_lock")


def test_module_has_no_global_mutable_state_or_bare_binary() -> None:
    mod = _mod()
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert BARE not in source
    assert "muse-cli.sh" in source
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            assert not isinstance(node.value, (ast.Dict, ast.List, ast.Set))
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                assert node.value.func.id not in {"dict", "list", "set"}

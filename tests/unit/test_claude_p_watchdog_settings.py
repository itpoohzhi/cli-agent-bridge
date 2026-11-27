"""L1: фасад watchdog-настроек моста и first_token_timeout_s в `_watchdog_for` (REQ-001/REQ-002, AD-002).

Детерминированные unit-тесты: FakeClock/StubWatchdog/FakeController, изолированный
`tmp_path/.env`, без реальных sleep и без чтения `~/.dsh` владельца.
"""

from __future__ import annotations

import dataclasses
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.bridge_watchdog_settings import ALLOWED_WATCHDOG_SETTINGS_KEYS, BridgeWatchdogFacade
from core.liveness_signals import FLAG_SOFT_LIVENESS
from core.watchdog import AdaptiveTimeoutController, WatchdogMetrics
from tests.unit._claude_bridge_tool_fakes import load_bridge
from tests.unit._claude_bridge_turn_fakes import (
    FakeClock,
    FakeController,
    bridge as bridge,  # noqa: F401
)

FIRST_KEY = "BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S"
IDLE_KEY = "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S"
WD_KEY = "CLAUDE_P_BRIDGE_WATCHDOG_ENABLED"
SECRET_KEY = "CLAUDE_P_BRIDGE_KEY"
_LEGACY_SUFFIXES = ("WATCHDOG_ENABLED", "IDLE_TIMEOUT_S", "IO_WAIT_CAP_S", "SAFETY_CAP_S", "WATCHDOG_INTERVAL_S")
_LEGACY_BRIDGE = ("IDLE_TIMEOUT_S", "IO_WAIT_CAP_S", "SAFETY_CAP_S", "WATCHDOG_INTERVAL_S")


class StubWatchdog:
    """Заглушка процессного сэмплера: живая группа без CPU-прогресса и потомков."""

    def __init__(self) -> None:
        self.seeded: list[int] = []

    def seed(self, pgid: int, *, rid: str = "", turn_id: str = "") -> WatchdogMetrics:
        self.seeded.append(pgid)
        return WatchdogMetrics.empty(pgid, 0.0, alive=True)

    def sample(self, pgid: int, *, rid: str = "", turn_id: str = "") -> WatchdogMetrics:
        return WatchdogMetrics.empty(pgid, 0.0, alive=True)

    def forget(self, pgid: int) -> None:
        pass


@pytest.fixture(autouse=True)
def _isolated_watchdog_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Мост и фасад не видят ни окружения хоста, ни ~/.dsh владельца."""
    for key in (*ALLOWED_WATCHDOG_SETTINGS_KEYS, *(f"BRIDGE_{s}" for s in _LEGACY_BRIDGE),
                FLAG_SOFT_LIVENESS, SECRET_KEY):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "absent-dynamic.json"))
    monkeypatch.setenv("BRIDGE_ENV_FILE_PATH", str(tmp_path / "absent.env"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "no-home"))


def _env_file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(body, encoding="utf-8")
    return path


def _facade(env_path: Path | None) -> BridgeWatchdogFacade:
    return BridgeWatchdogFacade.for_prefix(
        "CLAUDE_P_BRIDGE_", first_progress_keys=(FIRST_KEY,), env_path=env_path
    )


def _fake_run(pid: int = 4242) -> Any:
    return SimpleNamespace(proc=SimpleNamespace(pid=pid))


def test_allowlist_has_ten_nonsecret_keys_and_no_secrets() -> None:
    """REQ-002: строгий allowlist из 9 legacy-ключей + first-progress; секреты не читаются."""
    assert len(ALLOWED_WATCHDOG_SETTINGS_KEYS) == 10
    assert FIRST_KEY in ALLOWED_WATCHDOG_SETTINGS_KEYS
    assert {f"CLAUDE_P_BRIDGE_{s}" for s in _LEGACY_SUFFIXES} <= ALLOWED_WATCHDOG_SETTINGS_KEYS
    assert {f"BRIDGE_{s}" for s in _LEGACY_BRIDGE} <= ALLOWED_WATCHDOG_SETTINGS_KEYS
    assert SECRET_KEY not in ALLOWED_WATCHDOG_SETTINGS_KEYS


def test_secret_keys_from_env_file_are_never_read(tmp_path: Path) -> None:
    """QA-003/THREAT-001: секрет из .env не попадает ни в снимок, ни в get_setting."""
    facade = _facade(_env_file(tmp_path, f"{SECRET_KEY}=super-secret\n{IDLE_KEY}=123\n"))
    assert facade.get_setting(SECRET_KEY) == ""
    assert facade.get_setting(IDLE_KEY) == "123"


def test_cascade_os_environ_over_env_file_over_fallback_over_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-002: приоритет os.environ > .env > fallback-ключ > default."""
    env = _env_file(tmp_path, f"{IDLE_KEY}=123\nBRIDGE_IDLE_TIMEOUT_S=456\n")
    assert _facade(env).get_setting(IDLE_KEY, "BRIDGE_IDLE_TIMEOUT_S", "9") == "123"
    monkeypatch.setenv(IDLE_KEY, " 77 ")
    assert _facade(env).get_setting(IDLE_KEY, "BRIDGE_IDLE_TIMEOUT_S") == "77"
    monkeypatch.delenv(IDLE_KEY)
    only_fallback = _facade(_env_file(tmp_path, "BRIDGE_IDLE_TIMEOUT_S=456\n"))
    assert only_fallback.get_setting(IDLE_KEY, "BRIDGE_IDLE_TIMEOUT_S") == "456"
    assert _facade(tmp_path / "missing.env").get_setting(IDLE_KEY, "BRIDGE_IDLE_TIMEOUT_S", "9") == "9"


def test_first_progress_1500_read_from_env_file_and_os_environ(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-001: BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S=1500 виден из .env и из os.environ."""
    env = _env_file(tmp_path, f"export {FIRST_KEY}='1500'  # heavy thinking\n")
    assert _facade(env).first_token_timeout_s == 1500.0
    monkeypatch.setenv(FIRST_KEY, "1800")
    assert _facade(env).first_token_timeout_s == 1800.0


@pytest.mark.parametrize("raw", ["abc", "0.5", "0", "-5", "3600.5", "nan", "inf", "-inf", ""])
def test_bounded_float_invalid_warns_and_falls_back_to_none(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, raw: str
) -> None:
    """AD-004/BND-001: невалидное/неконечное/вне [1, 3600] значение -> warning + None."""
    facade = _facade(_env_file(tmp_path, f"{FIRST_KEY}={raw}\n"))
    with caplog.at_level(logging.WARNING, logger="core.bridge_watchdog_settings"):
        assert facade.get_bounded_float((FIRST_KEY,)) is None
    assert facade.first_token_timeout_s is None
    if raw:
        assert any(r.levelno == logging.WARNING and FIRST_KEY in r.getMessage()
                   for r in caplog.records), "ожидался warning о невалидном значении"


@pytest.mark.parametrize(("raw", "expected"), [("1", 1.0), ("3600", 3600.0), ("1500.0", 1500.0)])
def test_bounded_float_accepts_exact_bounds(tmp_path: Path, raw: str, expected: float) -> None:
    """BND-001: границы [1.0, 3600.0] включительны."""
    facade = _facade(_env_file(tmp_path, f"{FIRST_KEY}={raw}\n"))
    assert facade.get_bounded_float((FIRST_KEY,)) == expected
    assert facade.first_token_timeout_s == expected


def test_missing_key_returns_none_without_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """QA-002: отсутствие настройки — штатный дефолт NonstreamConfig, без шума в логе."""
    facade = _facade(tmp_path / "missing.env")
    with caplog.at_level(logging.WARNING, logger="core.bridge_watchdog_settings"):
        assert facade.first_token_timeout_s is None
    assert not caplog.records


def test_facade_never_mutates_os_environ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-002/THREAT-001: чтение .env не мутирует os.environ (нулевая мутация)."""
    monkeypatch.setenv(IDLE_KEY, "55")
    before = dict(os.environ)
    facade = _facade(_env_file(tmp_path, f"{IDLE_KEY}=123\n{SECRET_KEY}=s\n{FIRST_KEY}=1500\n"))
    assert facade.get_setting(IDLE_KEY) == "55"
    assert facade.first_token_timeout_s == 1500.0
    assert dict(os.environ) == before


def test_facade_is_frozen_with_readonly_projection(tmp_path: Path) -> None:
    """AD-002: frozen dataclass и read-only MappingProxyType снимка."""
    facade = _facade(_env_file(tmp_path, f"{IDLE_KEY}=123\n"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        facade.first_token_timeout_s = 1.0  # pyright: ignore[reportAttributeAccessIssue]
    snapshot = facade.env_file_values
    with pytest.raises(TypeError):
        snapshot[IDLE_KEY] = "1"  # pyright: ignore[reportIndexIssue]


def test_positive_float_and_watchdog_enabled_keep_legacy_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """QA-002: legacy get_positive_float (fallback 600.0) и is_watchdog_enabled (дефолт on)."""
    facade = _facade(_env_file(tmp_path, "BRIDGE_IDLE_TIMEOUT_S=456\n"))
    assert facade.get_positive_float(IDLE_KEY, "BRIDGE_IDLE_TIMEOUT_S", 600.0) == 456.0
    missing = _facade(tmp_path / "missing.env")
    assert missing.get_positive_float(IDLE_KEY, "BRIDGE_IDLE_TIMEOUT_S", 600.0) == 600.0
    monkeypatch.setenv(IDLE_KEY, "-1")
    assert _facade(None).get_positive_float(IDLE_KEY, None, 600.0) == 600.0
    assert facade.is_watchdog_enabled() is True
    monkeypatch.setenv(WD_KEY, "off")
    assert _facade(None).is_watchdog_enabled() is False


def test_server_aliases_and_first_token_timeout_from_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-001/W2: свежий мост читает 1500 из ~/.dsh/.env; legacy-алиасы сохранены."""
    home = tmp_path / "home"
    (home / ".dsh").mkdir(parents=True)
    (home / ".dsh" / ".env").write_text(f"{FIRST_KEY}=1500\n", encoding="utf-8")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    module = load_bridge(monkeypatch)
    assert module.CLAUDE_P_BRIDGE_FIRST_TOKEN_TIMEOUT_S == 1500.0
    assert module._get_positive_float.__func__ is BridgeWatchdogFacade.get_positive_float
    assert module._get_positive_float.__self__ is module._WATCHDOG_SETTINGS
    assert module._is_watchdog_enabled.__func__ is BridgeWatchdogFacade.is_watchdog_enabled
    assert module._is_watchdog_enabled.__self__ is module._WATCHDOG_SETTINGS


def test_watchdog_for_passes_first_token_timeout_to_controller(
    bridge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-001/W2: `_watchdog_for` передаёт first_token_timeout_s в AdaptiveTimeoutController."""
    captured: dict[str, Any] = {}

    class CapturingController(FakeController):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            captured.update(kwargs)

        def register_pgid(self, pgid: int) -> None:
            captured["pgid"] = pgid

    monkeypatch.setattr(bridge, "CLAUDE_P_BRIDGE_FIRST_TOKEN_TIMEOUT_S", 1500.0)
    monkeypatch.setattr(bridge, "AdaptiveTimeoutController", CapturingController)
    assert bridge._watchdog_for(_fake_run()) is not None
    assert captured["first_token_timeout_s"] == 1500.0
    assert captured["idle_timeout_s"] == bridge.CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S
    assert captured["pgid"] == 4242


def test_soft_on_p_signal_survives_t120_and_expires_at_t1500(
    bridge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """QA-001: soft=on, first=1500 — P на t=2 переживает t=120 и истекает ровно на t=1500."""
    monkeypatch.setenv(FLAG_SOFT_LIVENESS, "true")
    monkeypatch.setattr(bridge, "CLAUDE_P_BRIDGE_FIRST_TOKEN_TIMEOUT_S", 1500.0)
    clock = FakeClock(1000.0)
    stub = StubWatchdog()

    def factory(**kwargs: Any) -> AdaptiveTimeoutController:
        return AdaptiveTimeoutController(watchdog=stub, clock=clock.monotonic, **kwargs)

    monkeypatch.setattr(bridge, "AdaptiveTimeoutController", factory)
    ctrl = bridge._watchdog_for(_fake_run())
    assert isinstance(ctrl, AdaptiveTimeoutController)
    assert stub.seeded == [4242]
    clock.advance(2.0)
    ctrl.liveness.record_signal("P")  # ранний процессный P-сигнал на t=2
    for target in (120.0, 1499.0):
        clock.now = 1000.0 + target
        assert ctrl.check(4242)[:2] == (False, "")
    clock.now = 1000.0 + 1500.0
    assert ctrl.check(4242)[:2] == (True, "idle_timeout")


def test_post_s_sliding_window_and_soft_off_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L-LIVE/v1 + QA-002: после S дедлайн скользит на idle_timeout_s; soft=off — legacy idle."""
    monkeypatch.setenv(FLAG_SOFT_LIVENESS, "true")
    clock = FakeClock(1000.0)
    ctrl = AdaptiveTimeoutController(
        idle_timeout_s=600.0, safety_cap_s=7200.0, watchdog=StubWatchdog(),
        clock=clock.monotonic, first_token_timeout_s=1500.0,
    )
    clock.advance(1400.0)
    ctrl.record_activity("text")  # S на t=1400 -> дедлайн t=2000 (1400+600)
    clock.now = 1000.0 + 1500.0
    assert ctrl.check(4242)[:2] == (False, ""), "после S окно обязано скользить, а не рвать на 1500"
    clock.now = 1000.0 + 1999.0
    assert ctrl.check(4242)[:2] == (False, "")
    clock.now = 1000.0 + 2000.0
    assert ctrl.check(4242)[:2] == (True, "idle_timeout")

    monkeypatch.delenv(FLAG_SOFT_LIVENESS, raising=False)
    clock2 = FakeClock(1000.0)
    legacy = AdaptiveTimeoutController(
        idle_timeout_s=600.0, safety_cap_s=7200.0, watchdog=StubWatchdog(),
        clock=clock2.monotonic, first_token_timeout_s=1500.0,
    )
    clock2.advance(601.0)
    assert legacy.check(4242)[:2] == (True, "idle_timeout"), "soft=off обязан сохранить legacy idle_timeout_s"

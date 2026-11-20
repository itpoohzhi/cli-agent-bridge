"""L1: kill-switch флаги и числовые параметры (AD-007, VER-009). Только tmp_path и monkeypatch."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import core.recovery_flags as rf  # noqa: E402
from core.transport_failure_contracts import FLAG_ENV_BY_FIELD, RetryBudgetConfig  # noqa: E402
from core.turn_resolution_report import flags_snapshot_dict  # noqa: E402

_FLAG = "BRIDGE_TOOLCALL_ERROR_RECOVERY_ENABLED"
_NAMES = tuple(name for _, name in FLAG_ENV_BY_FIELD)


@pytest.fixture
def cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Изолированный dynamic_config: живой ~/.config не читается; env флагов очищен."""
    path = tmp_path / "dynamic_config.json"
    monkeypatch.setenv(rf.CONFIG_PATH_ENV, str(path))
    for name in _NAMES:
        monkeypatch.delenv(name, raising=False)
    return path


def _write(path: Path, data: object) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_six_flags_exist_with_architecture_names() -> None:
    assert _NAMES == (
        "BRIDGE_TRANSPORT_FAILURE_CLASSIFIER_ENABLED",
        "BRIDGE_KEEPALIVE_ONLY_PRERETRY_ENABLED",
        "BRIDGE_RETRY_WINDOW_PAUSE_ENABLED",
        "BRIDGE_HOT_SESSION_RETAIN_ON_TRANSIENT_ENABLED",
        "BRIDGE_TOOLCALL_ERROR_RECOVERY_ENABLED",
        "BRIDGE_VENDOR_RETRY_PHRASE_MASK_ENABLED",
    )


def test_all_flags_default_false_without_any_source(cfg: Path) -> None:
    snap = rf.read_recovery_flags()
    assert not any(flags_snapshot_dict(snap).values())
    assert rf.read_recovery_switch(_FLAG) is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on", " On "])
def test_env_true_enables(cfg: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(_FLAG, value)
    assert rf.read_recovery_switch(_FLAG) is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "maybe", "2", "enabled"])
def test_env_other_values_are_veto(cfg: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(_FLAG, value)
    assert rf.read_recovery_switch(_FLAG) is False


def test_config_true_enables_without_env(cfg: Path) -> None:
    _write(cfg, {_FLAG: True})
    assert rf.read_recovery_switch(_FLAG) is True


@pytest.mark.parametrize("value", [False, "true", 1, None, [], {}])
def test_config_non_true_value_is_veto(cfg: Path, monkeypatch: pytest.MonkeyPatch, value: object) -> None:
    monkeypatch.setenv(_FLAG, "true")
    _write(cfg, {_FLAG: value})
    assert rf.read_recovery_switch(_FLAG) is False


def test_env_false_vetoes_config_true(cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(cfg, {_FLAG: True})
    monkeypatch.setenv(_FLAG, "false")
    assert rf.read_recovery_switch(_FLAG) is False


def test_config_false_vetoes_env_true(cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(cfg, {_FLAG: False})
    monkeypatch.setenv(_FLAG, "true")
    assert rf.read_recovery_switch(_FLAG) is False


def test_unrelated_config_keys_are_neutral(cfg: Path) -> None:
    _write(cfg, {"something_else": False})
    assert rf.read_recovery_switch(_FLAG) is False


@pytest.mark.parametrize("raw", ["{broken", "", "[]", "null", "42", '"str"', "\xff\xfe"])
def test_broken_or_non_object_config_is_fail_closed(cfg: Path, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv(_FLAG, "true")
    cfg.write_bytes(raw.encode("latin-1"))
    assert rf.read_recovery_switch(_FLAG) is False
    assert not any(flags_snapshot_dict(rf.read_recovery_flags()).values())


def test_symlink_config_is_fail_closed(cfg: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = tmp_path / "real.json"
    _write(real, {_FLAG: True})
    cfg.symlink_to(real)
    monkeypatch.setenv(_FLAG, "true")
    assert rf.read_recovery_switch(_FLAG) is False


def test_fifo_config_is_fail_closed_without_hanging(cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    os.mkfifo(cfg)
    monkeypatch.setenv(_FLAG, "true")
    assert rf.read_recovery_switch(_FLAG) is False


def test_directory_config_is_fail_closed(cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg.mkdir()
    monkeypatch.setenv(_FLAG, "true")
    assert rf.read_recovery_switch(_FLAG) is False


def test_oversize_config_is_fail_closed(cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(cfg, {_FLAG: True, "pad": "x" * 4096})
    monkeypatch.setenv(rf.CONFIG_MAX_BYTES_ENV, "1024")
    assert rf.read_recovery_switch(_FLAG) is False
    monkeypatch.setenv(rf.CONFIG_MAX_BYTES_ENV, "65536")
    assert rf.read_recovery_switch(_FLAG) is True


def test_toggle_false_true_false_without_restart(cfg: Path) -> None:
    """Чтение свежее на каждый вызов: переключение без рестарта процесса."""
    _write(cfg, {_FLAG: False})
    first = rf.read_recovery_switch(_FLAG)
    _write(cfg, {_FLAG: True})
    second = rf.read_recovery_switch(_FLAG)
    _write(cfg, {_FLAG: False})
    third = rf.read_recovery_switch(_FLAG)
    assert (first, second, third) == (False, True, False)


def test_flags_are_independent(cfg: Path) -> None:
    _write(cfg, {_NAMES[0]: True, _NAMES[3]: True})
    snap = flags_snapshot_dict(rf.read_recovery_flags())
    assert [n for n, on in snap.items() if on] == [_NAMES[0], _NAMES[3]]


def test_snapshot_uses_injected_env_mapping_and_path(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    _write(path, {_NAMES[1]: True})
    snap = rf.read_recovery_flags({_NAMES[2]: "true"}, path)
    assert (snap.keepalive_only_preretry, snap.retry_window_pause, snap.toolcall_error_recovery) == (True, True, False)


def test_retry_budget_defaults_and_env_override(cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert rf.read_retry_budget_config() == RetryBudgetConfig()
    monkeypatch.setenv("BRIDGE_RETRY_PAUSE_MAX_S", "7.5")
    monkeypatch.setenv("BRIDGE_PRERETRY_MAX_RETRIES", "3")
    out = rf.read_retry_budget_config()
    assert (out.pause_max_s, out.max_retries) == (7.5, 3)


@pytest.mark.parametrize("raw", ["abc", "nan", "inf", "-5", "1e99", ""])
def test_invalid_numbers_fall_back_to_safe_default(cfg: Path, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("BRIDGE_RETRY_TOTAL_BUDGET_S", raw)
    assert rf.read_retry_budget_config().retry_total_budget_s == RetryBudgetConfig().retry_total_budget_s


def test_number_from_config_when_env_absent(cfg: Path) -> None:
    _write(cfg, {"BRIDGE_CLIENT_TIMEOUT_S": 120})
    assert rf.read_retry_budget_config().client_timeout_s == 120.0


def test_transport_failure_config_reads_limit_and_custom_patterns(cfg: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_TRANSPORT_FAILURE_MAX_CHARS", "500")
    monkeypatch.setenv("BRIDGE_TRANSPORT_TRANSIENT_PATTERNS", "alpha||beta|| ")
    out = rf.read_transport_failure_config()
    assert out.max_chars == 500
    assert out.transient_patterns == ("alpha", "beta", " ")
    monkeypatch.delenv("BRIDGE_TRANSPORT_TRANSIENT_PATTERNS")
    assert rf.read_transport_failure_config().transient_patterns


def test_no_module_level_state_survives_between_reads(cfg: Path) -> None:
    _write(cfg, {_FLAG: True})
    assert rf.read_recovery_switch(_FLAG) is True
    cfg.unlink()
    assert rf.read_recovery_switch(_FLAG) is False

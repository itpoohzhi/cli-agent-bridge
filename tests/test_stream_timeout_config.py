"""Регрессии безопасной настройки таймаута записи SSE."""

from __future__ import annotations

import dataclasses
import json
import math
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

import server
from core import runtime_env
from core.cli_runtime_config import (
    FLAG_NEUTRAL_NAMES,
    CliRuntimeConfig,
    cli_label,
    NonstreamConfig,
    WatchdogConfig,
    cli_number,
)
from core.runtime_env import (
    ConfigError,
    DynamicFlagSource,
    NumSpec,
    bounded_int,
    env_bool,
    env_first,
    flag_enabled,
    parse_number,
    positive_int,
)


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_live_write_timeout_default(
    monkeypatch: pytest.MonkeyPatch, raw: str | None
) -> None:
    if raw is None:
        monkeypatch.delenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", raising=False)
    else:
        monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", raw)
    assert server.parse_live_write_timeout() == 30.0


@pytest.mark.parametrize(
    "raw, expected", [("45.5", 45.5), (" 45.5 ", 45.5), ("1", 1.0), ("300", 300.0)]
)
def test_live_write_timeout_valid(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: float
) -> None:
    monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", raw)
    assert server.parse_live_write_timeout() == expected


@pytest.mark.parametrize(
    "raw", ["0", "-1", "0.99", "300.01", "inf", "-inf", "nan", "invalid"]
)
def test_live_write_timeout_invalid_fails_fast(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    """ADR-0015 (F-003): невалидное значение — ConfigError, как у `CLI_CFG` (exit 78 в start.sh)."""
    monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", raw)
    with pytest.raises(ConfigError):
        server.parse_live_write_timeout()
    with pytest.raises(ConfigError):
        CliRuntimeConfig.from_env()


# ---------------------------------------------------------------------------
# ADR-0015 (VER-002): числовые конфиги, alias-каскады, fail-fast, динамические флаги
# ---------------------------------------------------------------------------

_SECRET = "SECRET-VALUE-123"
_N = "BRIDGE_NONSTREAM_"
_W = "BRIDGE_WATCHDOG_"


@dataclasses.dataclass(frozen=True)
class Row:
    """Строка таблицы ADR: параметр конфигурации, каскад имён, default и диапазон."""

    factory: Callable[[Mapping[str, str]], Any]
    attr: str
    canonical: str
    legacy: tuple[str, ...]
    default: float
    low: float
    high: float
    low_open: bool = False
    integer: bool = False

    @property
    def id(self) -> str:
        return self.canonical

    def mid(self, k: float) -> float:
        value = self.low + (self.high - self.low) * k
        return int(value) if self.integer else value


def _row(factory: Any, attr: str, canonical: str, legacy: tuple[str, ...], default: float,
         low: float, high: float, **kw: Any) -> Row:
    return Row(factory, attr, canonical, legacy, default, low, high, **kw)


_NS = NonstreamConfig.from_env
_WD = WatchdogConfig.from_env
_CLI = CliRuntimeConfig.from_env
_CLI_PREFIX = "BRIDGE_CLI_"

ROWS_AD002: list[Row] = [
    _row(_NS, "first_progress_timeout_s", _N + "FIRST_PROGRESS_TIMEOUT_S", (), 90, 1, 3600),
    _row(_NS, "idle_timeout_s", _N + "IDLE_TIMEOUT_S", ("BRIDGE_IDLE_TIMEOUT_S",), 300, 1, 3600),
    _row(_NS, "soft_budget_s", _N + "SOFT_LIVENESS_BUDGET_S", (), 120, 0, 3600),
    _row(_NS, "min_cpu_delta_s", _N + "SOFT_LIVENESS_MIN_CPU_DELTA_S", (), 0.05, 0, 60, low_open=True),
    _row(_NS, "safety_cap_s", _N + "SAFETY_CAP_S", (), 3600, 1, 86400),
    _row(_NS, "poll_interval_s", _N + "POLL_INTERVAL_S", ("BRIDGE_PASSTHROUGH_POLL_INTERVAL_S",), 0.1, 0.01, 10),
    _row(_WD, "idle_timeout_s", _W + "IDLE_TIMEOUT_S", (), 300, 1, 3600),
    _row(_WD, "safety_cap_s", _W + "SAFETY_CAP_S", ("DROID_DSH_BRIDGE_SAFETY_CAP_S",), 3600, 1, 86400),
    _row(_WD, "finish_reserve_s", _W + "FINISH_RESERVE_S", (), 35, 0, 600),
    _row(_WD, "interval_s", _W + "INTERVAL_S", (), 5, 0.1, 60),
    _row(_WD, "ps_timeout_s", _W + "PS_TIMEOUT_S", (), 2, 0.1, 60),
]

ROWS_AD004: list[Row] = [
    _row(_CLI, "first_token_timeout_s", "BRIDGE_CLI_FIRST_TOKEN_TIMEOUT_S", ("DROID_BRIDGE_FIRST_TOKEN_TIMEOUT_S",), 90, 1, 3600),
    _row(_CLI, "live_write_timeout_s", "BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S", ("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S",), 30, 1, 300),
    _row(_CLI, "silence_watchdog_s", "BRIDGE_CLI_SILENCE_WATCHDOG_S", ("DROID_BRIDGE_SILENCE_WATCHDOG_S",), 120, 1, 3600),
    _row(_CLI, "rpc_call_timeout_s", "BRIDGE_CLI_RPC_CALL_TIMEOUT_S", ("DROID_BRIDGE_RPC_CALL_TIMEOUT_S",), 60, 1, 3600),
    _row(_CLI, "idle_seconds", "BRIDGE_CLI_IDLE_SECONDS", ("DROID_DSH_BRIDGE_IDLE_SECONDS",), 2700, 1, 86400),
    _row(_CLI, "max_rpc_line_bytes", "BRIDGE_CLI_MAX_RPC_LINE_BYTES", ("DROID_BRIDGE_MAX_RPC_LINE_BYTES",), 8388608, 1024, 268435456, integer=True),
    _row(_CLI, "max_stderr_bytes", "BRIDGE_CLI_MAX_STDERR_BYTES", ("DROID_BRIDGE_MAX_STDERR_BYTES",), 65536, 1024, 16777216, integer=True),
    _row(_CLI, "max_inbox_bytes", "BRIDGE_CLI_MAX_INBOX_BYTES", ("DROID_BRIDGE_MAX_INBOX_BYTES",), 4194304, 1024, 268435456, integer=True),
    _row(_CLI, "max_turn_text_bytes", "BRIDGE_CLI_MAX_TURN_TEXT_BYTES", ("DROID_BRIDGE_MAX_TURN_TEXT_BYTES",), 10485760, 1024, 1073741824, integer=True),
    _row(_CLI, "run_queue_maxsize", "BRIDGE_CLI_RUN_QUEUE_MAXSIZE", ("DROID_BRIDGE_RUN_QUEUE_MAXSIZE",), 1024, 1, 65536, integer=True),
    _row(_CLI, "max_json_struct_tokens", "BRIDGE_CLI_MAX_JSON_STRUCT_TOKENS", ("DROID_BRIDGE_MAX_JSON_STRUCT_TOKENS",), 50000, 1, 10000000, integer=True),
    _row(_CLI, "max_delivery_bytes", "BRIDGE_CLI_MAX_DELIVERY_BYTES", ("DROID_BRIDGE_MAX_DELIVERY_BYTES",), 268435456, 1048576, 4294967296, integer=True),
    _row(_CLI, "max_chats", "BRIDGE_CLI_MAX_CHATS", ("DROID_BRIDGE_MAX_CHATS",), 4096, 1, 65536, integer=True),
]

ALL_ROWS = ROWS_AD002 + ROWS_AD004
_ROW_IDS = [f"{r.factory.__qualname__.split('.')[0]}:{r.canonical}" for r in ALL_ROWS]
rows = pytest.mark.parametrize("row", ALL_ROWS, ids=_ROW_IDS)


def _get(row: Row, env: Mapping[str, str]) -> Any:
    return getattr(row.factory(env), row.attr)


def _assert_value(row: Row, got: Any, expected: float) -> None:
    assert got == pytest.approx(expected)
    assert isinstance(got, int if row.integer else float)
    assert not isinstance(got, bool)


def _assert_neutral_error(row: Row, env: Mapping[str, str], *forbidden: str) -> None:
    with pytest.raises(ConfigError) as info:
        row.factory(env)
    text = str(info.value)
    assert row.canonical in text
    assert _SECRET not in text
    for item in forbidden:
        assert item not in text


@rows
def test_row_default_when_unset(row: Row) -> None:
    _assert_value(row, _get(row, {}), row.default)
    assert getattr(row.factory({}), row.attr) == getattr(
        row.factory({row.canonical: "", **{n: "  " for n in row.legacy}}), row.attr
    )


@rows
def test_row_canonical_name_is_read(row: Row) -> None:
    value = row.mid(0.25)
    _assert_value(row, _get(row, {row.canonical: str(value)}), value)
    _assert_value(row, _get(row, {row.canonical: f"  {value}  "}), value)


@rows
def test_row_legacy_aliases_in_priority_order(row: Row) -> None:
    first, second = row.mid(0.25), row.mid(0.5)
    for alias in row.legacy:
        _assert_value(row, _get(row, {alias: str(first)}), first)
    if len(row.legacy) > 1:
        env = {row.legacy[0]: str(first), row.legacy[1]: str(second)}
        _assert_value(row, _get(row, env), first)


@rows
def test_row_canonical_beats_legacy(row: Row) -> None:
    canonical, legacy = row.mid(0.25), row.mid(0.75)
    env = {row.canonical: str(canonical), **{n: str(legacy) for n in row.legacy}}
    _assert_value(row, _get(row, env), canonical)


@rows
def test_row_empty_canonical_yields_to_legacy_or_default(row: Row) -> None:
    legacy = row.mid(0.5)
    for blank in ("", "   "):
        env = {row.canonical: blank}
        _assert_value(row, _get(row, env), row.default)
        for alias in row.legacy:
            _assert_value(row, _get(row, {**env, alias: str(legacy)}), legacy)


@rows
def test_row_invalid_canonical_does_not_fall_back_to_legacy(row: Row) -> None:
    env = {row.canonical: _SECRET, **{n: str(row.mid(0.5)) for n in row.legacy}}
    _assert_neutral_error(row, env)


@rows
def test_row_inclusive_exclusive_boundaries(row: Row) -> None:
    _assert_value(row, _get(row, {row.canonical: str(row.high)}), row.high)
    step = 1 if row.integer else 1e-3
    assert step  # шаг вне диапазона
    if row.low_open:
        _assert_neutral_error(row, {row.canonical: str(row.low)})
        _assert_value(row, _get(row, {row.canonical: "0.001"}), 0.001)
    else:
        _assert_value(row, _get(row, {row.canonical: str(row.low)}), row.low)
        _assert_neutral_error(row, {row.canonical: str(row.low - step)})
    _assert_neutral_error(row, {row.canonical: str(row.high + step)})


@rows
def test_row_nonsense_values_fail_fast_without_leaking_value(row: Row) -> None:
    bad = [_SECRET, "abc", "inf", "-inf", "nan", "Infinity", "1e999", "1,5", "0x10"]
    if row.integer:
        bad.append(str(row.mid(0.5)) + ".5")
    for raw in bad:
        _assert_neutral_error(row, {row.canonical: raw}, raw if raw != "abc" else _SECRET)


@rows
def test_row_error_on_legacy_value_names_canonical_not_legacy(row: Row) -> None:
    for alias in row.legacy:
        with pytest.raises(ConfigError) as info:
            row.factory({alias: _SECRET})
        text = str(info.value)
        assert row.canonical in text
        assert alias not in text
        assert _SECRET not in text


@rows
def test_row_from_env_reads_process_environment_by_default(
    row: Row, monkeypatch: pytest.MonkeyPatch
) -> None:
    value = row.mid(0.5)
    monkeypatch.setenv(row.canonical, str(value))
    _assert_value(row, getattr(row.factory(None), row.attr), value)
    monkeypatch.setenv(row.canonical, _SECRET)
    with pytest.raises(ConfigError):
        row.factory(None)


def test_config_error_is_value_error() -> None:
    assert issubclass(ConfigError, ValueError)


def test_nonstream_defaults_exact() -> None:
    cfg = NonstreamConfig.from_env({})
    assert (
        cfg.first_progress_timeout_s,
        cfg.idle_timeout_s,
        cfg.soft_budget_s,
        cfg.min_cpu_delta_s,
        cfg.safety_cap_s,
        cfg.poll_interval_s,
    ) == (90.0, 300.0, 120.0, 0.05, 3600.0, 0.1)
    assert cfg == NonstreamConfig()


def test_watchdog_defaults_exact() -> None:
    cfg = WatchdogConfig.from_env({})
    assert (
        cfg.idle_timeout_s,
        cfg.safety_cap_s,
        cfg.finish_reserve_s,
        cfg.interval_s,
        cfg.ps_timeout_s,
    ) == (300.0, 3600.0, 35.0, 5.0, 2.0)
    assert cfg == WatchdogConfig()


def test_nonstream_zero_min_cpu_delta_is_invalid_but_zero_budget_is_valid() -> None:
    with pytest.raises(ConfigError, match="SOFT_LIVENESS_MIN_CPU_DELTA_S"):
        NonstreamConfig.from_env({_N + "SOFT_LIVENESS_MIN_CPU_DELTA_S": "0"})
    assert NonstreamConfig.from_env({_N + "SOFT_LIVENESS_BUDGET_S": "0"}).soft_budget_s == 0.0
    assert WatchdogConfig.from_env({_W + "FINISH_RESERVE_S": "0"}).finish_reserve_s == 0.0


def test_configs_are_frozen_and_settings_independent() -> None:
    ns, wd = NonstreamConfig.from_env({_N + "IDLE_TIMEOUT_S": "10"}), WatchdogConfig.from_env({})
    with pytest.raises(dataclasses.FrozenInstanceError):
        ns.idle_timeout_s = 1.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        wd.safety_cap_s = 1.0  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        CliRuntimeConfig().max_chats = 1  # type: ignore[misc]
    # BRIDGE_WATCHDOG_* и BRIDGE_NONSTREAM_* не влияют друг на друга
    assert wd.idle_timeout_s == 300.0
    assert WatchdogConfig.from_env({_N + "IDLE_TIMEOUT_S": "10"}).idle_timeout_s == 300.0
    assert NonstreamConfig.from_env({_W + "IDLE_TIMEOUT_S": "10"}).idle_timeout_s == 300.0


# --- CliRuntimeConfig: launcher, cli_number, labels ------------------------


def test_cli_defaults_exact_and_match_dataclass_defaults() -> None:
    cfg = CliRuntimeConfig.from_env({})
    assert cfg == CliRuntimeConfig()
    assert cfg.launcher == ""
    assert len(ROWS_AD004) == 13
    for row in ROWS_AD004:
        _assert_value(row, getattr(cfg, row.attr), row.default)


def test_cli_launcher_cascade() -> None:
    assert CliRuntimeConfig.from_env({}).launcher == ""
    assert CliRuntimeConfig.from_env({"DROID_LAUNCHER": "/opt/legacy.sh"}).launcher == "/opt/legacy.sh"
    both = {"BRIDGE_CLI_LAUNCHER": " /opt/new.sh ", "DROID_LAUNCHER": "/opt/legacy.sh"}
    assert CliRuntimeConfig.from_env(both).launcher == "/opt/new.sh"
    blank = {"BRIDGE_CLI_LAUNCHER": "  ", "DROID_LAUNCHER": "/opt/legacy.sh"}
    assert CliRuntimeConfig.from_env(blank).launcher == "/opt/legacy.sh"
    assert CliRuntimeConfig.from_env({"BRIDGE_CLI_LAUNCHER": "/opt/new.sh"}).launcher == "/opt/new.sh"


def test_cli_launcher_ignores_vendor_droid_bin() -> None:
    assert CliRuntimeConfig.from_env({"DROID_BIN": "/vendor/droid"}).launcher == ""
    env = {"DROID_BIN": "/vendor/droid", "DROID_LAUNCHER": "/opt/legacy.sh"}
    assert CliRuntimeConfig.from_env(env).launcher == "/opt/legacy.sh"


def test_cli_launcher_error_free_with_garbage_numbers_elsewhere_unset() -> None:
    # launcher не участвует в числовой валидации
    cfg = CliRuntimeConfig.from_env({"BRIDGE_CLI_LAUNCHER": _SECRET})
    assert cfg.launcher == _SECRET


@pytest.fixture
def isolated_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Динамический конфиг -> tmp (файла нет); env-флаги очищены."""
    path = tmp_path / "dynamic_config.json"
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(path))
    monkeypatch.delenv(FLAG_NEUTRAL_NAMES, raising=False)
    return path


def test_cli_number_is_fail_fast_and_keeps_cascade(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S", "DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S"):
        monkeypatch.delenv(name, raising=False)
    assert cli_number("live_write_timeout_s", 30.0) == 30.0
    assert cli_number("live_write_timeout_s", 12.5) == 12.5
    for bad in ("0", "-1", "0.99", "300.01", "inf", "nan", "invalid", _SECRET):
        monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", bad)
        with pytest.raises(ConfigError) as info:
            cli_number("live_write_timeout_s", 30.0)
        assert _SECRET not in str(info.value)
    monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", "45.5")
    assert cli_number("live_write_timeout_s", 30.0) == 45.5
    monkeypatch.setenv("BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S", "10")  # canonical главнее
    assert cli_number("live_write_timeout_s", 30.0) == 10.0
    monkeypatch.setenv("BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S", "bad")  # невалидный canonical -> ConfigError
    with pytest.raises(ConfigError):
        cli_number("live_write_timeout_s", 30.0)


def test_cli_number_matches_server_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S", raising=False)
    for raw in ("", "7", "300"):
        monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", raw)
        assert server.parse_live_write_timeout(30.0) == cli_number("live_write_timeout_s", 30.0)
    for raw in ("301", "x"):  # одинаковый fail-fast контракт (F-003)
        monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", raw)
        for call in (lambda: server.parse_live_write_timeout(30.0), lambda: cli_number("live_write_timeout_s", 30.0)):
            with pytest.raises(ConfigError):
                call()


_LEGACY_LABELS = {
    "exec": "droid exec",
    "no_event": "no droid event",
    "no_progress": "no droid progress",
    "completion_prefix": "chatcmpl-droid-",
    "bridge": "droid-bridge",
}
_NEUTRAL_LABELS = {
    "exec": "cli-exec",
    "no_event": "no CLI event",
    "no_progress": "no CLI progress",
    "completion_prefix": "chatcmpl-cli-",
    "bridge": "cli-agent-bridge",
}


def test_cli_label_legacy_by_default(isolated_flags: Path) -> None:
    for key, text in _LEGACY_LABELS.items():
        assert cli_label(key) == text


def test_cli_label_unknown_key_raises(isolated_flags: Path) -> None:
    with pytest.raises(KeyError):
        cli_label("nope")


@pytest.mark.parametrize("raw", ["true", "TRUE", "1", "yes", "on", " On "])
def test_cli_label_neutral_when_env_flag_on(
    isolated_flags: Path, monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv(FLAG_NEUTRAL_NAMES, raw)
    for key, text in _NEUTRAL_LABELS.items():
        assert cli_label(key) == text


@pytest.mark.parametrize("raw", ["", "false", "0", "no", "off", "garbage", "2"])
def test_cli_label_legacy_when_env_flag_not_truthy(
    isolated_flags: Path, monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv(FLAG_NEUTRAL_NAMES, raw)
    for key, text in _LEGACY_LABELS.items():
        assert cli_label(key) == text


def test_cli_label_flag_is_dynamic_without_restart(
    isolated_flags: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert cli_label("exec") == "droid exec"
    monkeypatch.setenv(FLAG_NEUTRAL_NAMES, "true")
    assert cli_label("exec") == "cli-exec"
    monkeypatch.setenv(FLAG_NEUTRAL_NAMES, "false")
    assert cli_label("exec") == "droid exec"
    monkeypatch.delenv(FLAG_NEUTRAL_NAMES)
    assert cli_label("completion_prefix") == "chatcmpl-droid-"


def test_cli_label_json_file_overrides_env(
    isolated_flags: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(FLAG_NEUTRAL_NAMES, "false")
    isolated_flags.write_text(json.dumps({FLAG_NEUTRAL_NAMES: True}))
    assert cli_label("bridge") == "cli-agent-bridge"
    monkeypatch.setenv(FLAG_NEUTRAL_NAMES, "true")
    isolated_flags.write_text(json.dumps({FLAG_NEUTRAL_NAMES: False}))
    assert cli_label("bridge") == "droid-bridge"  # файл главнее env, смена без рестарта
    isolated_flags.write_text(json.dumps({FLAG_NEUTRAL_NAMES: "true", "x": 1}))
    assert cli_label("bridge") == "cli-agent-bridge"


def test_cli_label_file_without_key_falls_back_to_env(
    isolated_flags: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    isolated_flags.write_text(json.dumps({"OTHER_FLAG": True}))
    assert cli_label("exec") == "droid exec"
    monkeypatch.setenv(FLAG_NEUTRAL_NAMES, "true")
    assert cli_label("exec") == "cli-exec"


@pytest.mark.parametrize("content", ["{not json", "", "[]", "null", '"true"', "42"])
def test_cli_label_corrupt_file_is_fail_closed(
    isolated_flags: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    monkeypatch.setenv(FLAG_NEUTRAL_NAMES, "true")
    isolated_flags.write_text(content)
    for key, text in _LEGACY_LABELS.items():
        assert cli_label(key) == text


# --- core.runtime_env -----------------------------------------------------------


def test_env_first_order_and_blank_handling() -> None:
    assert env_first({}, ("A", "B")) is None
    assert env_first({"A": "", "B": "  "}, ("A", "B")) is None
    assert env_first({"B": "2"}, ("A", "B")) == ("B", "2")
    assert env_first({"A": " 1 ", "B": "2"}, ("A", "B")) == ("A", "1")
    assert env_first({"A": "", "B": "2"}, ("A", "B")) == ("B", "2")
    assert env_first({"A": "1"}, ()) is None


def test_parse_number_types_defaults_and_ranges() -> None:
    f = NumSpec(("X", "Y"), 5, 1, 10)
    i = NumSpec(("X",), 5, 1, 10, integer=True)
    o = NumSpec(("X",), 1, 0, 10, low_open=True)
    assert parse_number({}, f) == 5.0 and isinstance(parse_number({}, f), float)
    assert parse_number({}, i) == 5 and isinstance(parse_number({}, i), int)
    assert parse_number({"Y": "2.5"}, f) == 2.5
    assert parse_number({"X": "1", "Y": "9"}, f) == 1.0
    assert parse_number({"X": "10"}, f) == 10.0
    assert parse_number({"X": "7"}, i) == 7
    for bad in ("0.99", "10.01", "nan", "inf", "-inf", "x", _SECRET):
        with pytest.raises(ConfigError, match=r"invalid config parameter: X$"):
            parse_number({"X": bad}, f)
    with pytest.raises(ConfigError):
        parse_number({"X": "1.0"}, i)
    with pytest.raises(ConfigError):
        parse_number({"X": "0"}, o)
    assert parse_number({"X": "0.0001"}, o) == 0.0001


def test_parse_number_never_returns_nonfinite() -> None:
    spec = NumSpec(("X",), 1, -math.inf, math.inf)
    for bad in ("nan", "inf", "-inf"):
        with pytest.raises(ConfigError):
            parse_number({"X": bad}, spec)


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", "Yes", "on", " on "])
@pytest.mark.parametrize("default", [True, False])
def test_env_bool_truthy(raw: str, default: bool) -> None:
    assert env_bool({"F": raw}, ("F",), default) is True


@pytest.mark.parametrize("raw", ["0", "false", "FALSE", "No", "off", " off "])
@pytest.mark.parametrize("default", [True, False])
def test_env_bool_falsy(raw: str, default: bool) -> None:
    assert env_bool({"F": raw}, ("F",), default) is False


@pytest.mark.parametrize("raw", ["", "  ", "maybe", "2", "tru"])
@pytest.mark.parametrize("default", [True, False])
def test_env_bool_unknown_or_blank_gives_default(raw: str, default: bool) -> None:
    assert env_bool({"F": raw}, ("F",), default) is default
    assert env_bool({}, ("F",), default) is default


def test_env_bool_alias_cascade() -> None:
    assert env_bool({"B": "true"}, ("A", "B"), False) is True
    assert env_bool({"A": "false", "B": "true"}, ("A", "B"), True) is False
    assert env_bool({"A": "", "B": "true"}, ("A", "B"), False) is True


def test_positive_int_soft_parsing() -> None:
    assert positive_int({}, "X", 7) == 7
    assert positive_int({"X": "3"}, "X", 7) == 3
    assert positive_int({"X": " 3 "}, "X", 7) == 3
    for bad in ("0", "-1", "1.5", "x", ""):
        assert positive_int({"X": bad}, "X", 7) == 7


def test_bounded_int_soft_parsing_inclusive_bounds() -> None:
    assert bounded_int({}, "X", 5, 1, 10) == 5
    assert bounded_int({"X": "1"}, "X", 5, 1, 10) == 1
    assert bounded_int({"X": "10"}, "X", 5, 1, 10) == 10
    for bad in ("0", "11", "x", "1.5", ""):
        assert bounded_int({"X": bad}, "X", 5, 1, 10) == 5


class _Loads:
    """Счётчик реальных чтений файла (`runtime_env._load_snapshot`)."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.count = 0
        real = runtime_env._load_snapshot

        def counting(path: str) -> dict:
            self.count += 1
            return real(path)

        monkeypatch.setattr(runtime_env, "_load_snapshot", counting)


@pytest.fixture
def dyn_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    path = tmp_path / "dyn.json"
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(path))
    monkeypatch.delenv("ADR15_DYN_FLAG", raising=False)
    return path


def test_dynamic_flag_source_caches_by_file_signature(dyn_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    loads = _Loads(monkeypatch)
    src = DynamicFlagSource("ADR15_DYN_FLAG")
    assert src.enabled() is False and loads.count == 0  # файла нет: чтения нет
    dyn_path.write_text(json.dumps({"ADR15_DYN_FLAG": True}))
    assert src.enabled() is True
    assert src.enabled() is True and src.enabled() is True
    assert loads.count == 1  # неизменный файл читается один раз
    dyn_path.write_text(json.dumps({"ADR15_DYN_FLAG": False, "pad": "xxxxxxxx"}))
    assert src.enabled() is False
    assert src.enabled() is False
    assert loads.count == 2
    dyn_path.unlink()
    assert src.enabled() is False
    assert loads.count == 2


def test_dynamic_flag_source_path_switch_reloads(
    dyn_path: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    loads = _Loads(monkeypatch)
    src = DynamicFlagSource("ADR15_DYN_FLAG")
    dyn_path.write_text(json.dumps({"ADR15_DYN_FLAG": True}))
    assert src.enabled() is True
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"ADR15_DYN_FLAG": False}))
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(other))
    assert src.enabled() is False
    assert loads.count == 2


def test_snapshot_cache_is_shared_across_sources_and_keyed_by_path(
    dyn_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loads = _Loads(monkeypatch)
    dyn_path.write_text(json.dumps({"ADR15_A": True, "ADR15_B": False}))
    assert DynamicFlagSource("ADR15_A").enabled() is True
    assert DynamicFlagSource("ADR15_B").enabled() is False
    assert loads.count == 1  # один снимок на путь для всех флагов


def test_snapshot_ttl_skips_stat_until_expiry(dyn_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    monkeypatch.setattr(runtime_env.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(runtime_env, "_SNAP_TTL_S", 0.5)
    dyn_path.write_text(json.dumps({"ADR15_DYN_FLAG": True}))
    src = DynamicFlagSource("ADR15_DYN_FLAG")
    assert src.enabled() is True
    dyn_path.write_text(json.dumps({"ADR15_DYN_FLAG": False, "pad": "xxxxxxxx"}))
    now[0] += 0.4
    assert src.enabled() is True  # TTL ещё не истёк: stat не выполнялся
    now[0] += 0.2
    assert src.enabled() is False  # TTL истёк: сигнатура изменилась


def test_snapshot_read_error_is_not_cached_and_recovers(dyn_path: Path) -> None:
    src = DynamicFlagSource("ADR15_DYN_FLAG")
    dyn_path.write_text("{broken")
    assert src.enabled() is False  # fail-closed
    dyn_path.write_text(json.dumps({"ADR15_DYN_FLAG": True}))
    assert src.enabled() is True  # починка подхватывается без рестарта
    dyn_path.chmod(0)
    try:
        assert src.enabled() is False  # chmod 000: fail-closed
    finally:
        dyn_path.chmod(0o600)
    assert src.enabled() is True  # chmod обратно: ошибка не закеширована


def test_parse_number_overflow_is_config_error() -> None:
    spec = NumSpec(("ADR15_BIG",), 1, 0, 10, integer=True)
    for raw in ("9" * 5000, "1e999", "-1e999"):
        with pytest.raises(ConfigError):
            parse_number({"ADR15_BIG": raw}, spec)


def test_dynamic_flag_source_value_semantics(
    dyn_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = DynamicFlagSource("ADR15_DYN_FLAG")
    monkeypatch.setenv("ADR15_DYN_FLAG", "true")
    assert src.enabled() is True  # нет файла -> env
    dyn_path.write_text("{}")
    assert src.enabled() is True  # ключа нет -> env
    dyn_path.write_text('{"ADR15_DYN_FLAG": false}')
    assert src.enabled() is False  # файл главнее env
    monkeypatch.delenv("ADR15_DYN_FLAG")
    for raw, expected in (
        ('{"ADR15_DYN_FLAG": "yes"}', True),
        ('{"ADR15_DYN_FLAG": "off"}', False),
        ('{"ADR15_DYN_FLAG": 1}', True),
        ('{"ADR15_DYN_FLAG": 0}', False),
        ('{"ADR15_DYN_FLAG": null}', False),
        ('{"ADR15_DYN_FLAG": true,  "k": 1}', True),
    ):
        dyn_path.write_text(raw)
        assert src.enabled() is expected, raw
    monkeypatch.setenv("ADR15_DYN_FLAG", "true")
    for broken in ("{oops", "[1, 2, 3]"):
        dyn_path.write_text(broken)
        assert src.enabled() is False, broken  # fail-closed


def test_dynamic_flag_source_default_path_under_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BRIDGE_DYNAMIC_CONFIG_PATH", raising=False)
    monkeypatch.delenv("ADR15_DYN_FLAG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    src = DynamicFlagSource("ADR15_DYN_FLAG")
    assert src.enabled() is False
    cfg = tmp_path / ".config" / "cli-agent-bridge"
    cfg.mkdir(parents=True)
    (cfg / "dynamic_config.json").write_text('{"ADR15_DYN_FLAG": true}')
    assert src.enabled() is True


def test_flag_enabled_shared_source_default_false_and_dynamic(
    dyn_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    name = "ADR15_FLAG_ENABLED_PROBE"
    monkeypatch.delenv(name, raising=False)
    assert flag_enabled(name) is False
    source = runtime_env._SOURCES[name]
    monkeypatch.setenv(name, "true")
    assert flag_enabled(name) is True
    monkeypatch.setenv(name, "false")
    assert flag_enabled(name) is False
    dyn_path.write_text(json.dumps({name: True}))
    assert flag_enabled(name) is True
    assert runtime_env._SOURCES[name] is source  # один общий источник на имя
    assert flag_enabled(name + "_OTHER") is False
    assert runtime_env._SOURCES[name + "_OTHER"] is not source

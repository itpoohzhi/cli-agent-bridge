"""Статические контрактные тесты совместимости fleet.json ↔ agy.real (AD-006 / REQ-002d, W2-B).

Проверяют: суффикс длительности `--print-timeout` в `AgyStreamJsonDriver.build_argv`,
выключенность резидентного драйвера по умолчанию, отсутствие второго live-пула
в `bridges/agy-bridge/` и валидность `fleet.json` с секцией `technical_ref` (read-only).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from adapters.stdio_drivers.agy_config import (
    FLAG_AGY_RESIDENT,
    is_agy_resident_enabled,
    load_agy_resident_config,
)
from adapters.stdio_drivers.agy_driver import AgyStreamJsonDriver

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "bridges" / "agy-bridge"
FLEET_PATH = BRIDGE_DIR / "fleet.json"


def _print_timeout_value(argv: list[str]) -> str:
    """Извлекает значение `--print-timeout` из argv (формы `flag value` и `flag=value`)."""
    for idx, item in enumerate(argv):
        if item == "--print-timeout":
            return argv[idx + 1]
        if item.startswith("--print-timeout="):
            return item.split("=", 1)[1]
    raise AssertionError(f"--print-timeout missing from argv: {argv!r}")


@pytest.mark.parametrize(
    ("options", "base"),
    [
        ({}, []),
        ({"print_timeout": 30}, []),
        ({"print_timeout": 120}, []),
        ({"print_timeout_s": 45}, []),
        ({"idle_timeout_s": 60}, []),
        ({"print_timeout": 30}, ["--print-timeout=0"]),
        ({"print_timeout": 120}, ["--print-timeout", "0"]),
    ],
)
def test_build_argv_print_timeout_has_duration_suffix(
    options: dict[str, object], base: list[str]
) -> None:
    """agy.real 1.5.18 принимает `--print-timeout` только с единицей длительности (`30s`)."""
    argv = AgyStreamJsonDriver().build_argv(list(base), options)
    val = _print_timeout_value(argv)
    assert re.fullmatch(r"\d+s", val), f"print-timeout without duration suffix: {val!r}"


def test_resident_driver_disabled_without_flag() -> None:
    """AGY_RESIDENT_ENABLED не задан -> универсальный драйвер выключен (fail-closed)."""
    assert FLAG_AGY_RESIDENT == "AGY_RESIDENT_ENABLED"
    assert is_agy_resident_enabled({}) is False
    assert load_agy_resident_config({}).enabled is False
    assert AgyStreamJsonDriver().config.enabled is False


@pytest.mark.parametrize("raw", ["0", "false", "off", "no", "disabled"])
def test_resident_flag_false_values_stay_disabled(raw: str) -> None:
    env = {FLAG_AGY_RESIDENT: raw}
    assert is_agy_resident_enabled(env) is False
    assert load_agy_resident_config(env).enabled is False


def test_other_agy_env_does_not_enable_resident() -> None:
    """Прочие AGY_* переменные не включают драйвер без явного kill-switch."""
    env = {"AGY_RESIDENT_MAX_SLOTS": "4", "AGY_RESIDENT_IDLE_TIMEOUT_S": "600"}
    assert is_agy_resident_enabled(env) is False
    assert load_agy_resident_config(env).enabled is False


def _bridge_python_files() -> list[Path]:
    files = sorted(BRIDGE_DIR.rglob("*.py"))
    assert files, f"no python files found under {BRIDGE_DIR}"
    assert BRIDGE_DIR / "server.py" in files
    return files


def test_bridge_has_no_second_resident_pool_wiring() -> None:
    """Один live pool: мост не импортирует agy_driver и не ссылается на AGY_RESIDENT_ENABLED."""
    offenders: list[str] = []
    for path in _bridge_python_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bagy_driver\b", text) or FLAG_AGY_RESIDENT in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"second resident pool wiring in bridge: {offenders}"


def test_bridge_server_uses_single_persistent_pool() -> None:
    """server.py опирается только на AgyPersistentWorkerPool, без второго пула драйвера."""
    text = (BRIDGE_DIR / "server.py").read_text(encoding="utf-8")
    assert "AgyPersistentWorkerPool" in text
    assert "adapters.stdio_drivers.agy_driver" not in text


def test_fleet_json_valid_with_technical_ref() -> None:
    """fleet.json — валидный JSON с секцией technical_ref; проверка строго read-only."""
    raw = FLEET_PATH.read_bytes()
    fleet = json.loads(raw)
    assert isinstance(fleet, dict)
    ref = fleet.get("technical_ref")
    assert isinstance(ref, dict), "fleet.json must contain technical_ref section"
    for key in ("agy_version", "agy_binary_path", "launcher_path", "invocation"):
        value = ref.get(key)
        assert isinstance(value, str) and value, f"technical_ref.{key} missing/empty"
    assert isinstance(fleet.get("models"), list) and fleet["models"]
    assert FLEET_PATH.read_bytes() == raw, "fleet.json must not be mutated by the check"

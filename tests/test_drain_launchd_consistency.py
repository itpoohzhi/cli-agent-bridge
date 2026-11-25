"""Contract tests (Wave 0 / VER-003) for launchd plist & Hub drain timeout consistency."""

from __future__ import annotations

import plistlib
from pathlib import Path
from typing import Any

import pytest

import core.lifecycle as lifecycle

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHD_DIR = REPO_ROOT / "deploy" / "launchd"
HUB_PLIST = LAUNCHD_DIR / "com.user.dsh-hub.plist"

HUB_DRAIN_TAIL_S = 7.0
HUB_DRAIN_MARGIN_S = 5.0


def _load_plist(path: Path) -> dict[str, Any]:
    data = plistlib.loads(path.read_bytes())
    assert isinstance(data, dict), f"{path.name}: root plist element must be a dict"
    return data


def test_hub_plist_exit_timeout_is_valid() -> None:
    """Hub launchd plist must declare integer ExitTimeOut >= 30 (expected 180)."""
    assert HUB_PLIST.is_file(), f"Missing hub plist: {HUB_PLIST}"
    plist = _load_plist(HUB_PLIST)
    assert "ExitTimeOut" in plist
    exit_timeout = plist["ExitTimeOut"]
    assert isinstance(exit_timeout, int) and not isinstance(exit_timeout, bool)
    assert exit_timeout >= 30
    assert exit_timeout == 180


def test_hub_plist_env_bridge_exit_timeout_matches_exit_timeout() -> None:
    """Hub plist EnvironmentVariables must declare BRIDGE_EXIT_TIMEOUT_S == ExitTimeOut."""
    plist = _load_plist(HUB_PLIST)
    exit_timeout = plist["ExitTimeOut"]
    env = plist.get("EnvironmentVariables")
    assert isinstance(env, dict)
    assert "BRIDGE_EXIT_TIMEOUT_S" in env
    assert int(env["BRIDGE_EXIT_TIMEOUT_S"]) == exit_timeout


def test_effective_hub_drain_timeout_default_is_not_clamped() -> None:
    """Default 110.0s drain under 180s ExitTimeOut stays 110.0s without clamping."""
    exit_timeout = _load_plist(HUB_PLIST)["ExitTimeOut"]
    fn = getattr(lifecycle, "effective_hub_drain_timeout_s", None)
    assert callable(fn), "core.lifecycle.effective_hub_drain_timeout_s is not defined"

    effective, clamped = fn(110.0, exit_timeout)
    assert effective == pytest.approx(110.0)
    assert clamped is False
    assert effective + HUB_DRAIN_TAIL_S + HUB_DRAIN_MARGIN_S <= exit_timeout


def test_effective_hub_drain_timeout_clamps_oversized_drain() -> None:
    """Configured drain above ExitTimeOut (e.g. ExitTimeOut + 120) is clamped."""
    exit_timeout = _load_plist(HUB_PLIST)["ExitTimeOut"]
    fn = getattr(lifecycle, "effective_hub_drain_timeout_s", None)
    assert callable(fn), "core.lifecycle.effective_hub_drain_timeout_s is not defined"

    configured_drain_s = float(exit_timeout + 120)
    expected_effective_s = float(exit_timeout) - HUB_DRAIN_TAIL_S - HUB_DRAIN_MARGIN_S
    effective, clamped = fn(configured_drain_s, exit_timeout)
    assert effective == pytest.approx(expected_effective_s)
    assert clamped is True
    assert effective + HUB_DRAIN_TAIL_S + HUB_DRAIN_MARGIN_S <= exit_timeout


def test_all_launchd_plists_valid_and_exit_timeout_consistent() -> None:
    """All deploy/launchd/*.plist must be valid XML with Label and consistent ExitTimeOut."""
    paths = sorted(LAUNCHD_DIR.glob("*.plist"))
    assert paths, f"No plist files found in {LAUNCHD_DIR}"
    assert HUB_PLIST in paths

    for path in paths:
        plist = _load_plist(path)
        label = plist.get("Label")
        assert isinstance(label, str) and label.strip(), f"{path.name}: empty Label"
        if "ExitTimeOut" not in plist:
            continue
        exit_timeout = plist["ExitTimeOut"]
        assert isinstance(exit_timeout, int) and not isinstance(exit_timeout, bool), (
            f"{path.name}: ExitTimeOut must be int"
        )
        assert exit_timeout > 0, f"{path.name}: ExitTimeOut must be positive"
        env = plist.get("EnvironmentVariables") or {}
        assert isinstance(env, dict), f"{path.name}: EnvironmentVariables must be dict"
        for key, value in env.items():
            if key == "BRIDGE_EXIT_TIMEOUT_S" or key.endswith("_EXIT_TIMEOUT_S"):
                assert int(value) <= exit_timeout, (
                    f"{path.name}: {key}={value} exceeds ExitTimeOut={exit_timeout}"
                )


@pytest.mark.parametrize(
    ("exit_timeout_s", "max_effective_s"),
    [("180", 168.0), ("60", 48.0)],
)
def test_hub_lifecycle_manager_clamps_drain_timeout_under_exit_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_timeout_s: str,
    max_effective_s: float,
) -> None:
    """HubLifecycleManager must clamp BRIDGE_DRAIN_TIMEOUT_S=300 under ExitTimeOut - 12."""
    monkeypatch.setenv("BRIDGE_DRAIN_TIMEOUT_S", "300")
    monkeypatch.setenv("BRIDGE_EXIT_TIMEOUT_S", exit_timeout_s)

    manager = lifecycle.HubLifecycleManager(state_dir=tmp_path)
    effective = getattr(manager, "effective_drain_timeout_s", manager.drain_timeout_s)
    if callable(effective):
        effective = effective()
    assert 0.0 < float(effective) <= max_effective_s

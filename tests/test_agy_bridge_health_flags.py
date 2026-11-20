"""Wiring AD-009 (W2-E): `flags_snapshot`, `git_head_sha` в `/health` и строка `turn-resolved` в логе."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from resilience_wiring_support import FLAG_ENVS, collect_log, enable, facade, load_server, use_config

SIX_ENVS = frozenset(FLAG_ENVS.values())


def test_runtime_fields_expose_default_off_snapshot_and_git_sha(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = use_config(monkeypatch, tmp_path)
    fields = load_server()._runtime_build_fields()  # pyright: ignore[reportPrivateUsage, reportAny]
    snapshot = fields["flags_snapshot"]
    assert set(snapshot) == SIX_ENVS and not any(snapshot.values())
    assert fields["resilience_flags"] == snapshot
    assert re.fullmatch(r"[0-9a-f]{40}", str(fields["git_head_sha"])), fields["git_head_sha"]
    assert "boot_ts" in fields and "agy_binary_sha256" in fields  # прежние поля не потеряны


def test_snapshot_follows_flags_without_restart(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    server = load_server()
    enable(monkeypatch, tmp_path, "recovery", "mask")
    on = server._runtime_build_fields()["flags_snapshot"]  # pyright: ignore[reportPrivateUsage, reportAny]
    assert {k for k, v in on.items() if v} == {FLAG_ENVS["recovery"], FLAG_ENVS["mask"]}
    _ = use_config(monkeypatch, tmp_path)
    assert not any(server._runtime_build_fields()["flags_snapshot"].values())  # pyright: ignore[reportPrivateUsage, reportAny]


def test_health_last_turn_resolved_line_lists_enabled_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    enable(monkeypatch, tmp_path, "pause")
    line = str(facade().health_fields()["last_turn_resolved"])
    assert line.startswith("turn-resolved reason=idle") and "flags_on=retry_window_pause" in line


def test_turn_resolved_logged_only_when_a_flag_is_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = use_config(monkeypatch, tmp_path)
    lines, log = collect_log()
    facade()._say(log, "retry_gate:retry_allowed", 1)  # pyright: ignore[reportPrivateUsage]
    assert lines == []  # все флаги выкл.: логи побайтно как в базе
    enable(monkeypatch, tmp_path, "pause")
    facade()._say(log, "retry_gate:retry_allowed", 1)  # pyright: ignore[reportPrivateUsage]
    assert len(lines) == 1 and "turn-resolved reason=retry.gate:retry.allowed" in lines[0]
    assert "\n" not in lines[0] and "attempts=1" in lines[0]


def test_broken_config_fails_closed_in_health(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ = use_config(monkeypatch, tmp_path, "{не json")
    monkeypatch.setenv(FLAG_ENVS["recovery"], "true")
    assert not any(load_server()._runtime_build_fields()["flags_snapshot"].values())  # pyright: ignore[reportPrivateUsage, reportAny]

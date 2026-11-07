"""Cycle 7 (Seat 2 F-004): отсутствующий `dynamic_config.json` не вызывает `stat()` на каждый SSE-чанк."""

from __future__ import annotations

from pathlib import Path

import pytest

import core.runtime_env as env
from adapters import passthrough_adapter as adapter


def test_missing_config_file_is_stat_ed_once_per_ttl(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    missing = str(tmp_path / "absent.json")
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", missing)
    monkeypatch.delenv("BRIDGE_PASSTHROUGH_SLIDING_WINDOW_ENABLED", raising=False)
    monkeypatch.setattr(env, "_SNAPSHOTS", {})
    monkeypatch.setattr(
        env, "_SNAP_TTL_S", 60.0
    )  # conftest обнуляет TTL: здесь нужен реальный кэш
    calls: list[str] = []
    real_stat = env.os.stat
    monkeypatch.setattr(
        env.os, "stat", lambda p, *a, **k: calls.append(str(p)) or real_stat(p, *a, **k)
    )
    source = env.DynamicFlagSource("BRIDGE_PASSTHROUGH_SLIDING_WINDOW_ENABLED")
    assert [source.enabled() for _ in range(500)] == [False] * 500
    assert calls.count(missing) == 1  # один `stat()` на TTL, а не на каждый чанк


def test_adapter_shares_one_module_level_flag_source() -> None:
    assert isinstance(adapter._SLIDING_WIN_FLAG, env.DynamicFlagSource)
    src = Path(adapter.__file__).read_text(encoding="utf-8")
    assert "DynamicFlagSource(FLAG_PASSTHROUGH_SLIDING_WINDOW).enabled" not in src

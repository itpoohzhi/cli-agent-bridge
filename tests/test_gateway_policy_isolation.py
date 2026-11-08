"""Регрессия: ошибки одного теста не карантинят модели следующих тестов."""

from __future__ import annotations

from pathlib import Path

import pytest

import server
from tests.bridge_testlib import BridgeCase


@pytest.mark.parametrize("round_id", (0, 1))
def test_penalty_state_is_private_and_fresh(tmp_path: Path, round_id: int) -> None:
    tracker = server._PENALTY_TRACKER
    assert tracker.storage_path == tmp_path / "penalties.json"
    assert tracker.get_model_status("claude-sonnet-5-5")["fails"] == 0
    tracker.manually_penalize("claude-sonnet-5-5", duration_s=60)
    assert tracker.is_penalized("claude-sonnet-5-5")[0] is True
    assert tracker.storage_path.is_file()


def test_runtime_policy_paths_do_not_point_to_owner_files(tmp_path: Path) -> None:
    assert server._QUOTA_CB_CACHE.path == tmp_path / "quota.json"
    assert server._MODEL_NOTES_FILTER.path == tmp_path / "notes.md"
    assert server._MODEL_NOTES_FILTER.is_blocked("claude-sonnet-5-5") is False


def test_subclass_cleanup_cannot_restore_stale_adapter() -> None:
    case = BridgeCase()
    original = server.BACKENDS
    case._save_server()
    case.addCleanup(case._restore_server)
    case.addCleanup(setattr, server, "BACKENDS", object())
    try:
        assert case.doCleanups() is True
        assert server.BACKENDS is original
    finally:
        server.BACKENDS = original

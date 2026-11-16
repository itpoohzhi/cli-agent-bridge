"""Регрессии стыка диагностики dev с hot reload и классификацией main."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from core.stream_interruption_recovery import is_recoverable_function_call_error
from tests.test_agy_clean_home import _load_bridge


@pytest.mark.parametrize(
    "name", ("antigravity-oauth-token", "antigravity-account.json")
)
def test_dev_credentials_rotate_and_logout_without_restart(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    """Ротация источника перекрывает свежую копию; logout удаляет только копию."""
    bridge = _load_bridge("agy_bridge_sync_main_dev_under_test")
    home, clean = tmp_path.resolve() / "home", tmp_path.resolve() / "clean"
    source_dir = home / ".gemini/antigravity-cli"
    source_dir.mkdir(parents=True)
    (home / "Library").mkdir()
    source = source_dir / name
    source.write_text("first-fixture", encoding="utf-8")
    for key, value in (
        ("HOME", home),
        ("CLEAN_HOME_DIR", clean),
        ("BRAIN_DIR", clean / ".gemini/antigravity-cli/brain"),
        ("CONV_DIR", clean / ".gemini/antigravity-cli/conversations"),
    ):
        monkeypatch.setattr(bridge, key, value)
    monkeypatch.setenv("AGY_AUTH_HOT_RELOAD_ENABLED", "1")
    assert bridge._prepare_agy_home() == clean
    copy = clean / ".gemini/antigravity-cli" / name
    assert copy.read_text(encoding="utf-8") == "first-fixture"
    copy.write_text("child-refreshed-fixture", encoding="utf-8")
    source.write_text("rotated-fixture-with-new-size", encoding="utf-8")
    assert bridge._prepare_agy_home() == clean
    assert copy.read_text(encoding="utf-8") == "rotated-fixture-with-new-size"
    assert stat.S_IMODE(copy.stat().st_mode) == 0o600
    source.unlink()
    bridge._prepare_agy_home()
    assert not copy.exists()


@pytest.mark.parametrize("raw", ("", "invalid", "0", "-1"))
def test_function_call_classification_invalid_limit_uses_default(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("BRIDGE_ERROR_CLASSIFY_MAX_CHARS", raw)
    assert is_recoverable_function_call_error("PT_AT_ERROR" + "x" * 5000)
    assert not is_recoverable_function_call_error("x" * 5000 + "PT_AT_ERROR")


def test_function_call_classification_limit_updates_between_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = "x" * 5000 + "PT_AT_ERROR"
    monkeypatch.setenv("BRIDGE_ERROR_CLASSIFY_MAX_CHARS", "4096")
    assert not is_recoverable_function_call_error(error)
    monkeypatch.setenv("BRIDGE_ERROR_CLASSIFY_MAX_CHARS", str(len(error)))
    assert is_recoverable_function_call_error(error)
    monkeypatch.setenv("BRIDGE_ERROR_CLASSIFY_MAX_CHARS", str(len(error) - 1))
    assert not is_recoverable_function_call_error(error)

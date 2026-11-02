"""Регрессии безопасной настройки таймаута записи SSE."""

from __future__ import annotations

import pytest

import server


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_live_write_timeout_default(
    monkeypatch: pytest.MonkeyPatch, raw: str | None
) -> None:
    monkeypatch.delenv("BRIDGE_CLIENT_WRITE_TIMEOUT_S", raising=False)
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
    monkeypatch.delenv("BRIDGE_CLIENT_WRITE_TIMEOUT_S", raising=False)
    monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", raw)
    assert server.parse_live_write_timeout() == expected


@pytest.mark.parametrize(
    "raw", ["0", "-1", "0.99", "300.01", "inf", "-inf", "nan", "invalid"]
)
def test_live_write_timeout_fallback(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.delenv("BRIDGE_CLIENT_WRITE_TIMEOUT_S", raising=False)
    monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", raw)
    assert server.parse_live_write_timeout() == 30.0
    assert server.parse_live_write_timeout(12.0) == 12.0


def test_live_write_timeout_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    """BRIDGE_CLIENT_WRITE_TIMEOUT_S приоритетнее legacy DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S."""
    # Валидный общий ключ побеждает legacy.
    monkeypatch.setenv("BRIDGE_CLIENT_WRITE_TIMEOUT_S", "45")
    monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", "60")
    assert server.parse_live_write_timeout() == 45.0

    # Невалидный общий ключ -> валидный legacy.
    for bad in ("invalid", "0", "500", "nan"):
        monkeypatch.setenv("BRIDGE_CLIENT_WRITE_TIMEOUT_S", bad)
        monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", "60")
        assert server.parse_live_write_timeout() == 60.0

    # Оба невалидны -> default.
    monkeypatch.setenv("BRIDGE_CLIENT_WRITE_TIMEOUT_S", "invalid")
    monkeypatch.setenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", "-1")
    assert server.parse_live_write_timeout() == 30.0
    assert server.parse_live_write_timeout(12.0) == 12.0

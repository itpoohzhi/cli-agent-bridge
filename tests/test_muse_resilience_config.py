from __future__ import annotations

import pytest

from adapters.muse_config import (
    DEFAULT_PROXY_PORT,
    get_muse_timeouts,
    resolve_proxy_port,
)


def test_default_proxy_port_is_positive() -> None:
    assert isinstance(DEFAULT_PROXY_PORT, int)
    assert DEFAULT_PROXY_PORT > 0


def test_resolve_proxy_port_prefers_explicit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_PROXY_PORT", "12345")
    assert resolve_proxy_port() == 12345


def test_resolve_proxy_port_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUSE_PROXY_PORT", raising=False)
    assert resolve_proxy_port() == DEFAULT_PROXY_PORT


def test_resolve_proxy_port_invalid_env_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MUSE_PROXY_PORT", "not-a-port")
    assert resolve_proxy_port() == DEFAULT_PROXY_PORT


def test_muse_timeouts_have_stream_write_timeout() -> None:
    timeouts = get_muse_timeouts()
    assert hasattr(timeouts, "stream_write_timeout_s")
    assert timeouts.stream_write_timeout_s > 0

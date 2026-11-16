"""Контракт конфигурационной цепочки resident stdio-пула."""

from __future__ import annotations

import pytest

from core.runtime_env import ConfigError
from core.stdio_resident.config import StdioPoolConfig


_ENV_TO_FIELD = {
    "BRIDGE_STDIO_MAX_SLOTS": "max_slots",
    "BRIDGE_STDIO_IDLE_TIMEOUT_S": "idle_timeout_s",
    "BRIDGE_STDIO_TTL_S": "ttl_s",
    "BRIDGE_STDIO_MAX_RSS_BYTES": "max_rss_bytes",
    "BRIDGE_STDIO_LEASE_WAIT_S": "lease_wait_s",
    "BRIDGE_STDIO_CANCEL_GRACE_S": "cancel_grace_s",
    "BRIDGE_STDIO_SHUTDOWN_TIMEOUT_S": "shutdown_timeout_s",
}


def test_from_env_loads_every_resident_runtime_limit() -> None:
    """W2j-AC1: каждый эксплуатационный лимит загружается из окружения."""

    config = StdioPoolConfig.from_env(
        {
            "BRIDGE_STDIO_MAX_SLOTS": "7",
            "BRIDGE_STDIO_IDLE_TIMEOUT_S": "41.5",
            "BRIDGE_STDIO_TTL_S": "1800.0",
            "BRIDGE_STDIO_MAX_RSS_BYTES": "2147483648",
            "BRIDGE_STDIO_LEASE_WAIT_S": "3.5",
            "BRIDGE_STDIO_CANCEL_GRACE_S": "1.5",
            "BRIDGE_STDIO_SHUTDOWN_TIMEOUT_S": "8.5",
            "BRIDGE_STDIO_RESIDENT_ENABLED": "true",
        }
    )

    assert config.max_slots == 7
    assert config.idle_timeout_s == 41.5
    assert config.ttl_s == 1800.0
    assert config.max_rss_bytes == 2147483648
    assert config.lease_wait_s == 3.5
    assert config.cancel_grace_s == 1.5
    assert config.shutdown_timeout_s == 8.5
    assert config.enabled is True


@pytest.mark.parametrize("invalid_value", ["-1", "not-a-number"])
def test_invalid_runtime_limits_raise_config_error(invalid_value: str) -> None:
    """W2j-AC2: невалидные эксплуатационные лимиты отклоняются fail-closed."""

    for env_name in _ENV_TO_FIELD:
        with pytest.raises(ConfigError):
            StdioPoolConfig.from_env({env_name: invalid_value})


def test_default_config_matches_safe_defaults() -> None:
    """W2j-AC3: пустое окружение сохраняет безопасные значения по умолчанию."""

    config = StdioPoolConfig.from_env({})
    defaults = StdioPoolConfig()
    assert config == defaults

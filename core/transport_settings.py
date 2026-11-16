"""Динамические флаги транспорта и проверяемые границы seed и credentials."""

from __future__ import annotations

import os
import secrets
import sys
import unicodedata
from collections import ChainMap
from collections.abc import Mapping
from dataclasses import dataclass

from core.runtime_env import (
    ConfigError,
    ConfigSnapshotError,
    NumSpec,
    env_bool,
    flag_enabled,
    parse_number,
    read_config_snapshot,
)

ROUTING_FLAG = "BRIDGE_TRANSPORT_ROUTING_ENABLED"
TEST_SEED_FLAG = "BRIDGE_TRANSPORT_TEST_SEED_ENABLED"


def routing_enabled() -> bool:
    """Читает общий DynamicFlagSource; ошибка снимка закрывает kill-switch."""
    return flag_enabled(ROUTING_FLAG)


def _test_seed_enabled(env: Mapping[str, str] | None) -> bool:
    if env is None:
        return flag_enabled(TEST_SEED_FLAG)
    # Явный env — изолированный ввод теста, а не изменение окружения процесса.
    return env_bool(env, (TEST_SEED_FLAG,), False)


def _runtime_values(env: Mapping[str, str] | None) -> Mapping[str, object]:
    if env is not None:
        return env
    path = os.environ.get("BRIDGE_DYNAMIC_CONFIG_PATH") or os.path.expanduser(
        "~/.config/cli-agent-bridge/dynamic_config.json"
    )
    try:
        snapshot = read_config_snapshot(path)
    except ConfigSnapshotError:
        raise ConfigError("invalid transport config snapshot") from None
    return ChainMap(snapshot or {}, os.environ)


def _positive_limit(values: Mapping[str, object], name: str, default: int) -> int:
    raw = values.get(name)
    source = {} if raw is None else {name: str(raw)}
    spec = NumSpec((name,), default, 1, sys.maxsize, integer=True)
    return int(parse_number(source, spec))


@dataclass(frozen=True, slots=True)
class TransportSettings:
    """Настройки из dynamic_config.json поверх env, без нового кэша.

    BRIDGE_TRANSPORT_SEED_MAX_BYTES: 1024 байта UTF-8, без усечения.
    BRIDGE_TRANSPORT_SEED_ENTROPY_BYTES: 32 байта ОС (256 бит), вывод в hex.
    BRIDGE_TRANSPORT_CREDENTIAL_MAX_BYTES: 8192 байта, включая перевод строки
    файла. Это безопасные fallback-границы, не заявление о production sizing.
    """

    seed_max_bytes: int = 1024
    seed_entropy_bytes: int = 32
    credential_max_bytes: int = 8192

    def __post_init__(self) -> None:
        for value in (
            self.seed_max_bytes,
            self.seed_entropy_bytes,
            self.credential_max_bytes,
        ):
            if type(value) is not int or not 0 < value <= sys.maxsize:
                raise ConfigError("invalid transport limit")
        if self.seed_entropy_bytes > self.seed_max_bytes // 2:
            raise ConfigError("transport entropy exceeds seed limit")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> TransportSettings:
        """Загружает актуальные лимиты; переданный env изолирует тест от ФС."""
        values = _runtime_values(env)
        defaults = cls()
        return cls(
            seed_max_bytes=_positive_limit(
                values, "BRIDGE_TRANSPORT_SEED_MAX_BYTES", defaults.seed_max_bytes
            ),
            seed_entropy_bytes=_positive_limit(
                values, "BRIDGE_TRANSPORT_SEED_ENTROPY_BYTES", defaults.seed_entropy_bytes
            ),
            credential_max_bytes=_positive_limit(
                values, "BRIDGE_TRANSPORT_CREDENTIAL_MAX_BYTES", defaults.credential_max_bytes
            ),
        )


def _validate_seed(value: object, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("transport_seed_invalid")
    if len(value) > limit:
        raise ValueError("transport_seed_too_large")
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value):
        raise ValueError("transport_seed_invalid")
    if len(value.encode("utf-8")) > limit:
        raise ValueError("transport_seed_too_large")
    return value


def _request_seeds(
    headers: Mapping[str, object], body: Mapping[str, object], limit: int
) -> tuple[str | None, str | None]:
    header_seed = None
    for name, value in headers.items():
        if name.lower() != "x-transport-seed":
            continue
        checked = _validate_seed(value, limit)
        if header_seed is not None and header_seed != checked:
            raise ValueError("transport_seed_conflicting_headers")
        header_seed = checked
    body_seed = _validate_seed(body["transport_seed"], limit) if "transport_seed" in body else None
    return header_seed, body_seed


def resolve_transport_seed(
    headers: Mapping[str, object],
    body: Mapping[str, object],
    env: Mapping[str, str] | None = None,
    settings: TransportSettings | None = None,
) -> str:
    """Выбирает header → body → test-only env → свежую энтропию ОС.

    Оба явных значения проверяются даже при приоритете заголовка. Входы не
    изменяются: удаление controls выполняет HTTP-граница независимо от флага.
    Request-id никогда не служит seed; значения и ошибки их не логируют.
    """
    limits = settings if settings is not None else TransportSettings.from_env(env)
    header_seed, body_seed = _request_seeds(headers, body, limits.seed_max_bytes)
    if header_seed is not None:
        return header_seed
    if body_seed is not None:
        return body_seed
    source = os.environ if env is None else env
    if _test_seed_enabled(env) and "BRIDGE_TRANSPORT_SEED" in source:
        return _validate_seed(source["BRIDGE_TRANSPORT_SEED"], limits.seed_max_bytes)
    return secrets.token_bytes(limits.seed_entropy_bytes).hex()

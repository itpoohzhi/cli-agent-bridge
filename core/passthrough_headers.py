"""Единая недоверенная граница заголовков перед outbound HTTP."""

from __future__ import annotations

from collections.abc import Mapping, Set as AbstractSet
from string import ascii_letters, digits
from typing import Final

SAFE_PUBLIC_X_HEADERS: Final[frozenset[str]] = frozenset(("x-request-id",))
SAFE_PUBLIC_X_PREFIXES: Final[tuple[str, ...]] = ("x-ratelimit-",)

_TOKEN_CHARS = frozenset(ascii_letters + digits + "!#$%&'*+-.^_`|~")
_HOP_HEADERS = frozenset(
    "connection keep-alive proxy-authenticate proxy-authorization "
    "proxy-connection te trailer trailers transfer-encoding upgrade".split()
)
_PRIVATE_HEADERS = frozenset(
    "authorization x-api-key cookie cookie2 host content-length accept-encoding "
    "x-transport-seed x-exclude-transports x-subagent-id x-internal-service-key "
    "x-bypass-model-filter x-turn-owner-token x-review-profile".split()
)


def _check_value(value: str) -> None:
    if not isinstance(value, str):
        raise ValueError("outbound_header_value_invalid")
    if any((ord(char) < 32 and char != "\t") or ord(char) == 127 for char in value):
        raise ValueError("outbound_header_value_invalid")
    try:
        value.encode("latin-1")
    except UnicodeEncodeError:
        raise ValueError("outbound_header_value_invalid") from None


def _checked_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Проверяет все значения до фильтрации, не включая их в ошибки."""
    checked: dict[str, tuple[str, str]] = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not name or not _TOKEN_CHARS.issuperset(name):
            raise ValueError("outbound_header_name_invalid")
        _check_value(value)
        lowered = name.lower()
        if lowered == "connection" and lowered in checked:
            value = checked[lowered][1] + "," + value
        checked[lowered] = (name, value)
    return dict(checked.values())


def _connection_headers(headers: Mapping[str, str]) -> frozenset[str]:
    return frozenset(
        token.strip().lower()
        for name, value in headers.items() if name.lower() == "connection"
        for token in value.split(",")
        if token.strip()
    )


def _filtered_headers(
    headers: Mapping[str, str], excluded: frozenset[str],
) -> dict[str, str]:
    return {
        name: value for name, value in headers.items()
        if name.lower() not in excluded
        and not name.lower().startswith(("x-bridge-", "x-internal-"))
    }


def outbound_headers(
    client: Mapping[str, str], configured: Mapping[str, str], credential: str,
) -> dict[str, str]:
    """Собирает заголовки; auth создаёт только credential выбранного route.

    Connection-токены обоих источников действуют на всё объединение. Повторный
    фильтр после overrides не позволяет настройкам вернуть control/auth headers.
    Host, framing и режим соединения задаёт только транспорт после этой границы.
    """
    incoming, overrides = _checked_headers(client), _checked_headers(configured)
    excluded = (
        _HOP_HEADERS | _PRIVATE_HEADERS
        | _connection_headers(incoming) | _connection_headers(overrides)
    )
    forwarded = _filtered_headers(incoming, excluded)
    merged = {name.lower(): (name, value) for name, value in forwarded.items()}
    merged.update((name.lower(), (name, value)) for name, value in overrides.items())
    forwarded = _filtered_headers(dict(merged.values()), excluded)
    if not isinstance(credential, str):
        raise ValueError("outbound_credential_invalid")
    if credential:
        if any(not 33 <= ord(char) <= 126 for char in credential):
            raise ValueError("outbound_credential_invalid")
        forwarded["Authorization"] = "Bearer " + credential
    return forwarded


def allow_client_response_header(
    name: str,
    blocked: AbstractSet[str],
    *,
    peer_is_loopback: bool,
    expose_internal: bool = True,
) -> bool:
    """Fail-closed allow-list для x-* на non-loopback: наружу идут только x-request-id и x-ratelimit-*."""
    low = name.lower()
    is_blocked = blocked.__contains__(low)
    is_public_x = any((SAFE_PUBLIC_X_HEADERS.__contains__(low), low.startswith(SAFE_PUBLIC_X_PREFIXES)))
    is_internal_x = all((low.startswith("x-"), not is_public_x))
    allowed = False
    if not is_blocked:
        allowed = all((peer_is_loopback, expose_internal)) if is_internal_x else True
    return allowed

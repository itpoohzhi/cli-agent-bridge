from __future__ import annotations

# Pure Zero-I/O policy for classifying client disconnect errors (P0-S4).
# No I/O, no clocks, no mutable module state; only ``errno`` from stdlib.

import errno
from typing import cast

DISCONNECT_EXC_TYPES = (
    BrokenPipeError,
    ConnectionResetError,
    ConnectionAbortedError,
)
DISCONNECT_ERRNOS = frozenset(
    {
        errno.EPIPE,
        errno.ECONNRESET,
        errno.ECONNABORTED,
        errno.ENOTCONN,
        errno.ESHUTDOWN,
    }
)

_PEER_FIELD_MAX_CHARS = 40
_LOG_LINE_MAX_CHARS = 78


def _iter_exception_chain(exc: BaseException) -> list[BaseException]:
    """Iteratively walk exc/__cause__/__context__/group members, cycle-safe."""
    seen: set[int] = set()
    stack: list[BaseException] = [exc]
    found: list[BaseException] = []
    while stack:
        current = stack.pop()
        marker = id(current)
        if marker in seen:
            continue
        seen.add(marker)
        found.append(current)
        stack.extend(
            child for child in (current.__cause__, current.__context__) if child
        )
        if isinstance(current, BaseExceptionGroup):
            stack.extend(current.exceptions)
    return found


def _matches_disconnect(
    exc: BaseException,
    client_gone_cls: type[BaseException] | tuple[type[BaseException], ...] | None,
) -> bool:
    return (
        (client_gone_cls is not None and isinstance(exc, client_gone_cls))
        or isinstance(exc, DISCONNECT_EXC_TYPES)
        or (isinstance(exc, OSError) and exc.errno in DISCONNECT_ERRNOS)
    )


def classify_client_disconnect(
    exc: BaseException,
    client_gone_cls: type[BaseException]
    | tuple[type[BaseException], ...]
    | None = None,
) -> bool:
    """True if exc or any linked/grouped exception signals a gone client."""
    return any(
        _matches_disconnect(linked, client_gone_cls)
        for linked in _iter_exception_chain(exc)
    )


def _sanitize_field(text: str, max_chars: int) -> str:
    cleaned = "".join(
        "_" if ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F else ch for ch in text
    )
    return cleaned[:max_chars]


def _peer_text(peer: object) -> str:
    if isinstance(peer, tuple):
        pair = cast("tuple[object, ...]", peer)
        return f"{pair[0]}:{pair[1]}" if len(pair) == 2 else str(pair)
    return str(peer)


def format_client_disconnect_log(peer: object, exc: BaseException) -> str:
    """Single sanitized line without the exception message text."""
    peer_field = _sanitize_field(_peer_text(peer), _PEER_FIELD_MAX_CHARS)
    exc_field = _sanitize_field(type(exc).__name__, _PEER_FIELD_MAX_CHARS)
    line = f"client_disconnected peer={peer_field} exc={exc_field}"
    return line[:_LOG_LINE_MAX_CHARS]


def should_suppress_disconnect_traceback(
    exc: BaseException,
    *,
    flag_enabled: bool,
    client_gone_cls: type[BaseException]
    | tuple[type[BaseException], ...]
    | None = None,
) -> bool:
    """Suppress traceback only when the flag is on AND the client is gone."""
    return bool(flag_enabled) and classify_client_disconnect(
        exc, client_gone_cls=client_gone_cls
    )

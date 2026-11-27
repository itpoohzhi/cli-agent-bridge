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

_PEER_FIELD_MAX_BYTES = 26
_EXC_FIELD_MAX_BYTES = 22
_LOG_LINE_MAX_BYTES = 78


_GoneCls = type[BaseException] | tuple[type[BaseException], ...] | None


def _is_disconnect_chain(
    exc: BaseException,
    gone_types: tuple[type[BaseException], ...],
    seen: frozenset[int],
) -> bool:
    """Walk explicit __cause__ links only (never __context__); groups require all leaves."""
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        path_seen = seen | {id(cur)}
        os_gone = isinstance(cur, OSError) and cur.errno in DISCONNECT_ERRNOS
        grp = cur.exceptions if isinstance(cur, BaseExceptionGroup) else ()
        grp_ok = bool(grp) and all(
            _is_disconnect_chain(s, gone_types, path_seen) for s in grp
        )
        if isinstance(cur, gone_types) or os_gone or grp_ok:
            return True
        seen = path_seen
        cur = cur.__cause__
    return False


def classify_client_disconnect(
    exc: BaseException,
    client_gone_cls: _GoneCls = None,
) -> bool:
    """True if exc, its explicit __cause__, or every leaf in a group is client-gone."""
    cls = client_gone_cls
    extra = (cls,) if isinstance(cls, type) else (cls or ())
    return _is_disconnect_chain(exc, extra + DISCONNECT_EXC_TYPES, frozenset())


def _sanitize_field(text: str, max_bytes: int) -> str:
    cleaned = "".join(ch if 0x21 <= ord(ch) <= 0x7E else "_" for ch in text)
    return cleaned[:max_bytes]


def _peer_text(peer: object) -> str:
    if isinstance(peer, tuple):
        pair = cast("tuple[object, ...]", peer)
        return f"{pair[0]}:{pair[1]}" if len(pair) == 2 else str(pair)
    return str(peer)


def format_client_disconnect_log(peer: object, exc: BaseException) -> str:
    """Single ASCII/UTF-8 bounded line (<=78 B) without the exception message text."""
    peer_field = _sanitize_field(_peer_text(peer), _PEER_FIELD_MAX_BYTES)
    exc_field = _sanitize_field(type(exc).__name__, _EXC_FIELD_MAX_BYTES)
    line = f"client_disconnected peer={peer_field} exc={exc_field}"
    return line.encode("utf-8")[:_LOG_LINE_MAX_BYTES].decode("utf-8", "ignore")


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

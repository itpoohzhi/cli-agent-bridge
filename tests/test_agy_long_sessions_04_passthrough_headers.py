"""Unit-тесты границы egress-заголовков core/passthrough_headers.py и core/runtime_env.py (W2, THREAT-001)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.passthrough_headers import (  # noqa: E402
    SAFE_PUBLIC_X_HEADERS,
    SAFE_PUBLIC_X_PREFIXES,
    allow_client_response_header,
)
from core.runtime_env import allow_hub_client_response_header  # noqa: E402


def test_core_modules_contain_zero_vendor_agy_references() -> None:
    for rel in ("core/passthrough_headers.py", "core/runtime_env.py"):
        text = (_ROOT / rel).read_text(encoding="utf-8").lower()
        assert "x-agy-" not in text
        assert "agy-conversation" not in text
    assert "x-request-id" in SAFE_PUBLIC_X_HEADERS
    assert "x-ratelimit-" in SAFE_PUBLIC_X_PREFIXES


def test_allow_client_response_header_fail_closed_for_non_loopback() -> None:
    blocked = frozenset(("transfer-encoding", "connection"))
    # Стандартные HTTP и разрешённые публичные x-* пропускаются всем
    assert allow_client_response_header("Content-Type", blocked, peer_is_loopback=False) is True
    assert allow_client_response_header("X-Request-Id", blocked, peer_is_loopback=False) is True
    assert allow_client_response_header("X-RateLimit-Remaining", blocked, peer_is_loopback=False) is True
    # Любые нестандартные x-* (включая X-Agy-Conversation-Id, X-Bridge-*, X-Internal-*, X-Future-*) блокируются наружу!
    for hdr in ("X-Agy-Conversation-Id", "X-Bridge-Trace", "X-Internal-Id", "X-Custom-Bridge"):
        assert allow_client_response_header(hdr, blocked, peer_is_loopback=False) is False
        assert allow_client_response_header(hdr, blocked, peer_is_loopback=True, expose_internal=True) is True
        assert allow_client_response_header(hdr, blocked, peer_is_loopback=True, expose_internal=False) is False
    # Заблокированные hop-by-hop всегда отклоняются даже на loopback
    assert allow_client_response_header("Connection", blocked, peer_is_loopback=True) is False


def test_allow_hub_client_response_header_safe_peer_and_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    peers = ("127.0.0.1", "::1")
    blocked = frozenset(("connection",))
    monkeypatch.delenv("BRIDGE_EXPOSE_INTERNAL_HEADERS", raising=False)

    h_local = SimpleNamespace(client_address=("127.0.0.1", 12345))
    h_ext = SimpleNamespace(client_address=("10.20.30.40", 12345))
    h_missing = SimpleNamespace()
    h_empty = SimpleNamespace(client_address=())

    assert allow_hub_client_response_header("X-Agy-Conversation-Id", blocked, h_local, peers) is True
    assert allow_hub_client_response_header("X-Agy-Conversation-Id", blocked, h_ext, peers) is False
    assert allow_hub_client_response_header("X-Agy-Conversation-Id", blocked, h_missing, peers) is False
    assert allow_hub_client_response_header("X-Agy-Conversation-Id", blocked, h_empty, peers) is False
    assert allow_hub_client_response_header("X-Request-Id", blocked, h_ext, peers) is True

    monkeypatch.setenv("BRIDGE_EXPOSE_INTERNAL_HEADERS", "0")
    assert allow_hub_client_response_header("X-Agy-Conversation-Id", blocked, h_local, peers) is False

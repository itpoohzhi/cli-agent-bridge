"""L1: классификатор транспортных сбоев (AD-001, VER-004, FM-09)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from core.transport_failure_classifier import classify_transport_failure  # noqa: E402
from core.transport_failure_contracts import (  # noqa: E402
    FailureKind,
    TransportFailureConfig,
)

_USERINFO = 'Get "https://www.googleapis.com/oauth2/v2/userinfo"'
_TRANSIENT = FailureKind.NETWORK_TRANSIENT


@pytest.mark.parametrize(
    "text",
    [
        f"Eligibility check failed: {_USERINFO}: EOF",
        f"{_USERINFO}: net/http: TLS handshake timeout",
        f"{_USERINFO}: unexpected EOF",
        "dial tcp 127.0.0.1:10830: i/o timeout",
        "dial tcp 127.0.0.1:10830: connect: connection refused",
        "read tcp 127.0.0.1:1->127.0.0.1:2: read: connection reset by peer",
        "connection reset",
        "Post https://x: context deadline exceeded",
        "NET/HTTP: TLS HANDSHAKE TIMEOUT",
        f"Eligibility check failed: {_USERINFO}:\nEOF",
        f"[{_USERINFO}]: EOF",
    ],
)
def test_go_network_forms_are_transient(text: str) -> None:
    result = classify_transport_failure(text)
    assert result.kind is _TRANSIENT
    assert result.matched


@pytest.mark.parametrize(
    "text",
    [
        "HTTP 400 Bad Request",
        "Request failed with status 401: EOF",
        "Eligibility check failed: 403 Forbidden: EOF",
        "HTTP 401 Unauthorized: TLS handshake timeout",
        "Bad Request is a term used here: EOF",
        "invalid model selection: gemini-x",
        "quota exceeded for project: connection reset by peer",
        "code=403 : EOF",
    ],
)
def test_fatal_forms_always_veto_transient_markers(text: str) -> None:
    """FM-09: фатальные формы остаются FATAL даже рядом с транзиентным маркером."""
    assert classify_transport_failure(text).kind is FailureKind.FATAL


@pytest.mark.parametrize("value", [None, "", "   ", "\n\t", [], 0, 12.5, {}, b"EOF"])
def test_dirty_inputs_are_unclassified(value: object) -> None:
    result = classify_transport_failure(value)
    assert result.kind is FailureKind.UNCLASSIFIED
    assert result.reason == "empty_or_non_text"


def test_plain_text_without_markers_is_unclassified() -> None:
    assert classify_transport_failure("model produced a long answer").kind is FailureKind.UNCLASSIFIED


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("userinfo%3A%20EOF", _TRANSIENT),
        ("userinfo%253A%2520EOF", _TRANSIENT),
        ("HTTP%20401%20Unauthorized: EOF", FailureKind.FATAL),
        ("HTTP%25252520401", FailureKind.UNCLASSIFIED),
    ],
)
def test_percent_encoded_obfuscation_is_decoded(text: str, kind: FailureKind) -> None:
    assert classify_transport_failure(text).kind is kind


def test_long_text_keeps_head_and_tail() -> None:
    """Текст > max_chars: маркер в хвосте (Go-ошибка) и фатальный в голове обнаруживаются."""
    filler = "x " * 5000
    assert classify_transport_failure(f"{filler} userinfo: EOF").kind is _TRANSIENT
    assert classify_transport_failure(f"HTTP 401 {filler} : EOF").kind is FailureKind.FATAL


def test_marker_in_discarded_middle_is_ignored() -> None:
    cfg = TransportFailureConfig(max_chars=40)
    text = "a" * 100 + " : EOF " + "b" * 100
    assert classify_transport_failure(text, cfg).kind is FailureKind.UNCLASSIFIED


def test_custom_transient_patterns_replace_defaults() -> None:
    cfg = TransportFailureConfig(transient_patterns=(r"upstream hiccup",))
    assert classify_transport_failure("upstream hiccup", cfg).kind is _TRANSIENT
    assert classify_transport_failure("userinfo: EOF", cfg).kind is FailureKind.UNCLASSIFIED


def test_invalid_fatal_pattern_fails_closed_never_transient() -> None:
    cfg = TransportFailureConfig(fatal_patterns=("(unclosed",))
    result = classify_transport_failure("userinfo: EOF", cfg)
    assert result.kind is FailureKind.UNCLASSIFIED
    assert result.reason == "invalid_fatal_pattern"


def test_invalid_transient_pattern_is_not_transient() -> None:
    cfg = TransportFailureConfig(transient_patterns=("[bad",))
    assert classify_transport_failure("userinfo: EOF", cfg).kind is FailureKind.UNCLASSIFIED


def test_classification_is_deterministic_and_pure() -> None:
    text = f"Eligibility check failed: {_USERINFO}: EOF"
    assert classify_transport_failure(text) == classify_transport_failure(text)
    assert classify_transport_failure(text).reason == "go_network_form"

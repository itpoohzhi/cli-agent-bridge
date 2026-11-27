"""F-001 barrier tests: Zero-Canon attestation validated before send_response(200)."""

from __future__ import annotations

import io
import json

import pytest

import core.zc_http_barrier as barrier
from core.zc_admission import is_valid_server_thread_id
from core.zero_canon_attestation_http import ZeroCanonAdmissionProof, ZeroCanonCompletionProof


class FakeHandler:
    """In-memory HTTP handler recording statuses, headers, ended, and wfile bytes."""

    def __init__(self, profile=None, proof=None):
        self.statuses: list[int] = []
        self.headers: list[tuple[str, str]] = []
        self.ended = 0
        self.wfile = io.BytesIO()
        self.telemetry: list[tuple[int, bool]] = []
        self._response_status = None
        self._review_profile = profile
        self._zero_canon_completion = proof
        self._zero_canon_admission = object()
        self._active_managed_turn = None

    def send_response(self, status):
        self.statuses.append(status)

    def send_header(self, key, value):
        self.headers.append((key, value))

    def end_headers(self):
        self.ended += 1

    def _telemetry_note(self, total, first_byte=False):
        self.telemetry.append((total, first_byte))

    def header(self, name):
        return next((v for k, v in self.headers if k == name), None)


def make_proof(thread_id="srv-thread-1", model="gpt-6.1-sol"):
    adm = ZeroCanonAdmissionProof(
        model=model, effort="high", thread_id=thread_id, turn_id="turn-1",
        clean_home_verified=True, handshake_acked=True,
    )
    return ZeroCanonCompletionProof(adm, terminal_status="completed")


def emit(handler, total=11, out=None):
    return barrier.emit_nonstream_headers(
        handler, total, [("X-Trace-Id", "t1")], ("X-Context-Pruned", "2"), out or {}
    )


def assert_framed(handler, status, body):
    assert handler.statuses == [status]
    assert handler._response_status == status
    assert handler.ended == 1
    assert handler.header("Content-Length") == str(len(body))
    assert handler.header("Content-Type") == "application/json; charset=utf-8"
    assert handler.telemetry == [(len(body), True)]
    assert handler.header("X-Zero-Canon-Attestation") is None


@pytest.mark.parametrize("profile", ["standard", None])
def test_non_zc_missing_proof_legacy_200(profile):
    h = FakeHandler(profile=profile)
    assert emit(h, total=42) is True
    assert h.statuses == [200] and h.ended == 1
    assert h.header("Content-Length") == "42"
    assert h.header("X-Zero-Canon-Attestation") is None
    assert h.header("X-Trace-Id") == "t1" and h.header("X-Context-Pruned") == "2"
    assert h._response_status == 200 and h.telemetry == [(42, True)]
    assert h.wfile.getvalue() == b""


def test_zc_valid_proof_single_200_with_attestation():
    proof = make_proof()
    h = FakeHandler(profile="Zero-Canon", proof=proof)
    assert emit(h, total=7) is True
    assert h.statuses == [200] and h.ended == 1
    assert "phase=completed" in h.header("X-Zero-Canon-Attestation")
    assert h.header("Content-Length") == "7"
    assert h._zero_canon_completion is None and h._zero_canon_admission is None
    assert h.wfile.getvalue() == b""


def test_zc_missing_proof_fails_closed_502():
    h = FakeHandler(profile="zero-canon")
    assert emit(h) is False
    body = h.wfile.getvalue()
    assert_framed(h, 502, body)
    assert json.loads(body)["error"]["code"] == "zero_canon_attestation_failed"
    assert 200 not in h.statuses


def test_zc_tool_calls_forbidden_502():
    h = FakeHandler(profile="zero-canon", proof=make_proof())
    assert emit(h, out={"tool_calls": [{"id": "c1"}]}) is False
    body = h.wfile.getvalue()
    assert_framed(h, 502, body)
    err = json.loads(body)["error"]
    assert err["code"] == "zero_canon_attestation_failed"
    assert "zero_canon_tool_calls_forbidden" in err["message"]


@pytest.mark.parametrize(
    ("proof", "fragment"),
    [
        (make_proof(model="gpt-9-unsupported"), "unsupported"),
        (make_proof(thread_id="probe"), "thread"),
        (make_proof(thread_id="th-1"), "thread"),
    ],
)
def test_zc_policy_or_thread_rejection_single_502(proof, fragment):
    h = FakeHandler(profile="zero-canon", proof=proof)
    assert emit(h) is False  # ValueError never propagates upward
    body = h.wfile.getvalue()
    assert_framed(h, 502, body)
    err = json.loads(body)["error"]
    assert err["code"] == "zero_canon_attestation_failed"
    assert fragment in err["message"].lower()
    assert h._zero_canon_completion is None and h._zero_canon_admission is None


def test_thread_id_validator_matches_probe_and_th_prefix():
    assert not is_valid_server_thread_id("probe")
    assert not is_valid_server_thread_id("th-1")
    assert is_valid_server_thread_id("srv-thread-1")


def test_zc_foreign_valueerror_non_ascii_message_502(monkeypatch):
    def boom(proof, *, phase=None):
        raise ValueError("политика нарушена: аттестация ✗")

    monkeypatch.setattr(barrier, "build_attestation_header", boom)
    h = FakeHandler(profile="zero-canon", proof=make_proof())
    assert emit(h) is False
    body = h.wfile.getvalue()
    assert_framed(h, 502, body)
    err = json.loads(body.decode("utf-8"))["error"]
    assert err["code"] == "zero_canon_attestation_failed"
    assert "политика нарушена" in err["message"]


@pytest.mark.parametrize("exc", [RuntimeError("boom"), TypeError("bad type")])
def test_zc_unexpected_internal_error_500_not_502(monkeypatch, exc):
    def boom(proof, *, phase=None):
        raise exc

    monkeypatch.setattr(barrier, "build_attestation_header", boom)
    h = FakeHandler(profile="zero-canon", proof=make_proof())
    assert emit(h) is False
    body = h.wfile.getvalue()
    assert_framed(h, 500, body)
    err = json.loads(body)["error"]
    assert err == {
        "message": "internal_attestation_error", "type": "server_error", "code": "internal_error"
    }
    assert 502 not in h.statuses


def test_zc_broken_pipe_during_200_commit_propagates():
    class BrokenHandler(FakeHandler):
        def send_response(self, status):
            super().send_response(status)
            if status == 200:
                raise BrokenPipeError("client gone")

    h = BrokenHandler(profile="zero-canon", proof=make_proof())
    with pytest.raises(BrokenPipeError):
        emit(h)
    assert h.statuses == [200]
    assert h.wfile.getvalue() == b""

"""C1-2: независимые примеры классификации тел и границ потокового протокола."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from random import Random
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.stream_outcome import StreamOutcomeClassifier, inspect_json_body

SSE = "text/event-stream; charset=utf-8"
JSON = "application/json"
DONE = b"data: [DONE]\r\n\r\n"


def frame(value: Any) -> bytes:
    return b"data: " + json.dumps(value, ensure_ascii=False).encode() + b"\r\n\r\n"


def answer(text: Any, field: str = "delta") -> dict[str, Any]:
    return {"choices": [{field: {"content": text}, "finish_reason": "stop"}]}


def chunks(body: bytes, width: int) -> Iterator[bytes]:
    random, offset = Random(508), 0
    while offset < len(body):
        size = width or random.randint(1, 19)
        yield body[offset : offset + size]
        offset += size


def classify(body: bytes, width: int, content_type: str = SSE) -> str:
    classifier = StreamOutcomeClassifier(status=200, content_type=content_type)
    for chunk in chunks(body, width):
        classifier.feed(chunk)
    return classifier.finish().kind.name


CASES = [
    (SSE, frame(answer("Ответ 😀: да\\нет")) + DONE, "OK"),
    (SSE, frame(answer("")) + DONE, "EMPTY"),
    (SSE, frame(answer(" \n\t")) + DONE, "EMPTY"),
    (SSE, DONE, "EMPTY"),
    (SSE, b"", "EMPTY"),
    (SSE, b": heartbeat\r\n\r\n", "EMPTY"),
    (
        SSE,
        frame({"choices": [{"delta": {"reasoning_content": "думаю"}}]}) + DONE,
        "EMPTY",
    ),
    (SSE, frame(answer("часть")), "STREAM_ERROR"),
    (SSE, b'data: {"choices":[{"delta":{"content":"partial', "STREAM_ERROR"),
    (SSE, frame(answer("ok")) + b"data: [DONE]", "STREAM_ERROR"),
    (SSE, frame({"error": {"message": "failed"}}) + DONE, "STREAM_ERROR"),
    (SSE, b'event: error\r\ndata: {"message":"failed"}\r\n\r\n' + DONE, "STREAM_ERROR"),
    (SSE, b"event: error\r\n\r\n" + DONE, "STREAM_ERROR"),
    (SSE, frame(answer("ok")) + frame({"error": "late"}) + DONE, "STREAM_ERROR"),
    (SSE, frame(answer("Quota ")) + frame(answer("exceeded: лимит")), "STREAM_ERROR"),
    (
        SSE,
        frame(answer("Quota ")) + frame(answer("exceeded: лимит")) + DONE,
        "QUOTA_TEXT",
    ),
    (SSE, frame(answer("ok")) + DONE + frame({"error": "late"}), "STREAM_ERROR"),
    (SSE, frame(answer("ok")) + DONE + b"data: broken\n\n", "STREAM_ERROR"),
    (SSE, b"data: \xff\n\n" + DONE, "STREAM_ERROR"),
    (
        JSON,
        json.dumps(answer("Успех 😀", "message"), ensure_ascii=False).encode(),
        "OK",
    ),
    (JSON, b'{"error":{"message":"failed"}}', "ERROR_BODY"),
    (JSON, b'{"error":{},"choices":[{"message":{"content":"ok"}}]}', "ERROR_BODY"),
    (JSON, json.dumps(answer("quota exceeded", "message")).encode(), "QUOTA_TEXT"),
    (JSON, json.dumps(answer("", "message")).encode(), "EMPTY"),
    (JSON, b"{}", "EMPTY"),
    (JSON, b"", "EMPTY"),
    (JSON, b" \r\n\t", "EMPTY"),
    (JSON, b'{"choices":', "ERROR_BODY"),
    (JSON, b"\xff", "ERROR_BODY"),
    (JSON, b'["not a completion"]', "ERROR_BODY"),
    ("text/plain", b"quota exceeded", "QUOTA_TEXT"),
    ("text/plain", b"unexpected HTML", "ERROR_BODY"),
]


@pytest.mark.parametrize("content_type,body,expected", CASES)
@pytest.mark.parametrize("width", [1, 7, 0, 10000])
def test_chunk_invariance(
    content_type: str, body: bytes, expected: str, width: int
) -> None:
    assert classify(body, width, content_type) == expected


@pytest.mark.parametrize("separator", [b"\n", b"\r\n", b"\r"])
def test_every_utf8_and_sse_boundary(separator: bytes) -> None:
    wire = (frame(answer("ёж 😀 中文")) + DONE).replace(b"\r\n", separator)
    for boundary in range(len(wire) + 1):
        classifier = StreamOutcomeClassifier(200, SSE)
        classifier.feed(wire[:boundary])
        classifier.feed(wire[boundary:])
        assert classifier.finish().kind.name == "OK"


def test_multiline_data_and_ignored_fields_chunk_boundary() -> None:
    wire = (
        b"\xef\xbb\xbf: comment\r\nid: 12\r\nretry: 1000\r\nevent: message\r\n"
        b'data: {"choices":\r\ndata: [{"delta":{"content":"'
        + "Привет 😀".encode()
        + b'"}}]}\r\n\r\n'
        + DONE
    )
    assert classify(wire, 1) == "OK"


@pytest.mark.parametrize("field", ["delta", "message"])
def test_tool_call_is_useful_without_text(field: str) -> None:
    payload = {
        "choices": [
            {
                field: {
                    "tool_calls": [
                        {"index": 0, "function": {"name": "read", "arguments": "{}"}},
                    ]
                },
                "finish_reason": "tool_calls",
            }
        ]
    }
    body = frame(payload) + DONE if field == "delta" else json.dumps(payload).encode()
    assert classify(body, 1, SSE if field == "delta" else JSON) == "OK"


@pytest.mark.parametrize(
    "payload",
    [
        {"choices": None},
        {"choices": [None]},
        {"choices": [{"delta": None}]},
        {"choices": [{"delta": {"content": None, "tool_calls": []}}]},
        {"choices": [{"delta": {"tool_calls": [None, {}, "invalid"]}}]},
    ],
)
def test_malformed_choice_never_becomes_useful(payload: Any) -> None:
    assert classify(frame(payload) + DONE, 1) == "EMPTY"


@pytest.mark.parametrize(
    "body", [b"", b'{"error":"failed"}', frame(answer("ok")) + DONE]
)
@pytest.mark.parametrize("content_type", [SSE, JSON])
def test_client_abort_takes_precedence(body: bytes, content_type: str) -> None:
    classifier = StreamOutcomeClassifier(200, content_type)
    classifier.feed(body)
    assert classifier.finish(client_aborted=True).kind.name == "CLIENT_ABORT"


@pytest.mark.parametrize("status", [199, 400, 429, 500])
@pytest.mark.parametrize("content_type", [SSE, JSON])
def test_http_error_status_never_ok(status: int, content_type: str) -> None:
    classifier = StreamOutcomeClassifier(status, content_type)
    body = (
        frame(answer("ok")) + DONE
        if content_type == SSE
        else json.dumps(answer("ok", "message")).encode()
    )
    classifier.feed(body)
    expected = "STREAM_ERROR" if content_type == SSE else "ERROR_BODY"
    assert classifier.finish().kind.name == expected


@pytest.mark.parametrize(
    "content_type,body,expected", [case for case in CASES if case[0] == JSON]
)
def test_json_body_inspector(content_type: str, body: bytes, expected: str) -> None:
    assert inspect_json_body(body).kind.name == expected


def test_finish_is_idempotent_and_feed_after_finish_rejected() -> None:
    classifier = StreamOutcomeClassifier(200, SSE)
    classifier.feed(frame(answer("ok")) + DONE)
    result = classifier.finish()
    assert result.kind.name == "OK"
    assert classifier.finish() is result
    with pytest.raises(ValueError, match="finish"):
        classifier.feed(b"late bytes")


def test_truncated_utf8_at_eof_is_not_ok() -> None:
    classifier = StreamOutcomeClassifier(200, SSE)
    classifier.feed(frame(answer("ok")) + DONE + b"\xf0\x9f")
    assert classifier.finish().kind.name == "STREAM_ERROR"

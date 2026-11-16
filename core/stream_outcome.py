"""Чистая классификация исхода HTTP/SSE без зависимости от транспорта."""

from __future__ import annotations

import codecs
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class OutcomeKind(Enum):
    OK = "OK"
    STREAM_ERROR = "STREAM_ERROR"
    QUOTA_TEXT = "QUOTA_TEXT"
    EMPTY = "EMPTY"
    ERROR_BODY = "ERROR_BODY"
    CLIENT_ABORT = "CLIENT_ABORT"


@dataclass(frozen=True, slots=True)
class StreamOutcome:
    kind: OutcomeKind


_QUOTA = re.compile(
    r"\b(?:quota[\s_]+exceeded|insufficient[\s_]+quota|rate[\s_]+limit"
    r"(?:[\s_]+exceeded)?|usage limit (?:reached|exceeded)|out of credits"
    r"|too many requests)\b",
    re.IGNORECASE,
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _messages(payload: dict[str, Any]) -> list[dict[str, Any]]:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return []
    return [
        _mapping(_mapping(choice).get("delta", _mapping(choice).get("message")))
        for choice in choices
    ]


class StreamOutcomeClassifier:
    """Принимает произвольные байтовые чанки; finish фиксирует неизменяемый итог."""

    def __init__(
        self, status: int = 200, content_type: str = "text/event-stream"
    ) -> None:
        self._status = status
        self._sse = content_type.split(";", 1)[0].strip().lower() == "text/event-stream"
        self._decoder = codecs.getincrementaldecoder("utf-8-sig")()
        self._body: list[str] = []
        self._line: list[str] = []
        self._data: list[str] = []
        self._text: list[str] = []
        self._event = ""
        self._cr = self._error = self._seen = self._done = self._tools = False
        self._result: StreamOutcome | None = None

    def feed(self, chunk: bytes) -> None:
        if self._result is not None:
            raise ValueError("feed after finish")
        self._decode(chunk, final=False)

    def _decode(self, chunk: bytes, final: bool) -> None:
        try:
            text = self._decoder.decode(chunk, final=final)
        except UnicodeDecodeError:
            self._error = True
            return
        if self._sse:
            self._scan(text)
        else:
            self._body.append(text)

    def _scan(self, text: str) -> None:
        for char in text:
            if char == "\n" and self._cr:
                self._cr = False
                continue
            self._cr = char == "\r"
            if char in "\r\n":
                self._accept_line("".join(self._line))
                self._line.clear()
            else:
                self._line.append(char)

    def _accept_line(self, line: str) -> None:
        if not line:
            self._dispatch()
            return
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "data":
            self._data.append(value)
        elif field == "event":
            self._event = value

    def _dispatch(self) -> None:
        if self._event == "error":
            self._error = True
        if self._data:
            self._seen = True
            data = "\n".join(self._data)
            if self._done:
                self._error = True
            elif data.strip() == "[DONE]":
                self._done = True
            else:
                self._payload(data)
        self._data.clear()
        self._event = ""

    def _payload(self, text: str) -> None:
        try:
            value: Any = json.loads(text)
        except ValueError:
            self._error = True
            return
        if not isinstance(value, dict):
            self._error = True
            return
        if value.get("error") is not None:
            self._error = True
        for message in _messages(value):
            content = message.get("content")
            if isinstance(content, str):
                self._text.append(content)
            calls = message.get("tool_calls")
            if isinstance(calls, list) and any(
                _mapping(_mapping(call).get("function")) for call in calls
            ):
                self._tools = True

    def _content_kind(self) -> OutcomeKind:
        text = "".join(self._text)
        if _QUOTA.search(text):
            return OutcomeKind.QUOTA_TEXT
        return OutcomeKind.OK if text.strip() or self._tools else OutcomeKind.EMPTY

    def _stream_kind(self) -> OutcomeKind:
        if self._error or not 200 <= self._status < 300:
            return OutcomeKind.STREAM_ERROR
        if self._line or self._data or self._event:
            return OutcomeKind.STREAM_ERROR
        if self._seen and not self._done:
            return OutcomeKind.STREAM_ERROR
        return self._content_kind()

    def _body_kind(self) -> OutcomeKind:
        if self._error or not 200 <= self._status < 300:
            return OutcomeKind.ERROR_BODY
        body = "".join(self._body)
        if not body.strip():
            return OutcomeKind.EMPTY
        self._payload(body)
        if self._error:
            return (
                OutcomeKind.QUOTA_TEXT
                if _QUOTA.search(body) and not body.lstrip().startswith("{")
                else OutcomeKind.ERROR_BODY
            )
        return self._content_kind()

    def finish(self, client_aborted: bool = False) -> StreamOutcome:
        """Завершает UTF-8 и отличает EOF от подтверждённого конца SSE."""
        if self._result is None:
            self._decode(b"", final=True)
            kind = self._stream_kind() if self._sse else self._body_kind()
            self._result = StreamOutcome(
                OutcomeKind.CLIENT_ABORT if client_aborted else kind
            )
        return self._result


def inspect_json_body(body: bytes, status: int = 200) -> StreamOutcome:
    """Проверяет целое JSON-тело теми же правилами, что и накопитель."""
    classifier = StreamOutcomeClassifier(status, "application/json")
    classifier.feed(body)
    return classifier.finish()

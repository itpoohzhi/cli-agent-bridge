"""Framing-отказы моста (raw-сокеты): CL, короткое тело, 413, JSON, TE (C-02)."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import BridgeCase, FakeRun  # noqa: E402

VALID = json.dumps({"model": "claude-sonnet-5-5",
                    "messages": [{"role": "user", "content": "framing probe"}]}).encode()


class TestFraming(BridgeCase):
    def _case(self, raw, want_code, want_type, half_close=False, want_count=1):
        before = len(FakeRun.instances)
        buf, closed = self._raw_exchange(raw, half_close=half_close)
        code, typ, count = self._raw_parse(buf)
        self.assertEqual(code, want_code)
        self.assertEqual(typ, want_type)
        self.assertEqual(count, want_count)
        self.assertTrue(closed, "сервер обязан закрыть соединение при отказе")
        self.assertEqual(len(FakeRun.instances), before, "отказ обязан быть до запуска")

    def test_invalid_content_length(self):
        for value in ("-1", "abc", "12 34", "0x10", ""):
            self._case(self._raw_request(VALID, cl=value), 400, "invalid_request")

    def test_short_body(self):
        self._case(self._raw_request(b"x" * 10, cl=1000), 400, "invalid_request",
                   half_close=True)

    def test_body_over_limit_413_and_leftover_not_parsed(self):
        raw = self._raw_request(b"", cl=33554433) + self._raw_request(VALID)
        self._case(raw, 413, "payload_too_large")

    def test_json_not_object(self):
        for body in (b"[]", b'"x"', b"5", b"null", b"true"):
            self._case(self._raw_request(body), 400, "invalid_request")

    def test_transfer_encoding_rejected(self):
        chunk = ("%x\r\n" % len(VALID)).encode() + VALID + b"\r\n0\r\n\r\n"
        self._case(self._raw_request(chunk, cl=None,
                                     extra=("Transfer-Encoding: chunked",)),
                   400, "invalid_request")

    def test_conflicting_content_length(self):
        self._case(self._raw_request(VALID, extra=("Content-Length: 5",)),
                   400, "invalid_request")

    def test_each_reject_logs_one_strict_line(self):
        with self.capture_logs() as lines:
            self._case(self._raw_request(b"x" * 10, cl=1000), 400, "invalid_request",
                       half_close=True)
        rejects = [ln for ln in lines if "reject reason=" in ln]
        self.assertEqual(len(rejects), 1)
        self.assertRegex(rejects[0], r"^reject reason=invalid_request model=unknown "
                                     r"model_len=0 client=[0-9.:]+$")


if __name__ == "__main__":
    unittest.main(verbosity=2)

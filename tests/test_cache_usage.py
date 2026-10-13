"""Сквозной проброс cache-токенов Droid -> wire-`usage` (REQ-CACHE-001).

Покрывает: чистый нормализатор `normalize_prompt_cache_details` (AD-004),
маппер `_map_usage` (AD-002), wire-контракт `prompt_tokens_details` в normal
JSON и финальном SSE-чанке (AD-001, AD-003), лог `usage_cache_inconsistent`.
"""

import json
import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from tests.bridge_testlib import BridgeCase  # noqa: E402
from core.usage_wire import normalize_prompt_cache_details  # noqa: E402
from tests.rpc_testlib import USAGE_LINE  # noqa: E402

MODEL = "claude-sonnet-5-5"


class TestNormalizePromptCacheDetails(unittest.TestCase):
    """AD-004: чистая функция-нормализатор."""

    def test_none_inputs(self):
        self.assertEqual(normalize_prompt_cache_details(None, None), (None, False))
        self.assertEqual(normalize_prompt_cache_details(None, 5), (None, False))
        self.assertEqual(normalize_prompt_cache_details(100, None), (None, False))

    def test_valid(self):
        self.assertEqual(
            normalize_prompt_cache_details(100, 40), ({"cached_tokens": 40}, False)
        )

    def test_zero_cached(self):
        self.assertEqual(
            normalize_prompt_cache_details(100, 0), ({"cached_tokens": 0}, False)
        )

    def test_equal_cached(self):
        self.assertEqual(
            normalize_prompt_cache_details(100, 100), ({"cached_tokens": 100}, False)
        )

    def test_inconsistent(self):
        self.assertEqual(normalize_prompt_cache_details(10, 50), (None, True))

    def test_invalid_types(self):
        bad_values: list[Any] = [True, False, 1.5, "10", [1], {"n": 1}, (1,)]
        for bad in bad_values:
            with self.subTest(bad=bad):
                self.assertEqual(normalize_prompt_cache_details(bad, 5), (None, False))
                self.assertEqual(
                    normalize_prompt_cache_details(100, bad), (None, False)
                )

    def test_negative(self):
        self.assertEqual(normalize_prompt_cache_details(-1, 5), (None, False))
        self.assertEqual(normalize_prompt_cache_details(100, -1), (None, False))
        self.assertEqual(normalize_prompt_cache_details(-100, -50), (None, False))

    def test_creation_ignored(self):
        # cache_creation_tokens на результат не влияет (deferred, не на wire).
        self.assertEqual(
            normalize_prompt_cache_details(100, 40, 7), ({"cached_tokens": 40}, False)
        )
        self.assertEqual(normalize_prompt_cache_details(100, None, 7), (None, False))


class TestMapUsage(unittest.TestCase):
    """AD-002: `_map_usage` извлекает кэш как `int | None`."""

    def test_missing_keys_are_none(self):
        usage = server._map_usage({"inputTokens": 10, "outputTokens": 5})
        self.assertIsNone(usage["cache_read_tokens"])
        self.assertIsNone(usage["cache_creation_tokens"])
        self.assertEqual(usage["input_tokens"], 10)
        self.assertEqual(usage["output_tokens"], 5)

    def test_non_dict_is_none(self):
        usage = server._map_usage(None)
        self.assertIsNone(usage["cache_read_tokens"])
        self.assertIsNone(usage["cache_creation_tokens"])

    def test_explicit_zero_and_positive(self):
        usage = server._map_usage(
            {
                "inputTokens": 10,
                "outputTokens": 5,
                "cacheReadTokens": 0,
                "cacheCreationTokens": 7,
            }
        )
        self.assertEqual(usage["cache_read_tokens"], 0)
        self.assertEqual(usage["cache_creation_tokens"], 7)

    def test_invalid_cache_values_are_none(self):
        bad_values: list[Any] = [True, False, 1.5, "10", [1], {"n": 1}, -3]
        for bad in bad_values:
            with self.subTest(bad=bad):
                usage = server._map_usage(
                    {
                        "inputTokens": 10,
                        "outputTokens": 5,
                        "cacheReadTokens": bad,
                        "cacheCreationTokens": bad,
                    }
                )
                self.assertIsNone(usage["cache_read_tokens"])
                self.assertIsNone(usage["cache_creation_tokens"])


class TestCacheUsageHttp(BridgeCase):
    """AD-001/AD-003: wire-контракт через FakeDroid (normal JSON и SSE)."""

    def _scenario(self, usage: dict) -> None:
        self.hub.script([{"steps": [{"op": "text", "text": "hello"}], "usage": usage}])

    def _body(self, **extra: Any) -> dict:
        return {
            "model": MODEL,
            "messages": [{"role": "user", "content": "hi"}],
            **extra,
        }

    @staticmethod
    def _sse_frames(stream: str) -> list[Any]:
        frames: list[Any] = []
        for line in stream.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[len("data: ") :]
            frames.append(payload if payload == "[DONE]" else json.loads(payload))
        return frames

    # -- normal JSON ------------------------------------------------------
    def test_http_normal_cache_usage(self):
        self._scenario({"inputTokens": 100, "outputTokens": 5, "cacheReadTokens": 40})
        status, body = self._post_json(self._body())
        self.assertEqual(status, 200)
        assert body is not None
        self.assertEqual(body["usage"]["prompt_tokens"], 100)
        self.assertEqual(body["usage"]["prompt_tokens_details"], {"cached_tokens": 40})

    def test_http_normal_absent_cache(self):
        self._scenario({"inputTokens": 100, "outputTokens": 5})
        status, body = self._post_json(self._body())
        self.assertEqual(status, 200)
        assert body is not None
        # Нет данных кэша — ключ отсутствует, ноль не синтезируется.
        self.assertNotIn("prompt_tokens_details", body["usage"])

    def test_http_normal_zero_cache(self):
        self._scenario({"inputTokens": 100, "outputTokens": 5, "cacheReadTokens": 0})
        status, body = self._post_json(self._body())
        self.assertEqual(status, 200)
        assert body is not None
        self.assertEqual(body["usage"]["prompt_tokens_details"], {"cached_tokens": 0})

    def test_http_normal_equal_cache(self):
        self._scenario({"inputTokens": 100, "outputTokens": 5, "cacheReadTokens": 100})
        status, body = self._post_json(self._body())
        self.assertEqual(status, 200)
        assert body is not None
        self.assertEqual(body["usage"]["prompt_tokens_details"], {"cached_tokens": 100})

    def test_inconsistent_cache_usage_logged(self):
        self._scenario({"inputTokens": 10, "outputTokens": 5, "cacheReadTokens": 50})
        with self.capture_logs() as lines:
            status, body = self._post_json(self._body())
        self.assertEqual(status, 200)
        assert body is not None
        self.assertNotIn("prompt_tokens_details", body["usage"])
        self.assertTrue(
            any("usage_cache_inconsistent" in line for line in lines), lines
        )

    def test_creation_never_on_wire(self):
        self._scenario(
            {
                "inputTokens": 100,
                "outputTokens": 5,
                "cacheReadTokens": 40,
                "cacheCreationTokens": 7,
            }
        )
        status, body = self._post_json(self._body())
        self.assertEqual(status, 200)
        assert body is not None
        wire = json.dumps(body["usage"])
        self.assertNotIn("cache_creation", wire)
        self.assertNotIn("cacheCreation", wire)
        self.assertEqual(body["usage"]["prompt_tokens_details"], {"cached_tokens": 40})

    def test_creation_alone_yields_no_details(self):
        self._scenario(
            {"inputTokens": 100, "outputTokens": 5, "cacheCreationTokens": 7}
        )
        status, body = self._post_json(self._body())
        self.assertEqual(status, 200)
        assert body is not None
        self.assertNotIn("prompt_tokens_details", body["usage"])

    # -- SSE --------------------------------------------------------------
    def test_http_sse_cache_usage(self):
        # Без stream_options/include_usage: usage-чанк шлётся как раньше (AD-003).
        self._scenario({"inputTokens": 100, "outputTokens": 5, "cacheReadTokens": 40})
        status, stream = self._post(self._body(stream=True))
        self.assertEqual(status, 200)
        frames = self._sse_frames(stream)
        self.assertEqual(frames[-1], "[DONE]")
        usage_frames = [
            frame for frame in frames if isinstance(frame, dict) and "usage" in frame
        ]
        # Ровно один usage-чанк: после finish_reason, перед [DONE].
        self.assertEqual(len(usage_frames), 1)
        self.assertIs(frames[-2], usage_frames[0])
        finish_before = [
            frame
            for frame in frames[:-2]
            if isinstance(frame, dict)
            and frame.get("choices", [{}])[0].get("finish_reason")
        ]
        self.assertTrue(finish_before)
        self.assertEqual(
            usage_frames[0]["usage"]["prompt_tokens_details"], {"cached_tokens": 40}
        )

    def test_http_sse_absent_cache(self):
        self._scenario({"inputTokens": 100, "outputTokens": 5})
        status, stream = self._post(self._body(stream=True))
        self.assertEqual(status, 200)
        frames = self._sse_frames(stream)
        usage_frames = [
            frame for frame in frames if isinstance(frame, dict) and "usage" in frame
        ]
        self.assertEqual(len(usage_frames), 1)
        self.assertNotIn("prompt_tokens_details", usage_frames[0]["usage"])

    def test_http_sse_inconsistent_cache_logged(self):
        self._scenario({"inputTokens": 10, "outputTokens": 5, "cacheReadTokens": 50})
        with self.capture_logs() as lines:
            status, stream = self._post(self._body(stream=True))
        self.assertEqual(status, 200)
        frames = self._sse_frames(stream)
        usage_frames = [
            frame for frame in frames if isinstance(frame, dict) and "usage" in frame
        ]
        self.assertEqual(len(usage_frames), 1)
        self.assertNotIn("prompt_tokens_details", usage_frames[0]["usage"])
        self.assertTrue(
            any("usage_cache_inconsistent" in line for line in lines), lines
        )

    # -- журнал -----------------------------------------------------------
    def test_usage_log_reports_cache_read(self):
        self._scenario({"inputTokens": 100, "outputTokens": 5, "cacheReadTokens": 40})
        with self.capture_logs() as lines:
            status, _ = self._post_json(self._body())
        self.assertEqual(status, 200)
        matches = [
            USAGE_LINE.match(line) for line in lines if line.startswith("usage ")
        ]
        self.assertEqual(len(matches), 1)
        self.assertIsNotNone(matches[0])
        assert matches[0] is not None
        self.assertEqual(matches[0].group("cache_read"), "40")

    def test_usage_log_absent_cache_is_dash(self):
        self._scenario({"inputTokens": 100, "outputTokens": 5})
        with self.capture_logs() as lines:
            status, _ = self._post_json(self._body())
        self.assertEqual(status, 200)
        usage_lines = [line for line in lines if line.startswith("usage ")]
        self.assertEqual(len(usage_lines), 1)
        self.assertIn("cache_read=-", usage_lines[0])


if __name__ == "__main__":
    unittest.main()

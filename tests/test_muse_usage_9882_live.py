"""VER-006 live Muse :9882 HTTP usage E2E (opt-in via BRIDGE_LIVE_MUSE_USAGE_E2E=1)."""

from __future__ import annotations

import json
import os
import urllib.request

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BRIDGE_LIVE_MUSE_USAGE_E2E") != "1",
    reason="opt-in live :9882 Muse E2E test",
)


def _bridge_url() -> str:
    return os.environ.get("BRIDGE_LIVE_TEST_URL", "http://127.0.0.1:9882/v1").rstrip("/")


def _bridge_headers() -> dict[str, str]:
    key = os.environ.get("BRIDGE_LIVE_TEST_KEY") or os.environ.get("CLAUDE_BRIDGE_KEY") or "local"
    return {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}


def _assert_valid_usage(usage: dict[str, object]) -> None:
    prompt = usage.get("prompt_tokens")
    compl = usage.get("completion_tokens")
    total = usage.get("total_tokens")
    assert type(prompt) is int and prompt > 0
    assert type(compl) is int and compl > 0
    assert type(total) is int and total == prompt + compl
    p_det = usage.get("prompt_tokens_details")
    if isinstance(p_det, dict) and "cached_tokens" in p_det:
        assert type(p_det["cached_tokens"]) is int and 0 <= p_det["cached_tokens"] <= prompt
    c_det = usage.get("completion_tokens_details")
    if isinstance(c_det, dict) and "reasoning_tokens" in c_det:
        assert type(c_det["reasoning_tokens"]) is int and 0 <= c_det["reasoning_tokens"] <= compl


def test_ver006_live_muse_nonstream_and_sse_usage() -> None:
    model = os.environ.get("BRIDGE_LIVE_MUSE_MODEL", "muse-ember-1.0")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    req = urllib.request.Request(
        _bridge_url() + "/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "Reply with one word: OK"}],
            "stream": False,
        }).encode("utf-8"),
        headers=_bridge_headers(),
        method="POST",
    )
    with opener.open(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    _assert_valid_usage(data["usage"])

    req_sse = urllib.request.Request(
        _bridge_url() + "/chat/completions",
        data=json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": "Reply with one word: OK"}],
            "stream": True,
        }).encode("utf-8"),
        headers=_bridge_headers(),
        method="POST",
    )
    usage_chunks: list[dict[str, object]] = []
    with opener.open(req_sse, timeout=120) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            chunk = json.loads(line.removeprefix("data: "))
            if isinstance(chunk.get("usage"), dict):
                usage_chunks.append(chunk["usage"])
    assert len(usage_chunks) == 1
    _assert_valid_usage(usage_chunks[0])

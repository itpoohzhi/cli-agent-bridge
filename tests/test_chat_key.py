"""Матрица валидации единого ключа чата `core/chat_key` (prompt_cache_key)."""

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import chat_key  # noqa: E402
from core.chat_key import ChatKey, digest_of, resolve_chat_key  # noqa: E402


@pytest.fixture(autouse=True)
def _default_limit(monkeypatch):
    monkeypatch.delenv(chat_key.ENV_KEY_MAX_LEN, raising=False)


def test_absent_is_nokey_not_invalid():
    for req in (None, {}, {"prompt_cache_key": None}, {"other": 1}):
        res = resolve_chat_key(req)
        assert (res.keyed, res.route, res.value, res.digest, res.invalid) == (
            False,
            "nokey",
            "",
            "",
            False,
        )


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "\t", 5, 1.5, True, [], {}, "a\x00b", "a\nb", "a\x7fb", "a\ud800b"],
)
def test_invalid_values(bad):
    res = resolve_chat_key({"prompt_cache_key": bad})
    assert res.invalid is True
    assert (res.keyed, res.route, res.value, res.digest) == (False, "nokey", "", "")


def test_length_boundary_default_512():
    assert chat_key.DEFAULT_KEY_MAX_LEN == 512
    ok = resolve_chat_key({"prompt_cache_key": "k" * 512})
    assert ok.keyed and not ok.invalid and len(ok.value) == 512
    over = resolve_chat_key({"prompt_cache_key": "k" * 513})
    assert over.invalid and not over.keyed


def test_env_limit_and_fallback(monkeypatch):
    monkeypatch.setenv(chat_key.ENV_KEY_MAX_LEN, "8")
    assert resolve_chat_key({"prompt_cache_key": "k" * 8}).keyed
    assert resolve_chat_key({"prompt_cache_key": "k" * 9}).invalid
    for raw in ("0", "-3", "abc", ""):
        monkeypatch.setenv(chat_key.ENV_KEY_MAX_LEN, raw)
        assert chat_key.key_max_len() == 512


def test_source_priority_and_no_fallback_after_invalid():
    headers = {"x-dsh-chat-id": "h1", "x-session-id": "h2"}
    extra = {"chat_id": "ex"}
    req = {"prompt_cache_key": "pck", "chat_id": "body"}
    res = resolve_chat_key(req, headers, extra)
    assert (res.value, res.source) == ("pck", "prompt_cache_key")
    del req["prompt_cache_key"]
    assert resolve_chat_key(req, headers, extra).value == "h1"
    del headers["x-dsh-chat-id"]
    assert resolve_chat_key(req, headers, extra).value == "h2"
    del headers["x-session-id"]
    assert resolve_chat_key(req, headers, extra).value == "ex"
    extra["chat_id"] = None
    assert resolve_chat_key(req, headers, extra).value == "body"
    # Невалидный приоритетный источник не отдаёт чат следующему.
    bad = resolve_chat_key({"prompt_cache_key": "", "chat_id": "body"})
    assert bad.invalid and not bad.keyed


def test_headers_case_insensitive_plain_dict():
    res = resolve_chat_key({}, {"X-DSH-Chat-Id": "abc"})
    assert res.keyed and res.value == "abc"


def test_sources_narrowing():
    req = {"chat_id": "body"}
    assert resolve_chat_key(req, sources=("prompt_cache_key",)).route == "nokey"
    assert resolve_chat_key(req).route == "keyed"


def test_digest_stable_deterministic_64_hex():
    a = resolve_chat_key({"prompt_cache_key": "chat-1"})
    b = resolve_chat_key({"prompt_cache_key": "chat-1"})
    c = resolve_chat_key({"prompt_cache_key": "chat-2"})
    assert a.digest == b.digest != c.digest
    assert len(a.digest) == 64 and int(a.digest, 16) >= 0
    assert a.digest == hashlib.sha256(b"chat-1").hexdigest()
    assert a.value == "chat-1"


def test_namespace_digest_matches_legacy_facade_hash():
    res = resolve_chat_key({"prompt_cache_key": "k"}, namespace="droid-bridge/v1")
    legacy = hashlib.sha256(b"droid-bridge/v1\0k").hexdigest()
    assert res.digest == legacy == digest_of("k", "droid-bridge/v1")


def test_result_is_immutable():
    res = resolve_chat_key({"prompt_cache_key": "k"})
    assert isinstance(res, ChatKey)
    with pytest.raises(AttributeError):
        res.keyed = False  # type: ignore[misc]

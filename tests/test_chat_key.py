"""Матрица валидации единого ключа чата `core/chat_key` (prompt_cache_key)."""

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import chat_key  # noqa: E402
from core.chat_key import (  # noqa: E402
    NO_MAX_LEN,
    SOURCES_CACHE_KEY_ONLY,
    SOURCES_DEFAULT,
    SOURCES_SESSION_ID,
    ChatKey,
    digest_of,
    resolve_chat_key,
)


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
    # Явные chat-id приоритетнее prompt_cache_key (аффинность кэша — не идентичность чата).
    headers = {"x-dsh-chat-id": "h1", "x-session-id": "h2"}
    extra = {"chat_id": "ex"}
    req = {"prompt_cache_key": "pck", "chat_id": "body"}
    res = resolve_chat_key(req, headers, extra)
    assert (res.value, res.source) == ("h1", "x-dsh-chat-id")
    del headers["x-dsh-chat-id"]
    assert resolve_chat_key(req, headers, extra).value == "h2"
    del headers["x-session-id"]
    assert resolve_chat_key(req, headers, extra).value == "ex"
    extra["chat_id"] = None
    assert resolve_chat_key(req, headers, extra).value == "body"
    del req["chat_id"]
    assert resolve_chat_key(req, headers, extra).value == "pck"
    # Невалидный приоритетный источник не отдаёт чат следующему.
    bad = resolve_chat_key({"chat_id": "", "prompt_cache_key": "pck"})
    assert bad.invalid and not bad.keyed
    # Битый prompt_cache_key не отравляет валидный явный chat-id.
    ok = resolve_chat_key({"prompt_cache_key": "a\x00b"}, {"x-dsh-chat-id": "good"})
    assert ok.keyed and ok.value == "good"


def test_session_id_sources_exclude_prompt_cache_key():
    req = {"prompt_cache_key": "shared-prefix-cache"}
    assert SOURCES_SESSION_ID == tuple(
        s for s in SOURCES_DEFAULT if s != "prompt_cache_key"
    )
    res = resolve_chat_key(req, sources=SOURCES_SESSION_ID)
    assert (res.keyed, res.invalid, res.route) == (False, False, "nokey")
    # Битый prompt_cache_key для набора сессий вообще не источник.
    res = resolve_chat_key({"prompt_cache_key": "a\x00b"}, sources=SOURCES_SESSION_ID)
    assert (res.keyed, res.invalid) == (False, False)
    only = resolve_chat_key(req, {"x-dsh-chat-id": "h"}, sources=SOURCES_CACHE_KEY_ONLY)
    assert only.value == "shared-prefix-cache"


def test_strict_mode_strips_value_and_digest_consistently():
    a = resolve_chat_key({"prompt_cache_key": "  chat1  "})
    b = resolve_chat_key({"prompt_cache_key": "chat1"})
    assert a.value == b.value == "chat1" and a.digest == b.digest


def test_lenient_mode_is_legacy_facade_compat():
    # Прежнее поведение фасада: str, 0 < len <= max, значение как есть (пробелы/контролы).
    for raw in ("a b", " k ", "a\tb", "   "):
        res = resolve_chat_key(
            {"prompt_cache_key": raw},
            namespace="ns",
            sources=SOURCES_CACHE_KEY_ONLY,
            lenient=True,
        )
        assert res.keyed and res.value == raw and not res.invalid
        assert res.digest == hashlib.sha256(f"ns\0{raw}".encode()).hexdigest()
    for raw in ("", "k" * 513, 5, "a\ud800b"):
        res = resolve_chat_key(
            {"prompt_cache_key": raw}, sources=SOURCES_CACHE_KEY_ONLY, lenient=True
        )
        assert res.invalid and not res.keyed and res.route == "nokey"


def test_lenient_without_length_cap_is_muse_profile():
    """Профиль muse: lenient + NO_MAX_LEN — любая непустая строка как есть, без предела."""
    for raw in ("k" * 513, "k" * 5000, " k ", "   "):
        res = resolve_chat_key(
            {"prompt_cache_key": raw},
            sources=SOURCES_CACHE_KEY_ONLY,
            lenient=True,
            max_len=NO_MAX_LEN,
        )
        assert res.keyed and res.value == raw and not res.invalid
    for raw in ("", 5, "a\ud800b"):
        res = resolve_chat_key(
            {"prompt_cache_key": raw},
            sources=SOURCES_CACHE_KEY_ONLY,
            lenient=True,
            max_len=NO_MAX_LEN,
        )
        assert res.invalid and res.route == "nokey"


def test_explicit_max_len_overrides_env(monkeypatch):
    monkeypatch.setenv(chat_key.ENV_KEY_MAX_LEN, "4")
    assert resolve_chat_key({"prompt_cache_key": "abcde"}).invalid
    assert resolve_chat_key({"prompt_cache_key": "abcde"}, max_len=10).keyed


def test_headers_case_insensitive_plain_dict():
    res = resolve_chat_key({}, {"X-DSH-Chat-Id": "abc"})
    assert res.keyed and res.value == "abc"


def test_sources_narrowing():
    req = {"chat_id": "body"}
    assert resolve_chat_key(req, sources=SOURCES_CACHE_KEY_ONLY).route == "nokey"
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

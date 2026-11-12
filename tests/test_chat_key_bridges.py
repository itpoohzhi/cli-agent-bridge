"""Единый ключ чата (`prompt_cache_key`) и cache-usage в суб-мостах.

Регрессии по одному на мост: ключ доходит до идентичности чата/сессии, запрос
без ключа ведёт себя по-прежнему. Единый контракт на невалидный ключ во ВСЕХ
мостах: запрос обслуживается как без ключа (nokey), без 400. `prompt_cache_key` —
аффинность кэша, а не идентичность чата: agy его как chat id не читает.
Реальные внешние процессы не запускаются.
"""

import hashlib
import http.client
import importlib.util
import json
import queue
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.usage_wire import normalize_prompt_cache_details  # noqa: E402

KEY = "chat-key-under-test"
DIGEST16 = hashlib.sha256(KEY.encode()).hexdigest()[:16]
DIGEST_FULL = hashlib.sha256(KEY.encode()).hexdigest()
BODY_LONG_KEY = "k" * 513


def _load(name: str, tag: str, monkeypatch: pytest.MonkeyPatch) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"chatkey_{tag}", ROOT / "bridges" / name / "server.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    monkeypatch.setattr(sys, "path", list(sys.path))
    spec.loader.exec_module(module)
    return module


class _Live:
    """Настоящий Handler на свободном loopback-порту."""

    def __init__(self, module: Any) -> None:
        self.httpd = module.Server(("127.0.0.1", 0), module.Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def post(self, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            hdrs = {"Content-Type": "application/json", "Authorization": "Bearer t"}
            hdrs.update(headers or {})
            conn.request("POST", "/v1/chat/completions", json.dumps(payload), hdrs)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, {"raw": raw}
        finally:
            conn.close()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


@pytest.fixture()
def live(monkeypatch):
    started: list[_Live] = []

    def start(module: Any, key_attr: str = "AUTH_KEY") -> _Live:
        monkeypatch.setattr(module, key_attr, "t")
        item = _Live(module)
        started.append(item)
        return item

    yield start
    for item in started:
        item.stop()


# ---- muse-bridge -------------------------------------------------------------


@pytest.fixture()
def muse(monkeypatch):
    return _load("muse-bridge", "muse", monkeypatch)


def _muse_body(**extra: Any) -> dict:
    body = {
        "model": "muse-spark-1.3",
        "messages": [{"role": "user", "content": "привет"}],
    }
    body.update(extra)
    return body


def test_muse_key_reaches_session_identity(muse, live, monkeypatch):
    seen: list[str] = []

    def fake_create(**kwargs: Any) -> Any:
        seen.append(kwargs["session_id"])
        raise PermissionError("stop after identity")

    monkeypatch.setattr(muse.TURN_MANAGER, "create_or_attach_turn", fake_create)
    server = live(muse)
    status, _ = server.post(_muse_body(prompt_cache_key=KEY))
    assert status == 403 and seen == [KEY]


def test_muse_without_key_keeps_empty_session(muse, live, monkeypatch):
    seen: list[str] = []

    def fake_create(**kwargs: Any) -> Any:
        seen.append(kwargs["session_id"])
        raise PermissionError("stop after identity")

    monkeypatch.setattr(muse.TURN_MANAGER, "create_or_attach_turn", fake_create)
    status, _ = live(muse).post(_muse_body())
    assert status == 403 and seen == [""]


@pytest.mark.parametrize("bad", ["", "   ", BODY_LONG_KEY, 7, "a\x00b"])
def test_muse_invalid_key_is_treated_as_no_key(muse, live, monkeypatch, bad):
    seen: list[str] = []

    def fake_create(**kwargs: Any) -> Any:
        seen.append(kwargs["session_id"])
        raise PermissionError("stop after identity")

    monkeypatch.setattr(muse.TURN_MANAGER, "create_or_attach_turn", fake_create)
    status, _ = live(muse).post(_muse_body(prompt_cache_key=bad))
    assert status == 403 and seen == [""]


def test_muse_reads_only_prompt_cache_key_documented_exception(muse, live, monkeypatch):
    """Осознанное исключение: заголовок chat-id не меняет идентичность сессии muse."""
    seen: list[str] = []

    def fake_create(**kwargs: Any) -> Any:
        seen.append(kwargs["session_id"])
        raise PermissionError("stop after identity")

    monkeypatch.setattr(muse.TURN_MANAGER, "create_or_attach_turn", fake_create)
    status, _ = live(muse).post(_muse_body(), headers={"x-dsh-chat-id": "hdr"})
    assert status == 403 and seen == [""]


def test_muse_cache_read_goes_through_normalizer(muse):
    assert muse.extract_cache_read_tokens({"cacheReadTokens": 4}) == 4
    details, bad = muse.normalize_prompt_cache_details(10, 4)
    assert (details, bad) == ({"cached_tokens": 4}, False)
    assert muse.extract_cache_read_tokens({"promptTokens": 10}) is None


# ---- claude-p-bridge -----------------------------------------------------------


class _FakeRun:
    script: list = []
    calls = 0

    def __init__(self, prompt, model, effort, tag, img_dir=None):
        type(self).calls += 1
        self.q: queue.Queue = queue.Queue()
        for item in type(self).script:
            self.q.put(item)
        self.err_box: list = []

    def close(self) -> None:
        pass


def _claude_script(usage: dict) -> list:
    return [("text", "ok"), ("result", {"usage": usage}), ("done", 0)]


@pytest.fixture()
def claude(monkeypatch):
    mod = _load("claude-p-bridge", "claude", monkeypatch)
    _FakeRun.calls = 0
    _FakeRun.script = _claude_script({"input_tokens": 3, "output_tokens": 2})
    monkeypatch.setattr(mod, "Run", _FakeRun)
    logs: list[str] = []
    monkeypatch.setattr(mod, "_log", logs.append)
    mod.captured_logs = logs
    return mod


def _claude_body(**extra: Any) -> dict:
    body = {
        "model": "claude-sonnet-5-5",
        "stream": False,
        "messages": [{"role": "user", "content": "hi"}],
    }
    body.update(extra)
    return body


def test_claude_key_logged_as_digest_and_generation_unchanged(claude, live):
    status, payload = live(claude).post(_claude_body(prompt_cache_key=KEY))
    assert status == 200
    assert payload["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 2,
        "total_tokens": 5,
    }
    joined = "\n".join(claude.captured_logs)
    assert f"chat key={DIGEST16}" in joined and KEY not in joined


def test_claude_header_chat_id_is_accepted(claude, live):
    status, _ = live(claude).post(_claude_body(), headers={"x-dsh-chat-id": KEY})
    assert status == 200
    assert f"chat key={DIGEST16}" in "\n".join(claude.captured_logs)


def test_claude_without_key_is_unchanged(claude, live):
    status, _ = live(claude).post(_claude_body())
    assert status == 200 and _FakeRun.calls == 1
    assert "chat key=" not in "\n".join(claude.captured_logs)


@pytest.mark.parametrize("bad", ["", BODY_LONG_KEY, 5, "a\tb"])
def test_claude_invalid_key_is_treated_as_no_key(claude, live, bad):
    status, _ = live(claude).post(_claude_body(prompt_cache_key=bad))
    assert status == 200 and _FakeRun.calls == 1
    assert "chat key=" not in "\n".join(claude.captured_logs)


@pytest.mark.parametrize("bad", ["", BODY_LONG_KEY, "a\tb"])
def test_claude_invalid_header_does_not_break_request(claude, live, bad):
    status, _ = live(claude).post(_claude_body(), headers={"x-session-id": bad})
    assert status == 200 and _FakeRun.calls == 1


def test_claude_cache_read_goes_to_prompt_tokens_details(claude, live):
    _FakeRun.script = _claude_script(
        {"input_tokens": 3, "output_tokens": 2, "cache_read_input_tokens": 40}
    )
    _, payload = live(claude).post(_claude_body())
    assert payload["usage"] == {
        "prompt_tokens": 43,
        "completion_tokens": 2,
        "total_tokens": 45,
        "prompt_tokens_details": {"cached_tokens": 40},
    }


def test_claude_cache_creation_counts_in_prompt_tokens(claude, live):
    _FakeRun.script = _claude_script(
        {
            "input_tokens": 3,
            "output_tokens": 2,
            "cache_read_input_tokens": 40,
            "cache_creation_input_tokens": 7,
        }
    )
    _, payload = live(claude).post(_claude_body())
    assert payload["usage"]["prompt_tokens"] == 50
    assert payload["usage"]["total_tokens"] == 52
    assert payload["usage"]["prompt_tokens_details"] == {"cached_tokens": 40}


def _sse_usage_frames(raw: str) -> list[dict]:
    frames = []
    for line in raw.splitlines():
        if line.startswith("data: ") and line != "data: [DONE]":
            frame = json.loads(line[6:])
            if "usage" in frame:
                frames.append(frame)
    return frames


def _post_sse(live_server: _Live, payload: dict) -> str:
    conn = http.client.HTTPConnection("127.0.0.1", live_server.port, timeout=30)
    try:
        conn.request(
            "POST",
            "/v1/chat/completions",
            json.dumps(payload),
            {"Content-Type": "application/json", "Authorization": "Bearer t"},
        )
        return conn.getresponse().read().decode("utf-8", "replace")
    finally:
        conn.close()


def test_claude_sse_final_chunk_carries_cached_tokens(claude, live):
    _FakeRun.script = _claude_script(
        {"input_tokens": 3, "output_tokens": 2, "cache_read_input_tokens": 40}
    )
    raw = _post_sse(live(claude), _claude_body(stream=True))
    frames = _sse_usage_frames(raw)
    assert len(frames) == 1
    assert frames[0]["choices"][0]["finish_reason"] == "stop"
    assert frames[0]["usage"] == {
        "prompt_tokens": 43,
        "completion_tokens": 2,
        "total_tokens": 45,
        "prompt_tokens_details": {"cached_tokens": 40},
    }
    assert raw.rstrip().endswith("data: [DONE]")


def test_claude_sse_without_cache_has_no_details(claude, live):
    raw = _post_sse(live(claude), _claude_body(stream=True))
    (frame,) = _sse_usage_frames(raw)
    assert "prompt_tokens_details" not in frame["usage"]
    assert frame["usage"]["total_tokens"] == 5


def test_claude_upstream_without_cache_has_no_details_key(claude, live):
    _, payload = live(claude).post(_claude_body())
    assert "prompt_tokens_details" not in payload["usage"]


# ---- opencode-zen-bridge -------------------------------------------------------


@pytest.fixture()
def zen(monkeypatch):
    mod = _load("opencode-zen-bridge", "zen", monkeypatch)
    logs: list[str] = []
    monkeypatch.setattr(mod, "_log", logs.append)
    mod.captured_logs = logs
    return mod


def _zen_model(zen: Any) -> str:
    return sorted(zen.ALLOWED_MODELS)[0]


def test_zen_key_passes_gate_and_is_logged_as_digest(zen, live):
    # Пустые messages -> 400 «no user content»: ключ уже принят, бэкенд не нужен.
    status, payload = live(zen).post(
        {"model": _zen_model(zen), "messages": [], "prompt_cache_key": KEY}
    )
    assert status == 400 and "no user content" in payload["error"]["message"]
    joined = "\n".join(zen.captured_logs)
    assert f"chat key={DIGEST16}" in joined and KEY not in joined


def test_zen_without_key_keeps_previous_route(zen, live):
    status, payload = live(zen).post({"model": _zen_model(zen), "messages": []})
    assert status == 400 and "no user content" in payload["error"]["message"]
    assert "chat key=" not in "\n".join(zen.captured_logs)


@pytest.mark.parametrize("bad", ["", BODY_LONG_KEY, 5, "a\nb"])
def test_zen_invalid_key_is_treated_as_no_key(zen, live, bad):
    # Не 400 invalid_request: дальше срабатывает прежний гейт «no user content».
    status, payload = live(zen).post(
        {"model": _zen_model(zen), "messages": [], "prompt_cache_key": bad}
    )
    assert status == 400 and "no user content" in payload["error"]["message"]
    assert "chat key=" not in "\n".join(zen.captured_logs)


def test_zen_usage_uses_shared_normalizer(zen, monkeypatch):
    from zen_bridge.adapters import google_payload

    calls: list[tuple] = []
    real = normalize_prompt_cache_details

    def spy(prompt, cached, creation=None):
        calls.append((prompt, cached))
        return real(prompt, cached, creation)

    monkeypatch.setattr(google_payload, "normalize_prompt_cache_details", spy)
    usage = google_payload._build_openai_usage(100, 5, cached_tokens=40)
    assert calls == [(100, 40)]
    assert usage["prompt_tokens_details"] == {"cached_tokens": 40}
    assert usage["cached_tokens"] == 40
    # Нет cache-read -> ключей нет, нормализатор не вызывается.
    calls.clear()
    plain = google_payload._build_openai_usage(100, 5)
    assert "prompt_tokens_details" not in plain and calls == []
    # Несогласованный кэш (> prompt) на wire не выдаётся, без clamp.
    broken = google_payload._build_openai_usage(10, 5, cached_tokens=50)
    assert "prompt_tokens_details" not in broken and "cached_tokens" not in broken


# ---- agy-bridge ------------------------------------------------------------------


@pytest.fixture()
def agy(monkeypatch):
    return _load("agy-bridge", "agy", monkeypatch)


def test_agy_prompt_cache_key_is_not_a_chat_source(agy):
    """prompt_cache_key — аффинность кэша, не идентичность чата: сессии не склеиваются."""
    extra = {"chat_id": "extra-chat"}
    req = {"prompt_cache_key": KEY, "chat_id": "body-chat"}
    headers = {"x-dsh-chat-id": "header-chat"}
    assert agy._request_chat_id(headers, extra, req) == ("header-chat", False)
    assert agy._request_chat_id({}, extra, req) == ("extra-chat", False)
    assert agy._request_chat_id({}, {}, req) == ("body-chat", False)
    # Только prompt_cache_key (валидный или битый) -> нет chat id, холодный ход.
    assert agy._request_chat_id({}, {}, {"prompt_cache_key": KEY}) == ("", False)
    assert agy._request_chat_id({}, {}, {"prompt_cache_key": "a\x00b"}) == ("", False)
    assert agy._request_chat_id({}, {}, {}) == ("", False)


def test_agy_two_chats_sharing_cache_key_get_distinct_sessions(agy):
    shared = {"prompt_cache_key": "shared-prefix-cache"}
    a, _ = agy._request_chat_id({"x-dsh-chat-id": "chat-A"}, {}, shared)
    b, _ = agy._request_chat_id({"x-dsh-chat-id": "chat-B"}, {}, shared)
    assert agy._session_key_for("m", "/tmp", "low", a) != agy._session_key_for(
        "m", "/tmp", "low", b
    )
    # Без chat-id общий cache-key сессию не создаёт (ключ только по cwd).
    no_chat, _ = agy._request_chat_id({}, {}, shared)
    assert agy._session_key_for("m", "/tmp", "low", no_chat) == ("m", "/tmp", "low")


def test_agy_key_becomes_session_token_not_raw(agy):
    key = agy._session_key_for("m", "/tmp", "low", KEY)
    # Полный sha256 — идентичность сессии, не усечённый префикс.
    assert key == (DIGEST_FULL, "m", "/tmp", "low")
    assert KEY not in "".join(key)


def test_agy_invalid_explicit_chat_id_is_cold_not_error(agy):
    assert agy._request_chat_id({"x-dsh-chat-id": "a\tb"}, {}, {}) == ("", True)


def test_agy_limit_comes_from_shared_config(agy, monkeypatch):
    assert agy._request_chat_id({}, {}, {"chat_id": "k" * 512})[1] is False
    assert agy._request_chat_id({}, {}, {"chat_id": "k" * 513}) == ("", True)
    monkeypatch.setenv("BRIDGE_CHAT_KEY_MAX_LEN", "16")
    assert agy._request_chat_id({}, {}, {"chat_id": "k" * 17}) == ("", True)

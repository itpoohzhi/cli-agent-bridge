"""Регрессия цикла повторов agy-bridge: потеря сессии между tool-ходами.

Тесты зелёные при включённых флагах AGY_SESSION_CONTINUITY_ENABLED /
AGY_TRUNCATION_NOTICE_ENABLED; индекс continuity изолируется на каждый тест.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BRIDGE_PY = _REPO_ROOT / "bridges" / "agy-bridge" / "server.py"
_MODEL = "gemini-4-neon"
_NOTICE_MARKER = "[truncation-notice]"
_TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {"name": "read_file", "parameters": {}}}
]


def _load_bridge() -> Any:
    with pytest.MonkeyPatch.context() as mp:
        if "AGY_BRIDGE_KEY" not in os.environ:
            mp.setenv("AGY_BRIDGE_KEY", "test-key-agy-repeat-loop")
        mp.delenv("AGY_BRIDGE_FLEET", raising=False)
        spec = importlib.util.spec_from_file_location(
            "agy_bridge_server_repeat_loop_repro", _BRIDGE_PY
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return module


srv = _load_bridge()


def _turn_requests() -> tuple[dict[str, Any], dict[str, Any]]:
    """Два запроса DSH 0.2.2-rc.5: общий префикс, второй добавляет tool-цикл."""
    system = {"role": "system", "content": "Ты помощник."}
    user = {"role": "user", "content": "прочитай SKILL.md"}
    assistant = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "read_file", "arguments": "{}"},
            }
        ],
    }
    tool = {"role": "tool", "tool_call_id": "call_1", "content": "содержимое файла"}
    req1 = {"model": _MODEL, "messages": [system, user], "tools": _TOOLS}
    req2 = {
        "model": _MODEL,
        "messages": [system, user, assistant, tool],
        "tools": _TOOLS,
    }
    return req1, req2


@pytest.fixture(autouse=True)
def _fresh_continuity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Свежий индекс continuity на тест: независимость от порядка запуска."""
    monkeypatch.setattr(srv, "_CONTINUITY", srv.ContinuityIndex())


def _enable_flag(monkeypatch: pytest.MonkeyPatch, env_name: str) -> None:
    """Включить флаг через env и сбросить кэш снимка динамического конфига."""
    monkeypatch.setenv(env_name, "1")
    monkeypatch.setattr(srv, "_cfg_checked_at", None)
    monkeypatch.setattr(srv, "_cfg_key", None)


def _isolate_session_store(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Подменить глобальный стор сессий и файл персистентности на временные."""
    monkeypatch.setenv(srv.SESSIONS_FILE_ENV, str(tmp_path / "sessions.json"))
    monkeypatch.setattr(srv, "_session_store", {})
    monkeypatch.setattr(srv, "_in_flight_cids", set())
    monkeypatch.setattr(srv, "_active_cid_owners", {})


def test_dsh_second_tool_turn_without_chat_id_gets_continuity_session_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_flag(monkeypatch, "AGY_SESSION_CONTINUITY_ENABLED")
    req1, req2 = _turn_requests()
    chat_id_1, _ = srv._request_chat_id({}, {}, req1)
    chat_id_2, _ = srv._request_chat_id({}, {}, req2)
    sess_key_1 = srv._session_key_for(_MODEL, "", "high", chat_id_1)
    sess_key_2 = srv._session_key_for(_MODEL, "", "high", chat_id_2)

    assert chat_id_1
    assert chat_id_2 == chat_id_1
    assert len(sess_key_1) == 4
    assert sess_key_2 == sess_key_1


def test_active_tool_truncation_emits_single_notice_within_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_flag(monkeypatch, "AGY_TRUNCATION_NOTICE_ENABLED")
    big_result = "L" * 60000
    messages = [
        {"role": "system", "content": "S" * 61000},
        {"role": "user", "content": "прочитай SKILL.md"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": big_result},
    ]
    prompt = srv._messages_to_prompt(messages)

    assert srv._ndjson_bytes(prompt) <= srv._prompt_budget(0)
    assert big_result not in prompt
    assert prompt.count(_NOTICE_MARKER) == 1


def test_tool_turn_without_chat_id_commits_and_claims_session_store(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _isolate_session_store(monkeypatch, tmp_path)
    _enable_flag(monkeypatch, "AGY_SESSION_CONTINUITY_ENABLED")
    req1, req2 = _turn_requests()

    chat_id_1, invalid_1 = srv._request_chat_id({}, {}, req1)
    sess_key_1 = srv._session_key_for(_MODEL, "", "high", chat_id_1)
    srv._session_commit(sess_key_1, "cid-turn-1")

    chat_id_2, invalid_2 = srv._request_chat_id({}, {}, req2)
    sess_key_2 = srv._session_key_for(_MODEL, "", "high", chat_id_2)
    claimed = srv._session_claim(sess_key_2, turn_id="t2")

    assert not invalid_1 and not invalid_2
    assert sess_key_1 in srv._session_store
    assert claimed == "cid-turn-1"


def test_cwd_without_chat_id_keeps_cwd_session_key_and_skips_continuity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_flag(monkeypatch, "AGY_SESSION_CONTINUITY_ENABLED")
    _, req2 = _turn_requests()
    chat_id, invalid = srv._request_chat_id({}, {"cwd": "/abs/path"}, req2)
    sess_key = srv._session_key_for(_MODEL, "/abs/path", "high", chat_id)

    assert (chat_id, invalid) == ("", False)
    assert len(sess_key) == 3
    assert srv._CONTINUITY.link_count() == 0


@pytest.mark.parametrize("extra", [None])
def test_non_dict_extra_does_not_crash_and_keeps_continuity(
    monkeypatch: pytest.MonkeyPatch, extra: Any
) -> None:
    _enable_flag(monkeypatch, "AGY_SESSION_CONTINUITY_ENABLED")
    req1, _ = _turn_requests()
    chat_id, invalid = srv._request_chat_id({}, extra, req1)

    assert chat_id.startswith("cont-")
    assert not invalid

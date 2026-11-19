"""Adversarial QA (VER-005): continuity и notice agy-bridge под враждебными входами.

Только публичный API индекса/моста; без сокетов, subprocess и sleep; env, кэш
флагов и путь dynamic_config изолированы через monkeypatch + tmp_path.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path
from typing import Any

import pytest

_BRIDGE_PY = Path(__file__).resolve().parents[1] / "bridges" / "agy-bridge" / "server.py"
_MODEL = "gemini-4-neon"
_MARKER = "[truncation-notice]"
_SECRETS = ("SECRET_PAYLOAD_XYZ_999", "SENSITIVE_TOOL_BODY_777")
_ENV_CONT = "AGY_SESSION_CONTINUITY_ENABLED"
_ENV_NOTICE = "AGY_TRUNCATION_NOTICE_ENABLED"
_TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {"name": "read_file", "parameters": {}}}
]


def _load_bridge() -> Any:
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("AGY_BRIDGE_KEY", "test-key-agy-adversarial")
        mp.delenv("AGY_BRIDGE_FLEET", raising=False)
        spec = importlib.util.spec_from_file_location(
            "agy_bridge_server_continuity_adversarial", _BRIDGE_PY
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return module


srv = _load_bridge()


class _Spy:
    """Заглушка индекса: считает обращения к resolve."""

    def __init__(self) -> None:
        self.calls = 0

    def resolve(self, messages: object, scope: str = "") -> str:
        self.calls += 1
        return "spy-chain"


def _hist(user: str, rounds: int, tool: str = "ok") -> list[dict[str, Any]]:
    """История: [system, user] + `rounds` пар assistant(tool_call)/tool."""
    msgs: list[dict[str, Any]] = [
        {"role": "system", "content": "Ты помощник."},
        {"role": "user", "content": user},
    ]
    for n in range(rounds):
        fn = {"name": "read_file", "arguments": "{}"}
        call = {"id": f"call_{n}", "type": "function", "function": fn}
        msgs.append({"role": "assistant", "content": "", "tool_calls": [call]})
        msgs.append({"role": "tool", "tool_call_id": f"call_{n}", "content": f"{tool}-{n}"})
    return msgs


def _req(messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {"model": _MODEL, "messages": messages, "tools": _TOOLS}


def _new_index(logs: list[str] | None = None, max_links: int = 4096) -> Any:
    cfg = srv.ContinuityConfig(max_links, 1800.0, logs.append if logs is not None else None)
    return srv.ContinuityIndex(cfg)


def _write_cfg(path: Path, **flags: bool) -> None:
    path.write_text(json.dumps(flags), encoding="utf-8")
    srv._cfg_checked_at = None  # снимок флагов перечитывается без sleep/рестарта
    srv._cfg_key = None


@pytest.fixture(autouse=True)
def _isolation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Флаги выключены, динамический конфиг — во временный каталог, индекс свежий."""
    cfg = tmp_path / "dynamic_config.json"
    monkeypatch.delenv(_ENV_CONT, raising=False)
    monkeypatch.delenv(_ENV_NOTICE, raising=False)
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(cfg))
    monkeypatch.setattr(srv, "DYNAMIC_CONFIG_PATH", cfg)
    monkeypatch.setattr(srv, "_cfg_snapshot", srv._COLD_FLAGS)
    monkeypatch.setattr(srv, "_cfg_key", None)
    monkeypatch.setattr(srv, "_cfg_checked_at", None)
    monkeypatch.setattr(srv, "_CONTINUITY", _new_index())


def _interleave(rng: random.Random, turns: dict[str, int]) -> list[str]:
    """Случайный порядок ходов чатов; внутри чата порядок сохраняется."""
    left = dict(turns)
    order: list[str] = []
    while left:
        name = rng.choice(sorted(left))
        order.append(name)
        left[name] -= 1
        if not left[name]:
            del left[name]
    return order


def test_1000_random_chat_pairs_never_cross_resume() -> None:
    rng = random.Random(42)
    idx = _new_index(max_links=100_000)
    owners: dict[str, str] = {}
    for i in range(1000):
        users = {c: f"{c}{i}-{rng.getrandbits(64):x}" for c in ("A", "B")}
        done = {"A": 0, "B": 0}
        chains: dict[str, set[str]] = {"A": set(), "B": set()}
        for name in _interleave(rng, {"A": 3, "B": 3}):
            done[name] += 1
            chain = idx.resolve(_hist(users[name], done[name] - 1))
            chains[name].add(chain)
            assert owners.setdefault(chain, f"{name}{i}") == f"{name}{i}"
        assert len(chains["A"]) == len(chains["B"]) == 1
        assert chains["A"].isdisjoint(chains["B"])
    assert len(owners) == 2000


def test_identical_first_requests_conflict_then_independent_cold_chains() -> None:
    idx = _new_index()
    a1 = idx.resolve(_hist("same", 0))
    b1 = idx.resolve(_hist("same", 0))  # конфликт -> tombstone
    a2 = idx.resolve(_hist("same", 1, "A"))
    b2 = idx.resolve(_hist("same", 1, "B"))
    assert len({a1, b1, a2, b2}) == 4


def test_identical_first_requests_sequential_pop_order_keeps_chats_apart() -> None:
    idx = _new_index()
    a1 = idx.resolve(_hist("same", 0))
    a2 = idx.resolve(_hist("same", 1, "A"))  # pop префикса
    b1 = idx.resolve(_hist("same", 0))
    b2 = idx.resolve(_hist("same", 1, "B"))
    assert a2 == a1
    assert b1 != a1
    assert b2 == b1 != a2


def test_fork_retry_of_popped_prefix_starts_cold() -> None:
    idx = _new_index()
    chain_a = idx.resolve(_hist("u", 0))
    assert idx.resolve(_hist("u", 1, "A")) == chain_a
    retry = idx.resolve(_hist("u", 1, "A"))  # тот же префикс после pop
    assert retry != chain_a
    assert idx.resolve(_hist("u", 1, "A")) != retry  # и повторно — холодный


@pytest.mark.parametrize(
    ("header", "value"), [("x-dsh-chat-id", "chat-123"), ("x-session-id", "sess-777")]
)
def test_explicit_chat_id_beats_continuity(
    monkeypatch: pytest.MonkeyPatch, header: str, value: str
) -> None:
    monkeypatch.setenv(_ENV_CONT, "1")
    spy = _Spy()
    monkeypatch.setattr(srv, "_CONTINUITY", spy)
    req = _req(_hist("u", 1))
    assert srv._request_chat_id({header: value}, {}, req) == (value, False)
    assert spy.calls == 0
    assert srv._request_chat_id({}, {}, req) == ("spy-chain", False)  # флаг реально включён
    assert spy.calls == 1


def test_flags_off_bridge_behaves_like_base(monkeypatch: pytest.MonkeyPatch) -> None:
    logs: list[str] = []
    idx = _new_index(logs)
    monkeypatch.setattr(srv, "_CONTINUITY", idx)
    req = _req(_hist("u", 1))
    assert srv._request_chat_id({}, {"cwd": "/tmp/x"}, req) == ("", False)
    assert srv._request_chat_id({"x-dsh-chat-id": "c1"}, {}, req) == ("c1", False)
    assert idx.link_count() == 0 and logs == []
    token = hashlib.sha256(b"c1").hexdigest()
    assert srv._session_key_for(_MODEL, "/tmp/x", "high", "c1") == (token, _MODEL, "/tmp/x", "high")
    assert srv._session_key_for(_MODEL, "/tmp/x", "high", "") == (_MODEL, "/tmp/x", "high")
    assert srv._session_key_for(_MODEL, "", "high", "") == ()
    assert srv._session_key_for(_MODEL, "rel/path", "high", "") == ()
    assert srv._session_key_for(_MODEL, "", "high", "bad\x00id") == ()


def _big_messages(tool_text: str = "L") -> list[dict[str, Any]]:
    msgs = _hist("прочитай файл", 1)
    msgs[0] = {"role": "system", "content": "S" * 61000}
    msgs[-1] = {"role": "tool", "tool_call_id": "call_0", "content": tool_text * 60000}
    return msgs


def test_flags_off_prompt_has_no_notice_and_matches_explicit_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_off = srv._messages_to_prompt(_big_messages())
    monkeypatch.setenv(_ENV_NOTICE, "0")
    explicit_off = srv._messages_to_prompt(_big_messages())
    assert default_off == explicit_off
    assert _MARKER not in default_off
    assert srv._ndjson_bytes(default_off) <= srv._prompt_budget(0)
    small = _hist("u", 1)
    off_small = srv._messages_to_prompt(small)
    monkeypatch.setenv(_ENV_NOTICE, "1")
    assert srv._messages_to_prompt(small) == off_small  # без усечения — байт в байт
    assert _MARKER not in off_small
    assert _MARKER in srv._messages_to_prompt(_big_messages())


@pytest.mark.parametrize("flag", ["session_continuity_enabled", "truncation_notice_enabled"])
def test_dynamic_config_hot_toggle_false_true_false(tmp_path: Path, flag: str) -> None:
    cfg = tmp_path / "dynamic_config.json"
    seen: list[bool] = []
    for value in (False, True, False):
        _write_cfg(cfg, **{flag: value})
        seen.append(srv._new_flag(flag))
    assert seen == [False, True, False]


def test_dynamic_config_hot_toggle_changes_real_behavior(tmp_path: Path) -> None:
    cfg = tmp_path / "dynamic_config.json"
    req = _req(_hist("u", 0))
    results: list[tuple[bool, bool]] = []
    for value in (False, True, False):
        _write_cfg(cfg, session_continuity_enabled=value, truncation_notice_enabled=value)
        has_chain = bool(srv._request_chat_id({}, {}, req)[0])
        has_notice = _MARKER in srv._messages_to_prompt(_big_messages())
        results.append((has_chain, has_notice))
    assert results == [(False, False), (True, True), (False, False)]


def test_logs_never_contain_raw_message_content(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(_ENV_CONT, "1")
    monkeypatch.setenv(_ENV_NOTICE, "1")
    logs: list[str] = []
    monkeypatch.setattr(srv, "_CONTINUITY", _new_index(logs))
    policy = srv.NoticePolicy(srv._ndjson_bytes, None, logs.append)
    monkeypatch.setattr(srv, "_NOTICE_POLICY", policy)
    msgs = _hist(_SECRETS[0], 1, _SECRETS[1])
    for rounds in (0, 1):
        srv._request_chat_id({}, {}, _req(msgs[: 2 + 2 * rounds]))
    srv._messages_to_prompt(_big_messages(_SECRETS[1]))
    streams = capsys.readouterr()
    blob = "\n".join(logs) + streams.out + streams.err
    assert any(line.startswith("continuity status=") for line in logs)
    assert any(line.startswith("truncation_notice ") for line in logs)
    assert not any(secret in blob for secret in _SECRETS)


@pytest.mark.parametrize("reverse", [False, True])
def test_chat_order_forward_and_reverse_has_no_leakage(reverse: bool) -> None:
    idx = _new_index()
    names = [f"chat-{n}" for n in range(60)]
    if reverse:
        names.reverse()
    per_chat: dict[str, list[str]] = {}
    for name in names:
        per_chat[name] = [idx.resolve(_hist(name, r)) for r in range(3)]
    assert all(len(set(chains)) == 1 for chains in per_chat.values())
    assert len({chains[0] for chains in per_chat.values()}) == len(names)

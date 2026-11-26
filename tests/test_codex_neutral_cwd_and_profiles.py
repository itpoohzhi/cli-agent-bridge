"""Unit-тесты Wave 2: очистка `profiles.*` Zero-Canon и neutral fallback CWD для Codex Standard."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from adapters.stdio_resident_runtime import (
    _resolve_default_cwd,
    build_resident_envelope_from_chat,
    build_turn_request_from_ctx,
)
from core.stdio_resident import codex_std_home
from core.stdio_resident.codex_std_home import CODEX_STD_NEUTRAL_CWD_FLAG
from core.subbridge_zero_canon import filter_codex_config

_SECRET = b"s" * 32


@pytest.fixture(autouse=True)
def _isolated_flag_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BRIDGE_DYNAMIC_CONFIG_PATH", str(tmp_path / "missing_dynamic_config.json"))
    monkeypatch.setattr(codex_std_home.tempfile, "gettempdir", lambda: str(tmp_path))


def _flag(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(CODEX_STD_NEUTRAL_CWD_FLAG, value)


def _ctx(cwd: str) -> Any:
    return SimpleNamespace(
        conversation_id="c1", turn_id="t1", rid="r1", model="m", effort="medium", cwd=cwd,
        prompt="hi", fwd_env={}, rpc=None, images=(), tool_schemas={}, emulate_tools=False,
        tool_choice=None, conversation_ephemeral=False,
    )


def test_filter_codex_config_strips_profiles_recursively() -> None:
    raw = {
        "model": "gpt-x",
        "mcp_servers": {"top": {"command": "x"}},
        "profiles": {
            "work": {
                "model": "gpt-y",
                "model_reasoning_effort": "high",
                "mcp_servers": {"w": {"command": "y"}},
                "plugins": {"p": {}},
                "notify": ["say"],
                "hooks": {"h": {}},
                "project_doc_max_bytes": 65536,
                "nested": {"hooks": {"a": 1}, "keep": 1, "deep": {"plugins": {}, "ok": True}},
            },
            "other": {"model": "gpt-z"},
        },
    }
    out = filter_codex_config(raw)
    work = out["profiles"]["work"]
    assert "mcp_servers" not in out
    assert work["model"] == "gpt-y"
    assert work["model_reasoning_effort"] == "high"
    for key in ("mcp_servers", "plugins", "notify", "hooks", "project_doc_max_bytes"):
        assert key not in work
    assert work["nested"] == {"keep": 1, "deep": {"ok": True}}
    assert out["profiles"]["other"] == {"model": "gpt-z"}
    assert out["project_doc_max_bytes"] == 0
    assert "mcp_servers" in raw["profiles"]["work"]  # вход не мутируется


def test_filter_codex_config_without_profiles_unchanged() -> None:
    out = filter_codex_config({"model": "m"})
    assert out == {"model": "m", "project_doc_max_bytes": 0}


def test_flag_off_empty_cwd_is_getcwd(monkeypatch: pytest.MonkeyPatch) -> None:
    _flag(monkeypatch, "false")
    assert _resolve_default_cwd("codex", "") == os.getcwd()
    assert build_turn_request_from_ctx("codex", _ctx(""), "standard")["cwd"] == os.getcwd()
    env, _ = build_resident_envelope_from_chat("codex", {"prompt": "x"}, _SECRET)
    assert env.cwd_norm == os.path.realpath(os.getcwd())


def test_flag_on_codex_standard_empty_cwd_is_neutral_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    _flag(monkeypatch, "true")
    got = _resolve_default_cwd("codex", "")
    path = Path(got)
    assert got != os.getcwd()
    assert path.is_dir()
    assert not (path / "AGENTS.md").exists()
    assert list(path.iterdir()) == []
    assert stat.S_IMODE(path.stat().st_mode) == 0o700
    req_cwd = build_turn_request_from_ctx("codex", _ctx(""), "standard")["cwd"]
    assert req_cwd not in ("", os.getcwd())
    assert not (Path(req_cwd) / "AGENTS.md").exists()
    env, _ = build_resident_envelope_from_chat("codex", {"prompt": "x", "cwd": None}, _SECRET)
    assert env.cwd_norm != os.path.realpath(os.getcwd())
    assert not (Path(env.cwd_norm) / "AGENTS.md").exists()


def test_flag_on_keyed_chat_without_cwd_keeps_stable_cwd_norm(monkeypatch: pytest.MonkeyPatch) -> None:
    _flag(monkeypatch, "true")
    body = {"prompt": "x", "chat_id": "chat-1"}
    first, _ = build_resident_envelope_from_chat("codex", body, _SECRET)
    second, _ = build_resident_envelope_from_chat("codex", body, _SECRET)
    assert first.cwd_norm == second.cwd_norm
    assert first.cwd_norm != os.path.realpath(os.getcwd())


def test_flag_on_explicit_cwd_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    _flag(monkeypatch, "true")
    assert _resolve_default_cwd("codex", "/tmp/proj-with-agents") == "/tmp/proj-with-agents"
    assert build_turn_request_from_ctx("codex", _ctx("/tmp/proj-with-agents"), "standard")["cwd"] == (
        "/tmp/proj-with-agents"
    )
    env, _ = build_resident_envelope_from_chat("codex", {"prompt": "x", "cwd": "/tmp/proj-with-agents"}, _SECRET)
    assert env.cwd_norm == os.path.realpath("/tmp/proj-with-agents")


@pytest.mark.parametrize("adapter", ["claude", "muse", "agy"])
def test_flag_on_non_codex_adapter_uses_getcwd(monkeypatch: pytest.MonkeyPatch, adapter: str) -> None:
    _flag(monkeypatch, "true")
    assert _resolve_default_cwd(adapter, "") == os.getcwd()
    assert build_turn_request_from_ctx(adapter, _ctx(""), "standard")["cwd"] == os.getcwd()


def test_flag_on_zero_canon_not_intercepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _flag(monkeypatch, "true")
    assert _resolve_default_cwd("codex", "", "zero-canon") == os.getcwd()
    assert build_turn_request_from_ctx("codex", _ctx(""), "zero-canon")["cwd"] == os.getcwd()
    env, _ = build_resident_envelope_from_chat(
        "codex", {"prompt": "x", "review_profile": "zero-canon"}, _SECRET
    )
    assert env.cwd_norm == os.path.realpath(os.getcwd())

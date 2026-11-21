"""Юнит-тесты чистого домена Zero-Canon суб-мостов и роутера (без записи в ~)."""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
if str(_Path(__file__).resolve().parents[1]) not in _sys.path:
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import tomllib
from pathlib import Path

import pytest

from core import subbridge_zero_canon as zc
from core.stdio_resident.zero_canon_router import (
    DEFAULT_CLAUDE_BRIDGE_URL,
    KIND_BRIDGE,
    KIND_EPHEMERAL,
    KIND_RESIDENT,
    decide_zero_canon_route,
    zero_canon_isolation,
)

ROOT = Path(__file__).resolve().parents[1]


def test_domain_module_is_pure_stdlib_without_io_or_environ() -> None:
    path = ROOT / "core" / "subbridge_zero_canon.py"
    text = path.read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 250
    for forbidden in ("os.environ", "import os", "open(", "pathlib", "subprocess", "socket"):
        assert forbidden not in text


@pytest.mark.parametrize(
    ("base_path", "trust", "expected"),
    [
        ("/claude", "", True),
        ("/claude", "local", True),
        ("", "trusted", True),
        ("/sg-gemini", "", False),
        ("/sg-x/v1", "local", False),
        ("/claude", "external", False),
        ("/sg-x", "external", False),
    ],
)
def test_should_forward_review_profile(base_path: str, trust: str, expected: bool) -> None:
    assert zc.should_forward_review_profile(base_path, trust) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Zero-Canon", "zero-canon"),
        ("  ZERO-CANON ", "zero-canon"),
        ("zero-canon", "zero-canon"),
        ("standard", "standard"),
        ("zero_canon", "standard"),
        ("", "standard"),
        (None, "standard"),
    ],
)
def test_normalize_review_profile(value: str | None, expected: str) -> None:
    assert zc.normalize_review_profile(value) == expected
    assert zc.is_zero_canon_profile(value) is (expected == "zero-canon")


def test_review_profile_from_headers_is_case_insensitive() -> None:
    assert zc.review_profile_from_headers({"x-review-profile": "Zero-Canon"}) == "zero-canon"
    assert zc.review_profile_from_headers({"X-REVIEW-PROFILE": "zero-canon"}) == "zero-canon"
    assert zc.review_profile_from_headers({"X-Other": "zero-canon"}) == "standard"
    assert zc.review_profile_from_headers(None) == "standard"


def test_flag_names_are_stable_contract() -> None:
    assert zc.CODEX_CONFIG_DENY_SECTIONS == ("mcp_servers", "plugins", "notify")
    assert zc.MUSE_ZERO_CANON_FLAG == "MUSE_ZERO_CANON_ENABLED"
    assert zc.OPENCODE_ZERO_CANON_FLAG == "OPENCODE_ZERO_CANON_ENABLED"
    assert zc.HUB_ZERO_CANON_ROUTING_FLAG == "HUB_ZERO_CANON_ROUTING_ENABLED"


def test_filter_codex_config_drops_denied_sections_and_blocks_agents_md() -> None:
    raw = {
        "model": "gpt-x",
        "mcp_servers": {"a": {"command": "x"}},
        "plugins": {"p": {}},
        "notify": ["say", "hi"],
        "hooks": {"on_start": "x"},
        "profiles": {"fast": {"model": "m"}},
    }
    result = zc.filter_codex_config(raw)
    assert result == {
        "model": "gpt-x",
        "profiles": {"fast": {"model": "m"}},
        "project_doc_max_bytes": 0,
    }
    assert "mcp_servers" in raw  # вход не мутируется
    raw["profiles"]["fast"]["model"] = "changed"
    assert result["profiles"]["fast"]["model"] == "m"


def test_dump_toml_roundtrips_through_tomllib() -> None:
    table = {
        "model": 'we"ird\\name',
        "flag": True,
        "ratio": 1.5,
        "n": 3,
        "list": ["a", "b"],
        "profiles": {"fast": {"model": "m", "deep": {"x": 1}}},
        "empty": {},
    }
    assert tomllib.loads(zc.dump_toml(table)) == table


def test_filter_muse_settings_keeps_only_allowlist() -> None:
    raw = {"provider": "p", "model": "m", "mcp": {"x": 1}, "hooks": [1], "theme": "dark"}
    assert zc.filter_muse_settings(raw) == {"provider": "p", "model": "m"}
    with pytest.raises(TypeError):
        zc.filter_muse_settings([])  # type: ignore[arg-type]


def test_filter_opencode_config_forces_ask_permission() -> None:
    raw = {
        "model": "m", "mcp": {"x": 1}, "plugin": ["p"], "instructions": ["AGENTS.md"],
        "permission": {"*": "allow"},
    }
    assert zc.filter_opencode_config(raw) == {"model": "m", "permission": {"*": "ask"}}
    assert zc.filter_opencode_config({}) == {"permission": {"*": "ask"}}


def test_router_default_flag_off_never_routes_to_bridge() -> None:
    assert decide_zero_canon_route("zero-canon", "claude-stream-json", {}).kind == KIND_EPHEMERAL
    standard = decide_zero_canon_route("standard", "claude-stream-json", {})
    assert (standard.kind, standard.is_ephemeral) == (KIND_RESIDENT, False)


def test_router_flag_on_routes_zero_canon_claude_to_bridge() -> None:
    env = {"HUB_ZERO_CANON_ROUTING_ENABLED": "1"}
    route = decide_zero_canon_route("Zero-Canon", "claude-stream-json", env)
    assert (route.kind, route.base_url) == (KIND_BRIDGE, DEFAULT_CLAUDE_BRIDGE_URL)
    custom = {**env, "HUB_ZERO_CANON_CLAUDE_BRIDGE_URL": "http://127.0.0.1:19881/v1"}
    assert decide_zero_canon_route("zero-canon", "claude-stream-json", custom).base_url.endswith(":19881/v1")
    # Не-Claude протоколы и стандартный профиль мост не затрагивает.
    assert decide_zero_canon_route("zero-canon", "codex-app-server", env).kind == KIND_EPHEMERAL
    assert decide_zero_canon_route("standard", "claude-stream-json", env).kind == KIND_RESIDENT


def test_isolation_creates_and_removes_private_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))

    class Driver:
        def build_zero_canon_env(self, base: dict[str, str], root: str) -> dict[str, str]:
            return {**base, "HOME": root}

        def build_zero_canon_argv(self, argv: list[str], model: str = "", effort: str = "") -> list[str]:
            return [*argv, "--m", model]

    with zero_canon_isolation(Driver(), "zero-canon") as iso:
        assert iso.active and iso.root is not None
        root = Path(iso.root)
        assert root.parent == tmp_path and root.is_dir()
        assert (root.stat().st_mode & 0o777) == 0o700
        assert iso.env({"A": "1"}) == {"A": "1", "HOME": str(root)}
        assert iso.argv(["x"], "m1", "") == ["x", "--m", "m1"]
    assert not root.exists()
    with zero_canon_isolation(Driver(), "standard") as plain:
        assert not plain.active and plain.env({}) is None and plain.argv(["x"], "m", "e") == ["x"]
    with pytest.raises(RuntimeError, match="zero_canon_unsupported_by_driver"):
        with zero_canon_isolation(object(), "zero-canon"):
            pass
    assert [p for p in tmp_path.iterdir() if p.name.startswith("zc-")] == []


def test_dump_toml_preserves_array_of_tables() -> None:
    import tomllib
    from core.subbridge_zero_canon import dump_toml

    raw = {
        "model": "gpt-6",
        "items": [
            {"name": "a", "k": 1, "nested": {"x": 10}},
            {"name": "b", "k": 2, "nested": {"x": 20}},
        ],
    }
    parsed = tomllib.loads(dump_toml(raw))
    assert parsed == raw


def test_proxy_rejects_non_loopback_url() -> None:
    from core.stdio_resident.zero_canon_router import proxy_zero_canon_bridge_turn

    with pytest.raises(ValueError, match="non_loopback_zero_canon_bridge_url"):
        proxy_zero_canon_bridge_turn("https://evil.example/v1", "m", "hi")

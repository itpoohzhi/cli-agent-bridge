"""Domain unit tests for Agy Zero-Canon rules and CLI turn flags."""
from __future__ import annotations

import ast
from email.message import Message
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import agy_zero_canon as zc  # noqa: E402
from core.cli_turn_flags import build_turn_cli_flags, text_turn_cli_flags  # noqa: E402
CORE_PATH = ROOT / "core" / "agy_zero_canon.py"
FORBIDDEN_IMPORTS = frozenset({
    "os", "pathlib", "subprocess", "shutil", "tempfile", "pwd", "socket",
    "http", "urllib", "sys", "signal", "atexit", "threading", "importlib",
    "logging",
})
CC_NODES = (
    ast.If, ast.While, ast.For, ast.AsyncFor,
    ast.ExceptHandler, ast.With, ast.AsyncWith, ast.IfExp,
)


def _cc(fn: ast.AST) -> int:
    return 1 + sum(
        1 if isinstance(n, CC_NODES) else (
            len(n.values) - 1 if isinstance(n, ast.BoolOp)
            else (len(n.ifs) if isinstance(n, ast.comprehension) else 0)
        )
        for n in ast.walk(fn)
    )


def test_constants_and_ast_purity() -> None:
    assert zc.SCHEMA_VERSION == "1.0"
    assert zc.ENV_POLICY_VERSION == "pol-env/3"
    assert zc.REVIEW_PROFILE_HEADER == "X-Review-Profile"
    assert zc.REVIEW_PROFILE_VALUE == "Zero-Canon"
    assert zc.AGY_ZERO_CANON_FLAG == "AGY_ZERO_CANON_ENABLED"
    assert zc.AGY_SETTINGS_ALLOWLIST == frozenset(("selectedAuthType", "theme", "security", "auth"))
    assert zc.AGY_SETTINGS_OVERRIDES == {"hooks": {}, "mcpServers": {}}
    assert zc.zero_canon_settings_cli_arg() == "{}"
    assert zc.zero_canon_profile_tag(True) == "zero-canon"
    assert zc.zero_canon_profile_tag(False) == "standard"

    src = CORE_PATH.read_text(encoding="utf-8")
    assert len(src.splitlines()) <= 250
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(a.name.split(".")[0] not in FORBIDDEN_IMPORTS for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in FORBIDDEN_IMPORTS
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert node.end_lineno is not None and (node.end_lineno - node.lineno + 1) <= 40, node.name
            assert _cc(node) <= 10, node.name


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Zero-Canon", True),
        (" zero-canon ", True),
        ("ZERO-CANON", True),
        ("standard", False),
        ("", False),
        (None, False),
        ({"X-Review-Profile": "Zero-Canon"}, True),
        ({"x-review-profile": "zero-canon"}, True),
        ({"X-REVIEW-PROFILE": "  ZERO-CANON  "}, True),
        ({"X-Review-Profile": "standard"}, False),
        ({"X-Other": "Zero-Canon"}, False),
        ({}, False),
    ],
)
def test_is_zero_canon_review_profile_case_insensitive(value: object, expected: bool) -> None:
    assert zc.is_zero_canon_review_profile(value) is expected


def test_is_zero_canon_review_profile_http_message() -> None:
    msg = Message()
    msg["x-review-profile"] = "Zero-Canon"
    assert zc.is_zero_canon_review_profile(msg) is True
    other = Message()
    other["X-Review-Profile"] = "default"
    assert zc.is_zero_canon_review_profile(other) is False


def test_filter_agy_settings_allowlist_and_zero_leaks() -> None:
    forbidden_keys = (
        "trustedWorkspaces",
        "permissions",
        "allowNonWorkspaceAccess",
        "model",
        "artifactReviewPolicy",
        "toolPermission",
    )
    raw = {
        "selectedAuthType": "oauth-personal",
        "theme": "dark",
        "security": {"auth": {"selectedType": "oauth"}},
        "auth": {"mode": "oauth"},
        "hooks": {"PreToolUse": [{"cmd": "evil.sh"}]},
        "mcpServers": {"evil": {"command": "sh"}},
        "trustedWorkspaces": ["/Users/secret"],
        "permissions": {"allow": ["Bash(*)"]},
        "allowNonWorkspaceAccess": True,
        "model": "gemini-pro",
        "artifactReviewPolicy": "always",
        "toolPermission": "auto",
        "extraUnknownKey": "leak",
    }
    filtered = zc.filter_agy_settings(raw)
    assert filtered == {
        "selectedAuthType": "oauth-personal",
        "theme": "dark",
        "security": {"auth": {"selectedType": "oauth"}},
        "auth": {"mode": "oauth"},
        "hooks": {},
        "mcpServers": {},
    }
    for key in forbidden_keys:
        assert key not in filtered
    filtered["security"]["auth"]["selectedType"] = "mutated"
    assert raw["security"]["auth"]["selectedType"] == "oauth"
    with pytest.raises(TypeError):
        zc.filter_agy_settings(["not-a-dict"])  # type: ignore[arg-type]


def test_build_agy_zero_canon_plan() -> None:
    active = zc.build_agy_zero_canon_plan({"x-review-profile": "zero-canon"}, flag_enabled=True)
    assert active == zc.AgyZeroCanonPlan(
        enabled=True,
        profile_tag="zero-canon",
        use_zc_home=True,
        force_disable_slash_commands=True,
        use_empty_cwd=True,
        isolate_builtin_ro=True,
        settings_arg="{}",
    )
    killed = zc.build_agy_zero_canon_plan({"X-Review-Profile": "Zero-Canon"}, flag_enabled=False)
    assert killed == zc.AgyZeroCanonPlan(
        enabled=False,
        profile_tag="standard",
        use_zc_home=False,
        force_disable_slash_commands=False,
        use_empty_cwd=False,
        isolate_builtin_ro=False,
        settings_arg=None,
    )
    standard = zc.build_agy_zero_canon_plan({}, flag_enabled=True)
    assert standard.enabled is False
    assert standard.profile_tag == "standard"
    assert standard.settings_arg is None


def test_cli_turn_flags_zero_canon_all_modes() -> None:
    for mode in ("ask", "plan"):
        assert build_turn_cli_flags(mode, {}) == ["--disable-slash-commands"]
        assert text_turn_cli_flags(mode, {}) == ["--disable-slash-commands"]
        assert build_turn_cli_flags(mode, {"AGY_BRIDGE_DISABLE_SLASH_COMMANDS": "0"}) == []
    for mode in ("agent", "auto", "emulate"):
        assert build_turn_cli_flags(mode, {}) == []
        assert text_turn_cli_flags(mode, {}) == []
    for mode in ("ask", "plan", "agent", "auto", "emulate"):
        assert build_turn_cli_flags(mode, {}, zero_canon=True) == ["--disable-slash-commands"]
        assert build_turn_cli_flags(
            mode, {"AGY_BRIDGE_DISABLE_SLASH_COMMANDS": "0"}, zero_canon=True
        ) == ["--disable-slash-commands"]
        assert text_turn_cli_flags(mode, {}, zero_canon=True) == ["--disable-slash-commands"]

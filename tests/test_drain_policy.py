"""Wave 0 contract tests for `core.drain_policy` (pure stdlib leaf module)."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DRAIN_POLICY_PATH = ROOT / "core" / "drain_policy.py"
FORBIDDEN_IMPORTS = frozenset(
    {
        "os",
        "sys",
        "socket",
        "subprocess",
        "asyncio",
        "http",
        "urllib",
        "pathlib",
    }
)


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": ""}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "1"}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "true"}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "True"}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "  TRUE  "}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "yes"}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": " YeS "}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "on"}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": " ON "}, True),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "0"}, False),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "false"}, False),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "False"}, False),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "  FALSE "}, False),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "no"}, False),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": " No "}, False),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "off"}, False),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": " OFF "}, False),
    ],
)
def test_is_drain_policy_enabled(env: dict[str, str], expected: bool) -> None:
    from core.drain_policy import is_drain_policy_enabled

    assert is_drain_policy_enabled(MappingProxyType(env)) is expected


@pytest.mark.parametrize("raw", ["1", "7", "60"])
def test_resolve_retry_after_s_valid_env_same_for_main_and_subagent(raw: str) -> None:
    from core.drain_policy import resolve_retry_after_s

    env = MappingProxyType({"BRIDGE_RETRY_AFTER_S": raw})
    expected = int(raw)
    assert resolve_retry_after_s(env, is_subagent=False) == expected
    assert resolve_retry_after_s(env, is_subagent=True) == expected


@pytest.mark.parametrize("raw", ["0", "-5", "abc", ""])
@pytest.mark.parametrize(("is_subagent", "expected"), [(False, 5), (True, 3)])
def test_resolve_retry_after_s_invalid_or_nonpositive_falls_back_safely(
    raw: str, is_subagent: bool, expected: int
) -> None:
    from core.drain_policy import resolve_retry_after_s

    env = MappingProxyType({"BRIDGE_RETRY_AFTER_S": raw})
    result = resolve_retry_after_s(env, is_subagent=is_subagent)
    assert result == expected
    assert result >= 1


def test_resolve_retry_after_s_unset_defaults() -> None:
    from core.drain_policy import resolve_retry_after_s

    empty = MappingProxyType({})
    assert resolve_retry_after_s(empty, is_subagent=False) == 5
    assert resolve_retry_after_s(empty, is_subagent=True) == 3


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"BRIDGE_RETRY_AFTER_S": "999"}, 60),
        ({"BRIDGE_RETRY_AFTER_S": "999", "BRIDGE_RETRY_AFTER_MAX_S": "15"}, 15),
        ({"BRIDGE_RETRY_AFTER_S": "999", "BRIDGE_RETRY_AFTER_MAX_S": "bad"}, 60),
        ({"BRIDGE_RETRY_AFTER_S": "999", "BRIDGE_RETRY_AFTER_MAX_S": "0"}, 60),
        ({"BRIDGE_RETRY_AFTER_S": "999", "BRIDGE_RETRY_AFTER_MAX_S": "-3"}, 60),
        ({"BRIDGE_RETRY_AFTER_S": "999", "BRIDGE_RETRY_AFTER_MAX_S": ""}, 60),
    ],
)
def test_resolve_retry_after_s_ceiling_and_max_override(
    env: dict[str, str], expected: int
) -> None:
    from core.drain_policy import resolve_retry_after_s

    assert resolve_retry_after_s(MappingProxyType(env)) == expected
    assert resolve_retry_after_s(MappingProxyType(env), is_subagent=True) == expected


@pytest.mark.parametrize(
    ("env", "explicit", "expected"),
    [
        ({}, 0, 1),
        ({}, -2, 1),
        ({}, 120, 60),
        ({"BRIDGE_RETRY_AFTER_MAX_S": "15"}, 120, 15),
        ({}, 8, 8),
    ],
)
def test_resolve_retry_after_s_explicit_clamped(
    env: dict[str, str], explicit: int, expected: int
) -> None:
    from core.drain_policy import resolve_retry_after_s

    assert resolve_retry_after_s(MappingProxyType(env), explicit=explicit) == expected


@pytest.mark.parametrize(
    ("env", "is_subagent", "legacy_default", "expected"),
    [
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "0"}, False, 9, 9),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "0"}, True, 9, 9),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "0"}, False, 0, 1),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "0"}, False, -4, 1),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "0"}, False, 200, 60),
        (
            {"BRIDGE_DRAIN_POLICY_ENABLED": "0", "BRIDGE_RETRY_AFTER_MAX_S": "15"},
            False,
            200,
            15,
        ),
        (
            {"BRIDGE_DRAIN_POLICY_ENABLED": "0", "BRIDGE_RETRY_AFTER_S": "12"},
            False,
            9,
            12,
        ),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "0"}, False, None, 5),
        ({"BRIDGE_DRAIN_POLICY_ENABLED": "0"}, True, None, 3),
    ],
)
def test_resolve_retry_after_s_kill_switch_uses_clamped_legacy_default(
    env: dict[str, str],
    is_subagent: bool,
    legacy_default: int | None,
    expected: int,
) -> None:
    from core.drain_policy import resolve_retry_after_s

    result = resolve_retry_after_s(
        MappingProxyType(env),
        is_subagent=is_subagent,
        legacy_default=legacy_default,
    )
    assert result == expected


@pytest.mark.parametrize(
    ("configured", "exit_timeout", "expected"),
    [
        (110.0, 180.0, (110.0, False)),
        (300.0, 180.0, (168.0, True)),
        (110.0, 60.0, (48.0, True)),
        (110.0, None, (110.0, False)),
        (110.0, 5.0, (1.0, True)),
    ],
)
def test_effective_hub_drain_timeout_s_defaults(
    configured: float, exit_timeout: float | None, expected: tuple[float, bool]
) -> None:
    from core.drain_policy import effective_hub_drain_timeout_s

    assert effective_hub_drain_timeout_s(configured, exit_timeout) == expected


def test_effective_hub_drain_timeout_s_custom_tail_and_margin() -> None:
    from core.drain_policy import effective_hub_drain_timeout_s

    assert effective_hub_drain_timeout_s(
        110.0, 100.0, tail_s=10.0, margin_s=10.0
    ) == (80.0, True)
    assert effective_hub_drain_timeout_s(
        50.0, 100.0, tail_s=10.0, margin_s=10.0
    ) == (50.0, False)


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({}, 0.0),
        ({"BRIDGE_DRAIN_HOLD_TIMEOUT_S": "0.0"}, 0.0),
        ({"BRIDGE_DRAIN_HOLD_TIMEOUT_S": "abc"}, 0.0),
        ({"BRIDGE_DRAIN_HOLD_TIMEOUT_S": "-3"}, 0.0),
        ({"BRIDGE_DRAIN_HOLD_TIMEOUT_S": "5.5"}, 5.5),
        ({"BRIDGE_DRAIN_HOLD_TIMEOUT_S": "99"}, 30.0),
        ({"BRIDGE_DRAIN_HOLD_TIMEOUT_S": "nan"}, 0.0),
    ],
)
def test_resolve_drain_hold_timeout_s(env: dict[str, str], expected: float) -> None:
    from core.drain_policy import resolve_drain_hold_timeout_s

    assert resolve_drain_hold_timeout_s(MappingProxyType(env)) == expected


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"BRIDGE_EXIT_TIMEOUT_S": "180"}, 180.0),
        ({"BRIDGE_EXIT_TIMEOUT_S": "60.5"}, 60.5),
        ({"BRIDGE_EXIT_TIMEOUT_S": "0"}, None),
        ({"BRIDGE_EXIT_TIMEOUT_S": "-1"}, None),
        ({"BRIDGE_EXIT_TIMEOUT_S": "bad"}, None),
        ({"BRIDGE_EXIT_TIMEOUT_S": ""}, None),
        ({}, None),
    ],
)
def test_parse_exit_timeout_s(env: dict[str, str], expected: float | None) -> None:
    from core.drain_policy import parse_exit_timeout_s

    assert parse_exit_timeout_s(MappingProxyType(env)) == expected


def test_drain_policy_ast_purity_m_mod_i3() -> None:
    """M-MOD-I3: `core/drain_policy.py` is a pure stdlib leaf without I/O or process imports."""
    assert DRAIN_POLICY_PATH.is_file(), f"Missing module: {DRAIN_POLICY_PATH}"
    source = DRAIN_POLICY_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(DRAIN_POLICY_PATH))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
    violations = sorted(imported_roots & FORBIDDEN_IMPORTS)
    assert not violations, f"Forbidden imports in core/drain_policy.py: {violations}"

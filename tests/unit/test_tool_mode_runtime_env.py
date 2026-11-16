"""L1: чтение политики toolless-тегов из окружения (core/runtime_env.py)."""

from __future__ import annotations

import logging

import pytest

from core.runtime_env import resolve_toolless_tag_policy
from core.tool_mode import ToollessTagPolicy

POLICY_ENV = "BRIDGE_TOOLLESS_TOOL_TAG_POLICY"


@pytest.mark.parametrize("default", (ToollessTagPolicy.TEXT, ToollessTagPolicy.ERROR))
def test_missing_variable_returns_supplied_default(default: ToollessTagPolicy) -> None:
    assert resolve_toolless_tag_policy({}, default=default) is default


@pytest.mark.parametrize("default", (ToollessTagPolicy.TEXT, ToollessTagPolicy.ERROR))
@pytest.mark.parametrize("raw", ("", "   ", "\t"))
def test_empty_or_blank_variable_returns_supplied_default(
    raw: str, default: ToollessTagPolicy
) -> None:
    result = resolve_toolless_tag_policy({POLICY_ENV: raw}, default=default)
    assert result is default


def test_omitted_default_is_text_for_missing_and_empty() -> None:
    assert resolve_toolless_tag_policy({}) is ToollessTagPolicy.TEXT
    assert resolve_toolless_tag_policy({POLICY_ENV: ""}) is ToollessTagPolicy.TEXT


@pytest.mark.parametrize(
    "raw,expected",
    (
        ("text", ToollessTagPolicy.TEXT),
        ("TEXT", ToollessTagPolicy.TEXT),
        ("  Text  ", ToollessTagPolicy.TEXT),
        ("error", ToollessTagPolicy.ERROR),
        ("ERROR", ToollessTagPolicy.ERROR),
    ),
)
@pytest.mark.parametrize("default", (ToollessTagPolicy.TEXT, ToollessTagPolicy.ERROR))
def test_explicit_value_wins_over_default_case_insensitively(
    raw: str, expected: ToollessTagPolicy, default: ToollessTagPolicy
) -> None:
    result = resolve_toolless_tag_policy({POLICY_ENV: raw}, default=default)
    assert result is expected


@pytest.mark.parametrize("raw", ("bogus", "off", "0", "textual"))
def test_invalid_value_fails_closed_to_error_even_with_text_default(
    raw: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="core.runtime_env"):
        result = resolve_toolless_tag_policy(
            {POLICY_ENV: raw}, default=ToollessTagPolicy.TEXT
        )
    assert result is ToollessTagPolicy.ERROR
    assert [r.getMessage() for r in caplog.records] == [
        "Invalid BRIDGE_TOOLLESS_TOOL_TAG_POLICY; using error policy"
    ]


def test_invalid_value_message_does_not_echo_the_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="core.runtime_env"):
        resolve_toolless_tag_policy({POLICY_ENV: "sekret-token-value"})
    assert "sekret-token-value" not in caplog.text


def test_valid_and_missing_values_do_not_log(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="core.runtime_env"):
        resolve_toolless_tag_policy({})
        resolve_toolless_tag_policy({POLICY_ENV: "text"})
    assert caplog.records == []


def test_resolution_reads_mapping_only_and_does_not_mutate_process_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(POLICY_ENV, "error")
    assert resolve_toolless_tag_policy({}) is ToollessTagPolicy.TEXT
    assert resolve_toolless_tag_policy({POLICY_ENV: "text"}) is ToollessTagPolicy.TEXT

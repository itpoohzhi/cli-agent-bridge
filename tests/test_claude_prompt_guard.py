from __future__ import annotations

import pytest

from core.claude_prompt import PromptBudgetConfig, prepare_prompt_with_cap

ENV_KEY = "CLAUDE_P_BRIDGE_MAX_PROMPT_BYTES"


def test_config_default_is_disabled() -> None:
    assert PromptBudgetConfig().max_prompt_bytes == 0
    assert PromptBudgetConfig.from_env({}).max_prompt_bytes == 0


def test_config_from_env_reads_environ_when_env_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_KEY, "512")
    assert PromptBudgetConfig.from_env().max_prompt_bytes == 512
    monkeypatch.delenv(ENV_KEY)
    assert PromptBudgetConfig.from_env().max_prompt_bytes == 0


@pytest.mark.parametrize(("raw", "expected"), [("1024", 1024), (" 7 ", 7), ("0", 0)])
def test_config_from_env_valid(raw: str, expected: int) -> None:
    assert PromptBudgetConfig.from_env({ENV_KEY: raw}).max_prompt_bytes == expected


@pytest.mark.parametrize("raw", ["", "abc", "-5", "1.5", "12kb"])
def test_config_from_env_invalid_is_zero(raw: str) -> None:
    assert PromptBudgetConfig.from_env({ENV_KEY: raw}).max_prompt_bytes == 0


def test_prepare_cap_zero_is_disabled() -> None:
    result = prepare_prompt_with_cap("x" * 10_000, PromptBudgetConfig(0))
    assert result.exceeded is False
    assert result.error_status is None
    assert result.error_body is None
    assert result.byte_length == 10_000


def test_prepare_under_and_exact_cap_ok() -> None:
    cfg = PromptBudgetConfig(max_prompt_bytes=10)
    for prompt in ("a" * 9, "a" * 10):
        result = prepare_prompt_with_cap(prompt, cfg)
        assert result.exceeded is False
        assert result.error_status is None
        assert result.prompt == prompt


def test_prepare_over_cap_returns_413_without_truncation() -> None:
    prompt = "a" * 11
    result = prepare_prompt_with_cap(prompt, PromptBudgetConfig(max_prompt_bytes=10))
    assert result.exceeded is True
    assert result.error_status == 413
    assert result.prompt == prompt
    assert result.byte_length == 11
    assert result.max_prompt_bytes == 10
    assert result.error_body is not None
    error = result.error_body["error"]
    assert isinstance(error, dict)
    assert error["code"] == "prompt_too_large"
    assert error["type"] == "invalid_request_error"
    assert isinstance(error["message"], str)


def test_prepare_counts_utf8_bytes_not_chars() -> None:
    prompt = "й" * 5  # 5 символов, 10 байт
    assert len(prompt) == 5
    at_cap = prepare_prompt_with_cap(prompt, PromptBudgetConfig(max_prompt_bytes=10))
    assert at_cap.byte_length == 10
    assert at_cap.exceeded is False
    over = prepare_prompt_with_cap(prompt, PromptBudgetConfig(max_prompt_bytes=9))
    assert over.exceeded is True
    assert over.error_status == 413
    assert over.prompt == prompt


def test_prepare_multibyte_boundary_emoji() -> None:
    prompt = "ab😀"  # 2 + 4 байта
    ok = prepare_prompt_with_cap(prompt, PromptBudgetConfig(max_prompt_bytes=6))
    over = prepare_prompt_with_cap(prompt, PromptBudgetConfig(max_prompt_bytes=5))
    assert (ok.byte_length, ok.exceeded) == (6, False)
    assert over.exceeded is True
    assert over.prompt == prompt

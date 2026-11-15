"""W0-B, AD-002/CD-001: контракт классификации 429 до реализации модуля.

QuotaRules.from_config(quota_rules, env=...) загружает правила; classify_429
принимает headers, body (bytes), rules и необязательное now_s.
Результат: is_quota, reason, reset_s, retry_after_s, retry_allowed.
"""

from __future__ import annotations

import json
import sys
from email.utils import formatdate
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOW = 1_800_000_000


@pytest.mark.parametrize("body", [b"PLAN EMPTY", b"Plan   Empty", b"plan empty"])
def test_configured_body_patterns_are_case_insensitive(body: bytes) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config(
        {"body_patterns": [r"plan\s+empty"], "error_codes": []}, env={}
    )
    result = classify_429(headers={}, body=body, rules=rules)
    assert result.is_quota is True
    assert result.reason == "quota"
    assert result.retry_allowed is False


@pytest.mark.parametrize("field", ["code", "type"])
@pytest.mark.parametrize("code", ["GoUsageLimitError", "gousagelimiterror", "GOUSAGELIMITERROR"])
def test_configured_error_codes_match_code_and_type(field: str, code: str) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config(
        {"body_patterns": [r"^never$"], "error_codes": ["GoUsageLimitError"]}, env={}
    )
    body = json.dumps({"error": {field: code, "message": "unavailable"}}).encode()
    result = classify_429(headers={}, body=body, rules=rules)
    assert result.is_quota is True
    assert result.reason == "quota"
    assert result.retry_allowed is False


@pytest.mark.parametrize(
    "body",
    [
        b"ACCOUNT FROZEN",
        b"MONTHLY EXHAUSTED",
        b"plan empty",
        b'{"error":{"code":"CUSTOMLIMIT"}}',
        b'{"error":{"type":"gousagelimiterror"}}',
    ],
)
def test_env_rules_supplement_config_rules(body: bytes) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config(
        {"body_patterns": [r"plan\s+empty"], "error_codes": []},
        env={
            "BRIDGE_QUOTA_BODY_PATTERNS": r"monthly\s+exhausted,account\s+frozen",
            "BRIDGE_QUOTA_ERROR_CODES": "CustomLimit,GoUsageLimitError",
        },
    )
    assert classify_429(headers={}, body=body, rules=rules).is_quota is True


@pytest.mark.parametrize("code", ["GoUsageLimitError", "prefix-CustomLimit", "CustomLimitSuffix"])
def test_no_unconfigured_vendor_code_or_partial_code_match(code: str) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config(
        {"body_patterns": [r"^never$"], "error_codes": ["CustomLimit"]}, env={}
    )
    body = json.dumps({"error": {"code": code}}).encode()
    result = classify_429(headers={}, body=body, rules=rules)
    assert result.is_quota is False
    assert result.reason == "transient"
    assert result.retry_allowed is False


@pytest.mark.parametrize("body", [b"quota", b"USAGE LIMIT", b"insufficient_quota", b"BILLING"])
def test_generic_default_patterns_remain_available(body: bytes) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config({}, env={})
    result = classify_429(headers={}, body=body, rules=rules)
    assert result.is_quota is True
    assert result.reset_s == 3600


@pytest.mark.parametrize(
    ("retry_after", "allowed"),
    [("0", True), ("4.999", True), ("5", True), ("5.001", False), ("10", False)],
)
def test_transient_retry_is_bounded_by_max_wait(retry_after: str, allowed: bool) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config({}, env={"BRIDGE_TRANSIENT_429_MAX_WAIT_S": "5"})
    result = classify_429(headers={"Retry-After": retry_after}, body=b"busy", rules=rules)
    assert result.is_quota is False
    assert result.reason == "transient"
    assert result.retry_after_s == pytest.approx(float(retry_after))
    assert result.retry_allowed is allowed


@pytest.mark.parametrize("body", [b"", b"unrecognized failure", b"not-json {", b"[]"])
def test_unknown_429_is_transient_and_immediately_fallback_eligible(body: bytes) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    result = classify_429(headers={}, body=body, rules=QuotaRules.from_config({}, env={}))
    assert result.is_quota is False
    assert result.reason == "transient"
    assert result.retry_after_s is None
    assert result.retry_allowed is False
    assert result.reset_s == 3600


def test_quota_never_retries_even_with_zero_retry_after() -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config({}, env={})
    result = classify_429(headers={"Retry-After": "0"}, body=b"quota", rules=rules)
    assert result.is_quota is True
    assert result.reason == "quota"
    assert result.retry_allowed is False


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Retry-After": "7200"}, 7200),
        ({"retry-after": "12.5"}, 12.5),
        ({"Retry-After": formatdate(NOW + 7200, usegmt=True)}, 7200),
        ({"X-RateLimit-Reset-Requests": str(NOW + 7200)}, 7200),
        ({"x-ratelimit-reset-tokens": "2h"}, 7200),
        ({"Retry-After": "-10"}, 0),
        ({"Retry-After": formatdate(NOW - 10, usegmt=True)}, 0),
    ],
)
def test_reset_from_headers(headers: dict[str, str], expected: float) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    result = classify_429(
        headers=headers, body=b"quota", rules=QuotaRules.from_config({}, env={}), now_s=NOW
    )
    assert result.reset_s == pytest.approx(expected)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (b"resets in 2d 10h", 208800),
        (b"RESETS IN 2D 10H", 208800),
        (b"resets in 2m 15s", 135),
        (b"resets in 7d", 604800),
    ],
)
def test_human_reset_duration(body: bytes, expected: int) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    result = classify_429(headers={}, body=body, rules=QuotaRules.from_config({}, env={}))
    assert result.reset_s == expected
    if expected > 3600:
        assert result.is_quota is True
        assert result.reason == "quota"
        assert result.retry_allowed is False


def test_reset_uses_maximum_of_all_sources() -> None:
    from core.quota_classifier import QuotaRules, classify_429

    result = classify_429(
        headers={"Retry-After": "5", "x-ratelimit-reset-requests": str(NOW + 14400)},
        body=b"resets in 2d 10h",
        rules=QuotaRules.from_config({}, env={}),
        now_s=NOW,
    )
    assert result.reset_s == 2 * 86400 + 10 * 3600 == 208800
    assert result.is_quota is True
    assert result.retry_allowed is False


@pytest.mark.parametrize(
    ("headers", "body"),
    [
        ({"Retry-After": "999999999"}, b"quota"),
        ({"x-ratelimit-reset-tokens": str(NOW + 999999999)}, b"quota"),
        ({}, b"quota resets in 999999d"),
    ],
)
def test_reset_is_capped(headers: dict[str, str], body: bytes) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    result = classify_429(
        headers=headers, body=body, rules=QuotaRules.from_config({}, env={}), now_s=NOW
    )
    assert result.reset_s == 604800


@pytest.mark.parametrize("headers", [{}, {"Retry-After": "invalid"}])
def test_absent_or_unusable_reset_uses_configurable_default(headers: dict[str, str]) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config({}, env={"BRIDGE_QUOTA_COOLDOWN_DEFAULT_S": "123"})
    assert classify_429(headers=headers, body=b"quota", rules=rules).reset_s == 123


def test_cooldown_max_is_configurable_and_also_caps_default() -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config(
        {}, env={"BRIDGE_QUOTA_COOLDOWN_MAX_S": "120", "BRIDGE_QUOTA_COOLDOWN_DEFAULT_S": "500"}
    )
    for headers in ({}, {"Retry-After": "999"}):
        assert classify_429(headers=headers, body=b"quota", rules=rules).reset_s == 120


@pytest.mark.parametrize(("reset", "quota"), [("100", False), ("100.001", True)])
def test_reset_threshold_is_configurable_and_strict(reset: str, quota: bool) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config({}, env={"BRIDGE_QUOTA_RESET_THRESHOLD_S": "100"})
    result = classify_429(headers={"Retry-After": reset}, body=b"busy", rules=rules)
    assert result.is_quota is quota
    assert result.reason == ("quota" if quota else "transient")


@pytest.mark.parametrize("source", ["config", "env"])
def test_reset_body_patterns_are_configurable(source: str) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    pattern = r"available after\s+(?P<duration>(?:\d+\s*[dhms]\s*)+)"
    config = {"reset_body_patterns": [pattern]} if source == "config" else {}
    env = {"BRIDGE_QUOTA_RESET_BODY_PATTERNS": pattern} if source == "env" else {}
    rules = QuotaRules.from_config(config, env=env)
    result = classify_429(headers={}, body=b"AVAILABLE AFTER 2d 10h", rules=rules)
    assert result.reset_s == 208800
    assert result.is_quota is True


def test_transient_wait_limit_is_configurable() -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config({}, env={"BRIDGE_TRANSIENT_429_MAX_WAIT_S": "2"})
    result = classify_429(headers={"Retry-After": "2.001"}, body=b"busy", rules=rules)
    assert result.is_quota is False
    assert result.retry_allowed is False


@pytest.mark.parametrize("name", ["x-ratelimit-reset-requests", "X-RateLimit-Reset-Tokens"])
def test_small_numeric_reset_header_is_relative_seconds(name: str) -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config({}, env={})
    result = classify_429(headers={name: "20"}, body=b"busy", rules=rules, now_s=NOW)
    assert result.reset_s == 20
    assert result.is_quota is False


def test_epoch_reset_header_above_threshold_is_absolute() -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config({}, env={})
    result = classify_429(
        headers={"x-ratelimit-reset-requests": str(NOW + 120)}, body=b"busy", rules=rules, now_s=NOW
    )
    assert result.reset_s == 120


def test_epoch_threshold_is_configurable() -> None:
    from core.quota_classifier import QuotaRules, classify_429

    rules = QuotaRules.from_config({}, env={"BRIDGE_QUOTA_EPOCH_THRESHOLD": "1000"})
    relative = classify_429(headers={"x-ratelimit-reset-requests": "999"}, body=b"b", rules=rules, now_s=2000)
    absolute = classify_429(headers={"x-ratelimit-reset-requests": "2500"}, body=b"b", rules=rules, now_s=2000)
    assert (relative.reset_s, absolute.reset_s) == (999, 500)

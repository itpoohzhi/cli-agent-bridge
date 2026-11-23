"""W0 red-repro: контракт `core/timeout_ladder` (AD-001, L-LIVE/v1).

Скользящая лестница таймаутов: полезные чанки сдвигают idle-дедлайн,
keepalive/empty — нет; safety_cap — абсолютный предохранитель.
Только FakeClock: 0 реальных сокетов, внешних процессов и ожиданий (T-ISO).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import pytest

from core.timeout_ladder import (
    FLAG_TIMEOUT_LADDER,
    ActivityKind,
    SlidingActivityPolicy,
    TimeoutLadderConfig,
    load_timeout_ladder_config,
    validate_ladder_monotonicity,
)


class FakeClock:
    """Детерминированные часы: время движется только явно."""

    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def set(self, now: float) -> None:
        self.now = now


def kind(name: str) -> Any:
    """ActivityKind как Enum, StrEnum или Literal[str] — любой вариант."""
    try:
        return ActivityKind(name)  # type: ignore[operator]
    except Exception:
        member = getattr(ActivityKind, name.upper(), None)
        return member if member is not None else name


def eff(config: TimeoutLadderConfig, name: str) -> float:
    """effective_* допустимы и свойством, и методом."""
    value = getattr(config, name)
    return float(value() if callable(value) else value)


def call(obj: Any, name: str, *args: Any) -> Any:
    """Методы политики допустимы и свойством, и методом (без args)."""
    value = getattr(obj, name)
    return value(*args) if callable(value) else value


def make_policy(
    config: TimeoutLadderConfig, clock: Callable[[], float]
) -> SlidingActivityPolicy:
    try:
        return SlidingActivityPolicy(config, clock)
    except TypeError:
        return SlidingActivityPolicy(config=config, clock=clock)


def enabled_config(env: Mapping[str, str] | None = None) -> TimeoutLadderConfig:
    base: dict[str, str] = {FLAG_TIMEOUT_LADDER: "true"}
    if env:
        base.update(env)
    return load_timeout_ladder_config(base)


def test_default_flag_off_preserves_legacy_values() -> None:
    assert FLAG_TIMEOUT_LADDER == "BRIDGE_TIMEOUT_LADDER_ENABLED"
    config = load_timeout_ladder_config({})
    assert config.enabled is False
    assert eff(config, "effective_first_event_s") == 300.0
    assert eff(config, "effective_idle_s") == 120.0
    assert eff(config, "effective_read_chunk_s") == 330.0
    default = TimeoutLadderConfig()
    assert default.enabled is False
    assert eff(default, "effective_first_event_s") == config.legacy_first_event_s
    assert eff(default, "effective_idle_s") == config.legacy_idle_s
    assert eff(default, "effective_read_chunk_s") == config.legacy_read_chunk_s


def test_flag_on_defaults_no_180s_and_env_override() -> None:
    config = enabled_config()
    assert config.enabled is True
    assert config.connect_timeout_s == 10.0
    assert eff(config, "effective_first_event_s") == 600.0
    assert eff(config, "effective_idle_s") == 600.0
    assert eff(config, "effective_read_chunk_s") == 600.0
    assert config.safety_cap_s == 3600.0
    values = (
        config.connect_timeout_s,
        eff(config, "effective_first_event_s"),
        eff(config, "effective_idle_s"),
        eff(config, "effective_read_chunk_s"),
    )
    assert 180.0 not in values
    custom = enabled_config(
        {
            "BRIDGE_TIMEOUT_CONNECT_S": "15",
            "BRIDGE_TIMEOUT_FIRST_EVENT_S": "700",
            "BRIDGE_TIMEOUT_IDLE_S": "800",
            "BRIDGE_TIMEOUT_READ_CHUNK_S": "900",
            "BRIDGE_TIMEOUT_SAFETY_CAP_S": "4000",
        }
    )
    assert custom.connect_timeout_s == 15.0
    assert eff(custom, "effective_first_event_s") == 700.0
    assert eff(custom, "effective_idle_s") == 800.0
    assert eff(custom, "effective_read_chunk_s") == 900.0
    assert custom.safety_cap_s == 4000.0


def test_long_reasoning_progress_survives_past_338s_and_600s() -> None:
    clock = FakeClock(0.0)
    policy = make_policy(enabled_config(), clock)
    deadline = float(call(policy, "start"))
    assert deadline == pytest.approx(600.0)
    for at in (100.0, 250.0, 400.0, 550.0, 700.0, 900.0):
        clock.set(at)
        deadline = float(call(policy, "record", kind("reasoning")))
        assert deadline > at
        assert call(policy, "is_expired") is False
        assert call(policy, "expiry_reason") is None
        assert float(call(policy, "remaining")) > 0.0
    # Последний полезный чанк на 900: дедлайн 1500, переживает 338/600.
    assert deadline == pytest.approx(1500.0)
    clock.set(1499.0)
    assert call(policy, "is_expired") is False


def test_keepalive_does_not_extend_idle_deadline() -> None:
    clock = FakeClock(0.0)
    policy = make_policy(enabled_config(), clock)
    initial = float(call(policy, "start"))
    for at in (100.0, 300.0, 500.0, 599.0):
        clock.set(at)
        assert float(call(policy, "record", kind("keepalive"))) == initial
        assert float(call(policy, "record", kind("empty"))) == initial
        assert call(policy, "is_expired") is False
    clock.set(601.0)
    assert call(policy, "is_expired") is True
    assert call(policy, "expiry_reason") in (
        "idle_timeout",
        "first_event_timeout",
    )
    assert float(call(policy, "remaining")) == 0.0


def test_safety_cap_stops_infinite_stream() -> None:
    clock = FakeClock(0.0)
    policy = make_policy(enabled_config(), clock)
    call(policy, "start")
    at = 200.0
    while at <= 3400.0:
        clock.set(at)
        call(policy, "record", kind("content"))
        assert call(policy, "is_expired") is False
        at += 200.0
    clock.set(3601.0)
    call(policy, "record", kind("content"))
    assert call(policy, "is_expired") is True
    assert call(policy, "expiry_reason") == "safety_cap"
    assert float(call(policy, "remaining")) == 0.0


def test_monotonicity_fail_closed_when_upper_below_lower() -> None:
    lower = TimeoutLadderConfig(enabled=True)
    upper = TimeoutLadderConfig(
        enabled=True,
        first_event_timeout_s=900.0,
        idle_timeout_s=900.0,
        read_chunk_timeout_s=900.0,
        safety_cap_s=4000.0,
    )
    validate_ladder_monotonicity(upper, lower)
    validate_ladder_monotonicity(upper, lower, margin_s=100.0)
    below_idle = TimeoutLadderConfig(enabled=True, idle_timeout_s=100.0)
    with pytest.raises(ValueError):
        validate_ladder_monotonicity(below_idle, lower)
    below_cap = TimeoutLadderConfig(
        enabled=True, idle_timeout_s=900.0, safety_cap_s=1000.0
    )
    with pytest.raises(ValueError):
        validate_ladder_monotonicity(below_cap, lower)
    with pytest.raises(ValueError):
        validate_ladder_monotonicity(lower, lower, margin_s=1.0)
    below_connect = TimeoutLadderConfig(enabled=True, connect_timeout_s=5.0)
    with pytest.raises(ValueError):
        validate_ladder_monotonicity(below_connect, lower)


def test_open_sliding_deadline_wires_sliding_activity_policy() -> None:
    from types import SimpleNamespace

    from core.passthrough_sliding_window import open_sliding_deadline

    ladder = load_timeout_ladder_config(
        {
            FLAG_TIMEOUT_LADDER: "true",
            "BRIDGE_TIMEOUT_FIRST_EVENT_S": "600",
            "BRIDGE_TIMEOUT_IDLE_S": "600",
            "BRIDGE_TIMEOUT_SAFETY_CAP_S": "3600",
        }
    )
    limits = SimpleNamespace(
        total_timeout_s=300.0,
        idle_timeout_s=600.0,
        stream_safety_cap_s=3600.0,
        timeout_ladder=ladder,
    )
    cell = open_sliding_deadline(
        deadline=300.0,
        limits=limits,
        is_internal=False,
        request={"stream": True},
        flag_enabled_fn=lambda: True,
        now_s=100.0,
    )
    assert cell.deadline_s == 700.0
    cell.advance(now=500.0, is_useful_chunk=False)
    assert cell.deadline_s == 700.0
    cell.advance(now=500.0, is_useful_chunk=True)
    assert cell.deadline_s == 1100.0
    assert cell.expiry_reason(1050.0) is None
    assert cell.expiry_reason(1100.0) == "idle_timeout"


def test_invalid_negative_or_zero_config_raises_value_error() -> None:
    bad_kwargs: list[dict[str, float]] = [
        {"connect_timeout_s": 0.0},
        {"idle_timeout_s": -1.0},
        {"safety_cap_s": 100.0, "idle_timeout_s": 600.0},
    ]
    for kwargs in bad_kwargs:
        with pytest.raises(ValueError):
            config = TimeoutLadderConfig(enabled=True, **kwargs)
            config.validate()
    with pytest.raises(ValueError):
        load_timeout_ladder_config(
            {FLAG_TIMEOUT_LADDER: "true", "BRIDGE_TIMEOUT_IDLE_S": "-5"}
        )
    with pytest.raises(ValueError):
        load_timeout_ladder_config(
            {FLAG_TIMEOUT_LADDER: "true", "BRIDGE_TIMEOUT_IDLE_S": "abc"}
        )

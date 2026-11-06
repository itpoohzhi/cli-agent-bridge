"""Существующие оракулы passthrough, выделенные для сохранения границ legacy."""

from __future__ import annotations

from adapters.passthrough_adapter import PassthroughLimits
from core.cli_runtime_config import NonstreamConfig
from core.runtime_env import ConfigError
import unittest.mock


class TestNonstreamLimitsFromEnv(unittest.TestCase):
    def test_defaults_build_default_nonstream_config(self) -> None:
        limits = PassthroughLimits.from_env({})
        self.assertEqual(limits.nonstream, NonstreamConfig())
        self.assertEqual(limits.poll_interval_s, 0.1)

    def test_nonstream_field_is_built_from_canonical_env(self) -> None:
        limits = PassthroughLimits.from_env(
            {
                "BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S": "7",
                "BRIDGE_NONSTREAM_IDLE_TIMEOUT_S": "11",
                "BRIDGE_NONSTREAM_SOFT_LIVENESS_BUDGET_S": "5",
                "BRIDGE_NONSTREAM_SOFT_LIVENESS_MIN_CPU_DELTA_S": "0.2",
                "BRIDGE_NONSTREAM_SAFETY_CAP_S": "13",
                "BRIDGE_NONSTREAM_POLL_INTERVAL_S": "0.5",
            }
        )
        self.assertEqual(
            limits.nonstream,
            NonstreamConfig(
                first_progress_timeout_s=7.0,
                idle_timeout_s=11.0,
                soft_budget_s=5.0,
                min_cpu_delta_s=0.2,
                safety_cap_s=13.0,
                poll_interval_s=0.5,
            ),
        )

    def test_poll_interval_canonical_wins_over_legacy_alias(self) -> None:
        both = PassthroughLimits.from_env(
            {
                "BRIDGE_NONSTREAM_POLL_INTERVAL_S": "0.5",
                "BRIDGE_PASSTHROUGH_POLL_INTERVAL_S": "0.2",
            }
        )
        self.assertEqual(
            (both.poll_interval_s, both.nonstream.poll_interval_s), (0.5, 0.5)
        )
        legacy = PassthroughLimits.from_env(
            {"BRIDGE_PASSTHROUGH_POLL_INTERVAL_S": "0.2"}
        )
        self.assertEqual(
            (legacy.poll_interval_s, legacy.nonstream.poll_interval_s), (0.2, 0.2)
        )
        empty = PassthroughLimits.from_env(
            {
                "BRIDGE_NONSTREAM_POLL_INTERVAL_S": "  ",
                "BRIDGE_PASSTHROUGH_POLL_INTERVAL_S": "0.3",
            }
        )
        self.assertEqual(empty.poll_interval_s, 0.3)

    def test_idle_timeout_legacy_alias_and_priority(self) -> None:
        legacy = PassthroughLimits.from_env({"BRIDGE_IDLE_TIMEOUT_S": "42"})
        self.assertEqual(legacy.nonstream.idle_timeout_s, 42.0)
        both = PassthroughLimits.from_env(
            {"BRIDGE_NONSTREAM_IDLE_TIMEOUT_S": "17", "BRIDGE_IDLE_TIMEOUT_S": "42"}
        )
        self.assertEqual(both.nonstream.idle_timeout_s, 17.0)

    def test_invalid_nonstream_value_raises_config_error_without_value(self) -> None:
        secret = "sk-secret-123"
        cases = [
            ("BRIDGE_NONSTREAM_IDLE_TIMEOUT_S", secret),
            ("BRIDGE_NONSTREAM_IDLE_TIMEOUT_S", "nan"),
            ("BRIDGE_NONSTREAM_IDLE_TIMEOUT_S", "inf"),
            ("BRIDGE_NONSTREAM_IDLE_TIMEOUT_S", "0"),
            ("BRIDGE_NONSTREAM_IDLE_TIMEOUT_S", "99999"),
            ("BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S", "0.5"),
            ("BRIDGE_NONSTREAM_SAFETY_CAP_S", "-" + secret),
            ("BRIDGE_NONSTREAM_POLL_INTERVAL_S", "0.001"),
            ("BRIDGE_NONSTREAM_POLL_INTERVAL_S", "11"),
            ("BRIDGE_NONSTREAM_SOFT_LIVENESS_MIN_CPU_DELTA_S", "0"),
            ("BRIDGE_NONSTREAM_SOFT_LIVENESS_BUDGET_S", "-1"),
        ]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                with self.assertRaises(ConfigError) as ctx:
                    PassthroughLimits.from_env({name: value})
                message = str(ctx.exception)
                self.assertIn(name, message)
                self.assertNotIn(value, message)

    def test_invalid_legacy_alias_is_also_fail_fast(self) -> None:
        with self.assertRaises(ConfigError) as ctx:
            PassthroughLimits.from_env(
                {"BRIDGE_PASSTHROUGH_POLL_INTERVAL_S": "sk-secret-123"}
            )
        self.assertNotIn("sk-secret-123", str(ctx.exception))

    def test_soft_budget_zero_is_valid(self) -> None:
        limits = PassthroughLimits.from_env(
            {"BRIDGE_NONSTREAM_SOFT_LIVENESS_BUDGET_S": "0"}
        )
        self.assertEqual(limits.nonstream.soft_budget_s, 0.0)

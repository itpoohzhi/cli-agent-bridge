"""L1-тесты AD-005 (часть 1): сегмент net= в compute_env_digest (REQ-002c)."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGY_BRIDGE_DIR = REPO_ROOT / "bridges" / "agy-bridge"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(AGY_BRIDGE_DIR) not in sys.path:
    sys.path.append(str(AGY_BRIDGE_DIR))

from agy_runtime.persistent_worker_config import compute_env_digest  # noqa: E402


def _baseline_digest(
    cli_mode: str, zero_canon: bool, clean_home: str, settings_arg: str = ""
) -> str:
    """Независимая эталонная формула digest до AD-005 (без launch_env)."""
    raw = f"mode={cli_mode}|zc={int(zero_canon)}|home={clean_home}|cfg={settings_arg}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


class TestEnvDigestCloudMode(unittest.TestCase):
    def test_no_launch_env_matches_baseline_formula(self) -> None:
        """3/4-аргументные вызовы и launch_env=None побитово равны baseline."""
        cases = [
            ("plan", True, "/tmp/home-a", ""),
            ("plan", False, "/tmp/home-b", "cfg.json"),
            ("build", True, "", "settings=x"),
        ]
        for cli_mode, zero_canon, clean_home, settings_arg in cases:
            expected = _baseline_digest(cli_mode, zero_canon, clean_home, settings_arg)
            with self.subTest(cli_mode=cli_mode, settings_arg=settings_arg):
                self.assertEqual(
                    compute_env_digest(cli_mode, zero_canon, clean_home, settings_arg),
                    expected,
                )
                self.assertEqual(
                    compute_env_digest(
                        cli_mode, zero_canon, clean_home, settings_arg, launch_env=None
                    ),
                    expected,
                )
        self.assertEqual(
            compute_env_digest("plan", True, "/tmp/home-a"),
            _baseline_digest("plan", True, "/tmp/home-a"),
        )

    def test_direct_and_georouter_digests_differ(self) -> None:
        """AGY_DIRECT=1 (direct) и AGY_DIRECT=0 (georouter) дают разные digest."""
        direct = compute_env_digest(
            "plan", True, "/tmp/h", launch_env={"AGY_DIRECT": "1"}
        )
        georouter = compute_env_digest(
            "plan", True, "/tmp/h", launch_env={"AGY_DIRECT": "0"}
        )
        self.assertNotEqual(direct, georouter)
        baseline = _baseline_digest("plan", True, "/tmp/h")
        self.assertNotEqual(direct, baseline)
        self.assertNotEqual(georouter, baseline)

    def test_equivalent_georouter_values_share_digest(self) -> None:
        """Пустое/0/пробелы/отсутствие ключа — один и тот же georouter-digest."""
        digests = {
            compute_env_digest("plan", True, "/tmp/h", launch_env=env)
            for env in (
                {},
                {"AGY_DIRECT": ""},
                {"AGY_DIRECT": "0"},
                {"AGY_DIRECT": "  "},
            )
        }
        self.assertEqual(len(digests), 1)

    def test_direct_value_is_stripped(self) -> None:
        """AGY_DIRECT=' 1 ' эквивалентен '1' (classify_cloud_mode strip)."""
        padded = compute_env_digest(
            "plan", True, "/tmp/h", launch_env={"AGY_DIRECT": " 1 "}
        )
        exact = compute_env_digest(
            "plan", True, "/tmp/h", launch_env={"AGY_DIRECT": "1"}
        )
        self.assertEqual(padded, exact)

    def test_net_segment_uses_classified_mode(self) -> None:
        """Сегмент raw строго '|net=<classify_cloud_mode(env)>' поверх baseline."""
        for env, mode in (
            ({"AGY_DIRECT": "1"}, "direct"),
            ({"AGY_DIRECT": "0"}, "georouter"),
        ):
            raw = f"mode=plan|zc=1|home=/tmp/h|cfg=|net={mode}"
            expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
            with self.subTest(mode=mode):
                self.assertEqual(
                    compute_env_digest("plan", True, "/tmp/h", launch_env=env), expected
                )


if __name__ == "__main__":
    unittest.main()

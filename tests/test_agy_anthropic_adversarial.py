import ast
import unittest
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from core.agy_anthropic_gate import parse_agy_models_output, resolve_exact_5_5_upstream
from core.agy_anthropic_probe import (
    AgyAnthropicProbe,
    ProbeConfig,
    ProbeSnapshot,
)

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "core").is_dir():
    ROOT = ROOT / "cli-agent-bridge"

SPOOFED_MODEL_OUTPUTS = (
    "# claude-sonnet-5-5",
    "  # claude-sonnet-5-5\r\n",
    "\u0441laude-sonnet-5-5",
    "claude-sonnet-5-5-beta",
    "claude-sonnet-4-6-thinking",
    "claude-haiku-5-5",
    "claude-opus-4-6-thinking",
)
SCANNED_SOURCES = (
    "core/agy_anthropic_probe.py",
    "bridges/agy-bridge/anthropic_runtime.py",
)
FORBIDDEN_SECRET_REFERENCES = (".credentials.yaml", ".env", "BRIDGE_KEY")


class _SwitchingRunner:
    def __init__(self) -> None:
        self.output = "claude-sonnet-4-6-thinking\n"

    def __call__(self, _timeout_s: float, _max_bytes: int) -> tuple[int, str]:
        return 0, self.output


def _eight_calls(
    operation: Callable[[], ProbeSnapshot],
) -> tuple[ProbeSnapshot, ...]:
    barrier = Barrier(8)

    def call_operation(_: int) -> ProbeSnapshot:
        barrier.wait(timeout=10)
        return operation()

    with ThreadPoolExecutor(max_workers=8) as pool:
        return tuple(pool.map(call_operation, range(8)))


def _uses_shell_true(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if any(
            kw.arg == "shell"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in node.keywords
        ):
            return True
    return False


def _string_literals(tree: ast.AST) -> tuple[str, ...]:
    return tuple(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )


class AnthropicAdversarialTests(unittest.TestCase):
    def test_exact_5_5_positive_control(self) -> None:
        models = parse_agy_models_output("claude-sonnet-5-5\n")
        decision = resolve_exact_5_5_upstream("claude-sonnet-5-5", models)
        self.assertTrue(decision.available)
        self.assertEqual(decision.upstream_model, "claude-sonnet-5-5")

    def test_model_confusion_and_spoofing_are_rejected(self) -> None:
        for output in SPOOFED_MODEL_OUTPUTS:
            with self.subTest(output=ascii(output)):
                models = parse_agy_models_output(output)
                decision = resolve_exact_5_5_upstream("claude-sonnet-5-5", models)
                self.assertFalse(decision.available)
                self.assertIsNone(decision.upstream_model)

    def test_output_over_one_mib_fails_closed(self) -> None:
        probe = AgyAnthropicProbe(runner=lambda _t, _b: (0, "x" * 1_048_577))
        snap = probe.probe("claude-sonnet-5-5")
        self.assertFalse(snap.available)
        self.assertEqual(snap.reason, "output_too_large")

    def test_probe_and_runtime_do_not_touch_secrets_or_shell(self) -> None:
        for relative_path in SCANNED_SOURCES:
            with self.subTest(path=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                tree = ast.parse(source, filename=relative_path)
                literals = _string_literals(tree)
                for reference in FORBIDDEN_SECRET_REFERENCES:
                    self.assertFalse(any(reference in lit for lit in literals))
                self.assertFalse(_uses_shell_true(tree))

    def test_probe_races_have_consistent_snapshots(self) -> None:
        runner = _SwitchingRunner()
        now = [100.0]
        probe = AgyAnthropicProbe(
            runner=runner,
            clock=lambda: now[0],
            config=ProbeConfig(force_refresh_cooldown_s=5.0),
        )
        cold = _eight_calls(lambda: probe.probe("claude-sonnet-5-5"))
        now[0] = 200.0
        runner.output = "claude-sonnet-5-5\n"
        refreshed = _eight_calls(
            lambda: probe.probe("claude-sonnet-5-5", force_refresh=True)
        )
        final = probe.probe("claude-sonnet-5-5")

        for snap in (*cold, *refreshed, final):
            self.assertIsInstance(snap, ProbeSnapshot)
        self.assertEqual(cold, (cold[0],) * 8)
        self.assertFalse(cold[0].available)
        self.assertEqual(refreshed, (final,) * 8)
        self.assertTrue(final.available)
        self.assertNotEqual(cold[0], final)


if __name__ == "__main__":
    unittest.main()

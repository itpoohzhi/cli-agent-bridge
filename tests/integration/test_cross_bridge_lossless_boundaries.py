"""Cross-bridge boundary suite verifying REQ-001..REQ-005 across all bridges without silent loss."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.claude_prompt import PromptBudgetConfig, prepare_prompt_with_cap  # noqa: E402
from core.lossless_contracts import DEFAULT_SAFE_FRAME_BYTES, LosslessLimits  # noqa: E402
from core.lossless_gate import GateAction, evaluate_delivery_gate  # noqa: E402


def test_claude_p_bridge_enforces_413_without_truncation() -> None:
    payload = "а" * 20_000
    # max_prompt_bytes=0 disables cap and never truncates
    ok = prepare_prompt_with_cap(payload, PromptBudgetConfig(max_prompt_bytes=0))
    assert ok.exceeded is False
    assert ok.prompt == payload
    # Positive cap fails closed with HTTP 413 prompt_too_large, never truncates
    ov = prepare_prompt_with_cap(payload, PromptBudgetConfig(max_prompt_bytes=1000))
    assert ov.exceeded is True
    assert ov.error_status == 413
    assert ov.prompt == payload


def test_hub_dynamic_pruner_defaults_false_and_frozen_bridges_unmodified() -> None:
    cr_text = (REPO_ROOT / "core" / "context_resilience.py").read_text(encoding="utf-8")
    assert "DYNAMIC_PRUNER_ENABLED" in cr_text
    # opencode-zen has no input prompt truncation helper
    zen_text = (REPO_ROOT / "bridges" / "opencode-zen-bridge" / "server.py").read_text(encoding="utf-8")
    assert "_middle_prune_text" not in zen_text
    assert "_prune_messages" not in zen_text


def test_all_new_lossless_modules_stay_under_300_loc_and_respect_boundaries() -> None:
    new_modules = (
        "core/lossless_contracts.py",
        "core/lossless_chunker.py",
        "core/lossless_fsm.py",
        "core/lossless_gate.py",
        "bridges/agy-bridge/agy_runtime/process_admission_guard.py",
        "bridges/agy-bridge/agy_runtime/chunk_delivery_adapter.py",
        "bridges/agy-bridge/agy_runtime/lossless_prompt_facade.py",
        "bridges/muse-bridge/muse_runtime/lossless_policy.py",
        "scripts/qa_lossless_cases.py",
    )
    for rel in new_modules:
        path = REPO_ROOT / rel
        assert path.is_file(), f"Missing module {rel}"
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 300, f"{rel} has {len(lines)} LOC (> 300)"
        tree = ast.parse("\n".join(lines))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, "end_lineno", node.lineno) or node.lineno
                fn_loc = end_line - node.lineno + 1
                assert fn_loc <= 65, f"{rel}:{node.name} too long ({fn_loc} LOC)"


def test_cross_bridge_lossless_gate_never_allows_silent_truncation_when_enabled() -> None:
    limits = LosslessLimits(lossless_enabled=True, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES, max_chunks=16)
    for size in (10, 50_000, 260_000, 350_000, 2_000_000):
        decision = evaluate_delivery_gate("x" * size, limits)
        assert decision.allow_silent_truncation is False
        assert decision.action in (
            GateAction.DELIVER_SINGLE,
            GateAction.DELIVER_CHUNKED,
            GateAction.REJECT,
        )
        if decision.action is GateAction.REJECT:
            assert decision.http_status == 413
            assert decision.receipt is not None

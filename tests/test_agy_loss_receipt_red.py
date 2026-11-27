"""Red-repro I3/F1/F2: честная квитанция потерь и атомарность prompt compaction."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import os
import textwrap
from contextlib import nullcontext
from pathlib import Path
from typing import Any, cast

import pytest

_ROOT = Path(__file__).resolve().parents[1]
try:
    from resilience_wiring_support import load_server
except ImportError:
    from tests.resilience_wiring_support import load_server

from agy_runtime.history_compaction_adapter import (  # noqa: E402
    CompactionAdapterRequest,
    render_or_compact_blocks,
)
from agy_runtime.history_compaction_domain import (  # noqa: E402
    DEFAULT_MIDDLE_PRUNED_MARKER,
    json_text_bytes,
    middle_prune_text,
)
from agy_runtime.history_overflow_policy import (  # noqa: E402
    OverflowSpec,
    shrink_overflow_parts,
)

srv = cast(Any, load_server())
_RED_REPRO = pytest.mark.xfail(
    os.environ.get("LOSS_CONTRACT_RED") == "1",
    reason="известный дефект loss contract до реализации W1/W2",
    strict=True,
    raises=AssertionError,
)
_ACTIVE_MIDDLES = ("TOOL_A_UNIQUE_MIDDLE", "TOOL_B_UNIQUE_MIDDLE")


def _handler_method_source(name: str) -> str:
    """Исходник Handler.<name> из server.py (do_POST обёрнут subbridge_lifecycle без wraps)."""
    path = _ROOT / "bridges" / "agy-bridge" / "server.py"
    text = path.read_text(encoding="utf-8")
    for cls in ast.parse(text).body:
        if isinstance(cls, ast.ClassDef) and cls.name == "Handler":
            for node in cls.body:
                if isinstance(node, ast.FunctionDef) and node.name == name:
                    return ast.get_source_segment(text, node) or ""
    raise AssertionError(f"Handler.{name} не найден в server.py")


def _request_scope() -> Any:
    name = "agy_runtime.loss_receipt_context"
    if importlib.util.find_spec(name) is None:
        return nullcontext()
    return importlib.import_module(name).begin_request_scope()


def _incident_messages() -> list[dict[str, object]]:
    messages: list[dict[str, object]] = [
        {"role": "system", "content": "OpenAI function calling protocol."},
        {"role": "user", "content": "1"},
    ]
    messages += [
        {"role": "assistant", "content": f"historical-{i:03d}-" + "x" * 5000}
        for i in range(840)
    ]
    calls = [
        {
            "id": f"call_{letter}",
            "type": "function",
            "function": {"name": f"inspect_{letter}", "arguments": "{}"},
        }
        for letter in ("a", "b")
    ]
    messages.append({"role": "assistant", "content": "run", "tool_calls": calls})
    for letter in ("a", "b"):
        upper = letter.upper()
        body = (
            f"TOOL_{upper}_BEGIN "
            + "y" * 12000
            + f" TOOL_{upper}_UNIQUE_MIDDLE "
            + "z" * 12000
            + f" TOOL_{upper}_END"
        )
        messages.append(
            {"role": "tool", "tool_call_id": f"call_{letter}", "content": body}
        )
    return messages


def _rendered_blocks(messages: list[dict[str, object]]) -> list[tuple[int, str, str]]:
    counter = [0]
    blocks = []
    for index, message in enumerate(messages):
        rendered = srv._render_message(message, counter)
        if rendered:
            blocks.append((index, str(message.get("role") or "user"), rendered))
    assert len(blocks) == 845
    return blocks


@_RED_REPRO
def test_usage_payload_and_build_payload_expose_loss_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Общий usage-exit обязан обслуживать и JSON build_payload, и SSE."""
    flags = {"history_compaction_enabled", "loss_receipt_enabled"}
    monkeypatch.setattr(srv, "AGY_BRIDGE_ENABLE_HEAD_PRUNING", True)
    monkeypatch.setattr(srv, "_prompt_budget", lambda _reserve=0: 256)
    monkeypatch.setattr(
        srv, "_new_flag", lambda name, default=False: name in flags or default
    )
    with _request_scope():
        prompt = srv._messages_to_prompt([{"role": "user", "content": "x" * 2000}])
        usage = srv.Handler._usage_payload(
            {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
        )
    assert srv.MIDDLE_PRUNED_MARKER in prompt or srv.HISTORY_PRUNED_MARKER in prompt
    source = _handler_method_source("_serve_json_body")
    assert "def build_payload(" in source and "self._usage_payload(" in source
    receipt = usage.get("x_bridge_loss")
    assert isinstance(receipt, dict), "build_payload/_usage_payload скрывают потери"
    assert receipt.get("schema_version") == "loss-receipt/v1"
    assert receipt.get("truncated") is True


@_RED_REPRO
def test_markers_do_not_mislabel_prompt_cap_as_model_context() -> None:
    for marker in (srv.HISTORY_PRUNED_MARKER, srv.MIDDLE_PRUNED_MARKER):
        assert "лимита контекста" not in marker


@_RED_REPRO
def test_input_guard_does_not_silently_legacy_drop_active_tools() -> None:
    blocks = _rendered_blocks(_incident_messages())
    logs: list[str] = []
    request = CompactionAdapterRequest(
        blocks=blocks,
        tail_block="",
        limit_bytes=34473,
        enabled=True,
        legacy_prune=srv._prune_prompt_blocks,
        log_fn=logs.append,
        config_path=Path("/nonexistent/loss-contract-red.json"),
        size_fn=srv._ndjson_bytes,
    )
    prompt = render_or_compact_blocks(request)
    lost = [marker for marker in _ACTIVE_MIDDLES if marker not in prompt]
    legacy_guard = any(
        "mode=fallback" in line and "reason=input_guard" in line for line in logs
    )
    assert not (legacy_guard and lost == list(_ACTIVE_MIDDLES)), (
        "input_guard ушёл в legacy и потерял оба UNIQUE_MIDDLE"
    )


@_RED_REPRO
def test_overflow_never_evicts_only_one_part_of_tool_group() -> None:
    items = [
        (
            "assistant",
            "[tool call atomic_group] CALL_HEAD " + "a" * 800 + " CALL_TAIL",
        ),
        (
            "tool",
            "[tool result atomic_group] RESULT_HEAD " + "r" * 4000 + " RESULT_TAIL",
        ),
        ("user", "FINAL_QUESTION"),
    ]
    spec = OverflowSpec(
        300,
        "\n\n",
        DEFAULT_MIDDLE_PRUNED_MARKER,
        json_text_bytes,
        middle_prune_text,
    )
    prompt = shrink_overflow_parts(items, spec)
    call_present = "[tool call atomic_group]" in prompt
    result_present = "[tool result atomic_group]" in prompt
    assert call_present == result_present, "overflow разорвал assistant/tool группу"


@_RED_REPRO
def test_explicit_resume_cannot_bypass_tools_fingerprint_proof() -> None:
    tree = ast.parse(textwrap.dedent(_handler_method_source("do_POST")))
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "compact_tools"
            for target in node.targets
        )
    ]
    assert assignments
    value = assignments[0].value
    explicit_bypass = isinstance(
        value, ast.IfExp
    ) and "explicit_state.handled" in ast.dump(value)
    assert not explicit_bypass, (
        "explicit path включает compact tools без fingerprint proof"
    )

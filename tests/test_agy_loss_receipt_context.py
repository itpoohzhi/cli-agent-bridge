"""W2-E: request-scoped loss receipt и общий usage-exit (VER-015)."""

from __future__ import annotations

import inspect
import logging
import sys
import threading
from pathlib import Path
from typing import Any, Final, cast

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
AGY_BRIDGE: Final = ROOT / "bridges" / "agy-bridge"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(AGY_BRIDGE) not in sys.path:
    sys.path.append(str(AGY_BRIDGE))

from agy_runtime.input_guard_policy import ClientCompactionRequired  # noqa: E402  # pyright: ignore[reportMissingImports]
from agy_runtime.loss_receipt import LossReceipt  # noqa: E402  # pyright: ignore[reportMissingImports]
from agy_runtime.loss_receipt_context import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    begin_request_scope,
    record_build,
    record_lossless,
    send_client_compaction_required,
    usage_chunk_due,
    usage_payload,
)


@pytest.fixture(autouse=True)
def _enable_receipts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGY_BRIDGE_LOSS_RECEIPT_ENABLED", "1")


def _loss(original: int = 4, dropped: int = 1) -> LossReceipt:
    return LossReceipt(
        truncated=True,
        original_messages=original,
        effective_messages=original - dropped,
        original_prompt_bytes=100,
        effective_prompt_bytes=80,
        dropped_messages=dropped,
        fallback_reason="input_guard",
        configured_prompt_cap_bytes=80,
    )


def _lossless() -> LossReceipt:
    return LossReceipt(
        original_messages=2,
        effective_messages=2,
        original_prompt_bytes=20,
        effective_prompt_bytes=20,
        configured_prompt_cap_bytes=80,
    )


def test_request_scopes_isolate_two_threads_and_merge_conservatively() -> None:
    seen: dict[str, dict[str, Any]] = {}

    def worker(name: str, count: int) -> None:
        with begin_request_scope():
            record_build(_loss(count))
            seen[name] = usage_payload(
                {}, {"emit_wire_usage": False, "wire": {"ignored": 1}}
            )

    with begin_request_scope():
        record_build(_loss(3))
        record_build(_loss(6, dropped=2))
        record_lossless()
        threads = [
            threading.Thread(target=worker, args=("a", 7)),
            threading.Thread(target=worker, args=("b", 9)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        merged = usage_payload(
            {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}
        )["x_bridge_loss"]

    assert isinstance(merged, dict)
    assert merged["original_messages"] == 6
    assert seen["a"]["x_bridge_loss"]["original_messages"] == 7  # type: ignore[index]
    assert seen["b"]["x_bridge_loss"]["original_messages"] == 9  # type: ignore[index]


def test_nested_scope_restores_parent_and_orphan_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with begin_request_scope():
        record_build(_loss(5))
        with begin_request_scope():
            record_lossless()
            inner = usage_payload({}, {"emit_wire_usage": False})
        outer = usage_payload({}, {"emit_wire_usage": False})
    assert inner == {}
    assert outer["x_bridge_loss"]["original_messages"] == 5  # type: ignore[index]
    with caplog.at_level(logging.WARNING):
        record_build(_loss())
    assert "loss_receipt_orphan" in caplog.text
    assert usage_payload({}, {"emit_wire_usage": False}) == {}


def test_truncated_receipt_uses_zero_carrier_only_for_empty_wire() -> None:
    with begin_request_scope():
        record_build(_loss())
        carrier = usage_payload({}, {"emit_wire_usage": False})
        attached = usage_payload(
            {"input_tokens": 10, "output_tokens": 3, "thinking_tokens": 2}
        )
    assert carrier == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "x_bridge_loss": _loss().to_wire(),
    }
    assert attached == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 0,
        "x_bridge_loss": _loss().to_wire(),
    }


def test_resolved_wire_is_copied_and_receipt_attached() -> None:
    resolved: dict[str, Any] = {
        "emit_wire_usage": True,
        "wire": {"prompt_tokens": 8, "completion_tokens": 2, "total_tokens": 10},
    }
    with begin_request_scope():
        record_build(_loss())
        result = usage_payload({}, resolved)
    assert result["prompt_tokens"] == 8
    assert result["x_bridge_loss"] == _loss().to_wire()
    assert result is not resolved["wire"]
    assert "x_bridge_loss" not in resolved["wire"]


def test_lossless_and_suppressed_usage_stays_absent() -> None:
    with begin_request_scope():
        record_lossless()
        assert usage_payload({}, {"emit_wire_usage": False}) == {}
        positive = usage_payload({"input_tokens": 2, "output_tokens": 1})
    assert positive["x_bridge_loss"]["truncated"] is False  # type: ignore[index]


@pytest.mark.parametrize(
    ("usage", "resolved", "expected"),
    [
        (
            {"input_tokens": 2, "output_tokens": 3, "thinking_tokens": 4},
            None,
            {"prompt_tokens": 2, "completion_tokens": 7, "total_tokens": 0},
        ),
        ({}, {"wire": {"prompt_tokens": 4}}, {"prompt_tokens": 4}),
        ({"input_tokens": 2}, {"emit_wire_usage": False}, {}),
    ],
)
def test_flag_off_is_byte_identical_to_legacy_usage(
    monkeypatch: pytest.MonkeyPatch,
    usage: dict[str, object],
    resolved: object,
    expected: dict[str, object],
) -> None:
    monkeypatch.setenv("AGY_BRIDGE_LOSS_RECEIPT_ENABLED", "0")
    with begin_request_scope():
        record_build(_loss())
        assert usage_payload(usage, resolved) == expected


def test_usage_chunk_due_semantics() -> None:
    suppressed = {"emit_wire_usage": False}
    assert not usage_chunk_due({}, None)
    assert not usage_chunk_due({"prompt_tokens": 1}, suppressed)
    assert usage_chunk_due(
        {"completion_tokens": 1}, suppressed | {"emit_wire_usage": True}
    )
    assert not usage_chunk_due({"x_bridge_loss": _lossless().to_wire()}, suppressed)
    assert usage_chunk_due(
        {"prompt_tokens": 0, "x_bridge_loss": _loss().to_wire()}, suppressed
    )


class _Handler:
    def __init__(self) -> None:
        self.calls: list[tuple[int, dict[str, object]]] = []

    def _send(self, code: int, payload: dict[str, object]) -> None:
        self.calls.append((code, payload))


def test_send_client_compaction_required_delegates_exact_body() -> None:
    handler = _Handler()
    error = ClientCompactionRequired(5000, 4000, 3000, 12)
    send_client_compaction_required(handler, error)
    assert handler.calls == [(400, error.body)]
    body = cast("dict[str, Any]", error.body["error"])
    assert body["code"] == "context_length_exceeded"
    assert body["x_reason"] == "client_compaction_required"
    assert body["x_bridge_loss"]["fallback_reason"] == "input_guard"  # type: ignore[index]


def test_decorator_preserves_source_and_gives_each_call_a_fresh_scope() -> None:
    @begin_request_scope()
    def do_post(count: int) -> dict[str, object]:
        record_build(_loss(count))
        return usage_payload({}, {"emit_wire_usage": False})

    assert "def do_post(count: int)" in inspect.getsource(do_post)
    assert getattr(do_post, "__wrapped__", None) is not None
    assert do_post.__name__ == "do_post"
    first = do_post(3)
    second = do_post(8)
    assert first["x_bridge_loss"]["original_messages"] == 3  # type: ignore[index]
    assert second["x_bridge_loss"]["original_messages"] == 8  # type: ignore[index]
    assert usage_payload({}, {"emit_wire_usage": False}) == {}

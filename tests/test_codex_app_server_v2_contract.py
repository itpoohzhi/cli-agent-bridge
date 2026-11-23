"""Contract & expected-red tests for Codex app-server v2 protocol and catalogue (W0-A)."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stdio_resident.codex_driver import CodexAppServerDriver  # noqa: E402
from core.stdio_resident.process_io import (  # noqa: E402
    LINE,
    TIMEOUT,
    ResidentProcessHandle,
    TaggedLine,
)
from core.stdio_resident.protocol_driver import DecodedChunk  # noqa: E402
from core.stdio_resident.turn_stream import TurnStreamAssembler  # noqa: E402

EXPECTED_RED = "EXPECTED_RED:codex_v2"
SOL_EXPECTED_EFFORTS = ["low", "medium", "high", "xhigh", "max"]


class FakeHandshakeHandle:
    """In-memory process handle for pure unit handshake tests without subprocesses."""

    def __init__(self, lines: list[TaggedLine]) -> None:
        self._lines: list[TaggedLine] = list(lines)
        self.written: list[dict[str, Any]] = []

    def write(self, data: bytes) -> None:
        for raw in data.decode("utf-8").splitlines():
            if raw.strip():
                self.written.append(json.loads(raw))

    def read_line(self, timeout_s: float | None = None) -> TaggedLine | None:
        _ = timeout_s
        return self._lines.pop(0) if self._lines else None

    def read_stdout_line(self, timeout_s: float | None = None) -> TaggedLine | None:
        _ = timeout_s
        while self._lines:
            item = self._lines.pop(0)
            if not item.is_stderr:
                return item
        return None

    def read_line_outcome(
        self, timeout_s: float | None = None
    ) -> tuple[str, TaggedLine | None]:
        line = self.read_line(timeout_s=timeout_s)
        return (LINE, line) if line is not None else (TIMEOUT, None)


def _active_codex_driver() -> Any:
    candidates = (
        "core.stdio_resident.codex_v2_driver",
        "core.stdio_resident.codex_driver_v2",
        "core.stdio_resident.codex_driver",
    )
    for mod_name in candidates:
        try:
            mod = importlib.import_module(mod_name)
        except ImportError:
            continue
        cls = getattr(mod, "CodexAppServerV2Driver", None)
        if cls is not None:
            return cls()
    return CodexAppServerDriver()


def _import_contract_module(module_name: str, defect: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        pytest.fail(f"{EXPECTED_RED}: {defect} (missing {module_name}: {exc})")


def test_framing_accepts_optional_jsonrpc_and_v2_delta_events() -> None:
    """ADR-001 FSM #2/#8: accept responses without jsonrpc=2.0 and v2 delta notifications."""
    driver = _active_codex_driver()
    base = {"threadId": "thr-1", "turnId": "trn-1", "itemId": "itm-1"}
    init_resp = json.dumps({"id": 1, "result": {"userAgent": "codex/0.171.0-alpha.13"}})
    msg_delta = json.dumps(
        {"method": "item/agentMessage/delta", "params": {**base, "delta": "PONG"}}
    )
    reason_delta = json.dumps(
        {
            "method": "item/reasoning/textDelta",
            "params": {**base, "contentIndex": 0, "delta": "step"},
        }
    )
    summary_delta = json.dumps(
        {
            "method": "item/reasoning/summaryTextDelta",
            "params": {**base, "summaryIndex": 0, "delta": "brief"},
        }
    )

    decoded_init = driver.decode_line(init_resp)
    decoded_msg = driver.decode_line(msg_delta)
    decoded_reason = driver.decode_line(reason_delta)
    decoded_summary = driver.decode_line(summary_delta)

    assert decoded_init is not None, (
        f"{EXPECTED_RED}: framing dropped response without jsonrpc field"
    )
    assert decoded_msg is not None and decoded_msg.text == "PONG", (
        f"{EXPECTED_RED}: framing failed to decode item/agentMessage/delta"
    )
    assert decoded_reason is not None and decoded_reason.reasoning == "step", (
        f"{EXPECTED_RED}: framing failed to decode item/reasoning/textDelta"
    )
    assert decoded_summary is not None and decoded_summary.reasoning == "brief", (
        f"{EXPECTED_RED}: framing failed to decode item/reasoning/summaryTextDelta"
    )


def test_process_io_stdout_only_protocol_read_ignores_stderr() -> None:
    """ADR-001 Protocol FSM / F-006: process_io must provide stdout-only read_stdout_line."""
    read_stdout = getattr(ResidentProcessHandle, "read_stdout_line", None)
    assert callable(read_stdout), (
        f"{EXPECTED_RED}: ResidentProcessHandle lacks stdout-only read_stdout_line()"
    )


def test_lifecycle_handshake_ignores_stderr_and_sends_initialized() -> None:
    """ADR-001 FSM #1-#3: handshake skips stderr banner, matches id=1, sends initialized."""
    driver = _active_codex_driver()
    handle = FakeHandshakeHandle(
        [
            TaggedLine(line="WARN startup", generation=0, pid=42, is_stderr=True),
            TaggedLine(
                line='{"id": 1, "result": {"userAgent": "codex/0.171.0-alpha.13"}}',
                generation=0,
                pid=42,
                is_stderr=False,
            ),
        ]
    )

    ok = driver.run_handshake(handle, timeout_s=1.0)
    methods = [frame.get("method") for frame in handle.written]

    assert ok is True, f"{EXPECTED_RED}: handshake failed on stderr or optional jsonrpc"
    assert methods[:2] == ["initialize", "initialized"], (
        f"{EXPECTED_RED}: handshake must emit initialize then initialized, got {methods}"
    )


def test_lifecycle_forbids_client_thread_id_fabrication() -> None:
    """ADR-001 FSM #5: client must never fabricate th-1 threadId; server-issued only."""
    driver = _active_codex_driver()
    try:
        encoded = driver.encode_turn("PONG", {"model": "gpt-6.1-sol", "effort": "high"})
    except (ValueError, RuntimeError):
        return
    payload = json.loads(encoded.decode("utf-8"))
    thread_id = payload.get("params", {}).get("threadId", "")
    assert not str(thread_id).startswith("th-"), (
        f"{EXPECTED_RED}: lifecycle fabricated client-side threadId={thread_id!r}"
    )


def test_terminal_ack_is_nonterminal_and_failed_turn_is_error() -> None:
    """ADR-001 FSM #7/#9: turn/start ACK is non-terminal; status=failed is error."""
    driver = _active_codex_driver()
    ack_line = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "result": {"turn": {"id": "trn-srv-1", "status": "inProgress"}},
        }
    )
    failed_line = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "turn/completed",
            "params": {
                "threadId": "thr-srv-1",
                "turn": {
                    "id": "trn-srv-1",
                    "status": "failed",
                    "error": {"message": "upstream failure"},
                },
            },
        }
    )

    ack_chunk = driver.decode_line(ack_line)
    assert driver.is_terminal(ack_line, ack_chunk) is False, (
        f"{EXPECTED_RED}: terminal bug: turn/start ACK falsely treated as terminal"
    )
    failed_chunk = driver.decode_line(failed_line)
    assert failed_chunk is not None and failed_chunk.error, (
        f"{EXPECTED_RED}: terminal bug: turn/completed status=failed not marked error"
    )


def test_cancel_uses_turn_interrupt_with_thread_and_turn_ids() -> None:
    """ADR-001 FSM #10 & TurnInterruptParams.json: cancel uses turn/interrupt."""
    driver = _active_codex_driver()
    raw = driver.build_cancel_payload()
    assert raw is not None, f"{EXPECTED_RED}: cancel payload unexpectedly None"
    payload = json.loads(raw.decode("utf-8"))
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}

    assert payload.get("method") == "turn/interrupt", (
        f"{EXPECTED_RED}: cancel emitted forbidden method={payload.get('method')!r}"
    )
    assert "threadId" in params and "turnId" in params, (
        f"{EXPECTED_RED}: turn/interrupt missing required threadId/turnId: {params}"
    )


def test_protocol_fsm_pure_transitions_and_states() -> None:
    """ADR-001 Protocol FSM: pure transition(state, event) with all 9 lifecycle states."""
    fsm = _import_contract_module(
        "core.stdio_resident.codex_protocol_fsm",
        "pure codex v2 protocol FSM not implemented",
    )
    assert callable(getattr(fsm, "transition", None)), (
        f"{EXPECTED_RED}: codex_protocol_fsm missing transition(state, event)"
    )


def test_turn_stream_assembler_preserves_byte_invariance_across_splits() -> None:
    """ADR-001 Stream boundaries: arbitrary delta splits must not inject newlines."""
    expected = "Hello, world! PONG"
    splits = (
        [expected],
        list(expected),
        [expected[i : i + 7] for i in range(0, len(expected), 7)],
    )
    for parts in splits:
        assembler = TurnStreamAssembler()
        rendered = "".join(
            assembler.process_chunk(DecodedChunk(text=part)).content for part in parts
        )
        assert rendered == expected, (
            f"{EXPECTED_RED}: TurnStreamAssembler corrupted split: {rendered!r}"
        )


def test_catalogue_primary_codex_v2_route_and_sol_efforts() -> None:
    """ADR-001 Catalogue: separate codex-app-server-v2 contract and Sol xhigh effort."""
    codex_path = ROOT / "providers.d" / "codex.yaml"
    codex_yaml = yaml.safe_load(codex_path.read_text(encoding="utf-8"))
    sol_efforts = codex_yaml["models_overrides"]["gpt-6.1-sol"]["efforts"]
    assert sol_efforts == SOL_EXPECTED_EFFORTS, (
        f"{EXPECTED_RED}: providers.d/codex.yaml Sol efforts={sol_efforts!r}, "
        f"expected {SOL_EXPECTED_EFFORTS!r}"
    )
    _import_contract_module(
        "core.route_catalog_contract",
        "catalogue route contract separation module not implemented",
    )
    fleet = json.loads((ROOT / "fleet.json").read_text(encoding="utf-8"))
    models = {m["id"]: m for m in fleet["models"]}
    for model_id in ("gpt-6.1-sol", "gpt-6.1-terra"):
        route_ids = [r["route_id"] for r in models[model_id]["routing"]["routes"]]
        assert "codex-app-server-v2" in route_ids, (
            f"{EXPECTED_RED}: fleet.json {model_id} missing codex-app-server-v2 route"
        )


def test_recovery_fsm_module_contract() -> None:
    """ADR-001 Recovery FSM: separate route/credential domains requiring PONG receipt."""
    _import_contract_module(
        "core.codex_recovery_fsm",
        "codex recovery FSM module not implemented",
    )

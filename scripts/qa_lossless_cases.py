#!/usr/bin/env python3
"""Deterministic incident-corpus gate for lossless bridges (REQ-001..REQ-005)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
AGY_DIR = REPO_ROOT / "bridges" / "agy-bridge"
MUSE_DIR = REPO_ROOT / "bridges" / "muse-bridge"
for p in (str(AGY_DIR), str(MUSE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from core.lossless_chunker import iter_ndjson_frames  # noqa: E402
from core.lossless_contracts import DEFAULT_SAFE_FRAME_BYTES, LosslessLimits  # noqa: E402
from core.lossless_fsm import TERMINAL_STATES, EventKind, SessionEvent, SessionSnapshot, step  # noqa: E402
from core.lossless_gate import GateAction, evaluate_delivery_gate  # noqa: E402
from muse_runtime.context_pruner import _prune_messages  # noqa: E402
from muse_runtime.lossless_policy import evaluate_muse_prompt_policy  # noqa: E402
from muse_runtime.prompt_builder import _assemble_prompt  # noqa: E402
from muse_runtime.token_budget import _estimate_tokens  # noqa: E402


def _case_agy_350kib_lossless() -> dict[str, Any]:
    markers = [f"MK_{i:02d}" for i in range(1, 13)]
    payload = "\n".join(f"[{mk}] " + ('Кириллица "q" 🚀 ' * 1200) for mk in markers)
    raw_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    frames = list(iter_ndjson_frames(payload, safe_frame_bytes=DEFAULT_SAFE_FRAME_BYTES, max_chunks=16))
    rec = "".join(json.loads(f.ndjson_bytes.decode("utf-8"))["message"]["content"][0]["text"] for f in frames)
    ok = (
        len(frames) >= 4
        and all(len(f.ndjson_bytes) <= DEFAULT_SAFE_FRAME_BYTES for f in frames)
        and hashlib.sha256(rec.encode("utf-8")).hexdigest() == raw_sha
        and all(mk in rec for mk in markers)
    )
    return {"id": "INC-LOSSLESS-01", "ok": ok, "frames": len(frames)}


def _case_agy_overflow_413_redacted() -> dict[str, Any]:
    limits = LosslessLimits(lossless_enabled=True, max_chunks=2)
    dec = evaluate_delivery_gate("SECRET_999 " + ("x" * 300_000), limits)
    wire = json.dumps(dec.receipt.to_wire_dict()) if dec.receipt else ""
    ok = dec.action is GateAction.REJECT and dec.http_status == 413 and "SECRET_999" not in wire
    return {"id": "INC-LOSSLESS-02", "ok": ok, "status": dec.http_status}


def _case_fsm_zero_terminal_escapes() -> dict[str, Any]:
    escapes = 0
    for st in TERMINAL_STATES:
        snap = SessionSnapshot(state=st, active_epoch=1)
        for ev in EventKind:
            nxt, eff = step(snap, SessionEvent(ev, epoch=1))
            if nxt != snap or eff:
                escapes += 1
    return {"id": "INC-LOSSLESS-03", "ok": escapes == 0, "escapes": escapes}


def _case_muse_lossless_and_optin_413() -> dict[str, Any]:
    msgs = [{"role": "user", "content": "SECRET_MUSE " + ("z" * 10_000)}]
    dec = evaluate_muse_prompt_policy(
        msgs,
        limit=500,
        target=400,
        tools=None,
        tool_choice=None,
        raw_tools=None,
        prune_fn=_prune_messages,
        assemble_fn=_assemble_prompt,
        estimate_fn=_estimate_tokens,
        redact_fn=lambda s: s,
        env={"MUSE_BRIDGE_LOSSLESS_ENABLED": "true", "MUSE_BRIDGE_REFUSE_STATUS_MODE": "413"},
    )
    wire = json.dumps(dec.error_body or {})
    ok = (not dec.ok) and dec.http_status == 413 and "SECRET_MUSE" not in wire
    return {"id": "INC-LOSSLESS-04", "ok": ok, "status": dec.http_status}


def run_all_cases() -> list[dict[str, Any]]:
    return [
        _case_agy_350kib_lossless(),
        _case_agy_overflow_413_redacted(),
        _case_fsm_zero_terminal_escapes(),
        _case_muse_lossless_and_optin_413(),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run lossless bridge incident corpus gate.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = run_all_cases()
    ok = all(r["ok"] for r in results)
    if args.json:
        print(json.dumps({"ok": ok, "cases": results}, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"{r['id']}: {'PASS' if r['ok'] else 'FAIL'} {r}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

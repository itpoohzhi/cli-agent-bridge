#!/usr/bin/env python3
"""Детерминированный стаб `agy.real` для инцидентов EOF/Malformed function call.

Сценарии (`--scenario`):
  eof_then_ok        спавн 0: stall + eligibility EOF, rc=1; спавн >=1: успешный ответ.
  malformed_valid    служебная ошибка functionCall, затем валидные `<tool_call>`, result=ERROR.
  malformed_nine_ten тот же поток, но один из десяти `<tool_call>` — битый JSON (9/10).
  eof_always         каждый спавн: stall + EOF, rc=1 (оба повтора падают).
Живой режим (env `AGY_STUB_SCENARIO`): протокол реального `agy` (init/step_update/result в
stdout, `PLANNER_RESPONSE`/`ERROR_MESSAGE` в transcript_full.jsonl) — для Live-Isolated E2E.
Номер спавна хранится счётчиком в `--state-dir`. Без сети, секретов и реальных путей.
Чистая функция `build_run` пригодна для импорта без запуска процесса.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

USERINFO_EOF = (
    'Eligibility check failed: Get "https://www.googleapis.com/oauth2/v2/userinfo": EOF'
)
MALFORMED_TEXT = (
    "Your previous response contained an improperly formatted function call: "
    "Malformed function call: Failed to parse function call: Function call is empty - "
    "no input to parse. Please retry with a properly formatted function call "
    "Retries remaining: 3"
)
SCENARIOS = ("eof_then_ok", "malformed_valid", "malformed_nine_ten", "eof_always")
LIVE_CID = "c83f5757-1e5d-4a58-9d57-5d1a2c0de001"
_PLANNER_CALLS = 5


@dataclass(frozen=True)
class StubRun:
    """Результат одного спавна: события stdout, строка stderr и код возврата."""

    events: tuple[dict[str, object], ...]
    stderr: str
    rc: int


def _call_text(index: int, broken: bool) -> str:
    if broken:
        return '<tool_call>{"name": "read", "arguments": {"file_path": </tool_call>'
    body = {"name": "read", "arguments": {"file_path": f"/tmp/stub-{index}.txt"}}
    return f"<tool_call>{json.dumps(body)}</tool_call>"


def _planner_step(index: int, broken_at: int | None) -> dict[str, object]:
    # Пары представлений одного вызова: 5 вызовов, каждый дважды (10 блоков), как в idx4/idx6.
    # `broken_at` — индекс одного битого блока из десяти (9/10).
    texts = [_call_text(i % _PLANNER_CALLS, i == broken_at) for i in range(2 * _PLANNER_CALLS)]
    return {"event": "planner", "step_idx": index, "status": "DONE", "content": "".join(texts)}


def _malformed_events(broken_at: int | None) -> tuple[dict[str, object], ...]:
    error = {"event": "error_message", "step_idx": 5, "error": MALFORMED_TEXT}
    result = {"event": "result", "result": {"status": "ERROR", "error": MALFORMED_TEXT}}
    return (_planner_step(4, None), error, _planner_step(6, broken_at), result)


def _ok_events() -> tuple[dict[str, object], ...]:
    done = {"event": "planner", "step_idx": 2, "status": "DONE", "content": "Готово"}
    return (done, {"event": "result", "result": {"status": "SUCCESS", "text": "Готово"}})


def build_run(scenario: str, spawn_index: int) -> StubRun:
    """Вернуть детерминированный результат спавна `spawn_index` для сценария."""
    if scenario == "eof_always":
        return StubRun((), f"Print mode: eligibility check failed: {USERINFO_EOF}", 1)
    if scenario == "eof_then_ok":
        if spawn_index == 0:
            return StubRun((), f"Print mode: eligibility check failed: {USERINFO_EOF}", 1)
        return StubRun(_ok_events(), "", 0)
    if scenario == "malformed_valid":
        return StubRun(_malformed_events(None), "", 1)
    if scenario == "malformed_nine_ten":
        return StubRun(_malformed_events(8), "", 1)
    raise ValueError(f"unknown scenario: {scenario}")


def next_spawn_index(state_dir: Path, scenario: str) -> int:
    """Прочитать и увеличить счётчик спавнов в `state_dir`."""
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / f"{scenario}.count"
    index = int(path.read_text(encoding="utf-8")) if path.exists() else 0
    path.write_text(str(index + 1), encoding="utf-8")
    return index


def _emit(obj: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _transcript_records(scenario: str) -> list[dict[str, object]]:
    """Записи транскрипта `PLANNER_RESPONSE`/`ERROR_MESSAGE` из синтетических событий сценария."""
    records: list[dict[str, object]] = []
    for ev in build_run(scenario, 0).events:
        if ev["event"] == "planner":
            records.append({"type": "PLANNER_RESPONSE", "step_index": ev["step_idx"], "status": ev["status"],
                            "content": ev["content"], "tool_calls": [{"name": "read"}]})
        elif ev["event"] == "error_message":
            records.append({"type": "ERROR_MESSAGE", "step_index": ev["step_idx"], "content": ev["error"]})
    return records


def run_live(scenario: str, state_dir: Path, stall_s: float, settle_s: float) -> int:
    """Спавн в формате реального agy: stdin дочитан, события в stdout, транскрипт в HOME."""
    _ = sys.stdin.read()
    run = build_run(scenario, next_spawn_index(state_dir, scenario))
    if run.stderr:
        time.sleep(stall_s)
        sys.stderr.write(run.stderr + "\n")
        return run.rc
    if scenario.startswith("malformed"):
        logs = Path(os.environ["HOME"]) / ".gemini/antigravity-cli/brain" / LIVE_CID / ".system_generated/logs"
        logs.mkdir(parents=True, exist_ok=True)
        lines = (json.dumps(rec, ensure_ascii=False) for rec in _transcript_records(scenario))
        (logs / "transcript_full.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _emit({"event": "init", "conversation_id": LIVE_CID, "init": {"tools": [], "permission_mode": "auto"}})
    if scenario.startswith("malformed"):
        time.sleep(settle_s)
        result = {"status": "ERROR", "error": MALFORMED_TEXT, "conversation_id": LIVE_CID, "num_turns": 2}
    else:
        _emit({"event": "step_update", "step_update": {"step_type": "agent_response", "step_index": 2, "text_delta": "Готово"}})
        result = {"status": "SUCCESS", "response": "Готово", "conversation_id": LIVE_CID, "num_turns": 1}
    _emit({"event": "result", "result": result})
    return run.rc


def main(argv: Sequence[str] | None = None) -> int:
    live = os.environ.get("AGY_STUB_SCENARIO")
    if live:
        return run_live(live, Path(os.environ["AGY_STUB_STATE_DIR"]), float(os.environ.get("AGY_STUB_STALL_S", "0.6")),
                        float(os.environ.get("AGY_STUB_SETTLE_S", "0.6")))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--stall-s", type=float, default=0.0)
    args = parser.parse_args(argv)
    index = next_spawn_index(args.state_dir, args.scenario)
    run = build_run(args.scenario, index)
    if run.stderr and args.stall_s > 0:
        time.sleep(args.stall_s)
    for event in run.events:
        sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    if run.stderr:
        sys.stderr.write(run.stderr + "\n")
    return run.rc


if __name__ == "__main__":
    sys.exit(main())

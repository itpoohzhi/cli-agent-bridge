#!/usr/bin/env python3
"""Детерминированный стаб `agy.real` для инцидентов EOF/Malformed function call.

Сценарии (`--scenario`):
  eof_then_ok        спавн 0: stall + eligibility EOF, rc=1; спавн >=1: успешный ответ.
  malformed_valid    служебная ошибка functionCall, затем валидные `<tool_call>`, result=ERROR.
  malformed_nine_ten тот же поток, но один из десяти `<tool_call>` — битый JSON (9/10).
Номер спавна хранится счётчиком в `--state-dir`. Без сети, секретов и реальных путей.
Чистая функция `build_run` пригодна для импорта без запуска процесса.
"""

from __future__ import annotations

import argparse
import json
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
SCENARIOS = ("eof_then_ok", "malformed_valid", "malformed_nine_ten")
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


def main(argv: Sequence[str] | None = None) -> int:
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

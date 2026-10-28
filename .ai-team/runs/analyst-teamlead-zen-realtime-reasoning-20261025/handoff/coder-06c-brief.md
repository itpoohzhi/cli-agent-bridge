# Coder Brief — Cycle 4 Continuation (`coder-06c`): Fix `test_go_model_routing.py:388` Token-Bucket Drain on Mock `OSError` and Finalize Handoff

## Скилл роли Coder (ровно один путь по канону)
- `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md`

## Уже известно
- `repo_root`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning`
- `run_dir`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025`
- `branch`: `feature/zen-realtime-reasoning`
- `target_files` (`coder_target_files`):
  1. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py`
  2. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
  3. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_step_interruption.py`
- `prior_findings`:
  - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief.json`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json`
- Мост для субагентов: «Входы даны выше; на диск за ними не ходи; стартовый корень поиска ∈ {$HOME, /Users/<user>, /} запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни ASK».

## 1. Context & Exact Root Cause
- All `RW-001..RW-008` and `FU-001..FU-015` changes in `bridges/opencode-zen-bridge/server.py`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`, and `bridges/opencode-zen-bridge/tests/test_step_interruption.py` are already implemented, all 3 frozen hashes match, `VER-004` (`basedpyright`) exits `0`, and `pytest tests/test_realtime_reasoning.py tests/test_step_interruption.py` (`174 passed`) is green.
- The ONLY remaining blocker in `handoffs/coder-06.json` (`RP-03`) is a single failure when running the full test suite (`444 passed, 1 failed`):
  - `tests/test_go_model_routing.py:388` (`GoModelRoutingTest.test_stream_go_model_success_with_fake_launcher`) fails with:
    `AssertionError: '[мост] Подключение к модели…\nДумаю...' != 'Думаю...'`
- **Why this happens:**
  1. Immediately before `test_stream_go_model_success_with_fake_launcher`, `GoModelRoutingTest.test_effort_mapping_and_cli_flags` runs ~12 subTests calling `Run(...)._execute_once(...)` and `handler._stream_sse(...)` while mocking `_spawn_with_stdin` with `side_effect=OSError("test spawn")`.
  2. Both `Run._execute_once` and `Handler._stream_sse` call `res.spawn_limiter.acquire(...)` right before `_spawn_with_stdin(...)`.
  3. When `_spawn_with_stdin(...)` raises `OSError`, **no process was actually spawned** (`attempts.note_spawn()` is not called), yet the token in `res.spawn_limiter` (`_DEFAULT_RESILIENCE.spawn_limiter`, `rate=1.0/s`, `burst=1.0`) was consumed and never refunded!
  4. Consequently, `test_stream_go_model_success_with_fake_launcher` starts 1ms later with `0.0` tokens in `_DEFAULT_RESILIENCE.spawn_limiter` and blocks for `~0.95s` inside `res.spawn_limiter.acquire(...)`. Because `RW-002` keeps `status_timer` (`0.65s`) alive across `res.spawn_limiter.acquire(...)`, `status_timer` fires during that 0.95s wait and prepends `[мост] Подключение к модели…\n` to `Думаю...`!
- **Required Fix inside `bridges/opencode-zen-bridge/server.py` ONLY (do NOT touch `tests/test_go_model_routing.py`):**
  - Add a thread-safe `refund(self, amount: float = 1.0) -> None` method on `_TokenBucket` (restoring `self._tokens = min(self.burst, self._tokens + amount)` under `self._lock`), and call `res.spawn_limiter.refund()` inside `except OSError as exc:` right after `_spawn_with_stdin(...)` in both `Run._execute_once` and `Handler._stream_sse` (since no child process was spawned when `_spawn_with_stdin` raises `OSError`).
  - Remember: NEVER run full-file `ruff format` on `server.py`; only format changed ranges (`--range={start}:1-{end}:999`) as required by `VER-004`.
  - Verify that:
    - `test_rw002_initial_status_while_waiting_spawn_limiter` in `tests/test_realtime_reasoning.py` still passes (since it tests waiting inside `spawn_limiter.acquire()`, not `OSError` on `_spawn_with_stdin`),
    - `tests/test_go_model_routing.py` passes completely,
    - All 3 frozen functions (`_stream_google_sse`, `_execute_google_once`, `def _run_env`) retain their exact SHA-256 hashes,
    - `VER-004` (`basedpyright`) exits `0` (`newfile=0`, `server<=720`, `step<=194`),
    - Full `uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider tests` (`445 passed`) and full `python3 -m unittest discover -s tests -p 'test_*.py'` (`445 tests OK`) pass with 0 failures!

## 2. Finalize `plans/coder-06.json` and `handoffs/coder-06.json`
1. Update `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json`:
   - Set `"RP-03"` `"status": "DONE"`, update `actual_evidence` and `deviations` to reflect the clean fix in `server.py` (`res.spawn_limiter.refund()` on `_spawn_with_stdin` `OSError`) and `445 passed` in full `pytest` and `unittest`.
   - Validate:
     ```bash
     python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/teamlead-gate/scripts/validate_role_plan.py" \
       .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json \
       --phase after
     ```
2. Update `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json` (and copy byte-identically to `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json` and `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`):
   - Set `"status": "DONE"`, `"next_role": "reviewer"`, `"unresolved_risks": []`, `"open_questions": []`, update `"role_plan": {"path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json", "sha256": "<new_sha256_of_plans_coder_06_json>", "phase": "after"}`, update `"source_file_sha256"`, and record the green full `pytest`, full `unittest`, and `VER-004` results in `commands` and `verification_commands`.
   - Validate:
     ```bash
     python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/teamlead-gate/scripts/validate_handoff.py" \
       coder \
       .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json \
       --role-plan .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json \
       --root /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning
     ```

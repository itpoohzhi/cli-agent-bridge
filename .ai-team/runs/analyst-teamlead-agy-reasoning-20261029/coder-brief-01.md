# ROLE BRIEF — Coder (`coder-01`, Stage 3, LEAF SUBAGENT `AGENT_SPAWN_DEPTH=1`)

> **КРИТИЧЕСКОЕ ПРАВИЛО КОНТЕКСТА ЗАПУСКА (`AGENT_SPAWN_DEPTH=1`, `AGENTS.md` § «Глубина делегирования ≤ 1»):**
> 1. **ТЫ УЖЕ ЯВЛЯЕШЬСЯ ВНЕШНИМ САБАГЕНТОМ РОЛИ `Coder`** (`модель=claude-sonnet-5-5`, `effort=high`, `транспорт=claude -p`), запущенным главной сессией-оркестратором (`Antigravity`, семейство `Google`) в рамках открытого контура `cel` (`/tmp/cel-runs/analyst-teamlead-agy-reasoning-20261029`) и `analyst-teamlead` (`.ai-team/runs/analyst-teamlead-agy-reasoning-20261029`).
> 2. В `AGENTS.md` фраза «главная сессия файлы проекта не модифицирует» относится к родительскому оркестратору (`Antigravity`), который тебя вызвал! Для тебя (листового сабагента `Coder`, `AGENT_SPAWN_DEPTH=1`) действует правило **«Глубина делегирования ≤ 1 (субагент не порождает субагентов)»**.
> 3. **КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО** открывать собственный `/tmp/cel-runs/...`, делегировать работу дальше или вызывать `claude`, `agy-cli.sh`, `muse-cli.sh` или вложенный `codex`!
> 4. **ТВОЯ ПРЯМАЯ ОБЯЗАННОСТЬ В ЭТОМ ПРОЦЕССЕ:** лично создать `plans/coder-01.before.json`, лично отредактировать `bridges/agy-bridge/server.py` и `tests/test_agy_bridge_resilience.py`, лично прогнать проверки `VER-001..VER-010` и `VER-012`, и лично записать `plans/coder-01.json`, `handoffs/coder-01.json` и `coder.json`!


Skill: `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md`

- **Repository Root (`REPO`):** `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning`
- **Run Directory (`RUN_DIR`):** `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029`
- **Task ID:** `agy-realtime-reasoning`
- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Iteration:** `1`

## 1. Mandatory Inputs to Read First

Read these files in full before writing any code (they are now 100% synchronized on the approved SQLite `conversations/<cid>.db` + `_TranscriptTail` architecture `sha256=62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab`):
1. `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md`
2. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json`
3. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/panel/arch/final-panel-verdict.md` (**Раздел Б**, `F-001..F-009` mandatory safeguards!)
4. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/verification-surface.json`
5. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/handoff-architect.md`
6. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/handoff-qa.md`
7. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/bridges/agy-bridge/server.py`
8. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/tests/test_agy_bridge_resilience.py`

## 2. Strict Scope & Stop Conditions

- **Allowed Product Files to Modify (ONLY these 2 files outside `.ai-team/`):**
  1. `bridges/agy-bridge/server.py`
  2. `tests/test_agy_bridge_resilience.py` (strictly additive: do NOT delete or modify any existing lines in `tests/test_agy_bridge_resilience.py` so `VER-006` `git diff --unified=0 e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- tests/test_agy_bridge_resilience.py | grep -cE '^-[^-]'` equals `0`!)
- **Forbidden Paths:** Do NOT create or commit `bridges/agy-bridge/dynamic_config.json` in the repo (`VER-008`), and do NOT modify `analysis/agy-realtime-reasoning/**`, `core/**`, `ruff.toml`, `bridges/agy-bridge/fleet.json`, `bridges/agy-bridge/start.sh`, or any other test files.
- **No Git Mutations:** Do NOT run `git commit`, `git push`, `git reset`, `git checkout`, or `git stash`. Leave the modified files in the working tree for `CODE_GATE` and `Verifier`.
- **No `# type: ignore` or `# pyright: ignore` or `# noqa`:** Forbidden by `VER-004` and `F-007`.

## 3. Step-by-Step Execution Protocol

### Step 1: Write `plans/coder-01.before.json` and Validate `--phase before`
Before modifying `bridges/agy-bridge/server.py` or `tests/test_agy_bridge_resilience.py`, create:
`/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/coder-01.before.json`
with `schema_version: "1.0"`, `role: "coder"`, `task_id: "agy-realtime-reasoning"`, `run_id: "analyst-teamlead-agy-reasoning-20261029"`, `iteration: 1`, `plan_kind: "full"`, `objective`, `inputs_read`, `stop_conditions`, `deviations: []`, and `steps` (`RP-01..RP-05`, all with `status: "PENDING"`), and validate it:
```bash
python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" \
  --phase before \
  --role coder \
  "/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/coder-01.before.json"
```

### Step 2: Implement All Changes in `bridges/agy-bridge/server.py`
Implement the exact design in `architecture/architecture-packet.json` (`AD-001..AD-006`, `CD-001..CD-005`, `AO-01..AO-12`, `EVD-076`) and `panel/arch/final-panel-verdict.md` (`Раздел Б`, `F-001..F-009`):
1. **Fix all 12 baseline `basedpyright` errors (`EVD-076` in `architecture-packet.json`)** in `bridges/agy-bridge/server.py` with clean type annotations/narrowing (0 errors, 0 new warnings on `basedpyright@1.40.2`, no `# type: ignore` or `# pyright: ignore`).
2. **`AD-001` & `F-001`, `F-003`, `F-004`, `F-008` (Read-only SQLite live reasoning source `conversations/<cid>.db` + pure-Python wire parser + deduplication with `_TranscriptTail`):**
   - Open `~/.gemini/antigravity-cli/conversations/<cid>.db` (configurable via `AGY_BRIDGE_CONVERSATIONS`) strictly via `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=0.05, check_same_thread=False)` with `PRAGMA query_only=ON; PRAGMA busy_timeout=50;` (never use `mode=rw` or `immutable`, checked by `VER-009`).
   - Pure-Python protobuf wire parser for `steps.step_payload` (root field `20` length-delimited -> subfield `3` UTF-8 thinking text; skip wire types `0, 1, 2, 5`; trim incomplete trailing UTF-8 multibyte sequence on `status=8` snapshots; fail-open on malformed/truncated bytes without raising).
   - Shared per-step deduplication state (`seen_state` keyed by `idx == step_index`) with `observed_len`, `observed_sha256`, `delivered_len`, `delivered_sha256`, `finalized: bool`, `diverged: bool`:
     - Early exit `if state["finalized"]: continue/return` in both SQLite and transcript paths (`F-003`).
     - Prefix check via `sha256` of already delivered/observed prefix: if a new snapshot is NOT a prefix extension (`divergence`), increment `_sqlite_divergence_count`, log warning `sqlite_snapshot_divergence` / `sqlite_transcript_divergence`, mark step `diverged=True`, and freeze emission for that step at the already delivered prefix (`0` further chunks for that step from either source, `F-001`, `AO-08`).
     - Monotonically advance `poll_watermark` across contiguous `status=3` / `finalized` steps (including non-thinking steps) so `LIMIT 16` never stalls after 16 steps (`F-003`, `AO-10`).
     - Resume anchor (`watermark_resume`): on resumed turns (`resume=True`), capture pre-spawn SQLite max `idx` anchor before spawning `agy`; if pre-spawn SQLite anchor fails, set `turn_mode="OFF"` for the entire turn (`F-001`, `AO-12`).
     - Active `cid` ownership (`_active_cid_owners` under `_session_store_lock`, `F-004`, `AO-08`): atomically register `cid -> turn_id` on `init` / pre-claim; if `cid` is already owned by another active turn, do not overwrite owner and set `turn_mode="OFF"`; release in `finally` only if owned by `turn_id`.
     - Semantic canary (`SHADOW -> LIVE` per `binary_identity = (st_mtime_ns, st_size)` of `agy` binary under `_sqlite_guard_lock`, `F-003`, `AO-12`).
     - Store reasoning chunks in `list[str]` and `"".join` once (`F-008`), enforcing `MAX_REASONING_BYTES_PER_TURN = 2 * 1024 * 1024` in `_emit_reasoning` (`AD-001.details.memory_bounds`, `AO-05`: `AC-004` holds for all `ASM-001` turns within `<= MAX_REASONING_BYTES_PER_TURN`, while any turn exceeding `2 MiB` is explicitly capped at `2 MiB` with `reasoning-cap` per `AO-05`).
3. **`AD-002` & `F-005` (Deterministic post-EOF drain & atomic queue close):**
   - Wrap `Run._pump` body in `try/finally` guaranteeing a single idempotent call to `_close_and_put_done(run, ...)` under `run._emit_lock` (`F-005`, `AO-03`, `AO-11`).
   - Hold the full post-EOF drain window (`DRAIN_WINDOW_S = 0.35` s default, configurable via `AGY_BRIDGE_DRAIN_MIN` / `AGY_BRIDGE_TRANSCRIPT_GRACE` / `AGY_BRIDGE_DRAIN_JOIN`, capped so EOF -> `stop` <= 1.0 s) without the heuristic early exit (`F-005`, `AO-03`).
   - Suppress `sqlite3.ProgrammingError` / `sqlite3.OperationalError` when calling `conn.interrupt()` under the connection lock on an already-closed connection (`F-005`, `AO-11`).
   - `_execute` drains `run.q` until `"done"` so no reasoning emitted before `"done"` is ever lost (`REQ-006`).
4. **`AD-003` (`delivered` includes emitted reasoning, `REQ-008`, `AO-07`):**
   - Treat any emitted `reasoning` chunk (`bool(out.get("reasoning"))` / `reasoning_delivered`) as `delivered = True` in `_run_once`, forbidding silent retry after reasoning has already been streamed to the client (`AC-010`, `AO-07`).
5. **`AD-004` (Hot session isolation for background tool-less requests, `REQ-009`, `AO-04`):**
   - Do not claim or commit `_session_store` hot sessions for requests with `tools_count == 0` (`not has_tools`), preventing DSH background title-generation calls from stealing or overwriting agentic conversation sessions (`AC-011`, `AO-04`).
6. **`AD-005` & `F-002` (Circuit breaker, token buckets, and observability, `REQ-004`, `REQ-010`, `REQ-012`, `AO-01`, `AO-02`, `AO-06`):**
   - Integer token buckets (per-turn SQLite poll bucket `N(Δt) <= 3 + 2*Δt` and process-wide retry budget) + 3-state circuit breaker (`CLOSED`, `OPEN`, `HALF_OPEN` with `probe_gen`) under `_sqlite_guard_lock` (`AO-01`, `AO-02`).
   - Check schema errors (`no such table` / `no such column`) BEFORE `cold-open` (`unable to open database file` before DB creation) on the first `SELECT` so schema errors increment `consecutive_failures` (`F-002`, `AO-01`).
   - Add the 4 additive diagnostic fields to `/health` (`sqlite_reasoning_mode`, `sqlite_breaker_state`, `sqlite_divergence_count`, `sqlite_drain_deadline_count`) while keeping all existing `/health` fields unchanged (`REQ-010`, `AO-06`).
   - Emit structured diagnostic logs (`sqlite-emit`, `sqlite-off`, `drain`, etc.) without leaking thinking text or secrets (`REQ-012`).
7. **`AD-006` & `F-006` (Feature flag `SQLITE_REASONING_ENABLED` & env `AGY_SQLITE_REASONING_ENABLED`, `REQ-011`, `AO-09`):**
   - Read `dynamic_config.json` (cached with 1.0 s TTL, fail-closed `False` by default) and `AGY_SQLITE_REASONING_ENABLED` env override.
   - Re-check `_is_sqlite_reasoning_enabled()` on every poll iteration and before processing each row; if disabled mid-turn, call `conn.interrupt()`, close the DB connection, and log `sqlite-off reason=flag` within `<= 2.0 s` (`F-006`, `AO-09`).

### Step 3: Add All 52 New Tests (`TC-*`, `AO-01..AO-12`, `tc93`) to `tests/test_agy_bridge_resilience.py`
- Keep all 22 existing tests in `tests/test_agy_bridge_resilience.py` completely untouched (`0` deleted/modified lines vs `e00da0621fc95f7c63cd1565f4a5d1fd490c8d66` for `VER-006`!).
- Append all 52 new test methods inside `unittest.TestCase` classes (`F-007`) covering every required ID in `VER-007` (`tc01..tc12, tc20, tc21, tc23, tc24, tc30..tc33, tc40..tc44, tc50, tc51, tc60..tc63, tc70..tc72, tc80..tc82, tc91, tc92`, `ao01..ao12`) plus `tc93` / `l2_harness` (`VER-010`).

### Step 4: Run and Pass All L1 Gates (`VER-001..VER-010`, `VER-012`)
Run every command from `architecture/architecture-packet.json` (`verification_surface`) and verify `exit_code == 0`:
- `VER-001`: `uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py`
- `VER-002`: `uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py`
- `VER-003`: `PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py`
- `VER-004`: `basedpyright@1.40.2` zero errors and zero new warnings vs `e00da0621fc95f7c63cd1565f4a5d1fd490c8d66`
- `VER-005`: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_*agy*.py"`
- `VER-006`: `git diff` additive-only check on `tests/test_agy_bridge_resilience.py`
- `VER-007`: AST check of all 51 `tc*`/`ao*` IDs + assertions
- `VER-008`: Modified files & frozen analyst hashes check
- `VER-009`: AST check of imports and `sqlite3.connect(..., uri=True)` + no `immutable`
- `VER-010`: `tc93 or l2_harness` in both `pytest` and `/usr/bin/python3 -m unittest`
- `VER-012`: `/usr/bin/python3 -B -m unittest discover -s tests -p "test_*agy*.py"`

### Step 5: Write `plans/coder-01.json`, `handoffs/coder-01.json`, and `coder.json` and Validate
1. Write `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/coder-01.json` (`phase: "after"`, all steps `status: "DONE"` with `evidence` and `actual_evidence`) and validate with `validate_role_plan.py --phase after --role coder`.
2. Write `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/handoffs/coder-01.json` (and copy to `coder.json`) and validate with `validate_handoff.py coder`.

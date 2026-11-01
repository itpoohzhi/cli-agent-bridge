# Coder Brief — Task 1: DSH Timeout Finish Reason Bugfix

## 1. SDLC Profile & Meta
- **Skill Path:** `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md`
- **Target Repository:** `/Users/aazhiry1/work/src/cli-agent-bridge`
- **Assigned Model:** `gpt-6.1-sol` (effort: `high`) via `codex exec`
- **Architecture Consensus Proof:** `PANEL PROOF: /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-timeout-finish-reason-20261102/receipts/arch-panel.json sha256=234e2d3902003de67d97aae423ae2017f95921656e62d0a0fb4ae25e57f8dd2e verify_panel_proof exit=0`

## 2. Problem Statement & Root Cause
In `bridges/agy-bridge/server.py` (`finalize_timeout`), when an AGY turn hits the wall-clock execution limit (`AGY_TIMEOUT_S=3600.0`, elapsed ~3594.5s), graceful timeout completes partial streaming with `finish_reason="length"`.
DeepSeek Harness parses `finish_reason="length"` as `TurnMaxTokensItem` and displays a yellow warning banner:
> "Output token limit reached. The reply was cut off; earlier output is preserved in the conversation. Send 'continue' to let the model resume."

This misleads the user into thinking output tokens were exceeded, when in reality it was a 1-hour turn execution timeout.
Per OpenAI standard and chat completion semantics, graceful timeout after partial stream completion should emit `finish_reason="stop"` by default, while remaining fully configurable via environment variable and `dynamic_config.json` without any vendor-specific hardcoding.

## 3. Implementation Requirements

### 3.1 `bridges/agy-bridge/server.py`
1. **Extend `_RuntimeFlags` (line ~2925):**
   Add field 7 `graceful_timeout_finish_reason: str = "stop"`.
   Preserve all existing 6 fields intact, including `stream_resilience_enabled: bool = True`:
   ```python
   class _RuntimeFlags(NamedTuple):
       """Неизменяемый валидированный снимок флагов новой политики."""
       planner_content_streaming_enabled: bool = False
       emit_tool_trace: bool = False
       extended_timeout_enabled: bool = False
       graceful_timeout_on_partial: bool = False
       step_scoped_usage_enabled: bool = False
       stream_resilience_enabled: bool = True
       graceful_timeout_finish_reason: str = "stop"
   ```

2. **Update `_parse_runtime_flags` (line ~2953):**
   - Update `values` type annotation: `values: dict[str, Any] = {}`.
   - The boolean flag loop processes only boolean fields (`_RuntimeFlags._fields` except `graceful_timeout_finish_reason`).
   - For `graceful_timeout_finish_reason`:
     Read string value from `raw.get("graceful_timeout_finish_reason")` or uppercase alias `AGY_GRACEFUL_TIMEOUT_FINISH_REASON`.
     If value is not string or unrecognized, fallback to `"stop"`.
     Do not raise ValueError on invalid string value for `graceful_timeout_finish_reason` (safe fallback to `"stop"`).
     Put `values["graceful_timeout_finish_reason"] = reason`.

3. **Helper function `_graceful_finish_reason(default: str = "stop") -> str`:**
   Implement dynamic resolution:
   - Check `os.environ.get("AGY_GRACEFUL_TIMEOUT_FINISH_REASON", "").strip()`.
   - If empty, check `getattr(_runtime_snapshot(), "graceful_timeout_finish_reason", default)`.
   - Normalize: if lowercase value in `("length", "max_tokens")`, return `"length"`. Otherwise return `"stop"`.

4. **Update `finalize_timeout` Call Sites:**
   - JSON mode (~line 6927):
     Replace `"length"` with `_graceful_finish_reason()`.
   - SSE mode (~line 7111):
     Replace `"length"` with `_graceful_finish_reason()`.

5. **`_graceful_notice`:**
   Ensure the warning text in partial output clearly indicates that the turn reached the execution time limit (e.g. 3600s), avoiding token confusion.

### 3.2 `tests/test_agy_bridge_resilience.py`
1. Update existing tests asserting `"length"` on graceful timeout to reflect new default `"stop"`.
2. Add dedicated test cases:
   - Default emission is `"stop"`.
   - `AGY_GRACEFUL_TIMEOUT_FINISH_REASON="length"` restores `"length"`.
   - `dynamic_config.json: {"graceful_timeout_finish_reason": "length"}` restores `"length"`.
   - Invalid/empty string falls back to `"stop"`.
   - `DialogueStreamResilienceTests` passes cleanly.

## 4. Verification & Output Artifacts
- Run: `/Users/aazhiry1/work/src/cli-agent-bridge/.venv/bin/pytest tests/test_agy_bridge_resilience.py -v`
- Save patch to `.ai-team/runs/dsh-timeout-finish-reason-20261102/coder/candidate.patch`.
- Save manifest and test execution report to `.ai-team/runs/dsh-timeout-finish-reason-20261102/coder/handoff.md`.

You are the Stage 4 Coder (`claude-sonnet-5-5` `high`) for task `agy-universal-image-fallback-20261029` in repository `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback` (branch `feat/agy-universal-image-fallback`, base commit `012da99905ec27a6133afb4f3e768ff9b4426a8f`).

## Mandatory Skill (Read First)
Read `/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/coder/SKILL.md` in full before any action and follow every rule.

## Frozen Inputs & Contracts (Read Before Writing Any Code)
1. `.ai-team/runs/agy-universal-image-fallback-20261029/task.json` (`architecture_gate`: allowed_files are ONLY `["bridges/agy-bridge/server.py", "tests/test_agy_bridge_resilience.py"]`! Do NOT modify `bridges/agy-bridge/fleet.json` or any file in `analysis/` or any other repo file outside `.ai-team/runs/agy-universal-image-fallback-20261029/`!)
2. `.ai-team/runs/agy-universal-image-fallback-20261029/architecture/architecture-packet.json` (`AD-001..AD-005`)
3. `.ai-team/runs/agy-universal-image-fallback-20261029/teamlead/verification-surface.json` (`VER-001..VER-010`)
4. `analysis/agy-universal-image-fallback/handoff-architect.md` and `analysis/agy-universal-image-fallback/handoff-qa.md`
5. For exact JSON schema of `plans/coder-01.json` and `handoffs/coder-01.json`, you may inspect `/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py` and `/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_handoff.py`.

## Step-by-Step Instructions
1. **Role Plan Before (`plans/coder-01.initial.json` -> `plans/coder-01.json`)**:
   - Create `.ai-team/runs/agy-universal-image-fallback-20261029/plans/coder-01.initial.json` (and copy to `plans/coder-01.json`) with `role: "coder"`, `status: "READY"`, and steps `S1..S5` (`PENDING`), and verify:
     `python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" --phase before .ai-team/runs/agy-universal-image-fallback-20261029/plans/coder-01.initial.json` exits with `0`.
2. **Implement `AD-001..AD-004` in `bridges/agy-bridge/server.py`**:
   - Follow `architecture-packet.json` (`AD-001`, `AD-002`, `AD-003`, `AD-004`) to the letter!
   - Also incorporate the 4 minor refinements noted by the Architecture Panel (`ARCH_PANEL` R1):
     - In `_image_gate_universal(model_id, effort)`: when `effort is None` or `effort == ""`, allow if model is in `FLEET_MODELS` (mirroring `_image_proof_reason`), and when `effort` is provided, verify `effort in model["efforts"]`.
     - In `_downgrade_to_text_in_run_once` / session invalidation: in addition to `_session_invalidate(sess_key, old_cid)` and `_cid_release(old_cid, turn_id)`, also safely discard `old_cid` from `_in_flight_cids` under `_session_store_lock` if needed, and if `ctx.get("stripped_full_prompt")` was not pre-populated by a direct unit-test caller of `_run_once`, compute/fallback to a safe media-free text prompt without `[attachments]` or `[image N]`.
     - Ensure `_reset_sqlite_guards_for_tests()` resets `_image_fallback_flag_cache = (0.0, False)` alongside `_image_flag_cache`.
     - Ensure `_strip_media_from_messages` / `_messages_to_stripped_prompt` never mutates caller's `messages` in-place, classifies media `type` and payload keys BEFORE reading `"text"`, replaces image blocks (`image_url`, `image`, `input_image`) with `"[image omitted]"` and non-image media blocks (`input_audio`, `audio`, `video`, `video_url`, `file`, `document`, `inlineData`, `inline_data`, `fileData`, `file_data`) with `"[media omitted]"`, handles dict `content`, and preserves idempotency (`normalize(normalize(msgs)) == normalize(msgs)`).
3. **Append `UniversalImageFallbackTests` (`AD-005`) to `tests/test_agy_bridge_resilience.py`**:
   - **CRITICAL**: Do NOT modify or delete a single byte of the existing 6008 lines (`249933` bytes, sha256 `f318d605fa4643fd9eb8194a59d376c6134ff668a7ba2f094f8d2621330eeff5`) of `tests/test_agy_bridge_resilience.py`! Append the new helper functions and `class UniversalImageFallbackTests(unittest.TestCase):` (`test_uf01_...` through `test_uf10_...`) strictly AFTER the existing bytes of `tests/test_agy_bridge_resilience.py`.
   - Ensure the new test helper restores `AGY_IMAGE_FALLBACK_ENABLED` and `DYNAMIC_CONFIG_PATH` / caches cleanly so test order (`strict -> universal -> strict`) never leaks state.
4. **Run All Verification Commands (`VER-001..VER-010`)**:
   - Execute every command in `.ai-team/runs/agy-universal-image-fallback-20261029/teamlead/verification-surface.json` (`VER-001..VER-010`).
   - Fix any lint (`ruff check`, `ruff format --check`), typecheck (`basedpyright`), or test issues until `VER-001..VER-010` all pass with exit code `0`!
5. **Finalize Role Plan After (`plans/coder-01.json`) and Handoff (`handoffs/coder-01.json`)**:
   - Update `plans/coder-01.json` (`status: "DONE"`, all steps `"DONE"`) and validate with `validate_role_plan.py --phase after`.
   - Capture `.ai-team/runs/agy-universal-image-fallback-20261029/fingerprints/coder-after.json` using `worktree_fingerprint.py --root "$REPO" --exclude ".ai-team/runs" --write ...`.
   - Write `.ai-team/runs/agy-universal-image-fallback-20261029/handoffs/coder-01.json` and validate with:
     `python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_handoff.py"` (check `--help` for exact flags).
   - Write a summary of changes and `VER-001..VER-010` results to `.ai-team/runs/agy-universal-image-fallback-20261029/coder/summary.md`.

You are the Stage 1 System Analyst (`system-analyst` skill, `gpt-6.1-sol` `high`) for task `agy-universal-image-fallback-20261029` in repository `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback` (branch `feat/agy-universal-image-fallback`, base commit `012da99905ec27a6133afb4f3e768ff9b4426a8f`).

First, read `~/Мой диск/skils/ai-sdlc/system-analyst/SKILL.md` in full and follow every rule and DoD check (`SA-DOD-001..008`).

## Task Context & Owner Request
The user asked:
1. "Поддержка картинок для gemini-4-argon и gemini-3.8-flash - а такое надо для каждой модел? можно это сделать более универсально? что бывсегда примнимать и посылать если дает отлуп то удалять и без медиа и картинок"
2. "запускай доработку по скилу аналитик техлид что бы по моей идее работало"

## Core Technical Problem & Requirements to Analyze
Inspect:
- `bridges/agy-bridge/server.py` (especially `_is_image_input_enabled`, `_image_proof_reason`, `_model_supports_images`, `_image_gate`, `_collect_image_parts`, `_collect_images`, `_stage_images`, `_flatten_content`, `_messages_to_prompt`, `_get_resumed_turn_prompt`, `_run_once`, `do_POST`, `/v1/models`, `/health`)
- `bridges/agy-bridge/fleet.json`
- `bridges/muse-bridge/server.py` (lines 633-650) and `bridges/opencode-zen-bridge/server.py` (lines 4677-4694) for how `[image omitted]` is already used in sibling bridges
- `tests/test_agy_bridge_resilience.py` (especially lines 3803-6009)
- `analysis/agy-image-input-fix/` (previous task's analysis for context)

Analyze the exact mechanics needed so that:
1. **Universal Optimistic Image Acceptance & Send ("всегда принимать и посылать")**:
   - In `agy-bridge`, any model accepts requests with images/media without requiring per-model manual `proof` / `agy_binary_sha256` / `efforts_proven` whitelisting to avoid HTTP 400.
   - When valid decodable raster images (`image/png`, `image/jpeg`, `image/gif`, `image/webp` within size/count limits) are present in `user` messages and image staging is enabled (`IMAGE_INPUT_ENABLED` — which should be enabled in production `dynamic_config.json` and/or optimistic when trying images), `agy-bridge` stages them into `img_dir` and attempts `attempt == 1` with `--add-dir <img_dir>` and `[attachments]` prompt instructions.
2. **Automatic Media & Image Stripping Fallback on Reject/Failure ("если дает отлуп то удалять и без медиа и картинок")**:
   - **Runtime CLI Reject / Failure on Attempt 1 (`_run_once`):**
     If `attempt == 1` ran with `images` attached (`add_dir=img_dir`) and `agy` CLI failed or rejected the turn (`out["state"] != "done"` and `out["state"] != "client_gone"` and `not delivered`), `agy-bridge` MUST NOT fail the request or retry with the same images. Instead, before `attempt == 2`, it MUST:
     - Clean up `img_dir` (`_cleanup_img_dir(img_dir)`), set `img_dir = None` and `images = []`,
     - Invalidate any hot session (`_invalidate_hot_session_if_matches(session_key, conv_id)`),
     - Rebuild/switch `ctx["prompt"]` and `ctx["full_prompt"]` to a **media-stripped text-only prompt** (where all `image_url` and any non-text media parts like `image`, `input_image`, `input_audio`, `audio`, `video`, `file`, `document`, `inlineData`, `fileData` are replaced with `[image omitted]` / `[media omitted]` or stripped, and NO `[attachments]` block is included, and if a message becomes empty after stripping media, a safe fallback prompt is preserved),
     - Execute `attempt == 2` as a pure text-only turn (`add_dir=None`), returning HTTP 200!
   - **Pre-Stage / Pre-Spawn Image Reject or Unsupported Model/Flag/Media Fallback:**
     What happens when a request contains `image_url` (or other media blocks) that cannot be staged as valid images (e.g., `ImageReject` due to unsupported/unverified model, `IMAGE_INPUT_ENABLED=false`, binary SHA mismatch, unsupported effort, remote `http://`/`https://`/`file://` URL, unsupported MIME like SVG/BMP, corrupt base64, MIME mismatch, non-user role, >16 images, >20MB image, OR `ImageSpoolError` during `_stage_images`)?
     Analyze how `agy-bridge` should handle this so that:
     - In universal fallback mode (the production default / when universal fallback is enabled), instead of killing the user's DSH Desktop chat with HTTP 400 or HTTP 500, `agy-bridge` catches `ImageReject` / `ImageSpoolError`, logs a structured fallback event (`image_fallback ...`), strips all images and media parts from `messages[]` (`[image omitted]`, no `[attachments]`, `images = []`, `add_dir = None`), and runs the turn as pure text (`HTTP 200`)!
     - **CRITICAL BACKWARD-COMPATIBILITY & TEST CONSTRAINT (`VER-006` / `VER-007`):**
       Inspect `tests/test_agy_bridge_resilience.py` lines `3803..6009`! Notice that existing unit tests (`test_ao01`, `test_ao02`, `test_ao03`, `test_log01`, `test_log02`, `test_res02`, `test_f001`, `test_f002`, `test_life03`, `test_ao10`) and `VER-006` (`git diff --numstat 5a19559426de7508d525e2bd465eff648665a6a7 -- tests/test_agy_bridge_resilience.py` must have `0` deleted lines!) test strict rejection (`HTTP 400` / `HTTP 500`) and `test_ao10` checks repo default constants!
       Analyze the exact mechanism (e.g., how `IMAGE_FALLBACK_ENABLED` / `AGY_IMAGE_FALLBACK_ENABLED` / `IMAGE_POLICY` or `dynamic_config.json` vs unit-test harness setup works, or how `test_ao10` and `test_ao01..ao03` interact with the flag/config) so that:
       (a) ALL existing 44 tests in `tests/test_agy_bridge_resilience.py` (`img01..10`, `hist01..10`, `life01..05`, `log01..02`, `res01..03`, `ao01..10`) pass 100% WITHOUT deleting or modifying any existing lines in `tests/test_agy_bridge_resilience.py` (`0` deleted lines in `git diff --numstat`!),
       (b) New comprehensive tests (`uf01..uf10` or similar) are APPENDED to `tests/test_agy_bridge_resilience.py` verifying universal model acceptance, pre-stage `ImageReject` -> media-stripped HTTP 200 fallback, `ImageSpoolError` -> media-stripped HTTP 200 fallback, `attempt == 1` CLI error with images -> `attempt == 2` media-stripped HTTP 200 fallback, non-text media stripping (`input_audio`, `file`, `video`, `image`, `document`), and multi-turn history resilience,
       (c) In production (`bridges/agy-bridge/` + `~/.dsh/bridges/agy-bridge/dynamic_config.json` and/or default runtime when not in strict test mode), universal acceptance + auto-strip fallback is ACTIVE for all models so DSH Desktop NEVER gets HTTP 400 on images/media!

## Required Outputs
Create all 5 files in `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/analysis/agy-universal-image-fallback/`:
1. `research-plan.md`
2. `evidence-ledger.md`
3. `open-questions.md` (all questions must be RESOLVED with concrete evidence; 0 unresolved)
4. `handoff-architect.md` (with `REQ-*`, `CON-*`, `INV-*`, `RISK-*`, `ASSUMP-*`, and a Mermaid `flowchart` diagram)
5. `handoff-qa.md` (with `AC-*`, `SCN-*`, negative/boundary/idempotency/resource scenarios)

Ensure every requirement of `SA-DOD-001..008` in `~/Мой диск/skils/ai-sdlc/system-analyst/SKILL.md` is satisfied. Write a final summary to `$RUN_DIR/analyst/summary.md`.

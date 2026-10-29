PANEL-NONCE: 16b5fb5706ca88a7

# Architecture Panel Review (R1) — `agy-universal-image-fallback-20261029`

You are an independent Architecture Panel Judge (`ARCH_PANEL` Round 1) reviewing the Architecture Packet (`AP/v1`) for task `agy-universal-image-fallback-20261029` in repository `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback`.

## Artifact Under Review
- Architecture Packet: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/architecture/architecture-packet.json`
- Verification Surface: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/teamlead/verification-surface.json`
- Stage 1 System Analyst Handoffs:
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/analysis/agy-universal-image-fallback/handoff-architect.md`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/analysis/agy-universal-image-fallback/handoff-qa.md`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/analysis/agy-universal-image-fallback/evidence-ledger.md`
- Target Code & Tests (Read-Only):
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/server.py`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/bridges/agy-bridge/fleet.json`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/tests/test_agy_bridge_resilience.py`

## Owner Goal & Requirements Summary
1. **Universal Optimistic Image Acceptance (`AD-001`)**:
   - Controlled by `IMAGE_FALLBACK_ENABLED` in `dynamic_config.json` and `AGY_IMAGE_FALLBACK_ENABLED` env override (default `False` when absent so existing strict tests in `_ImgEnv` / `_Fixture` remain 100% green without modification; enabled in production `dynamic_config.json` alongside `IMAGE_INPUT_ENABLED: true`).
   - When `universal=True` and `input_enabled=True`, any catalog model in `FLEET_MODELS` and valid effort accepts valid user raster images (`png/jpeg/gif/webp`, `<=16` images, `<=20MB`) without requiring per-model `proof` / `agy_binary_sha256` / `efforts_proven` whitelisting, staging them to `img_dir` and passing `--add-dir <img_dir>` + `[attachments]` on `attempt == 1`.
2. **Complete Media Stripping & Three Downgrade Points (`AD-002`, `AD-003`)**:
   - **Pre-collect (`do_POST`, `stage="collect"`):** If `universal=True` and (`not input_enabled` or `_collect_images` raises `ImageReject`), strip all media/images (`[image omitted]` / `[media omitted]`, no `[attachments]`, `images = []`) and proceed as pure text turn (`HTTP 200`).
   - **Post-slot (`_run_once`, `stage="post_slot"` / `stage="spool"`):** If `universal=True` and (`_is_image_input_enabled()` flipped `False` while waiting for slot or `_stage_images` raises `ImageSpoolError`), clean up `img_dir`, invalidate/release hot session if any, switch `ctx["prompt"]` and `ctx["full_prompt"]` to `ctx["stripped_full_prompt"]`, and proceed into `attempt == 1` with `add_dir=None`.
   - **Runtime retry (`_run_once`, `stage="runtime"`):** If `universal=True` and `attempt == 1` ran with `images` (`img_dir is not None`) and `out["state"] not in ("done", "client_gone")` and `not delivered` (`text`/`tool_calls`/`delivered_reasoning` all empty), BEFORE early `if hot_resumed: ... continue` and generic `_retry_Transient`, clean up `img_dir`, clear `images = []`, CAS-invalidate and release hot session (`_session_invalidate`, `_cid_release`), reset `hot_resumed = False` and `conversation_id = ""`, switch `ctx["prompt"]` and `ctx["full_prompt"]` to `ctx["stripped_full_prompt"]`, and run `attempt == 2` as pure text (`add_dir=None`) using the 1-attempt media-degradation reserve even if generic `_retry_tenths == 0`.
3. **Observability & Test Preservation (`AD-004`, `AD-005`)**:
   - Preserve `bridges/agy-bridge/fleet.json` and all 6008 existing lines of `tests/test_agy_bridge_resilience.py` (`0` deleted lines, byte-identical prefix).
   - Append `UniversalImageFallbackTests` (`test_uf01_..` through `test_uf10_..`) covering `SCN-uf01..uf10`, `SCN-B01..B02`, `SCN-R01..R02`, `SCN-I01`.

## Review Instructions (Read-Only)
1. Do NOT modify any files.
2. Evaluate `architecture-packet.json` and `verification-surface.json` against `REQ-01..06`, `CON-01..06`, `INV-01..12`, `RISK-01..08`, and actual code in `bridges/agy-bridge/server.py`.
3. Provide your structured review with:
   - Concrete findings (if any) classified as `BLOCKER-SAFETY`, `BLOCKER`, `MAJOR`, or `MINOR` with exact file/line or section citations.
   - Final verdict line: `VERDICT: PASS` (if 0 blockers) or `VERDICT: NEEDS_WORK` (if any blocker exists).


IMPORTANT: You MUST echo the exact line `PANEL-NONCE: 16b5fb5706ca88a7` at the top of your response, and end with `VERDICT: PASS` or `VERDICT: NEEDS_WORK`.

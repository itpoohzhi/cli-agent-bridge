# Coder iteration 2 — summary

**F-001 (BLOCKER-SAFETY) fixed** in `bridges/agy-bridge/server.py`:
- `_classify_part`: keys matched case-insensitively (`_lower_keys`), so `InlineData`/`Image_Url`/`Input_Audio` classify as image/media; `text` that is not a `str` (dict/list) is `unknown`, never `text`.
- `_part_text` helper replaces `part["text"]` in `_flatten_content_stripped` / `_universal_render_messages` (no KeyError, never `str(...)` of a structure).
- `_media_part_counts`: every non-`text` part (media + unknown, incl. dict-content) counts into `other_media`, so `if image_parts or other_media` fires, `image_fallback stage=collect reason=unsupported_media` is logged, `force_cold` set.
- `do_POST`: with universal policy `stripped_full_prompt` is always computed via `_messages_to_stripped_prompt`.

**MINOR-2**: `media-degradation-reserve` added to `_LOG_EVENT_NAMES`.

**Tests**: `test_uf07` extended (after the frozen 249,933-byte prefix) with real HTTP + SSE subtests, cases A..E (`PAYLOAD_SECRET_12345`): 200, secret absent from prompt/argv/log, `[media omitted]` present, exactly one `collect/unsupported_media` event, no `--add-dir`.

**Verification** (all exit 0): VER-001, 002, 003 (58 tests OK), 006, 007, 008, 009; VER-004 (typecheck delta) also 0 after replacing `setdefault` (unused-result warning).
Plan (`--phase after`) and handoff (`coder`) validated; `fingerprints/coder-after.json` rewritten.

Not verified / unchanged: VER-005 (full pytest, red on BASE for unrelated collection errors), VER-010 (live deploy) — out of Coder scope.
Note: crash-guard printed "Log limit exceeded" (macOS could not write 2 crash reports) during VER-003; the run itself exited 0.

You are the Stage 4 Coder (`claude-sonnet-5-5` `high`, Iteration 2) for task `agy-universal-image-fallback-20261029` in repository `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback`.

## Context: Code Council R1 Findings to Fix
All 3 Code Council judges reviewed your iteration 1 diff and identified one concrete blocker (`F-001` / `BLOCKER-SAFETY`) and one minor log-masking item (`MINOR-2`):

1. **`F-001` (`BLOCKER-SAFETY` — Unknown-only structured content bypasses `do_POST` normalization):**
   - Look at `_classify_part(part)` (`bridges/agy-bridge/server.py:870`), `_media_part_counts(messages)` (`server.py:909`), and `Handler.do_POST` (`server.py:4090-4132`):
     - Currently, `_media_part_counts` only counts `"image"` and `"media"`, ignoring `"unknown"`!
     - As a result, when a request in universal mode contains ONLY unknown structured parts (e.g. `content={"type": "input_video", "data": "SECRET"}` or `content={"foo": {"bar": "SECRET"}}` or list part `{"type": "input_video", "text": "SECRET"}` or `{"type": "text", "text": {"inlineData": "SECRET"}}` or case-variant `{"InlineData": "SECRET"}`) and 0 recognized `image`/`media` parts, `if image_parts or other_media:` at `server.py:4092` is `False`!
     - Then `render_messages` stays the un-normalized `messages`, `stripped_full_prompt` is not computed, `image_fallback stage=collect reason=unsupported_media` is not logged, `force_cold` is not set, and legacy `_flatten_content` executes `str(content)` or `str(item["text"])`, leaking the raw structured payload into the CLI prompt!
   - **Exact Fix Required in `bridges/agy-bridge/server.py`:**
     - In `_classify_part(part)`:
       - Check payload keys case-insensitively (or normalize keys `k_lower = {str(k).lower() for k in part.keys()}` alongside exact keys) so `"InlineData"` / `"FileData"` / `"Input_Audio"` / `"Image_Url"` / `"Input_Image"` are classified properly as `"image"` or `"media"`.
       - When `part_type == "text"` (or `part_type == ""` and `"text" in part`), ONLY classify as `"text"` if `isinstance(part.get("text"), str)` or `part.get("text") is None`! If `part.get("text")` is a `dict`, `list`, or other non-string structured object (like `{"type": "text", "text": {"inlineData": ...}}`), classify it as `"unknown"` (or `"media"`), NEVER as `"text"`! And in `_flatten_content_stripped` / `_universal_render_messages`, ensure such a part is replaced with `"[media omitted]"` and never serialized via `str(...)`!
     - In `_media_part_counts(messages)`:
       - Count `kind in ("media", "unknown")` into `other_media` (the second element of the returned tuple `(img_count, media_count)`), AND if `isinstance(content, dict)` where `_classify_part(content) != "text"`, count it into `img_count` (if `"image"`) or `other_media` (if `"media"` or `"unknown"`)!
       - That way, in `Handler.do_POST`, ANY message containing `unknown` structured parts or non-text `dict` content has `other_media > 0`, which triggers `if image_parts or other_media:`, builds `stripped_full_prompt = _messages_to_stripped_prompt(messages)`, runs `_universal_render_messages`, logs `image_fallback stage=collect reason=unsupported_media` when `images == []`, and sets `force_cold = True`!
       - Furthermore, in `Handler.do_POST`, when `universal_fallback` is `True`, always compute `stripped_full_prompt = _messages_to_stripped_prompt(messages)` so `ctx["stripped_full_prompt"]` is always normalized through `_flatten_content_stripped`.
2. **`MINOR-2` (`_LOG_EVENT_NAMES` masking of `media-degradation-reserve`):**
   - Add `"media-degradation-reserve"` to `_LOG_EVENT_NAMES` in `bridges/agy-bridge/server.py` so `_mask_secrets` does not replace `"media-degradation-reserve"` with `"***"`.
3. **Add HTTP Regression Subtests to `test_uf07` in `tests/test_agy_bridge_resilience.py`:**
   - Remember: preserve the first 249,933 bytes (6008 lines) of `tests/test_agy_bridge_resilience.py` untouched!
   - In `UniversalImageFallbackTests.test_uf07_...` (after line 6008), add real HTTP `bridge.post` and SSE `_sse_post` regression checks for unknown-only structured content without any accompanying image:
     - Case A: `content={"type": "input_video", "data": "PAYLOAD_SECRET_12345"}`
     - Case B: `content=[{"type": "input_video", "text": "PAYLOAD_SECRET_12345"}]`
     - Case C: `content=[{"type": "text", "text": {"inlineData": "PAYLOAD_SECRET_12345"}}]`
     - Case D: `content={"InlineData": "PAYLOAD_SECRET_12345"}`
     - Case E: `content={"foo": {"bar": "PAYLOAD_SECRET_12345"}}`
     Verify for all A..E over HTTP that: status is `200`, `"PAYLOAD_SECRET_12345"` is NOT in the captured CLI prompt, `"[media omitted]"` IS in the captured CLI prompt, and `image_fallback stage=collect reason=unsupported_media` is logged!
4. **Re-validate Role Plan & Handoff:**
   - Run `VER-001`, `VER-002`, `VER-003`, `VER-006`, `VER-007`, `VER-008`, `VER-009` and verify all exit `0`.
   - Update `fingerprints/coder-after.json`, `plans/coder-01.json` (`validate_role_plan.py --phase after`), and `handoffs/coder-01.json` (`validate_handoff.py coder`), and write a short summary to `.ai-team/runs/agy-universal-image-fallback-20261029/coder-iter2/summary.md`.

# Code Council R1 Ledger — `agy-universal-image-fallback-20261029`

- **Judge 1 (`muse-wonder-full-1.0`, `Meta`):** `NEEDS_WORK` — `F-001` (`BLOCKER-SAFETY`): `_media_part_counts()` ignored `unknown` parts from `_classify_part()`, allowing unknown-only structured content (`{"type": "input_video", ...}`, `{"type": "text", "text": {"inlineData": ...}}`, `{"InlineData": ...}`) to bypass `do_POST` normalization; `MINOR`: `VER-005` collection errors on BASE.
- **Judge 2 (`gemini-4-argon-high`, `Google`):** `ACCEPT` — `0` blockers; `MAJOR-1`: same `_media_part_counts()` / `do_POST` observation on `unknown` dict blocks; `MINOR-2`: `media-degradation-reserve` masked by `_SECRET` unless added to `_LOG_EVENT_NAMES`.
- **Judge 3 (`gpt-6.1-sol-high`, `OpenAI`):** `NEEDS_WORK` — `F-001` (`BLOCKER-SAFETY`): same unknown structured content bypass in `do_POST`; `F-002` (`BLOCKER-SAFETY`): `VER-005` full repository pytest exited `2` on collection without `PASS_WITH_PREEXISTING` §8 multiset comparison.

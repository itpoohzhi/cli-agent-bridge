# Code Council Round 2 (D1) — Debate Ledger (`agy-universal-image-fallback-20261029`)

- **Artifact Reviewed:** `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/teamlead/package.md`
- **Artifact SHA256:** `baf9379d84ccc76fcd63830199dcac954170db64dedb95ec3c6fc24a8938eb41`
- **Round 2 Proof (`panel-proof.json`):** `PASS` (`verify_panel_proof.py` `exit=0`), `verdict_counts={"ACCEPT": 1, "NEEDS_WORK": 2}`
  - **Seat 1 (`gemini-4-argon-high`, `Google`, `agy`):** `VERDICT: ACCEPT`
  - **Seat 2 (`gpt-6.1-sol-high`, `OpenAI`, `codex`):** `VERDICT: NEEDS_WORK`
  - **Seat 3 (`muse-wonder-full-1.0`, `Meta`, `muse`):** `VERDICT: NEEDS_WORK`

## 1. Closed Findings Confirmed in Round 2 (3/3 Consensus)
- **`MINOR-2` (`media-degradation-reserve` log token masking):** CLOSED (3/3).
- **`F-001` Cases A–E (unknown-only / case-variant / non-str `text` structured content):** CLOSED (3/3).
- **`VER-010` (`DEFERRED_L3` pre-Council status):** Confirmed non-blocking at Council stage (3/3); mandatory before MR/completion.

## 2. Open Blockers Remaining After Round 2 (D1) & Exact Closure Criteria for Iteration 3 / Round 3 (D2)

### `F-001` (`BLOCKER-SAFETY` — Residual bypass when `msg["content"]` is a `dict` classified as `"text"`)
- **Finding (Seat 2 & Seat 3):**
  When `universal=True` and `_media_part_counts(messages) == (0, 0)`, `do_POST` (`bridges/agy-bridge/server.py:4116,4154,4201`) leaves `render_messages = messages` (raw input) instead of `_universal_render_messages(messages)`, so `full_prompt = _messages_to_prompt(render_messages, images)` calls legacy `_flatten_content`, which executes `return str(content)` on any `dict`-content (`{"role": "user", "content": {"type": "text", "text": "hello", "payload": {"data": "PAYLOAD_SECRET_12345"}}}`). That serializes the entire dictionary (including unenumerated `data`/`payload`/`source`/`attachment` keys) into the CLI prompt. Additionally, `{"type": "text", "text": None, "payload": S}` was classified as `"text"` because `_classify_part` allowed `text is None`.
- **Closure Criteria:**
  1. In `do_POST`, when `universal=True`, unconditionally set `render_messages = _universal_render_messages(messages)` at the start of `if universal:` (not only when `images` is non-empty), and when `force_cold or (universal and not images)`, use `stripped_full_prompt`.
  2. In `_classify_part`, require `isinstance(text, str)` (never `text is None`) and if `text == ""` with extra keys outside `{"type", "text"}`, classify as `"unknown"` so `{"type": "text", "text": None, "payload": S}` and `{"type": "text", "text": "", "payload": S}` count as `other_media=1` and render `[media omitted]`.
  3. Add unit and HTTP JSON/SSE regression subtests in `test_uf07_media_normalization_is_complete` covering `F_dict_text_extra_data`, `G_dict_notype_text_extra`, `H_dict_text_none_payload`, `K_dict_input_text_extra`, and `I_dict_text_only`, verifying the actual CLI prompt passed to `agy` contains `"hello"` (or `"[media omitted]"` for `H`), never contains `PAYLOAD_SECRET`, and never contains `"{'type'"`.

### `F-002` (`BLOCKER-SAFETY` — `VER-005` Full Repository Suite Clean-Room Evidence)
- **Finding (Seat 2 & Seat 3):**
  1. Using `--ignore=bridges/opencode-zen-bridge/tests` in `PYTEST_ADDOPTS` excluded 18 test files (`529` tests) from `bridges/opencode-zen-bridge/tests/`.
  2. The 3 pre-existing failure tuples listed in `execution-evidence.md` had stale/paraphrased test IDs that did not match the actual pytest node IDs in `tests/test_b_guard.py` and `tests/test_muse_bridge_killpg.py`, and paired raw BASE/CANDIDATE logs + `teamlead/environment-manifest.json` + exact executed test-ID multiset comparison were not attached in `teamlead/`.
- **Closure Criteria:**
  1. Execute the frozen `VER-005` command (`pytest -q`) in clean-room L2 across the **entire** repository (`tests/` + `bridges/opencode-zen-bridge/tests/`, `1,564` candidate tests vs `1,552` base tests, `0` ignored directories, `0` collection errors) on both clean `BASE` (`012da99905ec27a6133afb4f3e768ff9b4426a8f`) and `CANDIDATE`, saving raw logs `teamlead/logs/ver-005-base.log` and `teamlead/logs/ver-005-candidate.log`, exact test-ID lists, and `teamlead/environment-manifest.json`.
  2. Record the exact, verified pytest node IDs of any pre-existing failures on `BASE` and `CANDIDATE` from the raw logs and verify multiset equality `CANDIDATE_FAILURES == BASE_FAILURES` and `CANDIDATE_EXECUTED_IDS >= BASE_EXECUTED_IDS` per `verification-integrity.md` §8.

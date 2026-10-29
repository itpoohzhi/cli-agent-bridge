PANEL-NONCE: 1372fee65e6ea4b1
ARTIFACT-SHA256: f6c7a59500b8ece3b756c115b82eea5fd6de42de2825a7ed93b34345b4c49e6b

# ARCH_PANEL R1 — `agy-universal-image-fallback-20261029`

I read the packet, the verification surface, and `server.py` at 3119–3337 (`_run_once`), 3600–3728 (`do_POST`), 1105–1256 and 1520–1560 (session/CID helpers), and 676–716 (flag readers). I did not run the VER commands. I ran three read-only checks (see "Checked and confirmed"); the packet's own VER commands were not executed.

No finding below reaches BLOCKER level. The three downgrade points, their ordering, and the resource ownership are consistent with the real code.

## Findings

**MAJOR-1 — `stripped_full_prompt` is computed for every request, including strict and text-only ones.**
- AD-002 `ctx_contract` says: "Always store `ctx["stripped_full_prompt"]`".
- AD-003 `point1_collect` says: "Detect structured media… Precompute", which is conditional. The two decisions disagree.
- `do_POST` (`server.py:3661`) is the hot path for every request. "Always" doubles prompt rendering and memory, with bodies up to 32 MiB.
- It also adds a new exception surface to strict and pure-text requests, e.g. the normalizer raising on odd message shapes. A request that returns 200 today could become a 500.
- That contradicts CD-001/AC-07 ("flag absent/false exactly old behavior; text-only has the old prompt/protocol"). It also feeds the unproven memory closure in `resource_envelope`.
- Required: compute it only when `universal=True` and media is detected (or lazily on first downgrade), and never for `universal=False`. Make AD-002 and AD-003 say the same thing. Add an assertion to uf09/uf10 that strict and text-only requests make no normalizer call.

**MAJOR-2 — The runtime guard ignores native agy side effects (`tool_events`).**
- `delivered` (INV-08, AD-003 `point3_runtime.delivery`) counts only `text`, `tool_calls` and stream reasoning.
- `out["tool_events"]` is already tracked (`server.py:2955,3067`) and counts native tool executions.
- For `timeout`, `idle_timeout` and `first_token_timeout` (execution ceiling 1800 s), attempt 1 may have run native tools (writes, shell) with no text delivered. The retry then re-runs the whole task from scratch with a stripped prompt, which can duplicate side effects. Worst-case latency also doubles to roughly 2×1800 s plus the pause.
- RISK-001 only says "no exactly-once claim" and defers to a live read-only oracle. ASM-001 is classed as "continuable".
- Required before Coder: record an explicit owner risk acceptance, or narrow the guard so that `tool_events>0` combined with a timeout-class state does not replay.
- At minimum, log `tool_events` in the `image_fallback` runtime event and add an assertion for it in uf05/uf08.

**MINOR-1 — Env token contract for the new flag differs from the existing flag.**
- `AGY_IMAGE_INPUT_ENABLED` accepts `1/true/yes/on` (`server.py:704`).
- The new flag maps `on` to False ("including on/off for NEW flag").
- An operator setting `AGY_IMAGE_FALLBACK_ENABLED=on` silently gets strict behavior. That fails closed, but it is a footgun.
- Align the token set with the input flag, or document the difference and log a warning once for unrecognized non-empty values.

**MINOR-2 — Effectiveness for models that fail with `state=done`.**
- The owner guard excludes `done` (RISK-003/uf08). A text-only model that exits `done` with rc≠0 or empty text still gets `502 proxy_error` (`_error_body`, `server.py:3406–3414`).
- The packet gives no evidence that the historical agy 1.3.1 failure mode is `agy_error`, a timeout, or `pump_error`.
- If it is `done` with empty text, REQ-03 is not met for the motivating "previously text-only model" case. VER-010 (`previously_text_only_model`) catches this late, in live acceptance.
- Add the observed failure state to the design record now.

**MINOR-3 — Unbounded request-scoped reserve (A=2N) with no global brake.**
- Under a backend outage with all-image traffic, every request retries, and no breaker or global counter limits it.
- RISK-008 and `production_acceptance_blockers` flag this and block production acceptance on measurement.
- The design is acceptable for the owner's explicit override. Consider an observable counter, e.g. a `reserve_used` field, so the amplification is visible.

**MINOR-4 — Test isolation.**
- `_load_bridge` does not isolate the new env variable (F-201). VER-003 pops it, but a developer or CI shell exporting `AGY_IMAGE_FALLBACK_ENABLED=1` fails the legacy strict tests.
- Cheap to add: a guard in the new test class, or a note in the Coder brief that new fixtures must restore the env.

## Checked and confirmed
- Baseline test file: 249933 bytes, sha256 `f318d605…eeff5`, HEAD `012da99`, matches the packet.
- The five frozen Stage 1 file hashes in VER-008 match the current files.
- The only third-party import in `server.py` is `core`, which VER-009 allows.
- `_reset_sqlite_guards_for_tests` already resets the old flag cache (`server.py:1230–1243`), so adding the new cache reset there is consistent.
- Guard placement matches the real code:
  - After `run.close()` and the `done` break, before the hot early `continue` (3280) and the transient branch (3299).
  - `_session_invalidate` is a CAS on `(sess_key, cid)` (`server.py:1129`), and `_cid_release(cid, turn_id)` is owner-checked.
  - `do_POST`'s outer `finally` releases CIDs idempotently, so a double release is safe.
- Slot release stays in the `_run_once` `finally`. Downgrade keeps the slot and releases it once.
- The design never calls `_image_gate`/proof for universal requests, so the strict path and `fleet.json` stay untouched.

VERDICT: PASS
PANEL-NONCE: 16bcfbb52b32ca68
ARTIFACT-SHA256: 45905654733fd19ee8911b86033bd395b14c6f3ad5066803c58d0cb4b7f2f0ed

# Review (Визионер, seat k=2, `muse-bridge-heal-20261014`, S2)

artifact_sha256: 45905654733fd19ee8911b86033bd395b14c6f3ad5066803c58d0cb4b7f2f0ed

**What I checked**
- The SHA-256 of `code-review-package.md` matches the one in the brief. `server.py` (`7d02f13c…`) and the test file (`5ef6d3cd…`) match the hashes recorded in the package.
- I read the package, `arch-spec.md`, the current `server.py` (Handler, `ServeRun.execute`, `_serve_json`), the full test file and the verifier receipt.
- I re-ran `python3 -B -m unittest tests.test_muse_bridge_killpg` myself: 33 tests, OK. I did not re-run ruff or basedpyright. For those I rely on the verifier receipt.

**Criterion 1: AD-001..AD-005 and F-001**
- **AD-001:**
  - All three early exits log through `_format_err_log` before `_send`: spawn/launcher failure, failed terminal or non-zero rc, and `empty_output`.
  - Both `error.detail` and the log field are redacted before the 300/500 cut.
  - A `None` error becomes `""`. `ErrorLoggingTest` covers this for the JSON and SSE paths.
- **AD-002:**
  - A separate `turn_diag_lines` list is written only by the main thread, so the stderr collector cannot push it out.
  - The per-field limits (64/160/120/160) and the 300 budget work as specified.
  - A redaction marker is never cut in half. The priority block comes before stderr, and the total stays within 500.
  - The `completed` path and the other result contracts are unchanged.
- **AD-003:**
  - The sealing is correct.
  - The phase check and the write happen under the same `_wlock` hold, so a late keepalive tick cannot write after FINALIZING.
  - `[DONE]` sets CLOSED inside a `finally`, so a failed write cannot be followed by another one.
  - `join(timeout=2)` is only cleanup, and nothing joins while holding the lock.
  - Class-level defaults make `Handler.__new__` safe. The renamed `_ka_stop` has no remaining references.
  - `test_s2_inflight_flush_precedes_finalization`, `test_defaults_and_s3_seal…` and `test_done_write_failure_closes_phase` exercise the real race, not just the happy path.
- **AD-004:** The argv flags match the spec: `--yolo` is kept, and `approval/request` still raises `ServeUnavailable` and falls back to exec. Tests check argv and that no `approval/decide` is sent.
- **AD-005:** `muse-wonder-1.0` and `muse-wonder-full-1.0` are added. Tests cover `ALLOWED_MODELS` and both GET endpoints.
- **F-001:** JSON `{"token":…}`, quoted multi-word values, `Bearer`, `Authorization`, `sk-…`, the bare `MUSE_BRIDGE_KEY`, and sensitive keys inside nested `quota` are all masked before the cuts. Tests cover boundary prefixes of 285 and 485 characters.

**Criterion 2: concurrency, secrets, compatibility**
- I found no stream-sealing race, deadlock or write after `[DONE]`. The lock is taken once per operation and is not re-entrant.
- Wire compatibility holds. The only visible changes are the intended ones: the keepalive frame, `detail` being `""` instead of `"None"` for a missing error, and the added models.
- The `err_thread.join(5)` before the stderr snapshot was already in the `finally` block before this change. It was only moved, so I see no new delay.

**Advisory observations (not blocking; no secret leak, no wire or lifecycle effect)**
1. **Short messages garble diagnostics.**
   - `_serve_json` replaces each `messages[*].content` in the error text with `[REDACTED]`.
   - Short messages such as "hi", "ok" or "a" then damage every occurrence in the diagnostic. I confirmed this: replacing "e" turns "network connection could not be opened" into "n[REDACTED]twork conn[REDACTED]ction…".
   - Nothing leaks, but the diagnostics this change exists to surface lose value. Suggested follow-up: replace a reflected message only above a minimum length (for example 16–20 characters). The full-prompt replacement can stay unconditional.
2. **Escaped quotes in a quoted secret.**
   - With `password="a \"b c"`, the regex stops at the first `\"`.
   - I confirmed that `_redact_secrets` leaves `b c"` visible.
   - This is a narrow tail case. Suggested follow-up: use `"(?:[^"\\]|\\.)*"` for the quoted branch, and likewise for single quotes.
3. **Over-redaction.** Keys such as `prompt_token=5` or `client_secret=` are also masked. This is safe.
4. **The live checks are still pending.** `VER-005` and `AC-07`/`AC-11` (delivery to the live copy, `pi-ai` idle reset) are not verified. The package says so, and the docstring marks the idle-reset effect as needing a live check. This is correct, but "done" must not be claimed until the live DSH run is done.

**Criterion 3: test quality**
- There are 33 tests: 18 existing and 15 new. The new ones check real bytes over HTTP and the real race, not only mocks. The secret canaries cover both sinks, JSON and SSE, plus the log. The 300/500 boundary cases and the malformed-payload cases are in.
- Red-before-green evidence is recorded in `coder.json`.
- Gap: there is no test for observations 1 and 2 above.

VERDICT: ACCEPT

```json
{
  "artifact_sha256": "45905654733fd19ee8911b86033bd395b14c6f3ad5066803c58d0cb4b7f2f0ed",
  "verdict": "ACCEPT",
  "seat_k": 2,
  "findings": []
}
```

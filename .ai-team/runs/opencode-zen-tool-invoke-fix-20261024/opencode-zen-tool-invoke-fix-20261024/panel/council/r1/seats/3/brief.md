# Code Council Judge Brief — Seat k=3 (Визионер / Visionary)

- **Mode:** `code` (`teamlead-gate` Code Council, Round 1)
- **Role / Lens:** Seat `k=3` — **Визионер (Visionary)**: architectural alignment with `architecture-packet.json` (`AD-001`..`AD-004`, `BND-001`, `BND-002`, `CD-001`), cross-bridge parity across `opencode-zen-bridge`, `core/tool_emulation.py`, and `muse-bridge`, and long-term resilience against LLM tool-call formatting drift.
- **Task / Run ID:** `OPENCODE-ZEN-TOOL-INVOKE-FIX` / `opencode-zen-tool-invoke-fix-20261024`
- **Artifact under review:** `/Users/aazhiry1/tmp/cli-agent-bridge/opencode-zen-tool-invoke-fix/.ai-team/runs/opencode-zen-tool-invoke-fix-20261024/teamlead/package.md`
- **Architecture Packet:** `/Users/aazhiry1/tmp/cli-agent-bridge/opencode-zen-tool-invoke-fix/.ai-team/runs/opencode-zen-tool-invoke-fix-20261024/architecture/architecture-packet.json`
- **Coder Handoff:** `/Users/aazhiry1/tmp/cli-agent-bridge/opencode-zen-tool-invoke-fix/.ai-team/runs/opencode-zen-tool-invoke-fix-20261024/coder.json`

## Mandatory Output Format Rules (PoL v1.1 Gate)
1. Read `/Users/aazhiry1/tmp/cli-agent-bridge/opencode-zen-tool-invoke-fix/.ai-team/runs/opencode-zen-tool-invoke-fix-20261024/teamlead/package.md` (which contains the full unified diffs and L1/L2 test evidence); do NOT modify any files or run slow shell commands.
2. Your response MUST begin with the exact two lines `PANEL-NONCE: <hex16>` and `ARTIFACT-SHA256: <hex64>` echoed from the bottom of this brief.
3. Provide a substantive technical code review of at least 400 characters evaluating the diffs in `bridges/opencode-zen-bridge/server.py`, `core/tool_emulation.py`, `bridges/muse-bridge/server.py`, and the tests (`test_lenient_tool_call.py`, `test_step_interruption.py`, `tests/test_tool_parser.py`).
4. Your response MUST end with the exact final line (no trailing period, no extra words on that line):
   `VERDICT: ACCEPT` (or `VERDICT: NEEDS WORK` / `VERDICT: RED FLAG` if there is a blocking defect).

## Summary of Candidate Implementation (`teamlead/package.md`)
- **`AD-001` (`REQ-001`) — Trailing-Brace Recovery (`1..16` extra `}`):**
  - `_recover_trailing_braces` in `bridges/opencode-zen-bridge/server.py`, `core/tool_emulation.py`, and `bridges/muse-bridge/server.py` uses `raw_decode` after `json.loads` fails, catches `(ValueError, RecursionError)`, and accepts the decoded value iff `isinstance(obj, dict)` and the remaining tail consists strictly of whitespace and `1 <= extra_braces <= 16` closing braces `}`.
  - Includes `quiet: bool = False` threaded through `_loads_lenient` and `_parse_tool_call_block(s)` so history replay/sanitization does not spam `tool_call_recovered` logs.
- **`AD-002` (`REQ-002`) — Sink-Level Broken Block Stripping & Fail-Closed Cap:**
  - `_strip_broken_tool_blocks(text)` strips unparseable raw `<tool_call>`/`<tool_invoke>` blocks outside markdown code at 3 sinks (`Handler._stream_sse`, `Handler._serve_json`, `_incomplete_tool_step_prompt`) and emits `_BROKEN_BLOCK_NOTICE` when nothing else is visible.
  - Per `ARCH_PANEL` Skeptic (`k=1`), when a 17th candidate outside markdown code is reached (`scanned >= _STRIP_SCAN_MAX_TAGS = 16`), `_strip_broken_tool_blocks` fails closed by dropping `text[start:]` and logging `tool_strip_cap_hit max=16 dropping tail`, guaranteeing 0 leaked broken tags even on pathological input while bounding CPU to $O(16 \cdot n)$.
- **`AD-003` (`REQ-003`) — History Sanitization & OpenAI `"function"` Envelope:**
  - `_sanitize_assistant_text` calls `_strip_broken_tool_blocks(text)[0]` (which uses `quiet=True`), stripping closed malformed blocks while keeping valid closed single/multi-call batches byte-identical.
  - `_parse_tool_call_block` in all 3 modules unwraps `obj = obj["function"]` iff `"name" not in obj and isinstance(obj.get("function"), dict)`.
- **`AD-004` (`REQ-004`) — Verification (`VER-001`..`VER-004` & Clean-Room `L2`):**
  - `VER-001`: 52 tests OK; `VER-002`: 378 tests (360 + 18 new, 0 errors); `VER-003`: 12 tests OK; `VER-004`: `0.42 / 0.148 / 1.949` ms (< 5 ms); Clean-room `L2` red/green sensitivity check passed.

ARTIFACT-SHA256: d736aad93aceb28a508c81975ab089eb3920aff6f4711a52bcbdcc0d63b19e7e


---
PANEL-NONCE: bbe2cd25194ea9b3
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: bbe2cd25194ea9b3» и «ARTIFACT-SHA256: d736aad93aceb28a508c81975ab089eb3920aff6f4711a52bcbdcc0d63b19e7e».

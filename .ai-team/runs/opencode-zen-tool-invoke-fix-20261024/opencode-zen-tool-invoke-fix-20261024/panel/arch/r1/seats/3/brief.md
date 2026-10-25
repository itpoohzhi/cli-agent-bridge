# Architecture Council Judge Brief — Seat k=3 (Визионер / Visionary)

- **Mode:** `architecture` (`ARCH_PANEL`, Round 1)
- **Role / Lens:** Seat `k=3` — **Визионер (Visionary)**: architectural coherence, contract evolution (`CD-001`), component boundaries (`BND-001`, `BND-002`), long-term resilience against LLM tool-call formatting drift, and cross-bridge consistency (`core/tool_emulation.py`, `opencode-zen-bridge`, `muse-bridge`).
- **Task / Run ID:** `OPENCODE-ZEN-TOOL-INVOKE-FIX` / `opencode-zen-tool-invoke-fix-20261024`
- **Artifact under review:** `/Users/aazhiry1/tmp/cli-agent-bridge/opencode-zen-tool-invoke-fix/.ai-team/runs/opencode-zen-tool-invoke-fix-20261024/architecture/architecture-packet.json`
- **Human-readable companion spec:** `/Users/aazhiry1/tmp/cli-agent-bridge/opencode-zen-tool-invoke-fix/.ai-team/runs/opencode-zen-tool-invoke-fix-20261024/architecture/arch-spec.md`
- **Analyst handoff:** `/Users/aazhiry1/tmp/cli-agent-bridge/opencode-zen-tool-invoke-fix/analysis/opencode-zen-tool-invoke-fix/handoff-architect.md`

## Mandatory Output Format Rules (PoL v1.1 Gate)
1. Do NOT run slow shell commands or modify any files; evaluate the embedded architecture packet and spec directly (or read only the referenced files if needed).
2. Your response MUST begin with the exact two lines `PANEL-NONCE: <hex16>` and `ARTIFACT-SHA256: <hex64>` echoed from the bottom of this brief.
3. Provide a substantive technical architectural critique of at least 400 characters (evaluating `AD-001`..`AD-004`, `REQ-001`..`REQ-004`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`, and `VER-001`..`VER-004`).
4. Your response MUST end with the exact final line (no trailing period, no extra words on that line):
   `VERDICT: PASS` (or `VERDICT: NEEDS WORK` / `VERDICT: RED FLAG` if there is a blocking defect).

## Summary of Architecture Under Review (`arch-spec.md` & `architecture-packet.json`)
- **Problem:** In `opencode-zen-bridge` (`127.0.0.1:9883`), `GLM-5.3-Flash` emitted `<tool_invoke>{"id": "call_b2c1e7d4a71a44e09ddd", "name": "bash", "arguments": {"command": "...", "description": "..."}}}</tool_invoke>` (3 closing braces `}}}`). `_loads_lenient` failed with `JSONDecodeError: Extra data`, causing `ToolCallParser` to emit the raw `<tool_invoke>` tag to `on_content`, leaking it into the SSE stream and polluting `incomplete_tool_step re-prompt 2/2`.
- **AD-001 (Trailing-brace recovery at single decode choke):** In `opencode-zen-bridge/server.py:_loads_lenient`, after `json.loads(text)` and `json.loads(text, strict=False)` fail, call `_recover_trailing_braces(text, strict=False)` which uses `json.JSONDecoder(strict=False).raw_decode(text.lstrip())` and accepts the result iff `isinstance(obj, dict)` and `tail = body[end:]` contains `}` and consists exclusively of whitespace and `}` (`not tail.strip(" \t\r\n}")`). Same helper `_recover_trailing_braces` (with strict `JSONDecoder()`) added via `_loads_tolerant` in `core/tool_emulation.py` and `bridges/muse-bridge/server.py`. Negative controls (`{broken`, under-closed, `, "x": 1}`) still raise `ValueError` and return `None`.
- **AD-002 (Sink-level broken block stripping):** Pure helper `_strip_broken_tool_blocks(text) -> tuple[str, int]` (capped at `_STRIP_SCAN_MAX_TAGS = 16` candidates for `H-CPU/v1` $O(n)$ bound) strips unparseable raw `<tool_call>`/`<tool_invoke>` blocks outside markdown code at 3 sinks: (1) `ToolCallParser` content callback in `Handler._stream_sse`, (2) `Handler._serve_json` after `_split_tool_calls`, and (3) `_incomplete_tool_step_prompt`. `_split_tool_calls` itself is untouched so `test_negative_control_garbage_still_text_and_logged` and `test_unparsed_block_returned_as_text` stay 100% green. `_is_incomplete_tool_step` still inspects raw `attempt_texts` so retry triggers and caps (`MAX_TOTAL_SPAWNS = 3`) are preserved.
- **AD-003 (History hygiene & OpenAI function wrapper):** `_sanitize_assistant_text` calls `_strip_broken_tool_blocks(text)[0]` after `_strip_unclosed_tool_calls(text)`, stripping closed malformed blocks while keeping valid closed single/multi-call batches byte-identical (`test_closed_batch_without_intermediate_close_kept`, `test_sanitize_closed_alt_batch_kept`). `_parse_tool_call_block` in all 3 modules unwraps `obj = obj["function"]` when `"name" not in obj and isinstance(obj.get("function"), dict)`. `_render_tool_call` is untouched (`"id"` preserved).
- **AD-004 (Cross-bridge parity & live re-baseline/patch rollout):** Keep 3 standalone stdlib parsers with parity enforced in `tests/test_tool_parser.py::TestCrossBridgeParserContract`. Re-baseline untracked `bridges/opencode-zen-bridge/` on live `~/.dsh/bridges/opencode-zen-bridge/` (`sha256=5f6b7cb0...`, 3885 lines) before editing, and deploy via sha-guarded copy/patch + backup in `~/work/backups/` + `launchctl kickstart`.

ARTIFACT-SHA256: 42c8a5c77d48ae612b8bda503bcb31577b22222fad54767715975e1c0c3e85b4


---
PANEL-NONCE: 3390da5eb55a800c
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 3390da5eb55a800c» и «ARTIFACT-SHA256: 42c8a5c77d48ae612b8bda503bcb31577b22222fad54767715975e1c0c3e85b4».

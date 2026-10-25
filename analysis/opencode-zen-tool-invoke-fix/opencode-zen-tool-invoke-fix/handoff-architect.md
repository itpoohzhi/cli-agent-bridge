# Handoff to Architect — opencode-zen-tool-invoke-fix

## 1. Context & Problem Summary

In `opencode-zen-bridge` (`127.0.0.1:9883`), `GLM-5.3-Flash (Zen) Max` emitted a `<tool_invoke>` block during `incomplete_tool_step re-prompt 1/2` containing a multi-line Python heredoc inside `bash` `arguments` and three closing braces `}}}` at the end (`[F-01]`, `[F-02]`). Because `_loads_lenient` (`server.py:1118-1128`) and `_parse_tool_call_blocks` (`server.py:1316-1350`) did not tolerate trailing extra closing braces `}` (`[F-03]`, `[F-04]`), `_parse_tool_call_blocks` returned `None`. `ToolCallParser._process` (`server.py:1557-1567`) emitted the raw `<tool_invoke>...</tool_invoke>` block to `on_content` (`[F-06]`), and `Handler._stream_sse` (`server.py:2765-2769`) prematurely flushed `held` to `emit_content` and `collected_texts` before `re-prompt 2/2` (`[F-08]`, `[F-09]`).

## 2. Requirements (`REQ-001` .. `REQ-004`)

- **REQ-001 — Trailing Brace (`}}}`) Recovery in Lenient JSON & Tool Call Block Parsers:**
  - In `bridges/opencode-zen-bridge/server.py` (`_loads_lenient` and `_parse_tool_call_blocks`), `core/tool_emulation.py` (`_parse_tool_call_block` / `_normalize_arguments`), and `bridges/muse-bridge/server.py` (`_parse_tool_call_block` / `_normalize_arguments`), tolerate trailing extra closing braces `}` (e.g. `}}}` or `}}}}` with optional whitespace between/after braces) after a valid JSON object (`dict`) inside `<tool_call>` / `<tool_invoke>` blocks (`[F-03]`, `[F-04]`, `[F-05]`).
  - Specifically, if `json.loads` raises `JSONDecodeError` (after control-character escaping where applicable), attempt `json.JSONDecoder(strict=False).raw_decode` from the first non-whitespace character: if the decoded value is a `dict` and the remaining tail consists strictly of whitespace and one or more `}` characters (`re.fullmatch(r"[\s}]+", tail)`), accept the decoded `dict` (and in `_parse_tool_call_blocks` multi-object sequence parsing, skip whitespace + stray `}` between/after decoded `dict` objects).
  - Genuine malformed JSON (`<tool_call>{"name": "bash", "arguments": {broken</tool_call>`, `<tool_invoke>{broken</tool_invoke>`) MUST still return `None` from `_loads_lenient` / `_parse_tool_call_blocks` so `test_negative_control_garbage_still_text_and_logged` and `test_unparsed_block_returned_as_text` remain 100% intact (`[F-07]`).

- **REQ-002 — Prevent Premature `held` Flush and Raw Tag Re-Prompt Pollution in `Handler._stream_sse` & `Handler._serve_json`:**
  - In `Handler._stream_sse` (`bridges/opencode-zen-bridge/server.py:2641-2830`), do NOT flush `held` (`if holding[0]: ...`) to `emit_content` inside an attempt when `incomplete_retry` is going to trigger another attempt (`attempt + 1 <= _INCOMPLETE_STEP_MAX_RETRIES`). Instead:
    1. Keep `holding[0]` / `held` buffered until we know whether the current attempt will retry (`[F-08]`, `[F-09]`).
    2. If an `incomplete_retry` triggers while `held` is non-empty (meaning `on_content_raw` caught a raw `<tool_call>`/`<tool_invoke>` that failed to produce any `tool_calls`), strip any closed or unclosed raw `<tool_call>`/`<tool_invoke>` blocks from `held` before appending any prose prefix to `collected_texts` for `_incomplete_tool_step_prompt`, and clear `held` / reset `holding[0] = False` without emitting the broken `<tool_call>`/`<tool_invoke>` block to the client SSE stream!
    3. Only flush `held` to `emit_content` when the retry loop is terminating (`not tool_calls` and no further retry will occur), and if `held` contains an unparseable closed/unclosed `<tool_call>`/`<tool_invoke>` block after retries, strip the broken `<tool_call>`/`<tool_invoke>` tag block before `emit_content` so raw `<tool_invoke>{...}</tool_invoke>` never leaks into the assistant SSE stream.
  - Similarly, in `Handler._serve_json` (`bridges/opencode-zen-bridge/server.py:2540-2625`), when `not calls` and `content` contains a raw `<tool_call>`/`<tool_invoke>` match (`_RAW_CALL_RE.search(content)` outside markdown code), strip the broken closed/unclosed `<tool_call>`/`<tool_invoke>` block from `content` before appending to `contents` / passing to `_incomplete_tool_step_prompt` (`[F-10]`), while leaving `_split_tool_calls` itself unchanged (`[F-07]`).

- **REQ-003 — Sanitize Malformed Closed `<tool_call>`/`<tool_invoke>` Blocks in `_sanitize_assistant_text` & Support OpenAI-Style `"function"` Wrapper in `_parse_tool_call_block`:**
  - Preserve `"id"` in `_render_tool_call` (`server.py:1173-1176`) as required by `test_history_renders_tool_calls_and_results` (`[F-11]`).
  - In `_parse_tool_call_block` (`bridges/opencode-zen-bridge/server.py:1291-1313`, `core/tool_emulation.py:140-179`, `bridges/muse-bridge/server.py:276-306`), continue ignoring extra top-level keys like `"id"` and `"type"`, and if top-level `"name"` is absent but `isinstance(obj.get("function"), dict)` is present (OpenAI `tool_calls` schema echoed inside `<tool_call>`/`<tool_invoke>`), unwrap `fn = obj["function"]` to extract `name` and `arguments` (`[F-11]`).
  - In `_sanitize_assistant_text` (`bridges/opencode-zen-bridge/server.py:1395-1457`), in addition to stripping standalone closed blocks when `has_tool_calls=True` and stripping unclosed tails via `_strip_unclosed_tool_calls`, strip any closed `<tool_call>...</tool_call>` or `<tool_invoke>...</tool_invoke>` block outside fenced/inline markdown code whose inner payload is malformed (`_parse_tool_call_blocks(inner) is None`) (`[F-12]`, `[F-13]`). Valid closed multi-call batches when `has_tool_calls=False` (`_parse_tool_call_blocks(inner) is not None`) MUST remain preserved so `test_closed_batch_without_intermediate_close_kept` and `test_sanitize_closed_alt_batch_kept` continue to pass (`[F-12]`).

- **REQ-004 — Regression Test Coverage & Cross-Bridge Contract Verification:**
  - Add unit tests in `bridges/opencode-zen-bridge/tests/test_lenient_tool_call.py` and `bridges/opencode-zen-bridge/tests/test_step_interruption.py` (and `tests/test_tool_parser.py`) covering:
    1. Exact production payload `<tool_invoke>{"id": "call_b2c1e7d4a71a44e09ddd", "name": "bash", "arguments": {"command": "cat << 'EOF' > /tmp/extract_docx.py\n...\nEOF\n", "description": "Extract text..."}}}</tool_invoke>` with `}}}` and `}}}}\n` parsed into a valid `bash` tool call across `opencode-zen-bridge`, `core/tool_emulation.py`, and `muse-bridge`.
    2. OpenAI-wrapped `<tool_invoke>{"id": "call_1", "type": "function", "function": {"name": "bash", "arguments": {"command": "ls"}}}</tool_invoke>` parsed into a valid `bash` tool call.
    3. `Handler._stream_sse` and `Handler._serve_json` retry behavior when an attempt emits an unparseable `<tool_invoke>{broken</tool_invoke>`: verify that the broken `<tool_invoke>` block is NOT leaked to the client SSE stream or fed into `_incomplete_tool_step_prompt` during `re-prompt 1/2`.
    4. `_sanitize_assistant_text` stripping a malformed closed `<tool_invoke>{"name": "bash", "arguments": {broken}</tool_invoke>` block while preserving valid closed batches (`test_closed_batch_without_intermediate_close_kept` and `test_sanitize_closed_alt_batch_kept`).

## 3. High-Load Operational Envelope (`HL-ENV/v1` — 46 Fields)

| Section | Field | Value / Specification | Source |
| --- | --- | --- | --- |
| 1. Traffic & Concurrency | `peak_rps` | 5 RPS (local single-user / multi-agent developer bridge on `127.0.0.1:9883`) | `[F-14]` |
| 1. Traffic & Concurrency | `sustained_rps` | 0.5 RPS | `[F-14]` |
| 1. Traffic & Concurrency | `burst_profile` | Up to 8 concurrent parallel subagent/tool turns over 10s window | `[F-14]` |
| 1. Traffic & Concurrency | `concurrency_model` | `ThreadingHTTPServer` (`socketserver.ThreadingMixIn` + `HTTPServer`), one OS thread per active HTTP request | `[F-14]` |
| 1. Traffic & Concurrency | `read_write_ratio` | 50% read (SSE stream parsing) / 50% write (session state JSON + upstream POST) | `[F-14]` |
| 1. Traffic & Concurrency | `payload_p50_bytes` | 16384 bytes (16 KiB chat history + tool definitions) | `[F-01]` |
| 1. Traffic & Concurrency | `payload_p99_bytes` | 262144 bytes (256 KiB large multi-turn tool output history) | `[F-01]` |
| 2. Latency & SLO | `slo_p50_ms` | 1500 ms end-to-end; < 2 ms local bridge parser overhead | `[F-14]` |
| 2. Latency & SLO | `slo_p95_ms` | 15000 ms end-to-end; < 5 ms local bridge parser overhead | `[F-14]` |
| 2. Latency & SLO | `slo_p99_ms` | 60000 ms end-to-end (including up to 2 incomplete-step retries); < 10 ms parser overhead | `[F-08]` |
| 2. Latency & SLO | `hard_timeout_ms` | 300000 ms (`UPSTREAM_TIMEOUT = 300` s per upstream HTTP request) | `[F-14]` |
| 2. Latency & SLO | `availability_target` | 99.9% local daemon uptime (`KeepAlive=true` via LaunchAgent `com.user.dsh-opencode-zen-bridge`) | `[F-14]` |
| 2. Latency & SLO | `error_budget_policy` | Zero leaked raw `<tool_call>`/`<tool_invoke>` tags in assistant text responses | `[F-01]` |
| 3. Fan-Out & Dependencies | `sync_hops_max` | 1 synchronous upstream hop (`opencode.ai/zen/v1/chat/completions`) per attempt | `[F-14]` |
| 3. Fan-Out & Dependencies | `fanout_per_request_max` | 3 sequential upstream requests max per client call (initial attempt + up to `_INCOMPLETE_STEP_MAX_RETRIES = 2` retries) | `[F-08]` |
| 3. Fan-Out & Dependencies | `external_deps` | Upstream HTTPS API (`opencode.ai/zen/v1`), local filesystem state dir (`~/.dsh/bridges/opencode-zen-bridge/state/`) | `[F-14]` |
| 3. Fan-Out & Dependencies | `dep_timeout_budget_ms` | 300000 ms per upstream call; 0 ms external DB calls | `[F-14]` |
| 3. Fan-Out & Dependencies | `retry_amplification_cap` | Bounded by `_INCOMPLETE_STEP_MAX_RETRIES = 2` (max 3x upstream amplification on incomplete tool steps, 1x on normal turns) | `[F-08]` |
| 3. Fan-Out & Dependencies | `circuit_breaker_policy` | Immediate fail-fast on HTTP 4xx/5xx upstream status or client socket disconnect (`BrokenPipeError`) | `[F-08]` |
| 4. State & Storage | `primary_store` | Local JSON session files in `~/.dsh/bridges/opencode-zen-bridge/state/` (capped at 500 files) | `[F-02]` |
| 4. State & Storage | `cache_store` | In-process memory buffers (`ToolCallParser._buf`, `held`, `collected_texts`) scoped per request | `[F-06]` |
| 4. State & Storage | `hot_key_bound` | Per-session state file locked/updated per conversation turn (`dsh-<hash>.json`) | `[F-02]` |
| 4. State & Storage | `isolation_level` | Request-local parser instances (`ToolCallParser` instantiated per attempt) + atomic file write per session | `[F-06]` |
| 4. State & Storage | `retention_ttl` | LRU pruning of state directory to most recent 500 session JSON files | `[F-14]` |
| 5. Compute & Memory | `cpu_budget_per_req_ms` | < 5 ms CPU per request for regex + `json.JSONDecoder.raw_decode` parsing | `[F-04]` |
| 5. Compute & Memory | `alloc_budget_per_req_bytes` | < 1 MiB transient string/list allocation per request | `[F-06]` |
| 5. Compute & Memory | `max_inflight_requests` | 16 concurrent threads on local `127.0.0.1:9883` | `[F-14]` |
| 5. Compute & Memory | `worker_model` | Python 3 stdlib `ThreadingHTTPServer` (no external async loop or worker process pool) | `[F-14]` |
| 5. Compute & Memory | `gc_pause_bound_ms` | < 5 ms CPython refcount + generational GC pause | `[F-14]` |
| 6. Queues & Backpressure | `queue_type` | OS TCP listen backlog on `127.0.0.1:9883` + streaming chunk generator | `[F-14]` |
| 6. Queues & Backpressure | `queue_capacity` | `_MAX_BUFFER = 65536` bytes (64 KiB) inside `ToolCallParser._buf` before forced flush | `[F-06]` |
| 6. Queues & Backpressure | `overflow_policy` | When `ToolCallParser._buf` exceeds `_MAX_BUFFER = 65536` without a closing tag, logs `tool_call_unclosed_overflow` and flushes | `[F-06]` |
| 6. Queues & Backpressure | `backpressure_signal` | Blocking socket write to local HTTP client (`self.wfile.write`) | `[F-08]` |
| 6. Queues & Backpressure | `batch_window_ms` | 0 ms (immediate SSE token streaming except while holding an open `<tool_call>`/`<tool_invoke>` tag) | `[F-08]` |
| 7. Failure Modes & Degradation | `retry_storm_bound` | Hard cap `_INCOMPLETE_STEP_MAX_RETRIES = 2` per HTTP request; no recursive self-calls | `[F-08]` |
| 7. Failure Modes & Degradation | `fallback_behavior` | On genuine non-tool prose, stream text normally; on broken tool tag during retry, strip broken tag and re-prompt up to 2 times | `[F-08]` |
| 7. Failure Modes & Degradation | `partial_failure_mode` | If upstream stream drops mid-tag, `ToolCallParser.close()` logs `tool_call_unclosed_eof` and triggers incomplete-step retry if applicable | `[F-06]` |
| 7. Failure Modes & Degradation | `poison_pill_handling` | Malformed `<tool_invoke>{...}}}</tool_invoke>` recovered via trailing-brace decoder; genuinely broken tags stripped by `_sanitize_assistant_text` | `[F-03]`, `[F-13]` |
| 8. Observability & Rollout | `key_metrics` | `tool_call_unparsed`, `tool_call_unclosed_eof`, `incomplete_tool_step re-prompt`, `unmapped_tool_retry` in `bridge.err.log` | `[F-01]` |
| 8. Observability & Rollout | `structured_logs` | Timestamped stderr log entries in `~/.dsh/bridges/opencode-zen-bridge/logs/bridge.err.log` | `[F-01]` |
| 8. Observability & Rollout | `trace_propagation` | Session ID (`dsh-<16hex>`) logged with every request and state dump | `[F-01]` |
| 8. Observability & Rollout | `feature_flag_name` | N/A — standalone local Python stdlib bridge (`cli-agent-bridge`, not a GigaRC service) | `[F-14]` |
| 8. Observability & Rollout | `kill_switch_behavior` | Revert `~/.dsh/bridges/opencode-zen-bridge/server.py` and `launchctl kickstart -k gui/501/com.user.dsh-opencode-zen-bridge` (< 2s) | `[F-14]` |
| 8. Observability & Rollout | `canary_rollout_plan` | Run 360+ bridge unit tests + 44 root parser tests (`L1`/`L2`), sync to `~/.dsh/bridges/opencode-zen-bridge/server.py`, restart `:9883`, run live heavy-path tool call | `[F-14]`, `[F-15]` |
| 8. Observability & Rollout | `rollback_trigger` | Any regression in 360+ unit tests, crash on `:9883`, or non-200 / leaked `<tool_invoke>` on live `:9883` tool-call probe | `[F-14]`, `[F-15]` |
| 8. Observability & Rollout | `migration_compat` | 100% backward-compatible with OpenAI `/v1/chat/completions` SSE and JSON clients and existing `state/*.json` files | `[F-11]`, `[F-14]` |

## 4. Mandatory 4 Architecture Gates Mapping

1. **`C-MULT/v1` (Call Multiplicity & Retry Amplification Gate):**
   - Parser recovery (`_loads_lenient`, `_parse_tool_call_blocks`, `_parse_tool_call_block`) is purely in-memory ($O(N)$ over the tag payload, `0` extra I/O hops).
   - Recovering `<tool_invoke>{...}}}</tool_invoke>` on the first emission **reduces** upstream call multiplicity from $3\times$ (initial + 2 failed re-prompts) to $1\times$ (immediate tool call emission).
   - `_INCOMPLETE_STEP_MAX_RETRIES = 2` remains the strict upper bound on retry attempts.
2. **`S-HERD/v1` (Stampede / Thundering Herd & State Contention Gate):**
   - No shared mutable parser state across threads (`ToolCallParser` and `held` are instantiated per request/attempt).
   - Stripping malformed closed `<tool_call>`/`<tool_invoke>` blocks in `_sanitize_assistant_text` prevents poisoned session history from triggering repeated re-prompt loops across subsequent turns.
3. **`H-CPU/v1` (Hot-Path CPU & Algorithmic Complexity Gate):**
   - Trailing-brace recovery uses `json.JSONDecoder(strict=False).raw_decode` only on the cold error path (when `json.loads` has already raised `JSONDecodeError`), followed by a linear tail check (`tail.strip("{}").strip() == ""` or `all(ch in " \t\r\n}" for ch in tail)` with at least one `}`). Zero regex backtracking on large strings; bounded by `_MAX_BUFFER = 65536` bytes.
4. **`R-BULK/v1` (Bulkhead, Isolation & Fault Containment Gate):**
   - `ToolCallParser` buffer remains strictly capped at `_MAX_BUFFER = 65536` bytes.
   - Delaying `held` flush in `Handler._stream_sse` until retry resolution is bounded by the single-tag buffer (`<= 64 KiB`) and isolated to the individual HTTP request handler thread.

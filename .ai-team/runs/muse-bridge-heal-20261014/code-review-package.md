# Code Review Package (R2 Delta Fixed) — muse-bridge-heal-20261014

## 1. Metadata & Artifact Hashes
- **Task ID**: `muse-bridge-heal-20261014`
- **Criticality**: `S2` (`entry=full`, `reviewer_skip=true`, `parent_skill=analyst-teamlead`)
- **Architecture Spec**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-heal-20261014/arch-spec.md` (`sha256=2a51c65c057e5c573e50baa90a1d53b24ea1e98402b67c79538bdbddac4dfa5e`)
- **Architecture Packet**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-heal-20261014/architecture-packet.json` (`sha256=ab0b4851a6d408dd8efe29148f0f7cc275e166dfef852b37a816755bc244bed1`)
- **ARCH_PANEL Proof (Round 2)**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-heal-20261014/panel/arch/r2/panel-proof.json` (`sha256=cdd3e19299786a758605187fcda46d54c37e6b1eb56e89a5e7b29efc447e3472`)
- **Coder Plan**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-heal-20261014/plans/coder-v1.json` (`sha256=44204efa3a2796a2781d6c07c3b8fc7c5f04be98c133d5d7080a125b2a93079d`)
- **Coder Artifact**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-heal-20261014/coder.json` (`sha256=84a9a52dd53cd26ea890db85b28732b27a67c7ce7a428e0f07213c513fc0b1f9`)
- **Verifier Receipt**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-heal-20261014/receipts/verifier-receipt.json` (`sha256=f01f6050e827bb649ba0ffa1e44d0351155c10c99241b323ca83e7b920c07a96`)
- **Modified Production File**: `/Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py` (`sha256=084089ce29bacd8c248735473a5fea8f50c5fff9f73ee29746e60ed836cfc5b5`)
- **Modified Test File**: `/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_muse_bridge_killpg.py` (`sha256=1dcb4a0861bfe149bda9e64aa9b3b5a500fbcc830c723ad96a30d686b01a9a7f`)

## 2. Exact Requirements & Architecture Decision Traceability Matrix (`AD-001`..`AD-005` + `F-001` + `F-002`)
| Requirement / AD | Exact Implementation in `bridges/muse-bridge/server.py` | Exact Unit Tests in `tests/test_muse_bridge_killpg.py` | Status |
|---|---|---|---|
| `REQ-01` / `AD-001`: Log all 3 early HTTP 502 / SSE error exits in `Handler._serve_json` (`launcher_missing`/`spawn_failed`, `state != "ok" or rc != 0`, and `empty_output`) via `_format_err_log` and `_redact_secrets` before `return` | `_redact_secrets` (L177-L194), `_format_err_log` (L301-L308), `Handler._serve_json` (L1743-L2028) | `ErrorLoggingTest`: `test_all_error_branches_log_once_and_success_stays_done`, `test_secret_canaries_masked_in_log_json_and_sse`, `test_none_diagnostic_is_empty`, `test_r2_escaped_quotes_mask_entire_secret_in_all_sinks`, `test_r2_long_reflected_message_redacted_before_clipping`, `test_r2_short_messages_preserve_error_words`, `test_quota_secrets_do_not_reach_any_error_sink` | PASS |
| `REQ-02` / `AD-002`: Extract structured `turn/completed` `params.error` (`TurnError`: `kind[:64]`, `message[:160]`, `retryable`, recursively scrubbed `quota[:120]`) and non-duplicate `params.reason[:160]` into priority `turn_diag_lines` ahead of `stderr` (`<=300` priority, `<=500` total) | `_clip_diagnostic` (L197-L202), `_prompt_reflected_parts` (L205-L212), `_diagnostic_text` (L215-L227), `_redact_quota` (L230-L244), `_turn_diagnostics` (L247-L298), `ServeRun.execute` | `ServeTurnErrorExtractionTest`: `test_r2_prompt_parts_redacted_before_and_after_normalization`, `test_typed_error_reason_and_stderr_priority`, `test_reason_only_duplicate_and_malformed`, `test_no_diagnostics_preserves_stderr_tail_and_success`, `test_field_caps_budget_and_redaction_boundaries` | PASS |
| `REQ-03` / `AD-003`: Send valid SSE data chunk `self._sse_chunk({"content": ""})` in `Handler._keepalive_loop` with 3-phase stream sealing (`OPEN -> FINALIZING -> CLOSED`) under `self._wlock` and class-level default attributes on `Handler` | `_sse_write` (L1455-L1481), `_sse_emit` (L1492-L1495), `_keepalive_loop` (L1527-L1533), `_sse_stop_keepalive` (L1535-L1544) | `SseDataKeepaliveTest`: `test_defaults_and_s3_seal_suppresses_late_tick_and_duplicate_done`, `test_s1_data_ticks_before_done_preserve_content_and_tools`, `test_s2_inflight_flush_precedes_finalization`, `test_done_write_failure_closes_phase` | PASS |
| `REQ-04` & `REQ-05` / `AD-004`: Pass `--disable-write`, `--disable-shell` to `muse serve` (`ServeRun.execute`) and `--disable-write`, `--disable-shell`, `--disable-web-tools`, `--disable-reminders` to `muse exec` (`Run.execute`, keeping `--yolo`); preserve `approval/request` fallback | `Run.execute`, `ServeRun.execute`, `ServeRun._handle_event` | `CliDisableFlagsAndApprovalFallbackTest`: `test_serve_argv_disables_write_shell`, `test_approval_falls_back_to_exec_without_decide` | PASS |
| `REQ-06` / `AD-005`: Register `muse-wonder-1.0` and `muse-wonder-full-1.0` (`1048576` context, `131072` max_output) in `ALLOWED_MODELS` | `ALLOWED_MODELS` (L63-L96) | `AllowedModelsSyncTest`: `test_models_and_health_include_wonder_models` | PASS |
| `F-001` & `F-002` (Council R2 fixes): Support escaped quotes `\"` in `_redact_secrets`; scrub reflected user messages (`len >= 8`) via `_prompt_reflected_parts` BEFORE 160-char field truncation; protect short messages (`< 8` chars like `"hi"`) from garbling words (`"this"`) | `_redact_secrets` (L177-L194), `_prompt_reflected_parts` (L205-L212), `_diagnostic_text` (L215-L227), `Handler._serve_json` (L1743-L2028) | `ErrorLoggingTest` & `ServeTurnErrorExtractionTest` (37 total tests) | PASS |

## 3. Complete Test Suite Inventory (37 Tests, All Passing)
- `CloseKillsGroupTest` (L136-L178, 2 tests): `test_r1_run_close_kills_group`, `test_r1_serve_run_close_kills_group`
- `HealthQuarantinedTest` (L282-L288, 1 tests): `test_health_reports_quarantined_slots`
- `DisconnectScenarioTest` (L291-L338, 2 tests): `test_r2_disconnect_frees_slot_and_kills_group`, `test_r3_health_active_zero_after_disconnect`
- `ServeDisconnectScenarioTest` (L341-L374, 1 tests): `test_r4_disconnect_during_serve_turn_kills_group_and_frees_slot`
- `ClientGoneProbeTest` (L400-L470, 5 tests): `test_probe_uses_msg_dontwait_without_mode_change`, `test_probe_no_data_is_not_disconnect`, `test_probe_leaves_pending_data_unread`, `test_probe_detects_fin_and_reset`, `test_probe_does_not_break_concurrent_write`
- `QuarantineSlotTest` (L473-L573, 3 tests): `test_slot_stays_withdrawn_until_group_dies`, `test_no_signals_after_ceiling`, `test_reaped_leader_gets_no_signals`
- `ConcurrentCloseTest` (L576-L613, 2 tests): `test_run_second_close_waits_for_cleanup`, `test_serve_run_second_close_waits_for_cleanup`
- `WaitGroupExitTest` (L616-L639, 2 tests): `test_reaped_leader_gets_single_control_kill`, `test_live_leader_keeps_killing`
- `ErrorLoggingTest` (L669-L880, 7 tests): `test_all_error_branches_log_once_and_success_stays_done`, `test_secret_canaries_masked_in_log_json_and_sse`, `test_none_diagnostic_is_empty`, `test_r2_escaped_quotes_mask_entire_secret_in_all_sinks`, `test_r2_long_reflected_message_redacted_before_clipping`, `test_r2_short_messages_preserve_error_words`, `test_quota_secrets_do_not_reach_any_error_sink`
- `ServeTurnErrorExtractionTest` (L939-L1047, 5 tests): `test_r2_prompt_parts_redacted_before_and_after_normalization`, `test_typed_error_reason_and_stderr_priority`, `test_reason_only_duplicate_and_malformed`, `test_no_diagnostics_preserves_stderr_tail_and_success`, `test_field_caps_budget_and_redaction_boundaries`
- `SseDataKeepaliveTest` (L1050-L1160, 4 tests): `test_defaults_and_s3_seal_suppresses_late_tick_and_duplicate_done`, `test_s1_data_ticks_before_done_preserve_content_and_tools`, `test_s2_inflight_flush_precedes_finalization`, `test_done_write_failure_closes_phase`
- `CliDisableFlagsAndApprovalFallbackTest` (L1163-L1209, 2 tests): `test_serve_argv_disables_write_shell`, `test_approval_falls_back_to_exec_without_decide`
- `AllowedModelsSyncTest` (L1212-L1226, 1 tests): `test_models_and_health_include_wonder_models`

## 4. Clean-Room L2 Verifier Receipt Summary (`VER-001`..`VER-004`)
- Note on `basedpyright`: `cli-agent-bridge` has 538 pre-existing baseline type warnings on `HEAD`; `basedpyright --level error bridges/muse-bridge/server.py tests/test_muse_bridge_killpg.py` reports **0 errors** (`exit 0`). Live delivery checks (`VER-005`, `AC-07`, `AC-11`) are explicitly scheduled for Stage 3 post-council deployment.
```json
{
  "schema_version": "1.0",
  "gate": "VERIFIER",
  "status": "PASS",
  "run_id": "muse-bridge-heal-20261014",
  "checks": [
    {
      "id": "VER-001",
      "command": "python3 -B -m unittest -v tests.test_muse_bridge_killpg",
      "exit_code": 0
    },
    {
      "id": "VER-002",
      "command": "python3 -B -m py_compile bridges/muse-bridge/server.py tests/test_muse_bridge_killpg.py",
      "exit_code": 0
    },
    {
      "id": "VER-003-ruff-fmt",
      "command": ".venv/bin/ruff format --check bridges/muse-bridge/server.py tests/test_muse_bridge_killpg.py",
      "exit_code": 0
    },
    {
      "id": "VER-003-ruff-chk",
      "command": ".venv/bin/ruff check bridges/muse-bridge/server.py tests/test_muse_bridge_killpg.py",
      "exit_code": 0
    },
    {
      "id": "VER-003-pyright-err",
      "command": ".venv/bin/basedpyright --level error bridges/muse-bridge/server.py tests/test_muse_bridge_killpg.py",
      "exit_code": 0
    },
    {
      "id": "VER-004-serve-help",
      "command": "/Users/aazhiry1/.local/bin/muse serve --help",
      "exit_code": 0
    },
    {
      "id": "VER-004-exec-help",
      "command": "/Users/aazhiry1/.local/bin/muse exec --help",
      "exit_code": 0
    },
    {
      "id": "git-diff-check",
      "command": "git diff --check -- bridges/muse-bridge/server.py tests/test_muse_bridge_killpg.py",
      "exit_code": 0
    }
  ],
  "server_py_sha256": "7d02f13c475c5b205198a268ee9407539c27e9a6e26b45cd25c644e3e66af846",
  "test_py_sha256": "5ef6d3cd155347e7ea9f84d3040d592d67569a87567ad53a2ceac314d4fb7378",
  "verified_at": "2026-10-14T09:57:11.938734+00:00",
  "modified_files": {
    "bridges/muse-bridge/server.py": "084089ce29bacd8c248735473a5fea8f50c5fff9f73ee29746e60ed836cfc5b5",
    "tests/test_muse_bridge_killpg.py": "1dcb4a0861bfe149bda9e64aa9b3b5a500fbcc830c723ad96a30d686b01a9a7f"
  },
  "test_summary": "Ran 37 tests in clean-room L2 verifier (18 baseline + 19 new, including 4 regressions for F-001 escaped quotes and F-002 reflected user message scrubbing before truncation + short message protection): OK (exit 0)"
}
```

## 5. Exact Unified Diff (`bridges/muse-bridge/server.py` and `tests/test_muse_bridge_killpg.py`)
```diff
diff --git a/bridges/muse-bridge/server.py b/bridges/muse-bridge/server.py
index d351b6e..d5bf3b9 100644
--- a/bridges/muse-bridge/server.py
+++ b/bridges/muse-bridge/server.py
@@ -14,7 +14,8 @@ Stdout CLI — JSONL-конверты (schema_version=1). Текст ответ
 `task.lifecycle.failed` (event.reason). Usage CLI в JSONL не отдаёт — оценка по словам.
 
 Транспорт — stdlib. `stream:true`: заголовки 200 и role-delta уходят сразу, пока ход
-идёт — комментарии `: keepalive` (MUSE_BRIDGE_KEEPALIVE_S); по готовности — reasoning
+идёт — data-чанки `chat.completion.chunk` с пустой дельтой `{"content": ""}`
+(MUSE_BRIDGE_KEEPALIVE_S); по готовности — reasoning
 summaries как `delta.reasoning_content`, tool_calls, content-чанки (~300 символов), финал
 с finish_reason + usage, затем `data: [DONE]`. Ошибка после старта потока — кадр
 `{"error": …}` + `[DONE]`. Текст ответа CLI отдаёт в конце хода, поэтому content
@@ -23,10 +24,9 @@ summaries как `delta.reasoning_content`, tool_calls, content-чанки (~300
 Провал хода (failed terminal, rc != 0, таймаут) не отдаётся как успешный финал: частичный
 текст и tool-блоки отбрасываются — SSE-кадр ошибки + `[DONE]` (stream) либо 502 (JSON).
 
-Keepalive: комментарии `: keepalive` держат TCP-соединение от закрытия клиентом/прокси, но
-SDK отбрасывает их на уровне декодера и idle-watchdog не сбрасывают. Поэтому после применения
-профиля muse (`streamIdleTimeoutMs=1900000`) DSH нужно перезапустить; сброс watchdog кадрами
-данных (полный стрим текста muse) в этот мост не входит.
+Keepalive: пустые data-чанки держат SSE-соединение, не меняя текст ответа.
+Сброс idle-watchdog клиента pi-ai требует отдельной живой проверки в DSH.
+Перед финалом поток запечатывается; после `data: [DONE]` записей нет.
 
 Эмуляция OpenAI function calling (порт из droid-bridge): если запрос содержит
 непустой `tools` (и tool_choice != "none"), в системный текст добавляется протокол
@@ -74,6 +74,8 @@ ALLOWED_MODELS: dict[str, dict[str, Any]] = {
     # 2026-10-05: контрибьютор-слот (только пикер, по просьбе владельца).
     # id подтверждён `muse model-profile show` (резолвится); окно/лимит как у spark.
     "muse-spark-1.3-contributor": {"context_length": 1048576, "max_output": 131072},
+    "muse-wonder-1.0": {"context_length": 1048576, "max_output": 131072},
+    "muse-wonder-full-1.0": {"context_length": 1048576, "max_output": 131072},
 }
 DEFAULT_MODEL = os.environ.get("MUSE_BRIDGE_MODEL", "muse-spark-1.3")
 
@@ -172,6 +174,140 @@ def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
     return handler.headers.get("x-api-key", "") == AUTH_KEY or hdr.strip() == AUTH_KEY
 
 
+def _redact_secrets(text: str) -> str:
+    """Удалить отражённые ключи до обрезки диагностики; повторный вызов безопасен."""
+    if AUTH_KEY:
+        text = text.replace(AUTH_KEY, "[REDACTED]")
+    text = re.sub(
+        r"Authorization\s*:\s*[^\r\n]+",
+        "Authorization: [REDACTED]",
+        text,
+        flags=re.IGNORECASE,
+    )
+    text = re.sub(r"Bearer\s+\S+", "Bearer [REDACTED]", text, flags=re.IGNORECASE)
+    text = re.sub(
+        r"""(["']?(?:api[_-]?key|token|secret|password|bridge[_-]?key)["']?\s*[:=]\s*)("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s,;}"']+)""",
+        lambda match: match[1] + "[REDACTED]",
+        text,
+        flags=re.IGNORECASE,
+    )
+    return re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[REDACTED]", text)
+
+
+def _clip_diagnostic(text: str, limit: int) -> str:
+    """Ограничить поле, убрав его целиком при разрезании маркера редакции."""
+    for marker in re.finditer(re.escape("[REDACTED]"), text):
+        if marker.start() < limit < marker.end():
+            return ""
+    return text[:limit]
+
+
+def _prompt_reflected_parts(prompt: str) -> list[str]:
+    """Выделить длинные отражённые реплики, начиная с самых полных совпадений."""
+    parts = {prompt} if len(prompt.strip()) >= 8 else set()
+    for part in prompt.split("\n\n") + prompt.splitlines():
+        for candidate in (part, re.sub(r"^(?:User|Assistant|System):\s*", "", part)):
+            if len(candidate.strip()) >= 8:
+                parts.add(candidate)
+    return sorted(parts, key=len, reverse=True)
+
+
+def _diagnostic_text(value: Any, prompt: str = "") -> str:
+    """Санитизировать свободное поле и нормализовать управляющие переводы строк."""
+    text = str(value) if value is not None else ""
+    text = _redact_secrets(text)
+    parts = _prompt_reflected_parts(prompt)
+    for part in parts:
+        text = text.replace(part, "[REDACTED]")
+    control_chars = r"[\x00-\x1f\x7f-\x9f\u2028\u2029]"
+    text = re.sub(control_chars, " ", text).strip()
+    for part in parts:
+        normalized = re.sub(control_chars, " ", part).strip()
+        text = text.replace(normalized, "[REDACTED]")
+    return text
+
+
+def _redact_quota(value: Any) -> Any:
+    """Удалить значения чувствительных ключей quota до JSON-сериализации."""
+    if isinstance(value, dict):
+        return {
+            key: "[REDACTED]"
+            if re.sub(r"[_-]", "", str(key)).lower()
+            in {"token", "secret", "password", "apikey", "bridgekey", "authorization"}
+            else _redact_quota(item)
+            for key, item in value.items()
+        }
+    if isinstance(value, list):
+        return [_redact_quota(item) for item in value]
+    if isinstance(value, str):
+        return _redact_secrets(value)
+    return value
+
+
+def _turn_diagnostics(params: dict[str, Any], prompt: str) -> list[str]:
+    """Собрать приоритетный блок MSP с покомпонентными лимитами и бюджетом 300."""
+    error = params.get("error")
+    kind = message = quota = retryable = ""
+    if isinstance(error, dict):
+        kind = _diagnostic_text(error.get("kind"), prompt)
+        message = _diagnostic_text(error.get("message"), prompt)
+        if isinstance(error.get("retryable"), bool):
+            retryable = f" retryable={error['retryable']}"
+        if error.get("quota") is not None:
+            try:
+                quota = json.dumps(
+                    _redact_quota(error["quota"]),
+                    ensure_ascii=False,
+                    sort_keys=True,
+                    default=str,
+                    separators=(",", ":"),
+                )
+            except (TypeError, ValueError, RecursionError):
+                quota = str(error["quota"])
+            quota = _diagnostic_text(quota, prompt)
+    elif error is not None:
+        message = _diagnostic_text(error, prompt)
+    reason = _diagnostic_text(params.get("reason"), prompt)
+    if reason == message:
+        reason = ""
+    fields = {
+        "kind": _clip_diagnostic(kind, 64),
+        "message": _clip_diagnostic(message, 160),
+        "quota": _clip_diagnostic(quota, 120),
+        "reason": _clip_diagnostic(reason, 160),
+    }
+
+    def lines() -> list[str]:
+        primary = ": ".join(fields[key] for key in ("kind", "message") if fields[key])
+        primary += retryable
+        if fields["quota"]:
+            primary += " quota=" + fields["quota"]
+        result = [primary.strip()] if primary.strip() else []
+        if fields["reason"]:
+            result.append("reason: " + fields["reason"])
+        return result
+
+    for key in ("quota", "reason", "message", "kind"):
+        excess = len("\n".join(lines())) - 300
+        if excess <= 0:
+            break
+        minimum = min(16, len(fields[key])) if key == "reason" else 0
+        fields[key] = _clip_diagnostic(
+            fields[key], max(minimum, len(fields[key]) - excess)
+        )
+    return lines()
+
+
+def _format_err_log(
+    model: str, via: str, out: dict[str, Any], stream: bool, state: str | None = None
+) -> str:
+    """Единая однострочная запись финального отказа без промпта и секретов."""
+    return (
+        f"error model={model} via={via} rc={out.get('rc')} state={state or out.get('state')} "
+        f"err={_redact_secrets(str(out.get('err') or ''))[:300]!r} stream={stream}"
+    )
+
+
 def _flatten_content(content: Any) -> str:
     """OpenAI content (str | list[part]) -> plain text."""
     if content is None:
@@ -729,6 +865,10 @@ class Run:
             str(self.workdir),
             "--json",
             "--no-session-log",
+            "--disable-write",
+            "--disable-shell",
+            "--disable-web-tools",
+            "--disable-reminders",
             "--prompt-file",
             prompt_path,
         ]
@@ -986,6 +1126,8 @@ class ServeRun:
             self.model_id,
             "--no-session-log",
             "--trust-workspace",
+            "--disable-write",
+            "--disable-shell",
         ]
         try:
             self.proc = subprocess.Popen(
@@ -1008,6 +1150,8 @@ class ServeRun:
         os.set_blocking(self.proc.stdin.fileno(), False)
 
         err_lines: list[str] = []
+        turn_diag_lines: list[str] = []
+        stderr_joined = False
 
         def drain_stderr() -> None:
             try:
@@ -1193,6 +1337,8 @@ class ServeRun:
                         _handle_event(msg, None)
                         continue
                     terminal = str(p.get("terminal") or "unknown")
+                    if terminal != "completed":
+                        turn_diag_lines = _turn_diagnostics(p, self.prompt)
                     break
                 if "id" in msg and ("result" in msg or "error" in msg):
                     continue  # чужой/дублированный ack — игнор, не разрываем ход
@@ -1216,7 +1362,19 @@ class ServeRun:
                 if part not in summaries:
                     summaries.append(part)
             text = final_text if final_text is not None else "".join(deltas)
-            err = "\n".join(err_lines[-6:])
+            # Прежнее ожидание drain_stderr переносится до снимка: шум после terminal
+            # не теряется; приоритетный носитель не зависит от хвоста сборщика.
+            err_thread.join(timeout=5)
+            stderr_joined = True
+            stderr_tail = _redact_secrets("\n".join(list(err_lines)[-6:]))
+            if self.prompt:
+                stderr_tail = stderr_tail.replace(self.prompt, "[REDACTED]")
+            err = "\n".join(turn_diag_lines)
+            if err:
+                if stderr_tail:
+                    err += "\n" + _clip_diagnostic(stderr_tail, 499 - len(err))
+            else:
+                err = stderr_tail
             if terminal == "completed" and serve_rc not in (None, 0, *_SIGNAL_RCS):
                 return {
                     "rc": serve_rc,
@@ -1250,7 +1408,8 @@ class ServeRun:
                 "via": "serve",
             }
         finally:
-            err_thread.join(timeout=5)
+            if not stderr_joined:
+                err_thread.join(timeout=5)
             self.close()
 
 
@@ -1273,7 +1432,8 @@ class Handler(BaseHTTPRequestHandler):
     _sse_created: int = 0
     _sse_model: str = ""
     _wlock: threading.Lock = threading.Lock()
-    _ka_stop: threading.Event | None = None
+    _sse_phase: str = "OPEN"
+    _keepalive_stop: threading.Event | None = None
     _ka_thread: threading.Thread | None = None
 
     def setup(self) -> None:
@@ -1285,17 +1445,33 @@ class Handler(BaseHTTPRequestHandler):
         self._sse_created = 0
         self._sse_model = ""
         self._wlock = threading.Lock()
-        self._ka_stop: threading.Event | None = None
+        with self._wlock:
+            self._sse_phase = "OPEN"
+        self._keepalive_stop: threading.Event | None = None
         self._ka_thread: threading.Thread | None = None
         super().setup()
 
     # ---- ранний SSE: заголовки сразу, keepalive во время хода ---------------------
-    def _sse_write(self, text: str) -> bool:
+    def _sse_write(self, text: str, *, keepalive: bool = False) -> bool:
         """Запись кадра SSE под замком (keepalive и выдача из разных потоков)."""
         try:
             with self._wlock:
-                self.wfile.write(text.encode("utf-8"))
-                self.wfile.flush()
+                if self._sse_phase == "CLOSED" or self._client_gone:
+                    return False
+                if keepalive and (
+                    self._sse_phase != "OPEN"
+                    or (
+                        self._keepalive_stop is not None
+                        and self._keepalive_stop.is_set()
+                    )
+                ):
+                    return False
+                try:
+                    self.wfile.write(text.encode("utf-8"))
+                    self.wfile.flush()
+                finally:
+                    if text == "data: [DONE]\n\n":
+                        self._sse_phase = "CLOSED"
             return True
         except (BrokenPipeError, ConnectionResetError, OSError):
             if not self._client_gone:
@@ -1313,14 +1489,18 @@ class Handler(BaseHTTPRequestHandler):
             "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
         }
 
-    def _sse_emit(self, obj: dict) -> bool:
-        return self._sse_write("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n")
+    def _sse_emit(self, obj: dict, *, keepalive: bool = False) -> bool:
+        return self._sse_write(
+            "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n", keepalive=keepalive
+        )
 
     def _sse_begin(self, model: str) -> bool:
         """Заголовки 200 + role-кадр до запуска хода и поток keepalive; False — клиент ушёл."""
         self._sse_id = f"chatcmpl-muse-{uuid.uuid4().hex[:12]}"
         self._sse_created = int(time.time())
         self._sse_model = model
+        with self._wlock:
+            self._sse_phase = "OPEN"
         self.close_connection = True
         try:
             self.send_response(200)
@@ -1337,7 +1517,7 @@ class Handler(BaseHTTPRequestHandler):
         if not self._sse_emit(self._sse_chunk({"role": "assistant", "content": ""})):
             return False
         stop = threading.Event()
-        self._ka_stop = stop
+        self._keepalive_stop = stop
         self._ka_thread = threading.Thread(
             target=self._keepalive_loop, args=(stop,), daemon=True
         )
@@ -1345,17 +1525,22 @@ class Handler(BaseHTTPRequestHandler):
         return True
 
     def _keepalive_loop(self, stop: threading.Event) -> None:
-        """Комментарии `: keepalive`: держат TCP, но не сбрасывают idle-watchdog SDK."""
+        """Пустые data-чанки держат SSE; эффект на idle проверяется живым ходом."""
         while not stop.wait(KEEPALIVE_S):
-            if not self._sse_write(": keepalive\n\n"):
+            if self._client_gone or stop.is_set():
+                return
+            if not self._sse_emit(self._sse_chunk({"content": ""}), keepalive=True):
                 return
 
     def _sse_stop_keepalive(self) -> None:
-        if self._ka_stop is not None:
-            self._ka_stop.set()
+        if self._keepalive_stop is not None:
+            self._keepalive_stop.set()
+        with self._wlock:
+            if self._sse_phase == "OPEN":
+                self._sse_phase = "FINALIZING"
         if self._ka_thread is not None:
             self._ka_thread.join(timeout=2)
-        self._ka_stop = None
+        self._keepalive_stop = None
         self._ka_thread = None
 
     def _client_gone_probe(self) -> bool:
@@ -1687,12 +1872,31 @@ class Handler(BaseHTTPRequestHandler):
             # Клиент ушёл: ответ в закрытый сокет не пишется (ни JSON, ни кадр ошибки).
             _log("client gone — response skipped")
             return
+        # Только локальная граница запроса знает отражённый промпт; глобально его не храним.
+        out = dict(out)
+        diagnostic = _redact_secrets(str(out.get("err") or ""))
+        if len(prompt.strip()) >= 8:
+            diagnostic = diagnostic.replace(prompt, "[REDACTED]")
+        for message in req.get("messages") or []:
+            if isinstance(message, dict):
+                reflected = _flatten_content(message.get("content")).strip()
+                if len(reflected) >= 8:
+                    diagnostic = diagnostic.replace(reflected, "[REDACTED]")
+                    normalized = re.sub(
+                        r"[\x00-\x1f\x7f-\x9f\u2028\u2029]", " ", reflected
+                    )
+                    diagnostic = diagnostic.replace(normalized, "[REDACTED]")
+                    if len(normalized) >= 160:
+                        diagnostic = diagnostic.replace(normalized[:160], "[REDACTED]")
+        out["err"] = _redact_secrets(diagnostic)
         if out.get("state") in ("launcher_missing", "spawn_failed"):
+            _log(_format_err_log(model, via, out, req.get("stream") is True))
             self._send(
                 502,
                 {
                     "error": {
-                        "message": out.get("err") or out["state"],
+                        "message": _redact_secrets(str(out.get("err") or out["state"])),
+                        "detail": _redact_secrets(str(out.get("err") or ""))[:500],
                         "type": "proxy_error",
                         "code": 502,
                     }
@@ -1703,12 +1907,15 @@ class Handler(BaseHTTPRequestHandler):
             # Провал хода (failed terminal, rc != 0, таймаут): частичный текст и tool-блоки
             # не выдаются как успешный финал — SSE error + [DONE] либо 502 (Q-004).
             hint = " (proxy :10816 DOWN?)" if out.get("rc") == 42 else ""
+            _log(_format_err_log(model, via, out, req.get("stream") is True))
             self._send(
                 502,
                 {
                     "error": {
-                        "message": f"muse turn failed (rc={out.get('rc')}, state={out.get('state')}){hint}",
-                        "detail": str(out.get("err"))[:500],
+                        "message": _redact_secrets(
+                            f"muse turn failed (rc={out.get('rc')}, state={out.get('state')}){hint}"
+                        ),
+                        "detail": _redact_secrets(str(out.get("err") or ""))[:500],
                         "type": "proxy_error",
                         "code": 502,
                     }
@@ -1721,12 +1928,19 @@ class Handler(BaseHTTPRequestHandler):
             content, tool_calls = _split_tool_calls(out.get("chunks") or [content])
         if not content and not tool_calls:
             hint = " (proxy :10816 DOWN?)" if out.get("rc") == 42 else ""
+            _log(
+                _format_err_log(
+                    model, via, out, req.get("stream") is True, "empty_output"
+                )
+            )
             self._send(
                 502,
                 {
                     "error": {
-                        "message": f"muse exec produced no text (rc={out.get('rc')}, state={out.get('state')}){hint}",
-                        "detail": str(out.get("err"))[:500],
+                        "message": _redact_secrets(
+                            f"muse exec produced no text (rc={out.get('rc')}, state={out.get('state')}){hint}"
+                        ),
+                        "detail": _redact_secrets(str(out.get("err") or ""))[:500],
                         "type": "proxy_error",
                         "code": 502,
                     }
diff --git a/tests/test_muse_bridge_killpg.py b/tests/test_muse_bridge_killpg.py
index 9662841..99ff681 100644
--- a/tests/test_muse_bridge_killpg.py
+++ b/tests/test_muse_bridge_killpg.py
@@ -13,6 +13,8 @@ bridges/muse-bridge/server.py без живого muse-bin: вместо CLI —
 from __future__ import annotations
 
 import importlib.util
+import http.client
+import io
 import itertools
 import json
 import os
@@ -637,5 +639,592 @@ class WaitGroupExitTest(unittest.TestCase):
         self.assertGreater(count, 1)
 
 
+def bridge_request(
+    scenario: Any, payload: dict | None = None, path: str = "/v1/chat/completions"
+) -> tuple[int, bytes]:
+    """Прочитать полный ответ локального стенда, включая терминальный SSE-кадр."""
+    conn = http.client.HTTPConnection(*scenario.server.server_address[:2], timeout=5)
+    try:
+        conn.request(
+            "POST" if payload is not None else "GET",
+            path,
+            json.dumps(payload) if payload is not None else None,
+            {"Content-Type": "application/json", "Connection": "close"},
+        )
+        response = conn.getresponse()
+        return response.status, response.read()
+    finally:
+        conn.close()
+
+
+def turn_request(stream: bool = False) -> dict:
+    """Минимальный клиентский запрос без живого провайдера."""
+    return {
+        "model": "muse-spark-1.3",
+        "messages": [{"role": "user", "content": "prompt-canary-private"}],
+        "stream": stream,
+    }
+
+
+class ErrorLoggingTest(_BridgeScenario):
+    """AD-001/F-001: все выходы журналируются и не раскрывают отражённые секреты."""
+
+    def _error_response(
+        self, state: str, err: Any, stream: bool = False, rc: int = 1
+    ) -> tuple[dict, str]:
+        out = {"rc": rc, "state": state, "text": "", "err": err}
+        with mock.patch.object(self.mod.ServeRun, "execute", return_value=out):
+            status, body = bridge_request(self, turn_request(stream))
+        self.assertEqual(status, 200 if stream else 502)
+        if stream:
+            self.assertTrue(body.endswith(b"data: [DONE]\n\n"))
+            frames = [
+                json.loads(line[6:])
+                for line in body.decode().splitlines()
+                if line.startswith("data: {")
+            ]
+            error = next(frame["error"] for frame in frames if "error" in frame)
+        else:
+            error = json.loads(body)["error"]
+        logs = self.mod.LOG_PATH.read_text()
+        lines = [line for line in logs.splitlines() if " error model=" in line]
+        self.assertTrue(lines, "нет итогового error-лога")
+        return error, lines[-1]
+
+    def test_all_error_branches_log_once_and_success_stays_done(self) -> None:
+        for stream in (False, True):
+            for state in ("launcher_missing", "spawn_failed", "terminal_failed", "ok"):
+                with self.subTest(stream=stream, state=state):
+                    self.mod.LOG_PATH.unlink(missing_ok=True)
+                    error, line = self._error_response(
+                        state, "line1\nline2", stream, 0 if state == "ok" else 1
+                    )
+                    self.assertIn(
+                        "state=" + ("empty_output" if state == "ok" else state), line
+                    )
+                    self.assertIn("via=serve", line)
+                    self.assertIn(f"stream={stream}", line)
+                    self.assertIn("line1\\nline2", line)
+                    self.assertEqual(error["detail"], "line1\nline2")
+                    self.assertEqual(
+                        sum(
+                            " error model=" in x
+                            for x in self.mod.LOG_PATH.read_text().splitlines()
+                        ),
+                        1,
+                    )
+        with mock.patch.object(
+            self.mod.ServeRun,
+            "execute",
+            return_value={"rc": 0, "state": "ok", "text": "ok", "err": ""},
+        ):
+            self.mod.LOG_PATH.unlink()
+            self.assertEqual(bridge_request(self, turn_request())[0], 200)
+        self.assertEqual(
+            sum(
+                " done model=" in x for x in self.mod.LOG_PATH.read_text().splitlines()
+            ),
+            1,
+        )
+        self.assertNotIn(" error model=", self.mod.LOG_PATH.read_text())
+
+    def test_secret_canaries_masked_in_log_json_and_sse(self) -> None:
+        samples = [
+            "Bearer secret-canary-token-123",
+            "Authorization: super-private-value",
+            "api_key=canary_secret_val",
+            '{"token":"canary_secret_val"}',
+            "{'password': 'canary_secret_val'}",
+            'password="alpha beta gamma"',
+            "TOKEN: canary_secret_val",
+            "bridge-key=canary_secret_val",
+            "secret=canary_secret_val",
+            "sk-abcdefghijklmnop1234",
+            "bare-bridge-canary",
+        ]
+        # Подмена только локальной конфигурации модуля, окружение не меняется.
+        self.mod.AUTH_KEY = "bare-bridge-canary"
+        for stream in (False, True):
+            for sample in samples:
+                for prefix in ("", "x" * 285 + " ", "x" * 485 + " "):
+                    with self.subTest(stream=stream, sample=sample, prefix=len(prefix)):
+                        # Аутентификация запроса не нужна: модульный mock не меняет тестируемую редакцию.
+                        with mock.patch.object(self.mod, "_auth_ok", return_value=True):
+                            error, line = self._error_response(
+                                "terminal_failed", prefix + sample, stream
+                            )
+                        combined = json.dumps(error) + line
+                        for secret in (
+                            "secret-canary-token-123",
+                            "super-private-value",
+                            "canary_secret_val",
+                            "alpha beta gamma",
+                            "abcdefghijklmnop1234",
+                            "bare-bridge-canary",
+                        ):
+                            self.assertNotIn(secret, combined)
+                        if not prefix:
+                            self.assertIn("[REDACTED]", error["detail"])
+                            self.assertIn("[REDACTED]", line)
+                        self.assertLessEqual(len(error["detail"]), 500)
+                        self.assertNotIn("prompt-canary-private", combined)
+
+    def test_none_diagnostic_is_empty(self) -> None:
+        for state in ("spawn_failed", "terminal_failed", "ok"):
+            error, _ = self._error_response(state, None, rc=0 if state == "ok" else 1)
+            self.assertEqual(error["detail"], "")
+
+    def test_r2_escaped_quotes_mask_entire_secret_in_all_sinks(self) -> None:
+        samples = (
+            (
+                r'{"password": "alpha \" suffix-canary-27182"}',
+                '{"password": [REDACTED]}',
+            ),
+            (r'{"token":"alpha\" beta gamma"}', '{"token":[REDACTED]}'),
+        )
+        for stream in (False, True):
+            for sample, expected in samples:
+                with self.subTest(stream=stream, sample=sample):
+                    error, _ = self._error_response("terminal_failed", sample, stream)
+                    self.assertEqual(error["detail"], expected)
+                    logs = self.mod.LOG_PATH.read_text()
+                    self.assertNotIn("suffix-canary-27182", logs)
+                    self.assertNotIn("beta gamma", logs)
+
+    def _protocol_error_detail(self, content: str, message: str, stream: bool) -> str:
+        """Проверить все выходы ошибки реального протокольного стенда."""
+        install_protocol_wrapper(
+            self, {"terminal": "failed", "error": {"message": message}}
+        )
+        payload = turn_request(stream)
+        payload["messages"][0]["content"] = content
+        status, body = bridge_request(self, payload)
+        self.assertEqual(status, 200 if stream else 502)
+        if stream:
+            self.assertTrue(body.endswith(b"data: [DONE]\n\n"))
+            frames = [
+                json.loads(line[6:])
+                for line in body.decode().splitlines()
+                if line.startswith("data: {")
+            ]
+            return next(
+                frame["error"]["detail"] for frame in frames if "error" in frame
+            )
+        return json.loads(body)["error"]["detail"]
+
+    def test_r2_long_reflected_message_redacted_before_clipping(self) -> None:
+        content = "private-owner-content-" + "Q" * 220
+        for stream in (False, True):
+            with self.subTest(stream=stream):
+                detail = self._protocol_error_detail(content, content, stream)
+                self.assertEqual(detail, "[REDACTED]")
+                combined = detail + self.mod.LOG_PATH.read_text()
+                self.assertNotIn("private-owner-content-", combined)
+                self.assertNotIn("Q" * 20, combined)
+
+    def test_r2_short_messages_preserve_error_words(self) -> None:
+        expected = "this turn failed upstream"
+        for stream in (False, True):
+            for content in ("hi", "e"):
+                with self.subTest(stream=stream, content=content):
+                    detail = self._protocol_error_detail(content, expected, stream)
+                    self.assertEqual(detail, expected)
+                    self.assertIn(expected, self.mod.LOG_PATH.read_text())
+
+    def test_quota_secrets_do_not_reach_any_error_sink(self) -> None:
+        samples = (
+            "api_key=canary_secret_val",
+            '{"token":"canary_secret_val"}',
+            "{'password': 'canary_secret_val'}",
+            'password="alpha beta gamma"',
+        )
+        for stream in (False, True):
+            for sample in samples:
+                with self.subTest(stream=stream, sample=sample):
+                    params = {
+                        "terminal": "failed",
+                        "error": {
+                            "kind": "quota",
+                            "message": sample,
+                            "quota": {
+                                "token": "canary_secret_val",
+                                "note": sample,
+                            },
+                        },
+                        "stderr": sample,
+                    }
+                    install_protocol_wrapper(self, params)
+                    status, body = bridge_request(self, turn_request(stream))
+                    self.assertEqual(status, 200 if stream else 502)
+                    logs = self.mod.LOG_PATH.read_text()
+                    for secret in ("canary_secret_val", "alpha beta gamma"):
+                        self.assertNotIn(secret, body.decode() + logs)
+                    self.assertIn("[REDACTED]", body.decode())
+                    self.assertIn("[REDACTED]", logs)
+        for key in (
+            "token",
+            "secret",
+            "password",
+            "api_key",
+            "bridge_key",
+            "authorization",
+        ):
+            quota = {"outer": [{key: "alpha beta gamma"}]}
+            install_protocol_wrapper(
+                self, {"terminal": "failed", "error": {"quota": quota}}
+            )
+            _, body = bridge_request(self, turn_request())
+            self.assertIn("[REDACTED]", body.decode())
+            self.assertNotIn(
+                "alpha beta gamma", body.decode() + self.mod.LOG_PATH.read_text()
+            )
+
+
+def install_protocol_wrapper(
+    scenario: Any, params: dict, noise: bool = False, delay: float = 0
+) -> None:
+    """Фейковый MSP с реальными pipes; фиксирует argv и входящие RPC."""
+    config = {
+        "params": params,
+        "noise": noise,
+        "delay": delay,
+        "root": str(scenario.tmp),
+    }
+    script = scenario.tmp / "protocol.py"
+    script.write_text(
+        """import json, sys, time
+from pathlib import Path
+config = json.loads(sys.argv[1])
+root = Path(config["root"])
+mode = sys.argv[2]
+(root / (mode + "-argv.json")).write_text(json.dumps(sys.argv[2:]))
+if mode == "exec":
+    print(json.dumps({"schema_version": 1, "payload_type": "run.terminal.completed", "payload": {"text": "fallback-ok"}}), flush=True)
+    sys.exit(0)
+for line in sys.stdin:
+    msg = json.loads(line)
+    with (root / "rpc.jsonl").open("a") as fh:
+        fh.write(json.dumps(msg) + "\\n")
+    if "id" not in msg:
+        continue
+    method = msg["method"]
+    result = {"session": {"sessionId": "sess-1"}} if method == "session/start" else {"status": "accepted", "turnId": "turn-1"} if method == "turn/start" else {}
+    print(json.dumps({"id": msg["id"], "result": result}), flush=True)
+    if method == "turn/start":
+        time.sleep(config["delay"])
+        if config["params"].get("approval"):
+            print(json.dumps({"jsonrpc": "2.0", "id": 99, "method": "approval/request", "params": {}}), flush=True)
+            break
+        print(json.dumps({"method": "item/completed", "params": {"item": {"itemId": "a", "turnId": "turn-1", "kind": "agentMessage", "text": "hello"}}}), flush=True)
+        print(json.dumps({"method": "turn/completed", "params": dict(config["params"], turnId="turn-1")}), flush=True)
+        if config["params"].get("stderr"):
+            print(config["params"]["stderr"], file=sys.stderr, flush=True)
+        if config["noise"]:
+            for i in range(12):
+                print("noise-%02d-" % i + "z" * 100, file=sys.stderr, flush=True)
+        break
+""",
+        encoding="utf-8",
+    )
+    import shlex
+
+    wrapper = scenario.tmp / "muse-cli.sh"
+    wrapper.write_text(
+        f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))} {shlex.quote(json.dumps(config))} "$@"\n'
+    )
+    wrapper.chmod(0o755)
+    scenario.mod.MUSE_WRAPPER = str(wrapper)
+
+
+class ServeTurnErrorExtractionTest(_BridgeScenario):
+    """AD-002: приоритет, защитный разбор и точные лимиты терминальной причины."""
+
+    def _execute(self, params: dict, noise: bool = False) -> dict:
+        install_protocol_wrapper(self, params, noise)
+        return self.mod.ServeRun(
+            "muse-spark-1.3", "p", "max", self.tmp / "workspace"
+        ).execute()
+
+    def test_r2_prompt_parts_redacted_before_and_after_normalization(self) -> None:
+        content = "private-owner-content-" + "Q" * 220
+        prompt = "User: " + content + "\n\nAssistant: prior\tprivate\nSystem: hi"
+        parts = self.mod._prompt_reflected_parts(prompt)
+        self.assertEqual(parts, sorted(parts, key=len, reverse=True))
+        self.assertIn(content, parts)
+        self.assertIn("prior\tprivate", parts)
+        self.assertNotIn("hi", parts)
+        for reflected in (content, "prior\tprivate", "prior private"):
+            with self.subTest(reflected=reflected):
+                diagnostic = self.mod._turn_diagnostics(
+                    {"error": {"message": reflected}}, prompt
+                )
+                self.assertEqual(diagnostic, ["[REDACTED]"])
+
+    def test_typed_error_reason_and_stderr_priority(self) -> None:
+        params = {
+            "terminal": "failed",
+            "error": {
+                "kind": "quota_exceeded",
+                "message": "daily limit",
+                "retryable": False,
+                "quota": {"remaining": 0},
+            },
+            "reason": "try tomorrow",
+        }
+        out = self._execute(params, True)
+        expected = 'quota_exceeded: daily limit retryable=False quota={"remaining":0}\nreason: try tomorrow'
+        self.assertTrue(out["err"].startswith(expected), out)
+        self.assertEqual((out["rc"], out["state"]), (1, "terminal_failed"))
+        self.assertLessEqual(len(out["err"]), 500)
+        for stream in (False, True):
+            with mock.patch.object(self.mod.ServeRun, "execute", return_value=out):
+                _, body = bridge_request(self, turn_request(stream))
+            self.assertIn("quota_exceeded", body.decode())
+            self.assertIn("try tomorrow", body.decode())
+        self.assertIn("try tomorrow", self.mod.LOG_PATH.read_text())
+
+    def test_reason_only_duplicate_and_malformed(self) -> None:
+        for error, reason, expected in [
+            (None, "cancelled by caller", "reason: cancelled by caller"),
+            ({"message": "same"}, "same", "same"),
+            ("raw failure", None, "raw failure"),
+            ({"kind": 123, "quota": [1, 2]}, None, "123"),
+            (["odd"], 17, "17"),
+        ]:
+            with self.subTest(error=error):
+                out = self._execute(
+                    {"terminal": "failed", "error": error, "reason": reason}
+                )
+                self.assertEqual(out["state"], "terminal_failed")
+                self.assertIn(expected, out["err"])
+                if reason == "same":
+                    self.assertEqual(out["err"].count("same"), 1)
+
+    def test_no_diagnostics_preserves_stderr_tail_and_success(self) -> None:
+        tail = "\n".join("noise-%02d-" % i + "z" * 100 for i in range(6, 12))
+        for terminal in ("failed", "completed"):
+            out = self._execute({"terminal": terminal}, True)
+            self.assertEqual(out["err"], tail)
+            self.assertEqual(
+                out["state"], "ok" if terminal == "completed" else "terminal_failed"
+            )
+
+    def test_field_caps_budget_and_redaction_boundaries(self) -> None:
+        for field, limit in (("kind", 64), ("message", 160), ("reason", 160)):
+            params: dict = {"terminal": "failed", "error": {}}
+            (params if field == "reason" else params["error"])[field] = "X" * (
+                limit + 20
+            )
+            out = self._execute(params)
+            self.assertIn("X" * limit, out["err"])
+            self.assertNotIn("X" * (limit + 1), out["err"])
+        out = self._execute(
+            {
+                "terminal": "failed",
+                "error": {
+                    "kind": "K" * 90,
+                    "message": "M" * 200,
+                    "retryable": True,
+                    "quota": {"data": "Q" * 200},
+                },
+                "reason": "R" * 200,
+            },
+            True,
+        )
+        diagnostic = out["err"].split("\nnoise-", 1)[0]
+        self.assertEqual(len(diagnostic), 300)
+        self.assertIn("K" * 64, diagnostic)
+        self.assertIn("R" * 16, diagnostic)
+        self.assertNotIn("quota=", diagnostic)
+        self.assertNotIn("\r", diagnostic)
+        out = self._execute(
+            {
+                "terminal": "failed",
+                "error": {"message": "m" * 155 + " api_key=canary_secret_val"},
+            }
+        )
+        self.assertNotIn("canary", out["err"])
+        self.assertNotIn("[REDAC", out["err"].replace("[REDACTED]", ""))
+
+
+class SseDataKeepaliveTest(_BridgeScenario):
+    """AD-003: S1/S2/S3 проверяют байты и события, без гонок очереди замка."""
+
+    def _handler(self, writer: Any = None) -> Any:
+        handler = self.mod.Handler.__new__(self.mod.Handler)
+        handler._wlock = threading.Lock()
+        handler.wfile = writer if writer is not None else io.BytesIO()
+        handler._sse_open = True
+        return handler
+
+    def test_defaults_and_s3_seal_suppresses_late_tick_and_duplicate_done(self) -> None:
+        handler = self._handler()
+        other = self._handler()
+        self.assertEqual(handler._sse_phase, "OPEN")
+        self.assertIsNone(handler._keepalive_stop)
+        self.assertFalse(handler._client_gone)
+        handler._keepalive_stop = threading.Event()
+        self.assertIsNone(other._keepalive_stop)
+        handler._sse_stop_keepalive()
+        before = handler.wfile.getvalue()
+        self.assertFalse(
+            handler._sse_emit(handler._sse_chunk({"content": ""}), keepalive=True)
+        )
+        self.assertEqual(handler.wfile.getvalue(), before)
+        handler._send_sse("muse-spark-1.3", "hello", [], 1, 1, 0)
+        final = handler.wfile.getvalue()
+        self.assertTrue(final.endswith(b"data: [DONE]\n\n"))
+        self.assertEqual(handler._sse_phase, "CLOSED")
+        self.assertFalse(
+            handler._sse_emit(handler._sse_chunk({"content": ""}), keepalive=True)
+        )
+        self.assertFalse(handler._sse_write("data: [DONE]\n\n"))
+        self.assertFalse(handler._sse_emit({"late": True}))
+        self.assertEqual(handler.wfile.getvalue(), final)
+
+    def test_s1_data_ticks_before_done_preserve_content_and_tools(self) -> None:
+        install_protocol_wrapper(self, {"terminal": "completed"}, delay=0.2)
+        self.mod.KEEPALIVE_S = 0.05
+        _, body = bridge_request(self, turn_request(True))
+        self.assertNotIn(b": keepalive", body)
+        self.assertTrue(body.endswith(b"data: [DONE]\n\n"))
+        self.assertEqual(body.count(b"data: [DONE]"), 1)
+        frames = [
+            json.loads(line[6:])
+            for line in body.decode().splitlines()
+            if line.startswith("data: {")
+        ]
+        deltas = [frame["choices"][0]["delta"] for frame in frames]
+        self.assertTrue(any(delta == {"content": ""} for delta in deltas))
+        self.assertTrue(
+            all(frame["object"] == "chat.completion.chunk" for frame in frames)
+        )
+        self.assertEqual("".join(d.get("content", "") for d in deltas), "hello")
+        tool_text = '<tool_call>{"name":"read","arguments":{"path":"a"}}</tool_call>'
+        content, tools = self.mod._split_tool_calls(["", tool_text, ""])
+        self.assertEqual(content, "")
+        self.assertEqual(tools[0]["function"]["name"], "read")
+        self.assertEqual(json.loads(tools[0]["function"]["arguments"]), {"path": "a"})
+
+    def test_s2_inflight_flush_precedes_finalization(self) -> None:
+        entered, release = threading.Event(), threading.Event()
+
+        class Writer(io.BytesIO):
+            def flush(self) -> None:
+                if not entered.is_set():
+                    entered.set()
+                    if not release.wait(5):
+                        raise OSError("тест не отпустил flush")
+
+        writer = Writer()
+        handler = self._handler(writer)
+        stop = threading.Event()
+        handler._keepalive_stop = stop
+        self.mod.KEEPALIVE_S = 0.01
+        ticker = threading.Thread(
+            target=handler._keepalive_loop, args=(stop,), daemon=True
+        )
+        handler._ka_thread = ticker
+        ticker.start()
+        self.addCleanup(release.set)
+        self.assertTrue(entered.wait(3))
+        finalizer = threading.Thread(
+            target=handler._send_sse,
+            args=("muse-spark-1.3", "hello", [], 1, 1, 0),
+            daemon=True,
+        )
+        finalizer.start()
+        try:
+            self.assertTrue(
+                stop.wait(3), "остановка не использует единый _keepalive_stop"
+            )
+            self.assertTrue(finalizer.is_alive())
+            self.assertNotIn(b"[DONE]", writer.getvalue())
+        finally:
+            release.set()
+            finalizer.join(5)
+            ticker.join(5)
+        self.assertFalse(finalizer.is_alive())
+        self.assertFalse(ticker.is_alive())
+        self.assertTrue(writer.getvalue().startswith(b"data: {"))
+        self.assertTrue(writer.getvalue().endswith(b"data: [DONE]\n\n"))
+
+    def test_done_write_failure_closes_phase(self) -> None:
+        class BrokenWriter(io.BytesIO):
+            def write(self, data: object) -> int:
+                raise OSError("closed peer")
+
+        handler = self._handler(BrokenWriter())
+        self.assertFalse(handler._sse_write("data: [DONE]\n\n"))
+        self.assertEqual(handler._sse_phase, "CLOSED")
+        self.assertTrue(handler._client_gone)
+
+
+class CliDisableFlagsAndApprovalFallbackTest(_BridgeScenario):
+    """AD-004: реальные argv фейка и неизменный approval fallback."""
+
+    def test_serve_argv_disables_write_shell(self) -> None:
+        install_protocol_wrapper(self, {"terminal": "completed"})
+        self.assertEqual(bridge_request(self, turn_request())[0], 200)
+        argv = json.loads((self.tmp / "serve-argv.json").read_text())
+        for flag in (
+            "--disable-write",
+            "--disable-shell",
+            "--provider",
+            "meta",
+            "--model",
+            "muse-spark-1.3",
+            "--no-session-log",
+            "--trust-workspace",
+        ):
+            self.assertIn(flag, argv)
+
+    def test_approval_falls_back_to_exec_without_decide(self) -> None:
+        install_protocol_wrapper(self, {"approval": True})
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertIn("fallback-ok", body.decode())
+        argv = json.loads((self.tmp / "exec-argv.json").read_text())
+        for flag in (
+            "--disable-write",
+            "--disable-shell",
+            "--disable-web-tools",
+            "--disable-reminders",
+            "--yolo",
+            "--provider",
+            "meta",
+            "--model",
+            "--reasoning-effort",
+            "--trust-workspace",
+            "--workspace",
+            "--json",
+            "--no-session-log",
+            "--prompt-file",
+        ):
+            self.assertIn(flag, argv)
+        self.assertNotIn("approval/decide", (self.tmp / "rpc.jsonl").read_text())
+        self.assertIn(
+            "serve unavailable (serve needs interaction (approval/request)), fallback exec",
+            self.mod.LOG_PATH.read_text(),
+        )
+
+
+class AllowedModelsSyncTest(_BridgeScenario):
+    """AD-005: модели доступны в конфигурации и обоих GET endpoints."""
+
+    def test_models_and_health_include_wonder_models(self) -> None:
+        models = ("muse-wonder-1.0", "muse-wonder-full-1.0")
+        for model in models:
+            self.assertEqual(
+                self.mod.ALLOWED_MODELS.get(model),
+                {"context_length": 1048576, "max_output": 131072},
+            )
+        for path in ("/health", "/v1/models"):
+            status, body = bridge_request(self, path=path)
+            self.assertEqual(status, 200)
+            for model in models:
+                self.assertIn(model, body.decode())
+
+
 if __name__ == "__main__":
     unittest.main(verbosity=2)
```

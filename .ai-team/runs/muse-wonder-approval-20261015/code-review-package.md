# Code Review Package — muse-wonder-approval-20261015

## 1. Metadata & Artifact Hashes
- **Task ID**: `muse-wonder-approval-20261015`
- **Criticality**: `S2` (`entry=full`, `parent_skill=analyst-teamlead`, downstream panel)
- **Architecture Spec**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md` (`sha256=1b66622035d122d2cf18c80df0ff54c3285830158478580ddd9942218429b8af`)
- **Architecture Packet**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/architecture-packet.json` (`sha256=9ddc18254368aa868db6bdff1df2fcb91426f87bc6c4fe90fd7be90f73b830c6`)
- **ARCH_PANEL Proof (Round r93)**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/panel/arch/r93/panel-proof.json` (`sha256=2b1dd4eda1dc88035de7eefbd26da43d9a3d1277491cdc93b409865a28294bb3`)
- **Coder Plan**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/plans/coder-01.json` (`sha256=7fe8e9b1ce146f4a113470cbefab645bb7a903ad7e172d4f480fd176a662d484`)
- **Coder Artifact**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/coder.json` (`sha256=03481d34d34d32d50780a283b5fbbacf49bedc51d7838d38f137b12bdb943963`)
- **Verifier Receipt**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/receipts/verifier-receipt.json` (`sha256=3dd50b49cc4e840ed6c120b6987830524123af8563efbfa91011c2a9b9713955`)
- **Modified Production File**: `/Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py` (`sha256=ce9fd9c8129924650f2d9f756ffd14a00c612871bc3bd7074d49e755c687f3cc`)
- **Modified Test File**: `/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_muse_bridge_killpg.py` (`sha256=5ca7da36922d396797ce96f68a54c9fa9f23557bbaec4f2b401b99214c50c3c7`)
- **Git Commits**:
  - Baseline REQ-MUSE-001: `9f87eb083545c0b6fdc5de0827ae50ae9b7c40b9` (`[agent] fix(muse-bridge): прунинг контекста Wonder 400k/320k/200k (REQ-MUSE-001, принятый базис)`)
  - Implementation REQ-MUSE-002/003/004: `4548dd30840e42fbba218f36cb0bb23ff81b660e` (`[agent] fix(muse-bridge): approval без рестарта хода, ретрай net-timeout, live reasoning (REQ-MUSE-002/003/004)`)

## 2. Requirements & Architecture Decisions Traceability Matrix
| Requirement / AD | Exact Implementation in `bridges/muse-bridge/server.py` | Unit Tests in `tests/test_muse_bridge_killpg.py` | Status |
|---|---|---|---|
| `REQ-MUSE-002` / `AD-001`: approvalMode `allowAll` on `session/start` (env `denyUnmatched` support via `AD-007`); structured audit logging of auto-approved choices | `ApprovalPolicy`, `ServeRun.execute`, `_log_approval_decision` | `ApprovalTest` (22 tests, including `test_t_a01`, `test_t_a14`, `test_t_a10`) | PASS |
| `REQ-MUSE-002` / `AD-002`: Handle in-turn `approval/request` without `ServeUnavailable`/exec restart: return receipt `result={}`, then `approval/decide` with `choiceId` from `availableChoices`; `userInput/request` -> `userInput/cancel`; latch terminal denials; 15s cancel grace | `ApprovalPolicy.decide`, `ServeRun._handle_approval_request`, `ServeRun._handle_user_input_request`, terminal latch | `ApprovalTest`: `test_t_a02_approval_in_turn_decides_without_exec`, `test_t_a08_error_codes_latch`, `test_t_a09b_cancel_grace`, `test_t_a13_terminal_latch` | PASS |
| `REQ-MUSE-002` / `AD-006`: Server `-32030` ceiling: log warning, fallback to single exec pre-turn, no second `session/start` or decide | `ServeRun._handle_session_start_error` | `ApprovalTest.test_t_a11_ceiling_fallback` | PASS |
| `REQ-MUSE-003` / `AD-003`: Transient net-timeout retry loop in `Handler`: pre-action boundary (before first byte of `turn/start`), max 2 retries, 2s/4s backoff + jitter; absolute deadline `D = t0 + min(TIMEOUT_S, 1800)`, `E = D - 35`, `W = D - 12`; single slot retained | `Handler._can_start`, `Handler.handle_request` retry loop, monotonic deadlines | `TransientRetryTest` (14 tests, including `test_t_r01`, `test_t_r06`, `test_t_r07`, `test_t_r08`, `test_t_r10`, `test_t_r11`, `test_t_r12`) | PASS |
| `REQ-MUSE-004` / `AD-004`: Live reasoning SSE sink: prefix-monotonic streaming of `summary.0` reasoning deltas, freeze on first delta index > 0 or `item/completed`, final reconciliation with full text `F`; single bounded `_sse_write` (timeout 3s) for all writers | `_live_reasoning_sink`, `_sse_write`, `_send_sse` | `LiveReasoningTest` (12 tests, including `test_t_l01`, `test_t_l06`, `test_t_l07`, `test_t_l08a_b_c`, `test_t_l09`) | PASS |
| `AD-005` (REQ-MUSE-001): Context pruning 400k/320k/200k, atomic tool pairs, single context retry | Inherited baseline in `server.py` | `ContextPruneTest`, `ContextRetryTest` (21 tests) | PASS |
| `F-001` (a4): Setup-approval latches `ACTION_POSSIBLE` before receipt | `ApprovalPolicy.on_approval_seen`, `ACTION_POSSIBLE` flag | `test_t_a16_setup_approval_barrier`, `test_t_r11_setup_retry_barrier` | PASS |
| `F-002` (a4): Absolute deadline `W` for all writers, frame limit `L = min(s+3, W)` | `_sse_write`, monotonic deadline check | `test_t_l08`, `test_t_l09`, `test_t_r12` | PASS |
| `F-004` (a4): Validate startup constants | `validate_startup_constants` | `test_startup_constants_validation` | PASS |
| `F-005` (a4): Slot quarantine on unconfirmed group death | `_quarantine_slot`, periodic recheck | `test_t_r03b_unconfirmed_death_quarantine_then_release`, `HealthQuarantinedTest` | PASS |

## 3. Complete Test Inventory (111 Tests in `tests/test_muse_bridge_killpg.py`)
All 111 tests passing (102.35s).
- `ApprovalTest`: 22 tests (T-A01..T-A16, codes, ceiling, denyUnmatched, item logging, canaries)
- `TransientRetryTest`: 14 tests (T-R01..T-R12, markers, budget, pre-action barrier, queue/deadline, quarantine)
- `LiveReasoningTest`: 12 tests (T-L01..T-L09, monotonic deltas, freeze, diverged reconciliation, bounded socket write)
- `CloseKillsGroupTest`, `HealthQuarantinedTest`, `DisconnectScenarioTest`, `ServeDisconnectScenarioTest`, `ClientGoneProbeTest`, `QuarantineSlotTest`, `ConcurrentCloseTest`, `WaitGroupExitTest`, `ErrorLoggingTest`, `ServeTurnErrorExtractionTest`, `SseDataKeepaliveTest`, `CliDisableFlagsAndApprovalFallbackTest`, `AllowedModelsSyncTest`, `ContextPruneTest`, `ContextRetryTest`: 63 tests.

## 4. Clean-Room L2 Verifier Summary
- `tests/test_muse_bridge_killpg.py`: 111 passed, 0 failed.
- Full `tests/` suite: 648 passed, 1 pre-existing failure (`test_b_guard.py tm018`, PASS_WITH_PREEXISTING).
- Code quality:
  - `ruff format --check`: 0 errors (all files formatted)
  - `ruff check`: 0 errors
  - `basedpyright`: 0 errors (1982 warnings, baseline 1448 warnings)
  - `git diff --check`: 0 whitespace/conflict errors
  - Scope: strictly `bridges/muse-bridge/server.py` and `tests/test_muse_bridge_killpg.py`.

## 5. Full Git Diff (`git diff 9f87eb0..HEAD`)
```diff
diff --git a/bridges/muse-bridge/server.py b/bridges/muse-bridge/server.py
index f961cd8..0bbb1ad 100644
--- a/bridges/muse-bridge/server.py
+++ b/bridges/muse-bridge/server.py
@@ -38,6 +38,7 @@ Keepalive: пустые data-чанки держат SSE-соединение, 
 
 from __future__ import annotations
 
+import hashlib
 import json
 import logging
 import os
@@ -137,6 +138,170 @@ _SIGNAL_RCS = (
 TERMINAL_EXIT_GRACE_S = 0.5
 SERVE_SPAWN_TIMEOUT_S = 30.0  # handshake+session/start должны уложиться сюда
 
+# --- REQ-MUSE-002/003/004 (пакет a4): approval, бюджеты, повторы, live ---
+APPROVAL_MODE = os.environ.get("MUSE_BRIDGE_APPROVAL_MODE", "allowAll").strip()
+TRANSIENT_RETRY_SCOPE = os.environ.get(
+    "MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE", "pre-action"
+).strip()
+FINISH_RESERVE_S = 35.0
+CLOSE_RESERVE_S = 12.0
+REQUEST_CAP_S = 1800.0
+MIN_ATTEMPT_REMAINING_S = float(os.environ.get("MUSE_BRIDGE_MIN_ATTEMPT_S", "120"))
+CONTROL_WRITE_TIMEOUT_S = 5.0
+LIVE_WRITE_TIMEOUT_S = 3.0
+APPROVAL_CANCEL_GRACE_S = 15.0
+MAX_APPROVAL_DECIDE = 10
+MAX_USER_INPUT_CANCEL = 3
+TRANSIENT_MAX_RETRIES = 2
+TRANSIENT_BACKOFF_S: tuple[float, float] = (2.0, 4.0)
+TRANSIENT_JITTER_S = 1.0
+TRANSIENT_MARKERS: tuple[str, ...] = (
+    "[net-timeout]",
+    "timed out waiting for response data",
+    NETWORK_RETRY_MARKER,
+    "transport_connect_unreachable",
+)
+NON_RETRYABLE_STATES = frozenset(
+    {"timeout", "spawn_failed", "launcher_missing", "client_gone"}
+)
+
+
+def _validate_startup_config() -> None:
+    """Невалидный env-режим или бюджет останавливают старт моста (AD-007)."""
+    if APPROVAL_MODE not in ("allowAll", "denyUnmatched"):
+        raise RuntimeError(f"MUSE_BRIDGE_APPROVAL_MODE invalid: {APPROVAL_MODE!r}")
+    if TRANSIENT_RETRY_SCOPE not in ("pre-action", "observed-items"):
+        raise RuntimeError(
+            f"MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE invalid: {TRANSIENT_RETRY_SCOPE!r}"
+        )
+    if TIMEOUT_S < FINISH_RESERVE_S + MIN_ATTEMPT_REMAINING_S:
+        raise RuntimeError(
+            "MUSE_BRIDGE_TIMEOUT_S too small: "
+            f"{TIMEOUT_S} < FINISH_RESERVE_S + MIN_ATTEMPT_REMAINING_S "
+            f"({FINISH_RESERVE_S + MIN_ATTEMPT_REMAINING_S})"
+        )
+
+
+_validate_startup_config()
+
+
+def _is_transient_text(*values: Any) -> bool:
+    """Классификация транзиента только по явным маркерам (§3.1 пакета)."""
+    for value in values:
+        if value is None:
+            continue
+        if isinstance(value, str):
+            text = value
+        elif isinstance(value, (list, tuple)):
+            if _is_transient_text(*value):
+                return True
+            continue
+        elif isinstance(value, dict):
+            text = " ".join(
+                str(value.get(key) or "") for key in ("kind", "message", "code")
+            )
+            if not text.strip():
+                text = str(value)
+        else:
+            text = str(value)
+        if any(marker in text for marker in TRANSIENT_MARKERS):
+            return True
+    return False
+
+
+_AUDIT_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
+_TOOL_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:/-]+$")
+
+
+def _render_audit_token(value: Any) -> str:
+    """Безопасный рендер свободной строки в аудит-лог (FU-009)."""
+    text = value if isinstance(value, str) else ""
+    if text and len(text) <= 64 and _AUDIT_TOKEN_RE.match(text):
+        return text
+    raw = text if isinstance(value, str) else str(value or "")
+    digest = hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:8]
+    return f"redacted(len={len(raw)},sha256={digest})"
+
+
+def _render_tool_token(value: Any) -> str:
+    """Рендер toolName в журнал инструментальных item (allowlist §4.3)."""
+    text = value if isinstance(value, str) else ""
+    if text and len(text) <= 64 and _TOOL_TOKEN_RE.match(text):
+        return text
+    return f"redacted(len={len(text)})"
+
+
+class ApprovalPolicy:
+    """Чистая политика решения по снимку approval (BND-001): без I/O.
+
+    Читает только разрешённые поля снимка; rawArgs и тела не трогает.
+    Выход: approve / deny (ветка деградации) / fail_turn + аудит-строка.
+    """
+
+    def __init__(self, mode: str) -> None:
+        self.mode = mode
+
+    @staticmethod
+    def _choices(params: dict[str, Any]) -> list[dict[str, Any]]:
+        raw = params.get("availableChoices")
+        if not isinstance(raw, list):
+            return []
+        return [c for c in raw if isinstance(c, dict)]
+
+    @staticmethod
+    def deny_choice(params: dict[str, Any] | None) -> dict[str, Any] | None:
+        if not params:
+            return None
+        for choice in ApprovalPolicy._choices(params):
+            if choice.get("decision") in ("abort", "denied"):
+                return choice
+        return None
+
+    def evaluate(self, params: dict[str, Any]) -> dict[str, Any]:
+        choices = self._choices(params)
+        approve = next(
+            (c for c in choices if c.get("decision") == "approved"), None
+        ) or next(
+            (c for c in choices if c.get("decision") == "approvedForSession"), None
+        )
+        deny = self.deny_choice(params)
+        action = "fail_turn"
+        chosen: dict[str, Any] | None = None
+        if self.mode == "allowAll" and approve is not None:
+            action, chosen = "approve", approve
+        elif deny is not None:
+            action, chosen = "deny", deny
+        subject = (
+            params.get("subject") if isinstance(params.get("subject"), dict) else {}
+        )
+        choice_ids = ",".join(
+            _render_audit_token(c.get("choiceId")) for c in choices[:8]
+        )
+        audit = (
+            "approval_decide "
+            f"tool={_render_audit_token(params.get('toolName'))} "
+            f"subject={_render_audit_token(subject.get('kind'))} "
+            f"protected={1 if params.get('protectedWrite') else 0} "
+            f"judge={1 if params.get('judgeEscalated') else 0} "
+            f"choices=[{choice_ids}] "
+            f"chosen={_render_audit_token(chosen.get('choiceId')) if chosen else 'none'} "
+            f"decision={_render_audit_token(chosen.get('decision')) if chosen else 'none'}"
+        )
+        return {
+            "action": action,
+            "choice_id": chosen.get("choiceId") if chosen else None,
+            "decision": chosen.get("decision") if chosen else None,
+            "audit": audit,
+        }
+
+    def evaluate_user_input(self, params: dict[str, Any]) -> dict[str, Any]:
+        return {
+            "action": "cancel_user_input",
+            "audit": (
+                f"user_input_cancel tool={_render_audit_token(params.get('toolName'))}"
+            ),
+        }
+
 
 class ServeUnavailable(Exception):
     """Транспорт serve недоступен -> тихий fallback на exec. Не ошибка запроса."""
@@ -1332,6 +1497,11 @@ class Run:
         self.dead_confirmed = (
             True  # False — группа не подтверждена мёртвой (карантин слота)
         )
+        # Барьеры AD-003: exec защёлкивает ACTION_POSSIBLE при старте процесса.
+        self.action_possible = False
+        self.approval_seen = False
+        self.observed_barrier = False
+        self.exec_deadline = float("inf")
 
     def close(self) -> None:
         """Убить группу процессов хода и коротко дождаться её ухода.
@@ -1438,6 +1608,7 @@ class Run:
                     "err": f"spawn failed: {exc}",
                     "state": "spawn_failed",
                 }
+            self.action_possible = True
 
             def drain_stderr() -> None:
                 try:
@@ -1453,8 +1624,11 @@ class Run:
             err_thread.start()
 
             # Жёсткий дедлайн: таймер убивает процесс, даже если stdout молчит.
+            _remain = self.exec_deadline - time.monotonic()
+            _timer_s = min(TIMEOUT_S, _remain) if _remain != float("inf") else TIMEOUT_S
             timer = threading.Timer(
-                TIMEOUT_S, lambda: (err_lines.append("bridge timeout"), self.close())
+                max(0.05, _timer_s),
+                lambda: (err_lines.append("bridge timeout"), self.close()),
             )
             timer.daemon = True
             timer.start()
@@ -1556,25 +1730,29 @@ class Run:
             "err": "\n".join(err_lines[-6:]),
             "state": state,
             "hard_threshold": _has_hard_threshold_marker(err_lines, reason),
+            "action_possible": self.action_possible,
+            "approval_seen": False,
+            "observed_barrier": bool(text),
+            "transient": state != "ok" and _is_transient_text(err_lines, reason),
         }
 
 
 class ServeRun:
     """Один запрос через `muse serve` (MSP v1 по stdio, NDJSON JSON-RPC).
 
-    Поток (проверен офлайн на echo-провайдере 05.10.2026): initialize ->
-    notify initialized -> session/start (без approvalMode: любое явное
-    значение режектится startup ceiling; провайдер meta)
-    провайдер meta) -> turn/start (reasoningEffort=тир) -> ждём turn/completed.
+    Поток: initialize -> notify initialized -> session/start
+    (approvalMode из AD-001/AD-007; провайдер meta) -> turn/start
+    (reasoningEffort=тир) -> ждём turn/completed; остаточные
+    approval/userInput обрабатывает ApprovalPolicy в том же ходе (AD-002).
     Текст — из agentMessage (item/completed.text, fallback — item/delta);
     reasoning summaries — из reasoning-item (summary[] + item/delta
     field "summary.N"); токены — из session/tokenUsage (reasoningTokens
     включительно). Сырой reasoning-текст в v1 не стримится (только
     summaries) — ограничение протокола, не моста.
 
-    Любая транспортная неполадка (спавн, handshake, таймаут, интерактивный
-    запрос approval/userInput, JSON-RPC error) -> ServeUnavailable, и
-    вызывающий код тихо идёт на exec. Ошибка самой модели
+    Транспортная неполадка до ACTION_POSSIBLE -> ServeUnavailable;
+    допуск exec-fallback решает единый предикат Handler (AD-003).
+    Ошибка самой модели
     (terminal != completed) — НЕ ServeUnavailable: ход реально выполнен,
     fallback лишь удвоил бы вызов.
     """
@@ -1595,6 +1773,26 @@ class ServeRun:
         # Запись в stdin serve ограничена дедлайном (ставится в execute): зависший читатель
         # не держит слот бессрочно, при истечении ход завершается, группа убивается.
         self._write_until = float("inf")
+        # Барьеры и состояние approval/повторов (AD-002/AD-003, пакет a4).
+        self.approval_seen = False
+        self.action_possible = False
+        self.allowing_decide_attempted = False
+        self.approval_degraded = False
+        self.degraded_at: float | None = None
+        self.grace_end: float | None = None
+        self.observed_barrier = False
+        self.tool_item_count = 0
+        self.decide_count = 0
+        self.user_input_cancel_count = 0
+        self.ceiling_seen = False
+        self.server_version = "?"
+        self.last_error_text = ""
+        self.live_sink: Any = None
+        self.exec_deadline = float("inf")
+        self.write_deadline = float("inf")
+        self.request_deadline = float("inf")
+        self.turn_started_at: float | None = None
+        self._live_frozen = False
 
     def close(self) -> None:
         """Убить группу процессов хода и коротко дождаться её ухода (идемпотентно)."""
@@ -1603,23 +1801,24 @@ class ServeRun:
             return
         _terminate_run(self, (proc.stdin, proc.stdout, proc.stderr))
 
-    def _send(
-        self, method: str, params: dict | None = None, notify: bool = False
-    ) -> int:
+    def _control_limit(self) -> float:
+        limit = min(
+            self._write_until,
+            time.monotonic() + CONTROL_WRITE_TIMEOUT_S,
+            self.exec_deadline,
+        )
+        if self.grace_end is not None:
+            limit = min(limit, self.grace_end)
+        return limit
+
+    def _write_bytes(self, data: bytes, limit: float) -> None:
         assert self.proc is not None and self.proc.stdin is not None
-        self._rid += 1
-        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
-        if not notify:
-            msg["id"] = self._rid
-        if params is not None:
-            msg["params"] = params
-        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
         try:
             fd = self.proc.stdin.fileno()
             view = memoryview(data)
             sent = 0
             while sent < len(data):
-                remaining = self._write_until - time.time()
+                remaining = limit - time.monotonic()
                 if remaining <= 0:
                     raise ServeUnavailable(
                         "serve stdin write timed out: child does not read"
@@ -1631,10 +1830,40 @@ class ServeRun:
                     sent += os.write(fd, view[sent:])
                 except BlockingIOError:
                     continue
+        except ServeUnavailable:
+            raise
         except (OSError, ValueError) as exc:
             raise ServeUnavailable(f"stdio write failed: {exc}")
+
+    def _send(
+        self,
+        method: str,
+        params: dict | None = None,
+        notify: bool = False,
+        *,
+        control: bool = False,
+    ) -> int:
+        self._rid += 1
+        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
+        if not notify:
+            msg["id"] = self._rid
+        if params is not None:
+            msg["params"] = params
+        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
+        self._write_bytes(data, self._control_limit() if control else self._write_until)
         return self._rid
 
+    def _send_response(self, server_id: Any, result: dict) -> None:
+        """Receipt по серверному id дословно (AD-002)."""
+        msg: dict[str, Any] = {"jsonrpc": "2.0", "id": server_id, "result": result}
+        data = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
+        self._write_bytes(data, self._control_limit())
+
+    def _note_allowing_decide(self) -> None:
+        """Защёлкивание ДО первой попытки записи разрешающего decide (a4)."""
+        self.allowing_decide_attempted = True
+        self.action_possible = True
+
     def execute(self) -> dict[str, Any]:
         if not os.access(MUSE_WRAPPER, os.X_OK):
             raise ServeUnavailable(f"muse wrapper not executable: {MUSE_WRAPPER}")
@@ -1693,8 +1922,16 @@ class ServeRun:
 
         err_thread = threading.Thread(target=drain_stderr, daemon=True)
         err_thread.start()
-        deadline = time.time() + TIMEOUT_S
-        setup_deadline = time.time() + SERVE_SPAWN_TIMEOUT_S
+        _now0 = time.monotonic()
+        _exec_dl = self.exec_deadline
+        deadline = (
+            min(_now0 + TIMEOUT_S, _exec_dl)
+            if _exec_dl != float("inf")
+            else _now0 + TIMEOUT_S
+        )
+        if self.exec_deadline == float("inf"):
+            self.exec_deadline = deadline
+        setup_deadline = min(_now0 + SERVE_SPAWN_TIMEOUT_S, deadline)
         self._write_until = setup_deadline
 
         # Чтение stdout serve — собственным буфером поверх os.read: select по fd не видит строки,
@@ -1702,12 +1939,15 @@ class ServeRun:
         rbuf = bytearray()
 
         def read_msg(timeout_at: float) -> dict[str, Any]:
-            while time.time() < min(timeout_at, deadline):
+            while time.monotonic() < timeout_at:
                 if self.proc is None or self.proc.stdout is None:
                     raise ServeUnavailable("serve stdout closed")
                 newline = rbuf.find(b"\n")
                 if newline < 0:
-                    ready, _, _ = select.select([self.proc.stdout], [], [], 0.5)
+                    _remain = max(0.0, timeout_at - time.monotonic())
+                    ready, _, _ = select.select(
+                        [self.proc.stdout], [], [], min(0.5, _remain)
+                    )
                     if not ready:
                         if self.proc.poll() is not None:
                             raise ServeUnavailable(
@@ -1735,16 +1975,6 @@ class ServeRun:
                     return msg
             raise ServeUnavailable("serve read timeout")
 
-        def await_result(rid: int, timeout_at: float) -> dict[str, Any]:
-            while True:
-                msg = read_msg(timeout_at)
-                if isinstance(msg, dict) and msg.get("id") == rid:
-                    if "error" in msg:
-                        raise ServeUnavailable(f"serve RPC error: {msg['error']}")
-                    result = msg.get("result")
-                    return result if isinstance(result, dict) else {}
-                self._handle_event(msg, None)
-
         kinds: dict[str, str] = {}
         deltas: list[str] = []
         summary_parts: dict[int, str] = {}
@@ -1753,13 +1983,223 @@ class ServeRun:
         usage: dict[str, Any] = {}
         turn_id: str | None = None
         session_id: str | None = None
+        pending: dict[int, str] = {}
+        seen_pairs: set[tuple[str, str]] = set()
+        tool_item_ids: set[str] = set()
+        last_snapshot: list[dict[str, Any]] = []
+        transient_terminal = [False]
+        first_summary_logged = [False]
+
+        def _pair_key(params: dict[str, Any]) -> tuple[str, str]:
+            return (
+                str(params.get("approvalId") or ""),
+                json.dumps(
+                    params.get("currentRequirementId"),
+                    ensure_ascii=False,
+                    sort_keys=True,
+                    default=str,
+                ),
+            )
+
+        def _send_decide(
+            snapshot: dict[str, Any], choice: dict[str, Any], *, allowing: bool
+        ) -> None:
+            if allowing:
+                self._note_allowing_decide()
+            self.decide_count += 1
+            rid = self._send(
+                "approval/decide",
+                {
+                    "approvalId": snapshot.get("approvalId"),
+                    "choiceId": choice.get("choiceId"),
+                    "commandId": _uuid7(),
+                    "requirementId": snapshot.get("currentRequirementId"),
+                    "sessionId": snapshot.get("sessionId") or session_id or "",
+                },
+                control=True,
+            )
+            pending[rid] = "decide"
+
+        def _latch_degradation(
+            reason: str, snapshot: dict[str, Any] | None = None
+        ) -> None:
+            if self.approval_degraded:
+                return
+            self.approval_degraded = True
+            now = time.monotonic()
+            self.degraded_at = now
+            grace_end = now + APPROVAL_CANCEL_GRACE_S
+            if self.write_deadline != float("inf"):
+                grace_end = min(
+                    grace_end, self.write_deadline - 2 * LIVE_WRITE_TIMEOUT_S
+                )
+            self.grace_end = grace_end
+            _log(
+                f"approval_degraded reason={reason} approval_seen={int(self.approval_seen)} "
+                f"action_possible={int(self.action_possible)} "
+                f"barrier={int(self.observed_barrier)} tool_items={self.tool_item_count} "
+                f"grace_s={max(0.0, grace_end - now):.2f}"
+            )
+            snap = (
+                snapshot
+                if snapshot is not None
+                else (last_snapshot[0] if last_snapshot else None)
+            )
+            try:
+                deny = ApprovalPolicy.deny_choice(snap)
+                if deny is not None and self.decide_count < MAX_APPROVAL_DECIDE:
+                    _send_decide(snap or {}, deny, allowing=False)
+                elif turn_id:
+                    rid = self._send(
+                        "turn/cancel",
+                        {
+                            "commandId": _uuid7(),
+                            "sessionId": session_id or "",
+                            "turnId": turn_id,
+                        },
+                        control=True,
+                    )
+                    pending[rid] = "turn_cancel"
+            except ServeUnavailable as exc:
+                _log(f"approval degrade command failed: {exc}")
+
+        def _handle_ack(msg: dict[str, Any]) -> None:
+            raw_id = msg.get("id")
+            if not isinstance(raw_id, int):
+                return
+            kind = pending.pop(raw_id, None)
+            if kind is None:
+                return
+            if "error" in msg:
+                err = msg.get("error") if isinstance(msg.get("error"), dict) else {}
+                code = err.get("code")
+                if kind == "decide" and code == -32051:
+                    _log("approval decide benign -32051 already resolved")
+                    return
+                if kind in ("decide", "user_cancel"):
+                    _latch_degradation(f"{kind}_error_{code}")
+                return
+            result = msg.get("result") if isinstance(msg.get("result"), dict) else {}
+            if result.get("terminal") is False:
+                _log("approval decide terminal=false awaiting updated request")
+
+        def await_result(rid: int, timeout_at: float) -> dict[str, Any]:
+            while True:
+                msg = read_msg(timeout_at)
+                if "method" in msg:
+                    self._handle_event(msg, None)
+                    continue
+                if isinstance(msg, dict) and msg.get("id") == rid:
+                    if "error" in msg:
+                        err = msg["error"]
+                        if isinstance(err, dict) and err.get("code") == -32030:
+                            self.ceiling_seen = True
+                            _log(
+                                f"serve approval ceiling -32030 version={self.server_version} "
+                                "warning approvalMode not applied"
+                            )
+                        self.last_error_text = str(err)
+                        raise ServeUnavailable(f"serve RPC error: {err}")
+                    result = msg.get("result")
+                    return result if isinstance(result, dict) else {}
+                _handle_ack(msg)
 
         def _handle_event(msg: dict[str, Any], _unused: Any) -> None:
             nonlocal final_text
             method = msg.get("method")
-            params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
-            if method in ("approval/request", "userInput/request"):
-                raise ServeUnavailable(f"serve needs interaction ({method})")
+            _raw_params = msg.get("params")
+            params: dict[str, Any] = (
+                _raw_params if isinstance(_raw_params, dict) else {}
+            )
+            if method in (
+                "approval/request",
+                "approval/requested",
+                "userInput/request",
+            ):
+                # a4: защёлки ДО receipt/дедупликации/политики, включая setup.
+                self.approval_seen = True
+                self.action_possible = True
+                self.observed_barrier = True
+                if self.approval_degraded:
+                    _log(f"approval after degraded ignored method={method}")
+                    return
+                server_id = msg.get("id")
+                try:
+                    if server_id is not None:
+                        self._send_response(server_id, {})
+                except ServeUnavailable:
+                    _latch_degradation("receipt_write_failed", params)
+                    return
+                if method == "userInput/request":
+                    last_snapshot[:] = [params]
+                    policy = ApprovalPolicy(APPROVAL_MODE)
+                    _log(policy.evaluate_user_input(params)["audit"])
+                    if self.user_input_cancel_count >= MAX_USER_INPUT_CANCEL:
+                        _latch_degradation("user_input_limit", params)
+                        return
+                    self.user_input_cancel_count += 1
+                    try:
+                        rid = self._send(
+                            "userInput/cancel",
+                            {
+                                "commandId": _uuid7(),
+                                "sessionId": params.get("sessionId")
+                                or session_id
+                                or "",
+                                "userInputId": params.get("userInputId"),
+                            },
+                            control=True,
+                        )
+                        pending[rid] = "user_cancel"
+                    except ServeUnavailable:
+                        _latch_degradation("user_input_write_failed", params)
+                    return
+                pair = _pair_key(params)
+                if pair in seen_pairs:
+                    _log("approval duplicate suppressed")
+                    return
+                seen_pairs.add(pair)
+                last_snapshot[:] = [params]
+                if self.decide_count >= MAX_APPROVAL_DECIDE:
+                    _latch_degradation("decide_limit", params)
+                    return
+                verdict = ApprovalPolicy(APPROVAL_MODE).evaluate(params)
+                _log(f"{verdict['audit']} n={self.decide_count + 1}")
+                if verdict["action"] == "approve":
+                    choice = next(
+                        (
+                            c
+                            for c in ApprovalPolicy._choices(params)
+                            if c.get("choiceId") == verdict["choice_id"]
+                        ),
+                        {"choiceId": verdict["choice_id"]},
+                    )
+                    try:
+                        _send_decide(params, choice, allowing=True)
+                    except ServeUnavailable:
+                        _latch_degradation("decide_write_failed", params)
+                elif verdict["action"] == "deny":
+                    _latch_degradation("no_approve_choice", params)
+                else:
+                    _latch_degradation("no_choice", params)
+                return
+            if method == "turn/modelRetryScheduled":
+                _log(
+                    "turn modelRetryScheduled "
+                    f"attempt={params.get('attempt')} maxAttempts={params.get('maxAttempts')} "
+                    f"retryDelayMs={params.get('retryDelayMs')} "
+                    f"errorKind={_render_audit_token(params.get('errorKind'))}"
+                )
+                return
+            if method in (
+                "approval/updated",
+                "approval/resolved",
+                "session/approvalModeChanged",
+                "userInput/settled",
+            ):
+                if method == "approval/resolved":
+                    _log("approval resolved")
+                return
             if method in ("item/started", "item/completed"):
                 raw_item = params.get("item")
                 item: dict[str, Any] = raw_item if isinstance(raw_item, dict) else {}
@@ -1767,6 +2207,17 @@ class ServeRun:
                 kind = str(item.get("kind") or "")
                 if iid:
                     kinds[iid] = kind
+                if kind and kind not in ("reasoning", "agentMessage"):
+                    self.observed_barrier = True
+                    if iid:
+                        tool_item_ids.add(iid)
+                        self.tool_item_count = len(tool_item_ids)
+                    _log(
+                        f"tool_item kind={_render_tool_token(kind)} "
+                        f"tool={_render_tool_token(item.get('toolName'))}"
+                    )
+                if method == "item/completed" and kind == "reasoning":
+                    self._live_frozen = True
                 if (
                     method == "item/completed"
                     and turn_id is not None
@@ -1789,7 +2240,23 @@ class ServeRun:
                         idx = int(field.split(".", 1)[1])
                     except (IndexError, ValueError):
                         idx = len(summary_parts)
+                    if not first_summary_logged[0]:
+                        first_summary_logged[0] = True
+                        _t0 = self.turn_started_at or _now0
+                        _log(
+                            f"first summary delta idx={idx} "
+                            f"after_s={time.monotonic() - _t0:.2f}"
+                        )
                     summary_parts[idx] = summary_parts.get(idx, "") + piece
+                    if idx > 0:
+                        self._live_frozen = True
+                    elif not self._live_frozen and self.live_sink is not None:
+                        try:
+                            delivered = bool(self.live_sink(summary_parts.get(0, "")))
+                        except Exception:  # noqa: BLE001, S112
+                            delivered = False
+                        if not delivered:
+                            self._live_frozen = True
                 elif (
                     kinds.get(iid, "agentMessage") == "agentMessage" and field == "text"
                 ):
@@ -1807,10 +2274,18 @@ class ServeRun:
             )
             init = await_result(init_rid, setup_deadline)
             schema = init.get("schema") if isinstance(init.get("schema"), dict) else {}
+            _srv = (
+                init.get("serverInfo")
+                if isinstance(init.get("serverInfo"), dict)
+                else {}
+            )
+            self.server_version = str(_srv.get("version") or "?")
             _log(
-                f"serve init server={init.get('serverInfo', {}).get('version') if isinstance(init.get('serverInfo'), dict) else '?'} "
+                f"serve init server={self.server_version} "
                 f"schema_fp={str(schema.get('fingerprint', ''))[:19]}"
             )
+            if self.approval_degraded:
+                raise ServeUnavailable("serve approval degraded during setup")
             self._send("initialized", {}, notify=True)
             sess_rid = self._send(
                 "session/start",
@@ -1819,14 +2294,9 @@ class ServeRun:
                     "workspaceRoot": str(self.workdir),
                     "providerId": "meta",
                     "modelId": self.model_id,
+                    "approvalMode": APPROVAL_MODE,
                 },
             )
-            # approvalMode намеренно НЕ передаём: любое явное значение
-            # (allowAll, onRequest) отвергается sealed startup ceiling
-            # неинтерактивного serve (commandRejected/approval_mode_ceiling),
-            # а без ключа сервер назначает свой дефолт (promptUnmatched — так
-            # было в офлайн-пробе на echo). Запрос approval/userInput по ходу
-            # хода ведёт в ServeUnavailable -> fallback на exec.
             sess = await_result(sess_rid, setup_deadline)
             session = (
                 sess.get("session") if isinstance(sess.get("session"), dict) else {}
@@ -1834,7 +2304,19 @@ class ServeRun:
             session_id = str(session.get("sessionId") or "")
             if not session_id:
                 raise ServeUnavailable("session/start gave no sessionId")
+            _eff = session.get("approvalMode")
+            if isinstance(_eff, dict):
+                _eff_mode = str(_eff.get("mode") or APPROVAL_MODE)
+            elif isinstance(_eff, str) and _eff:
+                _eff_mode = _eff
+            else:
+                _eff_mode = APPROVAL_MODE
+            _log(f"serve session approvalMode={_eff_mode}")
+            if self.approval_degraded:
+                raise ServeUnavailable("serve approval degraded during setup")
             tier = _MSP_EFFORT.get(self.effort, "max")
+            # ACTION_POSSIBLE защёлкивается ДО первого байта turn/start (a3/a4).
+            self.action_possible = True
             turn_rid = self._send(
                 "turn/start",
                 {
@@ -1844,6 +2326,8 @@ class ServeRun:
                     "input": [{"type": "text", "text": self.prompt}],
                 },
             )
+            self._write_until = deadline
+            self.turn_started_at = time.monotonic()
             turn = await_result(turn_rid, setup_deadline)
             if turn.get("status") != "accepted":
                 raise ServeUnavailable(f"turn/start not accepted: {turn}")
@@ -1853,11 +2337,22 @@ class ServeRun:
             )
             terminal: str | None = None
             hard_threshold = False
-            while time.time() < deadline:
-                # Смерть serve здесь не проверяется: события и completed, уже лежащие в буфере
-                # чтения или pipe, разбираются первыми; read_msg сам поднимет ServeUnavailable
-                # на EOF/выходе процесса, когда разбирать больше нечего.
-                msg = read_msg(deadline)
+            while True:
+                _limit = (
+                    self.grace_end
+                    if self.approval_degraded and self.grace_end is not None
+                    else deadline
+                )
+                if time.monotonic() >= _limit:
+                    if self.approval_degraded:
+                        break
+                    raise ServeUnavailable("serve turn deadline exceeded")
+                try:
+                    msg = read_msg(_limit)
+                except ServeUnavailable:
+                    if self.approval_degraded:
+                        break  # EOF после cancel — подтверждение уборки
+                    raise
                 if msg.get("method") == "turn/completed" and isinstance(
                     msg.get("params"), dict
                 ):
@@ -1866,17 +2361,52 @@ class ServeRun:
                         _handle_event(msg, None)
                         continue
                     terminal = str(p.get("terminal") or "unknown")
+                    if isinstance(p.get("usage"), dict):
+                        usage.update(p["usage"])  # type: ignore[arg-type]
                     if terminal != "completed":
                         hard_threshold = _has_hard_threshold_marker(
                             p.get("error"), p.get("reason")
                         )
                         turn_diag_lines = _turn_diagnostics(p, self.prompt)
+                        _err_raw = p.get("error")
+                        transient_terminal[0] = _is_transient_text(
+                            _err_raw, p.get("reason")
+                        )
+                        if transient_terminal[0]:
+                            _log(
+                                "transient_terminal "
+                                f"ttft={1 if p.get('timeToFirstTokenMs') is not None else 0} "
+                                f"usage={1 if usage else 0} "
+                                f"tool_items={self.tool_item_count}"
+                            )
                     break
-                if "id" in msg and ("result" in msg or "error" in msg):
-                    continue  # чужой/дублированный ack — игнор, не разрываем ход
+                if "method" not in msg and ("result" in msg or "error" in msg):
+                    _handle_ack(msg)
+                    continue
                 _handle_event(msg, None)
-            else:
-                raise ServeUnavailable("serve turn deadline exceeded")
+            flags: dict[str, Any] = {
+                "action_possible": self.action_possible,
+                "approval_seen": self.approval_seen,
+                "approval_degraded": self.approval_degraded,
+                "allowing_decide": self.allowing_decide_attempted,
+                "observed_barrier": self.observed_barrier,
+                "tool_items": self.tool_item_count,
+                "transient": bool(transient_terminal[0]),
+            }
+            if self.approval_degraded:
+                _log(f"serve turn degraded outcome tool_items={self.tool_item_count}")
+                return {
+                    "rc": 1,
+                    "text": "",
+                    "chunks": [],
+                    "err": "approval_degraded",
+                    "state": "terminal_failed",
+                    "summaries": [],
+                    "usage": usage,
+                    "via": "serve",
+                    "hard_threshold": False,
+                    **flags,
+                }
             serve_rc: int | None = None
             if terminal == "completed":
                 # D-A3-1: после completed — тот же грейс, что у exec: serve вышел сам с rc != 0 ->
@@ -1894,6 +2424,8 @@ class ServeRun:
                 if part not in summaries:
                     summaries.append(part)
             text = final_text if final_text is not None else "".join(deltas)
+            if terminal != "completed":
+                self.close()
             # Прежнее ожидание drain_stderr переносится до снимка: шум после terminal
             # не теряется; приоритетный носитель не зависит от хвоста сборщика.
             err_thread.join(timeout=5)
@@ -1919,6 +2451,7 @@ class ServeRun:
                     "usage": usage,
                     "via": "serve",
                     "hard_threshold": hard_threshold,
+                    **flags,
                 }
             if terminal != "completed":
                 return {
@@ -1931,6 +2464,7 @@ class ServeRun:
                     "usage": usage,
                     "via": "serve",
                     "hard_threshold": hard_threshold,
+                    **flags,
                 }
             return {
                 "rc": 0,
@@ -1941,11 +2475,13 @@ class ServeRun:
                 "summaries": summaries,
                 "usage": usage,
                 "via": "serve",
+                "hard_threshold": hard_threshold,
+                **flags,
             }
         finally:
-            if not stderr_joined:
-                err_thread.join(timeout=5)
             self.close()
+            if not stderr_joined:
+                err_thread.join(timeout=1)
 
 
 class Handler(BaseHTTPRequestHandler):
@@ -1971,6 +2507,12 @@ class Handler(BaseHTTPRequestHandler):
     _sse_phase: str = "OPEN"
     _keepalive_stop: threading.Event | None = None
     _ka_thread: threading.Thread | None = None
+    _live_sent_text: str = ""
+    _write_deadline: float = float("inf")
+    _exec_deadline: float = float("inf")
+    _request_deadline: float = float("inf")
+    _delivery_failed: bool = False
+    _req_done: threading.Event | None = None
 
     def setup(self) -> None:
         # Состояние обрыва клиента и ссылка на текущий ход — на каждое соединение.
@@ -1986,36 +2528,88 @@ class Handler(BaseHTTPRequestHandler):
             self._sse_phase = "OPEN"
         self._keepalive_stop: threading.Event | None = None
         self._ka_thread: threading.Thread | None = None
+        self._live_sent_text = ""
+        self._write_deadline = float("inf")
+        self._exec_deadline = float("inf")
+        self._request_deadline = float("inf")
+        self._delivery_failed = False
+        self._req_done = None
         super().setup()
 
     # ---- ранний SSE: заголовки сразу, keepalive во время хода ---------------------
-    def _sse_write(self, text: str, *, keepalive: bool = False) -> bool:
-        """Запись кадра SSE под замком (keepalive и выдача из разных потоков)."""
+    def _sse_write(
+        self, text: str, *, keepalive: bool = False, mark_content: bool = False
+    ) -> bool:
+        """Один ограниченный бюджет L=min(s+LIVE_WRITE_TIMEOUT_S, W) (AD-004).
+
+        Ожидание замка, запись и flush делят единый остаток; исчерпание =
+        зависший клиент (client_gone + killpg). Действует на всех писателей.
+        """
+        started = time.monotonic()
+        w_deadline = getattr(self, "_write_deadline", float("inf"))
+        limit = min(started + LIVE_WRITE_TIMEOUT_S, w_deadline)
+        if limit <= started:
+            if not self._client_gone:
+                self._client_gone = True
+                self._delivery_failed = True
+                _log("delivery_deadline write budget exhausted before frame")
+                self._kill_current_run()
+            return False
+        if not self._wlock.acquire(timeout=max(0.0, limit - time.monotonic())):
+            if not self._client_gone:
+                self._client_gone = True
+                self._delivery_failed = True
+                _log("client gone mid-stream (sse lock wait budget)")
+                self._kill_current_run()
+            return False
         try:
-            with self._wlock:
-                if self._sse_phase == "CLOSED" or self._client_gone:
-                    return False
-                if keepalive and (
-                    self._sse_phase != "OPEN"
-                    or (
-                        self._keepalive_stop is not None
-                        and self._keepalive_stop.is_set()
-                    )
-                ):
-                    return False
+            if self._sse_phase == "CLOSED" or self._client_gone:
+                return False
+            if keepalive and (
+                self._sse_phase != "OPEN"
+                or (self._keepalive_stop is not None and self._keepalive_stop.is_set())
+            ):
+                return False
+            if time.monotonic() >= limit:
+                raise TimeoutError("sse write budget exhausted")
+            if mark_content:
+                self._content_started = True
+            conn = getattr(self, "connection", None)
+            prev_timeout: Any = None
+            have_conn = False
+            if conn is not None and hasattr(conn, "settimeout"):
                 try:
-                    self.wfile.write(text.encode("utf-8"))
-                    self.wfile.flush()
-                finally:
-                    if text == "data: [DONE]\n\n":
-                        self._sse_phase = "CLOSED"
+                    prev_timeout = conn.gettimeout()
+                    conn.settimeout(max(0.001, limit - time.monotonic()))
+                    have_conn = True
+                except (OSError, ValueError, AttributeError):
+                    have_conn = False
+            try:
+                self.wfile.write(text.encode("utf-8"))
+                if have_conn:
+                    try:
+                        conn.settimeout(max(0.001, limit - time.monotonic()))
+                    except (OSError, ValueError, AttributeError):
+                        pass
+                self.wfile.flush()
+            finally:
+                if text == "data: [DONE]\n\n":
+                    self._sse_phase = "CLOSED"
+                if have_conn:
+                    try:
+                        conn.settimeout(prev_timeout)
+                    except (OSError, ValueError, AttributeError):
+                        pass
             return True
         except (BrokenPipeError, ConnectionResetError, OSError):
             if not self._client_gone:
                 self._client_gone = True
+                self._delivery_failed = True
                 _log("client gone mid-stream")
                 self._kill_current_run()
             return False
+        finally:
+            self._wlock.release()
 
     def _sse_chunk(self, delta: dict, finish_reason: Any = None) -> dict:
         return {
@@ -2026,13 +2620,54 @@ class Handler(BaseHTTPRequestHandler):
             "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
         }
 
-    def _sse_emit(self, obj: dict, *, keepalive: bool = False) -> bool:
+    def _sse_emit(
+        self, obj: dict, *, keepalive: bool = False, mark_content: bool = False
+    ) -> bool:
         return self._sse_write(
-            "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n", keepalive=keepalive
+            "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n",
+            keepalive=keepalive,
+            mark_content=mark_content,
         )
 
+    def _live_reasoning_sink(self, full_text: str) -> bool:
+        """Sink ServeRun: публикует только прирост summary.0 до заморозки."""
+        if not full_text or not getattr(self, "_sse_open", False):
+            return True
+        sent = getattr(self, "_live_sent_text", "")
+        if full_text == sent or not full_text.startswith(sent):
+            return True
+        delta = full_text[len(sent) :]
+        if not delta:
+            return True
+        ok = self._sse_emit(
+            self._sse_chunk({"reasoning_content": delta}), mark_content=True
+        )
+        if ok:
+            self._live_sent_text = full_text
+        return ok
+
+    def _force_close_connection(self) -> None:
+        """Закрытие соединения надзором W без ожидания _wlock (a4)."""
+        self._client_gone = True
+        conn = getattr(self, "connection", None)
+        if conn is None:
+            return
+        try:
+            conn.shutdown(socket.SHUT_RDWR)
+        except (OSError, ValueError, AttributeError):
+            pass
+        try:
+            conn.close()
+        except (OSError, ValueError, AttributeError):
+            pass
+
     def _sse_begin(self, model: str) -> bool:
         """Заголовки 200 + role-кадр до запуска хода и поток keepalive; False — клиент ушёл."""
+        if time.monotonic() >= getattr(self, "_write_deadline", float("inf")):
+            self._delivery_failed = True
+            self._client_gone = True
+            return False
+        self._live_sent_text = ""
         self._sse_id = f"chatcmpl-muse-{uuid.uuid4().hex[:12]}"
         self._sse_created = int(time.time())
         self._sse_model = model
@@ -2072,11 +2707,22 @@ class Handler(BaseHTTPRequestHandler):
     def _sse_stop_keepalive(self) -> None:
         if self._keepalive_stop is not None:
             self._keepalive_stop.set()
-        with self._wlock:
-            if self._sse_phase == "OPEN":
-                self._sse_phase = "FINALIZING"
+        w_deadline = getattr(self, "_write_deadline", float("inf"))
+        if w_deadline == float("inf"):
+            budget = LIVE_WRITE_TIMEOUT_S
+        else:
+            budget = min(LIVE_WRITE_TIMEOUT_S, max(0.0, w_deadline - time.monotonic()))
+        if self._wlock.acquire(timeout=budget):
+            try:
+                if self._sse_phase == "OPEN":
+                    self._sse_phase = "FINALIZING"
+            finally:
+                self._wlock.release()
         if self._ka_thread is not None:
-            self._ka_thread.join(timeout=2)
+            join_budget = 2.0
+            if w_deadline != float("inf"):
+                join_budget = min(join_budget, max(0.0, w_deadline - time.monotonic()))
+            self._ka_thread.join(timeout=join_budget)
         self._keepalive_stop = None
         self._ka_thread = None
 
@@ -2137,6 +2783,26 @@ class Handler(BaseHTTPRequestHandler):
             self._sse_write("data: [DONE]\n\n")
             return
         body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
+        w_deadline = getattr(self, "_write_deadline", float("inf"))
+        if time.monotonic() >= w_deadline:
+            self._delivery_failed = True
+            _log("delivery_deadline json response skipped")
+            self._force_close_connection()
+            return
+        conn = getattr(self, "connection", None)
+        prev_timeout: Any = None
+        have_conn = False
+        if (
+            conn is not None
+            and hasattr(conn, "settimeout")
+            and w_deadline != float("inf")
+        ):
+            try:
+                prev_timeout = conn.gettimeout()
+                conn.settimeout(max(0.001, w_deadline - time.monotonic()))
+                have_conn = True
+            except (OSError, ValueError, AttributeError):
+                have_conn = False
         try:
             self.send_response(int(code))
             self.send_header("Content-Type", "application/json; charset=utf-8")
@@ -2147,6 +2813,12 @@ class Handler(BaseHTTPRequestHandler):
             self._client_gone = True
             _log("client gone before response")
             self._kill_current_run()
+        finally:
+            if have_conn:
+                try:
+                    conn.settimeout(prev_timeout)
+                except (OSError, ValueError, AttributeError):
+                    pass
 
     def _send_sse(
         self,
@@ -2168,12 +2840,29 @@ class Handler(BaseHTTPRequestHandler):
         if not self._sse_open and not self._sse_begin(model):
             return
         self._sse_stop_keepalive()
-        with self._wlock:
-            self._content_started = True
         chunk = self._sse_chunk
         reasoning = "\n\n".join(s for s in (summaries or []) if s)
-        if reasoning and not self._sse_emit(chunk({"reasoning_content": reasoning})):
-            return
+        live_sent = getattr(self, "_live_sent_text", "")
+        if reasoning:
+            if not live_sent:
+                tail = reasoning
+            elif reasoning.startswith(live_sent):
+                tail = reasoning[len(live_sent) :]
+            else:
+                common = 0
+                for a_ch, b_ch in zip(live_sent, reasoning):
+                    if a_ch != b_ch:
+                        break
+                    common += 1
+                _log(
+                    f"reasoning_diverged p_len={len(live_sent)} f_len={len(reasoning)} "
+                    f"common={common} count=1"
+                )
+                tail = "\n\n" + reasoning
+            if tail and not self._sse_emit(
+                chunk({"reasoning_content": tail}), mark_content=True
+            ):
+                return
         for tc in tool_calls:
             fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
             delta = {
@@ -2189,12 +2878,19 @@ class Handler(BaseHTTPRequestHandler):
                     }
                 ]
             }
-            if not self._sse_emit(chunk(delta)):
+            if not self._sse_emit(chunk(delta), mark_content=True):
                 return
         for piece in _split_sse_chunks(content):
-            if not self._sse_emit(chunk({"content": piece})):
+            if time.monotonic() >= getattr(self, "_write_deadline", float("inf")):
+                self._delivery_failed = True
+                return
+            if not self._sse_emit(chunk({"content": piece}), mark_content=True):
                 return
             if SSE_CHUNK_DELAY_S > 0:
+                _w = getattr(self, "_write_deadline", float("inf"))
+                if _w - time.monotonic() <= SSE_CHUNK_DELAY_S:
+                    self._delivery_failed = True
+                    return
                 time.sleep(SSE_CHUNK_DELAY_S)
         final = chunk({}, finish)
         final["usage"] = {
@@ -2278,8 +2974,38 @@ class Handler(BaseHTTPRequestHandler):
         finally:
             # Любой выход (в т.ч. обрыв в очереди за слотом): поток keepalive не переживает запрос.
             self._sse_stop_keepalive()
+            _done = getattr(self, "_req_done", None)
+            if _done is not None:
+                _done.set()
+            self._write_deadline = float("inf")
+            self._exec_deadline = float("inf")
+            self._request_deadline = float("inf")
+            self._delivery_failed = False
 
     def _serve_json(self, req: dict) -> None:
+        # Абсолютный бюджет запроса a4: t0 при приёме, до очереди и вычислений.
+        _t0 = time.monotonic()
+        _req_deadline = _t0 + min(TIMEOUT_S, REQUEST_CAP_S)
+        _exec_deadline = _req_deadline - FINISH_RESERVE_S
+        _write_deadline = _req_deadline - CLOSE_RESERVE_S
+        self._request_deadline = _req_deadline
+        self._exec_deadline = _exec_deadline
+        self._write_deadline = _write_deadline
+        self._live_sent_text = ""
+        self._delivery_failed = False
+        _req_done = threading.Event()
+        self._req_done = _req_done
+
+        def _supervise_w() -> None:
+            while not _req_done.wait(0.05):
+                if time.monotonic() >= _write_deadline:
+                    self._delivery_failed = True
+                    _log("delivery_deadline W reached: closing connection")
+                    self._kill_current_run()
+                    self._force_close_connection()
+                    return
+
+        threading.Thread(target=_supervise_w, daemon=True).start()
         model = str(req.get("model") or DEFAULT_MODEL).strip()
         if model not in ALLOWED_MODELS:
             self._send(
@@ -2371,13 +3097,13 @@ class Handler(BaseHTTPRequestHandler):
 
         if req.get("stream") is True and not self._sse_begin(model):
             return
-        waited = time.monotonic()
         while not _slots.acquire(timeout=1.0):
             if self._client_gone or self._client_gone_probe():
                 self._client_gone = True
                 _log("client gone while waiting for a slot")
                 return
-            if time.monotonic() - waited > TIMEOUT_S:
+            if time.monotonic() >= _exec_deadline - MIN_ATTEMPT_REMAINING_S:
+                _log("insufficient remaining budget while waiting for a slot")
                 self._send(
                     503, {"error": {"message": "bridge busy", "type": "overloaded"}}
                 )
@@ -2388,6 +3114,11 @@ class Handler(BaseHTTPRequestHandler):
             _log("client gone while waiting for a slot")
             _slots.release()
             return
+        if time.monotonic() > _exec_deadline - MIN_ATTEMPT_REMAINING_S:
+            _log("insufficient remaining budget after slot acquire")
+            _slots.release()
+            self._send(503, {"error": {"message": "bridge busy", "type": "overloaded"}})
+            return
         watch_stop = threading.Event()
         watcher = threading.Thread(
             target=self._watch_client, args=(watch_stop,), daemon=True
@@ -2396,80 +3127,205 @@ class Handler(BaseHTTPRequestHandler):
         runs: list = []
         terminal_context_err: str | None = None
         context_retry_count = 0
+        transient_retry_count = 0
+        attempt_calls = [0]
+        agg: dict[str, bool] = {
+            "approval_seen": False,
+            "action": False,
+            "allowing": False,
+            "degraded": False,
+            "observed": False,
+        }
+
+        def _update_agg(run: Any, out: dict[str, Any] | None) -> None:
+            if run is not None:
+                agg["approval_seen"] = agg["approval_seen"] or bool(
+                    getattr(run, "approval_seen", False)
+                )
+                agg["action"] = agg["action"] or bool(
+                    getattr(run, "action_possible", False)
+                )
+                agg["allowing"] = agg["allowing"] or bool(
+                    getattr(run, "allowing_decide_attempted", False)
+                )
+                agg["degraded"] = agg["degraded"] or bool(
+                    getattr(run, "approval_degraded", False)
+                )
+                agg["observed"] = agg["observed"] or bool(
+                    getattr(run, "observed_barrier", False)
+                )
+            if out:
+                agg["approval_seen"] = agg["approval_seen"] or bool(
+                    out.get("approval_seen")
+                )
+                agg["action"] = agg["action"] or bool(out.get("action_possible"))
+                agg["allowing"] = agg["allowing"] or bool(out.get("allowing_decide"))
+                agg["degraded"] = agg["degraded"] or bool(out.get("approval_degraded"))
+                observed = out.get("observed_barrier")
+                if observed is None:
+                    observed = bool(out.get("text") or out.get("summaries"))
+                agg["observed"] = agg["observed"] or bool(observed)
+
+        def _can_start(is_exec: bool, *, context: bool = False) -> tuple[bool, str]:
+            if self._client_gone or self._client_gone_probe():
+                self._client_gone = True
+                return False, "client_gone"
+            if getattr(self, "_content_started", False):
+                return False, "content_started"
+            if getattr(self, "_delivery_failed", False):
+                return False, "delivery_failed"
+            if agg["degraded"]:
+                return False, "approval_degraded"
+            if agg["approval_seen"] or agg["allowing"]:
+                return False, "approval_barrier"
+            if is_exec and APPROVAL_MODE == "denyUnmatched":
+                return False, "exec_fallback_disabled"
+            if runs and not all(getattr(r, "dead_confirmed", True) for r in runs):
+                return False, "group_not_dead"
+            if time.monotonic() > _exec_deadline - MIN_ATTEMPT_REMAINING_S:
+                return False, "insufficient_remaining"
+            if context or TRANSIENT_RETRY_SCOPE == "observed-items":
+                if agg["observed"]:
+                    return False, "observed_barrier"
+            elif agg["action"]:
+                return False, "action_possible"
+            return True, ""
+
+        def _blocked_out(err: str) -> dict[str, Any]:
+            return {
+                "rc": 1,
+                "text": "",
+                "chunks": [],
+                "err": err,
+                "state": "terminal_failed",
+                "approval_seen": agg["approval_seen"],
+                "action_possible": agg["action"],
+                "approval_degraded": agg["degraded"],
+                "observed_barrier": agg["observed"],
+                "transient": False,
+            }
 
-        def run_attempt(attempt_prompt: str) -> tuple[dict[str, Any], str]:
-            # Serve-first: пробуем MSP serve (там reasoning summaries), при любой
-            # транспортной неполадке — тихий fallback на проверенный exec.
-            attempt_out: dict[str, Any]
-            attempt_via = "exec"
+        def run_attempt(
+            attempt_prompt: str, *, context: bool = False
+        ) -> tuple[dict[str, Any], str]:
+            attempt_calls[0] += 1
+            ok_gate, gate_reason = _can_start(False, context=context)
+            if not ok_gate:
+                _log(f"new serve process blocked reason={gate_reason}")
+                return _blocked_out(f"new process blocked: {gate_reason}"), "blocked"
+            serve_run = ServeRun(model, attempt_prompt, effort, WORKSPACE)
+            serve_run.exec_deadline = _exec_deadline
+            serve_run.write_deadline = _write_deadline
+            serve_run.request_deadline = _req_deadline
+            if req.get("stream") is True and self._sse_open:
+                serve_run.live_sink = self._live_reasoning_sink
+            runs.append(serve_run)
+            self._current_run = serve_run
             try:
-                serve_run = ServeRun(model, attempt_prompt, effort, WORKSPACE)
-                runs.append(serve_run)
-                self._current_run = serve_run
                 attempt_out = serve_run.execute()
-                attempt_via = "serve"
+                _update_agg(serve_run, attempt_out)
+                return attempt_out, "serve"
             except ServeUnavailable as exc:
+                _update_agg(serve_run, None)
                 if self._client_gone:
-                    # Обрыв клиента уже убил serve-группу: новый exec-ход не запускаем.
                     _log("client gone during serve — exec fallback skipped")
-                    attempt_out = {
-                        "rc": -1,
-                        "text": "",
-                        "err": "client gone",
-                        "state": "client_gone",
-                    }
-                    attempt_via = "aborted"
-                else:
-                    safe_exc = _sanitize_reflected(
-                        str(exc), [*reflected_prompts, attempt_prompt], raw_messages
+                    return (
+                        {
+                            "rc": -1,
+                            "text": "",
+                            "err": "client gone",
+                            "state": "client_gone",
+                        },
+                        "aborted",
                     )
-                    safe_exc = re.sub(
-                        r"[\x00-\x1f\x7f-\x9f\u2028\u2029]", " ", safe_exc
-                    ).strip()[:300]
-                    _log(f"serve unavailable ({safe_exc}), fallback exec model={model}")
-                    exec_run = Run(model, attempt_prompt, effort, WORKSPACE)
-                    runs.append(exec_run)
-                    self._current_run = exec_run
-                    attempt_out = exec_run.execute()
-                    attempt_via = "exec-after-serve-fallback"
-                    if (
-                        attempt_out.get("rc") != 0
-                        and not self._client_gone
-                        and NETWORK_RETRY_MARKER in str(attempt_out.get("err") or "")
-                    ):
-                        _log("exec hit network marker, single retry")
-                        retry_run = Run(model, attempt_prompt, effort, WORKSPACE)
-                        runs.append(retry_run)
-                        self._current_run = retry_run
-                        attempt_out = retry_run.execute()
-                        attempt_via = "exec-retry"
-            return attempt_out, attempt_via
-
-        try:
-            t_first_attempt = time.monotonic()
-            out, via = run_attempt(prompt)
-            raw_err = str(out.get("err") or "")
-            is_hard_threshold = (
-                out.get("rc") != 0
-                and out.get("state") == "terminal_failed"
-                and (
-                    bool(out.get("hard_threshold"))
-                    or HARD_THRESHOLD_ERR_SUBSTR in raw_err
+                exc_text = str(exc)
+                safe_exc = _sanitize_reflected(
+                    exc_text, [*reflected_prompts, attempt_prompt], raw_messages
                 )
-            )
-            if (
-                is_hard_threshold
-                and context_retry_count == 0
-                and not self._client_gone
-                and not getattr(self, "_content_started", False)
-            ):
-                for run in runs:
-                    run.close()
-                if not all(run.dead_confirmed for run in runs):
+                safe_exc = re.sub(
+                    r"[\x00-\x1f\x7f-\x9f\u2028\u2029]", " ", safe_exc
+                ).strip()[:300]
+                if _is_transient_text(exc_text) and not serve_run.ceiling_seen:
+                    return (
+                        {
+                            "rc": 1,
+                            "text": "",
+                            "err": exc_text,
+                            "state": "terminal_failed",
+                            "transient": True,
+                            "approval_seen": agg["approval_seen"],
+                            "action_possible": agg["action"],
+                            "approval_degraded": agg["degraded"],
+                            "observed_barrier": agg["observed"],
+                        },
+                        "serve",
+                    )
+                ok_exec, exec_reason = _can_start(True, context=context)
+                if not ok_exec:
+                    if exec_reason == "exec_fallback_disabled":
+                        err = (
+                            "exec_fallback_disabled(denyUnmatched): "
+                            f"serve unavailable: {safe_exc}"
+                        )
+                    else:
+                        err = exc_text
                     _log(
-                        "context retry skipped: first attempt process group not confirmed dead"
+                        f"serve unavailable ({safe_exc}), exec fallback blocked "
+                        f"reason={exec_reason}"
                     )
-                else:
+                    return _blocked_out(err), "serve"
+                _log(f"serve unavailable ({safe_exc}), fallback exec model={model}")
+                exec_run = Run(model, attempt_prompt, effort, WORKSPACE)
+                exec_run.exec_deadline = _exec_deadline
+                exec_run.action_possible = True
+                agg["action"] = True
+                runs.append(exec_run)
+                self._current_run = exec_run
+                attempt_out = exec_run.execute()
+                _update_agg(exec_run, attempt_out)
+                return attempt_out, "exec-after-serve-fallback"
+
+        out: dict[str, Any] = {
+            "rc": 1,
+            "text": "",
+            "err": "no attempt",
+            "state": "terminal_failed",
+        }
+        via = "none"
+        try:
+            out, via = run_attempt(prompt)
+            while True:
+                if out.get("rc") == 0 and out.get("state") == "ok":
+                    break
+                if self._client_gone or getattr(self, "_delivery_failed", False):
+                    break
+                raw_err = str(out.get("err") or "")
+                is_hard_threshold = (
+                    out.get("rc") != 0
+                    and out.get("state") == "terminal_failed"
+                    and (
+                        bool(out.get("hard_threshold"))
+                        or HARD_THRESHOLD_ERR_SUBSTR in raw_err
+                    )
+                )
+                # Сначала контекстный повтор (AD-005), затем транзиентный.
+                if (
+                    is_hard_threshold
+                    and context_retry_count == 0
+                    and attempt_calls[0] < 4
+                    and not getattr(self, "_content_started", False)
+                ):
+                    for run in runs:
+                        run.close()
+                    if not all(run.dead_confirmed for run in runs):
+                        _log(
+                            "context retry skipped: first attempt process group not confirmed dead"
+                        )
+                        break
+                    ok_ctx, ctx_reason = _can_start(False, context=True)
+                    if not ok_ctx:
+                        _log(f"context retry skipped reason={ctx_reason}")
+                        break
                     retry_res = _prune_messages(
                         raw_messages,
                         limit=retry_target,
@@ -2492,9 +3348,9 @@ class Handler(BaseHTTPRequestHandler):
                             f"mandatory context exceeds budget "
                             f"(est_tokens={retry_res.mandatory_est}, limit={retry_target})"
                         )
-                    elif (
-                        retry_res.est_after >= current_est
-                        or time.monotonic() - t_first_attempt >= TIMEOUT_S
+                        break
+                    if retry_res.est_after >= current_est or (
+                        time.monotonic() > _exec_deadline - MIN_ATTEMPT_REMAINING_S
                     ):
                         _log_context_prune(
                             rid,
@@ -2506,39 +3362,92 @@ class Handler(BaseHTTPRequestHandler):
                             retry_res,
                         )
                         terminal_context_err = (
-                            f"context hard threshold exceeded after single compaction retry "
-                            f"(est_tokens={retry_res.est_after}, target={retry_target})"
+                            "context hard threshold exceeded after single "
+                            f"compaction retry (est_tokens={retry_res.est_after}, "
+                            f"target={retry_target})"
                         )
-                    elif self._client_gone or self._client_gone_probe():
+                        break
+                    if self._client_gone or self._client_gone_probe():
                         self._client_gone = True
-                    else:
-                        context_retry_count = 1
-                        _log_context_prune(
-                            rid,
-                            model,
-                            "hard_threshold_retry",
-                            2,
-                            limit,
-                            retry_target,
-                            retry_res,
+                        break
+                    context_retry_count = 1
+                    _log_context_prune(
+                        rid,
+                        model,
+                        "hard_threshold_retry",
+                        2,
+                        limit,
+                        retry_target,
+                        retry_res,
+                    )
+                    prompt = retry_res.prompt
+                    current_est = retry_res.est_after
+                    reflected_prompts.append(prompt)
+                    out, via = run_attempt(prompt, context=True)
+                    raw_err_2 = str(out.get("err") or "")
+                    if (
+                        out.get("rc") != 0
+                        and out.get("state") == "terminal_failed"
+                        and (
+                            bool(out.get("hard_threshold"))
+                            or HARD_THRESHOLD_ERR_SUBSTR in raw_err_2
                         )
-                        prompt = retry_res.prompt
-                        current_est = retry_res.est_after
-                        reflected_prompts.append(prompt)
-                        out, via = run_attempt(prompt)
-                        raw_err_2 = str(out.get("err") or "")
-                        if (
-                            out.get("rc") != 0
-                            and out.get("state") == "terminal_failed"
-                            and (
-                                bool(out.get("hard_threshold"))
-                                or HARD_THRESHOLD_ERR_SUBSTR in raw_err_2
-                            )
-                        ):
-                            terminal_context_err = (
-                                f"context hard threshold exceeded after single compaction retry "
-                                f"(est_tokens={current_est}, target={retry_target})"
-                            )
+                    ):
+                        terminal_context_err = (
+                            "context hard threshold exceeded after single "
+                            f"compaction retry (est_tokens={current_est}, "
+                            f"target={retry_target})"
+                        )
+                    continue
+                is_transient = (
+                    out.get("rc") != 0
+                    and str(out.get("state") or "") not in NON_RETRYABLE_STATES
+                    and (bool(out.get("transient")) or _is_transient_text(raw_err))
+                )
+                max_calls = 4 if context_retry_count else 3
+                if (
+                    not is_transient
+                    or transient_retry_count >= TRANSIENT_MAX_RETRIES
+                    or attempt_calls[0] >= max_calls
+                ):
+                    if is_transient and getattr(self, "_content_started", False):
+                        _log("retry_blocked reason=content_started")
+                    break
+                for run in runs:
+                    run.close()
+                ok_retry, retry_reason = _can_start(False)
+                if not ok_retry:
+                    if getattr(self, "_content_started", False):
+                        _log(f"retry_blocked reason={retry_reason} content_started=1")
+                    else:
+                        _log(f"transient retry blocked reason={retry_reason}")
+                    break
+                backoff = TRANSIENT_BACKOFF_S
+                pause = backoff[min(transient_retry_count, len(backoff) - 1)]
+                if TRANSIENT_JITTER_S > 0:
+                    pause += random.uniform(0, TRANSIENT_JITTER_S)
+                transient_retry_count += 1
+                if TRANSIENT_RETRY_SCOPE == "observed-items":
+                    _log(
+                        "transient retry retry_scope=observed-items "
+                        f"n={transient_retry_count}"
+                    )
+                else:
+                    _log(
+                        "transient retry retry_scope=pre-action "
+                        f"n={transient_retry_count} pause_s={pause:.2f}"
+                    )
+                pause_end = min(time.monotonic() + pause, _exec_deadline)
+                client_left = False
+                while time.monotonic() < pause_end:
+                    if self._client_gone or self._client_gone_probe():
+                        self._client_gone = True
+                        client_left = True
+                        break
+                    time.sleep(min(0.05, max(0.0, pause_end - time.monotonic())))
+                if client_left:
+                    break
+                out, via = run_attempt(prompt)
         finally:
             # Слот отпускаем после остановки надзора (kill -> wait уже внутри execute).
             watch_stop.set()
@@ -2723,6 +3632,14 @@ def main() -> int:
     if not AUTH_KEY:
         sys.stderr.write("MUSE_BRIDGE_KEY is required; refusing to start\n")
         return 2
+    try:
+        _validate_startup_config()
+    except RuntimeError as exc:
+        sys.stderr.write(f"{exc}; refusing to start\n")
+        _log(f"startup config invalid: {exc}")
+        return 2
+    if TRANSIENT_RETRY_SCOPE == "observed-items":
+        _log("warning retry_scope=observed-items at-least-once accepted by operator")
     try:
         WORKSPACE.mkdir(parents=True, exist_ok=True)
     except OSError as exc:
diff --git a/tests/test_muse_bridge_killpg.py b/tests/test_muse_bridge_killpg.py
index 1755947..81cdd5f 100644
--- a/tests/test_muse_bridge_killpg.py
+++ b/tests/test_muse_bridge_killpg.py
@@ -1032,6 +1032,311 @@ for line in sys.stdin:
     scenario.mod.MUSE_WRAPPER = str(wrapper)
 
 
+_FAKE_MSP_HEAD = """import json, os, sys, time
+from pathlib import Path
+cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
+root = Path(cfg["root"]); mode = sys.argv[2]
+(root / (mode + "-argv.json")).write_text(json.dumps(sys.argv[2:]), encoding="utf-8")
+with (root / (mode + "-argv.jsonl")).open("a", encoding="utf-8") as fh:
+    fh.write(json.dumps(sys.argv[2:]) + "\\n")
+def bump(name):
+    p = root / name
+    n = int(p.read_text(encoding="utf-8")) if p.exists() else 0
+    n += 1; p.write_text(str(n), encoding="utf-8"); return n
+def effect(name):
+    with (root / "effects.log").open("a", encoding="utf-8") as fh:
+        fh.write(str(name) + "\\n")
+idx = bump(mode + "-count.txt")
+if mode == "exec":
+    plans = cfg.get("exec_plans") or [{"text": "fallback-ok"}]
+    plan = plans[min(idx - 1, len(plans) - 1)]
+    if plan.get("effect"): effect(plan["effect"])
+    if plan.get("delay"): time.sleep(float(plan["delay"]))
+    if plan.get("stderr"): print(plan["stderr"], file=sys.stderr, flush=True)
+    rc = int(plan.get("rc", 0))
+    if rc == 0:
+        print(json.dumps({"schema_version": 1, "payload_type": "run.terminal.completed", "payload": {"text": plan.get("text", "fallback-ok")}}), flush=True)
+    sys.exit(rc)
+plans = cfg.get("serve_plans") or [{}]
+plan = plans[min(idx - 1, len(plans) - 1)]
+with (root / "serve-pids.log").open("a", encoding="utf-8") as fh:
+    fh.write(str(os.getpid()) + "\\n")
+active_file = None
+if cfg.get("track_concurrency"):
+    active_file = root / ("active-%d" % os.getpid()); active_file.write_text("1")
+    with (root / "concurrency.log").open("a", encoding="utf-8") as fh:
+        fh.write(str(len(list(root.glob("active-*")))) + "\\n")
+if plan.get("handshake_eof"):
+    sys.exit(0)
+if plan.get("handshake_hang"):
+    time.sleep(30); sys.exit(0)
+def send(obj):
+    sys.stdout.write(json.dumps(obj) + "\\n"); sys.stdout.flush()
+def read_msg():
+    line = sys.stdin.readline()
+    if not line: raise EOFError
+    msg = json.loads(line)
+    with (root / "rpc.jsonl").open("a", encoding="utf-8") as fh:
+        fh.write(json.dumps(msg) + "\\n")
+    return msg
+_decide_i = [0]
+def decide_reply(rid):
+    reps = plan.get("decide_replies") or [{"result": {"terminal": True}}]
+    rep = reps[min(_decide_i[0], len(reps) - 1)]; _decide_i[0] += 1
+    if "error" in rep: send({"jsonrpc": "2.0", "id": rid, "error": rep["error"]})
+    else: send({"jsonrpc": "2.0", "id": rid, "result": rep.get("result", {})})
+def cancel_reply(rid):
+    rep = plan.get("cancel_reply") or {}
+    if "error" in rep: send({"jsonrpc": "2.0", "id": rid, "error": rep["error"]})
+    else: send({"jsonrpc": "2.0", "id": rid, "result": rep.get("result", {})})
+def await_command():
+    while True:
+        msg = read_msg(); m = msg.get("method")
+        if m == "approval/decide": decide_reply(msg["id"]); return msg
+        if m in ("userInput/cancel", "turn/cancel"): cancel_reply(msg["id"]); return msg
+def appr_payload(over=None, n=0):
+    aid = "appr-%d" % n
+    base = {"approvalId": aid, "availableChoices": [
+        {"choiceId": "c-approve", "decision": "approved", "label": "Allow", "scope": "once"},
+        {"choiceId": "c-abort", "decision": "abort", "label": "Abort", "scope": "once"}],
+        "currentRequirementId": {"approvalId": aid, "sourceIndex": n}, "itemId": "item-1",
+        "judgeEscalated": False, "protectedWrite": False, "rawArgs": "{}", "sessionId": "sess-1",
+        "sourceRange": {}, "subject": {"kind": "tool", "toolName": "web_search"}, "taskId": "task-1",
+        "toolCallId": "tc-1", "toolName": "web_search", "turnId": "turn-1", "viewCursor": "0"}
+    if over: base.update(over)
+    return base
+def do_approval(over=None, req_mode="request", n=0):
+    payload = appr_payload(over, n)
+    if req_mode == "requested":
+        send({"jsonrpc": "2.0", "method": "approval/requested", "params": payload})
+    else:
+        send({"jsonrpc": "2.0", "id": 9000 + n, "method": "approval/request", "params": payload})
+    return await_command()
+def ui_payload(over=None, n=0):
+    base = {"userInputId": "ui-%d" % n, "sessionId": "sess-1", "toolName": "ask_user",
+            "itemId": "item-1", "toolCallId": "tc-1", "turnId": "turn-1", "viewCursor": "0",
+            "sourceRange": {}, "questions": [{"questionId": "q1", "text": "question"}]}
+    if over: base.update(over)
+    return base
+def do_user_input(over=None, n=0):
+    send({"jsonrpc": "2.0", "id": 9100 + n, "method": "userInput/request", "params": ui_payload(over, n)})
+    return await_command()
+"""
+
+_FAKE_MSP_TAIL = """_started = set()
+def ensure_item(kind):
+    iid = "r1" if kind == "reasoning" else "a1" if kind == "agentMessage" else "t1"
+    if iid not in _started:
+        _started.add(iid)
+        send({"jsonrpc": "2.0", "method": "item/started", "params": {"item": {"itemId": iid, "turnId": "turn-1", "kind": kind}}})
+    return iid
+def run_steps():
+    for step in plan.get("steps") or []:
+        if "delay" in step: time.sleep(float(step["delay"]))
+        elif "effect" in step: effect(step["effect"])
+        elif "approval" in step: do_approval(step["approval"] if isinstance(step["approval"], dict) else None, step.get("mode", "request"), int(step.get("n", 0)))
+        elif "approval_repeat" in step:
+            for i in range(int(step["approval_repeat"])): do_approval(None, "request", i)
+        elif "approval_nowait" in step:
+            over = step["approval_nowait"] if isinstance(step["approval_nowait"], dict) else None
+            n = int(step.get("n", 7))
+            send({"jsonrpc": "2.0", "id": 9200 + n, "method": "approval/request", "params": appr_payload(over, n)})
+        elif "approval_then_exit" in step:
+            over = step["approval_then_exit"] if isinstance(step["approval_then_exit"], dict) else None
+            send({"jsonrpc": "2.0", "id": 9300, "method": "approval/request", "params": appr_payload(over, 0)})
+            sys.stdout.flush(); os._exit(0)
+        elif "user_input" in step: do_user_input(step["user_input"] if isinstance(step["user_input"], dict) else None, int(step.get("n", 0)))
+        elif "user_input_repeat" in step:
+            for i in range(int(step["user_input_repeat"])): do_user_input(None, i)
+        elif "summary" in step:
+            ensure_item("reasoning")
+            sidx, text = step["summary"]
+            send({"jsonrpc": "2.0", "method": "item/delta", "params": {"itemId": "r1", "field": "summary.%s" % sidx, "delta": text}})
+        elif "reasoning_completed" in step:
+            ensure_item("reasoning")
+            send({"jsonrpc": "2.0", "method": "item/completed", "params": {"item": {"itemId": "r1", "turnId": "turn-1", "kind": "reasoning", "summary": list(step["reasoning_completed"])}}})
+        elif "tool_item" in step:
+            ti = step["tool_item"] if isinstance(step["tool_item"], dict) else {}
+            item = {"itemId": "t1", "turnId": "turn-1", "kind": ti.get("kind", "toolCall"), "toolName": ti.get("toolName", "web_search"), "rawArgs": ti.get("rawArgs", "{}")}
+            send({"jsonrpc": "2.0", "method": "item/started", "params": {"item": item}})
+            send({"jsonrpc": "2.0", "method": "item/completed", "params": {"item": item}})
+        elif "model_retry" in step:
+            send({"jsonrpc": "2.0", "method": "turn/modelRetryScheduled", "params": dict(step["model_retry"])})
+        elif "text_delta" in step:
+            ensure_item("agentMessage")
+            send({"jsonrpc": "2.0", "method": "item/delta", "params": {"itemId": "a1", "field": "text", "delta": step["text_delta"]}})
+        elif "eof" in step:
+            sys.stdout.flush(); os._exit(0)
+        elif "hang" in step:
+            while True:
+                msg = read_msg(); m = msg.get("method")
+                if m == "approval/decide": decide_reply(msg["id"])
+                elif m in ("userInput/cancel", "turn/cancel"): cancel_reply(msg["id"])
+        elif "no_read_hang" in step:
+            while True: time.sleep(1)
+        elif "terminal" in step:
+            t = step["terminal"] if isinstance(step["terminal"], dict) else {}
+            if t.get("text"):
+                ensure_item("agentMessage")
+                send({"jsonrpc": "2.0", "method": "item/completed", "params": {"item": {"itemId": "a1", "turnId": "turn-1", "kind": "agentMessage", "text": t["text"]}}})
+            params = {"turnId": "turn-1", "sessionId": "sess-1", "terminal": t.get("terminal", "completed")}
+            for key in ("error", "reason", "timeToFirstTokenMs", "usage", "durationMs"):
+                if key in t: params[key] = t[key]
+            send({"jsonrpc": "2.0", "method": "turn/completed", "params": params})
+            return
+def maybe_setup(when):
+    sa = plan.get("setup_approval")
+    if not sa or sa.get("when") != when: return False
+    do_approval(sa.get("payload") if isinstance(sa.get("payload"), dict) else None, sa.get("mode", "request"), 0)
+    if sa.get("effect"): effect(sa["effect"])
+    return sa.get("after") == "break"
+try:
+    while True:
+        msg = read_msg(); method = msg.get("method")
+        if method == "initialize":
+            if maybe_setup("initialize"):
+                send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": plan.get("setup_approval", {}).get("break_message", "[net-timeout] setup break")}}); break
+            send({"jsonrpc": "2.0", "id": msg["id"], "result": {"serverInfo": {"version": "1.4.9-test"}, "schema": {"fingerprint": "fp-test-1234567890abcdef"}}})
+        elif method == "session/start":
+            if maybe_setup("session/start"):
+                send({"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32603, "message": plan.get("setup_approval", {}).get("break_message", "[net-timeout] setup break")}}); break
+            if plan.get("setup_delay"): time.sleep(float(plan["setup_delay"]))
+            se = plan.get("session_error")
+            if se:
+                send({"jsonrpc": "2.0", "id": msg["id"], "error": se}); break
+            if plan.get("no_session_id"):
+                send({"jsonrpc": "2.0", "id": msg["id"], "result": {"session": {}}}); continue
+            reqmode = (msg.get("params") or {}).get("approvalMode") or "allowAll"
+            send({"jsonrpc": "2.0", "id": msg["id"], "result": {"session": {"sessionId": "sess-1", "approvalMode": {"mode": reqmode, "source": "startup", "lastCommandId": None}}}})
+        elif method == "turn/start":
+            if plan.get("turn_start_eof"): os._exit(0)
+            if plan.get("turn_delay"): time.sleep(float(plan["turn_delay"]))
+            send({"jsonrpc": "2.0", "id": msg["id"], "result": {"status": "accepted", "turnId": "turn-1"}})
+            run_steps(); break
+        elif method == "approval/decide": decide_reply(msg["id"])
+        elif method in ("userInput/cancel", "turn/cancel"): cancel_reply(msg["id"])
+except EOFError:
+    pass
+finally:
+    if active_file is not None:
+        try: active_file.unlink()
+        except OSError: pass
+"""
+
+FAKE_MSP_SCRIPT = _FAKE_MSP_HEAD + _FAKE_MSP_TAIL
+
+_OK_STEP = {"terminal": {"terminal": "completed", "text": "hello"}}
+
+
+def ok_plan(*steps: dict) -> dict:
+    """План serve, завершающийся успешным hello после шагов."""
+    return {"steps": [*steps, _OK_STEP]}
+
+
+def fail_terminal(marker: str, **extra: Any) -> dict:
+    """Шаг транзиентного терминального провала serve."""
+    term: dict[str, Any] = {
+        "terminal": "failed",
+        "error": {"kind": "network", "message": marker},
+    }
+    term.update(extra)
+    return {"terminal": term}
+
+
+def install_fake_msp(
+    scenario: Any,
+    serve_plans: list[dict] | None = None,
+    exec_plans: list[dict] | None = None,
+    track_concurrency: bool = False,
+) -> None:
+    """Расширенный фейковый MSP (a4): планы по вызовам, rpc.jsonl, счётчики."""
+    import shlex
+
+    for name in (
+        "rpc.jsonl",
+        "effects.log",
+        "serve-count.txt",
+        "exec-count.txt",
+        "serve-argv.jsonl",
+        "exec-argv.jsonl",
+        "serve-pids.log",
+        "concurrency.log",
+    ):
+        try:
+            (scenario.tmp / name).unlink()
+        except OSError:
+            pass
+    cfg = {
+        "root": str(scenario.tmp),
+        "serve_plans": serve_plans or [ok_plan()],
+        "exec_plans": exec_plans or [{"text": "fallback-ok"}],
+        "track_concurrency": track_concurrency,
+    }
+    cfg_path = scenario.tmp / "fake-cfg.json"
+    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
+    script = scenario.tmp / "fake_msp.py"
+    script.write_text(FAKE_MSP_SCRIPT, encoding="utf-8")
+    wrapper = scenario.tmp / "muse-cli.sh"
+    wrapper.write_text(
+        f"#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(script))} "
+        f'{shlex.quote(str(cfg_path))} "$@"\n',
+        encoding="utf-8",
+    )
+    wrapper.chmod(0o755)
+    scenario.mod.MUSE_WRAPPER = str(wrapper)
+
+
+def rpc_msgs(scenario: Any) -> list[dict]:
+    """Все входящие RPC фейка (мост -> serve), включая receipt-ответы."""
+    path = scenario.tmp / "rpc.jsonl"
+    if not path.exists():
+        return []
+    return [
+        json.loads(line)
+        for line in path.read_text(encoding="utf-8").splitlines()
+        if line.strip()
+    ]
+
+
+def rpc_by_method(scenario: Any, method: str) -> list[dict]:
+    return [m for m in rpc_msgs(scenario) if m.get("method") == method]
+
+
+def proc_count(scenario: Any, mode: str) -> int:
+    """Число запусков serve/exec по argv-журналу фейка."""
+    path = scenario.tmp / f"{mode}-argv.jsonl"
+    if not path.exists():
+        return 0
+    return len(
+        [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
+    )
+
+
+def effect_lines(scenario: Any) -> list[str]:
+    path = scenario.tmp / "effects.log"
+    if not path.exists():
+        return []
+    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
+
+
+def sse_frames(body: bytes) -> list[dict]:
+    return [
+        json.loads(line[6:])
+        for line in body.decode("utf-8", "replace").splitlines()
+        if line.startswith("data: {")
+    ]
+
+
+def sse_deltas(body: bytes, key: str) -> list[str]:
+    out: list[str] = []
+    for frame in sse_frames(body):
+        for choice in frame.get("choices") or []:
+            delta = choice.get("delta") or {}
+            if isinstance(delta.get(key), str):
+                out.append(delta[key])
+    return out
+
+
 class ServeTurnErrorExtractionTest(_BridgeScenario):
     """AD-002: приоритет, защитный разбор и точные лимиты терминальной причины."""
 
@@ -1257,7 +1562,7 @@ class SseDataKeepaliveTest(_BridgeScenario):
 
 
 class CliDisableFlagsAndApprovalFallbackTest(_BridgeScenario):
-    """AD-004: реальные argv фейка и неизменный approval fallback."""
+    """Реальные argv фейка; транспортный fallback до turn/start сохранён."""
 
     def test_serve_argv_disables_write_shell(self) -> None:
         install_protocol_wrapper(self, {"terminal": "completed"})
@@ -1275,8 +1580,11 @@ class CliDisableFlagsAndApprovalFallbackTest(_BridgeScenario):
         ):
             self.assertIn(flag, argv)
 
-    def test_approval_falls_back_to_exec_without_decide(self) -> None:
-        install_protocol_wrapper(self, {"approval": True})
+    def test_transport_fallback_exec_flags(self) -> None:
+        # oracle_change (REQ-MUSE-002): approval больше не уходит в exec;
+        # проверки exec-флагов сохранены на транспортном ServeUnavailable
+        # (EOF рукопожатия до turn/start), approval-контракт — класс Approval.
+        install_fake_msp(self, serve_plans=[{"handshake_eof": True}])
         status, body = bridge_request(self, turn_request())
         self.assertEqual(status, 200, body)
         self.assertIn("fallback-ok", body.decode())
@@ -1298,11 +1606,7 @@ class CliDisableFlagsAndApprovalFallbackTest(_BridgeScenario):
             "--prompt-file",
         ):
             self.assertIn(flag, argv)
-        self.assertNotIn("approval/decide", (self.tmp / "rpc.jsonl").read_text())
-        self.assertIn(
-            "serve unavailable (serve needs interaction (approval/request)), fallback exec",
-            self.mod.LOG_PATH.read_text(),
-        )
+        self.assertIn("fallback exec", self.mod.LOG_PATH.read_text())
 
 
 class AllowedModelsSyncTest(_BridgeScenario):
@@ -2068,35 +2372,46 @@ class ContextRetryTest(_BridgeScenario):
     def test_t18_serve_fallback_and_network_retry_preserve_context_retry_budget(
         self,
     ) -> None:
-        exec_prompts: list[str] = []
-
-        def fail_serve(_self: Any) -> dict[str, Any]:
-            raise self.mod.ServeUnavailable("serve down")
-
-        def fake_exec(run_self: Any) -> dict[str, Any]:
-            exec_prompts.append(run_self.prompt)
-            n = len(exec_prompts)
+        # oracle_change (AD-003): внутренний exec-reтрай по NETWORK_RETRY_MARKER
+        # упразднён; транзиентный счётчик Handler не расходует контекстный.
+        # Утверждение про контекстный бюджет сохранено дословно по смыслу:
+        # транзиентный повтор идёт тем же промптом, контекстный — прунённым.
+        self.mod.TRANSIENT_BACKOFF_S = (0.0, 0.0)
+        self.mod.TRANSIENT_JITTER_S = 0.0
+        serve_prompts: list[str] = []
+        exec_calls: list[str] = []
+
+        def fake_serve(run_self: Any) -> dict[str, Any]:
+            serve_prompts.append(run_self.prompt)
+            n = len(serve_prompts)
             if n == 1:
-                # Сетевой маркер на первой попытке -> сетевой ретрай с тем же промптом.
-                return {
-                    "rc": 1,
-                    "state": "nonzero_exit",
-                    "text": "",
-                    "err": self.mod.NETWORK_RETRY_MARKER,
-                }
+                # Пре-турновый транзиентный сбой serve: повтор новым serve.
+                raise self.mod.ServeUnavailable("[net-timeout] setup boom")
             if n == 2:
-                # Сетевой ретрай вернул ошибку порога Meta -> должен сработать контекстный retry.
+                # Транзиентный повтор вернул hard threshold: контекстный retry.
+                run_self.action_possible = True
                 return {
                     "rc": 1,
                     "state": "terminal_failed",
                     "text": "",
                     "err": self.mod.HARD_THRESHOLD_ERR_SUBSTR,
+                    "hard_threshold": True,
                 }
             return {
                 "rc": 0,
                 "state": "ok",
-                "text": "exec-recovered",
-                "chunks": ["exec-recovered"],
+                "text": "serve-recovered",
+                "chunks": ["serve-recovered"],
+                "err": "",
+            }
+
+        def fake_exec(run_self: Any) -> dict[str, Any]:
+            exec_calls.append(run_self.prompt)
+            return {
+                "rc": 0,
+                "state": "ok",
+                "text": "exec-should-not-run",
+                "chunks": ["exec-should-not-run"],
                 "err": "",
             }
 
@@ -2105,18 +2420,23 @@ class ContextRetryTest(_BridgeScenario):
             "messages": self._over_budget_messages(),
         }
         with (
-            mock.patch.object(self.mod.ServeRun, "execute", fail_serve),
+            mock.patch.object(self.mod.ServeRun, "execute", fake_serve),
             mock.patch.object(self.mod.Run, "execute", fake_exec),
         ):
             status, body = bridge_request(self, payload)
-        self.assertEqual(status, 200)
-        self.assertEqual(len(exec_prompts), 3)
-        self.assertEqual(exec_prompts[0], exec_prompts[1])
+        self.assertEqual(status, 200, body)
+        self.assertEqual(len(serve_prompts), 3)
+        self.assertEqual(serve_prompts[0], serve_prompts[1])
         self.assertLess(
-            self.mod._estimate_tokens(exec_prompts[2]),
-            self.mod._estimate_tokens(exec_prompts[0]),
+            self.mod._estimate_tokens(serve_prompts[2]),
+            self.mod._estimate_tokens(serve_prompts[0]),
+        )
+        self.assertEqual(exec_calls, [])
+        self.assertIn("serve-recovered", body.decode("utf-8"))
+        self.assertIn(
+            "reason=hard_threshold_retry",
+            self.mod.LOG_PATH.read_text(encoding="utf-8"),
         )
-        self.assertIn("exec-recovered", body.decode("utf-8"))
 
     def test_t19_client_disconnect_between_attempts_skips_second_run(self) -> None:
         calls = 0
@@ -2618,5 +2938,1076 @@ for line in sys.stdin:
         self.assertNotIn("fallback-secret-123", logs)
 
 
+class ApprovalTest(_BridgeScenario):
+    """REQ-MUSE-002 / AD-001, AD-002, AD-006, AD-007 (T-A01..T-A16)."""
+
+    def _shrink_grace(self) -> None:
+        self.mod.APPROVAL_CANCEL_GRACE_S = 0.4
+        self.mod.CONTROL_WRITE_TIMEOUT_S = 0.5
+
+    def test_t_a01_session_start_allowall_and_flags(self) -> None:
+        install_fake_msp(self, serve_plans=[ok_plan()])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        starts = rpc_by_method(self, "session/start")
+        self.assertEqual(len(starts), 1)
+        self.assertEqual(starts[0]["params"]["approvalMode"], "allowAll")
+        argv = json.loads((self.tmp / "serve-argv.json").read_text())
+        self.assertIn("--disable-write", argv)
+        self.assertIn("--disable-shell", argv)
+        self.assertNotIn("--disable-sandbox", argv)
+        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
+        self.assertIn("approvalMode=allowAll", logs)
+        self.assertIn("1.4.9-test", logs)
+
+    def test_t_a02_approval_receipt_and_decide_without_exec(self) -> None:
+        install_fake_msp(self, serve_plans=[ok_plan({"approval": {}})])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertIn("hello", body.decode())
+        self.assertEqual(proc_count(self, "exec"), 0)
+        self.assertEqual(len(rpc_by_method(self, "turn/start")), 1)
+        receipts = [
+            m for m in rpc_msgs(self) if "method" not in m and m.get("id") == 9000
+        ]
+        self.assertEqual(len(receipts), 1)
+        self.assertEqual(receipts[0].get("result"), {})
+        decides = rpc_by_method(self, "approval/decide")
+        self.assertEqual(len(decides), 1)
+        params = decides[0]["params"]
+        self.assertEqual(params["choiceId"], "c-approve")
+        self.assertEqual(
+            params["requirementId"], {"approvalId": "appr-0", "sourceIndex": 0}
+        )
+        self.assertIn("via=serve", self.mod.LOG_PATH.read_text(encoding="utf-8"))
+
+    def test_t_a03_policy_preference_and_amendment_never_chosen(self) -> None:
+        policy = self.mod.ApprovalPolicy("allowAll")
+        snap = {
+            "approvalId": "a1",
+            "sessionId": "s1",
+            "toolName": "web_search",
+            "availableChoices": [
+                {"choiceId": "c-sess", "decision": "approvedForSession"},
+                {"choiceId": "c-once", "decision": "approved"},
+            ],
+        }
+        got = policy.evaluate(snap)
+        self.assertEqual(got["action"], "approve")
+        self.assertEqual(got["choice_id"], "c-once")
+        only_amend = dict(
+            snap,
+            availableChoices=[
+                {"choiceId": "c-amend", "decision": "approvedPolicyAmendment"}
+            ],
+        )
+        self.assertEqual(policy.evaluate(only_amend)["action"], "fail_turn")
+        # Сценарно: выбор только amendment+abort ведёт в отказную деградацию.
+        self._shrink_grace()
+        choices = [
+            {
+                "choiceId": "c-amend",
+                "decision": "approvedPolicyAmendment",
+                "label": "Amend",
+                "scope": "once",
+            },
+            {
+                "choiceId": "c-abort",
+                "decision": "abort",
+                "label": "Abort",
+                "scope": "once",
+            },
+        ]
+        install_fake_msp(
+            self,
+            serve_plans=[
+                {"steps": [{"approval": {"availableChoices": choices}}, {"hang": True}]}
+            ],
+        )
+        status, _ = bridge_request(self, turn_request())
+        self.assertEqual(status, 502)
+        decides = rpc_by_method(self, "approval/decide")
+        self.assertEqual([d["params"]["choiceId"] for d in decides], ["c-abort"])
+        self.assertEqual(proc_count(self, "exec"), 0)
+
+    def test_t_a04_terminal_false_then_updated_request(self) -> None:
+        plan = ok_plan({"approval": {}, "n": 0}, {"approval": {}, "n": 1})
+        plan["decide_replies"] = [
+            {"result": {"terminal": False}},
+            {"result": {"terminal": True}},
+        ]
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 2)
+
+    def test_t_a05_requested_dedup_single_decide(self) -> None:
+        plan = ok_plan(
+            {"approval": {}, "mode": "requested", "n": 0},
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 1)
+        receipts = [m for m in rpc_msgs(self) if "method" not in m]
+        self.assertEqual(receipts, [])
+        # Пара request+requested с той же парой — по-прежнему один decide.
+        install_fake_msp(
+            self,
+            serve_plans=[
+                ok_plan({"approval": {}, "n": 0}, {"approval_nowait": {}, "n": 0})
+            ],
+        )
+        # approval_nowait шлёт request с другим серверным id, но той же
+        # парой appr-0/req-0: второй decide запрещён дедупликацией.
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 1)
+
+    def test_t_a06_user_input_receipt_and_cancel(self) -> None:
+        canary = "CANARY_QUESTION_TEXT"
+        plan = ok_plan(
+            {"user_input": {"questions": [{"questionId": "q1", "text": canary}]}}
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertEqual(len(rpc_by_method(self, "userInput/cancel")), 1)
+        receipts = [
+            m for m in rpc_msgs(self) if "method" not in m and m.get("id") == 9100
+        ]
+        self.assertEqual(len(receipts), 1)
+        self.assertNotIn(canary, self.mod.LOG_PATH.read_text(encoding="utf-8"))
+
+    def test_t_a07_approval_after_setup_window_still_decides(self) -> None:
+        self.mod.SERVE_SPAWN_TIMEOUT_S = 2.0
+        plan = ok_plan({"delay": 2.6}, {"approval": {}})
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 1)
+        self.assertEqual(proc_count(self, "exec"), 0)
+
+    def test_t_a08_decide_error_codes_latch_and_32051_benign(self) -> None:
+        self._shrink_grace()
+        for code in (-32050, -32052, -32053, -32054, -32030):
+            with self.subTest(code=code):
+                plan = {
+                    "steps": [{"approval": {}}, {"hang": True}],
+                    "decide_replies": [
+                        {"error": {"code": code, "message": "decide boom"}}
+                    ],
+                }
+                install_fake_msp(self, serve_plans=[plan])
+                status, _ = bridge_request(self, turn_request())
+                self.assertEqual(status, 502)
+                self.assertEqual(proc_count(self, "exec"), 0)
+                self.assertTrue(self._slot_free())
+        with self.subTest(code=-32051):
+            plan = ok_plan({"approval": {}})
+            plan["decide_replies"] = [
+                {"error": {"code": -32051, "message": "already resolved"}}
+            ]
+            install_fake_msp(self, serve_plans=[plan])
+            status, body = bridge_request(self, turn_request())
+            self.assertEqual(status, 200, body)
+        with self.subTest(case="empty_choices"):
+            plan = {
+                "steps": [
+                    {"approval": {"availableChoices": []}},
+                    {"hang": True},
+                ]
+            }
+            install_fake_msp(self, serve_plans=[plan])
+            status, _ = bridge_request(self, turn_request())
+            self.assertEqual(status, 502)
+            self.assertEqual(len(rpc_by_method(self, "approval/decide")), 0)
+            self.assertEqual(len(rpc_by_method(self, "turn/cancel")), 1)
+        with self.subTest(case="user_input_cancel_error"):
+            plan = {
+                "steps": [{"user_input": {}}, {"hang": True}],
+                "cancel_reply": {"error": {"code": -32603, "message": "cancel boom"}},
+            }
+            install_fake_msp(self, serve_plans=[plan])
+            status, _ = bridge_request(self, turn_request())
+            self.assertEqual(status, 502)
+            self.assertEqual(proc_count(self, "exec"), 0)
+
+    def test_t_a09_decide_and_cancel_bounds(self) -> None:
+        self._shrink_grace()
+        plan = {"steps": [{"approval_repeat": 12}]}
+        install_fake_msp(self, serve_plans=[plan])
+        status, _ = bridge_request(self, turn_request())
+        self.assertEqual(status, 502)
+        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 10)
+        self.assertEqual(proc_count(self, "exec"), 0)
+        self.assertTrue(self._slot_free())
+        plan = {"steps": [{"user_input_repeat": 5}]}
+        install_fake_msp(self, serve_plans=[plan])
+        status, _ = bridge_request(self, turn_request())
+        self.assertEqual(status, 502)
+        self.assertEqual(len(rpc_by_method(self, "userInput/cancel")), 3)
+        self.assertTrue(self._slot_free())
+
+    def test_t_a09b_ignored_cancel_killed_within_grace(self) -> None:
+        self._shrink_grace()
+        plan = {"steps": [{"approval": {"availableChoices": []}}, {"hang": True}]}
+        install_fake_msp(self, serve_plans=[plan])
+        started = time.monotonic()
+        status, body = bridge_request(self, turn_request(stream=True))
+        elapsed = time.monotonic() - started
+        self.assertEqual(status, 200)
+        self.assertEqual(body.count(b"data: [DONE]"), 1)
+        self.assertTrue(any("error" in f for f in sse_frames(body)))
+        self.assertLess(elapsed, 0.4 + 3.0)
+        self.assertTrue(
+            wait_until(self._slot_free, SCENARIO_DEADLINE_S), "слот не освободился"
+        )
+        pids = (self.tmp / "serve-pids.log").read_text().split()
+        self.assertTrue(pids)
+        self.assertTrue(
+            wait_until(lambda: not group_alive(int(pids[-1])), GROUP_EXIT_WAIT_S)
+        )
+        self.assertEqual(proc_count(self, "exec"), 0)
+
+    def test_t_a09c_blocked_stdin_grace_from_latch(self) -> None:
+        self._shrink_grace()
+        plan = {
+            "steps": [
+                {"approval_nowait": {"availableChoices": []}, "n": 3},
+                {"no_read_hang": True},
+            ]
+        }
+        install_fake_msp(self, serve_plans=[plan])
+        started = time.monotonic()
+        status, body = bridge_request(self, turn_request(stream=True))
+        elapsed = time.monotonic() - started
+        self.assertEqual(status, 200)
+        self.assertEqual(body.count(b"data: [DONE]"), 1)
+        self.assertLess(elapsed, 0.4 + 3.5)
+        self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
+        self.assertEqual(proc_count(self, "exec"), 0)
+        self.assertIn(
+            "approval_degraded", self.mod.LOG_PATH.read_text(encoding="utf-8")
+        )
+
+    def test_t_a10_canaries_redacted_in_audit_log(self) -> None:
+        bad_choice = "bad id CANARY_CHOICE"
+        choices = [
+            {
+                "choiceId": bad_choice,
+                "decision": "approved",
+                "label": "Allow",
+                "scope": "once",
+            },
+            {
+                "choiceId": "c-abort",
+                "decision": "abort",
+                "label": "Abort",
+                "scope": "once",
+            },
+        ]
+        plan = ok_plan(
+            {
+                "approval": {
+                    "availableChoices": choices,
+                    "toolName": "bad tool CANARY_TOOL",
+                    "rawArgs": "CANARY_RAWARGS",
+                    "subject": {"kind": "tool", "toolName": "bad tool"},
+                }
+            }
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        decides = rpc_by_method(self, "approval/decide")
+        self.assertEqual(decides[0]["params"]["choiceId"], bad_choice)
+        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
+        self.assertIn("approval_decide", logs)
+        for canary in ("CANARY_CHOICE", "CANARY_TOOL", "CANARY_RAWARGS"):
+            self.assertNotIn(canary, logs)
+            self.assertNotIn(canary, body.decode())
+        self.assertIn("redacted", logs)
+
+    def test_t_a11_ceiling_32030_single_exec_fallback(self) -> None:
+        plan = {"session_error": {"code": -32030, "message": "ceiling"}}
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertIn("fallback-ok", body.decode())
+        self.assertEqual(len(rpc_by_method(self, "session/start")), 1)
+        self.assertEqual(len(rpc_by_method(self, "approval/decide")), 0)
+        self.assertEqual(len(rpc_by_method(self, "turn/start")), 0)
+        self.assertEqual(proc_count(self, "serve"), 1)
+        self.assertEqual(proc_count(self, "exec"), 1)
+        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
+        self.assertIn("-32030", logs)
+        self.assertIn("1.4.9-test", logs)
+
+    def test_t_a11b_deny_unmatched_never_exec(self) -> None:
+        self._shrink_grace()
+        self.mod.APPROVAL_MODE = "denyUnmatched"
+        cases: list[tuple[str, dict]] = [
+            ("ceiling", {"session_error": {"code": -32030, "message": "x"}}),
+            ("eof", {"handshake_eof": True}),
+            ("hang", {"handshake_hang": True}),
+            ("no_session", {"no_session_id": True, "steps": []}),
+        ]
+        for name, plan in cases:
+            with self.subTest(case=name):
+                if name == "hang":
+                    self.mod.SERVE_SPAWN_TIMEOUT_S = 0.4
+                install_fake_msp(self, serve_plans=[plan])
+                status, body = bridge_request(self, turn_request(stream=True))
+                self.assertEqual(status, 200)
+                self.assertEqual(body.count(b"data: [DONE]"), 1)
+                self.assertIn(b"exec_fallback_disabled", body)
+                self.assertEqual(proc_count(self, "exec"), 0)
+                self.assertLessEqual(proc_count(self, "serve"), 1)
+                self.assertTrue(self._slot_free())
+        with self.subTest(case="spawn_failed"):
+            exec_calls: list[Any] = []
+
+            def fail_spawn(_self: Any) -> dict:
+                raise self.mod.ServeUnavailable("serve spawn failed: boom")
+
+            def fake_exec(run_self: Any) -> dict:
+                exec_calls.append(run_self)
+                return {"rc": 0, "state": "ok", "text": "x", "chunks": ["x"]}
+
+            with (
+                mock.patch.object(self.mod.ServeRun, "execute", fail_spawn),
+                mock.patch.object(self.mod.Run, "execute", fake_exec),
+            ):
+                status, body = bridge_request(self, turn_request(stream=True))
+            self.assertEqual(status, 200)
+            self.assertIn(b"exec_fallback_disabled", body)
+            self.assertEqual(exec_calls, [])
+
+    def test_t_a13_terminal_latch_discards_late_success(self) -> None:
+        self._shrink_grace()
+        choices = [
+            {
+                "choiceId": "c-abort",
+                "decision": "abort",
+                "label": "Abort",
+                "scope": "once",
+            }
+        ]
+        plan = {
+            "steps": [
+                {"approval": {"availableChoices": choices}},
+                {"approval_nowait": {}, "n": 5},
+                {"terminal": {"terminal": "completed", "text": "late-success"}},
+            ],
+            "decide_replies": [{"result": {"terminal": False}}],
+        }
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 502)
+        self.assertNotIn("late-success", body.decode())
+        self.assertLessEqual(len(rpc_by_method(self, "approval/decide")), 1)
+        self.assertEqual(proc_count(self, "exec"), 0)
+        # Молчание после denied: grace убивает группу, исход один.
+        plan = {"steps": [{"approval": {"availableChoices": choices}}, {"hang": True}]}
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200)
+        self.assertEqual(body.count(b"data: [DONE]"), 1)
+        self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
+
+    def test_t_a14_env_mode_gates_session_and_approve(self) -> None:
+        self._shrink_grace()
+        self.mod.APPROVAL_MODE = "denyUnmatched"
+        install_fake_msp(
+            self, serve_plans=[{"steps": [{"approval": {}}, {"hang": True}]}]
+        )
+        status, _ = bridge_request(self, turn_request())
+        self.assertEqual(status, 502)
+        starts = rpc_by_method(self, "session/start")
+        self.assertEqual(starts[0]["params"]["approvalMode"], "denyUnmatched")
+        chosen = [
+            d["params"]["choiceId"] for d in rpc_by_method(self, "approval/decide")
+        ]
+        self.assertNotIn("c-approve", chosen)
+        self.assertEqual(proc_count(self, "exec"), 0)
+        with mock.patch.dict(os.environ, {"MUSE_BRIDGE_APPROVAL_MODE": "bogus"}):
+            with self.assertRaises(Exception):
+                load_bridge()
+
+    def test_t_a15_tool_item_journal_without_args(self) -> None:
+        canary = "CANARY_TOOL_ARGS"
+        plan = {
+            "steps": [
+                {
+                    "tool_item": {
+                        "kind": "toolCall",
+                        "toolName": "web_search",
+                        "rawArgs": canary,
+                    }
+                },
+                fail_terminal(
+                    "[net-timeout] boom",
+                    timeToFirstTokenMs=123,
+                    usage={"outputTokens": 3},
+                ),
+            ]
+        }
+        install_fake_msp(self, serve_plans=[plan])
+        status, _ = bridge_request(self, turn_request())
+        self.assertEqual(status, 502)
+        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
+        self.assertIn("tool_item", logs)
+        self.assertIn("web_search", logs)
+        self.assertIn("tool_items=1", logs)
+        self.assertIn("ttft=1", logs)
+        self.assertNotIn(canary, logs)
+
+    def test_t_a16_setup_approval_blocks_any_new_process(self) -> None:
+        for when in ("initialize", "session/start"):
+            for req_mode in ("request", "requested"):
+                with self.subTest(when=when, mode=req_mode):
+                    plan = {
+                        "setup_approval": {
+                            "when": when,
+                            "mode": req_mode,
+                            "effect": "setup-effect",
+                            "after": "break",
+                        },
+                        "steps": [_OK_STEP],
+                    }
+                    install_fake_msp(self, serve_plans=[plan, ok_plan()])
+                    status, body = bridge_request(self, turn_request(stream=True))
+                    self.assertEqual(status, 200)
+                    self.assertEqual(body.count(b"data: [DONE]"), 1)
+                    self.assertTrue(any("error" in f for f in sse_frames(body)))
+                    self.assertEqual(proc_count(self, "serve"), 1)
+                    self.assertEqual(proc_count(self, "exec"), 0)
+                    self.assertEqual(effect_lines(self), ["setup-effect"])
+                    self.assertEqual(len(rpc_by_method(self, "approval/decide")), 1)
+        # Контроль: setup-транзиент без approval по-прежнему повторяется.
+        self.mod.TRANSIENT_BACKOFF_S = (0.0, 0.0)
+        self.mod.TRANSIENT_JITTER_S = 0.0
+        install_fake_msp(
+            self,
+            serve_plans=[
+                {"session_error": {"code": -32603, "message": "[net-timeout]"}},
+                ok_plan(),
+            ],
+        )
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertEqual(proc_count(self, "serve"), 2)
+
+    def test_startup_constants_validation(self) -> None:
+        with mock.patch.dict(os.environ, {"MUSE_BRIDGE_TIMEOUT_S": "100"}):
+            with self.assertRaises(Exception):
+                load_bridge()
+        with mock.patch.dict(os.environ, {"MUSE_BRIDGE_TIMEOUT_S": "1800"}):
+            self.assertIsNotNone(load_bridge())
+
+
+class TransientRetryTest(_BridgeScenario):
+    """REQ-MUSE-003 / AD-003 (T-R01..T-R12)."""
+
+    def setUp(self) -> None:
+        super().setUp()
+        self.mod.TRANSIENT_BACKOFF_S = (0.01, 0.01)
+        self.mod.TRANSIENT_JITTER_S = 0.0
+        self.mod.APPROVAL_CANCEL_GRACE_S = 0.4
+
+    def test_t_r01_pre_turn_markers_retry_new_serve(self) -> None:
+        markers = [
+            "[net-timeout]",
+            "timed out waiting for response data",
+            "network connection could not be opened",
+            "transport_connect_unreachable",
+        ]
+        for marker in markers:
+            with self.subTest(marker=marker):
+                install_fake_msp(
+                    self,
+                    serve_plans=[
+                        {"session_error": {"code": -32603, "message": marker}},
+                        ok_plan(),
+                    ],
+                )
+                status, body = bridge_request(self, turn_request(stream=True))
+                self.assertEqual(status, 200, body)
+                self.assertEqual(proc_count(self, "serve"), 2)
+                self.assertEqual(proc_count(self, "exec"), 0)
+                self.assertEqual(body.count(b"data: [DONE]"), 1)
+                self.assertFalse(any("error" in f for f in sse_frames(body)))
+        for marker in markers:
+            with self.subTest(terminal=marker):
+                install_fake_msp(
+                    self,
+                    serve_plans=[{"steps": [fail_terminal(marker)]}, ok_plan()],
+                )
+                status, _ = bridge_request(self, turn_request())
+                self.assertEqual(status, 502)
+                self.assertEqual(proc_count(self, "serve"), 1)
+
+    def test_t_r02_three_transient_failures_terminal(self) -> None:
+        plan = {"session_error": {"code": -32603, "message": "[net-timeout]"}}
+        install_fake_msp(self, serve_plans=[plan, plan, plan, ok_plan()])
+        status, _ = bridge_request(self, turn_request())
+        self.assertEqual(status, 502)
+        self.assertEqual(proc_count(self, "serve"), 3)
+        self.assertEqual(proc_count(self, "exec"), 0)
+        self.assertTrue(self._slot_free())
+
+    def test_t_r03_no_retry_guards(self) -> None:
+        with self.subTest(case="timeout_state"):
+            calls: list[int] = []
+
+            def fake_timeout(_self: Any) -> dict:
+                calls.append(1)
+                return {"rc": 1, "state": "timeout", "text": "", "err": "[net-timeout]"}
+
+            with mock.patch.object(self.mod.ServeRun, "execute", fake_timeout):
+                status, _ = bridge_request(self, turn_request())
+            self.assertEqual(status, 502)
+            self.assertEqual(len(calls), 1)
+        with self.subTest(case="spawn_failed_state"):
+            calls = []
+
+            def fake_spawn(_self: Any) -> dict:
+                calls.append(1)
+                return {
+                    "rc": 1,
+                    "state": "spawn_failed",
+                    "text": "",
+                    "err": "[net-timeout]",
+                }
+
+            with mock.patch.object(self.mod.ServeRun, "execute", fake_spawn):
+                status, _ = bridge_request(self, turn_request())
+            self.assertEqual(status, 502)
+            self.assertEqual(len(calls), 1)
+        with self.subTest(case="marker_in_success_text"):
+            install_fake_msp(
+                self,
+                serve_plans=[
+                    {
+                        "steps": [
+                            {
+                                "terminal": {
+                                    "terminal": "completed",
+                                    "text": "note [net-timeout] x",
+                                }
+                            }
+                        ]
+                    }
+                ],
+            )
+            status, body = bridge_request(self, turn_request())
+            self.assertEqual(status, 200, body)
+            self.assertEqual(proc_count(self, "serve"), 1)
+        with self.subTest(case="after_live_delta_observed_scope"):
+            self.mod.TRANSIENT_RETRY_SCOPE = "observed-items"
+            install_fake_msp(
+                self,
+                serve_plans=[
+                    {
+                        "steps": [
+                            {"summary": [0, "thinking"]},
+                            fail_terminal("[net-timeout]"),
+                        ]
+                    },
+                    ok_plan(),
+                ],
+            )
+            status, body = bridge_request(self, turn_request(stream=True))
+            self.assertEqual(status, 200)
+            self.assertEqual(proc_count(self, "serve"), 1)
+            self.assertIn(
+                "retry_blocked", self.mod.LOG_PATH.read_text(encoding="utf-8")
+            )
+
+    def test_t_r03b_unconfirmed_death_quarantine_then_release(self) -> None:
+        proc = CloseKillsGroupTest._spawn_group()
+        self.addCleanup(CloseKillsGroupTest._reap_group, proc)
+        calls: list[int] = []
+
+        def fake_transient(run_self: Any) -> dict:
+            calls.append(1)
+            run_self.proc = proc
+            raise self.mod.ServeUnavailable("[net-timeout] setup")
+
+        def fake_close(run_self: Any) -> None:
+            run_self.dead_confirmed = False
+
+        with (
+            mock.patch.object(self.mod.ServeRun, "execute", fake_transient),
+            mock.patch.object(self.mod.ServeRun, "close", fake_close),
+            mock.patch.object(self.mod, "_kill_group", lambda _p: None),
+        ):
+            status, _ = bridge_request(self, turn_request())
+            self.assertEqual(status, 502)
+            self.assertEqual(len(calls), 1)
+            self.assertEqual(len(self.mod._quarantined_slots), 1)
+            self.assertFalse(self._slot_free())
+            os.killpg(proc.pid, signal.SIGKILL)
+            proc.wait(timeout=5)
+            self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
+            self.assertEqual(len(self.mod._quarantined_slots), 0)
+
+    def test_t_r05_retry_gets_only_remaining_budget(self) -> None:
+        deadlines: list[float] = []
+        started = time.monotonic()
+
+        def fake_serve(run_self: Any) -> dict:
+            deadlines.append(float(run_self.exec_deadline))
+            if len(deadlines) == 1:
+                raise self.mod.ServeUnavailable("[net-timeout] setup")
+            return {
+                "rc": 0,
+                "state": "ok",
+                "text": "ok-now",
+                "chunks": ["ok-now"],
+                "err": "",
+            }
+
+        with mock.patch.object(self.mod.ServeRun, "execute", fake_serve):
+            status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertEqual(len(deadlines), 2)
+        self.assertAlmostEqual(deadlines[0], deadlines[1], places=6)
+        self.assertLess(deadlines[1], started + self.mod.TIMEOUT_S - 30)
+
+    def test_t_r06_admission_predicate_matrix(self) -> None:
+        cases: list[tuple[str, dict, int]] = [
+            ("turn_start_no_ack", {"turn_start_eof": True}, 502),
+            ("summary_eof", {"steps": [{"summary": [0, "x"]}, {"eof": True}]}, 502),
+            ("approval_exit", {"steps": [{"approval_then_exit": {}}]}, 502),
+            ("cancel_eof", {"steps": [{"approval": {"availableChoices": []}}]}, 502),
+        ]
+        for name, plan, want in cases:
+            with self.subTest(case=name):
+                install_fake_msp(self, serve_plans=[plan])
+                status, _ = bridge_request(self, turn_request())
+                self.assertEqual(status, want)
+                self.assertEqual(proc_count(self, "exec"), 0)
+        with self.subTest(case="handshake_eof_allows_exec"):
+            install_fake_msp(self, serve_plans=[{"handshake_eof": True}])
+            status, body = bridge_request(self, turn_request())
+            self.assertEqual(status, 200, body)
+            self.assertEqual(proc_count(self, "exec"), 1)
+
+    def test_t_r07_action_possible_single_effect(self) -> None:
+        with self.subTest(path="serve"):
+            install_fake_msp(
+                self,
+                serve_plans=[
+                    {"steps": [{"effect": "fx"}, fail_terminal("[net-timeout] mid")]},
+                    ok_plan(),
+                ],
+            )
+            status, _ = bridge_request(self, turn_request())
+            self.assertEqual(status, 502)
+            self.assertEqual(proc_count(self, "serve"), 1)
+            self.assertEqual(effect_lines(self), ["fx"])
+        with self.subTest(path="exec"):
+            install_fake_msp(
+                self,
+                serve_plans=[{"handshake_eof": True}],
+                exec_plans=[
+                    {"rc": 1, "stderr": "[net-timeout] exec", "effect": "exec-fx"}
+                ],
+            )
+            status, _ = bridge_request(self, turn_request())
+            self.assertEqual(status, 502)
+            self.assertEqual(proc_count(self, "exec"), 1)
+            self.assertEqual(effect_lines(self), ["exec-fx"])
+
+    def test_t_r07b_observed_items_scope(self) -> None:
+        self.mod.TRANSIENT_RETRY_SCOPE = "observed-items"
+        with self.subTest(case="no_signals_retries"):
+            install_fake_msp(
+                self,
+                serve_plans=[
+                    {"steps": [{"effect": "fx"}, fail_terminal("[net-timeout] mid")]},
+                    ok_plan(),
+                ],
+            )
+            status, body = bridge_request(self, turn_request())
+            self.assertEqual(status, 200, body)
+            self.assertEqual(proc_count(self, "serve"), 2)
+            self.assertIn("retry_scope", self.mod.LOG_PATH.read_text(encoding="utf-8"))
+        with self.subTest(case="tool_item_blocks"):
+            install_fake_msp(
+                self,
+                serve_plans=[
+                    {"steps": [{"tool_item": {}}, fail_terminal("[net-timeout] mid")]},
+                    ok_plan(),
+                ],
+            )
+            status, _ = bridge_request(self, turn_request())
+            self.assertEqual(status, 502)
+            self.assertEqual(proc_count(self, "serve"), 1)
+        with self.subTest(case="invalid_scope_stops_start"):
+            with mock.patch.dict(
+                os.environ, {"MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE": "bogus"}
+            ):
+                with self.assertRaises(Exception):
+                    load_bridge()
+
+    def test_t_r03c_client_gone_during_retry_pause(self) -> None:
+        self.mod.TRANSIENT_BACKOFF_S = (1.0, 1.0)
+        install_fake_msp(
+            self,
+            serve_plans=[
+                {"session_error": {"code": -32603, "message": "[net-timeout]"}},
+                ok_plan(),
+            ],
+        )
+        sock = self._open_request()
+        self.addCleanup(sock.close)
+        self.assertTrue(
+            wait_until(lambda: proc_count(self, "serve") == 1, 3.0),
+            "первый serve не стартовал",
+        )
+        time.sleep(0.3)
+        sock.close()
+        self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
+        time.sleep(0.3)
+        self.assertEqual(proc_count(self, "serve"), 1)
+
+    def test_t_r08_deadline_from_receipt_queue(self) -> None:
+        self.mod._slots = threading.Semaphore(2)
+        self.mod.TIMEOUT_S = 2.0
+        self.mod.FINISH_RESERVE_S = 0.3
+        self.mod.CLOSE_RESERVE_S = 0.2
+        self.mod.MIN_ATTEMPT_REMAINING_S = 0.8
+        install_fake_msp(self, serve_plans=[ok_plan({"delay": 1.2})])
+        results: list[tuple[int, bytes]] = []
+
+        def call() -> None:
+            results.append(bridge_request(self, turn_request()))
+
+        threads = [threading.Thread(target=call) for _ in range(3)]
+        started = time.monotonic()
+        for t in threads:
+            t.start()
+        for t in threads:
+            t.join(timeout=8)
+        elapsed = time.monotonic() - started
+        self.assertEqual(len(results), 3)
+        self.assertLess(elapsed, 3.5)
+        self.assertEqual(proc_count(self, "serve"), 2)
+        statuses = sorted(s for s, _ in results)
+        self.assertEqual(statuses, [200, 200, 503])
+
+    def test_t_r09_parallel_series_max_two_processes(self) -> None:
+        self.mod._slots = threading.Semaphore(2)
+        plan = {
+            "setup_delay": 0.25,
+            "session_error": {"code": -32603, "message": "[net-timeout]"},
+        }
+        install_fake_msp(self, serve_plans=[plan], track_concurrency=True)
+        results: list[tuple[int, bytes]] = []
+        threads = [
+            threading.Thread(
+                target=lambda: results.append(bridge_request(self, turn_request()))
+            )
+            for _ in range(2)
+        ]
+        for t in threads:
+            t.start()
+        for t in threads:
+            t.join(timeout=8)
+        self.assertEqual(sorted(s for s, _ in results), [502, 502])
+        counts = [int(x) for x in (self.tmp / "concurrency.log").read_text().split()]
+        self.assertTrue(counts)
+        self.assertLessEqual(max(counts), 2)
+
+    def test_t_r10_model_hangs_to_e_outcome_by_d(self) -> None:
+        self.mod.TIMEOUT_S = 2.6
+        self.mod.FINISH_RESERVE_S = 0.7
+        self.mod.CLOSE_RESERVE_S = 0.3
+        self.mod.MIN_ATTEMPT_REMAINING_S = 0.2
+        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
+        install_fake_msp(self, serve_plans=[{"steps": [{"hang": True}]}])
+        started = time.monotonic()
+        status, _ = bridge_request(self, turn_request())
+        elapsed = time.monotonic() - started
+        self.assertEqual(status, 502)
+        self.assertLess(elapsed, 2.6 + 1.5)
+        self.assertTrue(wait_until(self._slot_free, SCENARIO_DEADLINE_S))
+        self.assertEqual(proc_count(self, "exec"), 0)
+
+    def test_t_r11_setup_approval_no_replay_either_scope(self) -> None:
+        for scope in ("pre-action", "observed-items"):
+            with self.subTest(scope=scope):
+                self.mod.TRANSIENT_RETRY_SCOPE = scope
+                plan = {
+                    "setup_approval": {
+                        "when": "session/start",
+                        "mode": "requested",
+                        "effect": "setup-fx",
+                        "after": "break",
+                    },
+                    "steps": [_OK_STEP],
+                }
+                install_fake_msp(self, serve_plans=[plan, ok_plan()])
+                status, _ = bridge_request(self, turn_request())
+                self.assertEqual(status, 502)
+                self.assertEqual(proc_count(self, "serve"), 1)
+                self.assertEqual(proc_count(self, "exec"), 0)
+                self.assertEqual(effect_lines(self), ["setup-fx"])
+
+    def test_t_r12_slow_steady_delivery_cut_at_w(self) -> None:
+        # Детерминированный транспорт: каждый кадр быстрее L, сумма — дольше W.
+        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
+        self.mod.SSE_CHUNK_SIZE = 10
+        self.mod.SSE_CHUNK_DELAY_S = 0.0
+        handler = self.mod.Handler.__new__(self.mod.Handler)
+        starts: list[float] = []
+
+        class SlowWriter(io.BytesIO):
+            def write(self, data):  # type: ignore[override]
+                starts.append(time.monotonic())
+                time.sleep(0.05)
+                return super().write(data)
+
+        writer = SlowWriter()
+        handler._wlock = threading.Lock()
+        handler.wfile = writer
+        handler._sse_open = True
+        handler._live_sent_text = ""
+        w = time.monotonic() + 0.32
+        handler._write_deadline = w
+        handler._send_sse("muse-spark-1.3", "x" * 200, [], 1, 1, 0)
+        self.assertNotIn(b"data: [DONE]", writer.getvalue())
+        self.assertTrue(all(s <= w + 0.06 for s in starts), starts)
+        # Контроль: малый N успевает до W целиком с одним [DONE].
+        writer2 = SlowWriter()
+        handler.wfile = writer2
+        handler._sse_phase = "OPEN"
+        handler._client_gone = False
+        handler._write_deadline = time.monotonic() + 5
+        handler._send_sse("muse-spark-1.3", "hi", [], 1, 1, 0)
+        self.assertEqual(writer2.getvalue().count(b"data: [DONE]"), 1)
+        self.assertIn(b"hi", writer2.getvalue())
+
+
+class LiveReasoningTest(_BridgeScenario):
+    """REQ-MUSE-004 / AD-004 (T-L01..T-L09)."""
+
+    def test_t_l01_live_deltas_concat_equals_buffered(self) -> None:
+        plan = ok_plan(
+            {"summary": [0, "think-"]},
+            {"summary": [0, "more"]},
+            {"summary": [1, "second"]},
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200, body)
+        deltas = sse_deltas(body, "reasoning_content")
+        self.assertGreaterEqual(len(deltas), 3)
+        self.assertEqual("".join(deltas), "think-more\n\nsecond")
+        self.assertEqual("".join(sse_deltas(body, "content")), "hello")
+        self.assertEqual(body.count(b"data: [DONE]"), 1)
+
+    def test_t_l02_completed_only_summaries_not_lost(self) -> None:
+        plan = ok_plan({"reasoning_completed": ["alpha", "beta"]})
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200, body)
+        self.assertEqual(
+            "".join(sse_deltas(body, "reasoning_content")), "alpha\n\nbeta"
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertEqual(json.loads(body)["reasoning_summaries"], ["alpha", "beta"])
+
+    def test_t_l03_keepalive_data_chunks_preserved(self) -> None:
+        self.mod.KEEPALIVE_S = 0.05
+        install_fake_msp(self, serve_plans=[ok_plan({"delay": 0.25})])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200, body)
+        self.assertNotIn(b": keepalive", body)
+        self.assertEqual(body.count(b"data: [DONE]"), 1)
+        self.assertTrue(any(d == "" for d in sse_deltas(body, "content")[:-1]))
+
+    def test_t_l04_live_write_failure_is_terminal_not_exception(self) -> None:
+        handler = self.mod.Handler.__new__(self.mod.Handler)
+
+        class BrokenWriter(io.BytesIO):
+            def write(self, data):  # type: ignore[override]
+                raise OSError("closed peer")
+
+        handler._wlock = threading.Lock()
+        handler.wfile = BrokenWriter()
+        handler._sse_open = True
+        handler._live_sent_text = ""
+        self.assertFalse(handler._live_reasoning_sink("thinking"))
+        self.assertTrue(handler._client_gone)
+
+    def test_t_l05_model_retry_scheduled_log_only(self) -> None:
+        plan = ok_plan(
+            {
+                "model_retry": {
+                    "attempt": 1,
+                    "maxAttempts": 4,
+                    "retryDelayMs": 500,
+                    "errorKind": "network",
+                    "turnId": "turn-1",
+                }
+            }
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200, body)
+        self.assertEqual(sse_deltas(body, "reasoning_content"), [])
+        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
+        self.assertIn("modelRetryScheduled", logs)
+        self.assertIn("attempt=1", logs)
+
+    def test_t_l06_out_of_order_summaries_prefix_monotone(self) -> None:
+        plan = ok_plan(
+            {"summary": [0, "a"]},
+            {"summary": [1, "b"]},
+            {"summary": [0, "c"]},
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200, body)
+        self.assertEqual("".join(sse_deltas(body, "reasoning_content")), "ac\n\nb")
+        plan = ok_plan({"summary": [1, "b"]}, {"summary": [0, "a"]})
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200, body)
+        self.assertEqual("".join(sse_deltas(body, "reasoning_content")), "a\n\nb")
+
+    def test_t_l07_diverged_snapshot_sends_authoritative_full(self) -> None:
+        handler = self.mod.Handler.__new__(self.mod.Handler)
+        handler._wlock = threading.Lock()
+        handler.wfile = io.BytesIO()
+        handler._sse_open = True
+        handler._live_sent_text = "a"
+        handler._send_sse("muse-spark-1.3", "hi", [], 1, 1, 0, ["b", "c"])
+        deltas = sse_deltas(handler.wfile.getvalue(), "reasoning_content")
+        self.assertEqual(deltas, ["\n\nb\n\nc"])
+        logs = self.mod.LOG_PATH.read_text(encoding="utf-8")
+        self.assertIn("reasoning_diverged", logs)
+        handler2 = self.mod.Handler.__new__(self.mod.Handler)
+        handler2._wlock = threading.Lock()
+        handler2.wfile = io.BytesIO()
+        handler2._sse_open = True
+        handler2._live_sent_text = "a"
+        handler2._send_sse("muse-spark-1.3", "hi", [], 1, 1, 0, ["ab"])
+        self.assertEqual(
+            sse_deltas(handler2.wfile.getvalue(), "reasoning_content"), ["b"]
+        )
+
+    def _timing_handler(self) -> Any:
+        handler = self.mod.Handler.__new__(self.mod.Handler)
+        handler._wlock = threading.Lock()
+        handler._sse_open = True
+        handler._live_sent_text = ""
+        handler._write_deadline = time.monotonic() + 30
+        conn = SimpleNamespace(_timeout=None)
+
+        def gettimeout() -> Any:
+            return conn._timeout
+
+        def settimeout(value: Any) -> None:
+            conn._timeout = value
+
+        conn.gettimeout = gettimeout  # type: ignore[attr-defined]
+        conn.settimeout = settimeout  # type: ignore[attr-defined]
+        handler.connection = conn
+        return handler
+
+    def test_t_l08a_live_write_bounded_by_single_budget(self) -> None:
+        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
+        handler = self._timing_handler()
+
+        class TimeoutWriter(io.BytesIO):
+            def write(self, data):  # type: ignore[override]
+                limit = handler.connection.gettimeout() or 5.0
+                time.sleep(min(float(limit), 5.0))
+                raise TimeoutError("socket timeout")
+
+        handler.wfile = TimeoutWriter()
+        started = time.monotonic()
+        self.assertFalse(handler._live_reasoning_sink("thinking"))
+        self.assertLess(time.monotonic() - started, 1.0)
+        self.assertTrue(handler._client_gone)
+
+    def test_t_l08b_keepalive_blocking_first_bounds_sink(self) -> None:
+        self.mod.LIVE_WRITE_TIMEOUT_S = 0.25
+        handler = self._timing_handler()
+        release = threading.Event()
+        self.addCleanup(release.set)
+
+        class BlockWriter(io.BytesIO):
+            def write(self, data):  # type: ignore[override]
+                limit = handler.connection.gettimeout() or 5.0
+                if not release.wait(timeout=float(limit)):
+                    raise TimeoutError("socket timeout")
+                return super().write(data)
+
+        handler.wfile = BlockWriter()
+        results: dict[str, Any] = {}
+        ka = threading.Thread(
+            target=lambda: results.__setitem__(
+                "ka", handler._sse_write("data: ka\n\n", keepalive=True)
+            ),
+            daemon=True,
+        )
+        ka.start()
+        time.sleep(0.05)
+        started = time.monotonic()
+        self.assertFalse(handler._live_reasoning_sink("summary"))
+        self.assertLess(time.monotonic() - started, 1.0)
+        ka.join(timeout=2)
+        self.assertFalse(ka.is_alive())
+
+    def test_t_l08c_terminal_delivery_and_stop_bounded(self) -> None:
+        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
+        handler = self._timing_handler()
+
+        class TimeoutWriter(io.BytesIO):
+            def write(self, data):  # type: ignore[override]
+                limit = handler.connection.gettimeout() or 5.0
+                time.sleep(min(float(limit), 5.0))
+                raise TimeoutError("socket timeout")
+
+        handler.wfile = TimeoutWriter()
+        started = time.monotonic()
+        handler._send_sse("muse-spark-1.3", "hello", [], 1, 1, 0)
+        self.assertLess(time.monotonic() - started, 1.5)
+        self.assertTrue(handler._client_gone)
+
+    def test_t_l09_slow_steady_frames_stop_at_w(self) -> None:
+        self.mod.LIVE_WRITE_TIMEOUT_S = 0.2
+        self.mod.SSE_CHUNK_SIZE = 10
+        self.mod.SSE_CHUNK_DELAY_S = 0.0
+        handler = self.mod.Handler.__new__(self.mod.Handler)
+        starts: list[float] = []
+
+        class SlowWriter(io.BytesIO):
+            def write(self, data):  # type: ignore[override]
+                starts.append(time.monotonic())
+                time.sleep(0.05)
+                return super().write(data)
+
+        writer = SlowWriter()
+        handler._wlock = threading.Lock()
+        handler.wfile = writer
+        handler._sse_open = True
+        handler._live_sent_text = ""
+        w = time.monotonic() + 0.32
+        handler._write_deadline = w
+        handler._send_sse("muse-spark-1.3", "y" * 200, [], 1, 1, 0)
+        self.assertNotIn(b"data: [DONE]", writer.getvalue())
+        self.assertTrue(all(s <= w + 0.06 for s in starts), starts)
+        self.assertNotIn(b'"finish_reason": "stop"', writer.getvalue())
+
+
 if __name__ == "__main__":
     unittest.main(verbosity=2)

```

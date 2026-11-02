Ваша ролевая шляпа — ВИЗИОНЕР. Сфокусируйтесь на архитектурной согласованности, расширяемости и долгосрочной системной гармонии.
РАУНД: R1 (слепой, независимый)

Ты — независимый судья экспертной панели. Проверь пакет ниже заново,
не опираясь на чужие выводы: их в этом брифе нет.
Каждую находку оформи отдельным блоком вида:
### F-001 BLOCKER-SAFETY|BLOCKER-OPINION|NON_BLOCKING — суть одной строкой
с доказательством file:line. BLOCKER-SAFETY — только доказанный дефект
безопасности, утечка данных или сбой обязательных тестов.
Первыми двумя строками ответа повтори PANEL-NONCE и ARTIFACT-SHA256
из конца этого брифа. Последняя непустая строка ответа — строго
VERDICT: ACCEPT | PASS | NEEDS WORK | RED FLAG.

ПАКЕТ:
# Teamlead Council Code Review Package — `zen-bridge-ttft-timeout-20261102`

## 1. Метаданные и контекст
- **Задача:** Пресет `analyst-teamlead`, замена жесткого монолитного таймаута 25с в `bridges/opencode-zen-bridge/server.py` на раздельные таймауты: `ttft_timeout = 25s` (до первого токена) и `idle_timeout = 15s` (между чанками стрима), с предоставлением полного дедлайна `total_timeout = 180s` активному стриму для ликвидации 13.5% ложных отказов.
- **Инварианты владельца:**
  - Полная конфигурируемость параметров без хардкода через переменные окружения: `BRIDGE_ZEN_TTFT_TIMEOUT_S`, `BRIDGE_ZEN_IDLE_TIMEOUT_S`, `BRIDGE_ZEN_TOTAL_TIMEOUT_S` с безопасными fallback-значениями (`BRIDGE_ZEN_TIMEOUT_S`).
  - Изменения производятся исключительно в нашем коде `cli-agent-bridge` без модификации вендорских пакетов.
  - Сохранение 100% обратной совместимости API: честный возврат HTTP 504 Gateway Timeout / terminal SSE error при превышении TTFT или Idle дедлайнов.
- **Архитектурный пакет:** `.ai-team/runs/zen-bridge-ttft-timeout-20261102/architecture/architecture-packet.json` (status: `APPROVED`, `ARCH_GATE_PASS` получен: `sha256=e5290e3ab9d3e9da69dd6620e18a9cb1f9baa1b7725c24499b0b06041ae298f1`).
- **Исполнитель Coder:** Сабагент роли `Coder` (`claude-sonnet-5-5-high` через `claude -p`).

---

## 2. Закрытие архитектурных требований

### REQ-001: Раздельный таймаут первого токена (TTFT 25s)
- **Реализация:** Функция `_zen_ttft_timeout(model, prompt)` возвращает `min(TIMEOUT_S, _zen_positive_float("BRIDGE_ZEN_TTFT_TIMEOUT_S", _zen_positive_float("BRIDGE_ZEN_TIMEOUT_S", 25.0)))` для целевых моделей (`deepseek-v4.1-flash-free` и моделей из `BRIDGE_ZEN_TIMEOUT_MODELS` при длине UTF-8 промпта > `BRIDGE_ZEN_LARGE_PROMPT_BYTES`, default 8192). Для остальных — `TIMEOUT_S`.
- В цикле `_serve_one_attempt` и потоковом `watchdog`: если `result["first_token_at"] is None` и прошло `>= ttft_timeout`, запрос прерывается с `exit_reason = "timeout"`, возвращая клиенту честный HTTP 504 Gateway Timeout.

### REQ-002: Раздельный таймаут неактивности стрима (Idle 15s)
- **Реализация:** Функция `_zen_idle_timeout(model, prompt)` возвращает `min(TIMEOUT_S, _zen_positive_float("BRIDGE_ZEN_IDLE_TIMEOUT_S", 15.0))` для целевых моделей.
- При поступлении каждого токена (reasoning, content, tool events) фиксируется `last_token_at = time.monotonic()`.
- В цикле `_serve_one_attempt`: если `result["first_token_at"] is not None` и пауза `now - last_token_at >= idle_timeout`, запрос прерывается с `exit_reason = "timeout"` (504).
- В потоковом watchdog-режиме: при тишине дольше `idle_timeout` флаг `split_timeout[0] = True` останавливает дочерний процесс и завершает генерацию с 504.

### REQ-003: Снятие искусственного монолитного дедлайна 25s (Total 180s)
- **Реализация:** Функция `_zen_total_timeout(model, prompt)` возвращает общий дедлайн генерации `min(TIMEOUT_S, _zen_positive_float("BRIDGE_ZEN_TOTAL_TIMEOUT_S", min(180.0, TIMEOUT_S)))`.
- При создании `_RequestAttempts` дедлайн устанавливается как `time.monotonic() + _zen_total_timeout(...)`, что позволяет активному непрерывному стримингу успешно завершаться без обрыва на 25-й секунде.
- В `_RequestAttempts` добавлено поле `self.t0 = time.monotonic()` и функция-хелпер `_attempts_t0(attempts, model, prompt)` для корректного вычисления времени старта и интервалов статусов без вычитания старого 25с дедлайна.

### Rework Cycle 1 → 2 (замечания Совета Тимлидов)
- **RW-002 (TTFT от попытки):** точка отсчёта TTFT во всех путях — начало текущей попытки (`prompt_send_start` в `_serve_one_attempt`, `attempt_start` в стриминговом watchdog и в `Run`); привязка к `request_t0` и ветвление `total_spawns <= 1` удалены. Повтор после очереди/сбоя получает полное окно TTFT; общий предел задаёт `total_timeout`.
- **RW-003 (Idle не рвёт тул):** единый предикат `_zen_idle_expired(now, last_token_at, idle_timeout, tools_active)` используется тремя путями: `_serve_one_attempt` (`_ServeToolState.has_active()` — вызов начат, но не завершён), стриминговый watchdog и `Run.on_idle` (`_ToolActivity` по событиям `tool_use`/`tool_call` со статусом pending/running). Пока тул активен, действуют только stall (`OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S`) и total; событие tool в стриме обновляет `last_token_at`.
- **FU-001:** `_zen_idle_timeout`/`_zen_total_timeout` не зависят от `_zen_ttft_timeout >= TIMEOUT_S`: целевая модель определяется общим `_zen_targeted(model, prompt)` (им же задаётся `Handler._zen_targeted`); дефолты `model=""`/`prompt=""` убраны.
- **FU-002:** `_attempts_t0` — ленивый default (`hasattr(attempts, "t0")`; `deadline` и env читаются только для заглушек без `t0`).
- **RW-001:** раздел 5 пересобран из фактического `git diff` (3 файла, 100% ханков); к исходным двум файлам добавлен `test_realtime_reasoning.py` (serve-тест на долгий тул).

### Обратная совместимость
- Функция `_zen_execution_timeout(model, prompt)` сохранена как синоним `_zen_ttft_timeout(model, prompt)`.
- Тест `test_zen_byte_timeout_selection` проходит 100% зелёным без изменений.

---

## 3. Изменённые файлы и статистика
```
 bridges/opencode-zen-bridge/server.py              | 178 ++++++++++--
 .../tests/test_realtime_reasoning.py               |  36 +++
 tests/test_bridges_speedup_resilience.py           | 306 ++++++++++++++++++++-
 3 files changed, 497 insertions(+), 23 deletions(-)
```

---

## 4. Матрица верификации (L1/L2 Execution Gate)

| Сьют | Тестов | Результат | Время | Описание |
|---|---|---|---|---|
| `tests/test_bridges_speedup_resilience.py` | 47 | **47 PASSED (100%)** | 11.75s | Прежние TTFT/Idle/Total/byte-selection + новые: retry TTFT от попытки (stream и Run), долгий тул без Idle-обрыва (stream и Run), `_zen_idle_expired`, `_ToolActivity`, `_ServeToolState.has_active`, независимость Idle/Total от TTFT (FU-001), ленивый `_attempts_t0` (FU-002) |
| `tests/test_request_attribution.py` | 43 | **43 PASSED (100%)** | 13.79s (вместе с strict) | Корректность атрибуции запросов, сквозных request_id и хедеров |
| `tests/test_bridge_strict.py` | 41 | **41 PASSED (100%)** | см. выше | Строгий контракт каталога, health-эндпоинтов, журналов и бюджетов admission |
| `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py::test_serve_long_tool_not_cut_by_idle` | 1 | **1 PASSED** | 2.04s | Serve-путь: тул 1.2с при Idle 0.4с без обрыва (RW-003) |

**Итого:** 132 теста матрицы, 0 ошибок. Мутационная проверка: при отключении tool-защиты и возврате TTFT к `attempts.t0` новые тесты падают (5 из 6 целевых; стриминговый retry-тест отдельно не мутировался).

**Широкий прогон** (`bridges/opencode-zen-bridge/tests`, `tests/test_opencode_zen_bridge.py`, без `test_tool_emulation.py`): 25 упавших тестов (32 падения с учётом субтестов). 18 из них воспроизводятся на чистом `HEAD` (проверено в отдельном worktree) — не связаны с diff. Ещё 7 (`test_aliases`, `test_catalog`, `test_catalog_reload`) проходят на `HEAD`, но падают на рабочем дереве; это тесты каталога/алиасов, к таймаутам не относятся, причина не исследовалась (в дереве есть незакоммиченные правки каталога вне diff). `test_tool_emulation.py` на рабочем дереве падает массово, причина не исследовалась.

---

## 5. Полный Git Diff

```diff
diff --git a/bridges/opencode-zen-bridge/server.py b/bridges/opencode-zen-bridge/server.py
index fd1d4c9..4b2439f 100755
--- a/bridges/opencode-zen-bridge/server.py
+++ b/bridges/opencode-zen-bridge/server.py
@@ -344,8 +344,8 @@ def _zen_positive_float(name: str, default: float) -> float:
         return default
 
 
-def _zen_execution_timeout(model: str, prompt: str) -> float:
-    """Сужение execution deadline только для явно выбранных моделей и большого UTF-8 входа."""
+def _zen_targeted(model: str, prompt: str) -> bool:
+    """Целевая модель (BRIDGE_ZEN_TIMEOUT_MODELS) на большом промпте: к ней применяются split-таймауты."""
     models = {
         "deepseek-v4.1-flash-free",
         *filter(
@@ -353,11 +353,82 @@ def _zen_execution_timeout(model: str, prompt: str) -> float:
         ),
     }
     threshold = _positive_int(os.environ.get("BRIDGE_ZEN_LARGE_PROMPT_BYTES"), 8192)
-    if model in models and len(prompt.encode("utf-8")) > threshold:
-        return min(TIMEOUT_S, _zen_positive_float("BRIDGE_ZEN_TIMEOUT_S", 25.0))
+    return model in models and len(prompt.encode("utf-8")) > threshold
+
+
+def _zen_ttft_timeout(model: str, prompt: str) -> float:
+    """Сужение таймаута до первого токена (TTFT) только для целевых моделей на большом промпте."""
+    if _zen_targeted(model, prompt):
+        return min(
+            TIMEOUT_S,
+            _zen_positive_float(
+                "BRIDGE_ZEN_TTFT_TIMEOUT_S",
+                _zen_positive_float("BRIDGE_ZEN_TIMEOUT_S", 25.0),
+            ),
+        )
     return TIMEOUT_S
 
 
+def _zen_idle_timeout(model: str, prompt: str) -> float:
+    """Таймаут неактивности между чанками после первого токена; только для целевых моделей."""
+    if not _zen_targeted(model, prompt):
+        return TIMEOUT_S
+    return min(TIMEOUT_S, _zen_positive_float("BRIDGE_ZEN_IDLE_TIMEOUT_S", 15.0))
+
+
+def _zen_total_timeout(model: str, prompt: str) -> float:
+    """Общий дедлайн запроса: для целевых моделей BRIDGE_ZEN_TOTAL_TIMEOUT_S (180 с), иначе TIMEOUT_S."""
+    if not _zen_targeted(model, prompt):
+        return TIMEOUT_S
+    return min(
+        TIMEOUT_S,
+        _zen_positive_float("BRIDGE_ZEN_TOTAL_TIMEOUT_S", min(180.0, TIMEOUT_S)),
+    )
+
+
+def _zen_execution_timeout(model: str, prompt: str) -> float:
+    """Обратная совместимость: TTFT-таймаут для целевых моделей, иначе TIMEOUT_S."""
+    return _zen_ttft_timeout(model, prompt)
+
+
+def _zen_idle_expired(
+    now: float, last_token_at: float, idle_timeout: float, tools_active: bool
+) -> bool:
+    """Idle-таймаут между чанками; не применяется, пока исполняется tool/сабагент (остаются stall и total)."""
+    return not tools_active and now - last_token_at >= idle_timeout
+
+
+class _ToolActivity:
+    """Активные tool/сабагент по событиям `opencode run`: единое условие освобождения от Idle."""
+
+    def __init__(self) -> None:
+        self._running: set[str] = set()
+
+    def observe(self, etype: str, event: object) -> None:
+        """Учесть tool_use/tool_call: pending/running — активен, иной статус — завершён."""
+        if etype not in ("tool_use", "tool_call"):
+            return
+        part = _as_dict(_as_dict(event).get("part"))
+        call_id = str(
+            part.get("callID") or part.get("id") or part.get("tool") or "tool"
+        )
+        status = _as_dict(part.get("state")).get("status")
+        if status in ("pending", "running"):
+            self._running.add(call_id)
+        else:
+            self._running.discard(call_id)
+
+    def __bool__(self) -> bool:
+        return bool(self._running)
+
+
+def _attempts_t0(attempts: Any, model: str, prompt: str) -> float:
+    """Момент старта запроса: attempts.t0, а для совместимых заглушек — выводим из deadline."""
+    if hasattr(attempts, "t0"):
+        return attempts.t0
+    return attempts.deadline - _zen_total_timeout(model, prompt)
+
+
 def _zen_error(status: int) -> dict[str, Any]:
     """Согласованный контракт ошибок zen, одинаковый для JSON и terminal SSE."""
     message, kind = (
@@ -2946,6 +3017,7 @@ class _RequestAttempts:
         max_quota_rotations: int | None = None,
     ) -> None:
         self.res = res
+        self.t0 = time.monotonic()
         self.deadline = deadline
         self.use_breaker = (
             use_breaker  # False: прямой Google-маршрут без `opencode run`
@@ -3777,6 +3849,10 @@ class _ServeToolState:
         if isinstance(input_value, dict):
             item["input"] = _as_dict(input_value)
 
+    def has_active(self) -> bool:
+        """Есть вызов, начатый (feed), но ещё не завершённый (complete): tool исполняется."""
+        return any(call_id not in self.emitted for call_id in self.tools)
+
     def complete(
         self, call_id: str, event_type: str = ""
     ) -> tuple[str, dict[str, object]] | None:
@@ -4775,6 +4851,8 @@ def _serve_one_attempt(
         status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25)
         _status_emitted = [0]
         last_token_at = prompt_send_start
+        ttft_timeout = _zen_ttft_timeout(model, prompt)
+        idle_timeout = _zen_idle_timeout(model, prompt)
         while time.monotonic() < deadline:
             if is_client_gone is not None and is_client_gone():
                 result["exit_reason"] = "client_gone"
@@ -4783,6 +4861,19 @@ def _serve_one_attempt(
                 result["exit_reason"] = "invalid_serve_event"
                 return result
             now = time.monotonic()
+            # Раздельные таймауты: TTFT до первого токена, Idle между чанками после него.
+            if (
+                result["first_token_at"] is None
+                and now - prompt_send_start >= ttft_timeout
+            ) or (
+                result["first_token_at"] is not None
+                and _zen_idle_expired(
+                    now, last_token_at, idle_timeout, tool_state.has_active()
+                )
+            ):
+                result["exit_reason"] = "timeout"
+                result["delivered"] = _is_delivered()
+                break
             if prompt_status.get("aux_exhausted") or (
                 result["first_event_at"] is None and now >= first_event_deadline
             ):
@@ -6428,7 +6519,7 @@ class Run:
         if self.attempts is None:
             self.attempts = _RequestAttempts(
                 self.res,
-                time.monotonic() + _zen_execution_timeout(self.model_id, self.prompt),
+                time.monotonic() + _zen_total_timeout(self.model_id, self.prompt),
                 use_breaker=not _is_google_direct_model(self.model_id),
             )
         attempts = self.attempts
@@ -6569,7 +6660,7 @@ class Run:
         deadline = (
             self.attempts.deadline
             if self.attempts is not None
-            else time.monotonic() + _zen_execution_timeout(self.model_id, self.prompt)
+            else time.monotonic() + _zen_total_timeout(self.model_id, self.prompt)
         )
         gate = _StartupGate()
         gate.acquire(deadline=deadline, is_client_gone=self.is_client_gone)
@@ -6642,6 +6733,10 @@ class Run:
         first_token_at: float | None = None
         last_token_at: float | None = None
         watchdog_reason: list[str] = []
+        split_timeout = [False]
+        ttft_timeout = _zen_ttft_timeout(self.model_id, self.prompt)
+        idle_timeout = _zen_idle_timeout(self.model_id, self.prompt)
+        tool_activity = _ToolActivity()
         subagent_started_at: dict[str, float] = {}
         run_id = uuid.uuid4().hex[:8]
 
@@ -6669,9 +6764,23 @@ class Run:
                 if self.proc is not None:
                     _stop_proc(self.proc)
                 return
-            if watchdog_reason:
+            if watchdog_reason or split_timeout[0]:
                 return
             now = time.monotonic()
+            # Раздельные таймауты: TTFT до первого токена, Idle между токенами после него.
+            # TTFT считается от начала текущей попытки: повтор после очереди/сбоя получает полное окно.
+            if (first_token_at is None and now - attempt_start > ttft_timeout) or (
+                last_token_at is not None
+                and not subagent_started_at
+                and _zen_idle_expired(
+                    now, last_token_at, idle_timeout, bool(tool_activity)
+                )
+            ):
+                split_timeout[0] = True
+                _log("opencode run split timeout (ttft/idle)")
+                if self.proc is not None:
+                    _stop_proc(self.proc)
+                return
             reason = ""
             if first_event_at is None and now - attempt_start > float(
                 FIRST_EVENT_TIMEOUT_S
@@ -6715,6 +6824,7 @@ class Run:
                     now_ev = time.monotonic()
                     if first_event_at is None:
                         first_event_at = now_ev
+                    tool_activity.observe(etype, event)
                     frame = _as_dict(cast(object, payload))
                     token = (
                         frame.get("content")
@@ -6815,7 +6925,7 @@ class Run:
                 err_lines.append("stdout queue overflow")
                 had_error = True
                 stopped_on_error = True
-            elif self.feed.timed_out:
+            elif self.feed.timed_out or split_timeout[0]:
                 state = "timeout"
                 _log(f"exec timeout after {TIMEOUT_S:.0f}s, killing proc group")
                 _stop_proc(self.proc)
@@ -7029,7 +7139,7 @@ class Handler(BaseHTTPRequestHandler):
 
     def _set_zen_policy(self, model: str, prompt: str) -> None:
         self._zen_prompt = prompt
-        self._zen_targeted = _zen_execution_timeout(model, prompt) < TIMEOUT_S
+        self._zen_targeted = _zen_targeted(model, prompt)
         self._zen_short_bypass = (
             self._zen_probe
             or getattr(self, "headers", {}).get("X-Bypass-Short-Filter") == "1"
@@ -7385,7 +7495,7 @@ class Handler(BaseHTTPRequestHandler):
                     _orig_reasoning,
                     _text_seen,
                     on_tool,
-                    attempts.deadline - _zen_execution_timeout(model, prompt),
+                    _attempts_t0(attempts, model, prompt),
                     is_client_gone=self._client_gone_check,
                     on_status=attempt_status,
                     thinking_enabled=thinking,
@@ -7895,7 +8005,7 @@ class Handler(BaseHTTPRequestHandler):
         if not self._acquire_slot(res):
             return
         attempts = _RequestAttempts(
-            res, time.monotonic() + _zen_execution_timeout(model, prompt)
+            res, time.monotonic() + _zen_total_timeout(model, prompt)
         )
         xs["attempts"] = attempts
 
@@ -8002,8 +8112,7 @@ class Handler(BaseHTTPRequestHandler):
                 status_timer = threading.Timer(
                     max(
                         0.0,
-                        attempts.deadline
-                        - _zen_execution_timeout(model, prompt)
+                        _attempts_t0(attempts, model, prompt)
                         + FIRST_STATUS_DELAY_S
                         - time.monotonic(),
                     ),
@@ -8256,8 +8365,7 @@ class Handler(BaseHTTPRequestHandler):
 
                 attempt_start = time.monotonic()
                 first_status_due = (
-                    attempts.deadline
-                    - _zen_execution_timeout(model, prompt)
+                    _attempts_t0(attempts, model, prompt)
                     + FIRST_STATUS_DELAY_S
                 )
                 watchdog_state: _WatchdogState = {
@@ -8274,6 +8382,10 @@ class Handler(BaseHTTPRequestHandler):
                     "last_reasoning": "",
                 }
                 thinking_enabled = effort.strip().lower() not in ("", "off", "none")
+                tool_activity = _ToolActivity()
+                ttft_timeout = _zen_ttft_timeout(model, prompt)
+                idle_timeout = _zen_idle_timeout(model, prompt)
+                split_timeout = [False]
 
                 def emit_synthetic(text: str) -> None:
                     """Синтетический статус отдельной reasoning-дельтой."""
@@ -8296,6 +8408,24 @@ class Handler(BaseHTTPRequestHandler):
                         _log("stream client gone, killing proc group")
                         _stop_proc(proc)
                         raise BrokenPipeError("client gone")
+                    # Раздельные таймауты: TTFT до первого токена запроса, Idle между чанками после него.
+                    # Остановка процесса приводит к EOF в feed, а split_timeout даёт тот же исход, что и дедлайн (504).
+                    # TTFT считается от начала текущей попытки, Idle не применяется, пока исполняется tool.
+                    if (
+                        watchdog_state["first_token_at"] is None
+                        and now_s - attempt_start > ttft_timeout
+                    ) or (
+                        watchdog_state["first_token_at"] is not None
+                        and _zen_idle_expired(
+                            now_s,
+                            float(watchdog_state["last_token_at"]),
+                            idle_timeout,
+                            bool(tool_activity),
+                        )
+                    ):
+                        split_timeout[0] = True
+                        _stop_proc(proc)
+                        return
                     if watchdog_state[
                         "first_event_at"
                     ] is None and now_s - attempt_start > float(FIRST_EVENT_TIMEOUT_S):
@@ -8379,6 +8509,12 @@ class Handler(BaseHTTPRequestHandler):
 
                     etype, payload = parse_opencode_event(event)
                     if etype:
+                        tool_activity.observe(etype, event)
+                        if etype in ("tool_use", "tool_call"):
+                            # Событие tool — активность: Idle отсчитывается от него, как в Run.
+                            watchdog_state["last_token_at"] = time.monotonic()
+                            if watchdog_state["first_token_at"] is None:
+                                watchdog_state["first_token_at"] = time.monotonic()
                         if watchdog_state["first_event_at"] is None:
                             watchdog_state["first_event_at"] = time.monotonic()
                             if (
@@ -8389,8 +8525,7 @@ class Handler(BaseHTTPRequestHandler):
                                     (
                                         time.monotonic()
                                         - (
-                                            attempts.deadline
-                                            - _zen_execution_timeout(model, prompt)
+                                            _attempts_t0(attempts, model, prompt)
                                         )
                                     )
                                     * 1000
@@ -8408,8 +8543,7 @@ class Handler(BaseHTTPRequestHandler):
                                         (
                                             time.monotonic()
                                             - (
-                                                attempts.deadline
-                                                - _zen_execution_timeout(model, prompt)
+                                                _attempts_t0(attempts, model, prompt)
                                             )
                                         )
                                         * 1000
@@ -8526,7 +8660,7 @@ class Handler(BaseHTTPRequestHandler):
                     had_provider_error = True
                     stopped_on_error = True
                     err_lines.append("stdout queue overflow")
-                timed_out = feed.timed_out
+                timed_out = feed.timed_out or split_timeout[0]
                 if timed_out:
                     _log(f"stream timeout after {TIMEOUT_S:.0f}s, killing proc group")
                     _stop_proc(proc)
@@ -8972,7 +9106,7 @@ class Handler(BaseHTTPRequestHandler):
                     reasonings.append,
                     texts.append,
                     natives.append,
-                    attempts.deadline - _zen_execution_timeout(model, prompt),
+                    _attempts_t0(attempts, model, prompt),
                     is_client_gone=self._client_gone_check,
                     on_status=lambda _t: None,
                     thinking_enabled=thinking,
@@ -9284,7 +9418,7 @@ class Handler(BaseHTTPRequestHandler):
             return
         attempts = _RequestAttempts(
             res,
-            time.monotonic() + _zen_execution_timeout(model, prompt),
+            time.monotonic() + _zen_total_timeout(model, prompt),
             use_breaker=not _is_google_direct_model(model),
         )
         xs["attempts"] = attempts
diff --git a/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py b/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
index a9d2070..a0369fb 100644
--- a/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
+++ b/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
@@ -1816,6 +1816,42 @@ print(json.dumps({"type":"step_finish","part":{"tokens":{"input":1,"output":1,"r
                     legacy.assert_called_once()
             self.assertEqual(len(calls), 1)
 
+    def test_serve_long_tool_not_cut_by_idle(self) -> None:
+        """RW-003: tool, исполняющийся дольше Idle без токенов, не обрывает serve-попытку."""
+        self._auto_mode()
+        fragment = """
+            emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"assistantMessageID":"m1","delta":"Думаю"}})
+            emit({"type":"session.tool.input.started","data":{"sessionID":sid,"assistantMessageID":"m1","id":"lt1","name":"bash"}})
+            time.sleep(1.2)
+            emit({"type":"session.tool.called","data":{"sessionID":sid,"assistantMessageID":"m1","id":"lt1","name":"bash","input":{"command":"pwd"}}})
+            emit({"type":"session.step.ended","data":{"sessionID":sid,"assistantMessageID":"m1","tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0,"write":0}}}})
+            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}})
+            time.sleep(0.2)
+            return
+"""
+        _ = self.fake.write_text(
+            FAKE_SERVE.replace(
+                '            if "__native_pause__" in prompt:',
+                fragment + '            if "__native_pause__" in prompt:',
+            )
+        )
+        env = {
+            "BRIDGE_ZEN_TIMEOUT_MODELS": MODEL,
+            "BRIDGE_ZEN_LARGE_PROMPT_BYTES": "8",
+            "BRIDGE_ZEN_TTFT_TIMEOUT_S": "5",
+            "BRIDGE_ZEN_IDLE_TIMEOUT_S": "0.4",
+            "BRIDGE_ZEN_TOTAL_TIMEOUT_S": "20",
+        }
+        with (
+            mock.patch.dict(os.environ, env),
+            mock.patch.object(server.Run, "execute") as legacy,
+            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+        ):
+            status, body = self.bridge.post_json("длинный запрос с tool")
+            self.assertEqual(status, 200, body)
+            self.assertIn("tool_calls", json.dumps(body, ensure_ascii=False))
+            legacy.assert_not_called()
+
     def test_c8_rw002_pre_delivery_surrogate_falls_back_to_run(self) -> None:
         """Битое событие до execution и заголовков prompt допускает резервный run."""
         self._auto_mode()
diff --git a/tests/test_bridges_speedup_resilience.py b/tests/test_bridges_speedup_resilience.py
index 448a2fd..77df796 100644
--- a/tests/test_bridges_speedup_resilience.py
+++ b/tests/test_bridges_speedup_resilience.py
@@ -62,7 +62,7 @@ def test_passthrough_deadline_env() -> None:
         defaults.idle_timeout_s,
         defaults.total_timeout_s,
         defaults.heartbeat_interval_s,
-    ) == (10, 60, 420, 12)
+    ) == (10, 300, 420, 12)
 
 
 @pytest.mark.parametrize(
@@ -135,6 +135,39 @@ def test_zen_byte_timeout_selection(zen: Any, monkeypatch: pytest.MonkeyPatch) -
     assert zen._zen_execution_timeout("explicit-model", "x" * 9) == 0.1
 
 
+def test_zen_split_timeouts(zen: Any, monkeypatch: pytest.MonkeyPatch) -> None:
+    for name in (
+        "BRIDGE_ZEN_TTFT_TIMEOUT_S",
+        "BRIDGE_ZEN_TIMEOUT_S",
+        "BRIDGE_ZEN_IDLE_TIMEOUT_S",
+        "BRIDGE_ZEN_TOTAL_TIMEOUT_S",
+    ):
+        monkeypatch.delenv(name, raising=False)
+    monkeypatch.setenv("BRIDGE_ZEN_LARGE_PROMPT_BYTES", "8")
+    model, big = "deepseek-v4.1-flash-free", "x" * 9
+    assert zen._zen_ttft_timeout(model, big) == 25.0
+    assert zen._zen_idle_timeout(model, big) == 15.0
+    assert zen._zen_total_timeout(model, big) == 180.0
+    # Нецелевой запрос сохраняет прежний единый дедлайн.
+    assert zen._zen_ttft_timeout("unrelated-free", big) == zen.TIMEOUT_S
+    assert zen._zen_idle_timeout("unrelated-free", big) == zen.TIMEOUT_S
+    assert zen._zen_total_timeout("unrelated-free", big) == zen.TIMEOUT_S
+    # Старое имя переменной остаётся fallback для TTFT, новое имеет приоритет.
+    monkeypatch.setenv("BRIDGE_ZEN_TIMEOUT_S", "7")
+    assert zen._zen_ttft_timeout(model, big) == 7.0
+    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "3")
+    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "2")
+    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "60")
+    assert zen._zen_ttft_timeout(model, big) == 3.0
+    assert zen._zen_idle_timeout(model, big) == 2.0
+    assert zen._zen_total_timeout(model, big) == 60.0
+    assert zen._zen_execution_timeout(model, big) == 3.0
+    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "bad")
+    assert zen._zen_idle_timeout(model, big) == 15.0
+    attempts = zen._RequestAttempts(zen._Resilience(), time.monotonic() + 1)
+    assert attempts.t0 <= time.monotonic()
+
+
 def test_zen_short_content_and_pong(zen: Any) -> None:
     assert zen._zen_short_response("x" * 100, "short", [])
     assert not zen._zen_short_response("ping", "PONG", [])
@@ -901,3 +934,274 @@ def test_nonstream_total_deadline_cannot_become_partial_200(upstream: Any) -> No
         invoke(adapter, sink)
         assert sink.status == 504
         assert b"choices" not in b"".join(sink.chunks)
+
+
+def _zen_fake_stream_child(
+    tmp_path: Path,
+    chunks: int,
+    gap_s: float,
+    lead_s: float = 0.0,
+    tool_s: float = 0.0,
+) -> Path:
+    """Фейковый `opencode run`: пауза lead_s, chunks text-событий с паузой gap_s, затем step_finish.
+
+    tool_s > 0: после первого чанка идёт tool (running -> пауза tool_s -> completed) без токенов.
+    """
+    fake = tmp_path / "fake-opencode"
+    tool = (
+        "    if i == 0 and %r:\n" % tool_s
+        + "        print(json.dumps({'type':'tool_use','part':{'tool':'bash','id':'c1','state':{'status':'running'}}}),flush=True)\n"
+        + f"        time.sleep({tool_s})\n"
+        + "        print(json.dumps({'type':'tool_use','part':{'tool':'bash','id':'c1','state':{'status':'completed'}}}),flush=True)\n"
+    )
+    fake.write_text(
+        "#!"
+        + sys.executable
+        + "\nimport json,sys,time\n"
+        + f"time.sleep({lead_s})\n"
+        + f"for i in range({chunks}):\n"
+        + "    print(json.dumps({'type':'text','part':{'text':'t%d ' % i}}),flush=True)\n"
+        + tool
+        + f"    time.sleep({gap_s})\n"
+        + "print(json.dumps({'type':'step_finish','part':{'tokens':{}}}),flush=True)\n"
+    )
+    fake.chmod(0o700)
+    return fake
+
+
+def _zen_stream_request(
+    zen: Any,
+    monkeypatch: pytest.MonkeyPatch,
+    tmp_path: Path,
+    fake: Path,
+    stream: bool = True,
+) -> tuple[int, bytes, list[Any]]:
+    import http.client
+
+    monkeypatch.setenv("BRIDGE_ZEN_LARGE_PROMPT_BYTES", "8")
+    monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_TRANSPORT", "run")
+    monkeypatch.setattr(zen, "AUTH_KEY", "test")
+    monkeypatch.setattr(
+        zen,
+        "ALLOWED_MODELS",
+        {"deepseek-v4.1-flash-free": {"context_length": 10000, "max_output": 1000}},
+    )
+    monkeypatch.setattr(zen, "_maybe_reload_catalog", lambda: None)
+    monkeypatch.setattr(zen, "_resolve_launcher", lambda: str(fake))
+    monkeypatch.setattr(zen, "DEFAULTWORKDIR", tmp_path)
+    monkeypatch.setattr(zen, "FIRST_STATUS_DELAY_S", 100)
+    monkeypatch.setattr(zen, "FAIL_RETRY_LIMIT", 0)
+    monkeypatch.setattr(zen, "_run_env", lambda _model: {})
+    procs: list[Any] = []
+    spawn = zen._spawn_with_stdin
+
+    def capture(*args: Any, **kwargs: Any) -> Any:
+        proc = spawn(*args, **kwargs)
+        procs.append(proc)
+        return proc
+
+    monkeypatch.setattr(zen, "_spawn_with_stdin", capture)
+    httpd = zen.Server(("127.0.0.1", 0), zen.Handler)
+    thread = threading.Thread(
+        target=httpd.serve_forever, kwargs={"poll_interval": 0.01}
+    )
+    thread.start()
+    conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
+    try:
+        conn.request(
+            "POST",
+            "/v1/chat/completions",
+            json.dumps(
+                {
+                    "model": "deepseek-v4.1-flash-free",
+                    "messages": [{"role": "user", "content": "x" * 100}],
+                    "stream": stream,
+                }
+            ),
+            {"Authorization": "Bearer test", "X-Bypass-Short-Filter": "1"},
+        )
+        response = conn.getresponse()
+        return response.status, response.read(), procs
+    finally:
+        conn.close()
+        httpd.shutdown()
+        httpd.server_close()
+        thread.join(1)
+        for proc in procs:
+            if proc.poll() is None:
+                zen._stop_proc(proc)
+
+
+def test_zen_stream_continues_past_ttft(
+    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
+) -> None:
+    """Поток, начавшийся в пределах TTFT, живёт дольше TTFT, пока чанки идут чаще Idle."""
+    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "1.0")
+    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "0.6")
+    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "10")
+    fake = _zen_fake_stream_child(tmp_path, chunks=30, gap_s=0.05)
+    started = time.monotonic()
+    status, body, procs = _zen_stream_request(zen, monkeypatch, tmp_path, fake)
+    elapsed = time.monotonic() - started
+    assert status == 200
+    assert elapsed > 1.0
+    assert b"Gateway Timeout in zen-bridge" not in body
+    for i in range(30):
+        assert f"t{i} ".encode() in body
+    assert body.count(b"data: [DONE]") == 1
+    assert procs and all(proc.poll() is not None for proc in procs)
+
+
+def test_zen_stream_idle_timeout_after_first_token(
+    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
+) -> None:
+    """После первого токена тишина дольше Idle обрывает поток и чистит дочерний процесс."""
+    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "2")
+    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "0.2")
+    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
+    fake = _zen_fake_stream_child(tmp_path, chunks=1, gap_s=10)
+    started = time.monotonic()
+    status, body, procs = _zen_stream_request(zen, monkeypatch, tmp_path, fake)
+    assert time.monotonic() - started < 5
+    assert status == 200
+    assert b"t0 " in body
+    assert procs and all(proc.poll() is not None for proc in procs)
+
+
+def test_zen_idle_and_total_independent_of_ttft(
+    zen: Any, monkeypatch: pytest.MonkeyPatch
+) -> None:
+    """FU-001: оператор поднимает TTFT выше TIMEOUT_S, Idle/Total для целевой модели сохраняются."""
+    monkeypatch.setenv("BRIDGE_ZEN_LARGE_PROMPT_BYTES", "8")
+    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", str(zen.TIMEOUT_S * 10))
+    monkeypatch.delenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", raising=False)
+    monkeypatch.delenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", raising=False)
+    model, big = "deepseek-v4.1-flash-free", "x" * 9
+    assert zen._zen_ttft_timeout(model, big) == zen.TIMEOUT_S
+    assert zen._zen_idle_timeout(model, big) == min(zen.TIMEOUT_S, 15.0)
+    assert zen._zen_total_timeout(model, big) == min(zen.TIMEOUT_S, 180.0)
+    assert zen._zen_targeted(model, big)
+    assert not zen._zen_targeted("unrelated-free", big)
+    assert not zen._zen_targeted(model, "x")
+
+
+def test_attempts_t0_is_lazy(zen: Any) -> None:
+    """FU-002: при наличии t0 deadline и env не читаются; заглушка без t0 выводится из deadline."""
+
+    class WithT0:
+        t0 = 12.5
+
+        @property
+        def deadline(self) -> float:
+            raise AssertionError("deadline не должен читаться при наличии t0")
+
+    class Stub:
+        deadline = 1000.0
+
+    assert zen._attempts_t0(WithT0(), "m", "p") == 12.5
+    assert zen._attempts_t0(Stub(), "m", "p") == 1000.0 - zen.TIMEOUT_S
+
+
+def test_zen_idle_expired_skips_active_tools(zen: Any) -> None:
+    """RW-003: Idle не срабатывает, пока исполняется tool; без tool — срабатывает на пороге."""
+    assert zen._zen_idle_expired(20.0, 0.0, 15.0, False)
+    assert not zen._zen_idle_expired(20.0, 0.0, 15.0, True)
+    assert not zen._zen_idle_expired(10.0, 0.0, 15.0, False)
+
+
+def test_tool_activity_tracks_running_tools(zen: Any) -> None:
+    """RW-003: pending/running включают активность, завершённый статус выключает."""
+    activity = zen._ToolActivity()
+    assert not activity
+    running = {"part": {"id": "c1", "tool": "task", "state": {"status": "running"}}}
+    done = {"part": {"id": "c1", "tool": "task", "state": {"status": "completed"}}}
+    activity.observe("text", running)
+    assert not activity
+    activity.observe("tool_use", running)
+    assert activity
+    activity.observe("tool_use", done)
+    assert not activity
+
+
+def test_serve_tool_state_has_active(zen: Any) -> None:
+    """RW-003: вызов активен с первого фрагмента и до complete()."""
+    state = zen._ServeToolState()
+    assert not state.has_active()
+    state.feed({"id": "c1", "name": "bash"})
+    assert state.has_active()
+    state.feed({"id": "c1", "name": "bash", "input": {"command": "pwd"}})
+    assert state.complete("c1", "session.tool.called") is not None
+    assert not state.has_active()
+
+
+def test_zen_stream_retry_ttft_counts_from_attempt_start(
+    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
+) -> None:
+    """RW-002: запрос, стартовавший давно (очередь/первая попытка), не режется TTFT текущей попытки."""
+    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "3")
+    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "3")
+    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
+    real_t0 = zen._attempts_t0
+    monkeypatch.setattr(
+        zen,
+        "_attempts_t0",
+        lambda *a, **k: min(real_t0(*a, **k), time.monotonic() - 100.0),
+    )
+    fake = _zen_fake_stream_child(tmp_path, chunks=2, gap_s=0.05, lead_s=0.4)
+    status, body, procs = _zen_stream_request(zen, monkeypatch, tmp_path, fake)
+    assert status == 200
+    assert b"Gateway Timeout in zen-bridge" not in body
+    assert b"t0 " in body and b"t1 " in body
+    assert body.count(b"data: [DONE]") == 1
+
+
+def test_zen_run_retry_ttft_counts_from_attempt_start(
+    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
+) -> None:
+    """RW-002: тот же сценарий для не-стримингового Run."""
+    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "3")
+    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "3")
+    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
+    real_t0 = zen._attempts_t0
+    monkeypatch.setattr(
+        zen,
+        "_attempts_t0",
+        lambda *a, **k: min(real_t0(*a, **k), time.monotonic() - 100.0),
+    )
+    fake = _zen_fake_stream_child(tmp_path, chunks=2, gap_s=0.05, lead_s=0.4)
+    status, body, _procs = _zen_stream_request(
+        zen, monkeypatch, tmp_path, fake, stream=False
+    )
+    assert status == 200, body
+    assert b"t0 t1" in body
+
+
+def test_zen_stream_long_tool_not_cut_by_idle(
+    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
+) -> None:
+    """RW-003: tool дольше Idle без токенов не обрывает стриминговый поток."""
+    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "2")
+    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "0.3")
+    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
+    fake = _zen_fake_stream_child(tmp_path, chunks=2, gap_s=0.05, tool_s=1.2)
+    status, body, procs = _zen_stream_request(zen, monkeypatch, tmp_path, fake)
+    assert status == 200
+    assert b"Gateway Timeout in zen-bridge" not in body
+    assert b"t0 " in body and b"t1 " in body
+    assert body.count(b"data: [DONE]") == 1
+    assert procs and all(proc.poll() is not None for proc in procs)
+
+
+def test_zen_run_long_tool_not_cut_by_idle(
+    zen: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
+) -> None:
+    """RW-003: tool дольше Idle не обрывает не-стриминговый Run."""
+    monkeypatch.setenv("BRIDGE_ZEN_TTFT_TIMEOUT_S", "2")
+    monkeypatch.setenv("BRIDGE_ZEN_IDLE_TIMEOUT_S", "0.3")
+    monkeypatch.setenv("BRIDGE_ZEN_TOTAL_TIMEOUT_S", "30")
+    fake = _zen_fake_stream_child(tmp_path, chunks=2, gap_s=0.05, tool_s=1.2)
+    status, body, _procs = _zen_stream_request(
+        zen, monkeypatch, tmp_path, fake, stream=False
+    )
+    assert status == 200, body
+    assert b"t0 t1" in body
```


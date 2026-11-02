Ваша ролевая шляпа — СКЕПТИК. Сфокусируйтесь на безопасности, регрессиях, скрытых предположениях, нарушении инвариантов и рисках отказа.
PRIOR-LEDGER-SHA256: 4cca6c4e7d3c65f82c7bb9b39c2dc9bb2d6e51b348830e8eab91bfd810712c79
РАУНД: C1 (фиксация согласия)

НЕСОГЛАСНЫЕ НАХОДКИ ЭТОГО МЕСТА: RW-003; N=1

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

### Обратная совместимость
- Функция `_zen_execution_timeout(model, prompt)` сохранена как синоним `_zen_ttft_timeout(model, prompt)`.
- Тест `test_zen_byte_timeout_selection` проходит 100% зелёным без изменений.

---

## 3. Изменённые файлы и статистика
```
 bridges/opencode-zen-bridge/server.py    | 129 ++++++++++++++++++++++-----
 tests/test_bridges_speedup_resilience.py | 146 ++++++++++++++++++++++++++++++-
 2 files changed, 253 insertions(+), 22 deletions(-)
```

---

## 4. Матрица верификации (L1/L2 Execution Gate)

| Сьют | Тестов | Результат | Время | Описание |
|---|---|---|---|---|
| `tests/test_bridges_speedup_resilience.py` | 38 | **38 PASSED (100%)** | 4.08s | Проверка TTFT, Idle, Total, byte-selection, стриминга сквозь 0.3s и отсечки зависшего стрима |
| `tests/test_request_attribution.py` | 43 | **43 PASSED (100%)** | 2.11s | Корректность атрибуции запросов, сквозных request_id и хедеров |
| `tests/test_bridge_strict.py` | 41 | **41 PASSED (100%)** | 11.91s | Строгий контракт каталога, health-эндпоинтов, журналов и бюджетов admission |

**Итого:** 122 теста, 0 ошибок, 100% успешных прогонов.

---

## 5. Полный Git Diff

```diff
diff --git a/bridges/opencode-zen-bridge/server.py b/bridges/opencode-zen-bridge/server.py
index fd1d4c9..ce4fbbf 100755
--- a/bridges/opencode-zen-bridge/server.py
+++ b/bridges/opencode-zen-bridge/server.py
@@ -344,8 +344,8 @@ def _zen_positive_float(name: str, default: float) -> float:
         return default
 
 
-def _zen_execution_timeout(model: str, prompt: str) -> float:
-    """Сужение execution deadline только для явно выбранных моделей и большого UTF-8 входа."""
+def _zen_ttft_timeout(model: str, prompt: str) -> float:
+    """Сужение таймаута до первого токена (TTFT) только для целевых моделей на большом промпте."""
     models = {
         "deepseek-v4.1-flash-free",
         *filter(
@@ -354,10 +354,45 @@ def _zen_execution_timeout(model: str, prompt: str) -> float:
     }
     threshold = _positive_int(os.environ.get("BRIDGE_ZEN_LARGE_PROMPT_BYTES"), 8192)
     if model in models and len(prompt.encode("utf-8")) > threshold:
-        return min(TIMEOUT_S, _zen_positive_float("BRIDGE_ZEN_TIMEOUT_S", 25.0))
+        return min(
+            TIMEOUT_S,
+            _zen_positive_float(
+                "BRIDGE_ZEN_TTFT_TIMEOUT_S",
+                _zen_positive_float("BRIDGE_ZEN_TIMEOUT_S", 25.0),
+            ),
+        )
     return TIMEOUT_S
 
 
+def _zen_idle_timeout(model: str = "", prompt: str = "") -> float:
+    """Таймаут неактивности между чанками после первого токена; только для целевых моделей."""
+    if _zen_ttft_timeout(model, prompt) >= TIMEOUT_S:
+        return TIMEOUT_S
+    return min(TIMEOUT_S, _zen_positive_float("BRIDGE_ZEN_IDLE_TIMEOUT_S", 15.0))
+
+
+def _zen_total_timeout(model: str = "", prompt: str = "") -> float:
+    """Общий дедлайн запроса: для целевых моделей BRIDGE_ZEN_TOTAL_TIMEOUT_S (180 с), иначе TIMEOUT_S."""
+    if _zen_ttft_timeout(model, prompt) >= TIMEOUT_S:
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
+def _attempts_t0(attempts: Any, model: str, prompt: str) -> float:
+    """Момент старта запроса: attempts.t0, а для совместимых заглушек — выводим из deadline."""
+    return getattr(
+        attempts, "t0", attempts.deadline - _zen_total_timeout(model, prompt)
+    )
+
+
 def _zen_error(status: int) -> dict[str, Any]:
     """Согласованный контракт ошибок zen, одинаковый для JSON и terminal SSE."""
     message, kind = (
@@ -2946,6 +2981,7 @@ class _RequestAttempts:
         max_quota_rotations: int | None = None,
     ) -> None:
         self.res = res
+        self.t0 = time.monotonic()
         self.deadline = deadline
         self.use_breaker = (
             use_breaker  # False: прямой Google-маршрут без `opencode run`
@@ -4775,6 +4811,8 @@ def _serve_one_attempt(
         status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25)
         _status_emitted = [0]
         last_token_at = prompt_send_start
+        ttft_timeout = _zen_ttft_timeout(model, prompt)
+        idle_timeout = _zen_idle_timeout(model, prompt)
         while time.monotonic() < deadline:
             if is_client_gone is not None and is_client_gone():
                 result["exit_reason"] = "client_gone"
@@ -4783,6 +4821,17 @@ def _serve_one_attempt(
                 result["exit_reason"] = "invalid_serve_event"
                 return result
             now = time.monotonic()
+            # Раздельные таймауты: TTFT до первого токена, Idle между чанками после него.
+            if (
+                result["first_token_at"] is None
+                and now - prompt_send_start >= ttft_timeout
+            ) or (
+                result["first_token_at"] is not None
+                and now - last_token_at >= idle_timeout
+            ):
+                result["exit_reason"] = "timeout"
+                result["delivered"] = _is_delivered()
+                break
             if prompt_status.get("aux_exhausted") or (
                 result["first_event_at"] is None and now >= first_event_deadline
             ):
@@ -7021,7 +7070,7 @@ class Handler(BaseHTTPRequestHandler):
 
     def _set_zen_policy(self, model: str, prompt: str) -> None:
         self._zen_prompt = prompt
-        self._zen_targeted = _zen_execution_timeout(model, prompt) < TIMEOUT_S
+        self._zen_targeted = _zen_ttft_timeout(model, prompt) < TIMEOUT_S
         self._zen_short_bypass = (
             self._zen_probe
             or getattr(self, "headers", {}).get("X-Bypass-Short-Filter") == "1"
@@ -7377,7 +7426,7 @@ class Handler(BaseHTTPRequestHandler):
                     _orig_reasoning,
                     _text_seen,
                     on_tool,
-                    attempts.deadline - _zen_execution_timeout(model, prompt),
+                    _attempts_t0(attempts, model, prompt),
                     is_client_gone=self._client_gone_check,
                     on_status=attempt_status,
                     thinking_enabled=thinking,
@@ -7887,7 +7936,7 @@ class Handler(BaseHTTPRequestHandler):
         if not self._acquire_slot(res):
             return
         attempts = _RequestAttempts(
-            res, time.monotonic() + _zen_execution_timeout(model, prompt)
+            res, time.monotonic() + _zen_total_timeout(model, prompt)
         )
         xs["attempts"] = attempts
 
@@ -7994,8 +8043,7 @@ class Handler(BaseHTTPRequestHandler):
                 status_timer = threading.Timer(
                     max(
                         0.0,
-                        attempts.deadline
-                        - _zen_execution_timeout(model, prompt)
+                        _attempts_t0(attempts, model, prompt)
                         + FIRST_STATUS_DELAY_S
                         - time.monotonic(),
                     ),
@@ -8248,8 +8296,7 @@ class Handler(BaseHTTPRequestHandler):
                 attempt_start = time.monotonic()
                 first_status_due = (
-                    attempts.deadline
-                    - _zen_execution_timeout(model, prompt)
+                    _attempts_t0(attempts, model, prompt)
                     + FIRST_STATUS_DELAY_S
                 )
                 watchdog_state: _WatchdogState = {
@@ -8274,6 +8321,10 @@ class Handler(BaseHTTPRequestHandler):
                     "last_reasoning": "",
                 }
                 thinking_enabled = effort.strip().lower() not in ("", "off", "none")
+                request_t0 = _attempts_t0(attempts, model, prompt)
+                ttft_timeout = _zen_ttft_timeout(model, prompt)
+                idle_timeout = _zen_idle_timeout(model, prompt)
+                split_timeout = [False]
 
                 def emit_synthetic(text: str) -> None:
                     """Синтетический статус отдельной reasoning-дельтой."""
@@ -8296,6 +8347,25 @@ class Handler(BaseHTTPRequestHandler):
                         _log("stream client gone, killing proc group")
                         _stop_proc(proc)
                         raise BrokenPipeError("client gone")
+                    # Раздельные таймауты: TTFT до первого токена запроса, Idle между чанками после него.
+                    if (
+                        watchdog_state["first_token_at"] is None
+                        and now_s
+                        - (
+                            attempt_start
+                            if collected_texts or tool_calls
+                            else request_t0
+                        )
+                        > ttft_timeout
+                    ) or (
+                        watchdog_state["first_token_at"] is not None
+                        and now_s - float(watchdog_state["last_token_at"])
+                        > idle_timeout
+                    ):
+                        split_timeout[0] = True
+                        _stop_proc(proc)
+                        return
                     if watchdog_state[
                         "first_event_at"
                     ] is None and now_s - attempt_start > float(FIRST_EVENT_TIMEOUT_S):
@@ -8526,7 +8596,7 @@ class Handler(BaseHTTPRequestHandler):
                     had_provider_error = True
                     stopped_on_error = True
                     err_lines.append("stdout queue overflow")
-                timed_out = feed.timed_out
+                timed_out = feed.timed_out or split_timeout[0]
                 if timed_out:
                     _log(f"stream timeout after {TIMEOUT_S:.0f}s, killing proc group")
                     _stop_proc(proc)
@@ -8972,7 +9042,7 @@ class Handler(BaseHTTPRequestHandler):
                     reasonings.append,
                     texts.append,
                     natives.append,
-                    attempts.deadline - _zen_execution_timeout(model, prompt),
+                    _attempts_t0(attempts, model, prompt),
                     is_client_gone=self._client_gone_check,
                     on_status=lambda _t: None,
                     thinking_enabled=thinking,
@@ -9284,7 +9354,7 @@ class Handler(BaseHTTPRequestHandler):
             return
         attempts = _RequestAttempts(
             res,
-            time.monotonic() + _zen_execution_timeout(model, prompt),
+            time.monotonic() + _zen_total_timeout(model, prompt),
             use_breaker=not _is_google_direct_model(model),
         )
         xs["attempts"] = attempts
```


ПРЕДВАРИТЕЛЬНЫЕ ИТОГИ ПО ТВОИМ НЕСОГЛАСНЫМ НАХОДКАМ:
- RW-003 [BLOCKER-OPINION] итог=OPEN: RW-003 BLOCKER-OPINION — Idle 15с убивает легитимное долгое исполнение тула/сабагента в serve- и stream-путях

Дебаты закончены. По каждой перечисленной находке — ровно одна позиция:
CONSENT RW-NNN — могу жить с предварительным итогом
OBJECT RW-NNN — дефект: <file:line или цитата правила> — что ломает итог
OBJECT без воспроизводимого дефекта не засчитывается. Новых находок и ревизий нет.
Обязательно включи в ответ содержательное подтверждение согласия и анализ ключевых решений пакета (не менее 200 символов связного текста).
Предпоследняя строка — CONSENTS: <число твоих позиций>/<N выше>.
Первыми двумя строками ответа повтори PANEL-NONCE и ARTIFACT-SHA256 из конца брифа.
Последняя непустая строка ответа — VERDICT: ACCEPT | PASS | NEEDS WORK | RED FLAG.


---
PANEL-NONCE: 8543f92085eb73cd
ARTIFACT-SHA256: 5ea11245c3546b12f1de9c303b0ace2ae267e271d264f328fe4565e904c024a9
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 8543f92085eb73cd» и «ARTIFACT-SHA256: 5ea11245c3546b12f1de9c303b0ace2ae267e271d264f328fe4565e904c024a9».

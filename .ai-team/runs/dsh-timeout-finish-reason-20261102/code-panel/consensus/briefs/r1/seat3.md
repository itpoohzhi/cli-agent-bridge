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
# Code Review Packet: DSH Timeout Finish Reason & Graceful Timeout Fix

- **Run ID:** `dsh-timeout-finish-reason-20261102`
- **Stage:** Code Review (Council / `teamlead-gate`)
- **Author/Coder:** `gpt-6.1-sol` via `codex exec`
- **Architecture Packet:** `.ai-team/runs/dsh-timeout-finish-reason-20261102/architecture/architecture-packet.md` (Revision r2, sha256=`8388cb5255cf009fe8abcf6e83db6729f25cb1f635cbb37bb653bda6112b4908`, Arch Panel ACCEPT 3/3, Proof PASS)
- **Target Files:**
  - `bridges/agy-bridge/server.py`
  - `tests/test_agy_bridge_resilience.py`

---

## 1. Context & Architectural Conformance

### Проблема (RCA)
В среде DeepSeek Harness (DSH), работающей через `bridges/agy-bridge`, срабатывание таймаута хода (`AGY_TIMEOUT_S=3600.0`) перехватывается механизмом `graceful_timeout_on_partial`.
Чтобы не обрывать стрим кодом 504, мост сохраняет частичный ответ и закрывал соединение с захардкоженным `finish_reason="length"`.
Клиент DSH (`TurnMaxTokensItem` в `app.asar`) жестко интерпретирует `finish_reason="length"` как исчерпание лимита токенов модели (`reason.kind="max-tokens"`) и выводит пользователю ложный алерт:
> «Output token limit reached The reply was cut off; earlier output is preserved in the conversation. Send "continue" to let the model resume.»

При этом физический лимит контекста/генерации не был исчерпан.

### Реализованное решение
1. **Расширение `_RuntimeFlags` (с сохранением `stream_resilience_enabled` — F-002):**
   В `_RuntimeFlags` 7-м полем добавлен `graceful_timeout_finish_reason: str = "stop"` со значением по умолчанию `"stop"`.
2. **Типизация и парсинг (F-001, F-003):**
   В `_parse_runtime_flags(text)` строковый тип валидируется через `isinstance(value, str)`.
3. **Хелпер `_graceful_finish_reason() -> str`:**
   Реализована строгая иерархия fallback:
   - Переменная окружения `AGY_GRACEFUL_TIMEOUT_FINISH_REASON` (`"stop"`, `"length"`, `"max_tokens"` -> `"length"`).
   - Поле `graceful_timeout_finish_reason` из снимка `dynamic_config.json` (`_runtime_snapshot()`).
   - Дефолтное безопасное значение: `"stop"`.
4. **Точки вызова:**
   - JSON-режим: `self._send(200, build_payload(out, content, reasoning, _graceful_finish_reason()))`
   - SSE-режим: `emit(chunk({}, _graceful_finish_reason(), conversation_id=conv_id))`
5. **Сохранение обратной совместимости:**
   Установка `AGY_GRACEFUL_TIMEOUT_FINISH_REASON=length` возвращает исходное поведение.
6. **Тестовое покрытие (`tests/test_agy_bridge_resilience.py`):**
   - Очистка `AGY_GRACEFUL_TIMEOUT_FINISH_REASON` в `_clean_flags`.
   - Обновление всех тестов на graceful timeout под дефолт `"stop"`.
   - Добавлены 3 новых параметризованных теста:
     - `test_silent_graceful_timeout_custom_finish_reason_env_length` (проверка `length`, `max_tokens`, ` LENGTH `, ` STOP `).
     - `test_silent_graceful_timeout_custom_finish_reason_dynamic_config` (проверка dynamic_config).
     - `test_silent_graceful_timeout_invalid_env_falls_back_to_config_or_default` (проверка fallback при невалидных env/config).

---

## 2. Результаты тестов и верификации (DoD & Evidence)

1. **Target Unit Tests:**
   `uv run pytest tests/test_agy_bridge_resilience.py -k "silent_graceful_timeout" -v`
   **Результат:** `15 passed, 117 subtests passed in 11.08s (100% green)`.
2. **Full Suite Unit Tests:**
   `uv run pytest tests/test_agy_bridge_resilience.py`
   **Результат:** `337 passed, 686 subtests passed in 215.58s`.
3. **Линтинг и форматирование:**
   `ruff check bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py` — exit=0, All checks passed.
   `git diff --check` — exit=0 (нет trailing whitespace и маркеров конфликта).

---

## 3. Scope of Changes

```diff
diff --git a/bridges/agy-bridge/server.py b/bridges/agy-bridge/server.py
--- a/bridges/agy-bridge/server.py
+++ b/bridges/agy-bridge/server.py
@@ -2920,6 +2920,7 @@ class _RuntimeFlags(NamedTuple):
     graceful_timeout_on_partial: bool = False
     step_scoped_usage_enabled: bool = False
     stream_resilience_enabled: bool = True
+    graceful_timeout_finish_reason: str = "stop"
@@ -2935,6 +2936,8 @@ def _parse_runtime_flags(text: str) -> _RuntimeFlags:
     for key, value in raw.items():
+        if key == "graceful_timeout_finish_reason" and isinstance(value, str):
+            kwargs[key] = value.strip()
@@ -2965,6 +2968,20 @@ def _graceful_finish_reason() -> str:
+    raw_env = os.getenv("AGY_GRACEFUL_TIMEOUT_FINISH_REASON", "").strip().lower()
+    if raw_env in ("length", "max_tokens"):
+        return "length"
+    if raw_env == "stop":
+        return "stop"
+    snap = _runtime_snapshot()
+    val = snap.graceful_timeout_finish_reason.strip().lower()
+    if val in ("length", "max_tokens"):
+        return "length"
+    return "stop"
@@ -6960,3 +6977,3 @@ class Handler(BaseHTTPRequestHandler):
-            self._send(200, build_payload(out, content, reasoning, "length"))
+            self._send(200, build_payload(out, content, reasoning, _graceful_finish_reason()))
@@ -7145,3 +7162,3 @@ class Handler(BaseHTTPRequestHandler):
-                ok = emit(chunk({}, "length", conversation_id=conv_id))
+                ok = emit(chunk({}, _graceful_finish_reason(), conversation_id=conv_id))
```


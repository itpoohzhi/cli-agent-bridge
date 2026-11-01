Ваша ролевая шляпа — СКЕПТИК. Сфокусируйтесь на безопасности, регрессиях, скрытых предположениях, нарушении инвариантов и рисках отказа.
PRIOR-LEDGER-SHA256: b98388071861b42aea2036e3c89a9ce9a7dee0bb18b0df3237f779399221ce0a
РАУНД: D1 (анонимизированные дебаты)

# Architecture Packet: dsh-timeout-finish-reason-20261102 (Revision r2)

- **Run ID:** `dsh-timeout-finish-reason-20261102`
- **Preset:** `analyst-teamlead`
- **Stage:** Architecture (Revision r2 after Council R1 feedback F-001, F-002, F-003)
- **Date:** 2026-11-02
- **Status:** PROPOSED

---

## 1. Problem Statement & Context
При длительных операциях агентов в среде DeepSeek Harness (DSH), работающих через мост `bridges/agy-bridge`, срабатывание 1-часового таймаута хода (`AGY_TIMEOUT_S=3600.0`) перехватывается механизмом `graceful_timeout_on_partial`.
Чтобы не разрывать HTTP/SSE соединение ошибкой 504, мост сохраняет частичный вывод и закрывает стрим с захардкоженным значением `finish_reason="length"`.

Клиент DeepSeek Harness (компонент `TurnMaxTokensItem` в `app.asar`) жестко интерпретирует `finish_reason="length"` как событие `turn/end` с причиной `reason.kind="max-tokens"` и отображает пользователю вводящий в заблуждение баннер:
> *"Output token limit reached The reply was cut off; earlier output is preserved in the conversation. Send "continue" to let the model resume."*

При этом физический лимит токенов генерации (65536) не был исчерпан (было сгенерировано <15k токенов).

---

## 2. Architecture Drivers & Principles
- **AD-1 (Универсальность и независимость от вендоров):** Решение реализуется строго на слое моста `cli-agent-bridge` / `agy-bridge` без эвристик по `User-Agent` и без модификации бинарников DSH.
- **AD-2 (Zero-Hardcode / Полная конфигурируемость):** Значение `finish_reason` при graceful-таймауте настраивается через переменную окружения `AGY_GRACEFUL_TIMEOUT_FINISH_REASON` и поле `graceful_timeout_finish_reason` в `dynamic_config.json`.
- **AD-3 (Безопасный дефолт):** По умолчанию возвращается `finish_reason="stop"`, что полностью исключает ложный алерт в DSH при сохранении диагностического префикса `[⚠️ Превышен лимит времени хода agy...]` в тексте.
- **AD-4 (Обратная совместимость):** Полная возможность вернуть `"length"` установкой `AGY_GRACEFUL_TIMEOUT_FINISH_REASON=length`.

---

## 3. Technical Design (Устранение F-001 и F-003)

### 3.1. Интеграция в `_RuntimeFlags` и stat-кэш `_runtime_snapshot()`
Вместо вызова несуществующей функции `_read_dynamic_config()` (замечание F-001), новый параметр интегрируется напрямую в существующую подсистему `_RuntimeFlags` ([server.py:2897-2970](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py#L2897-L2970)), использующую stat-кэш `(st_mtime_ns, size)` с TTL 1.0 с:

1. В `_RuntimeFlags`:
   ```python
   class _RuntimeFlags(NamedTuple):
       planner_content_streaming_enabled: bool = False
       emit_tool_trace: bool = False
       extended_timeout_enabled: bool = False
       graceful_timeout_on_partial: bool = False
       step_scoped_usage_enabled: bool = False
       graceful_timeout_finish_reason: str = "stop"
   ```
2. В `_parse_runtime_flags(text)`:
   Для поля `graceful_timeout_finish_reason` проверяется строковый тип (`isinstance(value, str)`), для остальных — boolean.
3. Хелпер `_graceful_finish_reason()`:
   ```python
   def _graceful_finish_reason() -> str:
       """Возвращает finish_reason для graceful-завершения таймаута ('stop' или 'length').
       
       Приоритет:
         1. Валидный env AGY_GRACEFUL_TIMEOUT_FINISH_REASON ('stop', 'length', 'max_tokens').
         2. dynamic_config.json поле graceful_timeout_finish_reason.
         3. Дефолт: 'stop'.
       """
       raw_env = os.getenv("AGY_GRACEFUL_TIMEOUT_FINISH_REASON", "").strip().lower()
       if raw_env in ("length", "max_tokens"):
           return "length"
       if raw_env == "stop":
           return "stop"
       # F-003: если env не задан или содержит нераспознанное значение, читаем dynamic_config.json
       snap = _runtime_snapshot()
       val = snap.graceful_timeout_finish_reason.strip().lower()
       if val in ("length", "max_tokens"):
           return "length"
       return "stop"
   ```

### 3.2. Точки вызова в `bridges/agy-bridge/server.py`
1. **JSON-режим ([server.py:6868](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py#L6868)):**
   ```python
   self._send(200, build_payload(out, content, reasoning, _graceful_finish_reason()))
   ```
2. **SSE-режим ([server.py:7015](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py#L7015)):**
   ```python
   ok = self._emit(chunk({}, _graceful_finish_reason(), conversation_id=conv_id))
   ```

### 3.3. Документирование и docstrings (Устранение F-003)
Обновляются комментарии и описания в `bridges/agy-bridge/server.py`:
- Строки 60-61: обновлено описание политики graceful timeout (по умолчанию `finish_reason="stop"`, настраиваемо).
- Строки 6848, 6854, 6973: замена устаревших упоминаний фиксированного `"length"` на параметризованный `finish_reason`.

---

## 4. Analysis of Blocker Classes
1. **Границы и API-контракты:** Значение `"stop"` полностью валидно по спецификации OpenAI API и предотвращает ложную реакцию DSH `max-tokens`.
2. **Безопасность:** Отсутствуют риски `NameError` благодаря опоре на валидированный `_RuntimeFlags`.
3. **Целостность данных:** Все накопленные текстовые и reasoning данные сохраняются без потерь.
4. **Обратная совместимость:** Поддерживается возврат на `"length"` через `AGY_GRACEFUL_TIMEOUT_FINISH_REASON=length`.
5. **Ресурсный конверт:** $O(1)$ накладных расходов благодаря stat-кэшированию `_runtime_snapshot`.
6. **Асимптотика hot-path:** N/A (cold-path).

---

## 5. Verification Plan (Устранение F-002)
В `tests/test_agy_bridge_resilience.py`:
1. В `_clean_flags(self)` ([server.py:3823-3829](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_agy_bridge_resilience.py#L3823-L3829)) добавить очистку `os.environ.pop("AGY_GRACEFUL_TIMEOUT_FINISH_REASON", None)`.
2. Обновить хелпер `_is_length` и негативный ассерт на строке 5464 на ожидание `finish_reason == "stop"` при дефолтной конфигурации.
3. Обновить 10 тестов в `SilentGracefulTimeoutTests` и `SilentCouncilCycle2Tests`:
   - `test_silent_graceful_timeout_sse_both_states` (строка 5440) -> `"stop"`
   - `test_silent_graceful_timeout_json_matrix` (строка 5502) -> `"stop"`
   - `test_silent_graceful_timeout_final_flush_window_survives_expired_deadline` (строка 5541) -> `"stop"`
   - `test_silent_graceful_timeout_one_shared_window_for_all_final_writes` (строка 5572) -> `"stop"`
   - `test_silent_graceful_timeout_write_failure_stops_all_further_writes` (строка 5618) -> `"stop"`
   - `test_silent_graceful_timeout_post_hoc_path_when_run_once_skips_the_hook` (строка 5639) -> `"stop"`
   - `test_silent_graceful_timeout_end_to_end_real_run_both_states_sse` (строка 5785) -> `"stop"`
   - `test_silent_graceful_timeout_end_to_end_real_run_json_and_silent_504` (строка 5802) -> `"stop"`
   - `test_silent_rw001_json_window_reset_restores_timeout_hook_and_post_hoc` (строка 5946) -> `"stop"`
4. Добавить новые тесты:
   - `test_silent_graceful_timeout_custom_finish_reason_env_length`: проверка возврата `"length"` при `AGY_GRACEFUL_TIMEOUT_FINISH_REASON="length"`.
   - `test_silent_graceful_timeout_custom_finish_reason_dynamic_config`: проверка чтения из `dynamic_config.json`.
   - `test_silent_graceful_timeout_invalid_env_falls_back_to_config_or_default`: проверка корректного fallback.
5. Прогон всего тест-сьюта: `pytest tests/test_agy_bridge_resilience.py -v` (100% green).


НАХОДКИ К ДЕБАТАМ (авторы и модели скрыты):
- RW-001 [BLOCKER-OPINION]: RW-001 BLOCKER-OPINION — Предложенная схема теряет существующий флаг stream resilience
- RW-002 [BLOCKER-OPINION]: RW-002 BLOCKER-OPINION — План обновления тестов пропускает независимое ожидание length

По каждой находке — ровно одна позиция одной строкой:
AGREE RW-NNN — проверил: <file:line> — что увидел сам
DISPUTE RW-NNN — контр-evidence: <file:line> — почему неверно
AMEND RW-NNN — priority=<...>; fix=<...> — причина: <file:line> (не более одной правки)
REFUTE RW-NNN COUNTER-EVIDENCE: <проверяемое контр-доказательство> — только так
закрывается BLOCKER-SAFETY; большинством и переклассификацией он не снимается.
Первыми двумя строками ответа повтори PANEL-NONCE и ARTIFACT-SHA256 из конца брифа.
Последняя непустая строка ответа — VERDICT: ACCEPT | PASS | NEEDS WORK | RED FLAG.

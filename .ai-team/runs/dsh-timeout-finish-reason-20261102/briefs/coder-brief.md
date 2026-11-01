# Coder Brief: DSH Timeout Finish Reason & Graceful Shutdown Fix

- **Профиль SDLC:** `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md`
- **Роль:** Coder
- **Модель:** `gpt-6.1-sol` (effort: `high`, family: `OpenAI`)
- **Транспорт:** `codex exec -m gpt-6.1-sol -c model_reasoning_effort="high"`
- **Контекст задачи:** `dsh-timeout-finish-reason-20261102`
- **Architecture Packet:** `.ai-team/runs/dsh-timeout-finish-reason-20261102/architecture/architecture-packet.md` (Revision r2, sha256=`8388cb5255cf009fe8abcf6e83db6729f25cb1f635cbb37bb653bda6112b4908`)
- **Arch Council Verdict:** ACCEPT (3/3), `receipts/arch-panel.json` verified PASS (sha256=`234e2d3902003de67d97aae423ae2017f95921656e62d0a0fb4ae25e57f8dd2e`)

---

## 1. Задача
В `bridges/agy-bridge/server.py` при срабатывании таймаута хода (`AGY_TIMEOUT_S=3600.0`) механизм `graceful_timeout_on_partial` закрывает соединение с захардкоженным `finish_reason="length"`.
DeepSeek Harness (`TurnMaxTokensItem` в `app.asar`) воспринимает `length` как `reason.kind="max-tokens"` и выбрасывает ложный алерт:
«Output token limit reached The reply was cut off; earlier output is preserved in the conversation. Send "continue" to let the model resume.»

**Требуется:**
1. Сделать `finish_reason` при graceful timeout настраиваемым через `AGY_GRACEFUL_TIMEOUT_FINISH_REASON` и поле `graceful_timeout_finish_reason` в `dynamic_config.json`.
2. По умолчанию возвращать `"stop"`.
3. Сохранять возможность возврата `"length"` при `AGY_GRACEFUL_TIMEOUT_FINISH_REASON="length"`.
4. Обновить тесты в `tests/test_agy_bridge_resilience.py` и добавить новые на валидацию fallback-цепочки.

---

## 2. Требования к реализации в `bridges/agy-bridge/server.py`

### 2.1. Расширение `_RuntimeFlags` (с сохранением `stream_resilience_enabled`)
В строках ~2920:
```python
class _RuntimeFlags(NamedTuple):
    """Неизменяемый валидированный снимок флагов новой политики."""

    planner_content_streaming_enabled: bool = False
    emit_tool_trace: bool = False
    extended_timeout_enabled: bool = False
    graceful_timeout_on_partial: bool = False
    step_scoped_usage_enabled: bool = False
    stream_resilience_enabled: bool = True
    graceful_timeout_finish_reason: str = "stop"
```
**ВНИМАНИЕ:** Обязательно сохранить поле `stream_resilience_enabled: bool = True` (устранение замечания F-002)! `graceful_timeout_finish_reason` добавляется 7-м полем.

### 2.2. Парсинг в `_parse_runtime_flags(text: str)`
В строках ~2935:
- Для ключа `"graceful_timeout_finish_reason"` валидировать строковый тип (`isinstance(value, str)`).
- Для остальных ключей сохранять валидацию `isinstance(value, bool)`.

### 2.3. Хелпер `_graceful_finish_reason() -> str`
Реализовать:
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
    snap = _runtime_snapshot()
    val = snap.graceful_timeout_finish_reason.strip().lower()
    if val in ("length", "max_tokens"):
        return "length"
    return "stop"
```

### 2.4. Точки вызова
Заменить захардкоженный `"length"` на вызов `_graceful_finish_reason()`:
1. В JSON-режиме (около строки 6868):
   `self._send(200, build_payload(out, content, reasoning, _graceful_finish_reason()))`
2. В SSE-режиме (около строки 7015):
   `ok = self._emit(chunk({}, _graceful_finish_reason(), conversation_id=conv_id))`

### 2.5. Комментарии и docstrings
Обновить строки в `bridges/agy-bridge/server.py` (около 60, 6848, 6854, 6973), где упоминался фиксированный `"length"`.

---

## 3. Требования к тестам в `tests/test_agy_bridge_resilience.py`

### 3.1. Очистка окружения в `_clean_flags`
Добавить `os.environ.pop("AGY_GRACEFUL_TIMEOUT_FINISH_REASON", None)` в `_clean_flags`.

### 3.2. Обновление существующих тестов под дефолт `"stop"`
Все тесты на `graceful_timeout`, которые ранее проверяли `finish_reason == "length"` при дефолтной конфигурации, должны теперь ожидать `"stop"`:
- `test_silent_graceful_timeout_sse_both_states`
- `test_silent_graceful_timeout_json_matrix`
- `test_silent_graceful_timeout_final_flush_window_survives_expired_deadline`
- `test_silent_graceful_timeout_one_shared_window_for_all_final_writes`
- `test_silent_graceful_timeout_write_failure_stops_all_further_writes`
- `test_silent_graceful_timeout_post_hoc_path_when_run_once_skips_the_hook`
- `test_silent_graceful_timeout_end_to_end_real_run_both_states_sse`
- `test_silent_graceful_timeout_end_to_end_real_run_json_and_silent_504`
- `test_silent_rw001_json_window_reset_restores_timeout_hook_and_post_hoc`

### 3.3. Новые тесты
1. `test_silent_graceful_timeout_custom_finish_reason_env_length`:
   При установке `AGY_GRACEFUL_TIMEOUT_FINISH_REASON=length` возвращается `"length"`.
2. `test_silent_graceful_timeout_custom_finish_reason_dynamic_config`:
   При отсутствии env и наличии `"graceful_timeout_finish_reason": "length"` в `dynamic_config.json` возвращается `"length"`.
3. `test_silent_graceful_timeout_invalid_env_falls_back_to_config_or_default`:
   При невалидном значении в env (например, `"invalid_foo"`) происходит корректный fallback на конфиг/дефолт `"stop"`.

---

## 4. Оракул готовности
Команда: `uv run pytest tests/test_agy_bridge_resilience.py -k "silent_graceful_timeout" -v`
Все тесты обязаны завершиться со статусом PASSED (exit code 0).

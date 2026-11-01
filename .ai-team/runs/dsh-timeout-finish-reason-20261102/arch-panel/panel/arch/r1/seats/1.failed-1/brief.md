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
# Architecture Packet: dsh-timeout-finish-reason-20261102

- **Run ID:** `dsh-timeout-finish-reason-20261102`
- **Preset:** `analyst-teamlead`
- **Stage:** Architecture
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
- **AD-2 (Zero-Hardcode / Полная конфигурируемость):** Никаких захардкоженных констант. Значение `finish_reason` при graceful-таймауте настраивается через переменную окружения `AGY_GRACEFUL_TIMEOUT_FINISH_REASON` и файл `dynamic_config.json`.
- **AD-3 (Безопасный дефолт):** По умолчанию возвращается `finish_reason="stop"`, что полностью исключает ложный алерт в DSH при сохранении диагностического префикса `[⚠️ Превышен лимит времени хода agy...]` в тексте.
- **AD-4 (Обратная совместимость):** Возможность принудительно вернуть `"length"` установкой `AGY_GRACEFUL_TIMEOUT_FINISH_REASON=length`.

---

## 3. Technical Design

### 3.1. Хелпер `_graceful_finish_reason()`
В `bridges/agy-bridge/server.py` добавляется хелпер:
```python
def _graceful_finish_reason() -> str:
    """Возвращает finish_reason для graceful-завершения таймаута.
    
    По умолчанию 'stop', чтобы клиенты (например DSH) не показывали
    ложное предупреждение о превышении лимита токенов генерации.
    Допустимо переопределить на 'length' через env или dynamic_config.json.
    """
    val = os.getenv("AGY_GRACEFUL_TIMEOUT_FINISH_REASON", "").strip().lower()
    if not val:
        cfg = _read_dynamic_config()
        val = str(cfg.get("graceful_timeout_finish_reason") or "").strip().lower()
    if val in ("length", "max_tokens"):
        return "length"
    return "stop"
```

### 3.2. Точки вызова в `bridges/agy-bridge/server.py`
1. **JSON-режим (L6868):**
   ```python
   finish_reason = _graceful_finish_reason()
   self._send(200, build_payload(out, content, reasoning, finish_reason))
   ```
2. **SSE-режим (L7015):**
   ```python
   finish_reason = _graceful_finish_reason()
   if ok:
       ok = self._emit(chunk({}, finish_reason, conversation_id=conv_id))
   ```

### 3.3. Документирование флагов
В блоке описания конфигурации моста (`bridges/agy-bridge/server.py:50-66`) фиксируется новый параметр `graceful_timeout_finish_reason` / `AGY_GRACEFUL_TIMEOUT_FINISH_REASON`.

---

## 4. Analysis of Blocker Classes
1. **Границы и API-контракты:** OpenAI Chat Completions API допускает значения `stop`, `length`, `tool_calls`, `content_filter`. Значение `stop` является стандартным для завершенного ответа.
2. **Безопасность:** Отсутствуют угрозы безопасности; данные не изменяются.
3. **Целостность данных:** Текст ответа и reasoning передаются полностью без усечений.
4. **Обратная совместимость:** 100% совместимость сохранена благодаря флагу отката на `"length"`.
5. **Ресурсный конверт:** Накладные расходы $O(1)$, 0 дополнительных аллокаций.
6. **Асимптотика hot-path:** N/A (cold-path завершения таймаута).

---

## 5. Verification Plan
1. `tests/test_agy_bridge_resilience.py`:
   - Обновить тест graceful timeout на проверку `finish_reason == "stop"` по умолчанию.
   - Добавить тест с `monkeypatch.setenv("AGY_GRACEFUL_TIMEOUT_FINISH_REASON", "length")`, проверяющий возврат `"length"`.
   - Проверить как SSE-режим, так и JSON-режим.
2. Полный регрессионный прогон `pytest tests/ -v`.



---
PANEL-NONCE: 0abc39bb4b38c952
ARTIFACT-SHA256: ee8fe2792ea21e3c210a902ad1dcf2e5cf3322153652eb586506d9eca0ce4c13
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 0abc39bb4b38c952» и «ARTIFACT-SHA256: ee8fe2792ea21e3c210a902ad1dcf2e5cf3322153652eb586506d9eca0ce4c13».

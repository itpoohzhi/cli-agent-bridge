# Evidence White: As-Is Facts

Ты аналитик под Белой шляпой. Задача изменения: Устранение ложного срабатывания «Output token limit reached» при таймаутах хода в agy-bridge. Симптом отсутствует.

## As-Is факты системы

- [W-01] В JSON-режиме agy-bridge при срабатывании graceful timeout вызов завершается с захардкоженным `finish_reason="length"` | bridges/agy-bridge/server.py:6868 | 2026-11-02
- [W-02] В SSE-режиме agy-bridge при срабатывании graceful timeout вызов завершается чанком с захардкоженным `finish_reason="length"` | bridges/agy-bridge/server.py:7015 | 2026-11-02
- [W-03] В клиенте DeepSeek Harness (app.asar) функция `mapStopReason` транслирует `finish_reason: "length"` в `stopReason: "length"` | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar:116256641 | 2026-11-02
- [W-04] В клиенте DeepSeek Harness (app.asar) `stopReason: "length"` транслируется в событие `turn/end` с `reason.kind: "max-tokens"` | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar:17314864,24193098 | 2026-11-02
- [W-05] В UI DeepSeek Harness компонент `TurnMaxTokensItem` выводит строковый баннер `message.maxTokens` («Output token limit reached») строго при `reason.kind === "max-tokens"` | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar:23967813 | 2026-11-02
- [W-06] В реальной сессии DSH `session-6583934e-e9b0-499c-88ce-0ad1401bf69b` 2-й ход длился 3594.5 с и был прерван по таймауту с сообщением `[⚠️ Превышен лимит времени хода agy (timeout, 3594.5s)]` и `stopReason: "length"`, что вызвало показ баннера | ~/.dsh/sessions/--Users-aazhiry1-~041C~043E~0439~0020~0434~0438~0441~043A-~0420~0430~0431~043E~0442~0430-Sber-knowledge-base--/session-6583934e-e9b0-499c-88ce-0ad1401bf69b/session.v4.jsonl.zstd | 2026-11-02
- [W-07] Текущие таймауты в `bridges/agy-bridge/server.py` читаются из `AGY_IDLE_TIMEOUT_S` (дефолт 1800.0) и `AGY_TIMEOUT_S` (дефолт 3600.0), но отсутствует явная настройка для выбора возвращаемого `finish_reason` | bridges/agy-bridge/server.py:320-335,3011-3017 | 2026-11-02
- [W-08] В `tests/test_agy_bridge_resilience.py` зафиксированы тесты на graceful timeout, которые в настоящее время ожидают `finish_reason == "length"` | tests/test_agy_bridge_resilience.py:30-70 | 2026-11-02

## Заменители «ДО»
- Базовый main: `rg -n 'chunk.*"length"' bridges/agy-bridge/server.py` -> строка 7015.
- Стоимость решения: изменение ровно 2 мест отправки `finish_reason` (JSON + SSE) + тесты регрессии.
- SLA ДО: N/A (cold-path only).
- Окно времени: 2026-11-02.
- Воспроизведение: `pytest tests/test_agy_bridge_resilience.py` проходит и подтверждает контракт.

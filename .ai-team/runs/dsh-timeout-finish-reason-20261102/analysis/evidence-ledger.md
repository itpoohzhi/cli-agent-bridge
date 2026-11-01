# Evidence Ledger: dsh-timeout-finish-reason-20261102

[F-01] В JSON-режиме agy-bridge при срабатывании graceful timeout вызов завершается с захардкоженным finish_reason="length" | bridges/agy-bridge/server.py:6868 | 2026-11-02
[F-02] В SSE-режиме agy-bridge при срабатывании graceful timeout вызов завершается чанком с захардкоженным finish_reason="length" | bridges/agy-bridge/server.py:7015 | 2026-11-02
[F-03] В клиенте DeepSeek Harness (app.asar) функция mapStopReason транслирует finish_reason: "length" в stopReason: "length" | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar:116256641 | 2026-11-02
[F-04] В клиенте DeepSeek Harness (app.asar) stopReason: "length" транслируется в событие turn/end с reason.kind: "max-tokens" | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar:17314864,24193098 | 2026-11-02
[F-05] В UI DeepSeek Harness компонент TurnMaxTokensItem выводит строковый баннер message.maxTokens («Output token limit reached») строго при reason.kind === "max-tokens" | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar:23967813 | 2026-11-02
[F-06] В сессии DSH session-6583934e-e9b0-499c-88ce-0ad1401bf69b 2-й ход длился 3594.5 с и был прерван по таймауту с сообщением о лимите времени хода и stopReason: "length", что вызвало показ баннера | ~/.dsh/sessions/--Users-aazhiry1-~041C~043E~0439~0020~0434~0438~0441~043A-~0420~0430~0431~043E~0442~0430-Sber-knowledge-base--/session-6583934e-e9b0-499c-88ce-0ad1401bf69b/session.v4.jsonl.zstd | 2026-11-02
[F-07] Текущие таймауты в bridges/agy-bridge/server.py читаются из AGY_IDLE_TIMEOUT_S (1800.0) и AGY_TIMEOUT_S (3600.0), но отсутствует явная настройка для выбора возвращаемого finish_reason | bridges/agy-bridge/server.py:320-335,3011-3017 | 2026-11-02
[F-08] В tests/test_agy_bridge_resilience.py тесты на graceful timeout проверяют finish_reason == "length" | tests/test_agy_bridge_resilience.py:30-70 | 2026-11-02

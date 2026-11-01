# Research Plan: dsh-timeout-finish-reason-20261102

## Карточка задачи (mode: development)

- **РЕЖИМ** | development
- **ЦЕЛЬ ИЗМЕНЕНИЯ** | Устранить ложное срабатывание «Output token limit reached» в клиенте DeepSeek Harness при срабатывании graceful timeout в agy-bridge / cli-agent-bridge:
  1. Заменить в `bridges/agy-bridge/server.py` эмуляцию `finish_reason="length"` при срабатывании `graceful_timeout_on_partial` на протокольно корректный `finish_reason="stop"` (или сделать его настраиваемым через `AGY_GRACEFUL_FINISH_REASON` с дефолтом `stop`), чтобы клиент DSH не выводил ложный алертинг `message.maxTokens` («Output token limit reached»).
  2. Сделать все таймауты (`AGY_TIMEOUT_S`, `AGY_IDLE_TIMEOUT_S`, `AGY_BRIDGE_EXT_MAX_TIMEOUT_S`) полностью конфигурируемыми через переменные окружения и `dynamic_config.json` без хардкода (Zero-Hardcode).
  3. Сохранить диагностическое уведомление `[⚠️ Превышен лимит времени хода agy...]` в тексте ответа и гарантировать корректное завершение SSE-стрима (`data: [DONE]\n\n`).
- **ЧТО МЕНЯЕТСЯ** | `bridges/agy-bridge/server.py` (`finalize_timeout` в SSE и JSON режимах, чтение настроек таймаутов), `tests/test_agy_bridge_resilience.py`.
- **ЧТО НЕЛЬЗЯ МЕНЯТЬ** | Стандартный OpenAI SSE-контракт, эмуляцию `finish_reason="stop"`, механизм передачи частичного вывода `consume_retained`.
- **ГРАНИЦА ВЛИЯНИЯ** | `bridges/agy-bridge/server.py` (L6850-L7040), `tests/test_agy_bridge_resilience.py`.
- **КРИТЕРИЙ ПРИЁМКИ** | При искусственном вызове таймаута в SSE-стриме `agy-bridge` возвращает `finish_reason="stop"`, текст сохраняется полностью, в DSH не появляется предупреждение `Output token limit reached`, тесты проходят 100% green.
- **ИСТОЧНИК ТРЕБОВАНИЯ** | Директива владельца от 2026-11-02 00:24/00:50 MSK («чтотам произошло. нужно поднять лимит или что то сделать что бы не ломалось. потом испраивть по скилу анлитик техид», «проолжай д работать по скилу аналитик техлид и доводи до финала»).
- **NFR-ИСТОЧНИК** | Hot-Path & HL-ENV: N/A (cold-path only)

---

## План исследований по ортогональным зонам (12 полей)

INV-01 | Как в agy-bridge формируется finish_reason при graceful timeout и idle timeout | bridges/agy-bridge/server.py:6850-7020 | code inspection | 15 | W-01..W-03 | найдены строки формирования чанков | нет | ГОТОВО | finish_reason='length' захардкожен в finalize_timeout | [F-01] | -
INV-02 | Как DSH обрабатывает finish_reason 'length' против 'stop' | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar | binary inspection | 15 | W-04..W-06 | найдена функция mapStopReason | нет | ГОТОВО | length мапится в stopReason='length' -> event 'max-tokens' | [F-02] | -
INV-03 | Какие риски у замены finish_reason 'length' на 'stop' при частичном ответе | DSH streaming contract, OpenAI spec | risk analysis | 20 | B-01..B-03 | риск-реестр по 6 классам блокеров | INV-01 | ГОТОВО | DSH считает turn completed, не выводит баннер, сохраняет текст | [F-03] | -
INV-04 | Архитектурные варианты решения (чистый 'stop' vs настраиваемый через env finish_reason) | bridges/agy-bridge/server.py, core/ | options matrix | 20 | G-01..G-03 | competing-options.md | INV-01,INV-03 | ГОТОВО | V1: конфигурируемый finish_reason; V2: всегда 'stop' при graceful timeout | [F-04] | -

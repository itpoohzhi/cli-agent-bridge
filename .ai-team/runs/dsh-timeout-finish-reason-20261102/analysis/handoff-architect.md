# Handoff to Architect: dsh-timeout-finish-reason-20261102

## 1. Контекст и Architecture Drivers
- **Цель (REQ-01):** Устранить ложное срабатывание «Output token limit reached» в клиенте DeepSeek Harness при таймаутах хода в `bridges/agy-bridge/server.py`.
- **Источники фактов:** [F-01]..[F-08] из `evidence-ledger.md`.
- **Драйверы:**
  - Zero-Hardcode: полная конфигурируемость поведения через переменные окружения и `dynamic_config.json`.
  - Независимость от вендоров: отсутствие специфичных проверок User-Agent или клиентских веток.
  - Обратная совместимость: возможность вернуть `"length"` установкой переменной окружения.

## 2. Границы и контракты
- **Модули под изменением:** `bridges/agy-bridge/server.py` (L6850-7025), `tests/test_agy_bridge_resilience.py`.
- **Внешний API-контракт:** OpenAI Chat Completions API (SSE стриминг и non-streaming JSON).
- **Контрактная дельта:** В ответе при graceful timeout поле `choices[0].finish_reason` по умолчанию равно `"stop"` (вместо `"length"`). При установке `AGY_GRACEFUL_TIMEOUT_FINISH_REASON=length` возвращается `"length"`.

## 3. Ресурсный конверт и NFR
- **Hot-Path & HL-ENV:** N/A (cold-path only).
- **Time budget:** $O(1)$ при проверке флага/переменной окружения.
- **Memory budget:** 0 байт постоянного расхода.

## 4. Допущения и открытые вопросы
- OPEN-01 (МОЖНО ПРОДОЛЖИТЬ): Переменная окружения `AGY_GRACEFUL_TIMEOUT_FINISH_REASON` является приватной для agy-bridge. Допущение: имя переменной принято, конфликтов нет.

## 5. DoD & Review Mark
[ПРОВЕРЕНО ЛУПОМ: тройка R1→D1 OK (исправлено 0, отсеяно галлюцинаций 0)]

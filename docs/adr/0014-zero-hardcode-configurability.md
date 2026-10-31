# 0014 — agy-bridge: полная ликвидация вшитых констант и обеспечение 100% конфигурируемости эксплуатационных параметров

## Status

Proposed (2026-10-31, Architect cycle-3, revision a3, run `zero-hardcode-configurability`).
Целевой путь: `docs/adr/0014-zero-hardcode-configurability.md`.
Критичность: S2.
Пакет: `/tmp/cel-runs/zero-hardcode-configurability/architecture/architecture-packet.json`.

## Y-формулировка

В контексте standalone `agy-bridge` (`127.0.0.1:9887`), к которому DeepSeek Harness и внешние потребители обращаются напрямую,
столкнувшись с несоответствием правилу 4 `AGENTS.md` репозитория («Запрет на хардкод параметров: полная конфигурируемость»), выражавшимся в наличии жестко зашитых констант буферов памяти (8 MiB контент, 2 MiB reasoning), шагов (128), блобов (256 KiB), маркеров (32), дивергентного текста (64 KiB), интервала watchdog (5.0 с), бюджетов хода (3600 с, резерв 5.5 с), таймаутов дренажа и параметров circuit breaker/rate-limiter, что приводило к обрывам длительных ходов (`timeout, 3594.5s`),
мы решили:
1. Реализовать отказоустойчивые типизированные функции парсинга параметров окружения:
   - `_env_int(name: str, default: int, low: int, high: int) -> int` — безопасный парсинг с проверкой диапазона `[low, high]` и fallback на `default`;
   - `_env_int_with_zero_cap(name: str, default: int, low: int, high: int, zero_cap: int) -> int` — при `val == 0` возвращает `zero_cap`, иначе проверяет `low <= val <= high` с fallback на `default`;
   - `_env_float(name: str, default: float, low: float, high: float) -> float` — парсинг вещественных чисел с проверкой `math.isfinite()`, диапазона `[low, high]` и fallback на `default`;
   - `_env_bool(name: str, default: bool) -> bool` — разбор булевых значений (`"1"`, `"true"`, `"yes"`, `"on"` -> `True`; `"0"`, `"false"`, `"no"`, `"off"` -> `False`);
2. Объединить все параметры в единый неизменяемый снимок конфигурации `_BridgeConfig` с функцией доступа `get_bridge_config()` и возможностью переинициализации `reload_bridge_config()` для изолированного юнит-тестирования без перезагрузки модулей;
3. Ввести кросс-полевые инварианты при инициализации `_BridgeConfig`:
   - `idle_timeout_s = min(idle_timeout_s, req_budget_s)` — таймаут простоя не может превышать общий бюджет запроса;
   - `retry_capacity_tenths = max(retry_capacity_tenths, retry_cost_tenths)` — емкость корзины повторов не может быть меньше стоимости одной попытки;
   - `poll_bucket_capacity_tenths = max(poll_bucket_capacity_tenths, poll_cost_tenths)` — емкость корзины опросов не может быть меньше стоимости одного опроса;
4. Вынести 100% выявленных эксплуатационных параметров в переменные окружения с каноническим префиксом `AGY_BRIDGE_*`:
   - **Буферы памяти и защитные потолки:**
     - `AGY_BRIDGE_MAX_CONTENT_BYTES`: дефолт 8388608 (8 MiB), диапазон `[1024, 268435456]`; при `0` включается Safety Cap 256 MiB;
     - `AGY_BRIDGE_MAX_REASONING_BYTES`: дефолт 2097152 (2 MiB), диапазон `[1024, 67108864]`; при `0` включается Safety Cap 64 MiB;
     - `AGY_BRIDGE_MAX_STEP_BLOB_BYTES`: дефолт 262144 (256 KiB), диапазон `[1024, 16777216]`;
     - `AGY_BRIDGE_MAX_STEPS`: дефолт 128, диапазон `[1, 4096]`;
     - `AGY_BRIDGE_MAX_TOOL_MARKERS`: дефолт 32, диапазон `[1, 1024]`;
     - `AGY_BRIDGE_MAX_DIVERGENT_BYTES`: дефолт 65536 (64 KiB), диапазон `[1024, 1048576]`;
     - `AGY_BRIDGE_TRANSCRIPT_READ_MAX`: дефолт 4194304 (4 MiB), диапазон `[1024, 67108864]`;
     - `AGY_BRIDGE_DYNAMIC_CONFIG_MAX_BYTES`: дефолт 65536, диапазон `[1024, 1048576]`;
     - `AGY_BRIDGE_USAGE_STEP_CAP`: дефолт 16384, диапазон `[128, 1048576]`;
     - `AGY_BRIDGE_SQLITE_ROW_LIMIT`: дефолт 16, диапазон `[1, 1024]`;
   - **Таймауты, бюджеты и интервалы опроса:**
     - `AGY_BRIDGE_REQ_BUDGET_S`: дефолт 3600.0 с, диапазон `[10.0, 86400.0]`;
     - `AGY_BRIDGE_EXT_MAX_TIMEOUT_S`: дефолт 3600.0 с, диапазон `[10.0, 86400.0]`;
     - `AGY_BRIDGE_IDLE_TIMEOUT_S`: дефолт 1800.0 с, диапазон `[5.0, 86400.0]`;
     - `AGY_BRIDGE_TIMEOUT_S`: дефолт 1800, диапазон `[1, 86400]`;
     - `AGY_BRIDGE_QUEUE_TIMEOUT_S`: дефолт 900, диапазон `[1, 86400]`;
     - `AGY_BRIDGE_KEEPALIVE_S`: дефолт 15.0, диапазон `[0.5, 300.0]`;
     - `AGY_BRIDGE_FIRST_TOKEN_TIMEOUT_S`: дефолт 600.0, диапазон `[5.0, 3600.0]`;
     - `AGY_BRIDGE_TRANSCRIPT_POLL_S`: дефолт 0.5, диапазон `[0.05, 10.0]`;
     - `AGY_BRIDGE_WATCHDOG_INTERVAL_S`: дефолт 5.0, диапазон `[0.5, 60.0]`;
     - `AGY_BRIDGE_KILL_TERM_GRACE_S`: дефолт 2.0, диапазон `[0.1, 30.0]`;
     - `AGY_BRIDGE_PROC_EXIT_WAIT_S`: дефолт 5.0, диапазон `[0.1, 60.0]`;
     - `AGY_BRIDGE_DRAIN_WINDOW_S`: дефолт 15.0, диапазон `[1.0, 120.0]`;
     - `AGY_BRIDGE_DRAIN_POLL_STEP_S`: дефолт 0.1, диапазон `[0.01, 2.0]`;
     - `AGY_BRIDGE_JOIN_TIMEOUT_S`: дефолт 0.5, диапазон `[0.05, 10.0]`;
     - `AGY_BRIDGE_RESERVE_S`: дефолт 5.5, диапазон `[0.5, 60.0]`;
     - `AGY_BRIDGE_MIN_ATTEMPT_S`: дефолт 10.0, диапазон `[1.0, 300.0]`;
     - `AGY_BRIDGE_FINAL_FLUSH_S`: дефолт 5.0, диапазон `[0.5, 60.0]`;
     - `AGY_BRIDGE_SESSION_MAX_TTL_S`: дефолт 86400.0, диапазон `[60.0, 604800.0]`;
     - `AGY_BRIDGE_SESSION_MAX_TURNS`: дефолт 30, диапазон `[1, 1000]`;
     - `AGY_BRIDGE_SWEEP_CUTOFF_S`: дефолт 3600.0, диапазон `[60.0, 86400.0]`;
     - `AGY_BRIDGE_LIVENESS_GATED_TIMEOUT_ENABLED`: целевой дефолт `True` (предотвращает обрыв ходов при наличии мышления/активности модели согласно инварианту задачи; при необходимости сохраняется возможность явного переопределения на `False`);
   - **Circuit Breaker и Rate Limiter (Token Buckets):**
     - `AGY_BRIDGE_BREAKER_FAILURES`: дефолт 3, диапазон `[1, 100]`;
     - `AGY_BRIDGE_BREAKER_COOLDOWN_S`: дефолт 30.0, диапазон `[1.0, 3600.0]`;
     - `AGY_BRIDGE_BREAKER_PROBE_LEASE_S`: дефолт 60.0, диапазон `[1.0, 3600.0]`;
     - `AGY_BRIDGE_RETRY_CAPACITY_TENTHS`: дефолт 30, диапазон `[10, 1000]`;
     - `AGY_BRIDGE_RETRY_COST_TENTHS`: дефолт 10, диапазон `[1, 100]`;
     - `AGY_BRIDGE_RETRY_REFILL_PER_SEC_TENTHS`: дефолт 1, диапазон `[1, 100]`;
     - `AGY_BRIDGE_POLL_BUCKET_CAPACITY_TENTHS`: дефолт 30, диапазон `[10, 1000]`;
     - `AGY_BRIDGE_POLL_COST_TENTHS`: дефолт 10, диапазон `[1, 100]`;
     - `AGY_BRIDGE_POLL_REFILL_PER_SEC_TENTHS`: дефолт 1, диапазон `[1, 100]`;
5. Формировать шаблон `_STEPS_SQL` динамически на основе вычисленных `config.sqlite_row_limit` и `config.max_step_blob_bytes`;
6. Обеспечить сохранение обратной совместимости API и тестов: параметры по умолчанию соответствуют ранее зашитым константам, а изменение дефолта `liveness_gated_timeout_enabled` на `True` документировано как целевое функциональное исправление проблемы преждевременных таймаутов.

## Context and Problem Statement

В ходе аудита инцидента обрыва хода в DeepSeek Harness на отсечке `3594.5s` и выполнения директивы владельца по скиллу `analyst-teamlead` выявлено:
- `T_REQ_BUDGET_S = 3600.0` и `T_RESERVE_S = 5.5` зашиты константами, приводя к обрыву хода ровно через 59 минут 55 секунд независимо от того, продолжает ли модель думать или генерировать результат;
- `DEFAULT_LIVENESS_GATED_TIMEOUT_ENABLED = False` приводил к игнорированию признаков жизни процесса при расчёте жесткого потолка времени;
- `MAX_CONTENT_BYTES_PER_TURN = 8 * 1024 * 1024` и `MAX_REASONING_BYTES_PER_TURN = 2 * 1024 * 1024` зашиты статически, отсекая текст и рассуждения при длительных ходах;
- `MAX_STEPS_TRACKED = 128` и `MAX_STEP_BLOB_BYTES = 262144` жестко ограничивают транскрипт шагов;
- `WATCHDOG_INTERVAL_S = 5.0`, `PROC_EXIT_WAIT_S = 5.0`, `DRAIN_WINDOW_S = 15.0` зашиты без возможности адаптации под нагрузку;
- Константы circuit breaker и токен-бакетов не подлежали настройке;
- Чтение параметров окружения в ряде мест падало с необработанным `ValueError` при нечисловом вводе.

Это прямо нарушает п. 4 `AGENTS.md` проекта («Запрет на хардкод параметров: полная конфигурируемость»).

## Decision Drivers

- **D1 — 100% конфигурируемость без хардкода:** все эксплуатационные параметры (буферы, таймауты, лимиты, интервалы) вынесены в настройки окружения.
- **D2 — Защита непрерывности хода (Liveness Invariant):** активный процесс модели с признаками мышления и генерации не обрывается по таймеру; прерывание возможно только при полной тишине.
- **D3 — Отказоустойчивость парсинга (Robustness Principle):** невалидные значения, NaN, пустые строки и переполнения откатываются на безопасные дефолты.
- **D4 — Предотвращение OOM (Bounded Safety Cap):** значение 0 не снимает лимит до бесконечности, а включает безопасный потолок (256 MiB для текста, 64 MiB для reasoning).
- **D5 — Чистая архитектура и тестируемость:** единый `_BridgeConfig` позволяет юнит-тестам динамически проверять любые конфигурации.

## Verification Surface

- Юнит-тесты функций `_env_int`, `_env_int_with_zero_cap`, `_env_float` и `_env_bool` с проверкой граничных значений `[low, high]`, отрицательных чисел, NaN, `inf` и отката на default.
- Тесты переопределения каждого параметра через переменные окружения `AGY_BRIDGE_*`.
- Тест работы `liveness_gated_timeout` при сверхдлинном ходе.
- Тест динамической компиляции `_STEPS_SQL`.
- Полный регрессионный прогон `pytest tests/test_agy_bridge_resilience.py -v`.

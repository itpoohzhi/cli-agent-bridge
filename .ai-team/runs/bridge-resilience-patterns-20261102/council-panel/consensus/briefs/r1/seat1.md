Ваша ролевая шляпа — СКЕПТИК. Сфокусируйтесь на безопасности, регрессиях, скрытых предположениях, нарушении инвариантов и рисках отказа.
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
# Teamlead Council Code Review Package — `bridge-resilience-patterns-20261102`

## 1. Метаданные и архитектурный контекст
- **Задача:** Пресет `analyst-teamlead`, реализация универсальных паттернов отказоустойчивости (Circuit Breaker, Bulkhead, Exponential Backoff Retries) в шлюзе `cli-agent-bridge`.
- **Инвариант владельца:** Категорический запрет на автоматический fallback на резервную модель. При недоступности бэкенда — только честный `HTTP 503` с заголовком `Retry-After`.
- **Архитектурный пакет:** ADR-0020 (Rev 4), `.ai-team/runs/bridge-resilience-patterns-20261102/architecture/architecture-packet.md` (`sha256=f11926370796cb83074b1ddfce74de7ba251ee15b25a83a6621cb07ebaee77aa`).
- **Архитектурная панель (ARCH_PANEL):** Раунд C1 (Round 4), единогласный вердикт 3/3 `ACCEPT`, квитанция `panel/arch/r4/panel-proof.json` (`sha256=21df40b1705b4205b7bc31a27b12c75539f27eb80f1d3e4818c37ad86b1bb03f`, `verify_panel_proof exit=0`).
- **Гейт разработки:** Реализация выполнена сабагентом Coder (`claude-sonnet-5-5-high`, транспорт `claude-p`) по скиллу `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md`.

---

## 2. Закрытие архитектурных требований и замечаний Совета

### 1. Изоляция по `backend_id` и защита глобального пула соединений (F-001, F-006)
- **Реализация в `core/resilience.py`:** Автоматы `CircuitBreaker` и `Bulkhead` регистрируются и управляются строго по каталожному `backend_id` (`droid`, `muse`, `codex`, `agy`, `opencode-zen`, `claude-p`).
- **Лимит Bulkhead:** Зафиксирован на уровне `min(configured_max, 64)`. При насыщении бэкенда (64 одновременных запроса) запрос немедленно отклоняется с кодом `HTTP 503` (`BULKHEAD_CAPACITY_EXCEEDED`) за <1 мс, освобождая слот глобального семафора соединений `_conn_sem` (128) и гарантируя доступность минимум 64 слотов для остальных бэкендов.

### 2. Ранний fail-fast до отправки HTTP-заголовков (F-005)
- **Точки перехвата в `server.py`:** Захват `ResilienceLease` вынесен в `do_POST` до вызова `_serve_passthrough` и до ветвления на сессионные маршруты (`_serve_sse`/`_serve_json`).
- При открытом `CircuitBreaker` или превышении емкости `Bulkhead` клиенту немедленно возвращается честный `HTTP 503` с заголовком `Retry-After: <секунды>` и телом ошибки до вызова `self.send_response(200)` или передачи стартовых кадров SSE.

### 3. Безопасность состояний автомата: Generation Tokens и Discard (F-001, F-002, F-004)
- В `CircuitBreaker` реализован монотонный счётчик поколений `_generation: int`. Ответы или исключения из устаревших поколений (запоздалые таймауты) отбрасываются и не могут повредить текущее состояние брейкера.
- Метод `record_discard(generation, reason)` позволяет корректно освободить слот пробы в состоянии `HALF_OPEN` без штрафа и без перевода брейкера в `OPEN` (например, при клиентском дисконнекте или нейтральной ошибке шлюза).
- Контекстный менеджер `ResilienceLease.__exit__` исключает ложный дефолтный успех: он фиксирует сбой только при наличии необработанного исключения (`exc_val is not None`), а при нормальном завершении требует явного вызова `record_success()` или `record_failure()`.

### 4. Явная фиксация исходов для passthrough и сессий (F-002, F-003)
- **Passthrough:** `if sink.status < 500: lease.record_success() else: lease.record_failure()`. Клиентские ошибки 4xx (400, 401, 404) не считаются отказом бэкенда и не приводят к открытию брейкера. Ошибки 502/503/504 гарантированно штрафуют брейкер.
- **Session (Stream / JSON):** Успех фиксируется только при `rc == 0`. Пустой стартовый кадр SSE успехом не считается. Падение бинарника mid-stream гарантированно вызывает `record_failure()`.
- **Клиентские обрывы:** `sink.client_gone` переводит исход в `record_discard("client_disconnected")`.

### 5. Полная конфигурируемость без хардкода по `AGENTS.md` п. 4 (F-004)
- Все пороги (емкость Bulkhead 64, порог брейкера 3, cooldown 30с, параметры экспоненциального бэкоффа ретраев) являются безопасными значениями по умолчанию (fallback) и вынесены в модуль `ResilienceFlags`.
- Флаги выкатываются через локальные снимки GigaRC (`FlagSource`, дефолт `false`) с безопасным fallback на переменные окружения (`RESILIENCE_ENABLED`, `CIRCUIT_BREAKER_ENABLED`, `BULKHEAD_ENABLED`, `RETRY_ENABLED`, `BULKHEAD_MAX_CONCURRENT`, `CIRCUIT_BREAKER_FAIL_THRESHOLD`, `CIRCUIT_BREAKER_COOLDOWN_S`, `RETRY_MAX_ATTEMPTS`, `RETRY_BASE_DELAY_S`, `RETRY_MAX_DELAY_S`).

### 6. Наблюдаемость и неизменность `/health` (F-005 Seat 2)
- Замороженный контракт `/health` сохраняет ровно 7 ключей без изменений.
- Состояние отказоустойчивости вынесено в отдельный эндпоинт `GET /v1/resilience` под защитой авторизации `_auth_ok`, возвращающий состояние брейкеров и отсеков по всем бэкендам.

---

## 3. Изменённые файлы и контрольные суммы
1. `core/resilience.py` (новый файл, 360 строк, чистый Python stdlib без внешних зависимостей)
2. `server.py` (интеграция в `do_POST`, `_HandlerSink`, ручка `GET /v1/resilience`)
3. `tests/test_resilience.py` (новый файл, 22 теста, полное покрытие контрактных сценариев)

---

## 4. Матрица верификации (L1/L2 Verification Matrix)

| Проверка | Команда | Результат | Статус |
|---|---|---|---|
| Юнит-тесты отказоустойчивости | `pytest tests/test_resilience.py -v` | 22 passed in 0.21s | **PASS** |
| Регрессионный набор passthrough | `pytest tests/test_passthrough_adapter.py -v` | 93 passed, 118 subtests passed in 25.87s | **PASS** |
| Линтер и форматирование | `ruff check core/resilience.py tests/test_resilience.py` | 0 errors | **PASS** |
| Инвариант владельца (No Fallback) | `test_facade_open_breaker_returns_503_retry_after_without_upstream_call` | Возврат HTTP 503 + Retry-After без обращения к upstream | **PASS** |
| Изоляция Bulkhead | `test_bulkhead_concurrency_isolation` | Превышение 64 слотов бэкенда не блокирует другие бэкенды | **PASS** |
| Защита поколений Breaker | `test_circuit_breaker_generation_token_safety` | Устаревшие ответы игнорируются | **PASS** |
| Конфигурируемость GigaRC | `test_resilience_gigarc_flags` | Динамические флаги с дефолтом false и env-override | **PASS** |


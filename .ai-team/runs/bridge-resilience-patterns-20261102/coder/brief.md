# Бриф для роли Coder: Реализация паттернов отказоустойчивости в cli-agent-bridge

~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md

## Задача и критерии приёмки
1. **Задача:** Реализовать универсальные агент-агностические паттерны отказоустойчивости (Circuit Breaker с generation tokens, Bulkhead с защитой глобального пула соединений, RetryPolicy с Full Jitter и контролем дедлайнов) в шлюзе `cli-agent-bridge`.
2. **Инвариант владельца:** Категорический запрет на автоматический fallback на резервную модель. При недоступности бэкенда — только честный `HTTP 503` с заголовком `Retry-After`.
3. **Конфигурируемость (`AGENTS.md` п. 4):** Никаких жестко зашитых констант; все пороги (емкость Bulkhead 64, порог брейкера 3, cooldown 30с, задержки ретраев) — безопасные значения по умолчанию (fallback), конфигурируемые через модуль `ResilienceFlags` (снимки GigaRC `default=false` + переменные окружения).
4. **Спецификация:** `docs/adr/0020-universal-backend-circuit-breaker-bulkhead-and-retries.md` (Rev 4) и `.ai-team/runs/bridge-resilience-patterns-20261102/architecture/architecture-packet.md`.

## Разрешённые пути для изменения
- `core/resilience.py` (новый чистый модуль)
- `server.py` (интеграция в `do_POST`, `_serve_passthrough`, ручка `GET /v1/resilience`)
- `tests/test_resilience.py` (новый тестовый файл с 8 сценариями)

## Что реализовать в `core/resilience.py`
1. `CircuitBreakerState` (CLOSED, OPEN, HALF_OPEN).
2. `CircuitBreaker`:
   - Потокобезопасный автомат (`threading.Lock`).
   - Счётчик поколений `_generation: int` для защиты от гонок устаревших ответов.
   - Метод `acquire() -> tuple[bool, int, bool]` (allowed, generation, is_probe).
   - Методы `record_success(generation)`, `record_failure(generation, exc=None)`, `record_discard(generation, reason="")`.
   - Свойства `state`, `retry_after`.
3. `Bulkhead`:
   - Ограничитель параллелизма на `threading.Semaphore`.
   - Лимит параллельных запросов на бэкенд: `min(configured_max, 64)`.
   - Неблокирующий захват (`acquire(timeout=0) -> BulkheadLease | None`).
4. `RetryPolicy`:
   - Full Jitter экспоненциальный бэкофф: `sleep = random.uniform(0, min(max_delay, base_delay * (2 ** attempt)))`.
   - Поддержка `deadline_s`.
   - Запрет повторов, если байты ответа уже отданы клиенту (`bytes_delivered == True`).
5. `ResilienceFlags`:
   - Чтение снимков GigaRC (`FlagSource`) со строгим дефолтом `false`:
     - `RESILIENCE_ENABLED`: bool (default False)
     - `CIRCUIT_BREAKER_ENABLED`: bool (default False)
     - `BULKHEAD_ENABLED`: bool (default False)
     - `RETRY_ENABLED`: bool (default False)
   - Конфигурируемые пороги с env-fallback:
     - `BULKHEAD_MAX_CONCURRENT`: int (default 64)
     - `CIRCUIT_BREAKER_FAIL_THRESHOLD`: int (default 3)
     - `CIRCUIT_BREAKER_COOLDOWN_S`: float (default 30.0)
     - `RETRY_MAX_ATTEMPTS`: int (default 3)
     - `RETRY_BASE_DELAY_S`: float (default 1.0)
     - `RETRY_MAX_DELAY_S`: float (default 10.0)
6. `ResilienceLease`:
   - Контекстный менеджер.
   - Явные методы: `record_success()`, `record_failure(exc=None)`, `record_discard(reason="")`.
   - `__exit__` освобождает Bulkhead и при отсутствии явного вызова фиксирует сбой ТОЛЬКО при наличии необработанного исключения (`exc_val is not None`). Дефолтного успеха нет.
7. `ResilienceManager`:
   - Реестр `CircuitBreaker` и `Bulkhead` по `backend_id` (`droid`, `muse`, `codex`, `agy`, `opencode-zen`, `claude-p`).
   - Метод `acquire(backend_id: str) -> ResilienceLease`.
8. Исключения:
   - `ResilienceError(Exception)`
   - `CircuitBreakerOpen(ResilienceError)` (несет `backend_id`, `retry_after`, `error_code="CIRCUIT_BREAKER_OPEN"`)
   - `BulkheadCapacityExceeded(ResilienceError)` (несет `backend_id`, `retry_after`, `error_code="BULKHEAD_CAPACITY_EXCEEDED"`)

## Что интегрировать в `server.py`
1. Экземпляр `RESILIENCE = ResilienceManager()`.
2. В `do_POST`:
   - Определение `backend_id = model.get("backend", "unknown")`.
   - Ранний захват `with RESILIENCE.acquire(backend_id) as lease:` ДО отправки любых заголовков (до `_serve_passthrough`, до `self.send_response(200)`).
   - Обработка `CircuitBreakerOpen` и `BulkheadCapacityExceeded`: возврат `HTTP 503` с заголовком `Retry-After: <sec>` и JSON-телом ошибки `{"error": {"message": ..., "type": "resilience_error", "code": exc.error_code, "retry_after": exc.retry_after}}`.
   - Явная фиксация:
     - В passthrough: `if sink.status < 500: lease.record_success() else: lease.record_failure()`.
     - В session: при `rc == 0: lease.record_success() else: lease.record_failure()`.
     - При клиентском разрыве (`_client_gone` / `BrokenPipeError`): `lease.record_discard("client_disconnected")`.
3. Новый эндпоинт `GET /v1/resilience`:
   - Авторизация через `self._auth_ok()`.
   - Возврат состояния брейкеров и отсеков по всем бэкендам в JSON.
4. Контракт `/health` оставить строго неизменным (7 ключей).

## Тесты в `tests/test_resilience.py`
Реализовать 8 сценариев из ADR-0020 Rev 4:
1. `test_circuit_breaker_transitions`: CLOSED -> OPEN после N сбоев, возврат 503 в OPEN с заголовком `Retry-After`.
2. `test_circuit_breaker_half_open_probe_success`: Переход в HALF_OPEN по истечении cooldown, успешная проба переводит в CLOSED.
3. `test_circuit_breaker_half_open_probe_failure`: Сбой пробы немедленно возвращает в OPEN с новым cooldown.
4. `test_circuit_breaker_generation_token_safety`: Ответ из устаревшего поколения отбрасывается и не меняет состояние текущего брейкера.
5. `test_circuit_breaker_record_discard`: Отмена пробы освобождает слот пробы без перевода в OPEN.
6. `test_bulkhead_concurrency_isolation`: Заполнение слотов бэкенда (до 64) возвращает 503 (`BULKHEAD_CAPACITY_EXCEEDED`), не затрагивая другие бэкенды.
7. `test_retry_policy_full_jitter_and_deadline`: Экспоненциальный рост со случайным джиттером, запрет повторов после `bytes_delivered == True`, отсечка по дедлайну.
8. `test_resilience_gigarc_flags`: Проверка динамических флагов GigaRC (`default=false`) и переопределения через env-переменные.

## Проверка качества перед завершением
- `uv run ruff format core/resilience.py server.py tests/test_resilience.py`
- `uv run ruff check --fix core/resilience.py server.py tests/test_resilience.py`
- `uv run pytest tests/test_resilience.py -v`
- Вывод handoff в формате JSON: `{"changed_files": [...], "commands": [...], "status": "DONE"}`

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
# Архитектурный пакет: Паттерны отказоустойчивости в cli-agent-bridge (Rev 4)

## Метаданные пакета
- **Задача:** Пресет `analyst-teamlead`, реализация Circuit Breaker, Bulkhead и Exponential Backoff Retries для CLI-адаптеров.
- **Инвариант владельца:** Строгий запрет на автоматический fallback на резервную модель. При недоступности бэкенда — только честный `HTTP 503` с заголовком `Retry-After`.
- **Базовый ADR:** `docs/adr/0020-universal-backend-circuit-breaker-bulkhead-and-retries.md` (Rev 4).
- **Матрица закрытия замечаний Совета Тимлидов R1 Cycle 3:**
  - **F-001 (Seat 1 & Seat 2):** Маршрутизация и изоляция по `backend_id`. Определение `backend_id = model["backend"]` из каталога `fleet.json` (6 бэкендов: `droid`, `muse`, `codex`, `agy`, `opencode-zen`, `claude-p`). Lease acquisition происходит в `do_POST` до ветвления на passthrough/stream/json.
  - **F-002 (Seat 1 & Seat 2):** Исключение дефолтного успеха в `ResilienceLease.__exit__`. Успех фиксируется строго явно: при `sink.status < 500` (passthrough) или `rc == 0` (session). Ошибки `502`/`503`/`504` и падения процессов фиксируются как failure.
  - **F-003, F-004 (Seat 1 & Seat 2):** Стриминг и mid-stream сбои. Стартовый пустой кадр (`role: assistant`) успех не фиксирует. Падение CLI-бинарника mid-stream гарантированно вызывает `record_failure()`.
  - **F-003, F-004 (Seat 1 & Seat 2):** Агент-агностичность повторов (`AGENTS.md` п. 5). `RetryPolicy` вынесен в универсальное ядро `core/resilience.py` и единообразно применяется для всех адаптеров, если байты ответа еще не переданы клиенту (`bytes_delivered == False`).
  - **F-005 (Seat 1):** Fail-fast 503 до отправки заголовков. Проверка брейкера и захват слота Bulkhead происходят до `self.send_response(200)` и до `_serve_passthrough`, возвращая немедленный `HTTP 503` с `Retry-After`.
  - **F-006 (Seat 1):** Защита пула глобальных соединений (`_conn_sem`). Запросы сверх Bulkhead (64) отклоняются за <1 мс, немедленно освобождая слот в семафоре соединений (128) и гарантируя доступность минимум 64 соединений для остальных бэкендов.
  - **F-007 (Seat 1):** Соответствие правилу GigaRC (`AGENTS.md:249`). Дефолт всех флагов `false`, чтение через локальный снимок GigaRC (`FlagSource`) с env-fallback.
  - **F-005 (Seat 2):** Авторизация на эндпоинте `/v1/resilience` через `_auth_ok`.

---

## 1. Архитектура компонентов (`core/resilience.py`)

Модуль `core/resilience.py` реализуется как stdlib-only компонент с классами:
1. `CircuitBreaker`: автомат `CLOSED -> OPEN -> HALF_OPEN` с счетчиком поколений `_generation` и методом `record_discard(generation)`.
2. `Bulkhead`: ограничитель параллелизма на `threading.Semaphore` с лимитом `min(max_concurrent, 64)`.
3. `RetryPolicy`: агент-агностический планировщик повторов с Full Jitter и контролем дедлайна, запрещающий повторы после начала отдачи данных (`bytes_delivered`).
4. `ResilienceFlags`: чтение снимков GigaRC (`default=false`) с безопасным fallback на переменные окружения.
5. `ResilienceManager`: реестр брейкеров и отсеков по `backend_id`.

```python
class ResilienceLease:
    def __init__(self, backend_id: str, breaker: CircuitBreaker, bulkhead_lease, generation: int, is_probe: bool):
        self.backend_id = backend_id
        self._breaker = breaker
        self._bulkhead_lease = bulkhead_lease
        self.generation = generation
        self.is_probe = is_probe
        self._recorded = False

    def record_success(self) -> None:
        if not self._recorded:
            self._recorded = True
            self._breaker.record_success(self.generation)

    def record_failure(self, exc: Exception | None = None) -> None:
        if not self._recorded:
            self._recorded = True
            self._breaker.record_failure(self.generation, exc)

    def record_discard(self, reason: str = "") -> None:
        if not self._recorded:
            self._recorded = True
            self._breaker.record_discard(self.generation, reason)

    def close(self) -> None:
        if self._bulkhead_lease:
            self._bulkhead_lease.close()
            self._bulkhead_lease = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if not self._recorded:
                if exc_val is not None:
                    self.record_failure(exc_val)
        finally:
            self.close()
```

---

## 2. Точки интеграции в `server.py`

### А. Входная точка в `do_POST` (до отправки любых HTTP-заголовков)
```python
backend_id = model["backend"]
try:
    with RESILIENCE.acquire(backend_id) as lease:
        if isinstance(passthrough, PassthroughAdapter):
            self._serve_passthrough(passthrough, raw, req, model_id, lease)
        elif is_stream:
            self._serve_stream(ctx, lease)
        else:
            self._serve_json(ctx, lease)
except ResilienceRejected as exc:
    self._send(
        503,
        {
            "error": {
                "message": f"Backend '{backend_id}' is temporarily unavailable: {exc.reason}",
                "type": exc.error_type,
                "code": exc.error_code,
                "retry_after": exc.retry_after,
            }
        },
        headers={"Retry-After": str(exc.retry_after)},
    )
    return
```

### Б. Явная фиксация исходов
- **Passthrough:**
  ```python
  adapter.handle(path=self.path, raw_body=raw, request=req, headers=headers, sink=sink)
  if sink.status < 500:
      lease.record_success()
  else:
      lease.record_failure()
  ```
- **Stream / JSON:**
  ```python
  if ok_done and out.get("rc") == 0:
      lease.record_success()
  else:
      lease.record_failure()
  ```

### В. Наблюдаемость
- Замороженный эндпоинт `/health` сохраняет 7 ключей без изменений.
- Состояние Circuit Breaker доступно авторизованным клиентам по адресу:
  `GET /v1/resilience` -> `{"backends": {"droid": {"state": "CLOSED", "active": 0}, ...}}`.

---

## 3. План тестирования (8 сценариев в `tests/test_resilience.py`)
1. `test_circuit_breaker_transitions`: Переход CLOSED -> OPEN после 3 сбоев, отказ 503 в OPEN с корректным `Retry-After`.
2. `test_circuit_breaker_half_open_probe_success`: Переход в HALF_OPEN по истечении cooldown, успешная проба переводит в CLOSED.
3. `test_circuit_breaker_half_open_probe_failure`: Сбой пробы немедленно возвращает автомат в OPEN с новым cooldown.
4. `test_circuit_breaker_generation_token_safety`: Запоздавший ответ из устаревшего поколения не изменяет состояние текущего брейкера.
5. `test_circuit_breaker_record_discard`: Отмена пробы клиентом или нейтральная ошибка освобождает слот пробы без открытия брейкера.
6. `test_bulkhead_concurrency_isolation`: Заполнение слотов passthrough-бэкенда (до лимита 64) возвращает 503 (`BULKHEAD_CAPACITY_EXCEEDED`), при этом запросы к другим бэкендам (`droid`, `muse`) проходят успешно, а глобальный семафор освобождается мгновенно.
7. `test_retry_policy_full_jitter_and_deadline`: Проверка экспоненциального роста задержки со случайным джиттером, запрета повторов после отдачи данных (`bytes_delivered`) и отсечки по превышению дедлайна.
8. `test_resilience_gigarc_flags`: Проверка динамических флагов GigaRC (дефолт `false`) и переопределения через переменные окружения.



---
PANEL-NONCE: 2dfb4a758ba18ee3
ARTIFACT-SHA256: f11926370796cb83074b1ddfce74de7ba251ee15b25a83a6621cb07ebaee77aa
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 2dfb4a758ba18ee3» и «ARTIFACT-SHA256: f11926370796cb83074b1ddfce74de7ba251ee15b25a83a6621cb07ebaee77aa».

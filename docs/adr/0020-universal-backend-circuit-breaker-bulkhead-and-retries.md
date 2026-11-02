# ADR 0020: Универсальный Circuit Breaker, Bulkhead и ретраи с экспоненциальным бэкоффом для CLI-адаптеров хаба (Rev 4)

## Статус
Proposed (Пресет `analyst-teamlead`, закрыты все замечания Совета Тимлидов R1 Cycle 3: F-001..F-007)

## Контекст и проблема
1. **Проблема спиннинга и наивных повторов процессов:** В шлюзе повторы дочерних CLI-процессов выполнялись разрозненно или отсутствовали вовсе для passthrough-маршрутов. В `server.py:5289` цикл был привязан исключительно к `droid` и использовал линейный сон `_sleep(2 * attempt)` без Full Jitter и дедлайна.
2. **Отсутствие Circuit Breaker в ядре:** При систематическом отказе любого из 6 бэкендов (`droid`, `muse`, `codex`, `agy`, `opencode-zen`, `claude-p`) мост продолжает на каждый входящий HTTP-запрос порождать новые процессы, растрачивая ресурсы CPU/PID вместо быстрого отказа (*fail-fast 503*).
3. **Отсутствие изоляции параллелизма (Bulkhead):** Лимит глобальных HTTP-соединений шлюза (`max_http_connections`) равен 128 (`fleet.json`). Бэкенды `passthrough` имеют `max_concurrent: 128`. Зависание одного бэкенда способно занять все 128 соединений, заблокировав обработку запросов к остальным бэкендам.
4. **Инвариант владельца:** Автоматический переход на резервную модель/провайдер категорически запрещён. При недоступности бэкенда клиент получает прозрачный `HTTP 503` с заголовком `Retry-After`.

---

## Архитектурные решения

### 1. Ключ изоляции: полный перечень `backend_id`
Изоляция Circuit Breaker и Bulkhead выполняется строго по уникальному идентификатору `backend_id`. Идентификатор определяется в `server.py:6177` как `backend_id = model["backend"]` из каталога `fleet.json`:
1. `droid` (`kind: droid`, `max_concurrent: 4`)
2. `muse` (`kind: muse`, `max_concurrent: 1`)
3. `codex` (`kind: passthrough`, `max_concurrent: 128`)
4. `agy` (`kind: passthrough`, `max_concurrent: 128`)
5. `opencode-zen` (`kind: passthrough`, `max_concurrent: 128`)
6. `claude-p` (`kind: passthrough`, `max_concurrent: 128`)

---

### 2. Универсальный модуль отказоустойчивости ядра (`core/resilience.py`)
Чистый модуль `core/resilience.py` (stdlib-only, без внешних зависимостей, потокобезопасность на `threading.Lock`).

#### А. Конечный автомат `CircuitBreaker` с поколениями (Generations)
- **Состояния:**
  - `CLOSED`: запросы разрешены, счетчик сбоев сбрасывается при успехе.
  - `OPEN`: зафиксировано $N$ (`fail_threshold`, по умолчанию 3) последовательных сбоев. Новые запросы отклоняются (*fail-fast 503*) без вызова адаптера в течение `cooldown_s`.
  - `HALF_OPEN`: по истечении `cooldown_s` (с рандомизацией `reset_timeout_s * uniform(0.8, 1.2)`) допускается ровно одна проба (`max_half_open_probes = 1`). При успехе автомат переходит в `CLOSED`, при сбое — в `OPEN`.
- **Защита от запоздавших ответов (Generation Tokens):**
  Каждый переход состояния автомата инкрементирует `generation: int`. Допущенный запрос получает `(generation, is_probe)`. Если при завершении вызова `call_generation != current_generation`, результат игнорируется, исключая порчу состояния брейкера старыми параллельными ответами.
- **Освобождение пробы `record_discard()`:**
  Если пробный запрос отменен клиентом, прерван нейтральной ошибкой или не дошел до бэкенда, вызывается `record_discard(generation)`, который освобождает слот пробы в `HALF_OPEN` без фиксации сбоя или перехода в `OPEN`.
- **Классификация исключений:**
  - *Технические сбои бэкенда (учитываются брейкером):* `BackendUnavailable` (бинарник не найден, exit!=0 на префлайте, порт недоступен), `BackendProtocolError` (пустой ответ, нарушение протокола IPC), `SubprocessError`, `BrokenPipeError` к CLI-бинарнику.
  - *Нейтральные события (не ухудшают брейкер, вызывают `record_discard`):* обрывы клиентского HTTP-соединения (`BrokenPipeError`/`ConnectionResetError` в `StreamSink`), `BackendTimeout` из-за медленного чтения клиентом, ошибки 400 Bad Request / 401 Auth.
- **Заголовок `Retry-After`:**
  При состоянии `OPEN` возвращается точное целое число секунд: `max(1, int(math.ceil(self._open_until - now)))`. Джиттер вычисляется единожды при входе в `OPEN` (`self._open_until = now + reset_timeout_s * uniform(0.8, 1.2)`).

#### Б. Изоляция параллелизма `Bulkhead` с защитой пула соединений
- Ограничение ёмкости passthrough-бэкендов:
  $$\text{capacity}(b) = \min(\text{backend\_max\_concurrent}, \text{BRIDGE\_BULKHEAD\_MAX\_PASSTHROUGH})$$
  По умолчанию `BRIDGE_BULKHEAD_MAX_PASSTHROUGH = 64`.
- **Механизм защиты пула соединений:** Глобальный семафор `_conn_sem` (128) удерживается на время обработки соединения. Запросы сверх лимита Bulkhead отклоняются немедленно (<1 мс) со статусом 503 (`BULKHEAD_CAPACITY_EXCEEDED`), освобождая `_conn_sem` без задержек. Это гарантирует, что даже при зависании одного бэкенда минимум 64 глобальных HTTP-слота всегда доступны для остальных бэкендов шлюза.

#### В. Агент-агностическая политика повторов `RetryPolicy` (Exponential Backoff & Full Jitter)
- Универсальный компонент `RetryPolicy` используется всеми адаптерами шлюза (`droid`, `muse` и passthrough):
  ```python
  class RetryPolicy:
      def should_retry(self, attempt: int, bytes_delivered: bool, exc: Exception | None = None) -> bool:
          if bytes_delivered or attempt >= self.max_attempts:
              return False
          return is_transient_backend_error(exc)

      def compute_delay(self, attempt: int, deadline_s: float | None = None) -> float | None:
          ...
  ```
- **Инвариант доставки:** Если клиенту уже были отправлены смысловые байты ответа (`bytes_delivered == True`), повтор строго запрещён, предотвращая повторную генерацию и дублирование контента.

---

### 3. Точки интеграции в шлюз (`server.py`)

#### 3.1. Единая точка маршрутизации в `do_POST` до отправки HTTP-заголовков
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

#### 3.2. Явная фиксация результата вызова в `ResilienceLease`
`ResilienceLease.__exit__` **НЕ** считает выход без исключения автоматическим успехом. Результат фиксируется строго явно:
1. **Passthrough:** `if sink.status < 500: lease.record_success()` иначе `lease.record_failure()`.
2. **Session / Stream / JSON:**
   - Пустой стартовый кадр SSE (`role: assistant`) успех не фиксирует.
   - Успех `lease.record_success()` фиксируется строго при успешном завершении хода (процесс завершился с `rc == 0`, сгенерирован финальный ответ).
   - Аварийный обрыв процесса mid-stream вызывает `lease.record_failure()`.
   - Клиентский обрыв сокета вызывает `lease.record_discard("client_disconnected")`.

#### 3.3. Наблюдаемость и безопасность
- Замороженный контракт `/health` (`server.py:5782`) из семи ключей сохраняется без изменений.
- Детальное состояние Circuit Breakers доступно по защищенному эндпоинту `GET /v1/resilience`, требующему авторизации через `_auth_ok(self.headers)`.

---

### 4. Конфигурируемость без хардкода (Zero-Hardcode) и соответствие GigaRC
В соответствии с правилом `AGENTS.md:249` (директива 2026-10-16):
- Все новые механизмы закрыты флагами GigaRC с дефолтом `false`:
  - `RESILIENCE_ENABLED`: мастер-флаг (дефолт `false`).
  - `CIRCUIT_BREAKER_ENABLED`: флаг брейкера (дефолт `false`).
  - `BULKHEAD_ENABLED`: флаг bulkheads (дефолт `false`).
  - `RETRY_ENABLED`: флаг повторов с бэкоффом (дефолт `false`).
- Флаги читаются через локальный снимок GigaRC (`FlagSource` по аналогии с `core/context_resilience.py`) с fallback на переменные окружения (`BRIDGE_RESILIENCE_ENABLED` и др.), обеспечивая мгновенный kill-switch в рантайме без перезапуска процессов.
- Полный набор параметров окружения:
  - `BRIDGE_RESILIENCE_ENABLED` = `false`
  - `BRIDGE_CIRCUIT_BREAKER_ENABLED` = `false`
  - `BRIDGE_BULKHEAD_ENABLED` = `false`
  - `BRIDGE_RETRY_ENABLED` = `false`
  - `BRIDGE_CB_FAIL_THRESHOLD` = `3`
  - `BRIDGE_CB_RESET_TIMEOUT_S` = `30.0`
  - `BRIDGE_BULKHEAD_MAX_PASSTHROUGH` = `64`
  - `BRIDGE_RETRY_MAX_ATTEMPTS` = `3`
  - `BRIDGE_RETRY_BASE_SLEEP_S` = `0.5`
  - `BRIDGE_RETRY_BACKOFF_FACTOR` = `2.0`
  - `BRIDGE_RETRY_MAX_SLEEP_S` = `5.0`

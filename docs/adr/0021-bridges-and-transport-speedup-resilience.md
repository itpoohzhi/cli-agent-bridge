# ADR 0021: Комплексная оптимизация и стабилизация транспортного уровня мостов (:9882, agy-bridge, opencode-zen-bridge)

## Статус
Approved (Пресет `analyst-teamlead` / `teamlead-with-architect`, задачи B-1..B-4 по handoff-1-bridges-and-transport.md с учетом замечаний коллегии F-001..F-008)

## Контекст и проблема
1. **Монолитный блокирующий вызов `agy-bridge` без идемпотентности и keepalive (B-1, REQ-SPEEDUP-01):**
   При обрыве клиентского HTTP-соединения (DSH socket reset или timeout) процесс `agy-cli.sh` теряет потребителя, а повторный запрос клиента (`llm/retry`) порождает новый дочерний процесс с нуля. При длительности шагов 8–60 минут это приводит к лавинообразному расходу CPU и потере прогресса. Отсутствие SSE heartbeat-комментариев (`: keepalive\n\n`) провоцирует ложные read-timeout на промежуточных прокси и в клиентах `urllib`/`httpx`.
2. **Отсутствие разделения таймаутов на :9882 (B-2, REQ-SPEEDUP-02):**
   В `adapters/passthrough_adapter.py` используется монолитный `read_timeout_s`. При буферизованных вызовах тяжёлых reasoning-моделей (`gpt-6.1-sol` high, `muse-wonder-full-1.0`) ответ формируется 118–330 с, из-за чего клиенты с дефолтным таймаутом 120 с рвут соединение за секунды до готовности. Отсутствует гранулярное разделение на `connect_timeout` (10 с), `idle_timeout` (60 с) и `total_timeout` (420 с). При `client_gone` зависшие вызовы не зачищаются вовремя.
3. **Неэффективный режим `--mode agent` для судейских запросов к `agy` (B-3, REQ-SPEEDUP-04):**
   При вызове `gemini-4-argon-high` в качестве судьи arch-panel через `:9882` (бэкенд `agy`) по умолчанию активировался `--mode agent`. Модель начинала рекурсивно обследовать файловую систему тулами, раздувая `raw.out` до 600–960 КБ и растягивая раунд до 147–237 с. Для задач судейства и ревью требуется строгий режим `--mode ask` (чистый LLM-ответ без файловых тулов).
4. **Зависание `opencode-zen-bridge` на промптах >8 КБ и отсутствие pre-flight фильтра (B-4, REQ-SPEEDUP-07):**
   В `opencode-zen-bridge` на длинных промптах (9–35 КБ) запросы зависали на 60–95 с, после чего возвращалось 16-байтное тело с HTTP 200 OK. Требуется жёсткий внутренний таймаут 25 с с честным кодом HTTP 504 Gateway Timeout. На мосту `:9882` требуется быстрый pre-flight фильтр (<50 мс), отсекающий модели в статусе `LIMIT BLOCKED` / `TEMP OFF` по `model-notes.md` с кодом HTTP 503 `MODEL_LIMIT_BLOCKED`, а также отклонение пустых/усечённых ответов <32 байт с кодом HTTP 502 `EMPTY_UPSTREAM_RESPONSE`.

---

## Архитектурные решения (AD-001..AD-004)

### AD-001: Идемпотентность по `step_job_id` / `X-Idempotency-Key` и фоновые SSE keepalive
1. **Реестр активных заданий (`JobRegistry`):**
   В универсальном слое и в `bridges/agy-bridge/server.py` создаётся потокобезопасный реестр заданий `JobRegistry`.
   - Ключ идемпотентности формируется связкой `(step_job_id, model, prompt_sha256)`, извлекаемой из заголовка `X-Idempotency-Key` или поля JSON-тела `step_job_id`.
   - При совпадении `step_job_id`, но несовпадении `prompt_sha256` или `model`, запрос немедленно отклоняется с кодом HTTP 409 Conflict.
   - Если для данного ключа процесс уже запущен:
     - Новый HTTP-запрос не спавнит дублирующий `agy-cli.sh`, а подключается (`attach`) к существующему буферу вывода / генератору стрима через потокобезопасный `threading.Condition`.
     - При подключении новый читатель получает replay ранее накопленных чанков и подписывается на живой поток без пропусков и дублирования.
     - Если задание уже завершено, немедленно отдаётся закэшированный финальный ответ с исходным статусом задания (200 или сохранённая ошибка).
2. **Ресурсный конверт `JobRegistry` (F-004):**
   - Максимальный размер буфера вывода на одно задание: конфигурируется через `AGY_BRIDGE_JOB_BUFFER_MAX_BYTES` (по умолчанию 5 МБ). При превышении лимита буфер переходит в режим кольцевого вытеснения с фиксацией `buffer_overflow=true`.
   - Максимальное число завершённых заданий в кэше: `AGY_BRIDGE_JOB_MAX_ENTRIES` (по умолчанию 100) с LRU-вытеснением.
   - Время жизни завершённых заданий (TTL): 15 минут.
   - Лимит параллельных фоновых осиротевших задач при `client_gone`: `AGY_BRIDGE_ORPHAN_CONCURRENCY_MAX` (по умолчанию 5). При превышении лимита новые осиротевшие задачи немедленно терминируются, не истощая слоты Bulkhead.
3. **Heartbeat-генератор в SSE:**
   В цикле стриминга `relay_sse` и в `_serve_sse_body`, если от вышестоящего бэкенда нет чанков более `BRIDGE_SSE_HEARTBEAT_INTERVAL_S` (по умолчанию 12.0 с, диапазон 10–15 с), в выходной поток немедленно записывается W3C-валидный комментарий `: keepalive\n\n`.
   Это предотвращает сброс соединения по `idle_timeout` в клиентах и промежуточных прокси, не искажая полезную нагрузку SSE `data: {...}`.

### AD-002: Гранулярное разделение таймаутов (`connect`, `idle`, `total`) и защита reasoning-моделей
1. **Конфигурируемые таймауты в `adapters/passthrough_adapter.py`:**
   Вводится структура `PassthroughLimits`, полностью настраиваемая через переменные окружения:
   - `connect_timeout_s`: по умолчанию 10.0 с (env: `BRIDGE_CONNECT_TIMEOUT_S`);
   - `idle_timeout_s`: по умолчанию 60.0 с (env: `BRIDGE_IDLE_TIMEOUT_S`);
   - `total_timeout_s`: по умолчанию 420.0 с (env: `BRIDGE_TOTAL_TIMEOUT_S`).
   Хардкод параметров запрещён.
2. **Защита Time-To-First-Token (TTFT) для reasoning-моделей (F-001):**
   Для reasoning-моделей (`gpt-6.1-sol` high, `muse-wonder-full-1.0`, `gemini-4-argon-high`), а также любых нестриминговых (`stream: false`) вызовов `idle_timeout_s=60s` не обрывает соединение до получения первого токена, если общее прошедшее время вызова меньше `total_timeout_s=420s`. `idle_timeout_s` отслеживает только паузы между последующими чанками данных после начала отдачи контента.
3. **Корректная обработка `client_gone`:**
   При обрыве клиента сокет и сессия не виснут. Если запрос не содержал `step_job_id`, дочерний процесс и сокет немедленно закрываются, освобождая слот Bulkhead.

### AD-003: Режим `chat/ask` (без тулов) по умолчанию для passthrough к `agy`
1. **Инспекция запроса в `adapters/passthrough_adapter.py` / `bridges/agy-bridge`:**
   При проксировании запроса к бэкенду `agy`:
   - Если в теле запроса нет `tools` / `functions` и не передан явный флаг `"agent_tools": true`, аргумент запуска `agy-cli.sh` выставляется в `--mode ask` (чистый текстовый режим без тулов обхода диска).
   - Если переданы `tools` либо `"agent_tools": true`, выставляется `--mode agent`.
2. **Результат:**
   Для судейских панелей и ревью объем вывода сокращается с 900 КБ до 5–15 КБ, а длительность раунда падает со 180 с до 25–40 с.

### AD-004: Защита `opencode-zen-bridge` и Pre-Flight фильтр `LIMIT BLOCKED`
1. **Таймаут 25 с в `opencode-zen-bridge` (F-006, F-008):**
   В `bridges/opencode-zen-bridge/server.py`:
   - Жёсткий таймаут 25 с (`BRIDGE_ZEN_TIMEOUT_S = 25.0`) применяется строго целевым образом для модели `deepseek-v4.1-flash-free` (и моделей, явно указанных в `BRIDGE_ZEN_TIMEOUT_MODELS`), когда размер входящего промпта в байтах превышает 8192 байта (`len(prompt.encode('utf-8')) > 8192`, env: `BRIDGE_ZEN_LARGE_PROMPT_BYTES`).
   - Гарантированная зачистка подпроцессов и закрытие сокетов выполняются в блоке `finally` (F-003).
2. **Согласование ошибок со стримингом (F-005):**
   - Если таймаут 25 с или сбой произошли ДО отправки HTTP-заголовков, клиенту возвращается честный HTTP 504 Gateway Timeout (`{"error": {"message": "Gateway Timeout in zen-bridge", "type": "timeout_error", "code": 504}}`).
   - Если заголовки HTTP 200 уже были отправлены (в режиме стриминга), сервер отправляет терминальный SSE error chunk:
     `data: {"error": {"message": "Gateway Timeout in zen-bridge", "type": "timeout_error", "code": 504}}\n\ndata: [DONE]\n\n`
     после чего немедленно закрывает соединение.
3. **Отсечка усечённых/пустых ответов:**
   - Проверка минимальной длины ответа (<32 байт, env: `BRIDGE_ZEN_MIN_CONTENT_BYTES`) выполняется по извлечённому содержанию поля `content` модели, а не по сырой JSON-оболочке.
   - Пустой или усечённый ответ <32 байт приводит к возврату HTTP 502 Bad Gateway (`{"error": {"message": "Empty upstream response", "type": "bad_gateway", "code": 502}}`).
   - Защита легитимных коротких запросов: проверка отключается для коротких входных промптов (<64 байт, например, `ping`, `PONG`, классификация) и при наличии заголовка `X-Bypass-Short-Filter: 1`.
4. **Pre-flight фильтр доступности моделей по `model-notes.md`:**
   В `server.py` перед вызовом любого бэкенда:
   - Выполняется парсинг `~/Мой диск/Context/model-notes.md` (<10 мс) с кэшированием mtime (TTL: `BRIDGE_MODEL_NOTES_CACHE_TTL_S = 10.0`).
   - Если запрошенная модель или её семейство помечены `LIMIT BLOCKED`, `TEMP OFF`, `QUOTA_EXHAUSTED`, запрос немедленно отклоняется с HTTP 503 Service Unavailable (`MODEL_LIMIT_BLOCKED`) и заголовком `Retry-After: 300`.
   - Запросы с заголовком `X-Bypass-Model-Filter: 1`, а также вызовы проверки здоровья (`/health`, `PONG`) пропускаются в обход фильтра (F-005).

---

## Границы компонентов (Boundaries BND-001..BND-004)
- **BND-001 (Universal Gateway `:9882`):** `server.py`, `core/resilience.py`. Маршрутизация, pre-flight фильтр моделей, единые заголовки `X-Idempotency-Key`, Bulkhead и Circuit Breaker.
- **BND-002 (Passthrough Adapter):** `adapters/passthrough_adapter.py`. Раздельные таймауты (`connect`, `idle`, `total`), проброс SSE keepalive, селектор `--mode ask/agent`, защита TTFT.
- **BND-003 (AGY Bridge):** `bridges/agy-bridge/server.py`. Управление процессом `agy-cli.sh`, реестр активных заданий `JobRegistry` по `(step_job_id, model, prompt_sha256)`, поддержка повторного переподключения (`attach`), resource envelope.
- **BND-004 (OpenCode Zen Bridge):** `bridges/opencode-zen-bridge/server.py`. Таймаут 25 с для `deepseek-v4.1-flash-free` на промптах >8192 байт, разграничение 504 / SSE error, фильтр <32 байт content, гарантированный cleanup.

---

## Сценарии качества (Quality Scenarios QA-001..QA-005)
- **QA-001 (Performance & Latency):** Запрос судьи `gemini-4-argon-high` в режиме `--mode ask` завершается за $\le 60\text{ с}$, размер сырого вывода $\le 30\text{ КБ}$.
- **QA-002 (Reliability & Reconnect):** При обрыве соединения посреди 180-секундного вызова и повторе с тем же `step_job_id` процесс не перезапускается, а отдаёт завершённый результат без дублирования.
- **QA-003 (Resilience & Timeouts):** Reasoning-модели с задержкой первого токена до 120 с не обрываются по таймауту благодаря `total_timeout = 420 с` и SSE keepalive каждые 10–15 с.
- **QA-004 (Fail-Fast):** Запрос к заблокированной в `model-notes.md` модели отсекается pre-flight фильтром за $\le 50\text{ мс}$ с кодом HTTP 503.
- **QA-005 (Zen Bridge Safety):** Запрос промпта 15 КБ к `deepseek-v4.1-flash-free` завершается за $\le 25\text{ с}$ (либо валидным ответом, либо честным HTTP 504 / terminal SSE error).

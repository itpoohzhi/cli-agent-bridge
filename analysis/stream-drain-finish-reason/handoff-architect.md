# Handoff to Architect — Системный анализ сбоев стриминга, перезапуска моста и эмуляции инструментов в DeepSeek Harness

- **Задача:** `fix-stream-drain-finish-reason`
- **Прогон (`run_id`):** `fix-stream-drain-finish-reason-20261110`
- **Роль:** `system-analyst` (`Analyst`, модель `gpt-6.1-sol`, `X-Request-Id: req_62f609577687`)
- **Базовый коммит (`BASE_COMMIT`):** `31bbb52b213cf2fb9006e02ee26e64f9156f4854`

---

## 1. Краткое резюме задачи и бизнес-цель

Устранить на универсальном (агент-агностик) уровне шлюза `cli-agent-bridge` три боевых отказа, зафиксированных владельцем на двух скриншотах DeepSeek Harness (`[F-01]`..`[F-30]`):
1. **Сбой 1 (`Stream ended without finish_reason`, категория `TRANSPORT`):** При ошибке выполнения хода, отмене, истечении таймаута или начале `drain` после открытия SSE-потока (`HTTP 200 text/event-stream`) клиент DeepSeek Harness получает либо чанк с `finish_reason: null`, либо плоский объект `{"error": ...}` без массива `choices`, либо закрытие сокета без `data: [DONE]\n\n`, что вызывает падение парсера DSH с ошибкой `Stream ended without finish_reason` (`[F-06]`, `[F-07]`, `[F-10]`..`[F-16]`, `[F-28]`). Кроме того, при успешном получении слота в `QoSSlotManager` после срабатывания `_keepalive_cb` (`self._headers_already_sent = True`) метод `_serve_sse_body` повторно записывает сырые HTTP-заголовки `HTTP/1.0 200 OK` прямо внутрь открытого SSE-потока (`[F-05]`, `[F-08]`).
2. **Сбой 2 (`Codex upstream stream failed via proxy endpoint ...: ClientPayloadError`, категория `PI_AI_ERROR`, и пропуск `finish_reason` в `passthrough_adapter.py`):** В `adapters/passthrough_adapter.py` функция `relay_sse` пересылает сырые SSE error-кадры апстрима без массива `choices` (`write(raw)`) и при `trusted_tools=False` игнорирует незавершённые индексы `seen - finished` перед `data: [DONE]`, а также закрывает поток по EOF при пустом `seen` без единого чанка `finish_reason` (`[F-17]`..`[F-21]`).
3. **Сбой 3 (`503: {"message":"bridge is draining for restart","type":"overloaded","code":503}`, категория `SERVER`, и `[Вызов инструмента: unknown_tool]`):**
   - Во время `drain` (`SIGTERM`) `HubLifecycleManager.run_drain_once` ждёт завершения активных ходов до `110.0` с с открытым слушающим сокетом на `:9882`, а `Handler.do_POST` немедленно отвергает все новые запросы с HTTP 503 без окна удержания (`hold-and-serve` / `drain_hold`), тогда как в профиле DSH `retryPolicy.maxRetries` равен `0` (`[F-01]`..`[F-04]`, `[F-26]`, `[F-28]`).
   - В `adapters/muse_msp.py` метод `MspEvents.feed` использует дефолт `unknown_tool` и проверяет только `raw.get("toolName")` на `"item/started"`, а `MuseAdapter._build_serve_cmd` не передаёт `--disable-builtin-tools`, что приводит к спаму `[Вызов инструмента: unknown_tool]` в `delta.reasoning_content` (`[F-22]`..`[F-25]`, `[F-29]`).

---

## 2. Подтверждённый скоуп и границы (In-Scope / Out-of-Scope)

### In-Scope (внутри `cli-agent-bridge`)
- `core/stream_framing.py` и `server.py`: единый инвариант терминального SSE-фрейминга (любой открытый SSE-поток обязан завершиться чанком с непустым `choices[0].finish_reason` и `data: [DONE]\n\n` на всех путях ошибок, `qos_ok=False`, `ResilienceError`, исключений `_dispatch` и `live_sent >= 0`) и защита от повторной отправки HTTP-заголовков при `self._headers_already_sent == True` (`[F-05]`..`[F-13]`).
- `core/turn_session_manager.py`: гарантия терминального `finish_reason` и `data: [DONE]\n\n` в `BufferedTurnEvent.to_sse_frame` для `kind == "error"` и при `finalize_abandoned_turn` / `interrupt_for_drain` / `cancel_turn` (`[F-14]`, `[F-15]`), а также исключение пустого `"name": ""` на чанках-продолжениях в `TurnBuffer.feed_fsm_chunk` (`[F-25]`).
- `adapters/passthrough_adapter.py`: перехват и нормализация upstream SSE error-кадров (`chunk.get("error")` при отсутствии `choices`) через `build_stream_error_chunk` с `finish_reason="stop"`, безусловное закрытие всех незавершённых `seen - finished` (независимо от `trusted_tools`) перед `data: [DONE]` и эмиссия терминального error/stop-чанка при EOF с пустым `seen` (`[F-18]`..`[F-21]`).
- `core/lifecycle.py` и `server.py`: конфигурируемое окно graceful hold/ожидания (`BRIDGE_DRAIN_HOLD_TIMEOUT_S`) и неразрывное обслуживание уже принятых в `QoSSlotManager` интерактивных запросов при наличии запаса времени до дедлайна drain (`[F-01]`..`[F-06]`).
- `adapters/muse_msp.py`, `adapters/muse_adapter.py` и `core/tool_emulation.py`: нормализация имени инструмента из `toolName`/`tool`/`name`/`item.toolName` с обновлением на `"item/completed"`, подавление спам-маркера `unknown_tool` для безымянных внутренних служебных MSP-событий (`hookRun`, `reminderChild`), передача `--disable-builtin-tools` в `MuseAdapter._build_serve_cmd` при `disable_builtin_tools=True` и фильтрация пустых `function.name == ""` в `_sanitize_call` (`[F-22]`..`[F-24]`).

### Out-of-Scope
- Модификация бинарного кода или исходников DeepSeek Harness и внешнего прокси `codex-lb` (`:2455`).
- Модификация скиллового скрипта `select_round_seats.py` (передача `raw.err` вместо `seats/<k>/launch.json` — нарушение контракта вызывающим агентом на Скриншоте 1, `[F-30]`).

---

## 3. Функциональные требования и сценарии (`[F-01]`..`[F-30]`)

- **REQ-001 (Единый терминальный контракт SSE и защита заголовков в `server.py` и `core/turn_session_manager.py`):** Каждый ответ `POST /v1/chat/completions` со `stream=True`, для которого уже отправлены заголовки `HTTP 200 text/event-stream` (включая срабатывание `_keepalive_cb` в `QoSSlotManager`), обязан: (а) никогда не отправлять повторно HTTP-статус и заголовки в `_serve_sse_body` при `self._headers_already_sent == True`; (б) на любом пути ошибки (`qos_ok=False`, `ResilienceError`, исключение в `_dispatch`, ошибка бэкенда при `live_sent == 0` и `live_sent > 0`, `BufferedTurnEvent(kind="error")`, `finalize_abandoned_turn`) эмитировать канонический SSE-чанк с непустым `choices[0].finish_reason` (`graceful_finish_reason()`, по умолчанию `"stop"`) и завершать поток кадром `data: [DONE]\n\n` (`[F-05]`, `[F-06]`, `[F-07]`, `[F-08]`, `[F-10]`, `[F-11]`, `[F-12]`, `[F-13]`, `[F-14]`, `[F-15]`).
- **REQ-002 (Нормализация upstream SSE-ошибок и `finish_reason` в `adapters/passthrough_adapter.py`):** В `relay_sse` (`adapters/passthrough_adapter.py`): (а) при получении от upstream JSON-кадра без списка `choices`, содержащего поле `"error"` (например, `Codex upstream stream failed via proxy endpoint ...: ClientPayloadError`), не пересылать сырой кадр без `choices`, а преобразовывать его в канонический чанк `build_stream_error_chunk` с `choices[0].finish_reason = graceful_finish_reason()` (`"stop"`), помечать выбор завершённым в `finished` и фиксировать `outcome.error_code`; (б) при получении `data: [DONE]` досылать синтетический `finish_reason: "stop"` для всех незавершённых индексов `seen - finished` (либо для индекса `0`, если `seen` пуст) независимо от флага `trusted_tools`; (в) при EOF без `data: [DONE]` и пустом `seen` эмитировать терминальный `_error_frame` с `finish_reason="stop"` и `data: [DONE]\n\n` (`[F-17]`, `[F-18]`, `[F-19]`, `[F-20]`, `[F-21]`).
- **REQ-003 (Graceful Drain Admission & QoS Slot Continuity в `core/lifecycle.py` и `server.py`):** (а) В `QoSSlotManager.acquire_slot` не прерывать немедленно ожидание уже принятых интерактивных запросов (`not is_subagent`) по `drain_event.is_set()`, если до дедлайна drain остаётся достаточный резерв времени (`BRIDGE_DRAIN_QOS_GRACE_S`, конфигурируемо через env); (б) при поступлении нового запроса в начале/конце drain поддержать конфигурируемое окно ожидания переключения (`BRIDGE_DRAIN_HOLD_TIMEOUT_S`, по умолчанию безопасно настраиваемое через env) и согласованный `Retry-After` (`[F-01]`, `[F-02]`, `[F-03]`, `[F-04]`, `[F-26]`, `[F-28]`).
- **REQ-004 (Устранение `[Вызов инструмента: unknown_tool]` и безымянных `tool_calls` в `adapters/muse_msp.py`, `adapters/muse_adapter.py`, `core/tool_emulation.py`, `core/turn_session_manager.py`):** (а) В `MspEvents.feed` (`adapters/muse_msp.py`) извлекать имя инструмента по цепочке `toolName` -> `tool` -> `name` -> `item.toolName` с санитизацией символов вне `[A-Za-z0-9_.:-]` в `_` и дообновлением имени на `"item/completed"`, а для внутренних служебных MSP-событий без имени инструмента не эмитировать спам `[Вызов инструмента: unknown_tool]`; (б) в `MuseAdapter._build_serve_cmd` передавать `--disable-builtin-tools` при `self._cfg.disable_builtin_tools == True`; (в) в `_sanitize_call` (`core/tool_emulation.py`) отбраковывать вызовы с пустым именем `not name`, а в `TurnBuffer.feed_fsm_chunk` (`core/turn_session_manager.py`) не записывать пустое `"name": ""` в чанки-продолжения аргументов (`[F-22]`, `[F-23]`, `[F-24]`, `[F-25]`, `[F-29]`).
- **REQ-005 (Отсутствие хардкода эксплуатационных параметров):** Все новые или уточняемые пороги и флаги (`BRIDGE_DRAIN_HOLD_TIMEOUT_S`, `BRIDGE_DRAIN_QOS_GRACE_S`, `BRIDGE_GRACEFUL_ERROR_FRAMING_ENABLED`, `BRIDGE_GRACEFUL_FINISH_REASON`, `BRIDGE_MUSE_SUPPRESS_UNKNOWN_TOOL`) должны читаться из переменных окружения и конфигурации с безопасными значениями по умолчанию (`[F-03]`, `[F-10]`, `[F-23]`).

---

## 4. Нефункциональные требования (NFR) и ограничения

- **Надёжность стриминга (L1/L2 инварианты):** 100% потоков `POST /v1/chat/completions` со `stream=True` при любом сценарии отказа апстрима, таймаута или drain завершаются ровно одним терминальным чанком с непустым `finish_reason` и `data: [DONE]\n\n` (`[F-10]`..`[F-20]`).
- **Скользящее окно активности (`L-LIVE/v1`):** Любой полезный чанк (`content`, `reasoning_content`, `tool_calls`) сдвигает дедлайн неактивности вперёд (`deadline = now + idle_timeout_s`).
- **Модульность (`M-MOD/v1`):** Новые модули не превышают `300` физических строк; для baseline-монолитов (`>300` строк на `BASE_COMMIT`, таких как `server.py`, `adapters/passthrough_adapter.py`, `core/turn_session_manager.py`, `core/lifecycle.py`, `core/tool_emulation.py`, `adapters/muse_adapter.py`) соблюдается `added_lines - deleted_lines <= 0` с выносом новой чистой логики во вспомогательные модули и фасадом `<= 5` строк.

---

## 5. Внешние контракты, интеграции и зависимости

- Внешний OpenAI-совместимый контракт `POST /v1/chat/completions` (SSE `chat.completion.chunk`) и заголовки `Retry-After` / `X-Bridge-Draining` сохраняют обратную совместимость (`[F-01]`, `[F-26]`).
- Клиент DeepSeek Harness (`@deepseek-ai/dsh-llm-pi-ai`) требует присутствия непустого `choices[0].finish_reason` перед `data: [DONE]` в каждом SSE-потоке (`[F-18]`, `[F-28]`).
- Применимость гейтов Highload: для любых неприменимых к локальному однопроцессному демону подпунктов доказательство неприменимости (`N/A`) опирается одновременно на `git diff` от `BASE_COMMIT` и транзитивный граф вызовов (`callers` / `callees`), подтверждающий отсутствие пересечения с распределёнными k8s/БД-путями.

---

## 6. High-Load Context Envelope (`HL-ENV/v1`, 46 атомарных полей `REQUIRED_HL_ENV_FIELDS`)

Ниже приведена полная таблица из 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` в единицах СИ для целевого контура `cli-agent-bridge` (`127.0.0.1:9882`, локальный macOS launchd-демон `com.user.dsh-hub`):

| № | Поле `REQUIRED_HL_ENV_FIELDS` | Тип (`in`/`derived`) | Единица | Значение в СИ | Источник / Формула (`[F-NN]`) |
|---|---|---|---|---|---|
| 1 | `P_steady` | `in` | `pods` | `1 pods` | `~/Library/LaunchAgents/com.user.dsh-hub.plist` (`KeepAlive=true`, 1 экземпляр демона, `[F-03]`) |
| 2 | `P_hpa_max` | `in` | `pods` | `1 pods` | `com.user.dsh-hub.plist` (локальный демон без горизонтального автоскейлинга, `[F-03]`) |
| 3 | `maxSurge_pct` | `in` | `ratio` | `1.0 ratio` | `server.py:8647-8660` (`BRIDGE_SO_REUSEPORT_ENABLED=true`, допускается 1 новый процесс при перезапуске, `[F-03]`) |
| 4 | `maxSurge_abs` | `derived` | `pods` | `1 pods` | `ceil(P_hpa_max * maxSurge_pct) = ceil(1 * 1.0) = 1 pods` (`[F-03]`) |
| 5 | `maxUnavailable_pct` | `in` | `ratio` | `0.0 ratio` | `com.user.dsh-hub.plist` (`KeepAlive=true`, целевая доступность 1 инстанса, `[F-03]`) |
| 6 | `maxUnavailable_abs` | `derived` | `pods` | `0 pods` | `floor(P_steady * maxUnavailable_pct) = 0 pods` (`[F-03]`) |
| 7 | `P_terminating_overlap` | `in` | `pods` | `1 pods` | `core/lifecycle.py:542-630` (1 старый процесс в фазе `DRAINING` до `110.0 s`, `[F-03]`) |
| 8 | `P_live` | `derived` | `pods` | `3 pods` | `P_hpa_max + maxSurge_abs + P_terminating_overlap = 1 + 1 + 1 = 3 pods` (`[F-03]`) |
| 9 | `P_avail_min` | `derived` | `pods` | `1 pods` | `max(1, P_steady - maxUnavailable_abs) = 1 pods` (`[F-03]`) |
| 10 | `W` | `in` | `proc/pod` | `1 proc/pod` | `server.py:8811-8831` (`ThreadingHTTPServer` в 1 процессе Python, `[F-03]`) |
| 11 | `N_proc` | `derived` | `processes` | `3 processes` | `P_live * W = 3 * 1 = 3 processes` (`[F-03]`) |
| 12 | `N_proc_steady` | `derived` | `processes` | `1 processes` | `P_steady * W = 1 * 1 = 1 processes` (`[F-03]`) |
| 13 | `N_proc_avail_min` | `derived` | `processes` | `1 processes` | `P_avail_min * W = 1 * 1 = 1 processes` (`[F-03]`) |
| 14 | `CPU_limit_per_pod` | `in` | `cores` | `4.0 cores` | Бюджет CPU локального демона `dsh-hub` на хосте macOS (`[F-03]`) |
| 15 | `κ_skew` | `in` | `ratio` | `1.0 ratio` | Для `W = 1 proc/pod` межворкерный перекос отсутствует (`1.0`, `[F-03]`) |
| 16 | `u_bg_worker` | `in` | `cores` | `0.02 cores` | Фоновые потоки `hub-drain-coordinator`, `ProcessWatchdog` и `InstructionGuard` (`server.py:4040`, `[F-09]`) |
| 17 | `U_pod_sidecars` | `in` | `cores` | `0.05 cores` | Дочерние фоновые хелперы в пределах группы процесса (`[F-09]`) |
| 18 | `Mem_limit_per_pod` | `in` | `MiB` | `1024 MiB` | Целевой потолок памяти процесса `dsh-hub` (`1024 MiB`, `[F-03]`) |
| 19 | `Mem_rss_worker_max` | `in` | `MiB` | `256 MiB` | Пиковый приватный RSS процесса `server.py` с кольцевыми буферами `TurnBuffer` (`[F-14]`) |
| 20 | `Mem_shared_max` | `in` | `MiB` | `64 MiB` | Разделяемые библиотеки и файловые кэши состояния (`1 * 256 + 64 = 320 MiB <= 0.80 * 1024 = 819.2 MiB`, `[F-03]`) |
| 21 | `RPS_peak` | `in` | `req/s` | `20 req/s` | Пиковый локальный поток запросов от DSH и параллельных сабагентов (`[F-28]`) |
| 22 | `A_max` | `in` | `attempts/req` | `2 attempts/req` | Первичная попытка + до 1 fallback/reconnection в `PassthroughAdapter` (`adapters/passthrough_adapter.py:1666`, `[F-18]`) |
| 23 | `SLA_p99_s` | `in` | `s` | `1800.0 s` | `timeoutMs: 1800000` (`1800.0 s`) в `~/.dsh/profiles/desktop/cordis.patch.yml:931` (`[F-26]`) |
| 24 | `N_entities_max` | `in` | `items` | `1024 items` | Верхняя граница числа отслеживаемых сессий/ходов в `TurnSessionManager` (`core/turn_session_manager.py`, `[F-15]`) |
| 25 | `Limit_dep_share[d]` | `in` | `connections` | `codex_lb: 64 connections, muse_cli: 1 connections, droid_cli: 16 connections` | Лимиты параллельных подключений в `providers.d/codex.yaml` и `providers.d/muse.yaml:14` (`max_concurrent: 1`, `[F-17]`, `[F-27]`) |
| 26 | `Limit_dep_rps[d]` | `in` | `req/s` | `codex_lb: 20 req/s, muse_cli: 5 req/s, droid_cli: 10 req/s` | Допустимый темп запуска/проксирования по локальным апстримам (`[F-17]`, `[F-27]`) |
| 27 | `W_fetchers[d]` | `in` | `proc/pod` | `1 proc/pod` | Одиночный процесс `server.py` (`W = 1`, `[F-09]`) |
| 28 | `J_init_s[d]` | `in` | `s` | `1.0 s` | Стартовый джиттер фоновых проверок (`[F-09]`) |
| 29 | `J_pod_s[d]` | `in` | `s` | `0.0 s` | Одноподовый локальный контур (`P_steady = 1`, `[F-03]`) |
| 30 | `T_poll_s[d]` | `in` | `s` | `30.0 s` | `GUARD_TICK_S = 30` с для `InstructionGuard` в `server.py:4040` (`[F-09]`) |
| 31 | `K_calls[d]` | `in` | `calls` | `1 calls` | Одиночный запрос к апстриму на попытку (`[F-18]`) |
| 32 | `T_base_s[d]` | `in` | `s` | `0.5 s` | Базовый шаг backoff при временных сетевых сбоях (`[F-18]`) |
| 33 | `T_cap_s[d]` | `in` | `s` | `5.0 s` | Верхний предел `Retry-After` (`BRIDGE_RETRY_AFTER_S = 5.0 s` в `core/lifecycle.py:39`, `[F-01]`) |
| 34 | `Max_stale_age_s[c]` | `in` | `s` | `routing_snapshot: 30.0 s, dynamic_config: 30.0 s, auth_secret: 0.0 s` | Максимальный возраст кэша `InstructionGuard` (`30.0 s`) и немедленное чтение токенов (`0.0 s`, `[F-09]`) |
| 35 | `Min_healthy_ratio` | `in` | `ratio` | `0.5 ratio` | Минимальная доля здоровых апстрим-слотов в пуле (`[F-09]`) |
| 36 | `B_retry_max` | `in` | `tokens` | `10 tokens` | Ёмкость локального бюджета ретраев на процесс (`[F-18]`) |
| 37 | `min_reserve_retry_rps` | `in` | `req/s` | `0.5 req/s` | Минимальный резерв подпитки ретраев для локального трафика (`[F-18]`) |
| 38 | `FD_worker` | `in` | `descriptors` | `512 descriptors` | Пиковое число открытых сокетов и pipe-дескрипторов дочерних CLI в `server.py` (`[F-03]`) |
| 39 | `ulimit_n` | `in` | `descriptors` | `65536 descriptors` | Системный лимит файловых дескрипторов macOS launchd (`[F-03]`) |
| 40 | `λ_new_conn_per_pod(s)` | `in` | `conn/s` | `node_ephemeral: 20 conn/s, shared_snat: 5 conn/s` | Темп открытия loopback TCP-соединений на `127.0.0.1:9882` и `:2455` (`[F-17]`) |
| 41 | `C_active_in_scope(s)` | `in` | `connections` | `node_ephemeral: 64 connections, shared_snat: 16 connections` | Одновременно активные соединения (в пределах `max_concurrent`, `[F-27]`) |
| 42 | `N_pods_in_scope(s)` | `in` | `pods` | `node_ephemeral: 1 pods, shared_snat: 1 pods` | Локальный узел macOS (`1 pods`, `[F-03]`) |
| 43 | `Port_range_size(s)` | `in` | `ports` | `node_ephemeral: 16383 ports, shared_snat: 16383 ports` | Диапазон эфемерных портов macOS (`49152..65535 = 16383 ports`, `[F-03]`) |
| 44 | `T_hold_s(s)` | `in` | `s` | `node_ephemeral: 15.0 s, shared_snat: 60.0 s` | Время удержания `TIME_WAIT` на loopback и внешнем прокси (`[F-17]`) |
| 45 | `SNAT_ips_count(s)` | `in` | `IPs` | `node_ephemeral: 1 IPs, shared_snat: 1 IPs` | Один локальный IP `127.0.0.1` (`[F-03]`) |
| 46 | `HOTPATH_MODULES` | `in` | `list[str]` | `["server.py", "core/stream_framing.py", "core/turn_session_manager.py", "core/lifecycle.py", "core/tool_emulation.py", "adapters/passthrough_adapter.py", "adapters/muse_msp.py", "adapters/muse_adapter.py"]` | Модули горячего пути обработки запросов и SSE-чанков в `cli-agent-bridge` (`[F-01]`..`[F-25]`) |

Проверка замыкания памяти пода (`HL-ENV-01`):
$$W \cdot \text{Mem\_rss\_worker\_max} + \text{Mem\_shared\_max} = 1 \times 256\text{ MiB} + 64\text{ MiB} = 320\text{ MiB} \le 0.80 \times 1024\text{ MiB} = 819.2\text{ MiB}.$$

---

## 7. Causal Funnel (Воронка причинности)

1. **Воронка симптома `Stream ended without finish_reason` (`TRANSPORT`, Скриншот 2):**
   - **Кандидат 1.1:** Обрыв в `_serve_sse_body` (`server.py:8416`, `8602-8612`) при вызове `stream_error_frame`, где жёстко передан `finish_reason=None`, либо отправка плоского `data: {"error": err}\n\n` при `live_sent[0] == 0`. **Статус:** Подтверждено (`[F-10]`, `[F-11]`, `[F-12]`).
   - **Кандидат 1.2:** Обрыв в `_serve_resilient` (`server.py:7975-8036`, `8073-8090`), когда запрос `muse-ember-1.0` (`req_3bacf3e93e7d` в `18:27:50 MSK`) стоял в очереди `QoSSlotManager` за `req_2b2f605fc565` (`max_concurrent: 1`), `_keepalive_cb` уже открыл `HTTP 200 text/event-stream` (`headers_sent[0] = True`), а при начале `drain` или получении слота сервер либо закрыл поток без `finish_reason` и `[DONE]`, либо записал дублирующие HTTP-заголовки в `_serve_sse_body` (`server.py:8345-8357`). **Статус:** Подтверждено (`[F-05]`, `[F-06]`, `[F-08]`, `[F-28]`).
   - **Кандидат 1.3:** Отсутствие `finish_reason` и `[DONE]` в `BufferedTurnEvent.to_sse_frame` (`kind="error"`) и `finalize_abandoned_turn` в `core/turn_session_manager.py:372-390, 1302-1319`. **Статус:** Подтверждено (`[F-14]`, `[F-15]`).
2. **Воронка симптома `Codex upstream stream failed via proxy endpoint ...: ClientPayloadError` (`PI_AI_ERROR`, Скриншот 1):**
   - **Кандидат 2.1:** Ошибка генерируется внутри `cli-agent-bridge`. **Статус:** Опровергнуто (`cli-agent-bridge` не использует `aiohttp`; строку формирует `codex-lb` на `:2455`, `[F-17]`).
   - **Кандидат 2.2:** `relay_sse` в `adapters/passthrough_adapter.py:937-970` пересылает сырой error-кадр апстрима без массива `choices` (`write(raw)`) и при `trusted_tools=False` пропускает досылку `finish_reason` для `seen - finished` перед `[DONE]`. **Статус:** Подтверждено (`[F-18]`, `[F-19]`, `[F-20]`).
3. **Воронка симптома `503: bridge is draining for restart` (`SERVER`, Скриншот 1) и `[Вызов инструмента: unknown_tool]` (Скриншот 2):**
   - **Кандидат 3.1:** Внутренний вотчдог перезапускает `server.py`. **Статус:** Опровергнуто (`ProcessWatchdog` убивает только PGID хода; `SIGTERM` пришёл извне при рестарте сервиса в `15:30:49Z`, `[F-09]`, `[F-28]`).
   - **Кандидат 3.2:** Во время 61-секундного ожидания активных ходов в `run_drain_once` (`core/lifecycle.py:567-625`) старый процесс держит сокет `:9882` и немедленно отвечает 503 в `do_POST` (`server.py:6884-6898`), а DSH при `maxRetries: 0` сразу роняет ход. **Статус:** Подтверждено (`[F-02]`, `[F-03]`, `[F-04]`, `[F-26]`, `[F-28]`).
   - **Кандидат 3.3:** Строка `[Вызов инструмента: unknown_tool]` порождается `MspEvents.feed` в `adapters/muse_msp.py:33,168-205` на служебных MSP-событиях без `toolName` и из-за отсутствия `--disable-builtin-tools` в `MuseAdapter._build_serve_cmd` (`adapters/muse_adapter.py:572`). **Статус:** Подтверждено (`[F-22]`, `[F-23]`, `[F-29]`).

---

## 8. Риски, допущения и открытые вопросы

- Все открытые вопросы (`OPEN-01`, `OPEN-02` в `open-questions.md`) имеют класс `МОЖНО ПРОДОЛЖИТЬ`; блокирующих вопросов (`БЛОКИРУЕТ`) — `0`.
- Ключевой архитектурный риск при реализации: редактируемые файлы `server.py`, `adapters/passthrough_adapter.py`, `core/turn_session_manager.py`, `core/lifecycle.py`, `core/tool_emulation.py` и `adapters/muse_adapter.py` являются baseline-монолитами (`>300` строк на `BASE_COMMIT`), поэтому по инварианту `M-MOD-I2` для каждого из них обязательна кумулятивная дельта `added_lines - deleted_lines <= 0` с выносом новой чистой логики в отдельные компактные модули (`<= 300` строк).

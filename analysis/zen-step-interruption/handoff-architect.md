# Handoff to Architect: Устранение преждевременного обрывания многошаговых агентных цепочек в `opencode-zen-bridge` (v5)

## 1. Контекст и доказанная корневая причина (`[F-01]..[F-16]`)

В локальном мосте `bridges/opencode-zen-bridge/server.py` (обслуживающем `http://127.0.0.1:9883/v1` для DSH Desktop `[F-14]`, `[F-16]`) многошаговые агентные цепочки (`glm-5.3-flash-free` и др. модели с `emulate_tools=True`) обрываются посреди выполнения задачи с `finish_reason="stop"` и `tools=0` (`[F-10]`, `[F-11]`, `[F-12]`). Расследование по коду (`Zone A`), базе `opencode.db` (`Zone B`), журналу сессий DSH (`Zone C`) и логам моста (`Zone D`) выявило четыре взаимосвязанных механизма обрыва:

1. **Проглатывание тегов `<tool_call>` апстримом `opencode.ai/zen` (`[F-05]`, `[F-07]`, `[F-08]`, `[F-09]`):**
   Апстрим-провайдер `opencode.ai/zen` для семейства GLM (`glm-5.3-flash-free`) фильтрует/вырезает блоки `<tool_call>...</tool_call>` как служебные спец-токены (`[F-08]`: на промпте с `<tool_call>` возвращается `content=[]` при `tokens.output=75`, тогда как с нейтральным тегом `<tool_invoke>` возвращается валидный вызов `len(text)=283`). На Ходах 10 и 12 сессии `00e33abb-224c-4e4b-bd3d-6490f2bc9b87` модель сгенерировала короткую преамбулу намерения (`138` и `168` символов) и вызов инструмента (`non_reasoning_output = 350` и `133` токена), но блок `<tool_call>` был проглочен апстримом, а шаг закрылся с `finish="stop"` (`[F-07]`, `[F-09]`).
2. **Игнорирование `etype == "error"` (`ECONNRESET`) посреди стрима и склейка с синтетическим шагом `opencode run` (`[F-04]`, `[F-09]`, `[F-12]`):**
   На Ходе 11 (`14:11:56–14:12:27 MSK`) во время генерации произошёл обрыв соединения `ECONNRESET` (`[F-12]`). Исходный `server.py` при получении события `etype == "error"` не останавливал `proc` (`[F-04]`), из-за чего `opencode run` автоматически создал внутреннее синтетическое сообщение `"The previous response was interrupted..."`, на которое модель ответила текстом `"I was interrupted right before making tool calls..."` с `finish="stop"` без вызова тулов (`[F-09]`), а мост вернул этот склеенный текст клиенту как успешно завершённый ответ (`[F-03]`).
3. **Отсутствие детекции и ретрая оборванных инструментальных шагов в `Handler._stream_sse` и `Handler._serve_json` (`[F-01]`, `[F-02]`, `[F-03]`):**
   В исходном `server.py` ретрай при `emulate_tools=True` срабатывал только при `unmapped` нативных тулах (`NATIVE_RETRY_LIMIT = 2`) или при падении CLI с пустым выводом (`FAIL_RETRY_LIMIT = 3`) (`[F-03]`). Когда модель выдавала:
   - маркер прерванного ответа (`"I was interrupted right before making tool calls"`),
   - проглоченные токены (`non_reasoning_output - visible_est >= SWALLOWED_TOKENS_MIN`),
   - явный план вызова инструментов клиента в `reasoning` при короткой текстовой преамбуле без `tool_calls`,
   - или короткую статусную преамбулу намерения (`"Читаю вывод и проверяю состояние..."`, `"Собираю факты: ..."`),
   мост возвращал `finish_reason="stop"`, что приводило к немедленной записи `turn/end` в DSH (`[F-11]`).
4. **Блокирующее чтение `proc.stdout` без неблокирующей очереди с `maxsize` и SSE keepalive (`[F-06]`, `[F-15]`), а также отсутствие алиаса `"shell"` в `NATIVE_TOOL_ALIASES` (`[F-05]`):**
   В OpenCode v2.1.2 встроенный shell-инструмент называется `"shell"` (отсутствовал в `NATIVE_TOOL_ALIASES` `[F-05]`), а блокирующий цикл `for raw in proc.stdout:` не позволял отправлять `: keepalive\n\n` каждые `15s` и проверять дедлайн во время долгой фазы `thinking` (`[F-06]`).

## 2. Требования к архитектурному решению (`REQ-001..REQ-006`) с учётом замечаний Архитектурного Совета (`F1..F7`)

- **`REQ-001` (Двойная схема XML-тегов `<tool_invoke>` + `<tool_call>` и алиас `"shell"`):** В системной инструкции эмуляции инструментов требовать от модели тег `<tool_invoke>{"name": ..., "arguments": ...}</tool_invoke>` (не вырезаемый апстримом `opencode.ai/zen` `[F-08]`), а в `ToolCallParser` и `_parse_tool_call_blocks` поддерживать оба тега (`<tool_invoke>` и `<tool_call>`) для полной обратной совместимости (`[F-05]`, `[F-08]`). Добавить `"shell"` в `NATIVE_TOOL_ALIASES` (`[F-05]`).
- **`REQ-002` (Немедленная остановка `proc` при `etype == "error"`, классификация транзиентных ошибок и очистка маркеров обрыва):** В `Run._execute_once` и `Handler._stream_sse` при приходе `etype == "error"` немедленно останавливать дочерний процесс `_stop_proc(proc)`, чтобы не допускать запуска внутреннего синтетического шага `opencode run` (`[F-04]`, `[F-09]`), и вырезать строки `_INTERRUPTED_RE` из видимого текста. При этом выставлять `had_mid_stream_error = True` (разрешая ретрай) **только для транзиентных ошибок** (`_is_transient_stream_error(ev)`): когда `statusCode` отсутствует/`None`/`0`/`408`/`429`/`>= 500` или текст ошибки содержит транзиентный сетевой маркер (`econnreset`, `etimedout`, `timeout`, `timed out`, `socket hang up`, `interrupted`, `overloaded`, `rate limit`, `temporarily unavailable`, `fetch failed`, `network`), а для детерминированных клиентских/авторизационных ошибок `statusCode in (400, 401, 403, 404, 422)` НЕ ретраить (`had_mid_stream_error = False`) (`[F-12]`, закрытие `F5`).
- **`REQ-003` (Детектор оборванного инструментального шага `_is_incomplete_tool_step` с суженным признаком 5 и отдельным kill-switch `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY`):**
  - Ввести отдельный kill-switch `STEP_RECOVERY_ENABLED = os.environ.get("OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1").strip().lower() not in ("0", "false", "no", "off")` (независимый от `OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES`, закрытие `F4`). При `not STEP_RECOVERY_ENABLED` функция `_is_incomplete_tool_step` немедленно возвращает `False`.
  - Реализовать детерминированную функцию `_is_incomplete_tool_step(visible_text, reasoning_text, tool_names, had_mid_stream_error=False, output_tokens=0, reasoning_tokens=0) -> bool`, которая при `emulate_tools=True`, `STEP_RECOVERY_ENABLED=True` и отсутствии распознанных `tool_calls` определяет оборванный шаг по 5 признакам:
    1. `had_mid_stream_error=True` (только транзиентный `etype == "error"` или транзиентный сбой CLI);
    2. наличие маркера прерывания `_INTERRUPTED_RE` в `visible_text` или `reasoning_text`;
    3. **проглоченные токены (`swallowed_tokens`):** поскольку `tokens.output` в `opencode` включает `tokens.reasoning` (`[F-09]`), вычислять `non_reasoning_output = max(0, output_tokens - reasoning_tokens)` (если `reasoning_tokens > 0 and output_tokens >= reasoning_tokens`, иначе `output_tokens`), и при `len(stripped) <= 600` и `non_reasoning_output - max(1, len(stripped) // 3) >= SWALLOWED_TOKENS_MIN` (`35`) фиксировать проглоченный `<tool_call>`;
    4. явное упоминание имён клиентских инструментов (`tool_names`) и паттернов вызова (`_REASONING_TOOL_PLAN_RE`) в `reasoning_text` при коротком видимом ответе (`<= 600` символов);
    5. **узкая преамбула намерения (закрытие `F4`):** короткий текст (`<= 420` символов, до 6 строк, без финального вывода/таблицы/кода), который содержит **явный глагол намерения немедленного действия** (`_ACTION_INTENT_RE`: `"Читаю вывод..."`, `"Собираю факты..."`, `"Теперь посмотрим..."`, `"Let's check..."`, `"I'll run..."`) и при этом либо оканчивается на `:` / `...` / `…`, либо очень короток (`<= 220` символов). Голое двоеточие `:` в конце строки **без** `_ACTION_INTENT_RE` и без признаков 3/4 **не триггерит** ретрай (короткий финальный ответ `"Ответ: 42:"` или `"Итог проверки:"` возвращает `False`).
- **`REQ-004` (Единый потолок `A_max = 3` запусков на запрос, Full-Jitter backoff и безопасный fallback `dedup_prefix` в SSE/JSON):**
  - В `Handler._stream_sse` и `Handler._serve_json` ограничить **суммарное число запусков `opencode run` на один HTTP-запрос** константой `MAX_TOTAL_SPAWNS = 3` (`A_max = 3`: 1 первичный запуск + не более 2 повторных запусков суммарно по `fail_retries` и `attempt`) под единым `deadline = time.monotonic() + TIMEOUT_S` (закрытие `F3`).
  - Унифицировать паузу между повторными запусками через функцию `_retry_backoff_s(retry_num, rng_fn=random.uniform)` по формуле Full Jitter из `S-HERD-I2`: `rng_fn(0.0, min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** retry_num)))`, где `RETRY_BACKOFF_BASE_S = 0.5`, `RETRY_BACKOFF_CAP_S = 2.0` (закрытие `F3`).
  - В `Handler._stream_sse` при `attempt > 0`: если новый накопленный текст `current` начинается с `dedup_prefix`, подавлять уже отправленный префикс (`emitted_len = len(dedup_prefix)`). Если же `len(current) >= len(dedup_prefix)` и `not current.startswith(dedup_prefix)` (модель переформулировала начало на ретрае), **не терять текст**: сбрасывать `dedup_prefix = ""` и отправлять клиенту весь новый текст `current[emitted_len:]` (закрытие `F5`).
- **`REQ-005` (Ограниченный `_StdoutFeed` с `maxsize=4096` и SSE keepalive):** Заменить блокирующее чтение `for raw in proc.stdout:` на фоновый поток-читатель `_StdoutFeed` с ограниченной очередью `queue.Queue(maxsize=STDOUT_QUEUE_MAX)` (`STDOUT_QUEUE_MAX = 4096`). При переполнении очереди (`queue.Full`) выставлять флаг переполнения и останавливать процесс (`_stop_proc(proc)`), исключая неограниченный рост памяти (закрытие `F2`). Проверять дедлайн `TIMEOUT_S` каждые `0.25s` в `Run._execute_once` и отправлять `: keepalive\n\n` каждые `KEEPALIVE_INTERVAL_S = 15.0` секунд в `Handler._stream_sse` (`[F-06]`, `[F-15]`).
- **`REQ-006` (Сохранение публичных HTTP/OpenAI контрактов, `CD-002` и синхронизация репо с `~/.dsh`):** Внешний HTTP API (`/health`, `/v1/models`, `/v1/chat/completions`), порт `127.0.0.1:9883` и схема OpenAI остаются совместимыми (`[F-14]`, `[F-16]`). В `contract_deltas` явно зафиксировать `CD-002` (SSE `: keepalive` комментарии каждые `15s` и восстановление наблюдаемого `finish_reason` со сломанного `"stop"` на `"tool_calls"` при успешном ретрае), а в `VER-004` проверять побайтовое совпадение `bridges/opencode-zen-bridge/server.py` и `~/.dsh/bridges/opencode-zen-bridge/server.py` (закрытие `F6`, `F7`, `Seat 3 F2`).

## 3. Обязательный конверт `HL-ENV/v1` (46 канонических полей `REQUIRED_HL_ENV_FIELDS` + эксплуатационный профиль)

Ниже заданы все 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` из `aisdlc-gcge/agents/architecture.md` §3.0 в единицах СИ (секунды, байты, ядра, 1/с) и производные параметры:

```yaml
schema: HL-ENV/v1
required_hl_env_fields_46:
  P_steady: 1
  P_hpa_max: 1
  maxSurge_pct: 0.0
  maxSurge_abs: 0
  maxUnavailable_pct: 0.0
  maxUnavailable_abs: 0
  P_terminating_overlap: 0
  P_live: 1
  P_avail_min: 1
  W: 1
  N_proc: 1
  N_proc_steady: 1
  N_proc_avail_min: 1
  CPU_limit_per_pod: 2.0
  kappa_skew: 1.0
  u_bg_worker: 0.02
  U_pod_sidecars: 0.25
  Mem_limit_per_pod: 2147483648
  Mem_rss_worker_max: 67108864
  Mem_shared_max: 1207959552
  RPS_peak: 0.2
  A_max: 3
  SLA_p99_s: 180.0
  N_entities_max: 64
  Limit_dep_share_d: 6
  Limit_dep_rps_d: 2.0
  W_fetchers_d: 1
  J_init_s_d: 12.0
  J_pod_s_d: 12.0
  T_poll_s_d: 15.0
  K_calls_d: 1
  T_base_s_d: 0.5
  T_cap_s_d: 2.0
  Max_stale_age_s_c: 0.0
  Min_healthy_ratio: 1.0
  B_retry_max: 6
  min_reserve_retry_rps: 0.05
  FD_worker: 128
  ulimit_n: 4096
  lambda_new_conn_per_pod_s: 0.6
  C_active_in_scope_s: 12
  N_pods_in_scope_s: 1
  Port_range_size_s: 16383
  T_hold_s_s: 60.0
  SNAT_ips_count_s: 1
  HOTPATH_MODULES: "bridges/opencode-zen-bridge/server.py"
operational_profile:
  threads_per_worker: 12
  stdout_queue_max: 4096
  latency_p50_ms: 14000
  latency_p95_ms: 90000
  latency_p99_ms: 180000
  rps_sustained: 0.05
  rps_peak: 0.2
  concurrency_max: 6
  payload_p50_kb: 48
  payload_p99_kb: 480
  read_write_ratio: "10:90"
  session_ttl_sec: 1800
  availability_target: "99.5%"
  error_budget_window: "30d"
  cpu_request_m: 100
  cpu_limit_m: 2000
  mem_request_mb: 64
  mem_limit_mb: 2048
  workers_processes: 1
  db_pool_min: 0
  db_pool_max: 1
  conn_max_lifetime_sec: 1800
  network_bandwidth_mbps: 100
  connect_timeout_ms: 5000
  read_timeout_ms: 300000
  write_timeout_ms: 300000
  total_deadline_ms: 1800000
  max_retries: 2
  max_total_spawns: 3
  backoff_base_ms: 500
  backoff_max_ms: 2000
  jitter_mode: "full_jitter"
  retry_budget_pct: 20
  queue_max_depth: 4096
  rate_limit_rps: 2.0
  circuit_breaker_threshold: 3
  bulkhead_max_concurrent: 6
  startup_gate_sec: 12
  max_batch_size: 1
  max_response_size_mb: 16
  hot_dataset_gb: 1.8
  cache_ttl_sec: 0
  replication_lag_max_ms: 0
  graceful_shutdown_sec: 5
  keepalive_interval_sec: 15
  swallowed_tokens_min: 35
```

### Пояснение к замыканию памяти (`HL-ENV-01`) и потокам (`threads_per_worker`)
- **Память (`HL-ENV-01`):** `W = 1` (один Python-процесс `ThreadingHTTPServer`), `Mem_rss_worker_max = 67 108 864 B` (`64 MiB` — верхняя оценка RSS самого Python-процесса моста с очередями `_StdoutFeed` `maxsize=4096`), `Mem_shared_max = 1 207 959 552 B` (`1152 MiB` = до `MAX_CONCURRENT = 6` одновременных дочерних процессов `opencode run` по `192 MiB` RSS каждый), `Mem_limit_per_pod = 2 147 483 648 B` (`2048 MiB` — бюджет локального демона `com.user.dsh-opencode-zen-bridge` на рабочей станции macOS). Проверка инварианта `HL-ENV-01`:
  $$W \cdot \text{Mem\_rss\_worker\_max} + \text{Mem\_shared\_max} = 1 \times 64\text{ MiB} + 1152\text{ MiB} = 1216\text{ MiB} \le 0.80 \times 2048\text{ MiB} = 1638.4\text{ MiB} \quad (\text{PASS}).$$
- **Потоки (`threads_per_worker = 12`):** до `MAX_CONCURRENT = 6` потоков HTTP-хендлеров `ThreadingHTTPServer` + до `6` daemon-потоков `_StdoutFeed` (ровно 1 `_StdoutFeed` на активный `proc`, старый процесс завершается через `_stop_proc(proc)` до старта ретрая).

## 4. Семь гейтов отказоустойчивости (`HL-ENV/v1`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`) и 21 стоп-код

### 4.1. `C-MULT` (`C-MULT-I1..I5`) — Мультипликация коннектов, подпроцессов, портов и FD
- **`C-MULT-I1`:** Единственная зависимость моста — локальный CLI `opencode run` (обращающийся к `opencode.db` и `opencode.ai/zen`), `Limit_dep_share[opencode_cli] = 10` слотов на хосте. В мосте `N_proc = 1`, `G_reload = 1`, семафор `_slots = threading.Semaphore(MAX_CONCURRENT)` (`6`) удерживается на весь HTTP-запрос (ретраи выполняются внутри захваченного слота после `_stop_proc(proc)`): $1 \times 1 \times 6 = 6 \le 0.60 \times 10 = 6.0$ (`PASS`).
- **`C-MULT-I2`:** Очередь чтения stdout каждого дочернего процесса ограничена `queue.Queue(maxsize=STDOUT_QUEUE_MAX)` (`4096`), а входные HTTP-запросы ограничены семафором `_slots.acquire(timeout=TIMEOUT_S)` с отказом `HTTP 503 {"error": "slot timeout"}` (`PASS`).
- **`C-MULT-I3`:** Семафор `_slots` и `_STARTUP_LOCK` — синглтоны уровня процесса (`N_proc = 1`, `fork()` воркеров нет, а дочерний `subprocess.Popen` делает `execve("opencode")` с `close_fds=True` по умолчанию в Python 3) (`PASS`).
- **`C-MULT-I4`:** Освобождение `_slots.release()` и `_stop_proc(proc)` обёрнуты в `try ... finally:` как в `Handler.do_POST`, так и в `Run._execute_once` и `Handler._stream_sse` (`PASS`).
- **`C-MULT-I5`:** `FD_worker = 128 <= 0.70 * ulimit_n = 2867.2` (`ulimit_n = 4096`); эфемерные порты: $\lambda_{\text{new\_conn}} \cdot N_{\text{pods}} \cdot T_{\text{hold\_s}} + C_{\text{active}} = 0.6 \times 1 \times 60 + 12 = 48 \le 0.50 \times (1 \times 16383) = 8191.5$ (`PASS`).

### 4.2. `S-HERD` (`S-HERD-I1..I5`) — Защита от Thundering Herd и Full-Jitter Backoff
- **`S-HERD-I1`:** Первые `STARTUP_GATE_S = 12.0` с старта `opencode run` сериализуются через `_StartupGate` (`_STARTUP_LOCK`), причём слот освобождается сразу по первому событию `step_start`/`text`/`reasoning`/`tool_use` (`gate.release()`). Темп старта $\lambda_{\text{fetch}} = 1 / 12.0 = 0.0833\text{ с}^{-1}$, пачечная граница $1 \cdot (0.0833 + 4\sqrt{0.0833} + 4) = 5.24\text{ с}^{-1}$ при serial gate фактически не превышает $1$ одновременный холодный старт (`PASS`).
- **`S-HERD-I2`:** Пауза между ретраями вычисляется через `_retry_backoff_s(retry_num, rng_fn)` с Full Jitter `rng_fn(0.0, min(T_cap_s, T_base_s * (2 ** retry_num)))` (`T_base_s = 0.5`, `T_cap_s = 2.0`), детерминированно тестируемой с инъекцией `rng_fn` на точках `u in [0.0, 0.5, 1.0]` (`PASS`).
- **`S-HERD-I3`, `S-HERD-I4`, `S-HERD-I5`:** `N/A` с двойным доказательством: (а) `git diff` затрагивает только `bridges/opencode-zen-bridge/server.py` и `bridges/opencode-zen-bridge/tests/test_step_interruption.py`; (б) транзитивный граф вызовов `Handler.do_POST -> _stream_response/_complete_response -> _stream_sse/_serve_json -> Run.execute/_execute_once` не содержит фоновых поллеров Control Plane, `If-None-Match` кэшей, `singleflight`-кэшей и ротации секретов (`stateless HTTP-to-CLI bridge`).

### 4.3. `H-CPU` (`H-CPU-I1..I5`) — Отсутствие busy-wait, предкомпилированные регулярные выражения и бюджет CPU
- **`H-CPU-I1`:** `N/A` (двойное доказательство по `git diff` и графу вызовов: мост не хранит routing-индексы нод; маппинг тулов `canonical_map` и `allowed_map` — $O(1)$ `dict` на `<= 64` инструментов запроса).
- **`H-CPU-I2`:** Все регулярные выражения (`_TOOL_BLOCK_RE`, `_INTERRUPTED_RE`, `_ACTION_INTENT_RE`, `_REASONING_TOOL_PLAN_RE`, `_FINAL_CONCLUSION_RE`) компилируются **один раз при импорте модуля** на уровне `server.py`; внутри цикла обработки SSE-событий и `_is_incomplete_tool_step` вызовов `re.compile` и `copy.deepcopy` нет (`PASS`).
- **`H-CPU-I3`:** При `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0` (`STEP_RECOVERY_ENABLED = False`) `_is_incomplete_tool_step` возвращает `False` за $O(1)$ на первой инструкции (`Zero-Cost Disabled Path`); очередь `_StdoutFeed` использует `maxsize=4096` с немедленной остановкой процесса при `queue.Full` (`PASS`).
- **`H-CPU-I4`:** `N/A` (двойное доказательство: в `server.py` нет `asyncio` event loop и нет горячего reload `Snapshot`).
- **`H-CPU-I5`:** При `RPS_peak = 0.2`, `A_max = 3`, CPU-времени Python-моста на попытку `t_per_attempt_s = 0.05 с` и `t_per_req_s = 0.02 с`:
  $$\text{Util}_{\text{worker}} = 0.02 + 0.2 \times (0.02 + 3 \times 0.05) = 0.054 \le 0.70, \quad \text{CPU}_{\text{pod}} = 0.054 + 0.25 = 0.304 \le 0.80 \times 2.0 = 1.60 \quad (\text{PASS}).$$

### 4.4. `R-BULK` (`R-BULK-I1..I5`) и `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`
- **`R-BULK-I1`:** Сумма вспомогательных ожиданий и межатемптовых пауз по `A_max = 3` попыткам: $\sum_{a=1}^{3} (T_{\text{crit\_aux\_s}}(a) + T_{\text{wait\_s}}(a) + T_{\text{backoff\_s}}(a)) \le (12.0 + 0) + (12.0 + 1.0) + (12.0 + 2.0) = 39.0\text{ с} \le 0.30 \times 180.0 = 54.0\text{ с}$ (`SLA_p99_s = 180.0`), а при `time.monotonic() >= deadline` цикл немедленно прерывается (`PASS`).
- **`R-BULK-I2`:** Потолок запусков `MAX_TOTAL_SPAWNS = 3` (`A_max = 3`) и семафор `_slots = Semaphore(6)` жёстко ограничивают параллелизм и число ретраев (`PASS`).
- **`R-BULK-I3`:** Классификатор `_is_transient_stream_error(ev)` разделяет транзиентные сетевые сбои (`ECONNRESET`, `ETIMEDOUT`, `429`, `5xx` -> ретрай) и детерминированные ошибки (`400`, `401`, `403`, `404`, `422` -> немедленный Fail-Closed без ретрая) (`PASS`).
- **`R-BULK-I4`, `R-BULK-I5`, `M-SEM/v1`:** `N/A` с двойным доказательством (`git diff` + граф вызовов `server.py`: мост проксирует запросы в единственный локальный бинарник `OPENCODE_BIN` без пула прокси-нод и без мульти-тенантных пулов `crawler`/`llm`).
- **`T-LIFE/v1`:** Жизненный цикл каждого дочернего `proc` и его daemon-потока `_StdoutFeed` детерминированно закрывается вызовом `_stop_proc(proc)` (`SIGTERM` -> `SIGKILL`) в `finally:` перед любым следующим `attempt` или выходом из запроса (`PASS`).
- **`O-EXIT/v1`:** На каждом выходе из `Handler.do_POST` (включая `503 slot timeout`, `400 invalid json`, ошибку `opencode` и успешный ответ) в `bridge.log` записывается структурная строка с `mode` (`stream`/`json`), `model`, `rc`, `tools`, `out_chars`, `duration` (`PASS`).

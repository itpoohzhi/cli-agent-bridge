# Verdict C1 — Code Panel (Round 1)

- **Stage:** `council` (`code-panel`, Round 1)
- **Aggregate Verdict:** `ACCEPT` (3/3 unanimous `ACCEPT`, `FINDINGS: NONE`)
- **Panel Proof:** `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/analyst-teamlead-zen-step-20261024/panel/council/r1/panel-proof.json` (`sha256=40ccf7c6e24fd18c0ecd1f6c9e90e4b8f945cf9ebaf68a648ace93199f12d6e9`, `verify_panel_proof.py` `exit=0`)

## Seat 1 — Skeptic (`muse-wonder-full-1.0`, Meta, `muse`)
PANEL-NONCE: 1496e981c6adcf00
ARTIFACT-SHA256: 90b1d66499dceadac24f7990423b4c53b2ebd5b23247aaf50efe187851598b9e

Оценка с позиции Скептика (Adversarial / Failure Modes & High-Load Invariants) по пакету `v5` (`AD-001`–`AD-004`, `REQ-001`–`REQ-006`, `CD-001`–`CD-003`):

Проверены враждебные и граничные пути: классификация `_is_transient_stream_error` (детерминированные `400/401/403/404/422` — Fail-Closed без ретрая при любом тексте сообщения, `None/0/408/429/>=500` и сетевые маркеры — транзиентно, обе формы события — сырая и разобранная в `parse_opencode_event`); детектор `_detect_incomplete_tool_step_signal`/`_is_incomplete_tool_step` (kill-switch первой проверкой через `_step_recovery_disabled`, без касания regex при выключенном флоу; признак 3 с вычитанием `reasoning_tokens` и границей `34/35` и `600/601`; признак 5 только с `_ACTION_INTENT_RE`, голое `:` и финальные выводы/таблицы/код/`?` дают `0`, что закрывает `"Ответ: 42:"`; `_no_tools_overridden` не подавляет шаг при цитате `Rule 0` в начале `reasoning` при последующем плане вызовов, но сохраняет подавление при честном `no tools`; `tool_choice="none"` и пустой список инструментов дают `0` до принудительного `required`); немедленный `_stop_proc` на mid-stream `etype=="error"` только после полезного вывода (ошибка до первого токена процесс не убивает, флаг не «залипает» на восстановленном ответе) и вырезание `_INTERRUPTED_RE` из `text` и `reasoning` в обоих путях (`Run._execute_once`, `Handler._stream_sse`).

Проверены инварианты нагрузки: единый потолок `MAX_TOTAL_SPAWNS=3` через `_RequestAttempts` на всех комбинациях классов повтора (`cli_failure`/`unmapped`/`incomplete_step`, включая `locked_then_promise` и `unmapped_then_promise_forever` — ровно 3 запуска); Full-Jitter `_retry_backoff_s` с инъекцией `rng_fn` и обрезкой сна по остатку `deadline`; `_StdoutFeed(maxsize=4096)` с `put_nowait`, флагом `overflowed`, счётчиком `dropped_total`, остановкой процесса на `queue.Full` без молчаливого дропа, разблокировкой по дедлайну и keepalive при простое; `_SlotBulkhead` (13-й ждущий — мгновенный `overflow`/`503`, счётчики `in_use`/`waiters` возвращаются в `0` после таймаутов и исключений в ожидании, лишний `release` не уводит в минус); `_StartupGate(wait_s=5.0)` fail-open без освобождения чужого замка; `_SpawnRateLimiter(1.0/s)` с резервированием (10 одновременных резервов разнесены на 1 с, отказ при превышении `max_wait_s` токен не списывает); `_RetryBudget(capacity=6)` с границей на 100 падающих запросах; `_UpstreamBreaker` (`5` отказов → `OPEN`, cooldown `×U(0.8,1.2)`, в `HALF_OPEN` ровно 1 проба из 10 потоков, потерянная проба истекает, успех после ретрая через `attempt_done`/`commit` не засчитывается как отказ, детерминированные `4xx` в счётчик не входят); `dedup_prefix` (`_PrefixDedup`/`_dedup_retry_text`) при совпадении подавляет префикс, при несовпадении отдаёт полный текст без потерь в SSE и JSON; двойной тег `<tool_invoke>`/`<tool_call>` в потоковом `ToolCallParser` (разрыв между дельтами, пачки без промежуточных закрытий, закрывающий тег внутри JSON-строки, цитирование тега и fenced-код не являются вызовом) и в `_parse_tool_call_blocks`, алиас `"shell"` в `NATIVE_TOOL_ALIASES`; структурная строка `O-EXIT/v1` на всех выходах `do_POST` (`ok` stream/json, `400`, `401`, `503 circuit_open` без spawn, `503 slot_timeout`/`slot_overflow`). Остаточные риски (калибровка `SWALLOWED_TOKENS_MIN=35` вне GLM — `Q-001`, инженерная оценка RSS — `ASM-003`) зафиксированы в пакете как неблокирующие и не являются дефектами реализации; обход Retry Budget для локального отказа старта CLI без обращения к провайдеру (`charge_budget=False`, `database is locked`) ограничен `FAIL_RETRY_LIMIT`, `MAX_TOTAL_SPAWNS` и темпом spawn и не нагружает апстрим, поэтому инвариант `R-BULK-I2` для провайдерских повторов не нарушает.

Критических блокеров, нарушений Failure Modes или High-Load инвариантов относительно утверждённого пакета `v5` не обнаружено; заявленные верификации (`441` тест моста, `177` тестов `test_step_interruption.py` включая `VER-005` и `HlResilienceOracles`, `VER-004 diff -u exit=0`) согласуются с кодом артефакта.

FINDINGS: NONE
VERDICT: ACCEPT


---

## Seat 2 — Realist (`claude-sonnet-5-5-high`, Anthropic, `claude-p`)
PANEL-NONCE: c9b8ad4a5c52dc86
ARTIFACT-SHA256: 90b1d66499dceadac24f7990423b4c53b2ebd5b23247aaf50efe187851598b9e

# Совет Тимлидов по коду, r1, Seat 2: Реалист

Оценка сделана по встроенным артефактам. Прогоны `uvx pytest`, `unittest` и `diff -u` я не повторял и опираюсь на заявленные в брифе результаты (441 тест моста, 177 тестов `test_step_interruption.py`, VER-004 `exit=0`).

## Соответствие пакету v5

| Решение | Что в коде | Оценка |
|---|---|---|
| AD-001 / REQ-001 | Парсер и `_parse_tool_call_blocks` принимают `<tool_invoke>` и `<tool_call>`. Алиас `shell` добавлен. GLM получает протокол на `<tool_invoke>` через `_tool_tags_for_model` и `_rewrite_tool_tags_for_model`. | Соответствует. Минимальные правки по месту. |
| AD-002 / REQ-002 / REQ-003 | `_is_transient_stream_error` не ретраит 400/401/403/404/422. `_stop_proc` вызывается на mid-stream `error` только после первого вывода, ранняя ошибка не убивает процесс. Признак 5 сужен до `_ACTION_INTENT_RE`. Есть вычитание `reasoning_tokens`, `_no_tools_overridden` и отдельный kill-switch `STEP_RECOVERY`. | Соответствует. Ложные срабатывания закрыты тестами (`"Ответ: 42:"`, граница 34/35 токенов). |
| AD-003 / REQ-004 / REQ-005 | `_StdoutFeed(maxsize=4096)` с остановкой процесса на `queue.Full`. `MAX_TOTAL_SPAWNS=3` проверяется в `allow_retry` и `begin_attempt` для обоих путей. Full-Jitter через `_retry_backoff_s`. `_PrefixDedup` и `_dedup_retry_text` не теряют текст при переформулировке. | Соответствует. Потолок перебран по всем комбинациям классов повтора. |
| AD-004 / CD-003 | `_SlotBulkhead` (6 слотов, 12 ждущих, 15 с). `_StartupGate` с fail-open. `_SpawnRateLimiter` на GCRA. `_RetryBudget`. `_UpstreamBreaker` с одной пробой в HALF_OPEN. | Соответствует. Зависимости инъектируются, оракулы детерминированы на `FakeClock`. |
| O-EXIT/v1 | `do_POST` обёрнут в `try/finally` и пишет `_log_exit` на всех выходах. | Соответствует. |

По фактической посадке в кодовую базу всё в порядке:
- Новые функции чистые и без I/O, а старые имена оставлены как алиасы (`_PROMISE_RE`, `_slots`).
- Внешний HTTP-контракт, порт и эндпоинты не тронуты.
- Состояние защит вынесено в `_Resilience`, так что тестовые `Server` изолированы, а `main` берёт модульный набор.

## Замечания, не блокирующие приёмку

1. **Keepalive отличается от CD-002.** Пакет описывает комментарий `: keepalive\n\n`. Код шлёт парсируемый чанк `{"content": ""}`, и тест проверяет именно его. Это сознательное и более надёжное для клиентских watchdog'ов решение, но оно расходится с текстом контрактной дельты. В итоговом отчёте или KB его стоит зафиксировать как принятое отклонение.
2. **Таймаут `get` в стриме.** Пакет называет 1.0 с для `_stream_sse`, код везде использует 0.25 с. Это строже по дедлайну и безвредно.
3. **Один общий `_UpstreamBreaker` на все модели.** Серия 429 на free-tier Zen (анонимный лимит по IP, он указан в комментариях кода) откроет breaker и на 8–12 с даст 503 и Go-моделям. Эффект самоизлечивается и укладывается в AD-004, поэтому для приёмки это наблюдение, а не дефект. Если проявится в бою, breaker можно разнести по провайдерам.
4. **Лишний backoff при повторе из HALF_OPEN.** `allow_retry` списывает токен бюджета и спит backoff, а затем `breaker.allow()` отказывает, потому что проба уже занята. Выходит холостая пауза и потраченный токен. Это некритично, потому что ответ клиенту не меняется.
5. **Очистка процессов по client-gone.** На выходе по client-gone финальные `finally` в `_stream_sse` и `Run.close` делают `proc.kill()`, а не `killpg`. Заявление T-LIFE про `killpg` на всех путях верно для `_stop_proc`-путей и чуть сильнее реальности для этого выхода. Паттерн унаследован из исходного кода.
6. **Объём изменений.** Для моста с пиком 0.2 RPS на одной машине набор защит (bulkhead, breaker, budget, token bucket) избыточен. Он утверждён Архитектурным Советом (AD-004), код ему следует, тесты на каждую защиту есть. Для Реалиста это приемлемая, хотя и верхняя граница сложности.

## Итог

Реализация соответствует утверждённому пакету v5 и минимально достаточна для его целей. Ложные срабатывания детектора закрыты, потолок запусков (3) проверен перебором, ожидания ограничены. Тестовое покрытие пропорционально риску. Блокеров нет.

FINDINGS: NONE
VERDICT: ACCEPT


---

## Seat 3 — Visionary (`grok-4.7-high`, xAI, `cursor-agent`)
PANEL-NONCE: 578bcebed148bfc8
ARTIFACT-SHA256: 90b1d66499dceadac24f7990423b4c53b2ebd5b23247aaf50efe187851598b9e
Канон прочитан: AGENTS.md, 430 строк. Проектные AGENTS.md, .agents/AGENTS.md и CLAUDE.md в этом ходе не читались.

Приёмка с места Визионера: реализация `v5` в `bridges/opencode-zen-bridge/server.py` держит утверждённые контракты, границы и путь эволюции. SHA-256 файла на диске совпадает с хешем брифа.

**Контракты.** CD-001 соблюдён: для GLM протокол в промпте идёт на `<tool_invoke>`, `ToolCallParser` и `_parse_tool_call_blocks` принимают оба тега, история переписывается до отправки, алиас `shell` есть в `NATIVE_TOOL_ALIASES`. Внешний ответ клиенту остаётся OpenAI `tool_calls`. CD-002(б) соблюдён: успешный дозапрос заканчивается `finish_reason=tool_calls`. CD-003 соблюдён: слот ждёт не дольше 15 с, 13-й ожидающий получает мгновенный 503 `overloaded` (`bridge busy` / `slot_overflow`), открытый breaker отвечает 503 `upstream circuit open` без spawn. Порт, `/health`, `/v1/models`, `/v1/chat/completions` не менялись.

Носитель keepalive (CD-002(а)) — пустая content-дельта раз в 15 с, а не SSE-комментарий `: keepalive`. Пустая дельта — штатный чанк OpenAI, к видимому тексту ничего не добавляет и как раз сбрасывает watchdog клиента, ради которого дельта и введена. Схема чанка, эндпоинты и смысл «поток жив, пока stdout молчит» сохраняются. Это не разрыв внешнего контракта.

**Целостность решений.** AD-001…AD-004 сходятся с кодом. Детектор выключен первой проверкой `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY` и не трогает regex; 400/401/403/404/422 не ретраятся; mid-stream error сразу вызывает `_stop_proc`; `reasoning_tokens` вычитаются из output. Потолок `MAX_TOTAL_SPAWNS=3` общий для cli-failure, unmapped и incomplete step. Full Jitter: retry 1 → U(0, 1.0), retry 2 → U(0, 2.0). Несовпадение `dedup_prefix` отдаёт новый текст целиком и в SSE, и в JSON. `_StdoutFeed(maxsize=4096)` на `queue.Full` останавливает процесс. `_StartupGate` 5 с — fail-open. Token bucket 1.0/с не списывает токен, если ожидание длиннее бюджета. Retry budget 6 / +0.20 / +0.05. Breaker: 5 отказов, cooldown U(0.8, 1.2)×10 с, в HALF_OPEN одна проба. Парсер и детектор не зависят от proc и сокета; транспорт вызывает их, обратной зависимости нет.

Две более узкие формулы не ломают утверждённые числовые последствия. Оценка видимых токенов — `max(len//2, оценка по словам)`: для текста 168 символов и non-reasoning 133 остаётся 49 ≥ 35; для 138 символов и 350 — 281 ≥ 35. «Ответ: 42:» и «Итог проверки:» дают сигнал 0. Короткая преамбула без `:`/`...`/`…` дополнительно требует имя инструмента запроса; признак 5 по-прежнему требует глагол намерения.

**Эволюция и наблюдаемость.** Откат детектора — env `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0` без выключения unmapped-ретрая; миграций данных нет; константы переопределяются env. `do_POST` в `finally` пишет одну строку `O-EXIT/v1` с `mode`, `model`, `status`, `exit_reason`, `rc`, `total_spawns`, `retries`, `signal`, `tools`, `out_chars`, `duration_s`. Поле `signal` закрывает отложенную наблюдаемость детектора. Выходы, названные в O-EXIT/v1 (401, 400, 404, 503 слота и breaker, 502, успех stream/json, timeout, client_gone), размечены и покрыты тестами. Успешный запрос после транзиентного обрыва не открывает breaker.

FINDINGS: NONE
VERDICT: ACCEPT

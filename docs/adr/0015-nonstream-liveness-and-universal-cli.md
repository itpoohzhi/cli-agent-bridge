# ADR-0015: Живость non-stream запросов и универсальный CLI-раннер

- Статус: Approved
- Дата: 2026-11-05
- Run: `run-20261105-nonstream`
- Требования: REQ-01, REQ-02, REQ-03, REQ-04
- Базовая ревизия: `1d8e96cc14fa9dcd912a71587abe8dcf16923677`

## Контекст

Passthrough-ветка `stream=false` читает ответ целиком под статическим дедлайном и не получает сигналы живости. Для длинного активного ответа это создаёт ложный таймаут, хотя SSE-ветка уже умеет сдвигать окно неактивности при полезных чанках. CLI-ветка отдельно считает рост CPU и новых потомков прогрессом, но доверяет этим сигналам без суммарного бюджета.

Passthrough-запрос создаётся до `ManagedTurn`, поэтому активный ход не виден в `GET /v1/turns/<id>`. В конфигурации и пользовательских сообщениях также смешаны универсальные параметры моста и имена Droid. Вендорские протоколы, JSON-RPC методы `droid.*`, persisted-имена, `DROID_BIN`, `DROID_AUTO`, `DROID_SKIP_PREFLIGHT`, `FACTORY_API_KEY`, поле ошибки `type=droid_error` и значение `/health.transport=droid-exec` являются совместимыми контрактами и не переименовываются.

Решение должно быть агент-агностическим, располагаться в общем слое `core/`, не изменять семь ключей `/health`, сохранять прежнее поведение при выключенных флагах и не увеличивать ни один существующий продуктовый файл более 300 строк. Замороженный baseline находится в `architecture/baseline-monoliths.json`.

## Драйверы

1. REQ-01: `stream=false` должен переживать длинную активную генерацию и возвращать один OpenAI-compatible `chat.completion`.
2. REQ-02: полезный прогресс, мягкая процессная живость и transport heartbeat должны иметь разные семантики.
3. REQ-03: оператор должен видеть живость активного CLI- или passthrough-хода через существующий endpoint turns.
4. REQ-04: универсальный слой не должен зависеть от имени конкретного CLI-вендора.
5. Все runtime-параметры конфигурируются через ENV, а новые изменения поведения закрываются GigaRC-флагами с default `false`.
6. M-MOD-I2: для `server.py`, `adapters/passthrough_adapter.py`, `core/watchdog.py` и `core/turn_session_manager.py` накопительная дельта строк по каждому файлу не больше нуля.

## AD-001 — Внутренний SSE для внешнего `stream=false` (REQ-01)

### Решение

При `BRIDGE_NONSTREAM_VIA_STREAM_ENABLED=true` `PassthroughAdapter` копирует JSON-тело запроса с внешним `stream=false`, меняет только внутреннее поле на `stream=true` и читает upstream существующим SSE-читателем. При выключенном флаге байты запроса и текущая non-stream ветка остаются без изменений.

Новый `core/nonstream_aggregator.py` собирает SSE-чанки в один `chat.completion`. Классификация S/T ему не принадлежит: он принимает результат единственного классификатора `core/liveness_signals.py` и отдельно валидирует wire-протокол.

- `id`, `created`, `model` и `system_fingerprint` берутся из первого непустого значения и проверяются на совместимость последующих чанков;
- `choices` собираются независимо по целочисленному `choice.index` и выдаются в возрастающем порядке индекса; `n > 1` поддерживается;
- `role`, `content`, `reasoning_content` и `finish_reason` принадлежат конкретному `choice.index`: первое непустое `role` сохраняется, конфликтующее значение является ошибкой 502, текстовые поля конкатенируются дословно в порядке прихода, последнее непустое `finish_reason` сохраняется;
- существующие `\n\n` между шагами сохраняются, агрегатор не вставляет и не удаляет разделители;
- `tool_calls` объединяются по паре `(choice.index, tool_call.index)`; `id`, `type` и `function.name` берутся из первого непустого совместимого значения, конфликт даёт 502, а `function.arguments` конкатенируется по порядку чанков;
- `usage` берётся из последнего чанка, где оно присутствует;
- неизвестные delta-поля не переносятся в итоговый `chat.completion`; этот допустимый drop проверяется fixture-тестом, а известные OpenAI-compatible поля выше терять запрещено;
- `[DONE]` обязателен для любого 200 OK и сам в ответ не попадает; EOF или upstream error до `[DONE]`, `[DONE]` без хотя бы одного S, отсутствие `finish_reason` хотя бы у одной собранной choice, конфликт metadata и malformed JSON дают 502 без partial response;
- только истечение first/idle/safety deadline даёт 504; получение terminal chunk перед deadline не разрешает 200 до `[DONE]`;
- `max_body_bytes` независимо ограничивает число сырых SSE-байтов и размер агрегированного JSON; превышение любого лимита даёт 502 до публикации ответа.

`stream_options.include_usage` не добавляется автоматически: запрос клиента сохраняется, а отсутствие usage допустимо. Если upstream прислал usage, оно сохраняется.

Модуль ограничен 250 физическими строками. Каждая новая или изменённая функция ограничена 40 строками, 5 параметрами и цикломатической сложностью 10.

### Альтернативы

1. Оставить статический non-stream read — не выполняет REQ-01.
2. Реализовать второй SSE parser в адаптере — дублирует протокол и помещает общую логику в vendor-facing слой.
3. Всегда принудительно включать внутренний stream — нарушает обратную совместимость и не даёт kill switch.

### Последствия

Upstream увидит `stream=true` только при включённом флаге. Клиент по-прежнему не получает байты до завершения агрегирования, поэтому его собственный socket timeout остаётся внешним ограничением. Память ограничена существующим `max_body_bytes` passthrough, по умолчанию 16 MiB.

## AD-002 — Классификатор S/P/T и конфигурируемые окна (REQ-02)

### Решение

Новый `core/liveness_signals.py` — единственный владелец классификации S/P/T, монотонных окон, soft budget и общего immutable value object `@dataclass(frozen=True) LivenessSnapshot`. Он не знает имён агентов или backend kind, кроме факта наличия process group. `LivenessWindow` защищает state и создание snapshot приватным `threading.Lock`; signal update, timeout transition и snapshot атомарны относительно друг друга.

Порядок классификации фиксирован и не дублируется в aggregator, adapter или watchdog:

- SSE-комментарии, отсутствующее или пустое `data`, а также trimmed `data: ping`, `data: keepalive` и `data: [DONE]` классифицируются как **T** до попытки JSON parsing;
- JSON `{}`, `[]`, `null`, role-only, usage-only и finish_reason-only классифицируется как **T**; непарсящийся JSON также T для liveness и отдельно становится wire-error 502 в aggregator;
- JSON с непустым `content`, `reasoning_content`, `reasoning`, `reasoning_text`, `tool_calls` или `function_call` классифицируется как **S**; S полностью сдвигает idle deadline и обнуляет soft budget P;
- **P** возникает только из process sampler: прирост CPU не меньше `BRIDGE_NONSTREAM_SOFT_LIVENESS_MIN_CPU_DELTA_S` или новый потомок process group;
- любое событие, не удовлетворившее S/P, остаётся **T**. T обновляет только возраст транспорта и никогда не сдвигает first/idle deadline.

State machine разделяет ход до и после первого S:

1. **Passthrough до первого S:** `first_or_idle_deadline = started_at + BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S` (default 90). P неприменим, T deadline не меняет.
2. **CLI до первого S:** `first_or_idle_deadline = started_at + BRIDGE_CLI_FIRST_TOKEN_TIMEOUT_S` (default 90). P не переводит state в post-S, но при включённом soft-liveness может продлевать ожидание лишь в пределах общего бюджета 120 секунд.
3. **После первого S:** `first_or_idle_deadline = now + idle_timeout_s`; следующий S снова выставляет sliding idle и сбрасывает `accrued_p_s = 0`. P допустим только для CLI и расходует новый budget; T ничего не сдвигает.
4. **Во всех состояниях:** `safety_cap_deadline = started_at + safety_cap_s` абсолютен и никогда не сдвигается.

Для принятого P `dt = max(0, now - last_accepted_p_at)`, `remaining_budget_s = max(0, budget_s - accrued_p_s)`, затем строго выполняется:

```text
accrued_p_s += min(dt, remaining_budget_s)
remaining_budget_s = max(0, budget_s - accrued_p_s)
deadline = min(
    safety_cap_deadline,
    max(first_or_idle_deadline, now + min(idle_timeout_s, remaining_budget_s)),
)
```

Одинаковый timestamp даёт `dt=0`; частые P не могут начислить больше фактически прошедшего времени, один P не может потратить больше остатка, после исчерпания P только отражается в telemetry. При `BRIDGE_NONSTREAM_SOFT_LIVENESS_ENABLED=false` CLI сохраняет прежнее безлимитное доверие P. Passthrough никогда не принимает P.

Поведенческие флаги `BRIDGE_NONSTREAM_VIA_STREAM_ENABLED`, `BRIDGE_NONSTREAM_SOFT_LIVENESS_ENABLED`, `BRIDGE_NONSTREAM_TELEMETRY_ENABLED` и `BRIDGE_CLI_NEUTRAL_NAMES_ENABLED` читаются на каждом решающем переходе через существующий динамический GigaRC `_flag_source` с env fallback и default `false`. Их выключение действует без рестарта. Все числовые лимиты и alias cascade строятся один раз в composition root, валидируются fail-fast при старте и после этого immutable; изменение чисел требует рестарта.

### Полный реестр BRIDGE_NONSTREAM_*

Таблица исчерпывающая для AD-001/AD-002/AD-003: wildcard-алиасов нет, `—` означает отсутствие legacy alias. Для каждой строки первое непустое значение в указанном порядке побеждает; пустое значение уступает alias/default, два непустых значения разрешаются по порядку таблицы. Все значения non-sensitive; флаги читаются динамически, числа fail-fast при старте.

| Canonical ENV | Legacy aliases по приоритету | Default | Тип / допустимый диапазон | Назначение |
|---|---|---:|---|---|
| `BRIDGE_NONSTREAM_VIA_STREAM_ENABLED` | — | `false` | bool | GigaRC-флаг AD-001 |
| `BRIDGE_NONSTREAM_FIRST_PROGRESS_TIMEOUT_S` | — | `90` | float `[1,3600]` | первый S passthrough |
| `BRIDGE_NONSTREAM_IDLE_TIMEOUT_S` | `BRIDGE_IDLE_TIMEOUT_S` | `300` | float `[1,3600]` | окно после S |
| `BRIDGE_NONSTREAM_SOFT_LIVENESS_ENABLED` | — | `false` | bool | GigaRC-флаг bounded P |
| `BRIDGE_NONSTREAM_SOFT_LIVENESS_BUDGET_S` | — | `120` | float `[0,3600]` | суммарное доверие P между S |
| `BRIDGE_NONSTREAM_SOFT_LIVENESS_MIN_CPU_DELTA_S` | — | `0.05` | float `(0,60]` | минимальный CPU delta для P |
| `BRIDGE_NONSTREAM_SAFETY_CAP_S` | — | `3600` | float `[1,86400]` | абсолютный потолок internal stream |
| `BRIDGE_NONSTREAM_POLL_INTERVAL_S` | `BRIDGE_PASSTHROUGH_POLL_INTERVAL_S` | `0.1` | float `[0.01,10]` | частота опроса passthrough |
| `BRIDGE_NONSTREAM_TELEMETRY_ENABLED` | — | `false` | bool | GigaRC-флаг AD-003 |

### Параметры BRIDGE_WATCHDOG_*

Константы `core/watchdog.py` становятся ENV-настройками с прежними defaults. Пустое значение уступает alias/default; значения non-sensitive и валидируются fail-fast при старте.

| Canonical ENV | Legacy aliases по приоритету | Default | Тип / допустимый диапазон |
|---|---|---:|---|
| `BRIDGE_WATCHDOG_IDLE_TIMEOUT_S` | — | `300` | float `[1,3600]` |
| `BRIDGE_WATCHDOG_SAFETY_CAP_S` | `DROID_DSH_BRIDGE_SAFETY_CAP_S` | `3600` | float `[1,86400]` |
| `BRIDGE_WATCHDOG_FINISH_RESERVE_S` | — | `35` | float `[0,600]` |
| `BRIDGE_WATCHDOG_INTERVAL_S` | — | `5` | float `[0.1,60]` |
| `BRIDGE_WATCHDOG_PS_TIMEOUT_S` | — | `2` | float `[0.1,60]` |

Парсинг, валидация диапазонов и immutable config (`WatchdogConfig`, `NonstreamConfig`) выносятся из `core/watchdog.py` в `core/cli_runtime_config.py`; `core/watchdog.py` не вызывает `from_env()` при импорте — конфиг читается лениво в `__init__` контроллера. Невалидное ENV-значение завершается fail-fast при старте с нейтральным именем параметра; секреты и значения окружения в лог не выводятся.

**Контракт fail-fast (F-003).** Любое невалидное число (нечисло, `inf`/`nan`, вне диапазона, переполнение) в каноническом или fallback-имени параметра — `ConfigError`: `start.sh` завершается кодом 78, `server.parse_live_write_timeout()` ведёт себя так же, как `CLI_CFG.live_write_timeout_s` (тихого возврата к default нет). Мягкий разбор (`positive_int`/`positive_float`/`bounded_int`) сохранён только для прежних параметров passthrough-лимитов.

**Единый классификатор (F-016).** Активность CLI классифицирует только `classify_cli_activity(kind)` в `core/liveness_signals.py`: смысловой вывод — S, `start`/`done`/`protocol`/`keepalive`/`heartbeat` — T; `ManagedTurn.touch_activity` передаёт фактический тип события.

### Альтернативы

1. Считать любой входной байт прогрессом — heartbeat способен бесконечно скрывать зависание.
2. Убрать P целиком — ухудшает совместимость CLI, который долго думает без токенов.
3. Оставить P без бюджета — сохраняет ложную живость процесса с редким CPU tick.

### Последствия

Default-флаги сохраняют прежнее поведение. После включения soft-liveness редкий CPU progress больше не продлевает ход бесконечно: до первого S CLI завершается по bounded first-token deadline, после S — по bounded sliding idle; safety cap остаётся последним предохранителем.

## AD-003 — Per-turn телеметрия и реестр passthrough (REQ-03)

### Решение

Под `BRIDGE_NONSTREAM_TELEMETRY_ENABLED=true` `GET /v1/turns/<id>` добавляет необязательный объект `liveness`. Значение `SNAPSHOT_SCHEMA_VERSION=1.0`, существующие 18 ключей snapshot, коды 400/403/404 и все семь ключей `/health` сохраняются.

`liveness` содержит:

| Поле | Семантика |
|---|---|
| `internal_stream` | используется ли AD-001 |
| `stream_requested` | исходное значение stream клиента |
| `last_token_age_s` | возраст последнего content S |
| `last_reasoning_age_s` | возраст последнего reasoning S |
| `last_progress_kind` | `S`, `P` или `none`; T сюда не попадает |
| `last_keepalive_age_s` | возраст последнего T |
| `process_alive` | состояние PGID для CLI, `null` для passthrough |
| `soft_budget_used_s` | использованный бюджет P, `null` для passthrough |
| `soft_budget_limit_s` | лимит P, `null` для passthrough |
| `idle_remaining_s` | остаток скользящего окна |
| `safety_cap_remaining_s` | остаток абсолютного потолка |

Новый `core/liveness_registry.py` — единственный владелец mutable map только активных passthrough-ходов. Он хранит ID, `owner_token_hash`, числовые timestamps и метки; request/response body, prompt, исходные токены и секреты не сохраняются. Приватный `threading.Lock` защищает `register/update/finish/get_snapshot`; lookup с owner check, timeout transition и snapshot атомарны. Наружу возвращается общий frozen `LivenessSnapshot` из `core/liveness_signals.py`, а не mutable entry.

Passthrough ID, запись registry и заголовок `X-Turn-Id` создаются **только** когда динамический `BRIDGE_NONSTREAM_TELEMETRY_ENABLED=true`. При `false` нет ID, заголовка, map entry или live lookup: default-false wire behavior побайтово прежний. При `true` `_serve_passthrough` до вызова adapter создаёт ID, совместимый с `TURN_ID_RE`, регистрирует entry и удаляет его в `finally`; после cleanup lookup даёт прежний 404. `GET /v1/turns/<id>` по-прежнему доступен только при detached-mode и сначала запрашивает `TurnSessionManager`, затем live registry.

Для CLI и passthrough применяется один owner contract: берётся непустой `X-Turn-Owner-Token`, иначе токен `Authorization` (Bearer prefix снимается), после чего вызывается тот же `hash_owner_token`; наружу raw token/hash не возвращается. Несовпадение использует существующую неразличимую семантику 403/404 и не раскрывает наличие чужого turn.

CLI не входит в `LivenessRegistry`: `core/watchdog.py` строит общий frozen `LivenessSnapshot` и передаёт его через явный `ManagedTurn.update_liveness(snapshot)`; `ManagedTurn` владеет своим `_liveness_snapshot` под приватным `threading.Lock`. `TurnSessionManager` лишь включает immutable public projection в optional `liveness`, не знает passthrough map и сохраняет прежние 18 snapshot keys.

### Альтернативы

1. Создавать полный `ManagedTurn` для passthrough — смешивает HTTP proxy lifecycle с CLI session persistence.
2. Хранить телеметрию только в `PassthroughAdapter` — endpoint server не получает единый owner-aware lookup.
3. Добавить поля в `/health` — ломает замороженный контракт из семи ключей.

### Последствия

В памяти появляется ограниченная числом активных запросов map. Утечки предотвращаются обязательным `finally`; тест fault injection проверяет удаление записи при success, upstream error, timeout и client disconnect.

## AD-004 — Универсальные имена CLI-раннера (REQ-04)

### Решение

Новый компактный `core/cli_runtime_config.py` централизует чтение универсальных имён и нейтральное форматирование видимых сообщений. Разрешены только точные aliases из таблицы ниже: canonical имеет приоритет, пустое значение уступает следующему alias/default, конфликт двух непустых значений решается первым по таблице. Числа строятся и fail-fast валидируются при старте; флаг neutral names читается динамически. Все параметры non-sensitive, значения ENV в диагностике не печатаются.

| Canonical ENV | Legacy aliases по приоритету | Default | Тип / допустимый диапазон |
|---|---|---:|---|
| `BRIDGE_CLI_FIRST_TOKEN_TIMEOUT_S` | `DROID_BRIDGE_FIRST_TOKEN_TIMEOUT_S` | `90` | float `[1,3600]` |
| `BRIDGE_CLI_LIVE_WRITE_TIMEOUT_S` | `DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S` | `30` | float `[1,300]` |
| `BRIDGE_CLI_SILENCE_WATCHDOG_S` | `DROID_BRIDGE_SILENCE_WATCHDOG_S` | `120` | float `[1,3600]` |
| `BRIDGE_CLI_RPC_CALL_TIMEOUT_S` | `DROID_BRIDGE_RPC_CALL_TIMEOUT_S` | `60` | float `[1,3600]` |
| `BRIDGE_CLI_IDLE_SECONDS` | `DROID_DSH_BRIDGE_IDLE_SECONDS` | `2700` | float `[1,86400]` |
| `BRIDGE_CLI_LAUNCHER` | `DROID_BIN` | текущая launcher policy | непустая executable string |
| `BRIDGE_CLI_MAX_RPC_LINE_BYTES` | `DROID_BRIDGE_MAX_RPC_LINE_BYTES` | `8388608` | int `[1024,268435456]` |
| `BRIDGE_CLI_MAX_STDERR_BYTES` | `DROID_BRIDGE_MAX_STDERR_BYTES` | `65536` | int `[1024,16777216]` |
| `BRIDGE_CLI_MAX_INBOX_BYTES` | `DROID_BRIDGE_MAX_INBOX_BYTES` | `4194304` | int `[1024,268435456]` |
| `BRIDGE_CLI_MAX_TURN_TEXT_BYTES` | `DROID_BRIDGE_MAX_TURN_TEXT_BYTES` | `10485760` | int `[1024,1073741824]` |
| `BRIDGE_CLI_RUN_QUEUE_MAXSIZE` | `DROID_BRIDGE_RUN_QUEUE_MAXSIZE` | `1024` | int `[1,65536]` |
| `BRIDGE_CLI_MAX_JSON_STRUCT_TOKENS` | `DROID_BRIDGE_MAX_JSON_STRUCT_TOKENS` | `50000` | int `[1,10000000]` |
| `BRIDGE_CLI_MAX_DELIVERY_BYTES` | `DROID_BRIDGE_MAX_DELIVERY_BYTES` | `268435456` | int `[1048576,4294967296]` |
| `BRIDGE_CLI_MAX_CHATS` | `DROID_BRIDGE_MAX_CHATS` | `4096` | int `[1,65536]` |
| `BRIDGE_CLI_NEUTRAL_NAMES_ENABLED` | — | `false` | bool, dynamic GigaRC flag |

Под `BRIDGE_CLI_NEUTRAL_NAMES_ENABLED=true` пользовательские message/log/id prefix используют `CLI`, `cli-exec`, `chatcmpl-cli-` и `cli-agent-bridge`. При default `false` сохраняются текущие строки и `chatcmpl-droid-`.

Не меняются:

- `kind=droid`, `RPC_NAMESPACE=droid-bridge/v1`, JSON-RPC `droid.*`;
- `DROID_BIN`, `DROID_AUTO`, `DROID_SKIP_PREFLIGHT`, `FACTORY_API_KEY`;
- `droid-binary-receipt.json`, `runtime/droid-image`, persisted `droid_real`;
- error field `type=droid_error`;
- `/health.transport=droid-exec` и семь ключей `/health`.

В baseline `server.py:981` уже присутствует deny-префикс `DROID_`, поэтому он закрывает все `DROID_BRIDGE_*` и `DROID_DSH_BRIDGE_*`, включая `DROID_DSH_BRIDGE_SAFETY_CAP_S`. В `DENIED_FORWARD_PREFIXES` дополнительно добавляются `BRIDGE_CLI_`, `BRIDGE_NONSTREAM_`, `BRIDGE_WATCHDOG_`; вместе эти четыре семейства закрывают canonical и legacy aliases до передачи `extra_body.env` потомку. Существующие deny entries не удаляются.

### Альтернативы

1. Массово переименовать все `droid` — ломает вендорский и persisted contracts.
2. Оставить универсальные настройки под DROID-префиксом — сохраняет vendor coupling.
3. Переименовать только тексты — не решает конфигурационный контракт и env injection.

### Последствия

Появляется совместимый alias layer. Видимые строки меняются только после отдельного включения флага; сохранённые состояния и vendor transport остаются читаемыми.

## Границы модулей и ownership

| Модуль | Ответственность | Запрещено |
|---|---|---|
| `core/nonstream_aggregator.py` | OpenAI SSE chunk aggregation и bounded result; internal `stream=true` тело, дедлайны/сокет non-stream | HTTP handler, backend-name branches, process sampling |
| `core/liveness_signals.py` | единственная S/P/T policy, monotonic windows, soft budget, frozen `LivenessSnapshot`, `SseProgress` (учёт S/T SSE-кадров; legacy-семантика `last_progress` без флагов), окно passthrough | registry map, vendor RPC, HTTP, процессы |
| `core/liveness_registry.py` | owner-aware map только active passthrough turns и выдача immutable snapshot | CLI state, request/response bodies, disk persistence, subprocess control |
| `core/cli_runtime_config.py` | ENV cascade и neutral display labels | vendor protocol translation, turn state |
| `adapters/passthrough_adapter.py` | HTTP lifecycle и вызов общих core API | собственная агрегация и liveness policy |
| `core/watchdog.py` | sampling процесса и orchestration timeout controller | hardcoded runtime constants, собственная классификация бюджета |
| `core/turn_session_manager.py` | CLI turn lifecycle и persistence прежних snapshot keys | passthrough registry ownership |
| `server.py` | routing, auth/owner checks и композиция фасадов | реализация aggregator, registry или signal policy |

Mutable state имеет одного владельца:

- `NonstreamAggregator._choices` — только `NonstreamAggregator`;
- `LivenessWindow._state` — только `LivenessWindow`;
- `LivenessRegistry._entries` — только `LivenessRegistry`;
- `ManagedTurn._liveness_snapshot` — только `ManagedTurn`;
- `CliRuntimeConfig` immutable после построения.

## План декомпозиции M-MOD-I2

Замороженные файлы не могут расти: для каждого из четырёх файлов отдельно `added_lines - deleted_lines <= 0` относительно base revision. Удаление комментариев ради формального баланса запрещено; дельта достигается извлечением существующей логики.

| Existing file | Что извлекается | Что остаётся | Требование дельты |
|---|---|---|---|
| `adapters/passthrough_adapter.py` | chunk accumulation, S/T classification и internal-stream state в новые core-модули | HTTP connect/read/write и фасад вызова до 5 строк | `<=0`; aggregator <=250 строк |
| `core/watchdog.py` | ENV parsing, P budget и liveness snapshot в `liveness_signals.py` | process sampling и делегирование policy фасадом до 5 строк | `<=0` |
| `core/turn_session_manager.py` | повторяющийся wire mapping в общий frozen snapshot helper `liveness_signals.py` | CLI turn ownership, turn persistence и прежние 18 snapshot keys | `<=0` |
| `server.py` | CLI env cascade/labels и active passthrough lookup в новые core-модули | route wiring, owner check и фасады до 5 строк | `<=0` |

Все новые `core/*.py` не больше 300 физических строк; `core/nonstream_aggregator.py` не больше 250. Новые/изменённые функции: не больше 40 строк, 5 параметров, cyclomatic complexity не больше 10. Новая логика не маскируется удалением документации.

## Волны реализации

Каждая карточка Coder меняет не больше двух продуктовых файлов. Карточки с повторным файлом идут строго по `depends_on`, поэтому одновременных писателей нет.

1. **Wave 0 — expected red:** W0-A `tests/test_passthrough_adapter.py` + `tests/test_openai_passthrough.py`; W0-B `tests/test_adaptive_idle_watchdog.py` + `tests/test_stream_timeout_config.py`; W0-C `tests/test_detached_turn_execution.py` + `tests/test_dsh_env_forwarding.py`; W0-D `tests/test_launch_env.py` + `tests/test_agy_bridge_resilience.py`; W0-E `tests/test_stream_formatting_and_subagents.py`. Harness возвращает 0 только когда зафиксирован именно ожидаемый red-контракт.
2. **Wave 1 — pure policy/FSM:** W1-A создаёт `core/liveness_signals.py` и одновременно подключает policy в `core/watchdog.py`; W1-B после W1-A создаёт `core/nonstream_aggregator.py` и его chunk-boundary contracts. Таким образом classifier существует до любой интеграции с passthrough.
3. **Wave 2 — transport wiring:** W2-A (`core/nonstream_aggregator.py`, `adapters/passthrough_adapter.py`) подключает internal SSE, first/idle/safety windows; W2-B после W2-A (`adapters/passthrough_adapter.py`, `core/liveness_registry.py`) подключает telemetry updates и finally cleanup; W2-C (`core/watchdog.py`, `core/turn_session_manager.py`) проводит frozen snapshot по пути watchdog → `ManagedTurn`; W2-D после W2-B/W2-C (`core/liveness_registry.py`, `server.py`) подключает conditional ID/header, owner lookup и optional wire projection.
4. **Wave 3 — universal CLI, adversarial QA и cleanup:** W3-A (`core/cli_runtime_config.py`, `start.sh`) реализует точный alias registry; W3-B после W2-D/W3-A (`server.py`, `tests/test_dsh_env_forwarding.py`) добавляет новые canonical deny prefixes и проверяет покрытие существующим `DROID_`; W3-C (`tests/test_stream_formatting_and_subagents.py`, `tests/test_agy_bridge_resilience.py`) подтверждает L2 invariants и полный fault matrix. После каждой карточки — локальный oracle и M-MOD gate, затем общий `pytest tests/ -v`.

## Контрактная совместимость

- При всех четырёх флагах `false` поведение, error types, request bytes и display names остаются прежними.
- `liveness` — optional additive object без повышения snapshot schema version.
- `X-Turn-Id`, passthrough registry entry и lookup появляются только при `BRIDGE_NONSTREAM_TELEMETRY_ENABLED=true`; при false их нет.
- Legacy aliases перечислены исчерпывающе в таблицах; отсутствие alias обозначено `—`, removal legacy names в этой задаче запрещён.
- `/health` остаётся объектом ровно из семи ключей.
- Vendor JSON-RPC и persisted state не меняются.

## Rollout и rollback

1. Доставить код со всеми флагами `false`.
2. Включить telemetry на ограниченном окружении и проверить bounded registry/finally cleanup.
3. Включить internal stream для одной passthrough модели; сравнить latency, timeout, usage и размер ответа.
4. Включить soft-liveness budget для одного CLI backend и наблюдать timeout reason.
5. Включать neutral names последним после проверки потребителей логов и ID prefix.

Rollback поведения выполняется мгновенным выключением соответствующего динамического GigaRC-флага через существующий `_flag_source` без рестарта. Изменение числовых ENV требует рестарта и проходит стартовый fail-fast validator. Новые ENV aliases можно оставить: при прежних defaults они инертны. Схема данных и миграции отсутствуют.

## Риски и меры

1. **Usage расходится с non-stream:** не форсировать `include_usage`, покрыть вариант с usage и без него.
2. **Память агрегатора:** применять `max_body_bytes`, ошибка до публикации partial response.
3. **Heartbeat маскирует зависание:** T не сдвигает ни first-progress, ни idle deadline.
4. **CPU tick маскирует зависание:** P ограничен soft budget при включённом флаге.
5. **Registry leak:** `finally` cleanup на success/error/timeout/disconnect и тест на нулевой остаток.
6. **Env injection:** deny три новых canonical-префикса и уже существующий `DROID_` до передачи extra_body.env потомку.
7. **Потребитель парсит vendor text:** neutral names default false, vendor error type сохранён.
8. **Нарушение монолитного budget:** per-file numstat gate и line/function/complexity gate после каждой wave.

## Verification surface

Минимальный замороженный набор после реализации:

```bash
pytest tests/test_agy_bridge_resilience.py -v
pytest tests/test_stream_formatting_and_subagents.py -v
pytest tests/ -v
python3 scripts/smoke_models.py --dry-run
```

`VER-009` выполняется одной `python3`/`ast` командой: вычисляет все новые относительно base revision `core/*.py`, проверяет каждый на `<=300` строк, `core/nonstream_aggregator.py` на `<=250`, `start.sh` на `<=300`, а каждую функцию/метод в новых модулях — на `<=40` строк, `<=5` параметров и cyclomatic complexity `<=10`. Дополнительный новый core-модуль автоматически входит в scope; отсутствие любого из четырёх запланированных модулей является ошибкой.

Дополнительно deterministic checks подтверждают:

- regression red на base revision и green на candidate;
- whole/1-byte/7-byte/seed chunk-boundary invariance агрегатора;
- S сдвигает окно, P расходует budget, T не сдвигает окно;
- `/health` имеет ровно прежние семь ключей;
- error `type` и vendor RPC identifiers не изменились;
- three denied prefixes нельзя прокинуть через `extra_body.env`;
- per-file net line delta четырёх baseline-монолитов `<=0`;
- новые модули и функции проходят лимиты строк, параметров и сложности;
- live L3 выполняется только с замаскированными токенами после dry-run.

## Отложено

- Изменение `/health.transport`, vendor RPC и persisted Droid identifiers.
- Backend-specific timeout overrides в `fleet.json`.
- Удаление legacy ENV aliases.
- Публикация proposal в `docs/adr/` до ARCH_GATE и materialization exact bytes.

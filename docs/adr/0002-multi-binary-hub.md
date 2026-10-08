# 0002 — Многобинарный хаб `cli-agent-bridge`: единый фасад :9882 и адаптеры `BackendAdapter`

## Status

Accepted (2026-10-08). Формат: ADR-full — решение затрагивает публичную поверхность (один порт, каталог моделей),
модель безопасности (несколько дочерних бинарников, trust boundary), персистентные данные (`fleet.json`, записи чатов)
и откатывается не одним действием. Решение владельца по AD-007 принято 2026-10-08 12:07 MSK: Muse работает с
`--yolo --trust-workspace`, изоляция добирается компенсаторами (см. «Обновления после ревью Совета Тимлидов»).
Поставка P2 — только с `backends.muse.enabled=false`. Включение Muse (`enabled:true`, P3) требует лога живой пробы
на `meta` через обёртку и совместной нагрузки с Droid (ASM-001), с согласованием владельца, либо явной записи решения
владельца, снимающей P3-гейт. AD-007 разрешает флаги, но не снимает этот гейт. ASM-001 в этом контуре
**НЕ ПРОВЕРЕНО**; fake/echo и тесты его не заменяют. Не отменяет ADR 0001: его инварианты (L → P → T, receipt-допуск образа, изоляция ходов,
байтовые бюджеты) наследуются `DroidAdapter` без изменений.

### Обновления после ревью Совета Тимлидов (Cycle 1, 2026-10-08)

Ниже зафиксированы уточнения Cycle 1, а не итоговый вердикт Cycle 2. Свидетельства тестов относятся к `0cecaf0`;
замечания RW-001…RW-012 из Cycle 2 проверяются отдельно. Остальной текст содержит исходное предложение,
не обещание, что каждый архитектурный набросок уже реализован.

1. **Muse `max_concurrent` = 1** (было 2): параллельные muse-ходы разведены per-turn каталогом
   `workspace/muse/turn-<uuid>/`, но оба процесса идут под одним UID с `--yolo`, поэтому ёмкость 1 — реальная граница
   изоляции ходов; per-turn каталог и его prompt-файл удаляются в `finally` (RW-001).
2. **`--yolo --trust-workspace` сохранены** (решение владельца); вместо смены флагов — компенсаторы: sha256-pin сверяется
   с фактически запускаемым путём, `MUSE_BIN` вырезается из окружения ребёнка, неполный pin = отказ хода (RW-002).
3. **Автоматический replay промпта убран**: повторный ход при network-маркере не выполняется — ход мог уже исполнить
   native shell/write (RW-003). **Успех требует `terminal.completed`**; `delta + EOF + rc=0` без терминала — 502
   `backend_error` (RW-004).
4. **Схема 3 валидируется одним кодом** (`core/backend_adapter.py: backend_entry_error`) и в `server._build_backends`,
   и в `fleet_check.py`: вложенные типы `technical_ref`, `wrapper`, диапазон `proxy_port`, `max_concurrent ≥ 1`,
   неизвестные ключи — отказ до регистрации адаптера (RW-005).
5. **Байтовые бюджеты покрывают ошибки и failure reasons** (`MAX_LINE_BYTES`/`MAX_TURN_TEXT_BYTES`), сырой backend-текст
   не попадает в журнал — только класс ошибки/rc/байты (RW-006, RW-007).
6. **`_chat_known` — только резидентные сессии**: ключ существующего droid-чата не открывает muse-ход в обход `unsafe`
   (RW-008). Завершение группы muse ограничено по времени, потомки добиваются `killpg` до освобождения слота (RW-009).
7. **`_sweep_workspace` метёт наследие muse** (`muse/prompt-*.txt`, `muse/turn-*`), на остановке — безусловно;
   `children.json` тегируется `kind: muse` и `reconcile_children` на старте добивает свои осиротевшие группы (RW-010).
8. **`MUSE_PROXY_PORT` нормализуется один раз** и уходит и в preflight, и в окружение обёртки (RW-011);
   basedpyright по хабу в `0cecaf0` — без ошибок в новых модулях; сравнение с настоящим baseline `be95d60`
   требует отдельного commit-bound лога (исправление атрибуции: RW-011 Cycle 2).
9. **Фасадный шов покрыт интеграционными тестами** через настоящий HTTP-handler с fake droid/muse в `BACKENDS`
   (`tests/test_hub_integration.py`): JSON/SSE, `tool_calls`, 502 `backend_error` с detail, 503 preflight,
   `finalize_turn` (`emulate_tools` true/false), unsafe-guard, независимость ёмкостей, abort потока (RW-013).

## Y-формулировка

В контексте моста DSH → консольные AI-бинарники, сталкиваясь с требованием подключать **произвольное число разнородных
бинарников одновременно** (сейчас `droid` на :9882 и Muse CLI на :9886, дальше — любые) за **одним** OpenAI-совместимым
фасадом, мы решили держать один процесс-хаб с единым HTTP-портом :9882 и **in-tree реестром адаптеров** `BackendAdapter`
(связка `model → backend` в `fleet.json` schema 3) вместо отдельного моста на каждый бинарник и вместо вынесения адаптеров
в отдельные процессы, чтобы получить один клиентский контракт, один кэш сессий, одну эмуляцию tools и один охранник
промптов, принимая более слабую, чем у процесс-на-бинарник, изоляцию сбоев и необходимость строго ограничить поверхность
загрузки адаптеров и права дочерних бинарников.

## Context

Факты о текущей системе (все — с доказательствами в Architecture Packet, `EVD-*`):

- `server.py` — монолит ≈ 5 200 строк (stdlib, `ThreadingHTTPServer`, один процесс). Всё droid-специфичное (RPC-процессы,
  `ProcPool` cap 4, `ChatRegistry`, receipt, образы, autonomy) живёт в нём; внешний контракт заморожен ADR 0001 и
  `tests/baseline_inventory.json`: пути, Bearer-авторизация, `/health` ровно из 7 ключей, таксономия 400/502/503/504 (без 507).
- `fleet.json` — **schema_version 2**; загрузчик `_build_catalog` отказывает на любом другом значении (`schema_version_invalid`,
  rc=1) и **молча отбрасывает неизвестные ключи** — значит, добавление `backends` без смены версии привело бы к тому, что старый
  код тихо опубликовал бы модель Muse как droid-модель. `fleet_check.py` проверяет то же `!= 2`.
- `muse-bridge` (:9886, `~/.dsh/bridges/muse-bridge/server.py`, 1155 строк) — отдельный мост: один запрос = один headless-ход
  `muse-cli.sh exec …`, без сессий (`--no-session-log`), `usage` оценивается по словам, transport-стратегия «MSP `serve` первым,
  `exec` как fallback», эффорт-маппинг **мягкий** (неизвестное → `max`), SSE — эмуляция из готового текста, **`--yolo`**
  (отключены approval и sandbox, workspace доверенный). `ToolCallParser`/рендер tools — **копия** кода моста droid.
- Muse CLI: установлен `1.4.3` (README моста говорит 1.4.2 — дрейф), sha256 образа `c6db2947…a4bc`. `muse exec --help` показывает
  безопасные флаги (`--disable-shell`, `--disable-write`, `--disable-web-tools`, `--approval-mode`, `--permission-profile`);
  проба на провайдере `echo` принимает их (rc=0). На провайдере `meta` поведение без `--yolo` **не проверено** (лимиты Meta).
- Политика моделей (`~/Мой диск/Context/models.md`, стр. 321): `muse-spark-1.3`, effort **`max`** во всех ролях; `ultra` откатывается
  в `xhigh` (runtime-gate), канон — `max`; вызов — только через обёртку `~/.config/muse-launch/muse-cli.sh` (прокси :10816,
  `unset META_API_KEY`, exit 42 при DOWN прокси).

## Requirements (из задачи)

MB-REQ-001 интерфейс `BackendAdapter` (`get_models`, `execute_turn`, `spawn_session`, `is_healthy`, `qualify`) · 002 `DroidAdapter` без
регрессии · 003 `MuseAdapter` (`muse-spark-1.3`, effort `max`, через `muse-cli.sh`) · 004 `fleet.json`: `backends` и `model → backend` ·
005 единый фасад :9882 (`/v1/chat/completions`, `/v1/models`) · 006 единый кэш сессий · 007 общая tool-эмуляция · 008 общий `b_guard` ·
009 произвольное число бэкендов одновременно.

## Decision drivers

1. Один клиентский контракт: DSH видит один порт, один ключ, один `/v1/models`; baseline-тесты не краснеют.
2. Расширяемость: новый бинарник = новый адаптер + запись в `fleet.json`, без правки HTTP-обработчика (устранить копипаст
   `ToolCallParser`).
3. Безопасность: несколько бинарников с разным уровнем доверия; конфиг не загружает код; наименьшие права дочерних бинарников.
4. Изоляция и ресурсы: падение/насыщение одного бэкенда не ломает другой; per-backend ёмкость; ADR 0001 L → P → T сохранён.
5. Стоимость миграции: не переписывать 5 000 строк инвариантов ADR 0001; откат по шагам.

## Considered options

- **Option A — мост на каждый бинарник (status quo).** Отдельный порт/ключ/процесс/каталог; DSH знает N провайдеров.
- **Option B — хаб в одном процессе + in-tree адаптеры.** Один фасад; адаптеры — модули репозитория, реестр `kind → класс` в коде.
- **Option C — хаб + адаптеры отдельными процессами.** Хаб говорит с адаптерами по локальному HTTP/JSON-RPC; адаптеры подключаются как плагины.

## Decision

Выбрана **Option B**. Для C оставлен путь расширения: `BackendAdapter` — узкий контракт, поэтому out-of-process адаптер позже
реализуется как `RemoteAdapter` (прокси над IPC) без изменения фасада; триггер пересмотра — первый бинарник с недоверенным кодом,
другим рантаймом либо требованием жёсткой изоляции.

### Evaluation matrix

> **Веса критериев зафиксированы 2026-10-08 ДО оценки опций.**

| Критерий | Вес | A | B | C |
|---|---|---|---|---|
| Единый фасад и клиентский контракт (:9882) | 0.25 | 1 | 5 | 5 |
| Изоляция сбоев и безопасность | 0.20 | 5 | 3 | 5 |
| Простота эксплуатации (процессы, порты, ключи) | 0.15 | 2 | 4 | 2 |
| Расширяемость (N бинарников) | 0.20 | 2 | 4 | 5 |
| Совместимость и стоимость миграции (ADR 0001) | 0.20 | 5 | 3 | 1 |
| **Итого (взвешенно)** | | 2.95 | **3.85** | 3.75 |

Шкала: 1 = плохо, 5 = отлично.

### Sensitivity check

Каждый вес по очереди ×0.8 и ×1.2 с перенормировкой (10 пересчётов): победитель всегда B (B 3.79–3.90; C 3.64–3.86; A 2.86–3.05).
**Отрыв B от C тонкий**: минимум 0.02 при весе «изоляция» +20 % (3.82 против 3.80). Вывод: B устойчиво, но не с запасом; ключевая
чувствительность — вес изоляции. Поэтому изоляция добирается компенсаторами (AD-006, AD-007: per-backend ёмкость, отсутствие
межбэкендного fallback, qualify-гейт, наименьшие права), а при росте требований к изоляции ADR пересматривается в сторону C.

## Архитектура

### Container (VIEW-001)

```
 DSH / клиенты ──HTTP :9882 (Bearer)──▶  cli-agent-bridge (один процесс, stdlib)
                                          ├─ Facade: auth · framing · admission · model→backend · effort · prompt_guard (b_guard)
                                          │          · tool_emulation (render + ToolCallParser) · SSE/JSON · usage
                                          ├─ SessionCache (ChatRegistry): key_hash → binding(backend, model) · record schema 1
                                          ├─ BackendRegistry: kind → Adapter класс (в коде) ; fleet.json → экземпляры
                                          │     ├─ DroidAdapter ─▶ droid exec --input-format stream-jsonrpc (резидент на чат, ≤4)
                                          │     ├─ MuseAdapter  ─▶ ~/.config/muse-launch/muse-cli.sh exec (на ход, ≤1)
                                          │     └─ <будущий>Adapter ─▶ другой консольный бинарник
                                          └─ ChildRegistry (children.json, backend-тег) · shutdown_all
 muse-cli.sh ─▶ прокси 127.0.0.1:10816 ─▶ api.meta.ai   (egress вне хаба)
```

### Component: seam `BackendAdapter` (VIEW-002)

Межмодульный контракт определён в `core/backend_adapter.py`; фасад также использует общий `core/tool_emulation.py`.
Конкретные адаптеры не импортируют `server`.
**Следующий блок — неисполняемый архитектурный набросок (sketch), а не готовый интерфейс реализации.**
Сигнатуры `execute_turn(turn, session, sink, cancel)`, `qualify() -> Qualification`, `is_healthy() -> Health`
и допуск через `ADAPTER_API` не служат инструкцией регистрации адаптера.
Набросок сохранён как история предложения; типизированный seam реализован в RW-012 Cycle 2
(актуальный интерфейс ниже). Фактический контракт берётся из `core/backend_adapter.py`
и проверяется `tests/test_backend_contract.py`, а не из этого sketch.
Нормализованные типы в наброске — dataclass/TypedDict:

<!-- fmt: off -->

```python
ADAPTER_API = 1  # версия контракта; qualify() адаптера обязан её подтверждать

class Capabilities(TypedDict):
    sessions: Literal["resident", "none"]      # droid: resident (load_session/SID); muse: none
    streaming: Literal["native", "emulated"]   # emulated → фасад режет готовый текст SSE-чанками
    autonomy: bool                              # droid: True; muse: False (поле игнорируется, журнал)
    images: bool                                # по fleet.json models[].images; проверка доказательств — фасад (как сейчас)
    usage: Literal["exact", "estimated"]
    reasoning_summaries: bool                   # muse(serve): True → поле ответа reasoning_summaries
    native_tools: Literal["none"]               # хаб: нативные tools бинарника отключены/ограничены; tools — только эмуляция

class BackendAdapter(Protocol):
    id: str                                     # backends[].id
    capabilities: Capabilities
    def get_models(self) -> list[ModelSpec]: ...        # чистая функция конфигурации, без spawn, O(1)
    def qualify(self) -> Qualification: ...             # допуск образа: sha/версия/протокол/политика прав/пробы; кэш + пере-qualify
    def is_healthy(self) -> Health: ...                 # дёшево, не спаунит, <50 мс; ok|degraded|down + причина-slug
    def spawn_session(self, spec: SessionSpec) -> SessionHandle: ...  # sessions="none" → NotSupported
    def execute_turn(self, turn: TurnRequest, session: SessionHandle | None,
                     sink: EventSink, cancel: CancelToken) -> TurnResult: ...
    def close_session(self, session: SessionHandle, mode: Literal["term", "kill"]) -> None: ...
    def shutdown(self, grace_s: float) -> None: ...
```

<!-- fmt: on -->

Пять контрактов из задачи — `get_models/execute_turn/spawn_session/is_healthy/qualify`; `close_session` и `shutdown` — обязательное
дополнение (без них нельзя удовлетворить SIGTERM-инвариант ADR 0001 и отдачу слотов при смене бэкенда в чате).
В реализации `capabilities` — только `sessions`, `streaming`, `autonomy`, `usage`; остальные поля наброска
(`images`, `reasoning_summaries`, `native_tools`) не понадобились: картинки и native tools остаются фасадными проверками.

- **`EventSink`** — существующий интерфейс очереди `Run`: события `text`, `reasoning`, `result`, `stream_error`, `pump_error`, `done`.
  Адаптер только публикует; ToolCallParser, SSE, ретраи фасада не знают про бинарник.
- **`TurnRequest`**: `model`, `effort`, `autonomy`, `messages` (OpenAI), `system`, `tools_section` (уже отрендерен общим модулем),
  `work_dir`, `images`, `chat_key_hash | None`, `deadline`. Рендер истории адаптер делает общими функциями `tool_emulation`.
- **Ошибки (`BackendError`)** отображаются на существующую таксономию без новых кодов: `BackendUnavailable` → 503
  `launcher_unavailable`; `BackendProtocolError`/пустой ответ → 502 `proxy_error`; `BackendTimeout` → 504; `ModelMismatch` →
  502; перегрузка ёмкости → 503 `overloaded`.
- **Версионирование исходного sketch:** предполагался отказ `qualify()` при несовпадении `ADAPTER_API`.
  Описания `EventSink`/`TurnRequest` выше относятся к предложению, не к текущим DTO.
  Реализация теперь отказывает раньше, при регистрации, как описано далее.

#### Актуальный интерфейс (RW-012 Cycle 2)

`core/backend_adapter.py` определяет frozen dataclass `TurnContext`, `TurnResult`,
`BackendModel`, `Capabilities` (это фактическое имя, не `AdapterCapabilities`) и связанные
DTO `Transcript`/`TranscriptItem`, `ImageAttachment`, `Usage`, `ToolCall`/`ToolFunction`/`TurnEvent`.
`Qualification` — typed NamedTuple `(ok, reason)`. Текущие сигнатуры:

- `get_models() -> list[BackendModel]`, `qualify() -> Qualification`, `is_healthy() -> bool`;
- `spawn_session(ctx: TurnContext) -> object`, `execute_turn(ctx: TurnContext, sse_writer: StreamSink | None) -> TurnResult`;
- `close_session(sid: str) -> None`, `shutdown() -> None`.

`Capabilities` содержит только `sessions`, `streaming`, `autonomy`, `usage`.
`AdapterRegistry.register` проверяет `adapter_api == ADAPTER_API`, тип и допустимые значения
возможностей, bind `execute_turn` на два аргумента, точные аннотации `ctx`/return
(`TurnContext`/`TurnResult`) и return `qualify` (`Qualification`), уникальность backend id.
Невалидный адаптер получает `ValueError` до попадания в реестр. Это не проверка всех
runtime-возвратов и сигнатур каждого метода. Legacy dict-преобразование Droid ограничено
`DroidAdapter`; HTTP dict-кодирование остаётся локальным в фасаде.
`core.tool_emulation.finalize_turn(TurnResult, emulate_tools) -> TurnResult` сохраняет
готовые события Droid либо разбирает текст другого адаптера в типизированные события/tool calls.

### Адаптеры

**DroidAdapter** (MB-REQ-002). Фаза 1 — тонкая оболочка над существующими `Run`/`RpcProcess`/`ProcPool`/`_make_plan`/receipt
(класс остаётся в `server.py`; вынос внутренностей в `backends/droid_*.py` — отдельная будущая фаза, не цель этого ADR: 228 КБ
инвариантов и ~20 тестовых модулей привязаны к `server.*`). `qualify()` = текущий receipt (sha + протокол + tools_policy +
settings_profile + пробы, `tools/droid_image.py`); `is_healthy()` = `_receipt_state()`; `sessions="resident"`; `spawn_session` =
`initialize_session` + PENDING→READY по ADR 0001. Поведение для моделей droid **байт-в-байт прежнее**.

**MuseAdapter** (MB-REQ-003, `adapters/muse_adapter.py`, порт из muse-bridge). Модель `muse-spark-1.3`, `efforts=["max"]`,
`default_effort="max"`. Транспорт: `muse-cli.sh exec … --json --no-session-log --prompt-file` — один ход = один headless-запуск
(в реализации `serve` не используется; автоматического replay при network-маркере нет, RW-003).
`sessions="none"`: каждый ход — полный replay истории в промпте (как сейчас), запись чата в кэше не создаётся (путь `ephemeral`).
`usage`: оценка по словам ×1.3 (`exec` точных токенов не отдаёт). Дети — лидеры своих групп (`start_new_session`),
регистрируются в `ChildRegistry`, `kill` группы по `TIMEOUT_S`. `qualify()`: (1) `muse-cli.sh` исполняем; (2) образ `~/.local/bin/muse`
совпал по sha256 с `fleet.json technical_ref`; поле версии справочное, не отдельная runtime-проба.
Путь обязан быть каноническим `~/.local/bin/muse` (иначе `binary_path_not_canonical`).
Допуск повторяется после получения слота непосредственно перед spawn, без sha-кэша;
неизменяемый образ не создаётся, окно подмены между проверкой и exec остаётся.
Pin обязателен, без него ход не запускается; (3) прокси :10816 слушает
(иначе `is_healthy`=down, причина `proxy_down`, exit 42 → 503). Пункты исходного sketch о пробе `echo` и
`model-profile show` — не подтверждённые шаги runtime `qualify()`; `echo` не заменяет живой ASM-001.
Политика прав — AD-007.

### fleet.json schema 3 (MB-REQ-004)

```json
{ "schema_version": 3, "catalogue": "droid-bridge-fleet", "default_model": "claude-sonnet-5-5",
  "backends": {
    "droid": {"kind": "droid", "enabled": true, "required": true, "owned_by": "factory-droid", "max_concurrent": 4},
    "muse": {"kind": "muse", "enabled": false, "required": false, "owned_by": "meta-muse", "max_concurrent": 1,
             "wrapper": "~/.config/muse-launch/muse-cli.sh",
             "technical_ref": {"version": "1.4.3", "binary_sha256": "c6db2947…a4bc", "binary_path": "~/.local/bin/muse"}} },
  "models": [ {"id": "claude-sonnet-5-5", "backend": "droid", "…": "как в schema 2 (всего 6 droid-моделей)"},
              {"id": "muse-spark-1.3", "backend": "muse", "efforts": ["max"], "default_effort": "max",
               "context_window": 1048576, "max_tokens": 131072, "input": ["text"],
               "images": {"cli_registry": "implicit_supported", "status": "unverified", "method": null, "proof": null},
               "policy_lines": [321]},
              {"id": "muse-spark-1.3-contributor", "backend": "muse", "…": "как muse-spark-1.3"} ] }
```

`backends` — объект `id → запись` (не список). Допустимые ключи записи (единственный источник —
`core/backend_adapter.py: BACKEND_KEYS`): `kind`, `enabled`, `required`, `owned_by`, `max_concurrent`,
`wrapper`, `technical_ref`, `proxy_port`. `transport` и `tool_policy` не поддерживаются:
они исключены из allowlist и отвергаются с `backend_key_unknown`, а не игнорируются.
`technical_ref` — справочная `version` +
`binary_path` + `binary_sha256` (64 hex, обязательны для `kind: muse`).

Пример отражает P2: Muse выключен, его модели остаются определениями каталога, но не публикуются и не маршрутизируются.
Для разрешённых запросов модель должна ссылаться на включённый backend; `default_model` не может принадлежать выключенному.

Инварианты (класс I, отказ старта `fleet_invalid …`): `kind ∈ ADAPTER_KINDS` (реестр в коде); каждое определение модели
ссылается на существующий `backend`, а в эффективный каталог входят только модели включённых бэкендов;
`id` моделей уникальны **глобально** (не на бэкенд — клиент выбирает по `model`);
`default_model` принадлежит включённому бэкенду; `efforts ⊆ EFFORT_LEVELS`; `max_concurrent ≥ 1` (для Muse строго 1); неизвестные ключи — отказ
(в отличие от schema 2, где они молча отбрасывались). **Совместимость:** загрузчик принимает и schema 2 (неявный единственный
`backend: droid`, поведение прежнее) — это даёт откат конфигурации без смены кода. Код старой версии schema 3 **отвергает**
(fail-closed, rc=1), а не публикует модель Muse как droid — поэтому версия поднимается, а не расширяется молча.
Текущий полный структурный валидатор — `core/backend_adapter.py: build_catalog`; его вызывают
`server._build_catalog` и `fleet_check.check_catalogue` с одинаковыми env/probe-настройками.
Паритет охватывает schema 2/3, backends, модели (включая выключенные), ссылки/уникальные id/default/env model,
efforts, image status/proof, image limits и admission. Census класса III, policy, профили и live-проверки
в `fleet_check.py` остаются отдельными операционными проверками, не частью этого паритета.
Muse допускается только с `max_concurrent = 1` (иначе `backend_muse_max_concurrent_invalid`;
конструктор тоже отказывает). CLI сохраняет `--live-droid`; исходное предложение `--live-backends`
не реализовано этим rework.

### Единый фасад (MB-REQ-005..008)

- **HTTP:** путь, Bearer, framing, admission (413/503 до чтения тела), `/health`, `/v1/models` — остаются в фасаде. `/v1/models` =
  объединение `get_models()` включённых бэкендов в порядке `fleet.json`, `owned_by` из бэкенда; `/health` — **те же 7 ключей**:
  `ok = AND(required-бэкенды healthy)`, `active`/`max_concurrent` суммируются по бэкендам, `transport` и `model` — как сейчас
  (значение `transport` меняется только по решению владельца, ASM-002). Расширение `/health` запрещено контрактом.
- **Маршрутизация:** `model → backend` строго по `fleet.json`; один запрос — ровно один бэкенд; **межбэкендного fallback нет**
  (запрос на `muse-spark-1.3` никогда не уходит в droid при сбое Muse — это вопрос приватности и воспроизводимости, а не отказоустойчивости).
  Бэкенд не прошёл `qualify()`/`is_healthy()=down` → 503 `launcher_unavailable`; модель остаётся в `/v1/models` (как receipt-invalid у droid).
- **Валидация effort** остаётся строгой по `models[].efforts` (400 `unsupported_reasoning_effort`); для Muse это строже, чем мягкий
  маппинг :9886 (см. CD-004). `autonomy` валидируется только при `capabilities.autonomy`, иначе принимается и игнорируется с записью
  в журнале (как сегодня в muse-bridge; новых кодов ошибок нет).
- **Tool-эмуляция (MB-REQ-007):** `ToolCallParser`, `render_tools_section`, `render_tool_call`, `render_message` выносятся в
  `core/tool_emulation.py` (чистые функции, без I/O; `server.py` реэкспортирует имена для существующих тестов). Адаптеры получают
  `tools_section` в `TurnRequest` и публикуют сырой `text`; **разбор `<tool_call>` делает фасад** в `_execute`, как сейчас для droid.
  Копия в muse-bridge не переносится.
- **b_guard (MB-REQ-008):** гейт REQ-003 и контур `InstructionGuard` — **фасадная** проверка по тексту запроса, до выбора процесса,
  для **всех** бэкендов (блок agent-instructions — свойство клиента DSH, а не бинарника). Состояние `unsafe` → управляемый отказ
  для новых запросов с блоком. Отключение гарда per-backend запрещено (fail-closed). Код `tools/b_guard.py` не меняется.

### Единый кэш сессий (MB-REQ-006)

`ChatRegistry`/`Chat` остаётся единственным реестром keyed-чатов (`key_hash` → запись `conversations.v1/chats/…`, schema 1,
только хеши). Добавляются **аддитивные** поля записи: `backend` (по умолчанию `droid` для старых записей); `model` в записи уже есть.
Старый код игнорирует лишние поля (`_record_valid` проверяет только перечисленные), поэтому откат читает новые записи. Правила:

1. Бэкенд с `sessions="resident"` — план `hot | restore | rebase | cold` как в ADR 0001; `sessions="none"` — только `ephemeral`
   (записи нет, replay истории; блокировка чата L берётся для keyed-запросов так же, как сейчас).
2. Смена бэкенда в том же чате (DSH сменил модель droid → muse): запись связана с прежним `backend` → `cfg` не совпадает → новая
   generation; прежний процесс закрывается **его** адаптером (`close_session`), слот возвращается. Данные чата не передаются между бэкендами
   иначе как через авторитетную историю запроса.
3. `ChildRegistry` (`children.json`) получает тег `backend`; записи без тега трактуются как `droid`; reconcile на старте добивает
   только собственных осиротевших детей любого бэкенда по start-signature.

### Ресурсы и порядок (MB-REQ-009)

`MAX_CONCURRENT` ADR 0001 (cap 4) становится **ёмкостью P бэкенда droid**; у каждого бэкенда своя `max_concurrent` из `fleet.json`
(Muse = 1: per-turn каталог разводит ходы по данным, но при одном UID и `--yolo` параллельные ходы нельзя развести правами —
поэтому одновременность исключена планированием). Общий `_MUSE_SLOTS` сериализует ходы всех экземпляров MuseAdapter
в одном процессе хаба независимо от backend id; отдельные хабы и внешний muse-bridge этим семафором не связаны.
Порядок **L → P(backend) → T** сохранён; так как запрос принадлежит ровно одному бэкенду и межбэкендного fallback нет,
взаимные блокировки между пулами невозможны по построению. Admission (`max_http_connections`, `max_inflight_body_bytes`) остаётся общим.
Насыщение пула Muse не занимает слоты droid и наоборот. Число бэкендов не ограничено архитектурой; ограничение — ресурсы хоста.

### Безопасность (AD-007)

1. **Никакой динамической загрузки кода из конфигурации.** `kind` разрешается только через словарь `ADAPTER_KINDS` в коде; `fleet.json`
   (0600, владелец) не содержит путей к модулям/командам-шаблонам. Новый бинарник = новый модуль адаптера в репозитории + review.
   Универсальный `exec-template` адаптер — отдельный ADR (вне этого решения).
2. **Права дочернего бинарника.** Клиентские OpenAI tools эмулирует хаб; нативные tools droid
   отключены по `list_tools`/receipt, но это не запрет нативных tools Muse. Для Muse решение владельца по AD-007 (2026-10-08 12:07 MSK):
   `--yolo --trust-workspace` **сохранены** (как в muse-bridge :9886); изоляция добирается компенсаторами —
   per-turn каталог `workspace/muse/turn-<uuid>/` (0700, `cwd` и `--workspace` только он), `max_concurrent: 1`,
   обязательный sha256-pin исполняемого образа, вычищенный `MUSE_BIN`. Это **меняет baseline muse-bridge** (там `--yolo`
   без per-turn изоляции и без pin-гейта); до включения `enabled:true` действует P3-гейт ASM-001
   (живой лог плюс согласование, либо явное решение владельца о снятии гейта).
3. **Окружение детей — allowlist, а не наследование.** `META_API_KEY` и ключ моста вырезаются (как `_child_env()` сегодня для droid); у адаптера
   своя явная выборка (PATH, HOME, прокси-переменные из обёртки).
4. **qualify() — условие допуска.** Droid проходит receipt-допуск образа/протокола; Muse — проверку
   исполняемой обёртки и sha256 канонического бинарника, не отдельную проверку строки версии.
   Замена содержимого Muse даёт несовпавший pin в `is_healthy`/`preflight` (`binary_sha256_mismatch`), а в журнал пишутся
   только безопасные коды состояния/rc/байты (RW-007).
5. Аудит: журнал не содержит prompt-текст; `backend_state` / `backend_qualify` — без секретов; маскировка `_mask_secrets` сохраняется.

#### Ограничения вывода и владения процессами (Cycle 2)

- Stdout читается ограниченными блоками bytes, UTF-8 декодируется строго; JSONL-строка ≤ 8 МиБ,
  текст/дельты/failure reasons суммарно ≤ 10 МиБ. До `json.loads` допускаются ≤ 50 000 структурных
  токенов и глубина ≤ 128; на ход ≤ 50 000 непустых событий, пустые дельты не накапливаются.
- `STDERR_DRAIN_GRACE_S = 5 с` ограничивает добор pipe после выхода лидера; EOF stdout не превращается
  в бесконечное ожидание лидера/stderr. Очистка в `finally`: SIGKILL группе, wait лидера до 5 с,
  ожидание исчезновения группы до 2 с, затем ограниченные join потоков. Это отдельные окна, не общий
  shutdown-дедлайн 5 с. Сбой старта служебного потока не обходит очистку.
- Перед exec создаётся живой свидетель группы; в `children.json` до открытия exec-gate пишутся
  лидер `pid`/`pgid`/`start-signature` и подписанный свидетель в `members`. При рестарте `reconcile_children`
  проверяет подпись и PGID лидера либо члена при мёртвом лидере; повторно проверяет подпись перед сигналом,
  отвергает переиспользованный PID/неподтверждённый PGID. Запись сохраняется, пока свой член жив в группе.
  В ходе запись снимается только после исчезновения группы; живое наследие запрещает новые ходы адаптера.

0700/0600 и сериализация под одним UID — компенсаторы, **не OS sandbox** и не защита от
произвольного same-UID доступа. Подписанное владение подтверждает исходную группу, не все
возможные потомки: вызвавший `setsid` потомок выходит из неё, его завершение не гарантируется.
Ограниченный добор pipe не означает очистку escaped-потомка. FU-003/FU-008 и будущий
out-of-process путь остаются отдельными решениями владельца, не закрыты этим уточнением.

## Консервативные последствия

- ✅ Один порт/ключ/каталог/кэш; добавление бинарника не трогает HTTP-обработчик; копипаст `ToolCallParser` устранён.
- ✅ ADR 0001 для droid неизменен (L → P → T, receipt, бюджеты, изоляция ходов); откат возможен по шагам.
- ✅ Muse получает те же гейты (b_guard, admission, таксономия ошибок), что droid; `--yolo` сохраняется решением владельца,
  но его цена локализована: per-turn каталог, ёмкость 1, обязательный pin, вычищенный `MUSE_BIN`, нет replay промпта.
- ⚠️ Один процесс на все бэкенды: падение хаба = падение всех (смягчение: per-backend fail-closed qualify, isolation потоков/групп процессов,
  launchd KeepAlive; пересмотр → Option C).
- ⚠️ Монолит `server.py` пока растёт на оболочку `DroidAdapter`; вынос внутренностей отложен (долг, не новое нарушение).
- ⚠️ `reasoning_effort` для Muse строже, чем на :9886 (400 вместо тихого `max`); :9886 не меняется, DSH-cutover — решение владельца.
- ⚠️ Живая проба Muse на провайдере `meta` (реальный ход через обёртку, ASM-001) не выполнялась в этом контуре — блокирует
  боевой cutover Muse, не архитектуру.
- 🔄 Живые приёмки (мульти-бэкенд под нагрузкой, Muse least-privilege на `meta`, cutover DSH) — тяжёлый путь, в этом ADR не заявлены проверенными.

## Миграция и откат

**Фазы (strangler, каждая — отдельный MR, baseline зелёный на каждой):**
P1 — seam: `core/backend_adapter.py`, `AdapterRegistry`, `core/tool_emulation.py`, оболочка `DroidAdapter` (`adapters/droid_adapter.py`), загрузчик принимает schema 2|3; `fleet.json` ещё v2.
P2 — `adapters/muse_adapter.py` + fake-muse тесты + контрактный набор `BackendContract` по всем адаптерам; Muse в `fleet.json` v3 с `enabled:false`.
P3 — `enabled:true` только после приложенного лога ASM-001: реальный ход Muse на `meta` через
`~/.config/muse-launch/muse-cli.sh` и совместная нагрузка с Droid, с согласованием владельца; альтернатива —
явная запись решения владельца, снимающая P3-гейт. Fake/echo, unit/HTTP-тесты и `/health` не заменяют живой gate.
ASM-001 сейчас **НЕ ПРОВЕРЕНО**. Однострочное включение после гейта — README «Muse: безопасность и компенсаторы».
Cutover DSH с :9886 на :9882 — владелец (профили DSH принадлежат ему).
**Откат:** P3 — вернуть `enabled:false`/DSH на :9886; P2/P1 — revert коммита и вернуть `fleet.json` schema 2
(`git checkout <sha> -- fleet.json`: загрузчик читает и schema 2, отдельной копии `fleet.json.v2` в репозитории нет);
записи чатов и `children.json` читаются старым кодом (аддитивные поля). Смешанные версии: код с schema 2|3 + файл v2 = прежнее поведение.

## Validation

См. `verification_surface` пакета: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` (полный сьют), новые `tests/test_backend_contract.py`,
`tests/test_fleet_v3.py`, `tests/test_muse_adapter.py`, `tests/test_hub_integration.py` (фасадный шов, RW-013), arch-test границ, `fleet_check.py`;
ручные гейты — живой ход Muse на `meta` через обёртку (ASM-001) и сосуществование двух бэкендов на живом :9882. Пересмотр ADR: ADR 0001 теряет силу для droid,
появляется бинарник с недоверенным кодом/иным рантаймом (→ C), `ADAPTER_API` нужно ломать.

## Views

- **VIEW-001 Container** — раздел «Container» выше (внешние акторы, процессы, порты).
- **VIEW-002 Component** — раздел «Component: seam `BackendAdapter`».
- **VIEW-003 Dynamic** — ход чата:

```
client ─POST /v1/chat/completions─▶ Facade
  1 auth → framing → admission(Content-Length резерв) → JSON
  2 model → BackendRegistry.resolve(model) ─(нет)→ 400 model_not_allowed
  3 effort (строго по models[].efforts) → autonomy (если capability)
  4 prompt_guard(b_guard) ─(unsafe/size)→ 503 launcher_unavailable
  5 backend.is_healthy() ─(down)→ 503 launcher_unavailable
  6 SessionCache: keyed? L(chat) → plan(hot|restore|rebase|cold | ephemeral[sessions=none])
  7 P(backend) ─(очередь ≤900 с)→ T → adapter.execute_turn(sink)
  8 sink: text|reasoning|result|done|stream_error|pump_error → Facade: ToolCallParser → JSON | SSE
  9 checkpoint (READY) → release T,P,L → доставка срезами 64 КиБ
  ошибки: BackendProtocolError→502 · BackendTimeout→504 (kill группы) · Cancel→слоты возвращены
```

- **VIEW-004 DFD / trust boundaries** — Z0 клиент DSH (Bearer) │ Z1 хаб (процесс, `fleet.json` 0600, state 0700) │ Z2 дочерние бинарники
  (`droid`, `muse` — отдельные процессы/группы, окружение по allowlist) │ Z3 внешние сервисы (Factory/Anthropic…, Meta через прокси :10816). Потоки:
  Z0→Z1 prompt+tools; Z1→Z2 prompt-файл/stdin; Z2→Z3 egress вне хаба; Z2→Z1 события/текст (недоверенные: парсятся ограниченно по бюджетам).
- **VIEW-005 Deployment** — один launchd-сервис хаба на :9882 (127.0.0.1); :9886 muse-bridge продолжает работать до cutover; общий
  `workspace/` хаба (state, runtime), у Muse свой каталог внутри.

## Links

- ADR 0001 (`docs/adr/0001-persistent-droid-bridge.md`), README «RPC-режим», «Каталог fleet.json», «Развёртывание».
- `~/.dsh/bridges/muse-bridge/README.md`, `~/.config/muse-launch/muse-cli.sh`, `~/Мой диск/Context/models.md` (стр. 321).
- Architecture Packet (`architecture-packet.json`: AD-001…AD-009, QA-001…QA-010, VER-001…) — артефакт эфемерного прогона
  `/tmp/cel-runs/…`, в репозиторий не входит; здесь он источник фактов Context, а не ссылка для сопровождения.

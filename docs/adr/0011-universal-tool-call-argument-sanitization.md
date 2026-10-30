# ADR: Универсальная схемо-осведомлённая санитизация аргументов tool_calls в cli-agent-bridge

## Статус
Принято владельцем: AD-003/004 — явные A1+A2 (чат 2026-10-30 15:04 MSK, briefs/architect-delta-brief.md); AD-008 и supervised hub в объёме задачи — явное «Да, принимаем» (2026-10-30 16:23 MSK); AD-002 — после живой проверки фактов V-01/V-02 по требованию владельца проверить сейчас (briefs/live-verification-2026-10-30-1645.md); AD-007 следует за AD-008. Дельта a2 (арх-панель a1, handoff/panel-rework-brief.json): RW-001..RW-005; F-004 — OWNER_DECIDED (handoff/owner-decision-F-004.md, 2026-10-30 17:36 MSK; в consensus-ledger статус ESCALATED не переписан). Дельта 6 (арх-панель a2, handoff/panel-rework-brief.json RW-001..RW-005 + FU-001/FU-002): RW-001/RW-002/RW-004 — RESOLVED решения C1 сохранены без ослабления; RW-003 (F-003) и RW-005 (F-005) — OWNER_DECIDED (handoff/owner-decision-F-003-F-005.md, 2026-10-30 19:58 MSK; в consensus-ledger статусы ESCALATED не переписаны). Пакет архитектуры APPROVED; downstream panel-proof до Coder и живые гейты VER-011/015/016 — отдельные обязательные шаги. Это proposal ADR, не runtime сдача.

Номер 0011 свободен по inventory docs/adr; существующий ADR0010 не перезаписывается. Файл docs/adr/0011-universal-tool-call-argument-sanitization.md на диске уже равен proposal редакции a2 (sha256 f745ef7e49e038a19f634a7d96b52aa83b72802d873baf035a93851c864c1c2c, совпадает с materialization[] пакета a2; FU-001, сверено Architect дельтой 6) — повторный перенос a2 не требуется. Редакцию дельты 6 (этот proposal) переносит Coder отдельным вызовом exact bytes с read-back sha256 после approval; Architect target не трогает.

## Контекст и проблема
Модели разных семейств заполняют опциональные строковые параметры инструментов пустыми
строками вместо опускания ключа. В 60 свежих сессиях DSH зафиксировано 570 таких вызовов
(`subagent` — 356, `list_subagent_models` — 110, `update_goal` — 52, `bash` — 51,
синтетический `parallel` — 1; модели `codex/gpt-6.1-terra` — 558, `codex/gpt-6.1-sol` — 12).
Строгая валидация на стороне клиента отклоняет вызовы: ``child LLM `provider` must be
non-empty``, `invalid justification: expected a non-empty sentence`,
`GOAL_TOOL_INVALID_UPDATE`, `unknown tool "parallel"`.

Жёсткие ограничения (`AGENTS.md` репозитория):
- вендорский код не правится и оверлеями не перекрывается (DSH, `app.asar`, `codex-lb`,
  профили клиентов); ранее внедрённый оверлей
  `~/.dsh/profiles/desktop/node_modules/@deepseek-ai/dsh-tool-subagent` подлежит откату;
- исправление — только на универсальном слое `cli-agent-bridge`, без зависимости от
  вендора/клиента, модели и транспорта;
- внешняя форма OpenAI-совместимого ответа сохраняется (форма stream/non-stream,
  `finish_reason`, `id`/`index` tool_calls) — меняется содержимое `arguments`; отдельная согласованная CD-003 меняет unknown explicit model400 на404 (AD-008 ниже).

Факты системы, определяющие решение (evidence-ledger прогона):
- 100% зафиксированных сбоев — провайдер `codex` (`127.0.0.1:2455`, сторонний `codex-lb`),
  идущий мимо `cli-agent-bridge`; `codex-lb` аргументы не нормализует, хуков нет.
- В корневом фасаде санитизатор из ADR 0010 уже есть в `core/tool_emulation.py`, но
  вызывается с `tool_schemas=None`: `request.tools` не проброшен в `ctx`/`TurnContext`,
  поэтому схемная ветка мертва, чистятся только захардкоженные имена полей.
- Автономные мосты (`muse :9886`, `opencode-zen :9883`, `claude-p :9881`) уже импортируют
  части `core/` (например `core.backend_adapter`/`core.lifecycle`, `core.watchdog`/`core.usage_wire`),
  но не `core.tool_emulation`; `claude-p-bridge` в репозитории отсутствует (живёт только в `~/.dsh/bridges/`).
- `agy-bridge` наружу `tool_calls` не эмитит — санитизировать там нечего.

## Архитектурные решения

### AD-001. Один слой в `core/`, один владелец применения на маршрут (RW-002)
- Единственная реализация санитизации — ядро `core/` (`core/tool_emulation.py`:
  эволюция существующих `sanitize_tool_call`/`sanitize_tool_calls_list`). Чистые функции
  без I/O, без имён моделей, клиентов и транспортов.
- Владелец применения выбирается по маршруту (XOR): ни один `tool_call` не проходит две
  границы санитизации в одном процессе.
  - CLI-маршруты фасада (`droid`/`muse` через `server.py` `_dispatch`) — владелец ФАСАД:
    ровно одно применение на границе финализации после адаптера и после `finalize_turn`,
    до сериализации (`_serve_json`/`_serve_sse`). Применение обязано преобразовать согласованно
    оба представления — список `tool_calls` и события `tool_call` в `events` (один результат,
    без расхождения stream/non-stream). Существующие вызовы в `add_call` droid-пути и в
    `_serve_json` удаляются; `finalize_turn` на фасадном пути вызывается без санитизации
    (`sanitize=False`), иначе живой droid-путь с готовыми `events` (ранний возврат
    `finalize_turn` при `raw.events is not None`) и managed-путь разойдутся, а managed-путь
    получил бы двойное применение.
  - Passthrough-маршрут (AD-003) — владелец RAW-ШОВ passthrough, НЕ фасад: passthrough не
    проходит `_dispatch`/`finalize_turn`, поэтому фасадная граница его вызовы не трогает.
    Санитизация — при сборке ответа внутри шва (AD-005), ровно один раз на вызов.
  - Каждый автономный мост — владелец МОСТ: применение в колбэке эмиссии `tool_call`, до
    формирования SSE-кадра или JSON-ответа (мосты пишут SSE сразу в сокет).
  - Managed replay: повторная выдача отдаёт уже финализированные (санитизированные)
    представления из буфера хода дословно; повторного применения на replay нет.
- Схемы инструментов строятся один раз на запрос из `request.tools[].function.parameters`
  общей функцией ядра и пробрасываются владельцу маршрута (фасад — через `ctx`/`TurnContext`;
  мосты и passthrough — из тела запроса). В адаптерах и мостах собственной логики очистки нет.
- Доказательство «ровно один раз» — не grep: поиск вызовов (VER-004) доказывает только места
  определений/вызовов по владельцам маршрутов. Количество применений на вызов доказывают
  runtime-тесты со счётчиком (шпион на функцию ядра) в VER-001 (фасад: список+события+replay)
  и VER-006 (passthrough SSE/non-stream): ровно 1 применение на каждый опубликованный вызов.

### AD-002. Политика санитизации: схемо-осведомлённая, «только удаление» (RW-003, OWNER_DECIDED)
Санитизатор никогда не синтезирует значения (не подставляет fallback-тексты) — только
удаляет ключи верхнего уровня объекта `arguments` при одновременных условиях:
1. значение — пустая или пробельная строка;
2. толерантная проверка схем (RW-003, решение владельца 2026-10-30 19:58 MSK): схема
   инструмента известна из `request.tools`, поле объявлено в `properties` и является
   строковым — `type == "string"` либо `"string"` входит в массив `type`
   (например `type: ["string", null]`);
3. поле не входит в `required` (required-поля не удаляются никогда);
4. `enum`/`const` поля не допускает пустую/пробельную строку; если допускает —
   защищённое пустое/пробельное значение сохраняется и не считается отсутствием ключа;
5. поле не входит в закрытый список семантических payload-полей `prompt`, `content`,
   `command` (пустая строка там может быть осмысленной нагрузкой; расширение списка —
   только дельтой этого ADR с тестом).

Прочее:
- fail-conservative (RW-003): без схемы, при `anyOf`/`oneOf` без явного строкового
  `type`, неразрешённом `$ref` или `enum` без явного строкового `type` поле строковым
  не считается и `arguments` не мутируются; для неподдержанных схем отсутствие мутаций
  и остаточный риск названы явно (REQ-01 ограничен поддержанными формами);
- тесты политики (VER-003, `tests/test_tool_sanitizer.py`): схема `update_goal`,
  `type: ["string", null]`, `enum`/`const` с пустой/пробельной строкой, `required`,
  `anyOf`/`oneOf` без явного `string`, отсутствие схемы; проверка `update_goal`
  связана с доступной схемой теста и выполненной здесь не выдаётся;
- без схемы (инструмент не объявлен в запросе) `arguments` не мутируются; эвристики по
  именам полей (`ROUTE_FIELDS` и подобные из ADR 0010) удаляются — маршрутные поля
  `provider`/`model`/`reasoning_effort` чистятся общим правилом, так как в реальных
  схемах они опциональные строки;
- условно-обязательное `justification` при заданном `sandbox_permissions`: пустое
  значение удаляется общим правилом; fallback-текст НЕ подставляется — мост не вправе
  фабриковать обоснование эскалации песочницы от имени модели (аудит/безопасность).
  Подтверждено кодом потребителя DSH (`validateEscalationArgs`): при обоих пустых
  (`sandbox_permissions:""`, `justification:""`) вызов после удаления валиден;
  комбинация валидный `sandbox_permissions` + пустой/отсутствующий `justification`
  остаётся ошибкой `requires a justification` (вместо прежней `non-empty sentence`) —
  принятый остаточный риск: модель повторяет вызов с настоящим обоснованием.
  Обе комбинации фиксируются тестами и живым гейтом;
- вложенные объекты не трогаются; невалидный JSON и не-объектные `arguments` возвращаются
  как есть (fail-open); неизменённые `arguments` сохраняются байт-в-байт; повторное
  применение идемпотентно;
- распаковка синтетического `parallel` во вложенные вызовы сохраняется (структурная
  нормализация, от схемы не зависит); число опубликованных вызовов и глубина
  ограничены env-лимитами AD-005 (RW-005), а не зашитыми константами.

### AD-003 (one-way). Маршрут `codex` — через универсальный passthrough хаба: отдельный raw HTTP-шов (RW-003)
- В хаб (`server.py`, :9882) добавляется сквозной OpenAI-совместимый passthrough:
  новый `kind=passthrough`, upstream задаётся в `fleet.json` (`base_url`, модели и max_concurrent; без секретов). Шов не знает про `codex-lb` ничего специфичного:
  любой OpenAI-совместимый upstream подключается конфигом; `codex-lb :2455` — первый инстанс.
  Факт схемы fleet: действующий `BACKEND_KEYS` (schema 3, `core/backend_adapter.py`) ключа
  `base_url` не принимает — дельта CD-002 обязана аддитивно расширить `BACKEND_KEYS` и
  валидацию записи бэкенда (`base_url` обязателен для kind=passthrough, только loopback
  `http://127.0.0.1:<порт>/v1` в этой задаче) с паритетом загрузчика сервера и `fleet_check`;
  без этого расширения конфиг passthrough невалиден и хаб не стартует (fail-closed — правильно).
- Граница доставки (выбрано, Coder не выбирает): passthrough — ОТДЕЛЬНЫЙ raw HTTP-шов ВНЕ
  `TurnContext`/`TurnResult` и вне `BackendAdapter.execute_turn`. `TurnResult` не несёт
  HTTP-статус/заголовки/сырое тело, а SSE-фасад фиксирует downstream 200 до адаптера, поэтому
  дословный passthrough через этот шов невозможен. В `do_POST` после допуска (AD-007) и
  разрешения модели в backend kind=passthrough запрос уходит в raw-шов ДО построения
  транскрипции/`TurnContext`, managed-сессий и сериализации фасада; шов сам пишет ответ клиенту.
  Реестр `ADAPTER_KINDS` CLI-адаптеров passthrough не исполняет (kind нужен валидации fleet и
  маршрутизации; исполнение — raw-шов). Owner-сессии, транскрипция и эмуляция инструментов
  к passthrough не применяются.
- Контракт шва. Запрос: исходные байты тела уходят upstream без мутаций (разбор JSON-копии —
  только для маршрутизации, флага `stream` и построения `tool_schemas`); `model`,
  `reasoning_effort`, `tools`/`tool_choice` и прочие поля, а также `Authorization` (AD-007)
  передаются дословно; hop-by-hop заголовки не пробрасываются. Ответ: downstream-заголовки
  НЕ фиксируются, пока не получены статус и заголовки upstream. Non-stream: при 200+JSON
  санитизируются только `choices[].message.tool_calls` (AD-001/AD-005), остальное тело без
  пересборки полей; любой не-200 и не-JSON ответ — статус и тело дословно (без `TurnResult`).
  Stream: при upstream не-200 (например 429 при `stream=true`) статус и исходное тело
  возвращаются как обычный HTTP-ответ до любого downstream 200; при 200+SSE downstream
  фиксируется `200 text/event-stream`, далее по AD-005: `content`/`reasoning` без задержки,
  `tool_calls` буферизуются, терминальный чанк (`finish_reason`, `usage`), upstream error-chunk
  и `[DONE]` пробрасываются в исходном порядке с единственной нормализацией собранных
  `tool_calls`. Ошибка upstream после начала потока не превращается в HTTP-статус: error-chunk
  дословно, затем закрытие. Отмена клиента (`client_gone`) закрывает upstream-соединение в
  `finally`; повторов POST нет. Таймауты конечны: connect — короткий (порядка 10 с), чтение —
  idle/total в пределах safety-cap хода; превышение до начала потока — 502/504 без повтора,
  после начала — завершение потока ошибкой.
- `providers.codex.baseURL` в `~/.dsh/profiles/desktop/cordis.patch.yml` переключается
  на `http://127.0.0.1:9882/v1` (конфиг профиля, не вендорский код). Хаб становится
  обязательной зависимостью маршрута codex — это цена решения (см. «Последствия»).
- Альтернативы отклонены: A2 «только текущие адаптеры» не закрывает маршрут, дающий
  100% сбоев; A3 «патч codex-lb» запрещён `AGENTS.md`; отдельный прокси-процесс
  дублировал бы фасад и точку применения.
- Откат: вернуть `baseURL` на `:2455` и (при необходимости) оверлей из бэкапа; код
  passthrough при этом безвреден. Цена отката — минуты, но решение помечено one-way:
  после переключения доступность codex зависит от хаба операционно.

### AD-004. Шаринг ядра с автономными мостами
- Источник правды — репозиторий. Мосты импортируют `core.tool_emulation`; развёрнутые
  копии в `~/.dsh/bridges/*` получают пакет `core/` синхронно с `server.py` моста;
  побайтовая идентичность проверяется sha256-оракулом в verification surface.
  Ручные правки в `~/.dsh/bridges/*` запрещены (только синхронизация из репозитория).
- `claude-p-bridge` сначала вносится в репозиторий (`bridges/claude-p-bridge/`) как
  источник правды — без этого единый слой для :9881 невозможен.
- Ошибка импорта `core` в мосте — fail-closed на старте процесса (громко), а не тихая
  работа без санитизации.
- Дедупликация копий `ToolCallParser` в мостах в объём этого ADR не входит: сначала
  подключается санитизатор; слияние парсеров — отдельная задача с корпусом тестов
  эквивалентности (baseline debt зафиксирован).

### AD-005. Стриминг: буферизуются только `tool_calls`; ключ `(choice.index, tool_call.index)` (RW-004, сохранён дельтой 6) и env-лимиты (RW-005, OWNER_DECIDED)
- Корневой фасад уже буферизует `tool_calls` до конца хода — санитизация до первого
  кадра, `id`/`index`/`finish_reason` не меняются.
- Passthrough: upstream отдаёт `arguments` инкрементальными дельтами. Raw-шов копит
  дельты `choices[].delta.tool_calls` по составному ключу `(choice.index, tool_call.index)`
  (НЕ только по `tool_call.index`: разные choices с одинаковым `tool_call.index=0` иначе
  смешивают `id`/`name`/`arguments`). `id`/`name` берутся из первых дельт своего ключа,
  фрагменты `arguments` конкатенируются только внутри ключа. Завершение — отдельно для
  каждой choice: чанк с непустым `finish_reason` choice N санитизирует и выпускает только
  вызовы choice N (с сохранением `choice.index`, `tool_call.index`, `id`/`name`) перед её
  терминальным чанком и не сбрасывает буферы остальных choices; конец потока без
  `finish_reason` сбрасывает незавершённые вызовы и выдаёт error-chunk без `[DONE]`.
  Переиндексация внутри choice — только если распаковка `parallel` изменила число вызовов
  этой choice. Дельты `content`/`reasoning` не буферизуются и не задерживаются.
  Цена: клиент видит `tool_call` в конце генерации вызова своей choice, а не по частям.
  Архитектурный тест (VER-006): чередующиеся дельты двух choices с `tool_call.index=0` и
  разными `id`/`name` дают два несмешанных вызова с отдельными `finish_reason`.
- Env-лимиты ответа (RW-005, директива владельца «Я хочу чтобы мы ничего не зашивали,
  а всё можно было настроить»): ни один лимит этого раздела не зашивается в код
  неизменяемой константой. Единая таблица (чтение при старте процесса,
  `int(os.environ.get("<имя>", "<default>"))`; defaults — не жёсткие потолки,
  переопределение в обе стороны покрыто тестами VER-003/VER-006):

  | Env | Default | Enforcement |
  |---|---|---|
  | `BRIDGE_MAX_PARALLEL_CALLS` | 64 | максимум опубликованных вызовов после распаковки `parallel` |
  | `BRIDGE_MAX_PARALLEL_DEPTH` | 8 | максимальная глубина распаковки `parallel` |
  | `BRIDGE_PASSTHROUGH_MAX_BODY_BYTES` | 16777216 (16 MiB) | весь upstream non-stream body, до полного чтения/JSON-разбора, включая ответы без `tool_calls` |
  | `BRIDGE_ACCUMULATOR_MAX_BYTES` | 8388608 (8 MiB) | SSE-аккумулятор `tool_calls` на запрос (UTF-8 `arguments`+`id`/`name` по всем choices/ключам) |
  | `BRIDGE_ACCUMULATOR_MAX_KEYS` | 64 | максимум ключей `(choice.index, tool_call.index)` на запрос |
  | `BRIDGE_ACCUMULATOR_MAX_PROCESS_BYTES` | 33554432 (32 MiB) | аккумулятор суммарно на процесс по параллельным passthrough-запросам |

  Имена первых пяти заданы владельцем (19:58 MSK); имя процессного бюджета фиксирует
  Architect дельтой 6. Числа defaults выбраны под локальный envelope (один процесс,
  `max_http_connections=32`, passthrough `max_concurrent=4`) и действующими лимитами
  не выдаются; оценки HL-ENV/memory closure привязываются к эффективным значениям.
  Лимит входящего тела `max_inflight_body_bytes` (64 MiB) и delivery-бюджет фасада —
  другие объёмы и пределом аккумулятора/тела upstream не являются.
  Enforcement — при чтении upstream, ДО добавления фрагмента/полного чтения тела:
  проверка счётчиков запроса и процесса перед ростом буфера; учёт инкрементный,
  освобождение в `finally` на success/error/cancel/overflow без утечки. Превышение
  веера: дальнейшая распаковка прекращается, уже накопленные полные вызовы
  сохраняются. Превышение тела: upstream закрывается, HTTP 502 (Bad Gateway /
  Payload Too Large) без повтора POST. Превышение аккумулятора: upstream закрывается;
  до фиксации downstream — 502 `upstream_response_too_large`, в начатом SSE —
  терминальный error-chunk без `[DONE]`-успеха и без частично собранных вызовов.
  Тесты: лимит−1/= /+1 для тела и веера, огромный non-tool body, один `parallel`
  сверх лимита детей, сохранение накопленных вызовов, override каждого env в обе
  стороны и глубина (`tests/test_passthrough_adapter.py`, `tests/test_tool_sanitizer.py`;
  ожидания VER-003/VER-006).

### AD-006. Безопасная последовательность выката
1) Deploy common core + фасад + shared-core мосты + passthrough kind + routing/catalogue AD-008; sync runtime sha256 VER-005; поднять supervised hub, которого сейчас нет (подтверждено проверкой портов и LaunchAgents): новый ~/Library/LaunchAgents/com.user.dsh-hub.plist (Label com.user.dsh-hub, RunAtLoad+KeepAlive, как у соседних мостов), старт passthrough без обязательного FACTORY_API_KEY, отдельный проверяемый шаг ключа клиента хаба без логирования значений; install/readback и restart-persistence gate VER-016 (launchctl list/print + curl /health). baseURL ещё :2455, overlay на месте. 2) VER-014 green (stream/non-stream fake upstream + YAML-to-fleet exact catalogue) и остальная frozen surface. 3) Только providers.codex.baseURL :2455->:9882, VER-010. 4) VER-015 на codex/gpt-6.1-terra И codex/gpt-6.1-sol: exact model+route в безопасных логах, unknown explicit->404; VER-011 живой subagent без must be non-empty при ещё установленном overlay. 5) Только после обоих live gates: overlay ->сохранённый backup, VER-008/009, полный restart DSH, повтор VER-011+VER-015 без overlay.

Rollback каждого шага: По шагам: 1) до переключения baseURL вернуть прежние code/fleet/runtime из сохранённых снимков, отключить только новый supervisor и восстановить его прежнее состояние; текущий codex прямой :2455, overlay не трогать. 2) VER-014 FAIL ->switch запрещён, откат step1. 3) после switch любой FAIL ->baseURL :2455 и restart/reload DSH с overlay сохранённым. 4) VER-015/011 FAIL ->тот же возврат, overlay не удалять. 5) после удаления overlay восстановить сохранённый exact backup, baseURL :2455, restart DSH; проверить прежний живой маршрут. Runtime sync rollback каждого моста server.py+core вместе с sha256. Утечка Authorization ->остановить rollout и решение владельца о ротации. Kill-switch санитизации сохраняется, но не заменяет rollback каталога/маршрута.

### AD-007. Модель допуска passthrough и Authorization literal (RW-001, Q-008 закрыт выбором Architect)
Authorization входного запроса передаётся configured upstream дословно (AD-008 текущего owner brief); отсутствующий заголовок остаётся отсутствующим. Никакого env fallback, замены Bearer, логирования значения или сохранения в fleet/artifacts. apiKeyEnv остаётся конфигом DSH, который формирует клиентский заголовок.

Коллизия: действующий `_auth_ok` (`server.py`) сверяет тот же `Authorization` (или `x-api-key`) с ключом хаба `DROID_DSH_BRIDGE_KEY` ДО выбора маршрута, а DSH для codex присылает ключ codex-lb. Одним заголовком обе проверки не удовлетворить. Выбранная модель (не поручение Coder): **route-scoped допуск после разрешения маршрута**.

- Порядок: сначала минимальный разбор пути и тела (модель → backend/kind по fleet), затем допуск по маршруту, затем исполнение. Для `POST /v1/chat/completions` с моделью backend kind=passthrough проверка ключа хаба к `Authorization` НЕ применяется: аутентификатор — configured upstream, которому заголовок уходит дословно; неверный/отсутствующий ключ отклоняет upstream, хаб его ответ пробрасывает по AD-003. Для всех остальных маршрутов (CLI-бэкенды droid/muse, служебные пути) действующий `_auth_ok` против `DROID_DSH_BRIDGE_KEY` сохраняется без изменений — ключ хаба по-прежнему защищает локальное исполнение кода.
- `GET /v1/models`: каталог не секрет; допуск — ключ хаба ИЛИ (passthrough сконфигурирован И запрос с loopback-пира) — иначе DSH с ключом codex-lb не получит список моделей. Ответ при этом только публичный каталог fleet, без секретов и без вызова upstream.
- Trust boundary и цена (one-way аспект внутри принятого AD-003/AD-007): допуск passthrough опирается на loopback-границу хоста (bind только `127.0.0.1`, пир обязан быть loopback) + аутентификацию upstream. Любой локальный процесс может дойти до upstream через хаб, но не получает ни локального исполнения, ни чужих сессий: passthrough stateless, owner-сессии/`_owner_token_hash`/managed-буферы к нему не применяются, admission-лимиты (`max_http_connections`, `max_concurrent` бэкенда, бюджет AD-005) действуют. Альтернативы отклонены: единый ключ хаба = ключ upstream связывает два секрета и ломается при ротации любого; второй заголовок для ключа хаба требует от DSH неподтверждённой возможности слать дополнительный заголовок (вендор не трогаем); подмена заголовка запрещена AD-008.
- Матрица исходов: passthrough-модель + валидный ключ upstream → дословный проброс, ответ upstream; + неверный/отсутствующий Authorization → дословный проброс, отказ upstream дословно (хаб 401 не синтезирует и заголовок не синтезирует); passthrough-модель + ключ хаба вместо upstream-ключа → проброс дословно, решает upstream; CLI-модель/прочие маршруты + ключ upstream вместо ключа хаба → 401 хаба как сегодня, бэкенд не вызывается; не-loopback пир → отказ до upstream; `/v1/models` — по правилу выше. Значения ключей и `arguments` в логи/ошибки/артефакты не попадают; upstream только операторский fleet `base_url`, редиректы с Authorization не follow; внешний HTTPS — отдельным согласованным изменением.

### AD-008 (one-way вместе AD-003). Модель и effort не подменяются
Routing table target: gpt-6.1-terra ->backend passthrough ->configured codex-lb :2455; gpt-6.1-sol ->тот же passthrough, sol->droid удаляется. GET /v1/models публикует обе модели через активный passthrough adapter. Для passthrough model, reasoning_effort и Authorization остаются дословными; каталог не clamp/default effort и не меняет/пропускает поле. Explicit unknown model ->HTTP404 model_not_found, upstream/backend не вызываются, fallback MODEL_ID запрещён. Missing/null/blank model на legacy маршрутах отдельно сохраняет нынешний default contract; для положительных passthrough cases обязательны явные exact ids. Уточнение дельты a2: объём смены 400→404 — только явная неизвестная СТРОКОВАЯ модель (`model_not_found`); не-строковый `model` остаётся 400, missing/null/blank не меняются. Известный остаток: missing/blank model после switch по-прежнему молча уйдёт в legacy default (droid) — источник запроса надёжно не различим, контракт сознательно сохранён; DSH codex всегда шлёт явный id из каталога, маршрут default виден в безопасном логе (route/model без секретов), VER-014 фиксирует missing→default отдельным кейсом, а не как passthrough.

As-is: Перепроверено delta Architect: default_model=claude-sonnet-5-5, MODEL_ID=ENV_MODEL or fleet default; sol backend=droid efforts=[high], terra отсутствует в 10 ids. Missing/null/blank model используют MODEL_ID; explicit unknown НЕ fallback: HTTP400 model_not_allowed. Effort отсутствует/пустой ->default, строковый клампится; backend по model.backend, недоступность 503. GET models публикует активные BACKENDS.models() в порядке fleet/default.

QA-008: 100% fake-upstream комбинаций каждого codex.models[].id и effort values (low/medium/high), stream/non-stream, exact model+effort+Authorization и0 calls other backends. VER-014: `PYTHONPATH=. ~/.local/bin/uv run --python 3.14 --with pytest --with pyyaml pytest tests/test_passthrough_routing.py tests/test_codex_catalogue_contract.py -q` (будущие named tests; пока НЕ ВЫПОЛНЕНО). VER-015: обе живые модели и unknown404, mandatory перед overlay rollback. VER-016: supervised start/restart-persistence. Никакого Authorization в логах.

## Последствия
- Положительные: класс сбоев «`""` в опциональных строковых аргументах» закрыт для всех
  клиентов, моделей и транспортов через один слой; оверлей вендорского профиля удалён;
  будущий upstream получает санитизацию конфигом passthrough, а не новым кодом.
- Отрицательные: хаб :9882 — новая обязательная зависимость маршрута codex (SPOF
  локального контура; откат — возврат `baseURL`); в стриминге passthrough клиент
  получает `tool_calls` в конце вызова; автономные мосты приобретают зависимость от
  пакета `core/` и дисциплины синхронизации рантайм-копий.
- Известные остатки: инструменты без схемы в запросе не санитизируются (сознательный
  консерватизм); провайдеры через `model_georouter` (:10830) вне контура — отдельный
  сервис, при необходимости подключается тем же passthrough-механизмом;
  prompt-уровневая директива из ADR 0010 (AD-003 там) не реализована и сюда не входит.
- Kill-switch: существующий флаг `BRIDGE_SANITIZE_TOOL_CALLS` (env, default on)
  распространяется на мосты и passthrough; выключение возвращает прежнее поведение
  без смены кода.

## Проверка
Замороженная verification surface — в пакете прогона
(`architecture/architecture-packet.json`, `verification-surface.json`): целевой и полный
`pytest`, схемные тесты политики, параметризованный тест независимости
(≥3 транспорта × ≥3 модели, один санитизатор), grep-оракул мест вызовов по владельцам
маршрутов (VER-004; количество применений доказывают runtime-счётчики VER-001/VER-006),
sha256-синхронизация `~/.dsh/bridges/*`, проверки отката оверлея и
живой гейт в DSH (manual). Дельта a2 добавляет в ожидаемые результаты VER-006: матрицу
допуска AD-007, downstream-фиксацию после upstream (429 при stream), чередующиеся дельты
двух choices (RW-004) и границы бюджета аккумулятора (лимит−1/= /+1, один огромный вызов,
65-й вызов, параллельные запросы и освобождение после cancel). Команды VER не изменены.
Дельта 6 (RW-001..RW-005, FU-001/FU-002): VER-003 — кейсы толерантной схемы RW-003
(update_goal, type-массив со string и null, enum/const с пробелами, required,
anyOf/oneOf без string, без схемы); VER-003/VER-006 — env-лимиты RW-005 (границы
лимит−1/= /+1 тела и веера, огромный non-tool body, override каждого env в обе
стороны); VER-006/014/016 — сохранение матрицы AD-007 (RW-001/RW-002) и составного
ключа (RW-004); VER-008/VER-009 — однозначные PASS-оракулы (FU-002: PASS фиксируется
verifier как exit=0 гейта только при перечисленных условиях; команды заморожены).

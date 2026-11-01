# 0014 — Изображения и санирование потока Claude bridge

## Status

Proposed, DRAFT A2 S2, 2026-10-31; approval PENDING. Это proposal для материализации точных байтов
в `docs/adr/0014-claude-bridge-images-and-stream-sanitization.md` после approval.
Продуктовый код, профиль DSH и launchd настоящим документом не изменены.
Архитектурный gate не пройден. Q-001…Q-003 закрыты адресными решениями
на уровне DRAFT; обязательства GATE-HL/GATE-FLAGS и повторного рассмотрения
не выполнены. Q-004 остаётся неблокирующим вопросом корпуса. Coder запрещён
до approved/ARCH_GATE и проверенного panel-proof; это не приёмка продукта.

## Y-формулировка

В контексте OpenAI-совместимого `claude-p-bridge`, сталкиваясь с потерей
изображений, утечкой XML и потерей reasoning в JSON, предлагаем перенести
наш мост в репозиторий и использовать общую обработку вложений и потока в
`core/`, чтобы один нормализованный поток обслуживал SSE и JSON. Принимаем
зависимость развёртывания от согласованной версии core и необходимость
исполнить обязательные меры для нативного Read при явно принятом владельцем
остаточном same-UID риске на локальной macOS-станции.

## Context

Свежие факты: `analysis/bridge-claude-img-junk-fix/evidence-ledger.md`,
F-01…F-34, 2026-10-31. Мост вне репозитория отбрасывает image_url и
image-only сообщения, отключает инструменты Claude и содержит локальную
копию парсера, которая возвращает повреждённый XML в content. Сырой result
может повторно обойти обработку; JSON теряет thinking_delta.

Текущий task.json уже закрепляет REQ-04 ALWAYS-ON и обязательный REQ-05
Real-time Live Reasoning в core/tool_emulation.py. Его точный SHA-256 находится
в requirement_baseline пакета A2; Architect байты task.json не меняет.
Прежняя санитизация аргументов из аналитического handoff остаётся REQ-04/AD-004.
Авторизация — owner-decision-arch-r1.md §§2,4 (точный путь/hash ниже).
Прежняя формулировка REQ-05 не доказывает выполнения нового требования.

Фактический стек — stdlib ThreadingHTTPServer, subprocess, потоки и очереди.
ORM, SQLAlchemy, Pydantic, Alembic и новая БД здесь не требуются. Корневых
pyproject.toml/uv.lock нет. ADR 0011 AD-004 задаёт SSOT в репозитории,
совместную поставку core и fail-closed при ошибке импорта.

## Decision drivers

1. Ни одна правка не затрагивает вендорский код, app.asar, бинарники или
   исполняемые оверлеи в профилях. Исправления протокола принадлежат core.
2. Для принятого image-only запроса обязательно существует marker и файл;
   изображение не исчезает из промпта. Каталог 0700, файлы 0600, очистка
   после завершения группы процессов на каждом управляемом выходе.
3. Незавершённые/битые реальные tool_call не появляются в content ни при
   SSE, ни в JSON, ни через result fallback. Документирующие примеры в
   Markdown сохраняются; нельзя вырезать теги глобальным regex.
4. Reasoning публикуется до терминального события; сумма SSE-дельт равна
   message.reasoning_content JSON при одинаковом входном event transcript.
5. Накладные расходы на чанк <0.010 s; handoff дополнительно заявляет p99
   0.050 s. Это разные показатели, требуется профиль, а не unit wall-clock.
6. Заявленные 20 req/s, 10 активных CLI, 20 MB вход и RSS <64 MB пока имеют
   статус входных целей. Единицы MB/MiB и область RSS требуют подтверждения.

## Considered options

- **A — общее ядро и репозиторный мост.** Нормализовать содержимое в core;
  только адаптация событий Claude, argv и HTTP-обвязка — в нашем мосте.
- **B — независимые реализации внутри нашего Claude bridge.** Перенести
  SSOT, но продолжать отдельные парсеры и аккумуляторы для каждого моста.
- **C — исправления клиента DSH или исполняемые оверлеи.** Перехватывать
  изображения/вывод на стороне клиента. Недопустимо по AGENTS.md.

## Evaluation matrix

Веса зафиксированы 2026-10-31 до оценки: универсальность 0.35,
безопасность 0.30, проверяемость 0.20, простота эксплуатации 0.15.
Шкала 1…5; оценки — архитектурное суждение, не результаты бенчмарка.

- A: оценки 5, 4, 5, 3; взвешенно 4.40.
- B: оценки 2, 3, 3, 4; взвешенно 2.80.
- C: оценки 1, 1, 2, 2; взвешенно 1.35; дополнительно исключена жёстким гейтом.

## Sensitivity check

При независимом изменении каждого веса на ±20% с последующей нормировкой
A остаётся выше B и C. Даже без нормировки минимальная разница A−B равна
0.8×(0.35×3+0.30×1+0.20×2)−1.2×0.15 = 1.22 > 0.
Это устойчивость выбора слоя, а не подтверждение ресурсов или Read sandbox.
Risk acceptance F-002 уже получен; confinement не доказан. Нагрузочный
профиль и применимость HL-гейтов по-прежнему требуют evidence, их здесь нет.
Принятие риска не снимает обязательные меры и не превращает PoC в PASS.

## Decision

Предлагается A. Все пять решений ниже привязаны к verification_surface пакета.

### AD-001 — Декларативная мультимодальность DSH

Только в пользовательском YAML metadata всех моделей провайдера
`claude-p-bridge` объявить `input: [ text, image ]`, по F-01/F-02.
Это отдельная операция выката после квалификации работающего моста.
Не менять модельные ID, endpoint, auth, effort и остальные провайдеры.
Не создавать JS/Python loader, monkeypatch, module override или app.asar patch.
Файл профиля вне разрешённой области записи роли и вне materialization[].
Проверка: VER-001 и VER-012; повторное чтение YAML и diff только этих полей.

### AD-002 — Репозиторий как SSOT

Внести наш server.py и необходимый статический empty-mcp.json в
`bridges/claude-p-bridge/`, без логов, workspace, токенов и сессий.
Локальный legacy server.py — только источник миграции, после сверки SHA
не редактируется вручную. Core импортируется из репозитория или поставляется
как согласованный пакет с bridge server. Отсутствие core — отказ старта,
никакой встроенной запасной копии ToolCallParser.

Сохранить порт :9881, auth, model/effort routing, health и существующие
пути API. Не подключать Claude как новый backend хаба и не менять fleet
ради этой задачи. Перед переключением launchd сохранить manifest версий,
дождаться дренирования существующих ходов; параллельно старый и новый
слушатель на :9881 не запускать. Внешняя runtime-копия допустима только как
дословное развёртывание нашего кода по ADR 0011, не патч вендорской среды.
Проверка: VER-009, VER-011, VER-012.

### AD-003 — Вложения через workspace-read

Общая политика в core: принять только data URI с base64 PNG/JPEG, строго
валидировать кодировку и MIME/signature; не скачивать URL и не читать
file://. Имена генерируются мостом, пользовательские пути не используются.
Порядок [image N] един для всей истории; image-only сохраняет marker и
приглашение описать открытое изображение. Не возвращаться к PONG.

Владелец хода после admission создаёт `/tmp/claude-img-<uuid>/` атомарно
с 0700, без изменения глобального umask; файлы с 0600 и exclusive/no-follow
созданием. При частичной ошибке записи каталог тоже попадает под finally.
На macOS `/tmp` и `/private/tmp` учитывать при проверке canonical paths.
Файлы остаются до окончания CLI; затем завершить и reap только свою PGID,
закрыть трубы/дрейнеры и удалить весь созданный каталог вызовом
`shutil.rmtree` в outer `finally` на success/error/cancel. Владелец каталога
тот же, что у собственного дочернего процесса; чужие PGID/каталоги не трогать.
Сначала остановить читающего ребёнка, затем удалять; слот и байтовый резерв
освобождать также при ошибке удаления с явным privacy error.

При картинках передать `--tools "Read"`, `--add-dir <img_dir>`, использовать
img_dir как cwd для существующего шаблона `_messages_to_prompt(..., images)`
с относительными именами. Для текстового хода сохранить `--tools ""` и cwd.
Read — внутренний инструмент, его события не превращать в OpenAI tool_calls.
Обязателен жёсткий системный контракт: встроенный Read разрешён строго и
исключительно для фактических сгенерированных путей из секции [attachments].
Этот контракт действует и при request.tools=[]/tool_choice=none; нельзя
зависеть от наличия emulated tools или от пользовательской поддельной секции.
Промпт является эшелонированием, а не доказанным enforcement файловых прав.

**Граница безопасности:** tools Read ограничивает набор инструментов,
add-dir расширяет доступ; 0700 защищает от других UID, но не от того же UID.
Они НЕ ограничивают Read только этими файлами. Legacy содержит
bypassPermissions; запуск не является доказанной sandbox. F-002 закрыт
адресным решением OWNER_DECIDED / ACCEPTED_RISK владельца (§1): остаточный
риск чтения других файлов того же UID принят для локальной macOS-станции
при выполнении 0700/0600, add-dir, системного Read-only-[attachments] и
finally/shutil.rmtree с child ownership. Это не разрешение расширять доступ.
Q-002 CLOSED; VER-014 отдельно хранит owner risk decision и NOT_RUN оценку
confinement реальным benign canary. Отказ вне-dir не заявлен как проверенный.
Точные непроверенные permission-правила в argv не выдумываются.

Ни finally, ни Python не гарантируют cleanup после SIGKILL, os._exit или
падения ОС. Штатный SIGTERM должен вести через shutdown владельца ходов,
а не существующий os._exit(0). Для аварийных сирот нужен согласованный
startup recovery: удалять только каталог с ownership marker нашего моста,
доказанным отсутствием живого владельца (PID + start identity) и без
следования симлинкам. Без этого аварийная очистка остаётся непроверенной.
Проверка: VER-002, VER-003, VER-008, VER-014.

### AD-004 — Строгий поток и схемная санитизация

**ALWAYS-ON по адресному решению владельца §2:** использовать единственный
core.tool_emulation.ToolCallParser(strict_live=True) для всех выходов Claude:
SSE, JSON, tools отсутствуют/[]/tool_choice=none, terminal result fallback,
ошибка/отмена и EOF. Malformed/orphan guard и запрет raw fallback не зависят
от GigaRC, включая missing/false/true/stale/invalid snapshots.
Ни kill-switch, ни rollback новой фичи не отключает эту защиту. Его выходы — безопасный content и законченные
структурированные calls. В частности строгий режим выбран явно, а не
выводится из наличия SSE callback. Сохраняется дефолт legacy core для
других потребителей; глобально менять strict_live default нельзя.

Текст проходит через parser даже без request.tools: это исключает обход
защиты пустым tools/tool_choice=none. В таких ходах распознанный реальный
call — ошибка протокола, а не опубликованный/выполненный инструмент.
При emulate_tools разрешены только функции предоставленного набора с
соблюдением tool_choice. Аргументы проходят build_tool_schemas и
sanitize_tool_call ровно один раз на владельце маршрута. Не вызывать
приватный _loads_tolerant напрямую: это внутренняя политика общего парсера.
Не генерировать justification или новые значения аргументов.

Parser.feed/finish могут поднять LiveParserError. При любом исходе не
flush raw, не повторять parser.finish после ошибки и не подставлять result.
JSON до заголовков: существующий proxy_error HTTP 502. SSE после 200:
data error с type proxy_error, code 502, затем [DONE]; не обещать HTTP 502
после уже отправленных заголовков, не отправлять успешный finish_reason.
Предшествующие безопасные SSE-дельты отозвать нельзя. Клиент не должен
считать частичный набор инструментов успешно завершённым ходом.

Result fallback разрешён один раз лишь при отсутствии text deltas и calls,
успешном rc/result, отсутствии parser error. Он проходит свежий экземпляр
той же нормализации; неизвестный/битый tail не является основанием fallback.
Терминальные usage/result snapshots не переэмитят дельты. Stderr и служебные
stdout строки не являются ни content, ни reasoning; ошибки логируются без
сырых аргументов, изображений, stderr с секретами и путей пользователя.

Markdown inline/fenced code с буквальными тегами сохраняется согласно
существующему контракту core. Orphan `<arg_key>/<arg_value>` вне настоящего
tool_call существующий parser сам не покрывает: общая лексическая защита
должна задержать split-prefix и отклонить такое служебное семейство вне
Markdown-кода, не удаляя произвольный XML/HTML пользователя. Корпус F-29…F-32
обязателен; это не обещание отфильтровать любой возможный XML.
Проверка: VER-004, VER-005, VER-006, VER-009.

### AD-005 — Live reasoning на универсальном слое

Обязательный REQ-05 Real-time Live Reasoning реализуется универсально в
существующем `core/tool_emulation.py` по решению владельца §4. Отдельный
`core/stream_normalization.py` не предлагается. Внутренние сигнатуры выбирает
Coder после ARCH_GATE; политику нельзя дублировать в HTTP handlers/клиентах.
Трассировка: REQ-05 → AD-005 → CD-004 → VER-007. Схемная санитизация
сохраняется в REQ-04/AD-004. Тестовый файл tests/test_stream_normalization.py
может проверять этот существующий модуль и не задаёт новый product module.
Claude transport переводит stream-json thinking_delta/text_delta в события
общего нормализатора, оставаясь единственным местом знания vendor schema.
Нормализатор владеет tool parser, lexical routing reasoning и единым
ограниченным аккумулятором content/reasoning/calls для SSE и JSON.

В text-delta сначала определить opaque tool-call envelope и Markdown-code,
затем интерпретировать разрешённые reasoning tags только в обычном тексте.
Это единый лексический автомат с состояниями, а не последовательный regex
по всему документу: в состоянии reasoning встреченный tool_call не становится
внешним вызовом; в состоянии tool-call JSON встреченный think не переключает
канал. Открывающая конструкция, встретившаяся первой в обычном тексте,
определяет контекст до своего закрытия. Это проверяется в обоих направлениях.
Предлагаемый закрытый набор — `<think>`, `<thinking>`, `<analysis>` и парные
закрытия. Это новое проектное правило, не обнаруженный формат Claude.
Теги внутри JSON-строк аргументов и code не переключают reasoning state.
Вложенность поддержать стеком до согласованного лимита либо отклонять
контролируемой ошибкой; непарный close и EOF с незавершённым tag prefix
не сбрасывать в content. При EOF внутри открытого reasoning-body уже
доставленные мысли остаются reasoning, ход заканчивается protocol error.
Длинный body выпускается инкрементально, удерживается только префикс тега.

Нативное thinking — уже типизированный reasoning, его не подавать в
ToolCallParser и не исполнять встреченные там примеры tools. По умолчанию
выводить один источник reasoning на Claude content block: при наличии
native thinking не повторять его из финального assistant/result snapshot;
при текстовом tagged канале маршрутизировать его отдельно и сохранять
порядок событий. Не делать дедупликацию по совпадению текста: повторённое
слово может быть легитимной новой дельтой. Для native+tag дублей без
стабильной event identity не угадывать; corpus/правило выбора источника
фиксируются до approval (Q-004).

Обработка каждого нормализованного события сперва добавляет его к итогу,
затем синхронно уведомляет sink. SSE сериализует reasoning как
delta.reasoning_content сразу, до result/EOF; JSON использует тот же итог
в message.reasoning_content. Не генерировать мысли, если upstream их не дал.
Reasoning не подмешивать обратно в prompt следующего хода.

Границы очереди, pending parser state, stdout line, stderr, общего текста и
HTTP in-flight bytes должны быть конечны. Медленный sink не должен удерживать
stdout drain: ограниченная доставка с явным stream failure при переполнении,
без silent drop reasoning и без успешного неполного ответа. Политика текущего
моста — cancel при disconnect, не переносить detached semantics хаба без REQ.
Q-001 закрыт решением о DRAFT-маршруте неподтверждённых данных: конкретные
лимиты/units/scope/timeouts требуют GATE-HL перед approved/ARCH_GATE;
не подменять их числами другой задачи и не применять reported values как конфиг. Никаких автоматических повторных CLI ходов после call.
Проверка: VER-007, VER-008, VER-010.

## Evolution и Feature Flags

REQ-04 — адресное исключение владельца §2: strict_live=True, malformed/orphan
защита и запрет raw fallback ALWAYS-ON при всех состояниях флагов и во всех
выходах Claude. Дефолты остальных потребителей core не меняются.

Новые image и live reasoning возможности отдельно GigaRC default false:
предлагаются `CLAUDE_BRIDGE_IMAGES_ENABLED` и
`CLAUDE_BRIDGE_LIVE_REASONING_ENABLED`. Имена — проектное предложение, не факт
публикации. Существующий локальный атомарный FlagSource — только образец;
новых ключей/publisher пока нет. Q-003 CLOSED_DRAFT_ROUTING: настоящий
single publisher, путь/schema/namespace/expiry и владение публикацией должны
подтверждаться GATE-FLAGS до approved/ARCH_GATE; enable/kill-switch — живым
receipt до выката. Не заводить второго writer, env-подмену, SDK или новый poller.
Absent/false/stale/invalid снимок выключает только новые image/reasoning фичи.
ALWAYS-ON REQ-04 остаётся активным. False image не создаёт image workspace;
базовый strict pipeline остаётся вне optional disabled branch. Снимок фиксируется
на ход; следующий ход видит kill-switch без рестарта. REQ-05 обязателен как
результат после квалифицированного enable, default false не отменяет требование.

Порядок: DRAFT A2 → обязательные GATE-HL/GATE-FLAGS и повторное независимое
рассмотрение/proof → approved/ARCH_GATE → red regression → минимальная
реализация в репозитории → независимый verifier/full suite/кодовая панель →
согласованный safety-qualified bundle core+bridge и дренирование старого launchd
→ проверка REQ-04 при false флагах → публикация/квалификация новых фич
→ metadata DSH → живые повторные и параллельные ходы существующего чата.
Числа handoff и все будущие VER здесь REPORTED_UNVALIDATED / NOT_RUN;
проверка JSON-структуры и принятие риска не являются product PASS.

Rollback: сначала снять image capability DSH, выключить image/reasoning флаги
для новых ходов, дренировать активные с сохранением parser/файлов. REQ-04
остаётся ALWAYS-ON. Восстанавливать только целый safety-qualified bundle с
этой защитой; если такого предыдущего bundle нет, отключить/изолировать
Claude route. Не возвращать permissive/raw XML fallback. Не откатывать только
server или core, не удалять temp живых/чужих владельцев. Persistent DB
migrations/backfill отсутствуют: только ephemeral файлы и наш deployment,
история DSH не переписывается.

## Threat model и последствия

Активы: изображения/PII, prompt и reasoning, инструменты клиента, секреты
того же UID, process slots и память. Границы: DSH→HTTP, decoded bytes→FS,
FS→Read, stdout→normalizer→SSE/JSON. Prompt injection может заставить Read
открыть иной файл; этот остаточный same-UID риск адресно принят владельцем
в F-002 с обязательными мерами. Инструкция в prompt и add-dir не sandbox
и не доказательство отказа при adversarial Read. Base64/полиглот/URL/path traversal и ресурсные атаки отклоняются
до spawn и до бесконтрольной аллокации; сигнатура MIME не доказывает отсутствие
вредоносного декодера CLI. CLI обновления требуют повторной квалификации.

Положительные последствия: один парсер, единый итог SSE/JSON, переносимый SSOT.
Издержки: владение cleanup/recovery, проверка безопасности Read, бюджетирование
памяти при 20 MB запросах, новая совместная версия поставки. Неподтверждённые
NFR из handoff не превращаются в результаты измерений.

## Validation

Замороженные команды и бинарные expected outcomes находятся в
`architecture/architecture-packet.json:verification_surface` данного run.
Новые файлы тестов — планируемые выходы Coder, а не существующие зелёные тесты.
Чувствительность regression: старый bridge должен дать red на image-only,
malformed/split XML, JSON reasoning и live-before-result barrier.
Полный suite `pytest tests/ -v` обязателен после реализации. Живой сценарий
VER-012: существующий DSH чат, screenshot, image-only, текст+картинка,
повторные/параллельные ходы, reasoning до result, fault/cancel, факт cleanup.
Пока ни одна runtime-проверка этой архитектуры не выполнена.

## A2 — матрица решений и provenance

- RW-001: статус DRAFT, approval PENDING; Q-001/Q-003 CLOSED_DRAFT_ROUTING
  по отдельной текущей директиве A2, а не §§1–4 исторического решения.
  Неизмеренные NFR/HL и publisher/path не приняты молча; GATE-HL/GATE-FLAGS
  обязательны до approved/ARCH_GATE, все будущие VER — NOT_RUN.
- RW-002 / Q-002: OWNER_DECIDED / ACCEPTED_RISK F-002 (§1); обязательные меры
  перечислены в AD-003. Confinement не доказан; VER-014 не объединяет risk
  acceptance с результатом canary. Никакой product code этой ролью не изменён.
- RW-003: REQ-04/AD-004 ALWAYS-ON (§2) и самостоятельные default-false фичи.
- RW-004: ADR0012 ACCEPTED, коллегия архитекторов A7, единогласно3/3 (§3).
  Архитектурное принятие не равно успешному live deployment; receipt аналога
  отсутствует. Точные текущие core line refs/hash — EVD009/015/016/033/034/036.
- RW-005: REQ-05/AD-005/CD-004/VER-007 в core/tool_emulation.py (§4).
  JSON/SSE equality, reasoning до result/EOF, chunk boundaries, tool JSON/code
  opacity сохранены; санитизация аргументов осталась REQ-04/AD-004.

Исторический consensus/final-panel-verdict.md и ledger остаются ESCALATED:
архитектор не меняет голоса и не выдаёт ACCEPT. Новый gate/proof — отдельный этап.

Источник §§1–4: `.ai-team/runs/bridge-claude-img-junk-fix-20261031/handoff/owner-decision-arch-r1.md`, SHA-256 `f0431b5ba606d2cd2b8f291dd0e6106b10cad261966d39b37c56f06b218497bb`.

Текущая директива DRAFT/Q closure (parent-relayed owner quote): `.ai-team/runs/bridge-claude-img-junk-fix-20261031/architecture/owner-directive-a2.md`, SHA-256 `2877a6060ff17cf0d6348e063606fe29cc77519f804c94919fef507f13d74fff`.

Текущий baseline: `.ai-team/runs/bridge-claude-img-junk-fix-20261031/task.json`, SHA-256 `0e847c46b3bc97c39ea330f4a811ff961eaa0123b0a0de675ad5fd4540df7904` (байты не менялись).

Текущий `core/tool_emulation.py`, SHA-256 `89c99ee8e4bb8737eeebc859ddcb69c262842e4c44699eae48b33a22f20959cb`.

## Links

- `AGENTS.md` — универсальность и vendor zero-touch.
- `docs/adr/0011-universal-tool-call-argument-sanitization.md:AD-004` — SSOT/core.
- `analysis/bridge-claude-img-junk-fix/handoff-architect.md` — исходные NFR/HL-ENV.
- `analysis/bridge-claude-img-junk-fix/open-questions.md` — OPEN-01…OPEN-03.
- `architecture/architecture-packet.json` — authoritative draft и approval blockers.

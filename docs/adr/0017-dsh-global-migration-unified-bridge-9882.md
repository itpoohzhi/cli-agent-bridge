# 0017 — Миграция DSH на единый фасад cli-agent-bridge :9882 и отключение Droid

## Status

Accepted, revision A2, 2026-10-31. Критичность S3: миграция рабочего шлюза завершена консенсусом Архитектурного Совета Тимлидов. Пакет APPROVED для реализации Coder; exact model roster, memory limit 8 MiB и N/A статус K8s/GigaRC зафиксированы.

Автор: Architect, requested `gpt-6.1-sol`, high, native `collaboration.spawn_agent`; runtime actual model не раскрыта, `UNKNOWN`. Независимый reviewer не назначен. `panel-proof.json` отсутствует, ACCEPT не заявляется.

Целевой путь после отдельного ARCH_GATE и materialization: `docs/adr/0017-dsh-global-migration-unified-bridge-9882.md`. Сейчас файл находится только в `architecture/proposals/docs/adr/` текущего run. Запись в общий `docs/adr/INDEX.md` и любые runtime-изменения отложены.

## Y-формулировка

В контексте DSH Desktop/Web и рабочего универсального хаба `127.0.0.1:9882`, столкнувшись с разнесёнными endpoint и маршрутизацией через выведенный Factory Droid, проектируем единый клиентский фасад поверх существующих localhost upstream. Выбираем повторное использование `PassthroughAdapter`, сохраняя специализированные upstream-процессы и нативные Muse/Codex-маршруты, принимая дополнительный hop и необходимость доказать совместимость credentials, моделей и бюджета задержки до переключения клиентов.

## Context

Фактура аналитика — `evidence-ledger.md` [F-01]..[F-10] и `open-questions.md` OPEN-01..03 из `/tmp/cel-runs/dsh-global-migration-20261031/analysis/dsh-global-migration/`, дата 2026-10-31. Эти источники задают вход, но не являются доказательством живой приёмки новой схемы.

Коррекция baseline: сервер реализован `Handler(BaseHTTPRequestHandler)` (`server.py:3870`) и `Server(ThreadingHTTPServer)` (`server.py:6234`), а не FastAPI/Starlette из handoff. Нельзя переносить на него event-loop гарантии без адаптации к потокам, GIL и фактическим blocking I/O.

`core/backend_adapter.py:537-538` исключает модели выключенных backend из активного fleet-каталога; выключенный адаптер не создаётся registry (`:765-767`). Неизвестная модель отклоняется до upstream (`server.py:5294-5302`). Прокси требует exact model ID, а body/model/effort/tools передаются upstream до CLI effort clamp (`server.py:5304-5315`).

Включить `opencode-zen` недостаточно: fleet не содержит ни одной привязанной к нему модели. `/v1/models` строится из моделей активных адаптеров и порядка FLEET (`server.py:4987-5005`, `core/backend_adapter.py:649-662`), а не автоматически импортирует upstream discovery. Перед переключением нужны проверенные exact IDs для каждого разрешённого model/effort в трёх DSH provider-секциях. `allow_unknown` не предусмотрен; его добавление не является обходом этого gate.

### Scope и несовпадение понятия «глобальный»

Изменяемый на этой фазе набор DSH providers: ровно `claude-p-bridge`, `agy-bridge`, `opencode-zen-bridge` в `~/.dsh/profiles/desktop/cordis.patch.yml` и `~/.dsh/profiles/web/cordis.patch.yml`. Целевой baseURL у всех трёх: `http://127.0.0.1:9882/v1`.

Аналитический handoff также называет Muse/Codex. Muse уже подключён через хаб. Codex desktop использует :9882, но Codex web — :2455; совместимость его API, в том числе возможного `/v1/responses`, должна быть отдельно установлена до изменения. Само совпадение OpenAI-style имени провайдера совместимость не доказывает. Существующий default DSH — `opencode-go/deepseek-v4.1-flash` — отдельный маршрут, не legacy запись Droid. Он и его default/subagent-настройки не меняются этим ADR. Пока остаются провайдеры вне :9882, утверждение «весь DSH переведён на единый порт» недопустимо.

## Decision drivers

- Три явно названных providers обращаются к одному client endpoint; на backend-границе разрешён только localhost.
- Ни один новый запрос не исполняется через `droid`; `grok-4.7` и `glm-5.3` удалены из fleet; retired модели не возвращаются при rollback.
- Не нарушены существующие Muse/Codex model IDs, effort, tools, отмена и изоляция сессий.
- До cutover доказаны exact model coverage, корректная аутентификация и streaming/nonstream/tool semantics.
- NFR-Scale Card: 16 concurrent SSE, 20 req/s, routing overhead ≤0.002 s, process RSS ≤150 MB, JSON payload до 32 MB. Это требования, а не замеры.
- Все эксплуатационные лимиты, таймауты, интервалы, buffers и thresholds управляются поддерживаемой конфигурацией; константы в implementation не вводятся.

## Considered options

A. Использовать :9882 как фасад и оставить :9881/:9887/:9883 локальными специализированными upstream.
B. Сразу перенести все реализации адаптеров внутрь одного процесса :9882, используя только наш код.
C. Сохранить прямые подключения DSH к отдельным портам и лишь выключить Droid.

## Decision

Предлагается A, в соответствии с явным брифом и OPEN-01. B увеличивает объём изменения и связывает жизненный цикл upstream с хабом до доказанной необходимости. C не выполняет требование единого endpoint для трёх провайдеров. Vendor приложения, их модули, asar, binaries и overlays не меняются.

### AD-001. Фасад и границы ответственности

DSH владеет выбором provider/model и клиентским credential. Хаб владеет валидацией admission, exact fleet lookup и универсальной обработкой протокола. Passthrough остаётся единственным швом отправки исходного запроса в выбранный локальный upstream. Специфичные CLI особенности остаются у соответствующих адаптеров/мостов. Request-time discovery, чтение канона/каталога с диска на каждый chunk и vendor-specific patch в DSH не допускаются.

### AD-002. Целевой fleet

- `backends.droid.enabled=false`, `required=false`; запись backend может остаться для чтения исторических конфигов, исполняемых fallback к ней нет.
- Из `models` удалить exact IDs `grok-4.7`, `glm-5.3`.
- `claude-sonnet-5-5.backend=claude-p`; `gemini-3.8-flash.backend=agy`.
- `backends.claude-p`, `agy`, `opencode-zen`: `enabled=true`; base_url соответственно `http://127.0.0.1:9881/v1`, `http://127.0.0.1:9887/v1`, `http://127.0.0.1:9883/v1`.
- Fleet schema остаётся 3. Model-level `enabled` не добавлять: строгий parser имеет собственный allowlist полей. Объявления моделей выключенного backend не попадают в активный каталог.
- `deepseek-v4.1-flash`, пятый legacy Droid model, сохраняется только как неактивная историческая запись за выключенным backend; не рекламируется и не обслуживается. Переназначение на Zen или на ID `*-free` не разрешено молча: это изменение идентичности/контракта, а для SDLC допуска DeepSeek действует отдельное ограничение канона. Не путать эту запись с DSH default через `opencode-go`.
- Перед переключением сформировать конечный allowlist exact IDs/effort по пересечению DSH declarations и реальных `/v1/models` upstream. Включение backend без соответствующих моделей — ещё не выполнение требования маршрутизации. Не добавлять универсальный unknown-model forwarding.
- Zen cached catalog от 2026-10-31 13:42:49 содержит `glm-5.3-flash-free`. Нельзя автоимпортом вернуть retired семейство; exact fleet cleanup не доказывает глобальный policy compliance. Новый discovery/filter механизм требует отдельной спецификации scope, проверки и feature flag. Существующие upstream каталоги этим ADR не переписываются.
- Сохранить действующий fleet.default_model; он должен ссылаться на активный backend. При env MODEL_ID, указывающем на retired/disabled модель, startup должен fail closed, а не подменять модель незаметно.

### AD-003. Профили и alias coverage

Меняется только baseURL трёх явно названных секций. `apiKeyEnv`, model IDs, effort variants, allowedModels и default выбор остаются прежними до доказанной совместимости. Проверка coverage охватывает также скрытые deprecated aliases: если они нужны старым чатам, требуются точные безопасные routes либо явная ошибка до side effect. Нельзя обещать, что один base ID в fleet покрывает все `*-high`/`*-medium` IDs.

Union `/v1/models` не provider-scoped: DSH provider declarations/allowedModels должны ограничивать выбор и не давать несовместимый credential на нативный backend. Реальное поведение picker/discovery проверяется существующими рабочими чатами Desktop/Web; юнит-тест каталога его не заменяет.

### AD-004. Аутентификация без выдуманной трансляции ключей

У хаба уже есть fallback `BRIDGE_KEY -> DROID_DSH_BRIDGE_KEY` (`server.py:151-162`, `start.sh:30-43`). Это alias конфигурации одного server-side секрета, не гарантия приёма двух различных значений одновременно. Нельзя выводить из имени alias новый общий клиентский credential или обещать поддержку `CLI_BRIDGE_KEY`, которой не доказано.

Для native backend проверяется хабовый ключ. Для loopback passthrough существует узкое defer-правило (`server.py:688-695,5162-5166`); `Authorization` отправляется upstream без замены (`adapters/passthrough_adapter.py:674-682`). Adapter не имеет отдельного upstream-key env. Сохраняем этот baseline; используем имеющийся provider credential без значения в артефактах. Discovery `/v1/models` имеет отдельную проверку (`server.py:4967-4986`); POST проверяется независимо. Не расширяем defer на remote callers или native CLI, не добавляем permissive auth fallback. Нужны positive/negative tests с различными значениями hub/upstream keys и проверкой отсутствия request/hub credentials в логах и нерелевантных child env. Легитимные provider-auth переменные CLI не запрещаются и не меняются этим ADR.

### AD-005. Failure и lifecycle

Один request имеет один выбранный backend; скрытого перехода к другому вендору нет. Отказ отдельного upstream не должен делать недоступными уже работающие другие backend. Сохраняются baseline HTTP errors/admission semantics; overload и неизвестная модель отказывают до запуска CLI. После начала SSE статус HTTP не переписывается; ошибки оформляются по существующему протоколу без ложного нормального terminal.

Запросы с tools и незавершённые streams нельзя автоматически replay после переключения/сбоя: внешний tool side effect мог уже произойти. Для passthrough cancellation закрывает собственное соединение и освобождает budget/slot по try/finally; наличие detached upstream turn означает, что disconnect сам по себе не гарантирует остановку процесса — verifier обязан проверить поддерживаемую явную отмену. Нативный detached/resume контракт не меняется; нельзя убивать все процессы по имени или уничтожать старые чаты.

### AD-006. NFR и безопасность ресурсов

Точный measurement contract приведён ниже и в rollout plan. Существующее ядро буферизует ingress body и JSON, а SSE adapter парсит data frames; заявлять zero-copy или O(1) для полного 32 MB request нельзя. O(1) относится только к in-memory lookup, если это подтверждено. Основной риск — CPU/GIL и удерживаемая память, а не только localhost RTT.

Текущий admission: 32 MiB max_body, 64 MiB admitted raw body bytes, 32 HTTP connections. Это не memory RSS limit. У adapter по умолчанию другие пределы: 16 MiB body, 8 MiB accumulation, 32 MiB process budget на экземпляр adapter. При включении четырёх passthrough экземпляров бюджеты не становятся единым глобальным лимитом автоматически. До cutover согласовать конфигурацию max_body на каждом hop и суммарную стоимость buffers/JSON/streams.

Если одновременно принять и удерживать 16 полных payload по 32 MB, только raw body занимает 512 MB (при 32 MiB — 512 MiB), ещё до JSON, baseline RSS и response buffers. Текущий 64 MiB ingress admission не допускает такой одновременный набор; следовательно Nmax=16 и Smax=32 MB нельзя без уточнения считать одновременно гарантированными. Допустимые пути: сохранить bounded admission и согласовать отказ/очередь для больших bodies; либо проектировать отдельно bounded spool/stream parsing с доказанной памятью. Ни один путь не утверждён этим ADR, лимит RSS не увеличивается молча.

NFR units MB/MiB и percentile не зафиксированы источником; conservative gate до уточнения — RSS ≤150,000,000 bytes. Числа 32 MiB,64 MiB,16 MiB,8 MiB,32 MiB выше — факты действующей конфигурации/дефолтов, а не новые захардкоженные настройки.

### AD-007. Управляемый rollout

Новая runtime логика, если потребуется для каталогов, лимитов или policy, должна иметь remote GigaRC feature flag `*_ENABLED`, default false, мгновенный kill-switch и прежнее поведение до включения. Существующий backend.enabled остаётся административным hard filter, не доказательством реализации GigaRC. До Coder подтвердить имеющийся remote-config механизм и конкретный flag binding; новый GigaRC polling на chunk hot path запрещён. Если задача остаётся только конфигурационной миграцией существующих возможностей, feature gate всё равно должен быть явно согласован с каноном, а не молча заменён env.

При rollback не возвращать Grok/GLM/Droid. Для трёх migrated providers допустимо восстановить проверенные прежние прямые URLs к разрешённым upstream, сохранив policy-clean fleet; иначе fail closed для проблемного provider. Общий дамп старого fleet/profile нельзя восстанавливать без semantic policy check.

## Views

### Component view — кто владеет чем

DSH Desktop/Web отправляет exact model request в HTTP фасад :9882. Фасад проверяет вход и выбирает зарегистрированный backend. Native Muse остаётся внутри универсального runtime; Codex и три рассматриваемых upstream обслуживаются через passthrough. Claude :9881, AgY :9887 и Zen :9883 остаются loopback launchd сервисами. Никакие наши компоненты не пишут в vendor binaries/modules.

### Dynamic view — успешный ход и отказ

Клиент выбирает provider/model, читает свой credential из env и отправляет POST на :9882. Admission резервирует body bytes до чтения, JSON разбирается, exact model определяется в immutable snapshot каталога; применяются baseline auth rules. Выбранный passthrough отправляет исходный запрос конкретному upstream и отдаёт response/SSE через bounded response handling. На unknown/disabled model нет upstream call. На saturation нет бесконечной очереди; на abort освобождаются собственные ресурсы. Повтор после незавершённого tool turn — только после проверки terminal/idempotency владельцем.

### Deployment view — staged cutover

Upstream lifecycle не объединяется с хабом в этой фазе. Профили переключаются по одному после canary. Существующие streams завершаются на прежнем маршруте; новый запрос идёт в новый snapshot. Нет предположения, что runtime DSH автоматически перечитывает patch или что launchd умеет transactional reload fleet. Конкретный reload/restart и поведение существующих чатов должны быть доказаны runbook, до его появления deployment gate закрыт.

## Evaluation matrix

Решение единого endpoint задано владельцем, поэтому фальшивые измеренные баллы/веса не назначаются. Для A выполнение endpoint constraint предусмотрено и протокол уже существует; latency/memory неизвестны. Для B endpoint constraint выполним, но требуется новое объединение runtime и новая verification surface. Для C endpoint constraint не выполнен. NFR является hard gate для A и B, не весом, которым можно компенсировать нарушение памяти.

## Sensitivity check

При любой относительной важности удобства сопровождения вариант C остаётся несовместимым с явно требуемым endpoint. Если замер A не укладывается в overhead/RSS даже после корректной конфигурации, его нельзя принять по большинству качественных аргументов: нужны новые evidence и отдельный Architect delta для B или для уточнённого envelope. Изменение смысла T_budget, Nmax/Smax или RSS только после решения владельца. Нет результатов PoC; ADR остаётся Proposed.

## NFR measurement contract — proposal, не замер

- Разделить R0 (только auth/admission/catalog selection), R1 (вся локальная обработка bridge до upstream submit, включая decode/parse/validation/serialize) и R2 (локальная обработка каждого response/SSE frame). Измерять `perf_counter_ns`, отдельно CPU и wall, без времени генерации LLM и без сокрытия очереди/загрузки тела; transport RTT, client body ingress и admission wait показывать отдельными рядами. Основной ≤2 ms gate применять только после согласования boundary и percentile, не подменять R1 быстрым lookup R0.
- Предлагаемый статистический gate: p50/p95/p99 и maximum observed отдельно для successful/rejected/aborted, с консервативным требованием ≤2 ms для согласованного класса. Длительность, выборка, warmup и confidence фиксируются заранее в QA plan; источники пока их не задают.
- Нагрузка: до16 одновременно живых SSE, peak20 req/s, payload малый/обычный/32 MB, все три upstream и native Muse/Codex, slow-reader, partial frame, malformed JSON, saturation, cancellation и upstream timeout. Отклонённый 32 MB request нельзя считать успешным выполнением Smax.
- Измерить base RSS и peak process RSS при worst allowed concurrency, parsed JSON amplification, response buffers, threads, detached buffers и экземплярах adapter; бюджет 150 MB относится к процессу хаба, сумма upstream показывается отдельно. System-wide memory pressure не заменяет process RSS.
- При ThreadingHTTPServer event-loop tick N/A не утверждается голословно: HL-HCPU адаптируется к отсутствию async loop с import/call graph и code diff; GIL stall и worker scheduling измеряются отдельно.

## Threat model и pre-mortem

Активы: ключи hub/upstream, содержимое запросов/ответов, идентичность модели/provider, состояние рабочих чатов и внешние tool side effects. Trust boundaries: DSH→hub, hub→loopback upstream, native subprocess, отдельные чаты, конфиг→runtime.

- Пересылка неправильного provider key в другой backend: exact allowlist/route, отсутствие cross-provider fallback, негативные auth и отсутствие request/hub credentials в логах и нерелевантном child env; штатные provider-auth переменные не удаляются.
- Loopback exception становится remote bypass или открывает native CLI: адресная граница и независимые отрицательные тесты, без расширения существующего исключения.
- Retired IDs возвращаются через alias/discovery/rollback: hard eligibility до availability/fallback; проверка final active fleet и DSH allowed selection отдельно от upstream каталогов.
- Зависший upstream/slow reader удерживает память и slots: bounded config, admission до read, закрытие собственных ресурсов, нагрузочный fault injection.
- Повтор tool turn дублирует изменение: no automatic replay, сохраняется старый чат и terminal evidence.
- Миграция ломает существующие слоты при profile reload: drain и canary на тех же рабочих чатах, затем новые параллельные запросы; сохранение истории и route provenance.

Pre-mortem: green health скрывает upstream401; enabled Zen даёт404 из-за пустого fleet coverage; picker показывает модели другой credential-domain; 32 MB вход принимается хабом, но upstream leg отклоняет16MiB; body admission держится64MiB, а RSS превышает150MB из-за JSON/buffers; Codex Web отправляет Responses API в фасад только ChatCompletions; rollback возвращает запрещённую модель. Каждый сценарий соответствует frozen VER gate в packet.

## Consequences

Три явно заданных providers получают одну клиентскую точку входа и общий журнал маршрутизации без vendor patches. Цена — новый локальный hop, зависимость от хаба и необходимость согласованного каталога/credential mapping. Upstream процессы остаются отдельными, поэтому унификация порта не означает единственный daemon. Глобальная унификация всех DSH provider остаётся отдельным незакрытым scope decision.

## Rollout & Rollback Plan

Исполняемый порядок, stop-критерии и безопасный rollback приведены в `architecture/rollout-rollback-plan.md` того же run. План не запущен. Отключение legacy `com.user.dsh-muse-bridge` :9886 допускается только после отсутствия consumers и завершения текущих turns. Старые чаты, histories, vendor modules и секреты не удаляются.

## Validation

Фактически выполняется только проверка структуры draft packet и целостности bundle. Runtime тесты, профили, model calls, benchmarks и S3 architecture panel этой ролью не запускаются. Frozen команды: `pytest tests/test_fleet_v3.py tests/test_bridge_strict.py -q`; `pytest tests/test_passthrough_adapter.py tests/test_passthrough_routing.py tests/test_openai_passthrough.py -q`; `pytest tests/test_backend_contract.py -q`; полный `pytest tests/ -v` перед фиксацией изменений. Прежние тесты могут содержать legacy catalog expectations — их изменение относится к будущему Coder/QA и не выполняется здесь.

## Links и вопросы владельцу

Смежные ADR: `docs/adr/0002-multi-binary-hub.md` (Accepted в INDEX), `docs/adr/0015-universal-bridge-consolidation-and-dynamic-limits.md` (Proposed; не источник одобрения), `docs/adr/0014-zero-hardcode-configurability.md`. Jira не создавалась.

OPEN-01..03 сохраняются как continuable допущения: локальные upstream на фазе1, policy-clean disabled Droid и сохранение baseline credential env. Блокеры до rollout: exact profile/upstream model coverage; значение и проверяемая граница T_budget; совместимость Nmax/Smax/admission/RSS; недостающий HL environment; feature-control binding и rollout/reload mechanism; независимое S3 review и panel proof. Вопрос о Codex Web/opencode-go блокирует claim полной глобальной унификации, но не расширяет эту фазу автоматически.

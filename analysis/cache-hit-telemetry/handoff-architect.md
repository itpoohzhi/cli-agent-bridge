# As-Is пакет — REQ-CACHE-001

Владелец результата: архитектор и совет техлидов. Дата фактов: 2026-10-12. Тип исследования: standard As-Is и интерфейсный анализ. Передаются подтверждённые статические контракты и один live Factory Droid CLI completion с ненулевым cache-read [F-36]; повторный запрос, hit percentage, фактический UI и численные NFR остаются открытыми. Пакет не выбирает архитектуру и не является сдачей runtime telemetry.

REQ-001 — только формальный validation alias канонического REQ-CACHE-001 для SA-DOD-007: regex REQ-[0-9]+ не распознаёт канонический идентификатор. Это не новое требование.

## Происхождение и границы доказательств

Три read-only explorer и scaffold перед синтезом имели .done с exit=0 в `/tmp/cel-runs/cache-hit-telemetry-20261012-2326`. Для статического синтеза использованы только финальные agent_message из explore-agy.jsonl, explore-droid.jsonl и explore-clients.jsonl. Live-дополнение внесено после synthesis.done=0 и финального turn.completed предыдущего Coder: числовые поля [F-36] независимо сверены с private checker.jsonl и live-droid-verification.md; checker.done=0. Сырые сессии, prompts и секреты в пакет не перенесены. KB от 2026-10-09 не является доказательством текущего поведения.

[F-36] относится к Factory Droid CLI checker с моделью gemini-3.8-flash, не к agy и не к ответу любого из двух OpenAI мостов. Наблюдение: cache_read_input_tokens=19990, cache_creation_input_tokens=0, input_tokens=51407, output_tokens=13453, durationMs=96693, numTurns=2. Это один runtime completion: он не доказывает повторный запрос, процент cache hit, семантику cache creation, usage отдельного turn, RPC/HTTP/SSE либо отображение UI. Счётчики completion могут быть inclusive; охват getInclusiveTokenUsage остаётся OPEN-02.

Источники и даты каждого утверждения находятся в [evidence-ledger.md](evidence-ledger.md). Домашние пути заданы через `~/`; ASAR источники адресуют конкретный member установленного архива, строки внутри member. Три независимо перепроверенных статических источника: agy helper [F-04], proxy serializers [F-15] [F-16], repo bridge serializers [F-21]. Остальные статические факты получены из адресных исследований explorer; runtime из них не выводится. Отдельное runtime наблюдение [F-36] ограничено числовой проекцией одного CLI completion.

Elapsed плана — округлённое вверх время от birthtime JSONL до mtime .done: agy 3 минуты, droid 6, clients 5. Связанные INV одного explorer разделяют интервал, он не суммируется. Время последующего синтеза и числовой проверки уже завершённого checker не включено; durationMs=96693 [F-36] относится к completion checker, не к explorer. Ни один исследовательский timebox не превышен.

## As-Is system context

```mermaid
flowchart LR
  Client[DSH OpenAI client] -->|stream / include_usage: [F-25]| Agy[agy bridge]
  Client -->|stream / include_usage: [F-25]| Proxy[Droid proxy]
  Client -->|stream / include_usage: [F-25]| Bridge[Repo bridge]
  Agy -->|stream-json: [F-01]| AgyCLI[agy CLI]
  AgyCLI -->|result.usage: [F-02]| Agy
  Proxy -->|stream-json: [F-14]| DroidCLI[Droid CLI]
  DroidCLI -->|completion.usage: [F-11]| Proxy
  Bridge -->|stream-jsonrpc: [F-18]| DroidCLI
  DroidCLI -->|tokenUsage: [F-18]| Bridge
  Agy -->|normal / SSE usage: [F-06] [F-07]| Client
  Proxy -->|normal usage / SSE without usage: [F-15] [F-16]| Client
  Bridge -->|normal / conditional SSE usage: [F-21]| Client
  Client -->|terminal usage: [F-26]| Meter[DSH token meter]
  Meter -->|session buckets: [F-27]| UI[Client telemetry calculations]
```

Стрелки клиента показывают совместимые контрактные границы [F-25], а не доказательство выбранного endpoint в активном чате (OPEN-05). Proxy и repo bridge — два отдельных пути к Droid CLI [F-14] [F-18]; цепочка proxy → bridge в исследовании не установлена. Hermes известен только как конфигурационный потребитель chat_completions [F-34], его renderer остаётся OPEN-06. История и chat lock repo bridge [F-35] не доказывают provider cache hit.

## Инвентарь наблюдённых ingress/egress contracts

| Граница и направление | Протокол и схема | Normal | SSE / terminal | Доказательство |
|---|---|---|---|---|
| Клиент → OpenAI-compatible HTTP handler мостов, ingress | JSON chat request; stream и include_usage в клиентском коде | Отдельный normal serializer | Клиент предпочитает stream; usage читает до choice | [F-25] [F-06] [F-15] [F-21] |
| agy bridge → CLI, egress | stdin/stdout stream-json; stderr отдельно | event=result.result.usage | step_update usage не переносит | [F-01] [F-02] [F-03] |
| agy bridge → HTTP клиент, egress | chat.completion / SSE | Три usage ключа | stop, условный дополнительный usage stop, DONE | [F-04] [F-06] [F-07] [F-08] |
| Droid proxy → CLI, egress | droid exec -o stream-json | completion.usage dict | Terminal CLI usage сохраняется внутри proxy | [F-11] [F-14] |
| Droid proxy → HTTP клиент, egress | chat.completion / SSE data chunks | input/output/sum без cache | stop и DONE; usage не включён | [F-15] [F-16] |
| Repo bridge → Droid CLI, egress | stream-jsonrpc | agent_turn_completed.tokenUsage | RPC mapper сохраняет внутренние cache поля | [F-18] [F-19] |
| DroidAdapter → TurnResult, внутренняя граница | Usage DTO | Только input/output | Cache поля не входят в DTO | [F-20] |
| Repo bridge → HTTP клиент, egress | chat.completion / SSE | input/output/sum | finish и условный usage с непустыми choices | [F-21] |
| pi-ai → Harness projections, внутренняя клиентская граница | terminal usage event | input/output/total; positive cache fields | done/error usage перед finish | [F-26] [F-27] |

Подтверждённая точность инвентаря — схема usage и завершения, а не полный HTTP контракт. Владелец endpoint, auth, совместимость версий, idempotency, HTTP limits, retry/error policy и доступный тестовый контур остаются OPEN-09. Название OpenAI-compatible само по себе не подтверждает эти свойства. Для agy доступ к CLI даже через help оказался закрыт launcher guard [F-09]; inference или обход guard не выполнялись.

## Usage/cache модель и качество данных

Единица API-полей именуется tokens в преобразованиях; семантика реальных agy cache счётчиков не установлена (OPEN-01). Droid upstream handlers дают прямую связь cache-read с cached_tokens и отдельными Anthropic cache counters [F-12] [F-13]. Само имя cache_creation_input_tokens не означает «все misses»; охват getInclusiveTokenUsage не проверен (OPEN-02).

| Участок | Доказанная семантика | Missing / zero / null |
|---|---|---|
| agy HTTP usage | input → prompt; output+thinking → completion; upstream total отдельно; cache ключей нет [F-04] | Missing и numeric zero сходятся [F-05]; явный null не объявлен нулём, OPEN-08 |
| Droid CLI JSONL | completion.usage содержит отдельные read/create [F-11]; один live read=19990/create=0 [F-36]; upstream input может быть уже uncached [F-12] | Anthropic mapping сводит missing/null/zero к 0 [F-13]; не обобщать на все handlers или на происхождение счётчиков [F-36] |
| Proxy normal | input/output/sum без cache [F-15] | Missing → 0; null сохраняется None и не нормализован для суммы [F-17] |
| RPC mapper | input/output/read/create/thinking [F-18] | int кроме bool; missing/null/float/string → 0 [F-19] |
| Repo DTO/HTTP | DTO и output теряют cache [F-20] [F-21] | SSE при input=output=0 не имеет usage [F-21] |
| DSH OpenAI parser | Cache aliases и uncached subtraction [F-24] | Fallback cache read 0 не доказывает фактический miss |
| DSH adapter/meter | Positive-only cache, затем cumulative buckets [F-26] [F-27] | Protocol zero и отсутствие cache неразличимы после adapter; meter заполняет отсутствие 0 |
| Код DSH chat/context | Session ratio, Turn ratio и context formatting [F-28] [F-29] [F-30] | Нулевой denominator скрывает ratio; positive denominator/read=0 даёт 0% или 0.00%; incomplete projection даёт null |

Правила преобразования описывают установленный исходник; [F-36] подтверждает только числовые поля CLI completion. Отображение рабочего UI не наблюдалось. Capacity [F-31] и occupancy [F-32] — отдельные от cumulative usage величины. TTFT/tok/s вычисляются по клиентским событиям [F-33]; отсутствие отдельного timing поля не доказывает отсутствие этих расчётов. Compact задан в профиле [F-23], активный режим чата неизвестен (OPEN-05).

Модель данных пакета: CLI usage → внутренний usage → DTO/HTTP usage → клиентские buckets/projections. База данных, ERD, durable SSOT и retention telemetry не установлены и не вводятся. Ledger содержит только Internal схемы и обезличенные результаты команд; реальные prompts, session ids, содержимое сообщений и credentials исключены.

## Architecture drivers и риски

- Драйвер [F-04] [F-15] [F-20] [F-21]: upstream/internal cache поля и HTTP output имеют разные схемы. Риск — принятие общего token count за подтверждённый cache hit.
- Драйвер [F-07] [F-16] [F-21] [F-25]: клиент запрашивает stream usage, а три сервера по-разному финализируют его. Риск — недоступность telemetry на выбранном потоковом пути.
- Драйвер [F-12] [F-24]: Droid handler и клиент оба имеют uncached-input преобразования. Риск дальнейшего сопоставления — неверный denominator при неизвестной семантике input; это требует проверки, не доказывает двойное вычитание в нынешнем runtime.
- Драйвер [F-05] [F-13] [F-19] [F-26] [F-27]: преобразования стирают различия missing/zero/type. Риск — статистика «0%» интерпретируется как измеренный miss вместо отсутствующих данных.
- Драйвер [F-31] [F-32] [F-33]: capacity, occupancy, cumulative usage и timing имеют разные источники. Риск — соединение несопоставимых величин.
- Драйвер [F-09] и OPEN-01: нет актуального agy sample. Зависимая ветка определения agy cache семантики остановлена; статические контракты передаются независимо.

Архитектурных вариантов, выбора DTO, API расширения или порядка внедрения этот пакет не задаёт.

## NFR и качество

Один CLI completion имеет durationMs=96693 [F-36]; это длительность этого события, не p95/p99, TTFT или baseline рабочего сценария. Измеренных baselines RPS, объёма, TTFT, p95/p99, tok/s и cache ratio нет (OPEN-07). Формулы [F-33] не являются замерами. Timeout 1800 секунд [F-34] — значение конфигурации Hermes, а не фактическая latency или SLA. Численные целевые NFR в брифе не заданы; пакет их не придумывает.

Области quality scenarios для последующей работы архитектора: сохранность cache счётчиков на normal/SSE границах, честное unknown/zero, стабильная финализация stream, согласованный prompt denominator, повторные/параллельные рабочие вызовы. Для каждой baseline=unknown и threshold=owner decision; это области дальнейшей проверки, не новые требования и не AC.

## Mapping в architecture-packet.json

| Поле | Передаваемый вход | Ограничение |
|---|---|---|
| evidence | [F-01]–[F-36] с точным source и 2026-10-12 | F-01..35 — code/config и версии/help; F-36 — один CLI completion, без выводов о bridge/UI |
| blocking open questions / approval_required | OPEN-01 | Cache семантика agy не передаётся как установленная |
| open questions / assumptions | OPEN-02–OPEN-09 и явные допущения реестра | Допущения ограничивают утверждения; не подтверждают runtime |
| boundaries / contracts | Инвентарь ingress/egress, [F-01] [F-02] [F-14] [F-18] [F-20] [F-25] [F-26] | Proxy и bridge отдельны; unknown contract metadata — OPEN-09 |
| quality scenarios | Темы проверки выше; [F-07] [F-16] [F-21] [F-24] [F-33] | baseline неизвестен, OPEN-07; пороги не назначены |
| risks | Риски потери полей, отсутствующего usage, denominator и unknown/zero | Каждое основание привязано к ledger или OPEN |

## Статус передачи

ПРОВЕРЕНО ЛЁГКИМ: статический синтез, три независимых source spot checks, структурная проверка четырёх документов и SA-DOD-001..008; независимая числовая jq сверка [F-36] и checker.done=0.

ПРОВЕРЕНО ТЯЖЁЛЫМ: один ранее завершённый live Factory Droid CLI checker gemini-3.8-flash с rc=0 и read=19990 [F-36], числовая проекция независимо сверена. Это не проверка существующего рабочего чата владельца, HTTP/SSE мостов или UI; тяжёлый путь сдачи telemetry остаётся незавершённым.

НЕ ПРОВЕРЕНО: OPEN-01..OPEN-09; provenance и границы накопления CLI счётчиков, семантика creation, per-turn usage и hit percentage; повторные/параллельные рабочие вызовы; HTTP/SSE мостов; активный UI; NFR baseline. INV-02 остаётся open из-за этих границ, а не из-за отсутствия положительного live sample. Runtime результат не сдан. Ветка agy cache семантики остаётся у владельца/архитектора до ответа OPEN-01.

Связанные документы: [research-plan.md](research-plan.md), [evidence-ledger.md](evidence-ledger.md), [open-questions.md](open-questions.md). Независимые explorer чтения шли параллельно; синтез — после всех назначенных .done. Этот Coder проверил уже полученный CLI completion [F-36], не запускал дополнительные CLI inference, тесты продукта, build или сетевые вызовы; долгих jobs и новых scratch файлов не создавал.

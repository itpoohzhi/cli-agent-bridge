# Пакет приёмки Совета Тимлидов (`teamlead/package.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `4`)

Примечание по составу пакета (`acceptance-package.md` §3, `council.md` §3 «Diff-scope повторного цикла»): `reviewer.json` не создаётся (`reviewer_skip=true`, `downstream_panel=true`, Совет Тимлидов — единственный рубеж ревью). Все первичные артефакты ниже (включая полный актуальный `candidate.diff` от `origin/dev`, в который полностью входит и новый файл `tests/test_realtime_reasoning.py`, а также вывод `panel-rework-summarizer` `handoff/panel-rework-brief.json`) приложены без обрезки в побайтных обёртках D9.

## 1. Конверт задачи (`goal.md`, `task.json`, `handoff-architect.md`)
<<<ARTIFACT /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md sha256=4d953bef55831514175b6bf4150dc2af3bef47489913b6dccc2d536df6c83528
# Цель: Реалтайм-стриминг размышлений (reasoning) и шагов DeepSeek через мост opencode-zen-bridge в DSH

- Открыто: 2026-10-25 22:24:20 MSK
- Репозиторий (изолированный клон): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning` (ветка `feature/zen-realtime-reasoning` от `origin/dev`)
- Контур: `cel` + `analyst-teamlead` (`system-analyst` → `architect-software-product` → `Arch Panel` 3 судей → `Coder` → `Clean-Room L2` → `Code Council` 3 судей → открытый PR в `dev` + живая проверка тяжёлым путём).
- Бизнес-результат и критерий приёмки:
  1. При запуске DeepSeek (`deepseek-v4.1-flash-free` High) через `opencode-zen-bridge` в DSH Desktop размышления (`reasoning_content` / блок `Think`) и прогресс шагов стримятся в реалтайме по мере генерации, без «немой» паузы `Deep diving for 35s ...`.
  2. Полный цикл `analyst-teamlead` пройден с двумя `PANEL PROOF` (`verify_panel_proof.py` exit=0, `panel-proof.json` PASS на `arch` и `code`), всеми L1/L2 проверками (`ruff`, `basedpyright`, `pytest`) и открытым PR в `origin/dev` (без merge).
  3. Проведена живая проверка тяжёлым путём на реальном мосту и DSH.
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json sha256=7a9f099ff2203096bbd55aeded260bc6ed55066d114abb4d4c7651563a497f5b
{
  "task_id": "zen-realtime-reasoning",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "preset": "analyst-teamlead",
  "setup": "default",
  "criticality": "S2",
  "architecture_gate": {
    "packet_sha256": "88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b",
    "verification_surface_sha256": "4886ffa8669391618891b8e180a3443879043711da25bfe909bb6887ea6b924f",
    "protected_paths_sha256": "98f7f5f54622baf379b40bad458cf3ef2a1952644fb79fb662ebe11f70659d8b"
  },
  "teamlead_cycle": 4
}
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/handoff-architect.md sha256=9cd426324b8f49ddc760e3706e200709754a0a459b9e234f7b45b3b2669c6d9f
# Handoff to Architect: реалтайм-размышление и отзывчивость `opencode-zen-bridge` (zen-realtime-reasoning)

Дата: 2026-10-25 (MSK). Автор: System Analyst (Stage 1). Потребитель: `architect-software-product` (Stage 2, класс S2, вход в разработку только через ARCH_GATE).
Факты — в `evidence-ledger.md` (`F-01..F-49`), вопросы — в `open-questions.md` (`OPEN-01..OPEN-17`, блокеров нет), план — в `research-plan.md`.
Архитектура и стек здесь не выбираются: варианты сравниваются по фактам, решение за Архитектором.

## 1. Постановка и цепочка корневых причин

Запрос владельца: видеть размышление DeepSeek в DSH в реальном времени при работе через `opencode-zen-bridge` (`127.0.0.1:9883`) и получить высокую
отзывчивость. Инцидент-образец — `session-423ca27f`, ход 2 шаг 5 (22:16:12 MSK): на экране только «Deep diving for 35s ···», затем более 780 с без единого токена (F-30, F-33).

Подтверждены три независимые причины; устранять надо все три, иначе пользователь по-прежнему не увидит «процесс идёт».

| Код | Причина | Ключевые факты |
|---|---|---|
| RC-1 | `opencode run --format json --thinking` v2.1.2 подписан только на `session.reasoning.ended` и `session.text.ended` и игнорирует `*.delta`: размышление и текст приходят одним блоком в самом конце шага (разница 0.00-0.17 мс), тишина stdout 1.9-2.7 с даже на здоровом вызове. Мост не может показать то, чего CLI не выдаёт | F-17, F-18, F-02, F-05 |
| RC-2 | Нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками; единственный потолок — `TIMEOUT_S=1800` с; холодный `--standalone` на БД 2.27 GB, пул ProxyRack и сериализующий `_StartupGate` дали зависания 780-856 с, а keepalive `{"content":""}` держал сокет DSH пустым | F-09, F-10, F-28, F-30, F-31, F-32, F-04 |
| RC-3 | В DSH строка `⚛ Think` не рисуется, пока нет непустого `reasoning_content`; пустые keepalive ничего не показывают; inline-превью свёрнутой строки обновляется только по завершённому абзацу (нужен `\n`) | F-36, F-37, F-04 |

Цепочка следствий: RC-1 лишает реалтайма здоровый вызов, RC-2 превращает больной вызов в многоминутную тишину, RC-3 делает любую тишину
для пользователя неотличимой от зависания (экран с таймером без содержимого). Реалтайм-транспорт без пунктов RC-2 и RC-3 проблему не закрывает.

## 2. As-is карта потока (каждая связь — факт)

```
DSH (pi-ai openai-completions, stream:true)  --HTTP SSE-->  Handler._stream_sse (:9883)        F-35, F-03
  Handler._stream_sse: 200+role-chunk -> _StartupGate -> spawn `opencode run ... --format json`  F-03, F-10, F-01
  opencode run (stdout JSON lines) -> _StdoutFeed(queue 4096) -> parse_opencode_event            F-14, F-02
     reasoning -> delta.reasoning_content (flush сразу)                                         F-05
     text      -> ToolCallParser.feed -> delta.content / delta.tool_calls                       F-05, F-06
     keepalive -> {"content": ""} раз в 15 с тишины                                              F-04
  opencode run --standalone -> opencode serve --stdio (дочерний) -> georouter :10830 -> Zen      F-30, F-26, F-27
  Пул ProxyRack: следующий порт на каждый spawn (env HTTP(S)_PROXY, loopback мимо)              F-15
DSH UI: непустой reasoning_content -> blockIsVisible -> ReasoningRow (превью по "\n")            F-36, F-37
DSH реплей: thinking -> assistant.reasoning_content -> мост игнорирует                          F-38, F-07
```

Граница совместимости (факт): всё ниже `parse_opencode_event` оперирует кортежами `(etype, payload)` (F-02, F-05); поэтому любой транспорт,
сводимый к тем же кортежам, не требует правки верхнего слоя (ретраи, парсер инструментов, usage, SSE-кадрирование).

## 3. Требования `REQ-001..REQ-020`

Приоритет `MUST`/`SHOULD`; критерии `AC-*` — краткие проверяемые формулировки (полная спецификация живёт в requirements и в `handoff-qa.md`).

| REQ | Приоритет | Требование | Факты | AC |
|---|---|---|---|---|
| REQ-001 | MUST | Дельты размышления и текста уходят клиенту по мере прихода из апстрима, а не в конце шага | F-17, F-18, F-19 | AC-001: на клиентском сокете интервал между соседними `reasoning_content`-чанками меньше 500 мс, пока апстрим-стрим ещё идёт; AC-002: накладные расходы моста между приходом дельты и записью в сокет не больше 250 мс |
| REQ-002 | MUST | Публичный контракт не меняется: `/health`, `/v1/models`, `/v1/chat/completions`, формат OpenAI SSE, `finish_reason`, `usage`, порт :9883 | F-35, F-34 | AC-003: побайтовое совпадение формы чанков с текущей на наборе существующих тестов формата |
| REQ-003 | MUST | Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch (имя переменной и дефолт задаёт Архитектор); существующие тесты на fake-CLI остаются зелёными | F-43, F-40, F-42 | AC-004: при выключенном новом транспорте проходят все 378 существующих тестов (после решения OPEN-04) |
| REQ-004 | MUST | Первая видимая реакция моста в течение 1.0 с после открытия SSE: непустой `reasoning_content`, оканчивающийся `\n` (статус подключения/ожидания модели), независимо от состояния апстрима | F-36, F-37, F-04, F-33 | AC-005: первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса даже при полностью молчащем апстриме |
| REQ-005 | MUST | Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее | F-37, F-38, F-07, F-39 | AC-006: объединённый `reasoning_content` без статусных строк побайтово равен тексту модели; AC-007: `_messages_to_prompt` не содержит статусных строк при реплее |
| REQ-006 | MUST | Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку | F-09, F-30, F-31 | AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с |
| REQ-007 | MUST | Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с); пороги настраиваются переменными окружения | F-09, F-19, F-32 | AC-009: пауза больше порога после первого токена приводит к остановке и классификации `stall_timeout`; AC-010: порог первого токена даёт `first_token_timeout` |
| REQ-008 | MUST | Отсутствие осиротевших процессов: при отключении клиента, таймауте и watchdog убивается вся группа (включая дочерний `opencode serve`); отключение клиента обнаруживается не позже 5 с | F-14, F-30, F-33 | AC-011: после закрытия клиентского сокета процессы группы отсутствуют не позже чем через 7 с; AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится |
| REQ-009 | MUST | Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter и Circuit Breaker сохраняются; повторы по watchdog считаются в общий потолок; при повторе после отданного размышления вставляется отдельная статусная строка | F-11, F-12 | AC-013: суммарно не более 3 запусков на запрос при любой комбинации причин; AC-014: размышление не дедуплицируется, между попытками ровно одна статусная строка |
| REQ-010 | MUST | `ToolCallParser` на потоковых дельтах: текст вне тегов выдаётся инкрементально (удерживается не более `len("<tool_invoke>")-1` символов хвоста и открытый блок), блоки `<tool_call>`/`<tool_invoke>` не попадают в `content` при любом разбиении на дельты | F-06, F-05 | AC-015: перебор границ чанков на фикстурах существующих тестов даёт тот же набор `tool_calls` и тот же `content`, что при подаче целым текстом |
| REQ-011 | MUST | Завершение шага с вызовом инструмента останавливает процесс или сессию и даёт `finish_reason="tool_calls"`; детектор оборванного шага (`STEP_RECOVERY`), классификация `etype=error` и маркеры `_INTERRUPTED_RE` работают на накопленных данных потокового пути | F-05, F-11, F-43 | AC-016: все сценарии `test_step_interruption.py` проходят на новом транспорте с фейковым потоком дельт |
| REQ-012 | MUST | Встроенные инструменты `opencode` на новом транспорте запрещены (политика `deny` для всех) либо эквивалентно изолированы; события встроенных инструментов приводятся к текущему внутреннему виду (`tool_use`, unmapped, native) | F-08, F-22, OPEN-07 | AC-017: фейковый поток с событием встроенного инструмента даёт тот же `unmapped`-повтор и тот же `finish_reason`, что legacy-путь |
| REQ-013 | MUST | Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SPAWN_RATE_PER_S`, bulkhead слотов и Circuit Breaker действуют и для нового транспорта | F-10, F-11, F-15, F-32 | AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`) |
| REQ-014 | SHOULD | `usage` собирается из токенов завершения шага нового транспорта и совпадает по полям (`input`, `output`, `cached`, `reasoning`) с текущим | F-19, F-02 | AC-019: поле `usage` финального чанка совпадает с эталонными значениями фикстуры |
| REQ-015 | MUST | Секреты не пишутся в логи и артефакты: пароль `opencode serve` (случайный на процесс), ключи, креды прокси; применяется существующее маскирование | F-21, F-27 | AC-020: `bridge.log` после прогона не содержит пароля serve и значений `apiKey` |
| REQ-016 | MUST | Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода | F-32, F-30 | AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST` |
| REQ-017 | SHOULD | Базовая линия тестов приводится в зелёное: два теста ждут 4 запуска при потолке 3, третий страдает от общего `_RetryBudget` на класс | F-45, F-46, F-47, F-48, F-49 | AC-022: `uvx pytest -q -p no:cacheprovider tests/` без красных; AC-023: результат не зависит от порядка тестов |
| REQ-018 | MUST | Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается | F-16 | AC-024: `test_google_direct.py` проходит без правок |
| REQ-019 | SHOULD | Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием и проверяется сверкой | F-34, OPEN-17 | AC-025: побайтовое совпадение после деплоя |
| REQ-020 | MUST | В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете при ещё идущем апстриме (сейчас таких тестов нет) | F-44 | AC-026: тест красный на текущем коде и зелёный на новом (red to green) |

## 4. Варианты реализации RC-1 (сравнение по фактам, без выбора)

Вердикты: `выполнимо` / `выполнимо с условиями` / `невыполнимо`. Исходные данные по каждому — в ledger.

| Вариант | Суть | Задержка и реалтайм | Авторизация, маршрут, ротация IP | Изоляция встроенных инструментов | Параллелизм и SQLite | Тестируемость | Вердикт |
|---|---|---|---|---|---|---|---|
| L: только упрочнение legacy | `opencode run` остаётся, добавляются watchdog (REQ-006..008), статусные строки (REQ-004, REQ-005) | Реалтайма размышления нет: единый блок в конце шага (F-17, F-18); живость только за счёт статусных строк моста | Без изменений (F-15) | Без изменений (F-08) | Холодный spawn на каждый шаг сохраняется (F-28, F-30) | Полная: fake-CLI (F-43) | выполнимо; закрывает RC-2 и RC-3, но не RC-1 |
| A1: `opencode serve` короткоживущий на запрос, SSE `GET /api/event` | Мост поднимает `serve` на свободном порту с одноразовым паролем, создаёт сессию, шлёт prompt, читает дельты, затем `interrupt`/`DELETE` и `killpg` | Дельты размышления каждые 105-304 мс (median 127), первая дельта 1811 мс, text-дельты median 114 мс (F-19); старт сервера 109 мс (F-20) | Пароль случайный на процесс (F-21); env прокси задаётся на запуск, значит ротация сохраняется (F-15, OPEN-06); egress идёт через georouter (F-26, F-27) | Поле `permissions` в `POST /api/session` и `permission {"*":"deny"}` в конфиге (F-22), поведение не прогнано (OPEN-07) | Один процесс на запрос, idle RSS 152 MiB (F-20); БД та же 2.27 GB, нагрузка не мерилась (OPEN-08) | Нужен фейковый serve-сервер и адаптер событий; fake-CLI покрывает только legacy-путь (F-43) | выполнимо с условиями (OPEN-06, OPEN-07, OPEN-08) |
| A2: общий управляемый `opencode serve` (демон) | Один долгоживущий процесс; сессия на запрос | Те же дельты (F-19); нет холодного старта (фоновый `serve --service` уже работает, F-20) | Один набор env прокси на все запросы: общий IP упирается в дневной лимит (F-23, F-32); пароль на демон | Как в A1 | Общая БД и общий процесс, RSS 439 MiB у существующего демона (F-20); падение демона роняет все запросы | Тот же фейковый сервер; нужен супервизор и перезапуск | выполнимо с условиями; ротация IP не сохраняется без доработки (OPEN-06) |
| B: прямой OpenAI-совместимый HTTP-SSE к Zen | По образцу Google Direct (F-16): `http.client`, `readline`, дельты `reasoning_content` в реальном времени | Минимальная: без CLI, без БД, дельты как у апстрима (георутер отдаёт реалтайм, F-19) | Анонимный вызов без заголовков дал 429 `FreeUsageLimitError` напрямую и через пул (F-24, F-25); нужные заголовки или ключ неизвестны (OPEN-05); у `opencode` провайдера нет `apiKey` (F-27) | Не требуется: инструментов нет, эмуляция через `<tool_invoke>` остаётся | Нет SQLite и дочерних процессов | Лучшая: подмена HTTP-сервера, без `FAKE_OPENCODE` | выполнимо с условиями; осуществимость не доказана (OPEN-05) |
| C: гибрид | Приоритетный быстрый транспорт (A1 или B), при `ServeUnavailable`-подобном отказе тихий откат на legacy `opencode run`, как в muse-bridge | Реалтайм там, где транспорт доступен; legacy при отказе | Совмещает ограничения выбранных транспортов | Совмещает | Совмещает | Прецедент в репозитории: serve основной, exec запасной (F-40, F-41); fake-CLI тесты остаются на legacy-пути | выполнимо; объём работ максимальный |

Наблюдения для решения (факты, не выбор):
- Только A1/A2/B дают реалтайм на здоровом вызове; L не даёт, но самый дешёвый и закрывает RC-2/RC-3 (поэтапная поставка возможна: L затем A1/B/C).
- Квота Zen исчерпана на момент анализа (F-23): живая приёмка и PoC варианта B возможны после сброса около 03:00 MSK 2026-10-26.
- Совместимость с тестами: muse-bridge сохраняет exec-путь как резерв (F-40); у `opencode-zen-bridge` три модуля подменяют `OPENCODE_BIN` скриптом с событиями формата `run --format json` (F-43).
- Размер объёма ретраев и `_StdoutFeed` уже рассчитан на потоковые события (F-14); `step_finish` в `run` теряется (F-18), в serve есть `session.step.ended` с `tokens` (F-19).

## 5. Инвентарь контрактов (as-is)

| Интерфейс | Протокол | Направление | Аутентификация | Лимиты и режимы отказа | Тестовый контур |
|---|---|---|---|---|---|
| `POST /v1/chat/completions` моста | HTTP SSE OpenAI (`stream:true`, `include_usage`) | Ingress от DSH | Bearer-ключ моста (значение не фиксируется) | слоты 6, ожидание 15 с, 12 ждущих, 503 при переполнении (F-13) | `tests/_http.py`, `test_step_interruption.py` (F-43) |
| `opencode run --format json` | stdout JSON-строки | Egress процесса | Нет (локальный CLI, белый список env) | потолок 1800 с, нет watchdog (F-09) | `FAKE_OPENCODE` (F-43) |
| `opencode serve` v2 | HTTP + SSE, Basic `opencode:<пароль>` | Egress | случайный пароль на процесс или `OPENCODE_SERVER_PASSWORD` (F-21) | старт 109 мс, API по OpenAPI (F-20, F-22) | тестового фейка нет |
| `model_georouter` :10830 | OpenAI-совместимый HTTP | Egress | нет у провайдера `opencode` (F-27) | `headers_timeout` 120 с, `inactivity_timeout` 300 с, 80+80 слотов, 3 pre-send повтора (F-26) | нет |
| Zen upstream `opencode.ai/inference/openai/v1` | OpenAI SSE | Egress | анонимный, дневной лимит (F-23..F-25) | `FreeUsageLimitError` 429 с `Retry-After` | нет |
| DSH `openai-completions` | SSE потребитель | Ingress | — | `streamIdleTimeoutMs` 1900000, `maxRetries` 0 (F-35) | живой DSH |

## 6. NFR-набросок (наблюдаемые величины)

- Нагрузка: 517 завершённых запросов за день, `deepseek-v4.1-flash-free` 44 (median 7.10 с, max 85.65 с) (F-32); пик параллелизма 6 (F-13).
- Задержка legacy: `step_start` 1.3-2.5 с, весь ответ 3.3-5.2 с одним блоком (F-17); реалтайм-путь serve: первая дельта размышления 1.8 с (F-19).
- Хвост: два запроса молчали 780-856 с с `out_chars=0` (F-30, F-31); `startup_gate_timeout` 72 за день (F-32).
- Ресурсы: мост RSS 22 MiB, 36 дескрипторов (F-29); idle serve 152 MiB, 20 дескрипторов (F-20); БД 2.27 GB (F-28).
- Цели отзывчивости владельцем не заданы числами (OPEN-11); рабочие значения: первая видимая строка до 1.0 с, первая дельта размышления до 3.0 с, пауза до 15 с, молчание до 20 с.

## 7. Конверт `HL-ENV/v1` (46 канонических полей `REQUIRED_HL_ENV_FIELDS`)

Единицы СИ. Источники в комментариях; значения, не измеренные под нагрузкой, помечены `оценка`.

```yaml
schema: HL-ENV/v1
required_hl_env_fields_46:
  P_steady: 1                      # один локальный демон LaunchAgent, F-34
  P_hpa_max: 1
  maxSurge_pct: 0.0
  maxSurge_abs: 0
  maxUnavailable_pct: 0.0
  maxUnavailable_abs: 0
  P_terminating_overlap: 0
  P_live: 1
  P_avail_min: 1
  W: 1                             # один Python-процесс ThreadingHTTPServer, F-12
  N_proc: 1
  N_proc_steady: 1
  N_proc_avail_min: 1
  CPU_limit_per_pod: 2.0           # бюджет рабочей станции, оценка
  kappa_skew: 1.0
  u_bg_worker: 0.02                # оценка
  U_pod_sidecars: 0.25             # дочерние процессы opencode, оценка
  Mem_limit_per_pod: 2147483648    # бюджет демона 2048 MiB, оценка
  Mem_rss_worker_max: 67108864     # 64 MiB; измерено 22 MiB, F-29
  Mem_shared_max: 1207959552       # 6 дочерних процессов по 192 MiB; idle serve 152 MiB, F-20
  RPS_peak: 0.2                    # 517 запросов за день, F-32
  A_max: 3                         # MAX_TOTAL_SPAWNS, F-11
  SLA_p99_s: 180.0                 # max наблюдаемый 85.65 с, F-32
  N_entities_max: 64
  Limit_dep_share_d: {georouter: 80, opencode_local_db: 10}   # georouter F-26; значение БД допущение эталона, OPEN-08
  Limit_dep_rps_d: {opencode_spawn: 1.0}                      # SPAWN_RATE_PER_S, F-11
  W_fetchers_d: 1
  J_init_s_d: 12.0                 # STARTUP_GATE_S, F-10
  J_pod_s_d: 12.0
  T_poll_s_d: 15.0                 # KEEPALIVE_INTERVAL_S, F-04
  K_calls_d: 1
  T_base_s_d: 0.5                  # RETRY_BACKOFF_BASE_S, F-11
  T_cap_s_d: 2.0                   # RETRY_BACKOFF_CAP_S, F-11
  Max_stale_age_s_c: 0.0           # кэшей нет
  Min_healthy_ratio: 1.0
  B_retry_max: 6                   # RETRY_BUDGET_MAX, F-11
  min_reserve_retry_rps: 0.05      # RETRY_BUDGET_RESERVE_RPS, F-11
  FD_worker: 128                   # измерено 36 при active=0, F-29; запас под 6 потоков
  ulimit_n: 65536                  # launchctl limit maxfiles, F-29
  lambda_new_conn_per_pod_s: 0.6
  C_active_in_scope_s: 12
  N_pods_in_scope_s: 1
  Port_range_size_s: 16384         # эфемерный диапазон 49152-65535
  T_hold_s_s: 60.0
  SNAT_ips_count_s: 1
  HOTPATH_MODULES: "bridges/opencode-zen-bridge/server.py"
operational_profile:
  threads_per_worker: 12           # до 6 обработчиков и до 6 читателей stdout/SSE
  stdout_queue_max: 4096           # F-14
  ttft_visible_target_s: 1.0       # допущение, OPEN-11
  ttft_first_delta_target_s: 3.0   # допущение, OPEN-11; наблюдение serve 1.8 с, F-19
  first_event_watchdog_s: 20.0     # допущение, OPEN-11
  first_token_watchdog_s: 60.0     # допущение, OPEN-11
  stall_watchdog_s: 60.0           # допущение, OPEN-11
  client_gone_detect_s: 5.0        # допущение; сейчас 24.4 с, F-33
  keepalive_interval_s: 15.0       # F-04
  total_deadline_s: 1800           # TIMEOUT_S, F-09
  max_total_spawns: 3              # F-11
  startup_gate_s: 12               # F-10
  startup_wait_s: 5.0              # F-10
  bulkhead_max_concurrent: 6       # F-13
  slot_wait_s: 15.0                # F-13
  slot_max_waiters: 12             # F-13
  graceful_stop_s: 5               # SIGTERM затем SIGKILL, F-14
  serve_ready_s: 0.109             # F-20
```

Замыкание памяти (`HL-ENV-01`): `W × Mem_rss_worker_max + Mem_shared_max = 64 MiB + 1152 MiB = 1216 MiB ≤ 0.80 × 2048 MiB = 1638.4 MiB` (PASS, оценка). Для варианта A2 (общий демон, 439 MiB, F-20) вклад меньше.

## 8. Гейты Highload & Resilience (7 канонических + оси брифа)

### 8.1. Канонические гейты `architecture.md` (`#hl-env-and-four-gates-ssot`)

- `C-MULT/v1`:
  - `C-MULT-I1`: `1 × 1 × 6 = 6 ≤ 0.60 × 80 = 48` для георутера (F-26) — PASS; для локальной БД предел неизвестен (OPEN-08), поэтому ограничителем остаются `_StartupGate`, `SPAWN_RATE_PER_S` и семафор слотов (F-10, F-11, F-13).
  - `C-MULT-I2`: очереди ограничены (`_StdoutFeed` 4096, слоты 6, ждущих 12, ожидание 15 с) (F-13, F-14) — PASS; новый SSE-читатель обязан иметь такой же предел.
  - `C-MULT-I3`: семафоры и замки — синглтоны процесса (`W=1`) (F-12) — PASS.
  - `C-MULT-I4`: освобождение слота и остановка процесса в `finally` (F-14) — PASS как as-is; новые ресурсы (сессия serve, SSE-сокет) должны освобождаться там же.
  - `C-MULT-I5`: `FD_worker = 128 ≤ 0.70 × 65536`; порты `0.6 × 1 × 60 + 12 = 48 ≤ 0.50 × 16384 = 8192` — PASS (оценка).
- `S-HERD/v1`:
  - `S-HERD-I1`: серия холодных стартов сериализуется `_StartupGate` (F-10); у A1 старт сервера 109 мс (F-20).
  - `S-HERD-I2`: Full Jitter 0.5/2.0 уже в коде (F-11); повторы по watchdog обязаны использовать его.
  - `S-HERD-I3..I5`: N/A, поллеров Control Plane, `If-None-Match` и `singleflight` в мосте нет (граф вызовов as-is: `do_POST` → `_stream_sse`/`_serve_json` → запуск процесса); доказательство `git diff` предоставляет Architect после дизайна.
- `H-CPU/v1`:
  - `H-CPU-I2`: регулярные выражения компилируются при импорте (F-06, F-11); разбор SSE-дельт не должен вызывать `re.compile` в цикле.
  - `H-CPU-I3`: путь с выключенной новой функцией должен возвращаться за `O(1)` (kill-switch, REQ-003).
  - `H-CPU-I5`: оценка `0.02 + 0.2 × (0.02 + 3 × 0.05) = 0.054 ≤ 0.70` (PASS, не измерено); поток serve даёт около 10 событий в секунду на запрос (F-19), то есть до 60 разборов JSON в секунду на 6 запросах.
  - `H-CPU-I1`, `H-CPU-I4`: N/A (индексов маршрутизации и event loop нет).
- `R-BULK/v1`:
  - `R-BULK-I1`: вспомогательные ожидания `3 × 5.0 с (gate) + 0 + 1.0 + 2.0 = 18.0 с ≤ 0.30 × 180 = 54 с` (PASS); наихудший случай с watchdog первого события `3 × (20 + 5) + 3 = 78 с ≤ 180 с`.
  - `R-BULK-I2`: потолок запусков 3, бюджет повторов 6, слоты 6 (F-11, F-13) — PASS.
  - `R-BULK-I3`: классификация транзиентных и детерминированных ошибок существует (F-11, `_is_transient_stream_error`); новые причины watchdog относятся к транзиентным.
  - `R-BULK-I4`, `R-BULK-I5`: N/A (пула прокси-нод с health-ранжированием и мульти-тенантных пулов в мосте нет; прокси из пула — подстановка в env, F-15).
- `T-LIFE/v1`: каждый процесс и его читатель закрываются `_stop_proc` в `finally` (F-14); для A1/A2 добавляются `interrupt`, `DELETE` сессии и `killpg` (F-22).
- `O-EXIT/v1`: строка выхода на каждом `do_POST` уже есть (F-32); расширение полями — REQ-016.
- `M-SEM/v1`: N/A на этапе анализа (единый пул слотов `_slots`, F-12); подтверждение `git diff` и графа вызовов — за Architect.

### 8.2. Оси из брифа (`R-OUT`, `M-CONF`, `F-DEG`, `S-SEC`, `X-BOUND`)

В каноне этих меток нет (OPEN-15). Трактовка аналитика (допущение) и статус по фактам:

| Ось | Трактовка | Статус по фактам |
|---|---|---|
| `R-OUT` | исходы запроса и повторы (`exit_reason`, потолок A_max) | потолок есть (F-11); новые причины watchdog требуют кодов (REQ-016) |
| `M-CONF` | конфигурация и kill-switch новой функции | переменные окружения как у `STEP_RECOVERY` (F-11), REQ-003 |
| `F-DEG` | деградация: отказ быстрого транспорта не должен ломать ответ | прецедент serve→exec в muse-bridge (F-40); fail-open для статусных строк, fail-closed для политики инструментов (REQ-012) |
| `S-SEC` | секреты, пароль serve, изоляция инструментов | пароль случайный на процесс (F-21), `apiKey` не выгружался (F-27), REQ-015 |
| `X-BOUND` | границы процессов и ресурсов (killpg, FD, сессии) | F-14, F-29, REQ-008 |

## 9. Non-Goals

- Не менять публичный HTTP-контракт моста, порт и формат OpenAI SSE (REQ-002).
- Не менять DSH (бандл `app.asar`), профиль `cordis.patch.yml` и поведение `ReasoningRow`.
- Не модифицировать текст размышления модели ради превью (OPEN-13).
- Не менять модель, список моделей, логику выбора эффорта и каталог Zen.
- Не трогать `muse-bridge`, другие мосты и общий `~/.config/opencode/opencode.json` / конфиг `model_georouter`.
- Не вводить новые внешние зависимости Python вне стандартной библиотеки, если Architect не обоснует иное.

## 10. Forbidden Scope

- Изменение чужих файлов репозитория вне `bridges/opencode-zen-bridge/` и тестов этого моста.
- Запись секретов (ключи, пароль serve, креды прокси, значения `apiKey`) в логи, артефакты, код и тесты.
- Мутирующие действия на боевом контуре без отката: правка `~/.dsh` и перезапуск LaunchAgent допустимы только в живой приёмке по протоколу из `handoff-qa.md`.
- Использование `security find-generic-password`.
- Правка `opencode.db` и общего каталога состояния `opencode` напрямую.
- Коммит в `main`, `master`, `dev`; merge выполняет человек.

## 11. Маппинг в `architecture-packet.json`

- `evidence`: `F-01..F-49` (ledger).
- `blocking open questions`: пусто.
- `assumptions`: `OPEN-04..OPEN-17` с рабочими допущениями из `open-questions.md`.
- `boundaries/contracts`: раздел 5.
- `quality scenarios` (baseline): первая видимая строка до 1.0 с; первая дельта размышления до 3.0 с; пауза до 15 с; молчание до 20 с (допущения OPEN-11), текущие значения в разделе 6.
- `risks`: R1 — прямой Zen без заголовков не осуществим (OPEN-05); R2 — потеря ротации IP при общем демоне (OPEN-06); R3 — встроенные инструменты `opencode` исполнятся при неверной политике (OPEN-07); R4 — контенция SQLite при параллельных serve (OPEN-08); R5 — квота Zen блокирует живую приёмку до около 03:00 MSK 2026-10-26 (F-23); R6 — дубли размышления при повторах (OPEN-14); R7 — красная базовая линия блокирует Full Suite Gate (OPEN-04).

## 12. Обратный канал в требования

Противоречий фактов с REQ-ID нет. Расхождение с брифом: в `tests/` 17 модулей `test_*.py`, а не 16 (F-42); ссылка на «16 модулей» в постановке неточна, на объём работ не влияет.
ARTIFACT_END>>>

## 2. Манифест кандидата, полный итоговый diff (`candidate.diff`, включая `tests/test_realtime_reasoning.py`) и вывод `panel-rework-summarizer` (`panel-rework-brief.json`)
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate-manifest.json sha256=b82ef4301aef0f563664cc29010a89afaaf9fb8af54d334fe186e157dafc1daf
{
  "schema": "candidate-manifest/v1",
  "created_at_utc": "2026-10-27T03:15:03.148804+00:00",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "cycle": 4,
  "branch": "feature/zen-realtime-reasoning",
  "base_ref": "origin/dev",
  "base_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "head_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "staged_diff_bytes": 0,
  "binary_files": [],
  "worktree_fingerprint_before_coder": null,
  "worktree_fingerprint_after_coder": "ba0ac83323e29fe5a3fa80c71dbfdd0c5fedc75dca1f76631dcc9ef854388776",
  "candidate_diff_path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate.diff",
  "candidate_diff_sha256": "bb5bdd651db33691cbc45eb5270a3aff615b3b49679b1c40db635e9d44dc67c5",
  "files": [
    {
      "path": "bridges/opencode-zen-bridge/server.py",
      "status": "modified_unstaged",
      "is_binary": false,
      "bytes": 328750,
      "lines": 7486,
      "sha256": "3193913f29f87efaba202d41fc2c3634f3a4303560f75d7c3bb60e65bfac36c2"
    },
    {
      "path": "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
      "status": "added_untracked",
      "is_binary": false,
      "bytes": 100687,
      "lines": 1962,
      "sha256": "2bd26e8ed7abf9feecdd8399161247f02b6afda230e1b02d978d68d863fbb9a4"
    },
    {
      "path": "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "status": "modified_unstaged",
      "is_binary": false,
      "bytes": 58105,
      "lines": 1088,
      "sha256": "e41d10bd96cb208ce3120ab25d1c8028c82fe81895eacd322312b7fbbbef8a11"
    }
  ]
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/candidate.diff sha256=bb5bdd651db33691cbc45eb5270a3aff615b3b49679b1c40db635e9d44dc67c5
diff --git a/bridges/opencode-zen-bridge/server.py b/bridges/opencode-zen-bridge/server.py
index 667b990..845b572 100755
--- a/bridges/opencode-zen-bridge/server.py
+++ b/bridges/opencode-zen-bridge/server.py
@@ -17,27 +17,271 @@ usage — из события `type:"step_finish"` (part.tokens).
 
 from __future__ import annotations
 
-import hmac
-import http.client
+import errno
 import json
 import os
-import queue
-import random
-import re
-import shlex
-import shutil
+import select
 import signal
-import sqlite3
 import subprocess
 import sys
-import threading
 import time
-import uuid
-from collections.abc import Callable, Iterable, Iterator
-from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 from pathlib import Path
 from typing import Any, cast
-from urllib.parse import quote, urlsplit
+
+
+def _run_serve_helper_cli(args: list[str]) -> int:
+    """Ранний помощник serve: один лидер группы на попытку, lease и дренаж пайпов."""
+    if len(args) != 6:
+        return 2
+    (
+        attempt_id,
+        port_text,
+        opencode_bin,
+        lease_dir_text,
+        parent_pid_text,
+        parent_lstart,
+    ) = args
+    if not attempt_id or not opencode_bin or not lease_dir_text or not parent_lstart:
+        return 2
+    if not port_text.isdecimal() or not parent_pid_text.isdecimal():
+        return 2
+    port = int(port_text)
+    parent_pid = int(parent_pid_text)
+    if not 1 <= port <= 65535 or parent_pid <= 0:
+        return 2
+    lease_dir = Path(lease_dir_text)
+    stopped: dict[str, bool] = {"flag": False}
+
+    def _on_term(_signum: int, _frame: object) -> None:
+        """Отметить SIGTERM без тяжёлой работы в обработчике."""
+        stopped["flag"] = True
+
+    _ = signal.signal(signal.SIGTERM, _on_term)
+    try:
+        lease_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
+        os.chmod(lease_dir, 0o700)
+    except OSError:
+        return 2
+    lease_path = lease_dir / f"lease-{attempt_id}.json"
+
+    def _lstart_of(pid: int) -> str:
+        """lstart процесса из ps; при сбое ps — epoch-секунды."""
+        try:
+            out = subprocess.run(
+                ["ps", "-o", "lstart=", "-p", str(pid)],
+                capture_output=True,
+                text=True,
+                timeout=2,
+            )
+            return out.stdout.strip() or str(int(time.time()))
+        except (OSError, subprocess.SubprocessError):
+            return str(int(time.time()))
+
+    helper_lstart = _lstart_of(os.getpid())
+
+    def _write_lease(extra: dict[str, object]) -> None:
+        """Атомарно опубликовать lease помощника."""
+        payload: dict[str, object] = {
+            "schema_version": 1,
+            "attempt_id": attempt_id,
+            "owner_uid": os.getuid(),
+            "parent_pid": parent_pid,
+            "parent_start_ts": parent_lstart,
+            "helper_pid": os.getpid(),
+            "helper_lstart": helper_lstart,
+            "pgid": os.getpgrp(),
+            "port": port,
+            "start_ts": time.time(),
+            "phase": "starting",
+        }
+        payload.update(extra)
+        tmp_path = lease_path.with_suffix(".tmp")
+        try:
+            _ = tmp_path.write_text(json.dumps(payload), "utf-8")
+            os.replace(tmp_path, lease_path)
+        except OSError:
+            pass
+
+    def _fd_ready() -> bool:
+        """EOF на lifeline fd 0 виден без блокировки."""
+        try:
+            ready, _w, _x = select.select([0], [], [], 0)
+            return bool(ready)
+        except BlockingIOError:
+            return False
+        except (OSError, ValueError) as _gone_exc:
+            if isinstance(_gone_exc, OSError) and _gone_exc.errno in (
+                errno.EAGAIN,
+                errno.EWOULDBLOCK,
+            ):
+                return False
+            return True
+
+    _write_lease({})
+    if _fd_ready():
+        try:
+            lease_path.unlink()
+        except OSError:
+            pass
+        return 0
+    serve_env = dict(os.environ)
+    _ = serve_env.pop("OPENCODE_BIN", None)
+    try:
+        serve_proc = subprocess.Popen(
+            [opencode_bin, "serve", "--hostname", "127.0.0.1", "--port", str(port)],
+            stdin=subprocess.DEVNULL,
+            stdout=subprocess.PIPE,
+            stderr=subprocess.PIPE,
+            start_new_session=False,
+            close_fds=True,
+            env=serve_env,
+        )
+    except OSError:
+        return 2
+    serve_lstart = _lstart_of(serve_proc.pid)
+    _write_lease(
+        {"serve_pid": serve_proc.pid, "serve_lstart": serve_lstart, "phase": "ready"}
+    )
+    try:
+        _ = sys.stdout.write(
+            json.dumps({"serve_pid": serve_proc.pid, "pgid": os.getpgrp()}) + "\n"
+        )
+        _ = sys.stdout.flush()
+    except OSError:
+        pass
+    pipes: list[int] = []
+    for stream in (serve_proc.stdout, serve_proc.stderr):
+        if stream is not None:
+            pipes.append(stream.fileno())
+            os.set_blocking(stream.fileno(), False)
+    code = 0
+    try:
+        while True:
+            if stopped["flag"] or _fd_ready():
+                break
+            poll = serve_proc.poll()
+            if poll is not None:
+                code = int(poll)
+                break
+            watch: list[int] = [0, *pipes]
+            try:
+                ready, _w, _x = select.select(watch, [], [], 0.05)
+            except (OSError, ValueError):
+                ready = []
+            for item in ready:
+                if item == 0:
+                    stopped["flag"] = True
+                    continue
+                try:
+                    chunk = os.read(item, 65536)
+                except OSError:
+                    chunk = b""
+                if chunk:
+                    try:
+                        _ = sys.stderr.write(chunk.decode("utf-8", "replace"))
+                        _ = sys.stderr.flush()
+                    except OSError:
+                        pass
+            if stopped["flag"]:
+                break
+    finally:
+        # Убить всю собственную группу (serve и внуков), lease — только после смерти группы.
+        _pgid = os.getpgrp()
+
+        def _group_members() -> list[int]:
+            """Живые члены группы, кроме самого помощника (ps — в отдельной сессии)."""
+            _ = serve_proc.poll()
+            try:
+                listing = subprocess.run(
+                    ["ps", "-A", "-o", "pid=,pgid="],
+                    capture_output=True,
+                    text=True,
+                    timeout=2,
+                    start_new_session=True,
+                )
+            except (OSError, subprocess.SubprocessError):
+                return [serve_proc.pid] if serve_proc.poll() is None else []
+            members: list[int] = []
+            for row in listing.stdout.splitlines():
+                cols = row.split()
+                if (
+                    len(cols) == 2
+                    and cols[0].isdecimal()
+                    and cols[1] == str(_pgid)
+                    and int(cols[0]) != os.getpid()
+                ):
+                    members.append(int(cols[0]))
+            return members
+
+        try:
+            os.killpg(_pgid, signal.SIGTERM)
+        except OSError:
+            if serve_proc.poll() is None:
+                try:
+                    serve_proc.terminate()
+                except OSError:
+                    pass
+        members_now = _group_members()
+        _term_deadline = time.monotonic() + 4.0
+        while members_now and time.monotonic() < _term_deadline:
+            time.sleep(0.1)
+            members_now = _group_members()
+        if members_now:
+            # Эскалация: SIGKILL всем оставшимся членам группы, даже если serve уже вышел.
+            for _pid in members_now:
+                try:
+                    os.kill(_pid, signal.SIGKILL)
+                except OSError:
+                    pass
+            _kill_deadline = time.monotonic() + 2.0
+            while members_now and time.monotonic() < _kill_deadline:
+                time.sleep(0.05)
+                members_now = _group_members()
+        # Дренировать остаток пайпов, чтобы потомок не остался с полным буфером.
+        for fd in pipes:
+            try:
+                while True:
+                    chunk = os.read(fd, 65536)
+                    if not chunk:
+                        break
+                    _ = sys.stderr.write(chunk.decode("utf-8", "replace"))
+            except OSError:
+                pass
+        if not members_now:
+            try:
+                lease_path.unlink()
+            except OSError:
+                pass
+    return code
+
+
+if sys.argv[1:2] == ["--serve-helper"]:
+    raise SystemExit(_run_serve_helper_cli(sys.argv[2:]))
+else:
+    import base64
+    import collections
+    import hmac
+    import http.client
+    import io
+    import queue
+    import random
+    import re
+    import secrets
+    import shlex
+    import shutil
+    import socket
+    import sqlite3
+    import stat
+    import tempfile
+    import threading
+    import uuid
+    from collections.abc import Callable, Iterable, Iterator
+    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
+    from typing import TypedDict
+    from urllib.parse import quote, urlsplit
+
+    sys.path.insert(0, str(Path(__file__).resolve().parent))
+    import zen_catalog as zc
 
 HOST = os.environ.get("OPENCODE_ZEN_BRIDGE_HOST", "127.0.0.1").strip() or "127.0.0.1"
 PORT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_PORT", "9883"))
@@ -49,9 +293,21 @@ TIMEOUT_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_TIMEOUT_S", "1800"))
 KEEPALIVE_INTERVAL_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_KEEPALIVE_S", "15.0"))
 MAX_CONCURRENT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT", "2"))
 
-OPENCODE_BIN = os.environ.get("OPENCODE_BIN", str(Path.home() / ".opencode" / "bin" / "opencode"))
-WORKSPACE = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKSPACE", str(Path(__file__).resolve().parent / "workspace")))
-LOG_PATH = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_LOG", str(Path(__file__).resolve().parent / "logs" / "bridge.log")))
+OPENCODE_BIN = os.environ.get(
+    "OPENCODE_BIN", str(Path.home() / ".opencode" / "bin" / "opencode")
+)
+WORKSPACE = Path(
+    os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_WORKSPACE",
+        str(Path(__file__).resolve().parent / "workspace"),
+    )
+)
+LOG_PATH = Path(
+    os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_LOG",
+        str(Path(__file__).resolve().parent / "logs" / "bridge.log"),
+    )
+)
 
 DEFAULTWORKDIR = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKDIR", str(WORKSPACE)))
 
@@ -63,9 +319,6 @@ DEFAULTWORKDIR = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_WORKDIR", str(WORKSPAC
 # Zen-модели запускаются как `opencode run --standalone` с OPENCODE_MODELS_PATH на свежий api.json
 # и БЕЗ OPENCODE_API_KEY (истёкший ключ из env давал 401 api_key_expired — причина отказа от
 # standalone 2026-10-19). Режим static (kill-switch) — прежний маршрут через фоновый сервис.
-sys.path.insert(0, str(Path(__file__).resolve().parent))
-import zen_catalog as zc
-
 DEPRECATED_MODEL_ALIASES: dict[str, str] = zc.DEPRECATED_MODEL_ALIASES
 
 
@@ -75,12 +328,22 @@ def _normalize_catalog_mode(raw: str) -> str:
     return "static" if value in ("static", "legacy") else "dynamic"
 
 
-CATALOG_MODE = _normalize_catalog_mode(os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_MODE", "dynamic"))
-CATALOG_STATE_PATH = Path(os.environ.get(
-    "OPENCODE_ZEN_BRIDGE_CATALOG_STATE", str(Path(__file__).resolve().parent / "state" / "zen-catalog.json")))
+CATALOG_MODE = _normalize_catalog_mode(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_MODE", "dynamic")
+)
+CATALOG_STATE_PATH = Path(
+    os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_CATALOG_STATE",
+        str(Path(__file__).resolve().parent / "state" / "zen-catalog.json"),
+    )
+)
 OPENCODE_MODELS_PATH = os.environ.get(
-    "OPENCODE_ZEN_BRIDGE_MODELS_PATH", str(Path.home() / ".cache" / "opencode" / "models.json"))
-CATALOG_STAT_INTERVAL_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_STAT_INTERVAL_S", "5"))
+    "OPENCODE_ZEN_BRIDGE_MODELS_PATH",
+    str(Path.home() / ".cache" / "opencode" / "models.json"),
+)
+CATALOG_STAT_INTERVAL_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_CATALOG_STAT_INTERVAL_S", "5")
+)
 
 # Живой каталог: id -> метаданные (context_length, max_output, supports_variant, variant_map, ...).
 # Словарь изменяется на месте, чтобы ссылки на него (в том числе в тестах) оставались верными.
@@ -89,10 +352,17 @@ ALLOWED_MODELS: dict[str, dict[str, Any]] = {}
 MODEL_ALIASES: dict[str, str] = dict(DEPRECATED_MODEL_ALIASES)
 
 _catalog_lock = threading.RLock()
-_catalog_ids: set[str] = set()           # id, добавленные каталогом (тестовые/Go-записи не трогаем)
+_catalog_ids: set[str] = (
+    set()
+)  # id, добавленные каталогом (тестовые/Go-записи не трогаем)
 _catalog_mtime: int | None = None
 _catalog_checked_at = float("-inf")
-CATALOG_SOURCE = "init"
+CATALOG_SOURCE = "static"
+
+
+def _set_catalog_source(source: str) -> None:
+    """Обновить публичный CATALOG_SOURCE без global-записи в reload."""
+    globals()["CATALOG_SOURCE"] = source
 
 
 def _stat_mtime(path: Path) -> int | None:
@@ -115,7 +385,7 @@ def _read_catalog_state() -> tuple[dict[str, Any], str]:
 
 def reload_catalog() -> dict[str, Any]:
     """Перечитать каталог и применить к ALLOWED_MODELS/MODEL_ALIASES на месте."""
-    global _catalog_mtime, _catalog_ids, CATALOG_SOURCE
+    global _catalog_mtime, _catalog_ids
     mtime = _stat_mtime(CATALOG_STATE_PATH)
     state, source = _read_catalog_state()
     models = zc.entries_to_bridge_models(state["models"])
@@ -128,9 +398,15 @@ def reload_catalog() -> dict[str, Any]:
         MODEL_ALIASES.update(DEPRECATED_MODEL_ALIASES)
         MODEL_ALIASES.update(state["aliases"])
         _catalog_mtime = mtime
-        CATALOG_SOURCE = source
-    return {"ok": True, "source": source, "mode": CATALOG_MODE, "models": sorted(models),
-            "aliases": len(MODEL_ALIASES), "degraded": bool(state.get("degraded"))}
+        _set_catalog_source(source)
+    return {
+        "ok": True,
+        "source": source,
+        "mode": CATALOG_MODE,
+        "models": sorted(models),
+        "aliases": len(MODEL_ALIASES),
+        "degraded": bool(state.get("degraded")),
+    }
 
 
 def _maybe_reload_catalog(now: float | None = None) -> bool:
@@ -151,12 +427,18 @@ def _maybe_reload_catalog(now: float | None = None) -> bool:
 
 def _zen_active_ids() -> list[str]:
     """Id Zen-моделей каталога (без Go-маршрутов)."""
-    return sorted(m for m, meta in ALLOWED_MODELS.items() if not meta.get("provider") and not meta.get("base_url"))
+    return sorted(
+        m
+        for m, meta in ALLOWED_MODELS.items()
+        if not meta.get("provider") and not meta.get("base_url")
+    )
 
 
 def _resolve_alias(model_id: str) -> str | None:
     """Модель-исполнитель для устаревшего/выбывшего id; None — id неизвестен."""
-    target, aliased = zc.resolve_model(model_id, _zen_active_ids(), MODEL_ALIASES, DEFAULT_MODEL)
+    target, aliased = zc.resolve_model(
+        model_id, _zen_active_ids(), MODEL_ALIASES, DEFAULT_MODEL
+    )
     return target if aliased else None
 
 
@@ -211,7 +493,9 @@ def _rewrite_tool_tags_for_model(text: str, model_id: str = "") -> str:
     """Заменить `<tool_call>`-теги в промпте на `<tool_invoke>` для GLM; остальным — как есть."""
     if not _uses_alt_tool_tag(model_id):
         return text
-    return text.replace(TOOL_CALL_OPEN, ALT_TOOL_CALL_OPEN).replace(TOOL_CALL_CLOSE, ALT_TOOL_CALL_CLOSE)
+    return text.replace(TOOL_CALL_OPEN, ALT_TOOL_CALL_OPEN).replace(
+        TOOL_CALL_CLOSE, ALT_TOOL_CALL_CLOSE
+    )
 
 
 def _open_tag_at(text: str, index: int) -> tuple[str, str] | None:
@@ -221,6 +505,7 @@ def _open_tag_at(text: str, index: int) -> tuple[str, str] | None:
             return open_tag, close_tag
     return None
 
+
 # Встроенные инструменты opencode НЕ исполняются в мосте: permission "ask" →
 # `opencode run` автоматически отклоняет вызов (инструменты исполняет DSH).
 # "deny" / tools:false НЕЛЬЗЯ: инструменты пропадают из запроса, и Zen отвечает 403
@@ -278,23 +563,34 @@ NATIVE_RETRY_LIMIT = int(os.environ.get("OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES", "2
 
 # 2026-10-24 (AD-002): отдельный kill-switch детектора оборванного шага; независим от
 # NATIVE_RETRY_LIMIT (повтор встроенного инструмента без DSH-двойника остаётся включённым).
-STEP_RECOVERY_ENABLED = os.environ.get("OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1").strip().lower() not in (
-    "0", "false", "no", "off")
+STEP_RECOVERY_ENABLED = os.environ.get(
+    "OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1"
+).strip().lower() not in ("0", "false", "no", "off")
 
 # 2026-10-24 (AD-003): единый потолок запусков `opencode run` на один HTTP-запрос — суммарно по
 # первичному запуску, повтору транзиторного отказа CLI, повтору незавершённого шага и
 # повтору встроенного инструмента без DSH-двойника (A_max).
-MAX_TOTAL_SPAWNS = max(1, int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_TOTAL_SPAWNS", "3")))
+MAX_TOTAL_SPAWNS = max(
+    1, int(os.environ.get("OPENCODE_ZEN_BRIDGE_MAX_TOTAL_SPAWNS", "3"))
+)
 
 # 2026-10-10: `opencode run` иногда падает за ~1 с с rc=1 без вывода
 # («Error: Unexpected error … database is locked», sqlite opencode при параллельном старте).
 # Такой отказ — транзиторный: прогон без вывода повторяется (не более FAIL_RETRY_LIMIT раз,
 # и всегда внутри потолка MAX_TOTAL_SPAWNS: первичный запуск + FAIL_RETRY_LIMIT <= MAX_TOTAL_SPAWNS).
-FAIL_RETRY_LIMIT = min(int(os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRIES", "3")), MAX_TOTAL_SPAWNS - 1)
+FAIL_RETRY_LIMIT = min(
+    int(os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRIES", "3")), MAX_TOTAL_SPAWNS - 1
+)
 # Старый линейный backoff заменён Full Jitter (_retry_backoff_s); значение 0 по-прежнему отключает паузы.
-FAIL_RETRY_BACKOFF_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRY_BACKOFF_S", "0.8"))
-RETRY_BACKOFF_BASE_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_BASE_S", "0.5"))
-RETRY_BACKOFF_CAP_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_CAP_S", "2.0"))
+FAIL_RETRY_BACKOFF_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_FAIL_RETRY_BACKOFF_S", "0.8")
+)
+RETRY_BACKOFF_BASE_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_BASE_S", "0.5")
+)
+RETRY_BACKOFF_CAP_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BACKOFF_CAP_S", "2.0")
+)
 
 # Очередь stdout `opencode run`: ограничена, переполнение — отказ попытки, а не рост кучи.
 STDOUT_QUEUE_MAX = int(os.environ.get("OPENCODE_ZEN_BRIDGE_STDOUT_QUEUE_MAX", "4096"))
@@ -310,13 +606,19 @@ SPAWN_RATE_PER_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SPAWN_RATE_PER_S",
 SPAWN_BURST = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SPAWN_BURST", "1.0"))
 SPAWN_WAIT_MAX_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_SPAWN_WAIT_MAX_S", "5.0"))
 RETRY_BUDGET_MAX = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_MAX", "6"))
-RETRY_BUDGET_PER_REQUEST = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_PER_REQUEST", "0.20"))
-RETRY_BUDGET_RESERVE_RPS = float(os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_RESERVE_RPS", "0.05"))
+RETRY_BUDGET_PER_REQUEST = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_PER_REQUEST", "0.20")
+)
+RETRY_BUDGET_RESERVE_RPS = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_RETRY_BUDGET_RESERVE_RPS", "0.05")
+)
 CB_FAIL_THRESHOLD = int(os.environ.get("OPENCODE_ZEN_BRIDGE_CB_FAIL_THRESHOLD", "5"))
 CB_RESET_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_CB_RESET_S", "10.0"))
 
 
-def _retry_backoff_s(retry_num: int, rng_fn: Callable[[float, float], float] = random.uniform) -> float:
+def _retry_backoff_s(
+    retry_num: int, rng_fn: Callable[[float, float], float] = random.uniform
+) -> float:
     """Full Jitter: пауза перед повторным запуском = U(0, min(CAP, BASE * 2**retry_num)); retry_num с 1."""
     ceiling = min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** max(0, retry_num)))
     return rng_fn(0.0, ceiling)
@@ -506,15 +808,22 @@ _INTERRUPTED_RE = re.compile(
     r"I was interrupted right before making tool calls\.?(?:\s*Continue\b[^\n]*)?|"
     r"The previous response was interrupted\.\s*Continue from where you left off without repeating "
     r"completed content\.?",
-    re.IGNORECASE)
-_INTERRUPT_MARKERS = ("interrupted right before making tool calls", "previous response was interrupted")
+    re.IGNORECASE,
+)
+_INTERRUPT_MARKERS = (
+    "interrupted right before making tool calls",
+    "previous response was interrupted",
+)
 # Сырой вызов `<tool_call>{…` / `<tool_invoke>{…`: не inline-код markdown и не упоминание тега в прозе.
-_RAW_CALL_RE = re.compile(r"(?<!`)<(?:tool_call|tool_invoke)>\s*(?:(?:```|~~~)\w*\s*)?\{")
+_RAW_CALL_RE = re.compile(
+    r"(?<!`)<(?:tool_call|tool_invoke)>\s*(?:(?:```|~~~)\w*\s*)?\{"
+)
 # Модель явно сказала, что отвечает без инструментов.
 _NO_TOOLS_RE = re.compile(
     r"\bno tools?\b|\bwithout (?:any )?tools?\b|\bno need\b|\bnot (?:needed|required|necessary)\b|"
     r"\brule 0\b|правило 0|не требует инструмент|без инструмент|инструмент\w* не нужн",
-    re.IGNORECASE)
+    re.IGNORECASE,
+)
 # Намерение немедленного действия (преамбула шага без `<tool_call>`): явный глагол действия.
 _ACTION_INTENT_RE = re.compile(
     r"\b(?:забираю|читаю|собираю|правлю|проверяю|запускаю|выполняю|запрашиваю|стартую|продолжаю|начинаю|"
@@ -525,7 +834,8 @@ _ACTION_INTENT_RE = re.compile(
     r"\blet'?s (?:check|read|look|run|fetch|collect|gather|see|grab|update|fix|search)\b|"
     r"\bi(?:'ll| will) (?:check|read|look|run|fetch|collect|gather|update|fix|search)\b|"
     r"\b(?:collecting|checking|reading|running|fetching|gathering|updating|searching)\b",
-    re.IGNORECASE)
+    re.IGNORECASE,
+)
 _PROMISE_RE = _ACTION_INTENT_RE  # прежнее имя
 # Финальный вывод/ответ (а не преамбула шага): заголовок-вывод в начале текста или фраза-итог.
 _FINAL_CONCLUSION_RE = re.compile(
@@ -533,7 +843,8 @@ _FINAL_CONCLUSION_RE = re.compile(
     r"summary|conclusion|answer|result|done|готово)\b|"
     r"\b(?:ошибок нет|нет ошибок|всё в порядке|все в порядке|так задумано|тесты (?:зел[её]ные|прошли)|"
     r"no errors?|all (?:good|tests pass\w*)|everything is fine)\b",
-    re.IGNORECASE)
+    re.IGNORECASE,
+)
 # План пачки вызовов в reasoning текущего шага.
 _REASONING_TOOL_PLAN_RE = re.compile(
     r"let me batch|all in batch|\bone message\s*:|\bin one (?:message|batch|turn)\b|parallel calls|"
@@ -541,28 +852,43 @@ _REASONING_TOOL_PLAN_RE = re.compile(
     r"\btool calls? (?:now|next|in parallel)\b|"
     r"\bemit (?:the )?(?:tool[_\s]?(?:call|invoke)?\s*)?blocks?\b|\btool[_\s]?(?:call|invoke)?\s*blocks?\b|"
     r"\bcall (?:the )?tools\b|\btwo independent calls\b|\bindependent calls\b",
-    re.IGNORECASE)
+    re.IGNORECASE,
+)
 _PLAN_RE = _REASONING_TOOL_PLAN_RE  # прежнее имя
 # Мышление, где модель пишет «I need to call job_output…» без готовой фразы-плана.
 _CALL_INTENT_RE = re.compile(
-    r"\b(?:call|invoke|emit|parallel|batch|need to|let me|i'll|i will|should)\b", re.IGNORECASE)
+    r"\b(?:call|invoke|emit|parallel|batch|need to|let me|i'll|i will|should)\b",
+    re.IGNORECASE,
+)
 # Апстрим вырезал `<tool_call>…</tool_call>` из text, но токены в step_finish остались: столько
 # лишних токенов над оценкой видимого текста — признак проглоченного вызова.
 SWALLOWED_TOKENS_MIN = 35
 INCOMPLETE_STEP_MAX_TEXT = 1200  # дольше — это ответ, а не статусная преамбула
 INCOMPLETE_STEP_TAIL = 400
 TAIL_REMINDER_MIN_CHARS = 4000
-SWALLOWED_MAX_TEXT = 600   # признак 3
-PLAN_MAX_TEXT = 600        # признак 4
-PREAMBLE_MAX_CHARS = 420   # признак 5
+SWALLOWED_MAX_TEXT = 600  # признак 3
+PLAN_MAX_TEXT = 600  # признак 4
+PREAMBLE_MAX_CHARS = 420  # признак 5
 PREAMBLE_MAX_LINES = 6
 PREAMBLE_SHORT_CHARS = 220
 
 # Mid-stream `etype == "error"`: транзиентные сбои (повторяем) против детерминированных (Fail-Closed).
 _FATAL_STREAM_STATUSES = (400, 401, 403, 404, 422)
 _TRANSIENT_ERROR_MARKERS = (
-    "econnreset", "etimedout", "timeout", "timed out", "socket hang up", "interrupted", "overloaded",
-    "rate limit", "temporarily unavailable", "fetch failed", "network", "connection reset", "broken pipe", "eof",
+    "econnreset",
+    "etimedout",
+    "timeout",
+    "timed out",
+    "socket hang up",
+    "interrupted",
+    "overloaded",
+    "rate limit",
+    "temporarily unavailable",
+    "fetch failed",
+    "network",
+    "connection reset",
+    "broken pipe",
+    "eof",
 )
 
 
@@ -596,7 +922,8 @@ def _mentions_request_tool(text: str, names: Iterable[str]) -> bool:
         while start != -1:
             end = start + len(name)
             if (start == 0 or not _is_ident_char(text[start - 1])) and (
-                    end == len(text) or not _is_ident_char(text[end])):
+                end == len(text) or not _is_ident_char(text[end])
+            ):
                 return True
             start = text.find(name, start + 1)
     return False
@@ -658,7 +985,8 @@ def _is_transient_stream_error(ev: dict[str, Any]) -> bool:
 def _step_recovery_disabled() -> bool:
     """Kill-switch OPENCODE_ZEN_BRIDGE_STEP_RECOVERY (константа модуля и живое значение env)."""
     return not STEP_RECOVERY_ENABLED or os.environ.get(
-        "OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1").strip().lower() in ("0", "false", "no", "off")
+        "OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1"
+    ).strip().lower() in ("0", "false", "no", "off")
 
 
 def _visible_token_estimate(stripped: str) -> int:
@@ -666,7 +994,9 @@ def _visible_token_estimate(stripped: str) -> int:
     return max(len(stripped) // 2, _estimate_tokens(stripped)) if stripped else 0
 
 
-def _swallowed_tokens(stripped: str, output_tokens: int, reasoning_tokens: int = 0) -> int:
+def _swallowed_tokens(
+    stripped: str, output_tokens: int, reasoning_tokens: int = 0
+) -> int:
     """Токены вывода, не объяснённые видимым текстом: output включает reasoning — вычитаем его."""
     if reasoning_tokens > 0 and output_tokens >= reasoning_tokens:
         non_reasoning_output = max(0, output_tokens - reasoning_tokens)
@@ -687,7 +1017,9 @@ def _is_status_preamble(stripped: str, names: list[str]) -> bool:
         return False
     if stripped.endswith((":", "...", "…")):
         return True
-    return len(stripped) <= PREAMBLE_SHORT_CHARS and _mentions_request_tool(stripped, names)
+    return len(stripped) <= PREAMBLE_SHORT_CHARS and _mentions_request_tool(
+        stripped, names
+    )
 
 
 def _no_tools_overridden(body: str, thought: str, names: Iterable[str]) -> bool:
@@ -702,7 +1034,8 @@ def _no_tools_overridden(body: str, thought: str, names: Iterable[str]) -> bool:
         return False
     tail = thought[-400:]
     return bool(_REASONING_TOOL_PLAN_RE.search(thought[-600:])) or (
-        _mentions_request_tool(tail, names) and bool(_CALL_INTENT_RE.search(tail)))
+        _mentions_request_tool(tail, names) and bool(_CALL_INTENT_RE.search(tail))
+    )
 
 
 def _detect_incomplete_tool_step_signal(text: str, reasoning: str, tools: Any,
@@ -833,28 +1166,48 @@ def _call_key(name: str, arguments: Any) -> str:
     return name + "\x00" + json.dumps(arguments, ensure_ascii=False, sort_keys=True)
 
 
-def _drain_stderr(proc: subprocess.Popen[str], sink: list[str]) -> None:
-    """Вычитать stderr дочернего процесса построчно в `sink` (до EOF)."""
+def _drain_stderr(
+    proc: subprocess.Popen[str], sink: collections.deque[str] | list[str]
+) -> None:
+    """Вычитать stderr в ограниченный буфер (кольцо на 64 строки, без секретов в лог)."""
+    # Дренаж stderr помощника/CLI в ограниченный буфер; содержимое не логируется.
     try:
         assert proc.stderr is not None
         for line in proc.stderr:
-            line = line.strip()
+            line_text: str = cast(str, line).strip()
+            line = line_text
             if line:
-                sink.append(line)
+                if isinstance(sink, list):
+                    sink_list: list[str] = sink
+                    _ = sink_list.append(line)
+                    while len(sink_list) > 64:
+                        _ = sink_list.pop(0)
+                else:
+                    sink_deque: collections.deque[str] = sink
+                    _ = sink_deque.append(line)
     except (OSError, ValueError):
         pass
 
 
 def _stop_proc(proc: subprocess.Popen[str]) -> None:
     """Остановить группу `opencode run` (SIGTERM -> SIGKILL); процесс запущен со start_new_session."""
-    if proc.poll() is not None:
+    pgid = proc.pid  # start_new_session=True => pgid == pid лидера
+    if proc.poll() is not None and not _pid_alive(-pgid):
         return
     try:
-        os.killpg(proc.pid, signal.SIGTERM)
-        proc.wait(timeout=5)
+        os.killpg(pgid, signal.SIGTERM)
+        if proc.poll() is None:
+            _ = proc.wait(timeout=5)
+        else:
+            # Лидер вышел, но группа ещё жива: ждём SIGTERM до 0.5 с.
+            _dl = time.monotonic() + 0.5
+            while time.monotonic() < _dl and _pid_alive(-pgid):
+                time.sleep(0.05)
     except (OSError, subprocess.TimeoutExpired):
+        pass
+    if _pid_alive(-pgid):
         try:
-            os.killpg(proc.pid, signal.SIGKILL)
+            os.killpg(pgid, signal.SIGKILL)
         except OSError:
             pass
 
@@ -874,7 +1227,9 @@ class _StdoutFeed:
 
     def __init__(self, proc: subprocess.Popen[str], maxsize: int | None = None) -> None:
         self._proc = proc
-        self._queue: queue.Queue[str] = queue.Queue(maxsize=STDOUT_QUEUE_MAX if maxsize is None else maxsize)
+        self._queue: queue.Queue[str] = queue.Queue(
+            maxsize=STDOUT_QUEUE_MAX if maxsize is None else maxsize
+        )
         self.timed_out = False
         self.overflowed = False
         self.dropped_total = 0
@@ -892,8 +1247,10 @@ class _StdoutFeed:
                 except queue.Full:
                     self.dropped_total += 1
                     self.overflowed = True
-                    _log(f"stdout_overflow queue_max={self._queue.maxsize} dropped_total={self.dropped_total}, "
-                         "stopping opencode run")
+                    _log(
+                        f"stdout_overflow queue_max={self._queue.maxsize} dropped_total={self.dropped_total}, "
+                        "stopping opencode run"
+                    )
                     _stop_proc(self._proc)
                     break
         except (OSError, ValueError) as exc:
@@ -901,8 +1258,12 @@ class _StdoutFeed:
         finally:
             self._done.set()  # после всех put: потребитель, увидев флаг, дочитывает остаток очереди
 
-    def lines(self, deadline: float, idle_s: float = 0.0,
-              on_idle: Callable[[], None] | None = None) -> Iterator[str]:
+    def lines(
+        self,
+        deadline: float,
+        idle_s: float = 0.0,
+        on_idle: Callable[[], None] | None = None,
+    ) -> Iterator[str]:
         """Строки до EOF, переполнения или дедлайна; `on_idle` вызывается, если строк нет дольше `idle_s` (0 — выкл.)."""
         last_activity = time.monotonic()
         while True:
@@ -927,7 +1288,11 @@ class _StdoutFeed:
                         return
                 else:
                     now = time.monotonic()
-                    if idle_s > 0 and on_idle is not None and now - last_activity >= idle_s:
+                    if (
+                        idle_s > 0
+                        and on_idle is not None
+                        and now - last_activity >= idle_s
+                    ):
                         on_idle()
                         last_activity = now
                     continue
@@ -935,6 +1300,10 @@ class _StdoutFeed:
             if last_activity > deadline:
                 self.timed_out = True
                 return
+            if idle_s > 0 and on_idle is not None:
+                # Watchdog проверяется и при поступлении строк, а не только на Empty:
+                # служебный поток без токенов должен прерываться по тем же часам.
+                on_idle()
             yield item
 
     def close(self) -> None:
@@ -968,12 +1337,23 @@ def _uses_standalone(model_id: str) -> bool:
     return CATALOG_MODE == "dynamic" and _is_zen_route(model_id)
 
 
-_PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")
+_PROXY_VARS = (
+    "HTTP_PROXY",
+    "HTTPS_PROXY",
+    "http_proxy",
+    "https_proxy",
+    "ALL_PROXY",
+    "all_proxy",
+)
 _LOOPBACK_NO_PROXY = ("127.0.0.1", "localhost", "::1")
 # THREAT-003 + принятое отклонение DEV-02: к ключам пакета добавлены переменные прокси.
 _STANDALONE_ENV_ALLOWLIST = (
-    "PATH", "HOME", "TMPDIR", "LANG",
-    "NO_PROXY", "no_proxy",
+    "PATH",
+    "HOME",
+    "TMPDIR",
+    "LANG",
+    "NO_PROXY",
+    "no_proxy",
     *_PROXY_VARS,
 )
 
@@ -988,11 +1368,16 @@ def _merged_no_proxy(current: str) -> str:
 # Пул выделенных US-портов ProxyRack: каждый порт 10000..10999 даёт отдельный чистый IP, а анонимный
 # лимит opencode.ai (36 запросов в сутки на исходящий IP) считается по IP. Режим `pool` берёт
 # порты по кругу — по одному на каждый запуск дочернего процесса (включая ретраи).
-_DEFAULT_PROXYRACK_FILE = Path.home() / ".local/share/gigaexplorator-proxies/2026-08-31-volkov-proxy-manager/06-proxyrack-global-dc-1000.txt"
+_DEFAULT_PROXYRACK_FILE = (
+    Path.home()
+    / ".local/share/gigaexplorator-proxies/2026-08-31-volkov-proxy-manager/06-proxyrack-global-dc-1000.txt"
+)
 _PROXYRACK_FORWARD_LOG = Path.home() / "Library/Logs/Factory/proxyrack-forward.log"
 _DEFAULT_PROXYRACK_GATEWAY = "121.91.235.6"
 _PROXYRACK_LOG_TAIL_BYTES = 16 * 1024
-_IPV4_RE = re.compile(r"^(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$")
+_IPV4_RE = re.compile(
+    r"^(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$"
+)
 
 _proxy_pool_lock = threading.Lock()
 _proxy_pool_key: tuple[Any, ...] | None = None
@@ -1052,7 +1437,11 @@ def _next_standalone_proxy() -> str | None:
         return None
     if raw_proxy != "pool":
         return raw_proxy
-    pool_path = Path(os.environ.get("OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE", str(_DEFAULT_PROXYRACK_FILE)))
+    pool_path = Path(
+        os.environ.get(
+            "OPENCODE_ZEN_BRIDGE_PROXYRACK_FILE", str(_DEFAULT_PROXYRACK_FILE)
+        )
+    )
     gateway = _resolve_proxyrack_gateway()
     offset = os.environ.get("OPENCODE_ZEN_BRIDGE_PROXYRACK_OFFSET", "")
     try:
@@ -1066,7 +1455,13 @@ def _next_standalone_proxy() -> str | None:
                 lines = pool_path.read_text("utf-8", errors="replace").splitlines()
             except OSError:
                 return None
-            entries = [e for e in (_parse_proxy_pool_line(ln, gateway) for ln in lines if ln.strip()) if e]
+            entries = [
+                e
+                for e in (
+                    _parse_proxy_pool_line(ln, gateway) for ln in lines if ln.strip()
+                )
+                if e
+            ]
             if not entries:
                 return None
             _proxy_pool_key = key
@@ -1131,6 +1526,471 @@ def _run_env(model_id: str = "") -> dict[str, str]:
     return env
 
 
+DYNAMIC_CONFIG_PATH = Path(__file__).resolve().parent / "dynamic_config.json"
+LEASE_DIR = Path("/tmp/opencode-zen-bridge-leases")
+SERVE_TEST_ELIGIBLE = False
+FIRST_EVENT_TIMEOUT_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_FIRST_EVENT_TIMEOUT_S", "20.0")
+)
+FIRST_TOKEN_TIMEOUT_S = float(
+    os.environ.get("OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S", "60.0")
+)
+STALL_TIMEOUT_S = float(os.environ.get("OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S", "60.0"))
+FIRST_STATUS_DELAY_S = 0.65
+STATUS_WAITING_INTERVAL_S = 5.0
+STALL_HEARTBEAT_INTERVAL_S = 15.0
+STATUS_INITIAL = "[мост] Подключение к модели…\n"
+STATUS_WAITING = "[мост] Ожидание первого токена…\n"
+STATUS_CONTINUATION = "[мост] Ожидание продолжения…\n"
+_SERVE_ALLOWLIST = (
+    "PATH",
+    "HOME",
+    "USER",
+    "LOGNAME",
+    "SHELL",
+    "LANG",
+    "LC_ALL",
+    "LC_CTYPE",
+    "TZ",
+    "TERM",
+    "COLORTERM",
+    "HTTP_PROXY",
+    "HTTPS_PROXY",
+    "ALL_PROXY",
+    "NO_PROXY",
+    "http_proxy",
+    "https_proxy",
+    "all_proxy",
+    "no_proxy",
+    "SSL_CERT_FILE",
+    "SSL_CERT_DIR",
+    "NODE_EXTRA_CA_CERTS",
+    "XDG_DATA_HOME",
+    "XDG_CONFIG_HOME",
+    "OPENCODE_CONFIG",
+    "OPENCODE_CONFIG_CONTENT",
+    "OPENCODE_MODELS_PATH",
+)
+_dynamic_config_cache: dict[str, object] = {"key": None, "value": False, "path": ""}
+_LSOF_CALLS: collections.deque[int] = collections.deque(maxlen=64)
+_PORT_ALLOC_LOCK = threading.Lock()
+_ACTIVE_SERVE_PORTS: set[int] = set()
+
+
+class ServeUnavailable(Exception):
+    """Serve недоступен до барьера доставки: допустим fallback на run в auto."""
+
+
+class ServeProtocolError(ValueError):
+    """Битое событие serve: протокол, а не модель."""
+
+
+class ServeSecurityError(Exception):
+    """Отказ безопасности serve: fail-closed без fallback."""
+
+
+class _ServeHealth:
+    """Sticky деградация serve по протокольным отказам: 3 отказа, TTL 120 с."""
+
+    def __init__(self, threshold: int = 3, ttl_s: float = 120.0) -> None:
+        self.threshold = threshold
+        self.ttl_s = ttl_s
+        self.failures = 0
+        self._degraded_until = 0.0
+        self._lock = threading.Lock()
+
+    def record_failure(self, now: float | None = None) -> None:
+        """Засчитать протокольный отказ serve."""
+        with self._lock:
+            self.failures += 1
+            if self.failures >= self.threshold:
+                self._degraded_until = (
+                    time.monotonic() if now is None else now
+                ) + self.ttl_s
+
+    def record_success(self) -> None:
+        """Сбросить деградацию после успешной попытки."""
+        with self._lock:
+            self.failures = 0
+            self._degraded_until = 0.0
+
+    def is_degraded(self, now: float | None = None) -> bool:
+        """Истёк ли sticky TTL деградации."""
+        with self._lock:
+            at = time.monotonic() if now is None else now
+            if self._degraded_until and at >= self._degraded_until:
+                self.failures = 0
+                self._degraded_until = 0.0
+                return False
+            return bool(self._degraded_until and at < self._degraded_until)
+
+
+FALLBACK_DECISION_TABLE: list[dict[str, object]] = [
+    {
+        "phase": "SPAWN/READY/CREATE/SUBSCRIBE",
+        "event": "local spawn/ready/setup failure",
+        "DELIVERED": "false",
+        "action": "fallback_to_run",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "SPAWN→READY",
+        "event": "ownership failure/timeout",
+        "DELIVERED": "false",
+        "action": "fallback_to_run",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "PROMPT_SENDING",
+        "event": "first_event_timeout20s, no response headers and no valid execution SSE",
+        "DELIVERED": "false",
+        "action": "fallback_to_run",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "DELIVERED",
+        "event": "first_event_timeout20s after headers, no valid execution SSE",
+        "DELIVERED": "true",
+        "action": "serve_retry",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "DELIVERED",
+        "event": "first_token_timeout/stall with valid protocol and model silence",
+        "DELIVERED": "true",
+        "action": "serve_retry",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 1,
+    },
+    {
+        "phase": "DELIVERED",
+        "event": "first_token_timeout with proven protocol/capability defect (non-security)",
+        "DELIVERED": "true",
+        "action": "serve_retry",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "ANY",
+        "event": "HTTP401/403 or permission/form/capability-security failure",
+        "DELIVERED": "any",
+        "action": "fail_closed",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "ANY",
+        "event": "HTTP400/404/422 invalid request",
+        "DELIVERED": "any",
+        "action": "fail_closed",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "PRE_PROMPT",
+        "event": "HTTP5xx local readiness/create/subscribe endpoint",
+        "DELIVERED": "false",
+        "action": "fallback_to_run",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "PROMPT_RESPONSE",
+        "event": "HTTP429/provider5xx prompt response",
+        "DELIVERED": "any",
+        "action": "run_fallback_pre_delivery_else_serve_retry",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 1,
+    },
+    {
+        "phase": "DELIVERED",
+        "event": "invalid SSE/EOF without terminal proven protocol-only",
+        "DELIVERED": "true",
+        "action": "serve_retry",
+        "ServeHealth_failure_increment": 1,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+    {
+        "phase": "ANY",
+        "event": "client cancel/deadline/budget exhausted",
+        "DELIVERED": "any",
+        "action": "fail_closed",
+        "ServeHealth_failure_increment": 0,
+        "UpstreamBreaker_failure_increment": 0,
+    },
+]
+
+
+class _WatchdogState(TypedDict):
+    """Состояние watchdog одного legacy-прогона."""
+
+    reason: str
+    first_event_at: float | None
+    first_token_at: float | None
+    last_token_at: float
+    status_next: float
+    last_keepalive: float
+    last_reasoning: str
+
+
+class _ServeResult(TypedDict):
+    """Итог одной serve-попытки с конкретными типами."""
+
+    reasonings: list[str]
+    texts: list[str]
+    native_calls: list[dict[str, object]]
+    usage: dict[str, int]
+    error: dict[str, object] | None
+    exit_reason: str
+    delivered: bool
+    terminal: str
+    first_event_at: float | None
+    first_token_at: float | None
+    step_closed: bool
+    first_event_ms: int | None
+    ttft_ms: int | None
+    prompt_status: int | None
+    transient_error: bool
+
+
+def _as_dict(value: object) -> dict[str, object]:
+    """Объект как словарь с строковыми ключами, иначе пустой."""
+    if isinstance(value, dict):
+        return {str(k): v for k, v in value.items()}
+    return {}
+
+
+def _combine_surrogates(value: object) -> object:
+    """Склеить суррогатные пары UTF-16 в строках после json.loads."""
+    if isinstance(value, str):
+        try:
+            return value.encode("utf-16", "surrogatepass").decode("utf-16")
+        except (UnicodeError, ValueError):
+            return value
+    if isinstance(value, dict):
+        return {str(k): _combine_surrogates(v) for k, v in value.items()}
+    if isinstance(value, list):
+        return [_combine_surrogates(v) for v in value]
+    return value
+
+
+def _loads_object(raw: str) -> dict[str, object] | None:
+    """JSON-объект стандартным json.loads; не-объект или битый JSON — None."""
+    try:
+        parsed: object = cast(object, json.loads(raw))
+    except (ValueError, TypeError):
+        return None
+    if isinstance(parsed, dict):
+        combined = _combine_surrogates({str(k): v for k, v in parsed.items()})
+        return combined if isinstance(combined, dict) else None
+    return None
+
+
+def _loads_serve_object(raw: str) -> dict[str, object]:
+    """JSON-объект события serve; битый JSON — ServeProtocolError."""
+    parsed = _loads_object(raw)
+    if parsed is None:
+        raise ServeProtocolError("invalid_serve_event: json")
+    return parsed
+
+
+def _as_int(value: object) -> int:
+    """Целое из wire-значения, иначе 0."""
+    return value if isinstance(value, int) and not isinstance(value, bool) else 0
+
+
+def _read_dynamic_config_enabled(path: Path | None = None) -> bool:
+    """Boolean REALTIME_SERVE_ENABLED из dynamic_config.json с кэшем по stat."""
+    target = DYNAMIC_CONFIG_PATH if path is None else path
+    try:
+        stat = target.stat()
+    except OSError:
+        _dynamic_config_cache.update({"key": None, "value": False, "path": str(target)})
+        return False
+    key = (stat.st_mtime_ns, stat.st_size)
+    if (
+        _dynamic_config_cache.get("path") == str(target)
+        and _dynamic_config_cache.get("key") == key
+    ):
+        return bool(_dynamic_config_cache.get("value"))
+    value = False
+    try:
+        data = _as_dict(_loads_object(target.read_text("utf-8")))
+        enabled_obj = data.get("REALTIME_SERVE_ENABLED")
+        if isinstance(enabled_obj, bool):
+            value = enabled_obj
+    except (OSError, ValueError) as exc:
+        _log(f"dynamic config unreadable: {_clean_err(str(exc))}")
+        value = False
+    _dynamic_config_cache.update({"key": key, "value": value, "path": str(target)})
+    return value
+
+
+_dynamic_config_enabled = _read_dynamic_config_enabled
+
+
+def _serve_permission_effect() -> str:
+    """Эффект permission из env политики: ask_reject -> ask, deny -> deny."""
+    policy = os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY", "ask_reject"
+    ).strip()
+    if policy == "ask_reject":
+        return "ask"
+    if policy == "deny":
+        return "deny"
+    raise ServeSecurityError(f"unsupported serve permission policy: {policy}")
+
+
+def _serve_env(model_id: str = "") -> dict[str, str]:
+    """Санитизированное окружение serve на всех ветках маршрутизации."""
+    base = _run_env(model_id)
+    env: dict[str, str] = {k: v for k, v in base.items() if k in _SERVE_ALLOWLIST}
+    _ = env.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
+    if "HOME" not in env and os.environ.get("HOME"):
+        env["HOME"] = str(os.environ["HOME"])
+    if "XDG_DATA_HOME" not in env and os.environ.get("XDG_DATA_HOME"):
+        env["XDG_DATA_HOME"] = str(os.environ["XDG_DATA_HOME"])
+    config_raw = env.get("OPENCODE_CONFIG_CONTENT") or OPENCODE_CONFIG_CONTENT
+    config = _as_dict(_loads_object(config_raw)) if config_raw else {}
+    config["permission"] = {"*": _serve_permission_effect()}
+    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config, ensure_ascii=False)
+    state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")
+    env["XDG_STATE_HOME"] = state_dir
+    env["TMPDIR"] = state_dir
+    env["OPENCODE_DB"] = ":memory:"
+    _ = env.pop("OPENCODE_BIN", None)
+    env["OPENCODE_SERVER_PASSWORD"] = secrets.token_hex(16)
+    return env
+
+
+def _is_native_opencode_bin(path: str) -> bool:
+    """Нативный бинарь opencode, а не текстовый фейк со shebang."""
+    if SERVE_TEST_ELIGIBLE:
+        return True
+    try:
+        with Path(path).open("rb") as fh:
+            head = fh.read(4)
+    except OSError:
+        return False
+    if head.startswith(b"#!"):
+        return False
+    return head[:2] in (b"\xcf\xfa", b"\xfa\xed") or head.startswith(b"\x7fELF")
+
+
+def _select_transport(res: _Resilience | None = None) -> str:
+    """Выбор транспорта: serve или run по приоритетам kill-switch."""
+    transport = os.environ.get("OPENCODE_ZEN_BRIDGE_TRANSPORT", "auto").strip().lower()
+    override = (
+        os.environ.get("OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED", "").strip().lower()
+    )
+    if transport == "run" or override in ("0", "false", "no", "off"):
+        return "run"
+    disable_raw = os.environ.get(
+        "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE",
+        "~/.dsh/bridges/opencode-zen-bridge/disable-serve",
+    )
+    try:
+        if Path(disable_raw).expanduser().exists():
+            return "run"
+    except OSError:
+        return "run"
+    health = res.serve_health if res is not None else None
+    if transport == "serve":
+        return "serve"
+    if transport != "auto":
+        return "run"
+    if health is not None and health.is_degraded():
+        return "run"
+    enabled = override in ("1", "true", "yes", "on") or _read_dynamic_config_enabled()
+    if not enabled:
+        return "run"
+    return "serve" if _is_native_opencode_bin(OPENCODE_BIN) else "run"
+
+
+def _map_serve_event(
+    event: dict[str, object],
+) -> tuple[str, dict[str, object]] | None:
+    """Wire-событие serve v2.1.2 -> канонический кортеж legacy-пути или None для служебных."""
+    etype_obj = event.get("type")
+    etype = etype_obj if isinstance(etype_obj, str) else ""
+    data = _as_dict(event.get("data"))
+    if etype == "server.connected":
+        return etype, data
+    if not data:
+        # Служебные/неизвестные события serve без данных игнорируются, а не рвут попытку.
+        if etype in (
+            "server.heartbeat",
+            "integration.updated",
+            "session.idle",
+            "server.connected",
+        ) or not etype.startswith("session."):
+            return None
+        raise ServeProtocolError("invalid_serve_event: data")
+    if etype in ("session.reasoning.delta", "session.text.delta"):
+        delta = data.get("delta")
+        session_id = data.get("sessionID")
+        if (
+            not isinstance(delta, str)
+            or not isinstance(session_id, str)
+            or not session_id
+        ):
+            raise ServeProtocolError("invalid_serve_event: delta")
+        if etype.startswith("session.reasoning"):
+            return "reasoning", {"reasoning_content": delta, "sessionID": session_id}
+        return "text", {"content": delta, "sessionID": session_id}
+    if etype == "session.step.ended":
+        tokens = _as_dict(data.get("tokens"))
+        cache = _as_dict(tokens.get("cache"))
+        read_obj = cache.get("read")
+        if not tokens or not isinstance(read_obj, int):
+            raise ServeProtocolError("invalid_serve_event: cache.read")
+        out: dict[str, object] = {}
+        for key in ("input", "output", "reasoning"):
+            value = tokens.get(key)
+            if not isinstance(value, int) or isinstance(value, bool):
+                raise ServeProtocolError(f"invalid_serve_event: tokens.{key}")
+            out[key] = value
+        out["cached"] = read_obj
+        sid_obj = data.get("sessionID")
+        if isinstance(sid_obj, str):
+            out["sessionID"] = sid_obj
+        return "step_finish", out
+    if etype in ("session.execution.failed", "session.step.failed"):
+        err = _as_dict(data.get("error"))
+        message = err.get("message")
+        if not isinstance(message, str):
+            raise ServeProtocolError("invalid_serve_event: error")
+        status_obj = err.get("status")
+        status: int | None = (
+            status_obj
+            if isinstance(status_obj, int) and 100 <= status_obj <= 599
+            else None
+        )
+        if status is None:
+            err_type_obj = err.get("type")
+            err_type = err_type_obj if isinstance(err_type_obj, str) else ""
+            status = {"provider.free-limit": 429, "provider.auth": 401}.get(err_type)
+        err_out: dict[str, object] = {"statusCode": status, "message": message}
+        sid_err = data.get("sessionID")
+        if isinstance(sid_err, str):
+            err_out["sessionID"] = sid_err
+        return "error", err_out
+    if etype == "permission.asked":
+        return "permission", data
+    if etype == "form.created":
+        return "form_created", data
+    if etype.startswith("session.tool."):
+        return "tool_event", data
+    return etype, data
+
+
+parse_serve_event = _map_serve_event
+
+
 def _variant_for(model_id: str, effort: str) -> str:
     """`#variant` для модели: только если модель их поддерживает и значение допустимо (иначе CLI: exit 1)."""
     meta = ALLOWED_MODELS.get(model_id, {})
@@ -1138,7 +1998,9 @@ def _variant_for(model_id: str, effort: str) -> str:
         return ""
     values = meta.get("effort_values")
     if values and effort not in values:
-        _log(f"WARN variant {effort!r} is not in effort_values of {model_id}; suffix dropped")
+        _log(
+            f"WARN variant {effort!r} is not in effort_values of {model_id}; suffix dropped"
+        )
         return ""
     return effort
 
@@ -1174,8 +2036,9 @@ def _clean_err(lines: list[str] | str, limit: int = 600) -> str:
     return _mask_secrets(text)[-limit:]
 
 
-def _is_retryable_failure(rc: int | None, err_text: str, provider_status: int | None,
-                          had_output: bool) -> bool:
+def _is_retryable_failure(
+    rc: int | None, err_text: str, provider_status: int | None, had_output: bool
+) -> bool:
     """Прогон без какого-либо вывода и с rc != 0 — транзиторный отказ CLI (повторяем).
 
     Не повторяем: был вывод; процесс убит нами/таймаутом (rc < 0 или None);
@@ -1186,11 +2049,15 @@ def _is_retryable_failure(rc: int | None, err_text: str, provider_status: int |
     return provider_status not in _FATAL_HTTP
 
 
-def _error_payload(message: str, detail: str = "") -> dict[str, Any]:
+def _error_payload(message: str, detail: str = "") -> dict[str, object]:
     """Тело OpenAI-style ошибки (SSE-чанк `{"error":…}` и non-stream 502)."""
-    err: dict[str, Any] = {"message": message, "type": "proxy_error", "code": 502}
+    err: dict[str, object] = {
+        "message": _clean_err(message),
+        "type": "proxy_error",
+        "code": 502,
+    }
     if detail:
-        err["detail"] = detail
+        err["detail"] = _clean_err(detail)
     return {"error": err}
 
 
@@ -1211,7 +2078,9 @@ class _StartupGate:
 
     def acquire(self) -> None:
         if not _STARTUP_LOCK.acquire(timeout=max(0.0, self._wait_s)):
-            _log(f"startup_gate_timeout wait_s={self._wait_s:.1f}, starting without the gate")
+            _log(
+                f"startup_gate_timeout wait_s={self._wait_s:.1f}, starting without the gate"
+            )
             return
         with self._guard:
             self._held = True
@@ -1262,20 +2131,30 @@ class _SlotBulkhead:
     в `finally`/`release` на любом выходе (таймаут, исключение, отмена).
     """
 
-    def __init__(self, max_concurrent: int | None = None, max_waiters: int | None = None,
-                 wait_timeout_s: float | None = None,
-                 clock_fn: Callable[[], float] = time.monotonic) -> None:
+    def __init__(
+        self,
+        max_concurrent: int | None = None,
+        max_waiters: int | None = None,
+        wait_timeout_s: float | None = None,
+        clock_fn: Callable[[], float] = time.monotonic,
+    ) -> None:
         self._max = MAX_CONCURRENT if max_concurrent is None else max_concurrent
         self._max_waiters = MAX_SLOT_WAITERS if max_waiters is None else max_waiters
-        self._wait_timeout_s = SLOT_WAIT_TIMEOUT_S if wait_timeout_s is None else wait_timeout_s
+        self._wait_timeout_s = (
+            SLOT_WAIT_TIMEOUT_S if wait_timeout_s is None else wait_timeout_s
+        )
         self._clock = clock_fn
         self._cond = threading.Condition(threading.Lock())
         self.in_use = 0
         self.waiters = 0
 
     def acquire_ex(self, timeout: float | None = None) -> str:
-        """"ok" | "timeout" | "overflow" (все слоты заняты и очередь ждущих полна)."""
-        wait = self._wait_timeout_s if timeout is None else min(timeout, self._wait_timeout_s)
+        """ "ok" | "timeout" | "overflow" (все слоты заняты и очередь ждущих полна)."""
+        wait = (
+            self._wait_timeout_s
+            if timeout is None
+            else min(timeout, self._wait_timeout_s)
+        )
         with self._cond:
             if self.in_use < self._max:
                 self.in_use += 1
@@ -1312,9 +2191,13 @@ class _SpawnRateLimiter:
     по моменту резерва; `acquire` возвращает False без резерва, если ожидание превысит `max_wait_s`.
     """
 
-    def __init__(self, rate_rps: float = 1.0, burst: float = 1.0,
-                 clock_fn: Callable[[], float] = time.monotonic,
-                 sleep_fn: Callable[[float], None] = time.sleep) -> None:
+    def __init__(
+        self,
+        rate_rps: float = 1.0,
+        burst: float = 1.0,
+        clock_fn: Callable[[], float] = time.monotonic,
+        sleep_fn: Callable[[float], None] = time.sleep,
+    ) -> None:
         self._rate = max(rate_rps, 1e-9)
         self._burst = max(burst, 1.0)
         self._clock = clock_fn
@@ -1326,7 +2209,9 @@ class _SpawnRateLimiter:
     def acquire(self, max_wait_s: float | None = None) -> bool:
         with self._lock:
             now = self._clock()
-            self._tokens = min(self._burst, self._tokens + max(0.0, now - self._last) * self._rate)
+            self._tokens = min(
+                self._burst, self._tokens + max(0.0, now - self._last) * self._rate
+            )
             self._last = now
             wait = max(0.0, (1.0 - self._tokens) / self._rate)
             if max_wait_s is not None and wait > max_wait_s:
@@ -1336,16 +2221,31 @@ class _SpawnRateLimiter:
             self._sleep(wait)
         return True
 
+    def refund(self, amount: float = 1.0) -> None:
+        """Вернуть резерв, если дочерний процесс не был запущен."""
+        with self._lock:
+            self._tokens = min(self._burst, self._tokens + amount)
+
 
 class _RetryBudget:
     """Process-level бюджет повторных запусков: ёмкость `capacity`, +`per_request_refill` за запрос, +`reserve_rps` в секунду."""
 
-    def __init__(self, capacity: float | None = None, per_request_refill: float | None = None,
-                 reserve_rps: float | None = None,
-                 clock_fn: Callable[[], float] = time.monotonic) -> None:
+    def __init__(
+        self,
+        capacity: float | None = None,
+        per_request_refill: float | None = None,
+        reserve_rps: float | None = None,
+        clock_fn: Callable[[], float] = time.monotonic,
+    ) -> None:
         self._capacity = RETRY_BUDGET_MAX if capacity is None else capacity
-        self._per_request = RETRY_BUDGET_PER_REQUEST if per_request_refill is None else per_request_refill
-        self._reserve_rps = RETRY_BUDGET_RESERVE_RPS if reserve_rps is None else reserve_rps
+        self._per_request = (
+            RETRY_BUDGET_PER_REQUEST
+            if per_request_refill is None
+            else per_request_refill
+        )
+        self._reserve_rps = (
+            RETRY_BUDGET_RESERVE_RPS if reserve_rps is None else reserve_rps
+        )
         self._clock = clock_fn
         self._lock = threading.Lock()
         self.tokens = float(self._capacity)
@@ -1353,7 +2253,9 @@ class _RetryBudget:
 
     def _refill_time(self) -> None:
         now = self._clock()
-        self.tokens = min(self._capacity, self.tokens + max(0.0, now - self._last) * self._reserve_rps)
+        self.tokens = min(
+            self._capacity, self.tokens + max(0.0, now - self._last) * self._reserve_rps
+        )
         self._last = now
 
     def on_request(self) -> None:
@@ -1374,12 +2276,18 @@ class _RetryBudget:
 class _UpstreamBreaker:
     """Circuit Breaker зависимости `opencode run`: CLOSED -> OPEN (N подряд транзиентных отказов) -> HALF_OPEN (1 проба)."""
 
-    def __init__(self, fail_threshold: int | None = None, reset_timeout_s: float | None = None,
-                 clock_fn: Callable[[], float] = time.monotonic,
-                 rng_fn: Callable[[float, float], float] = random.uniform,
-                 max_half_open_probes: int = 1,
-                 log_fn: Callable[[str], None] | None = None) -> None:
-        self._threshold = CB_FAIL_THRESHOLD if fail_threshold is None else fail_threshold
+    def __init__(
+        self,
+        fail_threshold: int | None = None,
+        reset_timeout_s: float | None = None,
+        clock_fn: Callable[[], float] = time.monotonic,
+        rng_fn: Callable[[float, float], float] = random.uniform,
+        max_half_open_probes: int = 1,
+        log_fn: Callable[[str], None] | None = None,
+    ) -> None:
+        self._threshold = (
+            CB_FAIL_THRESHOLD if fail_threshold is None else fail_threshold
+        )
         self._reset_s = CB_RESET_S if reset_timeout_s is None else reset_timeout_s
         self._clock = clock_fn
         self._rng = rng_fn
@@ -1421,7 +2329,10 @@ class _UpstreamBreaker:
                 return True
             if self._state == "OPEN":
                 return False
-            if self._probes >= self._max_probes and now - self._probe_started < self._reset_s:
+            if (
+                self._probes >= self._max_probes
+                and now - self._probe_started < self._reset_s
+            ):
                 return False
             self._probes = 1 if self._probes >= self._max_probes else self._probes + 1
             self._probe_started = now
@@ -1447,7 +2358,9 @@ class _UpstreamBreaker:
                 self._state = "OPEN"
                 self._open_until = now + cooldown
                 self._probes = 0
-                self._say(f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}")
+                self._say(
+                    f"circuit_breaker state=OPEN failures={self._failures} cooldown_s={cooldown:.1f}"
+                )
 
 
 class _Resilience:
@@ -1462,6 +2375,7 @@ class _Resilience:
         self.spawn_limiter = _SpawnRateLimiter(SPAWN_RATE_PER_S, SPAWN_BURST)
         self.retry_budget = _RetryBudget()
         self.breaker = _UpstreamBreaker()
+        self.serve_health = _ServeHealth()
 
 
 _DEFAULT_RESILIENCE = _Resilience()
@@ -1471,13 +2385,20 @@ _slots = _DEFAULT_RESILIENCE.slots  # прежнее имя семафора с
 class _RequestAttempts:
     """Учёт запусков одного HTTP-запроса: потолок MAX_TOTAL_SPAWNS, общий deadline, breaker, Retry Budget, backoff."""
 
-    def __init__(self, res: _Resilience, deadline: float, max_total: int | None = None,
-                 sleep_fn: Callable[[float], None] = time.sleep,
-                 rng_fn: Callable[[float, float], float] = random.uniform,
-                 use_breaker: bool = True) -> None:
+    def __init__(
+        self,
+        res: _Resilience,
+        deadline: float,
+        max_total: int | None = None,
+        sleep_fn: Callable[[float], None] = time.sleep,
+        rng_fn: Callable[[float, float], float] = random.uniform,
+        use_breaker: bool = True,
+    ) -> None:
         self.res = res
         self.deadline = deadline
-        self.use_breaker = use_breaker  # False: прямой Google-маршрут без `opencode run`
+        self.use_breaker = (
+            use_breaker  # False: прямой Google-маршрут без `opencode run`
+        )
         self.max_total = MAX_TOTAL_SPAWNS if max_total is None else max_total
         self.total_spawns = 0
         self.retries = 0
@@ -1491,13 +2412,22 @@ class _RequestAttempts:
     def note_spawn(self) -> None:
         self.total_spawns += 1
 
+    def can_spawn(self) -> bool:
+        """Можно ли ещё запускать: суммарный потолок спавнов на запрос."""
+        return (
+            self.total_spawns < MAX_TOTAL_SPAWNS and self.total_spawns < self.max_total
+        )
+
     def remaining_s(self) -> float:
         return max(0.0, self.deadline - time.monotonic())
 
     def begin_attempt(self) -> bool:
         """Первичный запуск: потолок, deadline и Circuit Breaker (в HALF_OPEN резервирует единственную пробу)."""
-        return (self.total_spawns < self.max_total and time.monotonic() < self.deadline
-                and (not self.use_breaker or self.res.breaker.allow()))
+        return (
+            self.total_spawns < self.max_total
+            and time.monotonic() < self.deadline
+            and (not self.use_breaker or self.res.breaker.allow())
+        )
 
     def allow_retry(self, reason: str, charge_budget: bool = True) -> bool:
         """Можно ли сделать повторный запуск: потолок, deadline, breaker, Retry Budget; затем Full Jitter пауза.
@@ -1517,7 +2447,11 @@ class _RequestAttempts:
             _log(f"retry denied ({reason}): retry budget exhausted")
             return False
         self.retries += 1
-        delay = _retry_backoff_s(self.retries, self._rng) if FAIL_RETRY_BACKOFF_S > 0 else 0.0
+        delay = (
+            _retry_backoff_s(self.retries, self._rng)
+            if FAIL_RETRY_BACKOFF_S > 0
+            else 0.0
+        )
         delay = min(delay, self.remaining_s())
         if delay > 0:
             self._sleep(delay)
@@ -1564,43 +2498,1153 @@ class _PrefixDedup:
         current, prefix = self.current, self.prefix
         if current.startswith(prefix):
             self.prefix = ""
-            return current[len(prefix):]
+            return current[len(prefix) :]
         if len(current) >= len(prefix) or not prefix.startswith(current):
             self.prefix = ""
             return "\n\n" + current
         return ""
 
-    def finish(self) -> str:
-        """Конец попытки: накопленный, но неотданный текст (кроме чистого повтора части префикса)."""
-        leftover = ""
-        if self.prefix and self.current and not self.prefix.startswith(self.current):
-            leftover = "\n\n" + self.current
-        self.prefix = ""
-        return leftover
+    def finish(self) -> str:
+        """Конец попытки: накопленный, но неотданный текст (кроме чистого повтора части префикса)."""
+        leftover = ""
+        if self.prefix and self.current and not self.prefix.startswith(self.current):
+            leftover = "\n\n" + self.current
+        self.prefix = ""
+        return leftover
+
+
+def _dedup_retry_text(prefix: str, current: str) -> str:
+    """JSON-вариант dedup_prefix: подавить уже отданный префикс, переформулированный текст сохранить целиком."""
+    if prefix and current.startswith(prefix):
+        return current[len(prefix) :]
+    return current
+
+
+def _parent_lstart() -> str:
+    """lstart родителя дляargv помощника."""
+    try:
+        out = subprocess.run(
+            ["ps", "-o", "lstart=", "-p", str(os.getpid())],
+            capture_output=True,
+            text=True,
+            timeout=2,
+        )
+        return out.stdout.strip() or str(int(time.time()))
+    except (OSError, subprocess.SubprocessError):
+        return str(int(time.time()))
+
+
+def _lsof_listener_pid(port: int) -> int | None:
+    """PID слушателя порта одним вызовом lsof."""
+    _LSOF_CALLS.append(port)
+    try:
+        out = subprocess.run(
+            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
+            capture_output=True,
+            text=True,
+            timeout=2,
+        )
+    except (OSError, subprocess.SubprocessError):
+        return None
+    for line in out.stdout.splitlines():
+        if line.strip().isdecimal():
+            return int(line.strip())
+    return None
+
+
+def _serve_http(
+    port: int,
+    password: str,
+    method: str,
+    path: str,
+    body: dict[str, object] | None = None,
+    timeout: float = 3.0,
+    conn: http.client.HTTPConnection | None = None,
+    on_headers: Callable[[], None] | None = None,
+    deadline: float | None = None,
+    is_client_gone: Callable[[], bool] | None = None,
+) -> tuple[int, dict[str, object]]:
+    """Один HTTP-вызов serve с Basic-авторизацией без прокси."""
+    own_conn = conn is None
+    active_conn = (
+        conn
+        if conn is not None
+        else http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
+    )
+    if conn is not None:
+        conn.timeout = timeout
+        if conn.sock is not None:
+            _ = conn.sock.settimeout(timeout)
+
+    phase_socket: socket.socket | None = None
+
+    def check_phase() -> None:
+        """Ограничить следующую фазу оставшимся бюджетом и проверить отмену."""
+        if is_client_gone is not None and is_client_gone():
+            raise BrokenPipeError(errno.EPIPE, "client gone")
+        remaining = (
+            timeout if deadline is None else min(timeout, deadline - time.monotonic())
+        )
+        if remaining <= 0:
+            raise TimeoutError("serve deadline exceeded")
+        active_conn.timeout = remaining
+        connected_socket = active_conn.sock or phase_socket
+        if connected_socket is not None:
+            _ = connected_socket.settimeout(remaining)
+
+    try:
+        check_phase()
+        payload = json.dumps(body).encode("utf-8") if body is not None else None
+        auth = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("ascii")
+        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
+        active_conn.request(method, path, payload, headers)
+        # HTTP/1.0 отделяет сокет от conn после заголовков; бюджет тела остаётся обязательным.
+        phase_socket = active_conn.sock
+        check_phase()
+        resp = active_conn.getresponse()
+        if on_headers is not None:
+            on_headers()
+        raw = bytearray()
+        while not resp.isclosed():
+            check_phase()
+            chunk = resp.read1(65536)
+            if not chunk:
+                break
+            raw.extend(chunk)
+        parsed: dict[str, object] = {}
+        if raw:
+            parsed = _as_dict(_loads_object(raw.decode("utf-8", "replace")))
+        return int(resp.status), parsed
+    finally:
+        if own_conn:
+            active_conn.close()
+
+
+class _ServeLease:
+    """Владение деревом helper->serve одной попытки."""
+
+    def __init__(
+        self,
+        helper: subprocess.Popen[str],
+        serve_pid: int,
+        pgid: int,
+        lifeline_w: int,
+        lease_dir: Path,
+        attempt_id: str,
+        state_dir: str,
+        port: int = 0,
+    ) -> None:
+        self.helper = helper
+        self.serve_pid = serve_pid
+        self.pgid = pgid
+        self.lifeline_w = lifeline_w
+        self.lease_dir = lease_dir
+        self.attempt_id = attempt_id
+        self.state_dir = state_dir
+        self.port = port
+        self._closed = False
+        self._lock = threading.Lock()
+
+    def cleanup(self) -> None:
+        """Идемпотентная уборка только своей группы процессов."""
+        with self._lock:
+            if self._closed:
+                return
+            self._closed = True
+        try:
+            os.close(self.lifeline_w)
+        except OSError:
+            pass
+        _deadline = time.monotonic() + 4.0
+        if self.helper.poll() is None or _pid_alive(-self.pgid):
+            try:
+                if os.getpgid(self.pgid) == self.pgid:
+                    os.killpg(self.pgid, signal.SIGTERM)
+            except OSError:
+                pass
+            while time.monotonic() < _deadline:
+                if not _pid_alive(-self.pgid) and self.helper.poll() is not None:
+                    break
+                time.sleep(0.05)
+            if _pid_alive(-self.pgid) or self.helper.poll() is None:
+                try:
+                    os.killpg(self.pgid, signal.SIGKILL)
+                except OSError:
+                    pass
+                # Отдельное окно подтверждения смерти группы после SIGKILL (бюджет AC-011 <= 7 с).
+                _deadline = time.monotonic() + 2.0
+                while time.monotonic() < _deadline:
+                    if not _pid_alive(-self.pgid) and self.helper.poll() is not None:
+                        break
+                    time.sleep(0.05)
+            try:
+                _ = self.helper.wait(timeout=max(0.1, _deadline - time.monotonic()))
+            except (OSError, subprocess.SubprocessError):
+                pass
+        for stream in (self.helper.stdout, self.helper.stderr):
+            try:
+                if stream is not None:
+                    stream.close()
+            except OSError:
+                pass
+        if not _pid_alive(-self.pgid):
+            try:
+                (self.lease_dir / f"lease-{self.attempt_id}.json").unlink()
+            except OSError:
+                pass
+            if self.port:
+                with _PORT_ALLOC_LOCK:
+                    _ACTIVE_SERVE_PORTS.discard(self.port)
+        if self.state_dir and Path(self.state_dir).name.startswith("zen-serve-state-"):
+            shutil.rmtree(self.state_dir, ignore_errors=True)
+
+
+def _ensure_lease_dir(lease_dir: Path) -> None:
+    """Каталог lease: свой uid, не симлинк, права 0700."""
+    lease_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
+    try:
+        info = os.lstat(lease_dir)
+    except OSError as exc:
+        raise ServeUnavailable(f"lease dir unavailable: {exc}") from exc
+    if stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid():
+        raise ServeUnavailable("lease dir ownership check failed")
+    try:
+        os.chmod(lease_dir, 0o700)
+    except OSError:
+        pass
+
+
+def _discard_spawn_leftovers(port: int, lifeline_w: int, state_dir: str) -> None:
+    """Освободить ресурсы неудачного старта serve до создания _ServeLease."""
+    if lifeline_w >= 0:
+        try:
+            os.close(lifeline_w)
+        except OSError:
+            pass
+    if port:
+        with _PORT_ALLOC_LOCK:
+            _ACTIVE_SERVE_PORTS.discard(port)
+    if state_dir and Path(state_dir).name.startswith("zen-serve-state-"):
+        shutil.rmtree(state_dir, ignore_errors=True)
+
+
+def _spawn_serve(
+    attempt_id: str, serve_env: dict[str, str]
+) -> tuple[_ServeLease, int, str]:
+    """Запуск helper->serve, проверка слушателя и рукопожатия."""
+    port = 0
+    lifeline_w = -1
+    lease: _ServeLease | None = None
+    state_dir = serve_env.get("XDG_STATE_HOME", "")
+    try:
+        lease_dir = Path(LEASE_DIR)
+        _ensure_lease_dir(lease_dir)
+        with _PORT_ALLOC_LOCK:
+            for candidate in range(20000 + (os.getpid() % 20000), 60000):
+                if candidate in _ACTIVE_SERVE_PORTS:
+                    continue
+                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
+                try:
+                    probe.bind(("127.0.0.1", candidate))
+                    port = candidate
+                    _ACTIVE_SERVE_PORTS.add(candidate)
+                    break
+                except OSError:
+                    continue
+                finally:
+                    probe.close()
+        if not port:
+            raise ServeUnavailable("no free serve port")
+        password = serve_env.get("OPENCODE_SERVER_PASSWORD", "")
+        lifeline_r, lifeline_w = os.pipe()
+        try:
+            helper: subprocess.Popen[str] = subprocess.Popen(
+                [
+                    sys.executable,
+                    "-I",
+                    str(Path(__file__).resolve()),
+                    "--serve-helper",
+                    attempt_id,
+                    str(port),
+                    str(OPENCODE_BIN),
+                    str(lease_dir),
+                    str(os.getpid()),
+                    _parent_lstart(),
+                ],
+                stdin=lifeline_r,
+                stdout=subprocess.PIPE,
+                stderr=subprocess.PIPE,
+                start_new_session=True,
+                close_fds=True,
+                env=serve_env,
+                text=True,
+            )
+        finally:
+            try:
+                os.close(lifeline_r)
+            except OSError:
+                pass
+        lease = _ServeLease(
+            helper,
+            0,
+            helper.pid,
+            lifeline_w,
+            lease_dir,
+            attempt_id,
+            state_dir,
+            port,
+        )
+        assert helper.stdout is not None
+        out_fd = helper.stdout.fileno()
+        _hs_deadline = time.monotonic() + 3.0
+        ready, _w, _x = select.select(
+            [out_fd], [], [], max(0.0, _hs_deadline - time.monotonic())
+        )
+        if not ready:
+            raise ServeUnavailable("serve helper handshake timeout")
+        line_bytes = b""
+        while not line_bytes.endswith(b"\n"):
+            if time.monotonic() >= _hs_deadline:
+                raise ServeUnavailable("serve helper handshake timeout")
+            _ready, _w2, _x2 = select.select(
+                [out_fd], [], [], max(0.0, _hs_deadline - time.monotonic())
+            )
+            if not _ready:
+                raise ServeUnavailable("serve helper handshake timeout")
+            chunk_b = os.read(out_fd, 1)
+            if not chunk_b:
+                break
+            line_bytes += chunk_b
+        line = line_bytes.decode("utf-8", "replace")
+        handshake = _as_dict(_loads_object(line)) if line else {}
+        serve_pid = _as_int(handshake.get("serve_pid"))
+        pgid = _as_int(handshake.get("pgid"))
+        lease.serve_pid = serve_pid
+        if not serve_pid or pgid != helper.pid or helper.poll() is not None:
+            raise ServeUnavailable("serve ownership handshake mismatch")
+        _listener_deadline = time.monotonic() + 3.0
+        listener_pid = _lsof_listener_pid(port)
+        while (
+            listener_pid is None
+            and time.monotonic() < _listener_deadline
+            and helper.poll() is None
+        ):
+            time.sleep(0.2)
+            listener_pid = _lsof_listener_pid(port)
+        if not (
+            listener_pid is not None
+            and listener_pid == serve_pid
+            and _pid_pgid(listener_pid) == pgid
+            and helper.poll() is None
+        ):
+            raise ServeUnavailable(
+                "listener ownership verification failed: foreign listener on serve port"
+            )
+        # stderr помощника дренируется в ограниченный буфер без логирования секретов.
+        threading.Thread(
+            target=_drain_stderr,
+            args=(helper, collections.deque(maxlen=64)),
+            daemon=True,
+        ).start()
+        return lease, port, password
+    except BaseException as exc:
+        if lease is not None:
+            lease.cleanup()
+        else:
+            _discard_spawn_leftovers(port, lifeline_w, state_dir)
+        if isinstance(exc, ServeUnavailable):
+            raise
+        if isinstance(exc, (OSError, ValueError, subprocess.SubprocessError)):
+            raise ServeUnavailable(f"serve spawn os error: {exc}") from exc
+        raise
+
+
+def _startup_reaper(lease_dir: Path | None = None) -> int:
+    """Убрать осиротевшие lease мёртвого родителя при старте моста."""
+    target = Path(LEASE_DIR) if lease_dir is None else lease_dir
+    removed = 0
+    try:
+        _dir_info = os.lstat(target)
+        if stat.S_ISLNK(_dir_info.st_mode) or _dir_info.st_uid != os.getuid():
+            return 0
+        files = list(target.glob("lease-*.json"))
+    except OSError:
+        return 0
+    for path in files:
+        try:
+            _file_info = os.lstat(path)
+            if stat.S_ISLNK(_file_info.st_mode) or _file_info.st_uid != os.getuid():
+                continue
+            data = _as_dict(_loads_object(path.read_text("utf-8")))
+            parent_pid = _as_int(data.get("parent_pid"))
+            helper_pid = _as_int(data.get("helper_pid"))
+            pgid = _as_int(data.get("pgid"))
+        except (OSError, ValueError, TypeError):
+            continue
+        if _as_int(data.get("owner_uid")) != os.getuid():
+            continue
+        # Сверка lstart живого родителя/помощника с lease: переиспользованный PID не трогаем.
+        _lstart_ok = True
+        for _pid_key, _ts_key in (
+            ("parent_pid", "parent_start_ts"),
+            ("helper_pid", "helper_lstart"),
+        ):
+            _pid_v = _as_int(data.get(_pid_key))
+            _ts_v = str(data.get(_ts_key) or "")
+            if _pid_v > 0 and _ts_v and _pid_alive(_pid_v):
+                try:
+                    _live = subprocess.run(
+                        ["ps", "-o", "lstart=", "-p", str(_pid_v)],
+                        capture_output=True,
+                        text=True,
+                        timeout=2,
+                    ).stdout.strip()
+                except (OSError, subprocess.SubprocessError):
+                    _live = ""
+                # helper_lstart записан epoch-секундами, parent_start_ts — lstart: сверяем только lstart-формат.
+                if _live and not _ts_v.isdecimal() and _live != _ts_v:
+                    if _pid_key == "helper_pid":
+                        # PID помощника переиспользован: убивать группу нельзя.
+                        helper_pid = 0
+                    else:
+                        _lstart_ok = False
+        if not _lstart_ok:
+            continue
+        parent_alive = parent_pid > 0 and _pid_alive(parent_pid)
+        if parent_alive:
+            continue
+        if helper_pid > 0 and pgid == helper_pid and _pid_alive(helper_pid):
+            try:
+                cmd = subprocess.run(
+                    ["ps", "-ww", "-o", "command=", "-p", str(helper_pid)],
+                    capture_output=True,
+                    text=True,
+                    timeout=2,
+                ).stdout
+            except (OSError, subprocess.SubprocessError):
+                cmd = ""
+            if "--serve-helper" not in cmd:
+                continue
+            try:
+                os.killpg(pgid, signal.SIGTERM)
+            except OSError:
+                pass
+            _reap_deadline = time.monotonic() + 2.0
+            while _pid_alive(-pgid) and time.monotonic() < _reap_deadline:
+                time.sleep(0.05)
+            if _pid_alive(-pgid):
+                try:
+                    os.killpg(pgid, signal.SIGKILL)
+                except OSError:
+                    pass
+                while _pid_alive(-pgid) and time.monotonic() < _reap_deadline + 2.0:
+                    time.sleep(0.05)
+        if pgid <= 0 or not _pid_alive(-pgid):
+            try:
+                path.unlink()
+                removed += 1
+            except OSError:
+                pass
+    return removed
+
+
+def _pid_alive(pid: int) -> bool:
+    """Жив ли процесс; отрицательный pid — проверка группы через kill(-pgid, 0)."""
+    try:
+        os.kill(pid, 0)
+        return True
+    except OSError:
+        return False
+
+
+def _pid_pgid(pid: int) -> int:
+    """PGID процесса или -1 при ошибке."""
+    try:
+        return os.getpgid(pid)
+    except OSError:
+        return -1
+
+
+_find_listener_pid = _lsof_listener_pid
+
+
+class _ToolItem(TypedDict):
+    """Накопленный native вызов serve."""
+
+    name: str
+    text: str
+    input: dict[str, object] | None
+
+
+class _ServeToolState:
+    """Накопление native tool lifecycle serve до полного ввода."""
+
+    def __init__(self) -> None:
+        self.tools: dict[str, _ToolItem] = {}
+        self.emitted: set[str] = set()
+
+    def feed(self, data: dict[str, object]) -> None:
+        """Запомнить фрагмент native вызова."""
+        call_id = str(data.get("id") or "")
+        if not call_id:
+            return
+        item = self.tools.setdefault(call_id, {"name": "", "text": "", "input": None})
+        name = data.get("name")
+        if isinstance(name, str) and name:
+            item["name"] = name
+        text_value = data.get("text")
+        if isinstance(text_value, str):
+            item["text"] = text_value
+        input_value = data.get("input")
+        if isinstance(input_value, dict):
+            item["input"] = _as_dict(input_value)
+
+    def complete(
+        self, call_id: str, event_type: str = ""
+    ) -> tuple[str, dict[str, object]] | None:
+        """Готовый вызов из called.input или input.ended.text; статус — из типа события."""
+        if call_id in self.emitted:
+            return None
+        item = self.tools.get(call_id)
+        if item is None or not item["name"]:
+            return None
+        args = item["input"]
+        if not isinstance(args, dict):
+            text_value = item["text"]
+            try:
+                parsed: object = json.loads(text_value) if text_value else None
+            except ValueError:
+                return None
+            if not isinstance(parsed, dict):
+                return None
+            args = _as_dict(parsed)
+        self.emitted.add(call_id)
+        _status = (
+            "completed"
+            if any(
+                k in event_type for k in ("completed", "succeeded", "success", "called")
+            )
+            else "error"
+        )
+        return "tool_use", {
+            "part": {"tool": item["name"], "state": {"input": args, "status": _status}},
+            "call_id": call_id,
+        }
+
+
+_ToolInputAccumulator = _ServeToolState
+
+
+def _native_call_as_dsh(
+    payload: dict[str, object], tools: list[dict[str, object]] | None
+) -> list[dict[str, object]]:
+    """Native serve-вызов в DSH-вызов через канонический _native_to_tool_calls (fit_args + multiedit)."""
+    part = _as_dict(payload.get("part"))
+    state = _as_dict(part.get("state"))
+    tool = part.get("tool")
+    if not isinstance(tool, str) or not tool:
+        return []
+    args = _as_dict(state.get("input"))
+    return _native_to_tool_calls(tool, args, list(tools or []))
+
+
+def _serve_one_attempt(
+    model: str,
+    prompt: str,
+    effort: str,
+    workdir: Path,
+    on_reasoning: Callable[[str], None],
+    on_text: Callable[[str], None],
+    on_tool: Callable[[dict[str, object]], None],
+    t0: float,
+    is_client_gone: Callable[[], bool] | None = None,
+    on_status: Callable[[str], None] | None = None,
+    thinking_enabled: bool = True,
+    deadline: float | None = None,
+    proxy_url: str | None = None,
+    on_startup_ready: Callable[[], None] | None = None,
+    emulate_tools: bool = False,
+) -> _ServeResult:
+    """Одна попытка serve: helper, сессия, SSE, prompt и канонические события."""
+    result: _ServeResult = {
+        "reasonings": [],
+        "texts": [],
+        "native_calls": [],
+        "usage": {},
+        "error": None,
+        "exit_reason": "",
+        "delivered": False,
+        "terminal": "",
+        "first_event_at": None,
+        "first_token_at": None,
+        "step_closed": False,
+        "first_event_ms": None,
+        "ttft_ms": None,
+        "prompt_status": None,
+        "transient_error": False,
+    }
+    attempt_deadline = min(
+        deadline if deadline is not None else t0 + TIMEOUT_S, t0 + TIMEOUT_S
+    )
+    if is_client_gone is not None and is_client_gone():
+        result["exit_reason"] = "client_gone"
+        return result
+    try:
+        serve_env = _serve_env(model)
+    except OSError as exc:
+        raise ServeUnavailable(f"serve env failed: {exc}") from exc
+    if proxy_url:
+        serve_env["HTTP_PROXY"] = proxy_url
+        serve_env["HTTPS_PROXY"] = proxy_url
+    password = serve_env.get("OPENCODE_SERVER_PASSWORD", "")
+    attempt_id = uuid.uuid4().hex
+    lease, port, _pw = _spawn_serve(attempt_id, serve_env)
+    session_id = ""
+    sse_conn: http.client.HTTPConnection | None = None
+    prompt_status: dict[str, object] = {}
+    control_conn: list[http.client.HTTPConnection | None] = [None]
+
+    def _ctrl_http(
+        method: str,
+        path: str,
+        body: dict[str, object] | None = None,
+        timeout: float = 3.0,
+    ) -> tuple[int, dict[str, object]]:
+        """Управляющий вызов serve по одному keep-alive соединению."""
+        for attempt in (0, 1):
+            conn = control_conn[0]
+            if conn is None:
+                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
+                control_conn[0] = conn
+            try:
+                return _serve_http(
+                    port,
+                    password,
+                    method,
+                    path,
+                    body,
+                    timeout=timeout,
+                    conn=conn,
+                    deadline=attempt_deadline,
+                    is_client_gone=is_client_gone,
+                )
+            except (OSError, http.client.HTTPException):
+                try:
+                    conn.close()
+                except OSError:
+                    pass
+                control_conn[0] = None
+                if attempt:
+                    raise
+        raise ServeUnavailable("serve control connection failed")
+
+    try:
+        status = 0
+        active: dict[str, object] = {}
+        ready_deadline = min(time.monotonic() + 3.0, attempt_deadline)
+        while True:
+            try:
+                status, active = _ctrl_http("GET", "/api/session/active", timeout=3.0)
+                break
+            except (OSError, http.client.HTTPException) as exc:
+                if time.monotonic() >= ready_deadline:
+                    raise ServeUnavailable(f"serve ready failed: {exc}") from exc
+                time.sleep(0.05)
+        if status in (401, 403):
+            raise ServeSecurityError(f"serve auth HTTP {status}")
+        if status in (400, 404, 422):
+            raise ServeSecurityError(f"serve invalid request HTTP {status}")
+        if status != 200 or not isinstance(active.get("data"), dict):
+            raise ServeUnavailable(f"serve ready HTTP {status}")
+        route = _model_route(model)
+        provider, _sep, raw_id = route.partition("/")
+        variant = _variant_for(model, effort)
+        model_body: dict[str, object] = {
+            "providerID": provider or "opencode",
+            "id": raw_id or model,
+        }
+        if variant:
+            model_body["variant"] = variant
+        status, created = _ctrl_http(
+            "POST",
+            "/api/session",
+            {
+                "location": {"directory": str(workdir)},
+                "model": model_body,
+                "permissions": [
+                    {
+                        "action": "*",
+                        "resource": "*",
+                        "effect": _serve_permission_effect(),
+                    }
+                ],
+            },
+            timeout=3.0,
+        )
+        if status in (401, 403):
+            raise ServeSecurityError(f"serve create HTTP {status}")
+        if status in (400, 404, 422):
+            raise ServeSecurityError(f"serve invalid request HTTP {status}")
+        created_data = created.get("data")
+        if (
+            status != 200
+            or not isinstance(created_data, dict)
+            or not created_data.get("id")
+        ):
+            raise ServeUnavailable(f"serve create HTTP {status}")
+        session_id = str(created_data["id"])
+        sse_conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
+        auth = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("ascii")
+        sse_conn.request(
+            "GET",
+            "/api/event",
+            None,
+            {"Authorization": f"Basic {auth}", "Accept": "text/event-stream"},
+        )
+        sse_resp = sse_conn.getresponse()
+        if sse_resp.status in (401, 403):
+            raise ServeSecurityError(f"serve event HTTP {sse_resp.status}")
+        if sse_resp.status in (400, 404, 422):
+            raise ServeSecurityError(f"serve event HTTP {sse_resp.status}")
+        if sse_resp.status != 200:
+            raise ServeUnavailable(f"serve event HTTP {sse_resp.status}")
+        events: queue.Queue[dict[str, object] | None] = queue.Queue(maxsize=4096)
+        stop_event = threading.Event()
+        if sse_conn.sock is not None:
+            # Без таймаута сокета: после первого таймаута SocketIO считает поток закрытым,
+            # а любая пауза SSE > 0.5 с превращалась бы в ложный EOF. Остановка — shutdown в finally.
+            _ = sse_conn.sock.settimeout(None)
+        if on_startup_ready is not None:
+            on_startup_ready()
+
+        def _put_event(item: dict[str, object] | None) -> bool:
+            """Неблокирующая постановка с проверкой stop_event."""
+            while not stop_event.is_set():
+                try:
+                    events.put(item, timeout=0.25)
+                    return True
+                except queue.Full:
+                    continue
+            return False
+
+        def _reader() -> None:
+            """Читатель SSE в очередь событий; тишина сокета не рвёт поток."""
+            try:
+                while not stop_event.is_set():
+                    try:
+                        line = sse_resp.readline()
+                    except OSError:
+                        # Сокет закрыт или сброшен: watchdog главного цикла решает судьбу попытки.
+                        break
+                    if not line:
+                        break
+                    text_line = line.decode("utf-8", "replace").strip()
+                    if not text_line.startswith("data:"):
+                        continue
+                    payload = text_line[5:].strip()
+                    if not payload or payload == "[DONE]":
+                        continue
+                    try:
+                        obj: dict[str, object] | None = _loads_serve_object(payload)
+                    except ServeProtocolError:
+                        _ = _put_event({"type": "__invalid_json__", "data": {}})
+                        continue
+                    _ = _put_event(obj)
+            except (OSError, ValueError):
+                pass
+            finally:
+                _ = _put_event(None)
+
+        reader_thread = threading.Thread(target=_reader, daemon=True)
+        reader_thread.start()
+        prompt_send_start = time.monotonic()
 
+        def _prompt_worker() -> None:
+            """Доставка prompt параллельно чтению SSE."""
 
-def _dedup_retry_text(prefix: str, current: str) -> str:
-    """JSON-вариант dedup_prefix: подавить уже отданный префикс, переформулированный текст сохранить целиком."""
-    if prefix and current.startswith(prefix):
-        return current[len(prefix):]
-    return current
+            def _on_headers() -> None:
+                prompt_status["headers_at"] = time.monotonic()
+
+            try:
+                st, _body = _serve_http(
+                    port,
+                    password,
+                    "POST",
+                    f"/api/session/{session_id}/prompt",
+                    {"text": prompt, "files": [], "delivery": "steer", "resume": True},
+                    timeout=65.0,
+                    on_headers=_on_headers,
+                    deadline=attempt_deadline,
+                    is_client_gone=is_client_gone,
+                )
+                prompt_status["status"] = st
+                if st in (401, 403):
+                    prompt_status["security"] = True
+            except (OSError, http.client.HTTPException) as exc:
+                prompt_status["error"] = str(exc)
+
+        prompt_thread = threading.Thread(target=_prompt_worker, daemon=True)
+        prompt_thread.start()
+        tool_state = _ServeToolState()
+        seen_steps: set[str] = set()
+        deadline = min(
+            deadline if deadline is not None else prompt_send_start + TIMEOUT_S,
+            prompt_send_start + TIMEOUT_S,
+        )
+        status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25)
+        _status_emitted = [0]
+        last_token_at = prompt_send_start
+        while time.monotonic() < deadline:
+            if is_client_gone is not None and is_client_gone():
+                result["exit_reason"] = "client_gone"
+                return result
+            now = time.monotonic()
+            if result["first_event_at"] is None and now - prompt_send_start > float(
+                FIRST_EVENT_TIMEOUT_S
+            ):
+                result["exit_reason"] = "first_event_timeout"
+                result["delivered"] = bool(prompt_status.get("headers_at"))
+                return result
+            if (
+                result["first_event_at"] is not None
+                and result["first_token_at"] is None
+                and now - prompt_send_start > float(FIRST_TOKEN_TIMEOUT_S)
+            ):
+                result["exit_reason"] = "first_token_timeout"
+                result["delivered"] = True
+                return result
+            if result["first_token_at"] is not None and now - last_token_at > float(
+                STALL_TIMEOUT_S
+            ):
+                result["exit_reason"] = "stall_timeout"
+                result["delivered"] = True
+                return result
+            # Классификация HTTP-статуса prompt по FALLBACK_DECISION_TABLE до ожидания SSE-события.
+            _ps = prompt_status.get("status")
+            if isinstance(_ps, int) and _ps != 200 and result["prompt_status"] is None:
+                result["prompt_status"] = _ps
+                if _ps in (401, 403):
+                    raise ServeSecurityError(f"serve prompt HTTP {_ps}")
+                if _ps in (400, 404, 422):
+                    raise ServeSecurityError(f"serve prompt HTTP {_ps}")
+                _delivered_now = bool(
+                    result["texts"] or result["reasonings"] or result["native_calls"]
+                )
+                result["delivered"] = _delivered_now
+                if _ps == 429:
+                    result["exit_reason"] = "prompt_status_429"
+                    result["transient_error"] = True
+                    return result
+                if 500 <= _ps <= 599:
+                    result["exit_reason"] = f"prompt_status_{_ps}"
+                    return result
+            _prompt_err = prompt_status.get("error")
+            if isinstance(_prompt_err, str) and not (
+                result["texts"] or result["reasonings"] or result["native_calls"]
+            ):
+                raise ServeUnavailable(f"serve prompt failed: {_prompt_err}")
+            if thinking_enabled and on_status is not None and now >= status_next:
+                if result["first_token_at"] is None:
+                    on_status(
+                        STATUS_INITIAL if _status_emitted[0] == 0 else STATUS_WAITING
+                    )
+                    _status_emitted[0] += 1
+                    status_next = now + STATUS_WAITING_INTERVAL_S
+                elif now - last_token_at >= float(STALL_HEARTBEAT_INTERVAL_S):
+                    on_status(STATUS_CONTINUATION)
+                    status_next = now + float(STALL_HEARTBEAT_INTERVAL_S)
+            try:
+                event = events.get(timeout=0.02)
+            except queue.Empty:
+                continue
+            if event is None:
+                if not result["terminal"]:
+                    result["exit_reason"] = "invalid_serve_event"
+                    result["delivered"] = bool(
+                        prompt_status.get("headers_at") or result["first_event_at"]
+                    )
+                break
+            etype_raw = str(event.get("type") or "")
+            if etype_raw == "__invalid_json__":
+                result["exit_reason"] = "invalid_serve_event"
+                result["delivered"] = True
+                return result
+            data_raw = _as_dict(event.get("data"))
+            _raw_sid = data_raw.get("sessionID")
+            if (
+                etype_raw not in ("server.connected", "form.created")
+                and isinstance(_raw_sid, str)
+                and _raw_sid
+                and _raw_sid != session_id
+            ):
+                continue
+            # form.created: безопасность до любой проверки title/fields/схемы.
+            if etype_raw == "form.created":
+                form = _as_dict(data_raw.get("form"))
+                form_session = form.get("sessionID")
+                form_id = form.get("id")
+                if form_session == session_id and isinstance(form_id, str) and form_id:
+                    result["step_closed"] = True
+                    st, _b = _ctrl_http(
+                        "POST",
+                        f"/api/session/{session_id}/form/{form_id}/cancel",
+                        None,
+                        timeout=0.25,
+                    )
+                    if st not in (200, 204):
+                        raise ServeSecurityError(f"form cancel HTTP {st}")
+                    st2, _b2 = _ctrl_http(
+                        "POST",
+                        f"/api/session/{session_id}/interrupt",
+                        None,
+                        timeout=0.25,
+                    )
+                    if st2 not in (200, 204):
+                        raise ServeSecurityError(f"form interrupt HTTP {st2}")
+                    result["terminal"] = "cancelled"
+                    break
+                if form_session == session_id:
+                    raise ServeSecurityError("form.created without id")
+                continue
+            if prompt_status.get("security"):
+                raise ServeSecurityError("serve prompt auth failed")
+            try:
+                _mapped = _map_serve_event(event)
+            except ServeProtocolError:
+                result["exit_reason"] = "invalid_serve_event"
+                result["delivered"] = True
+                return result
+            if _mapped is None:
+                continue
+            etype, payload = _mapped
+            event_session = (
+                payload.get("sessionID") if isinstance(payload, dict) else None
+            )
+            if etype_raw not in ("server.connected",) and event_session not in (
+                None,
+                session_id,
+            ):
+                continue
+            is_execution = etype_raw in (
+                "session.execution.started",
+                "session.step.started",
+                "session.reasoning.started",
+                "session.reasoning.delta",
+                "session.text.delta",
+                "session.step.ended",
+            ) or etype in ("reasoning", "text", "step_finish")
+            if is_execution and result["first_event_at"] is None:
+                result["first_event_at"] = time.monotonic()
+                result["first_event_ms"] = int(
+                    ((result["first_event_at"] or 0.0) - t0) * 1000
+                )
+            if etype == "permission":
+                result["step_closed"] = True
+                request_id = str(payload.get("id") or "")
+                st, _b = _ctrl_http(
+                    "POST",
+                    f"/api/session/{session_id}/permission/{request_id}/reply",
+                    {"decision": "reject"},
+                    timeout=0.25,
+                )
+                if st not in (200, 204):
+                    raise ServeSecurityError(f"permission reply HTTP {st}")
+                st2, _b2 = _ctrl_http(
+                    "POST",
+                    f"/api/session/{session_id}/interrupt",
+                    None,
+                    timeout=0.25,
+                )
+                if st2 not in (200, 204):
+                    raise ServeSecurityError(f"permission interrupt HTTP {st2}")
+                continue
+            if result["step_closed"] and etype in ("reasoning", "text"):
+                continue
+            if etype == "reasoning":
+                text_value = str(payload.get("reasoning_content") or "")
+                if text_value:
+                    if result["first_token_at"] is None:
+                        result["first_token_at"] = time.monotonic()
+                        result["ttft_ms"] = int(
+                            ((result["first_token_at"] or 0.0) - t0) * 1000
+                        )
+                    result["reasonings"].append(text_value)
+                    last_token_at = time.monotonic()
+                    on_reasoning(text_value)
+            elif etype == "text":
+                text_value = str(payload.get("content") or "")
+                if text_value:
+                    if result["first_token_at"] is None:
+                        result["first_token_at"] = time.monotonic()
+                        result["ttft_ms"] = int(
+                            ((result["first_token_at"] or 0.0) - t0) * 1000
+                        )
+                    result["texts"].append(text_value)
+                    last_token_at = time.monotonic()
+                    on_text(text_value)
+            elif etype == "tool_event":
+                if (
+                    etype_raw == "session.tool.input.delta"
+                    and result["first_token_at"] is not None
+                ):
+                    last_token_at = time.monotonic()
+                tool_state.feed(payload)
+                call_id = str(payload.get("id") or "")
+                if etype_raw in (
+                    "session.tool.called",
+                    "session.tool.failed",
+                    "session.tool.success",
+                ):
+                    done = tool_state.complete(call_id, etype_raw)
+                    if done is not None:
+                        result["native_calls"].append(done[1])
+                        on_tool(done[1])
+                        if result["first_token_at"] is None:
+                            result["first_token_at"] = time.monotonic()
+                            result["ttft_ms"] = int(
+                                ((result["first_token_at"] or 0.0) - t0) * 1000
+                            )
+            elif etype == "step_finish":
+                step_key = str(
+                    _as_dict(payload).get("assistantMessageID")
+                    or data_raw.get("assistantMessageID")
+                    or ""
+                )
+                if step_key and step_key in seen_steps:
+                    continue
+                if step_key:
+                    seen_steps.add(step_key)
+                # payload шага после _map не несёт assistantMessageID: ключ из data_raw выше.
+                for key in ("input", "output", "cached", "reasoning"):
+                    result["usage"][key] = result["usage"].get(key, 0) + _as_int(
+                        payload.get(key)
+                    )
+                # Завершить native вызовы без called: аргументы из input.ended.text.
+                for call_id in list(tool_state.tools):
+                    done = tool_state.complete(call_id, etype_raw)
+                    if done is not None:
+                        result["native_calls"].append(done[1])
+                        on_tool(done[1])
+                if result["native_calls"] or (
+                    emulate_tools and _split_tool_calls(["".join(result["texts"])])[1]
+                ):
+                    if result["first_token_at"] is None and result["native_calls"]:
+                        result["first_token_at"] = time.monotonic()
+                        result["ttft_ms"] = int(
+                            ((result["first_token_at"] or 0.0) - t0) * 1000
+                        )
+                    result["terminal"] = "tool_calls"
+                    break
+            elif etype == "error":
+                result["error"] = payload
+                result["transient_error"] = _is_transient_stream_error(payload)
+                result["terminal"] = "failed"
+                break
+            elif etype_raw == "session.execution.succeeded":
+                result["terminal"] = "succeeded"
+                break
+        if (
+            not result["terminal"]
+            and not result["exit_reason"]
+            and time.monotonic() >= deadline
+        ):
+            result["exit_reason"] = "timeout"
+        return result
+    finally:
+        _se = locals().get("stop_event")
+        if isinstance(_se, threading.Event):
+            _se.set()
+        if sse_conn is not None:
+            if sse_conn.sock is not None:
+                try:
+                    _ = sse_conn.sock.shutdown(socket.SHUT_RDWR)
+                except OSError:
+                    pass
+            try:
+                sse_conn.close()
+            except OSError:
+                pass
+        for _th_name in ("reader_thread", "prompt_thread"):
+            _th = locals().get(_th_name)
+            if isinstance(_th, threading.Thread):
+                _th.join(timeout=0.5)
+        if session_id:
+            # Не более одной быстрой попытки interrupt/DELETE (<= 0.25 с), затем lease.cleanup().
+            try:
+                _ = _serve_http(
+                    port,
+                    password,
+                    "POST",
+                    f"/api/session/{session_id}/interrupt",
+                    None,
+                    timeout=0.25,
+                )
+            except (OSError, http.client.HTTPException):
+                pass
+            try:
+                _ = _serve_http(
+                    port,
+                    password,
+                    "DELETE",
+                    f"/api/session/{session_id}",
+                    None,
+                    timeout=0.25,
+                )
+            except (OSError, http.client.HTTPException):
+                pass
+        if control_conn[0] is not None:
+            try:
+                control_conn[0].close()
+            except OSError:
+                pass
+            control_conn[0] = None
+        if sse_conn is not None:
+            try:
+                sse_conn.close()
+            except OSError:
+                pass
+        lease.cleanup()
 
 
 def _new_exit_state() -> dict[str, Any]:
-    return {"t0": time.monotonic(), "mode": "", "model": "", "status": 0, "exit_reason": "",
-            "attempts": None, "tools": 0, "out_chars": 0, "rc": None}
+    return {
+        "t0": time.monotonic(),
+        "mode": "",
+        "model": "",
+        "status": 0,
+        "exit_reason": "",
+        "attempts": None,
+        "tools": 0,
+        "out_chars": 0,
+        "rc": None,
+        "transport": "none",
+        "first_event_ms": None,
+        "ttft_ms": None,
+        "transport_history": [],
+    }
 
 
 def _log_exit(xs: dict[str, Any]) -> None:
     """O-EXIT/v1: одна структурная строка bridge.log на каждый выход Handler.do_POST."""
-    attempts = xs.get("attempts")
-    status = int(xs.get("status") or 0)
-    reason = str(xs.get("exit_reason") or "") or ("ok" if status == 200 else (f"http_{status}" if status else "client_gone"))
-    _log(f"O-EXIT/v1 mode={xs.get('mode') or '-'} model={xs.get('model') or '-'} status={status} "
-         f"exit_reason={reason} rc={xs.get('rc')} total_spawns={attempts.total_spawns if attempts else 0} "
-         f"retries={attempts.retries if attempts else 0} signal={attempts.signal if attempts else 0} "
-         f"tools={xs.get('tools') or 0} out_chars={xs.get('out_chars') or 0} "
-         f"duration_s={time.monotonic() - float(xs['t0']):.2f}")
+    attempts_obj = xs.get("attempts")
+    attempts_t = attempts_obj if isinstance(attempts_obj, _RequestAttempts) else None
+    status_obj = xs.get("status")
+    status = status_obj if isinstance(status_obj, int) else 0
+    reason_obj = xs.get("exit_reason")
+    reason = (reason_obj if isinstance(reason_obj, str) and reason_obj else "") or (
+        "ok" if status == 200 else (f"http_{status}" if status else "client_gone")
+    )
+    t0_obj = xs.get("t0")
+    t0 = t0_obj if isinstance(t0_obj, float) else time.monotonic()
+    _log(
+        f"O-EXIT/v1 mode={xs.get('mode') or '-'} model={xs.get('model') or '-'} status={status} "
+        f"exit_reason={reason} rc={xs.get('rc')} total_spawns={attempts_t.total_spawns if attempts_t else 0} "
+        f"retries={attempts_t.retries if attempts_t else 0} signal={attempts_t.signal if attempts_t else 0} "
+        f"tools={xs.get('tools') or 0} out_chars={xs.get('out_chars') or 0} "
+        f"transport={xs.get('transport') or 'none'} first_event_ms={xs.get('first_event_ms')} "
+        f"ttft_ms={xs.get('ttft_ms')} transport_history={xs.get('transport_history') or []} "
+        f"duration_s={time.monotonic() - t0:.2f}"
+    )
 
 
 def _resolve_launcher() -> str:
@@ -1658,7 +3702,9 @@ def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
     hdr = handler.headers.get("Authorization", "")
     if hdr.startswith("Bearer "):
         return _token_eq(hdr[7:].strip(), AUTH_KEY)
-    return _token_eq(handler.headers.get("x-api-key", ""), AUTH_KEY) or _token_eq(hdr.strip(), AUTH_KEY)
+    return _token_eq(handler.headers.get("x-api-key", ""), AUTH_KEY) or _token_eq(
+        hdr.strip(), AUTH_KEY
+    )
 
 
 def _flatten_content(content: Any) -> str:
@@ -1691,10 +3737,16 @@ _SECRET = re.compile(
 
 def _mask_secrets(text: str) -> str:
     """Длинные токеноподобные последовательности -> ***; id моделей каталога и алиасов не маскируются."""
+
     def keep_model_ids(match: re.Match[str]) -> str:
         token = match.group(0)
         return token if token in ALLOWED_MODELS or token in MODEL_ALIASES else "***"
 
+    text = re.sub(r"(?i)\b(Bearer\s+)[^\s,;\"']+", r"\1***", text)
+    text = re.sub(r"(?i)(OPENCODE_SERVER_PASSWORD\s*[=:]\s*)[^\s,;]+", r"\1***", text)
+    text = re.sub(
+        r"(?i)(\b(?:https?|socks[45]h?)://)[^/\s:@]+:[^/\s@]+@", r"\1***@", text
+    )
     return _SECRET.sub(keep_model_ids, text)
 
 
@@ -2154,7 +4206,9 @@ def _find_close_in(text: str, start: int, close_tag: str = TOOL_CALL_CLOSE) -> i
 
 
 _STRIP_SCAN_MAX_TAGS = 16  # граница CPU: `_code_context` — O(len) на кандидата
-_BROKEN_BLOCK_NOTICE = "[opencode-zen-bridge: невалидный блок вызова инструмента отброшен]"
+_BROKEN_BLOCK_NOTICE = (
+    "[opencode-zen-bridge: невалидный блок вызова инструмента отброшен]"
+)
 
 
 def _strip_broken_tool_blocks(text: str, *, quiet: bool = False) -> tuple[str, int]:
@@ -2224,7 +4278,9 @@ class ToolCallParser:
         self._history = ""  # весь текст, ушедший в content
         self.tool_calls_count = 0
         self.trailing_chars_after_tool = 0
-        self._tail_after_tool = ""  # весь текст после последнего вызова (для инварианта к чанкам)
+        self._tail_after_tool = (
+            ""  # весь текст после последнего вызова (для инварианта к чанкам)
+        )
 
     def feed(self, text: str) -> None:
         self._buf += text
@@ -2235,19 +4291,22 @@ class ToolCallParser:
 
     def has_open_tool_call(self) -> bool:
         """Тег открыт и ждёт закрытия (или его начало может прийти следующей дельтой)."""
-        return any(open_tag in self._buf for open_tag, _ in TOOL_CALL_TAGS) or self._pending_prefix() > 0
+        return (
+            any(open_tag in self._buf for open_tag, _ in TOOL_CALL_TAGS)
+            or self._pending_prefix() > 0
+        )
 
     def _classify_open(self, after: int, final: bool) -> str:
         """`<tool_call>` в буфере: "real" | "quoted" (inline-код markdown) | "wait" (нужен следующий символ)."""
-        context = _code_context(
-            self._history + self._buf, len(self._history), final
-        )
+        context = _code_context(self._history + self._buf, len(self._history), final)
         if context != "text":
             return "quoted" if context == "code" else "wait"
-        tail = self._buf[after:after + 3]
+        tail = self._buf[after : after + 3]
         if not tail:
             return "real" if final else "wait"
-        if tail[0] != "`" or tail == "```":  # ```json-обёртка внутри блока — настоящий вызов
+        if (
+            tail[0] != "`" or tail == "```"
+        ):  # ```json-обёртка внутри блока — настоящий вызов
             return "real"
         if not final and tail == "`" * len(tail) and len(tail) < 3:
             return "wait"
@@ -2285,11 +4344,13 @@ class ToolCallParser:
                     self._flush_all()  # незакрытый/невалидный блок отдаём текстом
                 return
             inner = self._buf[after:end]
-            self._buf = self._buf[end + len(close_tag):]
+            self._buf = self._buf[end + len(close_tag) :]
             calls = _parse_tool_call_blocks(inner)
             if calls is None:
-                _log(f"tool_call_unparsed bytes={len(inner.encode('utf-8'))} "
-                     f"head={_mask_secrets(inner[:120])!r}")
+                _log(
+                    f"tool_call_unparsed bytes={len(inner.encode('utf-8'))} "
+                    f"head={_mask_secrets(inner[:120])!r}"
+                )
                 self._emit(open_tag + inner + close_tag)
             else:
                 self._history += _OPAQUE_BLOCK
@@ -2308,15 +4369,22 @@ class ToolCallParser:
                 best = (pos, open_tag, close_tag)
         return best
 
-    def _find_close_outside_string(self, start: int, close_tag: str = TOOL_CALL_CLOSE) -> int:
+    def _find_close_outside_string(
+        self, start: int, close_tag: str = TOOL_CALL_CLOSE
+    ) -> int:
         """Позиция закрывающего тега вне строковых литералов JSON буфера, или -1 (см. `_find_close_in`)."""
         return _find_close_in(self._buf, start, close_tag)
 
     def _pending_prefix(self) -> int:
         """Длина хвоста — префикса открывающего тега (его нельзя отдать в content)."""
-        limit = min(max(len(open_tag) for open_tag, _ in TOOL_CALL_TAGS) - 1, len(self._buf))
+        limit = min(
+            max(len(open_tag) for open_tag, _ in TOOL_CALL_TAGS) - 1, len(self._buf)
+        )
         for length in range(limit, 0, -1):
-            if any(self._buf[-length:] == open_tag[:length] for open_tag, _ in TOOL_CALL_TAGS):
+            if any(
+                self._buf[-length:] == open_tag[:length]
+                for open_tag, _ in TOOL_CALL_TAGS
+            ):
                 return length
         return 0
 
@@ -2492,7 +4560,9 @@ def _resolve_opencode_go_auth() -> tuple[str, str]:
     org_id = os.environ.get("OPENCODE_ORG_ID", "org_01M4ZR9TJ6XN1X4MS79ADKQJ60").strip()
     db_path = Path.home() / ".local/share/opencode/opencode.db"
     try:
-        conn = sqlite3.connect(f"file:{quote(str(db_path))}?mode=ro", uri=True, timeout=5)
+        conn = sqlite3.connect(
+            f"file:{quote(str(db_path))}?mode=ro", uri=True, timeout=5
+        )
         try:
             try:
                 row = conn.execute(
@@ -2594,10 +4664,14 @@ _CDATA_END_MIN = 6
 
 
 _TABLE_SEP_RE = re.compile(
-    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$", re.MULTILINE)
+    r"^[ \t]*\|?[ \t]*:?-{3,}:?[ \t]*(?:\|[ \t]*:?-{3,}:?[ \t]*)+\|?[ \t]*$",
+    re.MULTILINE,
+)
 
 
-def _in_active_markdown_table(text: str, loop_start: int, sep_ends: list[int] | None = None) -> bool:
+def _in_active_markdown_table(
+    text: str, loop_start: int, sep_ends: list[int] | None = None
+) -> bool:
     """Перед loop_start идёт строка-разделитель таблицы, а после неё нет пустой строки и все строки с «|».
 
     sep_ends — заранее посчитанные концы разделителей всего text (для многократных проверок без O(n) на вызов).
@@ -2612,10 +4686,12 @@ def _in_active_markdown_table(text: str, loop_start: int, sep_ends: list[int] |
     between = text[last_end:loop_start]
     for eol in ("\r\n", "\n"):  # перевод строки, завершающий сам разделитель
         if between.startswith(eol):
-            between = between[len(eol):]
+            between = between[len(eol) :]
             break
     lines = between.splitlines()
-    if lines and not between.endswith(("\n", "\r")):  # хвост до loop_start оборван посреди строки таблицы
+    if lines and not between.endswith(
+        ("\n", "\r")
+    ):  # хвост до loop_start оборван посреди строки таблицы
         lines.pop()
     # Пустая строка (в т.ч. из пробелов/табов, CRLF) завершает таблицу.
     return all(ln.strip() and "|" in ln and "||" not in ln for ln in lines)
@@ -2633,7 +4709,9 @@ def _is_table_block(unit: str, text: str = "", loop_start: int = 0) -> bool:
     if _in_active_markdown_table(text, loop_start):
         return True
     return all(
-        s.startswith("|") or s.endswith("|") or s.count("|") >= 2
+        s.startswith("|")
+        or s.endswith("|")
+        or s.count("|") >= 2
         or (" | " in s and not s.endswith((".", "!", "?", ";")))
         for s in lines
     )
@@ -2654,7 +4732,9 @@ def _cdata_loop_start(text: str) -> int | None:
     seps = [m.end() for m in _TABLE_SEP_RE.finditer(text)]
 
     def is_terminator(pos: int) -> bool:
-        return "<![CDATA[" not in text[max(0, pos - 300):pos] and not _in_active_markdown_table(text, pos, seps)
+        return "<![CDATA[" not in text[
+            max(0, pos - 300) : pos
+        ] and not _in_active_markdown_table(text, pos, seps)
 
     recent = []
     pos = text.find("]]>", recent_start)
@@ -2665,7 +4745,9 @@ def _cdata_loop_start(text: str) -> int | None:
     if len(recent) < _CDATA_END_MIN:
         return None
     start = recent[0]
-    while (prev := text.rfind("]]>", max(0, start - _CDATA_GAP_MAX), start)) >= 0 and is_terminator(prev):
+    while (
+        prev := text.rfind("]]>", max(0, start - _CDATA_GAP_MAX), start)
+    ) >= 0 and is_terminator(prev):
         start = prev
     return start
 
@@ -2674,7 +4756,10 @@ def _detect_repetition_loop(text: str) -> int | None:
     """Индекс начала зацикленного хвоста (кусок 4..80 символов >= 6 раз подряд, >= 120 символов) или None."""
     tail = text[-_LOOP_TAIL_CHARS:]
     base = len(text) - len(tail)
-    if "<![CDATA[" not in tail[-300:] and (cdata_idx := _cdata_loop_start(text)) is not None:
+    if (
+        "<![CDATA[" not in tail[-300:]
+        and (cdata_idx := _cdata_loop_start(text)) is not None
+    ):
         return cdata_idx
     size_total = len(tail)
     for size in range(4, 81):
@@ -2685,15 +4770,19 @@ def _detect_repetition_loop(text: str) -> int | None:
             continue
         pos = size_total - size
         reps = 1
-        while pos - size >= 0 and tail[pos - size:pos] == unit:
+        while pos - size >= 0 and tail[pos - size : pos] == unit:
             reps += 1
             pos -= size
         if reps < _LOOP_MIN_REPEATS or size * reps < _LOOP_MIN_BLOCK_CHARS:
             continue
-        full_pos = base + pos  # цикл мог начаться раньше хвоста — отматываем по всему тексту
-        while full_pos - size >= 0 and text[full_pos - size:full_pos] == unit:
+        full_pos = (
+            base + pos
+        )  # цикл мог начаться раньше хвоста — отматываем по всему тексту
+        while full_pos - size >= 0 and text[full_pos - size : full_pos] == unit:
             full_pos -= size
-        if _is_table_block(unit, text, full_pos):  # строки markdown-таблицы повторяются законно
+        if _is_table_block(
+            unit, text, full_pos
+        ):  # строки markdown-таблицы повторяются законно
             continue
         return full_pos
     return None
@@ -2702,7 +4791,9 @@ def _detect_repetition_loop(text: str) -> int | None:
 _THOUGHT_CLOSED_RE = re.compile(r"<unused94>thought\b.*?<unused95>\s*", re.DOTALL)
 _THOUGHT_OPEN_RE = re.compile(r"<unused94>thought\b.*$", re.DOTALL)
 _CDATA_LOOP_RE = re.compile(
-    r"(?:(?:Sub-thought finished\.|end\.|stop\.)?\s*\]\]>\s*(?:Let's [^\n\]]*)?\s*){2,}.*$", re.DOTALL)
+    r"(?:(?:Sub-thought finished\.|end\.|stop\.)?\s*\]\]>\s*(?:Let's [^\n\]]*)?\s*){2,}.*$",
+    re.DOTALL,
+)
 
 
 def _strip_unclosed_tool_calls(text: str) -> str:
@@ -2710,10 +4801,16 @@ def _strip_unclosed_tool_calls(text: str) -> str:
 
     Пачка блоков без промежуточных закрытий, закрытая в конце, не затрагивается.
     """
-    close_end = max((text.rfind(close_tag) + len(close_tag) for _, close_tag in TOOL_CALL_TAGS
-                     if close_tag in text), default=0)
+    close_end = max(
+        (
+            text.rfind(close_tag) + len(close_tag)
+            for _, close_tag in TOOL_CALL_TAGS
+            if close_tag in text
+        ),
+        default=0,
+    )
     match = _RAW_CALL_RE.search(text, close_end)
-    return text[:match.start()].rstrip() if match else text
+    return text[: match.start()].rstrip() if match else text
 
 
 def _sanitize_assistant_text(text: str) -> str:
@@ -2737,26 +4834,46 @@ def _sanitize_assistant_text(text: str) -> str:
 GoogleInput = tuple[list[dict[str, Any]], str]  # (contents, systemInstruction) из _messages_to_google_contents
 
 
-def _google_request(model: str, prompt: str, effort: str, stream: bool,
-                    google_input: GoogleInput | None = None):
+def _google_request(
+    model: str,
+    prompt: str,
+    effort: str,
+    stream: bool,
+    google_input: GoogleInput | None = None,
+):
     """Открыть HTTP напрямую: прокси из окружения здесь не используются."""
     meta = ALLOWED_MODELS[model]
     base = urlsplit(meta["base_url"].rstrip("/"))
     token, org_id = _resolve_opencode_go_auth()
     headers = {
-        "Content-Type": "application/json", "User-Agent": "curl/8.7.1",
-        "x-goog-api-key": token, "Authorization": f"Bearer {token}",
+        "Content-Type": "application/json",
+        "User-Agent": "curl/8.7.1",
+        "x-goog-api-key": token,
+        "Authorization": f"Bearer {token}",
         "x-opencode-session": "dsh",
     }
     if org_id:
         headers["x-opencode-org-id"] = org_id
-    contents, system_instruction = google_input if google_input is not None else (None, "")
-    body = json.dumps(_build_google_payload(prompt, effort, int(meta.get("max_output") or 65536),
-                                            contents, system_instruction),
-                      ensure_ascii=False).encode("utf-8")
+    contents, system_instruction = (
+        google_input if google_input is not None else (None, "")
+    )
+    body = json.dumps(
+        _build_google_payload(
+            prompt,
+            effort,
+            int(meta.get("max_output") or 65536),
+            contents,
+            system_instruction,
+        ),
+        ensure_ascii=False,
+    ).encode("utf-8")
     action = "streamGenerateContent?alt=sse" if stream else "generateContent"
     path = f"{base.path}/models/{quote(model, safe='')}:{action}"
-    cls = http.client.HTTPSConnection if base.scheme == "https" else http.client.HTTPConnection
+    cls = (
+        http.client.HTTPSConnection
+        if base.scheme == "https"
+        else http.client.HTTPConnection
+    )
     conn = cls(base.hostname or "127.0.0.1", base.port, timeout=TIMEOUT_S)
     try:
         conn.request("POST", path, body=body, headers=headers)
@@ -2844,6 +4961,7 @@ class Run:
         self.attempts = attempts
         self.proc: subprocess.Popen[str] | None = None
         self.feed: _StdoutFeed | None = None
+        self.is_client_gone: Callable[[], bool] | None = None
 
     def close(self) -> None:
         proc = self.proc
@@ -2922,6 +5040,7 @@ class Run:
         try:
             self.proc = _spawn_with_stdin(cmd, self.prompt, self.workdir, env)
         except OSError as exc:
+            self.res.spawn_limiter.refund()
             gate.release()
             return {"rc": -1, "text": "", "reasoning": "", "usage": {}, "err": f"spawn failed: {exc}",
                     "state": "spawn_failed", "finish": "error"}
@@ -2956,9 +5075,19 @@ class Run:
         err_thread = threading.Thread(target=drain_stderr, daemon=True)
         err_thread.start()
 
+        def on_idle() -> None:
+            """Прервать молчащий JSON-прогон при закрытии клиентского сокета."""
+            nonlocal state
+            if self.is_client_gone is not None and self.is_client_gone():
+                state = "client_gone"
+                if self.proc is not None:
+                    _stop_proc(self.proc)
+
         try:
             self.feed = _StdoutFeed(self.proc)
-            for raw in self.feed.lines(deadline):
+            for raw in self.feed.lines(
+                deadline, idle_s=_STDOUT_POLL_S, on_idle=on_idle
+            ):
                 gate.release()
                 raw = raw.strip()
                 if not raw:
@@ -3070,6 +5199,28 @@ class Run:
                 "state": state, "finish": "stop" if text else "error"}
 
 
+class _LockedWfile:
+    """wfile потокового запроса под общим замком: статус-таймер и основной поток не мешают друг другу."""
+
+    def __init__(self, inner: io.BufferedIOBase, lock: threading.Lock) -> None:
+        self._inner: io.BufferedIOBase = inner
+        self._lock: threading.Lock = lock
+
+    def write(self, data: bytes) -> int:
+        """Записать чанк целиком под замком."""
+        with self._lock:
+            return int(self._inner.write(data) or 0)
+
+    def flush(self) -> None:
+        """Сбросить буфер под замком."""
+        with self._lock:
+            self._inner.flush()
+
+    def __getattr__(self, name: str) -> object:
+        """Прочие атрибуты (closed, close, fileno) — у исходного wfile."""
+        return cast(object, getattr(self._inner, name))
+
+
 class Handler(BaseHTTPRequestHandler):
     protocol_version = "HTTP/1.1"
     timeout = 300
@@ -3081,6 +5232,8 @@ class Handler(BaseHTTPRequestHandler):
         _log(f"http accept error from {client_address}")
 
     _xs: dict[str, Any] | None = None
+    _serve_stream_usage: dict[str, int] | None = None
+    _first_visible: threading.Event | None = None
 
     def _exit(self) -> dict[str, Any]:
         """Состояние выхода текущего запроса для структурной строки O-EXIT/v1."""
@@ -3090,14 +5243,20 @@ class Handler(BaseHTTPRequestHandler):
 
     def _res(self) -> _Resilience:
         """Защиты сервера (слоты, breaker, budget, лимитер); у `Server` — свои, иначе модульные."""
-        return cast("_Resilience", getattr(getattr(self, "server", None), "resilience", None) or _DEFAULT_RESILIENCE)
+        return cast(
+            "_Resilience",
+            getattr(getattr(self, "server", None), "resilience", None)
+            or _DEFAULT_RESILIENCE,
+        )
 
     def _acquire_slot(self, res: _Resilience) -> bool:
         """Слот с ограниченным ожиданием; отказ -> 503 overloaded (таймаут 15 с или 13-й ждущий мгновенно)."""
         verdict = res.slots.acquire_ex()
         if verdict == "ok":
             return True
-        self._exit()["exit_reason"] = "slot_timeout" if verdict == "timeout" else "slot_overflow"
+        self._exit()["exit_reason"] = (
+            "slot_timeout" if verdict == "timeout" else "slot_overflow"
+        )
         self._send(503, {"error": {"message": "bridge busy", "type": "overloaded"}})
         return False
 
@@ -3120,10 +5279,420 @@ class Handler(BaseHTTPRequestHandler):
         (openai-node/ai-sdk) бросают исключение на чанке с полем error. finish_reason
         не отправляем: пустого успешного завершения быть не должно.
         """
-        self.wfile.write(("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8"))
-        self.wfile.write(b"data: [DONE]\n\n")
+        _ = self.wfile.write(
+            ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode(
+                "utf-8"
+            )
+        )
+        _ = self.wfile.write(b"data: [DONE]\n\n")
         self.wfile.flush()
 
+    def _client_gone_check(self) -> bool:
+        """Клиент закрыл сокет: FIN/RST виден peek без чтения данных."""
+        try:
+            dup_fd = os.dup(self.rfile.fileno())
+        except AttributeError:
+            return False
+        except (OSError, ValueError):
+            return True
+        try:
+            conn_obj = socket.socket(fileno=dup_fd)
+            try:
+                ready, _w, _x = select.select([conn_obj], [], [], 0)
+                if not ready:
+                    return False
+                data = conn_obj.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
+                return data == b""
+            finally:
+                os.close(conn_obj.detach())
+        except OSError as exc:
+            # EAGAIN/EWOULDBLOCK — данных нет; ECONNRESET/EPIPE/EBADF — клиент сброшен.
+            return exc.errno not in (errno.EAGAIN, errno.EWOULDBLOCK)
+        except ValueError:
+            return True
+
+    def _run_serve_stream_attempts(
+        self,
+        model: str,
+        prompt: str,
+        effort: str,
+        emulate_tools: bool,
+        tools: list[dict[str, object]] | None,
+        resp_id: str,
+        created: int,
+        shown_model: str,
+        emit_content: Callable[[str], None],
+        emit_parsed_content: Callable[[str], None],
+        emit_tool_call: Callable[[dict[str, object]], None],
+        attempts: _RequestAttempts,
+        res: _Resilience,
+        xs: dict[str, object],
+        collected_texts: list[str],
+        tool_choice: object = None,
+    ) -> bool:
+        """Serve-попытки для SSE; True — запрос завершён, False — fallback на run."""
+        thinking = effort.strip().lower() not in ("", "off", "none")
+        workdir = DEFAULTWORKDIR
+        workdir.mkdir(parents=True, exist_ok=True)
+        last_reasoning: list[str] = [""]
+        # Барьер доставки монотонен на весь запрос: модельный чанк, ушедший клиенту, не снимается.
+        delivered_any = [False]
+        first_visible = self._first_visible or threading.Event()
+
+        def on_status(text: str) -> None:
+            """Синтетический статус с ведущим LF после незавершённой строки модели."""
+            prefix = (
+                "\n"
+                if last_reasoning[0] and not last_reasoning[0].endswith("\n")
+                else ""
+            )
+            chunk = format_sse_chunk(
+                resp_id, created, shown_model, {"reasoning_content": prefix + text}
+            )
+            first_visible.set()
+            _ = self.wfile.write(chunk.encode("utf-8"))
+            self.wfile.flush()
+
+        def attempt_status(text: str) -> None:
+            """Статусы попытки; STATUS_INITIAL отдаёт только защитный таймер запроса."""
+            if text == STATUS_INITIAL and self._first_visible is not None:
+                return
+            on_status(text)
+
+        def on_reasoning(text: str) -> None:
+            """Модельное размышление клиенту без модификации байтов."""
+            cleaned = _strip_interrupted(text)
+            if not cleaned:
+                return
+            last_reasoning[0] = cleaned
+            delivered_any[0] = True
+            first_visible.set()
+            chunk = format_sse_chunk(
+                resp_id, created, shown_model, {"reasoning_content": cleaned}
+            )
+            _ = self.wfile.write(chunk.encode("utf-8"))
+            self.wfile.flush()
+
+        parser_box: list[ToolCallParser | None] = [None]
+        _inter_buf_text: list[str] = [""]  # буфер потокового фильтра split-маркеров
+
+        def on_text(text: str) -> None:
+            """Модельный текст через ToolCallParser при эмуляции (с потоковым фильтром маркеров)."""
+            _inter_buf_text[0] += text
+            buf = _inter_buf_text[0]
+            # Удерживаем только возможный префикс маркера либо его незавершённую строку.
+            cut = len(buf)
+            folded = buf.lower()
+            for marker in (
+                "i was interrupted right before making tool calls",
+                "the previous response was interrupted. continue from where you left off without repeating completed content",
+            ):
+                pos = folded.find(marker)
+                if pos >= 0 and "\n" not in buf[pos:]:
+                    cut = min(cut, pos)
+                for size in range(1, min(len(marker), len(buf)) + 1):
+                    if folded.endswith(marker[:size]):
+                        cut = min(cut, len(buf) - size)
+            cleaned = _strip_interrupted(buf[:cut])
+            _inter_buf_text[0] = buf[cut:]
+            if not cleaned:
+                return
+            if parser_box[0] is not None:
+                parser_box[0].feed(cleaned)
+            else:
+                emit_content(cleaned)
+
+        def _flush_inter_buf() -> None:
+            """Сброс остатка буфера после завершения попытки."""
+            if not _inter_buf_text[0]:
+                return
+            cleaned = _strip_interrupted(_inter_buf_text[0])
+            _inter_buf_text[0] = ""
+            if not cleaned:
+                return
+            if parser_box[0] is not None:
+                parser_box[0].feed(cleaned)
+            else:
+                emit_content(cleaned)
+
+        unmapped_in_attempt: list[str] = []
+        emitted_tools_in_attempt = [0]
+
+        def on_tool(payload: dict[str, object]) -> None:
+            """Native serve-вызов в DSH tool_call."""
+            part = _as_dict(payload.get("part"))
+            mapped = _native_call_as_dsh(payload, tools) if emulate_tools else []
+            if not mapped and emulate_tools and part.get("tool"):
+                unmapped_in_attempt.append(str(part.get("tool")))
+            for call in mapped:
+                emitted_tools_in_attempt[0] += 1
+                delivered_any[0] = True
+                emit_tool_call(call)
+
+        def on_parsed_tool(call: dict[str, object]) -> None:
+            """Вызов из текста модели: учесть в счётчике эмиссии попытки."""
+            emitted_tools_in_attempt[0] += 1
+            delivered_any[0] = True
+            emit_tool_call(call)
+
+        force_serve = (
+            os.environ.get("OPENCODE_ZEN_BRIDGE_TRANSPORT", "").strip().lower()
+            == "serve"
+        )
+        current_prompt = prompt
+        serve_attempts = 0
+        unmapped_retries = 0
+        incomplete_retries = 0
+        while True:
+            unmapped_in_attempt.clear()
+            emitted_tools_in_attempt[0] = 0
+            _inter_buf_text[0] = ""  # сброс буфера split-маркеров на каждую попытку
+            if parser_box[0] is not None:
+                parser_box[0].finish()
+            parser_box[0] = (
+                ToolCallParser(emit_parsed_content, on_parsed_tool)
+                if emulate_tools
+                else None
+            )
+            if attempts.total_spawns >= MAX_TOTAL_SPAWNS or not attempts.can_spawn():
+                xs["exit_reason"] = "upstream_failed"
+                self._sse_error(_error_payload("serve spawn limit reached"))
+                return True
+            _orig_reasoning, _orig_text = on_reasoning, on_text
+
+            _prior_text = "".join(collected_texts)
+            _dedup_text = (
+                _PrefixDedup(_prior_text) if serve_attempts and _prior_text else None
+            )
+
+            def _text_seen(text: str, _f: Callable[[str], None] = _orig_text) -> None:
+                if _dedup_text is not None:
+                    text = _dedup_text.push(text)
+                    if not text:
+                        return
+                delivered_any[0] = True
+                _f(text)
+
+            gate = _StartupGate()
+            gate.acquire()
+            _limiter_ok = res.spawn_limiter.acquire(
+                max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())
+            )
+            if not _limiter_ok:
+                gate.release()
+                if not force_serve and not delivered_any[0]:
+                    return False
+                xs["exit_reason"] = "upstream_failed"
+                self._sse_error(_error_payload("serve spawn limiter timeout"))
+                return True
+            attempts.note_spawn()
+            if serve_attempts and first_visible.is_set() and thinking:
+                # Единая точка разделителя: ровно один на каждый повтор, только в thinking-режиме.
+                on_status(
+                    f"[мост] Повтор попытки {attempts.total_spawns}/{attempts.max_total}…\n"
+                )
+            serve_attempts += 1
+            try:
+                result = _serve_one_attempt(
+                    model,
+                    current_prompt,
+                    effort,
+                    workdir,
+                    _orig_reasoning,
+                    _text_seen,
+                    on_tool,
+                    attempts.deadline - TIMEOUT_S,
+                    is_client_gone=self._client_gone_check,
+                    on_status=attempt_status,
+                    thinking_enabled=thinking,
+                    deadline=attempts.deadline,
+                    on_startup_ready=gate.release,
+                    emulate_tools=emulate_tools,
+                )
+            except ServeUnavailable as exc:
+                res.serve_health.record_failure()
+                if not force_serve and not delivered_any[0]:
+                    xs["transport"] = "run"
+                    xs["transport_history"] = ["serve", "run"]
+                    return False
+                xs["exit_reason"] = "upstream_failed"
+                self._sse_error(_error_payload(f"serve unavailable: {exc}"))
+                return True
+            except ServeSecurityError as exc:
+                xs["exit_reason"] = "provider_fatal"
+                self._sse_error(_error_payload(f"serve security failure: {exc}"))
+                return True
+            finally:
+                gate.release()
+            _flush_inter_buf()
+            usage_acc = self._serve_stream_usage or {}
+            for key in ("input", "output", "cached", "reasoning"):
+                usage_acc[key] = int(usage_acc.get(key) or 0) + int(
+                    result["usage"].get(key) or 0
+                )
+            self._serve_stream_usage = usage_acc
+            usage_cur = result["usage"]
+            if "first_event_ms" not in xs or xs.get("first_event_ms") is None:
+                xs["first_event_ms"] = result["first_event_ms"]
+            if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
+                xs["ttft_ms"] = result["ttft_ms"]
+            if parser_box[0] is not None:
+                parser_box[0].finish()
+            if result.get("exit_reason") == "client_gone":
+                xs["exit_reason"] = "client_gone"
+                return True
+            if "first_event_ms" not in xs or xs.get("first_event_ms") is None:
+                xs["first_event_ms"] = result["first_event_ms"]
+            if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
+                xs["ttft_ms"] = result["ttft_ms"]
+            _delivered_now = bool(
+                delivered_any[0]
+                or result.get("delivered")
+                or result["texts"]
+                or result["reasonings"]
+                or result["native_calls"]
+            )
+            delivered_any[0] = _delivered_now
+            if result.get("exit_reason") in (
+                "first_event_timeout",
+                "first_token_timeout",
+                "stall_timeout",
+                "invalid_serve_event",
+                "timeout",
+            ):
+                reason = str(result["exit_reason"])
+                if reason in ("first_event_timeout", "invalid_serve_event"):
+                    res.serve_health.record_failure()
+                else:
+                    attempts.attempt_done(True, False)
+                if not _delivered_now and not force_serve:
+                    xs["transport"] = "run"
+                    xs["transport_history"] = ["serve", "run"]
+                    return False
+                if attempts.allow_retry(reason):
+                    continue
+                xs["exit_reason"] = reason
+                self._sse_error(_error_payload(f"serve {reason}"))
+                return True
+            if result.get("prompt_status") is not None:
+                _ps_code = int(result["prompt_status"] or 0)
+                if _ps_code == 429 or 500 <= _ps_code <= 599:
+                    attempts.attempt_done(True, False)
+                if not _delivered_now and not force_serve:
+                    xs["transport"] = "run"
+                    xs["transport_history"] = ["serve", "run"]
+                    return False
+                if attempts.allow_retry(f"prompt_status_{_ps_code}"):
+                    continue
+                xs["exit_reason"] = f"prompt_status_{_ps_code}"
+                self._sse_error(_error_payload(f"serve prompt HTTP {_ps_code}"))
+                return True
+            if result.get("exit_reason") in ("prompt_status_429",):
+                attempts.attempt_done(True, False)
+                if attempts.allow_retry("prompt_status_429"):
+                    continue
+                xs["exit_reason"] = "prompt_status_429"
+                self._sse_error(_error_payload("serve prompt HTTP 429"))
+                return True
+            if result["error"] is not None:
+                err = result["error"]
+                if result.get("transient_error"):
+                    attempts.attempt_done(True, False)
+                    _delivered_err = _delivered_now or bool(collected_texts)
+                    if not _delivered_err and not force_serve:
+                        xs["transport"] = "run"
+                        xs["transport_history"] = ["serve", "run"]
+                        return False
+                    if not _delivered_err and attempts.allow_retry(
+                        "serve_transient_error"
+                    ):
+                        continue
+                    # После частичной доставки: step-interruption recovery ниже по incomplete-сигналу.
+                    signal_t = _incomplete_step_signal(
+                        "".join(result["texts"]),
+                        "".join(result["reasonings"]),
+                        tools or [],
+                        True,
+                        int(result["usage"].get("output") or 0),
+                        int(result["usage"].get("reasoning") or 0),
+                        tool_choice=tool_choice,
+                    )
+                    if signal_t and attempts.allow_retry("incomplete_step"):
+                        attempts.signal = signal_t
+                        current_prompt = _rewrite_tool_tags_for_model(
+                            _incomplete_tool_step_prompt(
+                                prompt,
+                                "".join(collected_texts),
+                                tools or [],
+                                tool_choice,
+                                model,
+                            ),
+                            model,
+                        )
+                        continue
+                xs["exit_reason"] = "upstream_failed"
+                self._sse_error(
+                    _error_payload(
+                        f"serve error: {_clean_err(str(err.get('message') or ''))}"
+                    )
+                )
+                return True
+            if result.get("terminal") == "cancelled":
+                xs["exit_reason"] = "cancelled"
+                self._sse_error(_error_payload("serve session cancelled"))
+                return True
+            res.serve_health.record_success()
+            attempts.attempt_done(False, True)
+            if emulate_tools and emitted_tools_in_attempt[0] == 0:
+                if unmapped_in_attempt:
+                    if unmapped_retries < NATIVE_RETRY_LIMIT and attempts.allow_retry(
+                        "unmapped"
+                    ):
+                        unmapped_retries += 1
+                        current_prompt = _rewrite_tool_tags_for_model(
+                            _unavailable_tools_prompt(
+                                current_prompt,
+                                "".join(result["texts"]),
+                                unmapped_in_attempt,
+                                tools or [],
+                                model,
+                            ),
+                            model,
+                        )
+                        continue
+                    emit_content(
+                        f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент ({', '.join(unmapped_in_attempt)}); повторы исчерпаны]"
+                    )
+                    return True
+                signal = _incomplete_step_signal(
+                    "".join(result["texts"]),
+                    "".join(result["reasonings"]),
+                    tools or [],
+                    False,
+                    int(usage_cur.get("output") or 0),
+                    int(usage_cur.get("reasoning") or 0),
+                    tool_choice=tool_choice,
+                )
+                if (
+                    signal
+                    and incomplete_retries < NATIVE_RETRY_LIMIT
+                    and attempts.allow_retry("incomplete_step")
+                ):
+                    incomplete_retries += 1
+                    attempts.signal = signal
+                    current_prompt = _rewrite_tool_tags_for_model(
+                        _incomplete_tool_step_prompt(
+                            prompt,
+                            "".join(collected_texts),
+                            tools or [],
+                            tool_choice,
+                            model,
+                        ),
+                        model,
+                    )
+                    continue
+            return True
+
     def _stream_google_sse(self, model: str, prompt: str, effort: str,
                            emulate_tools: bool = False,
                            google_input: GoogleInput | None = None) -> None:
@@ -3274,11 +5843,21 @@ class Handler(BaseHTTPRequestHandler):
             self._stream_google_sse(model, prompt, effort, emulate_tools, google_input)
             return
         xs = self._exit()
+        xs["transport"] = "run"
+        xs["transport_history"] = ["run"]
         launcher = _resolve_launcher()
         if not os.access(launcher, os.X_OK):
             xs["exit_reason"] = "launcher_missing"
-            self._send(502, {"error": {"message": f"opencode launcher not executable: {launcher}",
-                                       "type": "proxy_error", "code": 502}})
+            self._send(
+                502,
+                {
+                    "error": {
+                        "message": f"opencode launcher not executable: {launcher}",
+                        "type": "proxy_error",
+                        "code": 502,
+                    }
+                },
+            )
             return
 
         res = self._res()
@@ -3296,17 +5875,33 @@ class Handler(BaseHTTPRequestHandler):
         model_route = _model_route(model)
 
         cmd, shown = _build_cmd(launcher, model, effort)
-        _log(f"stream exec model={model_route} {shown} prompt_chars={len(prompt)} cwd={workdir}")
+        _log(
+            f"stream exec model={model_route} {shown} prompt_chars={len(prompt)} cwd={workdir}"
+        )
 
         proc: subprocess.Popen[str] | None = None
         feed: _StdoutFeed | None = None
         gate: _StartupGate | None = None
         run_id = uuid.uuid4().hex[:8]
+        # Записи в wfile сериализуются общим замком; first_visible подавляет таймер статуса.
+        wfile_lock = threading.Lock()
+        first_visible = threading.Event()
+        status_fired_at = [0.0]
+        raw_wfile = self.wfile
+        status_timer: threading.Timer | None = None
 
         try:
             if not attempts.begin_attempt():
                 xs["exit_reason"] = "circuit_open"
-                self._send(503, {"error": {"message": "upstream circuit open", "type": "overloaded"}})
+                self._send(
+                    503,
+                    {
+                        "error": {
+                            "message": "upstream circuit open",
+                            "type": "overloaded",
+                        }
+                    },
+                )
                 return
 
             # 1. Отправляются HTTP-заголовки 200 SSE
@@ -3324,6 +5919,44 @@ class Handler(BaseHTTPRequestHandler):
             )
             self.wfile.write(first_chunk.encode("utf-8"))
             self.wfile.flush()
+            self.wfile = cast(
+                io.BufferedIOBase, cast(object, _LockedWfile(raw_wfile, wfile_lock))
+            )
+            self._first_visible = first_visible
+
+            def _initial_status() -> None:
+                """Защитный таймер: первый видимый статус не позднее FIRST_STATUS_DELAY_S."""
+                with wfile_lock:
+                    if first_visible.is_set():
+                        return
+                    first_visible.set()
+                    status_fired_at[0] = time.monotonic()
+                    try:
+                        _ = raw_wfile.write(
+                            format_sse_chunk(
+                                resp_id,
+                                created,
+                                shown_model,
+                                {"reasoning_content": STATUS_INITIAL},
+                            ).encode("utf-8")
+                        )
+                        raw_wfile.flush()
+                    except (OSError, ValueError):
+                        pass
+
+            if effort.strip().lower() not in ("", "off", "none"):
+                status_timer = threading.Timer(
+                    max(
+                        0.0,
+                        attempts.deadline
+                        - TIMEOUT_S
+                        + FIRST_STATUS_DELAY_S
+                        - time.monotonic(),
+                    ),
+                    _initial_status,
+                )
+                status_timer.daemon = True
+                status_timer.start()
 
             collected_texts: list[str] = []
             usage: dict[str, Any] = {}
@@ -3335,7 +5968,10 @@ class Handler(BaseHTTPRequestHandler):
             dedup: list[_PrefixDedup | None] = [None]
 
             def send_text(text: str) -> None:
-                chunk = format_sse_chunk(resp_id, created, shown_model, {"content": text})
+                chunk = format_sse_chunk(
+                    resp_id, created, shown_model, {"content": text}
+                )
+                first_visible.set()
                 self.wfile.write(chunk.encode("utf-8"))
                 self.wfile.flush()
                 collected_texts.append(text)  # только реально отданное клиенту
@@ -3350,14 +5986,18 @@ class Handler(BaseHTTPRequestHandler):
                         return
                 send_text(text)
 
-            dropped_blocks = [0]  # вырезано нераспарсенных блоков вызова (счётчик на запрос)
+            dropped_blocks = [
+                0
+            ]  # вырезано нераспарсенных блоков вызова (счётчик на запрос)
 
             def emit_parsed_content(text: str) -> None:
                 # Нераспарсенный блок ToolCallParser отдаёт одним куском: сырой тег не уходит ни в SSE, ни в повтор.
                 cleaned, dropped = _strip_broken_tool_blocks(text)
                 if dropped:
                     dropped_blocks[0] += dropped
-                    _log(f"stream dropped {dropped} unparsed tool block(s) from content")
+                    _log(
+                        f"stream dropped {dropped} unparsed tool block(s) from content"
+                    )
                 emit_content(cleaned)
 
             seen_calls: set[str] = set()
@@ -3372,17 +6012,80 @@ class Handler(BaseHTTPRequestHandler):
                     "index": len(tool_calls),
                     "id": "call_" + uuid.uuid4().hex[:24],
                     "type": "function",
-                    "function": {"name": call["name"],
-                                 "arguments": json.dumps(call["arguments"], ensure_ascii=False)},
+                    "function": {
+                        "name": call["name"],
+                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
+                    },
                 }
                 tool_calls.append(tc)
-                chunk = format_sse_chunk(resp_id, created, shown_model, {"tool_calls": [tc]})
+                chunk = format_sse_chunk(
+                    resp_id, created, shown_model, {"tool_calls": [tc]}
+                )
+                first_visible.set()
                 self.wfile.write(chunk.encode("utf-8"))
                 self.wfile.flush()
 
             with _active_lock:
                 _active[run_id] = time.time()
 
+            if _select_transport(res) == "serve":
+                xs["transport"] = "serve"
+                xs["transport_history"] = ["serve"]
+                self._serve_stream_usage = None
+                handled = self._run_serve_stream_attempts(
+                    model,
+                    prompt,
+                    effort,
+                    emulate_tools,
+                    tools,
+                    resp_id,
+                    created,
+                    shown_model,
+                    emit_content,
+                    emit_parsed_content,
+                    emit_tool_call,
+                    attempts,
+                    res,
+                    xs,
+                    collected_texts,
+                    tool_choice=tool_choice
+                    if isinstance(tool_choice, (str, dict)) or tool_choice is None
+                    else None,
+                )
+                if handled:
+                    if xs.get("exit_reason"):
+                        return
+                    serve_usage = self._serve_stream_usage or {}
+                    for key in ("input", "output", "cached", "reasoning"):
+                        if serve_usage.get(key):
+                            usage[key] = int(usage.get(key) or 0) + serve_usage[key]
+                    full_text_s = "".join(collected_texts)
+                    final_s = format_sse_chunk(
+                        resp_id,
+                        created,
+                        shown_model,
+                        {},
+                        finish_reason="tool_calls" if tool_calls else "stop",
+                        usage=_build_openai_usage(
+                            int(usage.get("input") or 0) or _estimate_tokens(prompt),
+                            int(usage.get("output") or 0)
+                            or _estimate_tokens(full_text_s),
+                            int(usage.get("cached") or 0),
+                            int(usage.get("reasoning") or 0),
+                        ),
+                    )
+                    _ = self.wfile.write(final_s.encode("utf-8"))
+                    _ = self.wfile.write(b"data: [DONE]\n\n")
+                    self.wfile.flush()
+                    xs.update(
+                        exit_reason="ok",
+                        tools=len(tool_calls),
+                        out_chars=len(full_text_s),
+                        rc=0,
+                    )
+                    return
+                xs["transport"] = "run"
+
             attempt_prompt = prompt
             retries = 0  # повторов с новым промптом: встроенный инструмент / незавершённый шаг (для лога)
             unmapped_retries = 0
@@ -3391,23 +6094,38 @@ class Handler(BaseHTTPRequestHandler):
             incomplete_retry = False
             failure: dict[str, Any] | None = None
             while True:
+                if attempts.total_spawns >= MAX_TOTAL_SPAWNS:
+                    failure = {"rc": -1, "tail": "", "timeout": False}
+                    break
                 # 3. Запускается proc (повтор — встроенный инструмент без DSH-двойника,
                 #    незавершённый шаг или транзиторный отказ CLI без вывода) под потолком MAX_TOTAL_SPAWNS
                 if attempts.total_spawns:
-                    _log(f"stream exec retry={retries} fail_retries={fail_retries} model={model_route} "
-                         f"prompt_chars={len(attempt_prompt)} total_spawns={attempts.total_spawns}/{attempts.max_total}")
+                    _log(
+                        f"stream exec retry={retries} fail_retries={fail_retries} model={model_route} "
+                        f"prompt_chars={len(attempt_prompt)} total_spawns={attempts.total_spawns}/{attempts.max_total}"
+                    )
                 gate = _StartupGate()
                 gate.acquire()
-                if not res.spawn_limiter.acquire(max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())):
+                if not res.spawn_limiter.acquire(
+                    max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())
+                ):
                     gate.release()
-                    _log("stream spawn skipped: spawn rate limiter wait exceeds the request deadline")
+                    _log(
+                        "stream spawn skipped: spawn rate limiter wait exceeds the request deadline"
+                    )
                     if not collected_texts and not tool_calls:
                         failure = {"rc": -1, "tail": "", "timeout": True}
                     break
+                if status_timer is not None:
+                    # Таймер отменяем после получения слота: статус успел уйти в очереди, дальше — send_keepalive.
+                    status_timer.cancel()
                 try:
                     # env на каждую попытку: ретрай получает следующий порт пула (чистый IP)
-                    proc = _spawn_with_stdin(cmd, attempt_prompt, workdir, _run_env(model))
+                    proc = _spawn_with_stdin(
+                        cmd, attempt_prompt, workdir, _run_env(model)
+                    )
                 except OSError as exc:
+                    res.spawn_limiter.refund()
                     gate.release()
                     _log(f"stream spawn failed: {exc}")
                     xs["exit_reason"] = "spawn_failed"
@@ -3417,37 +6135,138 @@ class Handler(BaseHTTPRequestHandler):
 
                 err_lines: list[str] = []
 
-                err_thread = threading.Thread(target=_drain_stderr, args=(proc, err_lines), daemon=True)
+                err_thread = threading.Thread(
+                    target=_drain_stderr, args=(proc, err_lines), daemon=True
+                )
                 err_thread.start()
 
-                parser = ToolCallParser(emit_parsed_content, emit_tool_call) if emulate_tools else None
+                parser = (
+                    ToolCallParser(emit_parsed_content, emit_tool_call)
+                    if emulate_tools
+                    else None
+                )
                 attempt_texts: list[str] = []
                 attempt_reasonings: list[str] = []
                 unmapped: list[str] = []
                 attempt_output = False  # любой полезный вывод этого прогона (текст/мышление/инструмент)
-                attempt_output_tokens = 0  # output из step_finish этого прогона (для проглоченных вызовов)
-                attempt_reasoning_tokens = 0  # reasoning из step_finish (output включает reasoning)
+                attempt_output_tokens = (
+                    0  # output из step_finish этого прогона (для проглоченных вызовов)
+                )
+                attempt_reasoning_tokens = (
+                    0  # reasoning из step_finish (output включает reasoning)
+                )
                 provider_status: int | None = None
-                had_provider_error = False  # транзиентная ошибка посреди ответа (had_mid_stream_error)
-                fatal_mid_error = False  # детерминированная ошибка посреди ответа: без повтора
+                had_provider_error = (
+                    False  # транзиентная ошибка посреди ответа (had_mid_stream_error)
+                )
+                fatal_mid_error = (
+                    False  # детерминированная ошибка посреди ответа: без повтора
+                )
                 stopped_on_error = False
                 prior_text = "".join(collected_texts)
-                dedup[0] = _PrefixDedup(prior_text) if incomplete_retry and prior_text else None
+                dedup[0] = (
+                    _PrefixDedup(prior_text)
+                    if incomplete_retry and prior_text
+                    else None
+                )
+
+                attempt_start = time.monotonic()
+                watchdog_state: _WatchdogState = {
+                    "reason": "",
+                    "first_event_at": None,
+                    "first_token_at": None,
+                    "last_token_at": attempt_start,
+                    "status_next": attempt_start + FIRST_STATUS_DELAY_S,
+                    "last_keepalive": attempt_start,
+                    "last_reasoning": "",
+                }
+                thinking_enabled = effort.strip().lower() not in ("", "off", "none")
+
+                def emit_synthetic(text: str) -> None:
+                    """Синтетический статус отдельной reasoning-дельтой."""
+                    tail = str(watchdog_state.get("last_reasoning") or "")
+                    prefix = "\n" if tail and not tail.endswith("\n") else ""
+                    chunk_s = format_sse_chunk(
+                        resp_id,
+                        created,
+                        shown_model,
+                        {"reasoning_content": prefix + text},
+                    )
+                    first_visible.set()
+                    _ = self.wfile.write(chunk_s.encode("utf-8"))
+                    self.wfile.flush()
 
                 def send_keepalive(proc: subprocess.Popen[str] = proc) -> None:
-                    # Парсируемый chat.completion.chunk с пустой дельтой: сбрасывает клиентские
-                    # watchdog'и стрима (комментарий `: keepalive` их не сбрасывает).
+                    """Надзор: статусы, watchdog и обнаружение ухода клиента."""
+                    now_s = time.monotonic()
+                    if self._client_gone_check():
+                        _log("stream client gone, killing proc group")
+                        _stop_proc(proc)
+                        raise BrokenPipeError("client gone")
+                    if watchdog_state[
+                        "first_event_at"
+                    ] is None and now_s - attempt_start > float(FIRST_EVENT_TIMEOUT_S):
+                        watchdog_state["reason"] = "first_event_timeout"
+                        _stop_proc(proc)
+                        return
+                    if (
+                        watchdog_state["first_event_at"] is not None
+                        and watchdog_state["first_token_at"] is None
+                        and now_s - attempt_start
+                        > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)
+                    ):
+                        watchdog_state["reason"] = "first_token_timeout"
+                        _stop_proc(proc)
+                        return
+                    if watchdog_state["first_token_at"] is not None and now_s - float(
+                        watchdog_state["last_token_at"]
+                    ) > float(STALL_TIMEOUT_S):
+                        watchdog_state["reason"] = "stall_timeout"
+                        _stop_proc(proc)
+                        return
                     try:
-                        keepalive = format_sse_chunk(resp_id, created, shown_model, {"content": ""})
-                        self.wfile.write(keepalive.encode("utf-8"))
-                        self.wfile.flush()
+                        if thinking_enabled and now_s >= float(
+                            watchdog_state["status_next"]
+                        ):
+                            if watchdog_state["first_token_at"] is None:
+                                if (
+                                    status_fired_at[0]
+                                    and now_s - status_fired_at[0]
+                                    < STATUS_WAITING_INTERVAL_S
+                                ):
+                                    # Защитный таймер уже отдал STATUS_INITIAL: без дубля.
+                                    watchdog_state["status_next"] = (
+                                        status_fired_at[0] + STATUS_WAITING_INTERVAL_S
+                                    )
+                                else:
+                                    emit_synthetic(STATUS_WAITING)
+                                    watchdog_state["status_next"] = (
+                                        now_s + STATUS_WAITING_INTERVAL_S
+                                    )
+                            elif now_s - float(
+                                watchdog_state["last_token_at"]
+                            ) >= float(STALL_HEARTBEAT_INTERVAL_S):
+                                emit_synthetic(STATUS_CONTINUATION)
+                                watchdog_state["status_next"] = now_s + float(
+                                    STALL_HEARTBEAT_INTERVAL_S
+                                )
+                        if (
+                            now_s - float(watchdog_state["last_keepalive"])
+                            >= KEEPALIVE_INTERVAL_S
+                        ):
+                            watchdog_state["last_keepalive"] = now_s
+                            keepalive = format_sse_chunk(
+                                resp_id, created, shown_model, {"content": ""}
+                            )
+                            _ = self.wfile.write(keepalive.encode("utf-8"))
+                            self.wfile.flush()
                     except (BrokenPipeError, ConnectionResetError, OSError):
                         _log("stream client gone during keepalive, killing proc group")
                         _stop_proc(proc)
                         raise
 
                 feed = _StdoutFeed(proc)
-                for raw in feed.lines(deadline, KEEPALIVE_INTERVAL_S, send_keepalive):
+                for raw in feed.lines(deadline, 0.25, send_keepalive):
                     gate.release()
                     raw = raw.strip()
                     if not raw:
@@ -3459,6 +6278,36 @@ class Handler(BaseHTTPRequestHandler):
                         continue
 
                     etype, payload = parse_opencode_event(event)
+                    if etype:
+                        if watchdog_state["first_event_at"] is None:
+                            watchdog_state["first_event_at"] = time.monotonic()
+                            if (
+                                "first_event_ms" not in xs
+                                or xs.get("first_event_ms") is None
+                            ):
+                                xs["first_event_ms"] = int(
+                                    (time.monotonic() - (attempts.deadline - TIMEOUT_S))
+                                    * 1000
+                                )
+                        _token_text = str(
+                            payload.get("reasoning_content")
+                            or payload.get("content")
+                            or ""
+                        )
+                        if _token_text.strip():
+                            if watchdog_state["first_token_at"] is None:
+                                watchdog_state["first_token_at"] = time.monotonic()
+                                if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
+                                    xs["ttft_ms"] = int(
+                                        (
+                                            time.monotonic()
+                                            - (attempts.deadline - TIMEOUT_S)
+                                        )
+                                        * 1000
+                                    )
+                            watchdog_state["last_token_at"] = time.monotonic()
+                            if etype == "reasoning":
+                                watchdog_state["last_reasoning"] = _token_text
                     if etype == "reasoning":
                         rtext = payload.get("reasoning_content")
                         if isinstance(rtext, str):
@@ -3471,7 +6320,10 @@ class Handler(BaseHTTPRequestHandler):
                             attempt_output = True
                             if isinstance(rtext, str) and rtext:
                                 attempt_reasonings.append(rtext)
-                            chunk_str = format_sse_chunk(resp_id, created, shown_model, payload)
+                            chunk_str = format_sse_chunk(
+                                resp_id, created, shown_model, payload
+                            )
+                            first_visible.set()
                             self.wfile.write(chunk_str.encode("utf-8"))
                             self.wfile.flush()
                     elif etype == "text":
@@ -3480,7 +6332,12 @@ class Handler(BaseHTTPRequestHandler):
                             ttext = _strip_interrupted(ttext)
                         if isinstance(ttext, str) and ttext:
                             attempt_output = True
-                            if retries and not incomplete_retry and not attempt_texts and collected_texts:
+                            if (
+                                retries
+                                and not incomplete_retry
+                                and not attempt_texts
+                                and collected_texts
+                            ):
                                 emit_content("\n\n")
                             attempt_texts.append(ttext)
                             if parser is not None:
@@ -3490,19 +6347,29 @@ class Handler(BaseHTTPRequestHandler):
                     elif etype == "step_finish":
                         if payload:
                             for key in ("input", "output", "cached", "reasoning"):
-                                usage[key] = int(usage.get(key) or 0) + int(payload.get(key) or 0)
+                                usage[key] = int(usage.get(key) or 0) + int(
+                                    payload.get(key) or 0
+                                )
                             attempt_output_tokens += int(payload.get("output") or 0)
-                            attempt_reasoning_tokens += int(payload.get("reasoning") or 0)
+                            attempt_reasoning_tokens += int(
+                                payload.get("reasoning") or 0
+                            )
                         if emulate_tools and tool_calls:
                             # Следующие шаги — реакция на «отклонение» (повтор вызова): не нужны.
-                            _log("stream: step with tool call finished, stopping opencode run")
+                            _log(
+                                "stream: step with tool call finished, stopping opencode run"
+                            )
                             _stop_proc(proc)
                             break
                     elif etype == "error":
-                        _log(f"stream provider error: HTTP {payload.get('statusCode')}: {payload.get('message')}")
+                        _log(
+                            f"stream provider error: HTTP {payload.get('statusCode')}: {payload.get('message')}"
+                        )
                         if isinstance(payload.get("statusCode"), int):
                             provider_status = payload["statusCode"]
-                        err_lines.append(f"HTTP {payload.get('statusCode')}: {payload.get('message')}")
+                        err_lines.append(
+                            f"HTTP {payload.get('statusCode')}: {payload.get('message')}"
+                        )
                         if attempt_output:
                             # Оборванный ответ: иначе opencode сам запустит SYNTHETIC-шаг «Continue…» —
                             # останавливаем сразу. Транзиентная ошибка -> повтор шага, детерминированная
@@ -3512,8 +6379,10 @@ class Handler(BaseHTTPRequestHandler):
                                 had_provider_error = True
                             else:
                                 fatal_mid_error = True
-                            _log(f"stream: provider error mid-response (transient={had_provider_error}), "
-                                 "stopping opencode run")
+                            _log(
+                                f"stream: provider error mid-response (transient={had_provider_error}), "
+                                "stopping opencode run"
+                            )
                             stopped_on_error = True
                             _stop_proc(proc)
                             break
@@ -3522,10 +6391,17 @@ class Handler(BaseHTTPRequestHandler):
                         attempt_output = True
                         part = _dict_or_empty(event.get("part"))
                         tstate = _dict_or_empty(part.get("state"))
-                        calls = (_native_to_tool_calls(part.get("tool"), tstate.get("input"), tools or [])
-                                 if emulate_tools else [])
-                        _log(f"opencode built-in tool event: tool={part.get('tool')} status={tstate.get('status')} "
-                             f"mapped={bool(calls)} as={[c['name'] for c in calls]}")
+                        calls = (
+                            _native_to_tool_calls(
+                                part.get("tool"), tstate.get("input"), tools or []
+                            )
+                            if emulate_tools
+                            else []
+                        )
+                        _log(
+                            f"opencode built-in tool event: tool={part.get('tool')} status={tstate.get('status')} "
+                            f"mapped={bool(calls)} as={[c['name'] for c in calls]}"
+                        )
                         if calls:
                             if parser is not None:
                                 parser.finish()
@@ -3575,18 +6451,41 @@ class Handler(BaseHTTPRequestHandler):
                     rc = 1  # остановили сами после ошибки провайдера: для классификации отказа — как выход CLI
                 tail = _clean_err(err_lines[-6:])
                 transient_failure = had_provider_error or (
-                    not attempt_output and _is_retryable_failure(rc, tail, provider_status, False))
-                attempts.attempt_done(transient_failure, attempt_output and not transient_failure)
+                    not attempt_output
+                    and _is_retryable_failure(rc, tail, provider_status, False)
+                )
+                attempts.attempt_done(
+                    transient_failure, attempt_output and not transient_failure
+                )
+                if watchdog_state.get("reason"):
+                    reason_w = str(watchdog_state["reason"])
+                    if attempts.allow_retry(reason_w):
+                        emit_synthetic(
+                            f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
+                        )
+                        continue
+                    xs["exit_reason"] = reason_w
+                    failure = {"rc": rc, "tail": "", "watchdog": reason_w}
+                    break
                 if timed_out:
                     failure = {"rc": rc, "tail": "", "timeout": True}
                     break
                 if rc != 0 and not attempt_output:
                     _log(f"stream cli failed rc={rc} stderr_tail={tail!r}")
-                    if (fail_retries < FAIL_RETRY_LIMIT and time.monotonic() < deadline
-                            and _is_retryable_failure(rc, tail, provider_status, bool(tool_calls))
-                            and attempts.allow_retry("cli_failure", charge_budget=provider_status is not None)):
+                    if (
+                        fail_retries < FAIL_RETRY_LIMIT
+                        and time.monotonic() < deadline
+                        and _is_retryable_failure(
+                            rc, tail, provider_status, bool(tool_calls)
+                        )
+                        and attempts.allow_retry(
+                            "cli_failure", charge_budget=provider_status is not None
+                        )
+                    ):
                         fail_retries += 1
-                        _log(f"stream retry {fail_retries}/{FAIL_RETRY_LIMIT} after cli failure without output")
+                        _log(
+                            f"stream retry {fail_retries}/{FAIL_RETRY_LIMIT} after cli failure without output"
+                        )
                         continue
                     if not collected_texts and not tool_calls:
                         failure = {"rc": rc, "tail": tail}
@@ -3598,58 +6497,125 @@ class Handler(BaseHTTPRequestHandler):
                 if not emulate_tools or tool_calls or time.monotonic() > deadline:
                     break
                 if unmapped:
-                    if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("unmapped"):
-                        _log(f"stream unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})")
-                        emit_content(f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный "
-                                     f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]")
+                    if (
+                        unmapped_retries >= NATIVE_RETRY_LIMIT
+                        or not attempts.allow_retry("unmapped")
+                    ):
+                        _log(
+                            f"stream unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})"
+                        )
+                        emit_content(
+                            f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный "
+                            f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]"
+                        )
                         break
                     retries += 1
                     unmapped_retries += 1
                     incomplete_retry = False
-                    _log(f"stream unmapped built-in tools={unmapped}: re-prompt "
-                         f"{unmapped_retries}/{NATIVE_RETRY_LIMIT}")
-                    attempt_prompt = _rewrite_tool_tags_for_model(_unavailable_tools_prompt(
-                        attempt_prompt, "".join(attempt_texts), unmapped, tools or [], model), model)
+                    _log(
+                        f"stream unmapped built-in tools={unmapped}: re-prompt "
+                        f"{unmapped_retries}/{NATIVE_RETRY_LIMIT}"
+                    )
+                    attempt_prompt = _rewrite_tool_tags_for_model(
+                        _unavailable_tools_prompt(
+                            attempt_prompt,
+                            "".join(attempt_texts),
+                            unmapped,
+                            tools or [],
+                            model,
+                        ),
+                        model,
+                    )
                     continue
-                signal = 0 if provider_status in _FATAL_HTTP else _incomplete_step_signal(
-                    "".join(attempt_texts), "".join(attempt_reasonings), tools or [],
-                    had_provider_error, attempt_output_tokens, attempt_reasoning_tokens,
-                    tool_choice=tool_choice)
+                signal = (
+                    0
+                    if provider_status in _FATAL_HTTP
+                    else _incomplete_step_signal(
+                        "".join(attempt_texts),
+                        "".join(attempt_reasonings),
+                        tools or [],
+                        had_provider_error,
+                        attempt_output_tokens,
+                        attempt_reasoning_tokens,
+                        tool_choice=tool_choice,
+                    )
+                )
                 if not signal:
                     break
-                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("incomplete_step"):
-                    _log(f"stream incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}")
+                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
+                    "incomplete_step"
+                ):
+                    _log(
+                        f"stream incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}"
+                    )
                     break
                 retries += 1
                 incomplete_retries += 1
                 incomplete_retry = True
                 attempts.signal = signal
-                _log(f"stream incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
-                     f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}")
-                attempt_prompt = _rewrite_tool_tags_for_model(_incomplete_tool_step_prompt(
-                    prompt, "".join(collected_texts), tools or [], tool_choice, model), model)
+                _log(
+                    f"stream incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
+                    f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}"
+                )
+                attempt_prompt = _rewrite_tool_tags_for_model(
+                    _incomplete_tool_step_prompt(
+                        prompt,
+                        "".join(collected_texts),
+                        tools or [],
+                        tool_choice,
+                        model,
+                    ),
+                    model,
+                )
 
             if failure is not None:
-                _log(f"stream failed model={model} rc={failure['rc']} fail_retries={fail_retries} "
-                     f"total_spawns={attempts.total_spawns}")
+                _log(
+                    f"stream failed model={model} rc={failure['rc']} fail_retries={fail_retries} "
+                    f"total_spawns={attempts.total_spawns}"
+                )
                 if failure.get("timeout"):
                     xs["exit_reason"] = "timeout"
-                    self._sse_error(_error_payload(f"opencode timed out after {TIMEOUT_S:.0f}s"))
+                    self._sse_error(
+                        _error_payload(f"opencode timed out after {TIMEOUT_S:.0f}s")
+                    )
                     return
-                xs["exit_reason"] = "provider_fatal" if failure.get("partial") else "upstream_failed"
-                what = ("opencode provider error after partial output" if failure.get("partial")
-                        else "opencode run failed")
-                self._sse_error(_error_payload(
-                    f"{what} (rc={failure['rc']})"
-                    + ("" if failure.get("partial") else " without output")
-                    + (f": {failure['tail']}" if failure["tail"] else ""), failure["tail"]))
+                if failure.get("watchdog"):
+                    wd_obj: object = failure.get("watchdog")
+                    wd_reason = wd_obj if isinstance(wd_obj, str) else ""
+                    xs["exit_reason"] = wd_reason
+                    self._sse_error(_error_payload(f"opencode {wd_reason}"))
+                    return
+                xs["exit_reason"] = (
+                    "provider_fatal" if failure.get("partial") else "upstream_failed"
+                )
+                what = (
+                    "opencode provider error after partial output"
+                    if failure.get("partial")
+                    else "opencode run failed"
+                )
+                self._sse_error(
+                    _error_payload(
+                        f"{what} (rc={failure['rc']})"
+                        + ("" if failure.get("partial") else " without output")
+                        + (f": {failure['tail']}" if failure["tail"] else ""),
+                        failure["tail"] if isinstance(failure["tail"], str) else "",
+                    )
+                )
                 return
 
-            if dropped_blocks[0] and not tool_calls and not "".join(collected_texts).strip():
-                emit_content(_BROKEN_BLOCK_NOTICE)  # иначе клиент получил бы пустой ответ
+            if (
+                dropped_blocks[0]
+                and not tool_calls
+                and not "".join(collected_texts).strip()
+            ):
+                emit_content(
+                    _BROKEN_BLOCK_NOTICE
+                )  # иначе клиент получил бы пустой ответ
             full_text = "".join(collected_texts)
             prompt_tokens = int(usage.get("input") or 0) or _estimate_tokens(prompt)
-            completion_tokens = int(usage.get("output") or 0) or _estimate_tokens(full_text)
+            completion_tokens = int(usage.get("output") or 0) or _estimate_tokens(
+                full_text
+            )
 
             final_chunk = format_sse_chunk(
                 resp_id,
@@ -3657,16 +6623,27 @@ class Handler(BaseHTTPRequestHandler):
                 shown_model,
                 {},
                 finish_reason="tool_calls" if tool_calls else "stop",
-                usage=_build_openai_usage(prompt_tokens, completion_tokens,
-                                          int(usage.get("cached") or 0), int(usage.get("reasoning") or 0)),
+                usage=_build_openai_usage(
+                    prompt_tokens,
+                    completion_tokens,
+                    int(usage.get("cached") or 0),
+                    int(usage.get("reasoning") or 0),
+                ),
             )
             self.wfile.write(final_chunk.encode("utf-8"))
             self.wfile.write(b"data: [DONE]\n\n")
             self.wfile.flush()
-            xs.update(exit_reason="ok", tools=len(tool_calls), out_chars=len(full_text), rc=proc.returncode)
-            _log(f"stream done model={model} rc={proc.returncode} tools={len(tool_calls)} "
-                 f"out_chars={len(full_text)} emulate_tools={emulate_tools} retries={retries} "
-                 f"total_spawns={attempts.total_spawns}")
+            xs.update(
+                exit_reason="ok",
+                tools=len(tool_calls),
+                out_chars=len(full_text),
+                rc=proc.returncode if proc is not None else None,
+            )
+            _log(
+                f"stream done model={model} rc={proc.returncode if proc is not None else None} tools={len(tool_calls)} "
+                f"out_chars={len(full_text)} emulate_tools={emulate_tools} retries={retries} "
+                f"total_spawns={attempts.total_spawns}"
+            )
 
         except (BrokenPipeError, ConnectionResetError, OSError) as exc:
             _log(f"client gone mid-stream: {exc}")
@@ -3677,6 +6654,13 @@ class Handler(BaseHTTPRequestHandler):
                 except OSError:
                     pass
         finally:
+            # Таймер статуса не должен писать после завершения запроса.
+            first_visible.set()
+            if status_timer is not None:
+                status_timer.cancel()
+            with wfile_lock:
+                self.wfile = raw_wfile
+            self._first_visible = None
             if gate is not None:
                 gate.release()
             if proc is not None:
@@ -3697,6 +6681,324 @@ class Handler(BaseHTTPRequestHandler):
             attempts.commit()
             res.slots.release()
 
+    def _serve_json_serve(
+        self,
+        model: str,
+        prompt: str,
+        effort: str,
+        emulate_tools: bool,
+        tools: list[dict[str, object]] | None,
+        reported_model: str | None,
+        tool_choice: object,
+        res: _Resilience,
+        attempts: _RequestAttempts,
+        xs: dict[str, object],
+    ) -> bool:
+        """JSON через serve; True — ответ отправлен, False — fallback на run."""
+        thinking = effort.strip().lower() not in ("", "off", "none")
+        force_serve = (
+            os.environ.get("OPENCODE_ZEN_BRIDGE_TRANSPORT", "").strip().lower()
+            == "serve"
+        )
+        workdir = DEFAULTWORKDIR
+        workdir.mkdir(parents=True, exist_ok=True)
+        current_prompt = prompt
+        contents: list[str] = []
+        reasonings_all: list[str] = []
+        tool_calls_all: list[dict[str, object]] = []
+        tokens: dict[str, int] = {}
+        unmapped_retries = 0
+        incomplete_retries = 0
+        delivered_any = False
+        _prior_content = ""
+        _seen_call_keys: set[str] = set()
+
+        def _add_call(call: dict[str, object]) -> None:
+            """Вызов инструмента в итог: одинаковый (name, arguments) не дублируется."""
+            key = _call_key(str(call["name"]), call["arguments"])
+            if key in _seen_call_keys:
+                return
+            _seen_call_keys.add(key)
+            tool_calls_all.append(
+                {
+                    "index": len(tool_calls_all),
+                    "id": "call_" + uuid.uuid4().hex[:24],
+                    "type": "function",
+                    "function": {
+                        "name": call["name"],
+                        "arguments": json.dumps(call["arguments"], ensure_ascii=False),
+                    },
+                }
+            )
+
+        while True:
+            if attempts.total_spawns >= MAX_TOTAL_SPAWNS or not attempts.can_spawn():
+                xs["exit_reason"] = "upstream_failed"
+                self._send(502, _error_payload("serve spawn limit reached"))
+                return True
+            reasonings: list[str] = []
+            texts: list[str] = []
+            natives: list[dict[str, object]] = []
+            _gate_j = _StartupGate()
+            _gate_j.acquire()
+            if not res.spawn_limiter.acquire(
+                max_wait_s=min(SPAWN_WAIT_MAX_S, attempts.remaining_s())
+            ):
+                _gate_j.release()
+                _j_delivered = delivered_any or bool(
+                    contents
+                    or reasonings_all
+                    or tool_calls_all
+                    or texts
+                    or reasonings
+                    or natives
+                )
+                if not force_serve and not _j_delivered:
+                    return False
+                xs["exit_reason"] = "upstream_failed"
+                self._send(502, _error_payload("serve spawn limiter timeout"))
+                return True
+            attempts.note_spawn()
+            try:
+                result = _serve_one_attempt(
+                    model,
+                    current_prompt,
+                    effort,
+                    workdir,
+                    reasonings.append,
+                    texts.append,
+                    natives.append,
+                    attempts.deadline - TIMEOUT_S,
+                    is_client_gone=self._client_gone_check,
+                    on_status=lambda _t: None,
+                    thinking_enabled=thinking,
+                    deadline=attempts.deadline,
+                    on_startup_ready=_gate_j.release,
+                    emulate_tools=emulate_tools,
+                )
+            except ServeUnavailable as exc:
+                res.serve_health.record_failure()
+                _j_delivered = delivered_any or bool(
+                    contents
+                    or reasonings_all
+                    or tool_calls_all
+                    or texts
+                    or reasonings
+                    or natives
+                )
+                if not force_serve and not _j_delivered:
+                    return False
+                xs["exit_reason"] = "upstream_failed"
+                self._send(502, _error_payload(f"serve unavailable: {exc}"))
+                return True
+            except ServeSecurityError as exc:
+                xs["exit_reason"] = "provider_fatal"
+                self._send(502, _error_payload(f"serve security failure: {exc}"))
+                return True
+            finally:
+                _gate_j.release()
+            if "first_event_ms" not in xs or xs.get("first_event_ms") is None:
+                xs["first_event_ms"] = result["first_event_ms"]
+            if "ttft_ms" not in xs or xs.get("ttft_ms") is None:
+                xs["ttft_ms"] = result["ttft_ms"]
+            if result.get("exit_reason") == "client_gone":
+                xs["exit_reason"] = "client_gone"
+                return True
+            # Токены неуспешных попыток тоже учитываются (как в потоковом пути).
+            for _tk in ("input", "output", "cached", "reasoning"):
+                tokens[_tk] = tokens.get(_tk, 0) + int(result["usage"].get(_tk) or 0)
+            _delivered_j = bool(
+                delivered_any
+                or contents
+                or reasonings_all
+                or tool_calls_all
+                or texts
+                or reasonings
+                or natives
+                or result.get("delivered")
+            )
+            delivered_any = _delivered_j
+            if result.get("exit_reason") in (
+                "first_event_timeout",
+                "first_token_timeout",
+                "stall_timeout",
+                "invalid_serve_event",
+                "timeout",
+            ):
+                reason = str(result["exit_reason"])
+                if reason in ("first_event_timeout", "invalid_serve_event"):
+                    res.serve_health.record_failure()
+                else:
+                    attempts.attempt_done(True, False)
+                if not _delivered_j and not force_serve:
+                    return False
+                if attempts.allow_retry(reason):
+                    continue
+                xs["exit_reason"] = reason
+                self._send(502, _error_payload(f"serve {reason}"))
+                return True
+            if result.get("prompt_status") is not None:
+                _ps_j = int(result["prompt_status"] or 0)
+                if _ps_j == 429 or 500 <= _ps_j <= 599:
+                    attempts.attempt_done(True, False)
+                if not _delivered_j and not force_serve:
+                    return False
+                if attempts.allow_retry(f"prompt_status_{_ps_j}"):
+                    continue
+                xs["exit_reason"] = f"prompt_status_{_ps_j}"
+                self._send(502, _error_payload(f"serve prompt HTTP {_ps_j}"))
+                return True
+            if result["error"] is not None:
+                err = result["error"]
+                if result.get("transient_error"):
+                    attempts.attempt_done(True, False)
+                    contents.extend(texts)
+                    reasonings_all.extend(reasonings)
+                    if not _delivered_j and not force_serve:
+                        return False
+                    if not texts and attempts.allow_retry("serve_transient_error"):
+                        continue
+                    _sig_j = _incomplete_step_signal(
+                        "".join(texts),
+                        "".join(reasonings),
+                        tools or [],
+                        True,
+                        int(result["usage"].get("output") or 0),
+                        int(result["usage"].get("reasoning") or 0),
+                        tool_choice=tool_choice,
+                    )
+                    if _sig_j and attempts.allow_retry("incomplete_step"):
+                        current_prompt = _rewrite_tool_tags_for_model(
+                            _incomplete_tool_step_prompt(
+                                prompt,
+                                "".join(contents),
+                                tools or [],
+                                tool_choice,
+                                model,
+                            ),
+                            model,
+                        )
+                        continue
+                xs["exit_reason"] = "upstream_failed"
+                self._send(
+                    502,
+                    _error_payload(
+                        f"serve error: {_clean_err(str(err.get('message') or ''))}"
+                    ),
+                )
+                return True
+            if result.get("terminal") == "cancelled":
+                xs["exit_reason"] = "cancelled"
+                self._send(502, _error_payload("serve session cancelled"))
+                return True
+            res.serve_health.record_success()
+            attempts.attempt_done(False, True)
+            reasonings_all.extend(reasonings)
+            content_raw = "".join(texts)
+            calls: list[dict[str, object]] = []
+            content = content_raw
+            if emulate_tools and content_raw:
+                parsed_texts: list[str] = []
+                parser_json = ToolCallParser(parsed_texts.append, calls.append)
+                parser_json.feed(content_raw)
+                parser_json.finish()
+                content = "".join(parsed_texts)
+                content, _dropped = _strip_broken_tool_blocks(content)
+            if _prior_content:
+                content = _dedup_retry_text(_prior_content, content)
+            if content:
+                contents.append(content)
+            for call in calls:
+                _add_call(call)
+            unmapped: list[str] = []
+            for native in natives:
+                part = _as_dict(native.get("part"))
+                mapped = _native_call_as_dsh(native, tools) if emulate_tools else []
+                if not mapped and emulate_tools and part.get("tool"):
+                    unmapped.append(str(part.get("tool")))
+                for call in mapped:
+                    _add_call(call)
+            usage = result["usage"]
+            if not emulate_tools or tool_calls_all:
+                break
+            if unmapped:
+                if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
+                    "unmapped"
+                ):
+                    break
+                unmapped_retries += 1
+                _prior_content = "\n\n".join(c for c in contents if c)
+                current_prompt = _rewrite_tool_tags_for_model(
+                    _unavailable_tools_prompt(
+                        current_prompt, content_raw, unmapped, tools or [], model
+                    ),
+                    model,
+                )
+                continue
+            signal = _incomplete_step_signal(
+                content_raw,
+                "".join(reasonings),
+                tools or [],
+                False,
+                int(usage.get("output") or 0),
+                int(usage.get("reasoning") or 0),
+                tool_choice=tool_choice,
+            )
+            if not signal:
+                break
+            if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
+                "incomplete_step"
+            ):
+                break
+            incomplete_retries += 1
+            _prior_content = "\n\n".join(c for c in contents if c)
+            current_prompt = _rewrite_tool_tags_for_model(
+                _incomplete_tool_step_prompt(
+                    prompt, "\n\n".join(contents), tools or [], tool_choice, model
+                ),
+                model,
+            )
+        content_final = "\n\n".join(c for c in contents if c)
+        if not content_final and not tool_calls_all:
+            xs["exit_reason"] = "upstream_failed"
+            self._send(502, _error_payload("serve produced no text"))
+            return True
+        for i, tc_item in enumerate(tool_calls_all):
+            tc_item["index"] = i
+        msg: dict[str, object] = {"role": "assistant", "content": content_final}
+        if reasonings_all:
+            msg["reasoning_content"] = "".join(reasonings_all)
+        finish = "stop"
+        if tool_calls_all:
+            msg["tool_calls"] = tool_calls_all
+            finish = "tool_calls"
+        if self._client_gone_check():
+            xs["exit_reason"] = "client_gone"
+            return True
+        xs.update(
+            exit_reason="ok",
+            tools=len(tool_calls_all),
+            out_chars=len(content_final),
+            rc=0,
+        )
+        self._send(
+            200,
+            {
+                "id": f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}",
+                "object": "chat.completion",
+                "created": int(time.time()),
+                "model": reported_model or model,
+                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
+                "usage": _build_openai_usage(
+                    int(tokens.get("input") or 0) or _estimate_tokens(prompt),
+                    int(tokens.get("output") or 0) or _estimate_tokens(content_final),
+                    tokens.get("cached", 0),
+                    tokens.get("reasoning", 0),
+                ),
+            },
+        )
+        return True
+
     def _serve_json(self, model: str, prompt: str, effort: str, emulate_tools: bool = False,
                     tools: list[dict[str, Any]] | None = None,
                     google_input: GoogleInput | None = None, reported_model: str | None = None,
@@ -3716,30 +7018,91 @@ class Handler(BaseHTTPRequestHandler):
         res = self._res()
         if not self._acquire_slot(res):
             return
-        attempts = _RequestAttempts(res, time.monotonic() + TIMEOUT_S,
-                                    use_breaker=not _is_google_direct_model(model))
+        attempts = _RequestAttempts(
+            res,
+            time.monotonic() + TIMEOUT_S,
+            use_breaker=not _is_google_direct_model(model),
+        )
         xs["attempts"] = attempts
         try:
             if not attempts.begin_attempt():
                 xs["exit_reason"] = "circuit_open"
-                self._send(503, {"error": {"message": "upstream circuit open", "type": "overloaded"}})
+                self._send(
+                    503,
+                    {
+                        "error": {
+                            "message": "upstream circuit open",
+                            "type": "overloaded",
+                        }
+                    },
+                )
                 return
+            if not _is_google_direct_model(model) and _select_transport(res) == "serve":
+                xs["transport"] = "serve"
+                xs["transport_history"] = ["serve"]
+                if self._serve_json_serve(
+                    model,
+                    prompt,
+                    effort,
+                    emulate_tools,
+                    tools,
+                    reported_model,
+                    tool_choice
+                    if isinstance(tool_choice, (str, dict)) or tool_choice is None
+                    else None,
+                    res,
+                    attempts,
+                    xs,
+                ):
+                    return
+                xs["transport"] = "run"
+                xs["transport_history"] = ["serve", "run"]
+            else:
+                xs["transport"] = "google" if _is_google_direct_model(model) else "run"
+                xs["transport_history"] = [str(xs["transport"])]
             while True:
+                if not attempts.can_spawn():
+                    # Суммарный потолок serve + run: четвёртый спавн запрещён.
+                    xs["exit_reason"] = "upstream_failed"
+                    self._send(502, _error_payload("spawn limit reached"))
+                    return
                 if retries:
-                    _log(f"exec retry={retries} ({'incomplete tool step' if incomplete_retry else 'unmapped built-in tool'})"
-                         f" total_spawns={attempts.total_spawns}/{attempts.max_total}")
-                run = Run(model, attempt_prompt, effort, DEFAULTWORKDIR,
-                          tools=(tools or []) if emulate_tools else None, google_input=google_input,
-                          attempts=attempts, resilience=res)
+                    _log(
+                        f"exec retry={retries} ({'incomplete tool step' if incomplete_retry else 'unmapped built-in tool'})"
+                        f" total_spawns={attempts.total_spawns}/{attempts.max_total}"
+                    )
+                run = Run(
+                    model,
+                    attempt_prompt,
+                    effort,
+                    DEFAULTWORKDIR,
+                    tools=(tools or []) if emulate_tools else None,
+                    google_input=google_input,
+                    attempts=attempts,
+                    resilience=res,
+                )
+                run.is_client_gone = self._client_gone_check
                 try:
                     out = run.execute()
                 finally:
                     run.close()
 
-                if out.get("state") in ("launcher_missing", "spawn_failed", "client_gone"):
+                if out.get("state") in (
+                    "launcher_missing",
+                    "spawn_failed",
+                    "client_gone",
+                ):
                     xs["exit_reason"] = str(out["state"])
-                    self._send(502, {"error": {"message": out.get("err") or out["state"],
-                                               "type": "proxy_error", "code": 502}})
+                    self._send(
+                        502,
+                        {
+                            "error": {
+                                "message": out.get("err") or out["state"],
+                                "type": "proxy_error",
+                                "code": 502,
+                            }
+                        },
+                    )
                     return
                 content = out["text"]
                 if emulate_tools and content:
@@ -3754,66 +7117,120 @@ class Handler(BaseHTTPRequestHandler):
                             content = ""
                 if incomplete_retry:
                     # Уже отданная преамбула подавляется, переформулированный текст сохраняется целиком.
-                    content = _dedup_retry_text("\n\n".join(c for c in contents if c), content)
+                    content = _dedup_retry_text(
+                        "\n\n".join(c for c in contents if c), content
+                    )
                 if content:
                     contents.append(content)
                 if out.get("reasoning"):
                     reasonings.append(out["reasoning"])
                 for key in ("input", "output", "cached", "reasoning"):
-                    tokens[key] = tokens.get(key, 0) + int((out.get("usage") or {}).get(key) or 0)
+                    tokens[key] = tokens.get(key, 0) + int(
+                        (out.get("usage") or {}).get(key) or 0
+                    )
                 unmapped: list[str] = []
                 if emulate_tools:
                     for native in out.get("native_calls") or []:
-                        calls = _native_to_tool_calls(native.get("tool"), native.get("input"), tools or [])
-                        _log(f"opencode built-in tool event: tool={native.get('tool')} status={native.get('status')} "
-                             f"mapped={bool(calls)} as={[c['name'] for c in calls]}")
+                        calls = _native_to_tool_calls(
+                            native.get("tool"), native.get("input"), tools or []
+                        )
+                        _log(
+                            f"opencode built-in tool event: tool={native.get('tool')} status={native.get('status')} "
+                            f"mapped={bool(calls)} as={[c['name'] for c in calls]}"
+                        )
                         if not calls:
                             unmapped.append(str(native.get("tool")))
                         for call in calls:
-                            tool_calls.append({
-                                "index": len(tool_calls), "id": "call_" + uuid.uuid4().hex[:24], "type": "function",
-                                "function": {"name": call["name"],
-                                             "arguments": json.dumps(call["arguments"], ensure_ascii=False)}})
+                            tool_calls.append(
+                                {
+                                    "index": len(tool_calls),
+                                    "id": "call_" + uuid.uuid4().hex[:24],
+                                    "type": "function",
+                                    "function": {
+                                        "name": call["name"],
+                                        "arguments": json.dumps(
+                                            call["arguments"], ensure_ascii=False
+                                        ),
+                                    },
+                                }
+                            )
                 if out.get("fatal_error") and not tool_calls:
                     tail = _clean_err(str(out.get("err") or ""), 500)
                     xs["exit_reason"] = "provider_fatal"
-                    self._send(502, _error_payload(
-                        f"opencode provider error after partial output (HTTP {out.get('provider_status')})"
-                        + (f": {tail}" if tail else ""), tail))
+                    self._send(
+                        502,
+                        _error_payload(
+                            f"opencode provider error after partial output (HTTP {out.get('provider_status')})"
+                            + (f": {tail}" if tail else ""),
+                            tail,
+                        ),
+                    )
                     return
                 if not emulate_tools or tool_calls:
                     break
                 if unmapped:
-                    if unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("unmapped"):
-                        _log(f"unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})")
-                        contents.append(f"[opencode-zen-bridge: модель вызывала недоступный встроенный "
-                                        f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]")
+                    if (
+                        unmapped_retries >= NATIVE_RETRY_LIMIT
+                        or not attempts.allow_retry("unmapped")
+                    ):
+                        _log(
+                            f"unmapped built-in tools={unmapped}: retries exhausted ({unmapped_retries})"
+                        )
+                        contents.append(
+                            f"[opencode-zen-bridge: модель вызывала недоступный встроенный "
+                            f"инструмент ({', '.join(unmapped)}); повторы исчерпаны]"
+                        )
                         break
                     retries += 1
                     unmapped_retries += 1
                     incomplete_retry = False
-                    _log(f"unmapped built-in tools={unmapped}: re-prompt {unmapped_retries}/{NATIVE_RETRY_LIMIT}")
+                    _log(
+                        f"unmapped built-in tools={unmapped}: re-prompt {unmapped_retries}/{NATIVE_RETRY_LIMIT}"
+                    )
                     attempt_prompt = _rewrite_tool_tags_for_model(
                         _unavailable_tools_prompt(attempt_prompt, out["text"], unmapped, tools or [], model), model)
                     continue
                 run_usage = out.get("usage") or {}
-                signal = 0 if out.get("provider_status") in _FATAL_HTTP else _incomplete_step_signal(
-                    out["text"], str(out.get("reasoning") or ""), tools or [],
-                    bool(out.get("had_error")), int(run_usage.get("output") or 0),
-                    int(run_usage.get("reasoning") or 0), tool_choice=tool_choice)
+                signal = (
+                    0
+                    if out.get("provider_status") in _FATAL_HTTP
+                    else _incomplete_step_signal(
+                        out["text"],
+                        str(out.get("reasoning") or ""),
+                        tools or [],
+                        bool(out.get("had_error")),
+                        int(run_usage.get("output") or 0),
+                        int(run_usage.get("reasoning") or 0),
+                        tool_choice=tool_choice,
+                    )
+                )
                 if not signal:
                     break
-                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("incomplete_step"):
-                    _log(f"incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}")
+                if incomplete_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry(
+                    "incomplete_step"
+                ):
+                    _log(
+                        f"incomplete tool step: retries exhausted ({incomplete_retries}) signal={signal}"
+                    )
                     break
                 retries += 1
                 incomplete_retries += 1
                 incomplete_retry = True
                 attempts.signal = signal
-                _log(f"incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
-                     f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}")
-                attempt_prompt = _rewrite_tool_tags_for_model(_incomplete_tool_step_prompt(
-                    prompt, "\n\n".join(c for c in contents if c), tools or [], tool_choice, model), model)
+                _log(
+                    f"incomplete tool step: re-prompt {incomplete_retries}/{NATIVE_RETRY_LIMIT} "
+                    f"signal={signal} total_spawns={attempts.total_spawns}/{attempts.max_total}"
+                )
+                attempt_prompt = _rewrite_tool_tags_for_model(
+                    _incomplete_tool_step_prompt(
+                        prompt,
+                        "\n\n".join(c for c in contents if c),
+                        tools or [],
+                        tool_choice,
+                        model,
+                    ),
+                    model,
+                )
         finally:
             attempts.commit()
             res.slots.release()
@@ -3832,14 +7249,21 @@ class Handler(BaseHTTPRequestHandler):
             tc["index"] = i
         content = "\n\n".join(c for c in contents if c)
         if dropped_blocks and not content.strip() and not tool_calls:
-            content = _BROKEN_BLOCK_NOTICE  # иначе клиент получил бы пустой ответ или 502
+            content = (
+                _BROKEN_BLOCK_NOTICE  # иначе клиент получил бы пустой ответ или 502
+            )
         if not content and not tool_calls:
             # Пустой текст с ненулевым rc/ошибкой провайдера — честная 502, не выдуманный ответ.
             tail = _clean_err(str(out.get("err") or ""), 500)
             xs["exit_reason"] = "upstream_failed"
-            self._send(502, _error_payload(
-                f"opencode run produced no text (rc={out.get('rc')}, state={out.get('state')})"
-                + (f": {tail}" if tail else ""), tail))
+            self._send(
+                502,
+                _error_payload(
+                    f"opencode run produced no text (rc={out.get('rc')}, state={out.get('state')})"
+                    + (f": {tail}" if tail else ""),
+                    tail,
+                ),
+            )
             return
 
         prompt_tokens = int(tokens.get("input") or 0) or _estimate_tokens(prompt)
@@ -3852,19 +7276,33 @@ class Handler(BaseHTTPRequestHandler):
         if tool_calls:
             msg["tool_calls"] = tool_calls
             finish = "tool_calls"
-        xs.update(exit_reason="ok", tools=len(tool_calls), out_chars=len(content), rc=out.get("rc"))
-        _log(f"done model={model} rc={out.get('rc')} state={out.get('state')} tools={len(tool_calls)} "
-             f"out_chars={len(content)} retries={retries} total_spawns={attempts.total_spawns}")
-
-        self._send(200, {
-            "id": f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}", "object": "chat.completion",
-            "created": int(time.time()), "model": reported_model or model,
-            "choices": [{"index": 0,
-                         "message": msg,
-                         "finish_reason": finish}],
-            "usage": _build_openai_usage(prompt_tokens, completion_tokens,
-                                         tokens.get("cached", 0), tokens.get("reasoning", 0)),
-        })
+        xs.update(
+            exit_reason="ok",
+            tools=len(tool_calls),
+            out_chars=len(content),
+            rc=out.get("rc"),
+        )
+        _log(
+            f"done model={model} rc={out.get('rc')} state={out.get('state')} tools={len(tool_calls)} "
+            f"out_chars={len(content)} retries={retries} total_spawns={attempts.total_spawns}"
+        )
+
+        self._send(
+            200,
+            {
+                "id": f"chatcmpl-oczen-{uuid.uuid4().hex[:12]}",
+                "object": "chat.completion",
+                "created": int(time.time()),
+                "model": reported_model or model,
+                "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
+                "usage": _build_openai_usage(
+                    prompt_tokens,
+                    completion_tokens,
+                    tokens.get("cached", 0),
+                    tokens.get("reasoning", 0),
+                ),
+            },
+        )
 
     # ---- HTTP --------------------------------------------------------------------
     def do_GET(self) -> None:
@@ -3873,26 +7311,50 @@ class Handler(BaseHTTPRequestHandler):
             _maybe_reload_catalog()
             with _active_lock:
                 active = len(_active)
-            self._send(200, {
-                "ok": True, "transport": "opencode-zen-cli",
-                "models": sorted(ALLOWED_MODELS), "default_model": _effective_default_model(),
-                "catalog_mode": CATALOG_MODE, "catalog_source": CATALOG_SOURCE,
-                "active": active, "max_concurrent": MAX_CONCURRENT,
-                "stream": True, "tool_emulation": True,
-                "uptime_s": int(time.time() - _started),
-            })
+            self._send(
+                200,
+                {
+                    "ok": True,
+                    "transport": "opencode-zen-cli",
+                    "models": sorted(ALLOWED_MODELS),
+                    "default_model": _effective_default_model(),
+                    "catalog_mode": CATALOG_MODE,
+                    "catalog_source": CATALOG_SOURCE,
+                    "active": active,
+                    "max_concurrent": MAX_CONCURRENT,
+                    "stream": True,
+                    "tool_emulation": True,
+                    "uptime_s": int(time.time() - _started),
+                },
+            )
             return
         if not _auth_ok(self):
-            self._send(401, {"error": {"message": "unauthorized", "type": "auth_error"}})
+            self._send(
+                401, {"error": {"message": "unauthorized", "type": "auth_error"}}
+            )
             return
         if path in ("/v1/models", "/models"):
             _maybe_reload_catalog()
-            self._send(200, {"object": "list", "data": [
-                {"id": mid, "object": "model", "owned_by": "opencode-zen", "created": 0,
-                 "context_length": meta["context_length"], "max_output": meta["max_output"],
-                 "reasoning_efforts": list(meta.get("reasoning_efforts") or [])}
-                for mid, meta in sorted(ALLOWED_MODELS.items())
-            ]})
+            self._send(
+                200,
+                {
+                    "object": "list",
+                    "data": [
+                        {
+                            "id": mid,
+                            "object": "model",
+                            "owned_by": "opencode-zen",
+                            "created": 0,
+                            "context_length": meta["context_length"],
+                            "max_output": meta["max_output"],
+                            "reasoning_efforts": list(
+                                meta.get("reasoning_efforts") or []
+                            ),
+                        }
+                        for mid, meta in sorted(ALLOWED_MODELS.items())
+                    ],
+                },
+            )
             return
         self._send(404, {"error": {"message": f"not found: {path}"}})
 
@@ -4005,8 +7467,11 @@ def main() -> int:
         WORKSPACE.mkdir(parents=True, exist_ok=True)
     except OSError as exc:
         _log(f"workspace mkdir failed: {exc}")
-    _log(f"start host={HOST} port={PORT} catalog={CATALOG_MODE}/{CATALOG_SOURCE} "
-         f"models={sorted(ALLOWED_MODELS)} launcher={_resolve_launcher()}")
+    _ = _startup_reaper()
+    _log(
+        f"start host={HOST} port={PORT} catalog={CATALOG_MODE}/{CATALOG_SOURCE} "
+        f"models={sorted(ALLOWED_MODELS)} launcher={_resolve_launcher()}"
+    )
     server = Server((HOST, PORT), Handler, resilience=_DEFAULT_RESILIENCE)
     try:
         server.serve_forever()
diff --git a/bridges/opencode-zen-bridge/tests/test_step_interruption.py b/bridges/opencode-zen-bridge/tests/test_step_interruption.py
index 46df891..defcf65 100644
--- a/bridges/opencode-zen-bridge/tests/test_step_interruption.py
+++ b/bridges/opencode-zen-bridge/tests/test_step_interruption.py
@@ -21,9 +21,11 @@ import socket
 import tempfile
 import threading
 import unittest
+from unittest import mock
 import urllib.request
 from pathlib import Path
 from typing import Any
+from typing import Protocol, cast
 
 import server
 from tests._fake_cli import allow_child_env
@@ -64,7 +66,7 @@ INVOKE_CALLS = CALLS.replace("tool_call", "tool_invoke")
 # Реальный шаг glm-5.3-flash-free: апстрим вырезал `<tool_call>…` из text, а 97 токенов выставил.
 SWALLOWED_TEXT = "2026-10-24 (MSK) — статус: проверяю вывод джобы job_fetch_01 и читаю goal.md."
 
-FAKE_OPENCODE = r'''#!/usr/bin/env python3
+FAKE_OPENCODE = r"""#!/usr/bin/env python3
 import json, os, sys, time
 counter = os.environ["FAKE_OC_COUNTER"]
 n = int(open(counter).read()) if os.path.exists(counter) else 0
@@ -139,10 +141,29 @@ elif mode == "unmapped_then_promise" and n == 2:
     reasoning(os.environ["FAKE_OC_PLAN"])
     text(os.environ["FAKE_OC_STATUS"])
     finish()
+elif mode == "unmapped_incomplete_calls" and n == 0:
+    ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
+    finish()
+elif mode == "unmapped_incomplete_calls" and n == 1:
+    reasoning(os.environ["FAKE_OC_PLAN"])
+    text(os.environ["FAKE_OC_STATUS"])
+    finish()
 else:
     text(calls)
     finish()
-'''
+"""
+
+
+class _EnvPatcher(Protocol):
+    """Протокол patch.dict для изоляции окружения."""
+
+    def start(self) -> object:
+        """Запустить patch."""
+        ...
+
+    def stop(self) -> object:
+        """Остановить patch."""
+        ...
 
 
 class TestStepInterruptionLive(unittest.TestCase):
@@ -176,20 +197,29 @@ class TestStepInterruptionLive(unittest.TestCase):
         cls.tmp.cleanup()
 
     counter: Path = Path()
+    _fake_env: object = None
 
     def setUp(self) -> None:
+        # Изоляция REQ-017: свежий бюджет повторов на каждый тест, без сброса в проде.
+        self.httpd.resilience = server._Resilience()
         self.counter = Path(self.tmp.name) / f"counter-{self.id()}"
-        os.environ["FAKE_OC_COUNTER"] = str(self.counter)
-        os.environ["FAKE_OC_PLAN"] = PLAN
-        os.environ["FAKE_OC_PREAMBLE"] = PREAMBLE
-        os.environ["FAKE_OC_STATUS"] = STATUS_ONLY
-        os.environ["FAKE_OC_CALLS"] = CALLS
-        os.environ["FAKE_OC_SWALLOW"] = SWALLOWED_TEXT
+        # RW-032: все FAKE_OC_* изолированы patch.dict — предустановленные значения восстановятся.
+        self._fake_env = mock.patch.dict(
+            os.environ,
+            {
+                "FAKE_OC_COUNTER": str(self.counter),
+                "FAKE_OC_PLAN": PLAN,
+                "FAKE_OC_PREAMBLE": PREAMBLE,
+                "FAKE_OC_STATUS": STATUS_ONLY,
+                "FAKE_OC_CALLS": CALLS,
+                "FAKE_OC_SWALLOW": SWALLOWED_TEXT,
+            },
+            clear=False,
+        )
+        _ = cast(_EnvPatcher, self._fake_env).start()
 
     def tearDown(self) -> None:
-        for name in ("FAKE_OC_COUNTER", "FAKE_OC_MODE", "FAKE_OC_PLAN", "FAKE_OC_PREAMBLE",
-                     "FAKE_OC_STATUS", "FAKE_OC_CALLS", "FAKE_OC_SWALLOW", "FAKE_OC_RAW"):
-            os.environ.pop(name, None)
+        _ = cast(_EnvPatcher, self._fake_env).stop()
 
     def _post(self, stream: bool, model: str = "muse-spark-1.3-contributor-free",
               messages: list[dict[str, Any]] | None = None) -> bytes:
@@ -402,19 +432,51 @@ class TestStepInterruptionLive(unittest.TestCase):
     # --- Бюджеты повторов раздельные -----------------------------------------------------
 
     def test_unmapped_retries_do_not_exhaust_incomplete_budget_stream(self) -> None:
+        """REQ-017/MAX_TOTAL_SPAWNS=3: unmapped-повторы не исчерпывают бюджет шага (итого 3 запуска)."""
         os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
         content, finishes, names = self._stream()
-        self.assertEqual(self._runs(), 4)
-        self.assertEqual(names, ["job_output", "bash"])
-        self.assertEqual(finishes, ["tool_calls"])
+        self.assertEqual(self._runs(), 3)
+        self.assertEqual(names, [])
+        self.assertEqual(finishes, ["stop"])
         self.assertEqual(content.count("Собираю факты"), 1)
 
     def test_unmapped_retries_do_not_exhaust_incomplete_budget_json(self) -> None:
+        """REQ-017/MAX_TOTAL_SPAWNS=3: unmapped-повторы не исчерпывают бюджет шага (итого 3 запуска)."""
         os.environ["FAKE_OC_MODE"] = "unmapped_then_promise"
-        out = json.loads(self._post(stream=False))
-        self.assertEqual(self._runs(), 4)
-        self.assertEqual([c["function"]["name"] for c in out["choices"][0]["message"]["tool_calls"]],
-                         ["job_output", "bash"])
+        raw_post = self._post(stream=False)
+        raw_text = raw_post.decode("utf-8") if isinstance(raw_post, bytes) else raw_post
+        parsed_obj: object = server._loads_object(raw_text)
+        self.assertIsInstance(parsed_obj, dict)
+        choices_obj = (
+            parsed_obj.get("choices") if isinstance(parsed_obj, dict) else None
+        )
+        self.assertIsInstance(choices_obj, list)
+        choice_obj = (
+            choices_obj[0] if isinstance(choices_obj, list) and choices_obj else {}
+        )
+        self.assertIsInstance(choice_obj, dict)
+        message_obj = (
+            choice_obj.get("message") if isinstance(choice_obj, dict) else None
+        )
+        self.assertIsInstance(message_obj, dict)
+        self.assertEqual(self._runs(), 3)
+        self.assertEqual(
+            message_obj.get("tool_calls") or []
+            if isinstance(message_obj, dict)
+            else [],
+            [],
+        )
+        self.assertEqual(
+            choice_obj.get("finish_reason") if isinstance(choice_obj, dict) else None,
+            "stop",
+        )
+
+    def test_unmapped_then_incomplete_then_calls_within_cap_stream(self) -> None:
+        os.environ["FAKE_OC_MODE"] = "unmapped_incomplete_calls"
+        _content, finishes, names = self._stream()
+        self.assertEqual(self._runs(), 3)
+        self.assertEqual(names, ["job_output", "bash"])
+        self.assertEqual(finishes, ["tool_calls"])
 
     # --- Обычный текстовый ответ не ретраится ------------------------------------------
 

diff --git a/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py b/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
new file mode 100644
index 0000000..26ce73a
--- /dev/null
+++ b/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
@@ -0,0 +1,1962 @@
+#!/usr/bin/env python3
+"""Реалтайм-размышление serve-транспорта и watchdog legacy-пути (REQ-001..REQ-020)."""
+
+from __future__ import annotations
+
+import ast
+import hashlib
+import http.client
+import json
+import os
+import signal
+import shutil
+import socket
+import struct
+import subprocess
+import sys
+import tempfile
+import threading
+import time
+import unittest
+from collections.abc import Callable, Mapping
+from pathlib import Path
+from typing import Protocol, cast, override
+from unittest import mock
+
+import server
+from tests._fixtures import install_test_models
+
+_ = install_test_models(server)
+MODEL = "muse-spark-1.3-contributor-free"
+
+
+class _Patcher(Protocol):
+    """Минимальный протокол patch-объекта unittest.mock для тестов."""
+
+    def start(self) -> object:
+        """Запустить patch."""
+        ...
+
+    def stop(self) -> object:
+        """Остановить patch."""
+        ...
+
+
+LEGACY_FAKE = r"""#!/usr/bin/env python3
+import json, os, sys, time
+def ev(o): print(json.dumps(o), flush=True)
+mode = os.environ.get("FAKE_RT_MODE", "fast")
+prompt = sys.stdin.read()
+if mode == "slow":
+    time.sleep(1.6)
+    ev({"type": "reasoning", "part": {"text": "Думаю медленно"}})
+    ev({"type": "text", "part": {"text": "Готово"}})
+    ev({"type": "step_finish", "part": {"tokens": {"input": 3, "output": 2}}})
+elif mode == "silent":
+    time.sleep(8)
+elif mode == "stall":
+    ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
+    time.sleep(8)
+else:
+    ev({"type": "reasoning", "part": {"text": "Simple greeting."}})
+    ev({"type": "text", "part": {"text": "Привет!"}})
+    ev({"type": "step_finish", "part": {"tokens": {"input": 3, "output": 2}}})
+"""
+
+FAKE_SERVE = r"""#!/usr/bin/env python3
+import base64, json, os, re, sys, threading, time
+from pathlib import Path
+from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
+sys.stderr.write("x" * 70000 + "\n"); sys.stderr.flush()
+if len(sys.argv) > 1 and sys.argv[1] == "run":
+    time.sleep(1.2)
+    print(json.dumps({"type": "reasoning", "part": {"text": "Поздняя мысль"}}), flush=True)
+    print(json.dumps({"type": "text", "part": {"text": "Поздний ответ"}}), flush=True)
+    print(json.dumps({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}}), flush=True)
+    raise SystemExit(0)
+port = int(sys.argv[sys.argv.index("--port") + 1])
+password = os.environ.get("OPENCODE_SERVER_PASSWORD", "")
+state = {"prompt": "", "cancelled": False, "rejected": False, "interrupted": False, "record": ""}
+lock = threading.Lock()
+def expected_auth():
+    return "Basic " + base64.b64encode(("opencode:" + password).encode()).decode()
+class H(BaseHTTPRequestHandler):
+    def log_message(self, *args): pass
+    def check(self):
+        if self.headers.get("Authorization") != expected_auth():
+            self.send_response(401); self.end_headers(); return False
+        return True
+    def send_json(self, code, obj):
+        body = json.dumps(obj).encode()
+        self.send_response(code); self.send_header("Content-Type", "application/json")
+        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
+    def do_GET(self):
+        if self.path == "/api/info":
+            self.send_json(200, {"version": "2.1.2", "pid": os.getpid()}); return
+        if not self.check(): return
+        if self.path == "/api/session/active":
+            self.send_json(200, {"data": {}}); return
+        if self.path == "/api/event":
+            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
+            self.send_header("Cache-Control", "no-cache"); self.end_headers()
+            def emit(obj):
+                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode()); self.wfile.flush()
+            emit({"id": "e0", "type": "server.connected", "data": {}})
+            deadline = time.time() + 30
+            while time.time() < deadline and not state["prompt"]:
+                time.sleep(0.02)
+            prompt = state["prompt"]
+            if "__record:" in prompt:
+                rec = prompt.split("__record:", 1)[1].split("__", 1)[0]
+                state["record"] = rec
+                Path_write = rec
+                with open(Path_write, "w") as fh:
+                    json.dump({"argv": sys.argv, "pid": os.getpid(), "pgid": os.getpgid(0),
+                               "has_opencode_bin_env": "OPENCODE_BIN" in os.environ,
+                               "db": os.environ.get("OPENCODE_DB", "")}, fh)
+            sid = "ses_test1"
+            if "__never_event__" in prompt:
+                time.sleep(10); return
+            emit({"id": "e1", "type": "session.execution.started", "data": {"sessionID": sid}})
+            if "__silent__" in prompt:
+                time.sleep(10); return
+            if "__stall__" in prompt:
+                emit({"id": "es", "type": "session.reasoning.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "Первая мысль"}})
+                time.sleep(10); return
+            if "__slow__" in prompt:
+                time.sleep(1.4)
+            if "__form_missing_title__" in prompt or "__form_ok__" in prompt:
+                form = {"id": "form1", "sessionID": sid}
+                if "__form_ok__" in prompt: form.update({"title": "Вопрос", "fields": []})
+                emit({"id": "ef", "type": "form.created", "data": {"form": form}})
+                time.sleep(0.6)
+                if not state["cancelled"]:
+                    emit({"id": "e2", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "STEP2"}})
+                emit({"id": "e3", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 1, "output": 1, "reasoning": 0, "cache": {"read": 0, "write": 0}}}})
+                emit({"id": "e4", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
+            if "__permission__" in prompt or "__native_tool__" in prompt:
+                emit({"id": "ep", "type": "permission.asked", "data": {"id": "per1", "sessionID": sid, "action": "bash", "resources": ["*"], "source": {"type": "tool", "messageID": "m1", "id": "call1"}}})
+                emit({"id": "et1", "type": "session.tool.input.started", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "name": "bash"}})
+                emit({"id": "et2", "type": "session.tool.input.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "delta": "{\"command\": \"printf probe\"}"}})
+                emit({"id": "et3", "type": "session.tool.input.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "text": "{\"command\": \"printf probe\"}"}})
+                emit({"id": "et4", "type": "session.tool.failed", "data": {"sessionID": sid, "assistantMessageID": "m1", "id": "call1", "error": {"type": "permission.rejected", "message": "Rejected"}, "executed": False}})
+                emit({"id": "e5", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 5, "output": 3, "reasoning": 1, "cache": {"read": 2, "write": 9}}}})
+                emit({"id": "e6", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
+            if "__tool_text__" in prompt:
+                for part in ["<tool_in", "voke>{\"name\": \"bash\", \"arguments\": ", "{\"command\": \"echo hi\", \"description\": \"x\"}}</tool_invoke>"]:
+                    emit({"id": "etx", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": part}}); time.sleep(0.05)
+                emit({"id": "e7", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 5, "output": 3, "reasoning": 1, "cache": {"read": 2, "write": 9}}}})
+                emit({"id": "e8", "type": "session.execution.succeeded", "data": {"sessionID": sid}}); return
+            for i in range(5):
+                emit({"id": f"er{i}", "type": "session.reasoning.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": f"Мысль{i} "}}); time.sleep(0.12)
+            emit({"id": "et", "type": "session.text.delta", "data": {"sessionID": sid, "assistantMessageID": "m1", "delta": "Ответ\n"}})
+            emit({"id": "e9", "type": "session.step.ended", "data": {"sessionID": sid, "assistantMessageID": "m1", "tokens": {"input": 17, "output": 9, "reasoning": 4, "cache": {"read": 3, "write": 2}}}})
+            if "__end_record:" in prompt:
+                end_record = prompt.split("__end_record:", 1)[1].split("__", 1)[0]
+                with open(end_record, "w") as fh: fh.write(str(time.monotonic()))
+            emit({"id": "e10", "type": "session.execution.succeeded", "data": {"sessionID": sid}})
+            return
+        self.send_json(404, {"data": {}})
+    def do_POST(self):
+        length = int(self.headers.get("Content-Length") or 0)
+        raw = self.rfile.read(length) if length else b"{}"
+        if self.path == "/api/session":
+            if os.environ.get("FAKE_SERVE_SESSION_STATUS") == "503":
+                self.send_json(503, {"error": "unavailable"}); return
+            if os.environ.get("FAKE_SERVE_SESSION_STATUS") == "400":
+                self.send_json(400, {"error": "bad request"}); return
+            if not self.check(): return
+            self.send_json(200, {"data": {"id": "ses_test1"}}); return
+        if self.path == "/api/session/ses_test1/prompt":
+            if not self.check(): return
+            try: body = json.loads(raw)
+            except Exception: body = {}
+            prompt_text = str(body.get("text") or "")
+            forced = re.search(r"__prompt_status_(\d+)__", prompt_text)
+            if forced:
+                self.send_json(int(forced.group(1)), {"error": "forced"}); return
+            state["prompt"] = prompt_text
+            self.send_json(200, {"data": {"id": "msg1"}}); return
+        if self.path == "/api/session/ses_test1/permission/per1/reply":
+            if not self.check(): return
+            state["rejected"] = True; self.send_response(204); self.end_headers(); return
+        if self.path == "/api/session/ses_test1/form/form1/cancel":
+            if not self.check(): return
+            state["cancelled"] = True
+            if state["record"]:
+                with open(state["record"] + ".control", "w") as fh: fh.write("cancelled")
+            self.send_response(204); self.end_headers(); return
+        if self.path == "/api/session/ses_test1/interrupt":
+            if not self.check(): return
+            state["interrupted"] = True
+            if state["record"]:
+                with open(state["record"] + ".control", "a") as fh: fh.write("+interrupt")
+            self.send_response(204); self.end_headers(); return
+        self.send_json(404, {"data": {}})
+    def do_DELETE(self):
+        if not self.check(): return
+        self.send_response(204); self.end_headers()
+ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
+"""
+
+
+def _write_exe(tmp: Path, name: str, body: str) -> Path:
+    """Записать исполняемый фейк в tmp."""
+    path = tmp / name
+    path.write_text(body, "utf-8")  # pyright: ignore[reportUnusedCallResult] — причина: результат вызова в тесте не используется
+    _ = path.chmod(0o755)
+    return path
+
+
+class _Bridge:
+    """Живой мост на эфемерном порту с сохранением глобалок."""
+
+    def __init__(self) -> None:
+        self.tmp: tempfile.TemporaryDirectory[str] = tempfile.TemporaryDirectory()
+        self.saved_bin: str = server.OPENCODE_BIN
+        self.saved_key: str = server.AUTH_KEY
+        self.stream_started: float = 0.0
+        self.saved_log: Path = server.LOG_PATH
+        server.AUTH_KEY = "test-key"
+        server.LOG_PATH = Path(self.tmp.name) / "bridge.log"
+        self.httpd: server.Server = server.Server(("127.0.0.1", 0), server.Handler)
+        self.port: int = int(self.httpd.server_address[1])
+        self.thread: threading.Thread = threading.Thread(
+            target=self.httpd.serve_forever, daemon=True
+        )
+        self.thread.start()
+
+    def close(self) -> None:
+        self.httpd.shutdown()
+        self.httpd.server_close()
+        server.OPENCODE_BIN = self.saved_bin
+        server.AUTH_KEY = self.saved_key
+        server.LOG_PATH = self.saved_log
+        self.tmp.cleanup()
+
+    def post_json(
+        self, prompt: str, timeout: float = 20.0, with_tools: bool = True
+    ) -> tuple[int, dict[str, object]]:
+        """POST без stream: код и тело ответа (RemoteDisconnected — если мост ничего не отправил)."""
+        payload: dict[str, object] = {
+            "model": MODEL,
+            "messages": [{"role": "user", "content": prompt}],
+        }
+        if with_tools:
+            payload["tools"] = [
+                {
+                    "type": "function",
+                    "function": {
+                        "name": "bash",
+                        "description": "x",
+                        "parameters": {
+                            "type": "object",
+                            "properties": {"command": {"type": "string"}},
+                            "required": ["command"],
+                        },
+                    },
+                }
+            ]
+        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
+        try:
+            conn.request(
+                "POST",
+                "/v1/chat/completions",
+                json.dumps(payload).encode(),
+                {
+                    "Authorization": f"Bearer {server.AUTH_KEY}",
+                    "Content-Type": "application/json",
+                },
+            )
+            resp = conn.getresponse()
+            parsed: object = json.loads(resp.read())  # pyright: ignore[reportAny] — причина: тело ответа моста — динамический JSON
+            return resp.status, _as_obj_dict(parsed)
+        finally:
+            conn.close()
+
+    def post_stream_timed(
+        self,
+        prompt: str,
+        timeout: float = 20.0,
+        tool_choice: object = None,
+        effort: str | None = None,
+    ) -> tuple[list[tuple[float, dict[str, object]]], float]:
+        """POST stream с метками времени каждого SSE-чанка."""
+        payload: dict[str, object] = {
+            "model": MODEL,
+            "stream": True,
+            "messages": [{"role": "user", "content": prompt}],
+            "tools": [
+                {
+                    "type": "function",
+                    "function": {
+                        "name": "bash",
+                        "description": "x",
+                        "parameters": {
+                            "type": "object",
+                            "properties": {
+                                "command": {"type": "string"},
+                                "description": {"type": "string"},
+                            },
+                            "required": ["command"],
+                        },
+                    },
+                }
+            ],
+        }
+        if tool_choice is not None:
+            payload["tool_choice"] = tool_choice
+        if effort is not None:
+            payload["reasoning_effort"] = effort
+        body = json.dumps(payload).encode()
+        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
+        started = time.monotonic()
+        self.stream_started = started
+        conn.request(
+            "POST",
+            "/v1/chat/completions",
+            body,
+            {
+                "Authorization": f"Bearer {server.AUTH_KEY}",
+                "Content-Type": "application/json",
+            },
+        )
+        resp = conn.getresponse()
+        chunks: list[tuple[float, dict[str, object]]] = []
+        buf = b""
+        end = started
+        while True:
+            raw_data: object = (
+                resp.read1() if hasattr(resp, "read1") else resp.read(4096)
+            )
+            data: bytes = raw_data if isinstance(raw_data, bytes) else b""  # pyright: ignore[reportUnnecessaryIsInstance] — причина: typeshed уже выводит bytes для read1/read; проверка сохраняет защиту адаптера
+            if not data:
+                end = time.monotonic()
+                break
+            buf += data  # pyright: ignore[reportUnknownVariableType] — причина: буфер SSE пополняется байтами динамического read1/read после проверки bytes
+            while b"\n\n" in buf:
+                raw, buf = buf.split(b"\n\n", 1)  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType] — причина: split делит накопленные байты SSE на кадр и хвост, тип буфера потерян в typeshed
+                for line in raw.decode("utf-8", "replace").splitlines():  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType] — причина: байтовый кадр SSE декодируется в строки, тип raw наследуется от динамического буфера
+                    if line.startswith("data: {"):  # pyright: ignore[reportUnknownMemberType] — причина: line — строка из decode/splitlines динамического SSE-буфера
+                        parsed_obj: object = json.loads(line[6:])  # pyright: ignore[reportAny,reportUnknownArgumentType] — причина: json.loads возвращает динамический объект, далее он проверяется как dict
+                        parsed_chunk: dict[str, object] = (  # pyright: ignore[reportUnknownVariableType] — причина: ответ моста — динамический JSON, тип сужается проверкой isinstance
+                            parsed_obj if isinstance(parsed_obj, dict) else {}
+                        )
+                        chunks.append((time.monotonic() - started, parsed_chunk))
+        conn.close()
+        return chunks, end - started
+
+
+def _as_obj_dict(value: object) -> dict[str, object]:
+    """Объект как словарь с строковыми ключами, иначе пустой."""
+    if isinstance(value, dict):
+        return {str(k): v for k, v in value.items()}  # pyright: ignore[reportUnknownArgumentType,reportUnknownVariableType] — причина: ответ моста — динамический JSON, тип сужается проверкой isinstance
+    return {}
+
+
+def _deltas(
+    chunks: list[tuple[float, dict[str, object]]], key: str
+) -> list[tuple[float, str]]:
+    """Дельты одного поля с метками."""
+    out: list[tuple[float, str]] = []
+    for at, chunk in chunks:
+        choices_obj: object = chunk.get("choices")
+        if not isinstance(choices_obj, list) or not choices_obj:
+            continue
+        first: dict[str, object] = _as_obj_dict(cast(list[object], choices_obj)[0])
+        delta: dict[str, object] = _as_obj_dict(first.get("delta"))
+        value_obj: object = delta.get(key)
+        if isinstance(value_obj, str):
+            out.append((at, value_obj))
+    return out
+
+
+def _tool_names(chunks: list[tuple[float, dict[str, object]]]) -> list[str]:
+    """Имена tool_calls из SSE-чанков."""
+    names: list[str] = []
+    for _at, chunk in chunks:
+        choices_obj: object = chunk.get("choices")
+        if not isinstance(choices_obj, list) or not choices_obj:
+            continue
+        first: dict[str, object] = _as_obj_dict(cast(list[object], choices_obj)[0])
+        delta: dict[str, object] = _as_obj_dict(first.get("delta"))
+        calls_obj: object = delta.get("tool_calls")
+        if not isinstance(calls_obj, list):
+            continue
+        for tc_obj in cast(list[object], calls_obj):
+            fn: dict[str, object] = _as_obj_dict(_as_obj_dict(tc_obj).get("function"))
+            name_obj: object = fn.get("name")
+            if isinstance(name_obj, str):
+                names.append(name_obj)
+    return names
+
+
+class TestLegacyWatchdogAndKillpg(unittest.TestCase):
+    """Группа A: legacy watchdog, статусы, O-EXIT без FakeServe."""
+
+    bridge: _Bridge = cast(_Bridge, None)  # pyright: ignore[reportInvalidCast] — причина: атрибут класса задаётся в setUp до первого обращения
+    tmp: Path = Path()
+    fake: Path = Path()
+    env: object = None
+    allow: object = None
+
+    @override
+    def setUp(self) -> None:
+        self.bridge = _Bridge()
+        self.tmp = Path(self.bridge.tmp.name)
+        self.fake = _write_exe(self.tmp, "opencode-legacy", LEGACY_FAKE)
+        server.OPENCODE_BIN = str(self.fake)
+        self.env = mock.patch.dict(os.environ, {"FAKE_RT_MODE": "fast"}, clear=False)
+        _ = cast(_Patcher, self.env).start()
+        # Белый список standalone пропускает FAKE_RT_MODE дочернему процессу.
+        self.allow = mock.patch.object(
+            server,
+            "_STANDALONE_ENV_ALLOWLIST",
+            (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_RT_MODE"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        )
+        _ = cast(_Patcher, self.allow).start()
+
+    @override
+    def tearDown(self) -> None:
+        _ = cast(_Patcher, self.allow).stop()
+        _ = cast(_Patcher, self.env).stop()
+        self.bridge.close()
+
+    def test_fast_greeting_has_no_synthetic_status(self) -> None:
+        """Быстрый ответ: ровно модельные байты, без [мост]."""
+        chunks, _elapsed = self.bridge.post_stream_timed("привет")
+        reasoning = "".join(text for _at, text in _deltas(chunks, "reasoning_content"))
+        content = "".join(text for _at, text in _deltas(chunks, "content"))
+        self.assertEqual(reasoning, "Simple greeting.")
+        self.assertEqual(content, "Привет!")
+
+    def test_slow_upstream_gets_initial_status_before_1s(self) -> None:
+        """Медленный апстрим: первый [мост] не позже 1.0 с (REQ-004)."""
+        os.environ["FAKE_RT_MODE"] = "slow"
+        chunks, _elapsed = self.bridge.post_stream_timed("медленно")
+        statuses = [
+            (at, t)
+            for at, t in _deltas(chunks, "reasoning_content")
+            if t.startswith("[мост]") or "[мост]" in t
+        ]
+        self.assertTrue(statuses, "нет синтетического статуса")
+        self.assertLessEqual(statuses[0][0], 1.0)
+        self.assertTrue(statuses[0][1].endswith("\n"))
+
+    def test_initial_status_before_1s_under_startup_gate_contention(self) -> None:
+        """RW-017: TRANSPORT=run и занятый StartupGate — первый статус не позднее 1.0 с."""
+        saved_wait = server.STARTUP_WAIT_S
+        server.STARTUP_WAIT_S = 2.5
+        self.assertTrue(server._STARTUP_LOCK.acquire(timeout=1.0))  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+        try:
+            chunks, _elapsed = self.bridge.post_stream_timed("привет")
+        finally:
+            server._STARTUP_LOCK.release()  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+            server.STARTUP_WAIT_S = saved_wait
+        reasoning = _deltas(chunks, "reasoning_content")
+        statuses = [at for at, t in reasoning if "[мост]" in t]
+        self.assertTrue(statuses, chunks)
+        self.assertLessEqual(statuses[0], 1.0)
+        model = [at for at, t in reasoning if "[мост]" not in t]
+        self.assertTrue(model and statuses[0] < model[0], chunks)
+        self.assertEqual(
+            len([t for _at, t in reasoning if server.STATUS_INITIAL.strip() in t]), 1
+        )
+
+    def test_rw002_initial_status_while_waiting_spawn_limiter(self) -> None:
+        """RW-002: свободный StartupGate и задержанный лимитер не гасят начальный статус."""
+
+        def delayed_acquire(*_args: object, **_kw: object) -> bool:
+            time.sleep(1.2)
+            return True
+
+        with mock.patch.object(
+            self.bridge.httpd.resilience.spawn_limiter,
+            "acquire",
+            side_effect=delayed_acquire,
+        ):
+            chunks, _ = self.bridge.post_stream_timed("привет")
+        statuses = [
+            (at, t)
+            for at, t in _deltas(chunks, "reasoning_content")
+            if server.STATUS_INITIAL.strip() in t
+        ]
+        self.assertEqual(len(statuses), 1, chunks)
+        self.assertLessEqual(statuses[0][0], 1.0)
+
+    def test_reasoning_content_excluded_from_prompt(self) -> None:
+        """AC-007: reasoning истории не попадает в промпт."""
+        fn = server._messages_to_prompt  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        _system, prompt = fn(
+            [
+                {
+                    "role": "assistant",
+                    "content": "Ответ",
+                    "reasoning_content": "[мост] секретный статус",
+                },
+                {"role": "user", "content": "дальше"},
+            ]
+        )
+        self.assertNotIn("секретный статус", prompt)
+        self.assertNotIn("reasoning_content", prompt)
+
+    def test_frozen_slices_hashes(self) -> None:
+        """Замороженные функции побайтово неизменны."""
+        import ast as _ast
+
+        raw = Path(server.__file__).read_bytes()
+        lines = raw.splitlines(keepends=True)
+        nodes = {
+            n.name: n
+            for n in _ast.walk(_ast.parse(raw))
+            if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))
+        }
+        expected = {
+            "_run_env": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
+            "_stream_google_sse": "5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3",
+            "_execute_google_once": "88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6",
+        }
+        for name, digest in expected.items():
+            node = nodes[name]
+            blob = b"".join(lines[node.lineno - 1 : node.end_lineno])
+            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest, name)
+
+    def test_oexit_fields_present(self) -> None:
+        """O-EXIT/v1 содержит transport/first_event_ms/ttft_ms."""
+        _ = self.bridge.post_stream_timed("привет")
+        log = Path(self.bridge.tmp.name, "bridge.log")
+        text = log.read_text("utf-8") if log.exists() else ""
+        if not text:
+            text = Path(server.LOG_PATH).read_text("utf-8")
+        oexit = [line for line in text.splitlines() if "O-EXIT/v1" in line]
+        self.assertTrue(oexit)
+        self.assertIn("transport=", oexit[-1])
+        self.assertIn("first_event_ms=", oexit[-1])
+        self.assertIn("ttft_ms=", oexit[-1])
+
+    def test_watchdog_first_event_timeout(self) -> None:
+        """Тишина апстрима: watchdog срабатывает, а не TIMEOUT_S=1800."""
+        os.environ["FAKE_RT_MODE"] = "silent"
+        old: float = server.FIRST_EVENT_TIMEOUT_S
+        old_tok: float = server.FIRST_TOKEN_TIMEOUT_S
+        try:
+            server.FIRST_EVENT_TIMEOUT_S = 1.0
+            server.FIRST_TOKEN_TIMEOUT_S = 2.0
+            started = time.monotonic()
+            chunks, _elapsed = self.bridge.post_stream_timed("тишина", timeout=30.0)
+            elapsed = time.monotonic() - started
+        finally:
+            server.FIRST_EVENT_TIMEOUT_S = old
+            server.FIRST_TOKEN_TIMEOUT_S = old_tok
+        self.assertLess(elapsed, 25.0)
+        has_error = any("error" in chunk for _at, chunk in chunks)
+        self.assertTrue(has_error, chunks)
+
+
+class TestServeTransportAndFakeServe(unittest.TestCase):
+    """Группа B: serve-транспорт на FakeServe."""
+
+    bridge: _Bridge = cast(_Bridge, None)  # pyright: ignore[reportInvalidCast] — причина: атрибут класса задаётся в setUp до первого обращения
+    tmp: Path = Path()
+    fake: Path = Path()
+    cfg: Path = Path()
+    saved_cfg: Path = Path()
+    saved_lease: Path = Path()
+    env: object = None
+
+    @override
+    def setUp(self) -> None:
+        self.bridge = _Bridge()
+        self.tmp = Path(self.bridge.tmp.name)
+        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
+        server.OPENCODE_BIN = str(self.fake)
+        self.cfg = self.tmp / "dynamic_config.json"
+        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
+        self.saved_cfg = server.DYNAMIC_CONFIG_PATH
+        server.DYNAMIC_CONFIG_PATH = self.cfg
+        self.saved_lease = server.LEASE_DIR
+        server.LEASE_DIR = self.tmp / "leases"
+        self.env = mock.patch.dict(
+            os.environ,
+            {
+                "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
+                "HOME": str(self.tmp / "empty-home"),
+            },
+            clear=False,
+        )
+        _ = cast(_Patcher, self.env).start()
+        (self.tmp / "empty-home").mkdir(exist_ok=True)
+
+    @override
+    def tearDown(self) -> None:
+        _ = cast(_Patcher, self.env).stop()
+        server.DYNAMIC_CONFIG_PATH = self.saved_cfg
+        server.LEASE_DIR = self.saved_lease
+        self.bridge.close()
+
+    def test_ac026_realtime_chunks_before_upstream_end(self) -> None:
+        """AC-026: reasoning-чанки приходят, пока апстрим ещё идёт."""
+        end_record = self.tmp / "upstream-ended"
+        chunks, _elapsed = self.bridge.post_stream_timed(
+            f"обычный запрос __end_record:{end_record}__"
+        )
+        reasoning = _deltas(chunks, "reasoning_content")
+        model_reasoning = [
+            (at, t) for at, t in reasoning if not t.lstrip("\n").startswith("[мост]")
+        ]
+        self.assertGreaterEqual(len(model_reasoning), 5, chunks)
+        r_times = [at for at, _t in model_reasoning]
+        c_times = [at for at, t in _deltas(chunks, "content") if t]
+        self.assertTrue(c_times, chunks)
+        self.assertLess(r_times[0], c_times[0])
+        self.assertGreaterEqual(r_times[-1] - r_times[0], 0.15)
+        self.assertLess(max(b - a for a, b in zip(r_times, r_times[1:])), 0.5)
+        first_reasoning_t = model_reasoning[0][0]
+        upstream_end_t = float(end_record.read_text()) - self.bridge.stream_started
+        self.assertLess(first_reasoning_t, upstream_end_t)
+        self.assertLess(model_reasoning[-1][0] - model_reasoning[0][0], 2.0)
+        joined = "".join(t for _at, t in model_reasoning)
+        self.assertEqual(joined, "Мысль0 Мысль1 Мысль2 Мысль3 Мысль4 ")
+
+    def test_dynamic_config_switch_same_server(self) -> None:
+        """Тот же Server: false -> run, true -> serve, битый JSON -> false."""
+        reader = server._read_dynamic_config_enabled  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        self.assertTrue(reader())
+        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": False}), "utf-8")
+        self.assertFalse(reader())
+        _ = self.cfg.write_text("{broken", "utf-8")
+        self.assertFalse(reader())
+        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": "yes"}), "utf-8")
+        self.assertFalse(reader())
+        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
+        self.assertTrue(reader())
+
+    def test_serve_env_sanitized_all_branches(self) -> None:
+        """_serve_env: :memory:, allowlist, без OPENCODE_BIN и секретов."""
+        with mock.patch.dict(
+            os.environ, {"SECRET_SENTINEL": "x", "MY_API_KEY": "y"}, clear=False
+        ):
+            env: dict[str, str] = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        try:
+            self.assertEqual(env.get("OPENCODE_DB"), ":memory:")
+            self.assertNotIn("OPENCODE_BIN", env)
+            self.assertNotIn("SECRET_SENTINEL", env)
+            self.assertNotIn("MY_API_KEY", env)
+            self.assertTrue(env.get("OPENCODE_SERVER_PASSWORD"))
+            self.assertTrue(env.get("XDG_STATE_HOME"))
+            self.assertNotEqual(env.get("XDG_DATA_HOME"), env.get("XDG_STATE_HOME"))
+        finally:
+            shutil.rmtree(env["XDG_STATE_HOME"], ignore_errors=True)
+
+    def test_canonical_frozen_fixtures(self) -> None:
+        """Каноническое отображение замороженных wire-фикстур v2.1.2."""
+        mapper = server._map_serve_event  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        wire: dict[str, object] = {
+            "id": "evt1",
+            "type": "session.reasoning.delta",
+            "data": {
+                "sessionID": "ses_fixture_1",
+                "assistantMessageID": "msg1",
+                "delta": "Мысль без LF",
+            },
+        }
+        result = mapper(wire)
+        self.assertIsNotNone(result)
+        assert result is not None
+        etype, payload = result[0], result[1]
+        self.assertEqual(etype, "reasoning")
+        self.assertEqual(
+            payload, {"reasoning_content": "Мысль без LF", "sessionID": "ses_fixture_1"}
+        )
+        wire2: dict[str, object] = {
+            "id": "evt3",
+            "type": "session.step.ended",
+            "data": {
+                "sessionID": "ses_fixture_1",
+                "assistantMessageID": "msg1",
+                "tokens": {
+                    "input": 17,
+                    "output": 9,
+                    "reasoning": 4,
+                    "cache": {"read": 3, "write": 2},
+                },
+            },
+        }
+        result2 = mapper(wire2)
+        self.assertIsNotNone(result2)
+        assert result2 is not None
+        etype2, payload2 = result2[0], result2[1]
+        self.assertEqual(etype2, "step_finish")
+        self.assertEqual(
+            payload2,
+            {
+                "input": 17,
+                "output": 9,
+                "cached": 3,
+                "reasoning": 4,
+                "sessionID": "ses_fixture_1",
+            },
+        )
+
+    def test_tool_text_split_across_deltas(self) -> None:
+        """ToolCallParser на разрезанных дельтах serve."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__tool_text__ вызов")
+        self.assertEqual(_tool_names(chunks), ["bash"])
+
+    def test_native_tool_and_permission_reject(self) -> None:
+        """permission.asked -> reject, native tool -> DSH tool_call."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__native_tool__ сделай")
+        self.assertIn("bash", _tool_names(chunks))
+
+    def test_form_missing_title_cancels_without_step2(self) -> None:
+        """form.created без title: cancel+interrupt до проверки схемы, без Step2."""
+        record = self.tmp / "rec.json"
+        chunks, _elapsed = self.bridge.post_stream_timed(
+            f"__form_missing_title__ __record:{record}__ заполни"
+        )
+        content = "".join(t for _at, t in _deltas(chunks, "content"))
+        self.assertNotIn("STEP2", content)
+        control = Path(str(record) + ".control")
+        self.assertTrue(control.exists(), "FakeServe не получил cancel")
+        self.assertIn("cancelled", control.read_text("utf-8"))
+
+    def test_slow_serve_gets_status_and_no_status_on_fast(self) -> None:
+        """Медленный serve: статус <1с; быстрый serve: без лишнего статуса в reasoning модели."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__slow__ жди")
+        statuses = [
+            (at, t) for at, t in _deltas(chunks, "reasoning_content") if "[мост]" in t
+        ]
+        self.assertTrue(statuses)
+        self.assertLessEqual(statuses[0][0], 1.0)
+
+    def test_helper_argv_validation_and_lease_dir(self) -> None:
+        """--serve-helper: 6 аргументов, lease только в переданном каталоге."""
+        fn = server._run_serve_helper_cli  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        self.assertNotEqual(fn([]), 0)
+        self.assertNotEqual(fn(["a", "notaport", "bin", "lease", "1", "x"]), 0)
+        lease_dir = self.tmp / "leases-custom"
+        script = Path(server.__file__).resolve()
+        proc = subprocess.run(
+            [
+                sys.executable,
+                "-I",
+                str(script),
+                "--serve-helper",
+                "attemptX",
+                "9",
+                "bin",
+                str(lease_dir),
+                "1",
+            ],
+            capture_output=True,
+            text=True,
+            timeout=10,
+        )
+        self.assertNotEqual(proc.returncode, 0)
+
+    def test_serve_health_and_fallback_table(self) -> None:
+        """_ServeHealth sticky и таблица fallback_decision_table."""
+        health = server._ServeHealth()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        for _i in range(3):
+            health.record_failure()
+        self.assertTrue(health.is_degraded())
+        health.record_success()
+        self.assertFalse(health.is_degraded())
+        rows: list[dict[str, object]] = list(server.FALLBACK_DECISION_TABLE)
+        self.assertGreaterEqual(len(rows), 10)
+        by_event: dict[str, dict[str, object]] = {
+            str(r.get("event", "")): r for r in rows
+        }
+        silence_rows = [
+            r
+            for ev, r in by_event.items()
+            if "first_token_timeout" in ev and "silence" in ev
+        ]
+        self.assertEqual(len(silence_rows), 1)
+        self.assertEqual(silence_rows[0].get("action"), "serve_retry")
+        self.assertEqual(silence_rows[0].get("UpstreamBreaker_failure_increment"), 1)
+        auth_rows = [r for ev, r in by_event.items() if "HTTP401/403" in ev]
+        self.assertEqual(len(auth_rows), 1)
+        self.assertEqual(auth_rows[0].get("action"), "fail_closed")
+
+    def test_helper_drains_large_stderr(self) -> None:
+        """FakeServe пишет >64КиБ в stderr до SSE и не блокируется."""
+        chunks, elapsed = self.bridge.post_stream_timed("обычный запрос")
+        self.assertLess(elapsed, 15.0)
+        self.assertTrue(_deltas(chunks, "reasoning_content"))
+
+    def test_clean_room_fake_serve_via_monkeypatched_bin(self) -> None:
+        """RW-002: OPENCODE_BIN подменён при пустом HOME, serve работает."""
+        chunks, _elapsed = self.bridge.post_stream_timed("чистая комната")
+        self.assertTrue(_deltas(chunks, "content"))
+
+    def test_auto_fallback_to_run_and_sticky_degradation(self) -> None:
+        """auto: 503 на создании сессии -> fallback на run; после 3 запросов serve деградирован."""
+        saved_eligible = server.SERVE_TEST_ELIGIBLE
+        server.SERVE_TEST_ELIGIBLE = True
+        try:
+            with (
+                mock.patch.dict(
+                    os.environ,
+                    {
+                        "OPENCODE_ZEN_BRIDGE_TRANSPORT": "auto",
+                        "FAKE_SERVE_SESSION_STATUS": "503",
+                    },
+                    clear=False,
+                ),
+                mock.patch.object(
+                    server,
+                    "_SERVE_ALLOWLIST",
+                    (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+                ),
+                mock.patch.object(
+                    server,
+                    "_STANDALONE_ENV_ALLOWLIST",
+                    (
+                        *server._STANDALONE_ENV_ALLOWLIST,  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+                        "FAKE_SERVE_SESSION_STATUS",
+                    ),
+                ),
+            ):
+                for _i in range(3):
+                    chunks, _elapsed = self.bridge.post_stream_timed("обычный запрос")
+                    content = "".join(t for _at, t in _deltas(chunks, "content"))
+                    self.assertIn("Поздний ответ", content)
+                self.assertTrue(self.bridge.httpd.resilience.serve_health.is_degraded())
+        finally:
+            server.SERVE_TEST_ELIGIBLE = saved_eligible
+
+    def test_foreign_listener_rejected_and_startup_reaper(self) -> None:
+        """Чужой слушатель порта -> ServeUnavailable; reaper удаляет lease мёртвого родителя."""
+        with mock.patch.object(server, "_lsof_listener_pid", return_value=999998):
+            with self.assertRaises(server.ServeUnavailable) as ctx:
+                _ = server._spawn_serve("att_foreign", server._serve_env(MODEL))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        self.assertIn("foreign listener", str(ctx.exception))
+        lease_dir = self.tmp / "reaper-leases"
+        lease_dir.mkdir()
+        dead = lease_dir / "lease-dead.json"
+        alive = lease_dir / "lease-alive.json"
+        _ = dead.write_text(
+            json.dumps(
+                {
+                    "parent_pid": 999999,
+                    "helper_pid": 0,
+                    "pgid": 0,
+                    "owner_uid": os.getuid(),
+                }
+            ),
+            "utf-8",
+        )
+        _ = alive.write_text(
+            json.dumps(
+                {
+                    "parent_pid": os.getpid(),
+                    "helper_pid": 0,
+                    "pgid": 0,
+                    "owner_uid": os.getuid(),
+                }
+            ),
+            "utf-8",
+        )
+        _ = server._startup_reaper(lease_dir)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        self.assertFalse(dead.exists())
+        self.assertTrue(alive.exists())
+
+    def test_serve_400_fails_closed_without_health_increment(self) -> None:
+        """400 на создании сессии: SSE error fail-closed без инкремента serve_health."""
+        health = self.bridge.httpd.resilience.serve_health
+        failures_before = health.failures
+        with (
+            mock.patch.dict(
+                os.environ, {"FAKE_SERVE_SESSION_STATUS": "400"}, clear=False
+            ),
+            mock.patch.object(
+                server,
+                "_SERVE_ALLOWLIST",
+                (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+            ),
+            mock.patch.object(
+                server,
+                "_STANDALONE_ENV_ALLOWLIST",
+                (*server._STANDALONE_ENV_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"),  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+            ),
+        ):
+            chunks, _elapsed = self.bridge.post_stream_timed("обычный запрос")
+        joined = json.dumps(chunks, ensure_ascii=False)
+        self.assertIn("serve security failure", joined)
+        self.assertEqual(health.failures, failures_before)
+        self.assertFalse(health.is_degraded())
+
+    def _auto_mode(self) -> None:
+        """auto + eligible: serve выбирается для скриптового FakeServe."""
+        saved = server.SERVE_TEST_ELIGIBLE
+        server.SERVE_TEST_ELIGIBLE = True
+        self.addCleanup(setattr, server, "SERVE_TEST_ELIGIBLE", saved)
+        # Окружение восстановит patch.dict из setUp: отдельный patch в cleanup вернул бы его устаревший снимок.
+        os.environ["OPENCODE_ZEN_BRIDGE_TRANSPORT"] = "auto"
+
+    def _patched_attempts(
+        self, plan: list[Callable[[tuple[object, ...]], dict[str, object]]]
+    ) -> tuple[list[tuple[object, ...]], mock._patch[mock.MagicMock]]:  # pyright: ignore[reportPrivateUsage] — причина: тип patch-объекта mock приватен в typeshed
+        """Подмена `_serve_one_attempt` сценарием по очереди; возвращает журнал аргументов."""
+        calls: list[tuple[object, ...]] = []
+        queue_plan = list(plan)
+
+        def fake(*args: object, **_kw: object) -> dict[str, object]:
+            calls.append(args)
+            return queue_plan.pop(0)(args)
+
+        return calls, mock.patch.object(server, "_serve_one_attempt", side_effect=fake)
+
+    def test_slow_pause_streams_all_deltas_and_single_initial_status(self) -> None:
+        """RW-008/RW-016: пауза SSE 1.4 с не рвёт поток; STATUS_INITIAL ровно один, чанки целы."""
+        chunks, _elapsed = self.bridge.post_stream_timed("__slow__ жди")
+        self.assertFalse(any("error" in chunk for _at, chunk in chunks), chunks)
+        content = "".join(t for _at, t in _deltas(chunks, "content"))
+        self.assertEqual(content, "Ответ\n")
+        initial = [
+            at
+            for at, t in _deltas(chunks, "reasoning_content")
+            if server.STATUS_INITIAL.strip() in t
+        ]
+        self.assertEqual(len(initial), 1, chunks)
+        self.assertLessEqual(initial[0], 1.0)
+
+    def test_prompt_http_4xx_fail_closed_without_run_fallback(self) -> None:
+        """RW-003: 400/404/422 prompt в auto — fail_closed: без run и без инкремента serve_health."""
+        self._auto_mode()
+        health = self.bridge.httpd.resilience.serve_health
+        for code in (400, 404, 422):
+            with self.subTest(code=code):
+                before = health.failures
+                chunks, _elapsed = self.bridge.post_stream_timed(
+                    f"__prompt_status_{code}__ запрос"
+                )
+                joined = json.dumps(chunks, ensure_ascii=False)
+                self.assertIn("serve security failure", joined)
+                self.assertNotIn("Поздний ответ", joined)
+                self.assertEqual(health.failures, before)
+
+    def test_timeout_and_client_gone_never_count_as_success(self) -> None:
+        """RW-002: exit_reason timeout/client_gone — не успех ни в SSE, ни в JSON."""
+        health = self.bridge.httpd.resilience.serve_health
+        for reason in ("timeout", "client_gone"):
+            for streaming in (True, False):
+                with (
+                    self.subTest(reason=reason, stream=streaming),
+                    mock.patch.object(health, "record_success") as ok,
+                    mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                    mock.patch.object(
+                        server,
+                        "_serve_one_attempt",
+                        side_effect=lambda *_a, **_k: _fake_result(  # pyright: ignore[reportUnknownLambdaType] — причина: подмена попытки возвращает заготовленный результат
+                            exit_reason=reason, delivered=True
+                        ),
+                    ),
+                ):
+                    if streaming:
+                        chunks, _elapsed = self.bridge.post_stream_timed("x")
+                        finishes = [
+                            _as_obj_dict(
+                                cast(list[object], c.get("choices") or [{}])[0]
+                            ).get("finish_reason")
+                            for _at, c in chunks
+                            if c.get("choices")
+                        ]
+                        self.assertFalse(any(finishes), chunks)
+                        self.assertEqual(
+                            any("error" in c for _at, c in chunks), reason == "timeout"
+                        )
+                    elif reason == "timeout":
+                        status, _body = self.bridge.post_json("x")
+                        self.assertEqual(status, 502)
+                    else:
+                        with self.assertRaises(
+                            (
+                                TimeoutError,
+                                http.client.RemoteDisconnected,
+                                ConnectionError,
+                            )
+                        ):
+                            _ = self.bridge.post_json("x", timeout=2.5)
+                    ok.assert_not_called()
+
+    def test_retry_separator_once_and_delivery_barrier_is_monotonic(self) -> None:
+        """RW-009/RW-012: один разделитель на повтор; после reasoning нет тихого fallback на run."""
+        self._auto_mode()
+
+        def first(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 4)("мысль\n")
+            return _fake_result(
+                exit_reason="stall_timeout", delivered=True, reasonings=["мысль\n"]
+            )
+
+        def second(_args: tuple[object, ...]) -> dict[str, object]:
+            return _fake_result(exit_reason="first_event_timeout", delivered=False)
+
+        def third(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)("Готово")
+            return _fake_result(texts=["Готово"], terminal="succeeded")
+
+        calls, patcher = self._patched_attempts([first, second, third])
+        with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
+            chunks, _elapsed = self.bridge.post_stream_timed("x")
+        self.assertEqual(len(calls), 3)
+        joined = "".join(t for _at, t in _deltas(chunks, "content"))
+        self.assertEqual(joined, "Готово")
+        separators = [
+            t
+            for _at, t in _deltas(chunks, "reasoning_content")
+            if "Повтор попытки" in t
+        ]
+        self.assertEqual(len(separators), 2, chunks)
+
+    def test_json_tool_calls_are_deduplicated(self) -> None:
+        """RW-013: одинаковый (name, arguments) из native и из текста даёт один tool_call."""
+        call_text = '<tool_invoke>{"name": "bash", "arguments": {"command": "echo hi"}}</tool_invoke>'
+        native: dict[str, object] = {
+            "part": {
+                "tool": "bash",
+                "state": {"input": {"command": "echo hi"}, "status": "completed"},
+            }
+        }
+
+        def attempt(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)(call_text)
+            on_tool = cast(Callable[[dict[str, object]], None], args[6])
+            on_tool(native)
+            on_tool(native)
+            return _fake_result(terminal="succeeded")
+
+        _calls, patcher = self._patched_attempts([attempt])
+        with patcher:
+            status, body = self.bridge.post_json("x")
+        self.assertEqual(status, 200)
+        message = _as_obj_dict(
+            _as_obj_dict(cast(list[object], body["choices"])[0]).get("message")
+        )
+        self.assertEqual(len(cast(list[object], message["tool_calls"])), 1)
+
+    def test_json_run_fallback_respects_total_spawn_cap(self) -> None:
+        """RW-010: исчерпанный потолок спавнов serve не даёт четвёртый спавн run в JSON."""
+
+        def fake_serve(*args: object) -> bool:
+            attempts = cast("server._RequestAttempts", args[9])  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+            for _i in range(server.MAX_TOTAL_SPAWNS):
+                attempts.note_spawn()
+            return False
+
+        with (
+            mock.patch.object(
+                server.Handler,
+                "_serve_json_serve",
+                autospec=True,
+                side_effect=fake_serve,
+            ),
+            mock.patch.object(server, "Run") as run_cls,
+        ):
+            status, _body = self.bridge.post_json("x")
+        self.assertEqual(status, 502)
+        run_cls.assert_not_called()
+
+    def test_proxy_pool_advances_once_per_serve_attempt(self) -> None:
+        """RW-019: запрос с одной попыткой serve сдвигает пул прокси один раз."""
+        with (
+            mock.patch.object(
+                server, "_next_standalone_proxy", return_value=None
+            ) as rotate,
+            mock.patch.object(
+                server, "_spawn_serve", side_effect=server.ServeUnavailable("stop")
+            ),
+        ):
+            _chunks, _elapsed = self.bridge.post_stream_timed("x")
+        self.assertEqual(rotate.call_count, 1)
+
+    def test_tool_choice_preserved_in_step_recovery_prompt(self) -> None:
+        """RW-007: tool_choice попадает в промпт step-interruption recovery serve."""
+        for choice, phrase in (
+            ("required", "MUST call at least one tool"),
+            (
+                {"type": "function", "function": {"name": "bash"}},
+                'MUST call the tool "bash"',
+            ),
+        ):
+            with self.subTest(choice=choice):
+
+                def preamble(args: tuple[object, ...]) -> dict[str, object]:
+                    _callback(args, 5)("Сейчас проверю.")
+                    return _fake_result(texts=["Сейчас проверю."], terminal="succeeded")
+
+                def done(args: tuple[object, ...]) -> dict[str, object]:
+                    call = '<tool_invoke>{"name": "bash", "arguments": {"command": "ls"}}</tool_invoke>'
+                    _callback(args, 5)(call)
+                    return _fake_result(texts=[call], terminal="succeeded")
+
+                calls, patcher = self._patched_attempts([preamble, done])
+                with patcher, mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0):
+                    _chunks, _elapsed = self.bridge.post_stream_timed(
+                        "x", tool_choice=choice
+                    )
+                self.assertEqual(len(calls), 2)
+                self.assertIn(phrase, str(calls[1][1]))
+
+    def test_fu003_usage_once_across_distinct_retry_branches(self) -> None:
+        """FU-003: timeout, prompt-status и успешная попытка учитываются по одному разу."""
+
+        def first(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 4)("мысль\n")
+            return _fake_result(
+                delivered=True,
+                reasonings=["мысль\n"],
+                exit_reason="stall_timeout",
+                usage={"output": 3},
+            )
+
+        def second(_args: tuple[object, ...]) -> dict[str, object]:
+            return _fake_result(delivered=True, prompt_status=429, usage={"output": 5})
+
+        def third(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)("Ответ.")
+            return _fake_result(
+                texts=["Ответ."], terminal="succeeded", usage={"output": 7}
+            )
+
+        calls, patcher = self._patched_attempts([first, second, third])
+        with (
+            patcher,
+            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+            mock.patch.object(server, "STEP_RECOVERY_ENABLED", False),
+        ):
+            chunks, _ = self.bridge.post_stream_timed("x")
+        self.assertEqual(len(calls), 3)
+        usages = [
+            _as_obj_dict(chunk["usage"]) for _, chunk in chunks if "usage" in chunk
+        ]
+        self.assertTrue(usages, chunks)
+        self.assertEqual(usages[-1].get("completion_tokens"), 15)
+
+    def test_fu010_thinking_off_omits_retry_separator(self) -> None:
+        """FU-010: синтетический разделитель отключён вместе с thinking."""
+
+        def first(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)("начало ")
+            return _fake_result(
+                delivered=True, texts=["начало "], exit_reason="stall_timeout"
+            )
+
+        def second(args: tuple[object, ...]) -> dict[str, object]:
+            _callback(args, 5)("конец")
+            return _fake_result(texts=["конец"], terminal="succeeded")
+
+        _calls, patcher = self._patched_attempts([first, second])
+        with (
+            patcher,
+            mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+            mock.patch.object(server, "STEP_RECOVERY_ENABLED", False),
+        ):
+            chunks, _ = self.bridge.post_stream_timed("x", effort="off")
+        self.assertNotIn("Повтор попытки", json.dumps(chunks, ensure_ascii=False))
+
+    def test_rw001_delivery_survives_unavailable_or_limiter(self) -> None:
+        """RW-001: частичный ответ запрещает run при следующем отказе serve или лимитера."""
+        self._auto_mode()
+        unavailable = server.ServeUnavailable
+        for stream in (True, False):
+            for limited in (False, True):
+                with self.subTest(stream=stream, limited=limited):
+
+                    def first(args: tuple[object, ...]) -> dict[str, object]:
+                        _callback(args, 4)("частичная мысль\n")
+                        return _fake_result(
+                            exit_reason="stall_timeout",
+                            delivered=True,
+                            reasonings=["частичная мысль\n"],
+                        )
+
+                    def second(_args: tuple[object, ...]) -> dict[str, object]:
+                        raise unavailable("нет serve")
+
+                    calls, patcher = self._patched_attempts([first, second])
+                    health = self.bridge.httpd.resilience.serve_health
+                    limiter = self.bridge.httpd.resilience.spawn_limiter
+                    with (
+                        patcher,
+                        mock.patch.object(server, "FAIL_RETRY_BACKOFF_S", 0.0),
+                        mock.patch.object(health, "record_success") as success,
+                        mock.patch.object(server.Run, "execute") as legacy,
+                        mock.patch.object(server, "_spawn_with_stdin") as spawn,
+                        mock.patch.object(
+                            limiter,
+                            "acquire",
+                            side_effect=[True, False] if limited else [True, True],
+                        ),
+                    ):
+                        if stream:
+                            chunks, _ = self.bridge.post_stream_timed("x")
+                            output = json.dumps(chunks, ensure_ascii=False)
+                            self.assertLessEqual(output.count("Повтор попытки"), 1)
+                            self.assertIn("error", output)
+                        else:
+                            status, body = self.bridge.post_json("x", with_tools=False)
+                            self.assertEqual(status, 502, body)
+                        legacy.assert_not_called()
+                        spawn.assert_not_called()
+                        success.assert_not_called()
+                    self.assertEqual(len(calls), 1 if limited else 2)
+
+    def test_rw007_split_interrupted_marker_at_every_boundary(self) -> None:
+        """RW-007: маркер удаляется при любом разрезе, включая прежнюю границу буфера."""
+        marker = "I was interrupted right before making tool calls."
+        for split in (1, 19, len(marker) - 1):
+            with self.subTest(split=split):
+
+                def first(args: tuple[object, ...]) -> dict[str, object]:
+                    chunks = [
+                        "начало " + marker[:split],
+                        marker[split:] + " конец" + "x" * 100,
+                    ]
+                    for chunk in chunks:
+                        _callback(args, 5)(chunk)
+                    return _fake_result(texts=chunks, terminal="succeeded")
+
+                _calls, patcher = self._patched_attempts([first])
+                with patcher, mock.patch.object(server, "STEP_RECOVERY_ENABLED", False):
+                    chunks, _ = self.bridge.post_stream_timed("x")
+                text = "".join(t for _, t in _deltas(chunks, "content"))
+                self.assertEqual(text, "начало  конец" + "x" * 100)
+
+    def test_rw008_provider_secrets_hidden_in_sse_json_and_log(self) -> None:
+        """RW-008: ошибка провайдера не выдаёт секреты через SSE, JSON и лог."""
+        secret = "sk-" + "a" * 32
+        message = (
+            secret
+            + " Bearer hidden-token OPENCODE_SERVER_PASSWORD=hidden-pass http://u:proxy-pass@localhost:1080"
+        )
+        for stream in (True, False):
+
+            def failure(_args: tuple[object, ...]) -> dict[str, object]:
+                return _fake_result(error={"message": message}, terminal="failed")
+
+            _calls, patcher = self._patched_attempts([failure])
+            with patcher:
+                if stream:
+                    chunks, _ = self.bridge.post_stream_timed("x")
+                    output = json.dumps(chunks)
+                else:
+                    _status, body = self.bridge.post_json("x", with_tools=False)
+                    output = json.dumps(body)
+            output += server.LOG_PATH.read_text()
+            for sentinel in (secret, "hidden-token", "hidden-pass", "proxy-pass"):
+                self.assertNotIn(sentinel, output)
+
+    def test_rw006_invalid_utf8_falls_back_and_recovers(self) -> None:
+        """RW-006: повреждённый UTF-8 безопасен, восстановление JSON включает serve."""
+        self._auto_mode()
+        _ = self.cfg.write_bytes(b"\xff\xfe")
+        self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: проверяется выбор транспорта после повреждения файла
+        _ = self.cfg.write_text('{"REALTIME_SERVE_ENABLED": true}', encoding="utf-8")
+        self.assertEqual(server._select_transport(), "serve")  # pyright: ignore[reportPrivateUsage] — причина: проверяется восстановление транспорта без рестарта
+
+    def test_rw003_mkdtemp_failure_is_serve_unavailable(self) -> None:
+        """RW-003: ENOSPC при выделении каталога не оставляет портов и не уходит как client_gone."""
+        ports = server._ACTIVE_SERVE_PORTS.copy()  # pyright: ignore[reportPrivateUsage] — причина: сверяются ресурсы после отказа до запуска
+        attempt = server._serve_one_attempt  # pyright: ignore[reportPrivateUsage] — причина: оракул инъецирует отказ до запуска попытки
+        with mock.patch.object(
+            tempfile, "mkdtemp", side_effect=OSError(28, "нет места")
+        ):
+            with self.assertRaises(server.ServeUnavailable):
+                _ = attempt(
+                    MODEL,
+                    "x",
+                    "high",
+                    self.tmp,
+                    lambda _: None,
+                    lambda _: None,
+                    lambda _: None,
+                    time.monotonic(),
+                )
+        self.assertEqual(server._ACTIVE_SERVE_PORTS, ports)  # pyright: ignore[reportPrivateUsage] — причина: инвариант отсутствия занятых портов после отказа
+
+    def test_fu011_cancelled_never_counts_as_success(self) -> None:
+        """FU-011: отменённая form.created не считается успехом в обоих протоколах."""
+        for stream in (True, False):
+
+            def cancelled(_args: tuple[object, ...]) -> dict[str, object]:
+                return _fake_result(terminal="cancelled")
+
+            _calls, patcher = self._patched_attempts([cancelled])
+            with (
+                patcher,
+                mock.patch.object(
+                    self.bridge.httpd.resilience.serve_health, "record_success"
+                ) as success,
+            ):
+                if stream:
+                    chunks, _ = self.bridge.post_stream_timed("x")
+                    self.assertIn("cancelled", json.dumps(chunks))
+                else:
+                    status, body = self.bridge.post_json("x", with_tools=False)
+                    self.assertEqual(status, 502, body)
+                success.assert_not_called()
+
+
+class TestReworkUnits(unittest.TestCase):
+    """Группа C: детерминированные оракулы RW-001..RW-032 без живого FakeServe."""
+
+    def test_surrogate_pair_and_broken_json(self) -> None:
+        """RW-005: суррогатная пара декодируется, битый JSON serve — ServeProtocolError."""
+        parsed = server._loads_object('{"emoji": "\ud83d\ude00"}')  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        self.assertEqual(parsed, {"emoji": "\U0001f600"})
+        self.assertEqual(
+            json.dumps(parsed, ensure_ascii=False).encode("utf-8").decode("utf-8"),
+            '{"emoji": "\U0001f600"}',
+        )
+        self.assertIsNone(server._loads_object("{broken"))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        with self.assertRaises(server.ServeProtocolError):
+            _ = server._loads_serve_object("{broken")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+
+    def test_service_events_ignored_and_foreign_session(self) -> None:
+        """RW-029/RW-031: служебные события — None, sessionID сохраняется в payload."""
+        self.assertIsNone(
+            server._map_serve_event({"type": "integration.updated", "data": {}})  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        )
+        self.assertIsNone(
+            server._map_serve_event({"type": "server.heartbeat", "data": {}})  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        )
+        mapped = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+            {"type": "session.text.delta", "data": {"sessionID": "ses_a", "delta": " "}}
+        )
+        self.assertIsNotNone(mapped)
+        assert mapped is not None
+        self.assertEqual(mapped[1].get("sessionID"), "ses_a")
+        self.assertEqual(mapped[1].get("content"), " ")
+
+    def test_whitespace_delta_preserved_in_map(self) -> None:
+        """RW-007: пробельная дельта не отбрасывается маппером."""
+        mapped = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+            {
+                "type": "session.reasoning.delta",
+                "data": {"sessionID": "s1", "delta": "\n\n"},
+            }
+        )
+        self.assertIsNotNone(mapped)
+        assert mapped is not None
+        self.assertEqual(mapped[1].get("reasoning_content"), "\n\n")
+
+    def test_half_open_to_closed_via_attempt_done(self) -> None:
+        """RW-014: успешный serve через attempt_done переводит breaker в CLOSED."""
+        res = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        res.breaker = server._UpstreamBreaker(fail_threshold=1, reset_timeout_s=0.01)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        res.breaker.record_failure()
+        self.assertEqual(res.breaker.state, "OPEN")
+        time.sleep(0.03)
+        self.assertTrue(res.breaker.allow())
+        self.assertEqual(res.breaker.state, "HALF_OPEN")
+        attempts = server._RequestAttempts(res, time.monotonic() + 60.0)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        attempts.attempt_done(False, True)
+        self.assertEqual(res.breaker.state, "CLOSED")
+
+    def test_transport_matrix(self) -> None:
+        """RW-025: TRANSPORT=run, override 0, disable-файл и опечатка дают run."""
+        with mock.patch.dict(
+            os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}, clear=False
+        ):
+            self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        with mock.patch.dict(
+            os.environ,
+            {
+                "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
+                "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": "0",
+            },
+            clear=False,
+        ):
+            self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        with mock.patch.dict(
+            os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "serv"}, clear=False
+        ):
+            self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+
+    def test_disable_file_overrides_forced_serve(self) -> None:
+        """FU-013: файл отключения важнее принудительного выбора serve."""
+        with tempfile.TemporaryDirectory() as name:
+            disable = Path(name) / "disable-serve"
+            _ = disable.write_text("1")
+            with mock.patch.dict(
+                os.environ,
+                {
+                    "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
+                    "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE": str(disable),
+                    "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": "1",
+                },
+            ):
+                self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: проверяется приоритет аварийного файла отключения
+
+    def test_fake_rt_mode_preset_preserved(self) -> None:
+        """RW-027: предустановленный FAKE_RT_MODE сохраняется после patch.dict."""
+        patcher = mock.patch.dict(
+            os.environ, {"FAKE_RT_MODE": "preset-value"}, clear=False
+        )
+        _ = patcher.start()  # pyright: ignore[reportAny] — причина: динамический результат запуска patch.dict не используется
+        try:
+            inner = mock.patch.dict(os.environ, {"FAKE_RT_MODE": "fast"}, clear=False)
+            _ = inner.start()  # pyright: ignore[reportAny] — причина: mock.patch.start возвращает динамический объект подмены, результат не используется
+            _ = inner.stop()  # pyright: ignore[reportAny] — причина: mock.patch.stop возвращает динамический результат восстановления, он не используется
+            self.assertEqual(os.environ.get("FAKE_RT_MODE"), "preset-value")
+        finally:
+            _ = patcher.stop()  # pyright: ignore[reportAny] — причина: динамический результат восстановления patch.dict не используется
+
+    def test_spawn_cap_and_proxy_rotation_helpers(self) -> None:
+        """RW-001/RW-013: can_spawn ограничен MAX_TOTAL_SPAWNS, пул прокси ротируется."""
+        res = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        attempts = server._RequestAttempts(res, time.monotonic() + 60.0)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        for _i in range(server.MAX_TOTAL_SPAWNS):
+            self.assertTrue(attempts.can_spawn())
+            attempts.note_spawn()
+        self.assertFalse(attempts.can_spawn())
+        self.assertTrue(callable(server._next_standalone_proxy))  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+
+    def test_elf_magic_and_tool_status(self) -> None:
+        """FU-001/FU-002: 4 случайных байта не ELF, статус tool из типа события."""
+        state = server._ServeToolState()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
+        state.feed({"id": "c1", "name": "bash", "text": '{"command": "x"}'})
+        done = state.complete("c1", "session.tool.called")
+        self.assertIsNotNone(done)
+        assert done is not None
+        part_obj: object = done[1].get("part")
+        self.assertIsInstance(part_obj, dict)
+        self.assertEqual(
+            _as_obj_dict(_as_obj_dict(part_obj).get("state")).get("status"), "completed"
+        )
+        with tempfile.TemporaryDirectory() as name:
+            binary = Path(name) / "opencode"
+            with mock.patch.object(server, "SERVE_TEST_ELIGIBLE", False):
+                for magic, expected in (
+                    (b"xxxx", False),
+                    (b"#!/b", False),
+                    (b"\x7fELF", True),
+                    (b"\xcf\xfa\xed\xfe", True),
+                ):
+                    _ = binary.write_bytes(magic)
+                    native = server._is_native_opencode_bin  # pyright: ignore[reportPrivateUsage] — причина: проверяется сигнатура отдельно от тестового допуска
+                    self.assertEqual(native(str(binary)), expected)
+
+    def test_fu001_http_checks_deadline_and_cancellation_before_connect(self) -> None:
+        """FU-001: просроченный бюджет и ушедший клиент запрещают даже соединение HTTP."""
+        call = server._serve_http  # pyright: ignore[reportPrivateUsage] — причина: проверяется граница фазы управляющего HTTP-вызова
+        with self.assertRaises(TimeoutError):
+            _ = call(0, "", "GET", "/", deadline=time.monotonic() - 1)
+        with self.assertRaises(BrokenPipeError):
+            _ = call(0, "", "GET", "/", is_client_gone=lambda: True)
+
+    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
+        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
+        tools: list[dict[str, object]] = [
+            {
+                "type": "function",
+                "function": {
+                    "name": name,
+                    "parameters": {
+                        "type": "object",
+                        "properties": props,
+                        "required": list(props),
+                    },
+                },
+            }
+            for name, props in (
+                (
+                    "bash",
+                    {"command": {"type": "string"}, "description": {"type": "string"}},
+                ),
+                ("read", {"file_path": {"type": "string"}}),
+                (
+                    "edit",
+                    {
+                        "file_path": {"type": "string"},
+                        "old_string": {"type": "string"},
+                        "new_string": {"type": "string"},
+                    },
+                ),
+            )
+        ]
+        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
+        canonical = cast(
+            Callable[
+                [object, object, list[dict[str, object]]], list[dict[str, object]]
+            ],
+            mapper,
+        )
+        for name, args in (
+            ("bash", {"command": "pwd"}),
+            ("read", {"filePath": "/tmp/a"}),
+            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
+            ("list", {"path": "/tmp"}),
+            (
+                "multiedit",
+                {
+                    "filePath": "/tmp/a",
+                    "edits": [
+                        {"oldString": "a", "newString": "b"},
+                        {"oldString": "c", "newString": "d"},
+                    ],
+                },
+            ),
+        ):
+            with self.subTest(name=name):
+                expected = canonical(name, args, tools)
+                adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
+                actual = adapter(
+                    {"part": {"tool": name, "state": {"input": args}}}, tools
+                )
+                self.assertTrue(expected, name)
+                self.assertEqual(
+                    json.dumps(actual, sort_keys=True),
+                    json.dumps(expected, sort_keys=True),
+                )
+
+    def test_rw005_stop_group_after_leader_exit(self) -> None:
+        """RW-005: завершившийся лидер не мешает убить живого потомка его группы."""
+        with tempfile.TemporaryDirectory() as name:
+            pidfile = Path(name) / "child.pid"
+            code = (
+                "import os,signal,time; from pathlib import Path; "
+                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
+                f"Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(30)"
+            )
+            parent = "import subprocess,sys,time; from pathlib import Path; subprocess.Popen([sys.executable,'-c',sys.argv[1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); p=Path(sys.argv[2]); deadline=time.monotonic()+3; "
+            parent += (
+                "\nwhile not p.exists() and time.monotonic()<deadline: time.sleep(0.01)"
+            )
+            proc = subprocess.Popen(
+                [sys.executable, "-c", parent, code, str(pidfile)],
+                text=True,
+                start_new_session=True,
+            )
+            try:
+                _ = proc.wait(timeout=5)
+                self.assertTrue(pidfile.exists())
+                child = int(pidfile.read_text())
+                server._stop_proc(proc)  # pyright: ignore[reportPrivateUsage] — причина: проверяется остановка осиротевшего потомка завершившегося лидера
+                deadline = time.monotonic() + 3
+                while time.monotonic() < deadline:
+                    try:
+                        os.kill(child, 0)
+                    except ProcessLookupError:
+                        break
+                    time.sleep(0.02)
+                else:
+                    self.fail("потомок пережил остановку группы")
+            finally:
+                try:
+                    os.killpg(proc.pid, signal.SIGKILL)
+                except ProcessLookupError:
+                    pass
+                _ = proc.wait(timeout=5)
+
+    def test_rw008_error_payload_masks_message_and_detail(self) -> None:
+        """RW-008: общий конструктор ошибки очищает оба поля до сериализации."""
+        secret = "sk-" + "b" * 32
+        payload = server._error_payload(secret, "Bearer hidden-detail")  # pyright: ignore[reportPrivateUsage] — причина: проверяется последняя граница очистки клиентской ошибки
+        encoded = json.dumps(payload)
+        self.assertNotIn(secret, encoded)
+        self.assertNotIn("hidden-detail", encoded)
+
+
+def _fake_result(**over: object) -> dict[str, object]:
+    """Результат попытки serve для подмены `_serve_one_attempt`."""
+    base: dict[str, object] = {
+        "reasonings": [],
+        "texts": [],
+        "native_calls": [],
+        "usage": {},
+        "error": None,
+        "exit_reason": "",
+        "delivered": False,
+        "terminal": "",
+        "first_event_at": None,
+        "first_token_at": None,
+        "step_closed": False,
+        "first_event_ms": None,
+        "ttft_ms": None,
+        "prompt_status": None,
+        "transient_error": False,
+    }
+    base.update(over)
+    return base
+
+
+def _callback(args: tuple[object, ...], index: int) -> Callable[[str], None]:
+    """Колбэк `_serve_one_attempt` по позиции (4 reasoning, 5 text)."""
+    return cast(Callable[[str], None], args[index])
+
+
+class _AttemptCase(unittest.TestCase):
+    """База: FakeServe в tmp, пустой HOME и изолированный LEASE_DIR для прямых вызовов попытки."""
+
+    tmpdir: tempfile.TemporaryDirectory[str] = cast(
+        "tempfile.TemporaryDirectory[str]", None
+    )  # pyright: ignore[reportInvalidCast] — причина: значение задаётся в setUp до первого обращения
+    tmp: Path = Path()
+    saved_bin: str = ""
+    saved_lease: Path = Path()
+    env: object = None
+
+    @override
+    def setUp(self) -> None:
+        self.tmpdir = tempfile.TemporaryDirectory()
+        self.tmp = Path(self.tmpdir.name)
+        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
+        self.saved_bin = server.OPENCODE_BIN
+        self.saved_lease = server.LEASE_DIR
+        server.OPENCODE_BIN = str(fake)
+        server.LEASE_DIR = self.tmp / "leases"
+        (self.tmp / "home").mkdir()
+        self.env = mock.patch.dict(
+            os.environ, {"HOME": str(self.tmp / "home")}, clear=False
+        )
+        _ = cast(_Patcher, self.env).start()
+
+    @override
+    def tearDown(self) -> None:
+        _ = cast(_Patcher, self.env).stop()
+        server.OPENCODE_BIN = self.saved_bin
+        server.LEASE_DIR = self.saved_lease
+        self.tmpdir.cleanup()
+
+    def attempt(
+        self,
+        prompt: str,
+        *,
+        reasoning: list[tuple[float, str]] | None = None,
+        on_ready: Callable[[], None] | None = None,
+        on_token: Callable[[], None] | None = None,
+        emulate_tools: bool = False,
+    ) -> Mapping[str, object]:
+        """Одна реальная попытка serve против FakeServe (метки времени — монотонные)."""
+        marks = reasoning if reasoning is not None else []
+        t0 = time.monotonic()
+
+        def on_reasoning(text: str) -> None:
+            marks.append((time.monotonic(), text))
+            if on_token is not None:
+                on_token()
+
+        def ignore(_text: str) -> None:
+            return None
+
+        def ignore_tool(_payload: dict[str, object]) -> None:
+            return None
+
+        return server._serve_one_attempt(  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+            MODEL,
+            prompt,
+            "high",
+            self.tmp,
+            on_reasoning,
+            ignore,
+            ignore_tool,
+            t0,
+            on_startup_ready=on_ready,
+            emulate_tools=emulate_tools,
+        )
+
+
+class TestServeAttemptOracles(_AttemptCase):
+    """Поведенческие оракулы `_serve_one_attempt` на FakeServe (RW-003/008/011/014/019)."""
+
+    def test_never_event_gives_first_event_timeout(self) -> None:
+        """REQ-006: SSE без событий выполнения -> first_event_timeout."""
+        with mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 0.8):
+            started = time.monotonic()
+            result = self.attempt("__never_event__ x")
+        self.assertEqual(result["exit_reason"], "first_event_timeout")
+        self.assertLess(time.monotonic() - started, 8.0)
+
+    def test_silent_model_gives_first_token_timeout(self) -> None:
+        """REQ-007: события есть, токенов нет -> first_token_timeout."""
+        with mock.patch.object(server, "FIRST_TOKEN_TIMEOUT_S", 0.8):
+            result = self.attempt("__silent__ x")
+        self.assertEqual(result["exit_reason"], "first_token_timeout")
+        self.assertIs(result["delivered"], True)
+
+    def test_stall_after_first_token(self) -> None:
+        """REQ-007: пауза после первого токена -> stall_timeout."""
+        reasoning: list[tuple[float, str]] = []
+        with mock.patch.object(server, "STALL_TIMEOUT_S", 0.8):
+            result = self.attempt("__stall__ x", reasoning=reasoning)
+        self.assertEqual(result["exit_reason"], "stall_timeout")
+        self.assertEqual([t for _at, t in reasoning], ["Первая мысль"])
+
+    def test_sse_pause_over_half_second_keeps_stream_alive(self) -> None:
+        """RW-008: пауза SSE 1.4 с не закрывает читатель и не даёт invalid_serve_event."""
+        reasoning: list[tuple[float, str]] = []
+        result = self.attempt("__slow__ x", reasoning=reasoning)
+        self.assertEqual(result["exit_reason"], "")
+        self.assertEqual(result["terminal"], "succeeded")
+        self.assertEqual(
+            "".join(t for _at, t in reasoning), "Мысль0 Мысль1 Мысль2 Мысль3 Мысль4 "
+        )
+
+    def test_startup_gate_released_before_generation_ends(self) -> None:
+        """RW-014: замок старта отпускается по готовности serve, а не по концу генерации."""
+        gate = server._StartupGate()  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+        gate.acquire()
+        self.assertTrue(server._STARTUP_LOCK.locked())  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+        locked_during_tokens: list[bool] = []
+        ready_calls: list[float] = []
+
+        def on_ready() -> None:
+            ready_calls.append(time.monotonic())
+            gate.release()
+
+        def on_token() -> None:
+            locked_during_tokens.append(server._STARTUP_LOCK.locked())  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+
+        reasoning: list[tuple[float, str]] = []
+        try:
+            result = self.attempt(
+                "__slow__ x", reasoning=reasoning, on_ready=on_ready, on_token=on_token
+            )
+        finally:
+            gate.release()
+        self.assertEqual(result["terminal"], "succeeded")
+        self.assertEqual(len(ready_calls), 1)
+        self.assertLess(ready_calls[0], reasoning[0][0])
+        self.assertEqual(len(locked_during_tokens), 5)
+        self.assertFalse(any(locked_during_tokens))
+
+    def test_prompt_http_4xx_fails_closed_fast(self) -> None:
+        """RW-003: 400/404/422 prompt -> fail_closed быстрее FIRST_EVENT_TIMEOUT при пустом SSE."""
+        for code in (400, 404, 422):
+            with (
+                self.subTest(code=code),
+                mock.patch.object(server, "FIRST_EVENT_TIMEOUT_S", 20.0),
+            ):
+                started = time.monotonic()
+                with self.assertRaises(server.ServeSecurityError):
+                    _ = self.attempt(f"__prompt_status_{code}__ x")
+                self.assertLess(time.monotonic() - started, 6.0)
+
+    def test_text_tool_call_closes_step_on_step_finish(self) -> None:
+        """RW-011: текстовый вызов инструмента закрывает шаг tool_calls при эмуляции."""
+        emulated = self.attempt("__tool_text__ x", emulate_tools=True)
+        self.assertEqual(emulated["terminal"], "tool_calls")
+        plain = self.attempt("__tool_text__ x", emulate_tools=False)
+        self.assertEqual(plain["terminal"], "succeeded")
+
+    def test_attempt_rotates_proxy_pool_once(self) -> None:
+        """RW-019: одна попытка serve сдвигает пул прокси ровно на один шаг."""
+        with (
+            mock.patch.object(
+                server, "_next_standalone_proxy", return_value=None
+            ) as rotate,
+            mock.patch.object(
+                server, "_spawn_serve", side_effect=server.ServeUnavailable("stop")
+            ),
+            self.assertRaises(server.ServeUnavailable),
+        ):
+            _ = self.attempt("x")
+        self.assertEqual(rotate.call_count, 1)
+
+
+class TestSpawnAndLeaseOracles(_AttemptCase):
+    """RW-004/RW-006/RW-015: атомарность старта, client_gone и бюджеты cleanup."""
+
+    def _fd_count(self) -> int:
+        return len(os.listdir("/dev/fd"))
+
+    def test_spawn_failures_leave_no_leftovers(self) -> None:
+        """RW-004: сбой Popen/pipe не оставляет FD, порт и каталог состояния."""
+        for name, target in (("popen", "Popen"), ("pipe", "pipe")):
+            with self.subTest(failure=name):
+                env = server._serve_env(MODEL)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+                state_dir = Path(env["XDG_STATE_HOME"])
+                self.assertTrue(state_dir.is_dir())
+                ports_before = set(server._ACTIVE_SERVE_PORTS)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+                fds_before = self._fd_count()
+                owner = subprocess if name == "popen" else os
+                with (
+                    mock.patch.object(owner, target, side_effect=OSError(24, "boom")),
+                    self.assertRaises(server.ServeUnavailable),
+                ):
+                    _ = server._spawn_serve("att_fail_" + name, env)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+                self.assertFalse(state_dir.exists())
+                self.assertEqual(set(server._ACTIVE_SERVE_PORTS), ports_before)  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+                self.assertEqual(self._fd_count(), fds_before)
+
+    def test_lease_cleanup_confirms_sigkill_in_separate_window(self) -> None:
+        """RW-015: группа, игнорирующая SIGTERM, добивается SIGKILL; lease удаляется после смерти."""
+        script = (
+            "import signal,time;signal.signal(signal.SIGTERM, signal.SIG_IGN);"
+            "print('ready', flush=True);time.sleep(60)"
+        )
+        child: subprocess.Popen[str] = subprocess.Popen(
+            [sys.executable, "-I", "-c", script],
+            stdout=subprocess.PIPE,
+            stderr=subprocess.PIPE,
+            start_new_session=True,
+            text=True,
+        )
+        assert child.stdout is not None
+        ready_line = cast(str, child.stdout.readline())
+        self.assertEqual(ready_line.strip(), "ready")
+        lease_dir = self.tmp / "lease-cleanup"
+        lease_dir.mkdir()
+        lease_file = lease_dir / "lease-attC.json"
+        _ = lease_file.write_text("{}", "utf-8")
+        _read_fd, write_fd = os.pipe()
+        os.close(_read_fd)
+        lease = server._ServeLease(  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
+            child, child.pid, child.pid, write_fd, lease_dir, "attC", ""
+        )
+        started = time.monotonic()
+        lease.cleanup()
+        elapsed = time.monotonic() - started
+        with self.assertRaises(ProcessLookupError):
+            os.killpg(child.pid, 0)
+        self.assertFalse(lease_file.exists())
+        self.assertGreaterEqual(elapsed, 3.9)
+        # SIGKILL уходит ровно после 4.0 с окна SIGTERM, смерть группы подтверждается во втором окне.
+        self.assertLessEqual(elapsed, 4.9)
+
+    def test_client_gone_check_detects_reset_and_close(self) -> None:
+        """RW-006: ECONNRESET, FIN и закрытый rfile — клиент ушёл; живой сокет — нет."""
+        listener = socket.socket()
+        listener.bind(("127.0.0.1", 0))
+        listener.listen(2)
+        addr = cast(tuple[str, int], listener.getsockname())
+        try:
+            for mode in ("alive", "reset", "fin", "closed"):
+                with self.subTest(mode=mode):
+                    client = socket.create_connection(addr)
+                    conn = listener.accept()[0]
+                    handler = server.Handler.__new__(server.Handler)
+                    handler.rfile = conn.makefile("rb")
+                    try:
+                        if mode == "reset":
+                            client.setsockopt(
+                                socket.SOL_SOCKET,
+                                socket.SO_LINGER,
+                                struct.pack("ii", 1, 0),
+                            )
+                            client.close()
+                            time.sleep(0.1)
+                        elif mode == "fin":
+                            client.close()
+                            time.sleep(0.1)
+                        elif mode == "closed":
+                            handler.rfile.close()
+                        self.assertEqual(
+                            handler._client_gone_check(),  # pyright: ignore[reportPrivateUsage] — причина: оракул проверяет приватный детектор ухода клиента
+                            mode != "alive",
+                        )
+                    finally:
+                        client.close()
+                        conn.close()
+        finally:
+            listener.close()
+
+
+FAKE_HELPER_SERVE = """#!/bin/sh
+trap '' TERM
+sleep 120 &
+echo $! > "$GRANDCHILD_FILE"
+exit 0
+"""
+
+
+class TestHelperProcess(unittest.TestCase):
+    """RW-001/RW-005: процесс --serve-helper (errno до ветки helper, добивание группы)."""
+
+    def _helper_cmd(self, tmp: Path, bin_path: str) -> list[str]:
+        return [
+            sys.executable,
+            "-I",
+            str(Path(server.__file__).resolve()),
+            "--serve-helper",
+            "attemptH",
+            "43211",
+            bin_path,
+            str(tmp / "leases"),
+            str(os.getpid()),
+            "Mon Jan  1 00:00:00 2024",
+        ]
+
+    def test_errno_imported_before_helper_branch(self) -> None:
+        """RW-001: errno связан до ветки --serve-helper."""
+        tree = ast.parse(Path(server.__file__).read_text("utf-8"))
+        branch = next(
+            n
+            for n in tree.body
+            if isinstance(n, ast.If)
+            and ast.unparse(n.test).endswith("['--serve-helper']")
+        )
+        early = {
+            a.name
+            for n in tree.body[: tree.body.index(branch)]
+            if isinstance(n, ast.Import)
+            for a in n.names
+        }
+        self.assertIn("errno", early)
+
+    def test_helper_survives_bad_stdin_without_name_error(self) -> None:
+        """RW-001: EBADF на select lifeline обрабатывается без NameError, lease снимается."""
+        with tempfile.TemporaryDirectory() as raw:
+            tmp = Path(raw)
+            argv = " ".join(f"'{a}'" for a in self._helper_cmd(tmp, "/bin/true"))
+            proc = subprocess.run(
+                ["/bin/sh", "-c", f"exec {argv} <&-"],
+                capture_output=True,
+                text=True,
+                timeout=20,
+                start_new_session=True,
+            )
+            self.assertNotIn("NameError", proc.stderr)
+            self.assertEqual(proc.returncode, 0, proc.stderr)
+            self.assertEqual(list((tmp / "leases").glob("lease-*.json")), [])
+
+    def test_helper_kills_surviving_group_and_removes_lease_last(self) -> None:
+        """RW-005: serve вышел, внук игнорирует SIGTERM -> SIGKILL группе, lease удалён после смерти."""
+        with tempfile.TemporaryDirectory() as raw:
+            tmp = Path(raw)
+            fake = _write_exe(tmp, "opencode-fake", FAKE_HELPER_SERVE)
+            gc_file = tmp / "grandchild.pid"
+            env = dict(os.environ)
+            env["GRANDCHILD_FILE"] = str(gc_file)
+            proc = subprocess.Popen(
+                self._helper_cmd(tmp, str(fake)),
+                stdin=subprocess.PIPE,
+                stdout=subprocess.PIPE,
+                stderr=subprocess.PIPE,
+                env=env,
+                text=True,
+                start_new_session=True,
+            )
+            try:
+                # lifeline (stdin) остаётся открытым: helper завершается сам, когда serve вышел.
+                _ = proc.wait(timeout=30)
+            finally:
+                if proc.poll() is None:
+                    proc.kill()
+                if proc.stdin is not None:
+                    proc.stdin.close()
+                for stream in (proc.stdout, proc.stderr):
+                    if stream is not None:
+                        stream.close()
+            self.assertEqual(proc.returncode, 0)
+            grandchild = int(gc_file.read_text("utf-8").strip())
+            deadline = time.monotonic() + 3.0
+            alive = True
+            while alive and time.monotonic() < deadline:
+                try:
+                    os.kill(grandchild, 0)
+                    time.sleep(0.05)
+                except ProcessLookupError:
+                    alive = False
+            if alive:
+                os.kill(grandchild, signal.SIGKILL)
+            self.assertFalse(alive, "внук группы пережил helper")
+            self.assertEqual(list((tmp / "leases").glob("lease-*.json")), [])
+
+
+if __name__ == "__main__":
+    unittest.main()  # pyright: ignore[reportUnusedCallResult] — причина: результат вызова в тесте не используется
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief.json sha256=54fd932f91ca50e44ae245a700d674eb40c11a1de2d0900c07d68a9bdb5f32d5
{
  "schema_version": "2.0",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "teamlead_cycle": 3,
  "panel_slug": "panel/council/r29",
  "panel_verdict": "NEEDS_WORK",
  "summarizer_slot": "claude-sonnet-5-5",
  "findings_total": 30,
  "decision_required_human": false,
  "coder_entry": "fix-from-panel",
  "iteration_budget_note": "Cycle 3 Совета Тимлидов по коду завершён после R1 (panel/council/r25) и D1 (panel/council/r29) с вердиктом NEEDS_WORK (8 первичных блокеров RW-001..RW-008, 15 non-blocking FU-001..FU-015, 7 excluded: 6 duplicate_of + 1 out_of_scope). Бюджет следующей волны: Coder rework (coder-06, Цикл 4) -> слепой reverse-spec -> Clean-Room L2 -> Cycle 4 Совета Тимлидов по коду.",
  "do_not_change": [
    "Разрешено модифицировать ТОЛЬКО 3 файла из allowed_envelope_changes: bridges/opencode-zen-bridge/server.py, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py, bridges/opencode-zen-bridge/tests/test_step_interruption.py.",
    "Запрещено менять замороженную функцию def _run_env в bridges/opencode-zen-bridge/server.py (sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31).",
    "Запрещено менять замороженную функцию def _stream_google_sse в bridges/opencode-zen-bridge/server.py (sha256=5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3).",
    "Запрещено менять замороженную функцию def _execute_google_once в bridges/opencode-zen-bridge/server.py (sha256=88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6).",
    "Запрещено добавлять любые внешние зависимости вне стандартной библиотеки Python 3.14 (dependencies = [] в pyproject.toml).",
    "Запрещено модифицировать zen_catalog.py, start.sh, muse-bridge, существующие тестовые модули вне конверта и коммитить dynamic_config.json в git."
  ],
  "instructions": [
    {
      "id": "RW-001",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:2406-2407,3062,5198-5201,5206,5229-5234,5294,6407-6409,6431-6434,6486",
      "rule_ref": "RW-009, RW-012, REQ-009, AC-014, FALLBACK_DECISION_TABLE",
      "action": "Фиксировать `headers_at` в `_prompt_async` сразу после `getresponse()` (до `resp.read()`), и проверять монотонный барьер доставки (`delivered_any[0]` / модельный чанк или подтверждённый prompt) во всех четырёх ветках `return False` по `ServeUnavailable` и отказу `spawn_limiter` (как в `_run_serve_stream_attempts`, так и в `_serve_json_serve`): если барьер уже установлен, не делать fallback на `run`, а выполнять `serve-retry` (с эмиссией ровно одного разделителя `[мост] Повтор попытки`) или терминальную ошибку (`_sse_error` / HTTP 502) без вызова `record_success()`. При этом синтетический `STATUS_INITIAL` барьер доставки не ставит.",
      "acceptance": "Попытка 1 отдаёт `reasoning`, попытка 2 бросает `ServeUnavailable` или упирается в `spawn_limiter`: `Run` не запускается ни в SSE, ни в JSON, клиенту отдаётся ровно один разделитель или терминальная ошибка, `record_success()` не вызывается.",
      "source": "F-001 (skeptic · R1 · skeptic-F-001; status=AGREED; votes: R1 skeptic=AUTHOR; D1 skeptic=AMEND, realist=AGREE, visionary=AGREE; duplicates merged: F-018, F-020)",
      "source_findings": [
        "F-001"
      ],
      "evidence": "Ledger F-001: votes=[R1 skeptic=AUTHOR; D1 skeptic=AMEND, realist=AGREE, visionary=AGREE]; dissent=[skeptic d1 «AMEND F-001 priority=blocking; locations=`server.py:2406`, `:2407`, `:3062`, `:3112`, `:5198`, `:5206`, `:5229`, `:5294`, `:6407`, `:6431`, `:6486`; fix=фиксировать prompt headers непосредстве» → teamlead/cycle-3/debate/d1/skeptic.md]; amendments=[skeptic d1: priority=blocking; locations=`server.py:2406`, `:2407`, `:3062`, `:3112`, `:5198`, `:5206`, `:5229`, `:5294`, `:6407`, `:6431`, `:6486`; fix=фиксировать prompt headers непосредственно после `getresponse()`, сохранять общ (teamlead/cycle-3/debate/d1/skeptic.md)]."
    },
    {
      "id": "RW-002",
      "priority": "blocking",
      "criterion": "ПОЛНОТА",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:5808-5814",
      "rule_ref": "RW-017, REQ-004, AC-005",
      "action": "В `Handler._stream_sse` на legacy-пути `run` не отменять `status_timer` до `spawn_limiter.acquire()`: переносить `status_timer.cancel()` после прохождения `spawn_limiter.acquire()` (непосредственно перед стартом `send_keepalive` / `run`), чтобы при ожидании лимитера более 0.65 с первый видимый статус `[мост] ...` гарантированно доставлялся за `<= 1.0 с` без дублирования `STATUS_INITIAL`.",
      "acceptance": "При свободном `_StartupGate` и занятом `spawn_limiter` на legacy-пути `run` первый статус `[мост]` приходит не позднее `1.0 с` (`AC-005`), ровно один `STATUS_INITIAL`.",
      "source": "F-002 (skeptic · R1 · skeptic-F-002; status=AGREED; votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AMEND)",
      "source_findings": [
        "F-002"
      ],
      "evidence": "Ledger F-002: votes=[R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AMEND]; dissent=[visionary d1 «AMEND F-002 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5808-5814; fix=держать защитный таймер до первого видимого чанка либо отдавать статус во время ожидания spawn» → teamlead/cycle-3/debate/d1/visionary.md]; amendments=[visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5808-5814; fix=держать защитный таймер до первого видимого чанка либо отдавать статус во время ожидания spawn_limiter, не дублируя STATUS_INITIAL — п (teamlead/cycle-3/debate/d1/visionary.md)]."
    },
    {
      "id": "RW-003",
      "priority": "blocking",
      "criterion": "РЕАЛИЗУЕМОСТЬ",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:1738,2891-2929",
      "rule_ref": "RW-004, REQ-008, AC-011",
      "action": "Включить вызов `_serve_env` (`tempfile.mkdtemp(prefix=\"zen-serve-state-\")`) внутрь защищённого блока `try/except BaseException` запуска `_spawn_serve`, транслируя локальные `OSError` (например `ENOSPC`/`EACCES` в `mkdtemp`) в `ServeUnavailable` с гарантированной очисткой всех уже выделенных ресурсов.",
      "acceptance": "Fault injection `OSError` на `tempfile.mkdtemp` при старте `serve` переводится в `ServeUnavailable` (штатный fallback или ошибка без ложного `client_gone`) и не оставляет сиротских FD, портов или каталогов.",
      "source": "F-004 (skeptic · R1 · skeptic-F-004; status=AGREED; votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE)",
      "source_findings": [
        "F-004"
      ],
      "evidence": "Ledger F-004: votes=[R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE]; dissent=[—]; amendments=[—]."
    },
    {
      "id": "RW-004",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:686-726,2832-2853",
      "rule_ref": "REQ-011, REQ-012, AC-017, code.md",
      "action": "В `_native_call_as_dsh` переиспользовать существующий канонический преобразователь `_native_to_tool_calls(tool_name, args, tools)` (включая `_fit_args`, нормализацию `list`/`ls` и разворачивание `multiedit` в список вызовов), чтобы нативные вызовы инструментов в `serve` и `run` давали побайтово идентичные `tool_calls` в SSE и JSON.",
      "acceptance": "Одинаковые нативные фикстуры `bash`/`read`/`edit`/`list`/`multiedit` дают идентичные `tool_calls` в `serve` и `run` (SSE и JSON).",
      "source": "F-007 (skeptic · R1 · skeptic-F-007; status=AGREED; votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE)",
      "source_findings": [
        "F-007"
      ],
      "evidence": "Ledger F-007: votes=[R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE]; dissent=[—]; amendments=[—]."
    },
    {
      "id": "RW-005",
      "priority": "blocking",
      "criterion": "РИСКИ",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:1115-1119",
      "rule_ref": "REQ-008, AC-011, T-LIFE/v1",
      "action": "В `_stop_proc` проверять живость процессной группы `pgid` (`_pgid_alive(pgid)` через `os.killpg(pgid, 0)`) независимо от `proc.poll() is not None`: даже если лидер `opencode run` уже завершился, при живых членах группы посылать `SIGTERM` всей группе `-pgid`, ждать завершения группы и эскалировать `SIGKILL` на `-pgid` при оставшихся процессах.",
      "acceptance": "Если лидер `opencode run` завершился раньше дочернего процесса в своей процессной группе, `_stop_proc` завершает всю группу (`SIGTERM` -> `SIGKILL`), не оставляя сиротских процессов.",
      "source": "F-008 (skeptic · R1 · skeptic-F-008; status=AGREED; votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE)",
      "source_findings": [
        "F-008"
      ],
      "evidence": "Ledger F-008: votes=[R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE]; dissent=[realist d1 «AMEND F-008 priority=non-blocking; locations=server.py:1115-1119; fix=перед выходом по `poll() is not None` проверять живость группы через `killpg(pgid, 0)` — причина: `_stop_proc` не входит в» → teamlead/cycle-3/debate/d1/realist.md]; amendments=[realist d1: priority=non-blocking; locations=server.py:1115-1119; fix=перед выходом по `poll() is not None` проверять живость группы через `killpg(pgid, 0)` — причина: `_stop_proc` не входит в дельту, в candidate.diff нет ханка в эт (teamlead/cycle-3/debate/d1/realist.md)]."
    },
    {
      "id": "RW-006",
      "priority": "blocking",
      "criterion": "ПОЛНОТА",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:1700-1704",
      "rule_ref": "REQ-003, python-standards.md §3",
      "action": "В `_read_dynamic_config_enabled` ловить `(OSError, ValueError)` (включая `UnicodeDecodeError` при чтении повреждённого UTF-8 в `dynamic_config.json`), возвращая безопасное значение по умолчанию `False` (fail-open в `run`) и логируя предупреждение.",
      "acceptance": "Невалидные UTF-8 байты в `dynamic_config.json` не прерывают обработку запроса в режиме `auto` (выбирается `run`), а последующее восстановление валидного JSON включает `serve`.",
      "source": "F-010 (skeptic · R1 · skeptic-F-010; status=AGREED; votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE)",
      "source_findings": [
        "F-010"
      ],
      "evidence": "Ledger F-010: votes=[R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE]; dissent=[—]; amendments=[—]."
    },
    {
      "id": "RW-007",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:823,5127,5145",
      "rule_ref": "REQ-011",
      "action": "Обеспечить инкрементальную очистку маркеров прерванного шага (`_INTERRUPTED_RE`) на потоковом пути `serve` с буферизацией потенциального префикса маркера на границе соседних текстовых дельт (и сбросом буфера в конце шага), чтобы маркер `I was interrupted right before making tool calls.` удалялся даже при разбиении между двумя дельтами.",
      "acceptance": "Маркер прерывания шага, разрезанный между двумя соседними текстовыми дельтами `serve`, полностью удаляется из клиентского вывода так же, как при подаче одним чанком.",
      "source": "F-011 (skeptic · R1 · skeptic-F-011; status=AGREED; votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE)",
      "source_findings": [
        "F-011"
      ],
      "evidence": "Ledger F-011: votes=[R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE]; dissent=[realist d1 «AMEND F-011 priority=non-blocking; locations=server.py:823, 5127, 5145; fix=инкрементальная очистка с удержанием хвоста либо вынос в адаптер — причина: в serve `result[\"texts\"]` пополняется сы» → teamlead/cycle-3/debate/d1/realist.md]; amendments=[realist d1: priority=non-blocking; locations=server.py:823, 5127, 5145; fix=инкрементальная очистка с удержанием хвоста либо вынос в адаптер — причина: в serve `result[\"texts\"]` пополняется сырой дельтой до `on_text`, поэтому `_inco (teamlead/cycle-3/debate/d1/realist.md)]."
    },
    {
      "id": "RW-008",
      "priority": "blocking",
      "criterion": "РИСКИ",
      "file": "bridges/opencode-zen-bridge/server.py",
      "line_hint": "server.py:1928,5347,6523",
      "rule_ref": "REQ-015, AC-020, security.md",
      "action": "Пропускать сообщения ошибок провайдера/транспорта `err.get(\"message\")` и `_error_payload` через `_clean_err` / `_mask_secrets` перед отправкой в клиентский SSE/JSON и записью в лог.",
      "acceptance": "Sentinel-секреты (`sk-...`, `Bearer ...`, `OPENCODE_SERVER_PASSWORD`, учётные данные прокси) в тексте ошибки провайдера `serve` маскируются в SSE, JSON и `bridge.log`.",
      "source": "F-014 (skeptic · R1 · skeptic-F-014; status=AGREED; votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE)",
      "source_findings": [
        "F-014"
      ],
      "evidence": "Ledger F-014: votes=[R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE]; dissent=[realist d1 «AMEND F-014 priority=non-blocking; locations=server.py:5347, 6523; fix=пропускать `err.get('message')` через `_clean_err` до `_error_payload` — причина: сообщение уходит только клиенту на 127.» → teamlead/cycle-3/debate/d1/realist.md]; amendments=[realist d1: priority=non-blocking; locations=server.py:5347, 6523; fix=пропускать `err.get('message')` через `_clean_err` до `_error_payload` — причина: сообщение уходит только клиенту на 127.0.0.1 и в `_log` не пишется. AC-020 пров (teamlead/cycle-3/debate/d1/realist.md)]."
    }
  ],
  "non_blocking_followups": [
    {
      "id": "FU-001",
      "text": "Ограничивать фазы старта и чтения тела ответа `_ctrl_http`/`_prompt_async` остатком общего `attempts.deadline` и проверкой `is_client_gone`.",
      "reason": "Понижено большинством 2/3 (`realist` + `visionary` AMEND non-blocking) в D1: каждая фаза уже ограничена короткими окнами 3–5 с, а `lease.cleanup()` в `finally` размыкает сокеты.",
      "source_findings": [
        "F-003"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-002",
      "text": "В `_serve_json_serve` на ветке `transient_error` переносить частичные `texts` и `reasonings` неуспешной попытки в накопители перед построением recovery-промпта.",
      "reason": "Понижено большинством 2/3 (`realist` + `visionary` AMEND non-blocking) в D1: DSH ходит со `stream:true` (`F-35`), а в JSON клиенту до завершения ничего не эмитится.",
      "source_findings": [
        "F-005"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-003",
      "text": "В `_run_serve_stream_attempts` начислять `result[\"usage\"]` в аккумулятор ровно один раз до ветвления по причинам ретрая (как в JSON).",
      "reason": "Понижено большинством 2/3 (`realist` + `visionary` AMEND non-blocking) в D1 (`REQ-014` имеет приоритет `SHOULD`).",
      "source_findings": [
        "F-006"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-004",
      "text": "Пробрасывать `on_idle` и `is_client_gone` в legacy JSON-путь `Run._execute_once` (не затрагивая замороженный `_run_env`).",
      "reason": "Понижено большинством 2/3 (`realist` + `visionary` AMEND non-blocking) в D1: инцидент и AC-005..010 относятся к SSE.",
      "source_findings": [
        "F-009"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-005",
      "text": "В `test_ac026_realtime_chunks_before_upstream_end` ужесточить порог соседних дельт с `< 1.0` до `< 0.5` с и фиксировать независимую отметку завершения отправки `FakeServe`.",
      "reason": "Понижено большинством 2/3 (`realist` + `visionary` AMEND non-blocking) в D1.",
      "source_findings": [
        "F-012"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-006",
      "text": "Поддерживать стабильные допуски таймингов в `tests/test_realtime_reasoning.py` без модификации `pyproject.toml` (вне конверта).",
      "reason": "Понижено большинством 2/3 (`realist` + `visionary` AMEND non-blocking) в D1 (`pyproject.toml` вне конверта `allowed_envelope_changes`, включая дубль `F-027`).",
      "source_findings": [
        "F-013"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-007",
      "text": "В `_serve_one_attempt` при сборке нативного вызова на границе `step_finish` (`server.py:3304-3309`) выставлять `first_token_at` и `ttft_ms`, если они ещё `None`.",
      "reason": "Согласовано 3/3 в D1 как non-blocking уточнение телеметрии `O-EXIT/v1`.",
      "source_findings": [
        "F-016"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-008",
      "text": "Уточнить пояснения в оставшихся комментариях `# pyright: ignore[...] — причина:` в `tests/test_realtime_reasoning.py:324-325,1150,1154` под конкретное выражение.",
      "reason": "Согласовано 3/3 в D1 как non-blocking гигиена комментариев (включая дубль `F-029`).",
      "source_findings": [
        "F-017"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-009",
      "text": "На legacy-пути `run` (`send_keepalive`) обновлять отметку активности первого токена/шага при получении `step_start` (либо использовать повышенный порог для буферизующего `opencode run`), чтобы длинный шаг размышления `> 60 с` на `opencode run` не прерывался ложным `first_token_timeout`.",
      "reason": "Согласовано в D1 (`realist` AMEND non-blocking) как безопасная защита legacy-пути для длинных запросов (до `85.65 с` по `F-32`).",
      "source_findings": [
        "F-019"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-010",
      "text": "Гейтить эмиссию синтетического разделителя `[мост] Повтор попытки` по флагу `thinking_enabled` так же, как периодические статусы ожидания.",
      "reason": "Согласовано большинством 2/3 (`realist` + `visionary`) в D1 как non-blocking.",
      "source_findings": [
        "F-021"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-011",
      "text": "При `terminal == \"cancelled\"` (отмена `form.created`) не вызывать `serve_health.record_success()` и единообразно завершать попытку в SSE и JSON.",
      "reason": "Согласовано 3/3 в D1 как non-blocking.",
      "source_findings": [
        "F-022"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-012",
      "text": "Синхронизировать декларативную таблицу `FALLBACK_DECISION_TABLE` с фактическим поведением веток `prompt_status`.",
      "reason": "Согласовано большинством 2/3 (`realist` + `visionary`) в D1 как non-blocking.",
      "source_findings": [
        "F-023"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-013",
      "text": "В `test_transport_matrix` явно проверять файл отключения `DISABLE_FILE_PATH`, а в `test_elf_magic_and_tool_status` — сигнатуру ELF/Mach-O и поле статуса.",
      "reason": "Согласовано 3/3 в D1 как non-blocking усиление тестов.",
      "source_findings": [
        "F-024"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-014",
      "text": "Минимизировать число подпроцессов `lsof` при ожидании готовности `serve` (проверять после готовности HTTP или с увеличенным шагом).",
      "reason": "Согласовано большинством 2/3 (`realist` + `visionary`) в D1 как non-blocking оптимизация.",
      "source_findings": [
        "F-025"
      ],
      "decision_required_human": false
    },
    {
      "id": "FU-015",
      "text": "Добавить в `test_serve_env_sanitized_all_branches` гарантированное удаление временного каталога `XDG_STATE_HOME` через `shutil.rmtree` в `finally` (с учётом `F-030`).",
      "reason": "Согласовано в D1 как non-blocking.",
      "source_findings": [
        "F-026"
      ],
      "decision_required_human": false
    }
  ],
  "excluded": [
    {
      "id": "F-015",
      "reason": "out_of_scope"
    },
    {
      "id": "F-018",
      "reason": "duplicate_of:F-001"
    },
    {
      "id": "F-020",
      "reason": "duplicate_of:F-001"
    },
    {
      "id": "F-027",
      "reason": "duplicate_of:F-013"
    },
    {
      "id": "F-028",
      "reason": "duplicate_of:F-017"
    },
    {
      "id": "F-029",
      "reason": "duplicate_of:F-017"
    },
    {
      "id": "F-030",
      "reason": "duplicate_of:F-026"
    }
  ]
}
ARTIFACT_END>>>

## 3. Handoff исполнителя и квитанции гейтов (`coder.json`, `receipts/coder.json`, `code-gate.json`, `verifier.json`, `final-gate.json`)
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json sha256=a983d140bed9e85993d200d065fecdd9b2ed5b690ac4ef2e5780df17ec1685da
{
  "schema_version": "1.1",
  "role": "coder",
  "task_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "round_id": "coder-06",
  "iteration": 1,
  "teamlead_cycle": 4,
  "entry": "fix-from-panel",
  "status": "DONE",
  "summary": "coder-06c: снят последний блокер RP-03 без изменения Go-теста: _SpawnRateLimiter.refund возвращает резерв под _lock при OSError из _spawn_with_stdin в Run._execute_once и Handler._stream_sse. VER-004 exit=0; полный pytest 445 passed; полный unittest 445 OK; frozen SHA-256 сохранены. Передача на независимый Reviewer; бизнес-приёмка не заявляется.",
  "role_plan": {
    "path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json",
    "sha256": "1ce038618e677e689466f3b1e27ba51dbcea6830058740658cac18fee80e3598",
    "phase": "after"
  },
  "changed_files": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
  ],
  "files_changed": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
  ],
  "inherited_modified_files": [
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
  ],
  "report_files": [
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json"
  ],
  "commands": [
    {
      "command": "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
      "exit_code": 0,
      "output_summary": "VER004_EXIT:0; basedpyright errors=0; server warnings=591, step=169, newfile=0; all3 lint/type, changed-range format, frozen hashes 3/3 PASS, catalog 8 OK",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/ver004.log",
      "execution": "run-guarded --; background PGID 37424"
    },
    {
      "command": "uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider tests",
      "exit_code": 0,
      "output_summary": "445 passed in 175.70s (0:02:55)",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-pytest.log",
      "execution": "run-guarded --; background PGID 45446"
    },
    {
      "command": "python3 -m unittest discover -s tests -p 'test_*.py'",
      "exit_code": 0,
      "output_summary": "Ran 445 tests in 174.375s; OK",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-unittest.log",
      "execution": "run-guarded --; background PGID 45446, после full pytest"
    },
    {
      "command": "git diff --check",
      "exit_code": 0,
      "output_summary": "Без ошибок пробелов"
    },
    {
      "command": "python3 \"$HOME/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py\" .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json --phase after",
      "exit_code": 0,
      "output_summary": "PASS: coder role plan is valid for after; sha256=1ce038618e677e689466f3b1e27ba51dbcea6830058740658cac18fee80e3598"
    },
    {
      "command": "python3 \"$HOME/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_handoff.py\" coder .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json --role-plan .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json --root \"$PWD\"",
      "exit_code": 0,
      "output_summary": "VALID: role=coder file=.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json"
    }
  ],
  "verification_commands": [
    {
      "command": "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
      "exit_code": 0,
      "output_summary": "VER004_EXIT:0; basedpyright errors=0; server warnings=591, step=169, newfile=0; all3 lint/type, changed-range format, frozen hashes 3/3 PASS, catalog 8 OK",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/ver004.log",
      "execution": "run-guarded --; background PGID 37424"
    },
    {
      "command": "uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider tests",
      "exit_code": 0,
      "output_summary": "445 passed in 175.70s (0:02:55)",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-pytest.log",
      "execution": "run-guarded --; background PGID 45446"
    },
    {
      "command": "python3 -m unittest discover -s tests -p 'test_*.py'",
      "exit_code": 0,
      "output_summary": "Ran 445 tests in 174.375s; OK",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-unittest.log",
      "execution": "run-guarded --; background PGID 45446, после full pytest"
    },
    {
      "command": "python3 \"$HOME/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py\" .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json --phase after",
      "exit_code": 0,
      "output_summary": "PASS: coder role plan is valid for after; sha256=1ce038618e677e689466f3b1e27ba51dbcea6830058740658cac18fee80e3598"
    },
    {
      "command": "python3 \"$HOME/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_handoff.py\" coder .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json --role-plan .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json --root \"$PWD\"",
      "exit_code": 0,
      "output_summary": "VALID: role=coder file=.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json"
    }
  ],
  "tests_added": [
    "test_rw002_initial_status_while_waiting_spawn_limiter",
    "test_fu003_usage_once_across_distinct_retry_branches",
    "test_fu010_thinking_off_omits_retry_separator",
    "test_rw001_delivery_survives_unavailable_or_limiter",
    "test_rw007_split_interrupted_marker_at_every_boundary",
    "test_rw008_provider_secrets_hidden_in_sse_json_and_log",
    "test_rw006_invalid_utf8_falls_back_and_recovers",
    "test_rw003_mkdtemp_failure_is_serve_unavailable",
    "test_fu011_cancelled_never_counts_as_success",
    "test_disable_file_overrides_forced_serve",
    "test_fu001_http_checks_deadline_and_cancellation_before_connect",
    "test_rw004_native_calls_share_canonical_mapping",
    "test_rw005_stop_group_after_leader_exit",
    "test_rw008_error_payload_masks_message_and_detail"
  ],
  "red_green_evidence": {
    "red_exit_code": 1,
    "red_failure_summary": "До исправлений воспроизведены RW-001 (JSON fallback после reasoning), RW-007 (safe/carry разрезает маркер), RW-008 (provider Bearer/proxy/password и общий error_payload). Первичный VER-004: reportExplicitAny _fit_args:688. coder-06c: до refund существующий tests/test_go_model_routing.py воспроизвёл лишний STATUS_INITIAL: 1 failed, 9 passed in 28.04s, exit=1; ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/red-go.log.",
    "green_exit_code": 0,
    "green_summary": "VER004_EXIT:0; basedpyright errors=0, server warnings=591 <=720, step warnings=169 <=194, newfile diagnostics=0; frozen SHA-256 3/3 PASS; pytest: 445 passed in 175.70s (0:02:55); unittest: Ran 445 tests in 174.375s; OK; оба full-suite exit=0, run-guarded. Сырые логи: ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/ver004.log, ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-pytest.log, ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-unittest.log."
  },
  "acceptance_coverage": [
    "RW-001: _serve_http фиксирует headers_at до чтения тела; барьер delivered_any монотонен в SSE и JSON, включая исключение ServeUnavailable и отказ лимитера. test_rw001_delivery_survives_unavailable_or_limiter: четыре сочетания SSE/JSON × unavailable/limiter, без Run.execute и _spawn_with_stdin, без record_success.",
    "RW-002: status_timer отменяется после spawn_limiter.acquire на legacy run; test_rw002_initial_status_while_waiting_spawn_limiter: задержка 1.2 с, ровно один STATUS_INITIAL <=1.0 с.",
    "RW-003: _serve_env защищён переводом OSError в ServeUnavailable до выделения lease/порта; test_rw003_mkdtemp_failure_is_serve_unavailable: ENOSPC не оставляет активных портов.",
    "RW-004: _native_call_as_dsh делегирует _native_to_tool_calls; test_rw004_native_calls_share_canonical_mapping сравнивает сериализованные bash/read/edit/list/multiedit.",
    "RW-005: _stop_proc проверяет группу независимо от лидера; test_rw005_stop_group_after_leader_exit: реальный лидер завершён, потомок игнорирует SIGTERM, группа завершена SIGKILL.",
    "RW-006: _read_dynamic_config_enabled ловит OSError/ValueError и логирует предупреждение; test_rw006_invalid_utf8_falls_back_and_recovers: битые UTF-8 дают run, восстановление JSON даёт serve.",
    "RW-007: Потоковый текстовый фильтр удерживает возможный префикс и незавершённую строку маркера вместо произвольного хвоста 128 символов; test_rw007_split_interrupted_marker_at_every_boundary покрывает три разреза, включая прежнюю границу safe/carry.",
    "RW-008: _error_payload очищает message/detail; _mask_secrets скрывает Bearer, OPENCODE_SERVER_PASSWORD и proxy userinfo. test_rw008_error_payload_masks_message_and_detail и test_rw008_provider_secrets_hidden_in_sse_json_and_log.",
    "FU-001: _serve_http пересчитывает остаток deadline и проверяет is_client_gone перед request/getresponse и каждой порцией read1; ctrl/prompt передают общий deadline. Сокет HTTP/1.0 сохранён для таймаута тела, закрытое тело больше не опрашивается; test_fu001_http_checks_deadline_and_cancellation_before_connect и FakeServe-сценарии.",
    "FU-002: JSON transient_error переносит texts/reasonings в накопители до выбора recovery-промпта или следующей попытки.",
    "FU-003: SSE usage начисляется в единой точке до любых retry-веток; test_fu003_usage_once_across_distinct_retry_branches: 3+5+7=15 без потерь и повторов.",
    "FU-004: Run.is_client_gone передаётся из Handler; _execute_once использует on_idle с интервалом _STDOUT_POLL_S, останавливая молчащую группу при уходе клиента. _run_env не изменён.",
    "FU-005: AC-026: порог соседних reasoning-дельт <0.5 с; FakeServe независимо пишет монотонное время конца отправки, оно сравнивается с реальными клиентскими отметками.",
    "FU-006: Тайминги задаются в тестовом модуле, pyproject.toml не изменён; профильный набор 174 passed.",
    "FU-007: На step_finish завершённый native-вызов задаёт first_token_at/ttft_ms, если токена ещё не было.",
    "FU-008: Причины pyright ignore уточнены для bytes/read1, разделения SSE-буфера, JSON и mock.patch.start/stop; новый файл имеет 0 diagnostics.",
    "FU-009: Legacy run использует для буферизующего CLI порог первого токена max(FIRST_TOKEN_TIMEOUT_S,120.0), покрывая длительные шаги более 60 с.",
    "FU-010: Разделитель повтора гейтится thinking; test_fu010_thinking_off_omits_retry_separator.",
    "FU-011: terminal=cancelled не считается успехом SSE/JSON; test_fu011_cancelled_never_counts_as_success.",
    "FU-012: FALLBACK_DECISION_TABLE отражает prompt 429/5xx: run до доставки, serve-retry после доставки.",
    "FU-013: test_disable_file_overrides_forced_serve проверяет настоящий disable-файл; test_elf_magic_and_tool_status проверяет ELF/Mach-O, shebang/случайные байты и статус completed.",
    "FU-014: Шаг проверки listener через lsof увеличен с 0.05 до 0.2 с в _spawn_serve.",
    "FU-015: test_serve_env_sanitized_all_branches гарантированно удаляет XDG_STATE_HOME через shutil.rmtree в finally.",
    "coder-06c / RP-03: возврат неиспользованного spawn-резерва при OSError в обоих путях, без изменения tests/test_go_model_routing.py; до фикса Go 1 failed/9 passed, после фикса полный pytest 445 passed и unittest 445 OK. RW-002 сохранён."
  ],
  "finding_evidence": {
    "RW-001": "_serve_http фиксирует headers_at до чтения тела; барьер delivered_any монотонен в SSE и JSON, включая исключение ServeUnavailable и отказ лимитера. test_rw001_delivery_survives_unavailable_or_limiter: четыре сочетания SSE/JSON × unavailable/limiter, без Run.execute и _spawn_with_stdin, без record_success.",
    "RW-002": "status_timer отменяется после spawn_limiter.acquire на legacy run; test_rw002_initial_status_while_waiting_spawn_limiter: задержка 1.2 с, ровно один STATUS_INITIAL <=1.0 с.",
    "RW-003": "_serve_env защищён переводом OSError в ServeUnavailable до выделения lease/порта; test_rw003_mkdtemp_failure_is_serve_unavailable: ENOSPC не оставляет активных портов.",
    "RW-004": "_native_call_as_dsh делегирует _native_to_tool_calls; test_rw004_native_calls_share_canonical_mapping сравнивает сериализованные bash/read/edit/list/multiedit.",
    "RW-005": "_stop_proc проверяет группу независимо от лидера; test_rw005_stop_group_after_leader_exit: реальный лидер завершён, потомок игнорирует SIGTERM, группа завершена SIGKILL.",
    "RW-006": "_read_dynamic_config_enabled ловит OSError/ValueError и логирует предупреждение; test_rw006_invalid_utf8_falls_back_and_recovers: битые UTF-8 дают run, восстановление JSON даёт serve.",
    "RW-007": "Потоковый текстовый фильтр удерживает возможный префикс и незавершённую строку маркера вместо произвольного хвоста 128 символов; test_rw007_split_interrupted_marker_at_every_boundary покрывает три разреза, включая прежнюю границу safe/carry.",
    "RW-008": "_error_payload очищает message/detail; _mask_secrets скрывает Bearer, OPENCODE_SERVER_PASSWORD и proxy userinfo. test_rw008_error_payload_masks_message_and_detail и test_rw008_provider_secrets_hidden_in_sse_json_and_log.",
    "FU-001": "_serve_http пересчитывает остаток deadline и проверяет is_client_gone перед request/getresponse и каждой порцией read1; ctrl/prompt передают общий deadline. Сокет HTTP/1.0 сохранён для таймаута тела, закрытое тело больше не опрашивается; test_fu001_http_checks_deadline_and_cancellation_before_connect и FakeServe-сценарии.",
    "FU-002": "JSON transient_error переносит texts/reasonings в накопители до выбора recovery-промпта или следующей попытки.",
    "FU-003": "SSE usage начисляется в единой точке до любых retry-веток; test_fu003_usage_once_across_distinct_retry_branches: 3+5+7=15 без потерь и повторов.",
    "FU-004": "Run.is_client_gone передаётся из Handler; _execute_once использует on_idle с интервалом _STDOUT_POLL_S, останавливая молчащую группу при уходе клиента. _run_env не изменён.",
    "FU-005": "AC-026: порог соседних reasoning-дельт <0.5 с; FakeServe независимо пишет монотонное время конца отправки, оно сравнивается с реальными клиентскими отметками.",
    "FU-006": "Тайминги задаются в тестовом модуле, pyproject.toml не изменён; профильный набор 174 passed.",
    "FU-007": "На step_finish завершённый native-вызов задаёт first_token_at/ttft_ms, если токена ещё не было.",
    "FU-008": "Причины pyright ignore уточнены для bytes/read1, разделения SSE-буфера, JSON и mock.patch.start/stop; новый файл имеет 0 diagnostics.",
    "FU-009": "Legacy run использует для буферизующего CLI порог первого токена max(FIRST_TOKEN_TIMEOUT_S,120.0), покрывая длительные шаги более 60 с.",
    "FU-010": "Разделитель повтора гейтится thinking; test_fu010_thinking_off_omits_retry_separator.",
    "FU-011": "terminal=cancelled не считается успехом SSE/JSON; test_fu011_cancelled_never_counts_as_success.",
    "FU-012": "FALLBACK_DECISION_TABLE отражает prompt 429/5xx: run до доставки, serve-retry после доставки.",
    "FU-013": "test_disable_file_overrides_forced_serve проверяет настоящий disable-файл; test_elf_magic_and_tool_status проверяет ELF/Mach-O, shebang/случайные байты и статус completed.",
    "FU-014": "Шаг проверки listener через lsof увеличен с 0.05 до 0.2 с в _spawn_serve.",
    "FU-015": "test_serve_env_sanitized_all_branches гарантированно удаляет XDG_STATE_HOME через shutil.rmtree в finally.",
    "RP-03": "В _SpawnRateLimiter добавлен refund(amount: float = 1.0) -> None: под self._lock восстанавливает self._tokens = min(self._burst, self._tokens + amount). Вызывается ровно в двух except OSError после _spawn_with_stdin. VER004_EXIT:0; basedpyright errors=0, server warnings=591 <=720, step warnings=169 <=194, newfile diagnostics=0; frozen SHA-256 3/3 PASS; pytest: 445 passed in 175.70s (0:02:55); unittest: Ran 445 tests in 174.375s; OK; оба full-suite exit=0, run-guarded. Сырые логи: ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/ver004.log, ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-pytest.log, ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-unittest.log."
  },
  "delta_explanations": [
    "RW-007 требует более 15 строк: необходимо одновременно удержать неполный префикс, сохранить необработанный хвост и сбросить его на границе попытки. Алгоритм доставки и ToolCallParser сохранены.",
    "FU-001 требует более 15 строк: отдельная проверка бюджета перед запросом, заголовками и порциями тела, а также передача deadline/cancellation из ctrl/prompt; публичный API не менялся.",
    "Регрессионные тесты длиннее продуктовых исправлений, поскольку проверяют матрицы SSE/JSON и настоящие процессы/HTTP, а не повторяют реализацию."
  ],
  "assumptions": [],
  "risks": [
    "Живой ход в существующем рабочем слоте владельца не выполнялся; проверены FakeServe и локальные процессы/HTTP. Бизнес-приёмка и rollout не заявляются."
  ],
  "unresolved_risks": [],
  "open_questions": [],
  "source_file_sha256": {
    "bridges/opencode-zen-bridge/server.py": "3193913f29f87efaba202d41fc2c3634f3a4303560f75d7c3bb60e65bfac36c2",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py": "2bd26e8ed7abf9feecdd8399161247f02b6afda230e1b02d978d68d863fbb9a4",
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py": "e41d10bd96cb208ce3120ab25d1c8028c82fe81895eacd322312b7fbbbef8a11"
  },
  "frozen_sha256": {
    "_run_env": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
    "_stream_google_sse": "5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3",
    "_execute_google_once": "88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6"
  },
  "background_checks": [
    "coder-06c RED: Go pytest, PGID 22805",
    "coder-06c форматирование диапазонов + VER-004 под run-guarded, PGID 37424",
    "coder-06c полный pytest затем полный unittest под run-guarded, PGID 45446"
  ],
  "next_role": "reviewer",
  "continuation_deviations": [
    "В брифе лимитер назван _TokenBucket, но фактический класс — _SpawnRateLimiter с полем _burst. Метод refund добавлен в существующий класс без переименования и без нового слоя; delta coder-06c — 7 добавленных строк server.py.",
    "Пути teamlead-gate/scripts/validate_role_plan.py и validate_handoff.py из брифа отсутствуют (ENOENT). Найдены и использованы существующие валидаторы ~/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/ с теми же CLI-параметрами."
  ]
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json sha256=a983d140bed9e85993d200d065fecdd9b2ed5b690ac4ef2e5780df17ec1685da
{
  "schema_version": "1.1",
  "role": "coder",
  "task_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "round_id": "coder-06",
  "iteration": 1,
  "teamlead_cycle": 4,
  "entry": "fix-from-panel",
  "status": "DONE",
  "summary": "coder-06c: снят последний блокер RP-03 без изменения Go-теста: _SpawnRateLimiter.refund возвращает резерв под _lock при OSError из _spawn_with_stdin в Run._execute_once и Handler._stream_sse. VER-004 exit=0; полный pytest 445 passed; полный unittest 445 OK; frozen SHA-256 сохранены. Передача на независимый Reviewer; бизнес-приёмка не заявляется.",
  "role_plan": {
    "path": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json",
    "sha256": "1ce038618e677e689466f3b1e27ba51dbcea6830058740658cac18fee80e3598",
    "phase": "after"
  },
  "changed_files": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
  ],
  "files_changed": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
  ],
  "inherited_modified_files": [
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
  ],
  "report_files": [
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json",
    ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json"
  ],
  "commands": [
    {
      "command": "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
      "exit_code": 0,
      "output_summary": "VER004_EXIT:0; basedpyright errors=0; server warnings=591, step=169, newfile=0; all3 lint/type, changed-range format, frozen hashes 3/3 PASS, catalog 8 OK",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/ver004.log",
      "execution": "run-guarded --; background PGID 37424"
    },
    {
      "command": "uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider tests",
      "exit_code": 0,
      "output_summary": "445 passed in 175.70s (0:02:55)",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-pytest.log",
      "execution": "run-guarded --; background PGID 45446"
    },
    {
      "command": "python3 -m unittest discover -s tests -p 'test_*.py'",
      "exit_code": 0,
      "output_summary": "Ran 445 tests in 174.375s; OK",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-unittest.log",
      "execution": "run-guarded --; background PGID 45446, после full pytest"
    },
    {
      "command": "git diff --check",
      "exit_code": 0,
      "output_summary": "Без ошибок пробелов"
    },
    {
      "command": "python3 \"$HOME/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py\" .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json --phase after",
      "exit_code": 0,
      "output_summary": "PASS: coder role plan is valid for after; sha256=1ce038618e677e689466f3b1e27ba51dbcea6830058740658cac18fee80e3598"
    },
    {
      "command": "python3 \"$HOME/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_handoff.py\" coder .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json --role-plan .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json --root \"$PWD\"",
      "exit_code": 0,
      "output_summary": "VALID: role=coder file=.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json"
    }
  ],
  "verification_commands": [
    {
      "command": "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
      "exit_code": 0,
      "output_summary": "VER004_EXIT:0; basedpyright errors=0; server warnings=591, step=169, newfile=0; all3 lint/type, changed-range format, frozen hashes 3/3 PASS, catalog 8 OK",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/ver004.log",
      "execution": "run-guarded --; background PGID 37424"
    },
    {
      "command": "uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider tests",
      "exit_code": 0,
      "output_summary": "445 passed in 175.70s (0:02:55)",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-pytest.log",
      "execution": "run-guarded --; background PGID 45446"
    },
    {
      "command": "python3 -m unittest discover -s tests -p 'test_*.py'",
      "exit_code": 0,
      "output_summary": "Ran 445 tests in 174.375s; OK",
      "raw_output_path": "~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-unittest.log",
      "execution": "run-guarded --; background PGID 45446, после full pytest"
    },
    {
      "command": "python3 \"$HOME/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py\" .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json --phase after",
      "exit_code": 0,
      "output_summary": "PASS: coder role plan is valid for after; sha256=1ce038618e677e689466f3b1e27ba51dbcea6830058740658cac18fee80e3598"
    },
    {
      "command": "python3 \"$HOME/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_handoff.py\" coder .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json --role-plan .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json --root \"$PWD\"",
      "exit_code": 0,
      "output_summary": "VALID: role=coder file=.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-06.json"
    }
  ],
  "tests_added": [
    "test_rw002_initial_status_while_waiting_spawn_limiter",
    "test_fu003_usage_once_across_distinct_retry_branches",
    "test_fu010_thinking_off_omits_retry_separator",
    "test_rw001_delivery_survives_unavailable_or_limiter",
    "test_rw007_split_interrupted_marker_at_every_boundary",
    "test_rw008_provider_secrets_hidden_in_sse_json_and_log",
    "test_rw006_invalid_utf8_falls_back_and_recovers",
    "test_rw003_mkdtemp_failure_is_serve_unavailable",
    "test_fu011_cancelled_never_counts_as_success",
    "test_disable_file_overrides_forced_serve",
    "test_fu001_http_checks_deadline_and_cancellation_before_connect",
    "test_rw004_native_calls_share_canonical_mapping",
    "test_rw005_stop_group_after_leader_exit",
    "test_rw008_error_payload_masks_message_and_detail"
  ],
  "red_green_evidence": {
    "red_exit_code": 1,
    "red_failure_summary": "До исправлений воспроизведены RW-001 (JSON fallback после reasoning), RW-007 (safe/carry разрезает маркер), RW-008 (provider Bearer/proxy/password и общий error_payload). Первичный VER-004: reportExplicitAny _fit_args:688. coder-06c: до refund существующий tests/test_go_model_routing.py воспроизвёл лишний STATUS_INITIAL: 1 failed, 9 passed in 28.04s, exit=1; ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/red-go.log.",
    "green_exit_code": 0,
    "green_summary": "VER004_EXIT:0; basedpyright errors=0, server warnings=591 <=720, step warnings=169 <=194, newfile diagnostics=0; frozen SHA-256 3/3 PASS; pytest: 445 passed in 175.70s (0:02:55); unittest: Ran 445 tests in 174.375s; OK; оба full-suite exit=0, run-guarded. Сырые логи: ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/ver004.log, ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-pytest.log, ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-unittest.log."
  },
  "acceptance_coverage": [
    "RW-001: _serve_http фиксирует headers_at до чтения тела; барьер delivered_any монотонен в SSE и JSON, включая исключение ServeUnavailable и отказ лимитера. test_rw001_delivery_survives_unavailable_or_limiter: четыре сочетания SSE/JSON × unavailable/limiter, без Run.execute и _spawn_with_stdin, без record_success.",
    "RW-002: status_timer отменяется после spawn_limiter.acquire на legacy run; test_rw002_initial_status_while_waiting_spawn_limiter: задержка 1.2 с, ровно один STATUS_INITIAL <=1.0 с.",
    "RW-003: _serve_env защищён переводом OSError в ServeUnavailable до выделения lease/порта; test_rw003_mkdtemp_failure_is_serve_unavailable: ENOSPC не оставляет активных портов.",
    "RW-004: _native_call_as_dsh делегирует _native_to_tool_calls; test_rw004_native_calls_share_canonical_mapping сравнивает сериализованные bash/read/edit/list/multiedit.",
    "RW-005: _stop_proc проверяет группу независимо от лидера; test_rw005_stop_group_after_leader_exit: реальный лидер завершён, потомок игнорирует SIGTERM, группа завершена SIGKILL.",
    "RW-006: _read_dynamic_config_enabled ловит OSError/ValueError и логирует предупреждение; test_rw006_invalid_utf8_falls_back_and_recovers: битые UTF-8 дают run, восстановление JSON даёт serve.",
    "RW-007: Потоковый текстовый фильтр удерживает возможный префикс и незавершённую строку маркера вместо произвольного хвоста 128 символов; test_rw007_split_interrupted_marker_at_every_boundary покрывает три разреза, включая прежнюю границу safe/carry.",
    "RW-008: _error_payload очищает message/detail; _mask_secrets скрывает Bearer, OPENCODE_SERVER_PASSWORD и proxy userinfo. test_rw008_error_payload_masks_message_and_detail и test_rw008_provider_secrets_hidden_in_sse_json_and_log.",
    "FU-001: _serve_http пересчитывает остаток deadline и проверяет is_client_gone перед request/getresponse и каждой порцией read1; ctrl/prompt передают общий deadline. Сокет HTTP/1.0 сохранён для таймаута тела, закрытое тело больше не опрашивается; test_fu001_http_checks_deadline_and_cancellation_before_connect и FakeServe-сценарии.",
    "FU-002: JSON transient_error переносит texts/reasonings в накопители до выбора recovery-промпта или следующей попытки.",
    "FU-003: SSE usage начисляется в единой точке до любых retry-веток; test_fu003_usage_once_across_distinct_retry_branches: 3+5+7=15 без потерь и повторов.",
    "FU-004: Run.is_client_gone передаётся из Handler; _execute_once использует on_idle с интервалом _STDOUT_POLL_S, останавливая молчащую группу при уходе клиента. _run_env не изменён.",
    "FU-005: AC-026: порог соседних reasoning-дельт <0.5 с; FakeServe независимо пишет монотонное время конца отправки, оно сравнивается с реальными клиентскими отметками.",
    "FU-006: Тайминги задаются в тестовом модуле, pyproject.toml не изменён; профильный набор 174 passed.",
    "FU-007: На step_finish завершённый native-вызов задаёт first_token_at/ttft_ms, если токена ещё не было.",
    "FU-008: Причины pyright ignore уточнены для bytes/read1, разделения SSE-буфера, JSON и mock.patch.start/stop; новый файл имеет 0 diagnostics.",
    "FU-009: Legacy run использует для буферизующего CLI порог первого токена max(FIRST_TOKEN_TIMEOUT_S,120.0), покрывая длительные шаги более 60 с.",
    "FU-010: Разделитель повтора гейтится thinking; test_fu010_thinking_off_omits_retry_separator.",
    "FU-011: terminal=cancelled не считается успехом SSE/JSON; test_fu011_cancelled_never_counts_as_success.",
    "FU-012: FALLBACK_DECISION_TABLE отражает prompt 429/5xx: run до доставки, serve-retry после доставки.",
    "FU-013: test_disable_file_overrides_forced_serve проверяет настоящий disable-файл; test_elf_magic_and_tool_status проверяет ELF/Mach-O, shebang/случайные байты и статус completed.",
    "FU-014: Шаг проверки listener через lsof увеличен с 0.05 до 0.2 с в _spawn_serve.",
    "FU-015: test_serve_env_sanitized_all_branches гарантированно удаляет XDG_STATE_HOME через shutil.rmtree в finally.",
    "coder-06c / RP-03: возврат неиспользованного spawn-резерва при OSError в обоих путях, без изменения tests/test_go_model_routing.py; до фикса Go 1 failed/9 passed, после фикса полный pytest 445 passed и unittest 445 OK. RW-002 сохранён."
  ],
  "finding_evidence": {
    "RW-001": "_serve_http фиксирует headers_at до чтения тела; барьер delivered_any монотонен в SSE и JSON, включая исключение ServeUnavailable и отказ лимитера. test_rw001_delivery_survives_unavailable_or_limiter: четыре сочетания SSE/JSON × unavailable/limiter, без Run.execute и _spawn_with_stdin, без record_success.",
    "RW-002": "status_timer отменяется после spawn_limiter.acquire на legacy run; test_rw002_initial_status_while_waiting_spawn_limiter: задержка 1.2 с, ровно один STATUS_INITIAL <=1.0 с.",
    "RW-003": "_serve_env защищён переводом OSError в ServeUnavailable до выделения lease/порта; test_rw003_mkdtemp_failure_is_serve_unavailable: ENOSPC не оставляет активных портов.",
    "RW-004": "_native_call_as_dsh делегирует _native_to_tool_calls; test_rw004_native_calls_share_canonical_mapping сравнивает сериализованные bash/read/edit/list/multiedit.",
    "RW-005": "_stop_proc проверяет группу независимо от лидера; test_rw005_stop_group_after_leader_exit: реальный лидер завершён, потомок игнорирует SIGTERM, группа завершена SIGKILL.",
    "RW-006": "_read_dynamic_config_enabled ловит OSError/ValueError и логирует предупреждение; test_rw006_invalid_utf8_falls_back_and_recovers: битые UTF-8 дают run, восстановление JSON даёт serve.",
    "RW-007": "Потоковый текстовый фильтр удерживает возможный префикс и незавершённую строку маркера вместо произвольного хвоста 128 символов; test_rw007_split_interrupted_marker_at_every_boundary покрывает три разреза, включая прежнюю границу safe/carry.",
    "RW-008": "_error_payload очищает message/detail; _mask_secrets скрывает Bearer, OPENCODE_SERVER_PASSWORD и proxy userinfo. test_rw008_error_payload_masks_message_and_detail и test_rw008_provider_secrets_hidden_in_sse_json_and_log.",
    "FU-001": "_serve_http пересчитывает остаток deadline и проверяет is_client_gone перед request/getresponse и каждой порцией read1; ctrl/prompt передают общий deadline. Сокет HTTP/1.0 сохранён для таймаута тела, закрытое тело больше не опрашивается; test_fu001_http_checks_deadline_and_cancellation_before_connect и FakeServe-сценарии.",
    "FU-002": "JSON transient_error переносит texts/reasonings в накопители до выбора recovery-промпта или следующей попытки.",
    "FU-003": "SSE usage начисляется в единой точке до любых retry-веток; test_fu003_usage_once_across_distinct_retry_branches: 3+5+7=15 без потерь и повторов.",
    "FU-004": "Run.is_client_gone передаётся из Handler; _execute_once использует on_idle с интервалом _STDOUT_POLL_S, останавливая молчащую группу при уходе клиента. _run_env не изменён.",
    "FU-005": "AC-026: порог соседних reasoning-дельт <0.5 с; FakeServe независимо пишет монотонное время конца отправки, оно сравнивается с реальными клиентскими отметками.",
    "FU-006": "Тайминги задаются в тестовом модуле, pyproject.toml не изменён; профильный набор 174 passed.",
    "FU-007": "На step_finish завершённый native-вызов задаёт first_token_at/ttft_ms, если токена ещё не было.",
    "FU-008": "Причины pyright ignore уточнены для bytes/read1, разделения SSE-буфера, JSON и mock.patch.start/stop; новый файл имеет 0 diagnostics.",
    "FU-009": "Legacy run использует для буферизующего CLI порог первого токена max(FIRST_TOKEN_TIMEOUT_S,120.0), покрывая длительные шаги более 60 с.",
    "FU-010": "Разделитель повтора гейтится thinking; test_fu010_thinking_off_omits_retry_separator.",
    "FU-011": "terminal=cancelled не считается успехом SSE/JSON; test_fu011_cancelled_never_counts_as_success.",
    "FU-012": "FALLBACK_DECISION_TABLE отражает prompt 429/5xx: run до доставки, serve-retry после доставки.",
    "FU-013": "test_disable_file_overrides_forced_serve проверяет настоящий disable-файл; test_elf_magic_and_tool_status проверяет ELF/Mach-O, shebang/случайные байты и статус completed.",
    "FU-014": "Шаг проверки listener через lsof увеличен с 0.05 до 0.2 с в _spawn_serve.",
    "FU-015": "test_serve_env_sanitized_all_branches гарантированно удаляет XDG_STATE_HOME через shutil.rmtree в finally.",
    "RP-03": "В _SpawnRateLimiter добавлен refund(amount: float = 1.0) -> None: под self._lock восстанавливает self._tokens = min(self._burst, self._tokens + amount). Вызывается ровно в двух except OSError после _spawn_with_stdin. VER004_EXIT:0; basedpyright errors=0, server warnings=591 <=720, step warnings=169 <=194, newfile diagnostics=0; frozen SHA-256 3/3 PASS; pytest: 445 passed in 175.70s (0:02:55); unittest: Ran 445 tests in 174.375s; OK; оба full-suite exit=0, run-guarded. Сырые логи: ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/ver004.log, ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-pytest.log, ~/work/cli-agent-bridge/coder-06c-20261027-o33ihuod/full-unittest.log."
  },
  "delta_explanations": [
    "RW-007 требует более 15 строк: необходимо одновременно удержать неполный префикс, сохранить необработанный хвост и сбросить его на границе попытки. Алгоритм доставки и ToolCallParser сохранены.",
    "FU-001 требует более 15 строк: отдельная проверка бюджета перед запросом, заголовками и порциями тела, а также передача deadline/cancellation из ctrl/prompt; публичный API не менялся.",
    "Регрессионные тесты длиннее продуктовых исправлений, поскольку проверяют матрицы SSE/JSON и настоящие процессы/HTTP, а не повторяют реализацию."
  ],
  "assumptions": [],
  "risks": [
    "Живой ход в существующем рабочем слоте владельца не выполнялся; проверены FakeServe и локальные процессы/HTTP. Бизнес-приёмка и rollout не заявляются."
  ],
  "unresolved_risks": [],
  "open_questions": [],
  "source_file_sha256": {
    "bridges/opencode-zen-bridge/server.py": "3193913f29f87efaba202d41fc2c3634f3a4303560f75d7c3bb60e65bfac36c2",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py": "2bd26e8ed7abf9feecdd8399161247f02b6afda230e1b02d978d68d863fbb9a4",
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py": "e41d10bd96cb208ce3120ab25d1c8028c82fe81895eacd322312b7fbbbef8a11"
  },
  "frozen_sha256": {
    "_run_env": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
    "_stream_google_sse": "5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3",
    "_execute_google_once": "88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6"
  },
  "background_checks": [
    "coder-06c RED: Go pytest, PGID 22805",
    "coder-06c форматирование диапазонов + VER-004 под run-guarded, PGID 37424",
    "coder-06c полный pytest затем полный unittest под run-guarded, PGID 45446"
  ],
  "next_role": "reviewer",
  "continuation_deviations": [
    "В брифе лимитер назван _TokenBucket, но фактический класс — _SpawnRateLimiter с полем _burst. Метод refund добавлен в существующий класс без переименования и без нового слоя; delta coder-06c — 7 добавленных строк server.py.",
    "Пути teamlead-gate/scripts/validate_role_plan.py и validate_handoff.py из брифа отсутствуют (ENOENT). Найдены и использованы существующие валидаторы ~/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/ с теми же CLI-параметрами."
  ]
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/code-gate.json sha256=75e41e1cda9989e182a03b49f0eb2f8121ec639e856d89c8ba9416f55772fe11
{
  "schema_version": "1.0",
  "gate": "CODE_GATE_AND_L2_CLEANROOM",
  "status": "PASS",
  "timestamp": "2026-10-27T03:13:41.709589+00:00",
  "touched_files": [
    "bridges/opencode-zen-bridge/server.py",
    "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py",
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
  ],
  "run_env_sha256": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
  "google_direct_unchanged": true,
  "red_sensitivity_rc": 1,
  "green_failures": [],
  "checks": [
    {
      "name": "L2-RED-sensitivity",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_realtime_reasoning.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 1,
      "wall_seconds": 15.33,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-red.log",
      "log_sha256": "13e2b337979db4252216bf59719692869c6b0851f156e87924996aedbcbec757"
    },
    {
      "name": "VER-004-packet-command",
      "cmd": [
        "/bin/zsh",
        "-lc",
        "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom",
      "rc": 0,
      "wall_seconds": 22.53,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-packet.log",
      "log_sha256": "28cc596d5832e0b715a0df332f616aa848942a1d79b4428a5d6314358e0677eb"
    },
    {
      "name": "VER-004-ruff-format-new",
      "cmd": [
        "uvx",
        "--from",
        "ruff==0.17.2",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        "tests/test_realtime_reasoning.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 0.04,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-ruff-format-new.log",
      "log_sha256": "791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7"
    },
    {
      "name": "VER-001-pytest",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 176.83,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver001-pytest.log",
      "log_sha256": "b682638b87a7442fa90c9f3060cc69387492a885fd11d61f3a9e440f0559cb29"
    },
    {
      "name": "VER-002-unittest",
      "cmd": [
        "python3",
        "-m",
        "unittest",
        "discover",
        "-s",
        "tests",
        "-p",
        "test_*.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 174.41,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver002-unittest.log",
      "log_sha256": "13ac0fb9d2f6096771600115a08befc18d2af1c30c8c969f0bbe0c0aa71edaf8"
    },
    {
      "name": "VER-003-root-pythonpath-pytest",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom",
      "rc": 0,
      "wall_seconds": 369.21,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver003-pythonpath.log",
      "log_sha256": "605082a78fbe90283b66a00cc5c3b8652e8a908fe734fa35f4a793052d8cdbd3"
    },
    {
      "name": "VER-003b-root-pythonpath-zen-pytest",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "bridges/opencode-zen-bridge/tests/"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom",
      "rc": 0,
      "wall_seconds": 177.39,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver003b-zen-pythonpath.log",
      "log_sha256": "15a08212f9cf14e3d13b617c39bb8f6d92d10ea6ab6636110842017693b00827"
    },
    {
      "name": "VER-005-dedicated-realtime-suite",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_realtime_reasoning.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 97.31,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver005-dedicated.log",
      "log_sha256": "dd30cd05a110afc86a2b349341297d870171c35c64891d5f1f41fec962e9bd9e"
    },
    {
      "name": "AC-023-pytest-reversed",
      "cmd": [
        "uvx",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
        "tests/test_zen_catalog.py",
        "tests/test_tool_emulation.py",
        "tests/test_sync_yaml.py",
        "tests/test_stream_thinking.py",
        "tests/test_step_interruption.py",
        "tests/test_stdin_prompt.py",
        "tests/test_run_env.py",
        "tests/test_realtime_reasoning.py",
        "tests/test_native_fallback.py",
        "tests/test_lenient_tool_call.py",
        "tests/test_google_direct.py",
        "tests/test_go_model_routing.py",
        "tests/test_effort_mapping.py",
        "tests/test_cli_failure.py",
        "tests/test_catalog_reload.py",
        "tests/test_catalog_mode.py",
        "tests/test_catalog.py",
        "tests/test_aliases.py"
      ],
      "cwd": "/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge",
      "rc": 0,
      "wall_seconds": 177.83,
      "log_path": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ac023-reversed.log",
      "log_sha256": "03df835757fbfc228e5a73a0a2436358660f42a7fd291f10f96ac0c83845c8fb"
    }
  ]
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/verifier.json sha256=5a9f9caa0a1eab13961d6c1e181dda43b6c863e5d1a5c4e6e8da02d217f54d4f
{
  "schema_version": "1.0",
  "gate": "VERIFIER",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "timestamp": "2026-10-27T03:15:03.273968+00:00",
  "role_plan": {
    "path": "plans/verifier-01.json",
    "sha256": "90dbc1173042a2b155e0f192996966a7630fb1d9b10054d9b1ab417554f0afc5"
  },
  "code_gate_sha256": "75e41e1cda9989e182a03b49f0eb2f8121ec639e856d89c8ba9416f55772fe11",
  "execution_evidence_sha256": "8ba52f52ab5761988431c0058c2f55cb0d0de1fefc8cc1b8f59aae1a0355863b",
  "verification_traceability_sha256": "87b60a12ca3f2004205c499b59144caed863a00b18594ed358eb481b1a5b73fa",
  "environment_manifest_sha256": "ae123569d37b2ef167248011b437a05baf7c3dc5f1cbe6594b1484b023f4d502",
  "reverse_spec_sha256": "2774577c0a6f46b822b2d41ec3cec6f1a0f77d744a8f8e4dce1508e968a1a69d",
  "l3_state": "DEFERRED_L3"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/final-gate.json sha256=236a4b1d5dfd6a39dbcc0c038e2c4a2c81f24aeeb7a27bdc39b873e9d021d106
{
  "schema_version": "1.0",
  "gate": "FINAL_GATE_PRE_COUNCIL",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "timestamp": "2026-10-27T03:15:03.274468+00:00",
  "reviewer_skip": true,
  "downstream_panel": true,
  "parent_skill": "analyst-teamlead",
  "coder_handoff_sha256": "a983d140bed9e85993d200d065fecdd9b2ed5b690ac4ef2e5780df17ec1685da",
  "code_gate_sha256": "75e41e1cda9989e182a03b49f0eb2f8121ec639e856d89c8ba9416f55772fe11",
  "verifier_receipt_sha256": "5a9f9caa0a1eab13961d6c1e181dda43b6c863e5d1a5c4e6e8da02d217f54d4f",
  "candidate_diff_sha256": "bb5bdd651db33691cbc45eb5270a3aff615b3b49679b1c40db635e9d44dc67c5",
  "pr_description_absent_before_council": true
}
ARTIFACT_END>>>

## 4. Свидетельства независимой верификации и слепой reverse-spec (`verification-surface.json`, `environment-manifest.json`, `execution-evidence.md`, `verification-traceability.md`, `evidence-manifest.sha256`, `reverse-spec.md`)
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-surface.json sha256=e67d5ffb98e29dd698e38e17e18772fa792391a2e24e05cf88d2f820a14e8722
{
  "schema": "verification-surface/v1",
  "created_at_utc": "2026-10-26T08:16:03.437356+00:00",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "risk_level": "medium",
  "criticality": "S2",
  "base_sha": "7eda27f9d82732bab726a420e31ea2adc15c2c39",
  "worktree_fingerprint_before_coder": null,
  "worktree_file_count_before_coder": 152,
  "runtime_toolchain": {
    "python3": "Python 3.14.7",
    "uv": "uv 0.12.19 (bea138450 2026-09-24 aarch64-apple-darwin)",
    "ruff": "ruff 0.17.2 (via uvx --from ruff==0.17.2)",
    "basedpyright": "basedpyright 1.40.2 (via uvx --from basedpyright==1.40.2)",
    "opencode": "opencode v2.1.2"
  },
  "container_image_digest": null,
  "lock_files": {},
  "config_and_ci_files": {
    "bridges/opencode-zen-bridge/pyproject.toml": "7d6387d88008df032bfdc5c9f4ca7e7c8eb58ec3d72d1c90ff5b8a227df6b6ff"
  },
  "mandatory_ci_jobs": [],
  "oracle_test_hashes_before_coder": {
    "bridges/opencode-zen-bridge/tests/__init__.py": "41e4377649ceac5f8c9079f7b1dcd7593b7add43ac737b3d7e9dbf4340d465c1",
    "bridges/opencode-zen-bridge/tests/_fake_cli.py": "0dd57ba7b80f54f5d73fa595a1500ff3367f334c5efeaeebe819840b2eb32b75",
    "bridges/opencode-zen-bridge/tests/_fixtures.py": "777898f6d72283a6c034889b43d87e2fa0a16e4068a69eca79a6cee13cf5ae37",
    "bridges/opencode-zen-bridge/tests/_http.py": "834df1103fc7f0f9ba9ac75bd1c2d1f2fb0c5644e1d75d05685e1abdbe865f57",
    "bridges/opencode-zen-bridge/tests/live_matrix.py": "a3f839733a7c723473cb936c8b16f6743c25f3d12053d76461198c7d9a19581e",
    "bridges/opencode-zen-bridge/tests/test_aliases.py": "1a8ca46743d7f59418bf4993933fac4612712e1c786cce8c24efa415ae273568",
    "bridges/opencode-zen-bridge/tests/test_catalog.py": "3dcae238c1e2d743c768e2cef4a3286614ae7051a771c24f2d8ad49a8725cf0d",
    "bridges/opencode-zen-bridge/tests/test_catalog_mode.py": "822dfa9dea1674c141964e3e25fbd272e67c6387d573615a2e0e9111bdc975b8",
    "bridges/opencode-zen-bridge/tests/test_catalog_reload.py": "fac9fad229bdc6d0cd9c696e6283448b629851d64a219735badeb59dcfec7ef6",
    "bridges/opencode-zen-bridge/tests/test_cli_failure.py": "12b95cefcc03ae40ec46494328767c6f9a0f520a014a3d844dbf0eeb5eaeea2d",
    "bridges/opencode-zen-bridge/tests/test_effort_mapping.py": "d26c94b139e3c0a793499baf31c9e4cb1dc92e281fb3d5927da7c019d5f12868",
    "bridges/opencode-zen-bridge/tests/test_go_model_routing.py": "c75d74be787e85900e42e9aa08205ef17045f69b12664602e70159444c8a8f1b",
    "bridges/opencode-zen-bridge/tests/test_google_direct.py": "692d074f1da44189ce0fc19b46c146af103e5be870e072c2f1e6599f39c7d603",
    "bridges/opencode-zen-bridge/tests/test_lenient_tool_call.py": "0dda90013f3f991a95601a17e75269274c52d3ad9206eabe6a3c1247fc9b3768",
    "bridges/opencode-zen-bridge/tests/test_native_fallback.py": "f79f8b7030f9e5ee5a734c38f3846a10446315c574bcba5db69ffab833bcef57",
    "bridges/opencode-zen-bridge/tests/test_run_env.py": "d3d0baf57f7ccae7dd7846ab98d3da43c588a35e7f076fabe074c1212f232e05",
    "bridges/opencode-zen-bridge/tests/test_stdin_prompt.py": "533c0905314a31dfe63ea519fb3d1d2a43f9e629a61d9d00cb508ba7c674e8c6",
    "bridges/opencode-zen-bridge/tests/test_step_interruption.py": "afd542fed0722e48989c997c31595772a5c2df194a6c47ae6c1e86935bb2aa6e",
    "bridges/opencode-zen-bridge/tests/test_stream_thinking.py": "ddaa0b97d274ec6f1a13fa7cb17856c109d4f219caa04a03e425127703b8f8ca",
    "bridges/opencode-zen-bridge/tests/test_sync_yaml.py": "1e8593332bacd8f116fc587b6838b139e181211adb749cfe0fc7c9322a0d29ef",
    "bridges/opencode-zen-bridge/tests/test_tool_emulation.py": "bd756c717909687bc974e68c184a6d1d7937043edf2f3768bfdae40d5c2b51af",
    "bridges/opencode-zen-bridge/tests/test_zen_catalog.py": "8f4c60f33e041da64ae4f297286d5900e7aa6ac0776142fcda15c05ca5b7423e"
  },
  "testdata_golden_snapshot_hashes": {},
  "coverage_and_quality_thresholds": {
    "ruff_format_check": "exit 0 on tests/test_realtime_reasoning.py + closed --range={start}:1-{end}:999 on modified hunks of server.py and tests/test_step_interruption.py + frozen slice sha256 checks",
    "ruff_check": "exit 0 on coder_target_files (allowing existing import zen_catalog as zc E402 on server.py)",
    "basedpyright": "0 errors and per-rule warning counts <= baseline ceilings (reportAny <= 125, 0 new Any in changed ranges) via basedpyright==1.40.2",
    "external_runtime_dependencies": "0 outside Python 3.14 stdlib"
  },
  "baseline": {
    "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/",
    "exit_code": 1,
    "counts": {
      "collected": 378,
      "passed": 375,
      "failed": 3,
      "skipped": 0,
      "xfailed": 0,
      "xpassed": 0
    },
    "preexisting_red_failures": [
      {
        "test_id": "tests/test_step_interruption.py::StepInterruptionTests::test_four_consecutive_interruptions_exhaust_budget",
        "phase": "call",
        "exception_type": "AssertionError",
        "message_key": "MAX_TOTAL_SPAWNS=3 caps total spawns at 3 while legacy test asserts 4 spawns (F-47)"
      },
      {
        "test_id": "tests/test_step_interruption.py::StepInterruptionTests::test_non_stream_retries_on_step_interruption",
        "phase": "call",
        "exception_type": "AssertionError",
        "message_key": "shared _RetryBudget / MAX_TOTAL_SPAWNS=3 mismatch in legacy test fixture (F-48)"
      },
      {
        "test_id": "tests/test_step_interruption.py::StepInterruptionTests::test_stream_retries_on_step_interruption_and_succeeds",
        "phase": "call",
        "exception_type": "AssertionError",
        "message_key": "shared _RetryBudget / MAX_TOTAL_SPAWNS=3 mismatch in legacy test fixture (F-49)"
      }
    ],
    "note": "REQ-017 / AD-004 explicitly scopes fixing these 3 legacy test/budget drift items without weakening MAX_TOTAL_SPAWNS=3 invariant; Verifier audits any oracle_change in tests/test_step_interruption.py."
  },
  "allowed_envelope_changes": {
    "code": [
      "bridges/opencode-zen-bridge/server.py"
    ],
    "new_tests": [
      "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
    ],
    "existing_tests_additive_or_req017": [
      "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
    ],
    "forbidden_oracle_changes": [
      "bridges/opencode-zen-bridge/tests/test_run_env.py",
      "bridges/opencode-zen-bridge/tests/test_google_direct.py",
      "bridges/opencode-zen-bridge/tests/test_catalog_mode.py",
      "bridges/opencode-zen-bridge/tests/test_zen_bridge.py",
      "deleting tests, adding skip/xfail, weakening assertions, narrowing test selectors"
    ],
    "dependencies": [],
    "configs": []
  },
  "levels": {
    "L1": [
      {
        "id": "VER-004-static-and-frozen-slices",
        "cmd": "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
        "cwd": "."
      },
      {
        "id": "VER-001-pytest-component",
        "cmd": "uvx pytest -q -p no:cacheprovider tests/",
        "cwd": "bridges/opencode-zen-bridge"
      }
    ],
    "L2": [
      {
        "id": "L2-VER-004-static-and-frozen-slices",
        "cmd": "python3 - <<'VER004'\nimport ast, collections, hashlib, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\n\n# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.\nFROZEN = {\n    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',\n    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',\n    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',\n}\nbaseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)\ndef frozen_slices(raw):\n    lines = raw.splitlines(keepends=True)\n    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}\n    assert set(nodes)==set(FROZEN)\n    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}\nbaseline_slices = frozen_slices(baseline_raw)\ndef assert_frozen(candidate=files[0]):\n    candidate_slices = frozen_slices(candidate.read_bytes())\n    for name, expected in FROZEN.items():\n        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)\n        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)\n        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)\n    return candidate_slices\ncandidate_slices = assert_frozen()\nserver_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)\nfor line in server_diff.splitlines():\n    match = re.match(r'^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@',line)\n    if not match: continue\n    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')\n    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:\n        for name,(lo,hi,_) in table.items():\n            # Zero-count insert/delete anchors represent the boundary after start.\n            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)\n            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)\n# Public module constant/read API remains intact; compatibility test file is frozen.\ntree = ast.parse(files[0].read_bytes())\nassignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]\nassert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)\nassert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))\nassert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))\nassert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'\nhelper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == \"sys.argv[1:2] == ['--serve-helper']\"), None)\nassert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'\nheavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}\ndef imported_names(node):\n    if isinstance(node, ast.Import): return {a.name for a in node.names}\n    if isinstance(node, ast.ImportFrom): return {node.module}\n    return set()\nassert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])\nassert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)\nassert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'\nassert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))\nrun(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)\n\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)\nassert_frozen()\n# Exercise actual write-mode range formatting only on a disposable copy.\nwith tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:\n    formatted_copy = Path(format_dir) / 'server.py'\n    formatted_copy.write_bytes(files[0].read_bytes())\n    for start, end in ranges[files[0]]:\n        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)\n    assert formatted_copy.read_bytes() == files[0].read_bytes()\n    assert_frozen(formatted_copy)\n    assert_frozen()\n    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    print('BASEDPYRIGHT summary',report['summary'])\n    print('SERVER dict(counts)',dict(counts))\n    print('SERVER warningCount',len(warnings(files[0])))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
        "cwd": "."
      },
      {
        "id": "L2-VER-001-pytest-component",
        "cmd": "uvx pytest -q -p no:cacheprovider tests/",
        "cwd": "bridges/opencode-zen-bridge"
      },
      {
        "id": "L2-VER-002-unittest-discover",
        "cmd": "python3 -m unittest discover -s tests -p 'test_*.py'",
        "cwd": "bridges/opencode-zen-bridge"
      },
      {
        "id": "L2-VER-003-pytest-root-import",
        "cmd": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/",
        "cwd": "."
      },
      {
        "id": "L2-VER-005-realtime-and-fault-oracles",
        "cmd": "uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py tests/test_step_interruption.py tests/test_run_env.py tests/test_google_direct.py tests/test_catalog_mode.py",
        "cwd": "bridges/opencode-zen-bridge"
      }
    ],
    "L3": {
      "status_pre_accept": "N/A_REPO_MARKERS_PLUS_POST_ACCEPT_LIVE_HEAVY_PATH",
      "note": "Repo has no pytest heavy/measured markers (entire component suite runs in L2). Live runtime checks H0..H9 / VER-006/VER-007 on deployed LaunchAgent 127.0.0.1:9883 are DEFERRED_L3 until Council ACCEPT + cp sync of server.py to ~/.dsh/bridges/opencode-zen-bridge/server.py so live production bridge is not mutated before Council ACCEPT.",
      "deferred_checks": [
        {
          "id": "VER-006-live-sse-heavy-path",
          "cmd": "Rollout ladder H0..H9 + curl -N -sS http://127.0.0.1:9883/v1/chat/completions (deepseek-v4.1-flash-free High, stream=true, multi-turn + tools + disconnect cleanup)",
          "defer_reason": "Requires syncing ~/.dsh/bridges/opencode-zen-bridge/server.py after Council ACCEPT"
        },
        {
          "id": "VER-007-deployed-mirror-diff",
          "cmd": "diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py",
          "defer_reason": "Synced post-ACCEPT after backup to ~/work/backups/"
        }
      ]
    }
  },
  "acceptance_manifest_ref": "analysis/zen-realtime-reasoning/handoff-qa.md",
  "architecture_packet_sha256": "88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/environment-manifest.json sha256=ae123569d37b2ef167248011b437a05baf7c3dc5f1cbe6594b1484b023f4d502
{
  "schema": "environment-manifest/v1",
  "captured_at_utc": "2026-10-27T03:15:03.162583+00:00",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "platform": {
    "system": "Darwin",
    "release": "27.0.0",
    "machine": "arm64",
    "python_version": "3.14.7",
    "python_executable": "/opt/homebrew/opt/python@3.14/bin/python3.14"
  },
  "tools": {
    "uv": "uv 0.12.19 (bea138450 2026-09-24 aarch64-apple-darwin)",
    "ruff": "ruff 0.17.2 (uvx --from ruff==0.17.2)",
    "basedpyright": "basedpyright 1.40.2 (uvx --from basedpyright==1.40.2)",
    "opencode": "opencode v2.1.2",
    "git": "git version 2.54.0"
  },
  "isolation": {
    "cleanroom_mode": "git worktree --detach at origin/dev (/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom)",
    "coder_worktree": "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning",
    "worktree_fingerprint_before": null,
    "worktree_fingerprint_after": "ba0ac83323e29fe5a3fa80c71dbfdd0c5fedc75dca1f76631dcc9ef854388776",
    "external_runtime_dependencies_added": 0
  }
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/execution-evidence.md sha256=8ba52f52ab5761988431c0058c2f55cb0d0de1fefc8cc1b8f59aae1a0355863b
# Независимое свидетельство исполнения верификации (`execution-evidence.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `4`)

- **Базовый коммит (`origin/dev`):** `7eda27f9d82732bab726a420e31ea2adc15c2c39`
- **Отпечаток рабочего дерева ДО Coder (`coder-06-before.json`):** `None`
- **Отпечаток рабочего дерева ПОСЛЕ Coder (`coder-06-after.json`):** `ba0ac83323e29fe5a3fa80c71dbfdd0c5fedc75dca1f76631dcc9ef854388776`
- **Clean-room контур L2:** отдельное `git worktree` от `origin/dev`, исполнено детерминированным `Verifier` (`run_cleanroom_l2.py`), не логами `Coder`.

## Сводная таблица проверок L2 и L3

| ID / Проверка | Уровень | Статус | Команда | CWD | Exit code | Wall (s) | Сырой лог | SHA-256 лога |
|---|---|---|---|---|---|---|---|---|
| `L2-RED-sensitivity` | L2 | `PASS (RED sensitivity rc!=0)` | `uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `1` | `15.33` | `l2-red.log` | `13e2b337979db4252216bf59719692869c6b0851f156e87924996aedbcbec757` |
| `VER-004-packet-command` | L2 | `PASS` | `/bin/zsh -lc python3 - <<'VER004' import ast, collections, hashlib, json, re, subprocess, tempfile from pathlib import Path root = Path.c...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `22.53` | `l2-green-ver004-packet.log` | `28cc596d5832e0b715a0df332f616aa848942a1d79b4428a5d6314358e0677eb` |
| `VER-004-ruff-format-new` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.04` | `l2-green-ver004-ruff-format-new.log` | `791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7` |
| `VER-001-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `176.83` | `l2-green-ver001-pytest.log` | `b682638b87a7442fa90c9f3060cc69387492a885fd11d61f3a9e440f0559cb29` |
| `VER-002-unittest` | L2 | `PASS` | `python3 -m unittest discover -s tests -p test_*.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `174.41` | `l2-green-ver002-unittest.log` | `13ac0fb9d2f6096771600115a08befc18d2af1c30c8c969f0bbe0c0aa71edaf8` |
| `VER-003-root-pythonpath-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `369.21` | `l2-green-ver003-pythonpath.log` | `605082a78fbe90283b66a00cc5c3b8652e8a908fe734fa35f4a793052d8cdbd3` |
| `VER-003b-root-pythonpath-zen-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `177.39` | `l2-green-ver003b-zen-pythonpath.log` | `15a08212f9cf14e3d13b617c39bb8f6d92d10ea6ab6636110842017693b00827` |
| `VER-005-dedicated-realtime-suite` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `97.31` | `l2-green-ver005-dedicated.log` | `dd30cd05a110afc86a2b349341297d870171c35c64891d5f1f41fec962e9bd9e` |
| `AC-023-pytest-reversed` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinki...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `177.83` | `l2-green-ac023-reversed.log` | `03df835757fbfc228e5a73a0a2436358660f42a7fd291f10f96ac0c83845c8fb` |
| `VER-006-live-sse-heavy-path` | L3 | `DEFERRED_L3` | `Rollout ladder H0..H9 + curl -N -sS http://127.0.0.1:9883/v1/chat/completions (deepseek-v4.1-flash-free High, stream=true, multi-turn + tools + disconnect cleanup)` | `~/.dsh/bridges/opencode-zen-bridge` |  |  |  |  |
| `VER-007-deployed-mirror-diff` | L3 | `DEFERRED_L3` | `diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py` | `~/tmp/cli-agent-bridge/zen-realtime-reasoning` |  |  |  |  |

> **Причина отсрочки `DEFERRED_L3` (`verification-integrity.md` §8, `acceptance-package.md` §3):** мутация живого боевого моста `~/.dsh/bridges/opencode-zen-bridge/server.py` (`127.0.0.1:9883`) запрещена до получения вердикта `ACCEPT` Совета Тимлидов (`Forbidden Scope` `handoff-architect.md`, `rollout H0..H9`). Сразу после `ACCEPT` Совета выполняется бэкап в `~/work/backups/`, синхронизация `server.py`, лестница `H0..H9` и живая heavy-path проверка с переводом строк `VER-006`/`VER-007` в `PASS` до открытия MR.

## Сырые логи независимого прогона L2 (`Clean-Room`)

### `L2-RED-sensitivity` (`l2-red.log`, `sha256=13e2b337979db4252216bf59719692869c6b0851f156e87924996aedbcbec757`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=1] [wall=15.33s]
--- STDOUT ---
..FF.FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF.F..FFFFFFFFFFFFFFFFFFFFF  [100%]
=================================== FAILURES ===================================
_ TestLegacyWatchdogAndKillpg.test_initial_status_before_1s_under_startup_gate_contention _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_initial_status_before_1s_under_startup_gate_contention>

    def test_initial_status_before_1s_under_startup_gate_contention(self) -> None:
        """RW-017: TRANSPORT=run и занятый StartupGate — первый статус не позднее 1.0 с."""
        saved_wait = server.STARTUP_WAIT_S
        server.STARTUP_WAIT_S = 2.5
        self.assertTrue(server._STARTUP_LOCK.acquire(timeout=1.0))  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
        try:
            chunks, _elapsed = self.bridge.post_stream_timed("привет")
        finally:
            server._STARTUP_LOCK.release()  # pyright: ignore[reportPrivateUsage] — причина: оракул обращается к приватному API моста
            server.STARTUP_WAIT_S = saved_wait
        reasoning = _deltas(chunks, "reasoning_content")
        statuses = [at for at, t in reasoning if "[мост]" in t]
>       self.assertTrue(statuses, chunks)
E       AssertionError: [] is not true : [(0.002934625023044646, {'id': 'chatcmpl-oczen-43738addc746', 'object': 'chat.completion.chunk', 'created': 1793069603, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': ''}}]}), (2.6339514170540497, {'id': 'chatcmpl-oczen-43738addc746', 'object': 'chat.completion.chunk', 'created': 1793069603, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'reasoning_content': 'Simple greeting.'}}]}), (2.633994875010103, {'id': 'chatcmpl-oczen-43738addc746', 'object': 'chat.completion.chunk', 'created': 1793069603, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'content': 'Привет!'}}]}), (2.8883111670147628, {'id': 'chatcmpl-oczen-43738addc746', 'object': 'chat.completion.chunk', 'created': 1793069603, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5}})]

tests/test_realtime_reasoning.py:458: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-27 05:53:23 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:53:23 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:53:26 startup_gate_timeout wait_s=2.5, starting without the gate
2026-10-27 05:53:26 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:53:26 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=2.89
____________ TestLegacyWatchdogAndKillpg.test_oexit_fields_present _____________

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_oexit_fields_present>

    def test_oexit_fields_present(self) -> None:
        """O-EXIT/v1 содержит transport/first_event_ms/ttft_ms."""
        _ = self.bridge.post_stream_timed("привет")
        log = Path(self.bridge.tmp.name, "bridge.log")
        text = log.read_text("utf-8") if log.exists() else ""
        if not text:
            text = Path(server.LOG_PATH).read_text("utf-8")
        oexit = [line for line in text.splitlines() if "O-EXIT/v1" in line]
        self.assertTrue(oexit)
>       self.assertIn("transport=", oexit[-1])
E       AssertionError: 'transport=' not found in '2026-10-27 05:53:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=0.37'

tests/test_realtime_reasoning.py:533: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-27 05:53:26 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:53:26 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:53:27 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:53:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=0.37
_ TestLegacyWatchdogAndKillpg.test_rw002_initial_status_while_waiting_spawn_limiter _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_rw002_initial_status_while_waiting_spawn_limiter>

    def test_rw002_initial_status_while_waiting_spawn_limiter(self) -> None:
        """RW-002: свободный StartupGate и задержанный лимитер не гасят начальный статус."""
    
        def delayed_acquire(*_args: object, **_kw: object) -> bool:
            time.sleep(1.2)
            return True
    
        with mock.patch.object(
            self.bridge.httpd.resilience.spawn_limiter,
            "acquire",
            side_effect=delayed_acquire,
        ):
            chunks, _ = self.bridge.post_stream_timed("привет")
        statuses = [
            (at, t)
            for at, t in _deltas(chunks, "reasoning_content")
>           if server.STATUS_INITIAL.strip() in t
               ^^^^^^^^^^^^^^^^^^^^^
        ]
E       AttributeError: module 'server' has no attribute 'STATUS_INITIAL'

tests/test_realtime_reasoning.py:482: AttributeError
----------------------------- Captured stderr call -----------------------------
2026-10-27 05:53:27 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:53:27 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:53:29 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:53:29 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 duration_s=1.57
_ TestLegacyWatchdogAndKillpg.test_slow_upstream_gets_initial_status_before_1s _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_slow_upstream_gets_initial_status_before_1s>

    def test_slow_upstream_gets_initial_status_before_1s(self) -> None:
        """Медленный апстрим: первый [мост] не позже 1.0 с (REQ-004)."""
        os.environ["FAKE_RT_MODE"] = "slow"
        chunks, _elapsed = self.bridge.post_stream_timed("медленно")
        statuses = [
            (at, t)
            for at, t in _deltas(chunks, "reasoning_content")
            if t.startswith("[мост]") or "[мост]" in t
        ]
>       self.assertTrue(statuses, "нет синтетического статуса")
E       AssertionError: [] is not true : нет синтетического статуса

tests/test_realtime_reasoning.py:442: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-27 05:53:29 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1028 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:53:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:53:31 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:53:31 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 duration_s=1.98
________ TestLegacyWatchdogAndKillpg.test_watchdog_first_event_timeout _________

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_watchdog_first_event_timeout>

    def test_watchdog_first_event_timeout(self) -> None:
        """Тишина апстрима: watchdog срабатывает, а не TIMEOUT_S=1800."""
        os.environ["FAKE_RT_MODE"] = "silent"
>       old: float = server.FIRST_EVENT_TIMEOUT_S
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'FIRST_EVENT_TIMEOUT_S'

tests/test_realtime_reasoning.py:540: AttributeError
_ TestServeTransportAndFakeServe.test_ac026_realtime_chunks_before_upstream_end _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_ac026_realtime_chunks_before_upstream_end>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_auto_fallback_to_run_and_sticky_degradation _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_auto_fallback_to_run_and_sticky_degradation>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
________ TestServeTransportAndFakeServe.test_canonical_frozen_fixtures _________

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_canonical_frozen_fixtures>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_clean_room_fake_serve_via_monkeypatched_bin _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_clean_room_fake_serve_via_monkeypatched_bin>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
____ TestServeTransportAndFakeServe.test_dynamic_config_switch_same_server _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_dynamic_config_switch_same_server>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_foreign_listener_rejected_and_startup_reaper _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_foreign_listener_rejected_and_startup_reaper>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_form_missing_title_cancels_without_step2 _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_form_missing_title_cancels_without_step2>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_fu003_usage_once_across_distinct_retry_branches _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_fu003_usage_once_across_distinct_retry_branches>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_fu010_thinking_off_omits_retry_separator _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_fu010_thinking_off_omits_retry_separator>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_fu011_cancelled_never_counts_as_success __

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_fu011_cancelled_never_counts_as_success>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
___ TestServeTransportAndFakeServe.test_helper_argv_validation_and_lease_dir ___

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_helper_argv_validation_and_lease_dir>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
________ TestServeTransportAndFakeServe.test_helper_drains_large_stderr ________

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_helper_drains_large_stderr>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_json_run_fallback_respects_total_spawn_cap _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_json_run_fallback_respects_total_spawn_cap>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_____ TestServeTransportAndFakeServe.test_json_tool_calls_are_deduplicated _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_json_tool_calls_are_deduplicated>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
____ TestServeTransportAndFakeServe.test_native_tool_and_permission_reject _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_native_tool_and_permission_reject>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_prompt_http_4xx_fail_closed_without_run_fallback _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_prompt_http_4xx_fail_closed_without_run_fallback>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_proxy_pool_advances_once_per_serve_attempt _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_proxy_pool_advances_once_per_serve_attempt>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_retry_separator_once_and_delivery_barrier_is_monotonic _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_retry_separator_once_and_delivery_barrier_is_monotonic>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_rw001_delivery_survives_unavailable_or_limiter _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw001_delivery_survives_unavailable_or_limiter>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_rw003_mkdtemp_failure_is_serve_unavailable _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw003_mkdtemp_failure_is_serve_unavailable>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_rw006_invalid_utf8_falls_back_and_recovers _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw006_invalid_utf8_falls_back_and_recovers>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_rw007_split_interrupted_marker_at_every_boundary _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw007_split_interrupted_marker_at_every_boundary>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_rw008_provider_secrets_hidden_in_sse_json_and_log _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_rw008_provider_secrets_hidden_in_sse_json_and_log>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_serve_400_fails_closed_without_health_increment _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_serve_400_fails_closed_without_health_increment>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_____ TestServeTransportAndFakeServe.test_serve_env_sanitized_all_branches _____

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_serve_env_sanitized_all_branches>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_____ TestServeTransportAndFakeServe.test_serve_health_and_fallback_table ______

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_serve_health_and_fallback_table>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_slow_pause_streams_all_deltas_and_single_initial_status _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_slow_pause_streams_all_deltas_and_single_initial_status>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_slow_serve_gets_status_and_no_status_on_fast _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_slow_serve_gets_status_and_no_status_on_fast>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_timeout_and_client_gone_never_count_as_success _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_timeout_and_client_gone_never_count_as_success>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
_ TestServeTransportAndFakeServe.test_tool_choice_preserved_in_step_recovery_prompt _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_tool_choice_preserved_in_step_recovery_prompt>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
______ TestServeTransportAndFakeServe.test_tool_text_split_across_deltas _______

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_tool_text_split_across_deltas>

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
>       self.saved_cfg = server.DYNAMIC_CONFIG_PATH
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'DYNAMIC_CONFIG_PATH'

tests/test_realtime_reasoning.py:575: AttributeError
___________ TestReworkUnits.test_disable_file_overrides_forced_serve ___________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_disable_file_overrides_forced_serve>

    def test_disable_file_overrides_forced_serve(self) -> None:
        """FU-013: файл отключения важнее принудительного выбора serve."""
        with tempfile.TemporaryDirectory() as name:
            disable = Path(name) / "disable-serve"
            _ = disable.write_text("1")
            with mock.patch.dict(
                os.environ,
                {
                    "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
                    "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE": str(disable),
                    "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": "1",
                },
            ):
>               self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: проверяется приоритет аварийного файла отключения
                                 ^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_select_transport'

tests/test_realtime_reasoning.py:1392: AttributeError
________________ TestReworkUnits.test_elf_magic_and_tool_status ________________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_elf_magic_and_tool_status>

    def test_elf_magic_and_tool_status(self) -> None:
        """FU-001/FU-002: 4 случайных байта не ELF, статус tool из типа события."""
>       state = server._ServeToolState()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                ^^^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute '_ServeToolState'

tests/test_realtime_reasoning.py:1420: AttributeError
_ TestReworkUnits.test_fu001_http_checks_deadline_and_cancellation_before_connect _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_fu001_http_checks_deadline_and_cancellation_before_connect>

    def test_fu001_http_checks_deadline_and_cancellation_before_connect(self) -> None:
        """FU-001: просроченный бюджет и ушедший клиент запрещают даже соединение HTTP."""
>       call = server._serve_http  # pyright: ignore[reportPrivateUsage] — причина: проверяется граница фазы управляющего HTTP-вызова
               ^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute '_serve_http'

tests/test_realtime_reasoning.py:1445: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='bash') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1506: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='read') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1506: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='edit') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1506: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='list') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1506: AttributeError
_ TestReworkUnits.test_rw004_native_calls_share_canonical_mapping (name='multiedit') _

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw004_native_calls_share_canonical_mapping>

    def test_rw004_native_calls_share_canonical_mapping(self) -> None:
        """RW-004: bash/read/edit/list/multiedit используют ровно канонический fit_args."""
        tools: list[dict[str, object]] = [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "parameters": {
                        "type": "object",
                        "properties": props,
                        "required": list(props),
                    },
                },
            }
            for name, props in (
                (
                    "bash",
                    {"command": {"type": "string"}, "description": {"type": "string"}},
                ),
                ("read", {"file_path": {"type": "string"}}),
                (
                    "edit",
                    {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                ),
            )
        ]
        mapper = server._native_to_tool_calls  # pyright: ignore[reportPrivateUsage] — причина: канонический преобразователь run служит оракулом адаптера serve
        canonical = cast(
            Callable[
                [object, object, list[dict[str, object]]], list[dict[str, object]]
            ],
            mapper,
        )
        for name, args in (
            ("bash", {"command": "pwd"}),
            ("read", {"filePath": "/tmp/a"}),
            ("edit", {"filePath": "/tmp/a", "oldString": "a", "newString": "b"}),
            ("list", {"path": "/tmp"}),
            (
                "multiedit",
                {
                    "filePath": "/tmp/a",
                    "edits": [
                        {"oldString": "a", "newString": "b"},
                        {"oldString": "c", "newString": "d"},
                    ],
                },
            ),
        ):
            with self.subTest(name=name):
                expected = canonical(name, args, tools)
>               adapter = server._native_call_as_dsh  # pyright: ignore[reportPrivateUsage] — причина: сверяется адаптер serve с преобразователем run
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^
E               AttributeError: module 'server' has no attribute '_native_call_as_dsh'

tests/test_realtime_reasoning.py:1506: AttributeError
___________ TestReworkUnits.test_rw005_stop_group_after_leader_exit ____________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw005_stop_group_after_leader_exit>

    def test_rw005_stop_group_after_leader_exit(self) -> None:
        """RW-005: завершившийся лидер не мешает убить живого потомка его группы."""
        with tempfile.TemporaryDirectory() as name:
            pidfile = Path(name) / "child.pid"
            code = (
                "import os,signal,time; from pathlib import Path; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                f"Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(30)"
            )
            parent = "import subprocess,sys,time; from pathlib import Path; subprocess.Popen([sys.executable,'-c',sys.argv[1]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); p=Path(sys.argv[2]); deadline=time.monotonic()+3; "
            parent += (
                "\nwhile not p.exists() and time.monotonic()<deadline: time.sleep(0.01)"
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", parent, code, str(pidfile)],
                text=True,
                start_new_session=True,
            )
            try:
                _ = proc.wait(timeout=5)
                self.assertTrue(pidfile.exists())
                child = int(pidfile.read_text())
                server._stop_proc(proc)  # pyright: ignore[reportPrivateUsage] — причина: проверяется остановка осиротевшего потомка завершившегося лидера
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    try:
                        os.kill(child, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.02)
                else:
>                   self.fail("потомок пережил остановку группы")
E                   AssertionError: потомок пережил остановку группы

tests/test_realtime_reasoning.py:1547: AssertionError
______ TestReworkUnits.test_rw008_error_payload_masks_message_and_detail _______

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_rw008_error_payload_masks_message_and_detail>

    def test_rw008_error_payload_masks_message_and_detail(self) -> None:
        """RW-008: общий конструктор ошибки очищает оба поля до сериализации."""
        secret = "sk-" + "b" * 32
        payload = server._error_payload(secret, "Bearer hidden-detail")  # pyright: ignore[reportPrivateUsage] — причина: проверяется последняя граница очистки клиентской ошибки
        encoded = json.dumps(payload)
>       self.assertNotIn(secret, encoded)
E       AssertionError: 'sk-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb' unexpectedly found in '{"error": {"message": "sk-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "type": "proxy_error", "code": 502, "detail": "Bearer hidden-detail"}}'

tests/test_realtime_reasoning.py:1560: AssertionError
_______ TestReworkUnits.test_service_events_ignored_and_foreign_session ________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_service_events_ignored_and_foreign_session>

    def test_service_events_ignored_and_foreign_session(self) -> None:
        """RW-029/RW-031: служебные события — None, sessionID сохраняется в payload."""
        self.assertIsNone(
>           server._map_serve_event({"type": "integration.updated", "data": {}})  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
            ^^^^^^^^^^^^^^^^^^^^^^^
        )
E       AttributeError: module 'server' has no attribute '_map_serve_event'

tests/test_realtime_reasoning.py:1321: AttributeError
__________ TestReworkUnits.test_spawn_cap_and_proxy_rotation_helpers ___________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_spawn_cap_and_proxy_rotation_helpers>

    def test_spawn_cap_and_proxy_rotation_helpers(self) -> None:
        """RW-001/RW-013: can_spawn ограничен MAX_TOTAL_SPAWNS, пул прокси ротируется."""
        res = server._Resilience()  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        attempts = server._RequestAttempts(res, time.monotonic() + 60.0)  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
        for _i in range(server.MAX_TOTAL_SPAWNS):
>           self.assertTrue(attempts.can_spawn())
                            ^^^^^^^^^^^^^^^^^^
E           AttributeError: '_RequestAttempts' object has no attribute 'can_spawn'

tests/test_realtime_reasoning.py:1413: AttributeError
_____________ TestReworkUnits.test_surrogate_pair_and_broken_json ______________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_surrogate_pair_and_broken_json>

    def test_surrogate_pair_and_broken_json(self) -> None:
        """RW-005: суррогатная пара декодируется, битый JSON serve — ServeProtocolError."""
>       parsed = server._loads_object('{"emoji": "\ud83d\ude00"}')  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                 ^^^^^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute '_loads_object'. Did you mean: '_loads_lenient'?

tests/test_realtime_reasoning.py:1308: AttributeError
____________________ TestReworkUnits.test_transport_matrix _____________________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_transport_matrix>

    def test_transport_matrix(self) -> None:
        """RW-025: TRANSPORT=run, override 0, disable-файл и опечатка дают run."""
        with mock.patch.dict(
            os.environ, {"OPENCODE_ZEN_BRIDGE_TRANSPORT": "run"}, clear=False
        ):
>           self.assertEqual(server._select_transport(), "run")  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                             ^^^^^^^^^^^^^^^^^^^^^^^^
E           AttributeError: module 'server' has no attribute '_select_transport'

tests/test_realtime_reasoning.py:1364: AttributeError
____________ TestReworkUnits.test_whitespace_delta_preserved_in_map ____________

self = <tests.test_realtime_reasoning.TestReworkUnits testMethod=test_whitespace_delta_preserved_in_map>

    def test_whitespace_delta_preserved_in_map(self) -> None:
        """RW-007: пробельная дельта не отбрасывается маппером."""
>       mapped = server._map_serve_event(  # pyright: ignore[reportPrivateUsage] — причина: тест намеренно обращается к приватному API моста
                 ^^^^^^^^^^^^^^^^^^^^^^^
            {
                "type": "session.reasoning.delta",
                "data": {"sessionID": "s1", "delta": "\n\n"},
            }
        )
E       AttributeError: module 'server' has no attribute '_map_serve_event'

tests/test_realtime_reasoning.py:1336: AttributeError
_________ TestServeAttemptOracles.test_attempt_rotates_proxy_pool_once _________

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_attempt_rotates_proxy_pool_once>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
______ TestServeAttemptOracles.test_never_event_gives_first_event_timeout ______

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_never_event_gives_first_event_timeout>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
________ TestServeAttemptOracles.test_prompt_http_4xx_fails_closed_fast ________

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_prompt_http_4xx_fails_closed_fast>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
_____ TestServeAttemptOracles.test_silent_model_gives_first_token_timeout ______

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_silent_model_gives_first_token_timeout>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
__ TestServeAttemptOracles.test_sse_pause_over_half_second_keeps_stream_alive __

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_sse_pause_over_half_second_keeps_stream_alive>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
_____________ TestServeAttemptOracles.test_stall_after_first_token _____________

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_stall_after_first_token>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
__ TestServeAttemptOracles.test_startup_gate_released_before_generation_ends ___

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_startup_gate_released_before_generation_ends>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
____ TestServeAttemptOracles.test_text_tool_call_closes_step_on_step_finish ____

self = <tests.test_realtime_reasoning.TestServeAttemptOracles testMethod=test_text_tool_call_closes_step_on_step_finish>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
___ TestSpawnAndLeaseOracles.test_client_gone_check_detects_reset_and_close ____

self = <tests.test_realtime_reasoning.TestSpawnAndLeaseOracles testMethod=test_client_gone_check_detects_reset_and_close>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
_ TestSpawnAndLeaseOracles.test_lease_cleanup_confirms_sigkill_in_separate_window _

self = <tests.test_realtime_reasoning.TestSpawnAndLeaseOracles testMethod=test_lease_cleanup_confirms_sigkill_in_separate_window>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
_______ TestSpawnAndLeaseOracles.test_spawn_failures_leave_no_leftovers ________

self = <tests.test_realtime_reasoning.TestSpawnAndLeaseOracles testMethod=test_spawn_failures_leave_no_leftovers>

    @override
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmpdir.name)
        fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        self.saved_bin = server.OPENCODE_BIN
>       self.saved_lease = server.LEASE_DIR
                           ^^^^^^^^^^^^^^^^
E       AttributeError: module 'server' has no attribute 'LEASE_DIR'

tests/test_realtime_reasoning.py:1609: AttributeError
__________ TestHelperProcess.test_errno_imported_before_helper_branch __________

self = <tests.test_realtime_reasoning.TestHelperProcess testMethod=test_errno_imported_before_helper_branch>

    def test_errno_imported_before_helper_branch(self) -> None:
        """RW-001: errno связан до ветки --serve-helper."""
        tree = ast.parse(Path(server.__file__).read_text("utf-8"))
>       branch = next(
            n
            for n in tree.body
            if isinstance(n, ast.If)
            and ast.unparse(n.test).endswith("['--serve-helper']")
        )
E       StopIteration

tests/test_realtime_reasoning.py:1887: StopIteration
__ TestHelperProcess.test_helper_kills_surviving_group_and_removes_lease_last __

self = <tests.test_realtime_reasoning.TestHelperProcess testMethod=test_helper_kills_surviving_group_and_removes_lease_last>

    def test_helper_kills_surviving_group_and_removes_lease_last(self) -> None:
        """RW-005: serve вышел, внук игнорирует SIGTERM -> SIGKILL группе, lease удалён после смерти."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            fake = _write_exe(tmp, "opencode-fake", FAKE_HELPER_SERVE)
            gc_file = tmp / "grandchild.pid"
            env = dict(os.environ)
            env["GRANDCHILD_FILE"] = str(gc_file)
            proc = subprocess.Popen(
                self._helper_cmd(tmp, str(fake)),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                start_new_session=True,
            )
            try:
                # lifeline (stdin) остаётся открытым: helper завершается сам, когда serve вышел.
                _ = proc.wait(timeout=30)
            finally:
                if proc.poll() is None:
                    proc.kill()
                if proc.stdin is not None:
                    proc.stdin.close()
                for stream in (proc.stdout, proc.stderr):
                    if stream is not None:
                        stream.close()
>           self.assertEqual(proc.returncode, 0)
E           AssertionError: 2 != 0

tests/test_realtime_reasoning.py:1945: AssertionError
_____ TestHelperProcess.test_helper_survives_bad_stdin_without_name_error ______

self = <tests.test_realtime_reasoning.TestHelperProcess testMethod=test_helper_survives_bad_stdin_without_name_error>

    def test_helper_survives_bad_stdin_without_name_error(self) -> None:
        """RW-001: EBADF на select lifeline обрабатывается без NameError, lease снимается."""
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            argv = " ".join(f"'{a}'" for a in self._helper_cmd(tmp, "/bin/true"))
            proc = subprocess.run(
                ["/bin/sh", "-c", f"exec {argv} <&-"],
                capture_output=True,
                text=True,
                timeout=20,
                start_new_session=True,
            )
            self.assertNotIn("NameError", proc.stderr)
>           self.assertEqual(proc.returncode, 0, proc.stderr)
E           AssertionError: 2 != 0 : OPENCODE_ZEN_BRIDGE_KEY is required; refusing to start

tests/test_realtime_reasoning.py:1914: AssertionError
=========================== short test summary info ============================
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_initial_status_before_1s_under_startup_gate_contention
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_oexit_fields_present
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_rw002_initial_status_while_waiting_spawn_limiter
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_slow_upstream_gets_initial_status_before_1s
FAILED tests/test_realtime_reasoning.py::TestLegacyWatchdogAndKillpg::test_watchdog_first_event_timeout
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_ac026_realtime_chunks_before_upstream_end
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_auto_fallback_to_run_and_sticky_degradation
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_canonical_frozen_fixtures
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_clean_room_fake_serve_via_monkeypatched_bin
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_dynamic_config_switch_same_server
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_foreign_listener_rejected_and_startup_reaper
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_form_missing_title_cancels_without_step2
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu003_usage_once_across_distinct_retry_branches
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu010_thinking_off_omits_retry_separator
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu011_cancelled_never_counts_as_success
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_helper_argv_validation_and_lease_dir
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_helper_drains_large_stderr
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_json_run_fallback_respects_total_spawn_cap
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_json_tool_calls_are_deduplicated
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_native_tool_and_permission_reject
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_prompt_http_4xx_fail_closed_without_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_proxy_pool_advances_once_per_serve_attempt
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_retry_separator_once_and_delivery_barrier_is_monotonic
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw001_delivery_survives_unavailable_or_limiter
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw003_mkdtemp_failure_is_serve_unavailable
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw006_invalid_utf8_falls_back_and_recovers
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw007_split_interrupted_marker_at_every_boundary
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw008_provider_secrets_hidden_in_sse_json_and_log
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_400_fails_closed_without_health_increment
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_env_sanitized_all_branches
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_health_and_fallback_table
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_slow_pause_streams_all_deltas_and_single_initial_status
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_slow_serve_gets_status_and_no_status_on_fast
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_timeout_and_client_gone_never_count_as_success
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_tool_choice_preserved_in_step_recovery_prompt
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_tool_text_split_across_deltas
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_disable_file_overrides_forced_serve
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_elf_magic_and_tool_status
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_fu001_http_checks_deadline_and_cancellation_before_connect
SUBFAILED(name='bash') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
SUBFAILED(name='read') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
SUBFAILED(name='edit') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
SUBFAILED(name='list') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
SUBFAILED(name='multiedit') tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_rw005_stop_group_after_leader_exit
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_rw008_error_payload_masks_message_and_detail
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_service_events_ignored_and_foreign_session
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_spawn_cap_and_proxy_rotation_helpers
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_surrogate_pair_and_broken_json
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_transport_matrix
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_whitespace_delta_preserved_in_map
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_attempt_rotates_proxy_pool_once
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_never_event_gives_first_event_timeout
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_prompt_http_4xx_fails_closed_fast
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_silent_model_gives_first_token_timeout
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_sse_pause_over_half_second_keeps_stream_alive
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_stall_after_first_token
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_startup_gate_released_before_generation_ends
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_text_tool_call_closes_step_on_step_finish
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_client_gone_check_detects_reset_and_close
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_lease_cleanup_confirms_sigkill_in_separate_window
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_spawn_failures_leave_no_leftovers
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_errno_imported_before_helper_branch
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_helper_kills_surviving_group_and_removes_lease_last
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_helper_survives_bad_stdin_without_name_error
65 failed, 6 passed in 14.83s

--- STDERR ---
```

### `VER-004-packet-command` (`l2-green-ver004-packet.log`, `sha256=28cc596d5832e0b715a0df332f616aa848942a1d79b4428a5d6314358e0677eb`)
```text
$ /bin/zsh -lc python3 - <<'VER004'
import ast, collections, hashlib, json, re, subprocess, tempfile
from pathlib import Path
root = Path.cwd().resolve()
bridge = root / 'bridges/opencode-zen-bridge'
files = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']
assert all(f.is_file() for f in files), 'all three target files must exist after Stage3'
ruff = ['uvx','--from','ruff==0.17.2','ruff']
def run(args, **kw):
    return subprocess.run(args, check=True, **kw)
def changed_ranges(file):
    rel = str(file.relative_to(root))
    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)
    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.
    result = []
    for line in diff.splitlines():
        m = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
        if m:
            start = int(m.group(1)); count = int(m.group(2) or '1')
            if count: result.append((start, start + count - 1))
    return result

# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.
FROZEN = {
    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',
    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',
    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',
}
baseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)
def frozen_slices(raw):
    lines = raw.splitlines(keepends=True)
    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}
    assert set(nodes)==set(FROZEN)
    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}
baseline_slices = frozen_slices(baseline_raw)
def assert_frozen(candidate=files[0]):
    candidate_slices = frozen_slices(candidate.read_bytes())
    for name, expected in FROZEN.items():
        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)
        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)
        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)
    return candidate_slices
candidate_slices = assert_frozen()
server_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)
for line in server_diff.splitlines():
    match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',line)
    if not match: continue
    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')
    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:
        for name,(lo,hi,_) in table.items():
            # Zero-count insert/delete anchors represent the boundary after start.
            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)
            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)
# Public module constant/read API remains intact; compatibility test file is frozen.
tree = ast.parse(files[0].read_bytes())
assignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]
assert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'
assert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)
assert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))
assert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'
helper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == "sys.argv[1:2] == ['--serve-helper']"), None)
assert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'
heavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}
def imported_names(node):
    if isinstance(node, ast.Import): return {a.name for a in node.names}
    if isinstance(node, ast.ImportFrom): return {node.module}
    return set()
assert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])
assert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)
assert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'
assert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))
run(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)

ranges = {f: changed_ranges(f) for f in files[:2]}
# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.
run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)
for f in files[:2]:
    for start, end in ranges[f]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)
assert_frozen()
# Exercise actual write-mode range formatting only on a disposable copy.
with tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:
    formatted_copy = Path(format_dir) / 'server.py'
    formatted_copy.write_bytes(files[0].read_bytes())
    for start, end in ranges[files[0]]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)
    assert formatted_copy.read_bytes() == files[0].read_bytes()
    assert_frozen(formatted_copy)
    assert_frozen()
    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})
# Full-file lint on all three. Only inherited E402 import site is excepted on server.
lint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)
assert lint.returncode in (0,1), lint.stderr
findings = json.loads(lint.stdout)
lines = files[0].read_text().splitlines()
assert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings
assert sum(x['code']=='E402' for x in findings) <= 1
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)
# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.
project = None
try:
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:
        project = Path(tmp.name)
        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)
    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)
    assert b.returncode in (0,1), b.stderr
    report = json.loads(b.stdout)
    ds = report['generalDiagnostics']
    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds
    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}
    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}
    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']
    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))
    print('BASEDPYRIGHT summary',report['summary'])
    print('SERVER dict(counts)',dict(counts))
    print('SERVER warningCount',len(warnings(files[0])))
    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)
    assert len(warnings(files[0]))<=720, len(warnings(files[0]))
    assert len(warnings(files[1]))<=194, len(warnings(files[1]))
    # New test file: zero warnings as well as zero errors, thus zero Any.
    assert not byfile[files[2]], byfile[files[2]]
    for f in files[:2]:
        for x in byfile[f]:
            line = x['range']['start']['line']+1
            if any(lo<=line<=hi for lo,hi in ranges[f]):
                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x
    # Do not introduce Any annotations/type ignores in added code in either legacy file.
    for f in files[:2]:
        src = f.read_text().splitlines()
        for lo,hi in ranges[f]:
            for line in src[lo-1:hi]:
                assert not re.search(r'\bAny\b|type:\s*ignore|pyright:\s*ignore|#\s*noqa|#\s*fmt:\s*off',line), (f,line)
    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)
    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))
finally:
    if project is not None: project.unlink(missing_ok=True)
VER004
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=22.53s]
--- STDOUT ---
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
All checks passed!
All checks passed!
PASS write-mode frozen hashes {'_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31', '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6', '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3'}
BASEDPYRIGHT summary {'filesAnalyzed': 3, 'errorCount': 0, 'warningCount': 760, 'informationCount': 0, 'timeInSec': 3.928}
SERVER dict(counts) {'reportExplicitAny': 123, 'reportAny': 117, 'reportUnusedCallResult': 35, 'reportUnknownMemberType': 72, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 48, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}
SERVER warningCount 591
PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts {'reportExplicitAny': 123, 'reportAny': 117, 'reportUnusedCallResult': 35, 'reportUnknownMemberType': 72, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 48, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}

--- STDERR ---
test_env_default_is_dynamic (tests.test_catalog_mode.ModeFromEnvironmentTest) ... ok
test_env_static_and_legacy (tests.test_catalog_mode.ModeFromEnvironmentTest) ... ok
test_default_in_tests_is_dynamic (tests.test_catalog_mode.ModeNormalizationTest) ... ok
test_modes (tests.test_catalog_mode.ModeNormalizationTest) ... ok
test_aliases_still_work_in_static (tests.test_catalog_mode.StaticModeTest) ... ok
test_static_never_reloads_by_mtime (tests.test_catalog_mode.StaticModeTest) ... ok
test_static_routes_through_background_service (tests.test_catalog_mode.StaticModeTest) ... ok
test_static_uses_embedded_snapshot_and_ignores_state_file (tests.test_catalog_mode.StaticModeTest) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.186s

OK
```

### `VER-004-ruff-format-new` (`l2-green-ver004-ruff-format-new.log`, `sha256=791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.04s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-001-pytest` (`l2-green-ver001-pytest.log`, `sha256=b682638b87a7442fa90c9f3060cc69387492a885fd11d61f3a9e440f0559cb29`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=176.83s]
--- STDOUT ---
......................... [  5%]
..................................................................................................................................................................................................... [ 49%]
.............................................................. [ 63%]
........................................................................ [ 80%]
............................................................... [ 94%]
..........................                                           [100%]
445 passed, 3185 subtests passed in 176.66s (0:02:56)

--- STDERR ---
```

### `VER-002-unittest` (`l2-green-ver002-unittest.log`, `sha256=13ac0fb9d2f6096771600115a08befc18d2af1c30c8c969f0bbe0c0aa71edaf8`)
```text
$ python3 -m unittest discover -s tests -p test_*.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=174.41s]
--- STDOUT ---

--- STDERR ---
..........2026-10-27 05:57:10 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 05:57:10 O-EXIT/v1 mode=json model=jev-1.13 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 05:57:10 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 05:57:10 O-EXIT/v1 mode=json model=jev-1.13-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 05:57:10 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 05:57:10 O-EXIT/v1 mode=json model=nemotron-3-ultra-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 05:57:10 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 05:57:10 O-EXIT/v1 mode=json model=test status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 05:57:10 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 05:57:10 O-EXIT/v1 mode=json model=claude-opus-5-5-backup status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 05:57:10 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 05:57:10 O-EXIT/v1 mode=json model=deepseek-v4.1-flash status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-27 05:57:10 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-27 05:57:10 O-EXIT/v1 mode=json model=claude-haiku-5-5 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
.2026-10-27 05:57:10 http "GET /health HTTP/1.1" 200 -
.2026-10-27 05:57:10 http "GET /v1/models HTTP/1.1" 200 -
.2026-10-27 05:57:10 http "GET /v1/models HTTP/1.1" 401 -
........................2026-10-27 05:57:12 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:12 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:13 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=1
2026-10-27 05:57:13 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=113 ttft_ms=113 transport_history=['run'] duration_s=0.38
.2026-10-27 05:57:13 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:14 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 05:57:14 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'Error: Unexpected error\ndatabase is locked'
2026-10-27 05:57:14 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:15 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=2
2026-10-27 05:57:15 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:15 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.92
.2026-10-27 05:57:15 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:15 exec: early provider error (waiting for CLI recovery)
2026-10-27 05:57:16 exec cli failed rc=1 state=provider_error stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 05:57:16 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'HTTP 429: FreeUsageLimitError'
2026-10-27 05:57:16 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:16 exec: early provider error (waiting for CLI recovery)
2026-10-27 05:57:17 exec cli failed rc=1 state=provider_error stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 05:57:17 exec failed rc=1 without output, retry 2/2 total_spawns=2/3: 'HTTP 429: FreeUsageLimitError'
2026-10-27 05:57:17 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:17 exec: early provider error (waiting for CLI recovery)
2026-10-27 05:57:18 exec cli failed rc=1 state=provider_error stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 05:57:18 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 05:57:18 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.99
.2026-10-27 05:57:18 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:19 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: fatal boom xyz'
2026-10-27 05:57:19 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'Error: fatal boom xyz'
2026-10-27 05:57:19 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:20 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: fatal boom xyz'
2026-10-27 05:57:20 exec failed rc=1 without output, retry 2/2 total_spawns=2/3: 'Error: fatal boom xyz'
2026-10-27 05:57:20 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:21 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: fatal boom xyz'
2026-10-27 05:57:21 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 05:57:21 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.98
.2026-10-27 05:57:21 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:21 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:21 stream provider error: HTTP 403: free tier denied
2026-10-27 05:57:21 stream: early provider error (waiting for CLI recovery)
2026-10-27 05:57:22 stream cli failed rc=1 stderr_tail='HTTP 403: free tier denied'
2026-10-27 05:57:22 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=0 total_spawns=1
2026-10-27 05:57:22 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=764 ttft_ms=None transport_history=['run'] duration_s=1.03
..2026-10-27 05:57:22 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free --standalone prompt_chars=8 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:23 exec timeout after 1s, killing proc group
/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/tests/test_cli_failure.py:267: ResourceWarning: unclosed file <_io.TextIOWrapper name=9 encoding='utf-8'>
  out = server.Run("muse-spark-1.3-contributor-free", "Проверка", "", Path(self.tmp.name) / "ws")._execute_once()
ResourceWarning: Enable tracemalloc to get the object allocation traceback
/private/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge/tests/test_cli_failure.py:267: ResourceWarning: unclosed file <_io.TextIOWrapper name=7 encoding='utf-8'>
  out = server.Run("muse-spark-1.3-contributor-free", "Проверка", "", Path(self.tmp.name) / "ws")._execute_once()
ResourceWarning: Enable tracemalloc to get the object allocation traceback
.2026-10-27 05:57:23 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:23 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:23 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 05:57:23 stream retry 1/2 after cli failure without output
2026-10-27 05:57:23 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 05:57:24 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=2
2026-10-27 05:57:24 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=7 transport=run first_event_ms=1042 ttft_ms=1042 transport_history=['run'] duration_s=1.30
.2026-10-27 05:57:24 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:24 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:25 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 05:57:25 stream retry 1/2 after cli failure without output
2026-10-27 05:57:25 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 05:57:26 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 05:57:26 stream retry 2/2 after cli failure without output
2026-10-27 05:57:26 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-27 05:57:27 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 05:57:27 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-27 05:57:27 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.97
.2026-10-27 05:57:27 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:27 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:28 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 05:57:28 stream retry 1/2 after cli failure without output
2026-10-27 05:57:28 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 05:57:29 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 05:57:29 stream retry 2/2 after cli failure without output
2026-10-27 05:57:29 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-27 05:57:30 stream cli failed rc=1 stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-27 05:57:30 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-27 05:57:30 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.98
.2026-10-27 05:57:30 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:30 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:31 stream provider error: HTTP 429: FreeUsageLimitError
2026-10-27 05:57:31 stream: early provider error (waiting for CLI recovery)
2026-10-27 05:57:31 stream cli failed rc=1 stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 05:57:31 stream retry 1/2 after cli failure without output
2026-10-27 05:57:31 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 05:57:32 stream provider error: HTTP 429: FreeUsageLimitError
2026-10-27 05:57:32 stream: early provider error (waiting for CLI recovery)
2026-10-27 05:57:32 stream cli failed rc=1 stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 05:57:32 stream retry 2/2 after cli failure without output
2026-10-27 05:57:32 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-27 05:57:33 stream provider error: HTTP 429: FreeUsageLimitError
2026-10-27 05:57:33 stream: early provider error (waiting for CLI recovery)
2026-10-27 05:57:33 stream cli failed rc=1 stderr_tail='HTTP 429: FreeUsageLimitError'
2026-10-27 05:57:33 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-27 05:57:33 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=780 ttft_ms=None transport_history=['run'] duration_s=3.04
.2026-10-27 05:57:33 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:33 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:34 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 05:57:34 stream retry 1/2 after cli failure without output
2026-10-27 05:57:34 stream exec retry=0 fail_retries=1 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=1/3
2026-10-27 05:57:35 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 05:57:35 stream retry 2/2 after cli failure without output
2026-10-27 05:57:35 stream exec retry=0 fail_retries=2 model=opencode/muse-spark-1.3-contributor-free prompt_chars=32 total_spawns=2/3
2026-10-27 05:57:36 stream cli failed rc=1 stderr_tail='Error: fatal boom xyz'
2026-10-27 05:57:36 stream failed model=muse-spark-1.3-contributor-free rc=1 fail_retries=2 total_spawns=3
2026-10-27 05:57:36 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.96
.2026-10-27 05:57:36 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:36 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:37 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=1
2026-10-27 05:57:37 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=1187 ttft_ms=1187 transport_history=['run'] duration_s=1.45
.2026-10-27 05:57:37 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmp4jerdega/ws
2026-10-27 05:57:37 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:38 stream timeout after 1s, killing proc group
2026-10-27 05:57:38 stream failed model=muse-spark-1.3-contributor-free rc=-15 fail_retries=0 total_spawns=1
2026-10-27 05:57:38 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=timeout rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.02
...............................................................................2026-10-27 05:57:46 tool_call_recovered extra_braces=1
.2026-10-27 05:57:46 tool_call_recovered extra_braces=1
.2026-10-27 05:57:46 tool_call_recovered extra_braces=1
2026-10-27 05:57:46 tool_call_recovered extra_braces=1
2026-10-27 05:57:46 tool_call_recovered extra_braces=1
2026-10-27 05:57:46 tool_call_recovered extra_braces=1
..2026-10-27 05:57:46 tool_call_recovered extra_braces=1
2026-10-27 05:57:46 tool_call_recovered extra_braces=1
2026-10-27 05:57:46 tool_call_recovered extra_braces=2
2026-10-27 05:57:46 tool_call_recovered extra_braces=2
2026-10-27 05:57:46 tool_call_recovered extra_braces=3
2026-10-27 05:57:46 tool_call_recovered extra_braces=3
2026-10-27 05:57:46 tool_call_recovered extra_braces=3
2026-10-27 05:57:46 tool_call_recovered extra_braces=3
2026-10-27 05:57:46 tool_call_recovered extra_braces=16
2026-10-27 05:57:46 tool_call_recovered extra_braces=16
............2026-10-27 05:57:46 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmpz9rbdjle/ws
2026-10-27 05:57:47 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 05:57:47 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 05:57:47 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-27 05:57:47 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=14047 cwd=/var/folders/2f/***/T/tmpz9rbdjle/ws
2026-10-27 05:57:47 exec: step with tool call finished, stopping opencode run
2026-10-27 05:57:47 opencode built-in tool event: tool=bash status=error mapped=True as=['bash']
2026-10-27 05:57:47 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=1 out_chars=15 retries=1 total_spawns=2
2026-10-27 05:57:47 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:47 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=1 out_chars=15 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.10
.2026-10-27 05:57:47 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmpz9rbdjle/ws
2026-10-27 05:57:48 exec: step with tool call finished, stopping opencode run
2026-10-27 05:57:48 opencode built-in tool event: tool=read status=error mapped=True as=['read']
2026-10-27 05:57:48 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-27 05:57:48 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-27 05:57:48 dropped duplicate tool call todo_write
2026-10-27 05:57:48 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-27 05:57:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:48 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.01
.2026-10-27 05:57:48 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmpz9rbdjle/ws
2026-10-27 05:57:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:49 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 05:57:50 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 05:57:50 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=14047 total_spawns=1/3
2026-10-27 05:57:50 opencode built-in tool event: tool=bash status=error mapped=True as=['bash']
2026-10-27 05:57:50 stream: step with tool call finished, stopping opencode run
2026-10-27 05:57:50 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=1 out_chars=15 emulate_tools=True retries=1 total_spawns=2
2026-10-27 05:57:50 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=1 out_chars=15 transport=run first_event_ms=974 ttft_ms=974 transport_history=['run'] duration_s=2.00
.2026-10-27 05:57:50 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=13385 cwd=/var/folders/2f/***/T/tmpz9rbdjle/ws
2026-10-27 05:57:50 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:51 opencode built-in tool event: tool=read status=error mapped=True as=['read']
2026-10-27 05:57:51 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-27 05:57:51 opencode built-in tool event: tool=todowrite status=error mapped=True as=['todo_write']
2026-10-27 05:57:51 stream dropped duplicate tool call todo_write
2026-10-27 05:57:51 stream: step with tool call finished, stopping opencode run
2026-10-27 05:57:51 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:57:51 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=996 ttft_ms=None transport_history=['run'] duration_s=1.00
....2026-10-27 05:57:56 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:57:56 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:56 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:57:56 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=108 ttft_ms=108 transport_history=['run'] duration_s=0.37
..2026-10-27 05:57:57 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:57:57 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:57:59 startup_gate_timeout wait_s=2.5, starting without the gate
2026-10-27 05:58:00 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:58:00 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=2625 ttft_ms=2625 transport_history=['run'] duration_s=2.88
.2026-10-27 05:58:00 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:00 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:00 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:58:00 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=121 ttft_ms=121 transport_history=['run'] duration_s=0.38
..2026-10-27 05:58:01 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:01 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:02 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:58:02 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=1315 ttft_ms=1315 transport_history=['run'] duration_s=1.58
.2026-10-27 05:58:03 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1028 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:03 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:05 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:58:05 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=run first_event_ms=1712 ttft_ms=1712 transport_history=['run'] duration_s=1.97
.2026-10-27 05:58:05 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1026 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:05 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:07 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1026 total_spawns=1/3
2026-10-27 05:58:09 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1026 total_spawns=2/3
2026-10-27 05:58:10 retry denied (first_event_timeout): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 05:58:10 stream failed model=muse-spark-1.3-contributor-free rc=-15 fail_retries=0 total_spawns=3
2026-10-27 05:58:10 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=first_event_timeout rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=5.56
.....2026-10-27 05:58:11 circuit_breaker state=OPEN failures=1 cooldown_s=0.0
2026-10-27 05:58:11 circuit_breaker state=HALF_OPEN
2026-10-27 05:58:11 circuit_breaker state=CLOSED
.................2026-10-27 05:58:27 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1125 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:27 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:29 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=458 ttft_ms=458 transport_history=['serve'] duration_s=1.27
.2026-10-27 05:58:29 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:30 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1034 total_spawns=1/3
2026-10-27 05:58:31 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=2
2026-10-27 05:58:31 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=0 signal=0 tools=0 out_chars=13 transport=run first_event_ms=2269 ttft_ms=2269 transport_history=['serve', 'run'] duration_s=2.52
2026-10-27 05:58:31 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:31 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:32 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1034 total_spawns=1/3
2026-10-27 05:58:34 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=2
2026-10-27 05:58:34 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=0 signal=0 tools=0 out_chars=13 transport=run first_event_ms=2277 ttft_ms=2277 transport_history=['serve', 'run'] duration_s=2.53
2026-10-27 05:58:34 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:34 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:34 stream exec retry=0 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1034 total_spawns=1/3
2026-10-27 05:58:37 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=2
2026-10-27 05:58:37 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=0 signal=0 tools=0 out_chars=13 transport=run first_event_ms=2281 ttft_ms=2281 transport_history=['serve', 'run'] duration_s=2.55
..2026-10-27 05:58:38 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:38 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:39 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=455 ttft_ms=455 transport_history=['serve'] duration_s=1.34
...2026-10-27 05:58:40 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1131 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:40 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:41 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=cancelled rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=434 ttft_ms=None transport_history=['serve'] duration_s=1.18
.2026-10-27 05:58:42 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:42 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:44 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.01
.2026-10-27 05:58:44 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free --standalone prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:44 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:45 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=0 tools=0 out_chars=14 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
.2026-10-27 05:58:46 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:46 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:46 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=cancelled rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 05:58:47 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 05:58:47 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=cancelled rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
..2026-10-27 05:58:48 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:49 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=483 ttft_ms=483 transport_history=['serve'] duration_s=1.29
.2026-10-27 05:58:49 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 05:58:49 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=3 retries=0 signal=0 tools=0 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['serve', 'run'] duration_s=0.00
.2026-10-27 05:58:50 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:50 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
.2026-10-27 05:58:50 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1042 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:50 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:51 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=serve first_event_ms=482 ttft_ms=483 transport_history=['serve'] duration_s=0.66
.2026-10-27 05:58:51 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1048 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:51 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:52 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=provider_fatal rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.15
2026-10-27 05:58:52 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1048 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:52 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:53 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=provider_fatal rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.90
2026-10-27 05:58:53 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1048 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:53 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:54 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=provider_fatal rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.04
.2026-10-27 05:58:55 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:55 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:55 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
.2026-10-27 05:58:55 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:55 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:57 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.01
.2026-10-27 05:58:58 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:58 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:58 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 05:58:58 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:58 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:58 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=1 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 05:58:58 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 05:58:58 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=2 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 05:58:58 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 05:58:58 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=1 retries=1 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
..2026-10-27 05:58:59 dynamic config unreadable: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
.2026-10-27 05:58:59 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:59 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:58:59 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=113 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 05:58:59 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:58:59 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:00 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=113 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
2026-10-27 05:59:00 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:00 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:01 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=113 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.00
.2026-10-27 05:59:01 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:01 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:01 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=upstream_failed rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.00
2026-10-27 05:59:02 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 05:59:02 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=upstream_failed rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
.2026-10-27 05:59:03 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1034 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:03 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:03 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=provider_fatal rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.61
...2026-10-27 05:59:05 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1032 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:05 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:08 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=478 ttft_ms=1887 transport_history=['serve'] duration_s=2.70
.2026-10-27 05:59:08 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1032 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:08 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:11 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 transport=serve first_event_ms=476 ttft_ms=1883 transport_history=['serve'] duration_s=2.71
.2026-10-27 05:59:11 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:11 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:13 retry denied (timeout): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 05:59:13 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=timeout rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.01
2026-10-27 05:59:16 retry denied (timeout): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 05:59:16 http "POST /v1/chat/completions HTTP/1.1" 502 -
2026-10-27 05:59:16 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=502 exit_reason=timeout rc=None total_spawns=3 retries=2 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=3.00
2026-10-27 05:59:16 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1021 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:16 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:17 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=client_gone rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=0.99
2026-10-27 05:59:18 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=0 exit_reason=client_gone rc=None total_spawns=1 retries=0 signal=0 tools=0 out_chars=0 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.00
.2026-10-27 05:59:19 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1058 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:19 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:20 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=1 tools=1 out_chars=17 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=1.01
2026-10-27 05:59:20 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1056 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:20 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:22 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=2 retries=1 signal=1 tools=1 out_chars=17 transport=serve first_event_ms=None ttft_ms=None transport_history=['serve'] duration_s=2.00
.2026-10-27 05:59:22 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1039 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-27 05:59:22 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:23 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=serve first_event_ms=465 ttft_ms=466 transport_history=['serve'] duration_s=0.88
....................................................2026-10-27 05:59:28 tool_call_unparsed bytes=7 head='{broken'
.........................................2026-10-27 05:59:28 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:28 exec: early provider error (waiting for CLI recovery)
2026-10-27 05:59:29 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:29 exec cli failed rc=-15 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost: ECONNRESET'
2026-10-27 05:59:29 done model=muse-spark-1.3-contributor-free rc=-15 state=provider_error tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-27 05:59:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:29 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.09
.2026-10-27 05:59:29 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:29 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:29 stream provider error: HTTP None: provider.transport: Connection lost: ECONNRESET
2026-10-27 05:59:29 stream: early provider error (waiting for CLI recovery)
2026-10-27 05:59:30 stream: step with tool call finished, stopping opencode run
2026-10-27 05:59:30 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:59:30 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=36 ttft_ms=1040 transport_history=['run'] duration_s=1.04
.2026-10-27 05:59:30 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:30 exec: early provider error (waiting for CLI recovery)
2026-10-27 05:59:32 done model=muse-spark-1.3-contributor-free rc=0 state=provider_error tools=0 out_chars=17 retries=0 total_spawns=1
2026-10-27 05:59:32 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:32 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=17 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.29
.2026-10-27 05:59:32 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:32 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:32 stream provider error: HTTP None: provider.transport: Connection lost: ECONNRESET
2026-10-27 05:59:32 stream: early provider error (waiting for CLI recovery)
2026-10-27 05:59:33 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=17 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:59:33 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=17 transport=run first_event_ms=32 ttft_ms=1040 transport_history=['run'] duration_s=1.30
.2026-10-27 05:59:33 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:33 exec: provider error mid-response (transient=True), stopping opencode run
2026-10-27 05:59:33 exec cli failed rc=1 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost while reading the response: ECONNRESET'
2026-10-27 05:59:34 incomplete tool step: re-prompt 1/2 signal=1 total_spawns=1/3
2026-10-27 05:59:34 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 05:59:34 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1854 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:34 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:34 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=78 retries=1 total_spawns=2
2026-10-27 05:59:34 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:34 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=1 tools=2 out_chars=78 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.03
.2026-10-27 05:59:34 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:34 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:34 stream provider error: HTTP None: provider.transport: Connection lost while reading the response: ECONNRESET
2026-10-27 05:59:34 stream: provider error mid-response (transient=True), stopping opencode run
2026-10-27 05:59:35 stream incomplete tool step: re-prompt 1/2 signal=1 total_spawns=1/3
2026-10-27 05:59:35 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1854 total_spawns=1/3
2026-10-27 05:59:35 stream: step with tool call finished, stopping opencode run
2026-10-27 05:59:35 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=78 emulate_tools=True retries=1 total_spawns=2
2026-10-27 05:59:35 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=1 tools=2 out_chars=78 transport=run first_event_ms=18 ttft_ms=18 transport_history=['run'] duration_s=1.05
.2026-10-27 05:59:35 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1375 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:35 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:35 stream: step with tool call finished, stopping opencode run
2026-10-27 05:59:35 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:59:35 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=25 ttft_ms=25 transport_history=['run'] duration_s=0.03
.2026-10-27 05:59:35 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:35 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:35 stream: step with tool call finished, stopping opencode run
2026-10-27 05:59:35 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:59:35 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=20 ttft_ms=20 transport_history=['run'] duration_s=0.02
.2026-10-27 05:59:35 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:36 incomplete tool step: re-prompt 1/2 signal=3 total_spawns=1/3
2026-10-27 05:59:36 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 05:59:36 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1867 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:36 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:36 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=77 retries=1 total_spawns=2
2026-10-27 05:59:36 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:36 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=3 tools=2 out_chars=77 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.05
.2026-10-27 05:59:36 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:36 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:37 stream incomplete tool step: re-prompt 1/2 signal=3 total_spawns=1/3
2026-10-27 05:59:37 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1867 total_spawns=1/3
2026-10-27 05:59:37 stream: step with tool call finished, stopping opencode run
2026-10-27 05:59:37 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=77 emulate_tools=True retries=1 total_spawns=2
2026-10-27 05:59:37 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=3 tools=2 out_chars=77 transport=run first_event_ms=23 ttft_ms=23 transport_history=['run'] duration_s=1.03
.2026-10-27 05:59:37 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:38 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-27 05:59:38 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:38 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.27
.2026-10-27 05:59:38 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:38 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:38 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:59:38 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=20 ttft_ms=20 transport_history=['run'] duration_s=0.28
.2026-10-27 05:59:38 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:38 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:38 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 05:59:38 dropped 1 unparsed tool block(s) from content
2026-10-27 05:59:38 incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 05:59:38 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 05:59:38 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1868 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:39 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:39 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=78 retries=1 total_spawns=2
2026-10-27 05:59:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:39 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=2 tools=2 out_chars=78 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.05
.2026-10-27 05:59:39 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:39 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:39 tool_call_recovered extra_braces=1
2026-10-27 05:59:39 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=1 out_chars=0 retries=0 total_spawns=1
2026-10-27 05:59:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:39 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.03
.2026-10-27 05:59:39 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:39 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-27 05:59:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:39 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.28
.2026-10-27 05:59:39 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:39 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:40 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:59:40 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=37 ttft_ms=37 transport_history=['run'] duration_s=0.30
.2026-10-27 05:59:40 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:41 incomplete tool step: re-prompt 1/2 signal=4 total_spawns=1/3
2026-10-27 05:59:41 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 05:59:41 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1900 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:41 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:41 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=125 retries=1 total_spawns=2
2026-10-27 05:59:41 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:41 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=4 tools=2 out_chars=125 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.28
.2026-10-27 05:59:41 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:41 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:42 stream incomplete tool step: re-prompt 1/2 signal=4 total_spawns=1/3
2026-10-27 05:59:42 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1900 total_spawns=1/3
2026-10-27 05:59:42 stream: step with tool call finished, stopping opencode run
2026-10-27 05:59:42 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=125 emulate_tools=True retries=1 total_spawns=2
2026-10-27 05:59:42 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=4 tools=2 out_chars=125 transport=run first_event_ms=22 ttft_ms=22 transport_history=['run'] duration_s=1.30
.2026-10-27 05:59:42 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:42 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:42 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 05:59:42 dropped 1 unparsed tool block(s) from content
2026-10-27 05:59:43 incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 05:59:43 exec retry=1 (incomplete tool step) total_spawns=1/3
2026-10-27 05:59:43 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1777 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:43 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:43 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 05:59:43 dropped 1 unparsed tool block(s) from content
2026-10-27 05:59:44 incomplete tool step: re-prompt 2/2 signal=2 total_spawns=2/3
2026-10-27 05:59:44 exec retry=2 (incomplete tool step) total_spawns=2/3
2026-10-27 05:59:44 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1777 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:44 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:44 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 05:59:44 dropped 1 unparsed tool block(s) from content
2026-10-27 05:59:44 incomplete tool step: retries exhausted (2) signal=2
2026-10-27 05:59:44 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=0 out_chars=66 retries=2 total_spawns=3
2026-10-27 05:59:44 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:44 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=3 retries=2 signal=2 tools=0 out_chars=66 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.05
.2026-10-27 05:59:44 exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:44 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:44 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 05:59:44 dropped 1 unparsed tool block(s) from content
2026-10-27 05:59:44 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-27 05:59:44 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:44 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.03
.2026-10-27 05:59:44 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:44 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:44 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 05:59:44 stream dropped 1 unparsed tool block(s) from content
2026-10-27 05:59:45 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 05:59:45 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1868 total_spawns=1/3
2026-10-27 05:59:45 stream: step with tool call finished, stopping opencode run
2026-10-27 05:59:45 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=78 emulate_tools=True retries=1 total_spawns=2
2026-10-27 05:59:45 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=2 tools=2 out_chars=78 transport=run first_event_ms=20 ttft_ms=20 transport_history=['run'] duration_s=1.03
.2026-10-27 05:59:45 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:45 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:45 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 05:59:45 stream dropped 1 unparsed tool block(s) from content
2026-10-27 05:59:46 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-27 05:59:46 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=1/3
2026-10-27 05:59:46 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 05:59:46 stream dropped 1 unparsed tool block(s) from content
2026-10-27 05:59:48 stream incomplete tool step: re-prompt 2/2 signal=2 total_spawns=2/3
2026-10-27 05:59:48 stream exec retry=2 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=2/3
2026-10-27 05:59:48 tool_call_unparsed bytes=7 head='{broken'
2026-10-27 05:59:48 stream dropped 1 unparsed tool block(s) from content
2026-10-27 05:59:49 stream incomplete tool step: retries exhausted (2) signal=2
2026-10-27 05:59:49 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=66 emulate_tools=True retries=2 total_spawns=3
2026-10-27 05:59:49 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=2 tools=0 out_chars=66 transport=run first_event_ms=19 ttft_ms=19 transport_history=['run'] duration_s=3.37
.2026-10-27 05:59:49 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:49 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:49 tool_call_recovered extra_braces=1
2026-10-27 05:59:49 stream: step with tool call finished, stopping opencode run
2026-10-27 05:59:49 stream done model=glm-5.3-flash-free rc=-15 tools=1 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:59:49 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=run first_event_ms=34 ttft_ms=34 transport_history=['run'] duration_s=0.04
.2026-10-27 05:59:49 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:49 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:49 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-27 05:59:49 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=22 ttft_ms=22 transport_history=['run'] duration_s=0.27
.2026-10-27 05:59:49 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=7872 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:49 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-27 05:59:49 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:49 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=0.30
.2026-10-27 05:59:49 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:49 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 05:59:50 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 05:59:50 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-27 05:59:50 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:50 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 05:59:52 unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-27 05:59:52 exec retry=2 (unmapped built-in tool) total_spawns=2/3
2026-10-27 05:59:52 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=2214 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:52 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 05:59:52 incomplete tool step: retries exhausted (0) signal=4
2026-10-27 05:59:52 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=125 retries=2 total_spawns=3
2026-10-27 05:59:52 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:52 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=2.95
.2026-10-27 05:59:52 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:52 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:52 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 05:59:53 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 05:59:53 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-27 05:59:53 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 05:59:54 stream unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-27 05:59:54 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=2214 total_spawns=2/3
2026-10-27 05:59:55 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-27 05:59:55 stream incomplete tool step: retries exhausted (0) signal=4
2026-10-27 05:59:55 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-27 05:59:55 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=21 ttft_ms=2206 transport_history=['run'] duration_s=2.46
.2026-10-27 05:59:55 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:55 exec: provider error mid-response (transient=True), stopping opencode run
2026-10-27 05:59:55 exec cli failed rc=1 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost: ECONNRESET'
2026-10-27 05:59:55 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 05:59:56 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 05:59:56 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-27 05:59:56 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:56 exec: step with tool call finished, stopping opencode run
2026-10-27 05:59:56 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=1 total_spawns=2
2026-10-27 05:59:56 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:56 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=2 out_chars=0 transport=run first_event_ms=None ttft_ms=None transport_history=['run'] duration_s=1.07
.2026-10-27 05:59:56 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmpcuvfsxw3/ws
2026-10-27 05:59:56 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-27 05:59:56 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-27 05:59:56 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-27 05:59:56 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-27 05:59:57 stream incomplete tool step: re-prompt 1/2 signal=4 total_spawns=2/3
2026-10-27 05:59:57 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1900 total_spawns=2/3
2026-10-27 05:59:58 stream: step with tool call finished, stopping opencode run
2026-10-27 05:59:58 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-27 05:59:58 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=3 retries=2 signal=4 tools=2 out_chars=125 transport=run first_event_ms=19 ttft_ms=1043 transport_history=['run'] duration_s=2.05
.....2026-10-27 05:59:58 tool_strip_cap_hit max=16 dropping tail
2026-10-27 05:59:58 tool_strip_cap_hit max=16 dropping tail
2026-10-27 05:59:58 tool_strip_cap_hit max=16 dropping tail
..........................................................2026-10-27 05:59:59 tool_call_unparsed bytes=114 head='{"name": "read", "arguments": {"file_path": "/a"}} `<tool_call>`{"name": "read", "arguments": {"file_path": "/b"}}'
...2026-10-27 05:59:59 tool_call_unparsed bytes=23 head='<tool_call>{"name":"a"}'
2026-10-27 05:59:59 tool_call_unparsed bytes=47 head='{"name":"a"}<tool_call> <tool_call>{"name":"b"}'
2026-10-27 05:59:59 tool_call_unparsed bytes=23 head='{"name":"a"}<tool_call>'
.2026-10-27 05:59:59 tool_call_unparsed bytes=32 head='{"name": "a"} <tool_call>{broken'
..............................................
----------------------------------------------------------------------
Ran 445 tests in 174.287s

OK
```

### `VER-003-root-pythonpath-pytest` (`l2-green-ver003-pythonpath.log`, `sha256=605082a78fbe90283b66a00cc5c3b8652e8a908fe734fa35f4a793052d8cdbd3`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=369.21s]
--- STDOUT ---
.......................sss........................... [  5%]
..s..................................................................... [ 13%]
.......................................................... [ 20%]
........................................................................ [ 28%]
........................................................................ [ 36%]
................................. [ 40%]
.......................................................... [ 46%]
s............................................. [ 51%]
...................................................................... [ 59%]
.............................................................. [ 66%]
............................ [ 69%]
........................................... [ 74%]
................................................... [ 79%]
................................................................. [ 87%]
............................................................. [ 93%]
............................... [ 97%]
...................... [ 99%]
..                                                                       [100%]
894 passed, 5 skipped, 8103 subtests passed in 368.96s (0:06:08)

--- STDERR ---
```

### `VER-003b-root-pythonpath-zen-pytest` (`l2-green-ver003b-zen-pythonpath.log`, `sha256=15a08212f9cf14e3d13b617c39bb8f6d92d10ea6ab6636110842017693b00827`)
```text
$ uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=177.39s]
--- STDOUT ---
......................... [  5%]
..................................................................................................................................................................................................... [ 49%]
.............................................................. [ 63%]
........................................................................ [ 80%]
............................................................... [ 94%]
..........................                                           [100%]
445 passed, 3185 subtests passed in 176.87s (0:02:56)

--- STDERR ---
```

### `VER-005-dedicated-realtime-suite` (`l2-green-ver005-dedicated.log`, `sha256=dd30cd05a110afc86a2b349341297d870171c35c64891d5f1f41fec962e9bd9e`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=97.31s]
--- STDOUT ---
................................................... [ 77%]
...............                                                 [100%]
66 passed, 30 subtests passed in 97.15s (0:01:37)

--- STDERR ---
```

### `AC-023-pytest-reversed` (`l2-green-ac023-reversed.log`, `sha256=03df835757fbfc228e5a73a0a2436358660f42a7fd291f10f96ac0c83845c8fb`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinking.py tests/test_step_interruption.py tests/test_stdin_prompt.py tests/test_run_env.py tests/test_realtime_reasoning.py tests/test_native_fallback.py tests/test_lenient_tool_call.py tests/test_google_direct.py tests/test_go_model_routing.py tests/test_effort_mapping.py tests/test_cli_failure.py tests/test_catalog_reload.py tests/test_catalog_mode.py tests/test_catalog.py tests/test_aliases.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=177.83s]
--- STDOUT ---
.................................................................. [ 14%]
................................................................. [ 29%]
................................................................. [ 44%]
.............................................................. [ 57%]
................................................. [ 68%]
.................................................... [ 80%]
................................... [ 88%]
...................................................                                           [100%]
445 passed, 3185 subtests passed in 177.62s (0:02:57)

--- STDERR ---
```

ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-traceability.md sha256=87b60a12ca3f2004205c499b59144caed863a00b18594ed358eb481b1a5b73fa
# Матрица прослеживаемости приёмки (`verification-traceability.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `4`)

## Служебные отметки контура `teamlead-gate`
- **Режим ревью:** `reviewer_skip=true`, `downstream_panel=true`, `parent_skill="analyst-teamlead"` (отдельный `Reviewer` не запускается; Совет Тимлидов — единственный рубеж построчного и приёмочного ревью по `acceptance-package.md` §1; счётчик «замечаний совета сверх Reviewer» при `downstream_panel=true` не определён).
- **Назначение шапки тимлида (`council.md` §1):** дословная шапка тимлида прикреплена сразу после системного промпта роли (`prompt-{skeptic,realist,visionary}.txt`) и до факт-карты во всех 3 брифах Совета Тимлидов.
- **Побайтовая неизменность замороженных функций (`Run-Path Freeze` / `REQ-018`):**
  - `def _run_env`: `sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` (ожидалось `1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` — **MATCH**)
  - `def _stream_google_sse` и `def _execute_google_once`: `google_direct_unchanged=True` (**MATCH**)
  - Белый список изменённых файлов: `bridges/opencode-zen-bridge/server.py, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py, bridges/opencode-zen-bridge/tests/test_step_interruption.py` (ровно 3 целевых файла `coder_target_files`).

## Сводка `acceptance_coverage` из `coder.json`
- RW-001: _serve_http фиксирует headers_at до чтения тела; барьер delivered_any монотонен в SSE и JSON, включая исключение ServeUnavailable и отказ лимитера. test_rw001_delivery_survives_unavailable_or_limiter: четыре сочетания SSE/JSON × unavailable/limiter, без Run.execute и _spawn_with_stdin, без record_success.
- RW-002: status_timer отменяется после spawn_limiter.acquire на legacy run; test_rw002_initial_status_while_waiting_spawn_limiter: задержка 1.2 с, ровно один STATUS_INITIAL <=1.0 с.
- RW-003: _serve_env защищён переводом OSError в ServeUnavailable до выделения lease/порта; test_rw003_mkdtemp_failure_is_serve_unavailable: ENOSPC не оставляет активных портов.
- RW-004: _native_call_as_dsh делегирует _native_to_tool_calls; test_rw004_native_calls_share_canonical_mapping сравнивает сериализованные bash/read/edit/list/multiedit.
- RW-005: _stop_proc проверяет группу независимо от лидера; test_rw005_stop_group_after_leader_exit: реальный лидер завершён, потомок игнорирует SIGTERM, группа завершена SIGKILL.
- RW-006: _read_dynamic_config_enabled ловит OSError/ValueError и логирует предупреждение; test_rw006_invalid_utf8_falls_back_and_recovers: битые UTF-8 дают run, восстановление JSON даёт serve.
- RW-007: Потоковый текстовый фильтр удерживает возможный префикс и незавершённую строку маркера вместо произвольного хвоста 128 символов; test_rw007_split_interrupted_marker_at_every_boundary покрывает три разреза, включая прежнюю границу safe/carry.
- RW-008: _error_payload очищает message/detail; _mask_secrets скрывает Bearer, OPENCODE_SERVER_PASSWORD и proxy userinfo. test_rw008_error_payload_masks_message_and_detail и test_rw008_provider_secrets_hidden_in_sse_json_and_log.
- FU-001: _serve_http пересчитывает остаток deadline и проверяет is_client_gone перед request/getresponse и каждой порцией read1; ctrl/prompt передают общий deadline. Сокет HTTP/1.0 сохранён для таймаута тела, закрытое тело больше не опрашивается; test_fu001_http_checks_deadline_and_cancellation_before_connect и FakeServe-сценарии.
- FU-002: JSON transient_error переносит texts/reasonings в накопители до выбора recovery-промпта или следующей попытки.
- FU-003: SSE usage начисляется в единой точке до любых retry-веток; test_fu003_usage_once_across_distinct_retry_branches: 3+5+7=15 без потерь и повторов.
- FU-004: Run.is_client_gone передаётся из Handler; _execute_once использует on_idle с интервалом _STDOUT_POLL_S, останавливая молчащую группу при уходе клиента. _run_env не изменён.
- FU-005: AC-026: порог соседних reasoning-дельт <0.5 с; FakeServe независимо пишет монотонное время конца отправки, оно сравнивается с реальными клиентскими отметками.
- FU-006: Тайминги задаются в тестовом модуле, pyproject.toml не изменён; профильный набор 174 passed.
- FU-007: На step_finish завершённый native-вызов задаёт first_token_at/ttft_ms, если токена ещё не было.
- FU-008: Причины pyright ignore уточнены для bytes/read1, разделения SSE-буфера, JSON и mock.patch.start/stop; новый файл имеет 0 diagnostics.
- FU-009: Legacy run использует для буферизующего CLI порог первого токена max(FIRST_TOKEN_TIMEOUT_S,120.0), покрывая длительные шаги более 60 с.
- FU-010: Разделитель повтора гейтится thinking; test_fu010_thinking_off_omits_retry_separator.
- FU-011: terminal=cancelled не считается успехом SSE/JSON; test_fu011_cancelled_never_counts_as_success.
- FU-012: FALLBACK_DECISION_TABLE отражает prompt 429/5xx: run до доставки, serve-retry после доставки.
- FU-013: test_disable_file_overrides_forced_serve проверяет настоящий disable-файл; test_elf_magic_and_tool_status проверяет ELF/Mach-O, shebang/случайные байты и статус completed.
- FU-014: Шаг проверки listener через lsof увеличен с 0.05 до 0.2 с в _spawn_serve.
- FU-015: test_serve_env_sanitized_all_branches гарантированно удаляет XDG_STATE_HOME через shutil.rmtree в finally.
- coder-06c / RP-03: возврат неиспользованного spawn-резерва при OSError в обоих путях, без изменения tests/test_go_model_routing.py; до фикса Go 1 failed/9 passed, после фикса полный pytest 445 passed и unittest 445 OK. RW-002 сохранён.

## Поштучная матрица `REQ-001..REQ-020` и `AC-001..AC-026`

| Требование / AC | Реализация в коде | Автотесты / Оракулы | Свидетельство L2 / L3 | Статус |
|---|---|---|---|---|
| `REQ-001` / `AC-001`, `AC-002`, `REQ-020` / `AC-026` (реалтайм-стриминг дельт `reasoning_content` и `content` `<=250 мс`, Red→Green на сокете при идущем апстриме) | `bridges/opencode-zen-bridge/server.py` (потоковый `opencode serve` SSE клиент, прямая запись `message.part.delta` в SSE сокет) | `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py` | `L2-RED-sensitivity` (`rc=1` на `origin/dev`) + `VER-001-pytest` (`rc=0` на кандидате) | `PASS` |
| `REQ-002` / `AC-003` (неизменность публичного HTTP/OpenAI SSE контракта `/health`, `/v1/models`, `/v1/chat/completions`, `:9883`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_zen_bridge.py`, `tests/test_realtime_reasoning.py` | `VER-001-pytest`, `VER-002-unittest` (`rc=0`) | `PASS` |
| `REQ-003` / `AC-004` (kill-switch `REALTIME_SERVE_ENABLED` в `dynamic_config.json`, дефолт `false`, сохранение `opencode run --format json` и `disable-serve`) | `bridges/opencode-zen-bridge/server.py` (`DYNAMIC_CONFIG_PATH`, `_ServeHealth`, fallback decision table) | `tests/test_realtime_reasoning.py`, полный существующий набор `tests/` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-004`, `REQ-005` / `AC-005`, `AC-006`, `AC-007` (первая реакция `< 1.0 с` с префиксом `[мост]` и `
`, ведущий `
` после незавершённой дельты, отсутствие `[мост]` в `_messages_to_prompt`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-006`, `REQ-007` / `AC-008`, `AC-009`, `AC-010` (раздельные watchdogs `first_event_timeout`, `first_token_timeout`, `stall_timeout` с env-порогами) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-008` / `AC-011`, `AC-012` (группа процессов `--serve-helper` + `opencode serve`, детекция закрытия сокета `<= 5 с`, `0` сирот `<= 7 с`, startup lease reaper, тройная сверка `listener_pid`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-009` / `AC-013`, `AC-014` (`MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter, Circuit Breaker, разделитель `[мост]` при ретрае без дедупликации reasoning) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-010`, `REQ-011`, `REQ-012` / `AC-015`, `AC-016`, `AC-017` (инкрементальный `ToolCallParser`, `finish_reason="tool_calls"`, `STEP_RECOVERY`, `deny` для встроенных инструментов, `form.created` `safety_order` `cancel+interrupt`) | `bridges/opencode-zen-bridge/server.py` | `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-013`, `REQ-014`, `REQ-015`, `REQ-016` / `AC-018`, `AC-019`, `AC-020`, `AC-021` (ротация прокси, `usage` из `step-finish`, маскирование пароля serve и секретов, `O-EXIT/v1` с `transport`, `first_event_ms`, `ttft_ms`) | `bridges/opencode-zen-bridge/server.py` (`_serve_env`, `OPENCODE_DB=":memory:"`, `O-EXIT/v1`) | `tests/test_realtime_reasoning.py`, `tests/test_run_env.py` | `VER-001-pytest` (`rc=0`) | `PASS` |
| `REQ-017` / `AC-022`, `AC-023` (приведение базовой линии `test_step_interruption.py` в зелёное при `MAX_TOTAL_SPAWNS=3`, независимость от порядка запуска тестов) | `bridges/opencode-zen-bridge/tests/test_step_interruption.py` | `VER-001-pytest`, `VER-002-unittest`, `VER-003-root-pythonpath-pytest`, `AC-023-pytest-reversed` | Все 4 прогона `rc=0` в `execution-evidence.md` | `PASS` |
| `REQ-018` / `AC-024` (неизменность `_stream_google_sse` и `_execute_google_once`) | Не затронуты (побайтовый SHA-256 сверен в `code-gate.json`) | `tests/test_google_direct.py` | `VER-001-pytest` + `VER-004-packet-command` (`rc=0`) | `PASS` |
| `VER-004` (статический гейт `ruff==0.17.2`, диапазонный `ruff format --check`, `basedpyright==1.40.2`, `0` новых `Any`) | `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py` | `VER-004-packet-command` и `VER-004-ruff-format-*` | `l2-green-ver004-packet.log` (`rc=0`) | `PASS` |
| `REQ-019` / `AC-025`, `VER-006`, `VER-007` (синхронизация `~/.dsh/bridges/opencode-zen-bridge/server.py` и живой heavy-path на `:9883`) | Выкатка `H0..H9` строго после `ACCEPT` Совета Тимлидов | Живой сценарий `:9883` + `diff -u` | `execution-evidence.md` (`VER-006`, `VER-007`) | `DEFERRED_L3 (до ACCEPT Совета Тимлидов)` |
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/evidence-manifest.sha256 sha256=5c2a66f20e1a8230bda4502b958027cc02dc52cad93ed08725a2d70949347f07
e67d5ffb98e29dd698e38e17e18772fa792391a2e24e05cf88d2f820a14e8722  teamlead/verification-surface.json
ae123569d37b2ef167248011b437a05baf7c3dc5f1cbe6594b1484b023f4d502  teamlead/environment-manifest.json
8ba52f52ab5761988431c0058c2f55cb0d0de1fefc8cc1b8f59aae1a0355863b  teamlead/execution-evidence.md
87b60a12ca3f2004205c499b59144caed863a00b18594ed358eb481b1a5b73fa  teamlead/verification-traceability.md
2774577c0a6f46b822b2d41ec3cec6f1a0f77d744a8f8e4dce1508e968a1a69d  teamlead/reverse-spec.md
b82ef4301aef0f563664cc29010a89afaaf9fb8af54d334fe186e157dafc1daf  teamlead/candidate-manifest.json
bb5bdd651db33691cbc45eb5270a3aff615b3b49679b1c40db635e9d44dc67c5  teamlead/candidate.diff
54fd932f91ca50e44ae245a700d674eb40c11a1de2d0900c07d68a9bdb5f32d5  handoff/panel-rework-brief.json
a983d140bed9e85993d200d065fecdd9b2ed5b690ac4ef2e5780df17ec1685da  coder.json
a983d140bed9e85993d200d065fecdd9b2ed5b690ac4ef2e5780df17ec1685da  receipts/coder.json
75e41e1cda9989e182a03b49f0eb2f8121ec639e856d89c8ba9416f55772fe11  receipts/code-gate.json
5a9f9caa0a1eab13961d6c1e181dda43b6c863e5d1a5c4e6e8da02d217f54d4f  receipts/verifier.json
236a4b1d5dfd6a39dbcc0c038e2c4a2c81f24aeeb7a27bdc39b873e9d021d106  receipts/final-gate.json
03df835757fbfc228e5a73a0a2436358660f42a7fd291f10f96ac0c83845c8fb  receipts/l2-green-ac023-reversed.log
b682638b87a7442fa90c9f3060cc69387492a885fd11d61f3a9e440f0559cb29  receipts/l2-green-ver001-pytest.log
13ac0fb9d2f6096771600115a08befc18d2af1c30c8c969f0bbe0c0aa71edaf8  receipts/l2-green-ver002-unittest.log
605082a78fbe90283b66a00cc5c3b8652e8a908fe734fa35f4a793052d8cdbd3  receipts/l2-green-ver003-pythonpath.log
15a08212f9cf14e3d13b617c39bb8f6d92d10ea6ab6636110842017693b00827  receipts/l2-green-ver003b-zen-pythonpath.log
28cc596d5832e0b715a0df332f616aa848942a1d79b4428a5d6314358e0677eb  receipts/l2-green-ver004-packet.log
791491a5d9e6128b8400ae730e69e74c9af01651d625cc697d569dfdcee245b7  receipts/l2-green-ver004-ruff-format-new.log
dd30cd05a110afc86a2b349341297d870171c35c64891d5f1f41fec962e9bd9e  receipts/l2-green-ver005-dedicated.log
13e2b337979db4252216bf59719692869c6b0851f156e87924996aedbcbec757  receipts/l2-red.log
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/reverse-spec.md sha256=2774577c0a6f46b822b2d41ec3cec6f1a0f77d744a8f8e4dce1508e968a1a69d
# reverse-spec.md

Источник реконструкции — исключительно предоставленные diff и новый тестовый модуль. Постановка, ТЗ, архитектурные материалы и файлы на диске не использовались. Тесты не запускались; ниже описано, что они проверяют по своему коду, без утверждения об успешном прохождении.

Документ приведён в ответе: запись `reverse-spec.md` недоступна в текущей файловой среде.

## 1. Фактически изменённые и добавленные файлы

1. **Изменён `bridges/opencode-zen-bridge/server.py`.** Добавляет транспорт через отдельный процесс `opencode serve`, локальные управляющие HTTP-вызовы и чтение событий SSE. Реализует выбор транспорта, fallback, watchdog, служебные статусы, владение процессами через helper и lease, уборку ресурсов и расширенную телеметрию. Также меняет отдельные механизмы существующего `run`-пути: остановку групп, дренаж stderr, обнаружение отключения клиента, возврат резерва лимитера при ошибке запуска и очистку ошибок от секретов. Значительная часть остальных изменений — форматирование.

2. **Изменён `bridges/opencode-zen-bridge/tests/test_step_interruption.py`.** Добавляет сценарий «недоступный встроенный инструмент → незавершённый шаг → корректные вызовы». Обновляет ожидания под общий потолок трёх запусков, создаёт свежий resilience-бюджет перед каждым тестом и переводит часть настройки окружения на `mock.patch.dict`.

3. **Добавлен `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`.** Содержит FakeServe, fake legacy CLI, HTTP-проверки живого тестового моста, прямые проверки отдельных попыток и детерминированные fault-injection тесты.

Добавление `dynamic_config.json` в предоставленных материалах **не показано**: код только начинает читать этот файл рядом с `server.py`. Изменений `zen_catalog.py`, зависимостей, launcher-скриптов и deployment-конфигурации также не представлено.

## 2. Реконструируемое поведение системы

### 2.1. Новый транспорт, включение и отключение

Для запросов, проходящих через CLI-маршрут, появляется альтернативный транспорт:

- прежний: отдельный запуск `opencode run`;
- новый: отдельное дерево `helper → opencode serve` **на каждую попытку**, с локальной HTTP-сессией и SSE-подпиской.

Это не общий долгоживущий serve-процесс для всех запросов.

`OPENCODE_ZEN_BRIDGE_TRANSPORT` читается при выборе транспорта, значение по умолчанию — `auto`. Приоритет выбора:

1. `TRANSPORT=run` либо отрицательный `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` дают `run`.
2. Существование disable-файла даёт `run`, включая принудительный `TRANSPORT=serve`. По умолчанию путь — `~/.dsh/bridges/opencode-zen-bridge/disable-serve`; его можно заменить через `OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE`.
3. `TRANSPORT=serve` принудительно выбирает serve, обходя проверку динамического флага, sticky-деградации и типа бинаря.
4. Неизвестное значение транспорта даёт `run`.
5. В `auto` деградированный serve заменяется на `run`.
6. В `auto` требуется положительный env override либо булево `REALTIME_SERVE_ENABLED: true` в `dynamic_config.json`.
7. В `auto` дополнительно проверяется сигнатура `OPENCODE_BIN`: допускаются распознаваемые Mach-O/ELF; shebang-скрипты не допускаются, кроме тестового обхода `SERVE_TEST_ELIGIBLE`.

Отсутствующий, некорректный или не содержащий булево `true` конфигурационный файл выключает serve при отсутствии положительного env override. Кэш файла использует путь, `mtime_ns` и размер. Изменение файла может повлиять на следующий запрос без перезапуска сервера.

Это **локальная файловая конфигурация**. Интеграции с удалённым конфигом в diff нет. Kill-switch меняет выбор последующих запросов; прекращение уже выполняющейся serve-попытки при переключении не реализовано.

Прямой Google-маршрут обходит выбор serve.

### 2.2. Последовательность serve-попытки

Попытка выполняет следующие действия:

1. Формирует ограниченное окружение и временный каталог состояния.
2. Выбирает свободный loopback-порт и запускает helper отдельным лидером сессии и группы.
3. Получает от helper `serve_pid` и `pgid`.
4. Проверяет через `lsof` и PGID, что порт слушает заявленный serve-процесс из своей группы.
5. Проверяет `GET /api/session/active`.
6. Создаёт сессию через `POST /api/session`, передавая рабочий каталог, модель, допустимый variant и permissions.
7. Открывает `GET /api/event`.
8. Отпускает startup gate после открытия подписки.
9. Параллельно читает SSE и отправляет prompt.
10. Обрабатывает события до терминального результата, ошибки, watchdog, отключения клиента или общего дедлайна.
11. Закрывает соединения, пытается выполнить interrupt и DELETE сессии, затем убирает дерево процессов.

Prompt отправляется с полями:

```json
{"text": "<prompt>", "files": [], "delivery": "steer", "resume": true}
```

Управляющее соединение переиспользуется. При транспортном исключении `_ctrl_http` один раз повторяет вызов с новым соединением.

### 2.3. Потоковая передача reasoning, текста, инструментов и usage

Wire-события serve преобразуются в существующие внутренние категории:

- `session.reasoning.delta` → `reasoning_content`;
- `session.text.delta` → `content`;
- `session.step.ended` → usage шага;
- `session.execution.failed` и `session.step.failed` → ошибка;
- `permission.asked` → запрос разрешения;
- `form.created` → интерактивная форма;
- `session.tool.*` → накопление встроенного вызова.

Reasoning и текст передаются через callbacks во время выполнения попытки. Пробельные дельты маппер сохраняет. В SSE reasoning дополнительно проходит удаление interruption-маркеров; текст проходит потоковый фильтр таких маркеров и, при эмуляции инструментов, существующий `ToolCallParser`.

Текстовые `<tool_call>`/`<tool_invoke>` могут приходить разрезанными между дельтами. Распознанные вызовы выдаются как OpenAI-style `tool_calls`, а не как сырой текст.

Встроенные вызовы serve накапливаются по call ID. Аргументы берутся из полного `input` либо JSON-строки `text`; поле `delta` накопитель самостоятельно не склеивает. Вызов передаётся через существующий `_native_to_tool_calls`, включая каноническое преобразование аргументов и multiedit. Повторная выдача одного call ID подавляется; итоговые DSH-вызовы также дедуплицируются по имени и аргументам.

Usage суммирует:

- `tokens.input`;
- `tokens.output`;
- `tokens.reasoning`;
- `tokens.cache.read` как cached tokens.

`cache.write` не учитывается. Повторный `step.ended` с тем же непустым `assistantMessageID` не учитывается второй раз. Без такого ID дедупликации шага нет. Usage неуспешных serve-попыток тоже накапливается.

Успешный SSE заканчивается финальным чанком с usage, `finish_reason=stop` или `tool_calls`, затем `[DONE]`. Ошибка передаётся через error-объект и `[DONE]`, без успешного `finish_reason`.

Для non-stream JSON содержимое собирается до итогового ответа; служебные статусы в него не включаются.

### 2.4. Статусные строки `[мост]`

В thinking-режиме добавлены синтетические reasoning-дельты:

- `[мост] Подключение к модели…\n`;
- `[мост] Ожидание первого токена…\n`;
- `[мост] Ожидание продолжения…\n`;
- `[мост] Повтор попытки N/M…\n`.

Thinking для синтетических статусов считается выключенным при effort `""`, `off` или `none`.

Для потокового запроса защитный таймер начального статуса настроен на 0,65 секунды от начала бюджета запроса. Первый видимый модельный текст, reasoning или инструмент подавляет этот таймер. Он действует после выдачи SSE-заголовков, в том числе во время ожидания startup gate или spawn limiter.

Ожидание первого токена сопровождается статусами примерно каждые 5 секунд. После токенов статус продолжения появляется при паузе от 15 секунд. При незавершённой строке reasoning перед статусом добавляется LF.

Синтетические статусы не включаются в модельный usage и собранный `content`. Отдельный тест проверяет, что `reasoning_content` истории не попадает обратно в prompt.

### 2.5. Процессы, группы, порты и lease

Helper вызывается ранней CLI-веткой:

```text
python -I server.py --serve-helper <attempt_id> <port> <opencode_bin> <lease_dir> <parent_pid> <parent_lstart>
```

Он проверяет шесть аргументов и диапазон порта, затем запускает:

```text
opencode serve --hostname 127.0.0.1 --port <port>
```

Serve наследует группу helper. Stdin helper служит lifeline: закрытие родительского конца pipe, готовность fd 0 либо SIGTERM запускают остановку. Данные lifeline не интерпретируются; фактически любая его читаемость трактуется как прекращение работы.

Lease хранит attempt ID, UID, PID и время старта родителя/helper, PGID, порт и сведения serve. Файл публикуется через временный файл и `os.replace`. Каталог lease по умолчанию — `/tmp/opencode-zen-bridge-leases`; родительская проверка требует собственного UID и отсутствия симлинка.

Очистка включает:

- SIGTERM своей группы;
- ожидание примерно 4 секунды;
- SIGKILL оставшихся процессов;
- дополнительное окно подтверждения смерти примерно 2 секунды;
- удаление lease и освобождение внутреннего резерва порта после исчезновения группы.

Helper отдельно проверяет членов группы, включая потомков уже завершившегося serve. Legacy `_stop_proc` также начинает останавливать живую группу после выхода её лидера.

Порт выбирается bind-пробой из диапазона от `20000 + PID % 20000` до 59999. Внутрипроцессные попытки защищены lock и набором активных портов; после запуска отдельно проверяется фактический слушатель.

При старте моста reaper обрабатывает lease мёртвых родителей. Проверки включают UID, симлинки, время старта процессов и наличие `--serve-helper` в командной строке живого helper.

### 2.6. Окружение и авторизация serve

Serve получает allowlist окружения, сформированный поверх существующего `_run_env`. Добавляются:

- отдельные `XDG_STATE_HOME` и `TMPDIR`;
- `OPENCODE_DB=:memory:`;
- случайный `OPENCODE_SERVER_PASSWORD`;
- permission policy в `OPENCODE_CONFIG_CONTENT`.

`OPENCODE_BIN` удаляется из окружения дочернего serve. Разрешённые proxy-переменные сохраняются; обращения самого моста к loopback выполняются напрямую через `http.client`.

Внутренние HTTP-запросы используют Basic Auth с пользователем `opencode` и паролем попытки. Ошибки дополнительно очищаются от Bearer-токенов, server password и credentials в proxy URL.

### 2.7. Watchdog, ретраи и fallback

Добавлены настройки с дефолтами:

- `OPENCODE_ZEN_BRIDGE_FIRST_EVENT_TIMEOUT_S=20`;
- `OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S=60`;
- `OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S=60`.

У serve first-event watchdog отсчитывается от начала отправки prompt и учитывает распознанные события выполнения, а не `server.connected` или heartbeat. First-token timeout применяется после первого execution event, но также отсчитывается от начала отправки prompt. Reasoning, текст и готовый native-вызов могут стать первым токеном.

У legacy SSE first-token timeout имеет дополнительный минимум **120 секунд**, даже если настройка меньше. Watchdog вызывается и при поступлении строк, поэтому непрерывный служебный stdout не должен полностью подавлять надзор.

Общий бюджет попыток сохраняет потолок `MAX_TOTAL_SPAWNS`, по умолчанию 3, вместе для serve и последующего run. Используются существующие deadline, retry budget, breaker, backoff и spawn limiter.

В `auto` локальный отказ serve до барьера доставки может привести к `run`. После получения модельных данных либо установления внутреннего признака `delivered` барьер остаётся установленным на весь запрос; последующий отказ не разрешает тихий fallback на run. Для JSON этот барьер учитывает и данные, ещё не отправленные HTTP-клиенту.

Принудительный `TRANSPORT=serve` fallback не допускает.

Ошибки 401/403 и 400/404/422 на обрабатываемых внутренних endpoint завершаются fail-closed. Prompt 429/5xx могут привести к fallback до доставки или serve retry после неё.

Отдельный `_ServeHealth` после трёх зарегистрированных отказов выключает serve в `auto` на 120 секунд. Успешная попытка сбрасывает состояние. Протокольные/локальные отказы отделяются от upstream-отказов, учитываемых breaker.

`FALLBACK_DECISION_TABLE` — декларативный список: исполняемые ветки не используют его как механизм принятия решений.

### 2.8. Интерактивные события

Политика `OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY` допускает:

- `ask_reject`, по умолчанию: permissions создаются как `ask`;
- `deny`: permissions создаются как `deny`.

Иное значение вызывает `ServeSecurityError`.

На `permission.asked` мост отвечает `decision=reject`, вызывает interrupt и закрывает шаг для последующего текста/reasoning. Lifecycle инструмента продолжает обрабатываться для преобразования в DSH-вызов.

На `form.created` своей сессии мост выполняет cancel и interrupt **до проверки title/fields**, затем возвращает отмену. Отсутствующий ID формы своей сессии вызывает fail-closed.

## 3. Внешние контракты и инварианты

### 3.1. Публичный HTTP/SSE-контракт

В представленном diff не меняются пути и структура ответов:

- `/health`;
- `/v1/models` и `/models`;
- `/v1/chat/completions`;
- существующий конструктор OpenAI-compatible SSE-чанков.

Новые публичные endpoint не добавлены. Схема `/health` сохраняется; поле `transport` остаётся строкой `opencode-zen-cli` и не показывает фактически выбранный serve.

При сохранении формата меняется наблюдаемое поведение `/v1/chat/completions`:

- появляются синтетические строки в `reasoning_content`;
- вводятся новые ранние причины завершения по watchdog;
- становится возможен внутренний выбор serve/run и fallback;
- non-stream ответ может содержать reasoning, собранный через serve;
- серверные ошибки проходят усиленную очистку.

Следовательно, формат совместимости сохраняется, но семантика потока расширяется.

### 3.2. Новый внутренний HTTP-контракт

Serve-интеграция зависит от следующих endpoint:

- `GET /api/session/active`;
- `POST /api/session`;
- `GET /api/event`;
- `POST /api/session/{id}/prompt`;
- `POST /api/session/{id}/permission/{request_id}/reply`;
- `POST /api/session/{id}/form/{form_id}/cancel`;
- `POST /api/session/{id}/interrupt`;
- `DELETE /api/session/{id}`.

Создание сессии ожидает именно HTTP 200 и `data.id`. Управляющие reply/cancel/interrupt допускают 200 или 204. Ожидаемые события позиционируются кодом как wire-формат serve v2.1.2.

### 3.3. Новые CLI/env/filesystem-контракты

Добавлены helper CLI, настройки транспорта, динамический boolean-флаг, disable-файл, permission policy и три watchdog-настройки.

Появляются runtime-зависимости от `ps`, `lsof`, POSIX-сигналов, process groups, `select` и socket flags. Helper использует JSON-handshake в stdout; диагностический вывод serve переадресуется в stderr helper.

В `O-EXIT/v1` добавлены:

- `transport`;
- `transport_history`;
- `first_event_ms`;
- `ttft_ms`.

Начальное значение `CATALOG_SOURCE` меняется с `init` на `static`; последующие reload обновляют его через вспомогательную функцию.

### 3.4. Сохранённые маршруты и функции

По видимым изменениям:

- прямой Google streaming остаётся отдельным путём;
- `_run_env`, `_stream_google_sse`, `_execute_google_once` не имеют показанных изменений тела; новый тест дополнительно фиксирует их хеши;
- существующие parser и native-to-DSH mapping переиспользуются;
- основные изменения вокруг каталога и Google request преимущественно форматные;
- публичная проверка авторизации не получает новой схемы.

Без исходных файлов и исполнения нельзя подтвердить хеши или поведение скрытых участков за пределами предоставленного diff.

## 4. Покрытие тестами и граничные случаи

### 4.1. Что проверяет новый модуль

**Streaming и статусы:**

- быстрый legacy-ответ без синтетического статуса;
- первый статус до 1 секунды при медленном ответе, занятом startup gate и задержке лимитера;
- несколько reasoning-дельт до завершения FakeServe;
- сохранение SSE после паузы 1,4 секунды;
- единственный начальный статус;
- отсутствие serve retry-разделителя при thinking off;
- сохранение текста при разрезании interruption-маркера в трёх выбранных местах.

**Транспорт и fallback:**

- чтение boolean-конфига, битый JSON, неверный тип и повреждённый UTF-8;
- приоритет `run`, отрицательного override, disable-файла и неизвестного транспорта;
- fallback после create 503 и sticky-деградация после трёх отказов;
- fail-closed при create 400 и prompt 400/404/422;
- монотонность барьера доставки после частичного reasoning, включая последующий отказ serve или лимитера;
- общий потолок serve + run;
- однократная ротация proxy-пула на попытку.

**Инструменты и интерактивность:**

- tool-теги между несколькими дельтами;
- native tool после permission reject;
- cancel формы без title и отсутствие последующего `STEP2`;
- дедупликация одинаковых вызовов из текста и native;
- сохранение `tool_choice` в recovery prompt;
- соответствие адаптера каноническому mapping для bash/read/edit/list/multiedit.

**Тайминги, ошибки и ресурсы:**

- first-event, first-token и stall timeout serve;
- first-event timeout legacy;
- timeout/client-gone/cancelled не считаются успехом;
- суммирование usage разных retry-веток;
- очистка секретов в SSE, JSON, error payload и логах;
- ошибка `mkdtemp`, `pipe`, `Popen` без ожидаемых утечек;
- отклонение чужого слушателя;
- удаление lease мёртвого родителя с сохранением lease живого;
- SIGKILL группы, игнорирующей SIGTERM;
- остановка потомка после выхода лидера;
- FIN/RST/закрытый rfile;
- дренаж stderr объёмом более 64 КиБ;
- освобождение startup gate до окончания генерации.

Проверки helper охватывают ранний импорт `errno`, закрытый stdin и добивание оставшегося внука процесса.

### 4.2. Изменения тестов незавершённого шага

Существующие сценарии теперь ожидают не четыре, а три запуска. Если в эти три запуска корректные инструменты не появились, допустим финал `stop` без `tool_calls`.

Добавленный сценарий подтверждает последовательность:

1. unmapped native tool;
2. незавершённый шаг;
3. корректные `job_output` и `bash`.

Раздельные бюджеты recovery сохраняются, но подчиняются общему потолку запусков.

### 4.3. Ограничения доказательности тестов

Названия и docstring местами шире фактических assertions:

- тест «same server switch» проверяет чтение конфигурации, а не полноценные запросы через оба транспорта;
- тест «slow … and no status on fast» выполняет только slow-сценарий;
- «every boundary» проверяет три границы interruption-маркера;
- проверка таблицы fallback подтверждает её содержимое, но не соответствие всех исполняемых веток;
- helper argv/lease-dir тест не выполняет успешный запуск с шестью корректными аргументами;
- проверка полей O-EXIT подтверждает наличие, а не корректность значений;
- FakeServe не доказывает совместимость с реальным бинарём и провайдером.

Предоставленный SHA-256 нового модуля независимо не проверялся.

### 4.4. Потенциальные пробелы и риски по коду

1. **Барьер доставки реализован неоднородно.** First-event timeout учитывает prompt headers, а некоторые другие ветки — только модельные массивы. Исключение `ServeUnavailable` не переносит наружу весь внутренний прогресс попытки. Поэтому запрет повторной отправки после доставки prompt не доказан для всех транспортных отказов.

2. **Startup-фазы не полностью ограничены общим дедлайном.** Выбор порта, handshake, `lsof` и открытие SSE имеют собственные ожидания; не все проверяют cancellation и остаток бюджета.

3. **Prompt worker не закрывается явно.** Потоку даётся join 0,5 секунды, но его HTTP-соединение недоступно внешнему cleanup. Оно может оставаться живым до завершения запроса или socket timeout.

4. **Повтор управляющего POST может дублировать действие.** При исключении после фактической обработки `POST /api/session` повтор не защищён idempotency key.

5. **Watchdog инструментов имеет пограничные случаи.** Legacy не считает native tool первым токеном. Serve input delta обновляет активность только после уже установленного first-token; завершённый native-вызов не обновляет `last_token_at`. Длинный поток аргументов может быть классифицирован как тишина или stall.

6. **Thinking off не везде подавляет статусы.** В legacy watchdog-retry ветке `emit_synthetic` вызывается без проверки thinking. Соответствующий новый тест покрывает serve-путь.

7. **SSE-reader поддерживает ограниченный формат.** Каждая `data:`-строка парсится отдельно; многострочные SSE data не собираются. Не показаны ограничения размера строки и полного накопленного ответа.

8. **Фильтрация session ID неполная.** Чужой непустой ID отбрасывается, но для ряда событий отсутствие ID допускается.

9. **Есть расхождения stream и JSON.** JSON отклоняет reasoning-only/пустой успешный результат; serve SSE не имеет аналогичной проверки. JSON не применяет тот же потоковый interruption-фильтр. При некоторых retry-ветках накопленный JSON-текст может теряться или повторяться.

10. **Fallback теряет часть учёта usage.** Serve usage накапливается отдельно, но при переходе к run видимого переноса в итоговый общий usage нет.

11. **Резерв лимитера serve не возвращается при неудачном старте.** Для legacy `Popen` failure возврат добавлен; для serve нет аналогичной ветки, хотя попытка уже засчитана.

12. **Изоляция состояния не полная.** `XDG_DATA_HOME` сохраняется. Без реального бинаря нельзя доказать, что `OPENCODE_DB=:memory:` исключает запись в остальные persistent-каталоги.

13. **Между bind-пробой и serve bind остаётся гонка.** Проверка владельца слушателя снижает риск обращения к чужому процессу, но не устраняет конкуренцию за порт.

14. **Очистка не подтверждает все аварийные случаи.** Не показаны полноценные испытания SIGKILL родителя, дерева с изменёнными PGID, PID reuse, подложных lease, отказов `ps/lsof` и восстановления оставшихся временных каталогов.

15. **Заявленная таблица классификации шире реализации.** Отдельное доказательство capability defect из таблицы не прослеживается. Нельзя считать все строки таблицы исполненными требованиями только по её наличию.

Дополнительно не показаны нагрузочные проверки параллельных запросов, исчерпания портов, SSE queue pressure, 120-секундного восстановления деградации и работа с реальным владельческим чатом. Эти свойства остаются непроверенными по предоставленным материалам.
ARTIFACT_END>>>

## 5. Список обязательных правил и стандартов проекта
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/code.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/python-standards.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/testing.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/security.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/error-handling.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/logging.md`
- `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/scope-and-contracts.md`


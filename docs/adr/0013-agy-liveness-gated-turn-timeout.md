# 0013 — agy-bridge: потолок активной попытки снимается при признаках жизни; ход завершается только по полной тишине

## Status

Accepted (2026-10-31, Architect Delta-Pass **a3**, run `agy-turn-silence-timeout`); packet status **APPROVED**, approval AD-001/AD-005 **APPROVED** как JSON. Повторная панель a3 **PENDING**; Accepted не означает PANEL PROOF PASS. Формат: MADR-full (repo-native, как `docs/adr/0007-*`).
Номер 0013 предварительный: оркестратор сверяет свободный номер с `docs/adr/INDEX.md` при материализации
(рабочее дерево содержит чужие незакоммиченные ADR 0008/0009/0012 и изменённый INDEX.md).
Целевой путь: `docs/adr/0013-agy-liveness-gated-turn-timeout.md`.
Критичность: S2. Расширяет ADR 0007 (`0007-agy-bridge-resilience-watchdog.md`) и решение AD-003 (extended timeout policy) в `bridges/agy-bridge/server.py`.
Пакет: `/tmp/cel-runs/agy-turn-silence-timeout/architecture/architecture-packet.md`.

## Y-формулировка

В контексте standalone `agy-bridge` (`127.0.0.1:9887`), к которому DeepSeek Harness обращается напрямую,
столкнувшись с обрывом хода по wall-clock-потолку попытки (жизнь в незалогированном интервале не доказана) (инцидент 2026-10-31 00:26:43, conversation `46ea51bd`,
`gemini-4-argon`, `state=timeout wall_s=3597.1`, последняя залогированная thinking-дельта в 00:14:51, idle 1800 с не истёк — EVD-L01..L03)
при включённых `extended_timeout_enabled=true` и `graceful_timeout_on_partial=true` (EVD-L04),
мы решили под новым runtime-флагом `liveness_gated_timeout_enabled` (env `AGY_LIVENESS_GATED_TIMEOUT_ENABLED`, кодовый default `False`)
**не проверять потолок `effective_max_timeout_s` активной попытки** и завершать её по времени только при **полной тишине**:
ни одного признака жизни (stdout-JSON-событие | рост transcript | изменение thinking в SQLite | прирост CPU группы процессов agy выше порога шума при живом лидере)
дольше `idle_timeout_s` (1800 с, `AGY_IDLE_TIMEOUT_S`),
сохранив без изменений first-token timeout, admission, client disconnect, остановку службы, смерть процесса, legacy-путь и контракт ответа,
чтобы долгий ход с мышлением не обрывался, а реально зависший ход по-прежнему освобождал слот.
При этом мы принимаем отсутствие жёсткого верхнего предела активного хода (решение владельца, OPEN-08 закрыт) и риск ложной «жизни» от фонового CPU, который ограничиваем порогом и наблюдаемостью.

## Context and Problem Statement

- Extended-ветка `Handler._execute` первой проверяет `now - run.started >= policy.effective_max_timeout_s` без условия активности [F-09], [F-59]; потолок = `min(AGY_TIMEOUT_S|3600, t_req_start + 3600 - now - 5.5)` [F-06], [F-57]; отсюда 3594.5 с [F-07].
- Idle extended-ветки считает только producer activity (stdout/transcript/thinking-дельта) [F-10], [F-13]–[F-16], [F-65]; CPU-проверка `controller.check()` выполняется только при `not ext` [F-20], [F-67].
- Transcript tail имеет свой wall-clock `effective_max + 60` [F-24], [F-89] — наблюдение источников прекращается независимо от активности.
- Тесты [F-32], [F-33] закрепляют обрыв при постоянной активности; это контракт, противоречащий требованию владельца (handoff § «Не противоречит ли требование…»).
- Решения владельца 2026-10-31 01:13 (`owner-answers.md`): жизнь = stdout | transcript | thinking-дельта SQLite | прирост CPU agy или потомков; тишина = ни одного сигнала дольше idle 1800 с; снять только потолок активной попытки; остаются first-token, idle, admission, client disconnect, остановка службы, смерть процесса.

## Decision Drivers

- D1 — живой ход не обрывается по wall-clock (требование владельца).
- D2 — зависший ход освобождает слот не позже `idle + 10 с` (наблюдаемость в пределах тика очереди 1 с + интервал выборки CPU 5 с + `ps` timeout 2 с).
- D3 — мгновенный откат без рестарта (конвенция репо: runtime-флаги `dynamic_config.json`, TTL 1 с [F-03], [F-04]).
- D4 — без правки вендорского кода (AGENTS.md репо) и без изменения внешнего API.
- D5 — нет утечки процессов/потоков при любом исходе (ADR 0007, D2).
- D6 — минимальная дельта: переиспользовать существующие источники активности и `core.watchdog.ProcessWatchdog`.

## Considered Options

1. **O1 — новый флаг, потолок снимается, тишина = композит 4 источников (выбрано).**
2. **O2 — изменить семантику `extended_timeout_enabled` без нового флага.** Отклонено: нет отката к текущему extended-поведению (idle 1800 + cap), откат возможен только в legacy 1800 с безусловным wall-clock [F-11], [F-62] — хуже текущего состояния.
3. **O3 — оставить потолок, но поднять `AGY_TIMEOUT_S`/`T_REQ_BUDGET_S` (например, до 4–8 ч).** Отклонено: противоречит требованию владельца (обрыв живого хода по wall-clock сохраняется, лишь отодвигается); `T_REQ_BUDGET_S` — константа, не env [F-02].
4. **O4 — «мягкий» потолок: на cap обрывать, только если тишина дольше короткого окна (например, 300 с).** Отклонено: вводит второе определение тишины, противоречит решению владельца «тишина = дольше idle».
5. **O5 — вынести композитный liveness-монитор в новое ядро `core/` для всех мостов.** Отложено (coder-backlog CB-01): scope владельца ограничен agy (OPEN-08); core-изменение живо применяется к работающему мосту через `PYTHONPATH` на рестарте (EVD-L06) и влияет на другие адаптеры.

## Decision Outcome

Выбран O1.

### Правило завершения активной попытки (флаг включён И extended-политика активна)

1. Потолок `effective_max_timeout_s` **не проверяется**. При active extended+liveness=True _extended_timeouts() / _build_timeout_policy сохраняют idle_timeout_s = AGY_IDLE_TIMEOUT_S с прежним fallback, без min(idle, cap), даже если AGY_TIMEOUT_S < AGY_IDLE_TIMEOUT_S. effective_max=min(cap, remaining_budget - 5.5) остаётся сохранённым потолком для kill-switch. При off -> on текущего Run восстанавливается исходный незажатый idle; при on -> off возвращаются прежний min(idle,cap) и cap. Admission/can_start не получают нового бюджета.
2. CB-05 обязателен (AC-17): в Handler._execute суммарные UTF-8 байты pieces <= MAX_CONTENT_BYTES_PER_TURN = 8 MiB и reasoning_pieces <= MAX_REASONING_BYTES_PER_TURN = 2 MiB независимо от planner_content_streaming_enabled. В Run._pump при planner_content_streaming_enabled=False self._text_seen хранит полные снимки, пока len(_text_seen) <= MAX_CONTENT_STEPS = 128 И суммарный UTF-8 объём _text_seen_bytes <= MAX_CONTENT_BYTES_PER_TURN = 8 MiB. Защёлка переполнения _text_seen_overflow: bool = False (overflow latch, аналог _ContentArbiter.overflow, server.py:2767-2769, и _emit_reasoning, server.py:3851-3855) взводится до сохранения очередного снимка, если он превысит 128 шагов или 8 MiB суммарных байт (при replace учитывается полный размер нового снимка взамен старого), либо когда pieces в Handler._execute достигает 8 MiB; pieces никогда не добавляется сверх лимита. При _text_seen_overflow=True однократно за ход логируется content_cap_reached, дальнейшее добавление текста в _text_seen/pieces и эмиссия ("text", suffix) прекращаются до конца хода; достижение капа reasoning_pieces также логируется однократно на буфер/ход. Сохранённые снимки не усекаются и не вытесняются: полная база _reasoning_suffix (server.py:4181, text.startswith(prev) / text[len(prev):]) сохраняется, повторная эмиссия уже выданного префикса из-за потери базы дедупликации исключена. self.note_producer_activity("stdout") продолжает обновлять liveness на новых stdout-событиях после капа; живой ход не сбрасывается и не прерывается.
3. `last_life = max(run.started, last_producer_activity_ts, last_cpu_activity_ts)`; при `now - last_life >= policy.idle_timeout_s` → `idle_timeout`, rc=124, `timeout_limit_s = idle_timeout_s` (тот же state, тот же graceful notice и тот же `finish_reason=length`, что сегодня [F-27]–[F-29], [F-46]).
4. Остальные ветви `_execute` — first-token, `client_gone`, `agy_error` grace, `pump_error`, `done` — без изменений.

### Источники жизни (композит)

| Источник | Как учитывается | Что НЕ считается жизнью |
|---|---|---|
| stdout | успешно разобранное JSON-событие [F-14], [F-63] (уже есть) | пустые/не-JSON строки, stderr [F-23] |
| transcript | рост файла текущего хода, включая неполную строку [F-15], [F-64] (уже есть); продолжает учитываться после переполнения reasoning-квоты (tail читает transcript до проверки `dead`) | backlog, повторное чтение тех же байт [F-40] |
| thinking SQLite | выданная LIVE-дельта [F-16], [F-65] (уже есть) **+ новое: изменение blob шага текущего хода (`step_index >= base_idx`, иные size/SHA) в любом режиме LIVE/SHADOW и после переполнения reasoning-квоты** | одинаковый blob [F-17]; шаги прошлых ходов |
| CPU | **новое:** сумма положительных приростов `cputime` живых PID группы agy (PGID = PID лидера [F-72]) по `core.watchdog.ProcessWatchdog.sample`, учитывается, только если (а) лидер `run.proc` жив, (б) выборка не деградировала, (в) прирост `>= max(AGY_LIVENESS_CPU_MIN_S, AGY_LIVENESS_CPU_MIN_RATE * dt)` между последней успешной базой seed/sample и текущей успешной выборкой | новые PID без прироста CPU; деградация `ps` (fail-closed [F-76]); CPU после выхода лидера (осиротевшие потомки); SSE keepalive, stderr, собственные потоки моста (мост — вне группы agy) |

Выборка CPU (AD-005, AC-03/05, RW-003): Выбран регулярный watchdog.sample(pgid) каждые WATCHDOG_INTERVAL_S = 5.0 с на каждой итерации Handler._execute независимо от queue.Empty и свежей producer activity, при живом лидере и включённом watchdog. dt — между теми же sample/seed, что дали cpu_delta; _last_cpu_sample_ts обновляется только при watchdog.seed(pgid) и при успешной выборке watchdog.sample(pgid) (not metrics.ps_degraded and metrics.alive). При metrics.ps_degraded=True или not metrics.alive выборка не считается жизнью (cpu_active=False), а _last_cpu_sample_ts не перезаписывается: это метка последней успешной базы CPU. На следующей успешной выборке dt = max(now - _last_cpu_sample_ts, WATCHDOG_INTERVAL_S) вычисляется до обновления метки и в точности соответствует интервалу накопления metrics.cpu_delta_s (core/watchdog.py:239-275,290-316). Начальный seed синхронизирован с этой меткой. После отключения/пропуска мониторинга перед возобновлением — watchdog.seed(pgid) и _last_cpu_sample_ts=now, seed не жизнь, следующее окно 5с. Поэтому 600с producer-стрима + 5с CPU не дают dt=605 и порог 0.02*605=12.1с: delta=5.0с принимается при dt≈5с. При BRIDGE_ENABLE_ADAPTIVE_WATCHDOG=0 CPU отключён; legacy и core.check без изменений.

### Остальные wall-clock места

| Место | Решение | Основание |
|---|---|---|
| extended cap `effective_max_timeout_s` [F-06], [F-09] | снимается под флагом | требование владельца |
| legacy `TIMEOUT_S` 1800 [F-11], [F-62] | без изменений | это целевая точка kill-switch; extended=true в проде (EVD-L04) |
| tail deadline +60 [F-24/F-89] | На каждой итерации Handler._execute при active extended+liveness=True динамически выставлять run._tail.deadline_s = math.inf, включая off -> on уже идущего Run; на on -> off восстановить абсолютную границу run.started + policy.effective_max_timeout_s + 60.0. Сейчас _TranscriptTail._run_loop сравнивает относительную длительность: Coder обязан согласовать origin/единицы и пересчитать границу относительно того же origin, если duration-поле сохраняется; абсолютную метку нельзя подставлять в прежнее относительное сравнение. Legacy TIMEOUT_S+60 и bind FIRST_TOKEN_TIMEOUT_S не меняются; Run.close() гарантирует выход tail. | RW-001, AC-07/08, VER-010 |
| `T_REQ_BUDGET_S` / retry [F-02], [F-38] | остаётся только для admission [F-08], [F-91] и решения «можно ли начать новую попытку» (`can_start`); активную попытку не ограничивает | admission и запрет новых попыток при исчерпании — вне снятия (OPEN-08) |
| Handler._arm_flush_window:4488-4492 | Handler._arm_flush_window (server.py:4488-4492) для финального flush уже запущенной/завершившейся попытки безусловно задаёт _flush_deadline = time.monotonic() + T_FINAL_FLUSH_S; зажим min(..., t_req_start + T_REQ_BUDGET_S) из этого окна удаляется независимо от текущего флага, включая kill-switch off на t=4000. Admission/can_start сохраняются. При t>3600 JSON-ответ реально отправляется; SSE отправляет retained_events, _graceful_notice, finish_reason="length" и [DONE]. | RW-001, AD-006, AC-02/10, VER-003/008 |
| root `server.py` `TIMEOUT_S` 1800 [F-84] | без изменений, N/A для agy | клиент идёт напрямую на :9887 (EVD-L05); в корневом `fleet.json` agy нет (EVD-L07) |
| passthrough read timeout 1800 [F-80] | без изменений, N/A | тот же маршрут; риск при будущей маршрутизации — CB-06 |
| core `AdaptiveTimeoutController` safety cap [F-74], [F-43] | без изменений | используется только legacy-путём agy и другими мостами |
| detached watchdog [F-77], [F-78] | без изменений, N/A | на маршруте agy не вызывается |
| first-token 120 с [F-12], [F-68] | без изменений | решение владельца |
| admission 900 с [F-91] | без изменений | решение владельца |
| `RESULT_EXIT_GRACE_S` 5 с [F-26], `_kill_group` 2/5 с [F-72] | без изменений | не лимит живого хода |
| SSE keepalive 15 с [F-23], [F-69] | без изменений, не жизнь | служебная активность моста |

### SQLite и наблюдаемость (AC-06, AD-007, FU-004)

В _handle_row для текущего шага (>= base_idx) изменение size/SHA вызывает _note_activity() в LIVE/SHADOW и при dead=True после reasoning-квоты, без эмиссии reasoning после квоты. При payload is None (step_payload > 256 KiB) изменение blob_len также обновляет state.blob_len и вызывает _note_activity(); одинаковые blob_len без payload, одинаковый blob и старые шаги жизнь не обновляют. Альтернативы «после квоты только transcript» нет. Heartbeat не чаще 1/300с с last_life_src и last_life_age_s; без этих строк L2 не засчитывается.

### Kill-switch

- `liveness_gated_timeout_enabled=false` на лету → со следующей итерации снова действует `effective_max_timeout_s` попытки; ход старше потолка завершается `timeout` в течение ≤ `FLAG_TTL_S` + 1 тик (≈ 2 с) — штатный аварийный рычаг оператора против «вечного» хода.
- `extended_timeout_enabled=false` на лету → legacy-дедлайн `run.started + TIMEOUT_S` (поведение [F-50] без изменений), независимо от нового флага.
- Отсутствие ключа в `dynamic_config.json` = `false` (парсер берёт `raw.get(name, False)`).
- На каждой итерации Handler._execute при active extended+liveness=True динамически выставлять run._tail.deadline_s = math.inf, включая off -> on уже идущего Run; на on -> off восстановить абсолютную границу run.started + policy.effective_max_timeout_s + 60.0. Сейчас _TranscriptTail._run_loop сравнивает относительную длительность: Coder обязан согласовать origin/единицы и пересчитать границу относительно того же origin, если duration-поле сохраняется; абсолютную метку нельзя подставлять в прежнее относительное сравнение. Legacy TIMEOUT_S+60 и bind FIRST_TOKEN_TIMEOUT_S не меняются; Run.close() гарантирует выход tail.
- Handler._arm_flush_window (server.py:4488-4492) для финального flush уже запущенной/завершившейся попытки безусловно задаёт _flush_deadline = time.monotonic() + T_FINAL_FLUSH_S; зажим min(..., t_req_start + T_REQ_BUDGET_S) из этого окна удаляется независимо от текущего флага, включая kill-switch off на t=4000. Admission/can_start сохраняются. При t>3600 JSON-ответ реально отправляется; SSE отправляет retained_events, _graceful_notice, finish_reason="length" и [DONE].
- Общий kill-switch завершает все ходы старше их cap, включая полезные многочасовые; это сохранённое операторское последствие.

## Consequences

- Хорошо: живой ход длиннее 3594.5 с завершается `done`; зависший — `idle_timeout` через idle; формат ответа и типы ошибок не меняются.
- Хорошо: откат за ≤ 2 с без рестарта.
- Плохо: жёсткого верхнего предела нет; слот может удерживаться часами, пока есть жизнь и клиент подключён → рост `queue_timeout` у остальных (4 слота default [F-90]).
- Плохо: фоновый CPU зависшего, но живого agy выше порога даст бесконечный ход. Порог по умолчанию — допущение ASM-01; калибровка — обязательный шаг перед включением флага (verification-plan L0).
- Нейтрально: тесты [F-32], [F-33], [F-39] остаются как регрессия при выключенном флаге; добавляются зеркальные тесты для включённого.

## Assumptions и resource applicability

- ASM-01 / ASM-001: **ASSUMED**, 0.05с/0.02 — старт, не измеренный production-порог. L0 / VER-110 — жёсткий gate prod-enable: отдельно контролируемый живой незамороженный процесс agy/группа без SIGSTOP, в подтверждённом ожидании/сне на IO/сети без генерации шагов >=10 мин, ps -g <PGID> каждые 5с; отдельно полезная CPU-работа без producer-событий, паузы живого хода и SIGSTOP только zero-reference. AGY_LIVENESS_CPU_MIN_RATE >= 2 * max_observed_idle_rate живого процесса; запас должен обеспечить idle_rate < rate/2. Если фон Go language_server ~5% ядра, начальные 0.02 не проходят: env-порог >=0.10 с запасом, без правки кода. Фактическое значение и сырые ряды фиксирует Verifier; L0 ещё не выполнен.
- ASM-02 / ASM-002: **ASSUMED**, L2 требует клиентские данные отсутствия read-timeout и непрерывное соединение >3600с; 3597с инцидента этого не доказывают.
- ASM-03 / ASM-003: **ASSUMED**, L0 сверяет ps -g <PGID> с рекурсивным деревом pgrep -P; рабочие потомки вне PGID блокируют prod-enable до отдельного решения.
- ASM-004: VALIDATED (EVD-011), extended используется в проде.
- **HL-ENV-01: N/A (single local bridge process, max 4 slots, no external DB/broker)**, как JSON hl_env.status/reason; N/A не отменяет AC-17 и L0.
- Owner evidence как JSON: analysis/agy-turn-timeout/owner-answers.md (2026-10-31 01:13 MSK) + owner chat 'продолжай' (2026-10-31 02:06 MSK), без нового self-approval.

## Confirmation

- Автоматически: VER-001..016, особенно VER-004/005 (600с producer + 5с CPU, dt≈5; degraded → recovery: seed t=0, degraded t=5/10 сохраняют _last_cpu_sample_ts=0, recovery t=15: delta=0.12, dt=15, threshold=0.30, cpu_active=False), VER-010 (off -> on -> off и payload=None >256KiB), VER-016 (плато pieces/_text_seen <=8MiB и reasoning_pieces <=2MiB, overflow latch без дублей уже выданного префикса, liveness и done). VER-015: /usr/bin/python3 3.9.6 import + smoke _build_timeout_policy/production flag parser; ruff check --target-version py39 bridges/agy-bridge/server.py. Полный pytest/ruff/basedpyright — в verification-plan.
- Тяжёлый путь: L0 до prod-enable (живой незамороженный idle >=10мин + полезный CPU); L2 done >600с и клиентский gate >3600с с heartbeat last_life_src. L4 — отдельный ход, limit=600.0 либо min(600.0, remaining_budget-5.5), сверить policy.effective_max_timeout_s; L2 не прерывать. VER-003/008 проверяют JSON/SSE retained_events, _graceful_notice, finish_reason="length", [DONE] при t>3600 и off t=4000. L3 idle/SIGSTOP и L5 disconnect сохраняются.

## More Information

Evidence: `/tmp/cel-runs/agy-turn-silence-timeout/analysis/agy-turn-timeout/evidence-ledger.md` [F-01]–[F-89], handoff [F-90], [F-91]; живые наблюдения EVD-L01..L08 — в architecture-packet.md § 2.

Delta a3: RW-001/F-001 — успешная CPU-база dt/degraded; RW-002/F-002 — overflow latch без потери дедупликации. Предыдущая дельта a2 (tail/flush, обязательный CB-05, регулярный dt/L0 и FU-001..004) сохранена. Исторический NEEDS_WORK сохранён; повторная панель и живые проверки в этом проходе не выполнялись.

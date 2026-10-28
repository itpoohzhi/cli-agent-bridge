# Консенсус-леджер Совета Тимлидов по коду (`consensus-ledger.md` / `findings-ledger.md`) — Cycle 7, run `analyst-teamlead-zen-realtime-reasoning-20261025`

- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=5efd0909ef787d0125d23fe80ae837ad4d39d28975f2e455501c8f98b937f830`)
- **Раунд R1 (`panel/council/r82`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r82/panel-proof.json sha256=2cf7c3441dc30d3485717ac5a3428d33fb3eb45443a05bb03423751fa9ea6322 verify_panel_proof exit=0`
- **Раунд D1 (`panel/council/r89`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r89/panel-proof.json sha256=bb0e0279389377cca425491e41ec332da68107204496654de75ac57de2eafd52 verify_panel_proof exit=0`
- **Всего находок R1:** `6` (`F-001` .. `F-006`), новых находок в D1 (`r2_late`): `0`.
- **Итог дебатов D1:** `AGREED blocking` = `3` (`RW-001..RW-003`), `AGREED non-blocking` = `3` (`FU-001..FU-003`), `WITHDRAWN` = `0`. Открытых `OPEN` или `CONFLICT` нет (`0`).

## Сводная таблица статусов (`F-001` .. `F-006`)

| ID | skeptic | realist | visionary | priority | status |
|---|---|---|---|---|---|
| F-001 | AGREE | AGREE | AMEND | blocking | AGREED |
| F-002 | AGREE | AMEND | AUTHOR | blocking | AGREED |
| F-003 | AGREE | AMEND | AMEND | non-blocking | AGREED |
| F-004 | AGREE | AMEND | AMEND | non-blocking | AGREED |
| F-005 | AGREE | AMEND | AUTHOR | blocking | AGREED |
| F-006 | AGREE | AGREE | AUTHOR | non-blocking | AGREED |

---

## Карточки находок (`F-001` .. `F-006`)

### F-001
- origin: visionary · R1 · visionary-F-001
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AMEND
- dissent: visionary d1 «AMEND F-001 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6034,bridges/opencode-zen-bridge/server.py:7328; fix=разделить запрет fallback на run и допустимость serve-по» → teamlead/cycle-7/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6034,bridges/opencode-zen-bridge/server.py:7328; fix=разделить запрет fallback на run и допустимость serve-повтора ранней транзиентной ошибки без ток (teamlead/cycle-7/debate/d1/visionary.md)
- text (дословно, R1 visionary):
> F-001 [pre-existing]
>    
>    priority: blocking  
>    locations: `bridges/opencode-zen-bridge/server.py:6034`, `bridges/opencode-zen-bridge/server.py:6039`  
>    Правило: REQ-009, сохранение повторов транзиентных отказов; барьер доставки запрещает fallback в `run`, но допускает повтор `serve`.  
>    Evidence: условие `if not _delivered_err and attempts.allow_retry(...)`. После `session.execution.started` значение `_delivered_err=True`. Если следующим событием приходит `session.execution.failed` с 429/503 без текста и reasoning, общий повтор пропускается; `_incomplete_step_signal("", "", ...)` также возвращает 0. Запрос заканчивается ошибкой после первой попытки при свободном бюджете. JSON-ветка в `server.py:7328` допускает такой повтор.  
>    Исправление: разделить предикаты запрета fallback и допустимости serve-повтора; раннюю транзиентную ошибку без модельного вывода повторять через serve.  
>    Проверка: FakeServe возвращает execution-started → 429/503 без токенов, следующая попытка успешна; SSE и JSON используют две serve-попытки, без запуска `run`.

### F-002
- origin: visionary · R1 · visionary-F-002
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AMEND, visionary=AUTHOR
- dissent: realist d1 «AMEND F-002 priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:1785`; fix=отклонять непарный surrogate на границе serve через `ServeProtocolError` в следующем проходе — пр» → teamlead/cycle-7/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:1785`; fix=отклонять непарный surrogate на границе serve через `ServeProtocolError` в следующем проходе — причина: `server.py:1783` — механизм верен (teamlead/cycle-7/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-002 [pre-existing]
>    
>    priority: blocking  
>    locations: `bridges/opencode-zen-bridge/server.py:1785`, `bridges/opencode-zen-bridge/server.py:5800`, `bridges/opencode-zen-bridge/server.py:7460`  
>    Правило: python-standards.md §3, §14; некорректный вход транспорта должен завершаться классифицированной ошибкой.  
>    Evidence: `_combine_surrogates()` при ошибке декодирования возвращает исходную строку. JSON-значение `"\ud800"` проходит проверки строкового типа. В SSE последующее `.encode("utf-8")` выбрасывает `UnicodeEncodeError`; в JSON та же строка сохраняется в итоговом сообщении и достигает `_send`. Управляемая классификация `invalid_serve_event` отсутствует.  
>    Исправление: отклонять непарные surrogate на границе serve-протокола через `ServeProtocolError`, сохраняя корректные пары без изменения текста.  
>    Проверка: reasoning/text с непарным старшим и младшим surrogate в SSE и JSON дают управляемую ошибку, cleanup и корректный O-EXIT; корректная пара остаётся зелёной.

### F-003
- origin: visionary · R1 · visionary-F-003
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AMEND, visionary=AMEND
- dissent: realist d1 «AMEND F-003 priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:3818`, `bridges/opencode-zen-bridge/server.py:3309`; fix=сначала wire-фикстура двух `called` одного `assista» → teamlead/cycle-7/debate/d1/realist.md ; visionary d1 «AMEND F-003 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3818,bridges/opencode-zen-bridge/server.py:3829,bridges/opencode-zen-bridge/server.py:3309,bridges/opencode-z» → teamlead/cycle-7/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:3818`, `bridges/opencode-zen-bridge/server.py:3309`; fix=сначала wire-фикстура двух `called` одного `assistantMessageID`, затем обработка native lif (teamlead/cycle-7/debate/d1/realist.md) ; visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3818,bridges/opencode-zen-bridge/server.py:3829,bridges/opencode-zen-bridge/server.py:3309,bridges/opencode-zen-bridge/server.py:3316; fix=в окне зак (teamlead/cycle-7/debate/d1/visionary.md)
- text (дословно, R1 visionary):
> F-003 [pre-existing]
>    
>    priority: blocking  
>    locations: `bridges/opencode-zen-bridge/server.py:3818`, `bridges/opencode-zen-bridge/server.py:3829`, `bridges/opencode-zen-bridge/server.py:3309`, `bridges/opencode-zen-bridge/server.py:3316`  
>    Правило: REQ-011, REQ-012, AC-016, AC-017; полнота преобразования native tool calls.  
>    Evidence: после первого завершённого native-вызова при `emulate_tools` устанавливается `terminal="tool_calls"`, затем вызывается `_drain_serve_step_usage()` и выполняется `break`. Дрейнер пропускает любое событие, отличное от `session.step.ended`. Поэтому последовательность `called(c1,m1) → called(c2,m1) → step.ended(m1)` выдаёт только `c1`. Новый тест FU-001 проверяет исключение вызова из другого сообщения `m2`, но не сохранение второго вызова из `m1`.  
>    Исправление: в ограниченном окне закрытия шага обрабатывать native lifecycle текущего сообщения и его usage; события следующего сообщения исключать.  
>    Проверка: два разных native-вызова одного шага приходят в SSE и JSON ровно по одному разу, usage учитывается один раз, вызов следующего шага отсутствует.

### F-004
- origin: visionary · R1 · visionary-F-004
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AMEND, visionary=AMEND
- dissent: realist d1 «AMEND F-004 priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:5904`, `bridges/opencode-zen-bridge/server.py:6536`; fix=прерываемые общим дедлайном/отменой ожидания gate+l» → teamlead/cycle-7/debate/d1/realist.md ; visionary d1 «AMEND F-004 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5904,bridges/opencode-zen-bridge/server.py:5905,bridges/opencode-zen-bridge/server.py:6536,bridges/opencode-z» → teamlead/cycle-7/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:5904`, `bridges/opencode-zen-bridge/server.py:6536`; fix=прерываемые общим дедлайном/отменой ожидания gate+limiter — как follow-up — причина: `serve (teamlead/cycle-7/debate/d1/realist.md) ; visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5904,bridges/opencode-zen-bridge/server.py:5905,bridges/opencode-zen-bridge/server.py:6536,bridges/opencode-zen-bridge/server.py:7194; fix=прерывать  (teamlead/cycle-7/debate/d1/visionary.md)
- text (дословно, R1 visionary):
> F-004 [pre-existing]
>    
>    priority: blocking  
>    locations: `bridges/opencode-zen-bridge/server.py:5353`, `bridges/opencode-zen-bridge/server.py:5904`, `bridges/opencode-zen-bridge/server.py:6536`, `bridges/opencode-zen-bridge/server.py:7194`  
>    Правило: REQ-008, R-BULK-I1, feature.md §2 — дедлайн и отмена на каждом шаге I/O.  
>    Evidence: `gate.acquire()` использует собственный `STARTUP_WAIT_S`, не остаток запроса; затем limiter может отдельно спать до `SPAWN_WAIT_MAX_S`. Между ожиданиями нет проверки клиента. При стандартных пределах участок может занять около 10 секунд, превышая требование обнаружения отключения ≤5 секунд. На legacy-путях после этих ожиданий отсутствует повторная проверка дедлайна непосредственно перед `_spawn_with_stdin`, поэтому процесс может запускаться уже после истечения бюджета.  
>    Исправление: сделать ожидания ограниченными общим дедлайном и прерываемыми отменой; перед каждым spawn повторно проверять обе причины остановки и освобождать резервы.  
>    Проверка: занятый gate, затем задержанный limiter и FIN клиента; обнаружение ≤5 секунд, отсутствие новых запусков после отмены или истечения deadline, освобождённые слоты и резервы.
>
>    Verify-Fixed RW-004: PASS для HTTP-фаз — `server.py:3458`, `server.py:3496`, `server.py:3174`; соответствующий тест `tests/test_realtime_reasoning.py:2704` входит в зелёный L2.

### F-005
- origin: visionary · R1 · visionary-F-005
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AMEND, visionary=AUTHOR
- dissent: realist d1 «AMEND F-005 priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:5995`, `bridges/opencode-zen-bridge/server.py:7284`; fix=выделить стартовый `ServeStartupDeadlineExceeded` н» → teamlead/cycle-7/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:5995`, `bridges/opencode-zen-bridge/server.py:7284`; fix=выделить стартовый `ServeStartupDeadlineExceeded` нейтральным исходом, генерационный `timeo (teamlead/cycle-7/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-005 [pre-existing]
>    
>    priority: blocking  
>    locations: `bridges/opencode-zen-bridge/server.py:3382`, `bridges/opencode-zen-bridge/server.py:5995`, `bridges/opencode-zen-bridge/server.py:7284`  
>    Правило: FALLBACK_DECISION_TABLE, строка `client cancel/deadline/budget exhausted`: fail-closed, оба инкремента равны 0; R-BULK-I3.  
>    Evidence: `ServeStartupDeadlineExceeded` превращается в `exit_reason="timeout"`. SSE и JSON включают `timeout` в общую ветку, вызывающую `attempts.attempt_done(True, False)`. Последующий `commit()` увеличивает счётчик upstream breaker даже при локальном истечении бюджета до доставки prompt. Серия таких запросов может открыть breaker здорового провайдера.  
>    Исправление: выделить глобальный timeout как нейтральный терминальный исход; оставить отказами соответствующие фазовые watchdog и подтверждённые upstream failures.  
>    Проверка: повторные deadline-отказы до prompt в SSE/JSON не увеличивают failures и не открывают breaker; first-token/stall failures продолжают учитываться.

### F-006
- origin: visionary · R1 · visionary-F-006
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-006 [pre-existing]
>    
>    priority: non-blocking  
>    locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:900`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:922`  
>    Правило: REQ-020, AC-026; testing.md «Тест должен воспроизводить баг».  
>    Evidence: сырой RED-лог для `test_ac026_realtime_chunks_before_upstream_end` показывает `AttributeError` на `server.DYNAMIC_CONFIG_PATH` в `setUp`. Значение `red_sensitivity_rc=1` достоверно, но падение не доказывает воспроизведение задержанной доставки на клиентском сокете. GREEN измеряет требуемое поведение.  
>    Исправление: обеспечить запуск сокетного оракула на baseline без зависимости setup от новых символов либо приложить отдельный совместимый поведенческий RED-прогон.  
>    Проверка: baseline падает именно на количестве/времени клиентских дельт при продолжающемся upstream; кандидат проходит тот же оракул.

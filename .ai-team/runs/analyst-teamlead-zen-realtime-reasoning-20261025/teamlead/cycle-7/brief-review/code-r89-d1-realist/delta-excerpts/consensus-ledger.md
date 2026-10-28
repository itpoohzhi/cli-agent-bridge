# Черновой леджер совещания Совета Тимлидов по коду (цикл 7, после R1 r82, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `6` (`F-001..F-006`: `skeptic` `нет (0 находок, PASS)`, `realist` `нет (0 находок, ACCEPT)`, `visionary` `F-001..F-006`).
- Открытых blocking (`OPEN_BLOCKING`): `5`; открытых non-blocking: `1`.

### F-001
- origin: visionary · R1 · visionary-F-001
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
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
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
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
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
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
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
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
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
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
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
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

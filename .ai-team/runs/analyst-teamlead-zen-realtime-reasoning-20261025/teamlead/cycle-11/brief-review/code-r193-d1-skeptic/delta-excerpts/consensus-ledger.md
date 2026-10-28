# Черновой леджер совещания Совета Тимлидов по коду (цикл 11, после R1 r158, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `5` (`F-001..F-005`: `skeptic` `нет (0 находок, ACCEPT)`, `realist` `нет (0 находок, ACCEPT)`, `visionary` `F-001..F-005`).
- Открытых blocking (`OPEN_BLOCKING`): `4`; открытых non-blocking: `1`.

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
> **F-001 [pre-existing] — управляющие сетевые ошибки разрешают повтор.**
>
> - priority: **blocking**
> - locations: `bridges/opencode-zen-bridge/server.py:4231`, `:4239`, `:4288`, `:4296`, `:4440`.
> - Правило: REQ-012; `FALLBACK_DECISION_TABLE`: permission/form/security failure → `fail_closed`; SK-P security/error-handling.
> - Evidence: проверки HTTP-статусов явно поднимают `ServeSecurityError`, но `OSError`/`HTTPException` из тех же `_ctrl_http` попадают в общий обработчик. После доставки prompt он устанавливает `exit_reason="prompt_error"` и `transient_error=True`; обе внешние ветви допускают retry.
> - Воспроизводимый сценарий по коду: после prompt headers получить `permission.asked`; на `/permission/.../reply` получить `ConnectionResetError`. Вместо терминального security failure запускается следующая serve-попытка.
> - Исправление: сетевые и протокольные отказы reject/cancel/interrupt переводить в `ServeSecurityError` с обязательным cleanup. Сохранить отдельную нейтральную классификацию отмены клиента и общего deadline.
> - Проверка: инъекции отказа на всех четырёх перечисленных управляющих вызовах, SSE/JSON, `auto`: одна serve-попытка, ноль run-fallback, отсутствие успешного завершения, группа остановлена. Успешный reject в drain должен продолжить проходить.

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
> **F-002 [pre-existing] — JSON-retry теряет результаты предыдущей попытки.**
>
> - priority: **blocking**
> - locations: `bridges/opencode-zen-bridge/server.py:5868`, `:8099`, `:8110`, `:8184`.
> - Правило: REQ-005, REQ-009; SK-T сохранность результата потокового захвата; SK-P testing «полнота против эталона».
> - Evidence: `Run.execute` после watchdog вызывает `self.close(); continue`, возвращая вызывающему коду только последнюю попытку. `_serve_json_serve` на watchdog/protocol/prompt-status retry выполняет `continue` раньше `reasonings_all.extend(reasonings)` и сохранения текста.
> - Воспроизводимый сценарий по коду: первая попытка отдаёт reasoning `A` и текст `начало`, затем stall; вторая отдаёт reasoning `B` и текст `конец`. Serve JSON сохраняет только вторую пару, тогда как SSE уже передал первую клиенту. Legacy JSON также теряет первый результат внутри `Run.execute`.
> - Исправление: перед разрешённым повтором сохранять reasoning без дедупликации, нормализованный текст с предусмотренной prefix-dedup и доступный usage. Неподтверждённые native calls сохранять для публикации нельзя.
> - Проверка: для run/serve JSON проверить частичный вывод → watchdog → успешный повтор, а также serve prompt-status retry после SSE-вывода. Сверять точные итоговые данные и usage; исключить публикацию незавершённых tool calls.

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
> **F-003 [pre-existing] — секундное окно ограничивает активный инструментальный шаг.**
>
> - priority: **blocking**
> - locations: `bridges/opencode-zen-bridge/server.py:1581`, `:3594`, `:3759`, `:4362`.
> - Правило: REQ-007, REQ-011; SK-T независимый сигнал полноты и ограниченные I/O-ожидания.
> - Evidence: `_STEP_DRAIN_WINDOW_S = 1.0`; после первого native call в drain передаётся абсолютный срок `now + 1.0`. Поступающие события его не продлевают. По истечении срока возникает `ServeProtocolError("incomplete tool step without step.ended")`.
> - Воспроизводимый сценарий по коду: пять вызовов одного assistant message приходят в моменты 0, 0.3, 0.6, 0.9, 1.2 с; `step.ended` — в 1.3 с. Поток активен, лимиты числа/байтов не превышены, но попытка завершается ошибкой примерно через секунду.
> - Исправление: ожидать подтверждение шага в пределах общего deadline и согласованного watchdog паузы; учитывать активность событий. Сохранить удержание pending calls до `step.ended`.
> - Проверка: управляемые часы и многовызовный шаг длительностью более секунды: все calls и usage публикуются ровно один раз. Отдельно проверить реальный stall, EOF и общий deadline без публикации pending calls.

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
> **F-004 [pre-existing] — unmapped-exhaustion в serve JSON меняет результат legacy.**
>
> - priority: **blocking**
> - locations: `bridges/opencode-zen-bridge/server.py:8219`, `:8223`, `:8259`, `:8261`; legacy-эталон — `:8519`.
> - Правило: REQ-002, REQ-012, AC-017; SK-P scope-and-contracts.
> - Evidence: serve JSON при исчерпании unmapped выполняет `break`, после чего без текста возвращает `502 "serve produced no text"`. Legacy JSON добавляет уведомление о недоступном инструменте и возвращает обычный ответ с `finish_reason="stop"`. Serve SSE также добавляет уведомление.
> - Воспроизводимый сценарий по коду: каждая разрешённая попытка завершается только unmapped-вызовом `todoread`, без текста и доступных DSH-вызовов.
> - Исправление: при исчерпании unmapped восстановить согласованный legacy-исход, включая уведомление и finish reason; общий spawn/retry budget сохранить.
> - Проверка: сравнительная матрица serve/run × SSE/JSON для исчерпания по локальному лимиту, общему spawn cap и retry budget; сверять статус, уведомление и finish reason.

### F-005
- origin: visionary · R1 · visionary-F-005
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
> **F-005 — матрица прослеживаемости содержит устаревшие имена оракулов.**
>
> - priority: **non-blocking**, продолжение FU-001.
> - locations: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-traceability.md:23`, `:30`, `:32`, `:33`.
> - Правило: проверяемая прослеживаемость требований и свидетельств.
> - Evidence: строки ссылаются на шесть отсутствующих имён: `test_c11_rw001_drain_text_delivered_with_emulated_tools_sse_and_json`, `test_c11_rw003_slow_client_before_first_token_releases_slot_and_group`, `test_c11_rw004_client_gone_callback_error_logged_and_socket_aborted`, `test_c11_rw002_prompt_and_first_event_respect_aux_budget`, `test_c11_rw005_reasoning_marker_with_complete_text_matches_run_under_recovery`, `test_c11_rw006_tool_name_and_call_id_counted_in_state_bytes_main_and_drain`. Фактические оракулы существуют под другими именами. В строке 23 также осталось неточное `session.tool.delta`.
> - Исправление: заменить ссылки на фактические test IDs, для RW-002 перечислить его пять реальных оракулов; уточнить событие `session.tool.input.delta`.
> - Проверка: все test IDs матрицы разрешаются в кандидате; названия событий соответствуют wire-фикстурам. Подтверждённые результаты L2 этим замечанием не отменяются.

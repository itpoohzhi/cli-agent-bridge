# Черновой леджер совещания Совета Тимлидов по коду (цикл 9, после R1 r140, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `8` (`F-001..F-008`: `skeptic` `F-001`, `realist` `нет (0 находок, ACCEPT)`, `visionary` `F-002..F-008`).
- Открытых blocking (`OPEN_BLOCKING`): `7`; открытых non-blocking: `1`.

### F-001
- origin: skeptic · R1 · skeptic-F-001
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-001
> priority: blocking
> file: bridges/opencode-zen-bridge/server.py:3373, bridges/opencode-zen-bridge/server.py:3377, bridges/opencode-zen-bridge/server.py:3392, bridges/opencode-zen-bridge/server.py:3401, bridges/opencode-zen-bridge/server.py:4001, bridges/opencode-zen-bridge/server.py:4008
> rule: REQ-001, REQ-012, RW-001 blast-radius (окно дочитывания шага)
> evidence: после `on_tool` цикл входит в `_finish_serve_tool_step` и единственный читатель очереди — `_drain_serve_step_usage`. Там после фильтра сессии обрабатываются только `mapped[0] == "tool_event"` и `mapped[0] == "step_finish"`; иное событие не возвращается в очередь и не передаётся в `on_reasoning`/`on_text` и не проходит reject/cancel, которые основной цикл делает для `permission` (`server.py:3940-3958`) и `form.created` (`server.py:3881-3904`).
> expected: в том же окне `min(1.0, deadline-now)` доставлять reasoning/text той же сессии, на `permission`/`form.created` выполнять тот же fail-closed, на `error` завершать попытку ошибкой; `step.ended` по-прежнему обязателен для `terminal=tool_calls`.
> check: SSE и JSON, последовательность `tool.called` → `reasoning.delta` → `permission.asked` → `step.ended`: дельта видна клиенту, в FakeServe записан reject, финальный `finish_reason=tool_calls` один, usage шага сохранён. Вторая последовательность с `form.created` без `step.ended`: нет `finish_reason=tool_calls`, в логе `invalid_serve_event` или security failure, есть cancel.

### F-002
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
> **F-001 — [pre-existing] Потеря ошибок и управляющих событий при дочитывании шага.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3373`, `:3377`, `:3392`.
>    - **Правило:** REQ-011, REQ-012; `feature.md` §2 — полнота захвата потока; fail-closed для детерминированных ошибок.
>    - **Evidence:** после `_map_serve_event(event)` предусмотрены только ветви `"tool_event"` и `"step_finish"`. Событие `session.execution.failed`/`session.step.failed` превращается в `"error"` и теряется. `permission.asked` также не получает reject; `form.created` с вложенным `form.sessionID` отбрасывается ещё проверкой `data.get("sessionID")`.
>    - **Следствие:** ошибка 401/403 внутри drain при последующем EOF становится повторяемым `invalid_serve_event`; при последующем `step.ended` возможен успешный `tool_calls` вместо обработки ошибки. Обработчики reject/cancel из основного цикла обходятся.
>    - **Исправление:** сохранить в drain семантику ошибок, permission и form основного обработчика; не считать `step.ended` успешным подтверждением после терминального отказа.
>    - **Критерий проверки:** для SSE и JSON проверить последовательности `tool → error → EOF`, `tool → error → step.ended`, `tool → permission`, `tool → form`. Детерминированный отказ не повторяется; reject/cancel выполняются; cleanup обязателен.

### F-003
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
> **F-002 — Неподтверждённые tool calls переживают неуспешную попытку.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3390`, `:3397`, `:4001`, `:4008`, `:6056`, `:6227`, `:6682`.
>    - **Правило:** RW-001; REQ-011; независимое подтверждение полноты результата.
>    - **Evidence:** `on_tool(done[1])` вызывается до `_finish_serve_tool_step()`. Потоковый callback сразу вызывает `emit_tool_call()`, добавляющий вызов в общий `tool_calls`. При неподтверждённом шаге разрешается `continue` следующей попытки; общий список не откатывается.
>    - **Следствие:** попытка A выдаёт `bash("A")`, затем EOF без `step.ended`; попытка B успешно выдаёт другой вызов. Финальный ответ может содержать оба вызова, включая вызов неподтверждённого шага A. Новая проверка с `MAX_TOTAL_SPAWNS=1` этот переход не покрывает.
>    - **Исправление:** накапливать native-вызовы закрываемого шага до подтверждения и публиковать их после него. Уже опубликованный неподтверждённый вызов должен исключать последующее успешное завершение запроса с накопленным набором.
>    - **Критерий проверки:** при разрешённых повторах сценарии EOF/истечения окна первой попытки и успешного другого tool call второй попытки не возвращают вызовы первой попытки.

### F-004
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
> **F-003 — [pre-existing] Изменяются модельные байты reasoning.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:5708`, `:5988`, `:7005`.
>    - **Правило:** REQ-005/AC-006 — модельное размышление не модифицируется.
>    - **Evidence:** `_strip_interrupted()` применяет `_INTERRUPTED_RE.sub("", text)` непосредственно к reasoning. Целый маркер удаляется, а тот же маркер, разделённый между дельтами, сохраняется.
>    - **Исправление:** передавать модельный reasoning без текстовой фильтрации; распознавание служебных продолжений отделить от содержимого размышления.
>    - **Критерий проверки:** reasoning с обоими interruption-маркерами сохраняется побайтово при всех границах разбиения; синтетические статусы исключаются отдельно.

### F-005
- origin: visionary · R1 · visionary-F-004
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
> **F-004 — Устаревшие ссылки матрицы прослеживаемости.**
>    - **priority:** non-blocking.
>    - **locations:** `teamlead/verification-traceability.md:23`, `:27`, `:28`, `:29`, `:30`, `:31`.
>    - **Правило:** проверяемая привязка требования к фактически существующему оракулу.
>    - **Evidence:** матрица упоминает отсутствующие в кандидате `message.part.delta`, `_SSEByteCapReader` и следующие методы:
>      `test_c7_rw001_nonstream_json_watchdog_retries_and_preserves_exit_reason`,
>      `test_c7_rw003_legacy_sse_watchdog_classified_as_transient_in_attempt_done`,
>      `test_c8_fu002_startup_gate_and_spawn_limiter_abort_on_deadline_and_client_gone`,
>      `test_c7_rw004_startup_http_phases_enforce_phase_deadlines_on_dripping_headers`,
>      `test_c9_rw002_first_event_timeout_in_prompt_async_retries_without_run_fallback`,
>      `test_c8_rw001_early_execution_failed_429_503_before_tokens_retries_on_serve_without_run_fallback`,
>      `test_c8_rw003_local_request_deadline_timeout_does_not_increment_cb_or_retry`,
>      `test_c7_rw002_first_event_before_prompt_headers_closes_delivery_barrier`,
>      `test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_while_valid_pair_passes`,
>      `test_c9_rw001_drain_serve_step_usage_preserves_sse_line_and_body_byte_caps_with_tail_buffer`,
>      `test_c8_fu001_drain_serve_step_usage_collects_additional_same_message_native_tool_calls`,
>      `test_c7_fu001_native_tool_call_drains_step_ended_for_usage`.
>    - **Исправление:** заменить ссылки фактическими именами методов и реализации.
>    - **Критерий проверки:** каждая ссылка разрешается в конкретное определение; отдельные доказательства выполнения берутся из актуального L2. Сам факт полного зелёного прогона этим замечанием не оспаривается.

### F-006
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
> **F-005 — [pre-existing] Не выполняется бюджет вспомогательного I/O.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3232`, `:3240`, `:6227`, `:7573`.
>    - **Правило:** `R-BULK-I1`: сумма вспомогательных ожиданий всех попыток ≤ `0.30 × SLA_p99_s`.
>    - **Evidence:** конверт задаёт `SLA_p99_s=180`, следовательно предел — **54 с**. `_open_serve_events` допускает до `FIRST_EVENT_TIMEOUT_S=20` с на подписку каждой попытки. Три подписки, успешно открывшиеся перед своим пределом и затем завершившиеся повторяемой протокольной ошибкой, расходуют почти **60 с** только на эту фазу. Readiness, create, handshake, gate, backoff и cleanup добавляются сверх этого.
>    - **Исправление:** выделить общий вспомогательный бюджет запроса и передавать его остаток во все startup/control-фазы и повторы; согласовать фазовые потолки с этим бюджетом.
>    - **Критерий проверки:** управляемые часы подтверждают сумму ≤54 с и отсутствие следующего I/O после исчерпания бюджета.

### F-007
- origin: visionary · R1 · visionary-F-006
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
> **F-006 — [pre-existing] Байтовый предел не охватывает накопление native-инструментов.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3154`, `:3162`, `:3168`, `:3171`, `:3381`, `:3483`, `:3990`.
>    - **Правило:** `HL-ENV-01`, ограниченность накопленного состояния динамического источника.
>    - **Evidence:** `_serve_accumulated_bytes()` считает только `"reasoning"` и `"text"`. `_ServeToolState.tools` сохраняет произвольное число call ID и их `text`/`input`; освобождение wire-резерва очереди не освобождает это состояние. Поток уникальных `session.tool.input.ended` до первого завершённого вызова обходит оба новых лимита.
>    - **Исправление:** ограничить количество native-вызовов и совокупный размер удерживаемых аргументов, включая замену существующего значения и оба пути потребления событий.
>    - **Критерий проверки:** поток уникальных незавершённых native-вызовов превышает установленный предел, завершается управляемой ошибкой и cleanup; потребление памяти имеет вычислимую верхнюю границу.

### F-008
- origin: visionary · R1 · visionary-F-007
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
> **F-007 — [pre-existing] Блокирующая запись клиенту обходит watchdog и общий deadline.**
>    - **priority:** blocking.
>    - **locations:** `bridges/opencode-zen-bridge/server.py:5835`, `:5998`, `:6595`.
>    - **Правило:** `feature.md` §2 — таймаут на каждом шаге I/O; ограниченное время владения ресурсами.
>    - **Evidence:** `_LockedWfile.write()` выполняет блокирующий `inner.write()` под замком. Callback reasoning вызывается из контролирующего цикла попытки. При клиенте, который сохраняет соединение, но прекращает читать, заполнение TCP-буфера останавливает цикл до следующей проверки deadline/watchdog. Таймер статуса использует ту же блокирующую запись.
>    - **Исправление:** ограничить downstream-запись оставшимся сроком и обеспечить отмену, которая не зависит от освобождения того же замка.
>    - **Критерий проверки:** реальный сокетный клиент прекращает чтение после заголовков; достаточно большой поток приводит к ограниченному завершению, остановке группы и возврату слота.

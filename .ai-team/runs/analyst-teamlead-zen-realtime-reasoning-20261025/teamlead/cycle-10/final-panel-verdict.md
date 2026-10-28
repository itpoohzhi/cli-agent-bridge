# Итоговый консенсус-леджер Совета Тимлидов по коду (цикл 10, после R1 r149 + D1 r154, run analyst-teamlead-zen-realtime-reasoning-20261025)

- **Раунд R1 (`panel/council/r149`):** `skeptic` (`grok-4.7-high` via `cursor-agent`) = `NEEDS WORK` (4 находки `F-001..F-004`), `realist` (`gpt-6.1-sol-high` via `codex`) = `NEEDS WORK` (9 находок `F-005..F-013`), `visionary` (`muse-wonder-full-1.0` via `muse`) = `ACCEPT` (0 находок).
- **Раунд D1 (`panel/council/r154`):** `skeptic` (`muse-wonder-full-1.0` via `muse`) = `NEEDS WORK`, `realist` (`grok-4.7-high` via `cursor-agent`) = `NEEDS WORK`, `visionary` (`gpt-6.1-sol-high` via `codex`) = `NEEDS WORK`.
- **Сводка по 13 находкам (`F-001..F-013`) после D1 (`r154`):**
  - `F-001` (`skeptic-F-001`, объединён с дублем `F-005` `realist-F-001`): `status: ACCEPTED`, `priority: blocking` (`3/3`: `skeptic=AUTHOR/AGREE`, `realist=AMEND(blocking)`, `visionary=AGREE`) — **`RW-001`**.
  - `F-002` (`skeptic-F-002`, объединён с `F-008` `realist-F-004`): `status: ACCEPTED`, `priority: blocking` (`3/3`: `skeptic=AUTHOR/AGREE`, `realist=AGREE`, `visionary=AMEND(blocking)`) — **`RW-002`**.
  - `F-003` (`skeptic-F-003`, объединён с дублем `F-009` `realist-F-005`): `status: ACCEPTED`, `priority: blocking` (`3/3`: `skeptic=AUTHOR/AGREE`, `realist=AGREE`, `visionary=AMEND(blocking)`) — **`RW-003`**.
  - `F-004` (`skeptic-F-004`, объединён с дублем `F-010` `realist-F-006`): `status: ACCEPTED`, `priority: blocking` (`3/3`: `skeptic=AUTHOR/AGREE`, `realist=AGREE`, `visionary=AGREE`) — **`RW-004`**.
  - `F-005` (`realist-F-001`): `status: WITHDRAWN_DUPLICATE` (`duplicate_of: F-001`, снят `realist` через `WITHDRAW` и помечен `duplicate_of:F-001` у `skeptic` и `visionary`).
  - `F-006` (`realist-F-002`): `status: ACCEPTED`, `priority: blocking` (`3/3`: `skeptic=AGREE`, `realist=AUTHOR/AGREE`, `visionary=AGREE`) — **`RW-005`**.
  - `F-007` (`realist-F-003`): `status: ACCEPTED`, `priority: blocking` (`3/3`: `skeptic=AGREE`, `realist=AUTHOR/AGREE`, `visionary=AGREE`) — **`RW-006`**.
  - `F-008` (`realist-F-004`): `status: MERGED_DUPLICATE` (`duplicate_of: F-002`, объединён в `RW-002` по `DISPUTE duplicate_of:F-002` у `skeptic` и `visionary` + `AMEND F-008` у `realist`).
  - `F-009` (`realist-F-005`): `status: WITHDRAWN_DUPLICATE` (`duplicate_of: F-003`, снят `realist` через `WITHDRAW` и помечен `duplicate_of:F-003` у `skeptic` и `visionary`).
  - `F-010` (`realist-F-006`): `status: WITHDRAWN_DUPLICATE` (`duplicate_of: F-004`, снят `realist` через `WITHDRAW` и помечен `duplicate_of:F-004` у `skeptic` и `visionary`).
  - `F-011` (`realist-F-007 [pre-existing]`): `status: DISMISSED` (`2/3`: `realist=WITHDRAW`, `skeptic=DISPUTE out_of_scope` по `council.md` §3 «Diff-scope повторного цикла» и обязательному гейту `VER-002` `unittest discover` `AC-022`; `visionary=AGREE`).
  - `F-012` (`realist-F-008 [pre-existing]`): `status: DISMISSED` (`2/3`: `realist=WITHDRAW`, `skeptic=DISPUTE out_of_scope` по `council.md` §3 «Diff-scope повторного цикла» и инварианту `0` внешних runtime-зависимостей вне Python 3.14 stdlib / ADR-0001 `dynamic_config.json`; `visionary=AMEND`).
  - `F-013` (`realist-F-009 [pre-existing]`): `status: ACCEPTED`, `priority: non-blocking` (`3/3`: `skeptic=AGREE`, `realist=AUTHOR`, `visionary=AGREE`) — **`FU-001`**.

### F-001 (merged with F-005) -> RW-001
- origin: skeptic · R1 · skeptic-F-001 (+ realist-F-001)
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-001)
- resolved_in: D1 (r154)
- votes: D1 skeptic=AGREE, realist=AMEND(blocking), visionary=AGREE (F-005 withdrawn as duplicate_of:F-001)
- requirement: В `_drain_serve_step_usage` (`bridges/opencode-zen-bridge/server.py:3562-3564`, потребители `:6573`, `:7961`, `:8121`) передавать текстовые дельты `session.text.delta` в `text_cb` и при `emulate_tools=True` (через тот же безопасный путь `ToolCallParser` / `texts.append`, что и в основном цикле, продолжая удерживать публикацию нативных `tool_call` до подтверждённого `session.step.ended`), чтобы текст шага между `tool.called` и `session.step.ended` не терялся ни в SSE, ни в non-stream JSON. Добавить SSE- и JSON-оракулы последовательности `tool.called -> session.text.delta ("хвост") -> session.step.ended` при включённых инструментах: в ответе клиенту присутствует текст «хвост» ровно один раз и ровно один `tool_call` с `finish_reason="tool_calls"`.

### F-002 (merged with F-008) -> RW-002
- origin: skeptic · R1 · skeptic-F-002 (+ realist-F-004)
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-002)
- resolved_in: D1 (r154)
- votes: D1 skeptic=AGREE, realist=AGREE/AMEND, visionary=AMEND(blocking)
- requirement: Замкнуть применение общего вспомогательного бюджета `_AuxIoBudget` (`_AUX_IO_BUDGET_S = 54.0` с по `R-BULK-I1` и `feature.md`) на всех точках вспомогательного и управляющего I/O до начала модельного стриминга: (1) в `_prompt_worker` (`server.py:4045-4068`) не запускать HTTP prompt при `aux.exhausted()`, передавать в `_serve_http` `deadline=aux.deadline(attempt_deadline)` и `timeout=min(65.0, max(0.05, aux.remaining_s()))` для ожидания HTTP-заголовков prompt, и списывать время ожидания заголовков prompt в `aux` (отделив последующее ожидание первого модельного токена после `session.execution.started` от `aux`-фазы); (2) в `_open_serve_events` (`server.py:2472`, `:3331`, `:3996`) учитывать в `aux` ожидание подписки вплоть до получения первого SSE-события (`first_event_timeout`), а также списывать управляющие вызовы `permission`/`form` (вне резерва `cleanup()`) в `aux`; (3) добавить в `tests/test_realtime_reasoning.py` оракул реальных точек вызова `_serve_http` / prompt и подписки с управляемыми часами: при остатке `aux = 1.0` с зависший prompt обрывается по `aux.deadline` быстрее `2.0` с, суммарный `spent_s <= 54.0` с по нескольким попыткам, и при `aux.exhausted()` следующий вспомогательный I/O не начинается.

### F-003 (merged with F-009) -> RW-003
- origin: skeptic · R1 · skeptic-F-003 (+ realist-F-005)
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-003)
- resolved_in: D1 (r154)
- votes: D1 skeptic=AGREE, realist=AGREE, visionary=AMEND(blocking) (F-009 withdrawn as duplicate_of:F-003)
- requirement: Распространить ограничение downstream-записи (`_LockedWfile` с таймаутом `min(_DOWNSTREAM_WRITE_TIMEOUT_S, remaining_deadline)`) на всю цепочку начальной отправки клиенту в SSE (`bridges/opencode-zen-bridge/server.py:6997`, `:7004-7005`, `:7032-7047`): установить ограничение сокета / обёртку `_LockedWfile` до `self.end_headers()` и отправки первого `role="assistant"` чанка, а запись в таймере `_initial_status` проводить через тот же механизм ограниченной записи `_LockedWfile` без повторного захвата нерекурсивного замка, при ошибке/таймауте любой из этих записей выставляя `_downstream_client_gone`, вызывая `abort_socket()` и обеспечивая освобождение bulkhead-слота (`in_use == 0`) и остановку группы процессов `serve` быстрее `7.0` с. Добавить оракулы инъекции блокировки/ошибки на отправке заголовков, начального `role`-чанка и `_initial_status` (включая сокетный тест с полным окном до первого токена модели).

### F-004 (merged with F-010) -> RW-004
- origin: skeptic · R1 · skeptic-F-004 (+ realist-F-006)
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-004)
- resolved_in: D1 (r154)
- votes: D1 skeptic=AGREE, realist=AGREE, visionary=AGREE (F-010 withdrawn as duplicate_of:F-004)
- requirement: В `_LockedWfile._mark_client_gone` (`bridges/opencode-zen-bridge/server.py:6194-6197`) устранить нарушение запрета №1 `agents/python-standards.md` (`except Exception: pass`): вызывать `self.abort_socket()` гарантированно в `finally:`, а при перехвате сбоя callback `_on_client_gone` логировать диагностику через `_log` с маскированием секретов (`_mask_secrets`) без глушения в `pass`. Добавить тест: callback, бросающий `RuntimeError`, записывает маскированную диагностику в `bridge.log` и не препятствует `abort_socket()`.

### F-006 -> RW-005
- origin: realist · R1 · realist-F-002
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-005)
- resolved_in: D1 (r154)
- votes: D1 skeptic=AGREE, realist=AUTHOR/AGREE, visionary=AGREE
- requirement: В обеих успешных `serve`-ветках (SSE `bridges/opencode-zen-bridge/server.py:6751` и non-stream JSON `server.py:8169-8171`) передавать в классификатор `_incomplete_step_signal` очищенную через `_strip_interrupted(...)` копию `reasoning` (как в legacy `run` на `server.py:7678`, `:8473`), сохраняя при этом исходные побайтовые байты `reasoning_content` для клиента (`REQ-005`/`AC-006`), чтобы сохранённый в `reasoning` маркер прерывания при готовом текстовом ответе не вызывал ложный повтор попытки при включённом `STEP_RECOVERY_ENABLED`. Добавить оракулы SSE и JSON с включённым `STEP_RECOVERY_ENABLED=true`, доступными `tools`, обычным `tool_choice`, готовым текстовым ответом и `reasoning` с interruption-маркером: `serve` и `run` делают одинаковое число попыток (`1`), а `reasoning_content` клиенту остаётся побайтово неизменным.

### F-007 -> RW-006
- origin: realist · R1 · realist-F-003
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-006)
- resolved_in: D1 (r154)
- votes: D1 skeptic=AGREE, realist=AUTHOR/AGREE, visionary=AGREE
- requirement: В `_ServeToolState.feed` (`bridges/opencode-zen-bridge/server.py:3237`) и `_serve_tool_state_bytes` (`server.py:3679-3704`) включить UTF-8 размер всех удерживаемых строковых полей (`call_id` и `name`, наряду с `text` и сериализованным `input`) в байтовый учёт `_serve_tool_state_bytes` / `_serve_accumulated_bytes` (и при необходимости задать разумный потолок длины `call_id`/`name`), чтобы превышение совокупного размера через `call_id`/`name` как в основном цикле, так и в окне дренажа вызывало управляемый `ServeProtocolError` с `cleanup()` и отсутствием опубликованных pending-вызовов (`HL-ENV-01`). Добавить соответствующий тест для main и drain в `tests/test_realtime_reasoning.py`.

### F-013 -> FU-001
- origin: realist · R1 · realist-F-009
- rev: 2
- priority: non-blocking
- status: ACCEPTED
- outcome: FOLLOW_UP (FU-001)
- resolved_in: D1 (r154)
- votes: D1 skeptic=AGREE, realist=AUTHOR, visionary=AGREE
- requirement: В `teamlead/verification-traceability.md` (строки `REQ-001` и `REQ-010..REQ-012`) указать фактические имена событий протокола `session.*` (`session.reasoning.delta`, `session.text.delta`, `session.tool.delta`, `session.tool.called`, `session.step.ended`, `permission.asked`, `form.created`) вместо `message.part.updated` и указать фактическую политику `ask_reject` (default) с описанием обработки `permission.asked` в main и drain.

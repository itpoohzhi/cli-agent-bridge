# Итоговый консенсус-леджер Совета Тимлидов по коду (цикл 9, после R1 r140 + D1 r144, run analyst-teamlead-zen-realtime-reasoning-20261025)

- **Раунд R1 (`panel/council/r140`):** `skeptic` (`grok-4.7-high` via `cursor-agent`) = `NEEDS WORK`, `realist` (`muse-wonder-full-1.0` via `muse`) = `ACCEPT` (0 находок), `visionary` (`gpt-6.1-sol-high` via `codex`) = `NEEDS WORK`.
- **Раунд D1 (`panel/council/r144`):** `skeptic` (`grok-4.7-high` via `cursor-agent`) = `NEEDS WORK`, `realist` (`gpt-6.1-sol-high` via `codex`) = `NEEDS WORK`, `visionary` (`muse-wonder-full-1.0` via `muse`) = `NEEDS WORK`.
- **Сводка по 8 находкам (`F-001..F-008`) после D1 (`r144`):**
  - `F-001` (`skeptic-F-001`, объединён с дублем `F-002` `visionary-F-001`): `status: ACCEPTED`, `priority: blocking` (`3/3`: `skeptic=AUTHOR/AGREE`, `realist=AGREE`, `visionary=AGREE`) — `RW-001`.
  - `F-002` (`visionary-F-001`): `status: WITHDRAWN_DUPLICATE` (`duplicate_of: F-001`, снят автором `visionary` в D1 и помечен `duplicate_of:F-001` у `realist`).
  - `F-003` (`visionary-F-002`): `status: ACCEPTED`, `priority: blocking` (`3/3`: `skeptic=AMEND(blocking)`, `realist=AMEND(blocking)`, `visionary=AUTHOR`) — `RW-002`.
  - `F-004` (`visionary-F-003`): `status: ACCEPTED`, `priority: blocking` (`2/3`: `skeptic=AGREE(blocking)`, `realist=AGREE(blocking)`, `visionary=AMEND(non-blocking)`) — `RW-003`.
  - `F-005` (`visionary-F-004`): `status: ACCEPTED`, `priority: non-blocking` (`3/3` non-blocking) — `FU-001`.
  - `F-006` (`visionary-F-005`): `status: ACCEPTED`, `priority: non-blocking` (`2/3` `skeptic=AMEND(non-blocking)`, `visionary=AMEND(non-blocking)`, `realist=AGREE(blocking)`) — `FU-002` (реализуется в коде в этом же цикле для полного закрытия).
  - `F-007` (`visionary-F-006`): `status: ACCEPTED`, `priority: blocking` (`2/3`: `skeptic=AGREE(blocking)`, `realist=AGREE(blocking)`, `visionary=AMEND(non-blocking)`) — `RW-004`.
  - `F-008` (`visionary-F-007`): `status: ACCEPTED`, `priority: blocking` (`2/3`: `skeptic=AGREE(blocking)`, `realist=AGREE(blocking)`, `visionary=AMEND(non-blocking)`) — `RW-005`.

### F-001 (merged with F-002) -> RW-001
- origin: skeptic · R1 · skeptic-F-001 (+ visionary-F-001)
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-001)
- resolved_in: D1 (r144)
- votes: R1 skeptic=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AGREE (F-002 withdrawn as duplicate_of:F-001)
- requirement: В `_drain_serve_step_usage` (`bridges/opencode-zen-bridge/server.py:3373-3401`) в окне ожидания `session.step.ended` обрабатывать все значимые события сессии с той же семантикой, что в основном цикле `_serve_one_attempt`: (1) `form.created` проверять до верхнеуровневого фильтра `data.get("sessionID")` по `form.sessionID` (`server.py:3881-3904`), вызывать `cancel+interrupt` и завершать шаг `ServeSecurityError`; (2) `permission` (`permission.asked`) той же сессии отклонять через `reject+interrupt` и завершать попытку fail-closed (`ServeSecurityError` или управляемый отказ без `terminal="tool_calls"`); (3) `error` (`session.execution.failed` / `session.step.failed`) записывать в `result["error"]` и немедленно завершать шаг ошибкой (последующий `session.step.ended` не может перевести попытку в успешный `tool_calls`); (4) `reasoning` и `text` той же сессии передавать в `on_reasoning`/`on_text` с учётом байтового бюджета.

### F-003 -> RW-002
- origin: visionary · R1 · visionary-F-002
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-002)
- resolved_in: D1 (r144)
- votes: D1 skeptic=AMEND(blocking), realist=AMEND(blocking), visionary=AUTHOR
- requirement: В `_serve_one_attempt` (`bridges/opencode-zen-bridge/server.py:4001-4019`, `:6227`, `:6680`) сделать подтверждение `session.step.ended` границей публикации нативных вызовов инструментов (`on_tool` / `emit_tool_call`): буферизовать первый и дополнительные нативные tool_call закрываемого шага внутри `_finish_serve_tool_step` / `_drain_serve_step_usage` и вызывать `on_tool` только после успешного подтверждения `session.step.ended` без ошибки шага. При неподтверждённом шаге (`ServeProtocolError` / EOF / окно истекло / `error` / `form` / `permission`) ни один неподтверждённый вызов не должен попадать в SSE-поток или оставаться в общем списке `tool_calls` при последующей успешной попытке B.

### F-004 -> RW-003
- origin: visionary · R1 · visionary-F-003
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-003)
- resolved_in: D1 (r144)
- votes: D1 skeptic=AGREE(blocking), realist=AGREE(blocking), visionary=AMEND(non-blocking)
- requirement: Убрать вызов `_strip_interrupted(...)` с пути `reasoning` (`bridges/opencode-zen-bridge/server.py:5708`, `:5988`, `:7005`), оставив фильтрацию маркеров прерывания только на текстовом `content`, чтобы модельное размышление `reasoning_content` передавалось клиенту побайтово без модификации (`REQ-005` / `AC-006`) как на целых, так и на разрезанных по дельтам маркерах прерывания; обновить `tests/test_step_interruption.py:414-430` под `AC-006` и добавить регрессионный тест в `tests/test_realtime_reasoning.py`.

### F-007 -> RW-004
- origin: visionary · R1 · visionary-F-006
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-004)
- resolved_in: D1 (r144)
- votes: D1 skeptic=AGREE(blocking), realist=AGREE(blocking), visionary=AMEND(non-blocking)
- requirement: Ограничить накопление состояния нативных инструментов в `_ServeToolState` (`bridges/opencode-zen-bridge/server.py:3154-3175`, `:3381`, `:3483`, `:3990`): ввести потолок количества уникальных `call_id` на попытку (например `_MAX_SERVE_NATIVE_TOOLS = 128`) и включить суммарный UTF-8 объём удерживаемых `text` и сериализованных `input` всех записей `_ServeToolState.tools` (с учётом замены существующего значения по тому же `call_id` и обоих путей потребления событий — основного цикла и drain) в проверку байтового бюджета `_serve_accumulated_bytes` (`_MAX_SERVE_ACCUMULATED_BYTES`), завершая попытку `ServeProtocolError` с `cleanup()` при превышении (`HL-ENV-01`).

### F-008 -> RW-005
- origin: visionary · R1 · visionary-F-007
- rev: 2
- priority: blocking
- status: ACCEPTED
- outcome: REWORK_REQUIRED (RW-005)
- resolved_in: D1 (r144)
- votes: D1 skeptic=AGREE(blocking), realist=AGREE(blocking), visionary=AMEND(non-blocking)
- requirement: Ограничить downstream-запись клиенту в `_LockedWfile.write` / `flush` (`bridges/opencode-zen-bridge/server.py:5835`, `:5998`, `:6595`) оставшимся дедлайном запроса и конечным таймаутом сокета на запись (например `min(_DOWNSTREAM_WRITE_TIMEOUT_S, max(0.05, deadline - now))`), а также обеспечить не зависящее от освобождения `_LockedWfile._lock` прерывание заблокированной записи (через `shutdown`/`close` клиентского сокета из цикла надзора или по таймауту сокета), чтобы медленный клиент, переставший читать из сокета после заголовков, приводил к ограниченному по времени завершению, остановке группы процессов `serve` и возврату bulkhead-слота (`feature.md` §2).

### F-005 -> FU-001
- origin: visionary · R1 · visionary-F-004
- rev: 1
- priority: non-blocking
- status: ACCEPTED
- outcome: FOLLOW_UP (FU-001)
- resolved_in: D1 (r144)
- requirement: Актуализировать ссылки на имена тестовых методов и деталей реализации в `teamlead/verification-traceability.md`.

### F-006 -> FU-002
- origin: visionary · R1 · visionary-F-005
- rev: 2
- priority: non-blocking
- status: ACCEPTED
- outcome: FOLLOW_UP (FU-002 — реализуется вместе с RW-001..RW-005)
- resolved_in: D1 (r144)
- requirement: Ввести общий бюджет вспомогательного/управляющего I/O на запрос (`_AUX_IO_BUDGET_S = 54.0` с при `SLA_p99_s = 180` по `R-BULK-I1`) и ограничивать его остатком все startup/control/subscribe ожидания и паузы повторов по всем попыткам запроса (`_open_serve_events`, `_serve_http`, `_StartupGate`, `_SpawnRateLimiter`, backoff), сохраняя отдельный резерв времени на `cleanup()`, и подтвердить детерминированным тестом с управляемыми часами сумму вспомогательных ожиданий `<= 54.0` с и прекращение нового I/O после исчерпания бюджета.

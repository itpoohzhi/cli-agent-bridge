# Итоговый консенсус-леджер Совета Тимлидов по коду (цикл 11, после R1 r158 + D1 r193 + D2 r238, run analyst-teamlead-zen-realtime-reasoning-20261025)

## Раздел А. Состав коллегии и квитанции PANEL PROOF
- **Раунд R1 (`panel/council/r158`):** `skeptic` (`muse-wonder-full-1.0` via `muse`) = `ACCEPT` (0 находок), `realist` (`grok-4.7-high` via `cursor-agent`) = `ACCEPT` (0 находок), `visionary` (`gpt-6.1-sol-high` via `codex`) = `NEEDS WORK` (5 находок `F-001..F-005`). Квитанция: `receipts/council-r158-proof.json` (`sha256=8f8fb4c3c3de697937358c274b296f86e90eb60cb3eb0b89417d5b4596ca8845`).
- **Раунд D1 (`panel/council/r193`):** `skeptic` (`gpt-6.1-sol-high` via `codex`), `realist` (`muse-wonder-full-1.0` via `muse`), `visionary` (`grok-4.7-high` via `cursor-agent`). Квитанция: `receipts/council-r193-proof.json` (`sha256=6e1f4beb2aabb63858a39ac5b05702b3ff4784e5bcd3a7b72e63ad2ae229136f`).
- **Раунд D2 (`panel/council/r238`):** `skeptic` (`gpt-6.1-sol-high` via `codex`) = `NEEDS WORK`, `realist` (`grok-4.7-high` via `cursor-agent`) = `NEEDS WORK`, `visionary` (`muse-wonder-full-1.0` via `muse`) = `NEEDS WORK`. Квитанция: `receipts/council-r238-proof.json` (`sha256=dff11befa6a85afc393a066faa0fbea4e44fefd32a20055396b4ecaa7e9934cc`).
- **Проверка `Verify-Fixed` по 6 блокерам предыдущего цикла (`RW-001..RW-006`):** все 3 судьи подтвердили `Verify-Fixed: PASS` по всем 6 пунктам `RW-001..RW-006`.

## Раздел Б. Сводка консенсуса по находкам `F-001..F-005`
- `F-001` (`visionary-F-001`): `status: AGREED`, `priority: blocking`, `outcome: blocking` (`3/3` семейств ЗА `rev=1` `blocking` в `D2` `r238` по `council.md:456-459`) — **`RW-001`**.
- `F-002` (`visionary-F-002`): `status: AGREED`, `priority: blocking`, `outcome: blocking` (`3/3` семейств ЗА `rev=1` `blocking` в `D2` `r238` по `council.md:456-459`) — **`RW-002`**.
- `F-003` (`visionary-F-003`): `status: AGREED`, `priority: blocking`, `outcome: blocking` (`3/3` семейств ЗА `rev=1` `blocking` в `D2` `r238` по `council.md:456-459`) — **`RW-003`**.
- `F-004` (`visionary-F-004`): `status: AGREED`, `priority: blocking`, `outcome: blocking` (`3/3` семейств ЗА `rev=1` `blocking` в `D2` `r238` по `council.md:456-459`) — **`RW-004`**.
- `F-005` (`visionary-F-005`): `status: AGREED`, `priority: non-blocking`, `outcome: non-blocking` (`3/3` семейств ЗА `rev=1` `non-blocking` в `D1` `r193`) — **`FU-001`**.

## Раздел В. Детальные записи леджера (`F-001..F-005`)

### F-001
- origin: visionary · R1 · visionary-F-001
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d2
- votes: R1 visionary=AUTHOR(rev=1,blocking) | D1 skeptic=AGREE(rev=1,blocking) realist=DISPUTE(out_of_scope) visionary=AMEND(rev=2,non-blocking) | D2 skeptic=AGREE(rev=1,blocking) realist=AGREE(rev=1,blocking) visionary=AGREE(rev=1,blocking)
- dissent: —
- owner_decision: —
- requirement: В `_serve_one_attempt` (`bridges/opencode-zen-bridge/server.py:4231`, `:4239`, `:4288`, `:4296`, `:4440`, `:4447`) переводить сетевые и протокольные отказы (`OSError`, `http.client.HTTPException`, `ServeUnavailable`) управляющих вызовов безопасности (`form.created` cancel/interrupt на `:4231,:4239`, `permission.asked` reject/interrupt на `:4288,:4296`) в терминальный `ServeSecurityError` (сохраняя отдельную нейтральную классификацию `ServeClientDisconnect` / `ServeStartupDeadlineExceeded` и обязательный `cleanup` в `finally`), чтобы отказ доставки reject/cancel/interrupt не попадал в общий обработчик `:4440` как повторяемый `prompt_error` (`transient_error=True`). Добавить оракулы инъекции сетевого отказа на управляющих вызовах в SSE и JSON (`auto`): ровно 1 попытка `serve`, `0` переходов в `run`, терминальный отказ безопасности, группа процессов остановлена.

### F-002
- origin: visionary · R1 · visionary-F-002
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d2
- votes: R1 visionary=AUTHOR(rev=1,blocking) | D1 skeptic=AGREE(rev=1,blocking) realist=DISPUTE(out_of_scope) visionary=AMEND(rev=2,non-blocking) | D2 skeptic=AGREE(rev=1,blocking) realist=AGREE(rev=1,blocking) visionary=AGREE(rev=1,blocking)
- dissent: —
- owner_decision: —
- requirement: В `_serve_json_serve` (`bridges/opencode-zen-bridge/server.py:8099-8100`, `:8110-8111`, `:8184`) перед выполнением `continue` на разрешённом повторе (после `delivered_any` / частичного вывода) сохранять полученные `reasonings` в `reasonings_all` и нормализованный частичный текст `texts` (через `ToolCallParser` при `emulate_tools`, `_strip_broken_tool_blocks`, `_strip_interrupted` и `_dedup_retry_text` относительно `_prior_content`) в `contents` с обновлением `_prior_content`, не публикуя неподтверждённые нативные `tool_calls`. В `Run.execute` (`server.py:5858-5882`) при внутренних повторах (watchdog / retryable failure) аккумулировать полученные `reasoning`, нормализованный с дедупликацией префикса `text`/`chunks` и `usage` (`input`, `output`, `cached`, `reasoning`) между попытками вместо перезаписи результата только последней попыткой. Добавить оракулы для `serve` JSON и `run` JSON (частичный вывод -> watchdog/prompt-status retry -> успешный повтор): сохранность полного `reasoning_content`, склеенного `content` с дедупликацией префикса, суммарного `usage` и отсутствие публикации незавершённых `tool_calls`.

### F-003
- origin: visionary · R1 · visionary-F-003
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d2
- votes: R1 visionary=AUTHOR(rev=1,blocking) | D1 skeptic=AGREE(rev=1,blocking) realist=DISPUTE(out_of_scope) visionary=AMEND(rev=2,non-blocking) | D2 skeptic=AGREE(rev=1,blocking) realist=AGREE(rev=1,blocking) visionary=AGREE(rev=1,blocking)
- dissent: —
- owner_decision: —
- requirement: В `_drain_serve_step_usage` и `_finish_serve_tool_step` (`bridges/opencode-zen-bridge/server.py:1581`, `:3473-3477`, `:3594`, `:3759`, `:4362`) ограничить ожидание каждого следующего события в дренаже минимумом из окна неактивности (`min(float(STALL_TIMEOUT_S), _STEP_DRAIN_WINDOW_S)` или продлеваемого при каждом валидном событии текущего шага окна `min(attempt_deadline, time.monotonic() + max(_STEP_DRAIN_WINDOW_S, float(STALL_TIMEOUT_S)))` в пределах общего `attempt_deadline`), чтобы активный многовызовный инструментальный шаг длительностью более `1.0` с (при поступлении событий чаще окна неактивности и соблюдении лимитов числа вызовов/байтов) штатно дожидался `session.step.ended` и публиковал все `pending_calls` и `usage` ровно один раз, а при реальной тишине дольше окна дренажа, `EOF` или исчерпании общего `deadline` завершался `ServeProtocolError("incomplete tool step without step.ended")` без публикации `pending_calls`. Добавить соответствующие детерминированные оракулы в `tests/test_realtime_reasoning.py`.

### F-004
- origin: visionary · R1 · visionary-F-004
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d2
- votes: R1 visionary=AUTHOR(rev=1,blocking) | D1 skeptic=AGREE(rev=1,blocking) realist=DISPUTE(out_of_scope) visionary=AMEND(rev=2,non-blocking) | D2 skeptic=AGREE(rev=1,blocking) realist=AGREE(rev=1,blocking) visionary=AGREE(rev=1,blocking)
- dissent: —
- owner_decision: —
- requirement: В `_serve_json_serve` (`bridges/opencode-zen-bridge/server.py:8219-8223`, `:8259-8261`) при исчерпании повторов `unmapped` (`unmapped_retries >= NATIVE_RETRY_LIMIT or not attempts.allow_retry("unmapped")`) добавлять в `contents` стандартное уведомление `f"[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент ({', '.join(unmapped)}); повторы исчерпаны]"` перед `break` (в точном соответствии с legacy `run` JSON на `server.py:8519-8523` и `serve` SSE на `server.py:6806`), чтобы запрос возвращал `200 OK` с этим уведомлением и `finish_reason="stop"`, а не `502 "serve produced no text"`. Добавить сравнительную матрицу `serve`/`run` × `SSE`/`JSON` при исчерпании `unmapped` по локальному лимиту, общему потолку запусков и retry budget.

### F-005
- origin: visionary · R1 · visionary-F-005
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR(rev=1,non-blocking) | D1 skeptic=AGREE(rev=1,non-blocking) realist=AGREE(rev=1,non-blocking)
- dissent: —
- owner_decision: —
- requirement: В `teamlead/verification-traceability.md` заменить 6 старых имён тестов Цикла 11 на фактические имена в `tests/test_realtime_reasoning.py` (`test_c11_rw001_drain_text_delivered_once_with_native_tool`, `test_c11_rw002_execution_wait_excluded_from_prompt_budget`, `test_c11_rw002_exhausted_before_prompt_starts_no_http`, `test_c11_rw002_security_control_time_debited_main_and_drain`, `test_c11_rw002_first_sse_budget_across_real_attempts`, `test_c11_rw002_prompt_headers_use_remaining_aux`, `test_c11_rw003_initial_writes_fail_closed`, `test_c11_rw003_status_socket_timeout_before_model_token`, `test_c11_rw004_callback_error_logged_and_socket_aborted`, `test_c11_rw005_completed_text_preserves_reasoning_without_retry`, `test_c11_rw006_name_and_id_caps_main_and_drain` + новые оракулы Цикла 12) и уточнить имя события `session.tool.input.delta`.

## Раздел Г. Итоговый вердикт Совета Тимлидов по Циклу 11 и маршрут доработки
- **Итоговый вердикт Цикла 11:** `NEEDS_WORK` (`blocking_open = 4`: `F-001..F-004` -> `RW-001..RW-004`; `non_blocking = 1`: `F-005` -> `FU-001`; `OPEN = 0`, `OWNER_PENDING = 0`).
- **Следующий шаг:** запуск `Coder` (`coder-15`, Цикл 12, `entry="fix-from-panel"`) по `handoff/panel-rework-brief.json`, затем `Clean-Room L2`, слепой `reverse-spec.md`, сборка `teamlead/package.md` Цикла 12 и раунд `R1` Совета Тимлидов Цикла 12.

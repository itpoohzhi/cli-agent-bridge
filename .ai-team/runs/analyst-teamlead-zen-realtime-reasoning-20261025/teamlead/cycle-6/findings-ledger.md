# Консенсус-леджер Совета Тимлидов по коду (`consensus-ledger.md` / `findings-ledger.md`) — Cycle 6, run `analyst-teamlead-zen-realtime-reasoning-20261025`

- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb`)
- **Раунд R1 (`panel/council/r72`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r72/panel-proof.json sha256=a34983d792cdc88e231befc891a02382f96ca3f6b58d7c6d10da236630f24aa2 verify_panel_proof exit=0`
- **Раунд D1 (`panel/council/r77`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r77/panel-proof.json sha256=9c2bb7923056fcdbc28719c35f7cd1771053af8fc7e562c4f0acb0690052a5f6 verify_panel_proof exit=0`
- **Всего находок R1:** `6` (`F-001` .. `F-006`), новых находок в D1 (`r2_late`): `0`.
- **Итог дебатов D1:** `AGREED blocking` = `4` (`RW-001..RW-004`), `AGREED non-blocking` = `1` (`FU-001`), `WITHDRAWN` = `1` (`1` межсудейский дубль `F-004 -> duplicate_of:F-001`). Открытых `OPEN` или `CONFLICT` нет (`0`).

## Сводная таблица статусов (`F-001` .. `F-006`)

| ID | skeptic | realist | visionary | priority | status |
|---|---|---|---|---|---|
| F-001 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-002 | AGREE | AGREE | AUTHOR | blocking | AGREED |
| F-003 | AGREE | AGREE | AUTHOR | blocking | AGREED |
| F-004 | DISPUTE | AMEND | WITHDRAW | withdrawn | WITHDRAWN |
| F-005 | AGREE | AGREE | AUTHOR | blocking | AGREED |
| F-006 | AGREE | AMEND | AUTHOR | non-blocking | AGREED |

---

## Карточки находок (`F-001` .. `F-006`)

### F-001
- origin: realist · R1 · realist-F-001
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> F-001
> priority: blocking
> criterion: КОРРЕКТНОСТЬ, РИСКИ
> locations: bridges/opencode-zen-bridge/server.py:5488, bridges/opencode-zen-bridge/server.py:5507, bridges/opencode-zen-bridge/server.py:5228, bridges/opencode-zen-bridge/server.py:7516, bridges/opencode-zen-bridge/server.py:7518
> rule: REQ-016 MUST, AC-021, AC-010, RW-003 («классифицировать причину выхода `first_event_timeout`, `first_token_timeout`, `stall_timeout`»)
> evidence: В `Run._execute_once` блок `if watchdog_reason: rc = 1; fatal_error = True` (`server.py:5486-5488`) помечает любой watchdog как фатальную ошибку провайдера. Возврат включает `"fatal_error": fatal_error` и `"state": state` (`server.py:5505-5508`). `Run.execute` при исчерпанном бюджете делает `return out` (`server.py:5237`). `Handler._serve_json` выполняет `if out.get("fatal_error") and not tool_calls:` → `xs["exit_reason"] = "provider_fatal"` и `_error_payload("opencode provider error after partial output …")` (`server.py:7516-7527`). Clean-room: `exec cli failed rc=-15 state=first_event_timeout` затем `O-EXIT/v1 mode=json … status=502 exit_reason=provider_fatal … duration_s=0.77` (`execution-evidence.md:3468-3470`); `state=first_token_timeout` → `exit_reason=provider_fatal` duration_s=0.79 (`:3480-3482`); `state=stall_timeout` → `exit_reason=provider_fatal` duration_s=0.54 (`:3492-3494`). Ветка детерминированного HTTP `fatal_error = True` на `server.py:5442` — другой root cause и в этот блок не входит.
> expected: На исчерпанном JSON `run` `exit_reason` равен имени фазы (`first_event_timeout` / `first_token_timeout` / `stall_timeout`), тело 502 называет эту фазу. `fatal_error=True` остаётся только у детерминированного HTTP провайдера.
> verification: `OPENCODE_ZEN_BRIDGE_TRANSPORT=run`, `stream=false`, `MAX_TOTAL_SPAWNS=1`, молчащий CLI / служебное событие без токена / пауза после токена: строка `O-EXIT/v1` содержит `exit_reason=<фаза>`, в теле нет «provider error after partial output». Успешный повтор при `MAX_TOTAL_SPAWNS=2` по-прежнему `exit_reason=ok`.
> test_gap: `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs` должен утверждать `exit_reason=<фаза>` в `O-EXIT/v1`, а не только подстроку фазы где-либо в логе.

### F-002
- origin: visionary · R1 · visionary-F-001
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-001 [pre-existing]
>    priority: blocking
>    locations: `bridges/opencode-zen-bridge/server.py:3345`, `bridges/opencode-zen-bridge/server.py:3683`.
>    rule: `FALLBACK_DECISION_TABLE`, запрет fallback после valid execution SSE; REQ-009.
>    evidence: `_is_delivered()` учитывает только `headers_at`, тексты, reasoning и native calls. Получение `session.execution.started` устанавливает `first_event_at`, но не барьер. Если prompt-заголовки ещё не пришли, а SSE затем закрывается, результат может остаться `delivered=False`, разрешая переход в `run` после уже начавшегося исполнения.
>    исправление: включить валидное событие выполнения своей сессии в барьер; сохранять его между попытками в SSE и JSON.
>    проверка: FakeServe задерживает prompt-заголовки, отправляет execution.started своей сессии и закрывает SSE; `Run.execute` и `_spawn_with_stdin` не вызываются, допустимы только serve-retry либо ошибка.

### F-003
- origin: visionary · R1 · visionary-F-002
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-002 [pre-existing]
>    priority: blocking
>    locations: `bridges/opencode-zen-bridge/server.py:6772`, `bridges/opencode-zen-bridge/server.py:6776`, `bridges/opencode-zen-bridge/server.py:6779`.
>    rule: REQ-009; `R-BULK-I3`, сохранение Circuit Breaker.
>    evidence: `transient_failure` вычисляется без `watchdog_state["reason"]`. Убитый watchdog процесс имеет отрицательный rc и не считается retryable CLI failure. При отсутствии вывода breaker не получает failure; после частичного вывода `attempt_done(False, True)` может зарегистрировать успех. Затем отдельная ветка всё равно повторяет запрос по watchdog.
>    исправление: включить watchdog в транзиентный исход до единственного вызова `attempt_done`; исключить success для такой попытки.
>    проверка: для трёх watchdog-причин, с выводом и без него, проверить инкремент failure, отсутствие success и открытие breaker после заданного числа отказов.

### F-004
- origin: visionary · R1 · visionary-F-003
- rev: 1
- priority: blocking
- status: WITHDRAWN
- outcome: withdrawn
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AMEND, visionary=WITHDRAW
- dissent: skeptic d1 «DISPUTE F-004 класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:5488 и bridges/opencode-zen-bridge/server.py:7516 — тот же `fatal_error=True` → `exit_reason="prov» → teamlead/cycle-6/debate/d1/skeptic.md ; realist d1 «AMEND F-004 priority=blocking; locations=bridges/opencode-zen-bridge/server.py:5298, bridges/opencode-zen-bridge/server.py:5373, bridges/opencode-zen-bridge/server.py:5386, bridges/opencode-ze» → teamlead/cycle-6/debate/d1/realist.md ; visionary d1 «WITHDRAW F-004 ARG: realist/R1 «В `Run._execute_once` блок `if watchdog_reason: rc = 1; fatal_error = True` (`server.py:5486-5488`) помечает любой watchdog как фатальную ошибку провайдера»; прове» → teamlead/cycle-6/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: priority=blocking; locations=bridges/opencode-zen-bridge/server.py:5298, bridges/opencode-zen-bridge/server.py:5373, bridges/opencode-zen-bridge/server.py:5386, bridges/opencode-zen-bridge/server.py:5505, bridges/opencod (teamlead/cycle-6/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-003
>    priority: blocking
>    locations: `bridges/opencode-zen-bridge/server.py:5486`, `bridges/opencode-zen-bridge/server.py:5505`, `bridges/opencode-zen-bridge/server.py:7516`.
>    rule: REQ-016, AC-021; `O-EXIT/v1`, точная машиночитаемая причина отказа.
>    evidence: watchdog устанавливает `fatal_error=True`, после чего JSON-handler записывает `exit_reason="provider_fatal"`. Сырой clean-room лог подтверждает это для `first_event_timeout`, `first_token_timeout`, `stall_timeout`. Измеренные `first_event_at`/`first_token_at` также не возвращаются в handler: итоговые поля остаются `None`.
>    исправление: передать времена и терминальное состояние из `Run` в handler; обработать watchdog до общего provider-fatal пути.
>    проверка: пройти реальный HTTP JSON-handler до логового sink; получить ровно одну строку `O-EXIT/v1` с соответствующей watchdog-причиной и корректными временами наступивших событий.

### F-005
- origin: visionary · R1 · visionary-F-004
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-004
>    priority: blocking
>    locations: `bridges/opencode-zen-bridge/server.py:3171`, `bridges/opencode-zen-bridge/server.py:3375`, `bridges/opencode-zen-bridge/server.py:3391`, `bridges/opencode-zen-bridge/server.py:3394`.
>    rule: RW-005; `feature.md` §2, `R-BULK-I1`, ограничение каждого I/O-шага собственным бюджетом и остатком deadline.
>    evidence: watcher подписки получает общий `deadline`; `_ctrl_http` передаёт `attempt_deadline`. `ready_deadline=now+3` проверяется только после возврата/ошибки `_ctrl_http`. Если заголовки поступают по байту быстрее socket timeout, readiness/create могут ждать до общего deadline; аналогично подписка обходит собственный first-event-порог. Основной watchdog начинается после этих операций.
>    исправление: передавать в watcher и HTTP-вызов `min(request_deadline, phase_started + phase_budget)`; readiness-повторы должны использовать общий для них фазовый deadline.
>    проверка: при общем deadline 30–60 с и фазовом бюджете 0,3 с peer капает корректные заголовки каждые 0,02 с; readiness/create/subscribe завершаются по фазовому бюджету с cleanup и корректной классификацией. Существующие тесты с общим deadline 0,9 с этот случай не различают.

### F-006
- origin: visionary · R1 · visionary-F-005
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AMEND, visionary=AUTHOR
- dissent: realist d1 «AMEND F-006 priority=blocking; locations=bridges/opencode-zen-bridge/server.py:3745, bridges/opencode-zen-bridge/server.py:3753; fix=после готового native-вызова ограниченно собрать usage заве» → teamlead/cycle-6/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=blocking; locations=bridges/opencode-zen-bridge/server.py:3745, bridges/opencode-zen-bridge/server.py:3753; fix=после готового native-вызова ограниченно собрать usage завершаемого шага, исключив запуск следующег (teamlead/cycle-6/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-005 [pre-existing]
>    priority: non-blocking
>    locations: `bridges/opencode-zen-bridge/server.py:3745`, `bridges/opencode-zen-bridge/server.py:3753`.
>    rule: REQ-014 / AC-019, сохранение фактического usage.
>    evidence: готовый native call при `emulate_tools=True` завершает попытку до последующего `session.step.ended`; фактические токены этого шага могут не попасть в результат, и ответ использует оценку.
>    исправление: ограниченно дождаться usage завершаемого шага либо явно сохранить признак оценочного usage; не допускать следующего модельного шага.
>    проверка: native called → step.ended с известными токенами; итоговый usage равен фикстуре и учитывается один раз. Приоритет non-blocking, поскольку REQ-014 имеет SHOULD.

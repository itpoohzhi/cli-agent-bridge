# Согласованный консенсус-леджер Совета Тимлидов по коду — Cycle 1 (`R1` `panel/council/r1` → `D1` `panel/council/r5`, run `analyst-teamlead-zen-realtime-reasoning-20261025`)

- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4`)
- **Квитанция R1 (`r1`):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r1/panel-proof.json` (`sha256=be62a5cafb651ca25144150677efc39bf0ac1774552f61b65a7ddbc28f80ff8f`, `verify_panel_proof exit=0`)
- **Квитанция D1 (`r5`):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r5/panel-proof.json` (`sha256=7f5ec170ab30560df17b1c753efdb29003f745aa00776a5d56b913bebaf36de6`, `verify_panel_proof exit=0`)
- **Состав D1 (`r5`, ротация по `PoL-V13`):** Seat 1 `skeptic` = `grok-4.7-high` (`xAI`, `cursor-agent`, `POSITIONS: 53/53`), Seat 2 `realist` = `gpt-6.1-sol-high` (`OpenAI`, `codex`, `POSITIONS: 39/39`), Seat 3 `visionary` = `claude-sonnet-5-5-high` (`Anthropic`, `claude-p`, `POSITIONS: 50/50`).
- **Итог совещания после D1:** `OPEN = 0`, `CONFLICT = 0`, `OWNER_PENDING = 0`, `r2_late = 0`. Из `71` находок `R1`: `32` согласованы как первичные `blocking` (`RW-001..RW-032`), `9` согласованы как первичные `non-blocking` (`FU-001..FU-009`), `28` закрыты как точные межсудейские дубли (`duplicate_of:F-MMM`, `outcome: excluded`), `2` отклонены большинством `2/3` как невалидные после сверки (`F-045`, `F-053`, `status: REJECTED_BY_MAJORITY`, `outcome: excluded`). Итоговый вердикт Совета: **NEEDS WORK (Класс A, 3/3 судей)**.

## Сводная таблица позиций судей (R1 → D1)

| ID | Seat 1 (`skeptic`, `grok-4.7-high`, `xAI`) | Seat 2 (`realist`, `gpt-6.1-sol-high`, `OpenAI`) | Seat 3 (`visionary`, `claude-sonnet-5-5-high`, `Anthropic`) | Итоговый приоритет (`outcome`) | Статус (`status`) |
|---|---|---|---|---|---|
| F-001 | AUTHOR | DISPUTE | AGREE | blocking | AGREED |
| F-002 | AUTHOR | AGREE | AMEND | blocking | AGREED |
| F-003 | AUTHOR | AMEND | AMEND | blocking | AGREED |
| F-004 | AUTHOR | DISPUTE | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-005 | AUTHOR | DISPUTE | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-006 | AUTHOR | DISPUTE | AGREE | blocking | AGREED |
| F-007 | AUTHOR | DISPUTE | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-008 | AUTHOR | DISPUTE | AGREE | blocking | AGREED |
| F-009 | AUTHOR | DISPUTE | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-010 | AUTHOR | AMEND | AMEND | blocking | AGREED |
| F-011 | AUTHOR | DISPUTE | AGREE | non-blocking | AGREED |
| F-012 | AUTHOR | AMEND | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-013 | AUTHOR | DISPUTE | AMEND | excluded | REJECTED_BY_MAJORITY |
| F-014 | AUTHOR | DISPUTE | AMEND | non-blocking | AGREED |
| F-015 | AUTHOR | AMEND | AGREE | non-blocking | AGREED |
| F-016 | AUTHOR | DISPUTE | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-017 | AUTHOR | DISPUTE | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-018 | AUTHOR | DISPUTE | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-019 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-020 | DISPUTE | AUTHOR | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-021 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-022 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-023 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-024 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-025 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-026 | DISPUTE | AUTHOR | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-027 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-028 | AGREE | AUTHOR | INCONCLUSIVE | blocking | AGREED |
| F-029 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-030 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-031 | DISPUTE | AUTHOR | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-032 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-033 | AMEND | AMEND | AGREE | blocking | AGREED |
| F-034 | AMEND | AUTHOR | AMEND | non-blocking | AGREED |
| F-035 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-036 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-037 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-038 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-039 | DISPUTE | AUTHOR | AMEND | excluded | REJECTED_BY_MAJORITY |
| F-040 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-041 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-042 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-043 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-044 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-045 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-046 | AMEND | AUTHOR | AMEND | blocking | AGREED |
| F-047 | DISPUTE | AUTHOR | AMEND | non-blocking | AGREED |
| F-048 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-049 | DISPUTE | AUTHOR | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-050 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-051 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-052 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-053 | AMEND | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-054 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-055 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-056 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-057 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-058 | AGREE | INCONCLUSIVE | AUTHOR | blocking | AGREED |
| F-059 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-060 | AGREE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-061 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-062 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-063 | AGREE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-064 | AGREE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-065 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-066 | AGREE | AMEND | AUTHOR | non-blocking | AGREED |
| F-067 | AGREE | AMEND | AUTHOR | non-blocking | AGREED |
| F-068 | AMEND | AMEND | AUTHOR | non-blocking | AGREED |
| F-069 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-070 | AGREE | DISPUTE | AUTHOR | non-blocking | AGREED |
| F-071 | AGREE | AMEND | AUTHOR | blocking | AGREED |

---

## Карточки находок (`F-001` .. `F-071`)

### F-001
- origin: skeptic · R1 · skeptic-01
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: realist d1 «DISPUTE F-001 — класс: duplicate_of:F-026 — контр-evidence: `server.py:4848`, `5768` — тот же обход `_StartupGate` и `spawn_limiter` уже полностью описан в F-026; блокирующий дефект подтверждает» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-001
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/логика, РЕАЛИЗУЕМОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:4848, bridges/opencode-zen-bridge/server.py:5768, bridges/opencode-zen-bridge/server.py:4490, bridges/opencode-zen-bridge/server.py:5297
> rule: REQ-013 / AC-018; S-HERD-I1 (холодный старт сериализуется `_StartupGate`)
> evidence: `attempts.note_spawn()` затем `_serve_one_attempt` без `gate.acquire()` и без `spawn_limiter.acquire`; run-путь: `gate = _StartupGate()` и `self.res.spawn_limiter.acquire` / `res.spawn_limiter.acquire`.
> fix: Перед `_spawn_serve` в `_run_serve_stream_attempts` и `_serve_json_serve` захватывать `_StartupGate` и `spawn_limiter` с тем же `max_wait_s`, освобождать в `finally` попытки.
> verify: Тест двух перекрывающихся serve-попыток показывает сериализацию gate и отказ limiter при превышении `SPAWN_RATE_PER_S`.

### F-002
- origin: skeptic · R1 · skeptic-02
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=AGREE | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-002 — priority=non-blocking; locations=server.py:2552; fix=читать рукопожатие с остатком 3 с, при истечении `ServeUnavailable` и `cleanup` — причина: helper пишет `json.dumps(...)+"\n"» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:2552; fix=читать рукопожатие с остатком 3 с, при истечении `ServeUnavailable` и `cleanup` — причина: helper пишет `json.dumps(...)+"\n"` одним `write` и `flush` (server.py:~14 (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> ### F-002
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/граничные условия
> locations: bridges/opencode-zen-bridge/server.py:2552
> rule: feature.md — таймаут на каждом шаге I/O, включая чтение после первого байта
> evidence: `select.select([out_fd], [], [], 3.0)` покрывает только появление fd; далее `while not line_bytes.endswith(b"\n"): chunk_b = os.read(out_fd, 1)` без дедлайна.
> fix: Читать рукопожатие с остатком тех же 3 с; по истечении `ServeUnavailable` и `lease.cleanup()`.
> verify: Helper, который пишет один байт и замолкает, убивается в бюджете рукопожатия, слот и группа освобождены.

### F-003
- origin: skeptic · R1 · skeptic-03
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=AMEND | D1 visionary=AMEND
- dissent: realist d1 «AMEND F-003 — priority=blocking; locations=server.py:2609,server.py:2613; fix=После SIGTERM проверять завершение принадлежащей попытке группы в ограниченном бюджете, при необходимости эскалиро» → teamlead/cycle-1/debate/d1/realist.md ; visionary d1 «AMEND F-003 — priority=non-blocking; locations=server.py:2593,2609,2613; fix=сверять `parent_start_ts` и `helper_lstart` с живым `ps lstart`, ждать смерти группы до удаления lease — причина: S» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: — priority=blocking; locations=server.py:2609,server.py:2613; fix=После SIGTERM проверять завершение принадлежащей попытке группы в ограниченном бюджете, при необходимости эскалировать до SIGKILL; сохранять lease до подт (teamlead/cycle-1/debate/d1/realist.md) ; visionary d1: — priority=non-blocking; locations=server.py:2593,2609,2613; fix=сверять `parent_start_ts` и `helper_lstart` с живым `ps lstart`, ждать смерти группы до удаления lease — причина: SIGTERM шлётся только если `ps -o command (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> ### F-003
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/граничные условия
> locations: bridges/opencode-zen-bridge/server.py:72, bridges/opencode-zen-bridge/server.py:2593, bridges/opencode-zen-bridge/server.py:2609, bridges/opencode-zen-bridge/server.py:2613
> rule: REQ-008 / AC-011
> evidence: Lease пишет `"parent_start_ts": parent_lstart`. Reaper: `parent_alive = parent_pid > 0 and _pid_alive(parent_pid)` и при живом pid делает `continue`; иначе один `os.killpg(pgid, signal.SIGTERM)` и сразу `path.unlink()`.
> fix: Сверять lstart родителя и helper с lease до вывода «жив»; SIGKILL после 5 с; не удалять lease, пока группа жива. Тест с `helper_pid=0` эту ветку не исполняет — заменить живым фейком.
> verify: Lease мёртвого родителя, чей pid переиспользован (lstart не совпал), приводит к смерти helper+serve; lease остаётся, пока группа жива.

### F-004
- origin: skeptic · R1 · skeptic-04
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: duplicate_of:F-041 ; realist d1 «DISPUTE F-004 — класс: duplicate_of:F-041 — контр-evidence: `server.py:5770` — отсутствие callback отключения клиента в JSON-попытке уже входит в F-041.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-004
> priority: blocking
> criterion: ПОЛНОТА/пропущенные ветки
> locations: bridges/opencode-zen-bridge/server.py:5770, bridges/opencode-zen-bridge/server.py:4860
> rule: REQ-008 / AC-012 (обнаружение ухода клиента не позже 5 с, группа отсутствует не позже 7 с)
> evidence: Stream передаёт `is_client_gone=self._client_gone_check`. Вызов из `_serve_json_serve` аргумент не передаёт (`on_status=lambda _t: None` и сразу `thinking_enabled`).
> fix: Передавать `is_client_gone=self._client_gone_check` в JSON-попытку.
> verify: Закрытие сокета non-stream клиента останавливает группу не позже 7 с.

### F-005
- origin: skeptic · R1 · skeptic-05
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: duplicate_of:F-042 ; realist d1 «DISPUTE F-005 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_realtime_reasoning.py:99`, `102`, `376` — отсутствие serve-оракулов трёх watchdog уже включено в блокирующую неполноту F-0» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-005
> priority: blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:99, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:102
> rule: REQ-006 / REQ-007 / AC-008 / AC-009 / AC-010
> evidence: `if "__never_event__" in prompt` и `if "__silent__" in prompt` есть в `FAKE_SERVE`; вызовов этих маркеров в тестах нет. Legacy `FAKE_RT_MODE=silent` покрывает только run.
> fix: Три теста TRANSPORT=serve: нет событий → `first_event_timeout`; событие без токена → `first_token_timeout`; токен и пауза → `stall_timeout`; завершение за порог+2 с.
> verify: Тесты красные, если цикл `_serve_one_attempt` перестаёт проверять эти три порога.

### F-006
- origin: skeptic · R1 · skeptic-06
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: realist d1 «DISPUTE F-006 — класс: duplicate_of:F-031 — контр-evidence: `server.py:4950`, `4961`, `5981` — потеря исходного `tool_choice` уже описана в F-031.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-006
> priority: blocking
> criterion: ПОЛНОТА/пропущенные ветки
> locations: bridges/opencode-zen-bridge/server.py:4950, bridges/opencode-zen-bridge/server.py:4961, bridges/opencode-zen-bridge/server.py:5981
> rule: REQ-011 (STEP_RECOVERY на потоковом пути, включая forced tool_choice)
> evidence: `tool_choice=None` в `_incomplete_step_signal`; `_incomplete_tool_step_prompt(..., None, model)`; вызов `self._serve_json_serve(..., reported_model, None, res, attempts, xs)` при том, что параметр `tool_choice` у `_serve_json` есть и внутри `_serve_json_serve` используется.
> fix: Протащить `tool_choice` запроса в stream- и JSON-serve и в оба вызова recovery.
> verify: Serve-шаг с текстом без tool при `tool_choice`, требующем вызов, ретраится с force-клаузой в prompt.

### F-007
- origin: skeptic · R1 · skeptic-07
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: duplicate_of:F-042 ; realist d1 «DISPUTE F-007 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_step_interruption.py:159`, `167`, `188` — существующий набор использует run-фейк; необходимость эквивалентной serve-матриц» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-007
> priority: blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/tests/test_step_interruption.py:188
> rule: REQ-011 / AC-016
> evidence: `setUp` изолирует `_Resilience()` (это закрывает REQ-017). По файлу нет `OPENCODE_ZEN_BRIDGE_TRANSPORT`; фейк — shebang `opencode run`. Матрица incomplete/unmapped/tool_calls на serve не исполняется.
> fix: Прогнать существующие сценарии прерывания шага (или их fake-delta эквивалент) с `TRANSPORT=serve`.
> verify: Регрессия остановки по tool_calls или incomplete-retry на serve роняет этот тест.

### F-008
- origin: skeptic · R1 · skeptic-08
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: realist d1 «DISPUTE F-008 — класс: duplicate_of:F-020 — контр-evidence: `server.py:1679`, `1705`, `2857` — тот же собственный JSON-парсер и повреждение surrogate pairs уже описаны в F-020.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-008
> priority: blocking
> criterion: РИСКИ/данные, АЛЬТЕРНАТИВЫ
> locations: bridges/opencode-zen-bridge/server.py:1675, bridges/opencode-zen-bridge/server.py:1701, bridges/opencode-zen-bridge/server.py:2857
> rule: REQ-005 (байты размышления модели не модифицируются); python-standards KISS при уже импортированном `json`
> evidence: `parts.append(chr(int(hex_part, 16)))` без склейки суррогатной пары; `_loads_object` на `ValueError`/`IndexError` возвращает `{}`; читатель SSE кладёт payload через `_loads_object`.
> fix: Удалить `_JsonParser` и разбирать объекты через `json.loads`.
> verify: Дельта `reasoning_content` с `\uD83D\uDE00` доходит одним символом; битый JSON не превращается молча в пустое событие без `invalid_serve_event`.

### F-009
- origin: skeptic · R1 · skeptic-09
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: duplicate_of:F-029 ; realist d1 «DISPUTE F-009 — класс: duplicate_of:F-029 — контр-evidence: `server.py:2879`, `2880`, `2901` — неиспользуемая классификация prompt-response и неверный барьер доставки уже входят в F-029.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-009
> priority: blocking
> criterion: КОРРЕКТНОСТЬ/обработка ошибок
> locations: bridges/opencode-zen-bridge/server.py:2879, bridges/opencode-zen-bridge/server.py:4893, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:619
> rule: Строка `FALLBACK_DECISION_TABLE` «PROMPT_RESPONSE HTTP429/provider5xx»: `serve_retry`, ServeHealth 0, UpstreamBreaker +1; REQ-009 (breaker сохраняется)
> evidence: `prompt_status["status"] = st` и `headers_at` выставляются для любого статуса, кроме отдельной ветки 401/403. Дальше `first_event_timeout` делает `res.serve_health.record_failure()`. Тест: `self.assertTrue(silence or rows)`.
> fix: 429 и provider 5xx на prompt проводить в `attempt_done(True, False)` без `serve_health`; убрать тавтологию, утверждать инкременты строки 429.
> verify: Три ответа prompt 429 не делают `is_degraded()`, breaker фиксирует отказ.

### F-010
- origin: skeptic · R1 · skeptic-10
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(blocking) | D1 skeptic=AUTHOR | D1 realist=AMEND | D1 visionary=AMEND
- dissent: realist d1 «AMEND F-010 — priority=blocking; locations=server.py:2457,server.py:2464,server.py:2471; fix=Подтверждать завершение всей собственной группы, включая потомков после выхода helper; ограничить о» → teamlead/cycle-1/debate/d1/realist.md ; visionary d1 «AMEND F-010 — priority=non-blocking; locations=server.py:2464,2467,2471; fix=поправить `ResourceWarning` через F-035, а в `cleanup` после SIGKILL проверять `_pid_alive(pgid)` — причина: cleanu» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: — priority=blocking; locations=server.py:2457,server.py:2464,server.py:2471; fix=Подтверждать завершение всей собственной группы, включая потомков после выхода helper; ограничить ожидание общим cleanup-бюджетом и сохраня (teamlead/cycle-1/debate/d1/realist.md) ; visionary d1: — priority=non-blocking; locations=server.py:2464,2467,2471; fix=поправить `ResourceWarning` через F-035, а в `cleanup` после SIGKILL проверять `_pid_alive(pgid)` — причина: cleanup делает SIGTERM, `wait(0.5)`, `killpg(S (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> ### F-010
> priority: blocking
> criterion: РИСКИ/прод
> locations: bridges/opencode-zen-bridge/server.py:2464, bridges/opencode-zen-bridge/server.py:2467, bridges/opencode-zen-bridge/server.py:2471
> rule: REQ-008 / T-LIFE (процесс и читатель закрываются до возврата)
> evidence: `self.helper.wait(timeout=0.5)`, затем `os.killpg(..., SIGKILL)`, затем снова `wait(timeout=0.5)` и выход. `execution-evidence.md` / `l2-green-ver002-unittest.log`: `ResourceWarning: subprocess 98704 is still running` рядом со строками serve `O-EXIT`.
> fix: Ждать SIGTERM до 5 с, затем SIGKILL и ждать завершения; не возвращаться из `cleanup`, пока `_pid_alive(pgid)`.
> verify: Прогон unittest, включающий serve-тесты, не печатает `subprocess is still running`.

### F-011
- origin: skeptic · R1 · skeptic-11
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(non-blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: realist d1 «DISPUTE F-011 — класс: duplicate_of:F-049 — контр-evidence: `server.py:1791` — разрешающий дизъюнкт `len(head) == 4` уже описан в F-049.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-011
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ/логика
> locations: bridges/opencode-zen-bridge/server.py:1791
> rule: Предохранитель `_is_native_opencode_bin` в `auto` (shebang-фейк должен оставаться на run)
> evidence: `or len(head) == 4` после проверки Mach-O/ELF. Любой файл без `#!` длиной от 4 байт считается нативным.
> fix: Убрать дизъюнкт `len(head) == 4`; оставить Mach-O и ELF. Тест: 4 байта не-shebang → False.
> verify: Короткий бинарный мусор в `auto` не выбирает serve.

### F-012
- origin: skeptic · R1 · skeptic-12
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(non-blocking) | D1 skeptic=AUTHOR | D1 realist=AMEND | D1 visionary=AGREE
- dissent: duplicate_of:F-024 ; realist d1 «AMEND F-012 — priority=non-blocking; locations=server.py:1339; fix=Удалить неиспользуемую константу либо задействовать её в механизме раннего статуса, сохраняющем проверку быстрого ответа — пр» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: — priority=non-blocking; locations=server.py:1339; fix=Удалить неиспользуемую константу либо задействовать её в механизме раннего статуса, сохраняющем проверку быстрого ответа — причина: отсутствие чтения `STATUS_INITIAL (teamlead/cycle-1/debate/d1/realist.md)
- text (дословно, R1 skeptic):
> ### F-012
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/server.py:1339
> rule: REQ-004 (первая видимая строка). Живой статус закрывается `STATUS_WAITING`, константа начального текста не используется.
> evidence: `STATUS_INITIAL = "[мост] Подключение к модели…\n"` — присваивание без чтения в diff.
> fix: Эмитить `STATUS_INITIAL` как первую статусную строку либо удалить константу.
> verify: Поиск по `server.py` либо находит эмиссию, либо константы нет.

### F-013
- origin: skeptic · R1 · skeptic-13
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(non-blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AMEND
- dissent: duplicate_of:F-038 ; realist d1 «DISPUTE F-013 — класс: duplicate_of:F-038 — контр-evidence: `server.py:2495`, `2564`, `2565` — окно освобождённого порта и разрешение продолжить при недоказанном listener PID уже входят в F-038.» → teamlead/cycle-1/debate/d1/realist.md ; visionary d1 «AMEND F-013 — priority=blocking; locations=server.py:2495,2564; fix=выделять порт под общим замком до проверки владения либо `--port 0` с чтением реального порта; 401 на ready до DELIVERED счи» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=blocking; locations=server.py:2495,2564; fix=выделять порт под общим замком до проверки владения либо `--port 0` с чтением реального порта; 401 на ready до DELIVERED считать `ServeUnavailable`, а не `ServeSecu (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> ### F-013
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ/граничные условия
> locations: bridges/opencode-zen-bridge/server.py:2495, bridges/opencode-zen-bridge/server.py:2564
> rule: REQ-008 (свой слушатель). Окно между `bind` пробного сокета и bind serve; `lsof` с `None` проверку чужого слушателя пропускает.
> evidence: Скан порта `bind`/`close`, затем helper; `if listener_pid is not None and (listener_pid != serve_pid or ...)`.
> fix: Держать пробный сокет до старта serve или перепроверять слушателя до prompt; `lsof` без pid — `ServeUnavailable`.
> verify: Занятый между probe и bind порт даёт `ServeUnavailable`, а не чужой HTTP.

### F-014
- origin: skeptic · R1 · skeptic-14
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(non-blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AMEND
- dissent: realist d1 «DISPUTE F-014 — класс: invalid — контр-evidence: `server.py:2654`, `2655`, `2666`, `2678`; `tests/test_realtime_reasoning.py:114` — `feed()` сохраняет полный `input.ended.text`, а поле `delta` в» → teamlead/cycle-1/debate/d1/realist.md ; visionary d1 «AMEND F-014 — priority=non-blocking; locations=server.py:2654,2678; fix=статус `tool_use` брать из типа события (`success`/`failed`); накопление `input.delta` не нужно — причина: `feed` читает» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:2654,2678; fix=статус `tool_use` брать из типа события (`success`/`failed`); накопление `input.delta` не нужно — причина: `feed` читает поле `text`, которое несёт только `inpu (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> ### F-014
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ/логика
> locations: bridges/opencode-zen-bridge/server.py:2654, bridges/opencode-zen-bridge/server.py:2678
> rule: REQ-012 (native tool → текущий внутренний вид). DSH-маппинг читает имя и arguments; статус в выдачу DSH не входит.
> evidence: `feed` присваивает `item["text"] = text_value` вместо накопления дельт; `complete` всегда кладёт `"status": "error"`, в том числе на `session.tool.success`.
> fix: Склеивать `input.delta` либо опираться только на `input.ended.text`; статус брать из типа события.
> verify: Фикстура `session.tool.success` с двумя delta даёт полный JSON аргументов и status `success`.

### F-015
- origin: skeptic · R1 · skeptic-15
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(non-blocking) | D1 skeptic=AUTHOR | D1 realist=AMEND | D1 visionary=AGREE
- dissent: realist d1 «AMEND F-015 — priority=non-blocking; locations=server.py:2569,server.py:2570; fix=Исправить комментарий о записи stderr в лог; проверку отсутствия пароля в итоговом sink включить в F-042 — при» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: — priority=non-blocking; locations=server.py:2569,server.py:2570; fix=Исправить комментарий о записи stderr в лог; проверку отсутствия пароля в итоговом sink включить в F-042 — причина: `_drain_stderr` на `server.py:1028 (teamlead/cycle-1/debate/d1/realist.md)
- text (дословно, R1 skeptic):
> ### F-015
> priority: non-blocking
> criterion: РИСКИ/безопасность
> locations: bridges/opencode-zen-bridge/server.py:2569, bridges/opencode-zen-bridge/server.py:2570, bridges/opencode-zen-bridge/server.py:3242
> rule: REQ-015 / AC-020. Пароль в лог этим путём не пишется: sink пустой, `_mask_secrets` режет токены ≥24 символов.
> evidence: Комментарий «stderr помощника дренируется в лог»; вызов `_drain_stderr(helper, [])`. `_drain_stderr` только дополняет список.
> fix: Либо логировать stderr через `_mask_secrets`, либо поправить комментарий. Добавить тест: пароль попытки отсутствует в `bridge.log`.
> verify: Прогон serve с известным паролем, `assertNotIn(password, log)`.

### F-016
- origin: skeptic · R1 · skeptic-16
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(non-blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: duplicate_of:F-050 ; realist d1 «DISPUTE F-016 — класс: duplicate_of:F-050 — контр-evidence: `server.py:4877`, `4884`, `5456`, `5468` — семантика request-level «первых» таймингов уже описана в F-050. Простое обнуление при fallb» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-016
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/server.py:4877, bridges/opencode-zen-bridge/server.py:4884
> rule: REQ-016 / AC-021. Поля в строке `O-EXIT/v1` есть; после fallback значение `first_event_ms` остаётся от serve при `transport=run`.
> evidence: `xs["first_event_ms"] = result["first_event_ms"]` дважды подряд до ветки fallback, которая меняет `transport` на `run` и возвращает `False`.
> fix: При возврате в run сбрасывать `first_event_ms`/`ttft_ms` либо помечать, к какому транспорту они относятся.
> verify: O-EXIT fallback-запроса не показывает serve-миллисекунды как тайминг итогового run.

### F-017
- origin: skeptic · R1 · skeptic-17
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(non-blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: duplicate_of:F-042 ; realist d1 «DISPUTE F-017 — класс: duplicate_of:F-042 — контр-evidence: `server.py:1795`; `tests/test_realtime_reasoning.py:634` — отсутствие поведенческой матрицы переключателей входит в F-042; проверка чи» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-017 [sweep]
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/server.py:1795, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:634
> rule: REQ-003 / AC-004. Дефолт без флага — run: полный сьют 400 passed это подтверждает. Прямой матрицы kill-switch нет.
> evidence: `_select_transport` читает `TRANSPORT`, `REALTIME_SERVE_ENABLED` и файл `disable-serve`. Тесты группы B форсят `serve` или один сценарий `auto`+503.
> fix: Четыре случая: `TRANSPORT=run`, override `0`, файл disable, опечатка значения — все остаются на run и не зовут `_spawn_serve`.
> verify: Счётчик спавнов serve в этих четырёх случаях равен 0.

### F-018
- origin: skeptic · R1 · skeptic-18
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR(non-blocking) | D1 skeptic=AUTHOR | D1 realist=DISPUTE | D1 visionary=AGREE
- dissent: duplicate_of:F-042 ; realist d1 «DISPUTE F-018 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_realtime_reasoning.py:442`, `443`, `445` — слабость временного оракула и отсутствие независимого upstream-end уже описаны » → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> ### F-018
> priority: non-blocking
> criterion: ПОЛНОТА/покрытие AC
> locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:441
> rule: REQ-001 / AC-001 / AC-002. Реалтайм на сокете есть (red на `origin/dev`, green `VER-005`). Интервал соседей &lt;500 мс и накладные моста ≤250 мс тест не утверждает: проверяется span &lt;2.0 с и «первая дельта раньше конца апстрима».
> evidence: `test_ac026_realtime_chunks_before_upstream_end` сравнивает `model_reasoning[-1][0] - model_reasoning[0][0]` с `2.0`.
> fix: Утверждать максимум соседнего интервала reasoning-чанков и верхнюю границу задержки мост↔сокет на фейке с известным `sleep`.
> verify: Тест красный, если чанки склеиваются в один блок в конце шага.

### F-019
- origin: realist · R1 · realist-01
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-001 — priority=P1, blocking. Потеря пробельных дельт.**  
> Locations: `server.py:3018`, `server.py:3029`. Правило: REQ-005, REQ-010, AC-006. Evidence: `if text_value.strip():` окружает накопление и передачу дельты. Отдельные `" "`, `"\n"` и отступы исчезают, меняя reasoning, обычный текст и содержимое JSON-аргументов инструмента. Исправление: передавать все непустые дельты; определение первого содержательного токена отделить от сохранения байтов. Проверка: разбиения с отдельными пробелами, LF, отступами и пробелом внутри строкового аргумента дают исходную конкатенацию.

### F-020
- origin: realist · R1 · realist-02
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: duplicate_of:F-008 ; skeptic d1 «DISPUTE F-020 — класс: duplicate_of:F-008 — контр-evidence: server.py:1675 `parts.append(chr(int(hex_part, 16)))`, server.py:1701 `_loads_object` на ошибке возвращает `{}` — тот же парсер. Фикс » → teamlead/cycle-1/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-002 — priority=P1, blocking. Собственный JSON-парсер повреждает Unicode.**  
> Locations: `server.py:1560`, `server.py:1679`, `server.py:1705`, `server.py:2857`. Правило: python-standards.md §6, §16; REQ-005. Evidence: каждый `\uXXXX` преобразуется отдельным `chr()`. Допустимая пара `\ud83d\ude00` остаётся двумя суррогатами и ломает последующее UTF-8-кодирование. Глубина также не ограничена, `RecursionError` не обработан. Исправление: заменить парсер stdlib `json.loads` с типизированной границей и явной обработкой ошибок. Проверка: escaped emoji, вложенный JSON, невалидный JSON и прежние wire-фикстуры.

### F-021
- origin: realist · R1 · realist-03
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-021 — priority=non-blocking; locations=server.py:2718,2889,2892,3080; fix=передавать абсолютный `attempts.deadline` вместо `prompt_send_start + TIMEOUT_S`; выход цикла без `terminal` к» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:2718,2889,2892,3080; fix=передавать абсолютный `attempts.deadline` вместо `prompt_send_start + TIMEOUT_S`; выход цикла без `terminal` классифицировать как timeout, а не успех  (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-003 — priority=P1, blocking. Общий дедлайн не управляет serve-попыткой.**  
> Locations: `server.py:2718`, `server.py:2889`, `server.py:2892`, `server.py:3080`. Правило: `R-BULK-I1`, feature.md — остаток дедлайна на всей I/O-цепочке. Evidence: вместо дедлайна запроса создаётся `prompt_send_start + TIMEOUT_S`; при исчерпании цикла возвращается результат с пустыми `terminal` и `exit_reason`. Caller может выдать успешный финал для незавершённого ответа. Исправление: передавать абсолютный deadline, ограничивать им setup/read/retry и явно классифицировать истечение. Проверка: повтор у границы общего дедлайна не продлевает запрос; отсутствие terminal никогда не становится успехом.

### F-022
- origin: realist · R1 · realist-04
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-004 — priority=P1, blocking. Пять секунд тишины ошибочно обрывают serve.**  
> Locations: `server.py:2827`, `server.py:2848`, `server.py:2860`, `server.py:2928`. Правило: REQ-006–007, AC-009–010. Evidence: SSE-соединение создано с `timeout=5`; таймаут чтения превращается в EOF/`invalid_serve_event`, хотя первый токен и stall по умолчанию допускают 60 секунд. Исправление: согласовать чтение сокета с watchdog и отличать промежуточную тишину от окончания потока. Проверка: пауза больше 5 секунд и меньше заданного watchdog не вызывает повтор или ошибку.

### F-023
- origin: realist · R1 · realist-05
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-005 — priority=P1, blocking. Timeout cleanup не применяется к существующему соединению.**  
> Locations: `server.py:2403`, `server.py:2755`, `server.py:2997`, `server.py:3084`, `server.py:3094`. Правило: feature.md — таймаут каждого шага, включая `finally`; REQ-008. Evidence: при переданном `conn` аргумент `timeout=0.25` не меняет timeout соединения, созданного ранее с 3 секундами. Несколько управляющих вызовов и их повторов задерживают `lease.cleanup()`. Исправление: применять актуальный timeout к сокету, ограничить общий cleanup-бюджет, гарантировать kill группы независимо от HTTP-cleanup. Проверка: зависшие control-endpoints не удерживают процессы дольше AC-011.

### F-024
- origin: realist · R1 · realist-06
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-006 — priority=P1, blocking. Первая видимая реакция отсутствует во время setup.**  
> Locations: `server.py:2740`, `server.py:2778`, `server.py:2810`, `server.py:2835`, `server.py:2890`, `server.py:5298`, `server.py:5363`. Правило: REQ-004, AC-005. Evidence: статус начинает обслуживаться после spawn/readiness/create/subscribe; в legacy — после ожидания gate/limiter и запуска. Исправленная база `status_next` не позволяет эмитить статус во время уже блокирующего setup. Исправление: обслуживать ограниченный по времени первый статус с момента открытия SSE, включая ожидания запуска. Проверка: каждый setup-этап и занятый gate задержаны более секунды, статус всё равно приходит в пределах AC-005.

### F-025
- origin: realist · R1 · realist-07
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-025 — priority=non-blocking; locations=server.py:1096,5439,5453; fix=проверять watchdog и client_gone также после обработки каждой строки — причина: `on_idle` срабатывает на тишине `_S» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:1096,5439,5453; fix=проверять watchdog и client_gone также после обработки каждой строки — причина: `on_idle` срабатывает на тишине `_StdoutFeed`. `opencode run` выдаёт 3-4 со (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-007 — priority=P1, blocking. Legacy-watchdog зависит от отсутствия stdout.**  
> Locations: `server.py:1096`, `server.py:5439`, `server.py:5453`. Правило: REQ-006–008. Evidence: надзор передан как `on_idle`; поступление каждой строки сбрасывает idle. Непрерывные служебные либо невалидные строки предотвращают проверку первого токена, stall и ухода клиента. Исправление: выполнять надзор по независимому монотонному расписанию и при поступлении данных. Проверка: служебные строки каждые 100 мс не отменяют watchdog и обнаружение disconnect.

### F-026
- origin: realist · R1 · realist-08
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: duplicate_of:F-001 ; skeptic d1 «DISPUTE F-026 — класс: duplicate_of:F-001 — контр-evidence: server.py:4848 и server.py:5768 `attempts.note_spawn()` без `gate.acquire()` и без `spawn_limiter.acquire`; run берёт оба на server.py» → teamlead/cycle-1/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-008 — priority=P1, blocking. Serve обходит защиты холодного старта.**  
> Locations: `server.py:4848`, `server.py:5768`, `server.py:2740`. Правило: REQ-013, `S-HERD-I1`, `R-BULK-I2`. Evidence: перед `_serve_one_attempt` вызывается `note_spawn()`, но нет `_StartupGate.acquire()` и `res.spawn_limiter.acquire()`, присутствующих в run. Шесть обработчиков могут одновременно поднять шесть serve. Исправление: подключить serve к тем же защитам с остатком дедлайна и гарантированным освобождением. Проверка: конкурентные stream/JSON-запросы соблюдают общий темп запусков и gate.

### F-027
- origin: realist · R1 · realist-09
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-009 — priority=P1, blocking. Fallback может превысить потолок трёх запусков.**  
> Locations: `server.py:4866`, `server.py:4897`, `server.py:5298`, `server.py:5785`, `server.py:5806`, `server.py:5992`, `server.py:4491`. Правило: REQ-009, AC-013, `R-BULK-I2`. Evidence: после нескольких serve-попыток `return False` переводит управление в run без новой проверки потолка; run непосредственно запускает процесс и делает `note_spawn()`. Сам fallback также обходит `allow_retry`. Исправление: единый допуск каждой следующей попытки, включая смену транспорта. Проверка: две доставленные неудачи serve, третья pre-delivery неудача — run не становится четвёртым запуском.

### F-028
- origin: realist · R1 · realist-10
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=INCONCLUSIVE
- dissent: visionary d1 «INCONCLUSIVE F-028 — нужен исходник `_RequestAttempts.commit` и `attempt_done` (server.py ~2290) плюс тест OPEN→HALF_OPEN→успешный serve→CLOSED. В diff на serve-успехе вызывается только `serve_health» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-010 — priority=P1, blocking. Успех serve не закрывает HALF_OPEN Circuit Breaker.**  
> Locations: `server.py:4914`, `server.py:5818`. Правило: REQ-009, `R-BULK-I3`. Evidence: успех сбрасывает только `serve_health`; `attempts.attempt_done(False, True)` отсутствует. Зарезервированная проба HALF_OPEN не завершается успехом, последующие запросы могут оставаться заблокированными. После предыдущего timeout также может сохраниться `_pending_failure`. Исправление: завершать каждую попытку через общий механизм breaker. Проверка: OPEN → HALF_OPEN → успешный serve → CLOSED; timeout → успешный повтор не засчитывается окончательным отказом.

### F-029
- origin: realist · R1 · realist-11
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-011 — priority=P1, blocking. Prompt-response не управляет барьером доставки и классификацией ошибок.**  
> Locations: `server.py:2413`, `server.py:2414`, `server.py:2879`, `server.py:2880`, `server.py:2901`, `server.py:2965`. Правило: заявленная `FALLBACK_DECISION_TABLE`, REQ-009. Evidence: `headers_at` записывается после чтения всего тела; `status` и `error` практически не используются, security проверяется только после получения очередного SSE-события. HTTP 400/404/422/429/5xx prompt не получают заявленных действий. Исправление: фиксировать доставку при получении заголовков, независимо наблюдать результат worker и применять полную таблицу решений. Проверка: все классы prompt-ответов, включая заголовки с зависшим телом и отсутствие SSE, дают нужный исход без недопустимого fallback.

### F-030
- origin: realist · R1 · realist-12
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-012 — priority=P1, blocking. Ошибки провайдера обходят прежнюю recovery-семантику.**  
> Locations: `server.py:3073`, `server.py:4909`, `server.py:5813`, `server.py:4943`, `server.py:5884`. Правило: REQ-009, REQ-011. Evidence: любой `result["error"]` немедленно завершает запрос; различие транзиентной и фатальной ошибки не используется. В `_incomplete_step_signal` передаётся `False` вместо факта транзиентного обрыва. Исправление: сохранить классификацию, лимиты и восстановление legacy-пути на накопленном результате serve. Проверка: 429/5xx/transport error до и после вывода, фатальные 4xx и все соответствующие сценарии `test_step_interruption.py`.

### F-031
- origin: realist · R1 · realist-13
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: duplicate_of:F-006 ; skeptic d1 «DISPUTE F-031 — класс: duplicate_of:F-006 — контр-evidence: server.py:4950 и server.py:4961 `tool_choice=None`, вызов server.py:5981 передаёт литерал `None` при живом параметре `_serve_json` — т» → teamlead/cycle-1/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-013 — priority=P1, blocking. Теряется `tool_choice`.**  
> Locations: `server.py:4753`, `server.py:4950`, `server.py:4961`, `server.py:5971`. Правило: REQ-002, REQ-011; обратная совместимость входного контракта. Evidence: stream-helper не принимает `tool_choice`, использует `None`; JSON-helper получает явный `None` вместо аргумента `_serve_json`. Recovery для `required` и конкретного имени инструмента меняет поведение. Исправление: передавать исходное значение через все serve-ветки. Проверка: `required`, именованный выбор и `none` эквивалентны run.

### F-032
- origin: realist · R1 · realist-14
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-032 — priority=non-blocking; locations=server.py:3046,3052,3077,4804; fix=при `step_finish` с эмитированным вызовом инструмента завершать попытку (terminal) вместо ожидания `execution.» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:3046,3052,3077,4804; fix=при `step_finish` с эмитированным вызовом инструмента завершать попытку (terminal) вместо ожидания `execution.succeeded` — причина: при политике по ум (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-014 — priority=P1, blocking. Serve не останавливается после инструментального шага.**  
> Locations: `server.py:3046`, `server.py:3052`, `server.py:3077`, `server.py:4804`. Правило: REQ-011. Evidence: после получения tool call и `session.step.ended` цикл продолжает читать до `session.execution.succeeded`; последующие text/reasoning не блокируются для обычного текстового tool call. Исправление: завершать попытку на границе шага с вызовами, interrupt/cleanup выполнять до дальнейшей генерации. Проверка: апстрим посылает второй шаг после первого tool call — второй шаг не попадает клиенту, итог `tool_calls`.

### F-033
- origin: realist · R1 · realist-15
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AMEND | D1 realist=AMEND | D1 visionary=AGREE
- dissent: skeptic d1 «AMEND F-033 — priority=blocking; locations=server.py:4843, server.py:4901, server.py:4925, server.py:4952, server.py:5850, server.py:5908; fix=Дедуплицировать только text (как `_PrefixDedup` н» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «AMEND F-033 — priority=blocking; locations=server.py:4843,server.py:4901,server.py:4925,server.py:4952,server.py:5850,server.py:5908; fix=Сохранить прежнюю дедупликацию текстового префикса при» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: skeptic d1: — priority=blocking; locations=server.py:4843, server.py:4901, server.py:4925, server.py:4952, server.py:5850, server.py:5908; fix=Дедуплицировать только text (как `_PrefixDedup` на server.py:2318) и tool_calls (как serv (teamlead/cycle-1/debate/d1/skeptic.md) ; realist d1: — priority=blocking; locations=server.py:4843,server.py:4901,server.py:4925,server.py:4952,server.py:5850,server.py:5908; fix=Сохранить прежнюю дедупликацию текстового префикса при recovery, разделять reasoning между поп (teamlead/cycle-1/debate/d1/realist.md)
- text (дословно, R1 realist):
> **F-015 — priority=P1, blocking. Повтор serve дублирует уже отданный текст.**  
> Locations: `server.py:4843`, `server.py:4901`, `server.py:4925`, `server.py:4952`, `server.py:5850`, `server.py:5908`. Правило: сохранение recovery-семантики, REQ-009. Evidence: парсер пересоздаётся, но аналог `_PrefixDedup`/`_dedup_retry_text` не применяется; JSON соединяет результаты попыток. Повторы unmapped/incomplete также не получают обязательного разделителя reasoning между попытками. Исправление: сохранить reasoning без дедупликации, явно разделять попытки, дедуплицировать текст по прежнему правилу. Проверка: одинаковый и расходящийся префиксы при timeout/incomplete/unmapped через оба режима.

### F-034
- origin: realist · R1 · realist-16
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AMEND | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: skeptic d1 «AMEND F-034 — priority=non-blocking; locations=server.py:4886, server.py:4915, server.py:5795, server.py:5874; fix=Перед `continue` на timeout/invalid прибавлять уже полученный `result["usage"» → teamlead/cycle-1/debate/d1/skeptic.md ; visionary d1 «AMEND F-034 — priority=non-blocking; locations=server.py:4886,4915,5795,5874; fix=добавлять `result["usage"]` в аккумулятор до решения о повторе — причина: REQ-014 имеет приоритет SHOULD. Ветк» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: skeptic d1: — priority=non-blocking; locations=server.py:4886, server.py:4915, server.py:5795, server.py:5874; fix=Перед `continue` на timeout/invalid прибавлять уже полученный `result["usage"]` к аккумулятору попыток. — причина: RE (teamlead/cycle-1/debate/d1/skeptic.md) ; visionary d1: — priority=non-blocking; locations=server.py:4886,4915,5795,5874; fix=добавлять `result["usage"]` в аккумулятор до решения о повторе — причина: REQ-014 имеет приоритет SHOULD. Ветка timeout/invalid-event делает `continue (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-016 — priority=P2, blocking. Usage неуспешных попыток теряется.**  
> Locations: `server.py:4886`, `server.py:4915`, `server.py:5795`, `server.py:5874`. Правило: REQ-014. Evidence: ветки timeout/invalid-event выполняют `continue` до аккумуляции уже полученного `result["usage"]`. Исправление: учитывать usage завершённых шагов всех оплаченных попыток до принятия решения о повторе. Проверка: первая попытка отдаёт `step.ended`, затем обрывается; финальный usage равен сумме её токенов и успешного повтора.

### F-035
- origin: realist · R1 · realist-17
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-017 — priority=P1, blocking. На ошибках запуска пропускается cleanup.**  
> Locations: `server.py:1768`, `server.py:2510`, `server.py:2550`, `server.py:2563`, `server.py:2568`, `server.py:2572`, `server.py:2740`. Правило: REQ-008, `T-LIFE`, secure temporary files. Evidence: собственные `raise ServeUnavailable(...)` не входят в `except (OSError, ValueError, subprocess.SubprocessError)`; вызов `_spawn_serve` расположен до `try/finally` попытки. При отказе `Popen` также не закрывается write-конец lifeline и не удаляется созданный state-dir. Исправление: обеспечить владение ресурсами с момента их создания и cleanup на каждом исходе. Проверка: spawn failure, handshake timeout/mismatch и foreign listener оставляют ноль процессов, FD, lease и state-dir. Лог L2 дополнительно содержит `ResourceWarning: subprocess ... is still running`.

### F-036
- origin: realist · R1 · realist-18
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-036 — priority=non-blocking; locations=server.py:2842,2859,2863,2865,3107; fix=`put` с таймаутом и флагом остановки, ограниченный `join` потоков в `finally` — причина: блокировка требу» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:2842,2859,2863,2865,3107; fix=`put` с таймаутом и флагом остановки, ограниченный `join` потоков в `finally` — причина: блокировка требует 4096 непрочитанных событий в очереди. (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-018 — priority=P1, blocking. SSE-reader может навсегда остаться на заполненной очереди.**  
> Locations: `server.py:2842`, `server.py:2859`, `server.py:2863`, `server.py:2865`, `server.py:3107`. Правило: `T-LIFE`, `C-MULT-I4`. Evidence: оба `events.put(...)` блокирующие, без timeout/cancel; reader не присоединяется при выходе consumer. Убийство serve не разблокирует поток, уже ожидающий место в Python-очереди. Исправление: cancellation-aware bounded queue, отдельный сигнал окончания и ограниченный join. Проверка: заполнить очередь, отменить запрос; поток и принадлежащие ему ресурсы освобождаются.

### F-037
- origin: realist · R1 · realist-19
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-037 — priority=non-blocking; locations=server.py:2570,1028; fix=дренаж stderr с ограниченным хвостом (`deque(maxlen)`) — причина: список растёт только за время жизни одной попытки (до » → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:2570,1028; fix=дренаж stderr с ограниченным хвостом (`deque(maxlen)`) — причина: список растёт только за время жизни одной попытки (до `cleanup`). Тихий `opencode serve` пишет (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-019 — priority=P2, blocking. Дренаж stderr накапливает неограниченную память.**  
> Locations: `server.py:2570`, `server.py:1028`. Правило: ограниченные ресурсы `HL-ENV`, `C-MULT-I2`. Evidence: `_drain_stderr(helper, [])` добавляет каждую строку в список, удерживаемый потоком до окончания попытки; список никем не читается и не ограничен. Исправление: использовать ограниченный хвост либо дренаж с отбрасыванием и счётчиком. Проверка: многомегабайтный непрерывный stderr не вызывает линейного роста RSS.

### F-038
- origin: realist · R1 · realist-20
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-038 — priority=non-blocking; locations=server.py:2374,2564,2565,2778; fix=положительное доказательство слушателя (`lsof` вернул pid, и он равен `serve_pid`) до первой авторизованной за» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:2374,2564,2565,2778; fix=положительное доказательство слушателя (`lsof` вернул pid, и он равен `serve_pid`) до первой авторизованной записи, иначе `ServeUnavailable` — причина (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-020 — priority=P1, blocking. Авторизация отправляется без обязательного ownership-proof слушателя.**  
> Locations: `server.py:2374`, `server.py:2564`, `server.py:2565`, `server.py:2778`. Правило: security.md, подтверждение владения до передачи секретов. Evidence: `listener_pid is None` допускается; проверка выполняется сразу после handshake, до гарантированного bind serve. Порт предварительно освобождается, поэтому возможна гонка, а последующий reconnect не перепроверяет владельца. Исправление: требовать положительное совпадение listener PID, PGID и живого helper до первой авторизованной записи и при явном reconnect; неоднозначность — fail-closed. Проверка: отсутствующий/чужой/сменившийся слушатель получает ноль байтов Authorization и prompt.

### F-039
- origin: realist · R1 · realist-21
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: duplicate_of:F-003 ; skeptic d1 «DISPUTE F-039 — класс: duplicate_of:F-003 — контр-evidence: server.py:72 пишет `parent_start_ts`, server.py:2593 `parent_alive = parent_pid > 0 and _pid_alive`, при живом pid `continue`, затем о» → teamlead/cycle-1/debate/d1/skeptic.md ; visionary d1 «AMEND F-039 — priority=non-blocking; locations=server.py:74,2593,2606,2609; fix=сверять `owner_uid`, `helper_lstart`, argv и `attempt_id` с живым процессом, lease-каталог создавать с 0700 — пр» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:74,2593,2606,2609; fix=сверять `owner_uid`, `helper_lstart`, argv и `attempt_id` с живым процессом, lease-каталог создавать с 0700 — причина: сигнал идёт только процессу с `-- (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-021 — priority=P1, blocking. Reaper не проверяет идентичность процессов.**  
> Locations: `server.py:74`, `server.py:2593`, `server.py:2606`, `server.py:2609`. Правило: `T-LIFE`, безопасность сигналов. Evidence: сохранённые UID/start-time/attempt не сверяются; достаточно живого PID и подстроки `"--serve-helper"`. PID reuse может сохранить сироту либо привести к сигналу другой сессии. Исправление: сверять UID, реальные времена старта, точный script/argv, attempt и PGID; безопасно работать с lease-каталогом. Проверка: переиспользованные PID, чужой helper и подложный lease не получают сигналов.

### F-040
- origin: realist · R1 · realist-22
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-040 — priority=non-blocking; locations=server.py:174,177,181,195; fix=в `finally` helper слать SIGTERM всей собственной группе (`killpg(getpgrp())`) с эскалацией — причина: при штатном» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:174,177,181,195; fix=в `finally` helper слать SIGTERM всей собственной группе (`killpg(getpgrp())`) с эскалацией — причина: при штатном пути клиента `lease.cleanup()` делает ` (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-022 — priority=P1, blocking. Lifeline не гарантирует остановку всего дерева при смерти моста.**  
> Locations: `server.py:174`, `server.py:177`, `server.py:181`, `server.py:195`. Правило: REQ-008, `T-LIFE`. Evidence: helper завершает только непосредственный `serve_proc`, после чего удаляет lease. Потомок serve, переживший родителя, не получает гарантированный групповой сигнал и лишается следа для reaper. Исправление: реализовать проверяемое завершение всей собственной группы при EOF/TERM, включая эскалацию. Проверка: убить мост при helper → serve → grandchild; все процессы исчезают, чужие группы не затронуты.

### F-041
- origin: realist · R1 · realist-23
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-023 — priority=P1, blocking. Отмена клиента реализована не во всех режимах.**  
> Locations: `server.py:4750`, `server.py:5769`. Правило: REQ-008. Evidence: `_client_gone_check` превращает RST/OSError в `False`; JSON-путь вообще не передаёт callback `is_client_gone`. Исправление: различать отсутствие данных и терминальный разрыв, подключить надзор к JSON и setup-ожиданиям. Проверка: FIN и RST до первого события, после токена и в JSON приводят к остановке в пределах AC-011.

### F-042
- origin: realist · R1 · realist-24
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-024 — priority=P1, blocking. Матрица PASS не соответствует содержимому оракулов.**  
> Locations: `tests/test_realtime_reasoning.py:376`, `tests/test_realtime_reasoning.py:434`, `tests/test_realtime_reasoning.py:442`, `tests/test_realtime_reasoning.py:619`; `verification-traceability.md`, строки REQ-001, REQ-006–016. Правило: testing.md — независимый эталон полноты; task envelope — поштучная проверка AC. Evidence: `upstream_end_t = elapsed` — EOF самого клиентского ответа; выдача всех пяти дельт одной пачкой также удовлетворяет `first < elapsed` и spread `<2`. Пределы 500/250 мс не проверяются; `assertTrue(silence or rows)` заведомо проходит при непустой таблице. Исправление: независимые upstream timestamps/барьеры; добавить serve JSON, три watchdog, delivered-retry, лимиты, cleanup, permission/unmapped и финальный usage. Исправить traceability по реальным результатам; аварийную чистоту подпроцессов подтвердить crash-guard либо предусмотренным ручным свидетельством. Проверка: намеренно буферизующая и нарушающая таблицу реализация должна краснить соответствующие тесты.

### F-043
- origin: realist · R1 · realist-25
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-025 — priority=P2, blocking. «Ноль диагностик» получен с подавленными правилами.**  
> Locations: `tests/test_realtime_reasoning.py:2`, `381`, `384`, `385`, `390`, `391`, `408`, `411`, `429`, `431`. Правило: python-standards.md — запрет №9; запрет необъяснённых suppressions. Evidence: заголовок выключает множество диагностик, включая `reportAny` и `reportMissingParameterType`; новые обращения содержат необъяснённые `type: ignore`. Исправление: убрать blanket-подавления и ненужные ignores, исправить типы; узкие исключения обосновать. Проверка: новый файл проверяется с включёнными соответствующими правилами.

### F-044
- origin: realist · R1 · realist-26
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-044 — priority=non-blocking; locations=test_realtime_reasoning.py:299,300; fix=убрать `os.environ.pop("FAKE_RT_MODE")` после `self.env.stop()` — причина: `mock.patch.dict` уже восстана» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=test_realtime_reasoning.py:299,300; fix=убрать `os.environ.pop("FAKE_RT_MODE")` после `self.env.stop()` — причина: `mock.patch.dict` уже восстанавливает окружение. Лишний `pop` портит т (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-026 — priority=P2, blocking [sweep]. Тест удаляет исходное значение окружения.**  
> Locations: `tests/test_realtime_reasoning.py:299`, `tests/test_realtime_reasoning.py:300`. Правило: testing.md — гарантированный откат `os.environ`. Evidence: после `self.env.stop()`, восстановившего исходный `FAKE_RT_MODE`, выполняется безусловный `pop`. Исправление: удалить дополнительную мутацию либо восстанавливать точное предыдущее состояние. Проверка: запуск при заранее установленном значении сохраняет его после teardown.

### F-045
- origin: realist · R1 · realist-27
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=AUTHOR | D1 visionary=DISPUTE
- dissent: invalid_after_recheck: Отклонено большинством 2/3 семейств (`Skeptic` `grok-4.7-high` `DISPUTE out_of_scope` + `Visionary` `claude-sonnet-5-5-high` `DISPUTE invalid`): обязательный гейт `VER-002` запускает `python3 -m unittest discover -s tests -p 'test_*.py'`, и все 17 существующих тестовых модулей автономного stdlib-моста написаны на `unittest.TestCase`. ; skeptic d1 «DISPUTE F-045 — класс: out_of_scope — контр-evidence: testing.md «Не использовать unittest.TestCase» написан для async-стека Litestar; этот мост — sync `ThreadingHTTPServer`, весь существующий н» → teamlead/cycle-1/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-045 — класс: invalid — контр-evidence: verification-surface.json, уровень L2, `L2-VER-002-unittest-discover`: `python3 -m unittest discover -s tests -p 'test_*.py'` в `cwd=bridges/open» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-027 — priority=P2, blocking. Новый тестовый модуль нарушает прямой запрет TestCase.**  
> Locations: `tests/test_realtime_reasoning.py:279`, `tests/test_realtime_reasoning.py:397`. Правило: testing.md — «Не использовать `unittest.TestCase`, `setUp`, `tearDown`». Evidence: оба новых класса основаны на TestCase. Исправление: использовать pytest-тесты и фикстуры с гарантированным teardown. Async/Litestar-инструментарий для этого синхронного stdlib-моста не требуется. Проверка: тот же набор сценариев проходит без новых TestCase.

### F-046
- origin: realist · R1 · realist-28
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AMEND | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: skeptic d1 «AMEND F-046 — priority=blocking; locations=tests/test_realtime_reasoning.py:321, tests/test_realtime_reasoning.py:392, tests/test_realtime_reasoning.py:444, tests/test_realtime_reasoning.py:56» → teamlead/cycle-1/debate/d1/skeptic.md ; visionary d1 «AMEND F-046 — priority=non-blocking; locations=test_realtime_reasoning.py:321,392,444,445,568,624; fix=для проверок времени оставить запас над порогом и убрать пороги, не заданные требованием » → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: skeptic d1: — priority=blocking; locations=tests/test_realtime_reasoning.py:321, tests/test_realtime_reasoning.py:392, tests/test_realtime_reasoning.py:444, tests/test_realtime_reasoning.py:568; fix=Оставить замер реального клиентск (teamlead/cycle-1/debate/d1/skeptic.md) ; visionary d1: — priority=non-blocking; locations=test_realtime_reasoning.py:321,392,444,445,568,624; fix=для проверок времени оставить запас над порогом и убрать пороги, не заданные требованием — причина: в репозитории нет маркеров `m (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-028 — priority=P2, blocking. Измерения времени смешаны с обычным тестовым контуром.**  
> Locations: `tests/test_realtime_reasoning.py:321`, `392`, `444`, `445`, `568`, `624`. Правило: testing.md §7.2, Serial Lane. Evidence: wall-clock assertions выполняются в обычном полном наборе без `measured`/`heavy`; уже зафиксировано падение около границы 1 секунды. Исправление: выделить замеры в последовательный измерительный контур, а состояния watchdog дополнить FakeClock-оракулами. Проверка: обычный набор не зависит от загрузки машины; отдельный измерительный прогон сохраняет проверки реального клиентского сокета.

### F-047
- origin: realist · R1 · realist-29
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: skeptic d1 «DISPUTE F-047 — класс: out_of_scope — контр-evidence: `allowed_envelope_changes` — ровно три файла кодера; README/CHANGELOG в пакет не входят. python-standards §12 про README Litestar-сервиса. Р» → teamlead/cycle-1/debate/d1/skeptic.md ; visionary d1 «AMEND F-047 — priority=non-blocking; locations=server.py:1326,1743,1795; fix=описать приоритеты переключателей, пороги, fallback и откат в PR и rollout-инструкции — причина: verification-surfa» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:1326,1743,1795; fix=описать приоритеты переключателей, пороги, fallback и откат в PR и rollout-инструкции — причина: verification-surface.json `allowed_envelope_changes` разре (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-029 — priority=P2, blocking. Эксплуатационные изменения не документированы.**  
> Locations: `server.py:1326`, `server.py:1743`, `server.py:1795`; `candidate-manifest.json:files`. Правило: python-standards.md §12. Evidence: добавлены transport/permission/watchdog overrides, dynamic-config и disable-файл, но разрешённый трёхфайловый diff не содержит обновлений README/CHANGELOG. Исправление: согласовать расширение документационного scope и описать приоритеты переключателей, пороги, fallback и откат. Проверка: оператор может включить и отключить транспорт по опубликованной инструкции без чтения исходника.

### F-048
- origin: realist · R1 · realist-30
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-048 — priority=non-blocking; locations=server.py:1844,1845,1875,2973; fix=сверять `sessionID` по сырому событию до `_map_serve_event` — причина: `_map_serve_event` для reasoning/text/s» → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:1844,1845,1875,2973; fix=сверять `sessionID` по сырому событию до `_map_serve_event` — причина: `_map_serve_event` для reasoning/text/step_finish/error возвращает payload без  (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-030 — priority=P2, blocking. Фильтр чужих сессий применяется после потери sessionID.**  
> Locations: `server.py:1844`, `server.py:1845`, `server.py:1875`, `server.py:2973`. Правило: граница изоляции serve-сессии, security.md — проверка входа на границе. Evidence: mapper удаляет `sessionID` у reasoning/text/error, затем фильтр разрешает `None`; чужая дельта либо ошибка проходит. Исправление: проверять sessionID в исходном wire-событии до отображения и обработки. Проверка: события второй сессии не меняют текст, usage, исход и watchdog текущей.

### F-049
- origin: realist · R1 · realist-31
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR(non-blocking) | D1 skeptic=DISPUTE | D1 realist=AUTHOR | D1 visionary=AGREE
- dissent: duplicate_of:F-011 ; skeptic d1 «DISPUTE F-049 — класс: duplicate_of:F-011 — контр-evidence: server.py:1791 `or len(head) == 4` после Mach-O/ELF. Любой файл без `#!` длиной от 4 байт считается нативным. Тот же предохранитель.» → teamlead/cycle-1/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-031 — priority=P3, non-blocking. Проверка нативного бинарника почти всегда разрешающая.**  
> Locations: `server.py:1777`, `server.py:1791`. Правило: заявленная проверка допуска auto. Evidence: `or len(head) == 4` принимает любой файл длиной не меньше четырёх байтов без shebang. Исправление: проверять известные исполняемые форматы либо убрать вводящее в заблуждение утверждение о такой проверке. Проверка: произвольный четырёхбайтовый файл не считается нативным opencode.

### F-050
- origin: realist · R1 · realist-32
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AUTHOR | D1 visionary=AMEND
- dissent: visionary d1 «AMEND F-050 — priority=non-blocking; locations=server.py:4877,4884,5456,5468,5793; fix=хранить request-level `first_event_ms`/`ttft_ms` отдельно от attempt-level, либо маркировать транспорт — » → teamlead/cycle-1/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: — priority=non-blocking; locations=server.py:4877,4884,5456,5468,5793; fix=хранить request-level `first_event_ms`/`ttft_ms` отдельно от attempt-level, либо маркировать транспорт — причина: REQ-016 требует наличия полей.  (teamlead/cycle-1/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-032 — priority=P2, blocking [sweep]. Поля «первого события» переписываются последующими попытками.**  
> Locations: `server.py:4877`, `server.py:4884`, `server.py:5456`, `server.py:5468`, `server.py:5793`. Правило: REQ-016, `O-EXIT/v1`. Evidence: значения запроса перезаписываются таймингами очередной попытки; в сыром L2 есть `first_event_ms=1975 ttft_ms=974`. В итоге названия полей не соответствуют первому событию и первому токену запроса. Исправление: сохранять первые request-level значения, attempt-level значения учитывать отдельно. Проверка: retry/fallback не стирает первый момент; для одного запроса первый токен не предшествует первому событию.

### F-051
- origin: visionary · R1 · visionary-01
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-019 ; skeptic d1 «DISPUTE F-051 — класс: duplicate_of:F-019 — контр-evidence: server.py:3018 и server.py:3029 тот же `text_value.strip()` на reasoning и text.» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-051 — класс: duplicate_of:F-019 — контр-evidence: `server.py:3018`, `3029` — тот же подтверждённый дефект отбрасывания пробельных reasoning/text-дельт.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-01 [blocking] Whitespace-дельты не пересылаются клиенту
> - Locations: server.py:~2360-3114 (`_serve_one_attempt`, ветки `etype == "reasoning"` и `etype == "text"`).
> - Правило: REQ-005/AC-006 (текст модели не модифицируется), REQ-001; F-37 (превью требует `\n`).
> - Evidence: `if text_value.strip(): … on_reasoning(text_value)` и такое же условие для `on_text`.
> - Fix: пересылать любую непустую дельту без `strip`; `first_token_at` и `last_token_at` обновлять только по содержательным токенам.
> - Проверка: тест с дельтами `"\n\n"`, `" "`, `"\n"`: конкатенация побайтно равна эталону, в том числе внутри `<tool_invoke>`.

### F-052
- origin: visionary · R1 · visionary-02
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-038 ; skeptic d1 «DISPUTE F-052 — класс: duplicate_of:F-038 — контр-evidence: server.py:2495 скан порта с закрытием пробного сокета и server.py:2564 пропуск при `listener_pid is None`. Параллельный одинаковый пор» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-052 — класс: duplicate_of:F-038 — контр-evidence: `server.py:2495`, `2505`, `2565` — гонка выбора порта и отсутствие обязательного ownership-proof уже покрыты F-038. Предложение перево» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-02 [blocking] Гонка выбора порта serve и отправка пароля не тому serve
> - Locations: server.py:~2360-3114 (`_spawn_serve`, цикл `range(20000 + pid%20000, 60000)` с bind-проб и закрытием сокета); `_serve_one_attempt` (ready-проверка).
> - Правило: C-MULT-I3/I4; `scope-and-contracts` (не ломать конкурентные запросы); `security.md` §9.
> - Evidence: все потоки сканируют от одного кандидата, сокет закрывается до bind serve. Два запроса в окне ~110 мс получают один порт. Если `lsof` ещё не видит слушателя, `GET /api/session/active` попадает в чужой serve и возвращает 401. Это `ServeSecurityError` без fallback.
> - Fix: глобальный замок на выделение порта до проверки владения; либо `--port 0` с чтением реального порта; 401 на ready до DELIVERED считать `ServeUnavailable`.
> - Проверка: тест на 6 параллельных stream-запросов, ни одного `serve security failure`.

### F-053
- origin: visionary · R1 · visionary-03
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=AMEND | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: invalid_after_recheck: Отклонено большинством 2/3 семейств (`Realist` `gpt-6.1-sol-high` `DISPUTE invalid` + `Skeptic` `grok-4.7-high` против снятия legacy-watchdog): `REQ-007 MUST` и `AC-010` прямо требуют настраиваемый 60-секундный watchdog первого токена (`OPENCODE_ZEN_BRIDGE_FIRST_TOKEN_TIMEOUT_S=60`) на обоих транспортах (`serve` и `run`). ; skeptic d1 «AMEND F-053 — priority=blocking; locations=server.py:5351, server.py:5465, константа `FIRST_TOKEN_TIMEOUT_S`; fix=Watchdog на run оставить (REQ-007 MUST). Дефолт first-token для legacy поднять» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-053 — класс: invalid — контр-evidence: `handoff-architect.md`, REQ-007 и AC-010 прямо требуют настраиваемый watchdog первого токена с рабочим допущением 60 секунд. Его наличие на legac» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: skeptic d1: — priority=blocking; locations=server.py:5351, server.py:5465, константа `FIRST_TOKEN_TIMEOUT_S`; fix=Watchdog на run оставить (REQ-007 MUST). Дефолт first-token для legacy поднять выше наблюдаемого здорового максимума 8 (teamlead/cycle-1/debate/d1/skeptic.md)
- text (дословно, R1 visionary):
> F-03 [blocking] Регрессия дефолтного пути `run`: watchdog первого токена 60 с
> - Locations: server.py:5351-5474 (`send_keepalive`, `watchdog_state`); константы `FIRST_TOKEN_TIMEOUT_S`, `FIRST_EVENT_TIMEOUT_S`, `STALL_TIMEOUT_S`.
> - Правило: REQ-003 (прежний путь остаётся рабочим), REQ-002.
> - Evidence: F-17/F-18: `run` выдаёт reasoning и text одним блоком в конце шага. F-32: максимум `deepseek-v4.1-flash-free` 85.65 с. По умолчанию serve выключен, поэтому путь `run` основной. Шаг дольше 60 с убивается и повторяется до 3 раз. Статусы `[мост]` и watchdog на `run` работают вне переключателя транспорта.
> - Fix: для legacy использовать потолок не ниже прежнего поведения либо отдельные пороги с высоким дефолтом, `first_event` считать по `step_start`, watchdog первого токена оставить только для serve; поведение legacy за флагом.
> - Проверка: фейк-CLI с паузой 70 с до единого блока завершается успешно без ретраев.

### F-054
- origin: visionary · R1 · visionary-04
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-001 ; skeptic d1 «DISPUTE F-054 — класс: duplicate_of:F-001 — контр-evidence: server.py:4848 и server.py:5768 без `_StartupGate` и `spawn_limiter`, те же строки, что F-001.» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-054 — класс: duplicate_of:F-026 — контр-evidence: `server.py:4848`, `5768` — обход стартовых защит уже покрыт F-026. Отдельное доказательство ротации прокси включено в F-042.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-04 [blocking] REQ-013 не выполнен для serve
> - Locations: server.py:~2360-3114 (`_serve_one_attempt` / `_spawn_serve`); AC-018.
> - Правило: REQ-013 (`_StartupGate`, `SPAWN_RATE_PER_S`), R-BULK-I2.
> - Evidence: serve-путь не вызывает `gate.acquire()` и `res.spawn_limiter.acquire()`, теста на ротацию IP нет.
> - Fix: acquire `spawn_limiter` и gate перед `_spawn_serve`, release в `finally`.
> - Проверка: тест двух запусков с подменённым `_next_standalone_proxy` и ограничением частоты.

### F-055
- origin: visionary · R1 · visionary-05
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-029 ; skeptic d1 «DISPUTE F-055 — класс: duplicate_of:F-029 — контр-evidence: server.py:2879 статус prompt почти не читается; строка таблицы про 429 не исполняется. Узкий случай «429 увеличивает serve_health» уже» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-055 — класс: duplicate_of:F-029 — контр-evidence: `server.py:2879`, `2880`, `2965` — игнорирование результата prompt-worker уже входит в F-029.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-05 [blocking] Результат prompt-POST игнорируется, `FALLBACK_DECISION_TABLE` мёртва
> - Locations: server.py:~2360-3114 (`_prompt_worker`, `prompt_status`); `FALLBACK_DECISION_TABLE` (server.py:~1450-1560).
> - Правило: `error-handling.md` (Identify→Assess), REQ-009.
> - Evidence: пишется `prompt_status["status"/"error"]`, проверяется только 401/403. 400/429/5xx и сетевая ошибка приводят к ожиданию 20 с. Строка таблицы про 429 и provider5xx не реализована, тест таблицы проверяет только `len ≥ 10`.
> - Fix: классифицировать статус prompt по таблице (retry с breaker+1, fail-closed на 400/404/422) или удалить таблицу.
> - Проверка: FakeServe отвечает 429 на prompt, затем retry без ожидания 20 с.

### F-056
- origin: visionary · R1 · visionary-06
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-033 ; skeptic d1 «DISPUTE F-056 — класс: duplicate_of:F-033 — контр-evidence: server.py:4843 парсер создаётся заново, `_PrefixDedup` на serve нет. Фикс — только text и tool_calls, не reasoning (см. AMEND F-033, A» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-056 — класс: duplicate_of:F-033 — контр-evidence: `server.py:4843`, `4901`, `5850`, `5908` — дубли текста и отсутствие разделителей уже покрыты F-033. Уточнение: потоковые одинаковые t» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-06 [blocking] Повтор после отданного контента дублирует text и tool_calls
> - Locations: server.py:4734-4967 (`_run_serve_stream_attempts`, ветки `allow_retry`/`continue`); `_serve_json_serve`.
> - Правило: REQ-009/AC-014, REQ-010.
> - Evidence: legacy использует `_PrefixDedup`, serve нет. После `stall_timeout` при уже отданных text или tool_call повтор выдаёт тот же контент снова.
> - Fix: дедуп префикса либо запрет retry после отданного text или tool_call.
> - Проверка: тест stall после части текста и вызова инструмента, клиент не видит дублей.

### F-057
- origin: visionary · R1 · visionary-07
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-024 ; skeptic d1 «DISPUTE F-057 — класс: duplicate_of:F-024 — контр-evidence: server.py:2740 и server.py:2890 статус обслуживается после spawn/ready/subscribe; gate до `feed.lines` молчит. Тот же REQ-004.» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-057 — класс: duplicate_of:F-024 — контр-evidence: `server.py:2740`, `2890`, `5298`, `5363` — отсутствие своевременной видимой реакции во время setup и ожиданий уже описано в F-024. Исп» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-07 [blocking] Первый статус ≤1.0 с (REQ-004) не гарантирован
> - Locations: server.py:5351-5474 (`send_keepalive`); `_serve_one_attempt` (`status_next`, `STATUS_INITIAL`).
> - Правило: REQ-004/AC-005.
> - Evidence: `STATUS_INITIAL` объявлен и нигде не эмитируется. На legacy статусы идут только из цикла `feed.lines`, а до него `_StartupGate` держит до 5 с (STARTUP_WAIT_S) и `spawn_limiter`. На serve цикл статусов стартует после spawn, ready, create, subscribe.
> - Fix: эмитить `STATUS_INITIAL` сразу после role-чанка до gate и spawn при включённом thinking.
> - Проверка: удержать gate 3 с, первый чанк с `[мост]\n` приходит ≤1.0 с.

### F-058
- origin: visionary · R1 · visionary-08
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=INCONCLUSIVE | D1 visionary=AUTHOR
- dissent: realist d1 «INCONCLUSIVE F-058 — нужны реальные wire-фикстуры `integration.updated` и heartbeat с подтверждённой формой `data`. На `server.py:1830` пустой словарь действительно отвергается для всех типов, кроме » → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-08 [blocking] Реальный wire v2.1.2 не проверен: события с пустым `data`
> - Locations: server.py:~1800-1880 (`_map_serve_event`: `if not data: raise ServeProtocolError`); `_serve_one_attempt` (`except ServeProtocolError` → `delivered=True`).
> - Правило: R-BULK-I3, REQ-012; факт-карта F-19, VER-006 DEFERRED_L3.
> - Evidence: любое событие кроме `server.connected` с пустым `data` (в F-19 на 161 мс приходит `integration.updated`) даёт `invalid_serve_event`, `delivered=True` и retry вместо fallback. Все фикстуры синтетические.
> - Fix: игнорировать неизвестные события и пустой `data`, валидировать только известные типы; добавить фикстуры, снятые с реального serve; прогнать VER-006 на живом контуре до включения флага.
> - Проверка: тест, подающий heartbeat и `integration.updated` с пустым `data`, не прерывает попытку. Статус PLAUSIBLE.

### F-059
- origin: visionary · R1 · visionary-09
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-035 ; skeptic d1 «DISPUTE F-059 — класс: duplicate_of:F-035 — контр-evidence: server.py:1768 `mkdtemp`, server.py:2572 `ServeUnavailable` мимо `lease.cleanup()`. Та же утечка state-dir и FD на отказе запуска.» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-059 — класс: duplicate_of:F-035 — контр-evidence: `server.py:1768`, `2510`, `2572`, `2740` — утечки state-dir/lifeline и пропуск cleanup на отказах запуска уже полностью входят в F-035» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-09 [blocking] Утечка tempdir и FD при сбое запуска serve
> - Locations: server.py:~2360-3114 (`_serve_env` → `mkdtemp`; `_spawn_serve`: `os.pipe`, `Popen` до создания `_ServeLease`; `lease_dir.mkdir`).
> - Правило: T-LIFE/v1, C-MULT-I4 (освобождение в `finally`).
> - Evidence: `zen-serve-state-*` удаляется только `lease.cleanup()`. При `ServeUnavailable("no free serve port")`, `OSError` от `Popen` (не перехватывается обработчиками) состояние и `lifeline_w` не освобождаются.
> - Fix: `try/finally` вокруг всего пути от `_serve_env`, закрытие обоих концов pipe, оборачивание OSError в `ServeUnavailable`.
> - Проверка: тест с подменённым `Popen` (OSError): нет `zen-serve-state-*` и FD после 50 итераций.

### F-060
- origin: visionary · R1 · visionary-10
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-042 ; realist d1 «DISPUTE F-060 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_realtime_reasoning.py:376`, `434`, `619`; `verification-traceability.md`, строки REQ-006–016 — та же неполнота оракулов и » → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-10 [blocking] Пробелы покрытия AC и неточная матрица
> - Locations: tests/test_realtime_reasoning.py (весь модуль); verification-traceability.md (строки REQ-006..009, REQ-013..016).
> - Правило: testing.md (регресс на каждое требование), `council` «Полнота/покрытие AC».
> - Evidence: нет тестов на AC-011/AC-012, serve `first_event/first_token/stall`, `_serve_json_serve`, AC-018, AC-020; фикстуры `__silent__` и `__never_event__` не используются; все строки матрицы PASS ссылаются на общий VER-001.
> - Fix: добавить недостающие тесты и привязать каждую строку матрицы к конкретному тесту.
> - Проверка: матрица с именем теста на каждое REQ/AC.

### F-061
- origin: visionary · R1 · visionary-11
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-008 ; skeptic d1 «DISPUTE F-061 — класс: duplicate_of:F-008 — контр-evidence: server.py:1560 `_JsonParser` и server.py:1675 суррогаты. Замена на `json.loads`, не на `orjson` (0 внешних зависимостей).» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-061 — класс: duplicate_of:F-020 — контр-evidence: `server.py:1560`, `1679`, `1705` — самодельный JSON-парсер и его ошибки уже покрыты F-020.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-11 [blocking] Самописный `_JsonParser` / `_loads_object`, ошибки маскируются
> - Locations: server.py:~1560-1700 (`_JsonParser`, `_loads_object`), используется в `_read_dynamic_config_enabled`, `_spawn_serve`, `_serve_http`, `_reader`.
> - Правило: python-standards §6/§7 (KISS, DRY), §3 (не маскировать ошибки); `json` остаётся импортированным.
> - Evidence: ~150 строк разбора JSON при доступном `json.loads`; парсер возвращает `{}` на ошибку, `RecursionError` не ловится, битый SSE-кадр превращается в `invalid_serve_event`.
> - Fix: `json.loads` с явным `except (ValueError, RecursionError)` и логом.
> - Проверка: тест битого и глубоко вложенного кадра даёт управляемую ошибку.

### F-062
- origin: visionary · R1 · visionary-12
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-043 ; skeptic d1 «DISPUTE F-062 — класс: duplicate_of:F-043 — контр-evidence: tests/test_realtime_reasoning.py:2 тот же блоковый `# pyright:` и `type: ignore` без причины.» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-062 — класс: duplicate_of:F-043 — контр-evidence: `tests/test_realtime_reasoning.py:2`, `384`, `408` — blanket-подавления диагностик и необъяснённые ignores уже входят в F-043.» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-12 [blocking] Подавления типов без обоснования
> - Locations: tests/test_realtime_reasoning.py:2 (`# pyright: reportAny=false, …` на 10 правил); `# type: ignore[attr-defined]` в `test_watchdog_first_event_timeout` и `setUp`/`tearDown` группы B.
> - Правило: python-standards, запрет №9.
> - Evidence: VER-004 требует нуль диагностик в новом тест-файле, и он достигнут блоковым подавлением, а не типизацией.
> - Fix: типизировать, убрать блоковое подавление и ненужные `type: ignore`, оставить точечные с причиной.
> - Проверка: VER-004 без подавлений.

### F-063
- origin: visionary · R1 · visionary-13
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(non-blocking) | D1 skeptic=AGREE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-042 ; realist d1 «DISPUTE F-063 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_realtime_reasoning.py:619`, `573`, `535`, `561` — несоответствие заявленного покрытия фактическим assertions уже входит в » → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-13 [non-blocking] Тавтологичные и неустойчивые тесты
> - Locations: tests/test_realtime_reasoning.py: `test_serve_health_and_fallback_table` (`assertTrue(silence or rows)`), `test_helper_argv_validation_and_lease_dir`, `test_native_tool_and_permission_reject`, `test_slow_serve_gets_status_and_no_status_on_fast`, пороги `≤1.0` и `<2.0`.
> - Правило: testing.md («тест должен воспроизводить баг»).
> - Evidence: тавтология; тест для «lease_dir» проверяет только rc≠0 при 5 аргументах; в native-тесте не проверяется, что reject отправлен; в «fast» части нет утверждения; RED в 16 тестах из-за `AttributeError`, а не поведения; Coder сам видел 1.04 с против 1.0.
> - Fix: реальные утверждения, `FakeClock` или запас по порогам.
> - Проверка: тесты красные на мутациях.

### F-064
- origin: visionary · R1 · visionary-14
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(non-blocking) | D1 skeptic=AGREE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-003 ; realist d1 «DISPUTE F-064 — класс: duplicate_of:F-039 — контр-evidence: `server.py:2489`, `2593`, `2606` — безопасное владение lease-каталогом и проверка доверия к lease уже входят в исправление F-039. Это » → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-14 [non-blocking] Lease-каталог в `/tmp` без владельца и режима
> - Locations: server.py:~2360-3114 (`LEASE_DIR`, `_spawn_serve`, `_startup_reaper`).
> - Правило: `security.md` §9 (predictable path), `error-handling`.
> - Evidence: `mkdir(parents=True, exist_ok=True)` с umask по умолчанию, reaper не проверяет `owner_uid` и ориентируется на подстроку `--serve-helper`.
> - Fix: каталог 0700 под `~/.dsh/…` или `os.mkdir` с проверкой владельца, проверка `owner_uid` и `parent_start_ts`.
> - Проверка: тест reaper на чужой lease.

### F-065
- origin: visionary · R1 · visionary-15
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(non-blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-011 ; skeptic d1 «DISPUTE F-065 — класс: duplicate_of:F-011 — контр-evidence: server.py:1791 `or len(head) == 4`. `SERVE_TEST_ELIGIBLE` по умолчанию `False` и не является env kill-switch; отдельного прод-дефекта » → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-065 — класс: duplicate_of:F-049 — контр-evidence: `server.py:1777`, `1779`, `1791` — несостоятельная проверка формата бинарника уже покрыта F-049. Сам по себе внутренний тестовый флаг » → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-15 [non-blocking] Тестовый хук и вакуумная проверка нативного бинаря
> - Locations: server.py:~1560-1700 (`SERVE_TEST_ELIGIBLE`, `_is_native_opencode_bin`: `or len(head) == 4`).
> - Evidence: условие истинно для любого файла ≥4 байт без `#!`; тестовый флаг в продакшн-модуле.
> - Fix: проверка реального формата Mach-O/ELF, подмена бинаря в тестах через патч.
> - Проверка: текстовый файл без shebang не считается нативным.

### F-066
- origin: visionary · R1 · visionary-16
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR(non-blocking) | D1 skeptic=AGREE | D1 realist=AMEND | D1 visionary=AUTHOR
- dissent: realist d1 «AMEND F-066 — priority=non-blocking; locations=server.py:2204,server.py:2231,server.py:2338,server.py:4427,server.py:4696,tests/test_step_interruption.py:67; fix=По возможности сократить чисто» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: — priority=non-blocking; locations=server.py:2204,server.py:2231,server.py:2338,server.py:4427,server.py:4696,tests/test_step_interruption.py:67; fix=По возможности сократить чисто форматирующие hunks без затрагивания за (teamlead/cycle-1/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-16 [non-blocking] Косметический реформат чужих областей
> - Locations: server.py: `_UpstreamBreaker` (~2204), `_RequestAttempts` (~2230-2291), `_PrefixDedup`, `Run.execute/_execute_once` (4427-4530), `Handler._res`, `_log_exit`; test_step_interruption.py:67 (кавычки `FAKE_OPENCODE`).
> - Правило: AGENTS.md п.4 (минимальные изменения), scope-diff.
> - Evidence: reverse-spec §1 («чисто форматирующие перестановки»).
> - Fix: вынести форматирование в отдельный коммит или откатить hunk'и вне поведения.
> - Проверка: diff без форматирующих hunk'ов в немодифицированных функциях.

### F-067
- origin: visionary · R1 · visionary-17
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR(non-blocking) | D1 skeptic=AGREE | D1 realist=AMEND | D1 visionary=AUTHOR
- dissent: realist d1 «AMEND F-067 — priority=non-blocking; locations=server.py:2708,server.py:4753,server.py:5736; fix=После устранения поведенческих дефектов выделить общие переходы retry/fallback там, где их сема» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: — priority=non-blocking; locations=server.py:2708,server.py:4753,server.py:5736; fix=После устранения поведенческих дефектов выделить общие переходы retry/fallback там, где их семантика действительно совпадает; сохранить (teamlead/cycle-1/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-17 [non-blocking] Размер функций и дубли
> - Locations: `_serve_one_attempt` (~350 строк), `_run_serve_stream_attempts` (~190), `_serve_json_serve` (~210) в server.py (+1900 строк, итог 6287).
> - Правило: python-standards §6/§7, SOLID/SRP.
> - Evidence: вложенные замыкания; одинаковая логика retry, fallback и native-маппинга в stream и JSON.
> - Fix: выделить класс попытки serve и общий retry-цикл.
> - Проверка: функции ≤ ~80 строк, одна реализация retry-логики.

### F-068
- origin: visionary · R1 · visionary-18
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR(non-blocking) | D1 skeptic=AMEND | D1 realist=AMEND | D1 visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-068 — priority=non-blocking; locations=tests/test_step_interruption.py:413, tests/test_step_interruption.py:423; fix=Переименовать тесты `do_not_exhaust`, чтобы имя совпало с потолком » → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «AMEND F-068 — priority=non-blocking; locations=tests/test_step_interruption.py:413,tests/test_step_interruption.py:422,tests/test_step_interruption.py:451; fix=Уточнить названия тестов и явно » → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: skeptic d1: — priority=non-blocking; locations=tests/test_step_interruption.py:413, tests/test_step_interruption.py:423; fix=Переименовать тесты `do_not_exhaust`, чтобы имя совпало с потолком 3. Ожидание «3 запуска, finish stop» не  (teamlead/cycle-1/debate/d1/skeptic.md) ; realist d1: — priority=non-blocking; locations=tests/test_step_interruption.py:413,tests/test_step_interruption.py:422,tests/test_step_interruption.py:451; fix=Уточнить названия тестов и явно связать новые ожидания с REQ-017 и неизм (teamlead/cycle-1/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-18 [non-blocking] Изменённый оракул `test_step_interruption.py`
> - Locations: tests/test_step_interruption.py: `test_unmapped_retries_do_not_exhaust_incomplete_budget_stream/json` (~413-450).
> - Правило: verification-surface (`oracle_change` аудитирует Verifier), REQ-017.
> - Evidence: ожидания «4 запуска, tool_calls» заменены на «3 запуска, `[]`, stop», имена тестов «do_not_exhaust» утверждают обратное, записи аудита `oracle_change` в `verifier.json` нет.
> - Fix: переименовать тесты, задокументировать изменение контракта потолка, зафиксировать аудит.
> - Проверка: запись в `verifier.json`.

### F-069
- origin: visionary · R1 · visionary-19
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR(non-blocking) | D1 skeptic=DISPUTE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: duplicate_of:F-036 ; skeptic d1 «DISPUTE F-069 — класс: duplicate_of:F-036 — контр-evidence: server.py:2859 блокирующий `events.put` и daemon-поток без join в `finally`. Тот же жизненный цикл очереди.» → teamlead/cycle-1/debate/d1/skeptic.md ; realist d1 «DISPUTE F-069 — класс: duplicate_of:F-036 — контр-evidence: `server.py:2859`, `2863`, `2865` — блокировка reader на заполненной очереди и отсутствие гарантированного завершения читателя уже покр» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-19 [non-blocking] Жизненный цикл потоков и очереди
> - Locations: server.py:~2360-3114 (`_reader` с блокирующим `events.put`, `_prompt_worker` timeout 65 с, `threading.Thread(daemon=True)` без join).
> - Правило: T-LIFE/v1, C-MULT-I2.
> - Evidence: при заполненной очереди 4096 читатель блокируется навсегда, при раннем выходе потоки не завершаются, пока не закроются сокеты.
> - Fix: `put` с таймаутом и сигналом остановки, join или cancel потоков в `finally`.
> - Проверка: тест утечки потоков после 50 запросов.

### F-070
- origin: visionary · R1 · visionary-20
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR(non-blocking) | D1 skeptic=AGREE | D1 realist=DISPUTE | D1 visionary=AUTHOR
- dissent: realist d1 «DISPUTE F-070 — класс: invalid — контр-evidence: REQ-007 определяет первый токен как reasoning или text; `server.py:3016`, `3027`, `3040` различает эти события и native lifecycle. Наличие долгой» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-20 [non-blocking] [sweep] Watchdog считает только reasoning/text/завершённый tool
> - Locations: server.py:~2360-3114 (`_serve_one_attempt`, `last_token_at`, `first_token_at`).
> - Evidence: `session.tool.input.delta` и `reasoning.started` не обновляют `last_token_at`; при длинной генерации аргументов инструмента срабатывает `stall_timeout` через 60 с.
> - Fix: считать tool-input дельты признаком живости.
> - Проверка: фикстура с долгим tool-input без text не даёт ложный stall.

### F-071
- origin: visionary · R1 · visionary-21
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR(blocking) | D1 skeptic=AGREE | D1 realist=AMEND | D1 visionary=AUTHOR
- dissent: realist d1 «AMEND F-071 — priority=blocking; locations=tests/test_step_interruption.py:191,tests/test_step_interruption.py:192,tests/test_step_interruption.py:193,tests/test_step_interruption.py:194,tests» → teamlead/cycle-1/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: — priority=blocking; locations=tests/test_step_interruption.py:191,tests/test_step_interruption.py:192,tests/test_step_interruption.py:193,tests/test_step_interruption.py:194,tests/test_step_interruption.py:195,tests/tes (teamlead/cycle-1/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-21 [blocking] [pre-existing] Прямая мутация `os.environ` в изменённом тестовом файле
> - Locations: tests/test_step_interruption.py:~188-192 (`setUp`: `os.environ["FAKE_OC_COUNTER"] = …`, `FAKE_OC_PLAN`).
> - Правило: testing.md («запрет мутации `os.environ` без изоляции»); файл изменён задачей, значит blocking по §3 Diff-scope.
> - Evidence: записи без `monkeypatch` и гарантированного отката.
> - Fix: `mock.patch.dict` или `monkeypatch`.
> - Проверка: порядок запуска не влияет на результат (AC-023 reversed).

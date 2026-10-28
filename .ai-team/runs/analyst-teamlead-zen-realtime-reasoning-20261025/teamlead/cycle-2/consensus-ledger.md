# Консенсус-леджер Совета Тимлидов по коду (`consensus-ledger.md` / `findings-ledger.md`) — Cycle 2, run `analyst-teamlead-zen-realtime-reasoning-20261025`

- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80`)
- **Раунд R1 (`panel/council/r9`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r9/panel-proof.json sha256=d32aa979f463ccf426303988ed8f334839af341565d32da91a7a1419182ca518 verify_panel_proof exit=0`
- **Раунд D1 (`panel/council/r13`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r13/panel-proof.json sha256=fef29bcbc7ce6cfcc16e57574f2405dd50d5af81151d55a5fed3e6a10c98af0e verify_panel_proof exit=0`
- **Всего находок R1:** `50` (`F-001` .. `F-050`), новых находок в D1 (`r2_late`): `0`.
- **Итог дебатов D1:** `AGREED blocking` = `19` (`RW-001..RW-019`), `AGREED non-blocking` = `9` (`FU-001..FU-009`), `REJECTED_BY_MAJORITY excluded` = `22` (`20` межсудейских дублей `duplicate_of` + `2` отклонённых `out_of_scope`/`invalid_after_recheck`). Открытых `OPEN` или `CONFLICT` нет (`0`).

## Сводная таблица статусов (`F-001` .. `F-050`)

| ID | skeptic | realist | visionary | priority | status |
|---|---|---|---|---|---|
| F-001 | AUTHOR | DISPUTE | AMEND | blocking | AGREED |
| F-002 | AUTHOR | DISPUTE | AMEND | blocking | AGREED |
| F-003 | AUTHOR | DISPUTE | AGREE | blocking | AGREED |
| F-004 | AUTHOR | DISPUTE | AMEND | non-blocking | AGREED |
| F-005 | AUTHOR | DISPUTE | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-006 | AUTHOR | DISPUTE | AGREE | blocking | AGREED |
| F-007 | AUTHOR | AMEND | AGREE | blocking | AGREED |
| F-008 | AUTHOR | DISPUTE | AGREE | blocking | AGREED |
| F-009 | AUTHOR | DISPUTE | AGREE | blocking | AGREED |
| F-010 | AUTHOR | AGREE | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-011 | AUTHOR | DISPUTE | AGREE | non-blocking | AGREED |
| F-012 | AUTHOR | DISPUTE | AGREE | non-blocking | AGREED |
| F-013 | AUTHOR | AMEND | AGREE | non-blocking | AGREED |
| F-014 | AGREE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-015 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-016 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-017 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-018 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-019 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-020 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-021 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-022 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-023 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-024 | AGREE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-025 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-026 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-027 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-028 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-029 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-030 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-031 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-032 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-033 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-034 | AMEND | AUTHOR | AMEND | non-blocking | AGREED |
| F-035 | AGREE | AUTHOR | AMEND | blocking | AGREED |
| F-036 | AGREE | AUTHOR | AGREE | non-blocking | AGREED |
| F-037 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-038 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-039 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-040 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-041 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-042 | DISPUTE | DISPUTE | AMEND | excluded | REJECTED_BY_MAJORITY |
| F-043 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-044 | AGREE | AMEND | AUTHOR | non-blocking | AGREED |
| F-045 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-046 | AMEND | AMEND | AUTHOR | non-blocking | AGREED |
| F-047 | AGREE | AMEND | AUTHOR | non-blocking | AGREED |
| F-048 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-049 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-050 | AMEND | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |

---

## Карточки находок (`F-001` .. `F-050`)

### F-001
- origin: skeptic · R1 · skeptic-01
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=AMEND
- dissent: realist d1 «DISPUTE F-001 класс: duplicate_of:F-030 — контр-evidence: `bridges/opencode-zen-bridge/server.py:98`, `:99`, `:239`, `:244` — подтверждаю дефект: ранний helper обращается к `errno`, импортируемо» → teamlead/cycle-2/debate/d1/realist.md ; visionary d1 «AMEND F-001 priority=non-blocking; locations=server.py:98-99,239-244; fix=перенести `import errno` в начало модуля — причина: дефект возник в дельте цикла 2, а не остался от RW. Путь достижим » → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:98-99,239-244; fix=перенести `import errno` в начало модуля — причина: дефект возник в дельте цикла 2, а не остался от RW. Путь достижим только при EBADF: EINTR Python повторяет (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> F-1
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:98, bridges/opencode-zen-bridge/server.py:99, bridges/opencode-zen-bridge/server.py:239, bridges/opencode-zen-bridge/server.py:244
> rule: python-standards.md §3 (fail-fast, имя должно быть связано); дефект дельты цикла 1→2 (ветка EAGAIN)
> evidence: «if isinstance(_gone_exc, OSError) and _gone_exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK)» при том, что `import errno` стоит в `else` после `if sys.argv[1:2] == ["--serve-helper"]: raise SystemExit(...)`. `BlockingIOError` перехватывается раньше и до `errno` не доходит. Любой другой `OSError` (EBADF, EINTR) в процессе helper даёт `NameError`. Первый `_fd_ready()` выполняется до `try/finally` с `killpg`, lease фазы `starting` остаётся.
> expected: `import errno` рядом с `select` до определения `_run_serve_helper_cli`.
> verify: helper, у которого `select` на fd 0 бросает `OSError` с `EBADF` или `EINTR`, завершается без `NameError` и снимает lease.

### F-002
- origin: skeptic · R1 · skeptic-02
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=AMEND
- dissent: realist d1 «DISPUTE F-002 класс: duplicate_of:F-014 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3254`, `:5150`, `:5237`, `:6247`, `:6307` — возвращённый `timeout` действительно проходит мимо об» → teamlead/cycle-2/debate/d1/realist.md ; visionary d1 «AMEND F-002 priority=blocking; locations=server.py:3254,5150,5237-5238,6247,6307-6308; fix=обработать `exit_reason=="timeout"` и `"client_gone"` в обоих потребителях до ветки успеха: без `reco» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=blocking; locations=server.py:3254,5150,5237-5238,6247,6307-6308; fix=обработать `exit_reason=="timeout"` и `"client_gone"` в обоих потребителях до ветки успеха: без `record_success`, без `attempt_done(False,Tru (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> F-2
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3254, bridges/opencode-zen-bridge/server.py:5150, bridges/opencode-zen-bridge/server.py:5237, bridges/opencode-zen-bridge/server.py:5238, bridges/opencode-zen-bridge/server.py:6247, bridges/opencode-zen-bridge/server.py:6307, bridges/opencode-zen-bridge/server.py:6308
> rule: RW-008, REQ-006, REQ-009, R-BULK-I1
> evidence: «result["exit_reason"] = "timeout"» после цикла без `terminal`. Кортежи содержат только `first_event_timeout`, `first_token_timeout`, `stall_timeout`, `invalid_serve_event`. Дальше «res.serve_health.record_success()» и «attempts.attempt_done(False, True)», затем успешный `[DONE]` / JSON 200.
> expected: ветка `timeout` идёт в retry или ошибку, без `record_success` и без успешного finish.
> verify: укороченный `attempts.deadline` без terminal-события даёт `exit_reason=timeout`, счётчик `serve_health` не сбрасывается, клиент не получает `finish_reason=stop`.

### F-003
- origin: skeptic · R1 · skeptic-03
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=AGREE
- dissent: realist d1 «DISPUTE F-003 класс: duplicate_of:F-016 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3022`, `:3053`, `:3055`, `:3061` — HTTP-результат prompt проверяется после `events.get()`, а `que» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-3
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3022, bridges/opencode-zen-bridge/server.py:3027, bridges/opencode-zen-bridge/server.py:3054, bridges/opencode-zen-bridge/server.py:3055, bridges/opencode-zen-bridge/server.py:3056, bridges/opencode-zen-bridge/server.py:3061
> rule: RW-015, FALLBACK_DECISION_TABLE (HTTP401/403 → fail_closed)
> evidence: при пустой очереди «except queue.Empty: continue» происходит до чтения `prompt_status`. При тишине «result["exit_reason"] = "first_event_timeout"» и `return` выполняются до «if _ps in (401, 403): raise ServeSecurityError». `headers_at` пишется только после чтения тела ответа. Создание сессии с 400 по-прежнему fail-closed и тестом закрыто; дыра только у статуса prompt.
> expected: разбирать `prompt_status` в начале итерации, до watchdog-return; 401/403 всегда `ServeSecurityError`, без инкремента `serve_health` и без fallback.
> verify: FakeServe отвечает 401 на prompt при молчащем SSE → security failure сразу, `failures` health не растёт, auto не уходит в `run`.

### F-004
- origin: skeptic · R1 · skeptic-04
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=AMEND
- dissent: realist d1 «DISPUTE F-004 класс: invalid — контр-evidence: `bridges/opencode-zen-bridge/server.py:6359`, `:6371`, `:6378` — перед веткой unmapped-retry стоит `if not emulate_tools or tool_calls_all: break`.» → teamlead/cycle-2/debate/d1/realist.md ; visionary d1 «AMEND F-004 priority=non-blocking; locations=server.py:6370-6378; fix=удалить мёртвую переменную `_seen_tc` вместе с вводящим в заблуждение комментарием — причина: все `continue` после extend » → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:6370-6378; fix=удалить мёртвую переменную `_seen_tc` вместе с вводящим в заблуждение комментарием — причина: все `continue` после extend стоят после `if not emulate_tools or too (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> F-4
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:6370, bridges/opencode-zen-bridge/server.py:6371, bridges/opencode-zen-bridge/server.py:6378
> rule: RW-018, AC-014
> evidence: «_seen_tc = {str(tc.get("id")) for tc in tool_calls_all}» нигде не читается; следом `continue` оставляет уже добавленные вызовы в `tool_calls_all`. Поток SSE для текста использует `_PrefixDedup`; reasoning по AC-014 дедуплицировать не нужно.
> expected: перед retry очищать или дедуплицировать `tool_calls_all` и content неуспешной попытки.
> verify: JSON-сценарий unmapped-then-success возвращает каждый tool_call один раз.

### F-005
- origin: skeptic · R1 · skeptic-05
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=DISPUTE
- dissent: realist d1 «DISPUTE F-005 класс: duplicate_of:F-023 — контр-evidence: `bridges/opencode-zen-bridge/server.py:6203`, `:6231`, `:6239`, `:6243` — JSON освобождает startup gate на отдельных исключениях, но не » → teamlead/cycle-2/debate/d1/realist.md ; visionary d1 «DISPUTE F-005 класс: duplicate_of:F-023 — контр-evidence: server.py:6203,6243 входит в более широкую F-023: тот же `_StartupGate` держится дольше фазы старта в SSE, а в JSON его release отсутств» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-5
> priority: blocking
> criterion: РЕАЛИЗУЕМОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:6203, bridges/opencode-zen-bridge/server.py:6207, bridges/opencode-zen-bridge/server.py:6231, bridges/opencode-zen-bridge/server.py:6239, bridges/opencode-zen-bridge/server.py:6307
> rule: RW-001, REQ-013, S-HERD-I1, T-LIFE/v1
> evidence: «_gate_j.acquire()». `release()` есть на отказе limiter, `ServeUnavailable` и `ServeSecurityError`. После обычного возврата `_serve_one_attempt` до `record_success()` release нет. Stream отпускает gate на `server.py:5136`.
> expected: `try/finally: _gate_j.release()` на всех выходах JSON-попытки, включая `continue`.
> verify: два последовательных JSON-serve не ждут `STARTUP_GATE_S`.

### F-006
- origin: skeptic · R1 · skeptic-06
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=AGREE
- dissent: realist d1 «DISPUTE F-006 класс: duplicate_of:F-022 — контр-evidence: `bridges/opencode-zen-bridge/server.py:1718`, `:2493`, `:2502`, `:2505`, `:2531`, `:2599` — state-dir, резерв порта и pipe создаются до » → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-6
> priority: blocking
> criterion: РЕАЛИЗУЕМОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:1718, bridges/opencode-zen-bridge/server.py:2493, bridges/opencode-zen-bridge/server.py:2500, bridges/opencode-zen-bridge/server.py:2502, bridges/opencode-zen-bridge/server.py:2505, bridges/opencode-zen-bridge/server.py:2526, bridges/opencode-zen-bridge/server.py:2531, bridges/opencode-zen-bridge/server.py:2599
> rule: RW-019, REQ-008, AC-011, feature.md (таймаут и cleanup в finally на каждом шаге I/O)
> evidence: «state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")» выполняется до spawn. Порт кладётся в `_ACTIVE_SERVE_PORTS`, затем «lifeline_r, lifeline_w = os.pipe()» и `Popen`. `finally` закрывает только `lifeline_r`. Lease строится после успешного `Popen`. «except BaseException» вызывает `lease.cleanup()` только если lease уже есть. «raise ServeUnavailable("no free serve port")» тоже после `mkdtemp`.
> expected: один `try/finally` от каталога состояния и pipe: закрыть оба fd, снять порт, удалить каталог, cleanup lease если он создан.
> verify: `Popen`, бросающий `OSError`, не оставляет запись порта, каталог `zen-serve-state-*` и открытый `lifeline_w`.

### F-007
- origin: skeptic · R1 · skeptic-07
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE
- dissent: realist d1 «AMEND F-007 priority=blocking; locations=bridges/opencode-zen-bridge/server.py:197,bridges/opencode-zen-bridge/server.py:231,bridges/opencode-zen-bridge/server.py:232; fix=проверять и завершат» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=blocking; locations=bridges/opencode-zen-bridge/server.py:197,bridges/opencode-zen-bridge/server.py:231,bridges/opencode-zen-bridge/server.py:232; fix=проверять и завершать остальных членов собственной группы не (teamlead/cycle-2/debate/d1/realist.md)
- text (дословно, R1 skeptic):
> F-7
> priority: blocking
> criterion: РЕАЛИЗУЕМОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:231, bridges/opencode-zen-bridge/server.py:232, bridges/opencode-zen-bridge/server.py:233
> rule: RW-023, REQ-008, AC-011, T-LIFE/v1
> evidence: «if serve_proc.poll() is not None: lease_path.unlink()». Комментарий finally требует снимать lease после смерти группы; условие смотрит только на прямой дочерний `serve`. Внук, оставшийся в группе, теряет lease, и reaper его не находит.
> expected: `unlink` только когда `not _pid_alive(-os.getpgrp())` и `serve_proc` завершён.
> verify: живой внук в той же группе оставляет lease-файл на диске.

### F-008
- origin: skeptic · R1 · skeptic-08
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=AGREE
- dissent: realist d1 «DISPUTE F-008 класс: duplicate_of:F-026 — контр-evidence: `bridges/opencode-zen-bridge/server.py:4938`, `:4954`, `:4955`, `:6224` — передача checker в JSON добавлена, но RST по-прежнему попадает» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-8
> priority: blocking
> criterion: РИСКИ
> locations: bridges/opencode-zen-bridge/server.py:4954, bridges/opencode-zen-bridge/server.py:4955, bridges/opencode-zen-bridge/server.py:6224
> rule: RW-024, REQ-008, AC-011, AC-012
> evidence: «except (OSError, ValueError): return False». JSON передаёт `is_client_gone=self._client_gone_check`, но обрыв сокета (EBADF/RST) читается как «клиент на месте». Половина RW-024 (прокидка в JSON) сделана.
> expected: `return True`, если это не `BlockingIOError` и не `EAGAIN`/`EWOULDBLOCK`.
> verify: закрытый клиентский сокет в stream и JSON даёт `client_gone` и `lease.cleanup()` не позже 7 с.

### F-009
- origin: skeptic · R1 · skeptic-09
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=AGREE
- dissent: realist d1 «DISPUTE F-009 класс: duplicate_of:F-032 — контр-evidence: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:112`, `:115`, `:502`, `:591`, `:640`, `:830`, `:871`, `:881` — подтверждаю» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-9
> priority: blocking
> criterion: ПОЛНОТА
> locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:112, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:115, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:491, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:502, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:588, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:591, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:640, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:829, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:830, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:863, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:871, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:873, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:881
> rule: RW-025, REQ-020, AC-001, AC-002, AC-008, AC-009, AC-010, AC-016, AC-018, AC-020, testing.md (зелёный прогон ≠ полнота)
> evidence: маркеры `__never_event__` и `__silent__` живут только внутри строки FakeServe, вызовов нет. «self.assertLess(model_reasoning[-1][0] - model_reasoning[0][0], 2.0)» не проверяет соседний интервал и накладные расходы. `test_serve_health_and_fallback_table` сверяет строки таблицы. `test_native_tool_and_permission_reject` делает «self.assertIn("bash", _tool_names(chunks))». Docstring `test_transport_matrix` обещает disable-файл, код его не создаёт. «self.assertTrue(callable(server._next_standalone_proxy))». `test_elf_magic_and_tool_status` заканчивается «self.assertIsInstance(part_obj, dict)». Нет теста JSON-serve, client_gone, отсутствия пароля в логе и step-interruption на serve. L2 зелёный, потому что написанные тесты проходят, а не потому что оракулы RW-025 существуют.
> expected: по одному нетавтологическому тесту на каждый перечисленный AC.
> verify: каждый новый тест красный на `origin/dev` и зелёный на кандидате; prompt 401 не увеличивает `serve_health.failures`.

### F-010
- origin: skeptic · R1 · skeptic-10
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=DISPUTE
- dissent: visionary d1 «DISPUTE F-010 класс: out_of_scope — контр-evidence: `tests/test_cli_failure.py:267` не входит в `allowed_envelope_changes` и не затронут дельтой. Это [pre-existing] вне скоупа задачи (`scope-and» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-10
> priority: non-blocking
> criterion: РИСКИ
> tag: [pre-existing]
> locations: bridges/opencode-zen-bridge/tests/test_cli_failure.py:267
> rule: testing.md (ResourceWarning при выходе процесса); файл вне `allowed_envelope_changes`
> evidence: VER-002 stderr: «ResourceWarning: unclosed file <_io.TextIOWrapper name=9 ...>» и та же строка для fd 7, обе указывают на `tests/test_cli_failure.py:267`. Прогон rc=0, потому что discover шёл без `-W error`. Подмножество кодера с `-W error::ResourceWarning` этого файла не включало.
> expected: follow-up отдельной задачей: закрыть pipe в тесте. В этот diff файл не входит.
> verify: полный `unittest discover` с `-W error::ResourceWarning` без предупреждения на этой строке.

### F-011
- origin: skeptic · R1 · skeptic-11
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=AGREE
- dissent: realist d1 «DISPUTE F-011 класс: duplicate_of:F-033 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5166`, `:6260`, `:6271`, `:6281` — JSON retry-ветки пропускают накопление usage, SSE делает это л» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-11
> priority: non-blocking
> criterion: ПОЛНОТА
> locations: bridges/opencode-zen-bridge/server.py:6260, bridges/opencode-zen-bridge/server.py:6261, bridges/opencode-zen-bridge/server.py:6271, bridges/opencode-zen-bridge/server.py:6272, bridges/opencode-zen-bridge/server.py:6281, bridges/opencode-zen-bridge/server.py:6282, bridges/opencode-zen-bridge/server.py:5166
> rule: FU-004, REQ-014 (SHOULD)
> evidence: JSON-ветки `allow_retry` делают `continue` без суммирования `result["usage"]`. Stream перед таким `continue` копит `input/output/cached/reasoning` в `_serve_stream_usage` (`server.py:5166-5170`).
> expected: тот же аккумулятор перед каждым JSON `continue` на timeout, invalid event и transient retry.
> verify: две попытки JSON, первая с ненулевым usage и timeout, вторая успешная — финальный `usage` содержит сумму обеих.

### F-012
- origin: skeptic · R1 · skeptic-12
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=AGREE
- dissent: realist d1 «DISPUTE F-012 класс: duplicate_of:F-029 — контр-evidence: `bridges/opencode-zen-bridge/server.py:75`, `:2644`, `:2645`, `:2660` — epoch-значение helper действительно исключено из сравнения с `ps» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-12
> priority: non-blocking
> criterion: РИСКИ
> locations: bridges/opencode-zen-bridge/server.py:75, bridges/opencode-zen-bridge/server.py:2630, bridges/opencode-zen-bridge/server.py:2644, bridges/opencode-zen-bridge/server.py:2645, bridges/opencode-zen-bridge/server.py:2646
> rule: остаток RW-003 (сверка helper PID с живым `ps lstart`)
> evidence: lease пишет «"helper_lstart": str(int(time.time()))». Reaper: «if _live and not _ts_v.isdecimal() and _live != _ts_v». Десятичная epoch-строка пропускает сравнение с `ps -o lstart=`. Комментарий на :2644 это фиксирует. Сверка `parent_start_ts` для lstart-формата работает.
> expected: писать `helper_lstart` тем же форматом, что `ps lstart`, и сравнивать его.
> verify: lease с живым PID другого процесса и тем же номером не получает `killpg`.

### F-013
- origin: skeptic · R1 · skeptic-13
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE
- dissent: realist d1 «AMEND F-013 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3215,bridges/opencode-zen-bridge/server.py:3216; fix=согласовать определение первого токена для native tool c» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3215,bridges/opencode-zen-bridge/server.py:3216; fix=согласовать определение первого токена для native tool completion и применять его одинаково к wa (teamlead/cycle-2/debate/d1/realist.md)
- text (дословно, R1 skeptic):
> F-13
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3215, bridges/opencode-zen-bridge/server.py:3216, bridges/opencode-zen-bridge/server.py:3181, bridges/opencode-zen-bridge/server.py:3192
> rule: AC-021 (поле `ttft_ms` есть; семантика «первый токен» для tool-only не заполняется)
> evidence: при `tool_event` «if result["first_token_at"] is None: result["first_token_at"] = time.monotonic()» без присвоения `ttft_ms`. Reasoning и text пишут `ttft_ms` на :3181 и :3192. VER-002: `transport=serve ... tools=1 ... ttft_ms=None`.
> expected: при первом native tool completion выставлять `ttft_ms` так же, как для reasoning/text.
> verify: tool-only ответ в `O-EXIT/v1` имеет целое `ttft_ms`.

### F-014
- origin: realist · R1 · realist-01
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=DISPUTE
- dissent: visionary d1 «DISPUTE F-014 класс: duplicate_of:F-002 — контр-evidence: те же места 3252/5151/6249; `client_gone` в JSON учтён в AMEND F-002 — это один корень, один фикс.» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-001 — priority=blocking — незавершённая попытка может считаться успешной.**  
> locations: `bridges/opencode-zen-bridge/server.py:3252`, `bridges/opencode-zen-bridge/server.py:5151`, `bridges/opencode-zen-bridge/server.py:6249`.  
> Правило: RW-008, RW-024, `R-BULK-I1`, `O-EXIT/v1`. Evidence: producer возвращает `exit_reason="timeout"`, но оба consumer проверяют ограниченный список без `timeout`; JSON также не обрабатывает `client_gone`. Затем достижимы `record_success()` и успешный ответ с частичными данными.  
> Исправление: обработать все неуспешные исходы до success-ветки; ограничить setup I/O остатком общего deadline. Проверка: истёкший deadline и JSON disconnect никогда не вызывают success, HTTP 200 или успешный SSE finish.

### F-015
- origin: realist · R1 · realist-02
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
> **F-002 — priority=blocking — SSE не восстанавливается после socket timeout.**  
> locations: `bridges/opencode-zen-bridge/server.py:2941`, `bridges/opencode-zen-bridge/server.py:2955`.  
> Правило: RW-009, REQ-007, AC-009/010. Evidence: после timeout на `sse_resp.readline()` выполняется `continue`. У буферизованного SocketIO timeout оставляет состояние, при котором дальнейшее чтение вызывает `OSError: cannot read from timed out object`; этот OSError снова проглатывается. Возможен быстрый цикл ошибок до watchdog.  
> Исправление: использовать чтение, допускающее возобновление после ожидания готовности, без poisoning буферизованного response. Проверка: пауза более 5 секунд, но меньше watchdog, затем новые дельты доставляются в той же попытке.

### F-016
- origin: realist · R1 · realist-03
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=DISPUTE
- dissent: skeptic d1 «DISPUTE F-016 класс: duplicate_of:F-003 — контр-evidence: bridges/opencode-zen-bridge/server.py:3053, bridges/opencode-zen-bridge/server.py:3022 — `queue.Empty: continue` до `prompt_status` и ра» → teamlead/cycle-2/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-016 класс: duplicate_of:F-003 — контр-evidence: server.py:3053-3057 — та же проверка `prompt_status` после `events.get`.» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-003 — priority=blocking — HTTP-ошибка prompt зависит от наличия SSE-события.**  
> locations: `bridges/opencode-zen-bridge/server.py:3053`, `bridges/opencode-zen-bridge/server.py:3057`.  
> Правило: RW-015, обработка ошибок независимо от канала данных. Evidence: `queue.Empty` делает `continue` до проверки `prompt_status`. Если prompt уже вернул 401/429/5xx, а SSE молчит, ошибка может быть перекрыта watchdog.  
> Исправление: проверять результат prompt на каждой итерации до ожидания очереди. Проверка: каждый предусмотренный HTTP-status классифицируется при пустой SSE-очереди.

### F-017
- origin: realist · R1 · realist-04
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AMEND
- dissent: visionary d1 «AMEND F-017 priority=non-blocking; locations=server.py:2385,2997,3063,5208,6280; fix=выставлять `headers_at` по `getresponse()`, а не после `read()`, и считать `delivered` по latch «ответ на p» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:2385,2997,3063,5208,6280; fix=выставлять `headers_at` по `getresponse()`, а не после `read()`, и считать `delivered` по latch «ответ на prompt получен» или «валидное execution-с (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-004 — priority=blocking — барьер доставки не является необратимым.**  
> locations: `bridges/opencode-zen-bridge/server.py:2385`, `bridges/opencode-zen-bridge/server.py:2997`, `bridges/opencode-zen-bridge/server.py:3063`, `bridges/opencode-zen-bridge/server.py:5208`, `bridges/opencode-zen-bridge/server.py:6280`.  
> Правило: `FALLBACK_DECISION_TABLE`, REQ-009, RW-015/016. Evidence: `headers_at` устанавливается после полного `resp.read()`, а не получения заголовков; HTTP-ветка заново вычисляет delivered по накопленному контенту. SSE transient-ветка учитывает text, но игнорирует уже выданный reasoning. Поэтому принятый prompt может перейти в fallback.  
> Исправление: фиксировать согласованный delivery latch при заголовках/валидном execution-событии и никогда не сбрасывать его; отдельно учитывать клиентскую эмиссию. Проверка: headers-only, execution-only и reasoning-only сценарии не допускают запрещённого fallback. Противоречие текста RW-015 и таблицы относительно prompt 400/404/422 следует явно разрешить в конверте, не скрывать кодом.

### F-018
- origin: realist · R1 · realist-05
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
> **F-005 — priority=blocking — общий потолок запусков не защищает JSON fallback.**  
> locations: `bridges/opencode-zen-bridge/server.py:6194`, `bridges/opencode-zen-bridge/server.py:6230`, `bridges/opencode-zen-bridge/server.py:6498`, `bridges/opencode-zen-bridge/server.py:4704`.  
> Правило: RW-013, AC-013, `R-BULK-I2`. Evidence: после двух serve retries третья попытка может вернуть `ServeUnavailable`; auto возвращает `False`, затем JSON-путь запускает `Run` без предварительного `can_spawn()`. Сам `_execute_once()` создаёт процесс до `note_spawn()`.  
> Исправление: единая проверка бюджета непосредственно перед каждым фактическим запуском. Проверка: две retries → третий setup failure → fallback дают максимум три запуска.

### F-019
- origin: realist · R1 · realist-06
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AMEND
- dissent: visionary d1 «AMEND F-019 priority=non-blocking; locations=server.py:3236,5000,5030; fix=по `step.ended` завершать попытку и при `tool_calls`, распарсенных `ToolCallParser`, либо после `terminal` ждать не д» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:3236,5000,5030; fix=по `step.ended` завершать попытку и при `tool_calls`, распарсенных `ToolCallParser`, либо после `terminal` ждать не дольше короткого окна — причина: `finish_ (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-006 — priority=blocking — текстовый tool call не закрывает serve-шаг.**  
> locations: `bridges/opencode-zen-bridge/server.py:3236`, `bridges/opencode-zen-bridge/server.py:5000`, `bridges/opencode-zen-bridge/server.py:5030`.  
> Правило: RW-017, REQ-011. Evidence: parser может уже эмитировать клиенту tool call, но `_serve_one_attempt()` при `step_finish` проверяет только `result["native_calls"]`. Для вызова из `<tool_invoke>` список пуст, чтение следующего шага продолжается.  
> Исправление: передать в транспорт сигнал наличия распарсенного tool call и завершать попытку на соответствующем step boundary. Проверка: text tool call → step_finish → STEP2; STEP2 клиенту не передаётся.

### F-020
- origin: realist · R1 · realist-07
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AMEND
- dissent: visionary d1 «AMEND F-020 priority=non-blocking; locations=server.py:5211,5228,5255,5281; fix=единая эмиссия одного разделителя «Повтор попытки» на все причины повтора; объединить с фиксом F-027 — причина: » → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:5211,5228,5255,5281; fix=единая эмиссия одного разделителя «Повтор попытки» на все причины повтора; объединить с фиксом F-027 — причина: разделитель в веток unmapped/incomplete  (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-007 — priority=blocking — не все повторы reasoning разделены статусом.**  
> locations: `bridges/opencode-zen-bridge/server.py:5211`, `bridges/opencode-zen-bridge/server.py:5228`, `bridges/opencode-zen-bridge/server.py:5255`, `bridges/opencode-zen-bridge/server.py:5281`.  
> Правило: RW-018, AC-014. Evidence: transient recovery, unmapped и обычный incomplete recovery выполняют `continue` без общего разделителя; он добавлен только в отдельных watchdog/HTTP-ветках.  
> Исправление: единая эмиссия ровно одного retry-разделителя перед следующей попыткой после reasoning. Проверка: все причины повторов сохраняют reasoning и дают ровно один разделитель.

### F-021
- origin: realist · R1 · realist-08
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AMEND
- dissent: visionary d1 «AMEND F-021 priority=non-blocking; locations=server.py:6323,6344,6372; fix=дедуплицировать `tool_calls_all` по `_call_key(name, arguments)`, как `emit_tool_call` в SSE-пути — причина: паритет » → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:6323,6344,6372; fix=дедуплицировать `tool_calls_all` по `_call_key(name, arguments)`, как `emit_tool_call` в SSE-пути — причина: паритет с SSE-путём полезен. Но одинаковый вызов (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-008 — priority=blocking — JSON способен вернуть одинаковый инструмент дважды [pre-existing].**  
> locations: `bridges/opencode-zen-bridge/server.py:6323`, `bridges/opencode-zen-bridge/server.py:6344`, `bridges/opencode-zen-bridge/server.py:6372`.  
> Правило: RW-018, parity с существующим `emit_tool_call`. Evidence: parsed calls и mapped native calls независимо добавляются в `tool_calls_all` с разными случайными ID; `_seen_tc` вычисляется, но не используется. Одинаковые name/arguments из двух каналов становятся двумя клиентскими вызовами.  
> Исправление: дедуплицировать по семантическому ключу name/arguments. Проверка: одинаковый вызов в text и native даёт один `tool_call` в JSON.

### F-022
- origin: realist · R1 · realist-09
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=DISPUTE
- dissent: skeptic d1 «DISPUTE F-022 класс: duplicate_of:F-006 — контр-evidence: bridges/opencode-zen-bridge/server.py:1718, bridges/opencode-zen-bridge/server.py:2500, bridges/opencode-zen-bridge/server.py:2505 — `mk» → teamlead/cycle-2/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-022 класс: duplicate_of:F-006 — контр-evidence: server.py:1713,2476-2508 — тот же участок кода и тот же фикс.» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-009 — priority=blocking — ранние ошибки запуска обходят уборку.**  
> locations: `bridges/opencode-zen-bridge/server.py:1713`, `bridges/opencode-zen-bridge/server.py:2476`, `bridges/opencode-zen-bridge/server.py:2505`, `bridges/opencode-zen-bridge/server.py:2508`, `bridges/opencode-zen-bridge/server.py:2835`.  
> Правило: RW-019, `T-LIFE/v1`, `C-MULT-I4`. Evidence: state-dir создаётся до `_spawn_serve`; резервирование порта, `os.pipe()` и helper `Popen()` происходят до общего cleanup-блока. При ошибке `Popen` закрывается только read-end pipe.  
> Исправление: единый exception-safe владелец state-dir, порта, обоих FD и процесса с начала создания ресурсов. Проверка: инъекция отказов mkdir/pipe/Popen/handshake не оставляет FD, портов, каталогов или процессов.

### F-023
- origin: realist · R1 · realist-10
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
> **F-010 — priority=blocking — startup gate удерживается дольше startup-фазы.**  
> locations: `bridges/opencode-zen-bridge/server.py:5092`, `bridges/opencode-zen-bridge/server.py:5136`, `bridges/opencode-zen-bridge/server.py:6203`, `bridges/opencode-zen-bridge/server.py:6243`.  
> Правило: RW-001, `S-HERD-I1`, `C-MULT-I4`. Evidence: SSE освобождает gate после всей `_serve_one_attempt()`, JSON на обычном возврате вообще не вызывает release. Это создаёт ненужные ожидания и переходы в fail-open по таймеру gate.  
> Исправление: освобождать gate после подтверждённого startup/первого события и гарантированно в `finally`. Проверка: длинная генерация первого запроса не удерживает startup gate для второго.

### F-024
- origin: realist · R1 · realist-11
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=DISPUTE
- dissent: visionary d1 «DISPUTE F-024 класс: duplicate_of:F-007 — контр-evidence: server.py:195,232 — тот же корень.» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-011 — priority=blocking — после смерти родителя могут остаться внуки serve.**  
> locations: `bridges/opencode-zen-bridge/server.py:195`, `bridges/opencode-zen-bridge/server.py:232`.  
> Правило: RW-023, REQ-008, `T-LIFE/v1`. Evidence: helper эскалирует только если непосредственный `serve_proc` ещё жив; lease удаляется, если этот процесс завершился. Если serve завершился после TERM, а его потомок TERM игнорирует, эскалация пропускается и lease теряется.  
> Исправление: проверять всех остальных членов собственной группы независимо от состояния прямого потомка; сохранять свидетельство до их завершения. Проверка: смерть родителя + завершившийся serve + TERM-resistant grandchild не оставляют сирот.

### F-025
- origin: realist · R1 · realist-12
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AMEND
- dissent: visionary d1 «AMEND F-025 priority=non-blocking; locations=server.py:2432,2444,2450,2470; fix=разделить бюджет: TERM-окно (например 3 с) и отдельное окно подтверждения после SIGKILL — причина: после полных » → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:2432,2444,2450,2470; fix=разделить бюджет: TERM-окно (например 3 с) и отдельное окно подтверждения после SIGKILL — причина: после полных 5 с TERM-ожидания цикл после SIGKILL не  (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-012 — priority=blocking — бюджет cleanup исчерпан до проверки результата SIGKILL.**  
> locations: `bridges/opencode-zen-bridge/server.py:2432`, `bridges/opencode-zen-bridge/server.py:2444`, `bridges/opencode-zen-bridge/server.py:2450`, `bridges/opencode-zen-bridge/server.py:2470`.  
> Правило: RW-006/010, AC-011. Evidence: TERM-ожидание расходует весь `_deadline`; после SIGKILL повторный цикл использует тот же истёкший deadline. Cleanup может вернуться с живой группой, уже установив `_closed=True`, и удалить state-dir.  
> Исправление: заранее разделить общий бюджет на TERM, KILL и подтверждение; не считать уборку завершённой при живой группе. Проверка: игнорирующая TERM группа подтверждённо отсутствует до возврата в пределах AC-011.

### F-026
- origin: realist · R1 · realist-13
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=DISPUTE
- dissent: skeptic d1 «DISPUTE F-026 класс: duplicate_of:F-008 — контр-evidence: bridges/opencode-zen-bridge/server.py:4954 — `except (OSError, ValueError): return False`; `ConnectionResetError` есть `OSError`. Та же » → teamlead/cycle-2/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-026 класс: duplicate_of:F-008 — контр-evidence: server.py:4938-4955 — тот же чекер и тот же фикс.» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-013 — priority=blocking — RST не считается отключением клиента [pre-existing].**  
> locations: `bridges/opencode-zen-bridge/server.py:4938`, `bridges/opencode-zen-bridge/server.py:4955`.  
> Правило: RW-024, REQ-008. Evidence: `ConnectionResetError` является `OSError`; checker возвращает `False` для всех `OSError/ValueError`. JSON во время генерации ничего не пишет клиенту, поэтому альтернативного быстрого обнаружения нет.  
> Исправление: отличать EAGAIN/EWOULDBLOCK от RST/EBADF и других терминальных ошибок; включить ошибку `os.dup` в эту классификацию. Проверка: FIN и RST в SSE/JSON вызывают `client_gone` и cleanup в заданном бюджете.

### F-027
- origin: realist · R1 · realist-14
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AMEND
- dissent: visionary d1 «AMEND F-027 priority=non-blocking; locations=server.py:3042,5079-5087; fix=один владелец записей статусов, общий флаг «первый статус отправлен», `cancel` таймера в `finally` — причина: `wfile`» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:3042,5079-5087; fix=один владелец записей статусов, общий флаг «первый статус отправлен», `cancel` таймера в `finally` — причина: `wfile` не буферизован (`BaseHTTPRequestHandler (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-014 — priority=blocking — статусный timer не принадлежит жизненному циклу запроса.**  
> locations: `bridges/opencode-zen-bridge/server.py:3042`, `bridges/opencode-zen-bridge/server.py:5079`, `bridges/opencode-zen-bridge/server.py:5087`.  
> Правило: RW-011, `T-LIFE/v1`, целостность SSE. Evidence: отдельный daemon timer пишет непосредственно в `wfile`, не отменяется на terminal/fallback и работает одновременно со статусами основного serve-цикла. Возможны два initial-status и конкурентные записи с модельными чанками.  
> Исправление: один владелец SSE-записей, общее состояние первого статуса, отмена timer при любом завершении. Проверка: ранний tool-only terminal, fallback и модельная дельта около порога не дают поздних/двойных статусов или повреждения кадра.

### F-028
- origin: realist · R1 · realist-15
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
> **F-015 — priority=blocking — legacy не гарантирует первый видимый статус за секунду [pre-existing].**  
> locations: `bridges/opencode-zen-bridge/server.py:5649`, `bridges/opencode-zen-bridge/server.py:5716`, `bridges/opencode-zen-bridge/server.py:5743`.  
> Правило: RW-011, REQ-004, AC-005. Evidence: часы статуса legacy создаются после gate/limiter/spawn; служебный статус отправляется только при чтении feed. Ожидание gate может занять пять секунд до начала этих часов.  
> Исправление: запустить request-level статусный механизм до startup-ожиданий. Проверка: занятый gate и молчащий CLI всё равно дают видимый reasoning/status не позже 1,0 секунды.

### F-029
- origin: realist · R1 · realist-16
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=DISPUTE
- dissent: skeptic d1 «DISPUTE F-029 класс: duplicate_of:F-012 — контр-evidence: bridges/opencode-zen-bridge/server.py:75, bridges/opencode-zen-bridge/server.py:2644 — `helper_lstart` пишется как epoch-секунды, reaper» → teamlead/cycle-2/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-029 класс: duplicate_of:F-012 — контр-evidence: server.py:78,2639-2660 — тот же дефект; блокирующим его делать не нужно.» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-016 — priority=blocking — защита reaper от переиспользования helper PID неполна.**  
> locations: `bridges/opencode-zen-bridge/server.py:78`, `bridges/opencode-zen-bridge/server.py:2639`, `bridges/opencode-zen-bridge/server.py:2660`.  
> Правило: RW-003, ownership lifecycle. Evidence: `helper_lstart` записан epoch-числом, а reaper явно пропускает сравнение decimal timestamps с живым `ps lstart`. Наличие `--serve-helper` в argv не доказывает, что это helper данной попытки.  
> Исправление: сохранять и проверять сопоставимую идентичность процесса/группы до сигналов. Проверка: lease со старым временем и переиспользованным PID другого helper не вызывает сигналов.

### F-030
- origin: realist · R1 · realist-17
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=DISPUTE
- dissent: skeptic d1 «DISPUTE F-030 класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:98, bridges/opencode-zen-bridge/server.py:244 — `errno` читается в helper до импорта в `else` посл» → teamlead/cycle-2/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-030 класс: duplicate_of:F-001 — контр-evidence: server.py:99,240,245 — тот же `errno`, один фикс.» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-017 — priority=blocking — ранняя helper-ветка обращается к неимпортированному errno.**  
> locations: `bridges/opencode-zen-bridge/server.py:99`, `bridges/opencode-zen-bridge/server.py:240`, `bridges/opencode-zen-bridge/server.py:245`.  
> Правило: корректная обработка ошибок, RW-023. Evidence: helper завершается до импорта `errno` из `else`, но `_fd_ready()` использует `errno.EAGAIN/EWOULDBLOCK` при OSError. Эта ветка завершится `NameError`.  
> Исправление: импортировать требуемый stdlib-модуль до helper dispatch. Проверка: OSError на lifeline проверяет нужный исход без NameError.

### F-031
- origin: realist · R1 · realist-18
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
> **F-018 — priority=blocking — transient upstream-события обходят Circuit Breaker.**  
> locations: `bridges/opencode-zen-bridge/server.py:5180`, `bridges/opencode-zen-bridge/server.py:5207`, `bridges/opencode-zen-bridge/server.py:6265`, `bridges/opencode-zen-bridge/server.py:6278`.  
> Правило: RW-015/016, REQ-009, `R-BULK-I3`. Evidence: `attempt_done(True, False)` вызывается для HTTP 429, но отсутствует на ветках transient SSE error и prompt 5xx. Полученные `transient_error=True` и retry сами по себе breaker не обновляют.  
> Исправление: централизовать учёт исхода попытки, ровно один раз увеличивая соответствующий health/breaker. Проверка: серии 429/5xx/transport SSE failures открывают upstream breaker, не повышая serve-health за модельный отказ.

### F-032
- origin: realist · R1 · realist-19
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=DISPUTE
- dissent: skeptic d1 «DISPUTE F-032 класс: duplicate_of:F-009 — контр-evidence: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:112, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:502 — `__» → teamlead/cycle-2/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-032 класс: duplicate_of:F-009 — контр-evidence: tests/test_realtime_reasoning.py:489-873 — отдельно F-032 не нужна.» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-019 — priority=blocking — оракулы не подтверждают заявленную полноту исправлений.**  
> locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:489`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:508`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:587`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:639`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:787`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:830`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:863`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:873`.  
> Правило: RW-025/028, REQ-020, `testing.md` «Зелёный прогон ≠ корректно», §7.2. Evidence: `upstream_end_t = elapsed` означает конец клиентского ответа; даже буферизованный ответ проходит сравнение. Proxy проверяется через `callable`, fallback — чтением декларативной таблицы, foreign-session — маппером. Red AC-026 падает в `setUp` из-за отсутствия `DYNAMIC_CONFIG_PATH`.  
> Исправление: добавить независимый upstream-end/timestamps; проверки интервалов и overhead; три serve-watchdog и legacy first-token/stall; JSON serve/retries; FIN/RST; cleanup/parent death/PID reuse; частичный handshake; конкурентные старты/порты; реальную ротацию; secret-log oracle; disable-file; HTTP-status/health/breaker матрицу; step-interruption на serve; terminal после text tool call; retry-разделители и dedup; сохранение первых метрик. Детерминированные переходы проверять FakeClock.  
> Проверка: каждый указанный дефект воспроизводится своим тестом, а traceability ссылается на конкретное утверждение, не на зелёный модуль целиком.

### F-033
- origin: realist · R1 · realist-20
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=DISPUTE
- dissent: skeptic d1 «DISPUTE F-033 класс: duplicate_of:F-011 — контр-evidence: bridges/opencode-zen-bridge/server.py:6260, bridges/opencode-zen-bridge/server.py:5166 — JSON-`continue` без суммы `usage`, stream копит» → teamlead/cycle-2/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-033 класс: duplicate_of:F-011 — контр-evidence: server.py:5167,6259 — тот же дефект в тех же ветках.» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-020 — priority=non-blocking — usage не всех попыток попадает в итог.**  
> locations: `bridges/opencode-zen-bridge/server.py:5167`, `bridges/opencode-zen-bridge/server.py:5228`, `bridges/opencode-zen-bridge/server.py:6259`, `bridges/opencode-zen-bridge/server.py:6284`.  
> Правило: FU-004, REQ-014 SHOULD. Evidence: SSE суммирует usage на части watchdog-retry, JSON делает `continue` без аккумуляции, transient recovery также пропускает учёт.  
> Исправление: суммировать usage завершённых шагов перед каждым retry. Проверка: две попытки с известными tokens дают их сумму. Сохраняю согласованный non-blocking приоритет.

### F-034
- origin: realist · R1 · realist-21
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AMEND, realist=AUTHOR, visionary=AMEND
- dissent: skeptic d1 «AMEND F-034 priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:773; fix=не блокировать merge переписыванием модуля на pytest; follow-up отдельно, есл» → teamlead/cycle-2/debate/d1/skeptic.md ; visionary d1 «AMEND F-034 priority=non-blocking; locations=tests/test_realtime_reasoning.py:773; fix=при ближайшем касании перевести тесты на pytest-фикстуры, не меняя семантику — причина: все 17 модулей `t» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:773; fix=не блокировать merge переписыванием модуля на pytest; follow-up отдельно, если весь мост уйдёт с unittest — причина:  (teamlead/cycle-2/debate/d1/skeptic.md) ; visionary d1: priority=non-blocking; locations=tests/test_realtime_reasoning.py:773; fix=при ближайшем касании перевести тесты на pytest-фикстуры, не меняя семантику — причина: все 17 модулей `tests/` и соседний `test_step_interruptio (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-021 — priority=blocking — новый тестовый код нарушает явный запрет TestCase.**  
> locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:773`; также классы legacy/serve нового модуля с `setUp/tearDown` — [pre-existing] относительно дельты цикла.  
> Правило: приложенный `agents/testing.md`: «Не использовать unittest.TestCase, setUp, tearDown». Evidence: новый `TestReworkUnits(unittest.TestCase)` продолжает запрещённую структуру; runtime-ограничение stdlib не запрещает pytest из dev-зависимостей.  
> Исправление: новый модуль оформить pytest-тестами и фикстурами; сохранить изоляцию env и ресурсов. Проверка: новый модуль не содержит TestCase/setUp/tearDown, полный pytest остаётся зелёным.

### F-035
- origin: realist · R1 · realist-22
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AMEND
- dissent: visionary d1 «AMEND F-035 priority=non-blocking; locations=server.py:1696,2831,5119,6228; fix=убрать явный `proxy_url=_next_standalone_proxy()` из `_serve_one_attempt` и брать `HTTP_PROXY` из `_run_env` (ег» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:1696,2831,5119,6228; fix=убрать явный `proxy_url=_next_standalone_proxy()` из `_serve_one_attempt` и брать `HTTP_PROXY` из `_run_env` (его результат уже проходит `_serve_env`),  (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 realist):
> **F-022 — priority=blocking — прокси-пул продвигается дважды на одну serve-попытку.**  
> locations: `bridges/opencode-zen-bridge/server.py:1696`, `bridges/opencode-zen-bridge/server.py:2831`, `bridges/opencode-zen-bridge/server.py:5119`, `bridges/opencode-zen-bridge/server.py:6228`.  
> Правило: RW-001, REQ-013, AC-018. Evidence: вызывающий код сначала вычисляет `_next_standalone_proxy()`, затем `_serve_one_attempt()` вызывает `_serve_env()` → замороженный `_run_env()`, который для standalone снова выбирает proxy. После этого второй выбор затирается первым. Для пула `[A,B]` фактически используемый proxy последовательных попыток может быть `[A,A]`.  
> Исправление: оставить ровно одну точку потребления прокси-пула на попытку, не меняя frozen `_run_env`. Проверка: пул из двух записей, две реальные попытки → разные фактически переданные proxy, счётчик выбора равен числу попыток.

### F-036
- origin: realist · R1 · realist-23
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-023 — priority=non-blocking — диагностическая история lsof растёт без ограничения [pre-existing].**  
> locations: `bridges/opencode-zen-bridge/server.py:1433`, `bridges/opencode-zen-bridge/server.py:2347`.  
> Правило: ограниченность runtime-буферов, `HL-ENV-01`. Evidence: каждый lookup добавляет порт в глобальный `_LSOF_CALLS`, очистки или предела нет; polling повторяет добавления.  
> Исправление: убрать production-историю, заменить счётчиком либо ограниченным буфером; тестам использовать внешний spy. Проверка: размер диагностического состояния не растёт с числом запросов.

### F-037
- origin: visionary · R1 · visionary-01
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-037 класс: duplicate_of:F-015 — контр-evidence: bridges/opencode-zen-bridge/server.py:2941, bridges/opencode-zen-bridge/server.py:2959 — тот же `settimeout(0.5)` и `continue` на `Timeo» → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-037 класс: duplicate_of:F-015 — контр-evidence: `bridges/opencode-zen-bridge/server.py:2941`, `:2955` — повторное чтение буферизованного response после socket timeout и проглатывание п» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-01 [blocking, КОРРЕКТНОСТЬ/РЕАЛИЗУЕМОСТЬ]
> - Место: `server.py::_serve_one_attempt._reader`, примерно после выставления `sse_conn.sock.settimeout(0.5)`.
> - Правило: REQ-001, REQ-006, REQ-007, RW-009, RW-020, T-LIFE/v1.
> - Evidence: `except (TimeoutError, OSError): ... continue`. В CPython после первого `socket.timeout` объект `SocketIO` помечается `_timeout_occurred`, и любое следующее чтение бросает `OSError("cannot read from timed out object")`. Читатель уходит в бесконечный холостой цикл на 100% CPU и больше не выдаёт событий; EOF-sentinel `None` не ставится. По `F-19` пауза между `execution.started` (233 мс) и первой дельтой размышления (1811 мс) превышает 0,5 с. Тесты этого не ловят: `test_slow_serve_gets_status_and_no_status_on_fast` проверяет только наличие статуса, а `test_ac026` использует интервалы 0,12 с. Утверждение основано на моём знании реализации CPython и не подтверждено запуском.
> - Исправление:
>   - не использовать короткий таймаут чтения на сокете, у которого после этого продолжается `readline`;
>   - читать блокирующе, а завершение инициировать закрытием сокета из основного потока;
>   - при любой иной фатальной `OSError` ставить `None` и выходить;
>   - не допускать цикла без ожидания.
> - Критерий: новый тест с FakeServe, у которого между `server.connected` и первой дельтой пауза 1,5 с, получает все дельты. Второй тест роняет сокет сервера и обнаруживает EOF не позже чем через 1 с.

### F-038
- origin: visionary · R1 · visionary-02
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-038 класс: duplicate_of:F-014 — контр-evidence: bridges/opencode-zen-bridge/server.py:3254, bridges/opencode-zen-bridge/server.py:6307 — `timeout` и JSON-`client_gone` падают в `record» → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-038 класс: duplicate_of:F-014 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3254`, `:5150`, `:6247`, `:6307` — общий timeout и JSON `client_gone` действительно не отделены о» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-02 [blocking, КОРРЕКТНОСТЬ/ПОЛНОТА]
> - Место: `server.py::Handler._run_serve_stream_attempts` и `_serve_json_serve`, ветки после `_serve_one_attempt`.
> - Правило: REQ-006, REQ-009, RW-008.
> - Evidence: `_serve_one_attempt` возвращает `exit_reason="timeout"` и `"client_gone"` без `terminal`. Вызывающий код обрабатывает только `first_event_timeout`, `first_token_timeout`, `stall_timeout`, `invalid_serve_event`, статусы `prompt` и `client_gone` в потоковом пути. Результат `timeout` проваливается в `res.serve_health.record_success()`, `attempts.attempt_done(False, True)` и `finish_reason=stop` с `[DONE]`. В JSON-пути `client_gone` тоже падает в этот успех.
> - Исправление: явно обработать `timeout` (ошибка клиенту, `exit_reason=timeout`, без `record_success`) и `client_gone` в JSON-пути.
> - Критерий: тест с дедлайном 1 с и молчащим serve даёт `exit_reason=timeout` и не вызывает `record_success`.

### F-039
- origin: visionary · R1 · visionary-03
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-039 класс: duplicate_of:F-006 — контр-evidence: bridges/opencode-zen-bridge/server.py:2505, bridges/opencode-zen-bridge/server.py:2599 — `Popen` до lease и cleanup только после создани» → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-039 класс: duplicate_of:F-022 — контр-evidence: `bridges/opencode-zen-bridge/server.py:1718`, `:2505`, `:2526`, `:2531`, `:2835` — ранний spawn расположен вне общего cleanup; его `OSEr» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-03 [blocking, РЕАЛИЗУЕМОСТЬ/РИСКИ]
> - Место: `server.py::_serve_one_attempt` (`_serve_env` с `mkdtemp`, затем `_spawn_serve` вне `try`) и `_spawn_serve` (участок `Popen` до создания `_ServeLease`).
> - Правило: RW-019, REQ-008, T-LIFE/v1, C-MULT-I4.
> - Evidence:
>   - отказ `Popen` (`OSError`) и `"no free serve port"` происходят до создания lease;
>   - `lifeline_w` не закрывается, порт остаётся в `_ACTIVE_SERVE_PORTS` навсегда, каталог `zen-serve-state-*` не удаляется;
>   - `OSError` не конвертируется в `ServeUnavailable`, а потоковый обработчик перехватывает его как «client gone mid-stream»: клиенту ни ошибки, ни отката на `run`.
> - Исправление: один `try/finally` от `mkdtemp` до выхода из `_spawn_serve` с очисткой всего перечисленного. `OSError` при запуске превращать в `ServeUnavailable`.
> - Критерий: тест с подменённым `Popen`, бросающим `OSError`, показывает откат на `run`, ноль утечек FD, пустой `_ACTIVE_SERVE_PORTS` и удалённый state-каталог.

### F-040
- origin: visionary · R1 · visionary-04
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-040 класс: duplicate_of:F-023 — контр-evidence: bridges/opencode-zen-bridge/server.py:5136, bridges/opencode-zen-bridge/server.py:6203 — удержание gate на всю попытку SSE и отсутствие » → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-040 класс: duplicate_of:F-023 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5092`, `:5136`, `:6203`, `:6243` — startup gate освобождается слишком поздно в SSE и не освобожда» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-04 [blocking, РЕАЛИЗУЕМОСТЬ/РИСКИ]
> - Место: `server.py::_run_serve_stream_attempts` (`gate.acquire()`, `gate.release()` после `_serve_one_attempt`) и `_serve_json_serve` (`_gate_j`).
> - Правило: S-HERD-I1, REQ-013, REQ-004.
> - Evidence: legacy-путь освобождает gate на первой строке stdout (`F-10`). В serve-пути он удерживается на всё время попытки. В JSON-пути `_gate_j.release()` не вызывается при успешном возврате, а вызывается только при исключениях и отказе limiter. Остальные запросы ждут `STARTUP_WAIT_S=5` с и идут без замка. Это задержка запуска model-вызова при параллельной нагрузке. Внутреннее устройство `_StartupGate` в пакете не приложено, оценка условна.
> - Исправление: освобождать gate после готовности serve или первого события, как legacy. Добавить `finally` в JSON-пути.
> - Критерий: два параллельных запроса стартуют менее чем за 1 с друг от друга. Счётчик `acquire`/`release` в тесте равен.

### F-041
- origin: visionary · R1 · visionary-05
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-041 класс: duplicate_of:F-017 — контр-evidence: bridges/opencode-zen-bridge/server.py:3063, bridges/opencode-zen-bridge/server.py:2385 — защёлка `delivered` по токенам вместо заголовко» → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-041 класс: duplicate_of:F-017 — контр-evidence: `bridges/opencode-zen-bridge/server.py:2385`, `:2997`, `:3063`, `:5208` — фиксация headers после чтения тела и пересчёт delivered по кон» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-05 [blocking, КОРРЕКТНОСТЬ]
> - Место: `server.py::_serve_one_attempt` (проверка `prompt_status` после `events.get`) и `_serve_http`.
> - Правило: RW-015, `FALLBACK_DECISION_TABLE`, REQ-009.
> - Evidence:
>   - классификация `_ps` выполняется только после успешного `events.get()`; при пустой очереди идёт `continue`, и ошибка HTTP может ждать до `first_event_timeout` (20 с);
>   - `_serve_http` читает тело целиком, поэтому `headers_at` ставится после тела;
>   - для 429/5xx `delivered` считается по наличию токенов, а таблица говорит «headers received → DELIVERED=true → serve_retry»;
>   - в режиме auto такой отказ без токенов приводит к откату на `run` вопреки таблице.
> - Исправление: проверять `prompt_status` в каждой итерации цикла, до `events.get`. Заводить `delivered` по получению заголовков ответа.
> - Критерий: поведенческие тесты по строкам таблицы (429, 5xx, 400, 401) проверяют фактические переходы `serve_health` и `breaker`, а не поиск строки в таблице.

### F-042
- origin: visionary · R1 · visionary-06
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AMEND
- dissent: skeptic d1 «DISPUTE F-042 класс: duplicate_of:F-027 — контр-evidence: bridges/opencode-zen-bridge/server.py:5087 — неотменяемый таймер, запись в `wfile` и повторный `STATUS_INITIAL` уже в F-027.» → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-042 класс: duplicate_of:F-027 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3042`, `:5079`, `:5087` — неотменяемый timer, второй источник initial-status и отдельный писатель» → teamlead/cycle-2/debate/d1/realist.md ; visionary d1 «AMEND F-042 priority=non-blocking; locations=server.py:5079-5087; fix=как в F-027 — причина: NEW: `on_status` в `_run_serve_stream_attempts` пишет `format_sse_chunk(...)` одним `self.wfile.wri» → teamlead/cycle-2/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=server.py:5079-5087; fix=как в F-027 — причина: NEW: `on_status` в `_run_serve_stream_attempts` пишет `format_sse_chunk(...)` одним `self.wfile.write(...)` и `flush()`, а `wfile` не буфер (teamlead/cycle-2/debate/d1/visionary.md)
- text (дословно, R1 visionary):
> F-06 [blocking, ПОЛНОТА/РИСКИ]
> - Место: `server.py::_run_serve_stream_attempts` (`_initial_status_timer`, `on_status`, `last_reasoning`).
> - Правило: REQ-005, REQ-009 (AC-014), RW-011.
> - Evidence:
>   - `threading.Thread(target=_initial_status_timer)` пишет в `wfile` без синхронизации с основным потоком; при совпадении по времени кадры SSE могут перемешаться;
>   - таймер не отменяется при завершении попытки: он может записать после `[DONE]`;
>   - на повторе `_model_seen` новый, `_wait` отрицательный, поэтому `STATUS_INITIAL` выдаётся мгновенно в начале каждой попытки; вместе со строкой «Повтор попытки» между попытками уже две статусные строки, а не одна (AC-014);
>   - внутри `_serve_one_attempt` `STATUS_INITIAL` выдаётся ещё раз (`_status_emitted[0]==0`);
>   - `last_reasoning` читается из двух потоков и не обновляется после статуса.
> - Исправление: единый замок на запись в `wfile`, единый источник статусов, отмена таймера в `finally`, `STATUS_INITIAL` ровно один раз на запрос.
> - Критерий: тест на двух попытках получает ровно один `STATUS_INITIAL` и одну строку «Повтор попытки». Тест на гонку пишет только корректные кадры.

### F-043
- origin: visionary · R1 · visionary-07
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-043 класс: duplicate_of:F-009 — контр-evidence: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:502, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:871 — те » → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-043 класс: duplicate_of:F-032 — контр-evidence: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:491`, `:502`, `:508`, `:591`, `:640`, `:787`, `:871` — пробелы поведенческ» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-07 [blocking, ПОЛНОТА/РИСКИ]
> - Место: `tests/test_realtime_reasoning.py` (`test_ac026...`, `test_serve_health_and_fallback_table`, `test_spawn_cap_and_proxy_rotation_helpers`, `test_native_tool_and_permission_reject`, `test_dynamic_config_switch_same_server`, `test_slow_serve_gets_status_and_no_status_on_fast`, `test_helper_argv_validation_and_lease_dir`).
> - Правило: RW-025, REQ-020, AC-001, AC-002, AC-020, REQ-001..REQ-016.
> - Evidence:
>   - AC-001 не проверен: тест проверяет разброс < 2,0 с, а не интервал < 500 мс; AC-002 не проверен;
>   - в FakeServe есть режимы `__never_event__` и `__silent__`, но тестов serve-watchdog'ов (`first_event_timeout`, `first_token_timeout`, `stall_timeout`) нет;
>   - нет тестов JSON-пути serve, `client_gone`, отсутствия пароля в логах (AC-020), реальной ротации прокси (проверяется только `callable(...)`), поведения строк `FALLBACK_DECISION_TABLE`;
>   - тест permission проверяет только наличие `bash`, но не reject и не interrupt;
>   - тест «dynamic config» проверяет читатель, но не маршрут;
>   - успешный запуск helper с 6 аргументами и размещением lease не тестируется;
>   - тест на «чужой sessionID» проверяет маппер, а не отбрасывание в цикле;
>   - на `AC-005`, `AC-026` нет теста на медленный апстрим со статусом на живом сокете в serve-пути (только `__slow__` без проверки контента);
>   - не могу проверить, продвигается ли пул прокси дважды за попытку (в `_run_env` и при явной передаче `proxy_url`).
> - Исправление: добавить перечисленные тесты как нетривиальные оракулы.
> - Критерий: каждый REQ-001..REQ-020 и AC-001..AC-026 имеет прямой тест, красный на сломанной реализации.

### F-044
- origin: visionary · R1 · visionary-08
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AMEND, visionary=AUTHOR
- dissent: realist d1 «AMEND F-044 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:1388,bridges/opencode-zen-bridge/server.py:2476; fix=проверять существующий lease-каталог через lstat: владел» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:1388,bridges/opencode-zen-bridge/server.py:2476; fix=проверять существующий lease-каталог через lstat: владелец, права и отсутствие symlink; при нару (teamlead/cycle-2/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-08 [non-blocking, РИСКИ]
> - Место: `server.py` (`LEASE_DIR`, `_spawn_serve`, `_run_serve_helper_cli`, `_startup_reaper`).
> - Правило: `agents/security.md` (предсказуемые пути в `/tmp`), T-LIFE/v1.
> - Evidence: `/tmp/opencode-zen-bridge-leases` создаётся с `mode=0o700`, но существующий каталог не проверяется на владельца и не-symlink; `OSError` у `os.chmod` игнорируется. `owner_uid` и PID берутся из содержимого файла и самоопределяемы.
> - Исправление: хранить lease под пользовательским каталогом (например `~/.dsh/...`). Проверять `lstat` на владельца, режим и отсутствие symlink до записи и чтения.
> - Критерий: тест с чужим или symlink-каталогом возвращает отказ.

### F-045
- origin: visionary · R1 · visionary-09
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-045 класс: invalid — контр-evidence: `FALLBACK_DECISION_TABLE`, фаза ANY, событие «HTTP400/404/422 invalid request», action `fail_closed`; RW-015 — 404 на `/api/session/active` как `Se» → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-045 класс: invalid — контр-evidence: `FALLBACK_DECISION_TABLE`, строка «HTTP400/404/422 invalid request → fail_closed», и `bridges/opencode-zen-bridge/server.py:2882` — предлагаемое пе» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-09 [non-blocking, РЕАЛИЗУЕМОСТЬ]
> - Место: `server.py::_serve_one_attempt` (ветки `status in (400, 404, 422)` на ready/create/event).
> - Правило: R-BULK-I3, F-DEG.
> - Evidence: любой 404 на `GET /api/session/active` трактуется как `ServeSecurityError` (fail-closed без отката на `run`, без sticky-деградации). Обновление `~/.opencode/bin/opencode` с изменением маршрутов API выключит весь serve-путь с ошибкой клиенту, а не с откатом.
> - Исправление: проверка версии через `GET /api/info` до сессии. Несовместимость маршрута до доставки трактовать как `ServeUnavailable` с записью в `serve_health`. Оставить fail-closed для 401/403.
> - Критерий: тест с FakeServe, у которого `/api/session/active` отвечает 404, получает откат на `run` и рост `serve_health`.

### F-046
- origin: visionary · R1 · visionary-10
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AMEND, visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-046 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py, bridges/opencode-zen-bridge/tests/test_step_interruption.py:69; fix=косметический откат format-only hunks до» → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «AMEND F-046 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2167,bridges/opencode-zen-bridge/server.py:4585,bridges/opencode-zen-bridge/tests/test_step_interruption.py:6» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py, bridges/opencode-zen-bridge/tests/test_step_interruption.py:69; fix=косметический откат format-only hunks допустим как FU-006; `CATALOG_SOURCE` не в (teamlead/cycle-2/debate/d1/skeptic.md) ; realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2167,bridges/opencode-zen-bridge/server.py:4585,bridges/opencode-zen-bridge/tests/test_step_interruption.py:69; fix=по возможности сократить только н (teamlead/cycle-2/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-10 [non-blocking, scope-diff]
> - Место: `server.py` (format-only hunks в `_UpstreamBreaker`, `Run._execute_once`, `Handler._stream_sse`, `_serve_json`, `_RequestAttempts` и др.; `CATALOG_SOURCE = "init"` → `"static"`, `_set_catalog_source`); `tests/test_step_interruption.py:67` (`r'''` → `r"""`).
> - Правило: FU-006, `agents/scope-and-contracts.md` (минимально достаточные изменения), `agents/code.md`.
> - Evidence: в дельте Цикла 1→2 reformatting только вырос. Изменено начальное значение публичной константы `CATALOG_SOURCE`.
> - Исправление: откатить format-only hunks вне логики. Либо обосновать `CATALOG_SOURCE`, либо вернуть `init`.
> - Критерий: `git diff --stat` не содержит правок строк, не связанных с serve/watchdog. Тест `test_catalog_mode` зелёный.

### F-047
- origin: visionary · R1 · visionary-11
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AMEND, visionary=AUTHOR
- dissent: realist d1 «AMEND F-047 priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:290,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:294,bridges/opencode-» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:290,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:294,bridges/opencode-zen-bridge/tests/test_realtime_reasoning (teamlead/cycle-2/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-11 [non-blocking, СООТВЕТСТВИЕ КОНТЕКСТУ]
> - Место: `tests/test_realtime_reasoning.py` (около 100 строк `# pyright: ignore[...] — причина: тест проверяет приватный/динамический API моста, тип уточнён аннотациями вокруг`).
> - Правило: `python-standards.md` запрет №9, RW-026.
> - Evidence: идентичная шаблонная «причина» не объясняет конкретное подавление. `VER-004` проверяет отсутствие `pyright: ignore` только в изменённых диапазонах `server.py` и `test_step_interruption.py`, а новый файл просто «ноль диагностик» благодаря подавлениям.
> - Исправление: типизировать (`cast`, Protocol, публичные хелперы) вместо подавления. Оставшиеся подавления сопровождать конкретной причиной.
> - Критерий: число подавлений в новом файле существенно меньше, у каждого осмысленная причина.

### F-048
- origin: visionary · R1 · visionary-12
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-048 класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:98, bridges/opencode-zen-bridge/server.py:239 — тот же `errno` до импорта helper-ветки.» → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-048 класс: duplicate_of:F-030 — контр-evidence: `bridges/opencode-zen-bridge/server.py:98`, `:99`, `:239`, `:244` — тот же ранний доступ к неимпортированному `errno`; самостоятельного » → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-12 [non-blocking, КОРРЕКТНОСТЬ]
> - Место: `server.py::_run_serve_helper_cli._fd_ready`.
> - Правило: RW-023, T-LIFE/v1.
> - Evidence: `errno` импортируется только в `else`-ветке (после раннего выхода helper), а `_fd_ready` использует `errno.EAGAIN` при `OSError` вне `BlockingIOError`. При `EBADF` на fd 0 получим `NameError` вместо чистого завершения.
> - Исправление: импортировать `errno` в начале модуля.
> - Критерий: тест с закрытым fd 0 завершает helper кодом 0 с чисткой группы.

### F-049
- origin: visionary · R1 · visionary-13
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-049 класс: duplicate_of:F-011 — контр-evidence: bridges/opencode-zen-bridge/server.py:6260 — usage на JSON-`continue` не суммируется; мёртвый `_seen_tc` — это F-004, не отдельный дефек» → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-049 класс: duplicate_of:F-033 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5166`, `:6260`, `:6281` — недоучёт usage неуспешных попыток уже зарегистрирован в F-033. Неисполь» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-13 [non-blocking, ПОЛНОТА]
> - Место: `server.py::_run_serve_stream_attempts`, `_serve_json_serve` (ветки `prompt_status`, транзиентная ошибка, `invalid_serve_event`; мёртвая переменная `_seen_tc`).
> - Правило: FU-004 (REQ-014), RW-018.
> - Evidence: usage неуспешных попыток копится только в одной ветке потокового пути и нигде в JSON. `_seen_tc` вычисляется и не используется, комментарий над ним ничего не реализует.
> - Исправление: накапливать usage по всем веткам `continue`. Удалить мёртвый код.
> - Критерий: тест с двумя попытками получает сумму usage в финальном чанке.

### F-050
- origin: visionary · R1 · visionary-14
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-050 priority=blocking; locations=bridges/opencode-zen-bridge/server.py:5202, bridges/opencode-zen-bridge/server.py:5203; fix=в `_delivered_err` учитывать `reasonings` и native-вызовы; » → teamlead/cycle-2/debate/d1/skeptic.md ; realist d1 «DISPUTE F-050 класс: duplicate_of:F-017 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5207`, `:5208` — reasoning-only доставка исключена из `_delivered_err`, что уже охвачено F-017; о» → teamlead/cycle-2/debate/d1/realist.md
- owner_decision: —
- amendments: skeptic d1: priority=blocking; locations=bridges/opencode-zen-bridge/server.py:5202, bridges/opencode-zen-bridge/server.py:5203; fix=в `_delivered_err` учитывать `reasonings` и native-вызовы; при fallback на `run` после уже отданног (teamlead/cycle-2/debate/d1/skeptic.md)
- text (дословно, R1 visionary):
> F-14 [non-blocking, ПОЛНОТА] [sweep]
> - Место: `server.py::_run_serve_stream_attempts` (`_delivered_err = bool(collected_texts or result.get("texts"))`).
> - Правило: REQ-009 (AC-014), REQ-005.
> - Evidence: доставка, состоящая только из размышления, не считается «доставленной». Транзитная ошибка после размышления уходит в откат на `run`, и клиент получает размышление повторно без разделителя `[мост]`.
> - Исправление: учитывать `reasonings` в `_delivered_err`. При откате на `run` после выданного размышления вставлять одну статусную строку.
> - Критерий: тест с ошибкой после трёх дельт размышления не дублирует их и выдаёт ровно один разделитель.
>
> **Подкатегории (14):**
>
> SUB Корректность/логика: FAIL — `server.py::_serve_one_attempt._reader` (F-01); обработка `timeout` (F-02).
> SUB Корректность/граничные условия: FAIL — `settimeout(0.5)` против паузы 1,5–1,8 с (F-01, `F-19`); дедлайн (F-02).
> SUB Корректность/обработка ошибок: FAIL — `Popen OSError` попадает в «client gone» (F-03); HTTP-статус `prompt` классифицируется с задержкой (F-05).
> SUB Полнота/покрытие AC: FAIL — AC-001, AC-002, AC-020 и serve-watchdog'и без оракулов (F-07).
> SUB Полнота/пропущенные ветки: FAIL — `timeout`/`client_gone` в JSON (F-02), статусы (F-06), размышление-только доставка (F-14).
> SUB Реализуемость/общее: FAIL — спин читателя и удержание gate (F-01, F-04).
> SUB Риски/безопасность: FAIL — предсказуемый `/tmp`-каталог lease с самоопределяемым `owner_uid` (F-08, non-blocking).
> SUB Риски/данные: PASS — `OPENCODE_DB=:memory:`, allowlist окружения и случайный пароль (`_serve_env`, `execution-evidence.md` EVD-072).
> SUB Риски/прод: FAIL — утечки FD/порта/каталога и неотменённый статусный поток (F-03, F-06); живой L3 отложен (`DEFERRED_L3`).
> SUB Риски/regression red→green: PASS — `l2-red.log` rc=1, 24 падения на `origin/dev`; GREEN rc=0 (`code-gate.json`).
> SUB Риски/Full Suite (L2): PASS — `l2-green-ver001/002/003/003b/ac023`: 408 passed, unittest OK, обратный порядок OK.
> SUB Риски/scope-diff: FAIL — format-only hunks и смена `CATALOG_SOURCE` (F-10, non-blocking).
> SUB Альтернативы/общее: PASS — прецедент muse-bridge ADR-0004, kill-switch сохранён, Google-маршрут побайтово неизменён (`code-gate.json`).
> SUB Соответствие контексту/общее: FAIL — шаблонные `pyright: ignore` и унаследованный reformatting (F-09, F-10, F-11, non-blocking кроме части F-09 по версионной проверке).

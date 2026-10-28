# Стенограмма дебатов Совета Тимлидов по коду — Cycle 2 (run `analyst-teamlead-zen-realtime-reasoning-20261025`)

## Раунд R1 (`panel/council/r9`)

### Seat 1 (`skeptic`, `grok-4.7-high`)

PANEL-NONCE: ef848fb9789626c7
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Цикл 2 закрыл RW-002, RW-004, RW-005, RW-006, RW-007, RW-009, RW-010, RW-012, RW-013, RW-014, RW-016, RW-017, RW-020, RW-022, RW-026, RW-027, RW-029, RW-030, RW-031, RW-032 и кодовую часть FU-001/FU-002/FU-003/FU-008/FU-009. Открыты четыре дефекта логики в изменённом `server.py`. Дедлайн попытки пишется как `exit_reason="timeout"` (`server.py:3254`), но кортежи обработки (`server.py:5150`, `server.py:6247`) его не содержат, и оба обработчика вызывают `serve_health.record_success()` и `attempt_done(False, True)` (`server.py:5237-5238`, `server.py:6307-6308`) — RW-008. HTTP 401/403 prompt классифицируется только после `events.get()` (`server.py:3056-3061`), а `first_event_timeout` возвращается раньше (`server.py:3022-3027`) — RW-015. В JSON `_seen_tc` вычисляется и не используется (`server.py:6370-6371`), `tool_calls_all` сохраняется через `continue` (`server.py:6378`) — RW-018. В ветке `--serve-helper` `errno` читается в `_fd_ready` (`server.py:98-99`) до импорта, который стоит только в `else` (`server.py:244`) после `SystemExit` (`server.py:239-241`): любой `OSError`, кроме уже перехваченного `BlockingIOError`, даёт `NameError`. Первый вызов `_fd_ready` стоит до `try/finally` с `killpg`, поэтому падение оставляет lease фазы `starting`.
   СОВЕТЫ (при FAIL):
   - Импортировать `errno` на уровне модуля до `_run_serve_helper_cli`.
   - Обработать `exit_reason=="timeout"` наравне с watchdog: без `record_success`, без `attempt_done(False, True)`, без успешного `[DONE]` и без JSON 200.
   - Классифицировать `prompt_status` в начале цикла SSE, до возврата по watchdog; 401/403 поднимать как `ServeSecurityError` даже при пустой очереди.
   - Перед JSON-retry удалять или дедуплицировать `tool_calls_all` неуспешной попытки; `_seen_tc` либо использовать, либо убрать.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-011 (таймер первого статуса, `server.py:5082-5090`) и RW-030 закрыты. RW-025 не закрыт: оракулы не покрывают AC. `__never_event__` и `__silent__` есть только в строке FakeServe (`tests/test_realtime_reasoning.py:112`, `:115`), живых тестов watchdog serve нет. AC-026 проверяет размах дельт `< 2.0` с (`:502`), а не интервал соседей `< 500` мс (AC-001) и не накладные расходы моста `≤ 250` мс (AC-002). Таблица fallback проверяется как данные (`:640`), а не как переходы prompt 401/429/5xx. Native-tool тест проверяет имя `bash` (`:591`), не reject/interrupt. Матрица транспорта не создаёт disable-файл (`:829-830`). Прокси проверяется как `callable` (`:871`). ELF/status проверяет только `isinstance(..., dict)` (`:881`). Нет JSON-serve, `client_gone`, скана лога на пароль (AC-020) и матрицы step-interruption на транспорте serve. В JSON `_StartupGate` берётся (`server.py:6203`) и отпускается только на limiter/ServeUnavailable/ServeSecurityError (`:6207`, `:6231`, `:6239`); после обычного возврата `_serve_one_attempt` release нет, в отличие от stream (`:5136`) — RW-001 частично.
   СОВЕТЫ (при FAIL):
   - Добавить поведенческие тесты serve: `__never_event__` → `first_event_timeout`, `__silent__` → `first_token_timeout` и `stall_timeout`.
   - В AC-026 проверять соседние `reasoning_content` `< 500` мс и задержку моста `≤ 250` мс.
   - Прогнать строки `FALLBACK_DECISION_TABLE` через FakeServe (401/403 fail-closed без инкремента health, 429 → breaker, 5xx до доставки → fallback).
   - Проверить reject+interrupt на `permission.asked`, disable-файл, разные значения `_next_standalone_proxy`, магию ELF и поле `status` tool.
   - Добавить JSON-serve, `client_gone` и отсутствие `OPENCODE_SERVER_PASSWORD` в `bridge.log`.
   - Обернуть JSON-попытку в `try/finally: _gate_j.release()`.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=RW-002, RW-006, RW-010, RW-021, RW-022 закрыты: handshake с дедлайном, cleanup группы в бюджете 5 с, timeout control-сокета, кольцо stderr, доказательство слушателя до Authorization. Три операционных дыры остаются. JSON-gate не отпускается на успехе и держит холодные старты до `STARTUP_GATE_S=12` (RW-001). `_serve_env` создаёт `zen-serve-state-*` (`server.py:1718`) до `_spawn_serve`; порт резервируется (`:2493`), pipe открывается (`:2502`), `Popen` (`:2505`) стоит вне `except BaseException` (`:2599`); `finally` закрывает только `lifeline_r` (`:2526-2530`); `_ServeLease` создаётся после успешного `Popen` (`:2531`). Ошибка `Popen` и `ServeUnavailable("no free serve port")` (`:2500`) не убирают `lifeline_w`, порт и каталог состояния (RW-019). Helper удаляет lease при `serve_proc.poll() is not None` (`server.py:231-233`), не при смерти группы `-pgid` (RW-023).
   СОВЕТЫ (при FAIL):
   - `try/finally` вокруг JSON `_StartupGate.acquire()`.
   - Единый cleanup от `mkdtemp`+pipe+`Popen`: оба конца pipe, `discard` порта, `rmtree` state-dir, `lease.cleanup()` если lease уже есть, включая «no free serve port».
   - В helper удалять lease только после `not _pid_alive(-os.getpgrp())`.

4. РИСКИ: VERDICT=FAIL
   WHY=L2 зелёный и это принимается: `L2-RED-sensitivity` rc=1 на `origin/dev`; VER-001 `408 passed`; VER-005 `29 passed`; AC-023 reversed rc=0; VER-004 `errorCount=0`, frozen sha256 `_run_env`/`_stream_google_sse`/`_execute_google_once` совпали. Секретов в репозитории нет: пароль — `secrets.token_hex(16)` (`server.py:1723`), allowlist, Authorization только после доказательства слушателя. Дыры: `_client_gone_check` на `OSError`/`ValueError` возвращает `False` (`server.py:4954-4955`) — RW-024; JSON-путь колбэк получает (`:6224`), семантика обрыва нет. Мёртвый `_seen_tc` оставляет дубли `tool_calls` (RW-018). VER-002 rc=0, но в stderr есть `ResourceWarning` незакрытых файлов `tests/test_cli_failure.py:267` — файл вне конверта. VER-006/VER-007 законно `DEFERRED_L3`.
   СОВЕТЫ (при FAIL):
   - В `_client_gone_check` возвращать `True` на `OSError`/`ValueError`, кроме `BlockingIOError` и `errno` `EAGAIN`/`EWOULDBLOCK`.
   - Дедуплицировать JSON `tool_calls` перед retry (тот же фикс, что в критерии 1).
   - Follow-up вне конверта: закрыть файлы в `tests/test_cli_failure.py:267`, чтобы `-W error::ResourceWarning` на полном discover оставался чистым.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=На цикле ≥2 раздувание без воспроизводимого дефекта не даёт FAIL. Раздельные циклы SSE и JSON нужны разным контрактам ответа. FU-006 (косметический format) и FU-007 (неполная унификация классификации) остаются non-blocking follow-up. Более дешёвый путь «только watchdog на `opencode run`» не закрывает RC-1 и в конверте не выбран.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Diff ровно в трёх файлах конверта, внешних runtime-зависимостей нет (`dependencies = []`). Замороженные срезы побайтово совпали с VER-004. Публичный каркас SSE/JSON сохранён; строки `[мост]` и поля `O-EXIT/v1` заданы REQ-004/005/016. `muse-bridge`, DSH и Google-direct не тронуты. `import json` обязателен при запрете зависимостей вне stdlib. FU-005 (документация вне трёх файлов) корректно отложен.

SUB Корректность/логика: FAIL — server.py:3254 `exit_reason="timeout"` затем server.py:5237 и server.py:6307 `record_success()`; server.py:3022 возвращает `first_event_timeout` до классификации 401 на server.py:3056; server.py:6371 `_seen_tc` не используется (RW-008, RW-015, RW-018)
SUB Корректность/граничные условия: FAIL — server.py:98-99 читает `errno` в helper до импорта server.py:244; server.py:4954-4955 `OSError`/`ValueError` → `False` (RW-024)
SUB Корректность/обработка ошибок: FAIL — `NameError` в `_fd_ready` до `killpg`; `timeout` не входит в кортеж server.py:5150 и server.py:6247; prompt 401 перекрывается `first_event_timeout` (error-handling.md, RW-008, RW-015)
SUB Полнота/покрытие AC: FAIL — tests/test_realtime_reasoning.py:112, :115, :502 (`< 2.0` с вместо AC-001/AC-002), :591, :640, :829-830, :871, :881; нет JSON-serve, client_gone, AC-020, serve step-interruption (RW-025)
SUB Полнота/пропущенные ветки: FAIL — server.py:6203 `_gate_j.acquire()` без release на успехе (release только :6207, :6231, :6239; stream отпускает :5136); `"timeout"` отсутствует в :5150 и :6247 (RW-001, RW-008)
SUB Реализуемость/общее: FAIL — server.py:1718 `mkdtemp`, :2493 порт, :2502 pipe, :2505 `Popen` вне cleanup :2599; lease удаляется по смерти serve, не группы, server.py:231 (RW-019, RW-023, feature.md finally)
SUB Риски/безопасность: PASS — пароль `secrets.token_hex(16)` server.py:1723, allowlist, listener до Authorization; секретов в diff нет (REQ-015)
SUB Риски/данные: FAIL — server.py:6370-6378 `_seen_tc` мёртвый, `tool_calls_all` живёт через retry (RW-018, AC-014)
SUB Риски/прод: FAIL — server.py:4954 ложный «клиент жив» на RST/EBADF; server.py:231 lease снимается при живой группе; server.py:6203 gate до 12 с (REQ-008, AC-011, S-HERD-I1)
SUB Риски/regression red→green: PASS — execution-evidence.md `L2-RED-sensitivity` rc=1 и VER-001/VER-005 rc=0 (REQ-020)
SUB Риски/Full Suite (L2): PASS — VER-001 408 passed, VER-002 rc=0, VER-003/003b rc=0, AC-023 reversed rc=0, VER-004 rc=0; ResourceWarning в test_cli_failure.py:267 non-blocking
SUB Риски/scope-diff: PASS — candidate-manifest.json ровно server.py, tests/test_realtime_reasoning.py, tests/test_step_interruption.py; frozen sha256 совпали
SUB Альтернативы/общее: PASS — цикл 2, двойной цикл SSE/JSON требуется контрактами ответа; FU-006/FU-007 non-blocking
SUB Соответствие контексту/общее: PASS — 3 файла конверта, stdlib, frozen `_run_env`/`_stream_google_sse`/`_execute_google_once`, Forbidden Scope не задет

F-1
priority: blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:98, bridges/opencode-zen-bridge/server.py:99, bridges/opencode-zen-bridge/server.py:239, bridges/opencode-zen-bridge/server.py:244
rule: python-standards.md §3 (fail-fast, имя должно быть связано); дефект дельты цикла 1→2 (ветка EAGAIN)
evidence: «if isinstance(_gone_exc, OSError) and _gone_exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK)» при том, что `import errno` стоит в `else` после `if sys.argv[1:2] == ["--serve-helper"]: raise SystemExit(...)`. `BlockingIOError` перехватывается раньше и до `errno` не доходит. Любой другой `OSError` (EBADF, EINTR) в процессе helper даёт `NameError`. Первый `_fd_ready()` выполняется до `try/finally` с `killpg`, lease фазы `starting` остаётся.
expected: `import errno` рядом с `select` до определения `_run_serve_helper_cli`.
verify: helper, у которого `select` на fd 0 бросает `OSError` с `EBADF` или `EINTR`, завершается без `NameError` и снимает lease.

F-2
priority: blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:3254, bridges/opencode-zen-bridge/server.py:5150, bridges/opencode-zen-bridge/server.py:5237, bridges/opencode-zen-bridge/server.py:5238, bridges/opencode-zen-bridge/server.py:6247, bridges/opencode-zen-bridge/server.py:6307, bridges/opencode-zen-bridge/server.py:6308
rule: RW-008, REQ-006, REQ-009, R-BULK-I1
evidence: «result["exit_reason"] = "timeout"» после цикла без `terminal`. Кортежи содержат только `first_event_timeout`, `first_token_timeout`, `stall_timeout`, `invalid_serve_event`. Дальше «res.serve_health.record_success()» и «attempts.attempt_done(False, True)», затем успешный `[DONE]` / JSON 200.
expected: ветка `timeout` идёт в retry или ошибку, без `record_success` и без успешного finish.
verify: укороченный `attempts.deadline` без terminal-события даёт `exit_reason=timeout`, счётчик `serve_health` не сбрасывается, клиент не получает `finish_reason=stop`.

F-3
priority: blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:3022, bridges/opencode-zen-bridge/server.py:3027, bridges/opencode-zen-bridge/server.py:3054, bridges/opencode-zen-bridge/server.py:3055, bridges/opencode-zen-bridge/server.py:3056, bridges/opencode-zen-bridge/server.py:3061
rule: RW-015, FALLBACK_DECISION_TABLE (HTTP401/403 → fail_closed)
evidence: при пустой очереди «except queue.Empty: continue» происходит до чтения `prompt_status`. При тишине «result["exit_reason"] = "first_event_timeout"» и `return` выполняются до «if _ps in (401, 403): raise ServeSecurityError». `headers_at` пишется только после чтения тела ответа. Создание сессии с 400 по-прежнему fail-closed и тестом закрыто; дыра только у статуса prompt.
expected: разбирать `prompt_status` в начале итерации, до watchdog-return; 401/403 всегда `ServeSecurityError`, без инкремента `serve_health` и без fallback.
verify: FakeServe отвечает 401 на prompt при молчащем SSE → security failure сразу, `failures` health не растёт, auto не уходит в `run`.

F-4
priority: blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:6370, bridges/opencode-zen-bridge/server.py:6371, bridges/opencode-zen-bridge/server.py:6378
rule: RW-018, AC-014
evidence: «_seen_tc = {str(tc.get("id")) for tc in tool_calls_all}» нигде не читается; следом `continue` оставляет уже добавленные вызовы в `tool_calls_all`. Поток SSE для текста использует `_PrefixDedup`; reasoning по AC-014 дедуплицировать не нужно.
expected: перед retry очищать или дедуплицировать `tool_calls_all` и content неуспешной попытки.
verify: JSON-сценарий unmapped-then-success возвращает каждый tool_call один раз.

F-5
priority: blocking
criterion: РЕАЛИЗУЕМОСТЬ
locations: bridges/opencode-zen-bridge/server.py:6203, bridges/opencode-zen-bridge/server.py:6207, bridges/opencode-zen-bridge/server.py:6231, bridges/opencode-zen-bridge/server.py:6239, bridges/opencode-zen-bridge/server.py:6307
rule: RW-001, REQ-013, S-HERD-I1, T-LIFE/v1
evidence: «_gate_j.acquire()». `release()` есть на отказе limiter, `ServeUnavailable` и `ServeSecurityError`. После обычного возврата `_serve_one_attempt` до `record_success()` release нет. Stream отпускает gate на `server.py:5136`.
expected: `try/finally: _gate_j.release()` на всех выходах JSON-попытки, включая `continue`.
verify: два последовательных JSON-serve не ждут `STARTUP_GATE_S`.

F-6
priority: blocking
criterion: РЕАЛИЗУЕМОСТЬ
locations: bridges/opencode-zen-bridge/server.py:1718, bridges/opencode-zen-bridge/server.py:2493, bridges/opencode-zen-bridge/server.py:2500, bridges/opencode-zen-bridge/server.py:2502, bridges/opencode-zen-bridge/server.py:2505, bridges/opencode-zen-bridge/server.py:2526, bridges/opencode-zen-bridge/server.py:2531, bridges/opencode-zen-bridge/server.py:2599
rule: RW-019, REQ-008, AC-011, feature.md (таймаут и cleanup в finally на каждом шаге I/O)
evidence: «state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")» выполняется до spawn. Порт кладётся в `_ACTIVE_SERVE_PORTS`, затем «lifeline_r, lifeline_w = os.pipe()» и `Popen`. `finally` закрывает только `lifeline_r`. Lease строится после успешного `Popen`. «except BaseException» вызывает `lease.cleanup()` только если lease уже есть. «raise ServeUnavailable("no free serve port")» тоже после `mkdtemp`.
expected: один `try/finally` от каталога состояния и pipe: закрыть оба fd, снять порт, удалить каталог, cleanup lease если он создан.
verify: `Popen`, бросающий `OSError`, не оставляет запись порта, каталог `zen-serve-state-*` и открытый `lifeline_w`.

F-7
priority: blocking
criterion: РЕАЛИЗУЕМОСТЬ
locations: bridges/opencode-zen-bridge/server.py:231, bridges/opencode-zen-bridge/server.py:232, bridges/opencode-zen-bridge/server.py:233
rule: RW-023, REQ-008, AC-011, T-LIFE/v1
evidence: «if serve_proc.poll() is not None: lease_path.unlink()». Комментарий finally требует снимать lease после смерти группы; условие смотрит только на прямой дочерний `serve`. Внук, оставшийся в группе, теряет lease, и reaper его не находит.
expected: `unlink` только когда `not _pid_alive(-os.getpgrp())` и `serve_proc` завершён.
verify: живой внук в той же группе оставляет lease-файл на диске.

F-8
priority: blocking
criterion: РИСКИ
locations: bridges/opencode-zen-bridge/server.py:4954, bridges/opencode-zen-bridge/server.py:4955, bridges/opencode-zen-bridge/server.py:6224
rule: RW-024, REQ-008, AC-011, AC-012
evidence: «except (OSError, ValueError): return False». JSON передаёт `is_client_gone=self._client_gone_check`, но обрыв сокета (EBADF/RST) читается как «клиент на месте». Половина RW-024 (прокидка в JSON) сделана.
expected: `return True`, если это не `BlockingIOError` и не `EAGAIN`/`EWOULDBLOCK`.
verify: закрытый клиентский сокет в stream и JSON даёт `client_gone` и `lease.cleanup()` не позже 7 с.

F-9
priority: blocking
criterion: ПОЛНОТА
locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:112, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:115, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:491, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:502, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:588, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:591, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:640, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:829, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:830, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:863, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:871, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:873, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:881
rule: RW-025, REQ-020, AC-001, AC-002, AC-008, AC-009, AC-010, AC-016, AC-018, AC-020, testing.md (зелёный прогон ≠ полнота)
evidence: маркеры `__never_event__` и `__silent__` живут только внутри строки FakeServe, вызовов нет. «self.assertLess(model_reasoning[-1][0] - model_reasoning[0][0], 2.0)» не проверяет соседний интервал и накладные расходы. `test_serve_health_and_fallback_table` сверяет строки таблицы. `test_native_tool_and_permission_reject` делает «self.assertIn("bash", _tool_names(chunks))». Docstring `test_transport_matrix` обещает disable-файл, код его не создаёт. «self.assertTrue(callable(server._next_standalone_proxy))». `test_elf_magic_and_tool_status` заканчивается «self.assertIsInstance(part_obj, dict)». Нет теста JSON-serve, client_gone, отсутствия пароля в логе и step-interruption на serve. L2 зелёный, потому что написанные тесты проходят, а не потому что оракулы RW-025 существуют.
expected: по одному нетавтологическому тесту на каждый перечисленный AC.
verify: каждый новый тест красный на `origin/dev` и зелёный на кандидате; prompt 401 не увеличивает `serve_health.failures`.

F-10
priority: non-blocking
criterion: РИСКИ
tag: [pre-existing]
locations: bridges/opencode-zen-bridge/tests/test_cli_failure.py:267
rule: testing.md (ResourceWarning при выходе процесса); файл вне `allowed_envelope_changes`
evidence: VER-002 stderr: «ResourceWarning: unclosed file <_io.TextIOWrapper name=9 ...>» и та же строка для fd 7, обе указывают на `tests/test_cli_failure.py:267`. Прогон rc=0, потому что discover шёл без `-W error`. Подмножество кодера с `-W error::ResourceWarning` этого файла не включало.
expected: follow-up отдельной задачей: закрыть pipe в тесте. В этот diff файл не входит.
verify: полный `unittest discover` с `-W error::ResourceWarning` без предупреждения на этой строке.

F-11
priority: non-blocking
criterion: ПОЛНОТА
locations: bridges/opencode-zen-bridge/server.py:6260, bridges/opencode-zen-bridge/server.py:6261, bridges/opencode-zen-bridge/server.py:6271, bridges/opencode-zen-bridge/server.py:6272, bridges/opencode-zen-bridge/server.py:6281, bridges/opencode-zen-bridge/server.py:6282, bridges/opencode-zen-bridge/server.py:5166
rule: FU-004, REQ-014 (SHOULD)
evidence: JSON-ветки `allow_retry` делают `continue` без суммирования `result["usage"]`. Stream перед таким `continue` копит `input/output/cached/reasoning` в `_serve_stream_usage` (`server.py:5166-5170`).
expected: тот же аккумулятор перед каждым JSON `continue` на timeout, invalid event и transient retry.
verify: две попытки JSON, первая с ненулевым usage и timeout, вторая успешная — финальный `usage` содержит сумму обеих.

F-12
priority: non-blocking
criterion: РИСКИ
locations: bridges/opencode-zen-bridge/server.py:75, bridges/opencode-zen-bridge/server.py:2630, bridges/opencode-zen-bridge/server.py:2644, bridges/opencode-zen-bridge/server.py:2645, bridges/opencode-zen-bridge/server.py:2646
rule: остаток RW-003 (сверка helper PID с живым `ps lstart`)
evidence: lease пишет «"helper_lstart": str(int(time.time()))». Reaper: «if _live and not _ts_v.isdecimal() and _live != _ts_v». Десятичная epoch-строка пропускает сравнение с `ps -o lstart=`. Комментарий на :2644 это фиксирует. Сверка `parent_start_ts` для lstart-формата работает.
expected: писать `helper_lstart` тем же форматом, что `ps lstart`, и сравнивать его.
verify: lease с живым PID другого процесса и тем же номером не получает `killpg`.

F-13
priority: non-blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:3215, bridges/opencode-zen-bridge/server.py:3216, bridges/opencode-zen-bridge/server.py:3181, bridges/opencode-zen-bridge/server.py:3192
rule: AC-021 (поле `ttft_ms` есть; семантика «первый токен» для tool-only не заполняется)
evidence: при `tool_event` «if result["first_token_at"] is None: result["first_token_at"] = time.monotonic()» без присвоения `ttft_ms`. Reasoning и text пишут `ttft_ms` на :3181 и :3192. VER-002: `transport=serve ... tools=1 ... ttft_ms=None`.
expected: при первом native tool completion выставлять `ttft_ms` так же, как для reasoning/text.
verify: tool-only ответ в `O-EXIT/v1` имеет целое `ttft_ms`.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `gpt-6.1-sol-high`)

PANEL-NONCE: 58afef6847a0e4b3
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

Общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком в сообщении до `<!-- КАНОН-КОНЕЦ -->`. Проектный `AGENTS.md`, `feature.md` и перечисленные профильные стандарты прочитаны в приложенном пакете; файлы рабочей папки не открывались. Тесты не запускал.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL  
   WHY=Выбранный транспорт осуществим, но исправления не обеспечивают корректное завершение по deadline, устойчивое чтение SSE после паузы, обработку ошибок prompt независимо от SSE и общий потолок запусков в JSON-пути. Сохранились нарушения одношаговой обработки инструментов и семантики повторов. См. F-001–F-008, F-018, F-022.  
   СОВЕТЫ (при FAIL): обработать все неуспешные исходы до ветки успеха; исправить SSE-reader; развести получение HTTP-заголовков и чтение тела; сделать барьер доставки необратимым; проверять общий бюджет перед каждым запуском обоих транспортов; завершать шаг после текстовых и native tool calls; восстановить разделение попыток и дедупликацию.

2. ПОЛНОТА: VERDICT=FAIL  
   WHY=Заявление «RW-001..RW-032 закрыты» не подтверждается кодом и оракулами. Новый модуль содержит 29 зелёных тестов, однако существенная часть обязательных сценариев отсутствует либо проверяет вспомогательную структуру вместо конечного поведения. Первая реакция legacy-пути при ожидании startup gate также не укладывается в AC-005. См. F-015, F-019.  
   СОВЕТЫ (при FAIL): добавить перечисленные в F-019 поведенческие проверки; исправить legacy-статус до ожиданий; пересобрать traceability по конкретным тестам и проверяемым утверждениям, сохранив `INCONCLUSIVE` там, где прямого свидетельства нет.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL  
   WHY=Зависимости доступны: Python stdlib, установленный OpenCode v2.1.2, loopback API и существующий прокси-пул. Оценка памяти допускает шесть serve-процессов, но эксплуатацию блокируют незамкнутые пути освобождения ресурсов, удержание startup gate, неполная уборка потомков и ошибки обнаружения отключения клиента. См. F-009–F-014, F-016–F-017.  
   СОВЕТЫ (при FAIL): обеспечить единое владение ресурсами от создания временного каталога; освобождать gate в `finally`; завершать и проверять всю группу процессов; исправить проверку RST и идентичности PID; отменять фоновые таймеры. Оценочно потребуется 2–4 инженерных дня на исправления и 0,5–1 день на проверку после стабилизации; это оценка, зависящая от воспроизводимости отказов и доступности Zen.

4. РИСКИ: VERDICT=FAIL  
   WHY=Full Suite L2 действительно зелёный: 408 тестов компонента и 894 теста корневого набора. Это не устраняет конкретные риски: потерю SSE после штатной паузы, ложный успех при timeout, осиротевшие процессы, повтор принятого prompt и недоучёт upstream-сбоев. Red-прогон не доказывает чувствительность именно временного оракула AC-026. См. F-001–F-004, F-011–F-013, F-016, F-018–F-019.  
   СОВЕТЫ (при FAIL): закрыть эти дефекты regression-тестами с управляемыми часами и отказами; проверить конечные сокеты, процессы и журналы; после ACCEPT выполнить предусмотренный L3. Отсрочка VER-006/VER-007 сама по себе замечанием не является.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS  
   WHY=Короткоживущий serve с резервным run оправдан подтверждёнными ограничениями CLI и необходимостью ротации IP. Возврат к одному legacy-пути не закроет RC-1, общий демон усложнит ротацию, прямой Zen пока не подтверждён. Замена самописного JSON-парсера стандартным `json.loads` устраняет прежнее неоправданное усложнение. Полная смена архитектуры для исправления перечисленных дефектов не требуется.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL  
   WHY=Границы трёх файлов, stdlib-only и замороженные функции соблюдены; изменений публичных HTTP-маршрутов не обнаружено. Однако новый тестовый код использует прямо запрещённые приложенным `testing.md` конструкции `unittest.TestCase`/`setUp`/`tearDown`; обязательные проверки жизненного цикла и дедлайнов также закрыты неполно. См. F-009–F-012, F-019, F-021. Требования Litestar/async к автономному `ThreadingHTTPServer` механически не применяю.  
   СОВЕТЫ (при FAIL): перевести новый тестовый модуль на pytest-фикстуры; сохранить согласованную изоляцию окружения; закрыть применимые `T-LIFE`, `C-MULT-I4`, `R-BULK-I1/I3` поведенческими оракулами.

Обозначения далее: `S` — `bridges/opencode-zen-bridge/server.py`; `T` — `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`; `I` — `bridges/opencode-zen-bridge/tests/test_step_interruption.py`. `PASS по коду` означает подтверждённое исправление реализации; отсутствие прямого regression-оракула отмечено отдельно.

Проверка устранения замечаний:

- RW-001 — PARTIAL: gate, limiter и передача proxy добавлены (`S:5092`, `S:6203`), но освобождение gate некорректно, прокси выбирается дважды; F-010, F-022.
- RW-002 — PASS по коду: побайтовый handshake ограничен остатком трёх секунд (`S:2544`). Прямой тест частичной строки без LF — INCONCLUSIVE.
- RW-003 — FAIL: `0700` и UID добавлены, но идентичность helper не проверяется по времени запуска; F-016.
- RW-004 — PASS по коду: `tool_choice` передаётся в оба serve-пути и recovery (`S:5274`, `S:5593`, `S:6482`). Прямой serve regression — INCONCLUSIVE.
- RW-005 — PASS: самописный парсер удалён; стандартный JSON, суррогаты и ошибка разбора проверяются (`S:1625`, `T:778`).
- RW-006 — FAIL: после эскалации не остаётся полноценного бюджета подтверждения смерти группы; F-012.
- RW-007 — PASS по коду: `if text_value:` сохраняет пробельные дельты (`S:3178`, `S:3189`); unit-оракул маппера имеется (`T:806`).
- RW-008 — FAIL: deadline передан, но возвращённый `timeout` допускается в ветку успеха; F-001.
- RW-009 — FAIL: повторное чтение буферизованного HTTP-response после socket timeout не восстанавливает поток; F-002.
- RW-010 — PARTIAL: timeout существующего control-сокета обновляется, cleanup-запросы ограничены (`S:2377`, `S:3268`); общий lifecycle-бюджет не доказан, F-012.
- RW-011 — FAIL: timer добавлен только в serve-оркестрацию, не отменяется и конкурирует с другим механизмом статусов; legacy ожидание gate не покрыто; F-014, F-015.
- RW-012 — PASS по коду: watchdog вызывается и при поступлении stdout (`S:1187`). Прямые тесты непрерывных служебных событий — INCONCLUSIVE.
- RW-013 — FAIL: SSE fallback защищён, JSON fallback способен выполнить четвёртый запуск; F-005.
- RW-014 — PASS по коду: успешный serve вызывает `attempt_done(False, True)` в обоих режимах; unit перехода breaker зелёный (`T:817`). Проверка через сам serve-handler — INCONCLUSIVE.
- RW-015 — FAIL: HTTP-результат проверяется только после получения элемента SSE-очереди, барьер доставки не соответствует зафиксированной таблице; F-003, F-004.
- RW-016 — PARTIAL: transient-классификация добавлена, но upstream breaker учитывает эти отказы непоследовательно; F-004, F-018.
- RW-017 — FAIL: завершение шага реализовано для native calls, но не для вызовов, распарсенных из text; F-006.
- RW-018 — FAIL: разделитель есть не на всех retry-ветках; JSON не дедуплицирует одинаковые вызовы из двух каналов; F-007, F-008.
- RW-019 — FAIL: исключения до создания `_ServeLease` находятся вне cleanup-блока; F-009.
- RW-020 — PARTIAL: stop-aware очередь и ограниченный join добавлены (`S:2944`, `S:3259`); завершение prompt-thread до возврата не подтверждено. Матрица переполнения/отмены отсутствует; F-019.
- RW-021 — PASS: helper stderr дренируется в `deque(maxlen=64)` (`S:2595`).
- RW-022 — PASS по коду: внутрипроцессное резервирование портов и положительная ownership-проверка добавлены (`S:2486`, `S:2583`). Конкурентный оракул — INCONCLUSIVE.
- RW-023 — FAIL: helper проверяет непосредственный serve-процесс вместо всей группы; F-011.
- RW-024 — FAIL: RST/ошибки сокета по-прежнему превращаются в `False`; JSON дополнительно не обрабатывает возвращённый `client_gone`; F-001, F-013.
- RW-025 — FAIL: требуемая поведенческая матрица не добавлена полностью; F-019.
- RW-026 — PASS в согласованном статическом гейте: блоковые отключения удалены, VER-004 подтверждает ноль ошибок и ноль диагностик нового файла.
- RW-027 — PASS по коду: лишний `pop` удалён, восстановление окружения сохранено (`T:354`, `T:851`).
- RW-028 — PARTIAL: сокетный замер сохранён, но детерминированных watchdog-оракулов нет; F-019.
- RW-029 — PASS по коду: чужой явный `sessionID` фильтруется до диспетчеризации (`S:3086`); прямой тест фильтра в живом цикле — INCONCLUSIVE.
- RW-030 — PASS по коду: request-level метрики не затираются последующими попытками (`S:5137`, `S:5809`, `S:6243`). Retry-оракул метрик — INCONCLUSIVE.
- RW-031 — PASS: указанные служебные события с пустым `data` игнорируются (`S:1779`, `T:787`).
- RW-032 — PASS: окружение сохраняется и восстанавливается через `patch.dict` (`I:206`, `I:222`).

Сопутствующие пункты:

- FU-001 — PASS по коду: разрешающий `len(head) == 4` удалён (`S:1738`).
- FU-002 — PASS по коду: статус определяется типом tool-события (`S:2758`); тест не проверяет само значение статуса.
- FU-003 — PASS: комментарий описывает ограниченный буфер без логирования (`S:2594`).
- FU-004 — PARTIAL, non-blocking: SSE исправлен для части watchdog-ретраев; JSON и другие ветки продолжают терять usage; F-020.
- FU-005 — допустимо отложен на PR_DESCRIPTION/эксплуатационный handoff после Совета.
- FU-006 — косметические hunks остались; согласованный non-blocking follow-up, оснований для FAIL нет.
- FU-007 — общая классификация полностью не выделена; согласованный non-blocking follow-up. Конкретные поведенческие расхождения отражены отдельными findings.
- FU-008 — PASS: ожидания трёх запусков объяснены docstring (`I:435`, `I:444`).
- FU-009 — PASS по коду: tool input delta продлевает stall-часы после первого токена (`S:3199`).

Поштучная проверка требований:

- REQ-001 — FAIL: SSE может перестать читать дельты после штатной паузы; F-002.
- REQ-002 — PASS по структуре: публичные маршруты, порт и OpenAI-оболочки сохранены.
- REQ-003 — PASS по переключению: run сохранён, kill-switch имеется; ошибки fallback отдельно отражены в F-004/F-005.
- REQ-004 — FAIL: первая реакция legacy после gate/spawn не гарантирована; F-015.
- REQ-005 — PARTIAL: пробельные дельты восстановлены, replay исключает reasoning; полнота побайтовой проверки всех сценариев не доказана, F-019.
- REQ-006 — PARTIAL: watchdog реализован; уборка и временной бюджет отказов не закрыты, F-009/F-012.
- REQ-007 — FAIL: SSE-reader не переживает паузу до watchdog; F-002.
- REQ-008 — FAIL: RST, ранние утечки и потомки после смерти родителя; F-009/F-011–F-013/F-016.
- REQ-009 — FAIL: JSON spawn cap, delivery barrier, retry-разделители и breaker; F-004/F-005/F-007/F-018.
- REQ-010 — PASS по коду: существующий инкрементальный parser переиспользован; разрезанный tool tag проверяется (`T:583`).
- REQ-011 — FAIL: текстовый tool call не закрывает serve-шаг; F-006.
- REQ-012 — PASS по реализации политики: `ask_reject`/`deny`, reject и interrupt предусмотрены. Полная проверка parity — INCONCLUSIVE, F-019.
- REQ-013 — FAIL: двойное продвижение прокси-пула нарушает ротацию; F-022.
- REQ-014 — PARTIAL: нормальный usage отображается, failed-attempt usage учитывается не полностью; F-020, non-blocking.
- REQ-015 — INCONCLUSIVE по AC-020: пароль случайный, env ограничен; прямого log-оракула нет, F-019.
- REQ-016 — PASS по наличию полей и сохранению первого наблюдения; полная матрица исходов не подтверждена.
- REQ-017 — PASS: полный и обратный прогоны зелёные.
- REQ-018 — PASS: frozen hashes и неизменённый Google Direct подтверждены VER-004.
- REQ-019 — DEFERRED_L3: законно отложено до ACCEPT.
- REQ-020 — FAIL по качеству оракула: независимого сигнала окончания апстрима нет; F-019.

Поштучная проверка AC:

- AC-001 — INCONCLUSIVE: соседние клиентские интервалы `<500 мс` тест не проверяет.
- AC-002 — INCONCLUSIVE: независимых upstream timestamps для overhead `≤250 мс` нет.
- AC-003 — PASS: существующий формат сохранён, L2 зелёный.
- AC-004 — PASS: legacy-набор проходит.
- AC-005 — FAIL: ожидание legacy gate/spawn не покрыто первой реакцией; F-015.
- AC-006 — PARTIAL: эталонный reasoning проверен; полная матрица дельт и повторов отсутствует.
- AC-007 — PASS: исключение `reasoning_content` из prompt проверяется.
- AC-008 — INCONCLUSIVE: имеющийся тест проверяет суммарное время `<25 с`, не требуемую границу отдельной попытки.
- AC-009 — FAIL: пауза ломает reader раньше штатного stall-watchdog; F-002.
- AC-010 — FAIL: тот же дефект препятствует корректному ожиданию первого токена; F-002.
- AC-011 — FAIL: смерть всей группы и соблюдение бюджета не гарантированы; F-011/F-012.
- AC-012 — FAIL: RST может не обнаруживаться штатным checker; F-013.
- AC-013 — FAIL: JSON fallback допускает четвёртый запуск; F-005.
- AC-014 — FAIL: нет разделителя на всех переходах между попытками; F-007.
- AC-015 — PASS по переиспользованному parser и существующим тестам; отдельный serve-сценарий разрезанного тега зелёный.
- AC-016 — FAIL: всей step-interruption матрицы на serve нет, текстовый tool-call terminal неполон; F-006/F-019.
- AC-017 — INCONCLUSIVE: native `bash` проверен, parity unmapped-повтора и завершения не проверена.
- AC-018 — FAIL: при пуле из двух записей фактический proxy может повторяться; F-022.
- AC-019 — PASS для канонического отображения fixture; итоговый multi-attempt usage — PARTIAL, F-020.
- AC-020 — INCONCLUSIVE: проверки отсутствия пароля и apiKey в `bridge.log` нет.
- AC-021 — PASS по наличию полей; сквозная матрица всех исходов неполна.
- AC-022 — PASS: 408 passed в компоненте.
- AC-023 — PASS: обратный порядок также даёт 408 passed.
- AC-024 — PASS: Google Direct frozen и тесты зелёные.
- AC-025 — DEFERRED_L3.
- AC-026 — FAIL по оракулу: сравнение с окончанием клиентского ответа допускает буферизованную доставку; F-019.

Границы проверены по отдельности:

- Non-Goals 1 — публичные маршруты, порт и оболочка SSE сохранены.
- Non-Goals 2 — DSH, `app.asar`, профиль и ReasoningRow не изменены.
- Non-Goals 3 — отдельной переработки текста ради UI-превью нет; сохранение данных требует дополнительных оракулов.
- Non-Goals 4 — состав моделей и правила effort не переработаны.
- Non-Goals 5 — другие мосты и общие конфиги не изменены.
- Non-Goals 6 — внешних runtime-зависимостей не добавлено.
- Forbidden Scope 1 — кандидат ограничен тремя разрешёнными файлами.
- Forbidden Scope 2 — реальных секретов в diff не обнаружено; runtime-проверка журналов остаётся INCONCLUSIVE.
- Forbidden Scope 3 — живой контур законно не изменялся до ACCEPT.
- Forbidden Scope 4 — вызовов `security find-generic-password` нет.
- Forbidden Scope 5 — прямой правки общей БД/state нет; используется `OPENCODE_DB=:memory:`.
- Forbidden Scope 6 — кандидат на feature-ветке; свидетельства запрещённого коммита или merge нет.

Все findings одного прохода:

**F-001 — priority=blocking — незавершённая попытка может считаться успешной.**  
locations: `bridges/opencode-zen-bridge/server.py:3252`, `bridges/opencode-zen-bridge/server.py:5151`, `bridges/opencode-zen-bridge/server.py:6249`.  
Правило: RW-008, RW-024, `R-BULK-I1`, `O-EXIT/v1`. Evidence: producer возвращает `exit_reason="timeout"`, но оба consumer проверяют ограниченный список без `timeout`; JSON также не обрабатывает `client_gone`. Затем достижимы `record_success()` и успешный ответ с частичными данными.  
Исправление: обработать все неуспешные исходы до success-ветки; ограничить setup I/O остатком общего deadline. Проверка: истёкший deadline и JSON disconnect никогда не вызывают success, HTTP 200 или успешный SSE finish.

**F-002 — priority=blocking — SSE не восстанавливается после socket timeout.**  
locations: `bridges/opencode-zen-bridge/server.py:2941`, `bridges/opencode-zen-bridge/server.py:2955`.  
Правило: RW-009, REQ-007, AC-009/010. Evidence: после timeout на `sse_resp.readline()` выполняется `continue`. У буферизованного SocketIO timeout оставляет состояние, при котором дальнейшее чтение вызывает `OSError: cannot read from timed out object`; этот OSError снова проглатывается. Возможен быстрый цикл ошибок до watchdog.  
Исправление: использовать чтение, допускающее возобновление после ожидания готовности, без poisoning буферизованного response. Проверка: пауза более 5 секунд, но меньше watchdog, затем новые дельты доставляются в той же попытке.

**F-003 — priority=blocking — HTTP-ошибка prompt зависит от наличия SSE-события.**  
locations: `bridges/opencode-zen-bridge/server.py:3053`, `bridges/opencode-zen-bridge/server.py:3057`.  
Правило: RW-015, обработка ошибок независимо от канала данных. Evidence: `queue.Empty` делает `continue` до проверки `prompt_status`. Если prompt уже вернул 401/429/5xx, а SSE молчит, ошибка может быть перекрыта watchdog.  
Исправление: проверять результат prompt на каждой итерации до ожидания очереди. Проверка: каждый предусмотренный HTTP-status классифицируется при пустой SSE-очереди.

**F-004 — priority=blocking — барьер доставки не является необратимым.**  
locations: `bridges/opencode-zen-bridge/server.py:2385`, `bridges/opencode-zen-bridge/server.py:2997`, `bridges/opencode-zen-bridge/server.py:3063`, `bridges/opencode-zen-bridge/server.py:5208`, `bridges/opencode-zen-bridge/server.py:6280`.  
Правило: `FALLBACK_DECISION_TABLE`, REQ-009, RW-015/016. Evidence: `headers_at` устанавливается после полного `resp.read()`, а не получения заголовков; HTTP-ветка заново вычисляет delivered по накопленному контенту. SSE transient-ветка учитывает text, но игнорирует уже выданный reasoning. Поэтому принятый prompt может перейти в fallback.  
Исправление: фиксировать согласованный delivery latch при заголовках/валидном execution-событии и никогда не сбрасывать его; отдельно учитывать клиентскую эмиссию. Проверка: headers-only, execution-only и reasoning-only сценарии не допускают запрещённого fallback. Противоречие текста RW-015 и таблицы относительно prompt 400/404/422 следует явно разрешить в конверте, не скрывать кодом.

**F-005 — priority=blocking — общий потолок запусков не защищает JSON fallback.**  
locations: `bridges/opencode-zen-bridge/server.py:6194`, `bridges/opencode-zen-bridge/server.py:6230`, `bridges/opencode-zen-bridge/server.py:6498`, `bridges/opencode-zen-bridge/server.py:4704`.  
Правило: RW-013, AC-013, `R-BULK-I2`. Evidence: после двух serve retries третья попытка может вернуть `ServeUnavailable`; auto возвращает `False`, затем JSON-путь запускает `Run` без предварительного `can_spawn()`. Сам `_execute_once()` создаёт процесс до `note_spawn()`.  
Исправление: единая проверка бюджета непосредственно перед каждым фактическим запуском. Проверка: две retries → третий setup failure → fallback дают максимум три запуска.

**F-006 — priority=blocking — текстовый tool call не закрывает serve-шаг.**  
locations: `bridges/opencode-zen-bridge/server.py:3236`, `bridges/opencode-zen-bridge/server.py:5000`, `bridges/opencode-zen-bridge/server.py:5030`.  
Правило: RW-017, REQ-011. Evidence: parser может уже эмитировать клиенту tool call, но `_serve_one_attempt()` при `step_finish` проверяет только `result["native_calls"]`. Для вызова из `<tool_invoke>` список пуст, чтение следующего шага продолжается.  
Исправление: передать в транспорт сигнал наличия распарсенного tool call и завершать попытку на соответствующем step boundary. Проверка: text tool call → step_finish → STEP2; STEP2 клиенту не передаётся.

**F-007 — priority=blocking — не все повторы reasoning разделены статусом.**  
locations: `bridges/opencode-zen-bridge/server.py:5211`, `bridges/opencode-zen-bridge/server.py:5228`, `bridges/opencode-zen-bridge/server.py:5255`, `bridges/opencode-zen-bridge/server.py:5281`.  
Правило: RW-018, AC-014. Evidence: transient recovery, unmapped и обычный incomplete recovery выполняют `continue` без общего разделителя; он добавлен только в отдельных watchdog/HTTP-ветках.  
Исправление: единая эмиссия ровно одного retry-разделителя перед следующей попыткой после reasoning. Проверка: все причины повторов сохраняют reasoning и дают ровно один разделитель.

**F-008 — priority=blocking — JSON способен вернуть одинаковый инструмент дважды [pre-existing].**  
locations: `bridges/opencode-zen-bridge/server.py:6323`, `bridges/opencode-zen-bridge/server.py:6344`, `bridges/opencode-zen-bridge/server.py:6372`.  
Правило: RW-018, parity с существующим `emit_tool_call`. Evidence: parsed calls и mapped native calls независимо добавляются в `tool_calls_all` с разными случайными ID; `_seen_tc` вычисляется, но не используется. Одинаковые name/arguments из двух каналов становятся двумя клиентскими вызовами.  
Исправление: дедуплицировать по семантическому ключу name/arguments. Проверка: одинаковый вызов в text и native даёт один `tool_call` в JSON.

**F-009 — priority=blocking — ранние ошибки запуска обходят уборку.**  
locations: `bridges/opencode-zen-bridge/server.py:1713`, `bridges/opencode-zen-bridge/server.py:2476`, `bridges/opencode-zen-bridge/server.py:2505`, `bridges/opencode-zen-bridge/server.py:2508`, `bridges/opencode-zen-bridge/server.py:2835`.  
Правило: RW-019, `T-LIFE/v1`, `C-MULT-I4`. Evidence: state-dir создаётся до `_spawn_serve`; резервирование порта, `os.pipe()` и helper `Popen()` происходят до общего cleanup-блока. При ошибке `Popen` закрывается только read-end pipe.  
Исправление: единый exception-safe владелец state-dir, порта, обоих FD и процесса с начала создания ресурсов. Проверка: инъекция отказов mkdir/pipe/Popen/handshake не оставляет FD, портов, каталогов или процессов.

**F-010 — priority=blocking — startup gate удерживается дольше startup-фазы.**  
locations: `bridges/opencode-zen-bridge/server.py:5092`, `bridges/opencode-zen-bridge/server.py:5136`, `bridges/opencode-zen-bridge/server.py:6203`, `bridges/opencode-zen-bridge/server.py:6243`.  
Правило: RW-001, `S-HERD-I1`, `C-MULT-I4`. Evidence: SSE освобождает gate после всей `_serve_one_attempt()`, JSON на обычном возврате вообще не вызывает release. Это создаёт ненужные ожидания и переходы в fail-open по таймеру gate.  
Исправление: освобождать gate после подтверждённого startup/первого события и гарантированно в `finally`. Проверка: длинная генерация первого запроса не удерживает startup gate для второго.

**F-011 — priority=blocking — после смерти родителя могут остаться внуки serve.**  
locations: `bridges/opencode-zen-bridge/server.py:195`, `bridges/opencode-zen-bridge/server.py:232`.  
Правило: RW-023, REQ-008, `T-LIFE/v1`. Evidence: helper эскалирует только если непосредственный `serve_proc` ещё жив; lease удаляется, если этот процесс завершился. Если serve завершился после TERM, а его потомок TERM игнорирует, эскалация пропускается и lease теряется.  
Исправление: проверять всех остальных членов собственной группы независимо от состояния прямого потомка; сохранять свидетельство до их завершения. Проверка: смерть родителя + завершившийся serve + TERM-resistant grandchild не оставляют сирот.

**F-012 — priority=blocking — бюджет cleanup исчерпан до проверки результата SIGKILL.**  
locations: `bridges/opencode-zen-bridge/server.py:2432`, `bridges/opencode-zen-bridge/server.py:2444`, `bridges/opencode-zen-bridge/server.py:2450`, `bridges/opencode-zen-bridge/server.py:2470`.  
Правило: RW-006/010, AC-011. Evidence: TERM-ожидание расходует весь `_deadline`; после SIGKILL повторный цикл использует тот же истёкший deadline. Cleanup может вернуться с живой группой, уже установив `_closed=True`, и удалить state-dir.  
Исправление: заранее разделить общий бюджет на TERM, KILL и подтверждение; не считать уборку завершённой при живой группе. Проверка: игнорирующая TERM группа подтверждённо отсутствует до возврата в пределах AC-011.

**F-013 — priority=blocking — RST не считается отключением клиента [pre-existing].**  
locations: `bridges/opencode-zen-bridge/server.py:4938`, `bridges/opencode-zen-bridge/server.py:4955`.  
Правило: RW-024, REQ-008. Evidence: `ConnectionResetError` является `OSError`; checker возвращает `False` для всех `OSError/ValueError`. JSON во время генерации ничего не пишет клиенту, поэтому альтернативного быстрого обнаружения нет.  
Исправление: отличать EAGAIN/EWOULDBLOCK от RST/EBADF и других терминальных ошибок; включить ошибку `os.dup` в эту классификацию. Проверка: FIN и RST в SSE/JSON вызывают `client_gone` и cleanup в заданном бюджете.

**F-014 — priority=blocking — статусный timer не принадлежит жизненному циклу запроса.**  
locations: `bridges/opencode-zen-bridge/server.py:3042`, `bridges/opencode-zen-bridge/server.py:5079`, `bridges/opencode-zen-bridge/server.py:5087`.  
Правило: RW-011, `T-LIFE/v1`, целостность SSE. Evidence: отдельный daemon timer пишет непосредственно в `wfile`, не отменяется на terminal/fallback и работает одновременно со статусами основного serve-цикла. Возможны два initial-status и конкурентные записи с модельными чанками.  
Исправление: один владелец SSE-записей, общее состояние первого статуса, отмена timer при любом завершении. Проверка: ранний tool-only terminal, fallback и модельная дельта около порога не дают поздних/двойных статусов или повреждения кадра.

**F-015 — priority=blocking — legacy не гарантирует первый видимый статус за секунду [pre-existing].**  
locations: `bridges/opencode-zen-bridge/server.py:5649`, `bridges/opencode-zen-bridge/server.py:5716`, `bridges/opencode-zen-bridge/server.py:5743`.  
Правило: RW-011, REQ-004, AC-005. Evidence: часы статуса legacy создаются после gate/limiter/spawn; служебный статус отправляется только при чтении feed. Ожидание gate может занять пять секунд до начала этих часов.  
Исправление: запустить request-level статусный механизм до startup-ожиданий. Проверка: занятый gate и молчащий CLI всё равно дают видимый reasoning/status не позже 1,0 секунды.

**F-016 — priority=blocking — защита reaper от переиспользования helper PID неполна.**  
locations: `bridges/opencode-zen-bridge/server.py:78`, `bridges/opencode-zen-bridge/server.py:2639`, `bridges/opencode-zen-bridge/server.py:2660`.  
Правило: RW-003, ownership lifecycle. Evidence: `helper_lstart` записан epoch-числом, а reaper явно пропускает сравнение decimal timestamps с живым `ps lstart`. Наличие `--serve-helper` в argv не доказывает, что это helper данной попытки.  
Исправление: сохранять и проверять сопоставимую идентичность процесса/группы до сигналов. Проверка: lease со старым временем и переиспользованным PID другого helper не вызывает сигналов.

**F-017 — priority=blocking — ранняя helper-ветка обращается к неимпортированному errno.**  
locations: `bridges/opencode-zen-bridge/server.py:99`, `bridges/opencode-zen-bridge/server.py:240`, `bridges/opencode-zen-bridge/server.py:245`.  
Правило: корректная обработка ошибок, RW-023. Evidence: helper завершается до импорта `errno` из `else`, но `_fd_ready()` использует `errno.EAGAIN/EWOULDBLOCK` при OSError. Эта ветка завершится `NameError`.  
Исправление: импортировать требуемый stdlib-модуль до helper dispatch. Проверка: OSError на lifeline проверяет нужный исход без NameError.

**F-018 — priority=blocking — transient upstream-события обходят Circuit Breaker.**  
locations: `bridges/opencode-zen-bridge/server.py:5180`, `bridges/opencode-zen-bridge/server.py:5207`, `bridges/opencode-zen-bridge/server.py:6265`, `bridges/opencode-zen-bridge/server.py:6278`.  
Правило: RW-015/016, REQ-009, `R-BULK-I3`. Evidence: `attempt_done(True, False)` вызывается для HTTP 429, но отсутствует на ветках transient SSE error и prompt 5xx. Полученные `transient_error=True` и retry сами по себе breaker не обновляют.  
Исправление: централизовать учёт исхода попытки, ровно один раз увеличивая соответствующий health/breaker. Проверка: серии 429/5xx/transport SSE failures открывают upstream breaker, не повышая serve-health за модельный отказ.

**F-019 — priority=blocking — оракулы не подтверждают заявленную полноту исправлений.**  
locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:489`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:508`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:587`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:639`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:787`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:830`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:863`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:873`.  
Правило: RW-025/028, REQ-020, `testing.md` «Зелёный прогон ≠ корректно», §7.2. Evidence: `upstream_end_t = elapsed` означает конец клиентского ответа; даже буферизованный ответ проходит сравнение. Proxy проверяется через `callable`, fallback — чтением декларативной таблицы, foreign-session — маппером. Red AC-026 падает в `setUp` из-за отсутствия `DYNAMIC_CONFIG_PATH`.  
Исправление: добавить независимый upstream-end/timestamps; проверки интервалов и overhead; три serve-watchdog и legacy first-token/stall; JSON serve/retries; FIN/RST; cleanup/parent death/PID reuse; частичный handshake; конкурентные старты/порты; реальную ротацию; secret-log oracle; disable-file; HTTP-status/health/breaker матрицу; step-interruption на serve; terminal после text tool call; retry-разделители и dedup; сохранение первых метрик. Детерминированные переходы проверять FakeClock.  
Проверка: каждый указанный дефект воспроизводится своим тестом, а traceability ссылается на конкретное утверждение, не на зелёный модуль целиком.

**F-020 — priority=non-blocking — usage не всех попыток попадает в итог.**  
locations: `bridges/opencode-zen-bridge/server.py:5167`, `bridges/opencode-zen-bridge/server.py:5228`, `bridges/opencode-zen-bridge/server.py:6259`, `bridges/opencode-zen-bridge/server.py:6284`.  
Правило: FU-004, REQ-014 SHOULD. Evidence: SSE суммирует usage на части watchdog-retry, JSON делает `continue` без аккумуляции, transient recovery также пропускает учёт.  
Исправление: суммировать usage завершённых шагов перед каждым retry. Проверка: две попытки с известными tokens дают их сумму. Сохраняю согласованный non-blocking приоритет.

**F-021 — priority=blocking — новый тестовый код нарушает явный запрет TestCase.**  
locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:773`; также классы legacy/serve нового модуля с `setUp/tearDown` — [pre-existing] относительно дельты цикла.  
Правило: приложенный `agents/testing.md`: «Не использовать unittest.TestCase, setUp, tearDown». Evidence: новый `TestReworkUnits(unittest.TestCase)` продолжает запрещённую структуру; runtime-ограничение stdlib не запрещает pytest из dev-зависимостей.  
Исправление: новый модуль оформить pytest-тестами и фикстурами; сохранить изоляцию env и ресурсов. Проверка: новый модуль не содержит TestCase/setUp/tearDown, полный pytest остаётся зелёным.

**F-022 — priority=blocking — прокси-пул продвигается дважды на одну serve-попытку.**  
locations: `bridges/opencode-zen-bridge/server.py:1696`, `bridges/opencode-zen-bridge/server.py:2831`, `bridges/opencode-zen-bridge/server.py:5119`, `bridges/opencode-zen-bridge/server.py:6228`.  
Правило: RW-001, REQ-013, AC-018. Evidence: вызывающий код сначала вычисляет `_next_standalone_proxy()`, затем `_serve_one_attempt()` вызывает `_serve_env()` → замороженный `_run_env()`, который для standalone снова выбирает proxy. После этого второй выбор затирается первым. Для пула `[A,B]` фактически используемый proxy последовательных попыток может быть `[A,A]`.  
Исправление: оставить ровно одну точку потребления прокси-пула на попытку, не меняя frozen `_run_env`. Проверка: пул из двух записей, две реальные попытки → разные фактически переданные proxy, счётчик выбора равен числу попыток.

**F-023 — priority=non-blocking — диагностическая история lsof растёт без ограничения [pre-existing].**  
locations: `bridges/opencode-zen-bridge/server.py:1433`, `bridges/opencode-zen-bridge/server.py:2347`.  
Правило: ограниченность runtime-буферов, `HL-ENV-01`. Evidence: каждый lookup добавляет порт в глобальный `_LSOF_CALLS`, очистки или предела нет; polling повторяет добавления.  
Исправление: убрать production-историю, заменить счётчиком либо ограниченным буфером; тестам использовать внешний spy. Проверка: размер диагностического состояния не растёт с числом запросов.

Повторный self-sweep выполнен по всем 14 подкатегориям; обнаруженные замечания включены выше.

1. SUB Корректность/логика: FAIL — timeout/client_gone допускаются в success, JSON fallback превышает cap (`S:3252`, `S:6249`, `S:6498`; F-001/F-005).
2. SUB Корректность/граничные условия: FAIL — пауза SSE и пул из двух proxy нарушают ожидаемое поведение (`S:2955`, `S:2831`; F-002/F-022).
3. SUB Корректность/обработка ошибок: FAIL — prompt-status зависит от SSE-очереди, delivery latch неустойчив (`S:3053`, `S:3063`; F-003/F-004).
4. SUB Полнота/покрытие AC: FAIL — AC-001/002/026 не имеют независимого временного оракула (`T:489`; F-019).
5. SUB Полнота/пропущенные ветки: FAIL — JSON retries, disconnect, watchdog и lifecycle-матрица не покрыты (`T:450`, `T:773`; RW-025, F-019).
6. SUB Реализуемость/общее: FAIL — ранние утечки, удержание gate и неполная уборка группы (`S:2508`, `S:6203`, `S:2444`; F-009–F-012).
7. SUB Риски/безопасность: FAIL — reaper не доказывает идентичность helper перед сигналом (`S:2639`, `S:2660`; F-016).
8. SUB Риски/данные: FAIL — возможны потеря поздних дельт и дубли JSON tool calls (`S:2955`, `S:6323`, `S:6344`; F-002/F-008).
9. SUB Риски/прод: FAIL — RST и смерть родителя не гарантируют своевременную остановку работы (`S:4955`, `S:195`, `S:232`; F-011/F-013).
10. SUB Риски/regression red→green: FAIL — общий RED есть, но AC-026 падает на setup, а его временное утверждение допускает буферизацию (`T:469`, `T:489`; execution-evidence.md, F-019).
11. SUB Риски/Full Suite (L2): PASS — независимый компонентный прогон: 408 passed; корневой: 894 passed, 5 skipped; обратный порядок: 408 passed (execution-evidence.md, VER-001/003/AC-023).
12. SUB Риски/scope-diff: PASS — ровно три разрешённых файла; frozen `_run_env` и Google Direct совпадают (candidate-manifest.json, VER-004).
13. SUB Альтернативы/общее: PASS — serve/run оправдан подтверждёнными ограничениями CLI; самописный JSON удалён (`S:1653`; F-17–F-25 ledger, RW-005).
14. SUB Соответствие контексту/общее: FAIL — новый TestCase нарушает прямое правило testing.md; lifecycle-инварианты неполны (`T:773`, `S:2508`; F-009/F-021).

ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `claude-sonnet-5-5-high`)

PANEL-NONCE: 9b7ea843db2c0ac7
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

Все изменения в Цикле 2 суждены заново. У `server.py` в кандидате нет абсолютных номеров строк, поэтому в F-блоках привязка идёт к функции и фрагменту diff.

**Сверка SEED (критерий 6):** `seed_hex` = `4222bc6fb25df1ccb65e0dca4ccd65c56ebd69d0f7b014fea07252fe8d2720db`, `SEED` = `4222bc6f`. Пересчёт SHA-256 от дословной `seed_input` совпал с манифестом. `ranked_order` при ранжировании `SHA-256(seed_hex#slot_id)` совпал: claude-sonnet-5-5-high, gemini-4-argon-high, gpt-6.1-sol-high, grok-4.7-high, muse-wonder-full-1.0.

**Verify-fixed по RW-001..RW-032 (кратко):**
- Закрыты:
  - RW-002, RW-005, RW-007;
  - RW-013 (`can_spawn`), RW-014, RW-021, RW-024 (`_client_gone_check` в JSON-пути);
  - RW-027, RW-029, RW-030, RW-031, RW-032.
- Не закрыты или закрыты формально:
  - RW-001: тест ротации прокси сводится к `callable(...)`;
  - RW-008: `timeout` не классифицируется вызывающим кодом;
  - RW-009: фикс уведомлением через `settimeout(0.5)` с `continue` ломает чтение SSE (F-01);
  - RW-011: статусный таймер дублирует статусы и пишет без синхронизации (F-06);
  - RW-015: HTTP-статус `prompt` не доходит до классификации по таблице (F-05);
  - RW-018: AC-014 нарушается дублирующим статусом (F-06);
  - RW-019: утечки до создания lease (F-03);
  - RW-020: `join` потоков есть, но спин читателя остаётся (F-01);
  - RW-025: поведенческие оракулы не добавлены (F-07);
  - RW-026: подавления `pyright` заменены шаблонными (F-11);
  - RW-028: порог первого статуса не ужесточён.

Результаты L2 взяты из `execution-evidence.md`:
- RED: rc=1, 24 из 29 тестов падают на `origin/dev`.
- GREEN: pytest 408 passed, unittest OK, прогон в обратном порядке OK.
- Замороженные функции совпали.

Тесты я не запускал. `VER-006` и `VER-007` помечены `DEFERRED_L3`, живое поведение против реального `opencode serve` не проверено.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Читатель SSE ломается при любой паузе апстрима дольше 0,5 с (F-01). Истечение общего дедлайна и `client_gone` в JSON-пути трактуются как успех (F-02). Таблица `FALLBACK_DECISION_TABLE` и фактические переходы расходятся (F-05).
   СОВЕТЫ (при FAIL):
   - F-01: убрать короткий `settimeout` у SSE-сокета. Использовать блокирующее чтение и закрывать сокет из основного потока по `stop_event`. Либо ждать `select` на сокете до `readline`.
   - F-02: добавить в обработку результата ветки `timeout` и `client_gone`.
   - F-05: опрашивать `prompt_status` на каждой итерации цикла, а не только после получения события.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Нет поведенческих оракулов для AC-001, AC-002, AC-020, serve-watchdog'ов, JSON-пути serve, `client_gone` и ротации прокси (F-07). Не обработаны пути `timeout` и `client_gone` в JSON (F-02).
   СОВЕТЫ (при FAIL):
   - Добавить тесты по списку из F-07.
   - Закрыть ветки из F-02.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Спин-цикл читателя на любой ошибке сокета сжигает ядро и скрывает EOF (F-01). `_StartupGate` держится весь `_serve_one_attempt` и вообще не освобождается в JSON-пути при успехе (F-04). Локальный отказ `Popen` уходит в общий `except OSError` как «client gone» (F-03).
   СОВЕТЫ (при FAIL):
   - Освобождать gate сразу после готовности serve или первого события, как делает legacy-путь на первой строке stdout.
   - Конвертировать `OSError` в `ServeUnavailable`.
   - Выдавать sentinel `None` при любой фатальной ошибке сокета.

4. РИСКИ: VERDICT=FAIL
   WHY=Утечки `lifeline_w`, порта в `_ACTIVE_SERVE_PORTS` и каталога состояния при раннем отказе (F-03). Предсказуемый каталог lease в `/tmp` (F-08). Узкие места бюджета ресурсов не подтверждены нагрузочным прогоном (L3 отложен).
   СОВЕТЫ (при FAIL):
   - Обернуть всё от `mkdtemp` до `_ServeLease` в единый `try`.
   - Перенести каталог lease под пользовательский каталог и проверять владельца и права через `lstat`.
   - Провести живой L3 до приёмки.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбор «serve на запрос плюс откат на run» повторяет прецедент muse-bridge (ADR-0004) и сохраняет kill-switch. Прямой HTTP-SSE к Zen без заголовков CLI дал 429, поэтому не годится. Замечание о дублировании механизмов статусов оформлено как дефект F-06, а не как вопрос выбора пути.
   СОВЕТЫ (при FAIL): нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Сверка SEED: `seed_hex` = `4222bc6f…720db`, `SEED` = `4222bc6f`, `ranked_order` совпал с манифестом; независимый пересчёт совпал, в роли места №1 расхождений не нашёл. Замечания по соответствию правилам проекта:
   - около 100 одинаковых `# pyright: ignore[...] — причина: <шаблон>` в новом тестовом файле (F-11);
   - format-only правки в унаследованном коде и смена `CATALOG_SOURCE` (F-10);
   - единый механизм ошибок для 404 без проверки версии (F-09).
   Внешний HTTP-контракт моста сохранён.
   СОВЕТЫ (при FAIL):
   - Убрать шаблонные подавления и типизировать нормально.
   - Сократить format-only hunks в `server.py`.
   - Пересмотреть `CATALOG_SOURCE`.

**F-блоки**

F-01 [blocking, КОРРЕКТНОСТЬ/РЕАЛИЗУЕМОСТЬ]
- Место: `server.py::_serve_one_attempt._reader`, примерно после выставления `sse_conn.sock.settimeout(0.5)`.
- Правило: REQ-001, REQ-006, REQ-007, RW-009, RW-020, T-LIFE/v1.
- Evidence: `except (TimeoutError, OSError): ... continue`. В CPython после первого `socket.timeout` объект `SocketIO` помечается `_timeout_occurred`, и любое следующее чтение бросает `OSError("cannot read from timed out object")`. Читатель уходит в бесконечный холостой цикл на 100% CPU и больше не выдаёт событий; EOF-sentinel `None` не ставится. По `F-19` пауза между `execution.started` (233 мс) и первой дельтой размышления (1811 мс) превышает 0,5 с. Тесты этого не ловят: `test_slow_serve_gets_status_and_no_status_on_fast` проверяет только наличие статуса, а `test_ac026` использует интервалы 0,12 с. Утверждение основано на моём знании реализации CPython и не подтверждено запуском.
- Исправление:
  - не использовать короткий таймаут чтения на сокете, у которого после этого продолжается `readline`;
  - читать блокирующе, а завершение инициировать закрытием сокета из основного потока;
  - при любой иной фатальной `OSError` ставить `None` и выходить;
  - не допускать цикла без ожидания.
- Критерий: новый тест с FakeServe, у которого между `server.connected` и первой дельтой пауза 1,5 с, получает все дельты. Второй тест роняет сокет сервера и обнаруживает EOF не позже чем через 1 с.

F-02 [blocking, КОРРЕКТНОСТЬ/ПОЛНОТА]
- Место: `server.py::Handler._run_serve_stream_attempts` и `_serve_json_serve`, ветки после `_serve_one_attempt`.
- Правило: REQ-006, REQ-009, RW-008.
- Evidence: `_serve_one_attempt` возвращает `exit_reason="timeout"` и `"client_gone"` без `terminal`. Вызывающий код обрабатывает только `first_event_timeout`, `first_token_timeout`, `stall_timeout`, `invalid_serve_event`, статусы `prompt` и `client_gone` в потоковом пути. Результат `timeout` проваливается в `res.serve_health.record_success()`, `attempts.attempt_done(False, True)` и `finish_reason=stop` с `[DONE]`. В JSON-пути `client_gone` тоже падает в этот успех.
- Исправление: явно обработать `timeout` (ошибка клиенту, `exit_reason=timeout`, без `record_success`) и `client_gone` в JSON-пути.
- Критерий: тест с дедлайном 1 с и молчащим serve даёт `exit_reason=timeout` и не вызывает `record_success`.

F-03 [blocking, РЕАЛИЗУЕМОСТЬ/РИСКИ]
- Место: `server.py::_serve_one_attempt` (`_serve_env` с `mkdtemp`, затем `_spawn_serve` вне `try`) и `_spawn_serve` (участок `Popen` до создания `_ServeLease`).
- Правило: RW-019, REQ-008, T-LIFE/v1, C-MULT-I4.
- Evidence:
  - отказ `Popen` (`OSError`) и `"no free serve port"` происходят до создания lease;
  - `lifeline_w` не закрывается, порт остаётся в `_ACTIVE_SERVE_PORTS` навсегда, каталог `zen-serve-state-*` не удаляется;
  - `OSError` не конвертируется в `ServeUnavailable`, а потоковый обработчик перехватывает его как «client gone mid-stream»: клиенту ни ошибки, ни отката на `run`.
- Исправление: один `try/finally` от `mkdtemp` до выхода из `_spawn_serve` с очисткой всего перечисленного. `OSError` при запуске превращать в `ServeUnavailable`.
- Критерий: тест с подменённым `Popen`, бросающим `OSError`, показывает откат на `run`, ноль утечек FD, пустой `_ACTIVE_SERVE_PORTS` и удалённый state-каталог.

F-04 [blocking, РЕАЛИЗУЕМОСТЬ/РИСКИ]
- Место: `server.py::_run_serve_stream_attempts` (`gate.acquire()`, `gate.release()` после `_serve_one_attempt`) и `_serve_json_serve` (`_gate_j`).
- Правило: S-HERD-I1, REQ-013, REQ-004.
- Evidence: legacy-путь освобождает gate на первой строке stdout (`F-10`). В serve-пути он удерживается на всё время попытки. В JSON-пути `_gate_j.release()` не вызывается при успешном возврате, а вызывается только при исключениях и отказе limiter. Остальные запросы ждут `STARTUP_WAIT_S=5` с и идут без замка. Это задержка запуска model-вызова при параллельной нагрузке. Внутреннее устройство `_StartupGate` в пакете не приложено, оценка условна.
- Исправление: освобождать gate после готовности serve или первого события, как legacy. Добавить `finally` в JSON-пути.
- Критерий: два параллельных запроса стартуют менее чем за 1 с друг от друга. Счётчик `acquire`/`release` в тесте равен.

F-05 [blocking, КОРРЕКТНОСТЬ]
- Место: `server.py::_serve_one_attempt` (проверка `prompt_status` после `events.get`) и `_serve_http`.
- Правило: RW-015, `FALLBACK_DECISION_TABLE`, REQ-009.
- Evidence:
  - классификация `_ps` выполняется только после успешного `events.get()`; при пустой очереди идёт `continue`, и ошибка HTTP может ждать до `first_event_timeout` (20 с);
  - `_serve_http` читает тело целиком, поэтому `headers_at` ставится после тела;
  - для 429/5xx `delivered` считается по наличию токенов, а таблица говорит «headers received → DELIVERED=true → serve_retry»;
  - в режиме auto такой отказ без токенов приводит к откату на `run` вопреки таблице.
- Исправление: проверять `prompt_status` в каждой итерации цикла, до `events.get`. Заводить `delivered` по получению заголовков ответа.
- Критерий: поведенческие тесты по строкам таблицы (429, 5xx, 400, 401) проверяют фактические переходы `serve_health` и `breaker`, а не поиск строки в таблице.

F-06 [blocking, ПОЛНОТА/РИСКИ]
- Место: `server.py::_run_serve_stream_attempts` (`_initial_status_timer`, `on_status`, `last_reasoning`).
- Правило: REQ-005, REQ-009 (AC-014), RW-011.
- Evidence:
  - `threading.Thread(target=_initial_status_timer)` пишет в `wfile` без синхронизации с основным потоком; при совпадении по времени кадры SSE могут перемешаться;
  - таймер не отменяется при завершении попытки: он может записать после `[DONE]`;
  - на повторе `_model_seen` новый, `_wait` отрицательный, поэтому `STATUS_INITIAL` выдаётся мгновенно в начале каждой попытки; вместе со строкой «Повтор попытки» между попытками уже две статусные строки, а не одна (AC-014);
  - внутри `_serve_one_attempt` `STATUS_INITIAL` выдаётся ещё раз (`_status_emitted[0]==0`);
  - `last_reasoning` читается из двух потоков и не обновляется после статуса.
- Исправление: единый замок на запись в `wfile`, единый источник статусов, отмена таймера в `finally`, `STATUS_INITIAL` ровно один раз на запрос.
- Критерий: тест на двух попытках получает ровно один `STATUS_INITIAL` и одну строку «Повтор попытки». Тест на гонку пишет только корректные кадры.

F-07 [blocking, ПОЛНОТА/РИСКИ]
- Место: `tests/test_realtime_reasoning.py` (`test_ac026...`, `test_serve_health_and_fallback_table`, `test_spawn_cap_and_proxy_rotation_helpers`, `test_native_tool_and_permission_reject`, `test_dynamic_config_switch_same_server`, `test_slow_serve_gets_status_and_no_status_on_fast`, `test_helper_argv_validation_and_lease_dir`).
- Правило: RW-025, REQ-020, AC-001, AC-002, AC-020, REQ-001..REQ-016.
- Evidence:
  - AC-001 не проверен: тест проверяет разброс < 2,0 с, а не интервал < 500 мс; AC-002 не проверен;
  - в FakeServe есть режимы `__never_event__` и `__silent__`, но тестов serve-watchdog'ов (`first_event_timeout`, `first_token_timeout`, `stall_timeout`) нет;
  - нет тестов JSON-пути serve, `client_gone`, отсутствия пароля в логах (AC-020), реальной ротации прокси (проверяется только `callable(...)`), поведения строк `FALLBACK_DECISION_TABLE`;
  - тест permission проверяет только наличие `bash`, но не reject и не interrupt;
  - тест «dynamic config» проверяет читатель, но не маршрут;
  - успешный запуск helper с 6 аргументами и размещением lease не тестируется;
  - тест на «чужой sessionID» проверяет маппер, а не отбрасывание в цикле;
  - на `AC-005`, `AC-026` нет теста на медленный апстрим со статусом на живом сокете в serve-пути (только `__slow__` без проверки контента);
  - не могу проверить, продвигается ли пул прокси дважды за попытку (в `_run_env` и при явной передаче `proxy_url`).
- Исправление: добавить перечисленные тесты как нетривиальные оракулы.
- Критерий: каждый REQ-001..REQ-020 и AC-001..AC-026 имеет прямой тест, красный на сломанной реализации.

F-08 [non-blocking, РИСКИ]
- Место: `server.py` (`LEASE_DIR`, `_spawn_serve`, `_run_serve_helper_cli`, `_startup_reaper`).
- Правило: `agents/security.md` (предсказуемые пути в `/tmp`), T-LIFE/v1.
- Evidence: `/tmp/opencode-zen-bridge-leases` создаётся с `mode=0o700`, но существующий каталог не проверяется на владельца и не-symlink; `OSError` у `os.chmod` игнорируется. `owner_uid` и PID берутся из содержимого файла и самоопределяемы.
- Исправление: хранить lease под пользовательским каталогом (например `~/.dsh/...`). Проверять `lstat` на владельца, режим и отсутствие symlink до записи и чтения.
- Критерий: тест с чужим или symlink-каталогом возвращает отказ.

F-09 [non-blocking, РЕАЛИЗУЕМОСТЬ]
- Место: `server.py::_serve_one_attempt` (ветки `status in (400, 404, 422)` на ready/create/event).
- Правило: R-BULK-I3, F-DEG.
- Evidence: любой 404 на `GET /api/session/active` трактуется как `ServeSecurityError` (fail-closed без отката на `run`, без sticky-деградации). Обновление `~/.opencode/bin/opencode` с изменением маршрутов API выключит весь serve-путь с ошибкой клиенту, а не с откатом.
- Исправление: проверка версии через `GET /api/info` до сессии. Несовместимость маршрута до доставки трактовать как `ServeUnavailable` с записью в `serve_health`. Оставить fail-closed для 401/403.
- Критерий: тест с FakeServe, у которого `/api/session/active` отвечает 404, получает откат на `run` и рост `serve_health`.

F-10 [non-blocking, scope-diff]
- Место: `server.py` (format-only hunks в `_UpstreamBreaker`, `Run._execute_once`, `Handler._stream_sse`, `_serve_json`, `_RequestAttempts` и др.; `CATALOG_SOURCE = "init"` → `"static"`, `_set_catalog_source`); `tests/test_step_interruption.py:67` (`r'''` → `r"""`).
- Правило: FU-006, `agents/scope-and-contracts.md` (минимально достаточные изменения), `agents/code.md`.
- Evidence: в дельте Цикла 1→2 reformatting только вырос. Изменено начальное значение публичной константы `CATALOG_SOURCE`.
- Исправление: откатить format-only hunks вне логики. Либо обосновать `CATALOG_SOURCE`, либо вернуть `init`.
- Критерий: `git diff --stat` не содержит правок строк, не связанных с serve/watchdog. Тест `test_catalog_mode` зелёный.

F-11 [non-blocking, СООТВЕТСТВИЕ КОНТЕКСТУ]
- Место: `tests/test_realtime_reasoning.py` (около 100 строк `# pyright: ignore[...] — причина: тест проверяет приватный/динамический API моста, тип уточнён аннотациями вокруг`).
- Правило: `python-standards.md` запрет №9, RW-026.
- Evidence: идентичная шаблонная «причина» не объясняет конкретное подавление. `VER-004` проверяет отсутствие `pyright: ignore` только в изменённых диапазонах `server.py` и `test_step_interruption.py`, а новый файл просто «ноль диагностик» благодаря подавлениям.
- Исправление: типизировать (`cast`, Protocol, публичные хелперы) вместо подавления. Оставшиеся подавления сопровождать конкретной причиной.
- Критерий: число подавлений в новом файле существенно меньше, у каждого осмысленная причина.

F-12 [non-blocking, КОРРЕКТНОСТЬ]
- Место: `server.py::_run_serve_helper_cli._fd_ready`.
- Правило: RW-023, T-LIFE/v1.
- Evidence: `errno` импортируется только в `else`-ветке (после раннего выхода helper), а `_fd_ready` использует `errno.EAGAIN` при `OSError` вне `BlockingIOError`. При `EBADF` на fd 0 получим `NameError` вместо чистого завершения.
- Исправление: импортировать `errno` в начале модуля.
- Критерий: тест с закрытым fd 0 завершает helper кодом 0 с чисткой группы.

F-13 [non-blocking, ПОЛНОТА]
- Место: `server.py::_run_serve_stream_attempts`, `_serve_json_serve` (ветки `prompt_status`, транзиентная ошибка, `invalid_serve_event`; мёртвая переменная `_seen_tc`).
- Правило: FU-004 (REQ-014), RW-018.
- Evidence: usage неуспешных попыток копится только в одной ветке потокового пути и нигде в JSON. `_seen_tc` вычисляется и не используется, комментарий над ним ничего не реализует.
- Исправление: накапливать usage по всем веткам `continue`. Удалить мёртвый код.
- Критерий: тест с двумя попытками получает сумму usage в финальном чанке.

F-14 [non-blocking, ПОЛНОТА] [sweep]
- Место: `server.py::_run_serve_stream_attempts` (`_delivered_err = bool(collected_texts or result.get("texts"))`).
- Правило: REQ-009 (AC-014), REQ-005.
- Evidence: доставка, состоящая только из размышления, не считается «доставленной». Транзитная ошибка после размышления уходит в откат на `run`, и клиент получает размышление повторно без разделителя `[мост]`.
- Исправление: учитывать `reasonings` в `_delivered_err`. При откате на `run` после выданного размышления вставлять одну статусную строку.
- Критерий: тест с ошибкой после трёх дельт размышления не дублирует их и выдаёт ровно один разделитель.

**Подкатегории (14):**

SUB Корректность/логика: FAIL — `server.py::_serve_one_attempt._reader` (F-01); обработка `timeout` (F-02).
SUB Корректность/граничные условия: FAIL — `settimeout(0.5)` против паузы 1,5–1,8 с (F-01, `F-19`); дедлайн (F-02).
SUB Корректность/обработка ошибок: FAIL — `Popen OSError` попадает в «client gone» (F-03); HTTP-статус `prompt` классифицируется с задержкой (F-05).
SUB Полнота/покрытие AC: FAIL — AC-001, AC-002, AC-020 и serve-watchdog'и без оракулов (F-07).
SUB Полнота/пропущенные ветки: FAIL — `timeout`/`client_gone` в JSON (F-02), статусы (F-06), размышление-только доставка (F-14).
SUB Реализуемость/общее: FAIL — спин читателя и удержание gate (F-01, F-04).
SUB Риски/безопасность: FAIL — предсказуемый `/tmp`-каталог lease с самоопределяемым `owner_uid` (F-08, non-blocking).
SUB Риски/данные: PASS — `OPENCODE_DB=:memory:`, allowlist окружения и случайный пароль (`_serve_env`, `execution-evidence.md` EVD-072).
SUB Риски/прод: FAIL — утечки FD/порта/каталога и неотменённый статусный поток (F-03, F-06); живой L3 отложен (`DEFERRED_L3`).
SUB Риски/regression red→green: PASS — `l2-red.log` rc=1, 24 падения на `origin/dev`; GREEN rc=0 (`code-gate.json`).
SUB Риски/Full Suite (L2): PASS — `l2-green-ver001/002/003/003b/ac023`: 408 passed, unittest OK, обратный порядок OK.
SUB Риски/scope-diff: FAIL — format-only hunks и смена `CATALOG_SOURCE` (F-10, non-blocking).
SUB Альтернативы/общее: PASS — прецедент muse-bridge ADR-0004, kill-switch сохранён, Google-маршрут побайтово неизменён (`code-gate.json`).
SUB Соответствие контексту/общее: FAIL — шаблонные `pyright: ignore` и унаследованный reformatting (F-09, F-10, F-11, non-blocking кроме части F-09 по версионной проверке).

ОБЩИЙ ВЕРДИКТ: NEEDS WORK


---

## Раунд D1 (`panel/council/r13`)

### Seat 1 (`skeptic`, `grok-4.7-high`)

PANEL-NONCE: 69a48b2a8d5c0a6c
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

AGREE F-014 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:3254, bridges/opencode-zen-bridge/server.py:5150, bridges/opencode-zen-bridge/server.py:6247, bridges/opencode-zen-bridge/server.py:6307 — `exit_reason="timeout"` не входит в кортежи потребителей; JSON не ветвит `client_gone`; оба пути доходят до `serve_health.record_success()` и успешного ответа. Дополнение к F-002, не дубль: JSON-`client_gone` там не назван.
AGREE F-015 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:2941, bridges/opencode-zen-bridge/server.py:2959 — `sock.settimeout(0.5)` и `except (TimeoutError, OSError): continue`. После `socket.timeout` буферизованный `SocketIO` помечается и следующее чтение бросает `OSError("cannot read from timed out object")`; цикл крутится вхолостую. Пауза до первой дельты ~1.5 с (F-19) больше 0.5 с. Тесты с шагом 0.12 с это не ловят.
DISPUTE F-016 — класс: duplicate_of:F-003 — контр-evidence: bridges/opencode-zen-bridge/server.py:3053, bridges/opencode-zen-bridge/server.py:3022 — `queue.Empty: continue` до `prompt_status` и ранний `first_event_timeout` до `ServeSecurityError` уже в F-003.
AGREE F-017 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:2385, bridges/opencode-zen-bridge/server.py:3063, bridges/opencode-zen-bridge/server.py:5202 — `headers_at` ставится после полного `resp.read()`, `delivered` пересчитывается по токенам и может сброситься; ветка transient считает только `texts`. Это другой root cause, чем момент классификации в F-003.
AGREE F-018 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:6195, bridges/opencode-zen-bridge/server.py:6498, bridges/opencode-zen-bridge/server.py:4700, bridges/opencode-zen-bridge/server.py:4712 — потоковый fallback проверяет потолок на `server.py:5639`; JSON-`while True` после `return False` из `_serve_json_serve` запускает `Run.execute()` без `can_spawn()`. `_execute_once` делает `Popen` до `note_spawn()`. Две serve-попытки плюс `ServeUnavailable` плюс fallback дают четвёртый запуск.
AGREE F-019 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:3238 — `terminal="tool_calls"` только при непустом `result["native_calls"]`. Вызов из `ToolCallParser` туда не попадает, чтение следующего шага продолжается.
AGREE F-020 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5207, bridges/opencode-zen-bridge/server.py:5255 — `continue` на transient/unmapped/incomplete без общей строки «Повтор попытки»; разделитель есть только на части watchdog/HTTP-веток.
AGREE F-021 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:6323, bridges/opencode-zen-bridge/server.py:6344 — текстовые и native-вызовы одной попытки независимо кладутся в `tool_calls_all` с разными `call_*`. Это не мёртвый `_seen_tc` из F-004.
DISPUTE F-022 — класс: duplicate_of:F-006 — контр-evidence: bridges/opencode-zen-bridge/server.py:1718, bridges/opencode-zen-bridge/server.py:2500, bridges/opencode-zen-bridge/server.py:2505 — `mkdtemp`, порт, pipe и `Popen` до `_ServeLease` и `except BaseException` уже в F-006. Строка 1713 в RECHECK — `XDG_DATA_HOME`, не место утечки.
AGREE F-023 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5092, bridges/opencode-zen-bridge/server.py:5136, bridges/opencode-zen-bridge/server.py:6203, bridges/opencode-zen-bridge/server.py:6207 — SSE отпускает gate только после всего `_serve_one_attempt`; JSON вызывает `_gate_j.release()` на limiter/`ServeUnavailable`/`ServeSecurityError` и не вызывает на обычном возврате. SSE-удержание до конца генерации — сверх F-005.
AGREE F-024 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:197, bridges/opencode-zen-bridge/server.py:231 — `SIGKILL` группы только если `serve_proc.poll() is None`. Если прямой `serve` уже умер, а внук игнорирует `SIGTERM`, эскалации нет, и lease снимается по смерти прямого потомка. Это не условие `unlink` из F-007.
AGREE F-025 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:2432, bridges/opencode-zen-bridge/server.py:2444 — один `_deadline = monotonic()+5.0` тратится на ожидание `SIGTERM`; цикл после `SIGKILL` смотрит на тот же уже истёкший срок. `_closed=True` ставится до подтверждения смерти группы.
DISPUTE F-026 — класс: duplicate_of:F-008 — контр-evidence: bridges/opencode-zen-bridge/server.py:4954 — `except (OSError, ValueError): return False`; `ConnectionResetError` есть `OSError`. Та же ветка уже в F-008.
AGREE F-027 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5079, bridges/opencode-zen-bridge/server.py:5087 — daemon-таймер пишет в `wfile` без замка и без отмены в `finally`; на каждой попытке новый `_model_seen`, поэтому `STATUS_INITIAL` повторяется вместе со строкой повтора.
AGREE F-028 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5649, bridges/opencode-zen-bridge/server.py:5743 — часы статуса legacy создаются после `gate.acquire()` и spawn; первый видимый чанк не гарантирован за 1.0 с, пока gate занят до 5 с. Таймер до gate есть только у serve.
DISPUTE F-029 — класс: duplicate_of:F-012 — контр-evidence: bridges/opencode-zen-bridge/server.py:75, bridges/opencode-zen-bridge/server.py:2644 — `helper_lstart` пишется как epoch-секунды, reaper пропускает decimal-строку против `ps lstart`. Приоритет оставляю non-blocking: воспроизводимого убийства чужого PID нет.
DISPUTE F-030 — класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:98, bridges/opencode-zen-bridge/server.py:244 — `errno` читается в helper до импорта в `else` после `SystemExit`. Тот же `NameError`.
AGREE F-031 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5180, bridges/opencode-zen-bridge/server.py:5207, bridges/opencode-zen-bridge/server.py:6265 — `attempt_done(True, False)` есть на HTTP 429 и нет на transient SSE-error и prompt 5xx перед `continue`. Breaker эти отказы не видит.
DISPUTE F-032 — класс: duplicate_of:F-009 — контр-evidence: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:112, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:502 — `__never_event__`/`__silent__` без вызова, размах `< 2.0` с вместо AC-001/AC-002, `callable` прокси и таблица как данные уже в F-009. RED на `origin/dev` падает в `setUp` из-за отсутствия символов, а не на временном утверждении.
DISPUTE F-033 — класс: duplicate_of:F-011 — контр-evidence: bridges/opencode-zen-bridge/server.py:6260, bridges/opencode-zen-bridge/server.py:5166 — JSON-`continue` без суммы `usage`, stream копит usage только на части watchdog-веток. Тот же FU-004.
AMEND F-034 — priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:773; fix=не блокировать merge переписыванием модуля на pytest; follow-up отдельно, если весь мост уйдёт с unittest — причина: `testing.md` запрещает `TestCase`, но 17 модулей моста и `tests/test_step_interruption.py` в конверте уже на unittest; поведенческого дефекта нет; цикл ≥2 не даёт FAIL по стилю. Litestar-async к `ThreadingHTTPServer` не применяется.
AGREE F-035 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:1370, bridges/opencode-zen-bridge/server.py:5119, bridges/opencode-zen-bridge/server.py:6228 — NEW: строка 1696 в находке — это default политики permission, не прокси. `_run_env` (заморожен) вызывает `_next_standalone_proxy()` на 1370; вызывающий код вызывает его ещё раз и `_serve_one_attempt` затирает `HTTP(S)_PROXY`. На пуле `[A,B]` фактический прокси двух попыток может быть `[A,A]`. Фикс: одна точка потребления, `_run_env` не трогать — убрать лишний вызов на 5119/6228.
AGREE F-036 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:1433, bridges/opencode-zen-bridge/server.py:2345 — каждый `lsof` делает `_LSOF_CALLS.append(port)` без предела. Non-blocking: на ответ клиенту не влияет.
DISPUTE F-037 — класс: duplicate_of:F-015 — контр-evidence: bridges/opencode-zen-bridge/server.py:2941, bridges/opencode-zen-bridge/server.py:2959 — тот же `settimeout(0.5)` и `continue` на `TimeoutError`/`OSError`.
DISPUTE F-038 — класс: duplicate_of:F-014 — контр-evidence: bridges/opencode-zen-bridge/server.py:3254, bridges/opencode-zen-bridge/server.py:6307 — `timeout` и JSON-`client_gone` падают в `record_success` уже в F-014.
DISPUTE F-039 — класс: duplicate_of:F-006 — контр-evidence: bridges/opencode-zen-bridge/server.py:2505, bridges/opencode-zen-bridge/server.py:2599 — `Popen` до lease и cleanup только после создания lease уже в F-006; `OSError` запуска не становится `ServeUnavailable`.
DISPUTE F-040 — класс: duplicate_of:F-023 — контр-evidence: bridges/opencode-zen-bridge/server.py:5136, bridges/opencode-zen-bridge/server.py:6203 — удержание gate на всю попытку SSE и отсутствие release в JSON на успехе уже в F-023.
DISPUTE F-041 — класс: duplicate_of:F-017 — контр-evidence: bridges/opencode-zen-bridge/server.py:3063, bridges/opencode-zen-bridge/server.py:2385 — защёлка `delivered` по токенам вместо заголовков и чтение тела до `headers_at` уже в F-017; опрос статуса после `events.get` — F-003.
DISPUTE F-042 — класс: duplicate_of:F-027 — контр-evidence: bridges/opencode-zen-bridge/server.py:5087 — неотменяемый таймер, запись в `wfile` и повторный `STATUS_INITIAL` уже в F-027.
DISPUTE F-043 — класс: duplicate_of:F-009 — контр-evidence: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:502, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:871 — те же дыры оракулов AC-001/AC-002/AC-020, watchdog serve, JSON, `client_gone`, ротация прокси.
AGREE F-044 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:1388 — `LEASE_DIR=/tmp/opencode-zen-bridge-leases`, `chmod` при `OSError` пропускается, `owner_uid` берётся из содержимого файла. Каталог 0700 и сверка UID уже есть; symlink/`lstat` — follow-up, не blocking.
DISPUTE F-045 — класс: invalid — контр-evidence: `FALLBACK_DECISION_TABLE`, фаза ANY, событие «HTTP400/404/422 invalid request», action `fail_closed`; RW-015 — 404 на `/api/session/active` как `ServeSecurityError` задан таблицей, а не дефект. Проверка версии через `/api/info` — отдельный follow-up, не смена fail-closed для 401/403.
AMEND F-046 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py, bridges/opencode-zen-bridge/tests/test_step_interruption.py:69; fix=косметический откат format-only hunks допустим как FU-006; `CATALOG_SOURCE` не возвращать в `init` — причина: пакетный VER-004 требует `CATALOG_SOURCE=='static'` и `_set_catalog_source`; откат сломает зелёный гейт. `test_catalog_mode` 8 OK.
AGREE F-047 rev=1 — проверил: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:264 — шаблонные `# pyright: ignore[...] — причина: тест проверяет приватный/динамический API`. VER-004: `errorCount=0` и ноль диагностик нового файла. Non-blocking: причина у подавления есть, поведенческого дефекта нет.
DISPUTE F-048 — класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:98, bridges/opencode-zen-bridge/server.py:239 — тот же `errno` до импорта helper-ветки.
DISPUTE F-049 — класс: duplicate_of:F-011 — контр-evidence: bridges/opencode-zen-bridge/server.py:6260 — usage на JSON-`continue` не суммируется; мёртвый `_seen_tc` — это F-004, не отдельный дефект учёта токенов.
AMEND F-050 — priority=blocking; locations=bridges/opencode-zen-bridge/server.py:5202, bridges/opencode-zen-bridge/server.py:5203; fix=в `_delivered_err` учитывать `reasonings` и native-вызовы; при fallback на `run` после уже отданного размышления вставлять одну строку `[мост]` — причина: bridges/opencode-zen-bridge/server.py:5202 считает доставленным только text, JSON-ветка рядом смотрит и на `reasonings`; AC-014 / REQ-009. Откат на `run` повторяет размышление без разделителя. Это не пропущенный разделитель внутри serve-retry (F-020).

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=F-001 (`NameError` на `errno` в helper), F-002 и F-014 (`timeout` и JSON-`client_gone` идут в успех), F-003 (401 prompt перекрывается `first_event_timeout`), F-015 (SSE-чтение умирает после паузы 0.5 с), F-017 (защёлка доставки сбрасывается), F-018 (четвёртый spawn в JSON-fallback), F-019 (текстовый tool call не закрывает шаг), F-004 и F-021 (дубли `tool_calls`), F-031 (5xx/transient мимо breaker), F-050 (reasoning-only не считается доставленным).
   СОВЕТЫ (при FAIL): импорт `errno` до helper; явные ветки `timeout` и `client_gone` до `record_success`; классификация `prompt_status` до watchdog; чтение SSE без отравления сокета; необратимая защёлка доставки; `can_spawn()` перед каждым `Popen`, включая JSON-fallback; `terminal` после текстового tool call; дедуп `tool_calls`; один учёт breaker на 429/5xx/transient; учитывать reasoning в барьере доставки.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=F-009: нет поведенческих оракулов AC-001/AC-002, трёх serve-watchdog, JSON-serve, `client_gone`, AC-020, ротации прокси и step-interruption на serve. F-020 и F-027: не все повторы разделены одной статусной строкой, таймер не отменяется. F-028: legacy не даёт первый видимый статус за 1.0 с при занятом gate. F-005: JSON-gate не отпускается на успехе.
   СОВЕТЫ (при FAIL): по одному нетавтологическому тесту на перечисленные AC; один источник статусов с отменой в `finally`; статусный таймер legacy до `gate.acquire()`; `try/finally` на JSON-gate.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=F-006: `mkdtemp`, порт, pipe и `Popen` вне cleanup. F-007 и F-024: lease и `SIGKILL` смотрят на прямой `serve`, не на группу. F-023 и F-025: gate держится всю попытку, бюджет cleanup кончается до подтверждения `SIGKILL`. F-035: пул прокси продвигается дважды за попытку при замороженном `_run_env`.
   СОВЕТЫ (при FAIL): один `try/finally` от каталога состояния до lease; смерть всей группы до `unlink`; раздельный бюджет TERM/KILL; отпустить gate после готовности serve; одна точка `_next_standalone_proxy` без правки `_run_env`.
4. РИСКИ: VERDICT=FAIL
   WHY=L2 зелёный и это принимаю: RED rc=1 на `origin/dev`, VER-001 408 passed, AC-023 reversed rc=0, VER-004 `errorCount=0`, frozen sha256 совпали. Это не закрывает F-008 (RST читается как «клиент жив»), F-015 (потеря дельт и холостой цикл), F-006/F-024 (сироты и утечки FD/порта), F-035 (повтор одного IP и 429). F-010 и F-036 остаются non-blocking. VER-006/VER-007 законно `DEFERRED_L3`.
   СОВЕТЫ (при FAIL): `return True` в `_client_gone_check` на терминальных `OSError`; починить SSE-reader; cleanup до возврата из `_spawn_serve`; один proxy на попытку. F-010 (`tests/test_cli_failure.py:267`) вне конверта не чинить в этом diff.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve с откатом на run закрывает RC-1 и сохраняет ротацию IP; прямой Zen без заголовков дал 429 (F-24, F-25). Переписывание тестов на pytest (F-034) и откат `CATALOG_SOURCE` (F-046) раздуванием не требуются: поведенческого выигрыша нет, VER-004 требует `static`.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Ровно три файла конверта, `dependencies = []`, замороженные `_run_env` / `_stream_google_sse` / `_execute_google_once` совпали с VER-004. Публичный каркас SSE/JSON сохранён; строки `[мост]` и поля `O-EXIT/v1` заданы REQ-004/005/016. F-045 не дефект: 400/404/422 до доставки — `fail_closed` по таблице. F-047 — non-blocking шаблонные ignore. Forbidden Scope не задет.

POSITIONS: 37/37
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `gpt-6.1-sol-high`)

PANEL-NONCE: 7fcad6fc649838f0
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

Канон `~/Мой диск/Context/AGENTS.md` прочитан целиком в сообщении до `<!-- КАНОН-КОНЕЦ -->`; проектный `AGENTS.md`, `feature.md` и профильные стандарты прочитаны в приложенных обёртках. Файлы рабочей папки не открывал, тесты не запускал. Ниже используются номера сводного леджера.

DISPUTE F-001 — класс: duplicate_of:F-030 — контр-evidence: `bridges/opencode-zen-bridge/server.py:98`, `:99`, `:239`, `:244` — подтверждаю дефект: ранний helper обращается к `errno`, импортируемому только после его завершающего dispatch. Этот root cause уже полностью зарегистрирован в F-030.

DISPUTE F-002 — класс: duplicate_of:F-014 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3254`, `:5150`, `:5237`, `:6247`, `:6307` — возвращённый `timeout` действительно проходит мимо обработки отказов к `record_success()`. F-014 содержит тот же дефект обоих consumers и дополнительно необработанный JSON `client_gone`.

DISPUTE F-003 — класс: duplicate_of:F-016 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3022`, `:3053`, `:3055`, `:3061` — HTTP-результат prompt проверяется после `events.get()`, а `queue.Empty` возвращает управление к watchdog. Это тот же дефект зависимости контрольного канала от SSE, описанный в F-016.

DISPUTE F-004 — класс: invalid — контр-evidence: `bridges/opencode-zen-bridge/server.py:6359`, `:6371`, `:6378` — перед веткой unmapped-retry стоит `if not emulate_tools or tool_calls_all: break`. Поэтому сценарий «уже добавленные tool calls сохраняются через этот retry» показанным кодом исключён. Неиспользуемый `_seen_tc` сам по себе его не доказывает. Отдельный дефект дублирования одинакового вызова из text/native в одной попытке остаётся в F-021.

DISPUTE F-005 — класс: duplicate_of:F-023 — контр-evidence: `bridges/opencode-zen-bridge/server.py:6203`, `:6231`, `:6239`, `:6243` — JSON освобождает startup gate на отдельных исключениях, но не после обычного возврата попытки. F-023 уже охватывает этот путь и удержание gate на протяжении всей SSE-генерации.

DISPUTE F-006 — класс: duplicate_of:F-022 — контр-evidence: `bridges/opencode-zen-bridge/server.py:1718`, `:2493`, `:2502`, `:2505`, `:2531`, `:2599` — state-dir, резерв порта и pipe создаются до exception-safe владельца; при отказе `Popen` закрывается только read-end. Все перечисленные утечки охвачены F-022.

AMEND F-007 — priority=blocking; locations=bridges/opencode-zen-bridge/server.py:197,bridges/opencode-zen-bridge/server.py:231,bridges/opencode-zen-bridge/server.py:232; fix=проверять и завершать остальных членов собственной группы независимо от состояния непосредственного serve-процесса; удалять lease только после подтверждения отсутствия этих потомков — причина: проверка `not _pid_alive(-os.getpgrp())` внутри живого helper никогда не станет истинной, поскольку сам helper принадлежит группе. Дефект подтверждён, но предложенный предикат исправления необходимо заменить. Сценарий оставшегося TERM-resistant внука уже отражён также в F-024.

DISPUTE F-008 — класс: duplicate_of:F-026 — контр-evidence: `bridges/opencode-zen-bridge/server.py:4938`, `:4954`, `:4955`, `:6224` — передача checker в JSON добавлена, но RST по-прежнему попадает в общий `OSError → False`. F-026 содержит этот дефект и необходимость классификации ошибки `os.dup`.

DISPUTE F-009 — класс: duplicate_of:F-032 — контр-evidence: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:112`, `:115`, `:502`, `:591`, `:640`, `:830`, `:871`, `:881` — подтверждаю перечисленные пробелы: необращённые watchdog-режимы, проверка таблицы вместо переходов, `callable` вместо ротации, отсутствие JSON/disconnect/log-оракулов. F-032 включает их и независимый сигнал завершения апстрима.

AGREE F-010 rev=1 — проверил: `bridges/opencode-zen-bridge/tests/test_cli_failure.py:267` и сырой лог `execution-evidence.md`, `VER-002-unittest` — два `ResourceWarning` действительно присутствуют при итоговом `rc=0`. Это отдельный non-blocking follow-up вне разрешённых файлов; оснований объявлять весь выполненный L2 красным или аварийным нет.

DISPUTE F-011 — класс: duplicate_of:F-033 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5166`, `:6260`, `:6271`, `:6281` — JSON retry-ветки пропускают накопление usage, SSE делает это лишь частично. Это тот же согласованный non-blocking остаток FU-004 / REQ-014 SHOULD.

DISPUTE F-012 — класс: duplicate_of:F-029 — контр-evidence: `bridges/opencode-zen-bridge/server.py:75`, `:2644`, `:2645`, `:2660` — epoch-значение helper действительно исключено из сравнения с `ps lstart`; проверка подстроки argv идентичность попытки не заменяет. F-029 уже учитывает это как незакрытый обязательный RW-003 с blocking-приоритетом.

AMEND F-013 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3215,bridges/opencode-zen-bridge/server.py:3216; fix=согласовать определение первого токена для native tool completion и применять его одинаково к watchdog-часам и ttft_ms — причина: REQ-007 определяет первый токен как reasoning/text, тогда как реализация дополнительно устанавливает `first_token_at` на native completion без `ttft_ms`. Подтверждена внутренняя непоследовательность, но обязательность числового TTFT именно для tool-only ответа из AC-021 не следует.

DISPUTE F-037 — класс: duplicate_of:F-015 — контр-evidence: `bridges/opencode-zen-bridge/server.py:2941`, `:2955` — повторное чтение буферизованного response после socket timeout и проглатывание последующего `OSError` уже описаны в F-015. Уточнение: порог 0,5 с действует, только если `sse_conn.sock` доступен и `settimeout` выполнен; иначе остаётся исходный timeout 5 с. Формулировку «любая пауза дольше 0,5 с» без этого условия не подтверждаю.

DISPUTE F-038 — класс: duplicate_of:F-014 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3254`, `:5150`, `:6247`, `:6307` — общий timeout и JSON `client_gone` действительно не отделены от успешного результата. Это полностью совпадает с F-014.

DISPUTE F-039 — класс: duplicate_of:F-022 — контр-evidence: `bridges/opencode-zen-bridge/server.py:1718`, `:2505`, `:2526`, `:2531`, `:2835` — ранний spawn расположен вне общего cleanup; его `OSError` может выйти в обработку клиентского отключения вместо `ServeUnavailable`. Совпадает с корневой причиной F-022.

DISPUTE F-040 — класс: duplicate_of:F-023 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5092`, `:5136`, `:6203`, `:6243` — startup gate освобождается слишком поздно в SSE и не освобождается обычным JSON-путём. Это тот же lifecycle-дефект F-023. Критерий «старты менее чем через секунду» следует заменить проверкой освобождения gate: допустимый интервал дополнительно определяется spawn-limiter.

DISPUTE F-041 — класс: duplicate_of:F-017 — контр-evidence: `bridges/opencode-zen-bridge/server.py:2385`, `:2997`, `:3063`, `:5208` — фиксация headers после чтения тела и пересчёт delivered по контенту уже входят в F-017. Сопутствующая зависимость проверки HTTP-status от очереди отдельно зарегистрирована в F-016.

DISPUTE F-042 — класс: duplicate_of:F-027 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3042`, `:5079`, `:5087` — неотменяемый timer, второй источник initial-status и отдельный писатель в `wfile` уже охвачены F-027. Подтверждён риск позднего/двойного статуса; повреждение байтов кадра требует отдельного воспроизведения и не является необходимым основанием этого блокера.

DISPUTE F-043 — класс: duplicate_of:F-032 — контр-evidence: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:491`, `:502`, `:508`, `:591`, `:640`, `:787`, `:871` — пробелы поведенческой матрицы совпадают с F-032. При этом утверждение об отсутствии сокетного serve-замера первого статуса некорректно: `test_slow_serve_gets_status_and_no_status_on_fast` такой замер содержит; он не проверяет последующую полноту модельного ответа.

AMEND F-044 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:1388,bridges/opencode-zen-bridge/server.py:2476; fix=проверять существующий lease-каталог через lstat: владелец, права и отсутствие symlink; при нарушении прекращать использование каталога до чтения lease и записи файлов — причина: фиксированный путь сам по себе не доказывает эксплуатацию, но `mkdir(exist_ok=True)` и игнорирование ошибки `chmod` не подтверждают доверенность уже существующего каталога. Перенос в конкретный пользовательский путь не обязателен для устранения этой проблемы.

DISPUTE F-045 — класс: invalid — контр-evidence: `FALLBACK_DECISION_TABLE`, строка «HTTP400/404/422 invalid request → fail_closed», и `bridges/opencode-zen-bridge/server.py:2882` — предлагаемое переключение любого pre-prompt 404 в fallback противоречит приложенной таблице. Проверка версии может быть отдельным развитием, но несовместимость будущей версии не является доказанным дефектом поддерживаемого v2.1.2.

AMEND F-046 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2167,bridges/opencode-zen-bridge/server.py:4585,bridges/opencode-zen-bridge/tests/test_step_interruption.py:69; fix=по возможности сократить только необязательные косметические hunks, сохранив диапазонное форматирование и frozen-срезы — причина: FU-006 уже согласован как non-blocking. Требование вернуть `CATALOG_SOURCE="init"` исключаю: `VER-004-packet-command` прямо требует `"static"` и `_set_catalog_source`, а проверка прошла. Нарушение публичного HTTP-контракта этим изменением не доказано.

AMEND F-047 — priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:290,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:294,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:306; fix=для подавлений Unknown/Any указывать конкретный источник неопределённого типа и основание безопасности либо заменять подавление типизированным адаптером; намеренный доступ тестов к private API объяснять отдельно — причина: одинаковая причина действительно не объясняет разные диагностические классы. Однако выполненные условия RW-026 — отсутствие блокового отключения, пояснения и зелёный согласованный VER-004 — не позволяют автоматически объявить весь статический гейт недействительным.

DISPUTE F-048 — класс: duplicate_of:F-030 — контр-evidence: `bridges/opencode-zen-bridge/server.py:98`, `:99`, `:239`, `:244` — тот же ранний доступ к неимпортированному `errno`; самостоятельного root cause сверх F-030 нет.

DISPUTE F-049 — класс: duplicate_of:F-033 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5166`, `:6260`, `:6281` — недоучёт usage неуспешных попыток уже зарегистрирован в F-033. Неиспользуемый `_seen_tc` не доказывает дублирование через retry из-за предшествующего `break`; отдельное same-attempt дублирование остаётся F-021.

DISPUTE F-050 — класс: duplicate_of:F-017 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5207`, `:5208` — reasoning-only доставка исключена из `_delivered_err`, что уже охвачено F-017; отсутствие разделителя охвачено F-020. Дедуплицировать reasoning нельзя: AC-014 требует сохранять его полностью и разделять попытки одной статусной строкой.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL  
   WHY=Остаются ложный успех при timeout/JSON disconnect, неустойчивый delivery barrier, зависимость prompt-status от SSE и нарушения восстановления инструментальных шагов: F-014–F-021, F-030–F-031. Дубли в леджере не увеличивают число самостоятельных дефектов.  
   СОВЕТЫ (при FAIL): обработать терминальные отказы до success; исправить возобновляемое SSE-чтение; проверять HTTP-результат независимо от очереди; сделать delivery latch необратимым; защитить каждый spawn общим бюджетом; закрывать шаг после текстовых tool calls; обеспечить разделители и семантический dedup инструментов.

2. ПОЛНОТА: VERDICT=FAIL  
   WHY=RW-025/028 закрыты неполно: тесты не доказывают интервалы AC-001, overhead AC-002, независимое завершение апстрима AC-026 и матрицу отказов нового транспорта. Сохраняется проблема первой реакции legacy при startup-ожидании: F-028, F-032.  
   СОВЕТЫ (при FAIL): добавить независимые upstream timestamps/end-marker; проверки трёх watchdog, JSON/retries, FIN/RST, lifecycle, proxy rotation, secrets, переключателей и serve step-recovery; заменить обобщённые PASS traceability ссылками на конкретные утверждения.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL  
   WHY=Транспорт технически доступен на целевой машине, внешние runtime-зависимости не нужны. Внедрение блокируют утечки раннего запуска, удержание gate, неполное завершение потомков и исчерпание cleanup-бюджета до подтверждения SIGKILL: F-022–F-025. Архитектуру целиком менять не требуется.  
   СОВЕТЫ (при FAIL): замкнуть владение ресурсами с момента их создания; освобождать startup gate после startup и в `finally`; разделить бюджеты TERM/KILL/проверки; подтвердить отсутствие потомков после смерти родителя. Оценка: 2–4 инженерных дня на исправления и 0,5–1 день на повторную проверку; доступность Zen влияет на срок L3.

4. РИСКИ: VERDICT=FAIL  
   WHY=Независимый Full Suite L2 принимаю: 408 тестов компонента, 894 корневых теста и обратный порядок зелёные. Но остаются риски потери дельт, повторной доставки, продолжения работы после RST и сигнализации чужому переиспользованному helper PID: F-015, F-017, F-026–F-029, F-031–F-032. Общий RED не доказывает чувствительность временного оракула AC-026, падающего в setup.  
   СОВЕТЫ (при FAIL): закрыть перечисленные дефекты направленными regression-оракулами; проверять конечные сокеты, группы процессов и журнал; сохранить F-010 отдельным non-blocking follow-up. VER-006/007 законно отложены до ACCEPT и самостоятельным блокером не являются.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS  
   WHY=Короткоживущий serve с резервным run соответствует подтверждённым возможностям OpenCode и необходимости ротации IP. Legacy-only не обеспечивает RC-1, общий демон усложняет ротацию, прямой Zen не подтверждён. Исправления lifecycle и классификации можно выполнить внутри выбранного решения.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL  
   WHY=Три файла конверта, stdlib-only, frozen-функции и публичные оболочки соблюдены. Однако прямой запрет нового `unittest.TestCase` остаётся нарушенным в F-034; обязательные lifecycle/deadline-оракулы неполны в F-022–F-025/F-032. Косметические hunks и пояснения подавлений сохраняю non-blocking.  
   СОВЕТЫ (при FAIL): оформить новый тестовый модуль pytest-фикстурами с гарантированной изоляцией; закрыть применимые проверки владения, освобождения ресурсов и дедлайнов. Не расширять исправления на DSH, другие мосты и замороженные функции.

POSITIONS: 27/27
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `claude-sonnet-5-5-high`)

PANEL-NONCE: 151364be527710cd
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

В `server.py` в diff нет абсолютных номеров строк. Для строк кода я ссылаюсь на функцию и фрагмент diff, для строк чекеров — на их номера.

Первая позиция моего места по чужой находке не считается сменой позиции. Смену по собственной находке F-042 оформляю с `NEW:`.

AGREE F-001 rev=1 — проверил: `_run_serve_helper_cli._fd_ready` в diff — `errno` используется в `except (OSError, ValueError)`, а `import errno` стоит только в `else` после `raise SystemExit`. Дефект подтверждён, но достижим лишь при `OSError` от `select` на fd 0 (EBADF).
AMEND F-001 — priority=non-blocking; locations=server.py:98-99,239-244; fix=перенести `import errno` в начало модуля — причина: дефект возник в дельте цикла 2, а не остался от RW. Путь достижим только при EBADF: EINTR Python повторяет сам (PEP 475). Исправление в одну строку.

AMEND F-002 — priority=blocking; locations=server.py:3254,5150,5237-5238,6247,6307-6308; fix=обработать `exit_reason=="timeout"` и `"client_gone"` в обоих потребителях до ветки успеха: без `record_success`, без `attempt_done(False,True)`, без `finish_reason=stop` и JSON 200 — причина: `_serve_one_attempt` возвращает `timeout` после выхода из `while time.monotonic() < deadline` без `terminal`. Кортежи в `_run_serve_stream_attempts` и `_serve_json_serve` этот исход не содержат. В JSON-пути `client_gone` тоже проваливается в успех.
DISPUTE F-014 — класс: duplicate_of:F-002 — контр-evidence: те же места 3252/5151/6249; `client_gone` в JSON учтён в AMEND F-002 — это один корень, один фикс.

AGREE F-003 rev=1 — проверил: `_serve_one_attempt` — `events.get(timeout=0.05)` с `except queue.Empty: continue` стоит раньше блока `_ps = prompt_status.get("status")`. `server.connected` приходит сразу, после чего очередь пуста. Ошибка prompt (401/429/5xx) ждёт `first_event_timeout` (20 с). Вместо fail-closed на 401 запрос уходит в `run`.
DISPUTE F-016 — класс: duplicate_of:F-003 — контр-evidence: server.py:3053-3057 — та же проверка `prompt_status` после `events.get`.

AMEND F-004 — priority=non-blocking; locations=server.py:6370-6378; fix=удалить мёртвую переменную `_seen_tc` вместе с вводящим в заблуждение комментарием — причина: все `continue` после extend стоят после `if not emulate_tools or tool_calls_all: break`. Значит, в `continue` на ветках unmapped и incomplete `tool_calls_all` пуст, и дублей вызовов между попытками нет. Дефект сводится к мёртвому коду.

DISPUTE F-005 — класс: duplicate_of:F-023 — контр-evidence: server.py:6203,6243 входит в более широкую F-023: тот же `_StartupGate` держится дольше фазы старта в SSE, а в JSON его release отсутствует вовсе.

AGREE F-006 rev=1 — проверил: `_serve_env` вызывает `tempfile.mkdtemp` ещё до `_spawn_serve`. В `_spawn_serve` порт добавляется в `_ACTIVE_SERVE_PORTS`, затем идут `os.pipe()` и `Popen` вне `except BaseException`; `finally` закрывает только `lifeline_r`. `OSError` от `Popen` и «no free serve port» не освобождают `lifeline_w`, порт и state-каталог. `OSError` не превращается в `ServeUnavailable`, поэтому fallback на `run` не срабатывает.
DISPUTE F-022 — класс: duplicate_of:F-006 — контр-evidence: server.py:1713,2476-2508 — тот же участок кода и тот же фикс.

AGREE F-007 rev=1 — проверил: `finally` в `_run_serve_helper_cli` — `if serve_proc.poll() is not None: lease_path.unlink()` смотрит только на прямого потомка. SIGKILL-эскалация выполняется только при живом `serve_proc`. RW-023 требовал снимать lease по смерти всей группы. Критерий приёмки RW-023 не выполнен; исправление в одну проверку `_pid_alive(-pgid)`.
DISPUTE F-024 — класс: duplicate_of:F-007 — контр-evidence: server.py:195,232 — тот же корень.

AGREE F-008 rev=1 — проверил: `_client_gone_check` на `except (OSError, ValueError): return False`. RW-024 требовал `True` для всего, кроме `BlockingIOError` и EAGAIN/EWOULDBLOCK. Критерий приёмки не выполнен, а в JSON-пути чекер — единственный способ обнаружить отключение.
DISPUTE F-026 — класс: duplicate_of:F-008 — контр-evidence: server.py:4938-4955 — тот же чекер и тот же фикс.

AGREE F-009 rev=1 — проверил: `tests/test_realtime_reasoning.py` — `__never_event__` и `__silent__` встречаются только в тексте FakeServe, тестов serve-watchdog нет. `test_ac026` проверяет разброс `<2.0` с, а не интервалы `<500` мс. `test_spawn_cap_and_proxy_rotation_helpers` проверяет `callable(...)`, `test_serve_health_and_fallback_table` — декларативную таблицу, `test_transport_matrix` не создаёт disable-файл, а `test_elf_magic_and_tool_status` ограничивается `isinstance(dict)`. Нет тестов JSON-serve, `client_gone` и AC-020. RED-прогон AC-026 падает на `AttributeError` в `setUp`, а не на временном оракуле.
DISPUTE F-032 — класс: duplicate_of:F-009 — контр-evidence: те же тесты 489-873 — один корень (неполнота оракулов), включая замечания про AC-026.

DISPUTE F-010 — класс: out_of_scope — контр-evidence: `tests/test_cli_failure.py:267` не входит в `allowed_envelope_changes` и не затронут дельтой. Это [pre-existing] вне скоупа задачи (`scope-and-contracts.md` п.2); максимум отдельный follow-up.

AGREE F-011 rev=1 — проверил: `_serve_json_serve` — ветки `allow_retry(reason)` и `prompt_status` делают `continue` без суммирования `result["usage"]`. В SSE-пути есть `_serve_stream_usage`. REQ-014 имеет уровень SHOULD, поэтому non-blocking.
DISPUTE F-033 — класс: duplicate_of:F-011 — контр-evidence: server.py:5167,6259 — тот же дефект в тех же ветках.

AGREE F-012 rev=1 — проверил: lease пишет `helper_lstart = str(int(time.time()))`, а `_startup_reaper` сравнивает только не-decimal `_ts_v`. Остаётся защита через `--serve-helper` в argv, `pgid==helper_pid` и `parent_start_ts`. Реальный риск мал, поэтому non-blocking.
DISPUTE F-029 — класс: duplicate_of:F-012 — контр-evidence: server.py:78,2639-2660 — тот же дефект; блокирующим его делать не нужно.

AGREE F-013 rev=1 — проверил: ветки `tool_event` в `_serve_one_attempt` выставляют `first_token_at`, но не `ttft_ms`. В `O-EXIT/v1` для tool-only остаётся `ttft_ms=None` (VER-002, строки `tools=1 ... ttft_ms=None`). Non-blocking.

AGREE F-015 rev=1 — проверил: `_reader` ставит `sse_conn.sock.settimeout(0.5)` и делает `except (TimeoutError, OSError): continue`. У `SocketIO` в CPython после первого `TimeoutError` взводится `_timeout_occurred`, и каждое следующее чтение бросает `OSError("cannot read from timed out object")`. Читатель уходит в холостой цикл на 100% CPU, а sentinel `None` не ставится. Пауза от `server.connected` до первой дельты у реального serve — до ~1,8 с (F-19 ledger), то есть реалтайм ломается уже на первой тишине. FakeServe держит паузы 0,12 с, поэтому тесты проходят. Не проверял запуском.

AMEND F-017 — priority=non-blocking; locations=server.py:2385,2997,3063,5208,6280; fix=выставлять `headers_at` по `getresponse()`, а не после `read()`, и считать `delivered` по latch «ответ на prompt получен» или «валидное execution-событие», учитывая и `reasonings` — причина: расхождение с `FALLBACK_DECISION_TABLE` подтверждено (`_serve_http` читает тело целиком). Эффект ограничен маршрутом: уход в `run` ограничен потолком 3 запусков и breaker (`attempt_done(True,False)` на 429), побочных эффектов нет, потому что permissions обязательно блокируют инструменты. Дубль reasoning по F-050 закрывается тем же фиксом.

AGREE F-018 rev=1 — проверил: `_serve_json_serve` возвращает `False` после `ServeUnavailable`, затем в `_serve_json` идёт легаси-цикл `Run`, и `Run._execute_once` делает `note_spawn()` после `Popen`, а не проверку потолка. В `_run_serve_stream_attempts` и legacy-цикле stream защита `total_spawns >= MAX_TOTAL_SPAWNS` добавлена, в `_serve_json` — нет. Два serve-ретрая и затем сбой старта дают четвёртый запуск (AC-013 MUST).

AMEND F-019 — priority=non-blocking; locations=server.py:3236,5000,5030; fix=по `step.ended` завершать попытку и при `tool_calls`, распарсенных `ToolCallParser`, либо после `terminal` ждать не дольше короткого окна — причина: `finish_reason` формируется по `tool_calls` независимо от транспорта. Текстовые теги `<tool_invoke>` opencode не исполняет, поэтому после `step.ended` сессия завершается сама (`session.execution.succeeded`) и STEP2 не запускается. Остаётся только задержка до terminal-события.

AMEND F-020 — priority=non-blocking; locations=server.py:5211,5228,5255,5281; fix=единая эмиссия одного разделителя «Повтор попытки» на все причины повтора; объединить с фиксом F-027 — причина: разделитель в веток unmapped/incomplete отсутствует. Но `_initial_status_timer` на повторах уже даёт отдельную статусную строку, так что реасонинг не склеивается. Нарушение AC-014 — по точному числу строк, а не по потере данных.

AMEND F-021 — priority=non-blocking; locations=server.py:6323,6344,6372; fix=дедуплицировать `tool_calls_all` по `_call_key(name, arguments)`, как `emit_tool_call` в SSE-пути — причина: паритет с SSE-путём полезен. Но одинаковый вызов в одном шаге по двум каналам (текст и native) не воспроизведён, `_seen_tc` в повторах не влияет (см. F-004). Меток [pre-existing] нет, дефект не воспроизводится.

AGREE F-023 rev=1 — проверил: SSE: `gate.acquire()` перед `_serve_one_attempt`, `gate.release()` после неё, то есть на всё время попытки. JSON: `_gate_j.release()` есть только в `ServeUnavailable`, `ServeSecurityError` и при отказе limiter; на успешном возврате его нет. Legacy отпускает gate на первой stdout-строке (F-10 ledger). Параллельные запросы ждут `STARTUP_WAIT_S=5` с и идут fail-open — это прямо бьёт по цели отзывчивости. Внутренности `_StartupGate` в пакете не приложены, поэтому оценка условна.

AMEND F-025 — priority=non-blocking; locations=server.py:2432,2444,2450,2470; fix=разделить бюджет: TERM-окно (например 3 с) и отдельное окно подтверждения после SIGKILL — причина: после полных 5 с TERM-ожидания цикл после SIGKILL не ждёт, но `_pid_alive(-pgid)` проверяется до `unlink`; lease и порт остаются, если группа ещё не исчезла (микросекунды после SIGKILL). Затрагивает только случай процессов, игнорирующих TERM 5 с, и укладывается в AC-011 (≤7 с).

AMEND F-027 — priority=non-blocking; locations=server.py:3042,5079-5087; fix=один владелец записей статусов, общий флаг «первый статус отправлен», `cancel` таймера в `finally` — причина: `wfile` не буферизован (`BaseHTTPRequestHandler.wbufsize=0`), `on_status` пишет одним `write` целого кадра, поэтому кадры SSE не перемешиваются. Реальный эффект — дубль `STATUS_INITIAL` (таймер и внутренний механизм) и возможная запись после `[DONE]`.
AMEND F-042 — priority=non-blocking; locations=server.py:5079-5087; fix=как в F-027 — причина: NEW: `on_status` в `_run_serve_stream_attempts` пишет `format_sse_chunk(...)` одним `self.wfile.write(...)` и `flush()`, а `wfile` не буферизован, так что перемешивания байтов нет. Своё прежнее «blocking» по гонке кадров снимаю; остаются дубли статусов.

AGREE F-028 rev=1 — проверил: в legacy-пути `watchdog_state["status_next"] = attempt_start + FIRST_STATUS_DELAY_S`, где `attempt_start` берётся после `gate.acquire()`, limiter и `_spawn_with_stdin`, а первый статус отправляется только из `send_keepalive` при чтении feed. `REALTIME_SERVE_ENABLED` по умолчанию `false`, значит именно legacy — основной путь. При конкурентных запросах ожидание gate до 5 с задерживает первый статус, а REQ-004 (≤1,0 с) обязателен независимо от апстрима. RW-011 в этой ветке не закрыт.

DISPUTE F-030 — класс: duplicate_of:F-001 — контр-evidence: server.py:99,240,245 — тот же `errno`, один фикс.

AGREE F-031 rev=1 — проверил: в `_run_serve_stream_attempts` и `_serve_json_serve` ветки `result["error"]` с `transient_error` и `prompt_status` 5xx делают `continue` без `attempts.attempt_done(True, False)`. `attempt_done` вызывается только для HTTP 429. Breaker не открывается при штормах 5xx и SSE-ошибок, а legacy вызывает `attempt_done(transient_failure, ...)`. Выходит, что RW-016 (учёт транзиентных сбоев) закрыт частично.

DISPUTE F-032 — класс: duplicate_of:F-009 — контр-evidence: tests/test_realtime_reasoning.py:489-873 — отдельно F-032 не нужна.

AMEND F-034 — priority=non-blocking; locations=tests/test_realtime_reasoning.py:773; fix=при ближайшем касании перевести тесты на pytest-фикстуры, не меняя семантику — причина: все 17 модулей `tests/` и соседний `test_step_interruption.py` построены на `unittest.TestCase`, `testing.md` описывает Litestar/async-проект, а здесь stdlib-сервер. Претензия о стиле без воспроизводимого дефекта на цикле ≥2 даёт non-blocking по правилу шапки.

AMEND F-035 — priority=non-blocking; locations=server.py:1696,2831,5119,6228; fix=убрать явный `proxy_url=_next_standalone_proxy()` из `_serve_one_attempt` и брать `HTTP_PROXY` из `_run_env` (его результат уже проходит `_serve_env`), либо потреблять пул ровно один раз — причина: каждый вызов `_next_standalone_proxy()` в вызывающем коде плюс внутренний в `_run_env` продвигают пул дважды на попытку. Выбранный прокси меняется от попытки к попытке при пуле из трёх и более записей, но при чётном размере используется только половина записей, а в пуле из двух всегда одна. Frozen `_run_env` не трогается.

AGREE F-036 rev=1 — проверил: `_lsof_listener_pid` делает `_LSOF_CALLS.append(port)` в продакшн-коде, очистки и предела нет. В демоне с uptime в сутки список растёт без границы, хотя объёмы малы. Non-blocking.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Не обработан исход `timeout` и `client_gone` в потребителях (F-002), читатель SSE ломается после первой же паузы дольше 0,5 с (F-015), ошибки prompt классифицируются только по приходу SSE-события (F-003), чекер отключения клиента игнорирует `OSError` (F-008), JSON-fallback превышает потолок запусков (F-018), транзиентные сбои не доходят до breaker (F-031), в helper lease снимается по смерти прямого потомка, а не группы (F-007).
   СОВЕТЫ (при FAIL):
   - Разобрать все исходы `_serve_one_attempt` до ветки успеха.
   - Читать SSE без короткого `settimeout` или возобновляемо, а при фатальной `OSError` ставить `None`.
   - Проверять `prompt_status` на каждой итерации до `events.get`.
   - В `_client_gone_check` возвращать `True` для всего, кроме `BlockingIOError` и EAGAIN/EWOULDBLOCK.
   - Перед фактическим запуском в JSON-fallback проверять `can_spawn()`.
   - Вызывать `attempt_done` на ветках transient SSE-ошибки и prompt 5xx.
   - Снимать lease helper только когда `not _pid_alive(-pgid)`.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Поведенческие оракулы RW-025 не добавлены: нет тестов serve-watchdog, JSON-serve, `client_gone`, AC-001/002/020, пауз SSE, ротации прокси и матрицы fallback (F-009). Ветка timeout/client_gone в JSON не покрыта (F-002). Legacy-путь не покрывает ожидание gate при первой реакции (F-028). Отдельно non-blocking: usage теряется в JSON-ретраях (F-011), `ttft_ms` не заполняется для tool-only (F-013).
   СОВЕТЫ (при FAIL):
   - Добавить тесты по перечню F-009: паузы SSE 1,5 с, serve-watchdog, `prompt_status` 401/429/5xx, FIN/RST, пароль в `bridge.log`.
   - Запускать статусный механизм legacy до `gate.acquire`.
   - Накапливать usage на каждом `continue` в JSON-пути.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Утечки `lifeline_w`, порта и state-каталога при раннем отказе (F-006). `_StartupGate` держится всю попытку в SSE и не отпускается в JSON (F-023). Читатель SSE зацикливается при `OSError` (F-015). Остальное (F-025, F-035) — non-blocking.
   СОВЕТЫ (при FAIL):
   - Один `try/finally` от `mkdtemp` до выхода из `_spawn_serve`.
   - Освобождать gate после готовности serve или первого события, плюс `finally` в JSON.
   - Конвертировать `OSError` при запуске в `ServeUnavailable`.

4. РИСКИ: VERDICT=FAIL
   WHY=Пустая попытка по дедлайну завершается успехом (F-002). RST не считается отключением клиента (F-008). Lease теряется при живых потомках (F-007). Breaker не учитывает транзитные upstream-сбои (F-031). Full Suite L2 зелёный (408 passed, обратный порядок OK, frozen sha256 совпали); RED rc=1. VER-006 и VER-007 законно отложены до ACCEPT (`DEFERRED_L3`), живой serve не проверен.
   СОВЕТЫ (при FAIL):
   - Закрыть F-002, F-007, F-008, F-031 регрессионными тестами.
   - После ACCEPT выполнить живой L3 против реального `opencode serve` v2.1.2 с паузами 1,5–2 с.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve на запрос с откатом на `run` повторяет прецедент muse-bridge (ADR-0004), сохраняет kill-switch и ротацию IP. Прямой HTTP к Zen без заголовков CLI даёт 429 (F-24/F-25 ledger), общий демон ломает ротацию. Самописный JSON-парсер удалён. Замечания F-004, F-017, F-019, F-020, F-021, F-034 — дефекты реализации и стиля, а не выбор пути, и non-blocking.
   СОВЕТЫ (при FAIL): нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Сверка SEED: `seed_hex` = `32e2accf4ab768a6449b41472efacd1b3d6fd89d86bcf2015ef99521eaf68aa2`, `SEED` = `32e2accf`. Пересчёт SHA-256 от дословной `seed_input` совпал с манифестом. Ранжирование по `SHA-256(seed_hex#slot_id)` даёт порядок muse-wonder-full-1.0, claude-sonnet-5-5-high, gpt-6.1-sol-high, gemini-4-argon-high, grok-4.7-high; он совпал с `ranked_order` манифеста. Дифф ограничен тремя файлами конверта, внешних зависимостей нет, frozen `_run_env`, `_stream_google_sse` и `_execute_google_once` побайтово не тронуты. Публичный HTTP-контракт моста сохранён. `unittest.TestCase` (F-034) следует соглашению всех модулей `tests/` и оформлен как non-blocking.
   СОВЕТЫ (при FAIL): нет.

POSITIONS: 36/36
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


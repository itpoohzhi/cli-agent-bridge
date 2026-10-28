> PANEL-NONCE: ef848fb9789626c7
> ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=Цикл 2 закрыл RW-002, RW-004, RW-005, RW-006, RW-007, RW-009, RW-010, RW-012, RW-013, RW-014, RW-016, RW-017, RW-020, RW-022, RW-026, RW-027, RW-029, RW-030, RW-031, RW-032 и кодовую часть FU-001/FU-002/FU-003/FU-008/FU-009. Открыты четыре дефекта логики в изменённом `server.py`. Дедлайн попытки пишется как `exit_reason="timeout"` (`server.py:3254`), но кортежи обработки (`server.py:5150`, `server.py:6247`) его не содержат, и оба обработчика вызывают `serve_health.record_success()` и `attempt_done(False, True)` (`server.py:5237-5238`, `server.py:6307-6308`) — RW-008. HTTP 401/403 prompt классифицируется только после `events.get()` (`server.py:3056-3061`), а `first_event_timeout` возвращается раньше (`server.py:3022-3027`) — RW-015. В JSON `_seen_tc` вычисляется и не используется (`server.py:6370-6371`), `tool_calls_all` сохраняется через `continue` (`server.py:6378`) — RW-018. В ветке `--serve-helper` `errno` читается в `_fd_ready` (`server.py:98-99`) до импорта, который стоит только в `else` (`server.py:244`) после `SystemExit` (`server.py:239-241`): любой `OSError`, кроме уже перехваченного `BlockingIOError`, даёт `NameError`. Первый вызов `_fd_ready` стоит до `try/finally` с `killpg`, поэтому падение оставляет lease фазы `starting`.
>    СОВЕТЫ (при FAIL):
>    - Импортировать `errno` на уровне модуля до `_run_serve_helper_cli`.
>    - Обработать `exit_reason=="timeout"` наравне с watchdog: без `record_success`, без `attempt_done(False, True)`, без успешного `[DONE]` и без JSON 200.
>    - Классифицировать `prompt_status` в начале цикла SSE, до возврата по watchdog; 401/403 поднимать как `ServeSecurityError` даже при пустой очереди.
>    - Перед JSON-retry удалять или дедуплицировать `tool_calls_all` неуспешной попытки; `_seen_tc` либо использовать, либо убрать.
>
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=RW-011 (таймер первого статуса, `server.py:5082-5090`) и RW-030 закрыты. RW-025 не закрыт: оракулы не покрывают AC. `__never_event__` и `__silent__` есть только в строке FakeServe (`tests/test_realtime_reasoning.py:112`, `:115`), живых тестов watchdog serve нет. AC-026 проверяет размах дельт `< 2.0` с (`:502`), а не интервал соседей `< 500` мс (AC-001) и не накладные расходы моста `≤ 250` мс (AC-002). Таблица fallback проверяется как данные (`:640`), а не как переходы prompt 401/429/5xx. Native-tool тест проверяет имя `bash` (`:591`), не reject/interrupt. Матрица транспорта не создаёт disable-файл (`:829-830`). Прокси проверяется как `callable` (`:871`). ELF/status проверяет только `isinstance(..., dict)` (`:881`). Нет JSON-serve, `client_gone`, скана лога на пароль (AC-020) и матрицы step-interruption на транспорте serve. В JSON `_StartupGate` берётся (`server.py:6203`) и отпускается только на limiter/ServeUnavailable/ServeSecurityError (`:6207`, `:6231`, `:6239`); после обычного возврата `_serve_one_attempt` release нет, в отличие от stream (`:5136`) — RW-001 частично.
>    СОВЕТЫ (при FAIL):
>    - Добавить поведенческие тесты serve: `__never_event__` → `first_event_timeout`, `__silent__` → `first_token_timeout` и `stall_timeout`.
>    - В AC-026 проверять соседние `reasoning_content` `< 500` мс и задержку моста `≤ 250` мс.
>    - Прогнать строки `FALLBACK_DECISION_TABLE` через FakeServe (401/403 fail-closed без инкремента health, 429 → breaker, 5xx до доставки → fallback).
>    - Проверить reject+interrupt на `permission.asked`, disable-файл, разные значения `_next_standalone_proxy`, магию ELF и поле `status` tool.
>    - Добавить JSON-serve, `client_gone` и отсутствие `OPENCODE_SERVER_PASSWORD` в `bridge.log`.
>    - Обернуть JSON-попытку в `try/finally: _gate_j.release()`.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
>    WHY=RW-002, RW-006, RW-010, RW-021, RW-022 закрыты: handshake с дедлайном, cleanup группы в бюджете 5 с, timeout control-сокета, кольцо stderr, доказательство слушателя до Authorization. Три операционных дыры остаются. JSON-gate не отпускается на успехе и держит холодные старты до `STARTUP_GATE_S=12` (RW-001). `_serve_env` создаёт `zen-serve-state-*` (`server.py:1718`) до `_spawn_serve`; порт резервируется (`:2493`), pipe открывается (`:2502`), `Popen` (`:2505`) стоит вне `except BaseException` (`:2599`); `finally` закрывает только `lifeline_r` (`:2526-2530`); `_ServeLease` создаётся после успешного `Popen` (`:2531`). Ошибка `Popen` и `ServeUnavailable("no free serve port")` (`:2500`) не убирают `lifeline_w`, порт и каталог состояния (RW-019). Helper удаляет lease при `serve_proc.poll() is not None` (`server.py:231-233`), не при смерти группы `-pgid` (RW-023).
>    СОВЕТЫ (при FAIL):
>    - `try/finally` вокруг JSON `_StartupGate.acquire()`.
>    - Единый cleanup от `mkdtemp`+pipe+`Popen`: оба конца pipe, `discard` порта, `rmtree` state-dir, `lease.cleanup()` если lease уже есть, включая «no free serve port».
>    - В helper удалять lease только после `not _pid_alive(-os.getpgrp())`.
>
> 4. РИСКИ: VERDICT=FAIL
>    WHY=L2 зелёный и это принимается: `L2-RED-sensitivity` rc=1 на `origin/dev`; VER-001 `408 passed`; VER-005 `29 passed`; AC-023 reversed rc=0; VER-004 `errorCount=0`, frozen sha256 `_run_env`/`_stream_google_sse`/`_execute_google_once` совпали. Секретов в репозитории нет: пароль — `secrets.token_hex(16)` (`server.py:1723`), allowlist, Authorization только после доказательства слушателя. Дыры: `_client_gone_check` на `OSError`/`ValueError` возвращает `False` (`server.py:4954-4955`) — RW-024; JSON-путь колбэк получает (`:6224`), семантика обрыва нет. Мёртвый `_seen_tc` оставляет дубли `tool_calls` (RW-018). VER-002 rc=0, но в stderr есть `ResourceWarning` незакрытых файлов `tests/test_cli_failure.py:267` — файл вне конверта. VER-006/VER-007 законно `DEFERRED_L3`.
>    СОВЕТЫ (при FAIL):
>    - В `_client_gone_check` возвращать `True` на `OSError`/`ValueError`, кроме `BlockingIOError` и `errno` `EAGAIN`/`EWOULDBLOCK`.
>    - Дедуплицировать JSON `tool_calls` перед retry (тот же фикс, что в критерии 1).
>    - Follow-up вне конверта: закрыть файлы в `tests/test_cli_failure.py:267`, чтобы `-W error::ResourceWarning` на полном discover оставался чистым.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=На цикле ≥2 раздувание без воспроизводимого дефекта не даёт FAIL. Раздельные циклы SSE и JSON нужны разным контрактам ответа. FU-006 (косметический format) и FU-007 (неполная унификация классификации) остаются non-blocking follow-up. Более дешёвый путь «только watchdog на `opencode run`» не закрывает RC-1 и в конверте не выбран.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Diff ровно в трёх файлах конверта, внешних runtime-зависимостей нет (`dependencies = []`). Замороженные срезы побайтово совпали с VER-004. Публичный каркас SSE/JSON сохранён; строки `[мост]` и поля `O-EXIT/v1` заданы REQ-004/005/016. `muse-bridge`, DSH и Google-direct не тронуты. `import json` обязателен при запрете зависимостей вне stdlib. FU-005 (документация вне трёх файлов) корректно отложен.
>
> SUB Корректность/логика: FAIL — server.py:3254 `exit_reason="timeout"` затем server.py:5237 и server.py:6307 `record_success()`; server.py:3022 возвращает `first_event_timeout` до классификации 401 на server.py:3056; server.py:6371 `_seen_tc` не используется (RW-008, RW-015, RW-018)
> SUB Корректность/граничные условия: FAIL — server.py:98-99 читает `errno` в helper до импорта server.py:244; server.py:4954-4955 `OSError`/`ValueError` → `False` (RW-024)
> SUB Корректность/обработка ошибок: FAIL — `NameError` в `_fd_ready` до `killpg`; `timeout` не входит в кортеж server.py:5150 и server.py:6247; prompt 401 перекрывается `first_event_timeout` (error-handling.md, RW-008, RW-015)
> SUB Полнота/покрытие AC: FAIL — tests/test_realtime_reasoning.py:112, :115, :502 (`< 2.0` с вместо AC-001/AC-002), :591, :640, :829-830, :871, :881; нет JSON-serve, client_gone, AC-020, serve step-interruption (RW-025)
> SUB Полнота/пропущенные ветки: FAIL — server.py:6203 `_gate_j.acquire()` без release на успехе (release только :6207, :6231, :6239; stream отпускает :5136); `"timeout"` отсутствует в :5150 и :6247 (RW-001, RW-008)
> SUB Реализуемость/общее: FAIL — server.py:1718 `mkdtemp`, :2493 порт, :2502 pipe, :2505 `Popen` вне cleanup :2599; lease удаляется по смерти serve, не группы, server.py:231 (RW-019, RW-023, feature.md finally)
> SUB Риски/безопасность: PASS — пароль `secrets.token_hex(16)` server.py:1723, allowlist, listener до Authorization; секретов в diff нет (REQ-015)
> SUB Риски/данные: FAIL — server.py:6370-6378 `_seen_tc` мёртвый, `tool_calls_all` живёт через retry (RW-018, AC-014)
> SUB Риски/прод: FAIL — server.py:4954 ложный «клиент жив» на RST/EBADF; server.py:231 lease снимается при живой группе; server.py:6203 gate до 12 с (REQ-008, AC-011, S-HERD-I1)
> SUB Риски/regression red→green: PASS — execution-evidence.md `L2-RED-sensitivity` rc=1 и VER-001/VER-005 rc=0 (REQ-020)
> SUB Риски/Full Suite (L2): PASS — VER-001 408 passed, VER-002 rc=0, VER-003/003b rc=0, AC-023 reversed rc=0, VER-004 rc=0; ResourceWarning в test_cli_failure.py:267 non-blocking
> SUB Риски/scope-diff: PASS — candidate-manifest.json ровно server.py, tests/test_realtime_reasoning.py, tests/test_step_interruption.py; frozen sha256 совпали
> SUB Альтернативы/общее: PASS — цикл 2, двойной цикл SSE/JSON требуется контрактами ответа; FU-006/FU-007 non-blocking
> SUB Соответствие контексту/общее: PASS — 3 файла конверта, stdlib, frozen `_run_env`/`_stream_google_sse`/`_execute_google_once`, Forbidden Scope не задет
>
> F-1
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:98, bridges/opencode-zen-bridge/server.py:99, bridges/opencode-zen-bridge/server.py:239, bridges/opencode-zen-bridge/server.py:244
> rule: python-standards.md §3 (fail-fast, имя должно быть связано); дефект дельты цикла 1→2 (ветка EAGAIN)
> evidence: «if isinstance(_gone_exc, OSError) and _gone_exc.errno in (errno.EAGAIN, errno.EWOULDBLOCK)» при том, что `import errno` стоит в `else` после `if sys.argv[1:2] == ["--serve-helper"]: raise SystemExit(...)`. `BlockingIOError` перехватывается раньше и до `errno` не доходит. Любой другой `OSError` (EBADF, EINTR) в процессе helper даёт `NameError`. Первый `_fd_ready()` выполняется до `try/finally` с `killpg`, lease фазы `starting` остаётся.
> expected: `import errno` рядом с `select` до определения `_run_serve_helper_cli`.
> verify: helper, у которого `select` на fd 0 бросает `OSError` с `EBADF` или `EINTR`, завершается без `NameError` и снимает lease.
>
> F-2
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3254, bridges/opencode-zen-bridge/server.py:5150, bridges/opencode-zen-bridge/server.py:5237, bridges/opencode-zen-bridge/server.py:5238, bridges/opencode-zen-bridge/server.py:6247, bridges/opencode-zen-bridge/server.py:6307, bridges/opencode-zen-bridge/server.py:6308
> rule: RW-008, REQ-006, REQ-009, R-BULK-I1
> evidence: «result["exit_reason"] = "timeout"» после цикла без `terminal`. Кортежи содержат только `first_event_timeout`, `first_token_timeout`, `stall_timeout`, `invalid_serve_event`. Дальше «res.serve_health.record_success()» и «attempts.attempt_done(False, True)», затем успешный `[DONE]` / JSON 200.
> expected: ветка `timeout` идёт в retry или ошибку, без `record_success` и без успешного finish.
> verify: укороченный `attempts.deadline` без terminal-события даёт `exit_reason=timeout`, счётчик `serve_health` не сбрасывается, клиент не получает `finish_reason=stop`.
>
> F-3
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3022, bridges/opencode-zen-bridge/server.py:3027, bridges/opencode-zen-bridge/server.py:3054, bridges/opencode-zen-bridge/server.py:3055, bridges/opencode-zen-bridge/server.py:3056, bridges/opencode-zen-bridge/server.py:3061
> rule: RW-015, FALLBACK_DECISION_TABLE (HTTP401/403 → fail_closed)
> evidence: при пустой очереди «except queue.Empty: continue» происходит до чтения `prompt_status`. При тишине «result["exit_reason"] = "first_event_timeout"» и `return` выполняются до «if _ps in (401, 403): raise ServeSecurityError». `headers_at` пишется только после чтения тела ответа. Создание сессии с 400 по-прежнему fail-closed и тестом закрыто; дыра только у статуса prompt.
> expected: разбирать `prompt_status` в начале итерации, до watchdog-return; 401/403 всегда `ServeSecurityError`, без инкремента `serve_health` и без fallback.
> verify: FakeServe отвечает 401 на prompt при молчащем SSE → security failure сразу, `failures` health не растёт, auto не уходит в `run`.
>
> F-4
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:6370, bridges/opencode-zen-bridge/server.py:6371, bridges/opencode-zen-bridge/server.py:6378
> rule: RW-018, AC-014
> evidence: «_seen_tc = {str(tc.get("id")) for tc in tool_calls_all}» нигде не читается; следом `continue` оставляет уже добавленные вызовы в `tool_calls_all`. Поток SSE для текста использует `_PrefixDedup`; reasoning по AC-014 дедуплицировать не нужно.
> expected: перед retry очищать или дедуплицировать `tool_calls_all` и content неуспешной попытки.
> verify: JSON-сценарий unmapped-then-success возвращает каждый tool_call один раз.
>
> F-5
> priority: blocking
> criterion: РЕАЛИЗУЕМОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:6203, bridges/opencode-zen-bridge/server.py:6207, bridges/opencode-zen-bridge/server.py:6231, bridges/opencode-zen-bridge/server.py:6239, bridges/opencode-zen-bridge/server.py:6307
> rule: RW-001, REQ-013, S-HERD-I1, T-LIFE/v1
> evidence: «_gate_j.acquire()». `release()` есть на отказе limiter, `ServeUnavailable` и `ServeSecurityError`. После обычного возврата `_serve_one_attempt` до `record_success()` release нет. Stream отпускает gate на `server.py:5136`.
> expected: `try/finally: _gate_j.release()` на всех выходах JSON-попытки, включая `continue`.
> verify: два последовательных JSON-serve не ждут `STARTUP_GATE_S`.
>
> F-6
> priority: blocking
> criterion: РЕАЛИЗУЕМОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:1718, bridges/opencode-zen-bridge/server.py:2493, bridges/opencode-zen-bridge/server.py:2500, bridges/opencode-zen-bridge/server.py:2502, bridges/opencode-zen-bridge/server.py:2505, bridges/opencode-zen-bridge/server.py:2526, bridges/opencode-zen-bridge/server.py:2531, bridges/opencode-zen-bridge/server.py:2599
> rule: RW-019, REQ-008, AC-011, feature.md (таймаут и cleanup в finally на каждом шаге I/O)
> evidence: «state_dir = tempfile.mkdtemp(prefix="zen-serve-state-")» выполняется до spawn. Порт кладётся в `_ACTIVE_SERVE_PORTS`, затем «lifeline_r, lifeline_w = os.pipe()» и `Popen`. `finally` закрывает только `lifeline_r`. Lease строится после успешного `Popen`. «except BaseException» вызывает `lease.cleanup()` только если lease уже есть. «raise ServeUnavailable("no free serve port")» тоже после `mkdtemp`.
> expected: один `try/finally` от каталога состояния и pipe: закрыть оба fd, снять порт, удалить каталог, cleanup lease если он создан.
> verify: `Popen`, бросающий `OSError`, не оставляет запись порта, каталог `zen-serve-state-*` и открытый `lifeline_w`.
>
> F-7
> priority: blocking
> criterion: РЕАЛИЗУЕМОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:231, bridges/opencode-zen-bridge/server.py:232, bridges/opencode-zen-bridge/server.py:233
> rule: RW-023, REQ-008, AC-011, T-LIFE/v1
> evidence: «if serve_proc.poll() is not None: lease_path.unlink()». Комментарий finally требует снимать lease после смерти группы; условие смотрит только на прямой дочерний `serve`. Внук, оставшийся в группе, теряет lease, и reaper его не находит.
> expected: `unlink` только когда `not _pid_alive(-os.getpgrp())` и `serve_proc` завершён.
> verify: живой внук в той же группе оставляет lease-файл на диске.
>
> F-8
> priority: blocking
> criterion: РИСКИ
> locations: bridges/opencode-zen-bridge/server.py:4954, bridges/opencode-zen-bridge/server.py:4955, bridges/opencode-zen-bridge/server.py:6224
> rule: RW-024, REQ-008, AC-011, AC-012
> evidence: «except (OSError, ValueError): return False». JSON передаёт `is_client_gone=self._client_gone_check`, но обрыв сокета (EBADF/RST) читается как «клиент на месте». Половина RW-024 (прокидка в JSON) сделана.
> expected: `return True`, если это не `BlockingIOError` и не `EAGAIN`/`EWOULDBLOCK`.
> verify: закрытый клиентский сокет в stream и JSON даёт `client_gone` и `lease.cleanup()` не позже 7 с.
>
> F-9
> priority: blocking
> criterion: ПОЛНОТА
> locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:112, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:115, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:491, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:502, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:588, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:591, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:640, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:829, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:830, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:863, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:871, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:873, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:881
> rule: RW-025, REQ-020, AC-001, AC-002, AC-008, AC-009, AC-010, AC-016, AC-018, AC-020, testing.md (зелёный прогон ≠ полнота)
> evidence: маркеры `__never_event__` и `__silent__` живут только внутри строки FakeServe, вызовов нет. «self.assertLess(model_reasoning[-1][0] - model_reasoning[0][0], 2.0)» не проверяет соседний интервал и накладные расходы. `test_serve_health_and_fallback_table` сверяет строки таблицы. `test_native_tool_and_permission_reject` делает «self.assertIn("bash", _tool_names(chunks))». Docstring `test_transport_matrix` обещает disable-файл, код его не создаёт. «self.assertTrue(callable(server._next_standalone_proxy))». `test_elf_magic_and_tool_status` заканчивается «self.assertIsInstance(part_obj, dict)». Нет теста JSON-serve, client_gone, отсутствия пароля в логе и step-interruption на serve. L2 зелёный, потому что написанные тесты проходят, а не потому что оракулы RW-025 существуют.
> expected: по одному нетавтологическому тесту на каждый перечисленный AC.
> verify: каждый новый тест красный на `origin/dev` и зелёный на кандидате; prompt 401 не увеличивает `serve_health.failures`.
>
> F-10
> priority: non-blocking
> criterion: РИСКИ
> tag: [pre-existing]
> locations: bridges/opencode-zen-bridge/tests/test_cli_failure.py:267
> rule: testing.md (ResourceWarning при выходе процесса); файл вне `allowed_envelope_changes`
> evidence: VER-002 stderr: «ResourceWarning: unclosed file <_io.TextIOWrapper name=9 ...>» и та же строка для fd 7, обе указывают на `tests/test_cli_failure.py:267`. Прогон rc=0, потому что discover шёл без `-W error`. Подмножество кодера с `-W error::ResourceWarning` этого файла не включало.
> expected: follow-up отдельной задачей: закрыть pipe в тесте. В этот diff файл не входит.
> verify: полный `unittest discover` с `-W error::ResourceWarning` без предупреждения на этой строке.
>
> F-11
> priority: non-blocking
> criterion: ПОЛНОТА
> locations: bridges/opencode-zen-bridge/server.py:6260, bridges/opencode-zen-bridge/server.py:6261, bridges/opencode-zen-bridge/server.py:6271, bridges/opencode-zen-bridge/server.py:6272, bridges/opencode-zen-bridge/server.py:6281, bridges/opencode-zen-bridge/server.py:6282, bridges/opencode-zen-bridge/server.py:5166
> rule: FU-004, REQ-014 (SHOULD)
> evidence: JSON-ветки `allow_retry` делают `continue` без суммирования `result["usage"]`. Stream перед таким `continue` копит `input/output/cached/reasoning` в `_serve_stream_usage` (`server.py:5166-5170`).
> expected: тот же аккумулятор перед каждым JSON `continue` на timeout, invalid event и transient retry.
> verify: две попытки JSON, первая с ненулевым usage и timeout, вторая успешная — финальный `usage` содержит сумму обеих.
>
> F-12
> priority: non-blocking
> criterion: РИСКИ
> locations: bridges/opencode-zen-bridge/server.py:75, bridges/opencode-zen-bridge/server.py:2630, bridges/opencode-zen-bridge/server.py:2644, bridges/opencode-zen-bridge/server.py:2645, bridges/opencode-zen-bridge/server.py:2646
> rule: остаток RW-003 (сверка helper PID с живым `ps lstart`)
> evidence: lease пишет «"helper_lstart": str(int(time.time()))». Reaper: «if _live and not _ts_v.isdecimal() and _live != _ts_v». Десятичная epoch-строка пропускает сравнение с `ps -o lstart=`. Комментарий на :2644 это фиксирует. Сверка `parent_start_ts` для lstart-формата работает.
> expected: писать `helper_lstart` тем же форматом, что `ps lstart`, и сравнивать его.
> verify: lease с живым PID другого процесса и тем же номером не получает `killpg`.
>
> F-13
> priority: non-blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3215, bridges/opencode-zen-bridge/server.py:3216, bridges/opencode-zen-bridge/server.py:3181, bridges/opencode-zen-bridge/server.py:3192
> rule: AC-021 (поле `ttft_ms` есть; семантика «первый токен» для tool-only не заполняется)
> evidence: при `tool_event` «if result["first_token_at"] is None: result["first_token_at"] = time.monotonic()» без присвоения `ttft_ms`. Reasoning и text пишут `ttft_ms` на :3181 и :3192. VER-002: `transport=serve ... tools=1 ... ttft_ms=None`.
> expected: при первом native tool completion выставлять `ttft_ms` так же, как для reasoning/text.
> verify: tool-only ответ в `O-EXIT/v1` имеет целое `ttft_ms`.
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK

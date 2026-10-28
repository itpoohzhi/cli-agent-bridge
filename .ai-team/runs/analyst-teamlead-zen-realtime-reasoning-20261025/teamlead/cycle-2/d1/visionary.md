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

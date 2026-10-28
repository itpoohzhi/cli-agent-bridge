# Стенограмма дебатов Совета Тимлидов по коду — Cycle 6 (run `analyst-teamlead-zen-realtime-reasoning-20261025`)

## Раунд R1 (`panel/council/r72`)

### Seat 1 (`skeptic`, `muse-wonder-full-1.0`)

PANEL-NONCE: 28cd4acab313d414
ARTIFACT-SHA256: 2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb
1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Verify-Fixed RW-001: барьер `delivered` монотонно включает `headers_at`/текст/reasoning/native_calls в `_serve_one_attempt` (`finally` + все ветки error/timeout), внешние SSE/JSON-циклы при `delivered=True` не возвращают fallback в `run` и не зовут `record_success()`; оракул `test_c6_rw001_headers_at_blocks_run_fallback_on_sse_error_and_timeout` зелёный в L2 (`VER-001` rc=0, 466 passed). RW-002: пол `120.0` убран, legacy `send_keepalive` сравнивает строго `float(FIRST_TOKEN_TIMEOUT_S)`; оракул `test_c6_rw002_..._under_120s` зелёный. Публичный контракт `/health`,`/v1/models`,`/v1/chat/completions`, SSE-формат, `finish_reason`, `usage`, порт :9883 не изменены (REQ-002/AC-003); синтетические `[мост]` — прямое требование REQ-004/005, не самовольное изменение контракта. Замороженные `_run_env`/`_stream_google_sse`/`_execute_google_once` побайтово MATCH (`code-gate.json: run_env_sha256=1c51b28f...`, `google_direct_unchanged=True`, REQ-018).
2. ПОЛНОТА: VERDICT=PASS
   WHY=RW-003: в `Run.execute`/`_execute_once` добавлены `first_event_at/first_token_at/last_token_at`, `on_idle` убивает группу по трём фазам и повтор в `MAX_TOTAL_SPAWNS`, активный `task` не триггерит stall; оракулы `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs`, `test_c6_rw003_active_subagent_does_not_trigger_token_stall` зелёны. RW-004: матрица AC-016 (5 ветвей × SSE/JSON) и эквивалентность AC-017 serve-vs-run покрыты `test_c6_rw004_ac016_serve_step_interruption_matrix`, `test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence`, отражены в `verification-traceability.md`. Поштучно REQ-001..REQ-020/AC-001..AC-026 трассированы; только REQ-019/VER-006/VER-007 законно `DEFERRED_L3` до ACCEPT (Forbidden Scope: живой мост до вердикта не мутировать). Изменение ожиданий `test_step_interruption.py` 4→3 запусков — санкционированный REQ-017 при инварианте `MAX_TOTAL_SPAWNS=3`, компенсировано новым `test_unmapped_then_incomplete_then_calls_within_cap_stream` с `tool_calls` в пределах потолка, а не ослабление оракула.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=RW-005: `_spawn_serve` и `_open_serve_events` принимают `deadline`/`is_client_gone`, `_check_serve_start` не запускает helper при истёкшем сроке/ушедшем клиенте, отмена даёт терминальные `ServeClientDisconnect`/`ServeStartupDeadlineExceeded` без превращения в `ServeUnavailable` и без fallback; оракулы `test_c6_rw005_*` (3 теста) зелёны. RW-006: поток дренажа `helper.stderr` стартует сразу после `Popen` до handshake/listener, хвост ограничен `_MAX_STDERR_TAIL_BYTES=16384` байт (не строк); оракул `test_c6_rw006_..._multi_mib_stderr_before_bind_without_deadlock` (≥2 MiB без `\n`) зелёный. Транспорт по умолчанию выключен (`auto` требует `REALTIME_SERVE_ENABLED`+нативный бинарь, `disable-serve` и `TRANSPORT=run` — kill-switch, REQ-003), 0 зависимостей вне Python 3.14 stdlib, ровно 3 файла в `candidate-manifest.json`. Скептические остаточные наблюдения из `reverse-spec.md` §4.6 (гонка probe-bind порта, потомки вне PGID, многострочный SSE `data:`) не имеют воспроизводимого дефекта против AC на этом цикле и по правилу Cycle≥2 не дают FAIL — non-blocking follow-up, не блокер merge.
4. РИСКИ: VERDICT=PASS
   WHY=RW-007+FU-003: `_serve_http` пересчитывает таймаут по абсолютному `deadline` перед каждой фазой, watcher закрывает сокет при капающих заголовках/теле, `skip_body=True` на `interrupt`/`DELETE`, общий cleanup-бюджет 0.45с + `lease.cleanup()` в `finally` даёт смерть группы ≤7с (AC-011); оракулы `test_c6_rw007_absolute_deadline_...`, `test_c6_rw007_skip_body_...`, `test_c6_rw007_fu003_dripping_..._under_7s` зелёны. FU-001: `_MAX_SSE_LINE_BYTES=1MiB`, `_MAX_SERVE_HTTP_BODY_BYTES=8MiB` с `ServeProtocolError`; FU-002: все 4 поля usage валидируются `int and not bool and >=0`. Безопасность: `_serve_env` allowlist + `OPENCODE_DB=":memory:"` + случайный `OPENCODE_SERVER_PASSWORD` (`secrets.token_hex`), permission `ask_reject`/`deny` fail-closed, `form.created` cancel+interrupt до проверки схемы, расширенное `_mask_secrets`/`_error_payload` (Bearer/пароль/proxy-creds), тройная сверка listener PID/PGID/serve PID, lease reaper с lstart/uid — секретов в логах/диффе не видно (REQ-015/AC-020). Regression: Clean-Room L2 `code-gate.json status=PASS`, `red_sensitivity_rc=1` на `origin/dev`, `VER-001/002/003/003b/005` и `AC-023-reversed` все rc=0 (466 passed, 3238 subtests), `VER-004` ruff/basedpyright 0 errors — Full Suite не сужен, порядок тестов не влияет (AC-022/023).
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбран гибрид A1+fallback (вариант C handoff §4): только `opencode serve` даёт дельты (F-17/F-18: `run` игнорирует `*.delta`; F-19: serve median 127мс), вариант L реалтайм не закрывает RC-1, вариант B не подтверждён (F-24/F-25: 429), A2 теряет ротацию IP (F-23). Переиспользован прецедент `muse-bridge` serve→exec (F-40/F-41) и существующие `ToolCallParser`/`_native_to_tool_calls`/`_RetryBudget`/breaker ниже границы `(etype,payload)` — нового параллельного стека не введено. На Cycle 6 неоправданного раздувания/переписывания без доказательства необходимости нет: дельта ограничена RW-001..007/FU-001..003, основная масса diff в `server.py` — форматирование legacy в изменённых диапазонах под VER-004 range-gate при нетронутых замороженных срезах.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Scope ровно конверт: 3 файла `bridges/opencode-zen-bridge/{server.py,tests/test_realtime_reasoning.py,tests/test_step_interruption.py}` (`candidate-manifest.json`), чужих KEY/файлов/`muse-bridge`/конфига georouter нет (Non-Goals/Forbidden Scope соблюдены), `dependencies=[]` в `pyproject.toml` сохранён. Слои не смешаны сверх существующей монолитной архитектуры моста: serve сводится к тем же кортежам `parse_opencode_event`, верхний слой (ретраи, парсер, usage, SSE) переиспользован; subprocess — только list-формой без `shell=True`, с ограниченным env и таймаутами на каждом шаге включая cleanup в `finally` (feature.md §2, security.md §8); `O-EXIT/v1` расширен `transport/first_event_ms/ttft_ms/transport_history` на каждом выходе `do_POST` (REQ-016). HL-инварианты применительно к локальному ThreadingHTTPServer (`W=1`) закрыты существующими bulkhead/rate-limit/retry-budget/breaker — новых пулов/поллеров/кэшей, активирующих C-MULT/S-HERD сверх as-is анализа §8, не добавлено.
SUB Корректность/логика: PASS — `server.py` `_serve_one_attempt`/`_is_delivered` + `test_c6_rw001_*`, L2 VER-001 rc=0 (execution-evidence.md)
SUB Корректность/граничные условия: PASS — `server.py` `_map_serve_event` (строгие int≥0 usage, FU-002), `_MAX_SSE_LINE_BYTES`/`_MAX_SERVE_HTTP_BODY_BYTES` (FU-001), `test_c6_fu001_fu002_*`
SUB Корректность/обработка ошибок: PASS — `server.py` `FALLBACK_DECISION_TABLE` + fail-closed 400/401/403/404/422, `ServeSecurityError`/`ServeProtocolError`, `test_prompt_http_4xx_fail_closed_without_run_fallback`
SUB Полнота/покрытие AC: PASS — `verification-traceability.md` REQ-001..020/AC-001..026 поштучно PASS, VER-006/007 DEFERRED_L3 до ACCEPT
SUB Полнота/пропущенные ветки: PASS — `tests/test_realtime_reasoning.py` `test_c6_rw004_ac016_*`/`test_c6_rw004_ac017_*` (text/reasoning/broken/native/budget × SSE/JSON)
SUB Реализуемость/общее: PASS — `server.py` `_select_transport`/`_spawn_serve`/`_ServeLease` (RW-005/006), kill-switch default-off, 0 внешних зависимостей (`pyproject.toml: dependencies=[]`)
SUB Риски/безопасность: PASS — `server.py` `_serve_env` allowlist+`:memory:`+random password, `_mask_secrets`/`_error_payload`, `test_rw008_provider_secrets_hidden_in_sse_json_and_log`
SUB Риски/данные: PASS — `server.py` `_startup_reaper`/`_ServeLease.cleanup`/`_stop_proc` (группа после выхода лидера), `test_rw005_stop_group_after_leader_exit`, lease только после смерти группы
SUB Риски/прод: PASS — `server.py` watchdogs FIRST_EVENT/FIRST_TOKEN/STALL (RW-002/003), `_watch_serve_connection`+`skip_body` cleanup ≤7с AC-011 (RW-007)
SUB Риски/regression red→green: PASS — `receipts/code-gate.json` `red_sensitivity_rc=1` на origin/dev, `test_ac026_realtime_chunks_before_upstream_end` зелёный на кандидате (AC-026)
SUB Риски/Full Suite (L2): PASS — `execution-evidence.md` VER-001/002/003/003b/005+AC-023-reversed все rc=0, 466 passed без сужения селекторов
SUB Риски/scope-diff: PASS — `candidate-manifest.json` ровно 3 файла конверта, замороженные срезы sha256 MATCH, `google_direct_unchanged=True`
SUB Альтернативы/общее: PASS — `handoff-architect.md` §4 варианты L/A1/A2/B/C по фактам F-17..F-25, выбран C с прецедентом muse-bridge F-40
SUB Соответствие контексту/общее: PASS — `server.py` сведение serve к `(etype,payload)` parse-границы (F-02/F-05), O-EXIT/v1 расширен, публичный контракт REQ-002 сохранён
ОБЩИЙ ВЕРДИКТ: ACCEPT
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 0


### Seat 2 (`realist`, `grok-4.7-high`)

PANEL-NONCE: 70ffa302d0155885
ARTIFACT-SHA256: 2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb
Канон прочитан: AGENTS.md, 430 строк

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Цикл 6 закрывает RW-001, RW-002, RW-004, RW-005, RW-006, RW-007 и FU-001..FU-003: барьер `headers_at`, порог первого токена без пола 120 с, матрицы AC-016/AC-017, deadline/client_gone на старте serve, дренаж stderr, абсолютный HTTP-deadline и `skip_body`, байтовые потолки SSE/HTTP и строгие целые usage подтверждены кодом и зелёным L2 (VER-001: 466 passed). RW-003 по убийству группы и повтору внутри `MAX_TOTAL_SPAWNS` тоже закрыт. На исчерпанном JSON-пути `TRANSPORT=run` watchdog всё равно уходит клиенту и в `O-EXIT/v1` как `provider_fatal`. `Run._execute_once` при любом `watchdog_reason` ставит `fatal_error=True` (`server.py:5488`), словарь результата несёт и `fatal_error`, и `state` (`server.py:5507`), `Run.execute` при исчерпанном бюджете возвращает этот словарь (`server.py:5228-5238`), а `Handler._serve_json` на `fatal_error` без tool_calls пишет `xs["exit_reason"]="provider_fatal"` и тело «opencode provider error after partial output» (`server.py:7516-7527`). REQ-016 / AC-021 требуют на каждом `do_POST` коды `first_event_timeout`, `first_token_timeout`, `stall_timeout`. Clean-room VER-002 фиксирует ровно это: после `state=first_event_timeout` строка `O-EXIT/v1 mode=json … status=502 exit_reason=provider_fatal … duration_s=0.77` (`execution-evidence.md:3467-3470`); то же для `first_token_timeout` (`:3479-3482`, 0.79 с) и `stall_timeout` (`:3491-3494`, 0.54 с). Ветка `fatal_error=True` на детерминированном HTTP провайдера (`server.py:5442`) к этому дефекту не относится. SSE legacy и JSON serve выставляют имя фазы напрямую.
   СОВЕТЫ (при FAIL): В `Handler._serve_json` до ветки `fatal_error` обработать `out["state"]` из `{first_event_timeout, first_token_timeout, stall_timeout}`: `xs["exit_reason"]=state` и `_error_payload(f"opencode {state}")`, как на SSE. В `Run._execute_once` (`server.py:5488`) не ставить `fatal_error=True` из-за watchdog; `fatal_error=True` оставить только детерминированному HTTP (`server.py:5442`). В `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs` для исчерпанного бюджета (`MAX_TOTAL_SPAWNS=1`) утверждать `exit_reason=<фаза>` в строке `O-EXIT/v1`, а не только подстроку фазы в логе и HTTP 502.

2. ПОЛНОТА: VERDICT=PASS
   WHY=Матрица AC-001..AC-024 и AC-026 закрыта автотестами и зелёным L2; AC-025 / VER-006 / VER-007 законно `DEFERRED_L3` до ACCEPT. Промах `exit_reason` — неверная метка уже реализованной ветки исчерпанного watchdog, а не отсутствующий сценарий. Исключение stall для живого `task` есть на JSON `Run` (`server.py:5302`, `:5343`, `:5395-5399`); объём RW-003 этим путём и ограничен.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Serve по умолчанию выключен (`auto` + `REALTIME_SERVE_ENABLED` только при boolean true). Новых runtime-зависимостей нет, stdlib Python 3.14. Дефолт `OPENCODE_CONFIG_CONTENT` (`server.py:513-516`) уже содержит `baseURL` georouter `127.0.0.1:10830`; `_serve_env` перезаписывает только ключ `permission` (`server.py:1869-1872`). `lsof`/`ps` на целевой машине есть (факт-карта). Память короткоживущего serve укладывается в оценку HL-ENV. Живой выкат на `:9883` остаётся лестницей H0..H9 после ACCEPT.

4. РИСКИ: VERDICT=FAIL
   WHY=Оракул `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs` зелёный на L2, потому что проверяет HTTP 502, счётчик спавнов и наличие имени фазы в логе (`opencode run watchdog:` / `state=`). Строка `O-EXIT/v1` при этом `exit_reason=provider_fatal` (`execution-evidence.md:3470`, `:3482`, `:3494`). Оператор не отличает watchdog от фатального отказа провайдера. DSH ходит со `stream:true` (F-35), видимый Think этот JSON-путь не рисует; публичный non-stream и обязательное поле выхода REQ-016 всё равно ломаются. Полный сьют L2 зелёный (VER-001/002/003/003b/005, AC-023, rc=0); ранний лог кодера `1 failed, 465 passed` перекрыт clean-room 466 passed. RED на `origin/dev` (rc=1, 93 failed) — доказательство red→green, не дефект кандидата.
   СОВЕТЫ (при FAIL): Те же правки, что в КОРРЕКТНОСТЬ: классифицировать три фазы watchdog в `exit_reason` JSON-пути и закрепить это утверждением на строке `O-EXIT/v1`, а не на любой подстроке лога.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий `opencode serve` на запрос с откатом на `run` до барьера доставки — требуемый вариант A1/гибрид (RC-1 не закрывается упрочнением только `opencode run`). Объём в одном `server.py` задан конвертом из трёх файлов. Переписывания функции без необходимости нет. Таблица `FALLBACK_DECISION_TABLE` декларативна; переходы делают ветки, и это не раздувание ради раздувания.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Diff ровно в трёх разрешённых файлах. Замороженные срезы `_run_env`, `_stream_google_sse`, `_execute_google_once` совпали (VER-004, `google_direct_unchanged=True`). Публичные маршруты, порт `:9883` и форма SSE сохранены; строки `[мост]` требуются REQ-004/005. Новых зависимостей вне stdlib нет. Ранний выход `--serve-helper` и импорт `zen_catalog` только в основной ветке соответствуют VER-004. Kill-switch — env и `dynamic_config.json`, как задано конвертом.

F-001
priority: blocking
criterion: КОРРЕКТНОСТЬ, РИСКИ
locations: bridges/opencode-zen-bridge/server.py:5488, bridges/opencode-zen-bridge/server.py:5507, bridges/opencode-zen-bridge/server.py:5228, bridges/opencode-zen-bridge/server.py:7516, bridges/opencode-zen-bridge/server.py:7518
rule: REQ-016 MUST, AC-021, AC-010, RW-003 («классифицировать причину выхода `first_event_timeout`, `first_token_timeout`, `stall_timeout`»)
evidence: В `Run._execute_once` блок `if watchdog_reason: rc = 1; fatal_error = True` (`server.py:5486-5488`) помечает любой watchdog как фатальную ошибку провайдера. Возврат включает `"fatal_error": fatal_error` и `"state": state` (`server.py:5505-5508`). `Run.execute` при исчерпанном бюджете делает `return out` (`server.py:5237`). `Handler._serve_json` выполняет `if out.get("fatal_error") and not tool_calls:` → `xs["exit_reason"] = "provider_fatal"` и `_error_payload("opencode provider error after partial output …")` (`server.py:7516-7527`). Clean-room: `exec cli failed rc=-15 state=first_event_timeout` затем `O-EXIT/v1 mode=json … status=502 exit_reason=provider_fatal … duration_s=0.77` (`execution-evidence.md:3468-3470`); `state=first_token_timeout` → `exit_reason=provider_fatal` duration_s=0.79 (`:3480-3482`); `state=stall_timeout` → `exit_reason=provider_fatal` duration_s=0.54 (`:3492-3494`). Ветка детерминированного HTTP `fatal_error = True` на `server.py:5442` — другой root cause и в этот блок не входит.
expected: На исчерпанном JSON `run` `exit_reason` равен имени фазы (`first_event_timeout` / `first_token_timeout` / `stall_timeout`), тело 502 называет эту фазу. `fatal_error=True` остаётся только у детерминированного HTTP провайдера.
verification: `OPENCODE_ZEN_BRIDGE_TRANSPORT=run`, `stream=false`, `MAX_TOTAL_SPAWNS=1`, молчащий CLI / служебное событие без токена / пауза после токена: строка `O-EXIT/v1` содержит `exit_reason=<фаза>`, в теле нет «provider error after partial output». Успешный повтор при `MAX_TOTAL_SPAWNS=2` по-прежнему `exit_reason=ok`.
test_gap: `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs` должен утверждать `exit_reason=<фаза>` в `O-EXIT/v1`, а не только подстроку фазы где-либо в логе.

SUB Корректность/логика: FAIL — JSON run при исчерпанном watchdog пишет exit_reason=provider_fatal (server.py:5488, server.py:7518; REQ-016/AC-021; execution-evidence.md:3470)
SUB Корректность/граничные условия: PASS — потолок спавнов, deadline, client_gone, байтовые капы SSE/HTTP и запрет bool/отрицательных токенов зелёные на L2 (server.py:1580-1581, VER-001 rc=0)
SUB Корректность/обработка ошибок: FAIL — тот же F-001: клиентский JSON 502 подписан «provider error after partial output» вместо имени фазы (server.py:7518-7524; AC-010)
SUB Полнота/покрытие AC: PASS — AC-001..AC-024 и AC-026 зелёные в verification-traceability; AC-025/VER-006/VER-007 = DEFERRED_L3 (execution-evidence.md)
SUB Полнота/пропущенные ветки: PASS — stall-исключение живого task есть на JSON Run, как просил RW-003 (server.py:5343, server.py:5395-5399)
SUB Реализуемость/общее: PASS — serve выключен по умолчанию, stdlib, baseURL georouter сохраняется в дефолтном OPENCODE_CONFIG_CONTENT (server.py:513-516, server.py:1871)
SUB Риски/безопасность: PASS — пароль serve через secrets.token_hex, allowlist env, маскирование Bearer/пароля/proxy, lease 0700; оракулы секретов в зелёном VER-005
SUB Риски/данные: PASS — OPENCODE_DB=:memory:, usage только неотрицательный int, запись в opencode.db отсутствует (server.py:1876, FU-002)
SUB Риски/прод: FAIL — тот же F-001: O-EXIT исчерпанного JSON run фиксирует provider_fatal (execution-evidence.md:3470, :3482, :3494; server.py:7518)
SUB Риски/regression red→green: PASS — L2-RED-sensitivity rc=1 на origin/dev (93 failed), кандидат VER-005 87 passed и VER-001 466 passed (code-gate.json)
SUB Риски/Full Suite (L2): PASS — VER-001/002/003/003b/005 и AC-023 rc=0, 466 passed (execution-evidence.md, l2-green-ver001-pytest.log)
SUB Риски/scope-diff: PASS — ровно 3 файла конверта, frozen sha256 совпали, google_direct_unchanged=True (code-gate.json)
SUB Альтернативы/общее: PASS — транспорт A1 с откатом на run до барьера доставки требуется RC-1; дробление модуля конверт запрещает
SUB Соответствие контексту/общее: PASS — публичный HTTP/SSE и :9883 сохранены, чужих путей нет, helper-ветка соответствует VER-004 (server.py, scope-and-contracts REQ-002)

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 1


### Seat 3 (`visionary`, `gpt-6.1-sol-high`)

PANEL-NONCE: 8d610b4c7d17aad9
ARTIFACT-SHA256: 2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb

Канон `~/Мой диск/Context/AGENTS.md` прочитан до `<!-- КАНОН-КОНЕЦ -->`. В рабочей папке `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` отсутствуют; профильные правила прочитаны из пакета. SHA-256 трёх файлов кандидата совпали с манифестом. Тесты самостоятельно не запускались.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Решение существенно улучшает наблюдаемость долгих агентных ходов: настоящий поток дельт заменяет ожидание завершённого блока, сохраняя клиентский API. Однако барьер исполнения ещё допускает смену транспорта после подтверждённого начала генерации; legacy SSE неправильно учитывает watchdog в Circuit Breaker.

   SUB Корректность/логика: FAIL — watchdog обрабатывается после `attempt_done`, который не учитывает причину watchdog (bridges/opencode-zen-bridge/server.py:6772).
   SUB Корректность/граничные условия: FAIL — execution-событие без prompt-заголовков не устанавливает барьер доставки (bridges/opencode-zen-bridge/server.py:3345).
   SUB Корректность/обработка ошибок: FAIL — исчерпанный watchdog JSON-пути превращается в `provider_fatal` (bridges/opencode-zen-bridge/server.py:7516).

   СОВЕТЫ (при FAIL):

   - Включить подтверждённое execution-событие в монотонный барьер запроса.
   - Классифицировать watchdog до обновления breaker.
   - Передавать точную причину watchdog в финальный `O-EXIT`.

   F-001 [pre-existing]
   priority: blocking
   locations: `bridges/opencode-zen-bridge/server.py:3345`, `bridges/opencode-zen-bridge/server.py:3683`.
   rule: `FALLBACK_DECISION_TABLE`, запрет fallback после valid execution SSE; REQ-009.
   evidence: `_is_delivered()` учитывает только `headers_at`, тексты, reasoning и native calls. Получение `session.execution.started` устанавливает `first_event_at`, но не барьер. Если prompt-заголовки ещё не пришли, а SSE затем закрывается, результат может остаться `delivered=False`, разрешая переход в `run` после уже начавшегося исполнения.
   исправление: включить валидное событие выполнения своей сессии в барьер; сохранять его между попытками в SSE и JSON.
   проверка: FakeServe задерживает prompt-заголовки, отправляет execution.started своей сессии и закрывает SSE; `Run.execute` и `_spawn_with_stdin` не вызываются, допустимы только serve-retry либо ошибка.

   F-002 [pre-existing]
   priority: blocking
   locations: `bridges/opencode-zen-bridge/server.py:6772`, `bridges/opencode-zen-bridge/server.py:6776`, `bridges/opencode-zen-bridge/server.py:6779`.
   rule: REQ-009; `R-BULK-I3`, сохранение Circuit Breaker.
   evidence: `transient_failure` вычисляется без `watchdog_state["reason"]`. Убитый watchdog процесс имеет отрицательный rc и не считается retryable CLI failure. При отсутствии вывода breaker не получает failure; после частичного вывода `attempt_done(False, True)` может зарегистрировать успех. Затем отдельная ветка всё равно повторяет запрос по watchdog.
   исправление: включить watchdog в транзиентный исход до единственного вызова `attempt_done`; исключить success для такой попытки.
   проверка: для трёх watchdog-причин, с выводом и без него, проверить инкремент failure, отсутствие success и открытие breaker после заданного числа отказов.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Матрицы recovery и fault injection значительно усилены. Основные исправления подтверждены независимым L2, однако точная диагностика нового JSON-watchdog не доходит до финального sink; стартовые фазовые бюджеты закрыты частично.

   SUB Полнота/покрытие AC: FAIL — AC-021 формально имеет поля, но терминальная причина JSON-watchdog неверна; это видно в сыром логе (execution-evidence.md, `VER-002-unittest`, 09:47:32–09:47:36).
   SUB Полнота/пропущенные ветки: FAIL — проверены короткие общие дедлайны, но отсутствует оракул отдельного startup-бюджета при длинном общем deadline (bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2278).

   СОВЕТЫ (при FAIL):

   - Проверять финальную строку `O-EXIT/v1`, включая точную причину и измеренные времена.
   - Добавить сценарий капающих стартовых заголовков с длинным общим deadline.
   - Сохранить уже закрытые regression-оракулы.

   F-003
   priority: blocking
   locations: `bridges/opencode-zen-bridge/server.py:5486`, `bridges/opencode-zen-bridge/server.py:5505`, `bridges/opencode-zen-bridge/server.py:7516`.
   rule: REQ-016, AC-021; `O-EXIT/v1`, точная машиночитаемая причина отказа.
   evidence: watchdog устанавливает `fatal_error=True`, после чего JSON-handler записывает `exit_reason="provider_fatal"`. Сырой clean-room лог подтверждает это для `first_event_timeout`, `first_token_timeout`, `stall_timeout`. Измеренные `first_event_at`/`first_token_at` также не возвращаются в handler: итоговые поля остаются `None`.
   исправление: передать времена и терминальное состояние из `Run` в handler; обработать watchdog до общего provider-fatal пути.
   проверка: пройти реальный HTTP JSON-handler до логового sink; получить ровно одну строку `O-EXIT/v1` с соответствующей watchdog-причиной и корректными временами наступивших событий.

   Verify-Fixed:

   - RW-001: PASS для заявленных случаев «prompt headers → SSE error / общий timeout»; F-001 фиксирует отдельную незакрытую границу.
   - RW-002: PASS — нижний предел 120 с удалён, regression-оракул есть.
   - RW-003: PASS для остановки и повторов трёх фаз JSON/run; F-003 — дефект передачи результата.
   - RW-004: PASS — пять serve-сценариев AC-016 и сравнение serve/run для AC-017 включены в traceability.
   - RW-005: FAIL частично — общий deadline и отмена проброшены, собственный абсолютный бюджет startup HTTP-фазы не обеспечен; F-004.
   - RW-006: PASS — ранний побайтовый дренаж stderr и предел 16 КиБ подтверждены сценарием 2 МиБ без LF.
   - RW-007: PASS — абсолютный cleanup-deadline, `skip_body` и обязательный `lease.cleanup`.
   - FU-001: PASS — пределы SSE-строки и HTTP-тела реализованы.
   - FU-002: PASS для отрицательных и boolean token counts.
   - FU-003: PASS — сквозной cleanup-оракул проверяет исчезновение группы за установленный бюджет.

   Поштучная сверка требований:

   - REQ-001: PASS — дельты доставляются инкрементально.
   - REQ-002: PASS — публичные маршруты и форма ответов сохранены.
   - REQ-003: PASS — run, аварийный файл и выключенный по умолчанию serve сохранены.
   - REQ-004: PASS для проверенных SSE-сценариев ожидания.
   - REQ-005: PASS для проверенных модельных дельт, статусов и реплея.
   - REQ-006: FAIL на стартовых HTTP-фазах до запуска основного watchdog; F-004.
   - REQ-007: PASS для фаз после запуска транспорта.
   - REQ-008: PASS по представленным сценариям отмены и cleanup.
   - REQ-009: FAIL — F-001, F-002.
   - REQ-010: PASS — используется существующий инкрементальный parser.
   - REQ-011: PASS — recovery и terminal tool_calls покрыты матрицей.
   - REQ-012: PASS по коду ask→reject/interrupt и представленным оракулам; реальная политика остаётся частью L3.
   - REQ-013: PASS — общий limiter/gate/bulkhead и ротация сохранены.
   - REQ-014: частично подтверждено; ранний native terminal может потерять фактический usage, F-005.
   - REQ-015: PASS — случайный пароль, allowlist и маскирование.
   - REQ-016: FAIL — F-003.
   - REQ-017: PASS — полный и обратный порядок зелёные.
   - REQ-018: PASS — frozen-срезы и Google-тесты подтверждены.
   - REQ-019: DEFERRED_L3, допустимо до ACCEPT.
   - REQ-020: PASS — сокетный оракул и свидетельство RED→GREEN присутствуют.

   Поштучная сверка AC: AC-001 PASS; AC-002 PASS; AC-003 PASS; AC-004 PASS; AC-005 PASS; AC-006 PASS на представленных фикстурах; AC-007 PASS; AC-008 частично, F-004; AC-009 PASS; AC-010 PASS; AC-011 PASS; AC-012 PASS на синтетическом сценарии, живое подтверждение DEFERRED_L3; AC-013 PASS; AC-014 PASS на проверенных recovery-ветках; AC-015 PASS; AC-016 PASS; AC-017 PASS; AC-018 PASS по проверкам ротации; AC-019 PASS для step-ended фикстуры, ограничение F-005; AC-020 PASS по представленному оракулу; AC-021 FAIL; AC-022 PASS; AC-023 PASS; AC-024 PASS; AC-025 DEFERRED_L3; AC-026 PASS.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Короткоживущий serve сохраняет ротацию IP и изолирует отказы запросов; `:memory:` устраняет зависимость от большой SQLite-базы. Масштаб соответствует локальному мосту с ограниченным параллелизмом. Но старт всё ещё может занимать общий 1800-секундный бюджет вместо собственного окна фазы.

   SUB Реализуемость/общее: FAIL — readiness/create/subscribe защищены общим deadline, но не собственным абсолютным пределом (bridges/opencode-zen-bridge/server.py:3375).

   СОВЕТЫ (при FAIL):

   - Вычислять абсолютный deadline каждой стартовой фазы.
   - Ограничивать его остатком общего бюджета.
   - Делить один фазовый бюджет между повторами управляющего вызова.
   - Проверить капающие заголовки при длинном общем deadline.

   F-004
   priority: blocking
   locations: `bridges/opencode-zen-bridge/server.py:3171`, `bridges/opencode-zen-bridge/server.py:3375`, `bridges/opencode-zen-bridge/server.py:3391`, `bridges/opencode-zen-bridge/server.py:3394`.
   rule: RW-005; `feature.md` §2, `R-BULK-I1`, ограничение каждого I/O-шага собственным бюджетом и остатком deadline.
   evidence: watcher подписки получает общий `deadline`; `_ctrl_http` передаёт `attempt_deadline`. `ready_deadline=now+3` проверяется только после возврата/ошибки `_ctrl_http`. Если заголовки поступают по байту быстрее socket timeout, readiness/create могут ждать до общего deadline; аналогично подписка обходит собственный first-event-порог. Основной watchdog начинается после этих операций.
   исправление: передавать в watcher и HTTP-вызов `min(request_deadline, phase_started + phase_budget)`; readiness-повторы должны использовать общий для них фазовый deadline.
   проверка: при общем deadline 30–60 с и фазовом бюджете 0,3 с peer капает корректные заголовки каждые 0,02 с; readiness/create/subscribe завершаются по фазовому бюджету с cleanup и корректной классификацией. Существующие тесты с общим deadline 0,9 с этот случай не различают.

4. РИСКИ: VERDICT=FAIL
   WHY=Clean-room доказательства убедительны: 466 тестов компонента, 894 корневых теста, обратный порядок, статические проверки и frozen-хеши. Основной остаточный риск — усиление отказов из-за неверного breaker-учёта и повторное исполнение после допустимого execution-события. Зелёный набор этих веток не проверяет.

   SUB Риски/безопасность: PASS — Basic-пароль генерируется через secrets, окружение ограничено, ошибки маскируются (bridges/opencode-zen-bridge/server.py:1830; REQ-015).
   SUB Риски/данные: FAIL — смена транспорта после execution.started допускает повторное исполнение; F-001 (bridges/opencode-zen-bridge/server.py:3345).
   SUB Риски/прод: FAIL — legacy SSE watchdog способен сбросить breaker как успешная попытка; F-002 (bridges/opencode-zen-bridge/server.py:6776).
   SUB Риски/regression red→green: PASS — независимый RED rc=1 и GREEN rc=0 представлены (execution-evidence.md, `L2-RED-sensitivity`, `VER-005-dedicated-realtime-suite`).
   SUB Риски/Full Suite (L2): PASS — 466 passed; корневой suite 894 passed, 5 skipped; обратный порядок 466 passed (execution-evidence.md, `VER-001`, `VER-003`, `AC-023`).
   SUB Риски/scope-diff: PASS — ровно три разрешённых файла, frozen-функции совпали, зависимостей не добавлено (candidate-manifest.json; `VER-004-packet-command`).

   СОВЕТЫ (при FAIL):

   - Закрыть F-001..F-004 и добавить различающие поведенческие оракулы.
   - Повторить L2 на новом кандидате.
   - После ACCEPT выполнить предусмотренный L3 на реальном DSH, включая рабочий размер промпта, параллельные вызовы и отключение клиента.

   F-005 [pre-existing]
   priority: non-blocking
   locations: `bridges/opencode-zen-bridge/server.py:3745`, `bridges/opencode-zen-bridge/server.py:3753`.
   rule: REQ-014 / AC-019, сохранение фактического usage.
   evidence: готовый native call при `emulate_tools=True` завершает попытку до последующего `session.step.ended`; фактические токены этого шага могут не попасть в результат, и ответ использует оценку.
   исправление: ограниченно дождаться usage завершаемого шага либо явно сохранить признак оценочного usage; не допускать следующего модельного шага.
   проверка: native called → step.ended с известными токенами; итоговый usage равен фикстуре и учитывается один раз. Приоритет non-blocking, поскольку REQ-014 имеет SHOULD.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбор serve с резервным run оправдан подтверждённой невозможностью получить дельты из установленного run. Общий демон осложнил бы ротацию IP, прямой Zen HTTP не имеет подтверждённого рабочего пути авторизации. Исправление найденных дефектов возможно локально; переписывание транспортной архитектуры не требуется.

   SUB Альтернативы/общее: PASS — A1 с fallback решает RC-1..RC-3 при сохранении существующих ограничителей; более дешёвый legacy-only вариант не даёт реалтайма (handoff-architect.md §4; F-17..F-25).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Решение остаётся внутри автономного stdlib-моста. Новые Litestar/SQLAlchemy-слои и runtime-зависимости здесь не нужны. Изоляция транспорта открывает путь к дальнейшему развитию без изменения DSH, но не доказывает рост пропускной способности: ресурсная модель остаётся «процесс serve на попытку».

   SUB Соответствие контексту/общее: PASS — разрешённый файловый конверт соблюдён, публичные границы и замороженные маршруты сохранены (candidate-manifest.json; scope-and-contracts.md §1–2; `VER-004`).

   Non-Goals проверены поштучно: HTTP/порт/SSE — сохранены; DSH/профиль/ReasoningRow — не изменены; модельное reasoning ради превью не переписывается; модель/effort/каталог — не заменены; другие мосты и общие конфиги — не изменены; внешние runtime-зависимости — отсутствуют.

   Forbidden Scope проверен поштучно: файлов вне конверта нет; записанных реальных секретов не обнаружено; боевой rollout отложен; запрещённого keychain-вызова нет; общая БД напрямую не изменяется; коммита в target и merge пакет не заявляет.

   Независимая сверка: SEED=`f24bed3a`; seed_hex=`f24bed3aa414cb2b8ce5ca1bc587e03cf4d458ef3a96b860d3b6caa29e7753db`; ranked_order=`gpt-6.1-sol-high → grok-4.7-high → claude-sonnet-5-5-high → muse-wonder-full-1.0 → gemini-4-argon-high` — полностью совпадает с манифестом по алгоритму `select_round_seats.py`.

   Self-sweep выполнен по всем 14 подкатегориям. Отсроченные VER-006/VER-007 не использованы как основание FAIL. Межцикловая git-дельта отдельно не приложена; точную атрибуцию новых замечаний в `late_miss` должен подтвердить оркестратор.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 5


---

## Раунд D1 (`panel/council/r77`)

### Seat 1 (`skeptic`, `grok-4.7-high`)

PANEL-NONCE: 12c042ce4e46a5fe
ARTIFACT-SHA256: 2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb

AGREE F-001 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5488 — при любом `watchdog_reason` `_execute_once` ставит `fatal_error=True` и возвращает этот словарь (`server.py:5507`); `Run.execute` при исчерпанном бюджете делает `return out` (`server.py:5237`); `Handler._serve_json` на `fatal_error` без tool_calls пишет `exit_reason="provider_fatal"` и тело «opencode provider error after partial output» (`server.py:7516`). Clean-room VER-002: после `state=first_event_timeout` / `first_token_timeout` / `stall_timeout` строка `O-EXIT/v1 mode=json status=502 exit_reason=provider_fatal`. JSON-путь при этом уже считает watchdog транзиентным (`server.py:5491`); ломается метка выхода, не повтор. `fatal_error=True` на детерминированном HTTP (`server.py:5442`) — другой исход и в фикс не входит.

AGREE F-002 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:3345 — `_is_delivered()` учитывает только `headers_at`, тексты, reasoning и native calls. `session.execution.started` своей сессии ставит `first_event_at` (`server.py:3675`) и не поднимает барьер. На EOF без terminal `exit_reason="invalid_serve_event"` и `delivered=_is_delivered()` (`server.py:3609`). Внешний цикл при `not _delivered_now and not force_serve` возвращает `False` и уходит в `run` (`server.py:5878`). Строка таблицы `PROMPT_SENDING` разрешает fallback только при «no response headers and no valid execution SSE» (`server.py:1658`); код эту оговорку не исполняет.

AGREE F-003 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:6772 — `transient_failure` на legacy SSE считается без `watchdog_state["reason"]`, затем сразу `attempt_done` (`server.py:6776`). Убитый watchdog имеет `rc<0`, `_is_retryable_failure` на `rc<=0` возвращает False (`server.py:2063`). Без вывода исход нейтральный: breaker не получает failure. После частичного вывода `attempt_done(False, True)` пишет success, и только потом ветка watchdog вызывает `allow_retry` (`server.py:6779`). На JSON-пути `watchdog_reason` уже входит в `transient_failure` (`server.py:5491`) — это другой root cause, не F-001.

DISPUTE F-004 — класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:5488 и bridges/opencode-zen-bridge/server.py:7516 — тот же `fatal_error=True` → `exit_reason="provider_fatal"`. Поля `first_event_ms`/`ttft_ms` в строке `O-EXIT/v1` присутствуют; для `first_event_timeout` значение `None` корректно. Отдельного MUST на ненулевые времена нет: AC-021 требует имя фазы в `exit_reason`, и это закрывается фиксом F-001.

AGREE F-005 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:3171 — watcher подписки получает общий `deadline` запроса; `_ctrl_http` передаёт `deadline=attempt_deadline` (`server.py:3375`). `ready_deadline=now+3` (`server.py:3391`) проверяется только после возврата или исключения `_ctrl_http`. Если заголовки капают быстрее socket timeout, readiness/create/subscribe живут до общего `TIMEOUT_S`, а не до собственного окна фазы. RW-005 требует `min(своё окно, остаток deadline)` на handshake/listener/subscribe; тесты с общим deadline ~0.9 с это окно не отделяют.

AGREE F-006 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:3752 — при `emulate_tools` готовый native call ставит `terminal="tool_calls"` и `break` до `session.step.ended`, где usage читается из токенов (`server.py:3766`). Итог опирается на оценку. REQ-014 — SHOULD, priority остаётся non-blocking.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Исчерпанный JSON `run` отдаёт клиенту и в `O-EXIT/v1` `provider_fatal` вместо `first_event_timeout` / `first_token_timeout` / `stall_timeout` (F-001, REQ-016 / AC-021 / AC-010). Валидное `session.execution.started` не входит в барьер доставки, и EOF до заголовков prompt уводит `auto` в `opencode run` (F-002, `FALLBACK_DECISION_TABLE` `server.py:1658`, REQ-009).
   СОВЕТЫ (при FAIL): В `_serve_json` до ветки `fatal_error` обработать `out["state"]` из трёх фаз watchdog: `xs["exit_reason"]=state` и тело `opencode {state}`. В `_execute_once` не ставить `fatal_error=True` из-за watchdog. Включить валидное execution-событие своей сессии в монотонный `delivered` и в `_delivered_now` SSE/JSON, чтобы после него был только serve-retry или терминальная ошибка.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=AC-021 требует на каждом `do_POST` машиночитаемую причину watchdog. Оракул `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs` зелёный, потому что ищет имя фазы где-либо в логе и HTTP 502, а строка `O-EXIT/v1` при этом `exit_reason=provider_fatal` (F-001). Матрицы AC-016/AC-017 и прочие AC этим не закрываются; F-006 (SHOULD) полноту не роняет.
   СОВЕТЫ (при FAIL): В том же тесте при `MAX_TOTAL_SPAWNS=1` утверждать `exit_reason=<фаза>` именно в строке `O-EXIT/v1` и отсутствие «provider error after partial output» в теле 502. Успешный повтор при `MAX_TOTAL_SPAWNS=2` по-прежнему `exit_reason=ok`.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Стартовые HTTP-фазы readiness/create/subscribe ограничены общим дедлайном запроса, а окно ~3 с проверяется только после возврата вызова (F-005, RW-005, feature.md §2, R-BULK-I1). Капающие заголовки при длинном `TIMEOUT_S` не обрываются собственным бюджетом фазы.
   СОВЕТЫ (при FAIL): Передавать в watcher и `_serve_http` `min(request_deadline, phase_started + phase_budget)`; повторы readiness делят один фазовый deadline. Оракул: общий deadline 30–60 с, фаза 0.3 с, peer капает заголовки каждые 0.02 с — фаза завершается по своему бюджету с cleanup.
4. РИСКИ: VERDICT=FAIL
   WHY=Прод-строка JSON `run` не отличает watchdog от фатального отказа провайдера (F-001). Legacy SSE после частичного вывода записывает watchdog как success breaker и всё равно ретраит (F-003, REQ-009, R-BULK-I3). Fallback после `execution.started` допускает повторное исполнение того же хода (F-002). Полный L2 зелёный (466 passed, RED на `origin/dev` rc=1) эти ветки не ловит. F-006 non-blocking: ранний native terminal может потерять фактический usage (REQ-014 SHOULD).
   СОВЕТЫ (при FAIL): Те же правки F-001 и F-002. На SSE включить watchdog в `transient_failure` до единственного `attempt_done` и не писать success для такой попытки. Оракул трёх фаз с выводом и без: инкремент failure, отсутствие success, открытие breaker после порога.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий `opencode serve` с откатом на `run` до барьера доставки по-прежнему закрывает RC-1: `opencode run` не отдаёт `*.delta`, прямой Zen без заголовков дал 429, общий демон ломает ротацию IP. Фиксы F-001..F-003 и F-005 локальные; переписывания транспорта не требуется.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Diff ровно в трёх файлах конверта. Замороженные `_run_env` / `_stream_google_sse` / `_execute_google_once` совпали, `google_direct_unchanged=True`, зависимостей вне stdlib нет. Публичные маршруты, порт `:9883` и форма SSE сохранены; строки `[мост]` требуются REQ-004/005. VER-006/VER-007 остаются `DEFERRED_L3` до ACCEPT.

POSITIONS: 6/6
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `gpt-6.1-sol-high`)

PANEL-NONCE: 9c071d5b37133925
ARTIFACT-SHA256: 2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb

Перепроверю пять открытых находок и расчёт SEED. Тесты не запускаю; использую приложенный diff и независимые логи L2.

Подтвердились три дефекта: execution-событие не входит в барьер доставки, legacy SSE неверно учитывает watchdog в breaker, а JSON/run теряет точную причину и времена фаз в итоговом логе. Проверка также подтверждает, что стартовые HTTP-вызовы ограничены общим дедлайном, но их собственные окна можно обойти капающими заголовками. SEED и ranked_order совпали с манифестом.

PANEL-NONCE: 9c071d5b37133925
ARTIFACT-SHA256: 2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb

Канон `~/Мой диск/Context/AGENTS.md` прочитан до `<!-- КАНОН-КОНЕЦ -->`. В рабочей папке `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` отсутствуют; профильные стандарты прочитаны из пакета. Тесты самостоятельно не запускались.

AGREE F-002 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3345`, `:3683`. `_is_delivered()` учитывает заголовки prompt и модельный вывод, но не `first_event_at`. Валидное `session.execution.started` устанавливает только время события. При задержанных prompt-заголовках и последующем EOF барьер может остаться ложным, разрешая fallback после начала исполнения. Нужен оракул execution.started → EOF без prompt-заголовков для SSE и JSON.

AGREE F-003 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:6772`, `:6776`, `:6779`. Причина watchdog отсутствует в вычислении `transient_failure`; `attempt_done()` вызывается раньше её обработки. При отрицательном rc без вывода failure не учитывается, после частичного вывода возможен ложный success. Watchdog нужно включить в исход до единственного вызова `attempt_done()`, проверить failure/success и переход breaker на всех трёх фазах.

AMEND F-004 — priority=blocking; locations=bridges/opencode-zen-bridge/server.py:5298, bridges/opencode-zen-bridge/server.py:5373, bridges/opencode-zen-bridge/server.py:5386, bridges/opencode-zen-bridge/server.py:5505, bridges/opencode-zen-bridge/server.py:7444; fix=оставить в F-004 отдельный дефект передачи времён JSON/run: вернуть измеренные времена из Run и перенести их в first_event_ms/ttft_ms итогового O-EXIT; неверную классификацию watchdog учитывать только в F-001 — причина: времена вычисляются, но отсутствуют в возвращаемом результате. Сырой `VER-002-unittest` подтверждает `first_event_ms=None ttft_ms=None` даже после полученных событий. Проверка — HTTP-handler до логового sink: одна строка выхода, ненулевые измерения наступивших фаз и `None` только для ненаступивших.

AGREE F-005 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3171`, `:3375`, `:3391`, `:3398`. Watcher подписки и управляющий HTTP получают общий deadline. Собственный `ready_deadline` проверяется после возврата вызова; капающие заголовки могут удерживать его до общего бюджета. Нужны абсолютные фазовые deadlines `min(request_deadline, phase_start + phase_budget)`, общие для повторов одной фазы. Оракул должен использовать длинный общий deadline и короткий фазовый бюджет отдельно для readiness, create и subscribe.

AMEND F-006 — priority=blocking; locations=bridges/opencode-zen-bridge/server.py:3745, bridges/opencode-zen-bridge/server.py:3753; fix=после готового native-вызова ограниченно собрать usage завершаемого шага, исключив запуск следующего шага; проверить native called → step.ended с известными токенами и однократным учётом — причина: немедленный `break` при emulate_tools завершает чтение до step.ended. Приоритет определяется прямым правилом пакета: «в файле, изменённом задачей, — blocking»; приоритет SHOULD у REQ-014 этого правила не отменяет.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=F-001 сохраняется: исчерпанный watchdog JSON/run становится `provider_fatal` (`server.py:5488`, `:7518`), что подтверждено независимым логом. Дополнительно подтверждены незамкнутый барьер исполнения F-002 и неверный breaker-учёт F-003.
   СОВЕТЫ (при FAIL): Перед provider-fatal веткой обработать три watchdog-состояния с точным `exit_reason`; включить валидное execution-событие своей сессии в монотонный барьер; учитывать watchdog как failure до `attempt_done()`. Закрепить каждую границу отдельным поведенческим оракулом.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-001/002/004/006/007 и FU-001/002/003 подтверждены представленными исправлениями и L2. RW-003 закрывает остановку и повтор, но диагностика неполна — F-001/F-004. RW-005 закрывает общий deadline и отмену, однако собственные абсолютные окна HTTP-фаз остаются незамкнутыми — F-005. Native-ветка теряет фактический usage — F-006.
   СОВЕТЫ (при FAIL): Передать времена Run в итоговый лог; добавить различающий тест фазового бюджета при длинном общем deadline; проверить usage native-шага. Обновить traceability по фактическим результатам этих проверок.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Ресурсная схема применима к локальному мосту: короткоживущий serve, изолированная `:memory:` БД, сохранённая ротация, stdlib и выключенный по умолчанию транспорт. Однако F-005 позволяет стартовому HTTP удерживать слот до общего бюджета 1800 с. Это операционный блокер отзывчивости.
   СОВЕТЫ (при FAIL): Ограничить readiness/create/subscribe собственными абсолютными бюджетами, разделяемыми их повторами; сохранить терминальную обработку общего deadline и client_gone. Исправления локальны, миграций и новых зависимостей не требуют. После нового L2 выполнить предусмотренную лестницу H0..H9.

4. РИСКИ: VERDICT=FAIL
   WHY=F-002 допускает смену транспорта после подтверждённого исполнения; F-003 искажает защиту от серии зависаний; F-001/F-004 скрывают реальные причины и времена отказов; F-006 подменяет фактический usage оценкой. Полный L2 действительно зелёный: 466 тестов компонента, корневой прогон 894 passed, обратный порядок 466 passed. Эти результаты не опровергают конкретные непроверенные ветви.
   СОВЕТЫ (при FAIL): Добавить оракулы барьера execution, breaker при watchdog, точного O-EXIT, фазовых deadlines и native usage; повторить L2 на новом кандидате. VER-006/007 оставить DEFERRED_L3 до ACCEPT, затем проверить рабочий размер промпта, параллельные запросы и отключение клиента на живом DSH.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Serve с резервным run обоснован: установленный run не выдаёт дельты, общий демон осложняет ротацию IP, прямой Zen HTTP не имеет подтверждённого рабочего пути. Найденные дефекты исправляются внутри выбранной схемы; оснований требовать переписывания архитектуры нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Три разрешённых файла, замороженные функции и публичные HTTP/SSE-границы сохранены. Новых внешних runtime-зависимостей нет. Non-Goals и Forbidden Scope соблюдены; живой rollout законно отложен. Для автономного ThreadingHTTPServer перенос на Litestar и добавление сторонних библиотек не требуются.
   SEED=d179999a; seed_hex=d179999aecfb7627ab77305b16bab1b68bc405658973c9267cb90366b184e9bc; независимо рассчитанный ranked_order=gpt-6.1-sol-high → muse-wonder-full-1.0 → claude-sonnet-5-5-high → grok-4.7-high → gemini-4-argon-high — совпадает с manifest.json.

POSITIONS: 5/5
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `muse-wonder-full-1.0`)

PANEL-NONCE: 12bf0ea9850c8a43
ARTIFACT-SHA256: 2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb
Канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до `<!-- КАНОН-КОНЕЦ -->`; проектных `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` в рабочей папке нет, профильные правила прочитаны из пакета.

AGREE F-001 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5488 — `fatal_error = True` при любом `watchdog_reason`, а Handler._serve_json по `fatal_error` пишет `exit_reason="provider_fatal"` (bridges/opencode-zen-bridge/server.py:7516); RECHECK F-001 и сырые строки `O-EXIT/v1 ... exit_reason=provider_fatal` после `state=first_event_timeout|first_token_timeout|stall_timeout` в execution-evidence.md подтверждают нарушение REQ-016/AC-021.
WITHDRAW F-004 — ARG: realist/R1 «В `Run._execute_once` блок `if watchdog_reason: rc = 1; fatal_error = True` (`server.py:5486-5488`) помечает любой watchdog как фатальную ошибку провайдера»; проверил: bridges/opencode-zen-bridge/server.py:5486 — моя F-004 имеет тот же root cause, что F-001, оставляю F-001 как каноническую находку без дубля.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Реалтайм через короткоживущий serve меняет качество долгих ходов без смены клиентского API, но барьер после valid execution SSE и breaker-учёт legacy watchdog ещё неверны; терминальная причина JSON-watchdog искажается. F-001, F-002, F-003.
   СОВЕТЫ (при FAIL): включить валидное execution-событие своей сессии в монотонный барьер (F-002); учитывать watchdog как transient до единственного `attempt_done` без success (F-003); в JSON-пути выставлять `exit_reason` по имени фазы до ветки `fatal_error` (F-001).
2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-002, RW-004, RW-006, RW-007, FU-001..FU-003 закрыты; RW-001 закрыт только для prompt-headers, RW-003 — для убийства/повтора, но не для финальной классификации, RW-005 — без собственного абсолютного бюджета стартовых HTTP-фаз. F-001, F-002, F-005.
   СОВЕТЫ (при FAIL): добавить оракулы execution.started без headers (F-002), точного `exit_reason` в sink `O-EXIT/v1` (F-001) и капающих стартовых заголовков при длинном общем deadline (F-005).
3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Процесс serve на попытку с `:memory:` масштабируется в пределах локального моста и сохраняет ротацию IP, но readiness/create/subscribe могут занимать общий бюджет вместо собственного окна фазы. F-005.
   СОВЕТЫ (при FAIL): передавать `min(request_deadline, phase_started + phase_budget)` в watcher и каждый HTTP-шаг, делить один фазовый deadline между повторами (F-005).
4. РИСКИ: VERDICT=FAIL
   WHY=Clean-room L2 зелёный (466 passed, обратный порядок, VER-004), однако повторное исполнение после execution.started и ложный success breaker при watchdog остаются прод-рисками, не покрытыми зелёными тестами. F-001, F-002, F-003, F-006.
   СОВЕТЫ (при FAIL): закрыть F-001, F-002, F-003, F-005 различающими поведенческими тестами и повторить L2; F-006 оставить non-blocking follow-up по фактическому usage при раннем native terminal.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Гибрид serve+run — единственный подтверждённый путь к дельтам: `run` игнорирует `*.delta` (F-17/F-18), прямой Zen не подтверждён (F-24/F-25), общий демон теряет ротацию IP; исправления локальны, переписывания транспорта не требуется.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Ровно 3 файла конверта, 0 внешних runtime-зависимостей, публичные маршруты/SSE и замороженные `_run_env`/Google-срезы сохранены; Non-Goals и Forbidden Scope не нарушены, VER-006/VER-007 законно DEFERRED_L3 до ACCEPT.
POSITIONS: 1/1
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


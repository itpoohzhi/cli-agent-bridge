# Стенограмма дебатов Совета Тимлидов по коду — Cycle 7 (run `analyst-teamlead-zen-realtime-reasoning-20261025`)

## Раунд R1 (`panel/council/r82`)

### Seat 1 (`skeptic`, `muse-wonder-full-1.0`)

PANEL-NONCE: dd4e956ae49a9397
ARTIFACT-SHA256: 5efd0909ef787d0125d23fe80ae837ad4d39d28975f2e455501c8f98b937f830
Подтверждение: общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до `<!-- КАНОН-КОНЕЦ -->` в загруженном контексте; проектных `AGENTS.md`/`.agents/AGENTS.md`/`CLAUDE.md` в пакете нет (факт-карта: корневого `AGENTS.md` в репозитории нет), оценка — по приложенным стандартам `aisdlc-gcge`.

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Verify-Fixed RW-001: `Run._execute_once` возвращает `first_event_at/first_token_at`, watchdog даёт `rc=1` и `transient_failure`, `Handler._serve_json` при `state in (first_event_timeout,first_token_timeout,stall_timeout)` ставит `xs["exit_reason"]=state` и 502 `opencode <фаза>` вместо `provider_fatal` (diff `server.py` блок `watchdog_phase`); оракул `test_c7_rw001_json_run_watchdog_oexit_reason_and_phase_timings` в L2 зелёный. Verify-Fixed RW-002: `_is_delivered()` в `_serve_one_attempt` включает `result["first_event_at"] is not None`, барьер монотонен `delivered_any` в SSE и JSON; оракул `test_c7_rw002_execution_started_before_prompt_headers_sets_delivered_and_blocks_run_fallback` зелёный, `record_success` не вызывается. Публичный контракт `/health,/v1/models,/v1/chat/completions`, SSE-форма, `finish_reason`, `usage` не изменены (REQ-002); замороженные `_run_env/_stream_google_sse/_execute_google_once` побайтно совпали (`code-gate.json: google_direct_unchanged=True, run_env_sha256=1c51b28f…`).
2. ПОЛНОТА: VERDICT=PASS
   WHY=REQ-001..REQ-020/AC-001..AC-026 закрыты по `verification-traceability.md` поштучно; AC-026 red→green: L2-RED `rc=1` на `origin/dev`, кандидат 471 passed. FU-001 закрыт: `_drain_serve_step_usage` дочитывает только `session.step.ended` своей сессии/`assistantMessageID` в окне 0.15 с без пропуска следующего шага, оракул `test_c7_fu001_native_tool_call_captures_step_ended_usage` зелёный. VER-006/VER-007 законно `DEFERRED_L3` до ACCEPT (Forbidden Scope: живой `~/.dsh` до вердикта не мутируется) — не пропуск цикла кода. Остаточные наблюдения reverse-spec §4.2 (пустой serve-stream `stop`, многострочный SSE `data:`, usage без `assistantMessageID`) не имеют воспроизводимого дефекта на замороженных wire-фикстурах v2.1.2 и не нарушают ни одного AC — по правилам цикла N>=2 это non-blocking follow-up, не FAIL.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Verify-Fixed RW-004: `_ctrl_http(phase_deadline=…)`, `ready_deadline` для `/api/session/active`, отдельный дедлайн `POST /api/session`, `sub_deadline=min(deadline, now+FIRST_EVENT_TIMEOUT_S)` в `_open_serve_events/_watch_serve_connection`; оракул `test_c7_rw004_startup_http_phases_enforce_own_budget_under_long_request_deadline` при `TIMEOUT_S=30` и капающих заголовках прерывает фазу <<30 с с `lease.cleanup()`. Транспорт по умолчанию выключен (`dynamic_config` default false, `TRANSPORT=run`/override 0/disable-файл старше forced serve), откат — legacy `opencode run` без деплоя кода; 0 внешних зависимостей вне stdlib, ровно 3 файла конверта.
4. РИСКИ: VERDICT=PASS
   WHY=Verify-Fixed RW-003: на legacy SSE `transient_failure = has_watchdog or had_provider_error or …` до единственного `attempts.attempt_done(transient_failure, attempt_output and not transient_failure)`; оракул `test_c7_rw003_legacy_sse_watchdog_records_breaker_failure_with_and_without_output` доводит breaker до OPEN на всех трёх фазах с выводом и без, `record_success` не вызывается. Full Suite L2: `VER-001` 471 passed, `VER-002` unittest rc=0, `VER-003/003b` rc=0, `AC-023` reversed rc=0, `VER-004` ruff/basedpyright errors=0. Безопасность: `_serve_env` allowlist+`OPENCODE_DB=:memory:`+случайный пароль `secrets.token_hex(16)`, `_error_payload`/`_mask_secrets` чистят message и detail, permission `ask_reject`→reject+interrupt, `form.created` cancel до проверки схемы, чужой listener отклоняется по `lsof`+PGID, lease reaper проверяет UID/симлинк/`lstart`. Гонка bind-пробы порта и потомки вне PGID остаются известным остаточным риском, смягчены проверкой владельца и killpg TERM→KILL с подтверждением смерти группы; воспроизводимого обхода в пакете нет.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Варианты L/A1/A2/B/C сравнены в `handoff-architect.md` §4 по фактам F-17..F-27: L не даёт реалтайма (RC-1), B недоказуем (429 без заголовков CLI), A2 теряет ротацию IP; выбранный гибрид A1+legacy fallback повторяет прецедент `muse-bridge` (ADR-0004) и сводится к существующим кортежам `(etype,payload)` ниже `parse_opencode_event`, не переписывая верхний слой. Неоправданного раздувания в дельте цикла 7 нет: правки RW-001..RW-004 точечны (watchdog-классификация, один предикат доставки, один флаг в `attempt_done`, фазовые дедлайны), FU-001 — одна ограниченная функция дочитывания usage.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Границы слоёв сохранены: serve-адаптер мапит wire-события в канонические кортежи legacy-пути (`_map_serve_event`), native-вызовы идут через канонический `_native_to_tool_calls` (fit_args/multiedit не продублированы), Google-direct выбирается до serve и не тронут. Scope-diff: ровно `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`; чужих KEY/файлов нет, `dependencies=[]`. HL-гейты конверта: очереди ограничены (SSE 4096, строка 1 МиБ, тело 8 МиБ, stderr-tail 16 КиБ), `MAX_TOTAL_SPAWNS=3` общий для serve+run, Full Jitter и Retry Budget переиспользованы, cleanup группы в `finally`/`_cleanup_serve_attempt` с бюджетом, `O-EXIT/v1` расширен `transport/first_event_ms/ttft_ms/transport_history` на каждом выходе.

SUB Корректность/логика: PASS — `server.py:_is_delivered/_map_serve_event` + `test_c7_rw002…` зелёный в VER-005 (92 passed)
SUB Корректность/граничные условия: PASS — `tests/test_realtime_reasoning.py:test_c6_fu001_fu002_sse_line_body_byte_caps_and_strict_usage_ints` (bool/отрицательные токены, лимиты 1 МиБ/8 МиБ)
SUB Корректность/обработка ошибок: PASS — `server.py:_serve_attempt_error_reason/FALLBACK_DECISION_TABLE`, fail-closed 400/401/403/404/422, `test_prompt_http_4xx_fails_closed_without_run_fallback`
SUB Полнота/покрытие AC: PASS — `verification-traceability.md` REQ-001..020/AC-001..026 все PASS, VER-006/007 DEFERRED_L3 до ACCEPT
SUB Полнота/пропущенные ветки: PASS — `test_c6_rw004_ac016_serve_step_interruption_matrix` + `test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence` (serve/run × SSE/JSON)
SUB Реализуемость/общее: PASS — kill-switch `dynamic_config.json`/env/disable-файл, `test_rw006_invalid_utf8_falls_back_and_recovers`, дефолт выключен (REQ-003)
SUB Риски/безопасность: PASS — `server.py:_serve_env/_mask_secrets/_error_payload`, `test_rw008_provider_secrets_hidden_in_sse_json_and_log`
SUB Риски/данные: PASS — `OPENCODE_DB=:memory:`, статусы `[мост]` не в `_messages_to_prompt` (`test_reasoning_content_excluded_from_prompt`, AC-007)
SUB Риски/прод: PASS — `_ServeLease.cleanup/_startup_reaper/_stop_proc`, `test_c6_rw007_fu003_dripping_interrupt_delete_still_cleans_up_under_7s` (AC-011)
SUB Риски/regression red→green: PASS — `execution-evidence.md` L2-RED rc=1 на origin/dev, кандидат VER-001 rc=0 (AC-026/REQ-020)
SUB Риски/Full Suite (L2): PASS — `receipts/code-gate.json` status=PASS, 471 passed + reversed AC-023 rc=0
SUB Риски/scope-diff: PASS — `teamlead/candidate-manifest.json` ровно 3 файла, замороженные хэши `_run_env`/Google-direct MATCH (REQ-018)
SUB Альтернативы/общее: PASS — `handoff-architect.md` §4 сравнение L/A1/A2/B/C, гибрид по прецеденту muse-bridge ADR-0004
SUB Соответствие контексту/общее: PASS — stdlib-only `ThreadingHTTPServer`, канонический `_native_to_tool_calls`, O-EXIT/v1 `transport/first_event_ms/ttft_ms` (REQ-016)

ОБЩИЙ ВЕРДИКТ: PASS
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 0


### Seat 2 (`realist`, `grok-4.7-high`)

PANEL-NONCE: 999a3d5aca96cb3a
ARTIFACT-SHA256: 5efd0909ef787d0125d23fe80ae837ad4d39d28975f2e455501c8f98b937f830
Канон прочитан: AGENTS.md, 430 строк

Корневого `AGENTS.md` в репозитории нет. Профильные стандарты `aisdlc-gcge` приложены в пакете и учтены построчно.

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Цикл 7 закрывает ровно конверт: три файла `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`, ноль внешних runtime-зависимостей. Verify-fixed по брифу цикла 6 закрыт на строках и зелёным L2. RW-001: `fatal_error` выставляется только на детерминированной ошибке провайдера (`server.py:5542`); `Run._execute_once` возвращает `first_event_at`/`first_token_at` (`server.py:5624-5625`); исчерпание watchdog в JSON даёт 502 `opencode <фаза>` и `xs["exit_reason"]=<фаза>` (`server.py:7656-7675`). RW-002: `_is_delivered()` включает `first_event_at` (`server.py:3396-3403`), поэтому `session.execution.started` до заголовков prompt закрывает fallback на `run`. RW-003: legacy SSE считает watchdog транзиентным отказом до единственного `attempt_done` (`server.py:6890-6901`). RW-004: стартовые фазы имеют собственные дедлайны, сторож `_watch_serve_connection` только закрывает сокет (`server.py:2593-2621`), `_serve_http` повторно проверяет фазу после `read1` и пропускает `settimeout` на закрытом fd HTTP/1.0 (`server.py:2624-2712`). FU-001: `_drain_serve_step_usage` дочитывает `session.step.ended` своего шага в окне 0,15 с (`server.py:3292`, вызов `server.py:3822`). Публичный контракт SSE сохранён; строки `[мост]…\n` заданы REQ-004/REQ-005. Замороженные `_run_env`, `_stream_google_sse`, `_execute_google_once` совпали с эталоном (`google_direct_unchanged=True`, `run_env_sha256=1c51b28f…`). L2: `VER-001` rc=0, 471 passed; `O-EXIT/v1` в логе несёт `exit_reason=first_event_timeout|first_token_timeout|stall_timeout` и `first_event_ms`/`ttft_ms`.
2. ПОЛНОТА: VERDICT=PASS
   WHY=Матрица `verification-traceability.md` закрывает REQ-001..REQ-020 и AC-001..AC-026 поштучно статусом PASS, кроме законно отложенных VER-006/VER-007 (`DEFERRED_L3` до ACCEPT). Крайние ветки покрыты оракулами того же модуля: realtime до конца апстрима (AC-026), три фазы watchdog в SSE и JSON, барьер доставки, fail-closed 400/401/403/404/422, `form.created` cancel+interrupt до проверки схемы (`server.py:3694-3721`), native tool usage, маскирование секретов, потолок `MAX_TOTAL_SPAWNS=3` на связке serve+run. REQ-017 приводит `test_step_interruption.py` к потолку 3 запуска и изолирует `_RetryBudget` на тест; AC-023 (обратный порядок) rc=0. Живой heavy-path владельца в этом вердикте не заявлен и не требуется до ACCEPT.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Транспорт — короткоживущий `opencode serve` на запрос со stdlib (`http.client`, `subprocess`, `select`), kill-switch `OPENCODE_ZEN_BRIDGE_TRANSPORT` / `dynamic_config.json` / файл `disable-serve`, дефолт выключен. Ресурсы попытки снимаются в `finally`: interrupt/DELETE, `_ServeLease.cleanup`, reaper lease при старте, `OPENCODE_DB=":memory:"`, отдельный `XDG_STATE_HOME`. Фазовые бюджеты и общий `TIMEOUT_S` не дают зависшему cleanup держать слот. Выкат `~/.dsh` запрещён до ACCEPT (Forbidden Scope); операционная цена A1 ограничена слотами, `MAX_TOTAL_SPAWNS=3` и `_StartupGate`.
4. РИСКИ: VERDICT=PASS
   WHY=Clean-room L2 (`receipts/code-gate.json`, `execution-evidence.md`): `red_sensitivity_rc=1` на `origin/dev` (ожидаемый RED AC-026), на кандидате `VER-001`/`VER-002`/`VER-003`/`VER-003b`/`VER-005`/`AC-023` все rc=0, 471 passed. `basedpyright` 0 ошибок; новый тест — 0 предупреждений. Секреты: пароль serve — `secrets.token_hex(16)`, `_error_payload` идёт через `_clean_err`/`_mask_secrets`, allowlist env, пароль и proxy-креды не попадают в клиентский текст (оракул RW-008 зелёный). Регрессии watchdog, барьера доставки, breaker и HTTP/1.0 закрыты отдельными тестами и полным suite. Скрытого долга, ломающего инвариант потолка спавнов или Google-direct, в дельте нет.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Путь A1 с откатом на `opencode run` — выбранный архитектором гибрид, который закрывает RC-1 (дельты) вместе с RC-2/RC-3. Дельта цикла 7 точечная: гонка закрытия HTTP/1.0 в стороже и `_serve_http`, без переписывания транспорта. `FALLBACK_DECISION_TABLE` остаётся декларативной; исполняют те же ветки retry/fail-closed, что уже зелёные на L2. Более дешёвый путь «только watchdog на `opencode run`» не даёт реалтайма (F-17, F-18) и постановкой не принят.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Граница слоёв сохранена: wire `serve` сводится к кортежам `(etype, payload)` через `_map_serve_event`, верхний SSE/JSON и `ToolCallParser` не переписываются. Scope — только `bridges/opencode-zen-bridge/` и тесты моста. Запрещённый контур не тронут: DSH, `muse-bridge`, Google-direct, `zen_catalog.py`, коммит `dynamic_config.json`, внешние зависимости (`pyproject.toml` `dependencies = []`). Политика инструментов `ask_reject` с reject+interrupt эквивалентна изоляции REQ-012. `O-EXIT/v1` расширен полями REQ-016 (`server.py:3928-3947`).

SUB Корректность/логика: PASS — evidence (server.py:3396-3403, server.py:5542, server.py:5624-5625, server.py:7656-7675, RW-001/RW-002, VER-001 rc=0)
SUB Корректность/граничные условия: PASS — evidence (server.py:2593-2712 HTTP/1.0 fileno и check_phase после read1; server.py:3694-3721 form.created; server.py:3822 окно usage 0,15 с; test_c7_rw004/test_c6_rw007 rc=0)
SUB Корректность/обработка ошибок: PASS — evidence (server.py:6890-6901 watchdog → transient_failure; ServeSecurityError fail-closed; L2 exit_reason=first_*_timeout/stall_timeout/provider_fatal)
SUB Полнота/покрытие AC: PASS — evidence (verification-traceability.md REQ-001..020 / AC-001..026 PASS; VER-006/VER-007 DEFERRED_L3)
SUB Полнота/пропущенные ветки: PASS — evidence (test_realtime_reasoning.py AC-026, RW-001..004, FU-001, AC-016/AC-017; VER-005 92 passed)
SUB Реализуемость/общее: PASS — evidence (stdlib, kill-switch, OPENCODE_DB=:memory:, lease cleanup finally, Forbidden Scope до ACCEPT)
SUB Риски/безопасность: PASS — evidence (secrets.token_hex, _mask_secrets/_clean_err, allowlist, оракул RW-008; пароль serve не в логе)
SUB Риски/данные: PASS — evidence (server.py:3292 sessionID+assistantMessageID; usage из step.ended; SSE line 1 МиБ / HTTP body 8 МиБ)
SUB Риски/прод: PASS — evidence (MAX_TOTAL_SPAWNS=3, слоты, фазовые дедлайны server.py:2593-2712; живой :9883 отложен протоколом)
SUB Риски/regression red→green: PASS — evidence (L2-RED-sensitivity rc=1 на origin/dev; VER-005 и VER-001 rc=0 на кандидате)
SUB Риски/Full Suite (L2): PASS — evidence (execution-evidence.md VER-001/002/003/003b/005 и AC-023 rc=0, 471 passed)
SUB Риски/scope-diff: PASS — evidence (candidate-manifest.json ровно 3 файла; frozen sha256 MATCH; google_direct_unchanged=True)
SUB Альтернативы/общее: PASS — evidence (дельта цикла 7 — точечный CG-HTTP-CLOSE-RACE в server.py:2593-2712; гибрид A1 задан handoff-architect)
SUB Соответствие контексту/общее: PASS — evidence (pyproject.toml dependencies=[]; scope-and-contracts: публичный SSE сохранён, REQ-004/005 задают [мост]; Forbidden Scope не нарушен)

ОБЩИЙ ВЕРДИКТ: ACCEPT
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 0


### Seat 3 (`visionary`, `gpt-6.1-sol-high`)

PANEL-NONCE: 7ebd68134d56ef2e
ARTIFACT-SHA256: 5efd0909ef787d0125d23fe80ae837ad4d39d28975f2e455501c8f98b937f830

Прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком в переданном тексте до `<!-- КАНОН-КОНЕЦ -->` и приложенные правила AI-SDLC; локальные файлы правил рабочей папки пока не проверены. Проверю закрытие RW-001..RW-004, FU-001 и все 14 подкатегорий. Тесты запускать не буду; SEED пересчитаю независимо.

SEED совпал с манифестом. Все четыре исправления RW-001..RW-004 присутствуют в diff; приложенные L2-логи подтверждают прохождение их регрессионных тестов. Проверяю соседние ветки: пакет нативных вызовов инструментов, повторы после ранней ошибки провайдера и отмену во время ожидания запуска.

RW-001..RW-004 принимаю как исправленные в заявленном объёме; FU-001 добавляет ограниченное дочитывание usage. В соседних ветках обнаружены отдельные проблемы: потеря второго native-вызова того же шага, отсутствие serve-повтора после ранней SSE-ошибки и учёт локального дедлайна как отказа провайдера. Завершаю проверку ошибок протокола и полноты RED-свидетельства AC-026.

PANEL-NONCE: 7ebd68134d56ef2e
ARTIFACT-SHA256: 5efd0909ef787d0125d23fe80ae837ad4d39d28975f2e455501c8f98b937f830

Общий канон `~/Мой диск/Context/AGENTS.md` прочитан полностью в приложенном тексте до `<!-- КАНОН-КОНЕЦ -->`; приложенные проектные стандарты AI-SDLC прочитаны. В рабочей папке `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` отсутствуют. SHA-256 всех трёх файлов кандидата совпали с манифестом. Тесты самостоятельно не запускались.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL

   WHY=RW-001 и RW-002 исправлены: JSON сохраняет фазу watchdog и времена, а `_is_delivered()` учитывает начало исполнения по SSE. Однако ранняя транзиентная ошибка SSE необоснованно завершает запрос, а некорректная Unicode-дельта обходит управляемую обработку протокольной ошибки.

   SUB Корректность/логика: FAIL — получение execution event запрещает также допустимый serve-повтор ранней ошибки, F-001 (`server.py:6034`; REQ-009).
   
   SUB Корректность/граничные условия: FAIL — одиночный surrogate сохраняется и достигает UTF-8-сериализации, F-002 (`server.py:1785`, `server.py:5800`; python-standards.md §14).
   
   SUB Корректность/обработка ошибок: FAIL — `UnicodeEncodeError` не преобразуется в `ServeProtocolError` и терминальный ответ (`server.py:1785`, `server.py:5798`; F-002).

   F-001 [pre-existing]
   
   priority: blocking  
   locations: `bridges/opencode-zen-bridge/server.py:6034`, `bridges/opencode-zen-bridge/server.py:6039`  
   Правило: REQ-009, сохранение повторов транзиентных отказов; барьер доставки запрещает fallback в `run`, но допускает повтор `serve`.  
   Evidence: условие `if not _delivered_err and attempts.allow_retry(...)`. После `session.execution.started` значение `_delivered_err=True`. Если следующим событием приходит `session.execution.failed` с 429/503 без текста и reasoning, общий повтор пропускается; `_incomplete_step_signal("", "", ...)` также возвращает 0. Запрос заканчивается ошибкой после первой попытки при свободном бюджете. JSON-ветка в `server.py:7328` допускает такой повтор.  
   Исправление: разделить предикаты запрета fallback и допустимости serve-повтора; раннюю транзиентную ошибку без модельного вывода повторять через serve.  
   Проверка: FakeServe возвращает execution-started → 429/503 без токенов, следующая попытка успешна; SSE и JSON используют две serve-попытки, без запуска `run`.

   F-002 [pre-existing]
   
   priority: blocking  
   locations: `bridges/opencode-zen-bridge/server.py:1785`, `bridges/opencode-zen-bridge/server.py:5800`, `bridges/opencode-zen-bridge/server.py:7460`  
   Правило: python-standards.md §3, §14; некорректный вход транспорта должен завершаться классифицированной ошибкой.  
   Evidence: `_combine_surrogates()` при ошибке декодирования возвращает исходную строку. JSON-значение `"\ud800"` проходит проверки строкового типа. В SSE последующее `.encode("utf-8")` выбрасывает `UnicodeEncodeError`; в JSON та же строка сохраняется в итоговом сообщении и достигает `_send`. Управляемая классификация `invalid_serve_event` отсутствует.  
   Исправление: отклонять непарные surrogate на границе serve-протокола через `ServeProtocolError`, сохраняя корректные пары без изменения текста.  
   Проверка: reasoning/text с непарным старшим и младшим surrogate в SSE и JSON дают управляемую ошибку, cleanup и корректный O-EXIT; корректная пара остаётся зелёной.

   СОВЕТЫ (при FAIL): выполнить исправления и проверки F-001, F-002; сохранить исправленный монотонный барьер RW-002.

2. ПОЛНОТА: VERDICT=FAIL

   WHY=FU-001 реализован для одного native-вызова, но дочитывание usage теряет остальные вызовы того же шага. Это ограничивает стратегическую ценность транспорта: пакетные действия агента должны сохраняться полностью.

   SUB Полнота/покрытие AC: FAIL — AC-016/AC-017 не подтверждены для нескольких native-вызовов одного шага (`server.py:3818`, `server.py:3316`; F-003).
   
   SUB Полнота/пропущенные ветки: FAIL — второй native-вызов текущего `assistantMessageID` отбрасывается вместе с событиями следующего шага (`server.py:3309`; F-003).

   F-003 [pre-existing]
   
   priority: blocking  
   locations: `bridges/opencode-zen-bridge/server.py:3818`, `bridges/opencode-zen-bridge/server.py:3829`, `bridges/opencode-zen-bridge/server.py:3309`, `bridges/opencode-zen-bridge/server.py:3316`  
   Правило: REQ-011, REQ-012, AC-016, AC-017; полнота преобразования native tool calls.  
   Evidence: после первого завершённого native-вызова при `emulate_tools` устанавливается `terminal="tool_calls"`, затем вызывается `_drain_serve_step_usage()` и выполняется `break`. Дрейнер пропускает любое событие, отличное от `session.step.ended`. Поэтому последовательность `called(c1,m1) → called(c2,m1) → step.ended(m1)` выдаёт только `c1`. Новый тест FU-001 проверяет исключение вызова из другого сообщения `m2`, но не сохранение второго вызова из `m1`.  
   Исправление: в ограниченном окне закрытия шага обрабатывать native lifecycle текущего сообщения и его usage; события следующего сообщения исключать.  
   Проверка: два разных native-вызова одного шага приходят в SSE и JSON ровно по одному разу, usage учитывается один раз, вызов следующего шага отсутствует.

   Поштучная сверка требований и AC:

   - REQ-001 — AC-001, AC-002: PASS L2 для проверенных дельт и сокетных задержек.
   - REQ-002 — AC-003: PASS по форме HTTP/OpenAI SSE; непредусмотренного расширения схемы не обнаружено.
   - REQ-003 — AC-004: PASS; legacy, конфигурационный флаг и аварийное отключение сохранены.
   - REQ-004 — AC-005: PASS L2 для thinking-режима, включая ожидание gate и limiter.
   - REQ-005 — AC-006, AC-007: PASS на приложенных проверках текста и исключения reasoning из replay.
   - REQ-006 — AC-008: PASS L2 для watchdog после запуска транспорта.
   - REQ-007 — AC-009, AC-010: PASS L2; три фазы различаются.
   - REQ-008 — AC-011, AC-012: FAIL для ожиданий перед запуском, F-004.
   - REQ-009 — AC-013: потолок сохранён; AC-014: разделители проверены. Требование в целом FAIL из-за F-001 и F-005.
   - REQ-010 — AC-015: PASS по существующему парсеру и тестам разбиения.
   - REQ-011 — AC-016: FAIL для пакета native-вызовов, F-003.
   - REQ-012 — AC-017: FAIL для полноты преобразования пакета native-вызовов; reject/form-пути представлены.
   - REQ-013 — AC-018: PASS по сохранённому `_run_env`, вызову ротации и общим защитам.
   - REQ-014 — AC-019: PASS L2 для представленных usage-фикстур; FU-001 имеет ограниченное окно дочитывания.
   - REQ-015 — AC-020: PASS по маскированию, случайному паролю и санитарной обработке env.
   - REQ-016 — AC-021: PASS L2; RW-001 подтверждён проверкой конечного логового sink.
   - REQ-017 — AC-022, AC-023: PASS; полный и обратный порядок зелёные.
   - REQ-018 — AC-024: PASS; замороженные функции и Google-тесты сохранены.
   - REQ-019 — AC-025: DEFERRED_L3 согласно разрешённому порядку приёмки.
   - REQ-020 — AC-026: GREEN подтверждён; поведенческий RED остаётся INCONCLUSIVE, F-006.

   СОВЕТЫ (при FAIL): исправить F-003 и добавить проверку полноты нескольких вызовов одного шага.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL

   WHY=RW-004 исправляет фазовые HTTP-дедлайны, но общий бюджет и отмена клиента не охватывают предшествующее ожидание StartupGate и spawn limiter.

   SUB Реализуемость/общее: FAIL — последовательные ожидания перед spawn не контролируют отмену и остаток общего срока на всём участке (`server.py:5904`, `server.py:7194`; F-004).

   F-004 [pre-existing]
   
   priority: blocking  
   locations: `bridges/opencode-zen-bridge/server.py:5353`, `bridges/opencode-zen-bridge/server.py:5904`, `bridges/opencode-zen-bridge/server.py:6536`, `bridges/opencode-zen-bridge/server.py:7194`  
   Правило: REQ-008, R-BULK-I1, feature.md §2 — дедлайн и отмена на каждом шаге I/O.  
   Evidence: `gate.acquire()` использует собственный `STARTUP_WAIT_S`, не остаток запроса; затем limiter может отдельно спать до `SPAWN_WAIT_MAX_S`. Между ожиданиями нет проверки клиента. При стандартных пределах участок может занять около 10 секунд, превышая требование обнаружения отключения ≤5 секунд. На legacy-путях после этих ожиданий отсутствует повторная проверка дедлайна непосредственно перед `_spawn_with_stdin`, поэтому процесс может запускаться уже после истечения бюджета.  
   Исправление: сделать ожидания ограниченными общим дедлайном и прерываемыми отменой; перед каждым spawn повторно проверять обе причины остановки и освобождать резервы.  
   Проверка: занятый gate, затем задержанный limiter и FIN клиента; обнаружение ≤5 секунд, отсутствие новых запусков после отмены или истечения deadline, освобождённые слоты и резервы.

   Verify-Fixed RW-004: PASS для HTTP-фаз — `server.py:3458`, `server.py:3496`, `server.py:3174`; соответствующий тест `tests/test_realtime_reasoning.py:2704` входит в зелёный L2.

   СОВЕТЫ (при FAIL): закрыть F-004 на serve/run и SSE/JSON, сохранив отдельные HTTP-фазовые бюджеты.

4. РИСКИ: VERDICT=FAIL

   WHY=Независимый L2 зелёный, RW-003 исправлен в части передачи watchdog в `attempt_done`. Однако локальное исчерпание дедлайна загрязняет здоровье upstream. Дополнительно RED-свидетельство AC-026 не достигает сокетного оракула.

   SUB Риски/безопасность: PASS — случайный Basic-пароль, loopback, ограниченный env, reject/cancel и маскирование представлены (`server.py:1879`; REQ-012, REQ-015).
   
   SUB Риски/данные: FAIL — пакет native-вызовов теряет элементы, а некорректный Unicode обрывает выдачу (`server.py:3316`, `server.py:1785`; F-002, F-003).
   
   SUB Риски/прод: FAIL — локальный deadline учитывается как транзиентный отказ upstream (`server.py:5995`, `server.py:7284`; F-005).
   
   SUB Риски/regression red→green: N/A — поведенческий RED AC-026 INCONCLUSIVE: подтверждённый rc=1 возникает в `setUp` до сокетных assertions (`tests/test_realtime_reasoning.py:900`; `execution-evidence.md`, L2-RED-sensitivity).
   
   SUB Риски/Full Suite (L2): PASS — независимые логи: 471 тест компонента, 894 корневых теста, 92 realtime-теста и обратный порядок зелёные (`execution-evidence.md`, VER-001..VER-005, AC-023).
   
   SUB Риски/scope-diff: PASS — ровно три разрешённых файла; SHA-256 совпали, замороженные функции сохранены (`candidate-manifest.json`; VER-004).

   F-005 [pre-existing]
   
   priority: blocking  
   locations: `bridges/opencode-zen-bridge/server.py:3382`, `bridges/opencode-zen-bridge/server.py:5995`, `bridges/opencode-zen-bridge/server.py:7284`  
   Правило: FALLBACK_DECISION_TABLE, строка `client cancel/deadline/budget exhausted`: fail-closed, оба инкремента равны 0; R-BULK-I3.  
   Evidence: `ServeStartupDeadlineExceeded` превращается в `exit_reason="timeout"`. SSE и JSON включают `timeout` в общую ветку, вызывающую `attempts.attempt_done(True, False)`. Последующий `commit()` увеличивает счётчик upstream breaker даже при локальном истечении бюджета до доставки prompt. Серия таких запросов может открыть breaker здорового провайдера.  
   Исправление: выделить глобальный timeout как нейтральный терминальный исход; оставить отказами соответствующие фазовые watchdog и подтверждённые upstream failures.  
   Проверка: повторные deadline-отказы до prompt в SSE/JSON не увеличивают failures и не открывают breaker; first-token/stall failures продолжают учитываться.

   F-006 [pre-existing]
   
   priority: non-blocking  
   locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:900`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:922`  
   Правило: REQ-020, AC-026; testing.md «Тест должен воспроизводить баг».  
   Evidence: сырой RED-лог для `test_ac026_realtime_chunks_before_upstream_end` показывает `AttributeError` на `server.DYNAMIC_CONFIG_PATH` в `setUp`. Значение `red_sensitivity_rc=1` достоверно, но падение не доказывает воспроизведение задержанной доставки на клиентском сокете. GREEN измеряет требуемое поведение.  
   Исправление: обеспечить запуск сокетного оракула на baseline без зависимости setup от новых символов либо приложить отдельный совместимый поведенческий RED-прогон.  
   Проверка: baseline падает именно на количестве/времени клиентских дельт при продолжающемся upstream; кандидат проходит тот же оракул.

   СОВЕТЫ (при FAIL): исправить F-005; дополнить доказательство AC-026 по F-006. VER-006/VER-007 оставить `DEFERRED_L3` до разрешённой живой приёмки.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS

   WHY=Короткоживущий serve сохраняет ротацию IP и изоляцию запросов, а адаптер событий позволяет сохранить потребителя DSH. Legacy-only не решает реалтайм, общий демон осложняет ротацию, прямой Zen пока не имеет доказанной авторизации. Это существенное улучшение отзывчивости и основа для управляемых потоковых агентов; масштаб ограничен ресурсами локальных процессов, а не заявлен как неограниченный.

   SUB Альтернативы/общее: PASS — выбранный транспорт обоснован фактами и сохраняет запасной run; переписывание архитектуры ради закрытия замечаний не требуется (`handoff-architect.md` §4; `server.py:3324`).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS

   WHY=Границы локального stdlib-моста сохранены. Замечания требуют точечных исправлений транспорта и проверок.

   SUB Соответствие контексту/общее: PASS — три разрешённых файла, без новых runtime-зависимостей и изменения замороженных функций (`candidate-manifest.json`; `execution-evidence.md`, VER-004).

   Non-Goals проверены поштучно: публичная HTTP/SSE-схема и порт сохранены; DSH/ReasoningRow не изменены; преобразование reasoning ради превью не добавлено; выбор моделей/effort и каталог не переработаны; другие мосты и общие конфиги не изменены; внешние runtime-зависимости не добавлены.

   Forbidden Scope проверен поштучно: файлов вне разрешённой зоны нет; действующих секретов в diff не обнаружено; боевой контур до ACCEPT не мутировался по пакету; запрещённого обращения к keychain нет; прямых правок общей opencode.db нет; коммит/merge в защищённые ветки не выполнялся.

   Verify-Fixed: RW-001 PASS (`server.py:5624`, `server.py:7656`; тест `:741`); RW-002 PASS (`server.py:3399`; тест `:1243`); RW-003 PASS (`server.py:6891`; тест `:799`); RW-004 PASS для заявленных HTTP-фаз; FU-001 PASS для ограниченного дочитывания usage одного native-вызова. F-003 отдельно фиксирует незакрытый случай нескольких вызовов одного шага.

   SEED RECHECK: `seed_hex=dd66f2254a1714449011bd3841bf43993c785c47e60380a79aac3042ce3c2888`, `SEED=dd66f225`; ранжирование по полному `seed_hex` совпало: `gemini-4-argon-high → gpt-6.1-sol-high → grok-4.7-high → muse-wonder-full-1.0 → claude-sonnet-5-5-high`.

   Self-sweep 1–14 выполнен; все найденные замечания приведены выше. Живая бизнес-приёмка не заявляется.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 6


---

## Раунд D1 (`panel/council/r89`)

### Seat 1 (`skeptic`, `gpt-6.1-sol-high`)

PANEL-NONCE: 713f204814ee4766
ARTIFACT-SHA256: 5efd0909ef787d0125d23fe80ae837ad4d39d28975f2e455501c8f98b937f830

Общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком в переданном тексте до `<!-- КАНОН-КОНЕЦ -->`. Проектные файлы правил с диска не читались; приложенные стандарты AI-SDLC учтены. Тесты самостоятельно не запускались.

AGREE F-001 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:6034`, `:6039` — `_delivered_err` одновременно запрещает fallback и ограничивает serve-повтор. После `session.execution.started` он истинен даже без модельного вывода; ранний 429/503 пропускает обычный retry и достигает ошибки. Запрет fallback после RW-002 обоснован, запрет повторной serve-попытки — нет. JSON-ветка `:7328` различает эти случаи.

AGREE F-002 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:1785`, `:5800`, `:7460` — после неудачной склейки surrogate возвращается исходная строка. Непарный surrogate проходит строковую проверку и достигает UTF-8-сериализации. `UnicodeEncodeError` не входит в обработчики ошибок попытки, поэтому управляемая классификация протокольного отказа теряется. Отклонять такой вход следует на границе serve.

AGREE F-003 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3818`, `:3829`, `:3309`, `:3316` — первый native-вызов завершает основной цикл; последующее дочитывание принимает только `session.step.ended`. Второй native-вызов того же сообщения отбрасывается. Фильтрация следующего сообщения нужна, но не оправдывает потерю остальных вызовов текущего шага.

AGREE F-004 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:5353`, `:5904`, `:6536`, `:7194` — ожидания gate и limiter последовательно выполняются без общего прерываемого контроля отмены. На legacy-путях перед spawn нет повторной проверки клиента и истёкшего deadline. Возможны позднее обнаружение отключения и запуск уже ненужного процесса. Исправленные HTTP-дедлайны RW-004 этот участок не охватывают.

AGREE F-005 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3382`, `:5995`, `:7284` — локальный `ServeStartupDeadlineExceeded` превращается в `timeout`, затем проходит через `attempt_done(True, False)`. Это противоречит нейтральному исходу deadline exhaustion в `FALLBACK_DECISION_TABLE` и может открыть breaker здорового upstream.

AGREE F-006 rev=1 — проверил: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:900`, `:922`; сырой `execution-evidence.md`, `L2-RED-sensitivity` — baseline действительно падает в `setUp` на отсутствующем `DYNAMIC_CONFIG_PATH`, до измерения клиентских дельт. GREEN подтверждает потоковое поведение кандидата; данный RED доказывает несовместимость setup с baseline. Согласен с приоритетом **non-blocking** и необходимостью отдельного поведенческого RED-свидетельства.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 и RW-002 принимаю как исправленные. Однако F-001 выявляет смешение барьера доставки с разрешением повторов; F-002 — выход некорректного wire-входа за границу управляемой обработки ошибок.
   СОВЕТЫ (при FAIL): разделить запрет fallback и допустимость serve-retry; проверить ранние 429/503 с последующей успешной попыткой; отклонять непарные surrogate через `ServeProtocolError`; проверить обе формы ответа, cleanup и O-EXIT.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=F-003 показывает потерю части пакета native-вызовов одного шага. FU-001 закрыт для usage одного вызова, но полнота преобразования нескольких вызовов не обеспечена.
   СОВЕТЫ (при FAIL): при закрытии шага принимать оставшиеся native lifecycle-события текущего сообщения; исключать следующее сообщение; проверить два разных вызова в SSE/JSON, отсутствие дублей и однократный usage.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=RW-004 закрывает заявленные HTTP-фазы. F-004 оставляет перед ними участок ожиданий, который не соблюдает сквозной deadline и требование обнаружения отключения клиента.
   СОВЕТЫ (при FAIL): сделать gate/limiter прерываемыми по отмене и общему сроку; повторно проверять остановку непосредственно перед spawn; освобождать резервы; проверить FIN и истечение бюджета на serve/run × SSE/JSON.

4. РИСКИ: VERDICT=FAIL
   WHY=RW-003 исправлен, полный независимый L2 зелёный. Но F-005 нарушает разделение локальных отказов и здоровья upstream; F-002/F-003 создают риск оборванного ответа и потери действий. Поведенческий RED AC-026 по F-006 остаётся INCONCLUSIVE.
   СОВЕТЫ (при FAIL): выделить общий timeout в нейтральный терминальный исход без изменения breaker; проверить серию локальных deadline-отказов и сохранение учёта first-token/stall failures; дополнить RED-прогон совместимым сокетным оракулом.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve с резервным run обоснован реалтаймом, ротацией прокси и изоляцией запросов. F-001..F-005 устраняются внутри выбранной архитектуры; переписывание транспорта не требуется.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Три разрешённых файла, stdlib-only, сохранённые замороженные функции и публичная HTTP/SSE-схема соответствуют конверту. Non-Goals и Forbidden Scope по пакету соблюдены. VER-006/VER-007 законно отложены до ACCEPT; живая бизнес-приёмка не заявляется.

Прежний общий PASS пересматриваю по конкретным веткам F-001..F-005. Self-sweep выполнен; новых F-блоков нет.

POSITIONS: 6/6
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `muse-wonder-full-1.0`)

PANEL-NONCE: bb8ba6c4203eecdb
ARTIFACT-SHA256: 5efd0909ef787d0125d23fe80ae837ad4d39d28975f2e455501c8f98b937f830
Прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком до `<!-- КАНОН-КОНЕЦ -->` в загруженном контексте; проектных `AGENTS.md`/`.agents/AGENTS.md`/`CLAUDE.md` в пакете нет (корневого `AGENTS.md` в репозитории нет), оценка — по приложенным стандартам `aisdlc-gcge`.

AGREE F-001 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:6034` — повтор только при `not _delivered_err`; после `session.execution.started` `_is_delivered()` истинен (`server.py:3399`), а `_incomplete_step_signal("","",…)` даёт 0 (`server.py:1060` требует `body or thought`), поэтому ранняя транзиентная ошибка без вывода в SSE завершает запрос; JSON-ветка такой повтор допускает (`server.py:7328`). Асимметрия SSE/JSON на главном потоковом пути — воспроизводимый дефект дельты RW-002, фикс дешёвый (зеркалить JSON-условие `not texts`).

AMEND F-002 — priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:1785`; fix=отклонять непарный surrogate на границе serve через `ServeProtocolError` в следующем проходе — причина: `server.py:1783` — механизм верен (`return value` при `UnicodeError`), но источник — локальный доверенный `opencode serve`, валидных wire-фикстур с одиночным surrogate в пакете нет, корректные пары обрабатываются, транспорт по умолчанию выключен; падение ограничено одним запросом при cleanup в `finally`. Блокирующим для выката с kill-switch не считаю.

AMEND F-003 — priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:3818`, `bridges/opencode-zen-bridge/server.py:3309`; fix=сначала wire-фикстура двух `called` одного `assistantMessageID`, затем обработка native lifecycle текущего шага в окне дрейн — причина: `server.py:3829` — `break` после первого вызова и пропуск не-`step.ended` в дрейн (`server.py:3316`) механически верны, но доказательств, что реальный serve при `ask_reject`+interrupt (`server.py:3770`) эмитит второй `called` того же шага, в пакете нет; FU-001 принимался Советом цикла 6 как non-blocking с одним вызовом.

AMEND F-004 — priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:5904`, `bridges/opencode-zen-bridge/server.py:6536`; fix=прерываемые общим дедлайном/отменой ожидания gate+limiter — как follow-up — причина: `server.py:2104` — gate fail-open после `STARTUP_WAIT_S=5.0`, limiter ограничен `min(SPAWN_WAIT_MAX_S, attempts.remaining_s())` (`server.py:5906`), serve проверяет клиента до спавна (`server.py:3362`); во время ожидания процессов ещё нет, сирот не возникает, остаток — задержка обнаружения отмены до ~10 с только на предспавновом участке при контенции.

AMEND F-005 — priority=non-blocking; locations=`bridges/opencode-zen-bridge/server.py:5995`, `bridges/opencode-zen-bridge/server.py:7284`; fix=выделить стартовый `ServeStartupDeadlineExceeded` нейтральным исходом, генерационный `timeout` оставить отказом — причина: `server.py:2496` — `_pending_failure` коммитится один раз на запрос (`server.py:2500`), а `timeout` в основном рождается исчерпанием общего бюджета генерации (`server.py:3876`); стартовый вариант (`server.py:3382`) возможен лишь после уже израсходованного бюджета, поэтому «загрязнение breaker здорового провайдера» серией коротких запросов практически недостижимо.

AGREE F-006 rev=1 — проверил: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:900` — RED-лог в `execution-evidence.md` показывает `AttributeError: DYNAMIC_CONFIG_PATH` в `setUp` до сокетных assertions AC-026; `red_sensitivity_rc=1` достоверен как факт падения, но не как поведенческий RED. Приоритет автора non-blocking корректен: GREEN-оракул измеряет требуемые задержки, а соседние тесты RED падали поведенчески.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=F-001: ранняя транзиентная SSE-ошибка после `session.execution.started` без модельного вывода не повторяется через serve при свободном бюджете (`server.py:6034`), в отличие от JSON (`server.py:7328`); RW-001/RW-002 сами по себе закрыты, F-002 понижен до non-blocking.
   СОВЕТЫ (при FAIL): разделить предикаты запрета fallback и допустимости serve-повтора; повторять раннюю транзиентную ошибку без texts/reasonings через serve в SSE как в JSON; оракул FakeServe execution-started → 429/503 без токенов → успех второй попытки без запуска `run`; заодно закрыть F-002 на границе протокола.
2. ПОЛНОТА: VERDICT=PASS
   WHY=REQ-001..REQ-020/AC-001..AC-026 закрыты по `verification-traceability.md`; VER-006/VER-007 законно `DEFERRED_L3` до ACCEPT; F-003 понижен до non-blocking до wire-подтверждения мульти-вызова одного шага.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=RW-004 по HTTP-фазам закрыт; F-004 — ограниченный остаток предспавновых ожиданий без сирот и с fail-open gate; транспорт по умолчанию выключен, откат — legacy `run` без деплоя, ровно 3 файла и 0 внешних зависимостей.
4. РИСКИ: VERDICT=PASS
   WHY=Clean-room L2 зелёный (471 passed, reversed AC-023, VER-004 errors=0); F-005 понижен — breaker растёт не чаще раза на запрос и в основном на реальных генерационных таймаутах; F-006 — дефект доказательной базы RED, не кандидата.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Гибрид A1+legacy обоснован сравнением L/A1/A2/B/C в `handoff-architect.md` §4 и прецедентом muse-bridge; требуемый фикс F-001 — одна ветка условия, переписывания транспорта не нужно.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Публичный SSE/JSON-контракт и замороженные Google/`_run_env` сохранены, scope — только мост и его тесты, `dependencies=[]`; замечания D1 не требуют смены архитектуры или контракта.

POSITIONS: 6/6
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `grok-4.7-high`)

PANEL-NONCE: c62f1d0c7e63287f
ARTIFACT-SHA256: 5efd0909ef787d0125d23fe80ae837ad4d39d28975f2e455501c8f98b937f830

Канон прочитан: AGENTS.md, 430 строк. Корневого `AGENTS.md` в репозитории нет. Сужу заново по diff и строкам `server.py`.

AMEND F-001 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6034,bridges/opencode-zen-bridge/server.py:7328; fix=разделить запрет fallback на run и допустимость serve-повтора ранней транзиентной ошибки без токенов — причина: приёмка RW-002 допускает терминальную ошибку, а не обязывает второй serve. NEW: server.py:6034 `if not _delivered_err and attempts.allow_retry("serve_transient_error")` против server.py:7328 `if not texts and attempts.allow_retry(...)` (JSON не требует `not delivered`). ARG: skeptic R1 «по правилам цикла N>=2 это non-blocking follow-up, не FAIL».

F-002 оставляю blocking. NEW: server.py:1785 `return value` отдаёт непарный surrogate; server.py:5800 `chunk.encode("utf-8")` и server.py:5692 `json.dumps(...).encode("utf-8")` не ловятся обработчиками server.py:7099 и server.py:5699 (`BrokenPipeError`/`ConnectionResetError`/`OSError`). `UnicodeEncodeError` — `ValueError`, не `OSError`.

AMEND F-003 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3818,bridges/opencode-zen-bridge/server.py:3829,bridges/opencode-zen-bridge/server.py:3309,bridges/opencode-zen-bridge/server.py:3316; fix=в окне закрытия шага собирать native-вызовы того же assistantMessageID, не только usage — причина: FU-001 и AC-016/AC-017 не требуют второго вызова одного сообщения. NEW: server.py:3818 `if emulate_tools:` затем `break` после `_drain_serve_step_usage`; дрейнер на server.py:3316 пропускает всё, кроме `session.step.ended`. ARG: skeptic R1 «остаточные наблюдения reverse-spec … не нарушают ни одного AC — … non-blocking follow-up, не FAIL».

AMEND F-004 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5904,bridges/opencode-zen-bridge/server.py:5905,bridges/opencode-zen-bridge/server.py:6536,bridges/opencode-zen-bridge/server.py:7194; fix=прерывать StartupGate и spawn limiter остатком дедлайна и client-gone как follow-up — причина: приёмка RW-004 покрывает HTTP-фазы, лимитер уже режется `attempts.remaining_s()`. NEW: server.py:5904 `gate.acquire()` затем server.py:5905 `min(SPAWN_WAIT_MAX_S, attempts.remaining_s())`. ARG: realist R1 «RW-004: стартовые фазы имеют собственные дедлайны».

F-005 оставляю blocking. NEW: server.py:2488 «Нейтральные итоги (таймаут …) не считаются», но server.py:5995 и server.py:7284 вызывают `attempts.attempt_done(True, False)` для `timeout`; `commit()` пишет `record_failure()`. Таблица server.py:1729–1736: deadline = fail_closed, оба инкремента 0. server.py:3382–3386 мапит `ServeStartupDeadlineExceeded` в `exit_reason="timeout"` и `delivered=True`.

F-006 оставляю non-blocking. RED `test_ac026` падает в `setUp` на `DYNAMIC_CONFIG_PATH` (`tests/test_realtime_reasoning.py:900`) до сокетных assertions; GREEN измеряет дельты.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
WHY=RW-001 и RW-002 в заявленном объёме закрыты: JSON сохраняет фазу watchdog и времена, `_is_delivered()` на server.py:3396–3402 включает `first_event_at`. F-001 больше не блокирует: после `session.execution.started` повтор serve не обязателен, терминальная ошибка допустима. Блокер — F-002: непарный surrogate проходит `_combine_surrogates` (server.py:1785) и рвёт UTF-8-сериализацию SSE (server.py:5800) и JSON `_send` (server.py:5692) вне классификации `invalid_serve_event`.
СОВЕТЫ (при FAIL): на границе serve отклонять непарный surrogate через `ServeProtocolError` до `.encode("utf-8")`; корректные пары оставлять без изменения текста; SSE и JSON должны давать cleanup и `O-EXIT` с `invalid_serve_event`.

2. ПОЛНОТА: VERDICT=PASS
WHY=REQ-001..REQ-020 и AC-001..AC-026 закрыты матрицей `verification-traceability.md`; VER-006/VER-007 законно `DEFERRED_L3`. FU-001 дочитывает usage одного native-шага. F-003 (второй вызов того же шага) и F-006 (качество RED) — non-blocking follow-up, AC не нарушают.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
WHY=RW-004 закрыт для HTTP-фаз: сторож только закрывает сокет, `_serve_http` проверяет фазу после `read1` и пропускает `settimeout` на закрытом fd. Транспорт по умолчанию выключен, откат — legacy `run`, зависимости вне stdlib не добавлены. F-004 — follow-up до spawn, не дыра фазовых бюджетов.

4. РИСКИ: VERDICT=FAIL
WHY=L2 зелёный: 471 passed, обратный порядок AC-023 rc=0, VER-004 errors=0, замороженные хэши совпали, RW-003 учитывает watchdog в breaker. Секреты, allowlist и `ask_reject` на месте. Блокер F-005: локальный `timeout` до prompt идёт в `attempt_done(True, False)` (server.py:5995, server.py:7284) и `commit()` открывает upstream breaker здорового провайдера, вопреки docstring server.py:2488 и строке таблицы server.py:1729–1736. F-002 — тот же класс необработанного падения на данных транспорта.
СОВЕТЫ (при FAIL): считать глобальный timeout нейтральным исходом: не вызывать `attempt_done(True, False)` и не делать `allow_retry` для дедлайна до prompt; `first_token_timeout` и `stall_timeout` по-прежнему учитывать как отказы upstream. Закрыть F-002 до сериализации.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
WHY=Короткоживущий `serve` с откатом на `run` закрывает реалтайм (RC-1) и сохраняет ротацию IP. Legacy-only реалтайма не даёт, прямой Zen не доказан, общий демон теряет ротацию. Дельта цикла 7 точечная, переписывания транспорта нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
WHY=Ровно три файла конверта, `dependencies=[]`, публичная SSE-схема и порт сохранены, `[мост]` задан REQ-004/REQ-005, Google-direct и `_run_env` заморожены, `~/.dsh` до ACCEPT не мутировался. SEED RECHECK: `seed_hex=6ac3af291b0385acf0c4a6ed993775889c1291fbc8da93aa31a75ce5585f6e50`, `SEED=6ac3af29`; `ranked_order` по полному `seed_hex` совпал с манифестом r89: grok-4.7-high, muse-wonder-full-1.0, gemini-4-argon-high, gpt-6.1-sol-high, claude-sonnet-5-5-high.

POSITIONS: 0/0
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


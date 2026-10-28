# Стенограмма дебатов Совета Тимлидов по коду — Cycle 8 (run `analyst-teamlead-zen-realtime-reasoning-20261025`)

## Раунд R1 (`panel/council/r99`)

### Seat 1 (`skeptic`, `grok-4.7-high`)

PANEL-NONCE: 14f41025de37c906
ARTIFACT-SHA256: 1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8
Канон прочитан: AGENTS.md, 429 строк

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Цикл 8 закрывает ровно конверт `zen-realtime-reasoning` и пункты `RW-001..RW-003`/`FU-001..FU-003`. Ранний `session.execution.failed` (429/503) без токенов повторяет serve и держит барьер доставки: `server.py:6128-6145` (`not _has_model_output` → `allow_retry("serve_transient_error")`; `not _delivered_err and not force_serve` → fallback на run). Непарный суррогат даёт `ServeProtocolError` на границе `_combine_surrogates` (`server.py:1779-1787`), валидная пара сохраняется. Локальный `timeout` и `ServeStartupDeadlineExceeded` идут в `attempt_done(False, False)` без `allow_retry` (`server.py:6069-6072`, `server.py:7413-7416`). `first_event_timeout`/`invalid_serve_event` увеличивают `_ServeHealth`, а `first_token_timeout`/`stall_timeout` — pending failure breaker (`server.py:6095-6098`, `server.py:7441-7444`), что совпадает со строками `FALLBACK_DECISION_TABLE` (`server.py:1659`, `server.py:1667`). Публичные `/health`, `/v1/models`, `/v1/chat/completions` и форма SSE сохранены; `transport` в `/health` остаётся `opencode-zen-cli`. Замороженные `_run_env` / `_stream_google_sse` / `_execute_google_once` совпали с `code-gate.json` (`google_direct_unchanged=true`). L2: `VER-001` 478 passed, целевые `test_c8_rw001`, `test_c8_rw002`, `test_c8_rw003` зелёные.
2. ПОЛНОТА: VERDICT=PASS
   WHY=Матрица `verification-traceability.md` закрывает `REQ-001..REQ-020` и `AC-001..AC-026` на кандидате. `FU-001`: окно `_drain_serve_step_usage` забирает native-вызовы того же `assistantMessageID` и отсекает следующий шаг (`test_c8_fu001`, usage 123/45/cached 10/reasoning 6). `FU-002`: `_StartupGate.acquire` (`server.py:2117-2120`) и `_SpawnRateLimiter.acquire` обрываются по дедлайну и `is_client_gone`, резерв возвращается (`test_c8_fu002`). `FU-003`: `setUp` терпит отсутствие `DYNAMIC_CONFIG_PATH`/`LEASE_DIR`; на `origin/dev` `AC-026` падает `AssertionError` (1 чанк < 5), а не `AttributeError` в `setUp`. `VER-006`/`VER-007` законно `DEFERRED_L3` до `ACCEPT`. Повторный `gate.release` из `on_startup_ready` и `finally` (`server.py:6050`, `server.py:7404`) безопасен: `release()` выходит, если `_held` уже снят (`server.py:2139-2147`).
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Новых runtime-зависимостей нет (`pyproject.toml` `dependencies = []`). Транспорт — короткоживущий `opencode serve` через `--serve-helper`, lease `0700`, `killpg`, фазовые бюджеты HTTP и cleanup ≤ 7 с (`AC-011`), подтверждены L2. Kill-switch `TRANSPORT` / `REALTIME_SERVE_ENABLED` / `disable-serve` оставляет дефолт на `run`, пока флаг не включён (`REQ-003`). Сопровождение через полгода опирается на те же кортежи `(etype, payload)`, общий потолок `MAX_TOTAL_SPAWNS=3` и строку `O-EXIT/v1` с `transport`, `first_event_ms`, `ttft_ms`.
4. РИСКИ: VERDICT=PASS
   WHY=Секреты: пароль `secrets.token_hex(16)`, allowlist `_serve_env`, `OPENCODE_DB=":memory:"`, маскирование message/detail в `_error_payload` и Bearer/пароля/proxy userinfo. Fail-closed: HTTP 401/403 и 400/404/422 prompt → `ServeSecurityError` (`server.py:3706-3718`). Регрессия: `L2-RED-sensitivity` `rc=1`; кандидат `VER-001` 478 passed, `VER-002` 478 OK, `VER-005` 99 passed, `AC-023` reversed `rc=0`, `VER-004` `rc=0` (0 errors basedpyright, новый модуль 0 warnings). Дельта — ровно 3 файла конверта. `REQ-017`: потолок 3 запуска в `test_step_interruption.py`, свежий `_Resilience` и `patch.dict` на тест.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Цикл 8 — точечный rework поверх уже выбранного serve-транспорта с откатом на `run` до барьера доставки. Объём правок совпадает с `RW-001..RW-003` и `FU-001..FU-003`; архитектура не переписывалась, замороженные срезы не форматировались. Более дешёвый путь «только watchdog на `opencode run`» не закрывает `RC-1` (`REQ-001`), поэтому выбор A1-подобного транспорта для этой задачи оправдан.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Граница задачи — `bridges/opencode-zen-bridge/` и его тесты; `muse-bridge`, DSH, каталог Zen и Google-direct не затронуты. Слои моста сохранены: wire serve сводится к прежним кортежам ниже `parse_opencode_event`. Stdlib-only и ранний выход `--serve-helper` до тяжёлых импортов соблюдены (`VER-004`). Пересчёт сида: `seed_input` дословно совпал; `seed_hex` MATCH `64d44699b329a980bdb7efbd6f5bc436eeeed2d533cd9e8de15efa01780c3a52`; `ranked_order` по `SHA-256(seed_hex+'#'+slot_id)` на пуле default (`select_round_seats.py:235`, пять слотов) совпал с манифестом r99: grok-4.7-high, claude-sonnet-5-5-high, gpt-6.1-sol-high, muse-wonder-full-1.0, gemini-4-argon-high.

SUB Корректность/логика: PASS — server.py:6128-6145, RW-001 serve-retry без run после execution.started; VER-001 478 passed
SUB Корректность/граничные условия: PASS — server.py:1779-1787, непарный surrogate → ServeProtocolError; test_c8_rw002
SUB Корректность/обработка ошибок: PASS — server.py:3706-3718 fail-closed 401/403/400/404/422; server.py:6069 timeout нейтрален для breaker
SUB Полнота/покрытие AC: PASS — verification-traceability.md REQ-001..020 и AC-001..026 PASS; VER-006/007 DEFERRED_L3
SUB Полнота/пропущенные ветки: PASS — server.py:1659/6095 first_event → ServeHealth; JSON-близнец server.py:7441
SUB Реализуемость/общее: PASS — pyproject.toml dependencies=[]; helper/lease/killpg; L2 VER-001 rc=0
SUB Риски/безопасность: PASS — _serve_env allowlist, token_hex(16), _error_payload маскирует message и detail
SUB Риски/данные: PASS — OPENCODE_DB=:memory:, lease 0700, строгие неотрицательные token counts
SUB Риски/прод: PASS — kill-switch default run (REQ-003); живой путь VER-006/007 отложен до ACCEPT по Forbidden Scope
SUB Риски/regression red→green: PASS — l2-red.log rc=1, AC-026 AssertionError 1<5; кандидат VER-005 99 passed
SUB Риски/Full Suite (L2): PASS — VER-001/002/003/AC-023 rc=0, 478 passed
SUB Риски/scope-diff: PASS — candidate-manifest.json ровно 3 файла; frozen sha256 MATCH в code-gate.json
SUB Альтернативы/общее: PASS — цикл 8 точечно закрыл RW-001..003 и FU-001..003 без смены архитектуры
SUB Соответствие контексту/общее: PASS — seed_hex MATCH 64d44699b329a980bdb7efbd6f5bc436eeeed2d533cd9e8de15efa01780c3a52; ranked_order совпал с r99/manifest.json

ОБЩИЙ ВЕРДИКТ: ACCEPT
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 0


### Seat 2 (`realist`, `gpt-6.1-sol-high`)

PANEL-NONCE: b2896eeb90a0f629
ARTIFACT-SHA256: 1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8

Verify-Fixed: RW-001 — PASS; RW-002 — PASS; RW-003 — PASS для обеих serve-веток. FU-002 — PASS по отмене запуска и возврату резерва; FU-003 — PASS: приложенный RED достигает сокетного AssertionError AC-026. FU-001 закрыт для немедленно поступивших событий с `assistantMessageID`, но полнота инструментального шага остаётся ограниченной — F-001.

F-001
priority: blocking
locations: bridges/opencode-zen-bridge/server.py:3355, bridges/opencode-zen-bridge/server.py:3371, bridges/opencode-zen-bridge/server.py:3885, bridges/opencode-zen-bridge/server.py:3893
rule: REQ-011, REQ-014; feature.md §2 и §5 — захват потока с независимым сигналом полноты.
evidence: После первого native-вызова устанавливается `terminal="tool_calls"`; дочитывание ограничено `time.monotonic() + 0.15`. Истечение окна возвращает управление без подтверждения `session.step.ended`. Дополнительные tool-события обрабатываются только при истинном `assistant_message_id`. Поэтому второй вызов того же шага, пришедший через 200 мс, теряется; при отсутствии ID сообщения он игнорируется даже внутри окна. Ответ при этом может завершиться успешно с неполным набором инструментов и оценочным usage.
expected_fix: Сохранить ограниченное ожидание, но различать подтверждённое завершение шага и истечение окна. Получать идентификатор закрываемого сообщения либо завершать неоднозначный сценарий явно; не объявлять неполный набор успешным.
verification: SSE и JSON: два вызова одного шага с задержкой второго более 150 мс; отдельный сценарий без `assistantMessageID`; проверить полный набор, usage и исключение следующего шага.

F-002 [pre-existing]
priority: blocking
locations: bridges/opencode-zen-bridge/server.py:1580, bridges/opencode-zen-bridge/server.py:3580, bridges/opencode-zen-bridge/server.py:3593, bridges/opencode-zen-bridge/server.py:3850, bridges/opencode-zen-bridge/server.py:3862
rule: HL-ENV-01, C-MULT-I2 — замыкание памяти и ограничение очередей.
evidence: Очередь ограничена 4096 объектами, отдельная SSE-строка — 1 МиБ. Только полезная нагрузка заполненной очереди допускает около 4 ГиБ на попытку до накладных расходов Python. Это превышает весь бюджет 2 ГиБ из HL-ENV; шесть слотов увеличивают предел. Накопители reasoning/text дополнительно сохраняют обработанный вывод. Расчёт `64 MiB + 1152 MiB` эту память не учитывает.
expected_fix: Ввести общий байтовый бюджет очереди и накопленного ответа, согласовать его с числом слотов и HL-ENV; при превышении останавливать попытку с явной причиной и cleanup.
verification: Детерминированный тест заполнения крупными событиями проверяет точную байтовую границу, отсутствие дальнейшего накопления и освобождение ресурсов.

F-003 [sweep]
priority: blocking
locations: bridges/opencode-zen-bridge/server.py:5438, bridges/opencode-zen-bridge/server.py:7749, bridges/opencode-zen-bridge/server.py:7821, bridges/opencode-zen-bridge/server.py:7942
rule: REQ-016 / AC-021; O-EXIT/v1 — точная причина раннего отказа.
evidence: При исчерпании дедлайна перед legacy spawn возвращается `state="timeout"`. `_serve_json` отдельно обрабатывает три фазовых watchdog, но общий `timeout` попадает в пустой результат и заменяется на `upstream_failed`. Это подтверждено приложенным `l2-green-ver002-unittest.log`: сценарий FU-002 завершается с `total_spawns=0`, `duration_s=0.09`, `exit_reason=upstream_failed`, хотя причиной был локальный дедлайн.
expected_fix: Обрабатывать общий `timeout` терминально до разбора результата, сохранять `exit_reason=timeout`, прежний HTTP 502 и нейтральный учёт Circuit Breaker.
verification: Расширить FU-002 проверкой реального O-EXIT sink: ровно одно событие с `timeout`, ноль запусков, ноль отказов breaker и возвращённый резерв.

F-004 [pre-existing]
priority: blocking
locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:411, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:881, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2423, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2754, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2825, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2983, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3277, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3404
rule: agents/testing.md — прямой запрет новых `unittest.TestCase`, `setUp`, `tearDown`.
evidence: Новый тестовый модуль построен на `unittest.TestCase`, включая наследников `_AttemptCase`. Запуск этих классов через pytest не устраняет нарушение. Ограничение stdlib рантайма не мешает использовать pytest из существующих dev-зависимостей.
expected_fix: Перенести новый модуль на pytest-функции и fixtures с гарантированным teardown; сохранить все поведенческие оракулы и изоляцию окружения.
verification: Полный pytest и обратный порядок остаются зелёными; AC-026 сохраняет поведенческий RED на baseline. Согласовать verification-surface, поскольку unittest-discover после переноса больше не исполняет этот модуль.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 и RW-002 исправлены; обнаружена потеря точной причины локального дедлайна в legacy JSON — F-003.
   СОВЕТЫ (при FAIL): выполнить F-003 и проверить терминальное событие в журнале.

   SUB Корректность/логика: PASS — ранний 429/503 повторяется через serve при сохранении запрета run (`server.py:6132`; регрессия `tests/test_realtime_reasoning.py:934`).
   SUB Корректность/граничные условия: FAIL — поздний второй native-вызов и отсутствие ID сообщения приводят к неполному результату, F-001 (`server.py:3371`, `server.py:3893`).
   SUB Корректность/обработка ошибок: FAIL — локальный timeout классифицируется как upstream_failed, F-003 (`server.py:7942`; сырой лог VER-002).

2. ПОЛНОТА: VERDICT=FAIL
   WHY=FU-001 подтверждён только для событий, укладывающихся в окно; независимый сигнал завершения шага не обязателен. Остальные требования имеют реализацию и L2-свидетельства; REQ-019 / AC-025 законно отложены.
   СОВЕТЫ (при FAIL): выполнить F-001; добавить проверки задержанного завершения и отсутствующего ID сообщения.

   SUB Полнота/покрытие AC: FAIL — AC-016/AC-019 не доказывают сохранение полного позднего инструментального шага, F-001 (`server.py:3893`; тест `test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded`).
   SUB Полнота/пропущенные ветки: FAIL — без `assistantMessageID` drain не обрабатывает дополнительные tool-события, F-001 (`server.py:3371`).

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Транспорт практически доступен: OpenCode v2.1.2, локальная авторизация, ротация прокси и in-memory DB подтверждены. Однако допустимая память очередей не помещается в заявленный бюджет. После исправлений остаются выкатка с откатом и живой L3; подтверждённой оценки срока этого этапа пакет не содержит.
   СОВЕТЫ (при FAIL): выполнить F-002, пересчитать память для максимального параллелизма, затем пройти H0..H9 и VER-006/VER-007.

   SUB Реализуемость/общее: FAIL — допустимая очередь одной попытки превышает бюджет всего процесса, F-002 (`server.py:1580`, `server.py:3580`; HL-ENV-01).

4. РИСКИ: VERDICT=FAIL
   WHY=Clean-room Full Suite и статический гейт подтверждены. Они не закрывают выявленные риски потери вызовов и превышения памяти. Отсрочку живой проверки не считаю дефектом данного pre-ACCEPT этапа.
   СОВЕТЫ (при FAIL): выполнить F-001/F-002; после изменений повторить L2 и сохранить L3 обязательным условием открытия MR.

   SUB Риски/безопасность: PASS — случайный пароль, loopback, ограниченное env, reject/cancel и маскирование ошибок реализованы (`server.py:1864`; REQ-012, REQ-015, VER-005).
   SUB Риски/данные: FAIL — возможен успешный ответ с потерянными native-вызовами и usage, F-001 (`server.py:3355`, `server.py:3893`).
   SUB Риски/прод: FAIL — ограничение количества событий не обеспечивает бюджет памяти, F-002 (`server.py:3580`; HL-ENV-01).
   SUB Риски/regression red→green: PASS — AC-026 на origin/dev достигает `AssertionError: 1 not greater than or equal to 5`; кандидат зелёный (`execution-evidence.md`, L2-RED и VER-005).
   SUB Риски/Full Suite (L2): PASS — 478 тестов компонента, 894 теста корневого набора и обратный порядок зелёные; basedpyright: 0 ошибок (`execution-evidence.md`, VER-001..004, AC-023).
   SUB Риски/scope-diff: PASS — ровно три разрешённых файла; frozen-функции совпадают побайтно (`candidate-manifest.json`; VER-004).

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve с резервным run оправдан подтверждёнными ограничениями CLI и необходимостью ротации IP. Переписывать архитектуру для исправлений не требуется.

   SUB Альтернативы/общее: PASS — общий демон осложняет ротацию, прямой Zen HTTP не доказан; выбранный транспорт имеет рабочий прецедент (`handoff-architect.md` §4; REQ-003/REQ-013).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Публичные HTTP/SSE-границы и Google-direct сохранены; новые runtime-зависимости отсутствуют. Новый тестовый модуль нарушает прямо приложенное правило testing.md — F-004.
   СОВЕТЫ (при FAIL): выполнить F-004, сохранив оракулы; обновить свидетельства проверок после переноса.

   SUB Соответствие контексту/общее: FAIL — новый модуль использует запрещённый TestCase lifecycle, F-004 (`tests/test_realtime_reasoning.py:411`, `:881`, `:2423`, `:2754`, `:2825`, `:2983`, `:3277`, `:3404`; agents/testing.md).

Self-sweep: повторно проверены все 14 подкатегорий; добавлен F-003. REQ-001..REQ-020 и AC-001..AC-026 сопоставлены с кодом и свидетельствами; исключения перечислены выше. Non-Goals и Forbidden Scope по предоставленному diff соблюдены. Тесты судьёй не запускались.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 4


### Seat 3 (`visionary`, `muse-wonder-full-1.0`)

PANEL-NONCE: a42865325602803b
ARTIFACT-SHA256: 1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8
Канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до `<!-- КАНОН-КОНЕЦ -->`; проектных `AGENTS.md`/`CLAUDE.md` в рабочей папке нет (факт-карта пакета).
SUB Корректность/логика: PASS — evidence (`bridges/opencode-zen-bridge/server.py` `_serve_one_attempt`/`_map_serve_event`; `receipts/code-gate.json` status PASS)
SUB Корректность/граничные условия: PASS — evidence (`tests/test_realtime_reasoning.py` `test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_in_sse_and_json`, `test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded`)
SUB Корректность/обработка ошибок: PASS — evidence (`server.py` `ServeProtocolError`/`ServeSecurityError`/`FALLBACK_DECISION_TABLE`; `test_c8_rw001_early_transient_error_after_execution_started_retries_serve_without_run_fallback`)
SUB Полнота/покрытие AC: PASS — evidence (`teamlead/verification-traceability.md` REQ-001..REQ-020/AC-001..AC-026 PASS, REQ-019/VER-006/VER-007 DEFERRED_L3 до ACCEPT)
SUB Полнота/пропущенные ветки: PASS — evidence (`tests/test_realtime_reasoning.py` матрица SSE/JSON, `test_c6_rw004_ac016_serve_step_interruption_matrix`, `test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence`)
SUB Реализуемость/общее: PASS — evidence (`bridges/opencode-zen-bridge/pyproject.toml` dependencies=[]; `receipts/code-gate.json` 478 passed, 0 новых runtime-зависимостей)
SUB Риски/безопасность: PASS — evidence (`server.py` `_serve_env` allowlist/`OPENCODE_DB=:memory:`/`_error_payload` маскирование; `test_rw008_provider_secrets_hidden_in_sse_json_and_log`)
SUB Риски/данные: PASS — evidence (`server.py` строгая валидация токенов в `_map_serve_event` step_finish; `test_c6_fu001_fu002_sse_line_body_byte_caps_and_strict_usage_ints`)
SUB Риски/прод: PASS — evidence (`server.py` `_ServeLease.cleanup`/`_stop_proc` killpg; `execution-evidence.md` VER-006/VER-007 законно DEFERRED_L3 до вердикта Совета)
SUB Риски/regression red→green: PASS — evidence (`receipts/code-gate.json` red_sensitivity_rc=1; `l2-red.log` AC-026 AssertionError на сокетном оракуле origin/dev; `VER-005` rc=0 на кандидате)
SUB Риски/Full Suite (L2): PASS — evidence (`execution-evidence.md` VER-001/002/003/003b/005/AC-023 rc=0, 478 passed; VER-004 rc=0)
SUB Риски/scope-diff: PASS — evidence (`teamlead/candidate-manifest.json` ровно 3 файла coder_target_files; run_env_sha256=1c51b28f... google_direct_unchanged=True)
SUB Альтернативы/общее: PASS — evidence (`handoff-architect.md` §4 сравнение L/A1/A2/B/C; выбран serve на запрос с fallback run, прецедент `bridges/muse-bridge/server.py` ADR-0004)
SUB Соответствие контексту/общее: PASS — evidence (`server.py` публичный контракт `/health`/`/v1/models`/`/v1/chat/completions` сохранён; REQ-002/REQ-018, Non-Goals/Forbidden Scope из handoff-architect.md)

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Verify-fixed Цикла 8 зелёный: RW-001 разделён барьер доставки и допустимость serve-повтора раннего 429/503 после session.execution.started без токенов и без fallback на run (test_c8_rw001, обе формы SSE/JSON); RW-002 непарные суррогаты дают ServeProtocolError/invalid_serve_event с cleanup, валидная пара сохраняется (test_c8_rw002 + pre-delivery fallback); RW-003 локальный timeout/ServeStartupDeadlineExceeded нейтрален для Circuit Breaker и терминален, фазовые watchdog учитываются (test_c8_rw003). Сопутствующие FU-001 (все native-вызовы шага того же assistantMessageID, без следующего шага), FU-002 (gate/limiter с deadline/is_client_gone и повторной проверкой после резерва), FU-003 (AC-026 на origin/dev падает AssertionError по сокету, а не AttributeError в setUp) закрыты тестами из пакета и квитанцией coder.json.
2. ПОЛНОТА: VERDICT=PASS
   WHY=Матрица verification-traceability.md покрывает REQ-001..REQ-020 и AC-001..AC-026 поштучно со статусом PASS, кроме REQ-019/VER-006/VER-007, законно помеченных DEFERRED_L3 до ACCEPT Совета. Реалтайм-дельты, статусы [мост], watchdog всех фаз, ToolCallParser на разрезанных дельтах, native tools, unmapped/incomplete recovery, usage, O-EXIT полями transport/first_event_ms/ttft_ms покрыты 99 тестами нового модуля и полным сьютом. Стратегически закрыты все три корневые причины RC-1/RC-2/RC-3, а не только транспорт.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Решение построено на проверенном фактурой транспорте opencode serve v2.1.2 (дельты median 127/114 мс, старт ~109 мс), без новых зависимостей вне Python 3.14 stdlib, с kill-switch dynamic_config/env/disable-file и сохранённым legacy run как откатом. Масштаб одного локального демона и бюджета HL-ENV из handoff-architect соблюдён: потолок 3 спавнов, слоты, rate limiter, retry budget, breaker разделяют оба транспорта. Операционные издержки ограничены процессом на попытку с :memory: БД и подтверждаемой уборкой группы, что открывает безопасное поэтапное включение фичефлагом без рестарта.
4. РИСКИ: VERDICT=PASS
   WHY=Clean-room L2 независимого Verifier: VER-004/VER-001/VER-002/VER-003/VER-003b/VER-005/AC-023 все rc=0, 478 passed включая обратный порядок, red-sensitivity rc=1 на origin/dev. Безопасность: allowlist env, случайный пароль serve, маскирование секретов на последней границе _error_payload, permission ask_reject/deny и fail-closed form.created до схемы, лимиты SSE-строки 1 МиБ и HTTP-тела 8 МиБ, строгие int-токены. Замороженные _run_env и Google-direct побайтово неизменны. Остаточный риск совместимости с реальным opencode вне FakeServe честно отнесён в DEFERRED_L3 живой проверки после ACCEPT и merge не блокирует.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Альтернативы L/A1/A2/B/C сравнены архитектором по фактам: L не даёт реалтайма, A2 теряет ротацию IP, B не доказана из-за 429 без заголовков CLI — выбранный A1-подобный короткоживущий serve на запрос с fallback на run оптимален и повторяет прецедент muse-bridge serve→exec в этом же репозитории. Это меняет игру для потребителя: DSH впервые получает инкрементальное reasoning вместо блока в конце шага при сохранении прежнего публичного контракта, а транспортная абстракция ниже parse_opencode_event открывает путь к будущим транспортерам без переписывания ретраев, парсера инструментов и SSE-кадрирования. Неоправданного раздувания вне дельты задачи нет: ровно 3 целевых файла.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Diff строго внутри bridges/opencode-zen-bridge (server.py + 2 тестовых файла конверта), внешний OpenAI SSE/HTTP-контракт, порт 9883 и finish/usage-формы не изменены, DSH/muse-bridge/общие конфиги не тронуты, правило scope-and-contracts соблюдено. Стиль нового тестового модуля следует существующему unittest-контуру моста при ограничении 0 внешних зависимостей, что зафиксировано в брифе как применимое ограничение стандартов. Чужих Jira-KEY и работы «заодно» в diff и отчёте нет.
ОБЩИЙ ВЕРДИКТ: PASS
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 0


---

## Раунд D1 (`panel/council/r106`)

### Seat 1 (`skeptic`, `muse-wonder-full-1.0`)

PANEL-NONCE: 4b0dc4528b1a6f81
ARTIFACT-SHA256: 1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8

AGREE F-001 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:3893 — после первого native-вызова `_drain_serve_step_usage` вызван с дедлайном `time.monotonic() + 0.15`, а в bridges/opencode-zen-bridge/server.py:3371 дополнительные tool-события обрабатываются только при истинном `assistant_message_id`; истечение окна в bridges/opencode-zen-bridge/server.py:3355 не отличает подтверждённый `session.step.ended` от неполного набора, поэтому второй вызов того же шага с задержкой более 150 мс или без ID сообщения теряется при успешном завершении

AMEND F-002 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:1580, bridges/opencode-zen-bridge/server.py:3580; fix=ввести общий байтовый бюджет SSE-очереди и накопителей ответа как follow-up с пересчётом HL-ENV на максимальное число слотов — причина: handoff-architect.md §8.1 `C-MULT-I2` прямо фиксирует PASS для очередей, ограниченных 4096 элементами, и требует для нового SSE-читателя такой же предел по числу элементов, который в коде соблюдён; расчёт 4096×1 МиБ показывает теоретический худший случай, но не воспроизводит превышение при модельных пределах вывода и активном дренировании очереди основным циклом, поэтому для дельты Цикла 8 это не доказанный blocking-дефект, а ужесточение сверх согласованного конверта HL-ENV

AGREE F-003 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5438 — legacy-путь при исчерпании дедлайна после резерва возвращает `state="timeout"`, но bridges/opencode-zen-bridge/server.py:7821 обрабатывает терминально только три фазовых watchdog, а bridges/opencode-zen-bridge/server.py:7942 для пустого результата ставит `exit_reason=upstream_failed`; приложенный `l2-green-ver002-unittest.log` подтверждает сценарий с `total_spawns=0`, `duration_s=0.09`, `exit_reason=upstream_failed` при локальном дедлайне, что нарушает точную причину O-EXIT/v1 по REQ-016

DISPUTE F-004 — класс: invalid — контр-evidence: bridges/opencode-zen-bridge/tests/test_step_interruption.py:197 и весь существующий контур моста построены на `unittest.TestCase`, а `verification-surface.json` уровни L2 прямо задают оракул `VER-002: python3 -m unittest discover -s tests` — почему неверно: запрет в agents/testing.md находится в документе про полностью async Litestar-проект с `AsyncTestClient` и `asyncio_mode=auto`, что неприменимо к stdlib `ThreadingHTTPServer`-мосту с ограничением 0 внешних runtime-зависимостей; перенос только нового модуля на pytest-функции сломал бы заданный до Coder оракул VER-002 и разошёлся бы с конвенциями всех 17 существующих тестовых модулей без воспроизводимого поведенческого дефекта

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 и RW-002 закрыты, но F-001 даёт потерю поздних native-вызовов шага, а F-003 — неверную классификацию локального `timeout` как `upstream_failed` в legacy JSON
   СОВЕТЫ (при FAIL): выполнить F-001 — различать подтверждённое `session.step.ended` и истечение окна дочитывания, не завершать неполный набор успешно; выполнить F-003 — обрабатывать общий `timeout` терминально в `_serve_json` с `exit_reason=timeout` и прежним HTTP 502
2. ПОЛНОТА: VERDICT=FAIL
   WHY=FU-001 доказан только для немедленно поступивших событий с `assistantMessageID` внутри окна 0.15 с; сценарии задержанного второго вызова и отсутствующего ID не покрыты и по коду теряются — F-001
   СОВЕТЫ (при FAIL): добавить SSE и JSON оракулы F-001 — второй вызов через более 150 мс, сценарий без `assistantMessageID`, проверка полного набора вызовов, usage и исключения следующего шага
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Транспорт на проверенном `opencode serve` v2.1.2, 0 новых runtime-зависимостей, kill-switch с дефолтом `run`, подтверждение L2 rc=0; F-002 понижен до non-blocking follow-up по байтовому бюджету очереди
4. РИСКИ: VERDICT=FAIL
   WHY=Full Suite L2 и VER-004 зелёные, безопасность и маскирование секретов в порядке, но F-001 допускает успешный ответ DSH с неполным набором инструментов и оценочным usage, а F-003 искажает наблюдаемость отказа в O-EXIT
   СОВЕТЫ (при FAIL): выполнить F-001 и F-003, затем повторить целевой набор и Full Suite L2; VER-006/VER-007 оставить обязательным условием после ACCEPT
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve на запрос с fallback на run до барьера доставки оправдан сравнением L/A1/A2/B/C и прецедентом muse-bridge; исправления F-001/F-003 не требуют смены архитектуры
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Публичный HTTP/OpenAI SSE-контракт, порт и Google-direct сохранены, дельта ровно в 3 файлах конверта; F-004 отклонён как неприменимое к unittest-контуру моста правило, F-002 — non-blocking follow-up сверх согласованного HL-ENV

POSITIONS: 4/4
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `grok-4.7-high`)

PANEL-NONCE: 10a8d5bac8d7ca67
ARTIFACT-SHA256: 1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8
Канон прочитан: AGENTS.md, 429 строк

AMEND F-001 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3355, bridges/opencode-zen-bridge/server.py:3371, bridges/opencode-zen-bridge/server.py:3885, bridges/opencode-zen-bridge/server.py:3893; fix=окно 0.15 с оставить как задано в FU-001; поздний второй native-вызов и пустой assistantMessageID вынести в follow-up — причина: RECHECK `server.py:3355` — дочитывание того же шага; бриф FU-001 задаёт это окно; `test_c8_fu001` зелёный в L2
NEW: bridges/opencode-zen-bridge/server.py:3355
ARG: visionary/R1 «FU-001 (все native-вызовы шага того же assistantMessageID, без следующего шага) ... закрыты тестами из пакета»

AMEND F-002 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:1580, bridges/opencode-zen-bridge/server.py:3580; fix=общий байтовый бюджет очереди оставить follow-up; предел 4096 объектов и 1 МиБ на строку сохраняет границу читателя, постановка в очередь при Full ждёт — причина: RECHECK `server.py:1580` — потолок строки, а не заранее выделенный буфер
NEW: bridges/opencode-zen-bridge/server.py:1580

AMEND F-004 — priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:411, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:881, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2423, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2754, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2825, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2983, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3277, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3404; fix=сохранить unittest.TestCase: VER-002 (`unittest discover`) исполняет этот модуль, соседний `test_step_interruption.py` уже на TestCase — причина: RECHECK `test_realtime_reasoning.py:411`
NEW: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:411
ARG: visionary/R1 «Стиль нового тестового модуля следует существующему unittest-контуру моста при ограничении 0 внешних зависимостей»

F-003 остаётся blocking. Повторная проверка: `Run._execute_once` при дедлайне после резерва возвращает `state="timeout"` и `attempt_done(False, False)` (`server.py:5437-5454`); `_serve_json` принимает в ранний выход только `launcher_missing` / `spawn_failed` / `client_gone` (`server.py:7749-7765`), фазовые watchdog — только `first_event_timeout` / `first_token_timeout` / `stall_timeout` (`server.py:7821-7840`), пустой текст записывает `exit_reason=upstream_failed` (`server.py:7939-7942`). В `l2-green-ver002-unittest.log` сценарий FU-002 (JSON) даёт `total_spawns=0`, `duration_s=0.09`, `exit_reason=upstream_failed`.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 (повтор serve после раннего 429/503 без токенов и запрет run), RW-002 (непарный суррогат → `ServeProtocolError`) и обе serve-ветки RW-003 (локальный timeout нейтрален для breaker) подтверждены кодом и L2. В JSON-пути legacy общий `state="timeout"` до spawn теряет точную причину и становится `upstream_failed` — F-003 (`server.py:5437`, `server.py:7749`, `server.py:7939`; лог VER-002).
   СОВЕТЫ (при FAIL): в `_serve_json` обработать `state="timeout"` до ветки пустого content; сохранить HTTP 502, `attempt_done(False, False)` и возврат резерва; в оракуле FU-002 проверить одну строку O-EXIT с `exit_reason=timeout`, `total_spawns=0` и нулевой прирост отказов breaker.

2. ПОЛНОТА: VERDICT=PASS
   WHY=FU-001 закрыт для native-вызовов того же `assistantMessageID` внутри окна 0.15 с (`server.py:3355`, `test_c8_fu001`). Поздний вызов и пустой ID — non-blocking F-001. Матрица REQ-001..REQ-020 и AC-001..AC-026 на кандидате закрыта L2; REQ-019 / VER-006 / VER-007 законно DEFERRED_L3 до ACCEPT.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Новых runtime-зависимостей нет (`dependencies = []`). Короткоживущий `opencode serve` v2.1.2, lease 0700, killpg, kill-switch и fallback на `run` до барьера доставки подтверждены L2. Очередь SSE ограничена 4096 объектами, строка — 1 МиБ (`server.py:1580`); байтовый потолок всего ответа — non-blocking F-002. Лестница H0..H9 остаётся после ACCEPT.

4. РИСКИ: VERDICT=PASS
   WHY=Clean-room L2: VER-001..VER-005 и AC-023 с rc=0, 478 passed; RED AC-026 на origin/dev — AssertionError «1 < 5»; VER-004 — 0 ошибок basedpyright; ровно 3 файла конверта; frozen `_run_env` / Google-direct совпали. Пароль serve, allowlist, `:memory:`, fail-closed 401/403/400/404/422 и маскирование `_error_payload` на месте. F-003 меняет подпись уже нейтрального для breaker исхода при HTTP 502; после правки подписи нужен повтор L2.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve на попытку с откатом на `run` до барьера доставки закрывает RC-1 и сохраняет ротацию IP. Общий демон ломает ротацию, прямой Zen HTTP получил 429. Цикл 8 — точечные RW-001..RW-003 и FU-001..FU-003, архитектура не переписывалась.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Diff внутри `bridges/opencode-zen-bridge/` (ровно 3 файла), публичные `/health`, `/v1/models`, `/v1/chat/completions` и форма SSE сохранены, Google-direct побайтно неизменен. Новый модуль остаётся в unittest-контуре моста (F-004 non-blocking): VER-002 discover его исполняет. Пересчёт сида r106: `seed_hex=36998d6685fcfe25481966619a844e55f268be26c0559a66f6ac4d0de9b410d9` MATCH, SEED=`36998d66`; `ranked_order` по `rank_slots(полный seed_hex)` из `select_round_seats.py` MATCH манифесту r106 (grok-4.7-high, gpt-6.1-sol-high, gemini-4-argon-high, muse-wonder-full-1.0, claude-sonnet-5-5-high).

POSITIONS: 0/0
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `gpt-6.1-sol-high`)

PANEL-NONCE: 015834b346bbb4dd
ARTIFACT-SHA256: 1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8

Общий канон `~/Мой диск/Context/AGENTS.md` прочитан в предоставленном тексте целиком до `<!-- КАНОН-КОНЕЦ -->`. Проектные файлы правил с диска не читались; оценка основана на приложенных правилах, diff и свидетельствах.

AGREE F-001 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3355,3371,3885,3893` — истечение окна 0,15 с не подтверждает завершение шага, но оставляет `terminal="tool_calls"`. Дополнительные native-вызовы без `assistantMessageID` пропускаются. Тест немедленной доставки двух вызовов не исключает потерю задержанного второго вызова.

AGREE F-002 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:1580,3580,3593,3850,3862` — предел строки 1 МиБ и очередь 4096 событий допускают около 4 ГиБ полезной нагрузки одной попытки. Накопители ответа сохраняют дополнительную память. Это несовместимо с заявленным бюджетом HL-ENV 2 ГиБ; ограничение числа элементов не замыкает байтовый бюджет.

AGREE F-003 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:5438,7749,7821,7942` — общий `state="timeout"` отсутствует среди терминальных веток JSON-обработчика и доходит до `upstream_failed`. Сырой лог `execution-evidence.md`, VER-002, подтверждает именно этот исход при `total_spawns=0`, `duration_s=0.09`.

AGREE F-004 rev=1 — проверил: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:411,881,2423,2754,2825,2983,3277,3404` — новый модуль использует `unittest.TestCase` и его lifecycle вопреки прямому запрету `agents/testing.md`. `pytest` уже указан в dev-зависимостях; ограничение runtime stdlib этому исправлению не препятствует.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001..RW-003 исправлены в serve-ветках, однако F-003 показывает потерю причины локального дедлайна в legacy JSON. F-001 допускает успешное завершение с неполным инструментальным шагом.
   СОВЕТЫ (при FAIL): обработать общий `timeout` терминально до разбора результата, сохранить HTTP 502 и нейтральный учёт breaker; различать подтверждённый конец инструментального шага и исчерпание окна ожидания.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=FU-001 закрыт для немедленных событий с идентификатором сообщения. Полнота при задержке следующего вызова и отсутствии идентификатора не обеспечена — F-001. Законная отсрочка REQ-019/AC-025 до L3 замечанием не является.
   СОВЕТЫ (при FAIL): получать независимое подтверждение завершения шага; при неоднозначности возвращать явную ошибку; проверить SSE и JSON с задержанным вторым вызовом, отсутствующим `assistantMessageID`, точным usage и исключением следующего шага.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Короткоживущий serve практически осуществим и сохраняет ротацию IP. Однако допустимое потребление памяти превышает эксплуатационный конверт — F-002. При росте параллелизма этот разрыв увеличивается.
   СОВЕТЫ (при FAIL): установить общий байтовый бюджет очереди и накопителей, учесть накладные расходы Python и максимальное число слотов; при превышении обеспечить явный отказ и cleanup.

4. РИСКИ: VERDICT=FAIL
   WHY=Независимые L2, статические проверки и поведенческий RED AC-026 подтверждены. Они не опровергают потерю вызовов F-001, превышение памяти F-002 и неверную диагностику F-003.
   СОВЕТЫ (при FAIL): добавить оракулы полноты шага и точной границы памяти; расширить FU-002 проверкой конечного O-EXIT sink: одно событие `timeout`, ноль запусков и отказов breaker, возвращённый резерв; повторить L2 после исправлений.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Serve с резервным run обоснован: legacy не предоставляет дельты, общий демон осложняет ротацию IP, прямой Zen HTTP не доказан. Решение существенно улучшает отзывчивость DSH при сохранении публичного контракта. Выявленные дефекты исправляются в выбранной архитектуре.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Публичные границы, scope и замороженные функции сохранены. Однако F-004 нарушает непосредственно приложенный стандарт тестирования. Прежнее обоснование R1 существующим unittest-контуром этого запрета не отменяет.
   СОВЕТЫ (при FAIL): перенести новый модуль на pytest-функции и fixtures с гарантированным освобождением ресурсов; сохранить поведенческие оракулы и RED AC-026; согласовать verification-surface с изменившимся охватом unittest-discover.

POSITIONS: 4/4
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


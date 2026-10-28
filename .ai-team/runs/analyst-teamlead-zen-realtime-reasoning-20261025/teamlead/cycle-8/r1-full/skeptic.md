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

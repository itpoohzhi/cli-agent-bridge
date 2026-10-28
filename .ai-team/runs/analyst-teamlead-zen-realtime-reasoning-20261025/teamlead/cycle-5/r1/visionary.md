PANEL-NONCE: d3bb3ab877289505
ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Цикл 5 закрывает ровно ту архитектуру, которая меняет игру: короткоживущий `opencode serve` на попытку отдаёт дельты, которых `opencode run` v2.1.2 не выдаёт, ротация IP и kill-switch с дефолтом `run` сохраняются, публичный SSE-конверт остаётся. Verify-fixed по имени приёмки: RW-001 на обрыве тела prompt и на HTTP 429/5xx (заголовки входят в `delivered`, `ServeUnavailable` после `headers_at` не бросается, L2: `exit_reason=prompt_error|prompt_status_429|prompt_status_503`, `transport=serve`); RW-002 (абсолютный срок `STATUS_INITIAL`, оракул 0.5 с ≤ 1.0 с); RW-003/FU-001 (один разделитель watchdog/unmapped/incomplete только при thinking); RW-004 (`last_token_at` на `session.tool.input.delta` и на завершённом native-вызове). Дыра — соседняя ветка того же инварианта. `FALLBACK_DECISION_TABLE` (server.py:1701-1708) для prompt с уже полученными заголовками требует `serve_retry`, а не `fallback_to_run`. Ветки `first_event_timeout` (server.py:3309) и `_prompt_err` (server.py:3349-3357) этот флаг ставят. Ветка `etype == "error"` (server.py:3552-3556) пишет `error` / `transient_error` / `terminal="failed"` и выходит без `result["delivered"]`. `_is_transient_stream_error` (server.py:976-980) считает транзиентными `status is None`, 408, 429 и `>= 500`, то есть `session.execution.failed` / `provider.free-limit` после HTTP 200 prompt. Внешний SSE-барьер (server.py:5564-5570, 5618-5622) и JSON-барьер (server.py:6846-6855, 6911-6912) смотрят только `result["delivered"]`, тексты и native-вызовы. При `TRANSPORT=auto`, заголовках prompt и ошибке модели до первого токена запрос уходит в `opencode run` и шлёт тот же prompt в Zen второй раз. Отдельно legacy SSE поднимает порог первого токена до `max(FIRST_TOKEN_TIMEOUT_S, 120)` (server.py:6235) при дефолте 60 с и при AC-010.
   СОВЕТЫ (при FAIL):
   - В `bridges/opencode-zen-bridge/server.py:3552` перед `break` выставить `result["delivered"]` из `prompt_status["headers_at"]` или уже накопленных `texts` / `reasonings` / `native_calls`, тем же предикатом, что `_prompt_err` на server.py:3349-3357.
   - На server.py:5618 и server.py:6911 не возвращать fallback в `run`, пока этот флаг истинен: `serve-retry` через `attempts.allow_retry` либо терминальная SSE/502, без `Run.execute`, без `_spawn_with_stdin`, без `record_success()`.
   - Оракул: prompt HTTP 200 с `headers_at`, затем `session.execution.failed` (429 / timeout / eof) до первого токена, `TRANSPORT=auto`, и stream, и JSON.
   - На server.py:6235 убрать немой пол `120.0` либо завести отдельную legacy-переменную и покрыть тестом: `FIRST_TOKEN_TIMEOUT_S=60` и событие без токена дают `first_token_timeout` около 60 с, а не около 120 с.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=REQ-001..REQ-020 и AC-001..AC-026 на потоковом пути и на serve закрыты матрицей `verification-traceability.md` и зелёным L2 (451 pytest, 451 unittest, обратный порядок AC-023, VER-005 72). Статусы `[мост]` отделены префиксом и `\n`, `_messages_to_prompt` (server.py:3940) берёт только `_render_turn`, исторический `reasoning_content` в промпт не входит (AC-007, оракул зелёный). Google-срез и `_run_env` заморожены, `google_direct_unchanged=true`. Пропущенная ветка REQ-006/REQ-007: `Run.execute` для non-stream JSON (server.py:5094-5100, 5147) умеет только `client_gone`. Часы `first_event_timeout` / `first_token_timeout` / `stall_timeout` есть в `_serve_one_attempt` (server.py:3305-3324) и в legacy SSE `send_keepalive` (server.py:6225-6246), на JSON-прогоне их нет, потолок остаётся `TIMEOUT_S=1800`. Это прямой MUST, не спор о стиле. DSH ходит со `stream:true` (F-35), поэтому прод-потребитель закрыт, а JSON-ручка моста — нет.
   СОВЕТЫ (при FAIL):
   - В цикле чтения `Run.execute` завести тот же `_WatchdogState`, что у legacy SSE: нет события транспорта до `FIRST_EVENT_TIMEOUT_S` → убийство группы и `first_event_timeout`; нет токена до порога → `first_token_timeout`; пауза после токена дольше `STALL_TIMEOUT_S` → `stall_timeout`; всё внутри `MAX_TOTAL_SPAWNS`.
   - Регрессия: `stream:false`, фейковый CLI без stdout, выход с `first_event_timeout` заметно раньше 1800 с, процесс группы мёртв.
   - Либо явная фраза в конверте, что REQ-006/REQ-007 относятся только к SSE и serve. Пока её нет, ветка обязана работать.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Сопровождать это можно. Транспорт по умолчанию `run`, пока нет boolean `REALTIME_SERVE_ENABLED` или явного `TRANSPORT=serve`; disable-файл и override `0` остаются аварийными выключателями. На попытку один helper, одна группа, `OPENCODE_DB=:memory:`, lease `0700`, порт из процесса, `finally` делает interrupt/DELETE с дедлайном 0.35 с и `killpg`. Idle serve ~152 MiB при слоте 6 укладывается в оценку HL-ENV из конверта. Зависимости рантайма вне stdlib не добавлены. `ps`/`lsof` уже есть на целевом хосте (факт-карта). VER-006/VER-007 законно `DEFERRED_L3` до ACCEPT: живой `:9883` этим диффом не мутируется. Операционная цена — холодный serve на запрос и reaper при старте, она и есть способ сохранить ротацию IP.

4. РИСКИ: VERDICT=PASS
   WHY=Секреты: пароль serve — `secrets.token_hex`, в lease не пишется; `_mask_secrets` и `_error_payload` режут Bearer, `OPENCODE_SERVER_PASSWORD` и userinfo прокси; оракул RW-008 зелёный. Инструменты: дефолт `ask_reject`, `permission.asked` → reject+interrupt, `form.created` отменяется до разбора схемы, 401/403/400/404/422 — `ServeSecurityError` без fallback. Данные: `OPENCODE_DB=:memory:`, usage копится по попыткам, повтор шага с `assistantMessageID` подавляется (server.py:3521-3529). Прод-контур L2 зелёный, живой heavy-path отложен регламентом. Red→green: `L2-RED-sensitivity` rc=1 на `origin/dev` (76 падений на отсутствии символов), VER-005 rc=0 на кандидате. Full suite: pytest 451, unittest 451, порядок AC-023, VER-003/003b. Scope: ровно 3 файла манифеста, 0 новых runtime-зависимостей, замороженные срезы совпали. Дыра F-001 этим набором не поймана: существующие оракулы бьют в HTTP-статус prompt, а не в `session.execution.failed` после заголовков. Это дыра логики, чинится вместе с F-001, набор L2 сам по себе регрессию не прячет.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve на запрос — тот вариант, который одновременно даёт реалтайм (RC-1) и оставляет ротацию чистого IP на spawn (F-15, дневной лимит Zen). Общий демон дешевле по RSS и хуже по квоте: один IP на все запросы. Прямой HTTP к Zen на фактах анализа получил 429 без заголовков CLI. Откат на `run` до барьера доставки повторяет прецедент muse-bridge и нужен как kill-switch REQ-003. Объём `server.py` — след REQ-001..REQ-016 в одном файле конверта, не переписывание ради переписывания. Дешёвый путь «только watchdog и статусы на legacy» реалтайм размышления не даёт (F-17, F-18).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Граница задачи удержана: изменены `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`. Чужие мосты, DSH, каталог Zen, `zen_catalog.py` и Google-маршрут не тронуты. `sha256(_run_env)=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`, `google_direct_unchanged=true`. Публичные пути `/health`, `/v1/models`, `/v1/chat/completions` и форма OpenAI SSE сохранены; синтетические строки `[мост]` — явное требование REQ-004/REQ-005, не самовольный контракт. `CATALOG_SOURCE="static"` зафиксирован VER-004. Оракул `test_step_interruption` приведён к `MAX_TOTAL_SPAWNS=3` по REQ-017, потолок не ослаблен. Stdlib-only, `dependencies=[]`. Сверка сида: `seed_hex=9fc56e2918ce7c0cd76640cf97f8f8026b36f1f1f4870d9f746f7517a49c3ee2` совпал с манифестом r56, `SEED=9fc56e29`; `ranked_order` совпал с манифестом r56: grok-4.7-high, gpt-6.1-sol-high, muse-wonder-full-1.0, claude-sonnet-5-5-high, gemini-4-argon-high.

SUB Корректность/логика: FAIL — server.py:3552 не ставит `delivered` с `headers_at` на `etype=="error"`, server.py:5619 и server.py:6911 уходят в `run` (FALLBACK_DECISION_TABLE server.py:1701, REQ-009)
SUB Корректность/граничные условия: FAIL — server.py:6235 `max(FIRST_TOKEN_TIMEOUT_S, 120.0)` глушит дефолт 60 с на legacy SSE (REQ-007, AC-010)
SUB Корректность/обработка ошибок: PASS — server.py:3329-3332 и server.py:3349-3357: 401/403/400/404/422 → `ServeSecurityError`, обрыв тела после заголовков → `prompt_error` без `ServeUnavailable` (RW-001, L2 `prompt_error`)
SUB Полнота/покрытие AC: PASS — verification-traceability.md REQ-001..020 / AC-001..026, L2 VER-001 rc=0, VER-005 rc=0, VER-006/007 DEFERRED_L3
SUB Полнота/пропущенные ветки: FAIL — server.py:5094-5100 и server.py:5147: JSON `Run.execute` без `first_event_timeout`/`first_token_timeout`/`stall_timeout` (REQ-006, REQ-007) [pre-existing]
SUB Реализуемость/общее: PASS — kill-switch дефолт `run` (server.py:1888-1910), lease+killpg в `finally`, 0 зависимостей вне stdlib, живой деплой не мутирован
SUB Риски/безопасность: PASS — server.py:1898 пароль `token_hex`, маскирование `_mask_secrets`/`_error_payload`, permission reject и form cancel до схемы, оракул секретов зелёный (REQ-015)
SUB Риски/данные: PASS — `OPENCODE_DB=:memory:` в `_serve_env`, usage по попыткам, дедуп шага по `assistantMessageID` server.py:3521-3529
SUB Риски/прод: PASS — code-gate.json L2 PASS, слот 6 и idle serve 152 MiB в оценке HL-ENV, H0..H9 отложены до ACCEPT
SUB Риски/regression red→green: PASS — execution-evidence.md L2-RED rc=1 (76 failed на origin/dev), VER-005 rc=0 (72 passed)
SUB Риски/Full Suite (L2): PASS — VER-001 451 pytest, VER-002 451 unittest, AC-023 reversed rc=0, VER-003/003b rc=0
SUB Риски/scope-diff: PASS — candidate-manifest.json ровно 3 файла, frozen sha256 совпали, `dependencies=[]`
SUB Альтернативы/общее: PASS — per-request serve сохраняет ротацию IP (F-15) и даёт дельты, которых нет у `opencode run` (F-17, F-18); общий демон и прямой Zen этой цели не закрывают
SUB Соответствие контексту/общее: PASS — 3 файла конверта, REQ-002/REQ-018, seed_hex r56 совпал (`9fc56e29…3ee2`)

F-001
priority: blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:3552, bridges/opencode-zen-bridge/server.py:3556, bridges/opencode-zen-bridge/server.py:5564, bridges/opencode-zen-bridge/server.py:5618, bridges/opencode-zen-bridge/server.py:5619, bridges/opencode-zen-bridge/server.py:6846, bridges/opencode-zen-bridge/server.py:6911
rule: FALLBACK_DECISION_TABLE phase=PROMPT_RESPONSE (server.py:1701-1708), инвариант RW-001 «headers_at запрещает run», REQ-009
evidence: `elif etype == "error": result["error"] = payload; result["transient_error"] = _is_transient_stream_error(payload); result["terminal"] = "failed"; break` — флага `delivered` нет. Классификатор (server.py:976-980) возвращает True для 429, `status is None` и `status >= 500`. Снаружи: `_delivered_err = _delivered_now or bool(collected_texts)` и `if not _delivered_err and not force_serve: return False` с `transport_history=["serve","run"]`. JSON: `if not _delivered_j and not force_serve: return False`.
expected: на `etype=="error"` выставить `result["delivered"]` из `prompt_status["headers_at"]` или уже отданных токенов/вызовов; при истине — `serve_retry` или терминальная ошибка, без второго upstream-prompt.
check: `TRANSPORT=auto`, заголовки prompt 200, затем `session.execution.failed` (free-limit/timeout/eof) до токена, stream и JSON: `Run.execute` и `_spawn_with_stdin` не вызываются, `record_success()` не вызывается, `allow_retry` не больше одного раза на попытку.

F-002
priority: blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:6231, bridges/opencode-zen-bridge/server.py:6235
rule: REQ-007, AC-010
evidence: `now_s - attempt_start > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` при дефолте `FIRST_TOKEN_TIMEOUT_S=60`. Serve-путь сравнивает с сырым порогом (server.py:3314-3316). На legacy SSE событие без токена живёт до 120 с, сколько бы ни стояло в окружении ниже 120.
expected: сравнение с `float(FIRST_TOKEN_TIMEOUT_S)` на обоих транспортах, либо отдельная переменная с явным именем и тем же дефолтом, что в конверте.
check: `FIRST_TOKEN_TIMEOUT_S=60`, legacy SSE, есть событие и нет токена: `exit_reason=first_token_timeout` около 60 с плюс допуск, не около 120 с.

F-003
priority: blocking
criterion: ПОЛНОТА
locations: bridges/opencode-zen-bridge/server.py:5094, bridges/opencode-zen-bridge/server.py:5100, bridges/opencode-zen-bridge/server.py:5147
rule: REQ-006, REQ-007, AC-008, AC-009, AC-010
evidence: [pre-existing] `on_idle` в `Run.execute` ставит только `state = "client_gone"` и зовёт `_stop_proc`. Ветка `etype == "error"` (server.py:5147) не классифицирует молчание. Часы первого события, первого токена и паузы в этом методе отсутствуют; их копии живут в SSE (server.py:6225-6246) и в `_serve_one_attempt` (server.py:3305-3324). Non-stream JSON упирается в `TIMEOUT_S=1800`.
expected: те же три причины выхода и убийство группы внутри общего потолка спавнов на JSON-прогоне `opencode run`.
check: `stream:false`, фейковый CLI без stdout: завершение с `first_event_timeout` за порог плюс единицы секунд, процессов группы нет. Аналогично первый токен и пауза после токена.

[sweep] Повторный проход 1–14: новые корни сверх F-001..F-003 не найдены. RW-002/RW-003/RW-004 и FU-002..FU-006 подтверждены кодом и зелёными оракулами L2. FU-007 (оставить unittest) — вне FAIL. `_strip_interrupted` на reasoning режет только маркер обрыва, тот же приём уже на legacy-пути, AC-006 не ломает.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 3

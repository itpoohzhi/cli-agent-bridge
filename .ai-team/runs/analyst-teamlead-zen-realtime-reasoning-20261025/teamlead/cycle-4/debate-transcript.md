# Стенограмма дебатов Совета Тимлидов по коду — Cycle 4 (run `analyst-teamlead-zen-realtime-reasoning-20261025`)

## Раунд R1 (`panel/council/r30`)

### Seat 1 (`skeptic`, `muse-wonder-full-1.0`)

PANEL-NONCE: 2231ef0e55bcb9e9
ARTIFACT-SHA256: 25fcec1e8fb299ee624f57e742f6b88fe3c44700babf3ca4176179c737870568
1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Verify-fixed RW-001/RW-004/RW-007 закрыты кодом и regression-тестами: монотонный `delivered_any` в [server.py](/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py:5339) блокирует тихий fallback после доставки, `_native_call_as_dsh` делегирует канонический `_native_to_tool_calls`, split-маркер прерывания буферизуется; воспроизводимых логических дефектов в дельте Цикла 4 не найдено.
2. ПОЛНОТА: VERDICT=PASS
   WHY=RW-002/RW-006 и FU-001..FU-15 покрыты названными тестами в [test_realtime_reasoning.py](/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:1); матрица `REQ-001..REQ-020`/`AC-001..AC-026` в пакете полностью `PASS`, кроме законно отложенных до ACCEPT `VER-006`/`VER-007` (`DEFERRED_L3`, живая мутация боевого моста до вердикта запрещена Forbidden Scope).
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=RW-003 закрыт: `OSError` из `_serve_env`/`mkdtemp` транслируется в `ServeUnavailable` без утечки портов/FD; транспорт по умолчанию выключен (`dynamic_config.json` default `false`, disable-файл, `TRANSPORT=run`), откат на legacy `run` сохраняется, внешних зависимостей вне Python 3.14 stdlib нет (`dependencies = []`).
4. РИСКИ: VERDICT=PASS
   WHY=RW-005/RW-008 закрыты: `_stop_proc` добивает группу после смерти лидера, `_error_payload`/`_mask_secrets` маскируют Bearer/пароль serve/proxy-creds в SSE, JSON и логе; clean-room L2: RED-sensitivity `rc=1` на `origin/dev`, кандидат 445 passed (pytest, unittest, reversed), замороженные `_run_env`/`_stream_google_sse`/`_execute_google_once` побайтово неизменны.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбранный гибрид serve-per-attempt + fallback на `run` обоснован факт-картой: legacy `run` не даёт дельт (RC-1), прямой анонимный Zen вернул 429 (вариант B не доказан), общий демон теряет ротацию IP (вариант A2); неоправданного раздувания сверх конверта из 3 файлов нет, переписываний без доказательства необходимости не выявлено.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Diff ровно в 3 разрешённых файлах кандидата, публичный контракт `/health`, `/v1/models`, `/v1/chat/completions`, порт 9883 и формат OpenAI SSE не изменены, Google-direct не тронут, секреты в код/тесты/артефакты не записаны, чужих Jira-KEY и работ «заодно» в дельте нет.
SUB Корректность/логика: PASS — evidence (server.py `_map_serve_event`/`_serve_one_attempt`, canonical fixtures test)
SUB Корректность/граничные условия: PASS — evidence (server.py watchdog `FIRST_EVENT_TIMEOUT_S`/`FIRST_TOKEN_TIMEOUT_S`/`STALL_TIMEOUT_S`, `test_never_event_gives_first_event_timeout`)
SUB Корректность/обработка ошибок: PASS — evidence (server.py `_serve_http` `check_phase`, `ServeUnavailable`/`ServeSecurityError` fail-closed ветки)
SUB Полнота/покрытие AC: PASS — evidence (verification-traceability.md: REQ-001..REQ-020/AC-001..AC-026 PASS, VER-006/007 DEFERRED_L3)
SUB Полнота/пропущенные ветки: PASS — evidence (test_realtime_reasoning.py: prompt 400/404/422, form.created, permission.asked, client_gone, limiter)
SUB Реализуемость/общее: PASS — evidence (server.py `_select_transport`, default run + disable-file kill-switch)
SUB Риски/безопасность: PASS — evidence (server.py `_serve_env` `OPENCODE_DB=":memory:"`, `secrets.token_hex`, `_error_payload` masking, AC-020)
SUB Риски/данные: PASS — evidence (server.py lease 0700/uid-check, `_messages_to_prompt` без `reasoning_content`, AC-007)
SUB Риски/прод: PASS — evidence (server.py `_ServeHealth` sticky 3/120с, `_ServeLease.cleanup` SIGTERM→SIGKILL, AC-011)
SUB Риски/regression red→green: PASS — evidence (code-gate.json `red_sensitivity_rc=1`, VER-005 dedicated suite rc=0)
SUB Риски/Full Suite (L2): PASS — evidence (execution-evidence.md VER-001/002/003/AC-023 rc=0, 445 passed)
SUB Риски/scope-diff: PASS — evidence (candidate-manifest.json: ровно 3 файла, frozen sha256 MATCH)
SUB Альтернативы/общее: PASS — evidence (handoff-architect.md §4: L/A1/A2/B/C сравнение по F-17..F-27)
SUB Соответствие контексту/общее: PASS — evidence (pyproject.toml `dependencies = []`, stdlib `ThreadingHTTPServer`, REQ-002/REQ-018)
ОБЩИЙ ВЕРДИКТ: ACCEPT


### Seat 2 (`realist`, `grok-4.7-high`)

PANEL-NONCE: b7bd3b574bf20a64
ARTIFACT-SHA256: 25fcec1e8fb299ee624f57e742f6b88fe3c44700babf3ca4176179c737870568
1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-002..RW-008 и RP-03 закрыты и покрыты регрессиями: `status_timer.cancel()` стоит после `spawn_limiter.acquire` (`server.py:6121`), `_native_call_as_dsh` делегирует `_native_to_tool_calls`, `_stop_proc` добивает живую группу после выхода лидера, UTF-8 в `dynamic_config.json` даёт `run`, потоковый фильтр `_INTERRUPTED_RE` удерживает префикс маркера, `_error_payload` маскирует message/detail, `refund()` вызывается в обоих `OSError` после `_spawn_with_stdin` (`server.py:5043`, `server.py:6128`). Нормальный выход `first_event_timeout` честно ставит `delivered` из `headers_at` (`server.py:3302-3307`), и развилка `server.py:5548-5555` этот флаг учитывает. Дыра в том же классе, что RW-001, на одной попытке: заголовки prompt уже приняты, модельных токенов ещё нет, а барьер доставки смотрит только на `texts`/`reasonings`/`native_calls`. `headers_at` пишется до чтения тела (`server.py:3265-3266`). Ошибка транспорта prompt поднимает `ServeUnavailable`, не глядя на `headers_at` (`server.py:3341-3345`); SSE (`server.py:5512-5517`) и JSON (`server.py:6779-6790`) тогда возвращают fallback на `run`, потому что `delivered_any` ещё ложен. HTTP 429/5xx prompt ставит `delivered` только по модельным массивам (`server.py:3330-3333`), поэтому SSE (`server.py:5577-5584`) и JSON (`server.py:6840-6845`) тоже уходят в `run`. Строка таблицы: подтверждённый prompt (фаза DELIVERED) → `serve_retry`, не `fallback_to_run`. Второй `opencode run` шлёт тот же prompt в Zen повторно. `test_rw001_delivery_survives_unavailable_or_limiter` закрывает только случай «попытка 1 уже отдала reasoning, попытка 2 упала» и эту ветку не ловит. Принудительный `TRANSPORT=serve` в эту ветку не заходит: дыра в `auto`, то есть в штатном включении.
   СОВЕТЫ: F-001.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=AC-001..AC-026 в `verification-traceability.md` закрыты автотестами, L2 на кандидате зелёный (445 passed). Незакрыта ветка того же инварианта RW-001: подтверждённые заголовки prompt без модельного токена. Исключение `ServeUnavailable` и статусы 429/5xx не переносят `headers_at` в монотонный барьер, в отличие от нормального `return` по `first_event_timeout`.
   СОВЕТЫ: F-001.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Взлёт после закрытия F-001: ACCEPT Совета → бэкап в `~/work/backups/` → копия `server.py` в `~/.dsh/bridges/opencode-zen-bridge/server.py` → `REALTIME_SERVE_ENABLED: true` (или env) → нативный `opencode` v2.1.2, на хосте есть `ps` и `lsof`, каталог lease доступен на запись. Пока флага нет, `_select_transport` остаётся на `run`. На попытку один короткоживущий `serve` (~152 MiB RSS); 6 слотов укладываются в оценку HL-ENV (6×192 MiB + 64 MiB worker ≤ 0.8×2048 MiB). Зависимостей вне stdlib нет. `VER-006`/`VER-007` законно `DEFERRED_L3`. Включать `auto` до F-001 нельзя: каждый prompt с оборванным телом ответа породит второй upstream-вызов.
4. РИСКИ: VERDICT=FAIL
   WHY=Безопасность закрыта (RW-008: `_mask_secrets` / `_error_payload`, пароль `secrets.token_hex(16)`, allowlist, 401/403/400 fail-closed). RED→green и Full Suite L2 зелёные: `red_sensitivity_rc=1` (65 failed на `origin/dev`), кандидат `VER-001` 445 passed / 176.83s, `VER-002` unittest OK, `VER-003`/`VER-003b`, `AC-023` reversed 445, `VER-005` 66 passed, `VER-004` frozen SHA-256 3/3, basedpyright 0 errors, warnings 591≤720. Scope — ровно 3 файла конверта, `google_direct_unchanged=true`, `_run_env` не тронут. Прод до включения флага остаётся на `run`, disable-file побеждает даже `TRANSPORT=serve`. Дыра F-001 при включённом `auto` повторно исполняет уже принятый prompt и списывает квоту Zen второй раз (`F-23`/`F-32`: дневной лимит на IP). Это риск данных, не дыра в красном наборе: существующие тесты эту ветку не запускают.
   СОВЕТЫ: F-001.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий `serve` на попытку с откатом на `run` до барьера доставки — разрешённый гибрид A1+C из `handoff-architect.md`; общий демон ломает ротацию IP (OPEN-06), прямой Zen без заголовков CLI дал 429 (F-24, F-25). Рост `server.py` вынужден конвертом: продуктовый код разрешён только в этом файле. Переписывания замороженных `_run_env` / Google-direct нет. Остаточный разделитель legacy при `thinking off` — FU-010, без нарушения MUST (F-002, non-blocking).
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Граница моста сохранена: публичные пути `/health`, `/v1/models`, `/v1/chat/completions` и форма SSE те же; строки `[мост]` требуются REQ-004/005. Новых runtime-зависимостей нет (`pyproject.toml` `dependencies = []`). Google-direct и `_run_env` побайтово заморожены. Чужих ключей и файлов вне `bridges/opencode-zen-bridge/` нет. `CATALOG_SOURCE` стартует как `static` (`server.py:360`); полный набор 445 passed, `/health` после `reload_catalog` в `main` отдаёт источник файла. SEED/seed_hex MATCH `bcf4ae550e946f033bc737a956d8c8b9bee68cf1eff3426a2acee6828fe1accb`; ranked_order MATCH `["grok-4.7-high","gemini-4-argon-high","gpt-6.1-sol-high","muse-wonder-full-1.0","claude-sonnet-5-5-high"]` через SHA-256(полный seed_hex + '#' + slot_id).
F-001
priority: blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:3265-3266, bridges/opencode-zen-bridge/server.py:3330-3333, bridges/opencode-zen-bridge/server.py:3341-3345, bridges/opencode-zen-bridge/server.py:5512-5517, bridges/opencode-zen-bridge/server.py:5577-5584, bridges/opencode-zen-bridge/server.py:6779-6790, bridges/opencode-zen-bridge/server.py:6840-6845
rule: RW-001 action; FALLBACK_DECISION_TABLE phase=DELIVERED event «first_event_timeout20s after headers, no valid execution SSE» action=serve_retry; REQ-009 (повторный запуск — второе исполнение prompt)
evidence: `prompt_status["headers_at"] = time.monotonic()` пишется в `_on_headers` до чтения тела. Дальше `_delivered_now = bool(result["texts"] or result["reasonings"] or result["native_calls"])` и `result["delivered"] = _delivered_now` для 429/5xx. При ошибке тела: `if isinstance(_prompt_err, str) and not (result["texts"] or result["reasonings"] or result["native_calls"]): raise ServeUnavailable(...)`. В SSE: `except ServeUnavailable` → `if not force_serve and not delivered_any[0]: return False`. В JSON тот же `return False` по `_j_delivered`. Развилки `prompt_status` 429/5xx в SSE и JSON тоже возвращают `False` в `run`, когда `delivered` ложен.
expected: Если `headers_at` уже есть, не бросать `ServeUnavailable` и не ставить `delivered=False`. Вернуть результат с `delivered=True` и `exit_reason` для serve-retry (429/5xx — тот же барьер). `STATUS_INITIAL` барьер не ставит. Исключение, которое всё же вышло после подтверждённого prompt, не переводит запрос на `run` и не вызывает `record_success()`.
check: Режим `auto`, заголовки ответа prompt получены, затем обрыв тела или HTTP 429/5xx до первого токена модели. `Run.execute` и `_spawn_with_stdin` не вызываются. Клиент получает один serve-retry или терминальную SSE/502 ошибку. `record_success()` не вызывается.
F-002
priority: non-blocking
criterion: ПОЛНОТА
locations: bridges/opencode-zen-bridge/server.py:6463-6464
rule: FU-010 (non-blocking follow-up)
evidence: На legacy-пути после watchdog `emit_synthetic(f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n")` вызывается без `thinking_enabled`. На serve разделитель гейтится `thinking` (`server.py:5492`), периодические статусы keepalive тоже (`server.py:6228`).
expected: Эмиссию разделителя на legacy-retry обернуть тем же `thinking_enabled`, что и `STATUS_WAITING` / `STATUS_CONTINUATION`.
check: `reasoning_effort=off` на пути `run`, watchdog даёт retry: в SSE нет строки «Повтор попытки». MUST это не ломает; в агрегирующий FAIL не входит.
SUB Корректность/логика: FAIL — server.py:3341-3345 и server.py:5512-5517 (ServeUnavailable после headers_at уходит в run; RW-001 / FALLBACK_DECISION_TABLE)
SUB Корректность/граничные условия: FAIL — server.py:3330-3333 (429/5xx ставит delivered только по модельным массивам, headers_at уже есть)
SUB Корректность/обработка ошибок: FAIL — server.py:5577-5584 и server.py:6840-6845 (подтверждённый prompt классифицируется как доставка не начата)
SUB Полнота/покрытие AC: PASS — verification-traceability.md AC-001..AC-026, VER-001 445 passed, VER-005 66 passed
SUB Полнота/пропущенные ветки: FAIL — server.py:3341-3345 против server.py:3306 (normal return учитывает headers_at, raise и 429/5xx нет; test_rw001 эту попытку не покрывает)
SUB Реализуемость/общее: PASS — kill-switch default off, stdlib only, HL-ENV 6×serve в бюджете памяти; VER-006/VER-007 DEFERRED_L3
SUB Риски/безопасность: PASS — server.py:_error_payload/_mask_secrets, RW-008, tests test_rw008_* зелёные в VER-005
SUB Риски/данные: FAIL — server.py:5514 return False после принятого prompt (второй upstream-вызов, квота Zen F-23)
SUB Риски/прод: PASS — _select_transport auto без флага остаётся run; disable-file сильнее TRANSPORT=serve; lease/killpg на месте
SUB Риски/regression red→green: PASS — L2-RED rc=1 (65 failed на origin/dev), кандидат VER-005 rc=0 (66 passed)
SUB Риски/Full Suite (L2): PASS — receipts/code-gate.json status=PASS, VER-001 445 passed, VER-002 OK, AC-023 reversed 445, VER-004 frozen 3/3
SUB Риски/scope-diff: PASS — ровно server.py, tests/test_realtime_reasoning.py, tests/test_step_interruption.py; google_direct_unchanged=true
SUB Альтернативы/общее: PASS — A1+fallback на run до барьера, конверт разрешает только server.py; F-002 не раздувает выбор
SUB Соответствие контексту/общее: PASS — границы моста и REQ-002/018; seed_hex bcf4ae550e946f033bc737a956d8c8b9bee68cf1eff3426a2acee6828fe1accb MATCH; ranked_order MATCH
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `gpt-6.1-sol-high`)

PANEL-NONCE: f29157384d7a9f07
ARTIFACT-SHA256: 25fcec1e8fb299ee624f57e742f6b88fe3c44700babf3ca4176179c737870568
Общий канон `~/Мой диск/Context/AGENTS.md` прочитан в предоставленном тексте целиком, до `<!-- КАНОН-КОНЕЦ -->`; проектные стандарты прочитаны из приложенного пакета. Применяю приложенный `feature.md` и рубрику Совета. Проверяю исправления и оставшиеся ветки; тесты не запускаю.
Восемь исправлений проверены по коду: основные изменения присутствуют, но барьер доставки prompt остаётся неполным при ошибке чтения тела после HTTP-заголовков. Также обнаружены пробелы в гарантии первого статуса и обработке частичного JSON-ответа при повторе. Независимые L2-логи подтверждают зелёный набор; живую проверку L3 учитываю как законно отложенную.
PANEL-NONCE: f29157384d7a9f07
ARTIFACT-SHA256: 25fcec1e8fb299ee624f57e742f6b88fe3c44700babf3ca4176179c737870568
Общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком из предоставленного текста, до `<!-- КАНОН-КОНЕЦ -->`. Проектные стандарты прочитаны из пакета; в рабочей папке `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` отсутствуют. SHA-256 проверенного `server.py` совпадает с манифестом кандидата. Тесты не запускал; результаты исполнения беру из `execution-evidence.md`.
1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Переход к настоящим дельтам существенно улучшает управляемость длительных агентных ходов. Однако подтверждение доставки prompt пока теряется на одном из путей исключения, а классификация HTTP-ошибки зависит от завершения чтения тела.
   SUB Корректность/логика: FAIL — после подтверждённых заголовков prompt исключение может разрешить повторную отправку через run (`bridges/opencode-zen-bridge/server.py:3345`, `:5514`, `:6789`; RW-001).
   SUB Корректность/граничные условия: FAIL — завершённый native-вызов устанавливает первый токен без обновления последней активности (`bridges/opencode-zen-bridge/server.py:3502`; REQ-007).
   SUB Корректность/обработка ошибок: FAIL — статус prompt публикуется после чтения тела, поэтому известный HTTP 401/403 может обрабатываться как watchdog-отказ (`bridges/opencode-zen-bridge/server.py:3280`; FALLBACK_DECISION_TABLE).
   F-001 — priority=blocking; RW-001 закрыт частично.
   - locations: `bridges/opencode-zen-bridge/server.py:2604`, `:3266`, `:3284`, `:3345`, `:5514`, `:6789`.
   - Правило: RW-001; монотонный барьер доставки; запрет fallback после подтверждения prompt.
   - Evidence: `headers_at` записывается своевременно, но ветка `_prompt_err` выбрасывает `ServeUnavailable`. Исключение не переносит этот признак наружу. Обработчики SSE и JSON проверяют модельные данные и прежний барьер, а не подтверждение текущего prompt.
   - Сценарий: prompt принят, получены HTTP 200 headers, затем соединение сброшено при чтении тела до появления модельных дельт. Ошибка возникает раньше first-event watchdog; разрешается fallback в run.
   - Исправление: передавать подтверждение доставки в общий контекст попыток непосредственно при получении заголовков либо сохранять его в типизированном результате исключения.
   - Проверка: HTTP-фейк подтверждает prompt и обрывает тело; в SSE и JSON `Run` не запускается, повтор остаётся serve либо завершается явной ошибкой.
   F-002 — priority=blocking; [pre-existing].
   - locations: `bridges/opencode-zen-bridge/server.py:2604`, `:2608`, `:2617`, `:3266`, `:3280`, `:3306`, `:3324`.
   - Правило: FALLBACK_DECISION_TABLE — HTTP 400/401/403/404/422 завершаются fail-closed без протокольного retry и инкремента ServeHealth.
   - Evidence: callback заголовков передаёт только время. `prompt_status["status"] = st` выполняется после полного тела ответа. Если сервер уже прислал 401, но задерживает тело, основной цикл видит только `headers_at` и может вернуть `first_event_timeout`.
   - Исправление: публиковать HTTP-статус одновременно с заголовками; терминальные 4xx классифицировать до чтения тела.
   - Проверка: каждый из 400/401/403/404/422 с незавершающимся телом даёт один терминальный отказ, без run, serve-retry и изменения ServeHealth.
   СОВЕТЫ (при FAIL): выполнить исправления F-001 и F-002; добавить проверки именно отказа после заголовков, поскольку существующая матрица с готовым JSON-телом эти ветки не закрывает.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=Основные компоненты решения присутствуют, но гарантия первой реакции остаётся нарушаемой при короткой задержке старта. Есть расхождения обработки повторов между JSON и SSE. Матрица приёмки также объявляет доказанными отдельные свойства, которые приложенный оракул непосредственно не измеряет.
   SUB Полнота/покрытие AC: FAIL — отмена таймера до первого видимого чанка оставляет нарушение AC-005 (`bridges/opencode-zen-bridge/server.py:6121`, `:6179`).
   SUB Полнота/пропущенные ветки: FAIL — частичный JSON-текст при transient recovery обходит нормализацию; legacy retry-статусы неоднородны (`bridges/opencode-zen-bridge/server.py:6855`, `:6463`, `:6545`).
   F-003 — priority=blocking; RW-002 закрыт частично.
   - locations: `bridges/opencode-zen-bridge/server.py:5948`, `:6121`, `:6173`, `:6179`, `:6242`.
   - Правило: REQ-004, AC-005 — первая видимая реакция не позднее 1,0 с.
   - Evidence: защитный таймер отменяется сразу после лимитера, а следующий срок статуса считается заново: `attempt_start + FIRST_STATUS_DELAY_S`.
   - Сценарий: gate/limiter задержал старт примерно на 0,5 с, затем молчащий процесс запущен до срабатывания таймера 0,65 с. Таймер отменён; следующий статус возможен лишь примерно через 1,15 с плюс интервал опроса.
   - Исправление: сохранять защитный таймер до первого видимого чанка либо использовать единый абсолютный срок первого статуса.
   - Проверка: задержки старта по обе стороны 0,65 с, включая 0,4–0,6 с; первый статус ≤1,0 с, начальный статус ровно один.
   F-004 — priority=blocking; FU-002 закрыт частично.
   - locations: `bridges/opencode-zen-bridge/server.py:6713`, `:6855`, `:6870`, `:6897`, `:6900`, `:6907`, `:6930`, `:6954`.
   - Правило: REQ-010/REQ-011; сохранение канонической обработки текста и инструментов при recovery.
   - Evidence: transient-ветка выполняет `contents.extend(texts)` до `ToolCallParser` и очистки блоков. Перед `continue` она также не обновляет `_prior_content`; это делается только в других retry-ветках.
   - Сценарий: первая попытка отдаёт преамбулу и transient error; recovery повторяет преамбулу перед корректным tool-call. JSON сохраняет обе копии. Сырой фрагмент tool-блока из неуспешной попытки также попадает непосредственно в накопитель `content`.
   - Исправление: пропускать частичные попытки через ту же нормализацию, что успешные; перед recovery фиксировать нормализованный префикс для дедупликации.
   - Проверка: преамбула встречается один раз; сырой tool-блок отсутствует в `content`; итоговые вызовы инструментов совпадают с SSE.
   F-005 — priority=blocking; [pre-existing], FU-010 закрыт частично.
   - locations: `bridges/opencode-zen-bridge/server.py:6183`, `:6463`, `:6500`, `:6521`, `:6545`, `:6554`.
   - Правило: REQ-009, AC-014; согласованное отключение синтетических reasoning-статусов.
   - Evidence: watchdog-retry вызывает `emit_synthetic` без проверки `thinking_enabled`. Ветви unmapped/incomplete recovery не имеют соответствующей единой точки разделителя после уже отданного reasoning.
   - Исправление: централизовать legacy-разделитель перед фактической повторной попыткой; учитывать наличие предыдущего reasoning и thinking-флаг.
   - Проверка: watchdog, unmapped и incomplete recovery — ровно один разделитель между попытками при thinking on; ноль синтетических разделителей при thinking off.
   F-006 — priority=non-blocking; недостаточная доказательность AC-002.
   - locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:151`, `:597`, `:613`, `:616`.
   - Правило: AC-002; `testing.md` — независимый эталон измеряемого свойства.
   - Evidence: оракул измеряет интервалы клиентских чанков и сравнивает их с независимой отметкой завершения апстрима. Он не сопоставляет время прихода каждой upstream-дельты с её записью клиенту. Постоянная задержка всех дельт более 250 мс может сохранить проверяемые интервалы.
   - Исправление: добавить идентификаторы дельт и независимые отметки upstream-arrival/client-receive; до этого обозначать AC-002 как INCONCLUSIVE.
   - Проверка: искусственная задержка пересылки 300 мс делает проверку AC-002 красной.
   Verify-Fixed: в приложенном rework-brief восемь обязательных пунктов имеют идентификаторы **RW-001..RW-008**. Отдельного набора RP-01..RP-08 в нём нет; подменять номера не следует.
   - RW-001 — PARTIAL: заголовки фиксируются раньше тела; исключение после заголовков остаётся проблемой F-001.
   - RW-002 — PARTIAL: ожидание лимитера покрыто новым тестом; остаётся окно F-003.
   - RW-003 — PASS: `OSError` из `_serve_env` переводится в `ServeUnavailable`; предусмотрен ENOSPC-оракул.
   - RW-004 — PASS: `_native_call_as_dsh` использует `_native_to_tool_calls`; проверяются bash/read/edit/list/multiedit.
   - RW-005 — PASS: `_stop_proc` проверяет группу независимо от выхода лидера; есть процессный regression-тест.
   - RW-006 — PASS: повреждённый UTF-8 обрабатывается через `ValueError`; проверено восстановление выбора serve.
   - RW-007 — PASS для исправляемого текстового пути: удерживается префикс маркера и сбрасывается хвост; тест покрывает три выбранных разреза, а не все границы.
   - RW-008 — PASS: сообщения и detail проходят маскирование; sentinel-проверки SSE/JSON включены в зелёный L2.
   - Дополнительный RP-03 из coder handoff — PASS: `refund()` присутствует в двух ветвях legacy spawn failure; неизменённый Go-тест входит в зелёный полный набор.
   Сопутствующие follow-up:
   - FU-001 — PARTIAL: HTTP-фазы получили deadline; старт и cleanup полностью им не ограничены — F-008 ниже.
   - FU-002 — PARTIAL: перенос частичных данных добавлен, нормализация и дедупликация неполны — F-004.
   - FU-003 — PASS: usage начисляется до ветвления, проверяется сумма 3+5+7.
   - FU-004 — PASS: legacy JSON получил callback отключения клиента.
   - FU-005 — PASS: интервал ужесточён до 0,5 с, отметка окончания FakeServe независимая.
   - FU-006 — PARTIAL: допуски есть; измерения остаются в обычном тестовом контуре — F-011.
   - FU-007 — PARTIAL: first-token telemetry добавлена; часы последней активности native-вызова не обновлены — F-009.
   - FU-008 — PASS: причины подавлений уточнены; новый модуль имеет ноль диагностик по L2.
   - FU-009 — PASS: минимум 120 с для буферизующего legacy CLI реализован.
   - FU-010 — PARTIAL: serve покрыт, legacy сохраняет проблему F-005.
   - FU-011 — PASS: cancelled завершается до `record_success()`.
   - FU-012 — PARTIAL: декларация обновлена; остаются расхождения фактической классификации и учёта повторов — F-002, F-007.
   - FU-013 — PASS: disable-файл, сигнатуры бинаря и tool status проверяются.
   - FU-014 — PASS: шаг listener polling увеличен до 0,2 с.
   - FU-015 — PASS: временный state-каталог теста удаляется в `finally`.
   Поштучная сверка требований и AC:
   - REQ-001: AC-001 — PASS по сокетному оракулу; AC-002 — INCONCLUSIVE, F-006.
   - REQ-002: AC-003 — PASS по контрактным проверкам L2; несанкционированного изменения формы публичного API не выявлено.
   - REQ-003: AC-004 — PASS по сохранённому legacy-пути, матрице переключателей и полному набору.
   - REQ-004: AC-005 — FAIL, F-003.
   - REQ-005: AC-006 — PASS для обычных модельных дельт с отделением синтетических кадров; AC-007 — PASS.
   - REQ-006: AC-008 — не закрыт в предельных фазах старта/очистки, F-008.
   - REQ-007: AC-009 — FAIL на native-граничном случае F-009; AC-010 — PASS для проверенного serve-сценария.
   - REQ-008: AC-011 — не гарантирован общим бюджетом очистки; AC-012 — INCONCLUSIVE для полного запроса с задержанным setup, F-008.
   - REQ-009: AC-013 — PASS, общий потолок три запуска сохранён; AC-014 — FAIL для legacy-разделителей, F-005. Retry Budget нарушается при upstream fallback — F-007.
   - REQ-010: AC-015 — PASS для проверенного потокового parser-пути; JSON transient-ветка обходит этот путь, F-004.
   - REQ-011: AC-016 — INCONCLUSIVE: весь существующий модуль проходит на fake-CLI run; это не исполнение всех его сценариев через serve.
   - REQ-012: AC-017 — PASS на представленных permission/native/unmapped фикстурах; реальное исполнение политики относится к L3.
   - REQ-013: AC-018 — PASS по переиспользованию `_run_env` и однократному продвижению пула на попытку.
   - REQ-014: AC-019 — PASS для отображения полей fixture и проверенного накопления usage.
   - REQ-015: AC-020 — PASS для представленных sentinel-секретов.
   - REQ-016: AC-021 — PASS по расширенному финализатору и строкам O-EXIT в сырых логах.
   - REQ-017: AC-022 — PASS; AC-023 — PASS, включая обратный порядок модулей.
   - REQ-018: AC-024 — PASS, frozen hashes и Google-тесты.
   - REQ-019: AC-025 — DEFERRED_L3, законно до ACCEPT.
   - REQ-020: AC-026 — PASS: независимый RED на базе и GREEN сокетного сценария кандидата.
   СОВЕТЫ (при FAIL): исправить F-003..F-005; усилить измерение F-006; снять преждевременные PASS для AC-002/AC-016 и предельных lifecycle-сценариев до появления соответствующих свидетельств.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Короткоживущий serve с in-memory DB и сохранением ротации IP разумен для локального моста с ограниченным параллелизмом. Сопровождение возможно без новых Python-зависимостей. Однако предельное время освобождения ресурсов пока не замкнуто на весь путь запроса.
   SUB Реализуемость/общее: FAIL — spawn/SSE setup используют отдельные окна, cleanup HTTP не имеет абсолютного дедлайна (`bridges/opencode-zen-bridge/server.py:2799`, `:3196`, `:3574`; R-BULK-I1, T-LIFE/v1).
   F-008 — priority=blocking; [pre-existing].
   - locations: `bridges/opencode-zen-bridge/server.py:2585`, `:2608`, `:2648`, `:2731`, `:2799`, `:2825`, `:3101`, `:3196`, `:3204`, `:3574`, `:3585`, `:3606`.
   - Правило: `feature.md` — ограничение каждого звена I/O, включая cleanup; R-BULK-I1; REQ-008/AC-011.
   - Evidence: `_spawn_serve` не принимает deadline/cancellation; handshake и listener получают новые локальные сроки. SSE subscribe использует отдельный timeout=5. Cleanup вызывает `_serve_http` без абсолютного deadline, а при `deadline is None` каждая порция тела получает заново полный timeout.
   - Следствие: медленно поступающее незавершающееся тело cleanup-ответа может удержать выполнение до `lease.cleanup()` неограниченно долго. Короткий socket timeout не ограничивает длительность всей операции. Предельный setup также не обеспечивает детекцию отключения клиента ≤5 с.
   - Исправление: передать deadline/cancellation через setup; назначить отдельный абсолютный cleanup deadline и лимит тела; гарантировать переход к остановке группы после исчерпания cleanup-бюджета.
   - Проверка: задержанные handshake/listener/SSE headers, истёкший deadline до spawn и непрерывно капающее cleanup-тело; после отмены группа отсутствует в пределах AC-011.
   СОВЕТЫ (при FAIL): замкнуть startup и cleanup на абсолютные бюджеты по F-008; проверять совокупное время до исчезновения группы, а не только длительность `_ServeLease.cleanup()`.
4. РИСКИ: VERDICT=FAIL
   WHY=Изоляция процессов, случайный пароль, проверка владельца listener и маскирование ошибок снижают риск эксплуатации. Зелёный независимый L2 принят. Остаются ошибки учёта повторов, способные усиливать нагрузку при отказе провайдера, и ложный stall после полезного native-события.
   SUB Риски/безопасность: PASS — loopback, случайный пароль, ограниченный env, reject/cancel и очистка ошибок присутствуют (`bridges/opencode-zen-bridge/server.py:1848`, `:2600`, `:3400`; REQ-012/REQ-015).
   SUB Риски/данные: FAIL — JSON transient recovery может повторять преамбулу и сохранять ненормализованный текст (`bridges/opencode-zen-bridge/server.py:6855`; F-004).
   SUB Риски/прод: FAIL — serve→run после upstream-отказа обходит Retry Budget; cleanup не ограничен общим сроком (`bridges/opencode-zen-bridge/server.py:5581`, `:6844`; F-007/F-008).
   SUB Риски/regression red→green: PASS — независимый RED rc=1 и GREEN кандидата приложены (`execution-evidence.md`, L2-RED-sensitivity/VER-005).
   SUB Риски/Full Suite (L2): PASS — 445 component tests, 894 root tests и обратный порядок зелёные; статический гейт rc=0 (`execution-evidence.md`, VER-001..004, AC-023).
   SUB Риски/scope-diff: PASS — ровно три разрешённых файла; frozen функции сохранены (`candidate-manifest.json`, `receipts/code-gate.json`).
   F-007 — priority=blocking; [pre-existing].
   - locations: `bridges/opencode-zen-bridge/server.py:5578`, `:5581`, `:5600`, `:5605`, `:6087`, `:6096`, `:6841`, `:6844`, `:6854`, `:6858`, `:7058`, `:7063`.
   - Правило: REQ-009; R-BULK-I2 — общий Token-Bucket Retry Budget; сохранение Full Jitter.
   - Evidence: после prompt 429/5xx либо transient provider error ветка до доставки возвращает `False` раньше `attempts.allow_retry()`. Внешний handler запускает run, проверяя потолок запусков, но не разрешение на повтор.
   - Следствие: при пустом Retry Budget запрос всё равно получает дополнительный upstream-запуск. Такой fallback не отражается как retry; это видно и в приложенном логе с `total_spawns=2 retries=0`.
   - Исправление: перед сменой транспорта после upstream-отказа провести повтор через общий admission с бюджетом, breaker и jitter. Локальный pre-upstream отказ отделить от provider failure.
   - Проверка: при исчерпанном бюджете 429/5xx/transient failure не запускают run; при доступном бюджете списывается один retry и применяется один backoff.
   F-009 — priority=blocking; [pre-existing], сопутствующий FU-007.
   - locations: `bridges/opencode-zen-bridge/server.py:3296`, `:3316`, `:3486`, `:3502`.
   - Правило: REQ-007/AC-009 — stall отсчитывается от последнего полезного события.
   - Evidence: готовый native-вызов устанавливает `first_token_at`, но не обновляет `last_token_at`. До первого токена tool-input delta также не обновляет этот срок.
   - Сценарий: при first-token timeout больше stall timeout native-вызов завершается после длительной подготовки аргументов. Следующая итерация немедленно объявляет stall, хотя полезный вызов только что получен.
   - Исправление: обновлять последнюю активность при завершённом native-вызове и явно определить семантику активности аргументов.
   - Проверка: управляемые часы, поздний первый native-вызов, затем паузы STALL−ε/ST­­ALL+ε; преждевременного stall нет.
   СОВЕТЫ (при FAIL): исправить F-007 и F-009; добавить соответствующие детерминированные regression-оракулы. VER-006/VER-007 оставить DEFERRED_L3 до ACCEPT; их отсрочка сама по себе не является причиной FAIL.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбор оправдан: упрочнение run не устраняет буферизацию; общий serve осложняет ротацию IP и увеличивает общий радиус отказа; прямой HTTP к Zen пока не доказан. Адаптация существующего parser/native mapping и сохранение legacy fallback дают практическую ценность без смены потребителя. Для текущей локальной нагрузки это существенное улучшение отзывчивости; масштабирование за её пределы пока не подтверждено.
   SUB Альтернативы/общее: PASS — выбран осуществимый путь с сохранением ротации и совместимости; повторная переработка архитектуры ради стиля не требуется (`handoff-architect.md` §4; `bridges/opencode-zen-bridge/server.py:3038`).
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Границы продукта соблюдены: standalone stdlib-мост сохранён, Google-маршрут заморожен, DSH и соседние мосты не изменены. Вместе с тем новый тестовый модуль прямо нарушает приложенные правила организации тестов и размещения измерений времени.
   SUB Соответствие контексту/общее: FAIL — новый модуль использует unittest.TestCase и содержит немаркированные измерения wall-clock в обычном наборе (`bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394`, `:597`; testing.md).
   F-010 — priority=blocking; [pre-existing].
   - locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394`, `:556`, `:1303`, `:1592`, `:1663`, `:1761`, `:1867`.
   - Правило: приложенный `agents/testing.md` — использовать pytest, не использовать `unittest.TestCase`, `setUp`, `tearDown`.
   - Evidence: пять базовых классов прямо наследуют `unittest.TestCase`; ещё два наследуют `_AttemptCase`. Это новый файл кандидата, а не неизменяемый legacy-модуль.
   - Исправление: перевести новый модуль на pytest-функции/фикстуры с сохранением всех assertions, FakeServe и процессных сценариев. Async/Litestar-зависимости для этого не нужны.
   - Проверка: все нынешние сценарии и подслучаи сохранены; полный pytest и проверка порядка зелёные.
   F-011 — priority=blocking; [pre-existing].
   - locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394`, `:556`, `:1303`, `:1663`, `:1761`, `:1867`.
   - Правило: `testing.md` §7.2 и Serial Lane — временные/ресурсные измерения выносятся в `measured`/`heavy`; unit-оракулы переходов используют управляемые часы.
   - Evidence: обычные тесты проверяют реальные сроки первого статуса, интервалы SSE, wall-clock watchdog и окна SIGTERM/SIGKILL. В новом модуле отсутствует выделение этих сценариев в measured/heavy-контур.
   - Исправление: маркировать измерительные и ресурсные сценарии, запускать их последовательно; логические проверки дедлайнов и автоматов дополнить FakeClock. Сокетный AC-026 сохранить как отдельное реальное измерение.
   - Проверка: обычный параллельный набор не содержит измерений latency/cleanup; отдельный serial lane действительно исполняется и имеет приложенный лог.
   Поштучная проверка границ:
   - Non-Goals 1 — PASS: новые публичные endpoint и схема OpenAI SSE не добавлены.
   - Non-Goals 2 — PASS: DSH, профиль и ReasoningRow не изменены.
   - Non-Goals 3 — PASS для обычного reasoning: изменения ради inline-превью не внесены.
   - Non-Goals 4 — PASS: модель, каталог и выбор effort не заменены.
   - Non-Goals 5 — PASS: muse-bridge и общие конфиги не изменены.
   - Non-Goals 6 — PASS: новых внешних Python runtime-зависимостей нет.
   - Forbidden Scope 1 — PASS: продуктовый diff ограничен разрешёнными файлами моста.
   - Forbidden Scope 2 — PASS по представленному diff и sentinel-проверкам секретов.
   - Forbidden Scope 3 — PASS на этой стадии: живая мутация отложена до ACCEPT.
   - Forbidden Scope 4 — PASS: запрещённого обращения к keychain в пакете нет.
   - Forbidden Scope 5 — PASS по diff: прямой правки общей БД нет; используется `:memory:`.
   - Forbidden Scope 6 — PASS на текущей стадии: коммит/merge в target не заявлен.
   Self-sweep выполнен по всем 14 подкатегориям. Остаточные замечания в изменённых файлах помечены `[pre-existing]`; их наличие не отменяется зелёным L2. Принадлежность к дельте конкретного цикла требует отдельного сравнения cycle-3..cycle-4, которого пакет не содержит.
   СОВЕТЫ (при FAIL): выполнить F-010 и F-011 в пределах нового тестового модуля, сохранить все проверки. После устранения блокеров повторить независимый L2; после ACCEPT провести предусмотренную живую приёмку.
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


---

## Раунд D1 (`panel/council/r36`)

### Seat 1 (`skeptic`, `muse-wonder-full-1.0`)

PANEL-NONCE: 11fdf5901adce0b4
ARTIFACT-SHA256: 25fcec1e8fb299ee624f57e742f6b88fe3c44700babf3ca4176179c737870568
AGREE F-001 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:3341 — видел сам: `_prompt_err` при пустых `texts/reasonings/native_calls` бросает `ServeUnavailable` без проверки `prompt_status["headers_at"]` (строка 3266), а ветка 429/5xx на строках 3330-3333 ставит `delivered` только по модельным массивам; обработчики SSE/JSON по этому исключению возвращают fallback в `run`. Признаю пропуск своего R1: ARG: realist/r1 «заголовки prompt уже приняты, модельных токенов ещё нет, а барьер доставки смотрит только на texts/reasonings/native_calls» + NEW: bridges/opencode-zen-bridge/server.py:3342.
AGREE F-002 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:6463 — видел сам: legacy watchdog-retry зовёт `emit_synthetic` с разделителем без гейта `thinking_enabled`; priority=non-blocking сохраняю.
DISPUTE F-003 — класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:3345 — та же ветка `_prompt_err`, тот же root cause (потеря `headers_at` в исключении) и тот же фикс, что F-001; отдельный блокер не нужен.
AMEND F-004 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3266,bridges/opencode-zen-bridge/server.py:3280; fix=публиковать HTTP-статус в `on_headers` одновременно с `headers_at` и классифицировать 400/401/403/404/422 до чтения тела — причина: bridges/opencode-zen-bridge/server.py:3266 — дефект реален, но при 4xx prompt не принят, повторного исполнения и двойного списания квоты нет; ущерб — неверная классификация, лишний serve-retry и инкремент ServeHealth при зависшем теле локального serve, что ниже порога blocking.
AGREE F-005 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:6121 — видел сам: `status_timer.cancel()` сразу после `spawn_limiter.acquire`, а `status_next` на строке 6179 пересчитывается как `attempt_start + FIRST_STATUS_DELAY_S`; при задержке gate/limiter около 0,5 с и молчащем процессе первый статус уходит за 1,0 с (AC-005). Признаю пропуск своего R1: ARG: visionary/r1 «защитный таймер отменяется сразу после лимитера, а следующий срок статуса считается заново» + NEW: bridges/opencode-zen-bridge/server.py:6179.
AMEND F-006 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6855,bridges/opencode-zen-bridge/server.py:6713; fix=пропускать transient-части через ToolCallParser/очистку и обновлять `_prior_content` перед recovery-continue — причина: evidence-ledger F-35 — штатный потребитель DSH ходит `stream:true`; тот же класс FU-002 прошлый Совет квалифицировал non-blocking большинством 2/3, нового воспроизводимого ущерба на потоковом пути не показано.
AMEND F-007 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6463; fix=обернуть legacy-разделитель в `thinking_enabled`, как в F-002 — причина: panel-rework-brief FU-010 — этот же дефект прошлый цикл закрывал как non-blocking; претензия про отсутствие разделителя в unmapped/incomplete-ветках legacy не подкреплена падающим оракулом, существующие сценарии `test_step_interruption.py` зелёны.
AGREE F-008 rev=1 — проверил: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:597 — видел сам: оракул AC-026 меряет интервалы клиентских чанков и конец апстрима, но не попарную задержку upstream→client; AC-002 остаётся INCONCLUSIVE, priority=non-blocking сохраняю.
AMEND F-009 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5581,bridges/opencode-zen-bridge/server.py:6844; fix=явно решить в FALLBACK_DECISION_TABLE, списывает ли смена транспорта Retry Budget, и при положительном решении провести её через `attempts.allow_retry()` — причина: FALLBACK_DECISION_TABLE phase=PROMPT_RESPONSE прямо предписывает `run_fallback_pre_delivery_else_serve_retry` для 429/5xx, а радиус ограничен `MAX_TOTAL_SPAWNS=3`, spawn-лимитером и `attempt_done` в breaker; это расхождение учёта, а не неограниченный шторм ретраев.
AMEND F-010 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3574,bridges/opencode-zen-bridge/server.py:2799; fix=дать cleanup-вызовам абсолютный deadline и лимит тела, а `_spawn_serve` — остаток дедлайна запроса — причина: bridges/opencode-zen-bridge/server.py:3574 — interrupt/DELETE идут к собственному loopback-serve с `timeout=0.25` и пустым телом 204; сценарий «вечно капающее тело» требует сломанного serve и не воспроизведён, AC-011 на реальных процессных тестах зелён.
AMEND F-011 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3502; fix=при завершении native-вызова обновлять `last_token_at = time.monotonic()` рядом с установкой `first_token_at` — причина: bridges/opencode-zen-bridge/server.py:3502 — дефект виден, но завершённый native-вызов в норме немедленно закрывает шаг через `step_finish`/`tool_calls`-терминатор; ложный stall требует отсутствия step_finish после вызова дольше остатка окна, воспроизводимого падения нет.
DISPUTE F-012 — класс: invalid — контр-evidence: bridges/opencode-zen-bridge/tests/test_step_interruption.py (весь существующий набор из 17 модулей на `unittest.TestCase`) и `verification-surface.json` (VER-002 — `python3 -m unittest discover` обязателен) — приложенный `testing.md` писан для async-Litestar стека, а мост — stdlib `ThreadingHTTPServer` с локальной конвенцией unittest; переписывание 1962 строк нового модуля на pytest-фикстуры противоречит правилу минимально достаточных изменений и не чинит ни одного дефекта.
DISPUTE F-013 — класс: out_of_scope — контр-evidence: `verification-surface.json` L3 «Repo has no pytest heavy/measured markers (entire component suite runs in L2)» и REQ-020/AC-026 — сокетное измерение реального времени прямо требуется постановкой в обычном наборе; `pyproject.toml` с маркерами вне конверта из 3 файлов, вводить serial-lane в этом MR нельзя.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 закрыт не полностью: после принятых заголовков prompt ошибка тела и 429/5xx теряют `headers_at`, и запрос в `auto` повторно исполняет тот же prompt через `run` (F-001, дубль F-003). Остальные RW-003..RW-008 и RP-03 verify-fixed подтверждаю.
   СОВЕТЫ (при FAIL): F-001 — не бросать `ServeUnavailable` и не ставить `delivered=False` при наличии `headers_at`; возвращать результат с `delivered=True` под serve-retry в SSE и JSON; добавить регрессию «headers получены → обрыв тела/429 до первого токена → `Run` не запускается, `record_success()` не вызывается».
2. ПОЛНОТА: VERDICT=FAIL
   WHY=AC-005 нарушаем в окне задержки старта 0,4–0,6 с: таймер отменён, следующий статус отсчитан заново от `attempt_start` (F-005). AC-002 помечен PASS без попарного замера задержки (F-008, non-blocking).
   СОВЕТЫ (при FAIL): F-005 — держать защитный таймер до первого видимого чанка или считать первый статус от единого абсолютного срока запроса; добавить оракул с задержкой лимитера 0,4–0,6 с и ровно одним `STATUS_INITIAL` ≤1,0 с.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Транспорт по умолчанию выключен, откат на `run` и disable-файл работают, зависимостей вне stdlib нет; замечания по абсолютным дедлайнам setup/cleanup понижены до non-blocking (F-010), взлёту после F-001/F-005 не мешают.
4. РИСКИ: VERDICT=FAIL
   WHY=F-001 при включённом `auto` даёт второе исполнение уже принятого prompt и двойное списание дневной квоты Zen на IP (F-23/F-32) — риск данных и прода, не покрытый существующим `test_rw001`. Безопасность, RED→green, Full Suite L2 (445 passed) и scope-diff подтверждаю.
   СОВЕТЫ (при FAIL): F-001 до включения `REALTIME_SERVE_ENABLED` в проде; F-009/F-011/F-004 — follow-up одним пакетом с фиксами из AMEND выше.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Гибрид serve-per-attempt + fallback до барьера обоснован факт-картой (RC-1, 429 прямого Zen, ротация IP); архитектурную переделку ради F-012/F-013 не поддерживаю.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Rовно 3 файла конверта, публичный контракт и замороженные функции сохранены; F-012/F-013 отклонены как противоречащие локальным конвенциям репозитория и верификационной поверхности, а не применимому контексту моста.
POSITIONS: 13/13
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `grok-4.7-high`)

PANEL-NONCE: ef1e1f24de8310f8
ARTIFACT-SHA256: 25fcec1e8fb299ee624f57e742f6b88fe3c44700babf3ca4176179c737870568

DISPUTE F-003 — класс: duplicate_of:F-001 — контр-evidence: `server.py:3265-3266`, `server.py:3330-3333`, `server.py:3341-3345`, `server.py:5512-5517`, `server.py:5577-5584`, `server.py:6779-6790`, `server.py:6840-6845` — тот же корень, что у F-001: `headers_at` пишется до тела, а `ServeUnavailable` и 429/5xx ставят барьер только по модельным массивам и уводят `auto` в `run`. Отдельный дефект не открываю. F-001 остаётся blocking.

AMEND F-004 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2604-2606, bridges/opencode-zen-bridge/server.py:3265-3266, bridges/opencode-zen-bridge/server.py:3280, bridges/opencode-zen-bridge/server.py:3302-3307; fix=публиковать HTTP-статус в `_on_headers` и закрывать 400/401/403/404/422 до чтения тела, без инкремента ServeHealth — причина: `server.py:3280` ставит `status` только после полного тела, поэтому зависшее тело 401 успевает уйти в `first_event_timeout`. При этом `server.py:3306` уже ставит `delivered` из `headers_at`, второго вызова Zen нет. У `opencode` v2.1.2 тело ошибки короткое и завершается сразу (F-21). Это не блокер включения.

AGREE F-005 rev=1 — проверил: `server.py:5947-5959`, `server.py:6119-6121`, `server.py:6179` — таймер первого статуса вооружён на t0+0.65 с и снимается сразу после `spawn_limiter.acquire`, до вывода процесса. Комментарий «статус успел уйти» ложен, если слот получен раньше 0.65 с. `status_next` заново равен `attempt_start + 0.65`. Окно gate/limiter 0.4–0.6 с сдвигает первый `[мост]` за 1.0 с от запроса. Тесты на 1.2 с и 2.5 с это окно не закрывают. REQ-004 / AC-005, blocking.

AMEND F-006 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6855-6856, bridges/opencode-zen-bridge/server.py:6870, bridges/opencode-zen-bridge/server.py:6930, bridges/opencode-zen-bridge/server.py:6954; fix=перед recovery прогонять частичный JSON-текст через тот же `ToolCallParser` и `_strip_broken_tool_blocks`, что успешный путь, и записывать нормализованный префикс в `_prior_content` — причина: `contents.extend(texts)` на transient идёт до парсера, а `_prior_content` обновляется только на unmapped/incomplete. DSH ходит со `stream:true` (F-35); FU-002 уже понижен. Для взлёта SSE это не блокер.

AMEND F-007 — priority=blocking; locations=bridges/opencode-zen-bridge/server.py:6529, bridges/opencode-zen-bridge/server.py:6560-6569; fix=перед повтором unmapped и incomplete на legacy `run` эмитить ровно одну строку `[мост] Повтор попытки`, только если thinking включён и размышление уже ушло клиенту; ветку `server.py:6463` не поднимать — она остаётся в F-002 — причина: REQ-009 / AC-014 требуют одну статусную строку между попытками после отданного размышления. `continue` на unmapped и провал цикла на incomplete разделителя не шлют. Serve это уже делает в `server.py:5489-5493`. Вызов `emit_synthetic` без `thinking_enabled` на watchdog — тот же non-blocking FU-010, что F-002.

AGREE F-008 rev=1 — проверил: `tests/test_realtime_reasoning.py:597-616` — оракул мерит интервалы клиентских чанков и конец апстрима, не задержку моста на каждой дельте. Постоянные +300 мс пересылки тест не краснит. AC-002 остаётся слабо доказан. Приоритет non-blocking не поднимаю: это не второе исполнение prompt и не дыра AC-005.

AMEND F-009 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3330-3333, bridges/opencode-zen-bridge/server.py:5577-5584, bridges/opencode-zen-bridge/server.py:5597-5605, bridges/opencode-zen-bridge/server.py:6840-6845; fix=не заводить отдельный бюджетный блокер: после фикса F-001 (`delivered` при `headers_at`) 429/5xx и transient с уже принятым prompt идут в `allow_retry`, а не в `run`; fallback без заголовков prompt бюджет не списывает — причина: `server.py:2435-2437` прямо не тарифицирует локальный отказ старта, таблица до барьера — `fallback_to_run`. Зелёный `transport_history=['serve','run']` при `retries=0` — этот путь, не обход после принятого prompt. Повторный Zen после заголовков закрывает F-001.

AMEND F-010 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2585-2588, bridges/opencode-zen-bridge/server.py:3574-3590, bridges/opencode-zen-bridge/server.py:3606; fix=на interrupt/DELETE передать абсолютный потолок тела (не обновлять 0.25 с на каждый `read1`) и после него всё равно звать `lease.cleanup` — причина: при `deadline is None` каждая порция заново получает полный `timeout`, капающее тело может не дойти до `lease.cleanup`. FU-001 уже понижен; живой `opencode` на interrupt отвечает коротким 204 (F-22); пока флаг выключен, штатный путь — `run`. Для взлёта не блокер.

AGREE F-011 rev=1 — проверил: `server.py:3296`, `server.py:3486-3490`, `server.py:3502-3506` — `last_token_at` стартует в момент prompt. Дельта аргументов двигает часы только если первый токен уже был. `session.tool.called` ставит `first_token_at` и не трогает `last_token_at`. Вызов на 30 с при пороге stall 60 с обрывается на 60 с от prompt, то есть после 30 с тишины. REQ-007 / AC-009. Blocking.

AMEND F-012 — priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394; fix=не переписывать модуль на pytest-функции в этом цикле; оставить follow-up — причина: файл действительно наследует `unittest.TestCase`, приложенный `testing.md` это запрещает. Контур моста и гейт L2 уже гоняют TestCase через pytest и `unittest discover` (`test_step_interruption.py` в том же конверте). Перепись 1962 строк не нужна, чтобы фича взлетела, и это неоправданное раздувание. В агрегирующий FAIL не входит.

DISPUTE F-013 — класс: invalid — контр-evidence: REQ-020 / AC-026 и FU-006 — сокетный red→green обязан жить в обычном наборе: на `origin/dev` он красный (`red_sensitivity_rc=1`), на кандидате зелёный (VER-005, 66 passed). Вынос в `measured`/`heavy` снимет AC-026 с гейта 445 тестов. FakeClock не заменяет приход чанков на клиентском сокете. `pyproject.toml` по FU-006 не меняется.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=F-001 не снят: заголовки prompt уже есть (`server.py:3265-3266`), а обрыв тела и 429/5xx не считают это доставкой (`server.py:3330-3333`, `server.py:3341-3345`) и в `auto` запускают второй `run` (`server.py:5512-5517`, `server.py:5577-5584`, `server.py:6840-6845`). F-005: отмена таймера до 0.65 с ломает AC-005 на короткой задержке старта. F-011: native-вызов не сбрасывает часы stall. F-007: unmapped и incomplete на legacy `run` не вставляют обязательную строку повтора (AC-014).
   СОВЕТЫ: F-001 — если `headers_at` уже есть, не бросать `ServeUnavailable` и не ставить `delivered=False`; serve-retry или явная ошибка, без `run` и без `record_success()`. F-005 — держать первый статус до видимого чанка либо от абсолютного t0+0.65 с, не от `attempt_start`. F-011 — на завершённом native-вызове писать `last_token_at`. F-007 — одна строка `[мост] Повтор попытки` на unmapped и incomplete при включённом thinking.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=AC-005 и AC-014 на изменённом пути не закрыты (F-005, F-007). Ветки F-004, F-006 и F-008 реальны, но не блокируют SSE-запуск: зависшее 4xx-тело не шлёт второй Zen, JSON-recovery — не путь DSH, оракул AC-002 слабый. L2 445 passed эти три дыры не запускает.
   СОВЕТЫ: F-005, F-007. F-004, F-006, F-008 оставить follow-up, в этот цикл не тащить.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Включать `auto` до F-001, F-005, F-007 и F-011 нельзя, но выкат после них прямой: флаг по умолчанию выключен, disable-файл сильнее `TRANSPORT=serve`, зависимостей вне stdlib нет, на попытку один короткоживущий `serve`, 6 слотов влезают в оценку памяти, на хосте есть `ps` и `lsof`. F-010 — капающее тело cleanup — не держит взлёт: штатный interrupt короткий, `lease.cleanup` после него есть. `VER-006`/`VER-007` законно отложены до ACCEPT.
4. РИСКИ: VERDICT=FAIL
   WHY=L2 зелёный и это факт: RED на `origin/dev` rc=1, кандидат 445 passed, frozen SHA-256 3/3, basedpyright 0 errors. Набор не содержит ветку F-001 (заголовки без токена) и F-011 (stall от prompt, а не от native-вызова). F-001 при включённом `auto` второй раз исполняет уже принятый prompt и второй раз бьёт дневную квоту Zen (F-23, F-32). F-011 обрывает здоровый шаг с инструментом ложным `stall_timeout`. Секреты, пароль serve, allowlist и fail-closed 401/403 на полном теле закрыты.
   СОВЕТЫ: F-001, F-011. Регрессии: `auto`, заголовки prompt есть, тело оборвано или 429 до токена — `Run` не стартует; native-вызов на 30 с при stall 60 с не даёт `stall_timeout` до 60 с тишины после вызова.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий `serve` на попытку с откатом на `run` до барьера — разрешённый гибрид. Общий демон ломает ротацию IP, прямой Zen без заголовков CLI дал 429. Перепись тестов на pytest (F-012) и вынос таймингов из обычного набора (F-013) дороже и бьют по AC-026. Выбор транспорта раздуванием не является.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Ровно три файла конверта. Публичные пути, порт и форма SSE те же; строки `[мост]` требуются REQ-004/005. `_run_env` и Google-direct побайтово заморожены, внешних runtime-зависимостей нет. Чужих ключей и правок вне моста нет. Расхождение нового модуля с шаблоном `testing.md` про TestCase — follow-up F-012, не слом границы продукта: этот мост и его гейт L2 уже на unittest.

POSITIONS: 11/11
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `gpt-6.1-sol-high`)

PANEL-NONCE: e6dfb70c15df3d9e
ARTIFACT-SHA256: 25fcec1e8fb299ee624f57e742f6b88fe3c44700babf3ca4176179c737870568

AGREE F-001 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3265-3284,3341-3345,5512-5517,6779-6790` — после HTTP 200 headers ошибка чтения тела превращается в `ServeUnavailable`, не передавая `headers_at` наружу. При отсутствии модельных дельт обработчики разрешают fallback на run. Тест с reasoning предыдущей попытки этот сценарий не покрывает. Блокирующее основание подтверждается независимо от спорной трактовки доставки при HTTP 429/5xx.

AGREE F-002 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:6463-6464` — legacy watchdog-разделитель отправляется без проверки `thinking_enabled`. Согласен с non-blocking для отключения статусов при thinking off; отсутствие разделителей между другими попытками рассматривается отдельно в F-007.

WITHDRAW F-003 — ARG: realist/R1 «Ошибка транспорта prompt поднимает `ServeUnavailable`, не глядя на `headers_at`»; проверил: `bridges/opencode-zen-bridge/server.py:3341-3345,5512-5517,6779-6790` — duplicate_of:F-001. Причина, сценарий и исправление совпадают; отдельный блокер не нужен.

AMEND F-007 — priority=blocking; locations=`bridges/opencode-zen-bridge/server.py:6463-6464,6500,6521,6545,6554`; fix=централизовать разделитель legacy-повтора после уже выданного reasoning перед фактическим следующим запуском; проверять watchdog, unmapped и incomplete recovery — причина: REQ-009/AC-014 требуют ровно одну статусную строку между попытками. ARG: realist/R1 «Остаточный разделитель legacy при `thinking off` — FU-010, без нарушения MUST». Часть про thinking off исключаю из блокирующего основания и учитываю только в F-002.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Реалтайм-транспорт устраняет фундаментальное ограничение буферизующего CLI. Однако F-001 сохраняет повторную отправку после подтверждения prompt; F-004 откладывает классификацию известных HTTP 4xx до окончания тела; F-011 допускает ложный stall после готового native-вызова. Общий PASS Скептика эти конкретные ветви не опровергает.
   СОВЕТЫ (при FAIL): сохранить подтверждение доставки при исключениях; публиковать HTTP-статус непосредственно после заголовков; обновлять часы активности при готовом native-вызове. Добавить соответствующие fault-injection проверки.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=F-005 подтверждается порядком таймеров: отмена защитного таймера после задержки старта 0,4–0,6 с переносит следующую реакцию за 1 с. F-006 сохраняет необработанный частичный JSON-текст и не устанавливает префикс дедупликации перед recovery. F-007 остаётся нарушением разделения попыток. AC-002 по F-008 — INCONCLUSIVE: интервалы клиентских чанков не измеряют задержку пересылки каждой дельты.
   СОВЕТЫ (при FAIL): удерживать абсолютный таймер до первой видимой реакции; нормализовать частичные JSON-попытки тем же parser-путём; сохранять префикс перед recovery; обеспечить единый разделитель повторов. Для AC-002 сопоставить независимые временные отметки upstream и клиента.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Serve на попытку, in-memory DB и сохранение ротации IP подходят локальной нагрузке. Но F-010 подтверждён: cleanup вызывает `_serve_http` без абсолютного deadline; каждая порция тела получает новый socket timeout. Непрерывно поступающее незавершающееся тело способно задержать переход к `lease.cleanup()` неограниченно долго.
   СОВЕТЫ (при FAIL): передавать deadline/cancellation через startup; установить отдельный абсолютный cleanup-бюджет и предел тела; гарантировать остановку группы после исчерпания бюджета. Проверить полный путь отмены, включая setup и cleanup.

4. РИСКИ: VERDICT=FAIL
   WHY=Независимый L2 принят: полный компонентный набор, корневой набор, обратный порядок и статический гейт зелёные. Маскирование секретов и frozen-функции подтверждены. Однако F-009 показывает обход Retry Budget при provider failure → fallback; F-001, F-006, F-010 и F-011 сохраняют риски повторного исполнения, повреждения результата и удержания ресурсов.
   СОВЕТЫ (при FAIL): проводить смену транспорта после upstream-отказа через общий retry admission с бюджетом, breaker и jitter; добавить проверки исчерпанного бюджета и устранить перечисленные дефекты. VER-006/VER-007 оставить DEFERRED_L3 до ACCEPT: законная отсрочка сама по себе FAIL не даёт.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Гибрид A1+C оправдан: legacy не предоставляет дельты, общий демон осложняет ротацию IP, прямой Zen пока не доказан. Решение существенно повышает наблюдаемость долгих агентных ходов и создаёт основу для развития транспорта без изменения DSH. Оснований требовать архитектурную переработку ради стиля нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Три разрешённых файла, stdlib и замороженные маршруты соблюдены. F-012/F-013 остаются прямыми нарушениями явно приложенного `testing.md`: новый модуль использует `unittest.TestCase`, а временные и ресурсные измерения не выделены в measured/heavy. Зелёный последовательный L2 не отменяет этих требований.
   СОВЕТЫ (при FAIL): перевести новый модуль на pytest-фикстуры без потери сценариев; выделить измерения в последовательный контур, логические переходы проверять управляемыми часами; приложить результаты обоих контуров.
   SEED=7e74ca61; seed_hex=7e74ca61da3ad95b244cb52cd75520e50ddd649be471d1a4856b69e0700a856c — независимо пересчитаны; ranked_order совпадает с manifest r36 полностью.

POSITIONS: 2/2
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


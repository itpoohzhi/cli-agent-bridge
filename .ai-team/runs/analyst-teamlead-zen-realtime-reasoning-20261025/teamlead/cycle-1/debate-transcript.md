# Стенограмма дебатов Совета Тимлидов по коду — Cycle 1 (run `analyst-teamlead-zen-realtime-reasoning-20261025`)

## Раунд R1 (`panel/council/r1`)

### Seat 1 (`skeptic`, `claude-sonnet-5-5-high`)

PANEL-NONCE: 1c2ff9a190c73460
ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4
Канон прочитан: AGENTS.md, 430 строк

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Конверт закрыт по составу (ровно 3 файла моста, Google и `_run_env` заморожены, публичный SSE с `[мост]` разрешён REQ-004/005, потолок `MAX_TOTAL_SPAWNS=3` и `begin_attempt` до serve на `server.py:5150` и `:5967` сохранены). Serve-попытка обходит `_StartupGate` и `spawn_limiter`: `note_spawn()` на `server.py:4848` и `:5768` сразу зовёт `_serve_one_attempt`, тогда как run берёт оба на `server.py:4490–4492` и `:5297–5299` (REQ-013). Рукопожатие после `select` 3 с читает строку по байту без дедлайна (`server.py:2552–2556`). Reaper смотрит только живой `parent_pid` и шлёт один SIGTERM (`server.py:2593–2614`), не сверяя `parent_start_ts` с lease (`server.py:72`). HTTP 429/5xx prompt пишется в `prompt_status["status"]` (`server.py:2879–2880`) и дальше учитывается лишь как `headers_at`; `first_event_timeout` тогда делает `serve_health.record_failure()` (`server.py:4893–4894`), а строка таблицы про 429 требует breaker +1 и serve_health 0.
   СОВЕТЫ: Перед `_spawn_serve` в обоих serve-обработчиках вызывать тот же `_StartupGate` и `spawn_limiter.acquire`, что у run, с `release` в `finally`. На цикл `os.read` рукопожатия повесить остаток дедлайна 3 с и при истечении делать `ServeUnavailable` плюс `lease.cleanup()`. В `_startup_reaper` сравнивать `parent_start_ts`/`helper_lstart` с живым `ps lstart` до решения «родитель жив»; после SIGTERM ждать `graceful_stop` 5 с, затем SIGKILL, lease удалять только когда группа мертва. Ответ prompt 429 и provider 5xx проводить через `attempts.attempt_done(True, False)` без инкремента `serve_health`; либо исполнять `FALLBACK_DECISION_TABLE`, либо удалить её.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Legacy watchdog, realtime-чанки, usage, permission/form и split tool-text покрыты зелёным L2. Дыры MUST: JSON-serve не передаёт `is_client_gone` (`server.py:5770–5780` против `:4860`); `tool_choice` запроса отбрасывается (`server.py:4950`, `:4961`, вызов `:5981` с литералом `None`); маркеры `__never_event__`/`__silent__` (`tests/test_realtime_reasoning.py:99` и `:102`) ни одним тестом не вызываются; `tests/test_step_interruption.py` не выставляет `OPENCODE_ZEN_BRIDGE_TRANSPORT` и гоняет матрицу только на shebang-фейке `opencode run`.
   СОВЕТЫ: Прокинуть `self._client_gone_check` в `_serve_json_serve` так же, как в stream. Протащить `tool_choice` запроса в оба serve-обработчика и в `_incomplete_step_signal` / `_incomplete_tool_step_prompt`. Добавить serve-тесты на `__silent__` и `__never_event__`: убийство группы за порог+2 с и `exit_reason` `first_event_timeout` / `first_token_timeout` / `stall_timeout`. Прогнать сценарии `test_step_interruption.py` (или эквивалентный fake-delta набор) при `TRANSPORT=serve`.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Opt-in serve, `:memory:` и fallback до доставки сопровождать можно, L2 это показывает. На проде до 6 слотов каждый serve — холодный процесс ~152 MiB без сериализации `_StartupGate` и без `SPAWN_RATE_PER_S` (`server.py:4848`, `:5768`). Уборка группы сдаётся через 0.5 с + SIGKILL + 0.5 с (`server.py:2464–2473`); в `l2-green-ver002-unittest.log` рядом с serve `O-EXIT` есть `ResourceWarning: subprocess 98704 is still running`. Слушатель доказывается через `lsof`, lstart — через `ps`.
   СОВЕТЫ: Тот же gate и limiter, что в совете по КОРРЕКТНОСТИ. В `cleanup` ждать SIGTERM до существующего `graceful_stop` 5 с, затем SIGKILL и ждать, пока `pgid` мёртв. Если `lsof`/`ps` недоступны или слушатель не доказан — fail-closed `ServeUnavailable`, а не пропуск проверки.

4. РИСКИ: VERDICT=FAIL
   WHY=Утечки пароля в `bridge.log` по этому diff нет: `_drain_stderr(helper, [])` на `server.py:2570` пишет в пустой список, `_log` не вызывается; `_mask_secrets` на `server.py:3242` маскирует последовательности от 24 символов, пароль — `token_hex(16)`. Allowlist проверен тестом. Red→green и полный L2 зелёные: `L2-RED` rc=1 на `origin/dev`, `VER-005` 21 passed, `VER-001` 400 passed, `AC-023` rc=0, scope — 3 файла. Ломается REQ-005: `_JsonParser._string` кладёт каждый `\uXXXX` отдельным `chr` (`server.py:1675–1680`), SSE идёт через `_loads_object` (`server.py:2857`), ошибка разбора становится `{}` (`server.py:1701–1706`). REQ-008 на проде: уборка 0.5 с (`server.py:2464–2473`) и reaper без сверки lstart оставляют группу живой; JSON-клиент не детектится (см. ПОЛНОТА).
   СОВЕТЫ: Удалить `_JsonParser`, разбирать serve JSON через уже импортированный `json.loads` с явной проверкой типа. Удлинить ожидание kill до 5 с и не возвращаться, пока группа жива. Закрыть reaper и `is_client_gone` для JSON по советам выше. Оракул AC-020: после прогона сгенерированный пароль отсутствует в `bridge.log`.

5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL
   WHY=Выбор A1 (короткий `opencode serve` на попытку, fallback на run до доставки) оправдан фактами F-17..F-19 и прецедентом muse-bridge; дублирование stream/JSON само по себе не раздувание. Неоправдан собственный JSON-парсер на ~150 строк (`server.py:1630–1706`) при уже импортированном `json`: суррогатные пары `\uD83D\uDE00` не склеиваются, `RecursionError` глубже `except (OSError, ValueError)` читателя. `FALLBACK_DECISION_TABLE` не исполняется, тест заканчивается `assertTrue(silence or rows)` (`tests/test_realtime_reasoning.py:619`).
   СОВЕТЫ: Заменить `_loads_object` на `json.loads`. Либо исполнять таблицу fallback, либо удалить константу и утверждать в тесте конкретные инкременты `serve_health`/`breaker` для строки 429.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=SEED/seed_hex сверка: SHA-256(seed_input)=4525cada06248f2093f1acba9b9dd03c41c8dc7ef4d6a34167b8ed0ff91caa40 совпал с manifest.json seed_hex; SEED8=4525cada; ranked_order манифеста [grok-4.7-high, gpt-6.1-sol-high, gemini-4-argon-high, muse-wonder-full-1.0, claude-sonnet-5-5-high] принят как опубликованный (полный rank_slots по таблице пула в этом ходе не пересчитывался). Границы задачи удержаны: только `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`; новых runtime-зависимостей вне stdlib нет; DSH, muse-bridge, georouter и каталог не тронуты; `[мост]` в `reasoning_content` задан REQ-004/005; `_run_env`/`_stream_google_sse`/`_execute_google_once` совпали с замороженными sha256 (`google_direct_unchanged=True`). Слой Litestar к этому мосту неприменим. VER-006/VER-007 законно `DEFERRED_L3`.

### F-001
priority: blocking
criterion: КОРРЕКТНОСТЬ/логика, РЕАЛИЗУЕМОСТЬ
locations: bridges/opencode-zen-bridge/server.py:4848, bridges/opencode-zen-bridge/server.py:5768, bridges/opencode-zen-bridge/server.py:4490, bridges/opencode-zen-bridge/server.py:5297
rule: REQ-013 / AC-018; S-HERD-I1 (холодный старт сериализуется `_StartupGate`)
evidence: `attempts.note_spawn()` затем `_serve_one_attempt` без `gate.acquire()` и без `spawn_limiter.acquire`; run-путь: `gate = _StartupGate()` и `self.res.spawn_limiter.acquire` / `res.spawn_limiter.acquire`.
fix: Перед `_spawn_serve` в `_run_serve_stream_attempts` и `_serve_json_serve` захватывать `_StartupGate` и `spawn_limiter` с тем же `max_wait_s`, освобождать в `finally` попытки.
verify: Тест двух перекрывающихся serve-попыток показывает сериализацию gate и отказ limiter при превышении `SPAWN_RATE_PER_S`.

### F-002
priority: blocking
criterion: КОРРЕКТНОСТЬ/граничные условия
locations: bridges/opencode-zen-bridge/server.py:2552
rule: feature.md — таймаут на каждом шаге I/O, включая чтение после первого байта
evidence: `select.select([out_fd], [], [], 3.0)` покрывает только появление fd; далее `while not line_bytes.endswith(b"\n"): chunk_b = os.read(out_fd, 1)` без дедлайна.
fix: Читать рукопожатие с остатком тех же 3 с; по истечении `ServeUnavailable` и `lease.cleanup()`.
verify: Helper, который пишет один байт и замолкает, убивается в бюджете рукопожатия, слот и группа освобождены.

### F-003
priority: blocking
criterion: КОРРЕКТНОСТЬ/граничные условия
locations: bridges/opencode-zen-bridge/server.py:72, bridges/opencode-zen-bridge/server.py:2593, bridges/opencode-zen-bridge/server.py:2609, bridges/opencode-zen-bridge/server.py:2613
rule: REQ-008 / AC-011
evidence: Lease пишет `"parent_start_ts": parent_lstart`. Reaper: `parent_alive = parent_pid > 0 and _pid_alive(parent_pid)` и при живом pid делает `continue`; иначе один `os.killpg(pgid, signal.SIGTERM)` и сразу `path.unlink()`.
fix: Сверять lstart родителя и helper с lease до вывода «жив»; SIGKILL после 5 с; не удалять lease, пока группа жива. Тест с `helper_pid=0` эту ветку не исполняет — заменить живым фейком.
verify: Lease мёртвого родителя, чей pid переиспользован (lstart не совпал), приводит к смерти helper+serve; lease остаётся, пока группа жива.

### F-004
priority: blocking
criterion: ПОЛНОТА/пропущенные ветки
locations: bridges/opencode-zen-bridge/server.py:5770, bridges/opencode-zen-bridge/server.py:4860
rule: REQ-008 / AC-012 (обнаружение ухода клиента не позже 5 с, группа отсутствует не позже 7 с)
evidence: Stream передаёт `is_client_gone=self._client_gone_check`. Вызов из `_serve_json_serve` аргумент не передаёт (`on_status=lambda _t: None` и сразу `thinking_enabled`).
fix: Передавать `is_client_gone=self._client_gone_check` в JSON-попытку.
verify: Закрытие сокета non-stream клиента останавливает группу не позже 7 с.

### F-005
priority: blocking
criterion: ПОЛНОТА/покрытие AC
locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:99, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:102
rule: REQ-006 / REQ-007 / AC-008 / AC-009 / AC-010
evidence: `if "__never_event__" in prompt` и `if "__silent__" in prompt` есть в `FAKE_SERVE`; вызовов этих маркеров в тестах нет. Legacy `FAKE_RT_MODE=silent` покрывает только run.
fix: Три теста TRANSPORT=serve: нет событий → `first_event_timeout`; событие без токена → `first_token_timeout`; токен и пауза → `stall_timeout`; завершение за порог+2 с.
verify: Тесты красные, если цикл `_serve_one_attempt` перестаёт проверять эти три порога.

### F-006
priority: blocking
criterion: ПОЛНОТА/пропущенные ветки
locations: bridges/opencode-zen-bridge/server.py:4950, bridges/opencode-zen-bridge/server.py:4961, bridges/opencode-zen-bridge/server.py:5981
rule: REQ-011 (STEP_RECOVERY на потоковом пути, включая forced tool_choice)
evidence: `tool_choice=None` в `_incomplete_step_signal`; `_incomplete_tool_step_prompt(..., None, model)`; вызов `self._serve_json_serve(..., reported_model, None, res, attempts, xs)` при том, что параметр `tool_choice` у `_serve_json` есть и внутри `_serve_json_serve` используется.
fix: Протащить `tool_choice` запроса в stream- и JSON-serve и в оба вызова recovery.
verify: Serve-шаг с текстом без tool при `tool_choice`, требующем вызов, ретраится с force-клаузой в prompt.

### F-007
priority: blocking
criterion: ПОЛНОТА/покрытие AC
locations: bridges/opencode-zen-bridge/tests/test_step_interruption.py:188
rule: REQ-011 / AC-016
evidence: `setUp` изолирует `_Resilience()` (это закрывает REQ-017). По файлу нет `OPENCODE_ZEN_BRIDGE_TRANSPORT`; фейк — shebang `opencode run`. Матрица incomplete/unmapped/tool_calls на serve не исполняется.
fix: Прогнать существующие сценарии прерывания шага (или их fake-delta эквивалент) с `TRANSPORT=serve`.
verify: Регрессия остановки по tool_calls или incomplete-retry на serve роняет этот тест.

### F-008
priority: blocking
criterion: РИСКИ/данные, АЛЬТЕРНАТИВЫ
locations: bridges/opencode-zen-bridge/server.py:1675, bridges/opencode-zen-bridge/server.py:1701, bridges/opencode-zen-bridge/server.py:2857
rule: REQ-005 (байты размышления модели не модифицируются); python-standards KISS при уже импортированном `json`
evidence: `parts.append(chr(int(hex_part, 16)))` без склейки суррогатной пары; `_loads_object` на `ValueError`/`IndexError` возвращает `{}`; читатель SSE кладёт payload через `_loads_object`.
fix: Удалить `_JsonParser` и разбирать объекты через `json.loads`.
verify: Дельта `reasoning_content` с `\uD83D\uDE00` доходит одним символом; битый JSON не превращается молча в пустое событие без `invalid_serve_event`.

### F-009
priority: blocking
criterion: КОРРЕКТНОСТЬ/обработка ошибок
locations: bridges/opencode-zen-bridge/server.py:2879, bridges/opencode-zen-bridge/server.py:4893, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:619
rule: Строка `FALLBACK_DECISION_TABLE` «PROMPT_RESPONSE HTTP429/provider5xx»: `serve_retry`, ServeHealth 0, UpstreamBreaker +1; REQ-009 (breaker сохраняется)
evidence: `prompt_status["status"] = st` и `headers_at` выставляются для любого статуса, кроме отдельной ветки 401/403. Дальше `first_event_timeout` делает `res.serve_health.record_failure()`. Тест: `self.assertTrue(silence or rows)`.
fix: 429 и provider 5xx на prompt проводить в `attempt_done(True, False)` без `serve_health`; убрать тавтологию, утверждать инкременты строки 429.
verify: Три ответа prompt 429 не делают `is_degraded()`, breaker фиксирует отказ.

### F-010
priority: blocking
criterion: РИСКИ/прод
locations: bridges/opencode-zen-bridge/server.py:2464, bridges/opencode-zen-bridge/server.py:2467, bridges/opencode-zen-bridge/server.py:2471
rule: REQ-008 / T-LIFE (процесс и читатель закрываются до возврата)
evidence: `self.helper.wait(timeout=0.5)`, затем `os.killpg(..., SIGKILL)`, затем снова `wait(timeout=0.5)` и выход. `execution-evidence.md` / `l2-green-ver002-unittest.log`: `ResourceWarning: subprocess 98704 is still running` рядом со строками serve `O-EXIT`.
fix: Ждать SIGTERM до 5 с, затем SIGKILL и ждать завершения; не возвращаться из `cleanup`, пока `_pid_alive(pgid)`.
verify: Прогон unittest, включающий serve-тесты, не печатает `subprocess is still running`.

### F-011
priority: non-blocking
criterion: КОРРЕКТНОСТЬ/логика
locations: bridges/opencode-zen-bridge/server.py:1791
rule: Предохранитель `_is_native_opencode_bin` в `auto` (shebang-фейк должен оставаться на run)
evidence: `or len(head) == 4` после проверки Mach-O/ELF. Любой файл без `#!` длиной от 4 байт считается нативным.
fix: Убрать дизъюнкт `len(head) == 4`; оставить Mach-O и ELF. Тест: 4 байта не-shebang → False.
verify: Короткий бинарный мусор в `auto` не выбирает serve.

### F-012
priority: non-blocking
criterion: ПОЛНОТА/покрытие AC
locations: bridges/opencode-zen-bridge/server.py:1339
rule: REQ-004 (первая видимая строка). Живой статус закрывается `STATUS_WAITING`, константа начального текста не используется.
evidence: `STATUS_INITIAL = "[мост] Подключение к модели…\n"` — присваивание без чтения в diff.
fix: Эмитить `STATUS_INITIAL` как первую статусную строку либо удалить константу.
verify: Поиск по `server.py` либо находит эмиссию, либо константы нет.

### F-013
priority: non-blocking
criterion: КОРРЕКТНОСТЬ/граничные условия
locations: bridges/opencode-zen-bridge/server.py:2495, bridges/opencode-zen-bridge/server.py:2564
rule: REQ-008 (свой слушатель). Окно между `bind` пробного сокета и bind serve; `lsof` с `None` проверку чужого слушателя пропускает.
evidence: Скан порта `bind`/`close`, затем helper; `if listener_pid is not None and (listener_pid != serve_pid or ...)`.
fix: Держать пробный сокет до старта serve или перепроверять слушателя до prompt; `lsof` без pid — `ServeUnavailable`.
verify: Занятый между probe и bind порт даёт `ServeUnavailable`, а не чужой HTTP.

### F-014
priority: non-blocking
criterion: КОРРЕКТНОСТЬ/логика
locations: bridges/opencode-zen-bridge/server.py:2654, bridges/opencode-zen-bridge/server.py:2678
rule: REQ-012 (native tool → текущий внутренний вид). DSH-маппинг читает имя и arguments; статус в выдачу DSH не входит.
evidence: `feed` присваивает `item["text"] = text_value` вместо накопления дельт; `complete` всегда кладёт `"status": "error"`, в том числе на `session.tool.success`.
fix: Склеивать `input.delta` либо опираться только на `input.ended.text`; статус брать из типа события.
verify: Фикстура `session.tool.success` с двумя delta даёт полный JSON аргументов и status `success`.

### F-015
priority: non-blocking
criterion: РИСКИ/безопасность
locations: bridges/opencode-zen-bridge/server.py:2569, bridges/opencode-zen-bridge/server.py:2570, bridges/opencode-zen-bridge/server.py:3242
rule: REQ-015 / AC-020. Пароль в лог этим путём не пишется: sink пустой, `_mask_secrets` режет токены ≥24 символов.
evidence: Комментарий «stderr помощника дренируется в лог»; вызов `_drain_stderr(helper, [])`. `_drain_stderr` только дополняет список.
fix: Либо логировать stderr через `_mask_secrets`, либо поправить комментарий. Добавить тест: пароль попытки отсутствует в `bridge.log`.
verify: Прогон serve с известным паролем, `assertNotIn(password, log)`.

### F-016
priority: non-blocking
criterion: ПОЛНОТА/покрытие AC
locations: bridges/opencode-zen-bridge/server.py:4877, bridges/opencode-zen-bridge/server.py:4884
rule: REQ-016 / AC-021. Поля в строке `O-EXIT/v1` есть; после fallback значение `first_event_ms` остаётся от serve при `transport=run`.
evidence: `xs["first_event_ms"] = result["first_event_ms"]` дважды подряд до ветки fallback, которая меняет `transport` на `run` и возвращает `False`.
fix: При возврате в run сбрасывать `first_event_ms`/`ttft_ms` либо помечать, к какому транспорту они относятся.
verify: O-EXIT fallback-запроса не показывает serve-миллисекунды как тайминг итогового run.

### F-017 [sweep]
priority: non-blocking
criterion: ПОЛНОТА/покрытие AC
locations: bridges/opencode-zen-bridge/server.py:1795, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:634
rule: REQ-003 / AC-004. Дефолт без флага — run: полный сьют 400 passed это подтверждает. Прямой матрицы kill-switch нет.
evidence: `_select_transport` читает `TRANSPORT`, `REALTIME_SERVE_ENABLED` и файл `disable-serve`. Тесты группы B форсят `serve` или один сценарий `auto`+503.
fix: Четыре случая: `TRANSPORT=run`, override `0`, файл disable, опечатка значения — все остаются на run и не зовут `_spawn_serve`.
verify: Счётчик спавнов serve в этих четырёх случаях равен 0.

### F-018
priority: non-blocking
criterion: ПОЛНОТА/покрытие AC
locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:441
rule: REQ-001 / AC-001 / AC-002. Реалтайм на сокете есть (red на `origin/dev`, green `VER-005`). Интервал соседей &lt;500 мс и накладные моста ≤250 мс тест не утверждает: проверяется span &lt;2.0 с и «первая дельта раньше конца апстрима».
evidence: `test_ac026_realtime_chunks_before_upstream_end` сравнивает `model_reasoning[-1][0] - model_reasoning[0][0]` с `2.0`.
fix: Утверждать максимум соседнего интервала reasoning-чанков и верхнюю границу задержки мост↔сокет на фейке с известным `sleep`.
verify: Тест красный, если чанки склеиваются в один блок в конце шага.

SUB Корректность/логика: FAIL — server.py:4848 и :5768 `note_spawn` без `_StartupGate`/`spawn_limiter`, run их берёт на :5297 (REQ-013)
SUB Корректность/граничные условия: FAIL — server.py:2552 чтение рукопожатия без дедлайна; server.py:2593 reaper без `parent_start_ts` (REQ-008)
SUB Корректность/обработка ошибок: FAIL — server.py:2879/:4893 prompt 429 увеличивает `serve_health`, таблица требует breaker; test_realtime_reasoning.py:619 тавтология
SUB Полнота/покрытие AC: FAIL — test_realtime_reasoning.py:99/:102 маркеры serve-watchdog без теста; test_step_interruption.py без TRANSPORT=serve (AC-008..010, AC-016)
SUB Полнота/пропущенные ветки: FAIL — server.py:5770 JSON без `is_client_gone`; server.py:4950/:5981 `tool_choice=None` (REQ-008, REQ-011)
SUB Реализуемость/общее: FAIL — server.py:4848/:5768 холодный serve без gate; server.py:2464 cleanup 0.5 с и ResourceWarning в l2-green-ver002 (REQ-013, REQ-008)
SUB Риски/безопасность: PASS — server.py:2570 `_drain_stderr(helper, [])` не вызывает `_log`; server.py:3242 `_mask_secrets` маскирует токен ≥24; пароль в лог не пишется (REQ-015)
SUB Риски/данные: FAIL — server.py:1675 `\uXXXX` как отдельный `chr`, SSE через `_loads_object` на :2857 (REQ-005)
SUB Риски/прод: FAIL — server.py:2464–2473 wait 0.5 с и сдача; ResourceWarning `subprocess 98704 is still running` в VER-002 (REQ-008)
SUB Риски/regression red→green: PASS — execution-evidence.md L2-RED rc=1 на origin/dev, VER-005 rc=0, 21 passed (REQ-020)
SUB Риски/Full Suite (L2): PASS — code-gate.json VER-001 400 passed rc=0, AC-023-pytest-reversed rc=0
SUB Риски/scope-diff: PASS — candidate-manifest.json ровно 3 файла в bridges/opencode-zen-bridge; Forbidden Scope не задет
SUB Альтернативы/общее: FAIL — server.py:1630–1706 свой JSON-парсер при импортированном `json` (KISS, REQ-005)
SUB Соответствие контексту/общее: PASS — seed_hex 4525cada… совпал с manifest; Non-Goals и freeze Google/_run_env удержаны (REQ-002, REQ-018)

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 18


### Seat 2 (`realist`, `grok-4.7-high`)

PANEL-NONCE: fce3b92e58de602c
ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4

Проверяю пакет как судья «Реалист»: все 14 подкатегорий, реализуемость выката, ресурсы и зависимости. Результаты проверок беру из приложенных свидетельств; тесты не запускаю.

Применяю правила `teamlead-gate` для полного прохода. Общий канон `~/Мой диск/Context/AGENTS.md` прочитан до `<!-- КАНОН-КОНЕЦ -->`; в рабочей папке `AGENTS.md`, `.agents/AGENTS.md` и `CLAUDE.md` отсутствуют. Профильные стандарты прочитаны в приложенном пакете.

L2 подтверждает зелёный полный набор, но reverse-spec отмечает непроверенные ветки serve. Сверяю их с кодом, прежде всего таймауты, повторы и освобождение ресурсов.

Нашёл конкретные расхождения: serve обходит ограничитель стартов, отбрасывает дельты из одних пробелов и переводов строк, а некоторые ошибки запуска выходят до уборки процесса. Полный L2-прогон остаётся подтверждённым; он не проверяет эти сценарии. Завершаю сверку требований и повторный проход по рубрике.

Повторный проход завершён. Базовая идея внедряема: нужный CLI установлен, новый транспорт не требует сторонних Python-зависимостей, а память предварительно укладывается в бюджет. Блокеры — в реализации жизненного цикла и совместимости serve с прежним поведением. Отсроченные `VER-006` и `VER-007` учитываю как законный `DEFERRED_L3`, без отдельного FAIL.

PANEL-NONCE: fce3b92e58de602c
ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4

Общий канон `~/Мой диск/Context/AGENTS.md` прочитан до `<!-- КАНОН-КОНЕЦ -->`. В рабочей папке `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` отсутствуют; приложенные профильные стандарты прочитаны. Проверенные SHA-256 трёх файлов совпадают с манифестом. Тесты самостоятельно не запускал.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL  
   WHY=Транспорт реализуем, но новый путь теряет часть модельных данных, нарушает семантику повторов, `tool_choice`, завершения инструментального шага и общего дедлайна. Обнаружены пути ложного успешного завершения и превышения потолка запусков.  
   СОВЕТЫ (при FAIL): выполнить F-001–F-016 и F-030; проверить одинаковые сценарии через stream и JSON.

2. ПОЛНОТА: VERDICT=FAIL  
   WHY=Полный L2 зелёный, однако матрица приёмки приписывает ему проверки, которых приведённые тесты не выполняют. Не закрыты существенные ветки serve: таймауты, повтор после доставки, отключение клиента, JSON, полноценная уборка и восстановление после смерти родителя.  
   СОВЕТЫ (при FAIL): выполнить F-023–F-029; заменить групповые заявления PASS по AC точными свидетельствами отдельных оракулов.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL  
   WHY=Зависимости доступны: установленный `opencode v2.1.2`, Python stdlib, georouter и пул прокси. Расчёт памяти `64 + 6 × 192 = 1216 MiB ≤ 1638,4 MiB` предварительно сходится; фактический расход активных процессов остаётся предметом законно отложенного L3. Сейчас внедрение блокируют обход ограничителя стартов и утечки процессов, потоков и памяти.  
   СОВЕТЫ (при FAIL): выполнить F-008, F-017–F-023; затем провести H0–H9 с шестью параллельными запросами рабочего размера. Оценка исправлений с проверками — ориентировочно 3–5 рабочих дней одного разработчика с независимой верификацией; доступность живой квоты определяет срок L3.

4. РИСКИ: VERDICT=FAIL  
   WHY=Есть конкретные риски передачи авторизации неподтверждённому слушателю, сигналов чужому процессу при PID reuse, зависания cleanup, повреждения текста и блокировки Circuit Breaker. Зелёные результаты L2 признаю: 400 компонентных тестов и 894 теста корневого набора; они не доказывают отсутствия перечисленных дефектов.  
   СОВЕТЫ (при FAIL): выполнить F-003–F-005, F-009–F-012, F-017–F-024, F-026, F-028, F-030, F-032. `VER-006` и `VER-007` оставить `DEFERRED_L3` до ACCEPT; их отсрочка сама по себе не является замечанием.

5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL  
   WHY=Короткоживущий serve с резервным run оправдан фактами: он сохраняет ротацию окружения и даёт реальные дельты. Однако собственный JSON-парсер добавляет значительный объём и дефекты вместо использования уже разрешённой стандартной библиотеки. Таблица fallback также существует отдельно от реально исполняемой политики.  
   СОВЕТЫ (при FAIL): выполнить F-002 и F-011–F-012; использовать один проверяемый механизм классификации исходов для stream и JSON.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL  
   WHY=Периметр файлов соблюдён, Google Direct и `_run_env` побайтово сохранены, новых сторонних runtime-зависимостей нет. Но нарушены применимые требования `R-BULK`, `S-HERD`, `T-LIFE`, правила тестирования и подавления диагностик. Новые параметры эксплуатации не сопровождаются документацией.  
   СОВЕТЫ (при FAIL): устранить перечисленные нарушения; согласовать расширение разрешённого набора файлов для обязательной документации. Не переносить stdlib-мост на Litestar и не добавлять зависимости ради формального соответствия чужому стеку.

1. SUB Корректность/логика: FAIL — потеря `tool_choice`, отсутствует остановка после инструментального шага, возможен четвёртый запуск (`server.py:4950`, `5971`, `3052`, `5298`; REQ-009, REQ-011).
2. SUB Корректность/граничные условия: FAIL — пробельные дельты отбрасываются, Unicode surrogate pair разбирается неверно (`server.py:3018`, `3029`, `1679`; AC-006, REQ-010).
3. SUB Корректность/обработка ошибок: FAIL — статусы prompt и транзиентные ошибки не проходят требуемую классификацию (`server.py:2879`, `2965`, `4909`, `5813`; REQ-009, REQ-011).
4. SUB Полнота/покрытие AC: FAIL — временной оракул сравнивает приход с EOF клиента, не с независимым окончанием апстрима (`tests/test_realtime_reasoning.py:442`; AC-001, AC-002, AC-026).
5. SUB Полнота/пропущенные ветки: FAIL — serve JSON, разрыв клиента, watchdog serve и реальные orphan-сценарии не закрыты приведёнными тестами (`verification-traceability.md`, `reverse-spec.md §4.3`; F-024).
6. SUB Реализуемость/общее: FAIL — serve обходит ограничитель стартов и имеет утечки на отказах запуска (`server.py:4848`, `5768`, `2572`; REQ-008, REQ-013).
7. SUB Риски/безопасность: FAIL — ownership допускает отсутствие доказательства слушателя, reaper не сверяет идентичность владельца (`server.py:2565`, `2593`, `2606`; security.md, T-LIFE).
8. SUB Риски/данные: FAIL — потеря пробелов, повторная выдача префикса и неполный usage попыток (`server.py:3029`, `4843`, `4915`; REQ-005, REQ-014).
9. SUB Риски/прод: FAIL — сброс общего дедлайна, неверный timeout переиспользованного соединения и незавершённый HALF_OPEN (`server.py:2889`, `2403`, `4914`; R-BULK-I1, R-BULK-I3).
10. SUB Риски/regression red→green: PASS — независимый RED на `origin/dev`: 16 failed; кандидат: 21 passed (`execution-evidence.md`, `L2-RED-sensitivity`, `VER-005`); достаточность конкретных оракулов отдельно оспорена в F-024.
11. SUB Риски/Full Suite (L2): PASS — подтверждены 400 passed, обратный порядок 400 passed, корневой набор 894 passed / 5 skipped (`execution-evidence.md`, VER-001–003, AC-023).
12. SUB Риски/scope-diff: PASS — ровно три разрешённых файла; замороженные функции совпали (`candidate-manifest.json`, `code-gate.json`, VER-004).
13. SUB Альтернативы/общее: FAIL — собственный JSON-парсер неоправданно раздувает решение и ломает допустимый JSON (`server.py:1560`; python-standards.md §6, §16).
14. SUB Соответствие контексту/общее: FAIL — подавления типов, новые TestCase и немаркированные временные проверки нарушают прямые стандарты (`tests/test_realtime_reasoning.py:2`, `279`, `397`, `321`; testing.md, python-standards.md §9).

Поштучная сверка требований и AC:

- REQ-001 — FAIL: AC-001 и AC-002 — INCONCLUSIVE по измерениям; присутствуют дефекты доставки F-001, F-002.
- REQ-002 — FAIL по поведенческой совместимости F-013–F-014; AC-003 подтверждён существующими проверками формы, но не полной эквивалентностью serve.
- REQ-003 — PASS по наличию переключаемого run; AC-004 — PASS по полному L2. Полная матрица переключателей требует F-024.
- REQ-004 — FAIL; AC-005 — FAIL для медленных setup/gate, F-006.
- REQ-005 — FAIL; AC-006 — FAIL, F-001–F-002; AC-007 — PASS.
- REQ-006 — FAIL для непрерывного служебного stdout; AC-008 покрыт только ограниченным legacy-сценарием, F-007, F-024.
- REQ-007 — FAIL; AC-009 и AC-010 не доказаны для serve и конфликтуют с пятисекундным socket timeout, F-004.
- REQ-008 — FAIL; AC-011 и AC-012 не доказаны, имеются дефекты F-017–F-023.
- REQ-009 — FAIL; AC-013 — FAIL, F-009; AC-014 — FAIL для части повторов, F-015.
- REQ-010 — FAIL; AC-015 не доказан на полном переборе serve-дельт; пробельные фрагменты теряются, F-001.
- REQ-011 — FAIL; AC-016 не доказан на новом транспорте; F-012–F-014.
- REQ-012 — политика `ask_reject` обеспечивает отказ разрешения по коду; AC-017 — INCONCLUSIVE: нет эквивалентной serve-матрицы unmapped. Изоляция событий нарушена F-030.
- REQ-013 — FAIL из-за обхода `_StartupGate` и rate limiter; AC-018 — INCONCLUSIVE: соответствующий двухзапусковый оракул не приведён.
- REQ-014 — FAIL, F-016; AC-019 подтверждает отображение полей mapper, но не полный финальный usage HTTP-ответа.
- REQ-015 — INCONCLUSIVE по AC-020: санитизация окружения проверена, требуемый поиск случайного пароля и `apiKey` в финальном логе не показан.
- REQ-016 — поля существуют; AC-021 проверен на успешном legacy-выходе, полная матрица выходов INCONCLUSIVE; семантика таймингов нарушена F-032.
- REQ-017 — PASS; AC-022 и AC-023 — PASS по независимым полным прогонам. Дополнительная утечка окружения — F-026.
- REQ-018 — PASS; AC-024 — PASS по полному набору и замороженным хешам.
- REQ-019 — DEFERRED_L3; AC-025 — DEFERRED_L3, допустимо до ACCEPT.
- REQ-020 — FAIL по достаточности оракула AC-026, F-024; сам факт RED→GREEN признаётся.

Границы проверены отдельно:

- Non-Goals: маршруты, порт и форма SSE сохранены; поведенческие регрессии перечислены отдельно. DSH, `cordis.patch.yml`, `ReasoningRow`, выбор модели/эффорта, каталог Zen, другие мосты и общие конфиги не изменены. Сторонние runtime-зависимости не добавлены. Побайтовая сохранность reasoning нарушена F-001–F-002.
- Forbidden Scope: изменений вне разрешённых трёх файлов нет; секретов в представленном diff нет; мутаций `~/.dsh`, общей БД и общего состояния пакет не заявляет; вызовов Keychain нет. Коммит в защищённую ветку и merge не выполнялись.
- HL: арифметические оценки памяти, georouter `6 ≤ 48`, FD `128 ≤ 45875,2` и портов `48 ≤ 8192` сходятся как оценки конверта. Они не заменяют поведенческие оракулы. `S-HERD-I1`, `R-BULK-I1..I3`, `C-MULT-I4`, `T-LIFE` имеют конкретные нарушения ниже. Применимость правил pooled-клиентов, Snapshot, Redis и async event loop нельзя переносить на этот автономный stdlib-мост без учёта его архитектуры.

Все замечания одним списком; повторный проход по подкатегориям 1–14 выполнен.

**F-001 — priority=P1, blocking. Потеря пробельных дельт.**  
Locations: `server.py:3018`, `server.py:3029`. Правило: REQ-005, REQ-010, AC-006. Evidence: `if text_value.strip():` окружает накопление и передачу дельты. Отдельные `" "`, `"\n"` и отступы исчезают, меняя reasoning, обычный текст и содержимое JSON-аргументов инструмента. Исправление: передавать все непустые дельты; определение первого содержательного токена отделить от сохранения байтов. Проверка: разбиения с отдельными пробелами, LF, отступами и пробелом внутри строкового аргумента дают исходную конкатенацию.

**F-002 — priority=P1, blocking. Собственный JSON-парсер повреждает Unicode.**  
Locations: `server.py:1560`, `server.py:1679`, `server.py:1705`, `server.py:2857`. Правило: python-standards.md §6, §16; REQ-005. Evidence: каждый `\uXXXX` преобразуется отдельным `chr()`. Допустимая пара `\ud83d\ude00` остаётся двумя суррогатами и ломает последующее UTF-8-кодирование. Глубина также не ограничена, `RecursionError` не обработан. Исправление: заменить парсер stdlib `json.loads` с типизированной границей и явной обработкой ошибок. Проверка: escaped emoji, вложенный JSON, невалидный JSON и прежние wire-фикстуры.

**F-003 — priority=P1, blocking. Общий дедлайн не управляет serve-попыткой.**  
Locations: `server.py:2718`, `server.py:2889`, `server.py:2892`, `server.py:3080`. Правило: `R-BULK-I1`, feature.md — остаток дедлайна на всей I/O-цепочке. Evidence: вместо дедлайна запроса создаётся `prompt_send_start + TIMEOUT_S`; при исчерпании цикла возвращается результат с пустыми `terminal` и `exit_reason`. Caller может выдать успешный финал для незавершённого ответа. Исправление: передавать абсолютный deadline, ограничивать им setup/read/retry и явно классифицировать истечение. Проверка: повтор у границы общего дедлайна не продлевает запрос; отсутствие terminal никогда не становится успехом.

**F-004 — priority=P1, blocking. Пять секунд тишины ошибочно обрывают serve.**  
Locations: `server.py:2827`, `server.py:2848`, `server.py:2860`, `server.py:2928`. Правило: REQ-006–007, AC-009–010. Evidence: SSE-соединение создано с `timeout=5`; таймаут чтения превращается в EOF/`invalid_serve_event`, хотя первый токен и stall по умолчанию допускают 60 секунд. Исправление: согласовать чтение сокета с watchdog и отличать промежуточную тишину от окончания потока. Проверка: пауза больше 5 секунд и меньше заданного watchdog не вызывает повтор или ошибку.

**F-005 — priority=P1, blocking. Timeout cleanup не применяется к существующему соединению.**  
Locations: `server.py:2403`, `server.py:2755`, `server.py:2997`, `server.py:3084`, `server.py:3094`. Правило: feature.md — таймаут каждого шага, включая `finally`; REQ-008. Evidence: при переданном `conn` аргумент `timeout=0.25` не меняет timeout соединения, созданного ранее с 3 секундами. Несколько управляющих вызовов и их повторов задерживают `lease.cleanup()`. Исправление: применять актуальный timeout к сокету, ограничить общий cleanup-бюджет, гарантировать kill группы независимо от HTTP-cleanup. Проверка: зависшие control-endpoints не удерживают процессы дольше AC-011.

**F-006 — priority=P1, blocking. Первая видимая реакция отсутствует во время setup.**  
Locations: `server.py:2740`, `server.py:2778`, `server.py:2810`, `server.py:2835`, `server.py:2890`, `server.py:5298`, `server.py:5363`. Правило: REQ-004, AC-005. Evidence: статус начинает обслуживаться после spawn/readiness/create/subscribe; в legacy — после ожидания gate/limiter и запуска. Исправленная база `status_next` не позволяет эмитить статус во время уже блокирующего setup. Исправление: обслуживать ограниченный по времени первый статус с момента открытия SSE, включая ожидания запуска. Проверка: каждый setup-этап и занятый gate задержаны более секунды, статус всё равно приходит в пределах AC-005.

**F-007 — priority=P1, blocking. Legacy-watchdog зависит от отсутствия stdout.**  
Locations: `server.py:1096`, `server.py:5439`, `server.py:5453`. Правило: REQ-006–008. Evidence: надзор передан как `on_idle`; поступление каждой строки сбрасывает idle. Непрерывные служебные либо невалидные строки предотвращают проверку первого токена, stall и ухода клиента. Исправление: выполнять надзор по независимому монотонному расписанию и при поступлении данных. Проверка: служебные строки каждые 100 мс не отменяют watchdog и обнаружение disconnect.

**F-008 — priority=P1, blocking. Serve обходит защиты холодного старта.**  
Locations: `server.py:4848`, `server.py:5768`, `server.py:2740`. Правило: REQ-013, `S-HERD-I1`, `R-BULK-I2`. Evidence: перед `_serve_one_attempt` вызывается `note_spawn()`, но нет `_StartupGate.acquire()` и `res.spawn_limiter.acquire()`, присутствующих в run. Шесть обработчиков могут одновременно поднять шесть serve. Исправление: подключить serve к тем же защитам с остатком дедлайна и гарантированным освобождением. Проверка: конкурентные stream/JSON-запросы соблюдают общий темп запусков и gate.

**F-009 — priority=P1, blocking. Fallback может превысить потолок трёх запусков.**  
Locations: `server.py:4866`, `server.py:4897`, `server.py:5298`, `server.py:5785`, `server.py:5806`, `server.py:5992`, `server.py:4491`. Правило: REQ-009, AC-013, `R-BULK-I2`. Evidence: после нескольких serve-попыток `return False` переводит управление в run без новой проверки потолка; run непосредственно запускает процесс и делает `note_spawn()`. Сам fallback также обходит `allow_retry`. Исправление: единый допуск каждой следующей попытки, включая смену транспорта. Проверка: две доставленные неудачи serve, третья pre-delivery неудача — run не становится четвёртым запуском.

**F-010 — priority=P1, blocking. Успех serve не закрывает HALF_OPEN Circuit Breaker.**  
Locations: `server.py:4914`, `server.py:5818`. Правило: REQ-009, `R-BULK-I3`. Evidence: успех сбрасывает только `serve_health`; `attempts.attempt_done(False, True)` отсутствует. Зарезервированная проба HALF_OPEN не завершается успехом, последующие запросы могут оставаться заблокированными. После предыдущего timeout также может сохраниться `_pending_failure`. Исправление: завершать каждую попытку через общий механизм breaker. Проверка: OPEN → HALF_OPEN → успешный serve → CLOSED; timeout → успешный повтор не засчитывается окончательным отказом.

**F-011 — priority=P1, blocking. Prompt-response не управляет барьером доставки и классификацией ошибок.**  
Locations: `server.py:2413`, `server.py:2414`, `server.py:2879`, `server.py:2880`, `server.py:2901`, `server.py:2965`. Правило: заявленная `FALLBACK_DECISION_TABLE`, REQ-009. Evidence: `headers_at` записывается после чтения всего тела; `status` и `error` практически не используются, security проверяется только после получения очередного SSE-события. HTTP 400/404/422/429/5xx prompt не получают заявленных действий. Исправление: фиксировать доставку при получении заголовков, независимо наблюдать результат worker и применять полную таблицу решений. Проверка: все классы prompt-ответов, включая заголовки с зависшим телом и отсутствие SSE, дают нужный исход без недопустимого fallback.

**F-012 — priority=P1, blocking. Ошибки провайдера обходят прежнюю recovery-семантику.**  
Locations: `server.py:3073`, `server.py:4909`, `server.py:5813`, `server.py:4943`, `server.py:5884`. Правило: REQ-009, REQ-011. Evidence: любой `result["error"]` немедленно завершает запрос; различие транзиентной и фатальной ошибки не используется. В `_incomplete_step_signal` передаётся `False` вместо факта транзиентного обрыва. Исправление: сохранить классификацию, лимиты и восстановление legacy-пути на накопленном результате serve. Проверка: 429/5xx/transport error до и после вывода, фатальные 4xx и все соответствующие сценарии `test_step_interruption.py`.

**F-013 — priority=P1, blocking. Теряется `tool_choice`.**  
Locations: `server.py:4753`, `server.py:4950`, `server.py:4961`, `server.py:5971`. Правило: REQ-002, REQ-011; обратная совместимость входного контракта. Evidence: stream-helper не принимает `tool_choice`, использует `None`; JSON-helper получает явный `None` вместо аргумента `_serve_json`. Recovery для `required` и конкретного имени инструмента меняет поведение. Исправление: передавать исходное значение через все serve-ветки. Проверка: `required`, именованный выбор и `none` эквивалентны run.

**F-014 — priority=P1, blocking. Serve не останавливается после инструментального шага.**  
Locations: `server.py:3046`, `server.py:3052`, `server.py:3077`, `server.py:4804`. Правило: REQ-011. Evidence: после получения tool call и `session.step.ended` цикл продолжает читать до `session.execution.succeeded`; последующие text/reasoning не блокируются для обычного текстового tool call. Исправление: завершать попытку на границе шага с вызовами, interrupt/cleanup выполнять до дальнейшей генерации. Проверка: апстрим посылает второй шаг после первого tool call — второй шаг не попадает клиенту, итог `tool_calls`.

**F-015 — priority=P1, blocking. Повтор serve дублирует уже отданный текст.**  
Locations: `server.py:4843`, `server.py:4901`, `server.py:4925`, `server.py:4952`, `server.py:5850`, `server.py:5908`. Правило: сохранение recovery-семантики, REQ-009. Evidence: парсер пересоздаётся, но аналог `_PrefixDedup`/`_dedup_retry_text` не применяется; JSON соединяет результаты попыток. Повторы unmapped/incomplete также не получают обязательного разделителя reasoning между попытками. Исправление: сохранить reasoning без дедупликации, явно разделять попытки, дедуплицировать текст по прежнему правилу. Проверка: одинаковый и расходящийся префиксы при timeout/incomplete/unmapped через оба режима.

**F-016 — priority=P2, blocking. Usage неуспешных попыток теряется.**  
Locations: `server.py:4886`, `server.py:4915`, `server.py:5795`, `server.py:5874`. Правило: REQ-014. Evidence: ветки timeout/invalid-event выполняют `continue` до аккумуляции уже полученного `result["usage"]`. Исправление: учитывать usage завершённых шагов всех оплаченных попыток до принятия решения о повторе. Проверка: первая попытка отдаёт `step.ended`, затем обрывается; финальный usage равен сумме её токенов и успешного повтора.

**F-017 — priority=P1, blocking. На ошибках запуска пропускается cleanup.**  
Locations: `server.py:1768`, `server.py:2510`, `server.py:2550`, `server.py:2563`, `server.py:2568`, `server.py:2572`, `server.py:2740`. Правило: REQ-008, `T-LIFE`, secure temporary files. Evidence: собственные `raise ServeUnavailable(...)` не входят в `except (OSError, ValueError, subprocess.SubprocessError)`; вызов `_spawn_serve` расположен до `try/finally` попытки. При отказе `Popen` также не закрывается write-конец lifeline и не удаляется созданный state-dir. Исправление: обеспечить владение ресурсами с момента их создания и cleanup на каждом исходе. Проверка: spawn failure, handshake timeout/mismatch и foreign listener оставляют ноль процессов, FD, lease и state-dir. Лог L2 дополнительно содержит `ResourceWarning: subprocess ... is still running`.

**F-018 — priority=P1, blocking. SSE-reader может навсегда остаться на заполненной очереди.**  
Locations: `server.py:2842`, `server.py:2859`, `server.py:2863`, `server.py:2865`, `server.py:3107`. Правило: `T-LIFE`, `C-MULT-I4`. Evidence: оба `events.put(...)` блокирующие, без timeout/cancel; reader не присоединяется при выходе consumer. Убийство serve не разблокирует поток, уже ожидающий место в Python-очереди. Исправление: cancellation-aware bounded queue, отдельный сигнал окончания и ограниченный join. Проверка: заполнить очередь, отменить запрос; поток и принадлежащие ему ресурсы освобождаются.

**F-019 — priority=P2, blocking. Дренаж stderr накапливает неограниченную память.**  
Locations: `server.py:2570`, `server.py:1028`. Правило: ограниченные ресурсы `HL-ENV`, `C-MULT-I2`. Evidence: `_drain_stderr(helper, [])` добавляет каждую строку в список, удерживаемый потоком до окончания попытки; список никем не читается и не ограничен. Исправление: использовать ограниченный хвост либо дренаж с отбрасыванием и счётчиком. Проверка: многомегабайтный непрерывный stderr не вызывает линейного роста RSS.

**F-020 — priority=P1, blocking. Авторизация отправляется без обязательного ownership-proof слушателя.**  
Locations: `server.py:2374`, `server.py:2564`, `server.py:2565`, `server.py:2778`. Правило: security.md, подтверждение владения до передачи секретов. Evidence: `listener_pid is None` допускается; проверка выполняется сразу после handshake, до гарантированного bind serve. Порт предварительно освобождается, поэтому возможна гонка, а последующий reconnect не перепроверяет владельца. Исправление: требовать положительное совпадение listener PID, PGID и живого helper до первой авторизованной записи и при явном reconnect; неоднозначность — fail-closed. Проверка: отсутствующий/чужой/сменившийся слушатель получает ноль байтов Authorization и prompt.

**F-021 — priority=P1, blocking. Reaper не проверяет идентичность процессов.**  
Locations: `server.py:74`, `server.py:2593`, `server.py:2606`, `server.py:2609`. Правило: `T-LIFE`, безопасность сигналов. Evidence: сохранённые UID/start-time/attempt не сверяются; достаточно живого PID и подстроки `"--serve-helper"`. PID reuse может сохранить сироту либо привести к сигналу другой сессии. Исправление: сверять UID, реальные времена старта, точный script/argv, attempt и PGID; безопасно работать с lease-каталогом. Проверка: переиспользованные PID, чужой helper и подложный lease не получают сигналов.

**F-022 — priority=P1, blocking. Lifeline не гарантирует остановку всего дерева при смерти моста.**  
Locations: `server.py:174`, `server.py:177`, `server.py:181`, `server.py:195`. Правило: REQ-008, `T-LIFE`. Evidence: helper завершает только непосредственный `serve_proc`, после чего удаляет lease. Потомок serve, переживший родителя, не получает гарантированный групповой сигнал и лишается следа для reaper. Исправление: реализовать проверяемое завершение всей собственной группы при EOF/TERM, включая эскалацию. Проверка: убить мост при helper → serve → grandchild; все процессы исчезают, чужие группы не затронуты.

**F-023 — priority=P1, blocking. Отмена клиента реализована не во всех режимах.**  
Locations: `server.py:4750`, `server.py:5769`. Правило: REQ-008. Evidence: `_client_gone_check` превращает RST/OSError в `False`; JSON-путь вообще не передаёт callback `is_client_gone`. Исправление: различать отсутствие данных и терминальный разрыв, подключить надзор к JSON и setup-ожиданиям. Проверка: FIN и RST до первого события, после токена и в JSON приводят к остановке в пределах AC-011.

**F-024 — priority=P1, blocking. Матрица PASS не соответствует содержимому оракулов.**  
Locations: `tests/test_realtime_reasoning.py:376`, `tests/test_realtime_reasoning.py:434`, `tests/test_realtime_reasoning.py:442`, `tests/test_realtime_reasoning.py:619`; `verification-traceability.md`, строки REQ-001, REQ-006–016. Правило: testing.md — независимый эталон полноты; task envelope — поштучная проверка AC. Evidence: `upstream_end_t = elapsed` — EOF самого клиентского ответа; выдача всех пяти дельт одной пачкой также удовлетворяет `first < elapsed` и spread `<2`. Пределы 500/250 мс не проверяются; `assertTrue(silence or rows)` заведомо проходит при непустой таблице. Исправление: независимые upstream timestamps/барьеры; добавить serve JSON, три watchdog, delivered-retry, лимиты, cleanup, permission/unmapped и финальный usage. Исправить traceability по реальным результатам; аварийную чистоту подпроцессов подтвердить crash-guard либо предусмотренным ручным свидетельством. Проверка: намеренно буферизующая и нарушающая таблицу реализация должна краснить соответствующие тесты.

**F-025 — priority=P2, blocking. «Ноль диагностик» получен с подавленными правилами.**  
Locations: `tests/test_realtime_reasoning.py:2`, `381`, `384`, `385`, `390`, `391`, `408`, `411`, `429`, `431`. Правило: python-standards.md — запрет №9; запрет необъяснённых suppressions. Evidence: заголовок выключает множество диагностик, включая `reportAny` и `reportMissingParameterType`; новые обращения содержат необъяснённые `type: ignore`. Исправление: убрать blanket-подавления и ненужные ignores, исправить типы; узкие исключения обосновать. Проверка: новый файл проверяется с включёнными соответствующими правилами.

**F-026 — priority=P2, blocking [sweep]. Тест удаляет исходное значение окружения.**  
Locations: `tests/test_realtime_reasoning.py:299`, `tests/test_realtime_reasoning.py:300`. Правило: testing.md — гарантированный откат `os.environ`. Evidence: после `self.env.stop()`, восстановившего исходный `FAKE_RT_MODE`, выполняется безусловный `pop`. Исправление: удалить дополнительную мутацию либо восстанавливать точное предыдущее состояние. Проверка: запуск при заранее установленном значении сохраняет его после teardown.

**F-027 — priority=P2, blocking. Новый тестовый модуль нарушает прямой запрет TestCase.**  
Locations: `tests/test_realtime_reasoning.py:279`, `tests/test_realtime_reasoning.py:397`. Правило: testing.md — «Не использовать `unittest.TestCase`, `setUp`, `tearDown`». Evidence: оба новых класса основаны на TestCase. Исправление: использовать pytest-тесты и фикстуры с гарантированным teardown. Async/Litestar-инструментарий для этого синхронного stdlib-моста не требуется. Проверка: тот же набор сценариев проходит без новых TestCase.

**F-028 — priority=P2, blocking. Измерения времени смешаны с обычным тестовым контуром.**  
Locations: `tests/test_realtime_reasoning.py:321`, `392`, `444`, `445`, `568`, `624`. Правило: testing.md §7.2, Serial Lane. Evidence: wall-clock assertions выполняются в обычном полном наборе без `measured`/`heavy`; уже зафиксировано падение около границы 1 секунды. Исправление: выделить замеры в последовательный измерительный контур, а состояния watchdog дополнить FakeClock-оракулами. Проверка: обычный набор не зависит от загрузки машины; отдельный измерительный прогон сохраняет проверки реального клиентского сокета.

**F-029 — priority=P2, blocking. Эксплуатационные изменения не документированы.**  
Locations: `server.py:1326`, `server.py:1743`, `server.py:1795`; `candidate-manifest.json:files`. Правило: python-standards.md §12. Evidence: добавлены transport/permission/watchdog overrides, dynamic-config и disable-файл, но разрешённый трёхфайловый diff не содержит обновлений README/CHANGELOG. Исправление: согласовать расширение документационного scope и описать приоритеты переключателей, пороги, fallback и откат. Проверка: оператор может включить и отключить транспорт по опубликованной инструкции без чтения исходника.

**F-030 — priority=P2, blocking. Фильтр чужих сессий применяется после потери sessionID.**  
Locations: `server.py:1844`, `server.py:1845`, `server.py:1875`, `server.py:2973`. Правило: граница изоляции serve-сессии, security.md — проверка входа на границе. Evidence: mapper удаляет `sessionID` у reasoning/text/error, затем фильтр разрешает `None`; чужая дельта либо ошибка проходит. Исправление: проверять sessionID в исходном wire-событии до отображения и обработки. Проверка: события второй сессии не меняют текст, usage, исход и watchdog текущей.

**F-031 — priority=P3, non-blocking. Проверка нативного бинарника почти всегда разрешающая.**  
Locations: `server.py:1777`, `server.py:1791`. Правило: заявленная проверка допуска auto. Evidence: `or len(head) == 4` принимает любой файл длиной не меньше четырёх байтов без shebang. Исправление: проверять известные исполняемые форматы либо убрать вводящее в заблуждение утверждение о такой проверке. Проверка: произвольный четырёхбайтовый файл не считается нативным opencode.

**F-032 — priority=P2, blocking [sweep]. Поля «первого события» переписываются последующими попытками.**  
Locations: `server.py:4877`, `server.py:4884`, `server.py:5456`, `server.py:5468`, `server.py:5793`. Правило: REQ-016, `O-EXIT/v1`. Evidence: значения запроса перезаписываются таймингами очередной попытки; в сыром L2 есть `first_event_ms=1975 ttft_ms=974`. В итоге названия полей не соответствуют первому событию и первому токену запроса. Исправление: сохранять первые request-level значения, attempt-level значения учитывать отдельно. Проверка: retry/fallback не стирает первый момент; для одного запроса первый токен не предшествует первому событию.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 32


### Seat 3 (`visionary`, `gemini-4-argon-high`)

PANEL-NONCE: 7ec7d741c844094d
ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4

**Позиция Визионера.** Стратегически кандидат правильный. Это гибрид C: `opencode serve` по SSE с откатом на `run`, как в `muse-bridge` (ADR-0004). Он единственный даёт реальные дельты размышления (F-19), kill-switch и расширяемую телеметрию `O-EXIT/v1`. Но в нынешнем виде он ломает доставку текста, ломает конкурентность и ухудшает дефолтный путь `run`. Номера строк в F-блоках приблизительные: они выведены из диапазонов VER-004 и названий функций, потому что в пакете есть только diff.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=В `_serve_one_attempt` дельты reasoning и text с пустым `.strip()` не пересылаются клиенту. Параграфные `\n\n` и пробелы теряются, это нарушает AC-006 и ломает превью DSH по `\n` (F-01). Аллокация порта serve гоняется при параллельных запросах и может отправить пароль чужому serve, после чего ответ fail-closed с `ServeSecurityError` (F-02). Для serve не реализованы `_StartupGate` и `spawn_limiter` из REQ-013 (F-04). Статус ответа prompt игнорируется (F-05). Повтор после `delivered=True` дублирует контент и tool_calls (F-06). Сторож `FIRST_TOKEN_TIMEOUT_S=60` убивает легитимные шаги дефолтного пути `run` (F-03).
   СОВЕТЫ:
   - Пересылать любые непустые дельты без `strip`, а живость токенов считать отдельно (F-01).
   - Выделять порты под замком до проверки владения слушателем или брать порт 0 (F-02).
   - Не применять 60-секундные сторожа токенов к legacy-пути и вынести его поведение за флаг (F-03).
   - Подключить `spawn_limiter` и `_StartupGate` к serve (F-04).
   - Разбирать `prompt_status`, а `FALLBACK_DECISION_TABLE` либо сделать исполняемой, либо удалить (F-05).
   - После отданного контента делать дедуп или не ретраить (F-06).

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Нет тестов на AC-011 и AC-012, на serve-таймауты, на `_serve_json_serve` (+208 строк), на AC-018 и AC-020; фикстуры `__silent__` и `__never_event__` не используются (F-10). Первый статус `[мост]` ≤1.0 с (REQ-004) не гарантирован: `STATUS_INITIAL` не эмитируется, а ожидание gate и фаза spawn молчат (F-07). Матрица прослеживаемости ставит PASS «по VER-001» для требований без теста. Часть тестов тавтологична (F-13). Поддерживаемость страдает из-за функций по ~350 строк и дублирования stream/JSON (F-17).
   СОВЕТЫ:
   - Добавить тесты на watchdog, client_gone, kill orphans, JSON-serve, ротацию прокси и отсутствие пароля в логах.
   - Эмитить `STATUS_INITIAL` сразу после role-чанка, до gate.
   - Исправить матрицу прослеживаемости.
   - Разбить `_serve_one_attempt` и вынести общую логику stream/JSON.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Скрытые операционные издержки: гонка портов при `max_concurrent=6` (F-02), утечка tempdir и FD при сбое spawn (F-09), `lsof` и `ps` на каждую попытку, предсказуемый каталог в `/tmp` (F-14). Неподтверждённый реальный wire v2.1.2: событие с пустым `data` (на 161 мс в F-19 есть `integration.updated`) даёт `ServeProtocolError` с `delivered=True` (F-08).
   СОВЕТЫ:
   - Сериализовать запуск serve.
   - Освобождать ресурсы в `finally` до создания lease.
   - Снять реальные wire-фикстуры v2.1.2 и прогнать лестницу H0..H9 до включения флага.
   - Ограничить права на lease-каталог.

4. РИСКИ: VERDICT=FAIL
   WHY=Искажение данных клиента (F-01), регрессия дефолтного пути `run` (F-03), конкурентный отказ (F-02), риск 100% отказа serve на реальном wire (F-08). Полный набор зелёный (400 passed, `VER-001..003`, `AC-023`), но проверяет в основном фейки. Выявленные дефекты воспроизводимы только новыми тестами. Lease-каталог в `/tmp` без владельца и режима (F-14). Прямая мутация `os.environ` в `test_step_interruption.py` (F-21).
   СОВЕТЫ:
   - Закрыть F-01, F-02, F-03 и F-08 regression-тестами по схеме red→green.
   - Поднять конкурентный тест на 6 запросов.
   - Добавить live-замер на реальном `opencode` после сброса квоты.

5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL
   WHY=Выбор архитектуры оправдан. Но реализация раздута: самописный `_JsonParser` на ~150 строк при импортированном stdlib `json` (F-11), тестовый хук `SERVE_TEST_ELIGIBLE` и вакуумная `_is_native_opencode_bin` в проде (F-15), мёртвая `FALLBACK_DECISION_TABLE` (F-05).
   СОВЕТЫ:
   - Заменить парсер на `json.loads` с явным `except`.
   - Убрать тестовые хуки из продакшн-кода.
   - Удалить декларативную таблицу или сделать её исполняемой.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Нарушены python-standards: блоковое подавление pyright и `type: ignore` без обоснования (F-12), функции сильно длиннее ~40 строк и дубли (F-17), тавтологичные тесты (F-13), шум форматирования в немодифицируемых зонах (F-16). Публичный OpenAI-контракт и `_run_env`/Google-срезы не изменены, это соответствует Non-Goals.
   СОВЕТЫ:
   - Убрать подавления типов, типизировать тесты.
   - Откатить косметические hunk'и.
   - Декомпозировать serve-функции.
   - Переименовать тесты, чьи ожидания изменены (F-18).

**SUB-строки (14/14):**
1. SUB Корректность/логика: FAIL — `_serve_one_attempt` (server.py:~2360-3114) `if text_value.strip():` в ветках reasoning и text; `_spawn_serve`; повтор в `_run_serve_stream_attempts` (F-01, F-02, F-06)
2. SUB Корректность/граничные условия: FAIL — whitespace-дельты, события с пустым `data`, stall при длинном tool-input (F-01, F-08, F-20)
3. SUB Корректность/обработка ошибок: FAIL — `_prompt_worker` игнорирует статус и ошибку, `_loads_object` возвращает `{}` при ошибке, `_spawn_serve` пропускает не-`ServeUnavailable` OSError (F-05, F-09, F-11)
4. SUB Полнота/покрытие AC: FAIL — AC-011/012/018/020 без тестов; REQ-013 и REQ-004 не выполнены полностью (F-04, F-07, F-10)
5. SUB Полнота/пропущенные ветки: FAIL — не реализованы строки 429/5xx и ответ prompt из таблицы; нет дедупа при повторе (F-05, F-06)
6. SUB Реализуемость/общее: FAIL — гонка портов при `max_concurrent=6`, утечки, `lsof` на попытку (F-02, F-09)
7. SUB Риски/безопасность: FAIL — предсказуемый `/tmp/opencode-zen-bridge-leases` без 0700 и проверки `owner_uid`; пароль может уйти чужому слушателю (F-14, F-02)
8. SUB Риски/данные: FAIL — потеря `\n` и пробелов в `reasoning_content` и `content` (F-01)
9. SUB Риски/прод: FAIL — `FIRST_TOKEN_TIMEOUT_S=60` на буферизующем `run`, максимум наблюдения 85.65 с (F-03, F-08)
10. SUB Риски/regression red→green: PASS — `l2-red.log` rc=1 на `origin/dev`, зелёный на кандидате; слабость RED (падения по `AttributeError`) учтена в F-13
11. SUB Риски/Full Suite (L2): PASS — `receipts/code-gate.json` VER-001/002/003/003b/005 и AC-023 rc=0, 400 passed; VER-006/007 законно DEFERRED_L3
12. SUB Риски/scope-diff: FAIL — косметический реформат `Run.execute`, `_RequestAttempts`, `_UpstreamBreaker`, `_PrefixDedup` и др. (F-16)
13. SUB Альтернативы/общее: FAIL — самописный `_JsonParser`, тестовый хук в проде (F-11, F-15)
14. SUB Соответствие контексту: FAIL — python-standards #9, §6/§7, testing.md об `os.environ` (F-12, F-17, F-21)

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

**F-блоки**

F-01 [blocking] Whitespace-дельты не пересылаются клиенту
- Locations: server.py:~2360-3114 (`_serve_one_attempt`, ветки `etype == "reasoning"` и `etype == "text"`).
- Правило: REQ-005/AC-006 (текст модели не модифицируется), REQ-001; F-37 (превью требует `\n`).
- Evidence: `if text_value.strip(): … on_reasoning(text_value)` и такое же условие для `on_text`.
- Fix: пересылать любую непустую дельту без `strip`; `first_token_at` и `last_token_at` обновлять только по содержательным токенам.
- Проверка: тест с дельтами `"\n\n"`, `" "`, `"\n"`: конкатенация побайтно равна эталону, в том числе внутри `<tool_invoke>`.

F-02 [blocking] Гонка выбора порта serve и отправка пароля не тому serve
- Locations: server.py:~2360-3114 (`_spawn_serve`, цикл `range(20000 + pid%20000, 60000)` с bind-проб и закрытием сокета); `_serve_one_attempt` (ready-проверка).
- Правило: C-MULT-I3/I4; `scope-and-contracts` (не ломать конкурентные запросы); `security.md` §9.
- Evidence: все потоки сканируют от одного кандидата, сокет закрывается до bind serve. Два запроса в окне ~110 мс получают один порт. Если `lsof` ещё не видит слушателя, `GET /api/session/active` попадает в чужой serve и возвращает 401. Это `ServeSecurityError` без fallback.
- Fix: глобальный замок на выделение порта до проверки владения; либо `--port 0` с чтением реального порта; 401 на ready до DELIVERED считать `ServeUnavailable`.
- Проверка: тест на 6 параллельных stream-запросов, ни одного `serve security failure`.

F-03 [blocking] Регрессия дефолтного пути `run`: watchdog первого токена 60 с
- Locations: server.py:5351-5474 (`send_keepalive`, `watchdog_state`); константы `FIRST_TOKEN_TIMEOUT_S`, `FIRST_EVENT_TIMEOUT_S`, `STALL_TIMEOUT_S`.
- Правило: REQ-003 (прежний путь остаётся рабочим), REQ-002.
- Evidence: F-17/F-18: `run` выдаёт reasoning и text одним блоком в конце шага. F-32: максимум `deepseek-v4.1-flash-free` 85.65 с. По умолчанию serve выключен, поэтому путь `run` основной. Шаг дольше 60 с убивается и повторяется до 3 раз. Статусы `[мост]` и watchdog на `run` работают вне переключателя транспорта.
- Fix: для legacy использовать потолок не ниже прежнего поведения либо отдельные пороги с высоким дефолтом, `first_event` считать по `step_start`, watchdog первого токена оставить только для serve; поведение legacy за флагом.
- Проверка: фейк-CLI с паузой 70 с до единого блока завершается успешно без ретраев.

F-04 [blocking] REQ-013 не выполнен для serve
- Locations: server.py:~2360-3114 (`_serve_one_attempt` / `_spawn_serve`); AC-018.
- Правило: REQ-013 (`_StartupGate`, `SPAWN_RATE_PER_S`), R-BULK-I2.
- Evidence: serve-путь не вызывает `gate.acquire()` и `res.spawn_limiter.acquire()`, теста на ротацию IP нет.
- Fix: acquire `spawn_limiter` и gate перед `_spawn_serve`, release в `finally`.
- Проверка: тест двух запусков с подменённым `_next_standalone_proxy` и ограничением частоты.

F-05 [blocking] Результат prompt-POST игнорируется, `FALLBACK_DECISION_TABLE` мёртва
- Locations: server.py:~2360-3114 (`_prompt_worker`, `prompt_status`); `FALLBACK_DECISION_TABLE` (server.py:~1450-1560).
- Правило: `error-handling.md` (Identify→Assess), REQ-009.
- Evidence: пишется `prompt_status["status"/"error"]`, проверяется только 401/403. 400/429/5xx и сетевая ошибка приводят к ожиданию 20 с. Строка таблицы про 429 и provider5xx не реализована, тест таблицы проверяет только `len ≥ 10`.
- Fix: классифицировать статус prompt по таблице (retry с breaker+1, fail-closed на 400/404/422) или удалить таблицу.
- Проверка: FakeServe отвечает 429 на prompt, затем retry без ожидания 20 с.

F-06 [blocking] Повтор после отданного контента дублирует text и tool_calls
- Locations: server.py:4734-4967 (`_run_serve_stream_attempts`, ветки `allow_retry`/`continue`); `_serve_json_serve`.
- Правило: REQ-009/AC-014, REQ-010.
- Evidence: legacy использует `_PrefixDedup`, serve нет. После `stall_timeout` при уже отданных text или tool_call повтор выдаёт тот же контент снова.
- Fix: дедуп префикса либо запрет retry после отданного text или tool_call.
- Проверка: тест stall после части текста и вызова инструмента, клиент не видит дублей.

F-07 [blocking] Первый статус ≤1.0 с (REQ-004) не гарантирован
- Locations: server.py:5351-5474 (`send_keepalive`); `_serve_one_attempt` (`status_next`, `STATUS_INITIAL`).
- Правило: REQ-004/AC-005.
- Evidence: `STATUS_INITIAL` объявлен и нигде не эмитируется. На legacy статусы идут только из цикла `feed.lines`, а до него `_StartupGate` держит до 5 с (STARTUP_WAIT_S) и `spawn_limiter`. На serve цикл статусов стартует после spawn, ready, create, subscribe.
- Fix: эмитить `STATUS_INITIAL` сразу после role-чанка до gate и spawn при включённом thinking.
- Проверка: удержать gate 3 с, первый чанк с `[мост]\n` приходит ≤1.0 с.

F-08 [blocking] Реальный wire v2.1.2 не проверен: события с пустым `data`
- Locations: server.py:~1800-1880 (`_map_serve_event`: `if not data: raise ServeProtocolError`); `_serve_one_attempt` (`except ServeProtocolError` → `delivered=True`).
- Правило: R-BULK-I3, REQ-012; факт-карта F-19, VER-006 DEFERRED_L3.
- Evidence: любое событие кроме `server.connected` с пустым `data` (в F-19 на 161 мс приходит `integration.updated`) даёт `invalid_serve_event`, `delivered=True` и retry вместо fallback. Все фикстуры синтетические.
- Fix: игнорировать неизвестные события и пустой `data`, валидировать только известные типы; добавить фикстуры, снятые с реального serve; прогнать VER-006 на живом контуре до включения флага.
- Проверка: тест, подающий heartbeat и `integration.updated` с пустым `data`, не прерывает попытку. Статус PLAUSIBLE.

F-09 [blocking] Утечка tempdir и FD при сбое запуска serve
- Locations: server.py:~2360-3114 (`_serve_env` → `mkdtemp`; `_spawn_serve`: `os.pipe`, `Popen` до создания `_ServeLease`; `lease_dir.mkdir`).
- Правило: T-LIFE/v1, C-MULT-I4 (освобождение в `finally`).
- Evidence: `zen-serve-state-*` удаляется только `lease.cleanup()`. При `ServeUnavailable("no free serve port")`, `OSError` от `Popen` (не перехватывается обработчиками) состояние и `lifeline_w` не освобождаются.
- Fix: `try/finally` вокруг всего пути от `_serve_env`, закрытие обоих концов pipe, оборачивание OSError в `ServeUnavailable`.
- Проверка: тест с подменённым `Popen` (OSError): нет `zen-serve-state-*` и FD после 50 итераций.

F-10 [blocking] Пробелы покрытия AC и неточная матрица
- Locations: tests/test_realtime_reasoning.py (весь модуль); verification-traceability.md (строки REQ-006..009, REQ-013..016).
- Правило: testing.md (регресс на каждое требование), `council` «Полнота/покрытие AC».
- Evidence: нет тестов на AC-011/AC-012, serve `first_event/first_token/stall`, `_serve_json_serve`, AC-018, AC-020; фикстуры `__silent__` и `__never_event__` не используются; все строки матрицы PASS ссылаются на общий VER-001.
- Fix: добавить недостающие тесты и привязать каждую строку матрицы к конкретному тесту.
- Проверка: матрица с именем теста на каждое REQ/AC.

F-11 [blocking] Самописный `_JsonParser` / `_loads_object`, ошибки маскируются
- Locations: server.py:~1560-1700 (`_JsonParser`, `_loads_object`), используется в `_read_dynamic_config_enabled`, `_spawn_serve`, `_serve_http`, `_reader`.
- Правило: python-standards §6/§7 (KISS, DRY), §3 (не маскировать ошибки); `json` остаётся импортированным.
- Evidence: ~150 строк разбора JSON при доступном `json.loads`; парсер возвращает `{}` на ошибку, `RecursionError` не ловится, битый SSE-кадр превращается в `invalid_serve_event`.
- Fix: `json.loads` с явным `except (ValueError, RecursionError)` и логом.
- Проверка: тест битого и глубоко вложенного кадра даёт управляемую ошибку.

F-12 [blocking] Подавления типов без обоснования
- Locations: tests/test_realtime_reasoning.py:2 (`# pyright: reportAny=false, …` на 10 правил); `# type: ignore[attr-defined]` в `test_watchdog_first_event_timeout` и `setUp`/`tearDown` группы B.
- Правило: python-standards, запрет №9.
- Evidence: VER-004 требует нуль диагностик в новом тест-файле, и он достигнут блоковым подавлением, а не типизацией.
- Fix: типизировать, убрать блоковое подавление и ненужные `type: ignore`, оставить точечные с причиной.
- Проверка: VER-004 без подавлений.

F-13 [non-blocking] Тавтологичные и неустойчивые тесты
- Locations: tests/test_realtime_reasoning.py: `test_serve_health_and_fallback_table` (`assertTrue(silence or rows)`), `test_helper_argv_validation_and_lease_dir`, `test_native_tool_and_permission_reject`, `test_slow_serve_gets_status_and_no_status_on_fast`, пороги `≤1.0` и `<2.0`.
- Правило: testing.md («тест должен воспроизводить баг»).
- Evidence: тавтология; тест для «lease_dir» проверяет только rc≠0 при 5 аргументах; в native-тесте не проверяется, что reject отправлен; в «fast» части нет утверждения; RED в 16 тестах из-за `AttributeError`, а не поведения; Coder сам видел 1.04 с против 1.0.
- Fix: реальные утверждения, `FakeClock` или запас по порогам.
- Проверка: тесты красные на мутациях.

F-14 [non-blocking] Lease-каталог в `/tmp` без владельца и режима
- Locations: server.py:~2360-3114 (`LEASE_DIR`, `_spawn_serve`, `_startup_reaper`).
- Правило: `security.md` §9 (predictable path), `error-handling`.
- Evidence: `mkdir(parents=True, exist_ok=True)` с umask по умолчанию, reaper не проверяет `owner_uid` и ориентируется на подстроку `--serve-helper`.
- Fix: каталог 0700 под `~/.dsh/…` или `os.mkdir` с проверкой владельца, проверка `owner_uid` и `parent_start_ts`.
- Проверка: тест reaper на чужой lease.

F-15 [non-blocking] Тестовый хук и вакуумная проверка нативного бинаря
- Locations: server.py:~1560-1700 (`SERVE_TEST_ELIGIBLE`, `_is_native_opencode_bin`: `or len(head) == 4`).
- Evidence: условие истинно для любого файла ≥4 байт без `#!`; тестовый флаг в продакшн-модуле.
- Fix: проверка реального формата Mach-O/ELF, подмена бинаря в тестах через патч.
- Проверка: текстовый файл без shebang не считается нативным.

F-16 [non-blocking] Косметический реформат чужих областей
- Locations: server.py: `_UpstreamBreaker` (~2204), `_RequestAttempts` (~2230-2291), `_PrefixDedup`, `Run.execute/_execute_once` (4427-4530), `Handler._res`, `_log_exit`; test_step_interruption.py:67 (кавычки `FAKE_OPENCODE`).
- Правило: AGENTS.md п.4 (минимальные изменения), scope-diff.
- Evidence: reverse-spec §1 («чисто форматирующие перестановки»).
- Fix: вынести форматирование в отдельный коммит или откатить hunk'и вне поведения.
- Проверка: diff без форматирующих hunk'ов в немодифицированных функциях.

F-17 [non-blocking] Размер функций и дубли
- Locations: `_serve_one_attempt` (~350 строк), `_run_serve_stream_attempts` (~190), `_serve_json_serve` (~210) в server.py (+1900 строк, итог 6287).
- Правило: python-standards §6/§7, SOLID/SRP.
- Evidence: вложенные замыкания; одинаковая логика retry, fallback и native-маппинга в stream и JSON.
- Fix: выделить класс попытки serve и общий retry-цикл.
- Проверка: функции ≤ ~80 строк, одна реализация retry-логики.

F-18 [non-blocking] Изменённый оракул `test_step_interruption.py`
- Locations: tests/test_step_interruption.py: `test_unmapped_retries_do_not_exhaust_incomplete_budget_stream/json` (~413-450).
- Правило: verification-surface (`oracle_change` аудитирует Verifier), REQ-017.
- Evidence: ожидания «4 запуска, tool_calls» заменены на «3 запуска, `[]`, stop», имена тестов «do_not_exhaust» утверждают обратное, записи аудита `oracle_change` в `verifier.json` нет.
- Fix: переименовать тесты, задокументировать изменение контракта потолка, зафиксировать аудит.
- Проверка: запись в `verifier.json`.

F-19 [non-blocking] Жизненный цикл потоков и очереди
- Locations: server.py:~2360-3114 (`_reader` с блокирующим `events.put`, `_prompt_worker` timeout 65 с, `threading.Thread(daemon=True)` без join).
- Правило: T-LIFE/v1, C-MULT-I2.
- Evidence: при заполненной очереди 4096 читатель блокируется навсегда, при раннем выходе потоки не завершаются, пока не закроются сокеты.
- Fix: `put` с таймаутом и сигналом остановки, join или cancel потоков в `finally`.
- Проверка: тест утечки потоков после 50 запросов.

F-20 [non-blocking] [sweep] Watchdog считает только reasoning/text/завершённый tool
- Locations: server.py:~2360-3114 (`_serve_one_attempt`, `last_token_at`, `first_token_at`).
- Evidence: `session.tool.input.delta` и `reasoning.started` не обновляют `last_token_at`; при длинной генерации аргументов инструмента срабатывает `stall_timeout` через 60 с.
- Fix: считать tool-input дельты признаком живости.
- Проверка: фикстура с долгим tool-input без text не даёт ложный stall.

F-21 [blocking] [pre-existing] Прямая мутация `os.environ` в изменённом тестовом файле
- Locations: tests/test_step_interruption.py:~188-192 (`setUp`: `os.environ["FAKE_OC_COUNTER"] = …`, `FAKE_OC_PLAN`).
- Правило: testing.md («запрет мутации `os.environ` без изоляции»); файл изменён задачей, значит blocking по §3 Diff-scope.
- Evidence: записи без `monkeypatch` и гарантированного отката.
- Fix: `mock.patch.dict` или `monkeypatch`.
- Проверка: порядок запуска не влияет на результат (AC-023 reversed).

COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 21


---

## Раунд D1 (`panel/council/r5`)

### Seat 1 (`skeptic`, `grok-4.7-high`)

PANEL-NONCE: c310df07f3342d79
ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4
Канон прочитан: AGENTS.md, 430 строк

AGREE F-019 rev=1 — проверил: server.py:3018 и server.py:3029 — `if text_value.strip():` стоит и вокруг накопления, и вокруг `on_reasoning`/`on_text`; отдельная дельта `" "` или `"\n"` не уходит клиенту (REQ-005, AC-006).
DISPUTE F-020 — класс: duplicate_of:F-008 — контр-evidence: server.py:1675 `parts.append(chr(int(hex_part, 16)))`, server.py:1701 `_loads_object` на ошибке возвращает `{}` — тот же парсер. Фикс только stdlib `json.loads`: §16 `orjson` здесь неприменим, `pyproject.toml` `dependencies = []`, Forbidden Scope запрещает новую runtime-зависимость.
AGREE F-021 rev=1 — проверил: server.py:2889 `deadline = prompt_send_start + TIMEOUT_S`, server.py:3080 `return result` при пустых `terminal` и `exit_reason` — вызывающий на server.py:4914 делает `record_success()` и успешный SSE-финал. Остаток `attempts.deadline` не управляет попыткой (R-BULK-I1).
AGREE F-022 rev=1 — проверил: server.py:2827 `HTTPConnection(..., timeout=5)`, чтение server.py:2848; таймаут `readline` обрывает поток раньше `FIRST_TOKEN_TIMEOUT_S`/`STALL_TIMEOUT_S` = 60 с и классифицируется как EOF/`invalid_serve_event` (REQ-006, REQ-007).
AGREE F-023 rev=1 — проверил: server.py:2403 при переданном `conn` аргумент `timeout` не применяется к сокету; cleanup server.py:3084 и server.py:3094 передаёт `timeout=0.25` в соединение, созданное на 3 с (server.py:2755). Зависший control держит `lease.cleanup()` дольше AC-011.
AGREE F-024 rev=1 — проверил: server.py:2740 `_spawn_serve` до цикла статусов, server.py:2890 `status_next` считается уже после prompt; legacy-статус только внутри `feed.lines` после gate (server.py:5298, `STARTUP_WAIT_S=5`). `STATUS_INITIAL` не эмитируется. REQ-004/AC-005 на время setup не закрыт.
AGREE F-025 rev=1 — проверил: server.py:1096 `on_idle` вызывается только из `queue.Empty`, server.py:1126 любая строка stdout сбрасывает `last_activity`; вызов server.py:5441 `feed.lines(deadline, 0.25, send_keepalive)`. Непрерывный служебный stdout не даёт ни first-token, ни stall, ни `client_gone`.
DISPUTE F-026 — класс: duplicate_of:F-001 — контр-evidence: server.py:4848 и server.py:5768 `attempts.note_spawn()` без `gate.acquire()` и без `spawn_limiter.acquire`; run берёт оба на server.py:4490 и server.py:5297 — тот же обход REQ-013.
AGREE F-027 rev=1 — проверил: `begin_attempt` один раз на server.py:5150; serve на server.py:4848 делает `note_spawn()` до попытки; pre-delivery `return False` на server.py:4866 не идёт в `allow_retry`; цикл run server.py:5291 снова `note_spawn()` на server.py:5318. Две delivered-неудачи serve плюс pre-delivery fallback дают четвёртый запуск (REQ-009, AC-013).
AGREE F-028 rev=1 — проверил: server.py:2169 `allow()` в HALF_OPEN резервирует пробу; server.py:2184 `record_success` закрывает её; успех serve на server.py:4914 и server.py:5818 зовёт только `serve_health.record_success()`, не `attempt_done(False, True)` (server.py:2297). Проба HALF_OPEN не возвращает breaker в CLOSED (REQ-009, R-BULK-I3).
AGREE F-029 rev=1 — проверил: server.py:2879 пишет `prompt_status["status"]` и `headers_at` после полного тела (server.py:2413); дальше читаются только 401/403. 400/404/422/429/5xx prompt не получают строки `FALLBACK_DECISION_TABLE`.
AGREE F-030 rev=1 — проверил: server.py:3073 любой `etype == "error"` ставит `terminal="failed"` и выходит; server.py:4909 и server.py:5813 сразу шлют ошибку клиенту. В `_incomplete_step_signal` на server.py:4943 передаётся `False`, а не факт транзиентного обрыва (REQ-009, REQ-011).
DISPUTE F-031 — класс: duplicate_of:F-006 — контр-evidence: server.py:4950 и server.py:4961 `tool_choice=None`, вызов server.py:5981 передаёт литерал `None` при живом параметре `_serve_json` — тот же обрыв REQ-011.
AGREE F-032 rev=1 — проверил: server.py:3046–3079 после `tool_event` и `step_finish` цикл не прерывается, выход только на `session.execution.succeeded` или `error`. `step_closed` гасит reasoning/text только для permission/form, не для обычного tool call. Второй шаг доходит до клиента (REQ-011).
AMEND F-033 — priority=blocking; locations=server.py:4843, server.py:4901, server.py:4925, server.py:4952, server.py:5850, server.py:5908; fix=Дедуплицировать только text (как `_PrefixDedup` на server.py:2318) и tool_calls (как server.py:5208). Уже отданный reasoning не вычитать и не склеивать. Между попытками оставить ровно одну строку `[мост] Повтор попытки`, она уже эмитируется. — причина: AC-014 «размышление не дедуплицируется».
AMEND F-034 — priority=non-blocking; locations=server.py:4886, server.py:4915, server.py:5795, server.py:5874; fix=Перед `continue` на timeout/invalid прибавлять уже полученный `result["usage"]` к аккумулятору попыток. — причина: REQ-014 в конверте помечен SHOULD; дефект реален, merge сам по себе не блокирует.
AGREE F-035 rev=1 — проверил: server.py:2550, server.py:2562, server.py:2568 бросают `ServeUnavailable` вне `except (OSError, ValueError, subprocess.SubprocessError)` на server.py:2572, поэтому `lease.cleanup()` пропускается. `_spawn_serve` на server.py:2740 стоит до `try/finally` попытки. `mkdtemp` на server.py:1768 и write-конец lifeline при отказе `Popen` не закрываются. Совпадает с `ResourceWarning: subprocess 98704 is still running` в VER-002 (REQ-008).
AGREE F-036 rev=1 — проверил: server.py:2842 очередь `maxsize=4096`, server.py:2859 `events.put` без timeout; reader не присоединяется в `finally` server.py:3107. Поток, ждущий место в очереди, не отпускается закрытием сокета serve.
AGREE F-037 rev=1 — проверил: server.py:2570 `_drain_stderr(helper, [])` складывает каждую строку stderr в список, который никто не читает и не ограничивает. Это не комментарий F-015, а рост RSS на всю попытку.
AGREE F-038 rev=1 — проверил: server.py:2564 `if listener_pid is not None and ...` пропускает проверку, когда `lsof` ничего не вернул; пароль уходит на server.py:2778. Параллельный bind с server.py:2495 (пробный сокет закрыт до bind serve) попадает в тот же класс: Authorization без доказанного своего слушателя.
DISPUTE F-039 — класс: duplicate_of:F-003 — контр-evidence: server.py:72 пишет `parent_start_ts`, server.py:2593 `parent_alive = parent_pid > 0 and _pid_alive`, при живом pid `continue`, затем один SIGTERM и `unlink`. Сверка UID/lstart — тот же дефект reaper, её надо влить в фикс F-003, не считать вторым блокером.
AGREE F-040 rev=1 — проверил: server.py:174 `finally` helper делает `serve_proc.terminate()` и удаляет lease, без `killpg` своей группы. Потомок, переживший serve, теряет и сигнал, и след для reaper. Путь смерти моста через EOF lifeline этот пробел не закрывает (REQ-008).
AGREE F-041 rev=1 — проверил: server.py:4750 `except (OSError, ValueError): return False` — RST выглядит как «клиент на месте». JSON-вызов server.py:5769 не передаёт `is_client_gone` (это шире F-004, где нет только callback).
AGREE F-042 rev=1 — проверил: tests/test_realtime_reasoning.py:442 `upstream_end_t = elapsed` — это EOF клиентского ответа; пачка из пяти дельт одним куском проходит `first < elapsed` и span `< 2.0`. tests/test_realtime_reasoning.py:619 `assertTrue(silence or rows)` истинно на любой непустой таблице.
AGREE F-043 rev=1 — проверил: tests/test_realtime_reasoning.py:2 блоковый `# pyright: reportAny=false, ...` на десяток правил и `# type: ignore` без причины. Запрет №9 python-standards. Ноль диагностик VER-004 на новом файле получен подавлением, не типами.
AGREE F-044 rev=1 — проверил: tests/test_realtime_reasoning.py:299 `self.env.stop()` восстанавливает исходный `FAKE_RT_MODE`, следующая строка безусловно `os.environ.pop("FAKE_RT_MODE")`. Предустановленное значение теста стирается (testing.md, откат окружения).
DISPUTE F-045 — класс: out_of_scope — контр-evidence: testing.md «Не использовать unittest.TestCase» написан для async-стека Litestar; этот мост — sync `ThreadingHTTPServer`, весь существующий набор (`tests/test_step_interruption.py`, класс `TestStepInterruptionLive`) уже на `unittest.TestCase`, pytest только раннер (`pyproject.toml` `testpaths`). Переписывание одного нового файла фреймворк не чинит и конвертом не требовалось.
AMEND F-046 — priority=blocking; locations=tests/test_realtime_reasoning.py:321, tests/test_realtime_reasoning.py:392, tests/test_realtime_reasoning.py:444, tests/test_realtime_reasoning.py:568; fix=Оставить замер реального клиентского сокета: его требуют AC-005 и AC-026. Пометить эти тесты `measured` и гонять Serial Lane; порог 1.0 с дать с запасом (уже был срыв 1.040 с). FakeClock добавить только на переходы watchdog, не вместо сокета. — причина: testing.md §7.2 запрещает wall-clock в обычном наборе, REQ-020 запрещает убрать сокетный оракул.
DISPUTE F-047 — класс: out_of_scope — контр-evidence: `allowed_envelope_changes` — ровно три файла кодера; README/CHANGELOG в пакет не входят. python-standards §12 про README Litestar-сервиса. Расширение scope на документацию — отдельное согласование, не блокер внутри замороженного набора. Сам текст находки говорит «согласовать расширение».
AGREE F-048 rev=1 — проверил: server.py:1844 mapper возвращает `{"reasoning_content": delta}` без `sessionID`; фильтр server.py:2973 пропускает `event_session is None`. Чужая дельта reasoning/text/error той же формы проходит в текущую сессию.
DISPUTE F-049 — класс: duplicate_of:F-011 — контр-evidence: server.py:1791 `or len(head) == 4` после Mach-O/ELF. Любой файл без `#!` длиной от 4 байт считается нативным. Тот же предохранитель.
AGREE F-050 rev=1 — проверил: server.py:4877 и server.py:4884 перезаписывают `xs["first_event_ms"]`/`ttft_ms` каждой попыткой; legacy то же на server.py:5456. Это не F-016: там тайминг serve остаётся после смены `transport=run`, здесь стирается первое значение запроса (REQ-016).
DISPUTE F-051 — класс: duplicate_of:F-019 — контр-evidence: server.py:3018 и server.py:3029 тот же `text_value.strip()` на reasoning и text.
DISPUTE F-052 — класс: duplicate_of:F-038 — контр-evidence: server.py:2495 скан порта с закрытием пробного сокета и server.py:2564 пропуск при `listener_pid is None`. Параллельный одинаковый порт и пароль чужому слушателю — тот же ownership, фикс один: доказанный listener до первой записи Authorization.
AMEND F-053 — priority=blocking; locations=server.py:5351, server.py:5465, константа `FIRST_TOKEN_TIMEOUT_S`; fix=Watchdog на run оставить (REQ-007 MUST). Дефолт first-token для legacy поднять выше наблюдаемого здорового максимума 85.65 с с запасом и оставить env-переопределение. `step_start` уже ставит `first_event_at`, если `etype` непустой; ломает запрос именно порог первого токена, потому что `opencode run` отдаёт reasoning и text одним блоком в конце шага. — причина: F-17, F-18, F-32; снятие сторожа нарушает REQ-007.
DISPUTE F-054 — класс: duplicate_of:F-001 — контр-evidence: server.py:4848 и server.py:5768 без `_StartupGate` и `spawn_limiter`, те же строки, что F-001.
DISPUTE F-055 — класс: duplicate_of:F-029 — контр-evidence: server.py:2879 статус prompt почти не читается; строка таблицы про 429 не исполняется. Узкий случай «429 увеличивает serve_health» уже в F-009.
DISPUTE F-056 — класс: duplicate_of:F-033 — контр-evidence: server.py:4843 парсер создаётся заново, `_PrefixDedup` на serve нет. Фикс — только text и tool_calls, не reasoning (см. AMEND F-033, AC-014).
DISPUTE F-057 — класс: duplicate_of:F-024 — контр-evidence: server.py:2740 и server.py:2890 статус обслуживается после spawn/ready/subscribe; gate до `feed.lines` молчит. Тот же REQ-004.
AGREE F-058 rev=1 — проверил: `_map_serve_event` на пустом `data` (кроме `server.connected`) бросает `ServeProtocolError`; обработчик server.py:2969 ставит `delivered=True` и выходит. Heartbeat или `integration.updated` с пустым `data` (F-19, 161 мс) ретраит попытку. Живое тело события не в пакете (VER-006 отложен), ветка кода безусловная.
DISPUTE F-059 — класс: duplicate_of:F-035 — контр-evidence: server.py:1768 `mkdtemp`, server.py:2572 `ServeUnavailable` мимо `lease.cleanup()`. Та же утечка state-dir и FD на отказе запуска.
AGREE F-060 rev=1 — проверил: tests/test_realtime_reasoning.py:99 и :102 маркеры `__never_event__`/`__silent__` ни одним тестом не вызываются; JSON-serve, обрыв клиента, ротация прокси и отсутствие пароля в логе отдельных оракулов не имеют. `verification-traceability.md` ставит этим REQ `PASS` со ссылкой на общий VER-001.
DISPUTE F-061 — класс: duplicate_of:F-008 — контр-evidence: server.py:1560 `_JsonParser` и server.py:1675 суррогаты. Замена на `json.loads`, не на `orjson` (0 внешних зависимостей).
DISPUTE F-062 — класс: duplicate_of:F-043 — контр-evidence: tests/test_realtime_reasoning.py:2 тот же блоковый `# pyright:` и `type: ignore` без причины.
AGREE F-063 rev=1 — проверил: tests/test_realtime_reasoning.py:619 `assertTrue(silence or rows)`; тест helper проверяет только `returncode != 0`; native-тест не утверждает, что reject ушёл на сервер. Тавтологии, не второй корень. priority остаётся non-blocking.
AGREE F-064 rev=1 — проверил: `LEASE_DIR = Path("/tmp/opencode-zen-bridge-leases")`, `mkdir` без режима 0700; reaper не сверяет `owner_uid`. На однопользовательской машине это слабее удалённой атаки, предсказуемый путь реален. priority non-blocking, как подано.
DISPUTE F-065 — класс: duplicate_of:F-011 — контр-evidence: server.py:1791 `or len(head) == 4`. `SERVE_TEST_ELIGIBLE` по умолчанию `False` и не является env kill-switch; отдельного прод-дефекта сверх F-011 нет.
AGREE F-066 rev=1 — проверил: форматирующие hunk в `Run`/`_RequestAttempts`/`_PrefixDedup` и кавычки `FAKE_OPENCODE` в tests/test_step_interruption.py:67 не меняют поведение. Файлы внутри конверта из трёх путей. priority non-blocking, scope-diff blocking из этого не следует.
AGREE F-067 rev=1 — проверил: `_serve_one_attempt` и два почти одинаковых цикла retry stream/JSON. Это долг читаемости, не доказанная нужда переписывать функцию ради merge. priority non-blocking.
AMEND F-068 — priority=non-blocking; locations=tests/test_step_interruption.py:413, tests/test_step_interruption.py:423; fix=Переименовать тесты `do_not_exhaust`, чтобы имя совпало с потолком 3. Ожидание «3 запуска, finish stop» не откатывать. — причина: REQ-017 и F-47: старое ожидание 4 запусков само нарушало `MAX_TOTAL_SPAWNS=3`. Это выравнивание оракула, не подгонка.
DISPUTE F-069 — класс: duplicate_of:F-036 — контр-evidence: server.py:2859 блокирующий `events.put` и daemon-поток без join в `finally`. Тот же жизненный цикл очереди.
AGREE F-070 rev=1 — проверил: server.py:3038 `tool_event` ставит `first_token_at` только когда `complete()` что-то вернул, и не обновляет `last_token_at`. Длинный `session.tool.input.delta` может дать ложный `stall_timeout`. priority non-blocking: типичный ввод инструмента короче 60 с, фикс — считать эти дельты живостью.
AGREE F-071 rev=1 — проверил: tests/test_step_interruption.py setUp пишет `os.environ["FAKE_OC_COUNTER"]` и `FAKE_OC_PLAN` без отката. Строка, добавленная задачей, — server.py-изоляция `_Resilience()` на :188; мутация окружения в том же `setUp` была раньше. Файл в скоупе задачи, testing.md запрещает мутацию без отката, значит blocking с меткой pre-existing. AC-023 это не отменяет.

CONFLICT F-053↔снятие legacy-watchdog — REQ-007 MUST требует сторожа на обоих транспортах; выключение его на run ломает MUST. Совместимый фикс — порог first-token для run выше 85.65 с, не удаление ветки.
CONFLICT F-033↔дедуп reasoning — AC-014 запрещает дедупликацию reasoning и требует ровно одну статусную строку между попытками. Дедуп text/tool_calls с дедупом reasoning взаимоисключающи.

F-001..F-018 не снимаю: RECHECK подтвердил строки, аргументы коллег их не опровергли.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Serve теряет пробельные дельты, не держит общий дедлайн, после fallback может сделать четвёртый запуск, не закрывает HALF_OPEN, не останавливает шаг с tool call и пропускает чужую сессию. Порог 60 с на буферизующем `run` убивает здоровый шаг длиннее наблюдения 85.65 с.
   СОВЕТЫ: F-019 пересылать непустые дельты без `strip`. F-021 вести попытку по `attempts.deadline` и не считать пустой `exit_reason` успехом. F-027 единый допуск каждой попытки, включая смену транспорта, потолок 3. F-028 на успехе serve звать `attempt_done(False, True)`. F-030 разделить транзиентную и фатальную ошибку, как на run. F-032 завершать попытку на границе шага с tool call. F-033 дедуп только text и tool_calls. F-048 фильтровать `sessionID` исходного события до маппера. F-053 поднять legacy first-token выше 85.65 с, сторож не снимать. Плюс открытые F-001, F-006, F-009.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=Первый `[мост]` не обслуживается, пока идут gate и spawn. Watchdog legacy живёт только в idle-callback. Оракул AC-026 сравнивает чанк с EOF собственного ответа. Матрица PASS ссылается на общий VER-001 там, где теста нет.
   СОВЕТЫ: F-024 эмитить статус с открытия SSE, включая ожидание gate. F-025 звать надзор по монотонным часам и при приходе строк, не только в простое. F-042 независимая метка конца апстрима и соседний интервал, не span < 2 с. F-050 хранить первые request-level `first_event_ms`/`ttft_ms`. F-058 неизвестное событие с пустым `data` игнорировать, не ретраить. F-060 отдельные тесты на три serve-watchdog, JSON, обрыв клиента, ротацию прокси и отсутствие пароля в логе. Плюс F-004, F-005, F-007.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Отказ запуска и cleanup control-сокета оставляют процессы и каталоги. Очередь SSE и список stderr не ограничены по ожиданию и памяти. Смерть моста не гарантирует смерть внука serve.
   СОВЕТЫ: F-023 выставлять timeout на уже открытый сокет и убивать группу независимо от HTTP-cleanup. F-035 `cleanup` на каждом исходе с момента `mkdtemp` и `pipe`, включая `ServeUnavailable`. F-036 `put` с таймаутом и join читателя. F-037 ограниченный хвост stderr, не безлимитный список. F-040 `killpg` своей группы на EOF lifeline, lease не удалять, пока группа жива. Плюс F-001 и F-010.
4. РИСКИ: VERDICT=FAIL
   WHY=Пароль может уйти на недоказанный слушатель. Пять секунд тишины SSE обрывают попытку, которой контракт даёт 60 с. RST клиента не виден. Подавления типов и порча чужого `FAKE_RT_MODE` — прямые нарушения стандартов в новом коде. Зелёный L2 принимаю как факт и не отменяю им эти дефекты: L2-RED rc=1 на origin/dev, VER-005 21 passed, VER-001 400 passed, AC-023 rc=0. VER-006 и VER-007 остаются DEFERRED_L3, это не находка.
   СОВЕТЫ: F-022 читать SSE дольше порога watchdog и не превращать промежуточную тишину в EOF. F-038 требовать совпадение listener pid и pgid до первой строки Authorization; нет pid — `ServeUnavailable`. F-041 отличать FIN/RST от «данных нет» и в JSON тоже. F-043 убрать блоковый pyright и необоснованные `type: ignore`. F-044 не делать `pop` после восстановления env. F-046 вынести сокетные пороги в Serial Lane с запасом. F-071 откатить `os.environ` в `test_step_interruption.py` через `patch.dict`. Плюс F-008 (`json.loads`) и F-010.
5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL
   WHY=Короткий serve с откатом на run до доставки оправдан (F-17..F-19, прецедент muse-bridge). Неоправдан свой JSON-парсер при уже импортированном `json` и таблица fallback, которую код не исполняет. Длина функций (F-067) сама по себе блокер не даёт.
   СОВЕТЫ: F-008 удалить `_JsonParser`, разбирать объекты через `json.loads` с явной ошибкой. F-029 либо исполнять строки таблицы (429 → breaker, не serve_health), либо удалить константу и утверждать в тесте конкретные инкременты. `orjson` не добавлять.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Граница трёх файлов, заморозка `_run_env` и Google, ноль новых зависимостей — держатся. Критерий ломают нарушения внутри этой дельты: подавление диагностик, мутация окружения, wall-clock в обычном наборе. Запрет TestCase и отсутствие README (F-045, F-047) в основание FAIL не кладу: они вне применимого стека и вне разрешённых файлов. Слой Litestar к этому мосту не переносится.
   СОВЕТЫ: закрыть F-043, F-044, F-046 и F-071. Документацию переключателей не тащить в этот diff, пока конверт файлов не расширен.

POSITIONS: 53/53
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `gpt-6.1-sol-high`)

PANEL-NONCE: 2ca86821366dd5ff
ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4

Канон `~/Мой диск/Context/AGENTS.md` прочитан целиком в приложенном тексте до `<!-- КАНОН-КОНЕЦ -->`; проектные файлы правил с диска в этом ходе ещё не читались. Пересмотрю позиции D1 по коду и свидетельствам пакета. Тесты не запускаю.
Сверка уточнила два вывода R1: потоковый ответ уже дедуплицирует одинаковые tool calls, поэтому замечание о дублях сужаю до текста и JSON-ветки; сам по себе `wait(timeout=0.5)` не доказывает утечку — блокер в отсутствии проверки завершения всей группы. Предложение убрать 60-секундный watchdog legacy отклоняю: этот порог прямо предусмотрен REQ-007.
PANEL-NONCE: 2ca86821366dd5ff
ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4

Канон `~/Мой диск/Context/AGENTS.md` прочитан целиком в приложенном тексте до `<!-- КАНОН-КОНЕЦ -->`. В рабочей папке `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` отсутствуют. Ниже `server.py` и тестовые пути относятся к `bridges/opencode-zen-bridge/`. Тесты самостоятельно не запускал.

DISPUTE F-001 — класс: duplicate_of:F-026 — контр-evidence: `server.py:4848`, `5768` — тот же обход `_StartupGate` и `spawn_limiter` уже полностью описан в F-026; блокирующий дефект подтверждается.

AGREE F-002 rev=1 — проверил: `server.py:2552` — после первоначального `select` цикл побайтового чтения до LF не проверяет остаток дедлайна. Нужны ограничение времени всего рукопожатия и cleanup при его истечении.

AMEND F-003 — priority=blocking; locations=server.py:2609,server.py:2613; fix=После SIGTERM проверять завершение принадлежащей попытке группы в ограниченном бюджете, при необходимости эскалировать до SIGKILL; сохранять lease до подтверждения завершения — причина: `server.py:2609`, `2613` содержат одиночный сигнал с последующим удалением lease. Проверку идентичности процессов учитывать отдельно в F-039, без дублирования.

DISPUTE F-004 — класс: duplicate_of:F-041 — контр-evidence: `server.py:5770` — отсутствие callback отключения клиента в JSON-попытке уже входит в F-041.

DISPUTE F-005 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_realtime_reasoning.py:99`, `102`, `376` — отсутствие serve-оракулов трёх watchdog уже включено в блокирующую неполноту F-042; наличие зелёного legacy-теста этого не исправляет.

DISPUTE F-006 — класс: duplicate_of:F-031 — контр-evidence: `server.py:4950`, `4961`, `5981` — потеря исходного `tool_choice` уже описана в F-031.

DISPUTE F-007 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_step_interruption.py:159`, `167`, `188` — существующий набор использует run-фейк; необходимость эквивалентной serve-матрицы прерываний уже входит в F-042.

DISPUTE F-008 — класс: duplicate_of:F-020 — контр-evidence: `server.py:1679`, `1705`, `2857` — тот же собственный JSON-парсер и повреждение surrogate pairs уже описаны в F-020.

DISPUTE F-009 — класс: duplicate_of:F-029 — контр-evidence: `server.py:2879`, `2880`, `2901` — неиспользуемая классификация prompt-response и неверный барьер доставки уже входят в F-029.

AMEND F-010 — priority=blocking; locations=server.py:2457,server.py:2464,server.py:2471; fix=Подтверждать завершение всей собственной группы, включая потомков после выхода helper; ограничить ожидание общим cleanup-бюджетом и сохранять диагностическое свидетельство при неуспехе — причина: `helper.wait()` проверяет только непосредственный helper; успешный выход helper не доказывает смерть оставшихся потомков. Значение `0.5` само по себе не доказывает утечку, а ResourceWarning из L2 нельзя однозначно приписать именно этой ветке вместо F-035. Неограниченное ожидание также недопустимо по feature.md и AC-011.

DISPUTE F-011 — класс: duplicate_of:F-049 — контр-evidence: `server.py:1791` — разрешающий дизъюнкт `len(head) == 4` уже описан в F-049.

AMEND F-012 — priority=non-blocking; locations=server.py:1339; fix=Удалить неиспользуемую константу либо задействовать её в механизме раннего статуса, сохраняющем проверку быстрого ответа — причина: отсутствие чтения `STATUS_INITIAL` является мёртвым кодом, но конкретный текст первой строки требованиями не предписан. Нарушение срока первой реакции во время setup учитывать в F-024.

DISPUTE F-013 — класс: duplicate_of:F-038 — контр-evidence: `server.py:2495`, `2564`, `2565` — окно освобождённого порта и разрешение продолжить при недоказанном listener PID уже входят в F-038. Держать probe-сокет открытым без механизма передачи сокета нельзя: это помешает bind самого serve.

DISPUTE F-014 — класс: invalid — контр-evidence: `server.py:2654`, `2655`, `2666`, `2678`; `tests/test_realtime_reasoning.py:114` — `feed()` сохраняет полный `input.ended.text`, а поле `delta` вообще не записывает в `text`. Утверждение о перезаписи текста каждой дельтой не соответствует реализации. Канонический `status="error"` используется для передачи заблокированного native-вызова клиенту; представленная фикстура именно такая. Необходимость поддержать иной wire-вариант требует отдельного подтверждённого контракта.

AMEND F-015 — priority=non-blocking; locations=server.py:2569,server.py:2570; fix=Исправить комментарий о записи stderr в лог; проверку отсутствия пароля в итоговом sink включить в F-042 — причина: `_drain_stderr` на `server.py:1028`–`1037` добавляет строки в список и не вызывает логирование. Утечка пароля этим путём не доказана. Добавлять логирование ради исправления комментария не требуется; неограниченное накопление списка отдельно покрыто F-037.

DISPUTE F-016 — класс: duplicate_of:F-050 — контр-evidence: `server.py:4877`, `4884`, `5456`, `5468` — семантика request-level «первых» таймингов уже описана в F-050. Простое обнуление при fallback не является достаточным исправлением: оно уничтожит действительно первое наблюдение запроса.

DISPUTE F-017 — класс: duplicate_of:F-042 — контр-evidence: `server.py:1795`; `tests/test_realtime_reasoning.py:634` — отсутствие поведенческой матрицы переключателей входит в F-042; проверка читателя JSON-флага не заменяет проверку выбора транспорта.

DISPUTE F-018 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_realtime_reasoning.py:442`, `443`, `445` — слабость временного оракула и отсутствие независимого upstream-end уже описаны в F-042. Выдача нескольких накопленных дельт в конце также может удовлетворить приведённым assertions.

DISPUTE F-051 — класс: duplicate_of:F-019 — контр-evidence: `server.py:3018`, `3029` — тот же подтверждённый дефект отбрасывания пробельных reasoning/text-дельт.

DISPUTE F-052 — класс: duplicate_of:F-038 — контр-evidence: `server.py:2495`, `2505`, `2565` — гонка выбора порта и отсутствие обязательного ownership-proof уже покрыты F-038. Предложение переводить любой readiness-401 в fallback не принимаю: оно ослабляет требуемый fail-closed; сначала нужно доказать владение слушателем.

DISPUTE F-053 — класс: invalid — контр-evidence: `handoff-architect.md`, REQ-007 и AC-010 прямо требуют настраиваемый watchdog первого токена с рабочим допущением 60 секунд. Его наличие на legacy-пути соответствует задаче. F-32 сообщает длительность всего запроса, но не доказывает непрерывное отсутствие первого токена более 60 секунд. Удалять watchdog или менять согласованный порог на этом основании нельзя.

DISPUTE F-054 — класс: duplicate_of:F-026 — контр-evidence: `server.py:4848`, `5768` — обход стартовых защит уже покрыт F-026. Отдельное доказательство ротации прокси включено в F-042.

DISPUTE F-055 — класс: duplicate_of:F-029 — контр-evidence: `server.py:2879`, `2880`, `2965` — игнорирование результата prompt-worker уже входит в F-029.

DISPUTE F-056 — класс: duplicate_of:F-033 — контр-evidence: `server.py:4843`, `4901`, `5850`, `5908` — дубли текста и отсутствие разделителей уже покрыты F-033. Уточнение: потоковые одинаковые tool calls дедуплицируются внешним `emit_tool_call` на `server.py:5208`–`5213`; утверждение об их безусловном повторном выводе в stream неверно.

DISPUTE F-057 — класс: duplicate_of:F-024 — контр-evidence: `server.py:2740`, `2890`, `5298`, `5363` — отсутствие своевременной видимой реакции во время setup и ожиданий уже описано в F-024. Исправление должно также сохранить разрешённый сценарий быстрого ответа без лишней синтетики.

INCONCLUSIVE F-058 — нужны реальные wire-фикстуры `integration.updated` и heartbeat с подтверждённой формой `data`. На `server.py:1830` пустой словарь действительно отвергается для всех типов, кроме `server.connected`, но F-19 подтверждает имя и время события, а не пустое `data`. Утверждение о фактическом отказе реального v2.1.2 пока не доказано; законный `DEFERRED_L3` сам по себе не является FAIL.

DISPUTE F-059 — класс: duplicate_of:F-035 — контр-evidence: `server.py:1768`, `2510`, `2572`, `2740` — утечки state-dir/lifeline и пропуск cleanup на отказах запуска уже полностью входят в F-035.

DISPUTE F-060 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_realtime_reasoning.py:376`, `434`, `619`; `verification-traceability.md`, строки REQ-006–016 — та же неполнота оракулов и необоснованная детализация PASS.

DISPUTE F-061 — класс: duplicate_of:F-020 — контр-evidence: `server.py:1560`, `1679`, `1705` — самодельный JSON-парсер и его ошибки уже покрыты F-020.

DISPUTE F-062 — класс: duplicate_of:F-043 — контр-evidence: `tests/test_realtime_reasoning.py:2`, `384`, `408` — blanket-подавления диагностик и необъяснённые ignores уже входят в F-043.

DISPUTE F-063 — класс: duplicate_of:F-042 — контр-evidence: `tests/test_realtime_reasoning.py:619`, `573`, `535`, `561` — несоответствие заявленного покрытия фактическим assertions уже входит в F-042. Нестабильность немаркированных измерений отдельно покрыта F-046. Сам факт поведенческого RED для AC-026 признаётся: в приложенном RED-логе получена одна поздняя дельта вместо требуемых нескольких.

DISPUTE F-064 — класс: duplicate_of:F-039 — контр-evidence: `server.py:2489`, `2593`, `2606` — безопасное владение lease-каталогом и проверка доверия к lease уже входят в исправление F-039. Это существенная часть безопасности сигналов, а не только косметический выбор места хранения.

DISPUTE F-065 — класс: duplicate_of:F-049 — контр-evidence: `server.py:1777`, `1779`, `1791` — несостоятельная проверка формата бинарника уже покрыта F-049. Сам по себе внутренний тестовый флаг без внешнего управления не доказывает отдельного эксплуатационного дефекта.

AMEND F-066 — priority=non-blocking; locations=server.py:2204,server.py:2231,server.py:2338,server.py:4427,server.py:4696,tests/test_step_interruption.py:67; fix=По возможности сократить чисто форматирующие hunks без затрагивания замороженных срезов и без изменения поведения — причина: AGENTS.md требует минимальных изменений, но перечисленные hunks находятся внутри разрешённых файлов. Доказательства выхода в чужую задачу или изменения внешнего контракта нет; FAIL по scope-diff из этого не следует.

AMEND F-067 — priority=non-blocking; locations=server.py:2708,server.py:4753,server.py:5736; fix=После устранения поведенческих дефектов выделить общие переходы retry/fallback там, где их семантика действительно совпадает; сохранить отдельное оформление stream и JSON — причина: python-standards.md §6–7 поддерживает упрощение, но произвольный предел «≤80 строк» не является согласованным критерием. На цикле доработки размер функции без самостоятельного дефекта не обосновывает FAIL.

AMEND F-068 — priority=non-blocking; locations=tests/test_step_interruption.py:413,tests/test_step_interruption.py:422,tests/test_step_interruption.py:451; fix=Уточнить названия тестов и явно связать новые ожидания с REQ-017 и неизменным потолком трёх запусков в аудите оракулов — причина: REQ-017 прямо разрешает устранить дрейф ожидания четырёх запусков; добавленный сценарий подтверждает успешную цепочку в пределах трёх. Требовать изменения runtime-контракта или выдуманного обязательного поля `oracle_change` в receipt нельзя.

DISPUTE F-069 — класс: duplicate_of:F-036 — контр-evidence: `server.py:2859`, `2863`, `2865` — блокировка reader на заполненной очереди и отсутствие гарантированного завершения читателя уже покрыты F-036. Глобальное требование ограниченного завершения вспомогательных потоков сохраняется.

DISPUTE F-070 — класс: invalid — контр-evidence: REQ-007 определяет первый токен как reasoning или text; `server.py:3016`, `3027`, `3040` различает эти события и native lifecycle. Наличие долгой генерации tool-input в фактах не доказано. Автоматически отменять установленный watchdog на любом tool-событии нельзя: это может замаскировать отсутствие требуемого прогресса.

AMEND F-071 — priority=blocking; locations=tests/test_step_interruption.py:191,tests/test_step_interruption.py:192,tests/test_step_interruption.py:193,tests/test_step_interruption.py:194,tests/test_step_interruption.py:195,tests/test_step_interruption.py:196,tests/test_step_interruption.py:198,tests/test_step_interruption.py:201; fix=Сохранять и восстанавливать исходные значения всех изменяемых FAKE_OC-переменных из teardown и тестовых сценариев через изолированную fixture или эквивалентный гарантированный откат — причина: teardown существует, поэтому формулировка «отката нет» неточна. Однако безусловный `pop` удаляет исходные значения вместо восстановления. Обратный порядок зелёных тестов не проверяет запуск с заранее заданным окружением. Дефект [pre-existing] находится в изменённом задачей файле.

AMEND F-033 — priority=blocking; locations=server.py:4843,server.py:4901,server.py:4925,server.py:4952,server.py:5850,server.py:5908; fix=Сохранить прежнюю дедупликацию текстового префикса при recovery, разделять reasoning между попытками и проверять накопление JSON tool calls; сохранить существующую потоковую дедупликацию вызовов — NEW: `server.py:5208`–`5213`, прочитано в этом ходе: внешний `emit_tool_call` уже подавляет одинаковые вызовы. Собственная проверка: serve не устанавливает `_PrefixDedup` перед повтором, а JSON накапливает результаты incomplete/unmapped-попыток. Сужаю прежнюю формулировку: безусловное дублирование одинаковых tool calls в stream не утверждаю; JSON-ветки timeout выходят до добавления текущего текста в `contents`.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL  
   WHY=Подтверждены потеря пробельных дельт, повреждение Unicode, несоблюдение общего дедлайна, неверная обработка prompt-response, потеря `tool_choice` и recovery-совместимости. Начальный `begin_attempt` не устраняет обход допуска при последующем fallback.  
   СОВЕТЫ (при FAIL): устранить F-019–F-025, F-027–F-034, F-048; сохранить существующую дедупликацию потоковых tool calls; проверить stream и JSON на одинаковых последовательностях событий.

2. ПОЛНОТА: VERDICT=FAIL  
   WHY=Зелёный L2 подтверждает исполненный набор, но не все утверждения матрицы AC. Не доказаны задержки 500/250 мс независимыми измерениями, serve-watchdog, JSON, отключение клиента, ротация, полный cleanup и эквивалентная матрица прерываний.  
   СОВЕТЫ (при FAIL): закрыть F-042 конкретными поведенческими оракулами; исправить traceability; включить проверку точного восстановления окружения из F-044 и F-071. `VER-006` и `VER-007` сохранить как законный `DEFERRED_L3`.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL  
   WHY=Выбранный транспорт внедряем: CLI и маршрутизатор доступны, внешних Python-зависимостей не добавлено, предварительный бюджет памяти сходится. Выкат блокируют обход общего темпа запусков, недостаточная защита владения ресурсами и незавершённые сценарии cleanup.  
   СОВЕТЫ (при FAIL): устранить F-026, F-035–F-041 и уточнённые F-003/F-010; затем проверить H0–H9 на рабочем размере и шести параллельных запросах. Плановая оценка — 3–5 рабочих дней одного разработчика плюс независимая верификация; доступность квоты и результат L3 определяют окончательный срок.

4. РИСКИ: VERDICT=FAIL  
   WHY=Сохраняются риски повреждения данных, отправки авторизации неподтверждённому слушателю, сигналов процессам с переиспользованными PID, зависания reader и нарушения Circuit Breaker. Утечка пароля через `_drain_stderr(helper, [])` не доказана. Полные зелёные прогоны и RED→GREEN признаются.  
   СОВЕТЫ (при FAIL): устранить F-020–F-023, F-028–F-030, F-035–F-041, F-048 и F-050; проверить финальные sinks и отсутствие оставшихся процессов, потоков и FD. Не использовать один ResourceWarning как доказательство конкретной причины.

5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL  
   WHY=Короткоживущий serve с резервным run оправдан требованиями реалтайма и ротации. Неоправданное раздувание — собственный JSON-парсер при доступном stdlib-декодере; он уже создаёт конкретный дефект Unicode.  
   СОВЕТЫ (при FAIL): выполнить F-020 с типизированной проверкой результата стандартного декодера; привести исполняемую классификацию к F-029. Декомпозицию и сокращение форматирующего шума из F-066/F-067 считать неблокирующим улучшением.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL  
   WHY=Разрешённый файловый периметр, замороженные Google Direct/`_run_env` и отсутствие сторонних runtime-зависимостей соблюдены. Нарушены применимые требования дедлайнов, жизненного цикла, стартовых защит, изоляции тестов и объяснения подавлений диагностик. Требования Litestar/async к этому stdlib-мосту механически не переношу.  
   СОВЕТЫ (при FAIL): закрыть F-021, F-023, F-026, F-035–F-046, F-071; разрешить конфликт документационного scope для F-047. Не отменять предусмотренный REQ-007 watchdog и не требовать изменения уже согласованного потолка запусков.

POSITIONS: 39/39
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `claude-sonnet-5-5-high`)

PANEL-NONCE: f2590035b5dc07f7
ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4

Позиции Визионера, D1. Размер дефектов оцениваю по долгосрочной ценности транспорта. Блокирующими оставляю то, что ломает доставку, конкурентность или безопасность запуска. Остальное перевожу в non-blocking.

AGREE F-001 rev=1 — проверил: server.py:4848, `_run_serve_stream_attempts` вызывает `attempts.note_spawn()` и сразу `_serve_one_attempt`, без `_StartupGate` и `spawn_limiter`. В run-пути они на :4490 и :5297. Дубль F-026 и F-054.
AMEND F-002 — priority=non-blocking; locations=server.py:2552; fix=читать рукопожатие с остатком 3 с, при истечении `ServeUnavailable` и `cleanup` — причина: helper пишет `json.dumps(...)+"\n"` одним `write` и `flush` (server.py:~140), поэтому частичная строка с зависанием практически недостижима. Дефект теоретический, а не операционный.
AMEND F-003 — priority=non-blocking; locations=server.py:2593,2609,2613; fix=сверять `parent_start_ts` и `helper_lstart` с живым `ps lstart`, ждать смерти группы до удаления lease — причина: SIGTERM шлётся только если `ps -o command=` содержит `--serve-helper` и `pgid==helper_pid` (server.py:~2606). Последствия PID reuse ограничены сиротой или сигналом helper-подобному процессу.
AGREE F-004 rev=1 — проверил: `_serve_json_serve` вызывает `_serve_one_attempt(..., on_status=lambda _t: None, thinking_enabled=...)` без `is_client_gone` (server.py:5770). В stream он передан (:4860). Это REQ-008 для JSON.
AGREE F-005 rev=1 — проверил: маркеры `__never_event__` и `__silent__` есть в `FAKE_SERVE` (test_realtime_reasoning.py:99,102), но ни один тест их не использует. Serve-пороги REQ-006/007 (AC-008..010) не покрыты.
AGREE F-006 rev=1 — проверил: `_serve_json` передаёт в `_serve_json_serve` литерал `None` вместо `tool_choice` (server.py:5981). В stream-helper `tool_choice=None` на :4950 и :4961. Ветку legacy-stream в diff проверить не могу.
AGREE F-007 rev=1 — проверил: test_step_interruption.py:188 только изолирует `_Resilience`. Фейк остаётся shebang-`opencode run`, `OPENCODE_ZEN_BRIDGE_TRANSPORT` не выставляется, AC-016 на serve не исполняется. Закрыть можно fake-delta эквивалентом.
AGREE F-008 rev=1 — проверил: server.py:1675 `parts.append(chr(int(hex_part, 16)))` без склейки суррогатных пар. `_loads_object` на ошибке возвращает `{}` (:1701). `json` импортирован в `else:`-блоке, парсер лишний. Дубль F-020 и F-061.
AGREE F-009 rev=1 — проверил: `_prompt_worker` пишет `prompt_status["status"]` (server.py:2879), классифицируется только 401/403. `FALLBACK_DECISION_TABLE` не исполняется, тест table заканчивается на `assertTrue(silence or rows)` (test:619). Дубль F-029 и F-055.
AMEND F-010 — priority=non-blocking; locations=server.py:2464,2467,2471; fix=поправить `ResourceWarning` через F-035, а в `cleanup` после SIGKILL проверять `_pid_alive(pgid)` — причина: cleanup делает SIGTERM, `wait(0.5)`, `killpg(SIGKILL)`, `wait(0.5)`, это в бюджете AC-011 (≤7 с). Предупреждение `subprocess 98704 is still running` объясняется утечкой в F-035: `raise ServeUnavailable` внутри `_spawn_serve` минует `except (OSError, ValueError, SubprocessError)` и `lease.cleanup()`.
AGREE F-011 rev=1 — проверил: server.py:1791 `or len(head) == 4` разрешает любой файл без `#!` длиной от 4 байт. Non-blocking сохраняю. Дубль F-049 и F-065.
AGREE F-012 rev=1 — проверил: server.py:1339 `STATUS_INITIAL` объявлена и нигде не эмитируется. Поведенческий разрыв REQ-004 закрывается блокирующей F-024.
AMEND F-013 — priority=blocking; locations=server.py:2495,2564; fix=выделять порт под общим замком до проверки владения либо `--port 0` с чтением реального порта; 401 на ready до DELIVERED считать `ServeUnavailable`, а не `ServeSecurityError`; `listener_pid is None` считать отказом — причина: `_spawn_serve` в каждом потоке начинает скан с одного и того же `20000 + (os.getpid() % 20000)` (server.py:2495). Пробный сокет закрывается до bind serve, а helper отдаёт рукопожатие сразу после `Popen`, до bind. Два запроса в окне ~110 мс получают один порт. Если `lsof` ещё не видит слушателя, `GET /api/session/active` попадает в чужой serve, получает 401 и превращается в `ServeSecurityError` без fallback. При `max_concurrent=6` это функциональный отказ. Совпадает с моей F-052.
AMEND F-014 — priority=non-blocking; locations=server.py:2654,2678; fix=статус `tool_use` брать из типа события (`success`/`failed`); накопление `input.delta` не нужно — причина: `feed` читает поле `text`, которое несёт только `input.ended`. Дельты идут в поле `delta` (FakeServe `et2`), поэтому перезапись `text` безвредна. Остаётся жёстко заданный `"status": "error"`.
AGREE F-015 rev=1 — проверил: `_drain_stderr(helper, [])` (server.py:2570) не вызывает `_log`, утечки пароля по diff нет. Теста AC-020 нет, комментарий вводит в заблуждение. Non-blocking.
AGREE F-016 rev=1 — проверил: server.py:4877 и :4884 присваивают `first_event_ms` и `ttft_ms` дважды подряд до fallback на run. В `O-EXIT` остаются тайминги serve при `transport=run`. Non-blocking.
AGREE F-017 rev=1 — проверил: матрицы kill-switch (`TRANSPORT=run`, override `0`, disable-файл, опечатка) в тестах нет. Группа B форсит `serve` либо один сценарий `auto`+503 (test:634). Non-blocking.
AGREE F-018 rev=1 — проверил: test:441-445 проверяют `len>=3` и span `<2.0`. Пороги 500/250 мс AC-001/002 не утверждаются. Non-blocking, красный на буферизации тест всё же даёт.
AGREE F-019 rev=1 — проверил: `if text_value.strip():` стоит в ветках reasoning и text (server.py:3018,3029). Дельты `"\n\n"` и `" "` не доходят до клиента. Это нарушает REQ-005/AC-006 и ломает превью DSH по `\n`. Дубль F-051.
AGREE F-020 rev=1 — проверил: server.py:1679 каждый `\uXXXX` превращается в отдельный `chr()`, пара `\ud83d\ude00` даёт два суррогата. Последующий `.encode("utf-8")` кидает `UnicodeEncodeError`. Дубль F-008.
AMEND F-021 — priority=non-blocking; locations=server.py:2718,2889,2892,3080; fix=передавать абсолютный `attempts.deadline` вместо `prompt_send_start + TIMEOUT_S`; выход цикла без `terminal` классифицировать как timeout, а не успех — причина: `while time.monotonic() < deadline` выходит без `terminal` только после 1800 с непрерывных токенов, так как `stall_timeout` сработает раньше. Дефект реален, но краевой.
AGREE F-022 rev=1 — проверил: server.py:2827 `HTTPConnection(..., timeout=5)`. `readline()` на молчащем SSE выбрасывает `TimeoutError`, `_reader` ловит `OSError` и кладёт `None`. Потребитель получает `invalid_serve_event` с `delivered=True`. Первый токен и stall по 60 с становятся недостижимыми. Тесты не ловят это: самая долгая пауза FakeServe 1.4 с. Блокирующий дефект для промптов ~100 КБ.
AGREE F-023 rev=1 — проверил: `_serve_http(..., conn=conn, timeout=timeout)` при `own_conn=False` не применяет `timeout`. Соединение создано с 3.0 с (server.py:2403, 2755). `finally` делает `interrupt` и `DELETE` с двумя попытками каждый до `lease.cleanup()`. На зависшем serve cleanup растягивается за 7 с (AC-011). Лечится порядком: сначала `killpg`, потом HTTP.
AGREE F-024 rev=1 — проверил: статус обслуживается только из цикла событий (server.py:2890). Он стартует после spawn, ready, create и subscribe. В legacy перед циклом стоят `gate.acquire()` и `spawn_limiter` (:5298). REQ-004 MUST требует первую реакцию ≤1.0 с независимо от апстрима.
AMEND F-025 — priority=non-blocking; locations=server.py:1096,5439,5453; fix=проверять watchdog и client_gone также после обработки каждой строки — причина: `on_idle` срабатывает на тишине `_StdoutFeed`. `opencode run` выдаёт 3-4 события за шаг (F-17 в ledger), поэтому непрерывный служебный поток нереалистичен. Теоретический дефект.
AGREE F-026 rev=1 — проверил: тот же дефект, что F-001 (server.py:4848, 5768). Блокирую.
AGREE F-027 rev=1 — проверил: `_run_serve_stream_attempts` при `not delivered and not force_serve` возвращает `False` (server.py:4866), после чего управление идёт в run без нового допуска. Последовательность delivered-fail ×2 затем undelivered-fail даёт четвёртый запуск, AC-013 это нарушает. Защиту первого запуска в legacy-цикле в diff проверить не могу.
INCONCLUSIVE F-028 — нужен исходник `_RequestAttempts.commit` и `attempt_done` (server.py ~2290) плюс тест OPEN→HALF_OPEN→успешный serve→CLOSED. В diff на serve-успехе вызывается только `serve_health.record_success()` (:4914, 5818), а `attempts.attempt_done(False, True)` не вызывается. Последствие для breaker из diff не выводится.
AGREE F-029 rev=1 — проверил: `prompt_status["status"]` и `"error"` не используются дальше проверки 401/403 (server.py:2879-2880, 2965). Для 400/404/422/429/5xx действий из таблицы нет. Дубль F-009 и F-055.
AGREE F-030 rev=1 — проверил: ветка `etype == "error"` ставит `result["error"]` и `terminal="failed"` (server.py:3073). Затем `serve error: …`, `upstream_failed`, без повтора (:4909, 5813). Legacy ретраит транзиентные 429/5xx/ECONNRESET (F-32: 22 free-limit и 9 ECONNRESET за день). REQ-009 и REQ-011 нарушены.
AGREE F-031 rev=1 — проверил: тот же дефект, что F-006 (server.py:4753, 4950, 4961, 5971).
AMEND F-032 — priority=non-blocking; locations=server.py:3046,3052,3077,4804; fix=при `step_finish` с эмитированным вызовом инструмента завершать попытку (terminal) вместо ожидания `execution.succeeded` — причина: при политике по умолчанию `ask_reject` `permission.asked` ставит `step_closed=True`, а ветка `if result["step_closed"] and etype in ("reasoning","text"): continue` блокирует дальнейший вывод. Текстовый `<tool_invoke>` завершает шаг без продолжения, `finally` делает `interrupt`. Утечка второго шага возможна только при `deny` и в нестандартных сценариях.
AGREE F-033 rev=1 — проверил: `_run_serve_stream_attempts` пересоздаёт парсер, но `_PrefixDedup` не применяется. После `stall_timeout` с уже отданными текстом или tool_call повтор выдаёт их снова (:4843, 4901, 4925). Дублирование tool_calls ведёт к повторному исполнению инструмента в DSH. Блокирую.
AMEND F-034 — priority=non-blocking; locations=server.py:4886,4915,5795,5874; fix=добавлять `result["usage"]` в аккумулятор до решения о повторе — причина: REQ-014 имеет приоритет SHOULD. Ветка timeout/invalid-event делает `continue` до аккумуляции. Это неточность учёта, а не потеря контента.
AGREE F-035 rev=1 — проверил: в `_spawn_serve` `raise ServeUnavailable(...)` (handshake timeout, mismatch, foreign listener) стоит внутри `try`, но `except` ловит `(OSError, ValueError, SubprocessError)`. `ServeUnavailable` туда не входит, поэтому `lease.cleanup()` не вызывается (server.py:2550-2572). Helper, serve, lifeline fd и каталог `zen-serve-state-*` остаются. `mkdtemp` в `_serve_env` (:1768) вызывается до `_spawn_serve` вне `try/finally`. Это источник `ResourceWarning: subprocess 98704 is still running` в `l2-green-ver002-unittest.log`. Блокирую, дубль F-059.
AMEND F-036 — priority=non-blocking; locations=server.py:2842,2859,2863,2865,3107; fix=`put` с таймаутом и флагом остановки, ограниченный `join` потоков в `finally` — причина: блокировка требует 4096 непрочитанных событий в очереди. Потребитель выходит раньше только при ошибке или отмене. Утечка daemon-потока, не отказ запроса.
AMEND F-037 — priority=non-blocking; locations=server.py:2570,1028; fix=дренаж stderr с ограниченным хвостом (`deque(maxlen)`) — причина: список растёт только за время жизни одной попытки (до `cleanup`). Тихий `opencode serve` пишет в stderr мало.
AMEND F-038 — priority=non-blocking; locations=server.py:2374,2564,2565,2778; fix=положительное доказательство слушателя (`lsof` вернул pid, и он равен `serve_pid`) до первой авторизованной записи, иначе `ServeUnavailable` — причина: пароль — одноразовый `token_hex(16)` на loopback и на одну попытку. Утечка возможна только на локальный слушатель. Условие `listener_pid is not None and (...)` пропускает отсутствие слушателя, это надо закрыть. Функциональную гонку портов блокирую в F-013.
AMEND F-039 — priority=non-blocking; locations=server.py:74,2593,2606,2609; fix=сверять `owner_uid`, `helper_lstart`, argv и `attempt_id` с живым процессом, lease-каталог создавать с 0700 — причина: сигнал идёт только процессу с `--serve-helper` в командной строке и `pgid==helper_pid`. Тот же класс, что F-003.
AMEND F-040 — priority=non-blocking; locations=server.py:174,177,181,195; fix=в `finally` helper слать SIGTERM всей собственной группе (`killpg(getpgrp())`) с эскалацией — причина: при штатном пути клиента `lease.cleanup()` делает `killpg` по всей группе. Потомки serve могут пережить только аварийную смерть моста.
AGREE F-041 rev=1 — проверил: `_serve_json_serve` не передаёт `is_client_gone` (server.py:5769). В `_client_gone_check` `except (OSError, ValueError): return False` (:4750) превращает RST в «клиент на месте». Блокирую по JSON-пути (дубль F-004).
AGREE F-042 rev=1 — проверил: `upstream_end_t = elapsed` в test:442 — это EOF клиентского ответа, а не независимое окончание апстрима. `assertTrue(silence or rows)` (:619) — тавтология. Матрица ставит PASS строкам REQ-006..016 без отдельных тестов. Совпадает с моей F-060.
AGREE F-043 rev=1 — проверил: test_realtime_reasoning.py:2 отключает 10 правил pyright блоком. Стоят `# type: ignore[attr-defined]` (:381-431). Запрет №9 python-standards блокирует merge, подавления без причины. Совпадает с F-062.
AMEND F-044 — priority=non-blocking; locations=test_realtime_reasoning.py:299,300; fix=убрать `os.environ.pop("FAKE_RT_MODE")` после `self.env.stop()` — причина: `mock.patch.dict` уже восстанавливает окружение. Лишний `pop` портит только предустановленное значение. Риск мал.
DISPUTE F-045 — класс: invalid — контр-evidence: verification-surface.json, уровень L2, `L2-VER-002-unittest-discover`: `python3 -m unittest discover -s tests -p 'test_*.py'` в `cwd=bridges/opencode-zen-bridge`. Все 17 существующих модулей и `test_step_interruption.py` построены на `unittest.TestCase`. Pytest-функции с фикстурами не выполнились бы под `unittest discover`, и обязательный VER-002 стал бы красным. Правило testing.md о `pytest`/Litestar адресовано async-проекту на Litestar, а мост — автономный stdlib-сервис (факт-карта).
AMEND F-046 — priority=non-blocking; locations=test_realtime_reasoning.py:321,392,444,445,568,624; fix=для проверок времени оставить запас над порогом и убрать пороги, не заданные требованием — причина: в репозитории нет маркеров `measured`/`heavy` (verification-surface.json, L3 note), все модули гоняют реальные подпроцессы в обычном наборе. REQ-004 требует ≤1.0 с, этот порог надо утверждать. Остальные пороги — flakiness.
AMEND F-047 — priority=non-blocking; locations=server.py:1326,1743,1795; fix=описать приоритеты переключателей, пороги, fallback и откат в PR и rollout-инструкции — причина: verification-surface.json `allowed_envelope_changes` разрешает `server.py`, один новый тест и `test_step_interruption.py`. Правка README вышла бы за согласованный состав файлов.
AMEND F-048 — priority=non-blocking; locations=server.py:1844,1845,1875,2973; fix=сверять `sessionID` по сырому событию до `_map_serve_event` — причина: `_map_serve_event` для reasoning/text/step_finish/error возвращает payload без `sessionID`, и фильтр `event_session not in (None, session_id)` пропускает любое. Каждый serve поднят на одну попытку с `OPENCODE_DB=":memory:"`, поэтому чужая сессия практически недостижима. Остаётся мёртвая проверка.
AGREE F-049 rev=1 — проверил: server.py:1791 `or len(head) == 4`. Дубль F-011. Non-blocking.
AMEND F-050 — priority=non-blocking; locations=server.py:4877,4884,5456,5468,5793; fix=хранить request-level `first_event_ms`/`ttft_ms` отдельно от attempt-level, либо маркировать транспорт — причина: REQ-016 требует наличия полей. Значения последней попытки в `O-EXIT` вводят в заблуждение (`first_event_ms=1975 ttft_ms=974`), но поведение запроса не искажают.

Критерии:

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Блокирующие дефекты доставки и конкурентности: F-001/F-026, F-006/F-031, F-008/F-020, F-013, F-019, F-022, F-030, F-033, F-035. Сторож 5 с на SSE (F-022) делает 60-секундные пороги недостижимыми. Потеря whitespace-дельт (F-019) нарушает AC-006. Утечка процессов при сбое запуска (F-035) прямо нарушает REQ-008.
   СОВЕТЫ: закрыть перечисленные F; сторожа serve согласовать с сокетными таймаутами; порт выделять под замком; общий gate и limiter для serve.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=Нет тестов на serve-сторожа (F-005), JSON-serve и client_gone (F-004/F-041), AC-011/012/018/020, matrix kill-switch (F-017). REQ-004 не выполнен под нагрузкой gate (F-024). Матрица прослеживаемости переоценена (F-042).
   СОВЕТЫ: добавить недостающие serve-тесты и сопоставить каждую строку матрицы с конкретным тестом; эмитить первый статус до gate и spawn.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Подход A1 с откатом на run осуществим: нужный CLI есть, memory-бюджет сходится. Конкурентная гонка портов (F-013), утечки (F-035), обход gate (F-001) и отсутствие повтора при 429/5xx (F-030) мешают катить без H0..H9. VER-006 и VER-007 законно `DEFERRED_L3`, отдельным FAIL они не являются.
   СОВЕТЫ: закрыть F-013, F-035, F-001, F-030, затем лестница H0..H9 на шести параллельных запросах рабочего размера.
4. РИСКИ: VERDICT=FAIL
   WHY=Двойное исполнение tool_calls при повторе после доставки (F-033), потеря tool_choice (F-006), ложные отказы при concurrency (F-013), 5-секундный разрыв SSE (F-022). Red→green и Full Suite L2 зелёные: `L2-RED` rc=1 (16 failed), VER-001/002/003/005 и AC-023 rc=0, 400 passed. Они не покрывают перечисленные сценарии.
   СОВЕТЫ: regression-тесты red→green для F-013, F-022, F-033, F-035, F-019.
5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL
   WHY=Выбор гибрида C (serve плюс откат на run, как muse-bridge ADR-0004) стратегически верен и даёт единственный реальный реалтайм (F-17..F-19 в ledger). Самописный `_JsonParser` (F-008/F-020) при уже импортированном `json` — неоправданное раздувание и источник дефектов. `FALLBACK_DECISION_TABLE` не исполняется (F-009).
   СОВЕТЫ: заменить парсер на `json.loads`; таблицу сделать исполняемой или удалить.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Периметр трёх файлов, неизменность Google и `_run_env` (hash совпал) и Non-Goals соблюдены. Нарушены: блоковые подавления pyright и `type: ignore` без причины (F-043), косметический реформат вне дельты (F-066), нет документации включения (F-047, non-blocking). Сверка SEED: SHA-256(seed_input)=e593a7f64a2f4bf24efeee98819327688ac6ee30db58451af712832e8193b2ee, SEED8=e593a7f6, это совпало с `seed_hex` манифеста r5. `ranked_order` независимо не воспроизвёл: ранжирование `SHA-256(seed_hex + '#' + slot_id)` даёт порядок claude, gemini, grok, gpt, muse, а в манифесте claude, gemini, grok, gpt, muse-wonder. Совпадение порядка при этом получилось, но точный алгоритм `rank_slots` (tier и filter) не перечитывал.
   СОВЕТЫ: убрать подавления, откатить форматирующие hunk'и вне дельты, оформить rollout-инструкцию в PR.

POSITIONS: 50/50
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


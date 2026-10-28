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

Skill: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md

ВАЖНО: Ты УЖЕ являешься запущенным внешним сабагентом роли Coder (модель `gpt-6.1-sol`, семейство `OpenAI`, транспорт `codex exec`), вызванным главным оркестратором Antigravity (семейство `Google`). Семейства оркестратора (`Google`) и Coder (`OpenAI`) различаются по канону. НЕ пытайся запускать ещё одного сабагента Coder изнутри себя — ТЫ САМ исполнитель роли Coder (`coder-08`) и должен непосредственно внести правки в код и обновить артефакты `plans/coder-08.before.json`, `plans/coder-08.json`, `handoffs/coder-08.json`, `coder.json`.

Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

Ты — внешний исполнитель роли **Coder** (`gpt-6.1-sol`, effort `high`, раунд `coder-08`, вход `fix-from-panel`, `teamlead_cycle: 6`, `iteration: 1` нового dev-цикла) в изолированном клоне проекта `cli-agent-bridge`.

## Уже известно
- `repo_root`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning`
- `branch`: `feature/zen-realtime-reasoning` (от `origin/dev` `7eda27f9d82732bab726a420e31ea2adc15c2c39`)
- `run_dir`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025`
- `target_files` (ЕДИНСТВЕННЫЕ 3 продуктовых и тестовых пути для модификации по `coder_target_files` и `do_not_change`):
  1. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py`
  2. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
  3. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_step_interruption.py`
- `prior_findings`:
  - Канон скилла реворка: `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md`
  - Бриф доработки от `panel-rework-summarizer`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief.json`
  - Итоговый вердикт Совета Тимлидов Cycle 5 (А–Г): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-5/final-panel-verdict.md`
  - Предыдущий план роли Coder: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.json`

Входы даны выше; на диск за ними не ходи мимо указанных путей; стартовый корень поиска ∈ {$HOME, /Users/aazhiry1, /} запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни ASK.

## ЖЁСТКИЕ ИНВАРИАНТЫ РЕВОРКА
1. Разрешено менять ТОЛЬКО 3 файла продукта/тестов:
   - `bridges/opencode-zen-bridge/server.py`
   - `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
   - `bridges/opencode-zen-bridge/tests/test_step_interruption.py`
   и файлы отчётности роли Coder:
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-08.before.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-08.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-08.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`
2. **НЕ ТРОГАТЬ НИ НА ОДИН БАЙТ** 3 замороженные функции в `bridges/opencode-zen-bridge/server.py`:
   - `def _run_env` (`sha256 == 1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`)
   - `def _stream_google_sse` (`sha256 == 5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3`)
   - `def _execute_google_once` (`sha256 == 88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6`)
3. **ЗАПРЕЩЕНО запускать full-file `ruff format server.py` или `ruff format .`!** Форматировать `tests/test_realtime_reasoning.py` можно целиком, а на `server.py` и `tests/test_step_interruption.py` использовать **ТОЛЬКО** закрытый диапазон `uvx --from ruff==0.17.2 ruff format --config ruff.toml --no-cache --range=START:1-END:999 <file>` по изменённым ханкам, не пересекая замороженные функции!
4. **ВАЖНО (`L2-RED-sensitivity`):** В `tests/test_realtime_reasoning.py` НЕ обращаться к новым атрибутам `server.*` на уровне импорта модуля (`module top-level`), чтобы `pytest --collect-only` на непатченном `origin/dev` всегда проходил с `rc=0`.
5. **НЕ делать `git commit`, `git push`, `gh pr create`**.
6. Сохранить ранний перехват `--serve-helper` в начале `server.py` и совместимость с `ast.parse(..., feature_version=(3, 9))`. Все комментарии и докстринги — строго на русском языке.

---

## Семь обязательных исправлений (`RW-001` .. `RW-007`) и сопутствующие `FU-001` .. `FU-003`

### 1. `RW-001` (`F-001`, 3/3): Барьер `headers_at` на ветках `etype == "error"` и `timeout` в `_serve_one_attempt`
- В `_serve_one_attempt` (`server.py:3552-3556` и `:3563-3566`):
  - На ветке `etype == "error"` (`server.py:3552`) сейчас вычисляется только `result["delivered"] = bool(texts or reasonings or native_calls)`, а `prompt_status.get("headers_at")` не учитывается!
  - А при выходе из цикла `while time.monotonic() < deadline:` по общему дедлайну (`server.py:3563-3566`, `result["exit_reason"] = "timeout"`) `result["delivered"]` не пересчитывается вовсе (остаётся `False`, если не было токенов)!
  - **Исправление:**
    1) Заведи локальный хелпер внутри `_serve_one_attempt`:
       ```python
       def _is_delivered() -> bool:
           return bool(
               prompt_status.get("headers_at")
               or texts
               or reasonings
               or native_calls
           )
       ```
       и вызывай `result["delivered"] = _is_delivered()` на **каждой** точке выхода из `_serve_one_attempt` (включая `etype == "error"`, `exit_reason = "timeout"`, watchdog-таймауты, `prompt_status != 200`, `prompt_error`, `step_finish`, `invalid_serve_event`), кроме явно не-доставленных pre-prompt HTTP 400/401/403/404/422.
    2) Во внешних циклах `Handler._run_serve_stream_attempts` (`server.py:5564-5570`, `:5618-5622`) и `Handler._handle_chat_json` (`server.py:6846-6855`, `:6911-6912`):
       убедись, что при `_delivered_now == True` (или `_delivered_j == True`) ни одна ветка (включая `transient_error` при исчерпании `allow_retry` и `exit_reason == "timeout"`) **НЕ возвращает `False`** (переход в `opencode run`) и **НЕ вызывает `serve_health.record_success()`**, а завершается терминальной SSE-ошибкой / HTTP 502!

### 2. `RW-002` (`F-002`, 3/3): Убрать нижний пол `120.0` из `FIRST_TOKEN_TIMEOUT_S` на legacy-пути `send_keepalive`
- В `Handler._stream_sse` -> `send_keepalive` (`server.py:6231-6235`):
  - Замени:
    ```python
    elif now_s - attempt_start > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0):
    ```
    на:
    ```python
    elif now_s - attempt_start > float(FIRST_TOKEN_TIMEOUT_S):
    ```
    чтобы настроенный `FIRST_TOKEN_TIMEOUT_S` (включая дефолтные `60 с`) одинаково соблюдался и на `serve`, и на legacy `run`.

### 3. `RW-003` (`F-008`, 3/3): Пофазные watchdog-таймауты (`first_event_timeout`, `first_token_timeout`, `stall_timeout`) в non-stream JSON `Run.execute`
- В `Run.execute` (`server.py:5050-5160`):
  - Сейчас в `Run.execute` отслеживаются только общий `deadline` и `subagent_stall_killed`, но нет пофазных watchdog-таймаутов `FIRST_EVENT_TIMEOUT_S`, `FIRST_TOKEN_TIMEOUT_S`, `STALL_TIMEOUT_S`.
  - **Исправление:**
    1) Внутри каждой попытки `for attempt in range(...)` в `Run.execute` заведи:
       - `attempt_start = time.monotonic()`
       - `first_event_at: float | None = None`
       - `first_token_at: float | None = None`
       - `last_token_at: float | None = None`
       - `watchdog_reason: list[str] = []`
    2) При получении любого валидного JSON-события в `handle_event`:
       - если `first_event_at is None`: `first_event_at = time.monotonic()`
       - если событие несёт модельный текст (`etype == "text"` с непустым текстом), размышление (`etype == "reasoning"` с непустым текстом) или вызов инструмента (`etype in ("tool_use", "tool_call")`):
         обновляй `now_ev = time.monotonic()`, `if first_token_at is None: first_token_at = now_ev`, `last_token_at = now_ev`.
    3) В `on_idle` (наряду с проверкой `subagent_started_at`):
       проверяй:
       - если `first_event_at is None and (now - attempt_start) > float(FIRST_EVENT_TIMEOUT_S)`:
         `watchdog_reason.append("first_event_timeout")`; `_stop_proc(proc)`; `return`
       - иначе если `first_token_at is None and (now - attempt_start) > float(FIRST_TOKEN_TIMEOUT_S)`:
         `watchdog_reason.append("first_token_timeout")`; `_stop_proc(proc)`; `return`
       - иначе если `last_token_at is not None and not subagent_started_at and (now - last_token_at) > float(STALL_TIMEOUT_S)`:
         `watchdog_reason.append("stall_timeout")`; `_stop_proc(proc)`; `return`
    4) После завершения чтения stdout, если `watchdog_reason`:
       логируй причину (`first_event_timeout` / `first_token_timeout` / `stall_timeout`), сохраняй её (например, в `last_err = f"opencode run watchdog: {watchdog_reason[0]}"`), и если есть бюджет повтора в рамках цикла попыток (`attempt + 1 < max_attempts` и `time.monotonic() < deadline`), делай `continue` (как при transient/watchdog retry), иначе выходи с ошибкой 502.

### 4. `RW-004` (`F-009`, 2/3): Параметризованная матрица `step interruption` (`AC-016`) и сравнительный тест `unmapped recovery` (`AC-017`) на транспорте `serve`
- В `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`:
  - Добавь явный параметризованный (или зеркальный по сценариям `tests/test_step_interruption.py`) набор тестов для `AC-016` на транспорте `serve`:
    - `test_c6_rw004_ac016_serve_step_interruption_matrix`: покрывает все 5 ветвей обрыва шага на `serve` (и для SSE, и для JSON):
      1. обрыв после `text` без финального `step_finish(stop)` -> retry -> успешная догенерация без дублирования преамбулы (`_dedup_retry_text`);
      2. обрыв после `reasoning` без `text` и без `step_finish(stop)` -> retry -> успешный ответ;
      3. обрыв на незакрытом `<tool_call>` блоке при `emulate_tools` -> `_strip_broken_tool_blocks` вырезает битый хвост -> retry -> чистое выполнение;
      4. обрыв после завершённого нативного вызова `session.tool.called` -> **НЕ повторяется** (немедленный возврат `finish_reason="tool_calls"`, защита от повторного выполнения инструмента);
      5. исчерпание бюджета повторов (`MAX_STEP_RETRIES` / `MAX_TOTAL_SPAWNS`) при продолжающемся `incomplete_step` -> контролируемое завершение без бесконечного цикла.
  - Добавь сравнительный тест для `AC-017`:
    - `test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence`: один и тот же сценарий (попытка 1 падает unmapped/transient ошибкой после частичного вывода, попытка 2 завершается `stop` с финальным ответом) прогоняется через `serve` и через `run` (как в SSE, так и в JSON) и проверяет эквивалентность итогового собранного текста, `finish_reason == "stop"`, отсутствие сырых дублей и соблюдение потолка `MAX_TOTAL_SPAWNS`.

### 5. `RW-005` (`F-010`, 2/3): Сквозной `deadline` и `is_client_gone` в `_spawn_serve` и открытии `/api/event`
- В `_spawn_serve` (`server.py:2731-2895`) и `_serve_one_attempt` (`server.py:3101-3210`):
  1) Расширь сигнатуру `_spawn_serve`:
     ```python
     def _spawn_serve(
         run_env: dict[str, str],
         deadline: float | None = None,
         is_client_gone: Callable[[], bool] | None = None,
     ) -> ServeLease:
     ```
  2) В самом начале `_spawn_serve` (до `subprocess.Popen`):
     - если `is_client_gone is not None and is_client_gone()`: выброси специальное исключение (или `ServeClientDisconnect("client disconnected before serve spawn")`, НЕ являющееся `ServeUnavailable`!)
     - если `deadline is not None and time.monotonic() >= deadline`: выброси `ServeStartupDeadlineExceeded("deadline expired before serve spawn")` (НЕ являющееся `ServeUnavailable`!)
  3) Внутри `_spawn_serve` ограничь окно ожидания handshake (`wait_deadline`) и окно поиска `listener_pid` (`pid_deadline`) сверху значением `deadline` (если `deadline is not None`), и на каждой итерации ожидания проверяй `is_client_gone()` и `time.monotonic() >= deadline`. Если во время старта клиент отключился или истёк общий `deadline` запроса:
     гарантированно прибери helper/группу процессов (`lease.cleanup()` / `_kill_pgid`) и выброси `ServeClientDisconnect` / `ServeStartupDeadlineExceeded` (чтобы `_serve_one_attempt` вернул `exit_reason = "client_disconnect"` или `"timeout"` с `delivered = True`, **НЕ вызывая `serve_health.record_failure()` и НЕ падая в fallback на `opencode run`**!).
  4) При открытии подписки `GET /api/event` в `_serve_one_attempt` (`server.py:3196-3206`):
     - перед открытием проверь `is_client_gone()` и `time.monotonic() >= deadline`;
     - передавай `timeout=max(0.05, min(float(FIRST_EVENT_TIMEOUT_S), deadline - time.monotonic()))`;
     - если на фазе открытия `/api/event` сработал `is_client_gone()` или общий `time.monotonic() >= deadline`, возвращай `exit_reason = "client_disconnect"` или `"timeout"` (без превращения в `ServeUnavailable` и без fallback на `run`).

### 6. `RW-006` (`F-011`, 2/3): Ранний старт дренажа `helper.stderr` сразу после `Popen` и байтовый лимит хвоста
- В `_spawn_serve` (`server.py:181`, `:2826-2885`):
  - Проблема: сейчас поток `_drain_stderr` запускается только на строке `2877` (ПОСЛЕ чтения handshake из `stdout` и ПОСЛЕ `_find_listener_pid`). Если `opencode serve` до открытия порта пишет в `stderr` больше размера буфера ОС (`>= 64 KiB`, например `2 MiB` логов или одну длинную строку без `
`), дочерний процесс блокируется на `write(2)` и никогда не доходит до bind порта! Кроме того, `collections.deque(maxlen=64)` по строкам не ограничивает память, если в `stderr` идёт поток без `
`.
  - **Исправление:**
    1) Введи константу `_MAX_STDERR_TAIL_BYTES = 16384` (`16 KiB`) и `_STDERR_CHUNK_READ_BYTES = 4096`.
    2) Запускай фоновый демон-поток `_drain_stderr` **сразу после `subprocess.Popen`** (до цикла чтения handshake из `stdout`!), читая `helper.stderr.read1(_STDERR_CHUNK_READ_BYTES)` (или `os.read` / порционное чтение по байтам, а не `for line in helper.stderr`, чтобы поток без `
` не копился в безразмерной строке!) и поддерживая кольцевой буфер последних `<= _MAX_STDERR_TAIL_BYTES` байт (разбивая на строки при декодировании для `lease.stderr_tail` под локом или сохраняя последние строки суммарно `<= _MAX_STDERR_TAIL_BYTES`).
    3) Убедись, что в `_serve_helper_main` (`server.py:181`) или родительском `_drain_stderr` буфер ограничен по байтам и `stderr` дренируется непрерывно с первой миллисекунды после `Popen`.

### 7. `RW-007` (`F-012`, 2/3) и `FU-003` (`F-005`, 3/3): Жёсткое соблюдение `deadline` в `_serve_http`, `skip_body=True` для cleanup `interrupt`/`DELETE` и бюджет уборки `<= 7 с` (`AC-011`)
- В `_serve_http` (`server.py:2575-2635`):
  1) Добавь параметр `skip_body: bool = False`.
  2) Перед `active_conn.request(...)` и перед `resp = active_conn.getresponse()` пересчитывай остаток времени до `deadline`:
     если `deadline is not None`:
     `rem = deadline - time.monotonic()`
     если `rem <= 0`: закрой `active_conn.close()` и выброси ` TimeoutError("serve http deadline expired")`.
     Выстави `active_conn.sock.settimeout(max(0.02, min(float(timeout), rem)))` (если `active_conn.sock is not None`), и дополнительно запусти сторожевой таймер (или поток-сторож на время `getresponse()`/чтения), который при наступлении `deadline` вызывает ` sock.shutdown(socket.SHUT_RDWR)` / `active_conn.close()`, чтобы даже капающие по 1 байту заголовки HTTP-ответа не могли удерживать `getresponse()` дольше `deadline`!
  3) Если `skip_body=True`: после получения заголовков `resp = active_conn.getresponse()` (и вызова `on_headers`) **не читай тело ответа вовсе** — сразу закрывай `active_conn.close()` и возвращай `(int(resp.status), {}, b"")`.
  4) При чтении тела (`skip_body=False`) перед каждым `resp.read1(...)` обновляй `sock.settimeout(max(0.02, min(float(timeout), deadline - time.monotonic())))`!
- В `finally` функции `_serve_one_attempt` (`server.py:3580-3615`, `FU-003` / `F-005` + `RW-007` / `F-012`):
  - Передавай `skip_body=True` в cleanup-вызовы `POST /api/session/{session_id}/interrupt` и `DELETE /api/session/{session_id}` с коротким общим бюджетом cleanup (например, `cleanup_deadline = time.monotonic() + 0.45`), и ужми `join` фоновых потоков (`sse_thread.join(timeout=0.2)`, `prompt_thread.join(timeout=0.2)`), чтобы `lease.cleanup()` всегда стартовал не позднее `~0.6 с` после выхода из цикла и вся цепочка уборки (`interrupt` + `DELETE` + `SIGTERM` -> `2 с` -> `SIGKILL` в `lease.cleanup()`) гарантированно укладывалась в `<= 7 с` (`AC-011`) даже при капающем апстриме!

### 8. Сопутствующие неблокирующие улучшения `FU-001` (`F-003`) и `FU-002` (`F-004`)
- **`FU-001` (`F-003`):**
  - Введи константы `_MAX_SSE_LINE_BYTES = 1 * 1024 * 1024` (`1 MiB`) и `_MAX_SERVE_HTTP_BODY_BYTES = 8 * 1024 * 1024` (`8 MiB`).
  - В `_sse_reader` (`server.py:3235`) читай строку с лимитом `raw_line = sse_resp.readline(_MAX_SSE_LINE_BYTES + 1)`: если `len(raw_line) > _MAX_SSE_LINE_BYTES` (строка превысила лимит без `
`), помечай `invalid_event.append("sse line exceeds max bytes")`, ставь `stop_sse.set()` и выходи из `_sse_reader`.
  - В `_serve_http` (`server.py:2613`) проверяй суммарный размер `len(raw_chunks_total) > _MAX_SERVE_HTTP_BODY_BYTES`: при превышении закрывай соединение и выбрасывай `ServeProtocolError("serve http response body exceeds max bytes")`.
- **`FU-002` (`F-004`):**
  - В `_map_serve_event` (`server.py:1949-1956`) заведи предикат:
    ```python
    def _valid_token_int(v: Any) -> bool:
        return isinstance(v, int) and not isinstance(v, bool) and v >= 0
    ```
    и проверяй все четыре поля `usage` (`input`, `output`, `reasoning`, `cache.read` при его наличии): если любое из присутствующих значений не `None` и не проходит `_valid_token_int(v)`, выбрасывай `ServeProtocolError("invalid token count in step_finish")`.

---

## Новые регрессионные тесты в `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
Добавь детерминированные unit-тесты на все исправления Цикла 6:
1. `test_c6_rw001_headers_at_blocks_run_fallback_on_sse_error_and_timeout`:
   - В режиме `auto` после получения HTTP-заголовков `prompt` (`headers_at` установлен) происходит: (а) transient SSE `session.execution.failed` (`429 rate limit`); (б) общий `timeout` попытки до первого модельного токена. Проверяется, что `result["delivered"] is True`, ни в SSE, ни в JSON не вызываются `Run.execute` / `_spawn_with_stdin` и `serve_health.record_success()`.
2. `test_c6_rw002_legacy_first_token_timeout_respects_configured_value_under_120s`:
   - На legacy SSE при `FIRST_TOKEN_TIMEOUT_S=0.35` и полученном служебном событии без токенов попытка завершается по `first_token_timeout` за `< 1.5 с` (не ожидая `120 с`).
3. `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs`:
   - В `Run.execute` (`TRANSPORT=run`, `stream=false`) проверяются все 3 пофазных watchdog-таймаута (`first_event_timeout`, `first_token_timeout`, `stall_timeout`): зависший CLI убивается через `_stop_proc` за доли секунды по настроенным порогам, а при наличии бюджета происходит повтор попытки.
4. `test_c6_rw004_ac016_serve_step_interruption_matrix` и `test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence`:
   - Полная матрица `AC-016` (5 сценариев обрыва шага на `serve`) и сравнительный тест `AC-017` (`unmapped recovery` на `serve` против `run`).
5. `test_c6_rw005_spawn_serve_respects_deadline_and_client_disconnect_without_run_fallback`:
   - При уже истёкшем `deadline` или `is_client_gone() == True` `_spawn_serve` не порождает helper и не переключается в `run`; при отключении клиента во время handshake/subscribe группа убирается без fallback в `run`.
6. `test_c6_rw006_spawn_serve_drains_multi_mib_stderr_before_bind_without_deadlock`:
   - `FakeServe` пишет `2 MiB` в `stderr` (включая поток без `
`) ДО вывода `listening on http://...`: `_spawn_serve` не блокируется, успешно завершает handshake, а буфер `stderr_tail` ограничен по байтам (`<= _MAX_STDERR_TAIL_BYTES`).
7. `test_c6_rw007_fu003_dripping_interrupt_delete_still_cleans_up_under_7s`:
   - При отключении клиента и `FakeServe`, медленно капающем заголовки/тело на `interrupt` и `DELETE`, cleanup в `_serve_one_attempt` не ждёт тела (`skip_body=True`), прерывает чтение по `deadline` и завершает всю группу процессов значительно быстрее `7 с` (`AC-011`).
8. `test_c6_fu001_fu002_sse_line_body_byte_caps_and_strict_usage_ints`:
   - Проверка `_MAX_SSE_LINE_BYTES`, `_MAX_SERVE_HTTP_BODY_BYTES` и отклонения `bool`/отрицательных чисел в `usage.{input,output,reasoning,cache.read}` через `ServeProtocolError`.

---

## Пошаговый порядок выполнения `coder-08`
1. Создай `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-08.before.json` (`iteration: 1`, `plan_kind: "delta"`, `parent_plan: ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.json"`, `trigger_ids: ["RW-001", "RW-002", "RW-003", "RW-004", "RW-005", "RW-006", "RW-007"]`, шаги `RP-01..RP-08` со статусом `"PENDING"`) и провалидируй:
   ```bash
   python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-08.before.json" --phase before
   ```
2. Внеси изменения в `bridges/opencode-zen-bridge/server.py` и `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`. Форматируй `server.py` ТОЛЬКО через `ruff format --range=...`!
3. Запусти `VER-004`:
   ```bash
   python3 - <<'VER004'
import ast, collections, hashlib, json, re, subprocess, tempfile
from pathlib import Path
root = Path.cwd().resolve()
bridge = root / 'bridges/opencode-zen-bridge'
files = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']
assert all(f.is_file() for f in files), 'all three target files must exist after Stage3'
ruff = ['uvx','--from','ruff==0.17.2','ruff']
def run(args, **kw):
    return subprocess.run(args, check=True, **kw)
def changed_ranges(file):
    rel = str(file.relative_to(root))
    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)
    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.
    result = []
    for line in diff.splitlines():
        m = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
        if m:
            start = int(m.group(1)); count = int(m.group(2) or '1')
            if count: result.append((start, start + count - 1))
    return result

# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.
FROZEN = {
    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',
    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',
    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',
}
baseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)
def frozen_slices(raw):
    lines = raw.splitlines(keepends=True)
    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}
    assert set(nodes)==set(FROZEN)
    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}
baseline_slices = frozen_slices(baseline_raw)
def assert_frozen(candidate=files[0]):
    candidate_slices = frozen_slices(candidate.read_bytes())
    for name, expected in FROZEN.items():
        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)
        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)
        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)
    return candidate_slices
candidate_slices = assert_frozen()
server_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)
for line in server_diff.splitlines():
    match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',line)
    if not match: continue
    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')
    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:
        for name,(lo,hi,_) in table.items():
            # Zero-count insert/delete anchors represent the boundary after start.
            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)
            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)
# Public module constant/read API remains intact; compatibility test file is frozen.
tree = ast.parse(files[0].read_bytes())
assignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]
assert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'
assert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)
assert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))
assert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'
helper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == "sys.argv[1:2] == ['--serve-helper']"), None)
assert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'
heavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}
def imported_names(node):
    if isinstance(node, ast.Import): return {a.name for a in node.names}
    if isinstance(node, ast.ImportFrom): return {node.module}
    return set()
assert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])
assert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)
assert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'
assert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))
run(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)

ranges = {f: changed_ranges(f) for f in files[:2]}
# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.
run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)
for f in files[:2]:
    for start, end in ranges[f]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)
assert_frozen()
# Exercise actual write-mode range formatting only on a disposable copy.
with tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:
    formatted_copy = Path(format_dir) / 'server.py'
    formatted_copy.write_bytes(files[0].read_bytes())
    for start, end in ranges[files[0]]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)
    assert formatted_copy.read_bytes() == files[0].read_bytes()
    assert_frozen(formatted_copy)
    assert_frozen()
    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})
# Full-file lint on all three. Only inherited E402 import site is excepted on server.
lint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)
assert lint.returncode in (0,1), lint.stderr
findings = json.loads(lint.stdout)
lines = files[0].read_text().splitlines()
assert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings
assert sum(x['code']=='E402' for x in findings) <= 1
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)
# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.
project = None
try:
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:
        project = Path(tmp.name)
        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)
    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)
    assert b.returncode in (0,1), b.stderr
    report = json.loads(b.stdout)
    ds = report['generalDiagnostics']
    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds
    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}
    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}
    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']
    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))
    print('BASEDPYRIGHT summary',report['summary'])
    print('SERVER dict(counts)',dict(counts))
    print('SERVER warningCount',len(warnings(files[0])))
    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)
    assert len(warnings(files[0]))<=720, len(warnings(files[0]))
    assert len(warnings(files[1]))<=194, len(warnings(files[1]))
    # New test file: zero warnings as well as zero errors, thus zero Any.
    assert not byfile[files[2]], byfile[files[2]]
    for f in files[:2]:
        for x in byfile[f]:
            line = x['range']['start']['line']+1
            if any(lo<=line<=hi for lo,hi in ranges[f]):
                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x
    # Do not introduce Any annotations/type ignores in added code in either legacy file.
    for f in files[:2]:
        src = f.read_text().splitlines()
        for lo,hi in ranges[f]:
            for line in src[lo-1:hi]:
                assert not re.search(r'\bAny\b|type:\s*ignore|pyright:\s*ignore|#\s*noqa|#\s*fmt:\s*off',line), (f,line)
    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)
    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))
finally:
    if project is not None: project.unlink(missing_ok=True)
VER004
   ```
   и прогони тесты `uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py bridges/opencode-zen-bridge/tests/test_step_interruption.py` и `python3 -m unittest discover -s bridges/opencode-zen-bridge/tests -p "test_*.py"`.
4. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-08.json` (`phase: "after"`, все шаги `"DONE"`), `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-08.json` (`round_id: "coder-08"`, `iteration: 1`, `status: "DONE"`, `next_role: "reviewer"`), скопируй в `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json` и `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`, и провалидируй оба файла через `validate_role_plan.py --phase after` и `validate_handoff.py coder`.

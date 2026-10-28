Skill: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md

ВАЖНО: Ты УЖЕ являешься запущенным внешним сабагентом роли Coder (модель `gpt-6.1-sol`, семейство `OpenAI`, транспорт `codex exec`), вызванным главным оркестратором Antigravity (семейство `Google`). Семейства оркестратора (`Google`) и Coder (`OpenAI`) различаются по канону. НЕ пытайся запускать ещё одного сабагента Coder изнутри себя — ТЫ САМ исполнитель роли Coder (`coder-09`) и должен непосредственно внести правки в код и обновить артефакты `plans/coder-09.before.json`, `plans/coder-09.json`, `handoffs/coder-09.json`, `coder.json`.

Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

Ты — внешний исполнитель роли **Coder** (`gpt-6.1-sol`, effort `high`, раунд `coder-09`, вход `fix-from-panel`, `teamlead_cycle: 7`, `iteration: 1` нового dev-цикла) в изолированном клоне проекта `cli-agent-bridge`.

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
  - Итоговый вердикт Совета Тимлидов Cycle 6 (А–Г): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-6/final-panel-verdict.md`
  - Предыдущий план роли Coder: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-08.json`

Входы даны выше; на диск за ними не ходи мимо указанных путей; стартовый корень поиска ∈ {$HOME, /Users/aazhiry1, /} запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни ASK.

## ЖЁСТКИЕ ИНВАРИАНТЫ РЕВОРКА
1. Разрешено менять ТОЛЬКО 3 файла продукта/тестов:
   - `bridges/opencode-zen-bridge/server.py`
   - `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
   - `bridges/opencode-zen-bridge/tests/test_step_interruption.py`
   и файлы отчётности роли Coder:
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-09.before.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-09.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-09.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`
2. **НЕ ТРОГАТЬ НИ НА ОДИН БАЙТ** 3 замороженные функции в `bridges/opencode-zen-bridge/server.py`:
   - `def _run_env` (`sha256 == 1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`)
   - `def _stream_google_sse` (`sha256 == 5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3`)
   - `def _execute_google_once` (`sha256 == 88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6`)
3. **ЗАПРЕЩЕНО запускать full-file `ruff format server.py` или `ruff format .`!** Форматировать `tests/test_realtime_reasoning.py` можно целиком, а на `server.py` и `tests/test_step_interruption.py` использовать **ТОЛЬКО** закрытый диапазон `uvx --from ruff==0.17.2 ruff format --config ruff.toml --no-cache --range=START:1-END:999 <file>` по изменённым ханкам, не пересекая замороженные функции!
4. **ВАЖНО (`L2-RED-sensitivity`):** В `tests/test_realtime_reasoning.py` НЕ обращаться к новым атрибутам `server.*` на уровне импорта модуля (`module top-level`), чтобы `pytest --collect-only` на непатченном `origin/dev` всегда проходил с `rc=0`.
5. **НЕ уменьшать `min(2.0, deadline - time.monotonic())` в `_parent_lstart` (`server.py:2556`) и `_lsof_listener_pid` (`server.py:2573`)** — на macOS под нагрузкой параллельных тестов `lsof` требует до `2.0 с`!
6. **НЕ делать `git commit`, `git push`, `gh pr create`**.
7. Сохранить ранний перехват `--serve-helper` в начале `server.py` и совместимость с `ast.parse(..., feature_version=(3, 9))`. Все комментарии и докстринги — строго на русском языке.

---

## Четыре обязательных исправления (`RW-001` .. `RW-004`) и сопутствующий `FU-001`

### 1. `RW-001` (`F-001` + `F-004`, 3/3): Точный `exit_reason` и времена `first_event_ms`/`ttft_ms` в `O-EXIT/v1` при исчерпании JSON watchdog (`Run.execute`)
- В `Run._execute_once` (`server.py:5486-5508`):
  1) Убери `fatal_error = True` из блока `if watchdog_reason:` (`server.py:5486-5488`):
     оставь только `if watchdog_reason: rc = 1` (чтобы `fatal_error` выставлялся исключительно при детерминированной HTTP-ошибке провайдера `400/401/403/404/422` на строке `5442`).
  2) Добавь `"first_event_at": first_event_at` и `"first_token_at": first_token_at` в возвращаемый словарь `Run._execute_once` (`server.py:5505-5508`).
- В `Handler._serve_json` (`server.py:7440-7460`, `:7516-7527`):
  1) Сразу после `out = run.execute()` переноси времена в `xs` (сохраняя самое раннее измерение, если `xs["first_event_at"]` / `xs["first_token_at"]` ещё `None`):
     ```python
     if xs.get("first_event_at") is None and isinstance(out.get("first_event_at"), (int, float)):
         xs["first_event_at"] = float(out["first_event_at"])
     if xs.get("first_token_at") is None and isinstance(out.get("first_token_at"), (int, float)):
         xs["first_token_at"] = float(out["first_token_at"])
     ```
  2) Перед проверкой `if out.get("fatal_error") and not tool_calls:` (`server.py:7516`) добавь явную обработку исчерпанного watchdog `Run.execute`:
     ```python
     if out.get("state") in (
         "first_event_timeout",
         "first_token_timeout",
         "stall_timeout",
     ) and not tool_calls:
         w_state = str(out["state"])
         tail = _clean_err(str(out.get("err") or ""), 500)
         xs["exit_reason"] = w_state
         self._send(
             502,
             _error_payload(
                 f"opencode {w_state}" + (f": {tail}" if tail else ""),
                 tail,
             ),
         )
         return
     ```
- Обнови `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs` (и добавь явный тест `test_c7_rw001_json_run_watchdog_oexit_reason_and_phase_timings`): при исчерпании попыток (`MAX_TOTAL_SPAWNS=1`) проверяй, что:
  - тело HTTP 502 содержит `opencode <phase>` и **НЕ** содержит `"provider error after partial output"`,
  - итоговая строка `O-EXIT/v1` в `bridge.log` содержит `exit_reason=<phase>` (а не `provider_fatal`),
  - для `first_event_timeout` в `O-EXIT/v1` `first_event_ms=None ttft_ms=None`, для `first_token_timeout` — `first_event_ms=<int> ttft_ms=None`, для `stall_timeout` — `first_event_ms=<int> ttft_ms=<int>`.

### 2. `RW-002` (`F-002`, 3/3): Включить `result["first_event_at"] is not None` в монотонный барьер `_is_delivered()`
- В `_serve_one_attempt` (`server.py:3345-3351`):
  - Обнови `_is_delivered()`:
    ```python
    def _is_delivered() -> bool:
        return bool(
            prompt_status.get("headers_at")
            or result["first_event_at"] is not None
            or result["texts"]
            or result["reasonings"]
            or result["native_calls"]
        )
    ```
  - Убедись, что при получении `session.execution.started` (или любого другого execution-события своей `session_id` на строке `3675-3685`) `result["first_event_at"]` сразу устанавливается и, следовательно, `_is_delivered()` становится `True` даже тогда, когда HTTP-ответ `POST /api/session/{id}/prompt` ещё не прислал заголовки (`headers_at is None`).
  - Добавь тест `test_c7_rw002_execution_started_before_prompt_headers_sets_delivered_and_blocks_run_fallback` (и для SSE, и для JSON в режиме `auto`): `FakeServe` задерживает HTTP-заголовки `POST /api/session/{id}/prompt`, но по `/api/event` присылает `session.execution.started` для созданной `session_id`, после чего обрывает SSE (EOF) или присылает transient error. Проверяется, что `delivered == True`, fallback в `opencode run` (`_spawn_with_stdin` / `Run.execute`) **НЕ вызывается**, `serve_health.record_success()` не вызывается, а повторы идут только через `serve` в пределах `MAX_TOTAL_SPAWNS`.

### 3. `RW-003` (`F-003`, 3/3): Учёт legacy SSE watchdog в `transient_failure` и Circuit Breaker до `attempts.attempt_done`
- В `Handler._stream_sse` (`server.py:6772-6780`):
  - Сейчас:
    ```python
    transient_failure = had_provider_error or (
        not attempt_output
        and _is_retryable_failure(rc, tail, provider_status, False)
    )
    attempts.attempt_done(
        transient_failure, attempt_output and not transient_failure
    )
    ```
    из-за чего при `watchdog_state.get("reason")` (когда процесс убит сигналом `rc < 0`):
    - без вывода `transient_failure == False` и `attempt_done(False, False)` не записывает failure в Circuit Breaker;
    - с частичным выводом (`attempt_output == True`) `attempt_done(False, True)` ошибочно записывает `record_success()` в Circuit Breaker!
  - **Исправление:**
    ```python
    has_watchdog = bool(watchdog_state.get("reason"))
    transient_failure = (
        has_watchdog
        or had_provider_error
        or (
            not attempt_output
            and _is_retryable_failure(rc, tail, provider_status, False)
        )
    )
    attempts.attempt_done(
        transient_failure, attempt_output and not transient_failure
    )
    ```
  - Добавь тест `test_c7_rw003_legacy_sse_watchdog_records_breaker_failure_with_and_without_output`: прогони все 3 фазы watchdog (`first_event_timeout`, `first_token_timeout`, `stall_timeout` после частичного вывода) на legacy SSE (`TRANSPORT=run`, `stream=true`) и проверь, что на каждой попытке счётчик отказов `breaker` увеличивается, `record_success` не вызывается, и при достижении `CB_FAILURE_THRESHOLD` Circuit Breaker переходит в состояние `OPEN`.

### 4. `RW-004` (`F-005`, 3/3): Собственные абсолютные фазовые дедлайны `min(attempt_deadline, phase_started + phase_budget)` для readiness, session create и subscribe
- В `_open_serve_events` (`server.py:3155-3195`) и `_serve_one_attempt` (`server.py:3353-3446`):
  1) В `_ctrl_http` (`server.py:3353`) добавь параметр `phase_deadline: float | None = None`:
     ```python
     def _ctrl_http(
         method: str,
         path: str,
         body: dict[str, object] | None = None,
         timeout: float = 3.0,
         phase_deadline: float | None = None,
     ) -> tuple[int, dict[str, object]]:
     ```
     Внутри `_ctrl_http` вычисляй:
     `call_deadline = min(attempt_deadline, phase_deadline if phase_deadline is not None else time.monotonic() + float(timeout))`
     и передавай `deadline=call_deadline` в `_serve_http(...)`!
     При этом в `except (OSError, http.client.HTTPException):` проверяй `_check_serve_start(attempt_deadline, is_client_gone)` (чтобы истечение общего `attempt_deadline` или `is_client_gone()` давало `timeout`/`client_gone`, а истечение локального `phase_deadline` при живом `attempt_deadline` пробрасывало `TimeoutError`/`OSError`, которое перехватывается как `ServeUnavailable` для pre-prompt fallback!).
  2) В цикле readiness (`/api/session/active`, `server.py:3391-3400`):
     вычисляй `ready_deadline = min(time.monotonic() + 3.0, attempt_deadline)` ОДИН раз перед циклом и передавай `phase_deadline=ready_deadline` в `_ctrl_http("GET", "/api/session/active", timeout=3.0, phase_deadline=ready_deadline)`, чтобы все повторы внутри readiness делили один абсолютный бюджет `ready_deadline` и капающие заголовки прерывались сторожем `_watch_serve_connection` в `_serve_http` по `ready_deadline`!
  3) В вызове `POST /api/session` (`server.py:3416-3431`):
     передавай `phase_deadline=min(time.monotonic() + 3.0, attempt_deadline)`.
  4) В `_open_serve_events` (`server.py:3155-3195`):
     вычисляй фазовый дедлайн открытия подписки:
     `sub_deadline = min(deadline, time.monotonic() + float(FIRST_EVENT_TIMEOUT_S))`
     и передавай `sub_deadline` в `_watch_serve_connection(conn, sub_deadline, is_client_gone, phase_socket)`.
     При перехвате `(ServeStartupDeadlineExceeded, TimeoutError, OSError)` во время открытия `/api/event`:
     если общий `time.monotonic() < deadline` и не `is_client_gone()`, но истёк именно `sub_deadline`, преобразуй `ServeStartupDeadlineExceeded` в `ServeUnavailable("serve event subscribe timeout")` (чтобы в `_serve_one_attempt` до отправки prompt сработал штатный pre-prompt fallback/retry, а при истёкшем общем `deadline` — терминальный `timeout`!).
  - Добавь тест `test_c7_rw004_startup_http_phases_enforce_own_budget_under_long_request_deadline`: при длинном общем `TIMEOUT_S=30.0` проверяются отдельно 3 случая медленно капающих заголовков (по 1 байту каждые `0.02 с` без `

`): (а) на `/api/session/active` (с коротким бюджетом фазы), (б) на `POST /api/session`, (в) на `GET /api/event`. В каждом случае фаза прерывается за время своего фазового окна (`<< 30 с`), а `lease.cleanup()` освобождает группу процессов.

### 5. `FU-001` (`F-006`, non-blocking, реализуем заодно): Дочитывание `session.step.ended` после нативного tool call при `emulate_tools`
- В `_serve_one_attempt` (`server.py:3742-3755`):
  - Когда при `emulate_tools` завершается нативный вызов (`done is not None`, `result["terminal"] = "tool_calls"`):
    вместо немедленного `break` дочитай из очереди `events` (в пределах короткого окна `min(deadline, time.monotonic() + 0.15)`) события текущего шага до первого `step_finish` (`session.step.ended`), игнорируя любые новые `reasoning`/`text`/`tool_event` (`result["step_closed"] = True`), чтобы если `opencode serve` присылает `session.step.ended` вслед за `session.tool.called`, его токены (`input`, `output`, `cached`, `reasoning`) попали в `result["usage"]`! Как только `step_finish` получен (или окно `0.15 с` / `None` в очереди истекло), делай `break`.
  - Добавь unit-тест `test_c7_fu001_native_tool_call_captures_step_ended_usage`: `FakeServe` отправляет `session.tool.called` и сразу следом `session.step.ended` с известными токенами (`input=123, output=45, cached=10, reasoning=67`) — проверяется, что финальный чанк содержит и `tool_calls`, и точный `usage` из `session.step.ended`.

---

## Пошаговый порядок выполнения `coder-09`
1. Создай `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-09.before.json` (`iteration: 1`, `plan_kind: "delta"`, `parent_plan: ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-08.json"`, `trigger_ids: ["RW-001", "RW-002", "RW-003", "RW-004"]`, шаги `RP-01..RP-05` со статусом `"PENDING"`) и провалидируй:
   ```bash
   python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-09.before.json" --phase before
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
   и прогони тесты `uvx --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py bridges/opencode-zen-bridge/tests/test_step_interruption.py`.
4. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-09.json` (`phase: "after"`, все шаги `"DONE"`), `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-09.json` (`round_id: "coder-09"`, `iteration: 1`, `status: "DONE"`, `next_role: "reviewer"`), скопируй в `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json` и `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`, и провалидируй оба файла через `validate_role_plan.py --phase after` и `validate_handoff.py coder`.

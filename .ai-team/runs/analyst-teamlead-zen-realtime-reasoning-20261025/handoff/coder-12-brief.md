Skill: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md

ВАЖНО: Ты УЖЕ являешься запущенным внешним сабагентом роли Coder (модель `gpt-6.1-sol`, семейство `OpenAI`, транспорт `codex exec`), вызванным главным оркестратором Antigravity (семейство `Google`). Семейства оркестратора (`Google`) и Coder (`OpenAI`) различаются по канону. НЕ пытайся запускать ещё одного сабагента Coder изнутри себя — ТЫ САМ исполнитель роли Coder (`coder-12`) и должен непосредственно внести правки в код и обновить артефакты `plans/coder-12.before.json`, `plans/coder-12.json`, `handoffs/coder-12.json`, `coder.json`.

Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

Ты — внешний исполнитель роли **Coder** (`gpt-6.1-sol`, effort `high`, раунд `coder-12`, вход `fix-from-panel`, `teamlead_cycle: 9`, `iteration: 1` нового dev-цикла) в изолированном клоне проекта `cli-agent-bridge`.

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
  - Итоговый вердикт Совета Тимлидов Cycle 8 (А–Г): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-8/final-panel-verdict.md`
  - Предыдущий план роли Coder: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-11.json`

Входы даны выше; на диск за ними не ходи мимо указанных путей; стартовый корень поиска ∈ {$HOME, /Users/aazhiry1, /} запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни ASK.

## ЖЁСТКИЕ ИНВАРИАНТЫ РЕВОРКА
1. Разрешено менять ТОЛЬКО 3 файла продукта/тестов:
   - `bridges/opencode-zen-bridge/server.py`
   - `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
   - `bridges/opencode-zen-bridge/tests/test_step_interruption.py`
   и файлы отчётности роли Coder:
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-12.before.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-12.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-12.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`
2. **НЕ ТРОГАТЬ НИ НА ОДИН БАЙТ** 3 замороженные функции в `bridges/opencode-zen-bridge/server.py`:
   - `def _run_env` (`sha256 == 1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`)
   - `def _stream_google_sse` (`sha256 == 5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3`)
   - `def _execute_google_once` (`sha256 == 88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6`)
3. **ЗАПРЕЩЕНО запускать full-file `ruff format server.py` или `ruff format .`!** Форматировать `tests/test_realtime_reasoning.py` можно целиком, а на `server.py` и `tests/test_step_interruption.py` использовать **ТОЛЬКО** закрытый диапазон `uvx --offline --from ruff==0.17.2 ruff format --config ruff.toml --no-cache --range=START:1-END:999 <file>` по изменённым ханкам, не пересекая замороженные функции! (При вызове `uvx` используй `--offline`, чтобы не ждать PyPI).
4. **ВАЖНО (`L2-RED-sensitivity`):** В `tests/test_realtime_reasoning.py` НЕ обращаться к новым атрибутам `server.*` на уровне импорта модуля (`module top-level`), чтобы `pytest --collect-only` на непатченном `origin/dev` всегда проходил с `rc=0`. Сохраняй классы `unittest.TestCase` (`FU-002` / `F-004`), чтобы `VER-002` (`python3 -m unittest discover -s tests -p 'test_*.py'`) исполнял все тесты.
5. **НЕ уменьшать `min(2.0, deadline - time.monotonic())` в `_parent_lstart` и `_lsof_listener_pid`** — на macOS под нагрузкой параллельных тестов `lsof` требует до `2.0 с`!
6. **НЕ делать `git commit`, `git push`, `gh pr create`**.
7. Сохранить ранний перехват `--serve-helper` в начале `server.py` и совместимость с `ast.parse(..., feature_version=(3, 9))`. Все комментарии и докстринги — строго на русском языке.

---

## Два обязательных исправления (`RW-001`, `RW-002`) и сопутствующий `FU-001`

### 1. `RW-001` (`F-001`, blocking): Полное дочитывание нативных tool calls шага и обязательное подтверждение `session.step.ended` в `_drain_serve_step_usage`
- **Контекст проблемы (`server.py:3345-3398`, `server.py:3885-3905`):**
  1. Сейчас после первого завершённого `session.tool.called`/`failed`/`success` при `emulate_tools=True` вызывается `_drain_serve_step_usage(..., min(deadline, time.monotonic() + 0.15), ...)`:
     - Окно `0.15 с` слишком узкое: если второй параллельный tool call того же шага приходит через `200 мс` (`> 150 мс`) до `session.step.ended`, окно истекает раньше и второй вызов теряется.
     - На строке `3371` дополнительные `tool_event` принимаются только при `if assistant_message_id and ev_msg_id == assistant_message_id:`. Если `assistantMessageID` отсутствовал в событиях `session.tool.*` текущего шага (или присутствовал в `session.reasoning.delta`/`session.text.delta`, но не в `session.tool.called`), дополнительные нативные вызовы того же шага отбрасываются!
     - Если окно `_drain_serve_step_usage` истекло или поток закрылся (`item is None`) БЕЗ получения `session.step.ended`, код всё равно оставляет `result["terminal"] = "tool_calls"` и возвращает неполный набор инструментов как успешный ответ!
- **Исправление:**
  1. Добавь константу `_STEP_DRAIN_WINDOW_S = 1.0` около `_MAX_SSE_LINE_BYTES` (`server.py:1580`).
  2. В `_serve_one_attempt` отслеживай `current_step_msg_id = ""` из `data_raw.get("assistantMessageID")` любых событий текущей сессии до закрытия шага, чтобы при вызове `_drain_serve_step_usage` передавать `data_raw.get("assistantMessageID") or current_step_msg_id or None` и дедлайн `min(deadline, time.monotonic() + _STEP_DRAIN_WINDOW_S)`.
  3. В `_drain_serve_step_usage(...) -> bool`:
     - Возвращай `bool`: `True`, если получен подтверждённый `session.step.ended` для `session_id` (с совместимым `assistantMessageID`: `not assistant_message_id or not ev_msg_id or ev_msg_id == assistant_message_id`), и `False`, если окно истекло или пришёл EOF (`item is None`) без `session.step.ended`.
     - Если `not assistant_message_id and ev_msg_id` у события `tool_event` той же `session_id`, запоминай `assistant_message_id = ev_msg_id`.
     - Для `etype == "tool_event"` той же `session_id`: принимай событие, когда `not assistant_message_id or not ev_msg_id or ev_msg_id == assistant_message_id` (отсекай только события, где и `assistant_message_id`, и `ev_msg_id` непустые и `ev_msg_id != assistant_message_id`!).
     - Внутри `_drain_serve_step_usage` при `etype == "step_finish"` также завершай любые незакрытые вызовы из `tool_state.tools` (как в основном цикле на строках `3916-3920`, с защитой от дублей по `call_id`), записывай `usage` и возвращай `True`.
  4. В `_serve_one_attempt` (`server.py:3885-3900`):
     - Вызывай `step_confirmed = _drain_serve_step_usage(...)`.
     - Если `not step_confirmed`: НЕ выставляй `result["terminal"] = "tool_calls"` — возбуждай `ServeProtocolError("incomplete tool step without step.ended")` (это переведёт попытку в управляемый `exit_reason = "invalid_serve_event"` с `interrupt` + `lease.cleanup()`, исключая успешный возврат неполного инструментального шага!).
     - Если `step_confirmed`: выставляй `result["terminal"] = "tool_calls"`, `result["step_closed"] = True` и `break`.
  5. **Проверь совместимость с существующим тестом `_c6_scenario` (`tests/test_realtime_reasoning.py:2313-2320`):**
     - В `_c6_scenario` (`tests/test_realtime_reasoning.py:2317-2319`) для `scenario == "native"` сейчас написано:
       ```python
       if scenario=="native": time.sleep(2); return
       if scenario=="unmapped":
           emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
       ```
       Поскольку `scenario == "native"` в `test_c6_rw004_ac016_serve_step_interruption_matrix` проверяет успешное закрытие первого шага с `finish_reason == "tool_calls"` и прерывание перед вторым шагом (`time.sleep(2)`), измени строки `2317-2320` в `_c6_scenario` так, чтобы `session.step.ended` отправлялся и для `native`, и для `unmapped` перед `if scenario=="native": time.sleep(2); return`:
       ```python
       if scenario in ("native","unmapped"):
           emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
       if scenario=="native": time.sleep(2); return
       ```
  6. **Расширь `test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded` (или добавь рядом `test_c9_rw001_delayed_and_idless_native_tool_calls_and_unconfirmed_step_rejected`)** в `tests/test_realtime_reasoning.py`:
     - Проверь в SSE (`stream=True`) и JSON (`stream=False`):
       (а) два нативных tool calls одного шага (`m1`), где второй вызов приходит с задержкой `time.sleep(0.22)` (`> 150 мс`) перед `session.step.ended(m1)`, а следом идёт вызов следующего шага (`m2`) — оба вызова `c1` и `c2` доставляются полностью с точным `usage` из `m1`, а `m2` отсекается;
       (б) два нативных tool calls одного шага БЕЗ `assistantMessageID` с последующим `session.step.ended` — оба вызова доставляются полностью с точным `usage`;
       (в) нативный tool call БЕЗ последующего `session.step.ended` (поток закрывается или истекает `_STEP_DRAIN_WINDOW_S`) — попытка НЕ завершается успешным `finish_reason="tool_calls"`, а завершается ошибкой `invalid_serve_event` (`502` в JSON / SSE `error`).

### 2. `RW-002` (`F-003`, blocking): Терминальная обработка `state == "timeout"` в `Handler._serve_json` с точной записью `exit_reason="timeout"` в `O-EXIT/v1`
- **Контекст проблемы (`server.py:5438, 5677, 7749-7765, 7821-7840, 7942`):**
  - В `Run._execute_once` при истечении локального дедлайна до спавна (`server.py:5434, 5452`) или во время чтения (`server.py:5635`) возвращается `state="timeout"` с `attempts.attempt_done(False, False)` (нейтрально для Circuit Breaker).
  - Однако в `Handler._serve_json`:
    - На строке `7749` проверяется только `if out.get("state") in ("launcher_missing", "spawn_failed", "client_gone"):`.
    - На строке `7821` проверяется только `if watchdog_phase in ("first_event_timeout", "first_token_timeout", "stall_timeout") and not tool_calls:`.
    - В результате `out.get("state") == "timeout"` проваливается до строки `7942` (`if not content and not tool_calls:`) и перезаписывает `xs["exit_reason"] = "upstream_failed"`!
- **Исправление:**
  1. В `Handler._serve_json` (`server.py:7749` или `7821`) обработай `out.get("state") == "timeout"` терминально до ветки пустого текста (`server.py:7942`):
     - В блоке `watchdog_phase = cast(object, out.get("state"))` (`server.py:7821`) добавь `"timeout"` в кортеж `("first_event_timeout", "first_token_timeout", "stall_timeout", "timeout")` (или обработай `out.get("state") == "timeout"` сразу на строке `7749`, если `not contents and not tool_calls`), чтобы выставлялся `xs["exit_reason"] = "timeout"`, отправлялся HTTP `502` через `_error_payload(...)` и выполнялся `return`.
     - Также в `Run._execute_once` (`server.py:5677-5681`) убедись, что при `state == "timeout"` никогда не передаётся `success=True` в `attempt_done` и `breaker.record_success()` (`had_output and not transient_failure and state != "timeout"`).
  2. **Обнови `test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation` (`tests/test_realtime_reasoning.py:1272-1313`):**
     - Для обоих режимов (`stream in (True, False)`) и сценария дедлайна (`cancel=False`) проверь по записанному логу `server.LOG_PATH`:
       - ровно одно новое событие `O-EXIT/v1` на запрос;
       - в нём `exit_reason=timeout` и `total_spawns=0` (а при `cancel=True` — `exit_reason=client_gone` и `total_spawns=0`);
       - счётчик отказов `self.bridge.httpd.resilience.breaker._failures == 0` и резерв `spawn_limiter` возвращён (`refund.assert_called_once()`).

### 3. `FU-001` (`F-002`, non-blocking, реализуем заодно): Явный байтовый бюджет очереди SSE-событий и накопленного ответа в `_serve_one_attempt`
- **Контекст (`server.py:1580, 3580-3629, 3843-3865`):**
  - В `server.py:1580` задан `_MAX_SSE_LINE_BYTES = 1024 * 1024` (1 МиБ), а в `server.py:3580` — `events = queue.Queue(maxsize=4096)`. Теоретическое произведение `4096 * 1 МиБ = 4 ГиБ` превышает эксплуатационный потолок памяти `HL-ENV-01` (`<= 2 GiB` при 6 параллельных слотах).
- **Исправление:**
  1. Около `_MAX_SSE_LINE_BYTES` (`server.py:1580`) введи две константы:
     - `_MAX_SERVE_QUEUE_BYTES = 16 * 1024 * 1024` (`16 МиБ` суммарно в очереди `events` одной попытки)
     - `_MAX_SERVE_ACCUMULATED_BYTES = 16 * 1024 * 1024` (`16 МиБ` суммарного UTF-8 текста `reasonings` + `texts` одной попытки)
     (при 6 параллельных слотах `6 * (16 + 16) = 192 МиБ` полезной нагрузки гарантированно укладываются в `<= 2 GiB` `HL-ENV-01` даже с учётом накладных расходов Python-объектов).
  2. В `_serve_one_attempt`:
     - Отслеживай текущий байтовый объём очереди `events` (например, через защищённый `threading.Lock()` счётчик `queued_bytes = [0]` и поле `"_raw_bytes": len(line)` в словаре события, уменьшая `queued_bytes[0]` при каждом `events.get(...)` в основном цикле и в `_drain_serve_step_usage`). Если в `_reader()` очередная строка `line` приводит к `queued_bytes[0] + len(line) > _MAX_SERVE_QUEUE_BYTES`, помещай в очередь `{"type": "__invalid_json__", "data": {}}` и завершай `_reader()` (`break`), чтобы попытка немедленно завершилась с `exit_reason = "invalid_serve_event"` и `lease.cleanup()`.
     - Отслеживай `accumulated_bytes` в основном цикле `_serve_one_attempt` при добавлении в `result["reasonings"]` и `result["texts"]`: если `accumulated_bytes + len(text_value.encode("utf-8", "replace")) > _MAX_SERVE_ACCUMULATED_BYTES`, возбуждай `ServeProtocolError("serve accumulated response byte budget exceeded")` (что переведёт попытку в `exit_reason = "invalid_serve_event"` с `interrupt` + `lease.cleanup()`).
  3. Добавь детерминированный тест `test_c9_fu001_serve_queue_and_accumulated_byte_budget_enforced` в `tests/test_realtime_reasoning.py` (с `mock.patch.object(server, "_MAX_SERVE_QUEUE_BYTES", ...)` и `mock.patch.object(server, "_MAX_SERVE_ACCUMULATED_BYTES", ...)`), проверяющий, что превышение любого из двух байтовых бюджетов детерминированно останавливает попытку с `exit_reason == "invalid_serve_event"` и гарантированным `lease.cleanup()`.

---

## Пошаговый порядок выполнения `coder-12`
1. Создай `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-12.before.json` (`iteration: 1`, `plan_kind: "delta"`, `parent_plan: ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-11.json"`, `trigger_ids: ["RW-001", "RW-002"]`, шаги `RP-01..RP-04` со статусом `"PENDING"`) и провалидируй:
   ```bash
   python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-12.before.json" --phase before
   ```
2. Внеси изменения в `bridges/opencode-zen-bridge/server.py` и `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`. Форматируй `server.py` ТОЛЬКО через `uvx --offline --from ruff==0.17.2 ruff format --config ruff.toml --no-cache --range=...`!
3. Запусти `VER-004` (с `--offline` для `uvx`):
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
   и прогони тесты `uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py bridges/opencode-zen-bridge/tests/test_step_interruption.py`.
4. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-12.json` (`phase: "after"`, все шаги `"DONE"`), `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-12.json` (`round_id: "coder-12"`, `iteration: 1`, `status: "DONE"`, `next_role: "reviewer"`), скопируй в `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json` и `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`, и провалидируй оба файла через `validate_role_plan.py --phase after` и `validate_handoff.py coder`.

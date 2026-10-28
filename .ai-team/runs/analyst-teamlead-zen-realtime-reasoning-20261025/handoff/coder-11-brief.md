Skill: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md

ВАЖНО: Ты УЖЕ являешься запущенным внешним сабагентом роли Coder (модель `gpt-6.1-sol`, семейство `OpenAI`, транспорт `codex exec`), вызванным главным оркестратором Antigravity (семейство `Google`). Семейства оркестратора (`Google`) и Coder (`OpenAI`) различаются по канону. НЕ пытайся запускать ещё одного сабагента Coder изнутри себя — ТЫ САМ исполнитель роли Coder (`coder-11`) и должен непосредственно внести правки в код и обновить артефакты `plans/coder-11.before.json`, `plans/coder-11.json`, `handoffs/coder-11.json`, `coder.json`.

Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

Ты — внешний исполнитель роли **Coder** (`gpt-6.1-sol`, effort `high`, раунд `coder-11`, вход `fix-from-panel`, `teamlead_cycle: 8`, `iteration: 1` нового dev-цикла) в изолированном клоне проекта `cli-agent-bridge`.

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
  - Итоговый вердикт Совета Тимлидов Cycle 7 (А–Г): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-7/final-panel-verdict.md`
  - Предыдущий план роли Coder: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-10.json`

Входы даны выше; на диск за ними не ходи мимо указанных путей; стартовый корень поиска ∈ {$HOME, /Users/aazhiry1, /} запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни ASK.

## ЖЁСТКИЕ ИНВАРИАНТЫ РЕВОРКА
1. Разрешено менять ТОЛЬКО 3 файла продукта/тестов:
   - `bridges/opencode-zen-bridge/server.py`
   - `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
   - `bridges/opencode-zen-bridge/tests/test_step_interruption.py`
   и файлы отчётности роли Coder:
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-11.before.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-11.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-11.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`
2. **НЕ ТРОГАТЬ НИ НА ОДИН БАЙТ** 3 замороженные функции в `bridges/opencode-zen-bridge/server.py`:
   - `def _run_env` (`sha256 == 1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`)
   - `def _stream_google_sse` (`sha256 == 5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3`)
   - `def _execute_google_once` (`sha256 == 88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6`)
3. **ЗАПРЕЩЕНО запускать full-file `ruff format server.py` или `ruff format .`!** Форматировать `tests/test_realtime_reasoning.py` можно целиком, а на `server.py` и `tests/test_step_interruption.py` использовать **ТОЛЬКО** закрытый диапазон `uvx --offline --from ruff==0.17.2 ruff format --config ruff.toml --no-cache --range=START:1-END:999 <file>` по изменённым ханкам, не пересекая замороженные функции! (При вызове `uvx` используй `--offline`, чтобы не ждать PyPI).
4. **ВАЖНО (`L2-RED-sensitivity`):** В `tests/test_realtime_reasoning.py` НЕ обращаться к новым атрибутам `server.*` на уровне импорта модуля (`module top-level`), чтобы `pytest --collect-only` на непатченном `origin/dev` всегда проходил с `rc=0`.
5. **НЕ уменьшать `min(2.0, deadline - time.monotonic())` в `_parent_lstart` и `_lsof_listener_pid`** — на macOS под нагрузкой параллельных тестов `lsof` требует до `2.0 с`!
6. **НЕ делать `git commit`, `git push`, `gh pr create`**.
7. Сохранить ранний перехват `--serve-helper` в начале `server.py` и совместимость с `ast.parse(..., feature_version=(3, 9))`. Все комментарии и докстринги — строго на русском языке.

---

## Три обязательных исправления (`RW-001` .. `RW-003`) и три сопутствующих `FU-001` .. `FU-003`

### 1. `RW-001` (`F-001`, blocking): Разделить барьер запрета fallback в `run` и разрешение `serve`-повтора ранней транзиентной ошибки без модельного вывода в SSE (`Handler._stream_sse_serve`)
- В `Handler._stream_sse_serve` (`server.py:6028-6044`) и для EOF/timeout после начала исполнения без модельного вывода (`server.py:6090-6110`):
  - Сейчас на строке `6034`:
    ```python
    _delivered_err = _delivered_now or bool(collected_texts)
    if not _delivered_err and attempts.allow_retry("serve_transient_error"):
        continue
    if not _delivered_err and not force_serve:
        return False
    ```
    Из-за `RW-002` цикла 7 получение `session.execution.started` делает `_delivered_now = True` даже тогда, когда клиенту ещё не выдан ни один модельный токен (`not collected_texts and not collected_reasonings and not result.get("native_calls")`). В результате ранняя ошибка `session.execution.failed` (429/503) сразу после `session.execution.started` пропускает `continue` и завершает запрос ошибкой на первой же попытке, хотя в JSON-ветке (`server.py:7328` `if not texts and attempts.allow_retry("serve_transient_error"): continue`) такой `serve`-повтор выполняется!
  - **Исправление:**
    - Введи явный предикат `_has_model_output = bool(collected_texts or collected_reasonings or result.get("native_calls"))`.
    - В ветке `err.get("kind") == "transient_error"` (`server.py:6034`):
      разрешай повтор через `serve`, если модельного вывода ещё не было (`if not _has_model_output and attempts.allow_retry("serve_transient_error"): continue`), но переход в `opencode run` по-прежнему блокируй по полному монотонному барьеру `_delivered_err = _delivered_now or _has_model_output` (`if not _delivered_err and not force_serve: return False`).
    - Аналогично в JSON-ветке `Handler._serve_json_via_serve` (`server.py:7325-7345`): убедись, что при `err.get("kind") == "transient_error"` повтор через `serve` разрешён при `not texts and not reasonings and not result.get("native_calls")`, а fallback в `run` (`return None`) запрещён при `delivered_any`.
  - Добавь тест `test_c8_rw001_early_transient_error_after_execution_started_retries_serve_without_run_fallback`: `FakeServe` на попытке #1 присылает `session.execution.started`, затем `session.execution.failed` (429/503) без токенов, а на попытке #2 присылает `reasoning` + `text` + `step.ended`. Проверяется, что и SSE (`stream=true`), и JSON (`stream=false`) в режиме `auto` выполняют вторую `serve`-попытку и завершаются успехом (200 OK), не вызывая `opencode run`.

### 2. `RW-002` (`F-002`, blocking): Отклонять непарные UTF-16 суррогаты (`\ud800..\udfff`) на границе `serve`-протокола через `ServeProtocolError`
- В `_combine_surrogates` (`server.py:1776-1786`):
  - Сейчас:
    ```python
    try:
        return value.encode("utf-16-be", "surrogatepass").decode("utf-16-be")
    except UnicodeError:
        return value
    ```
    Если JSON от `opencode serve` содержит одиночный (непарный) суррогат `"\ud800"` или `"\udc00"`, `decode("utf-16-be")` выбрасывает `UnicodeDecodeError`, `_combine_surrogates` возвращает исходную строку с непарным суррогатом, и позже `.encode("utf-8")` на отправке SSE/JSON падает с необработанным `UnicodeEncodeError` вне классификации `invalid_serve_event` (`ServeProtocolError`).
  - **Исправление:**
    - В `_combine_surrogates(value: str) -> str` при `UnicodeError` выбрасывай `ServeProtocolError("invalid unpaired surrogate in serve event")`.
    - Также убедись, что `_combine_surrogates` применяется ко всем строковым полям текста/reasoning/tool-аргументов/имени на границе разбора `serve`-событий (`_map_serve_event` / `_extract_serve_error`), чтобы любой непарный суррогат в `serve`-событии детерминированно вызывал `ServeProtocolError` (`exit_reason="invalid_serve_event"`). Корректные суррогатные пары (`"\ud83d\ude00"`) при этом продолжают склеиваться в `"😀"` без ошибок.
  - Добавь тест `test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_in_sse_and_json`: проверяй подачу `"\ud800"` и `"\udc00"` в `reasoning`/`text` в SSE и JSON (с `lease.cleanup()` и `O-EXIT/v1` `invalid_serve_event` при `force_serve` или после барьера доставки, и с fallback в `run` до барьера в `auto`), а также сохранение валидной пары `"\ud83d\ude00" -> "😀"`.

### 3. `RW-003` (`F-005`, blocking): Выделить локальный общий `timeout` (`ServeStartupDeadlineExceeded` / исчерпание дедлайна запроса) в нейтральный терминальный исход без загрязнения Circuit Breaker
- В `Handler._stream_sse_serve` (`server.py:5995`, `:6091`) и `Handler._serve_json_via_serve` (`server.py:7284`, `:7380`):
  - По `FALLBACK_DECISION_TABLE` (`server.py:1729-1736`) и докстрингу `_AttemptController` (`server.py:2488`), исчерпание локального дедлайна запроса (`exit_reason == "timeout"`, в том числе при `ServeStartupDeadlineExceeded`) — это **нейтральный терминальный исход** (`fail_closed`, `serve_health_inc=0`, `upstream_cb_inc=0`), а НЕ транзиентный отказ апстрима.
  - Сейчас `"timeout"` включён в кортеж `( "first_event_timeout", "first_token_timeout", "stall_timeout", "timeout", "eof_before_step_finish")` на строках `5995`, `6091`, `7284`, `7380`, который вызывает `attempts.attempt_done(True, False)` и при `commit()` увеличивает счётчик отказов upstream Circuit Breaker!
  - **Исправление:**
    - Исключи `"timeout"` из кортежа, вызывающего `attempts.attempt_done(True, False)` и `attempts.allow_retry(...)` в `_stream_sse_serve` и `_serve_json_via_serve`.
    - Обрабатывай `exit_reason == "timeout"` отдельно как нейтральный терминальный исход: вызывай `attempts.attempt_done(False, False)`, выставляй `xs["exit_reason"] = "timeout"`, НЕ делай retry и НЕ переключайся в `opencode run` (в JSON сразу отправляй `504` / `502` `opencode timeout`, в SSE завершай поток с `xs["exit_reason"] = "timeout"`).
    - Фазовые тайм-ауты watchdog (`first_event_timeout`, `first_token_timeout`, `stall_timeout`) и `eof_before_step_finish` оставь в кортеже транзиентных отказов (`attempts.attempt_done(True, False)`).
  - Добавь тест `test_c8_rw003_request_deadline_timeout_is_neutral_for_circuit_breaker`: серия запросов в SSE и JSON, завершающихся по `ServeStartupDeadlineExceeded` / общему `timeout` (`exit_reason="timeout"`), оставляет `breaker.failures == 0` и `breaker.state == "CLOSED"`, тогда как `first_token_timeout` и `stall_timeout` продолжают увеличивать `breaker.failures`.

### 4. `FU-001` (`F-003`, non-blocking, реализуем заодно): Сохранение всех нативных tool calls одного шага (`assistantMessageID`) в окне закрытия шага
- В `_drain_serve_step_usage` (`server.py:3292-3321`) и `_serve_one_attempt` (`server.py:3818-3829`):
  - Сейчас после первого завершённого `session.tool.called`/`failed`/`success` при `emulate_tools` вызывается `_drain_serve_step_usage(...)` и сразу `break`, причём `_drain_serve_step_usage` пропускает все события, кроме `session.step.ended`. Если модель в одном шаге (с тем же `assistantMessageID`) выдала пакет из двух параллельных нативных tool calls (`called(c1, m1) -> called(c2, m1) -> step.ended(m1)`), второй вызов `c2` теряется!
  - **Исправление:**
    - В `_drain_serve_step_usage` передавай также `tool_assembler` и `result` (или обрабатывай внутри `_drain_serve_step_usage` события `session.tool.*` ТОЛЬКО для того же `session_id` и того же `assistant_msg_id`, когда `assistant_msg_id` непустой): если до прихода `session.step.ended` в окне `0.15 с` приходит ещё один завершённый нативный tool call того же `session_id` и того же `assistant_msg_id`, преобразуй его через `_native_to_tool_calls` и добавляй в `result["native_calls"]` (и в `on_native_tool_call`, если задан, без дублирования по `callID`), при этом строго отбрасывая любые события другого `assistantMessageID` (следующего шага)!
  - Добавь тест `test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded`: `FakeServe` присылает `called(c1, m1)`, `called(c2, m1)`, `step.ended(m1)` и следом `called(c3, m2)` второго шага — проверяется, что в SSE и JSON клиент получает оба вызова `c1` и `c2` ровно по одному разу, точный `usage` из `step.ended(m1)`, и не получает `c3` из `m2`.

### 5. `FU-002` (`F-004`, non-blocking, реализуем заодно): Прерываемое по дедлайну и `is_client_gone` ожидание в `_StartupGate.acquire()` и `spawn_limiter.acquire()` + проверка перед `_spawn_with_stdin`
- В `_StartupGate.acquire` (`server.py:2092-2115`), `_SpawnRateLimiter.acquire` (`server.py:2135-2165`) и точках вызова перед спавном (`server.py:5353, 5904, 6536, 7194`):
  - Добавь в `_StartupGate.acquire` и `_SpawnRateLimiter.acquire` необязательные параметры `deadline: float | None = None` и `is_client_gone: Callable[[], bool] | None = None`, чтобы ожидание шло короткими шагами (до `0.05 с`), ограничивалось `min(wait_budget, deadline - time.monotonic())` и немедленно прерывалось, если `is_client_gone()` вернул `True` или `deadline` истёк.
  - В точках перед спавном (`_stream_sse_serve`, `_serve_json_via_serve`, `_stream_sse`, `Run._execute_once`) передавай дедлайн запроса и `is_client_gone`, а непосредственно перед `_spawn_with_stdin` на legacy-путях повторно проверяй `is_client_gone()` и `attempts.remaining_s() <= 0` (освобождая gate/slot и не запуская процесс при отмене или истечении бюджета).
  - Добавь unit-тест `test_c8_fu002_pre_spawn_gate_and_limiter_respect_deadline_and_client_disconnect`.

### 6. `FU-003` (`F-006`, non-blocking, реализуем заодно): Совместимость `TestServeTransportAndFakeServe.setUp`/`tearDown` с немодифицированным `origin/dev` для поведенческого RED `AC-026`
- В `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py` (`setUp` и `tearDown` класса `TestServeTransportAndFakeServe`, строки `900, 922`):
  - Замени прямое чтение `self.saved_cfg = server.DYNAMIC_CONFIG_PATH` на:
    `self._had_dyn_cfg = hasattr(server, "DYNAMIC_CONFIG_PATH")`
    `self.saved_cfg = getattr(server, "DYNAMIC_CONFIG_PATH", Path(self.tmp_dir.name) / "missing_dyn.json")`
    и в `tearDown`: если `self._had_dyn_cfg`, восстанавливай `server.DYNAMIC_CONFIG_PATH = self.saved_cfg`.
  - Аналогично проверь остальные строки `TestServeTransportAndFakeServe.setUp` / `tearDown` и начала `test_ac026_realtime_chunks_before_upstream_end`: убедись, что при запуске `test_ac026_realtime_chunks_before_upstream_end` против немодифицированного `origin/dev` `server.py` (где нет `DYNAMIC_CONFIG_PATH`, `_StartupGate`, `serve_health`) `setUp` не падает по `AttributeError`, а сам `test_ac026_realtime_chunks_before_upstream_end` доходит до HTTP-запроса в мост и падает именно на сокетном оракуле реалтайм-чанков (`AssertionError`)!

---

## Пошаговый порядок выполнения `coder-11`
1. Создай `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-11.before.json` (`iteration: 1`, `plan_kind: "delta"`, `parent_plan: ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-10.json"`, `trigger_ids: ["RW-001", "RW-002", "RW-003"]`, шаги `RP-01..RP-06` со статусом `"PENDING"`) и провалидируй:
   ```bash
   python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-11.before.json" --phase before
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
4. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-11.json` (`phase: "after"`, все шаги `"DONE"`), `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-11.json` (`round_id: "coder-11"`, `iteration: 1`, `status: "DONE"`, `next_role: "reviewer"`), скопируй в `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json` и `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`, и провалидируй оба файла через `validate_role_plan.py --phase after` и `validate_handoff.py coder`.

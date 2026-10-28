Skill: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md

ВАЖНО: Ты УЖЕ являешься запущенным внешним сабагентом роли Coder (модель `gpt-6.1-sol`, семейство `OpenAI`, транспорт `codex exec`), вызванным главным оркестратором Antigravity (семейство `Google`). Семейства оркестратора (`Google`) и Coder (`OpenAI`) различаются по канону. НЕ пытайся запускать ещё одного сабагента Coder изнутри себя — ТЫ САМ исполнитель роли Coder (`coder-07`) и должен непосредственно внести правки в код и обновить артефакты `plans/coder-07.before.json`, `plans/coder-07.json`, `handoffs/coder-07.json`, `coder.json`.

Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

Ты — внешний исполнитель роли **Coder** (`gpt-6.1-sol`, effort `high`, раунд `coder-07`, вход `fix-from-panel`, `teamlead_cycle: 5`, `iteration: 1` нового dev-цикла) в изолированном клоне проекта `cli-agent-bridge`.

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
  - Итоговый вердикт Совета Тимлидов Cycle 4 (А–Г): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/cycle-4/final-panel-verdict.md`
  - Предыдущий план роли Coder: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json`

Входы даны выше; на диск за ними не ходи мимо указанных путей; стартовый корень поиска ∈ {$HOME, /Users/aazhiry1, /} запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни ASK.

## ЖЁСТКИЕ ИНВАРИАНТЫ РЕВОРКА
1. Разрешено менять ТОЛЬКО 3 файла продукта/тестов:
   - `bridges/opencode-zen-bridge/server.py`
   - `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
   - `bridges/opencode-zen-bridge/tests/test_step_interruption.py`
   и файлы отчётности роли Coder:
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.before.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-07.json`
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

## Четыре обязательных исправления (`RW-001` .. `RW-004`) и сопутствующие `FU-001` .. `FU-006`

### 1. `RW-001` (`F-001` + `F-003`) и `FU-002` (`F-004`) и `FU-005` (`F-009`): Барьер доставки `headers_at` и ранняя публикация HTTP-статуса в `_serve_http` / `_serve_one_attempt`
- В `_serve_http` (`server.py:2604-2606`) поддержи передачу HTTP-статуса в `on_headers`:
  - Если `on_headers` принимает аргумент или вызывается после `resp = active_conn.getresponse()`, например:
    в `_prompt_worker` (`server.py:3265-3266`) передавай `on_headers`:
    ```python
    def _on_headers(status_code: int = 200) -> None:
        prompt_status["headers_at"] = time.monotonic()
        prompt_status["status"] = status_code
        if status_code in (401, 403):
            prompt_status["security"] = True
    ```
    А в `_serve_http` вызывай `on_headers(int(resp.status))` (или через `try: on_headers(int(resp.status)) except TypeError: on_headers()`), чтобы:
    1) если сервер прислал заголовки `400/401/403/404/422` и задержал тело, основной цикл `_serve_one_attempt` сразу видел `prompt_status["status"]` и завершался `ServeSecurityError` (без ложного `first_event_timeout` и без установки `delivered=True` при 400/401/403/404/422);
    2) если сервер прислал заголовки `200` (или `429`/`5xx`), `prompt_status["headers_at"]` уже установлен!
- В `_serve_one_attempt`:
  - На строках `3330-3333` (ветка `if isinstance(_ps, int) and _ps != 200`):
    после проверки `_ps in (401, 403)` и `_ps in (400, 404, 422)` вычисляй:
    ```python
    _delivered_now = bool(
        prompt_status.get("headers_at")
        or result["texts"]
        or result["reasonings"]
        or result["native_calls"]
    )
    result["delivered"] = _delivered_now
    ```
  - На строках `3341-3345` (ветка `_prompt_err = prompt_status.get("error")`):
    если `isinstance(_prompt_err, str)`:
    проверяй `_has_delivery = bool(prompt_status.get("headers_at") or result["texts"] or result["reasonings"] or result["native_calls"])`.
    - Если `not _has_delivery`: как и раньше `raise ServeUnavailable(f"serve prompt failed: {_prompt_err}")` (ошибка соединения ДО получения заголовков ответа `prompt` — разрешён fallback в `run`).
    - Если `_has_delivery` истинно (заголовки `prompt` уже были приняты, а ошибка произошла при чтении тела ответа): **НЕ бросай `ServeUnavailable`!** Выставь:
      ```python
      result["delivered"] = True
      result["exit_reason"] = "prompt_error"
      result["transient_error"] = True
      return result
      ```
- В `Handler._run_serve_stream_attempts` (`server.py:5556-5596`) и `Handler._handle_chat_json` (`server.py:6821-6850`):
  - Добавь `"prompt_error"` в кортеж обрабатываемых причин выхода рядом с `"invalid_serve_event"` (или перед `if result.get("prompt_status") is not None:`):
    при `exit_reason == "prompt_error"` учитывай `attempts.attempt_done(True, False)`, проверяй `if not _delivered_now and not force_serve: return False`, а при `_delivered_now == True` вызывай `if attempts.allow_retry("prompt_error"): continue`, иначе завершай ошибкой (`_sse_error` / HTTP 502) без вызова `record_success()` и без ухода в `run`!
  - В ветке `if result.get("exit_reason") in ("prompt_status_429",):` (`server.py:5590`) и `if result.get("prompt_status") is not None:` (`server.py:5577`, `:6840`): так как `result["delivered"]` теперь `True` (благодаря `headers_at`), `_delivered_now` / `_delivered_j` будет `True`, поэтому `if not _delivered_now and not force_serve:` НЕ сработает, запрос НЕ уйдёт в `run`, а пойдёт строго через `if attempts.allow_retry(f"prompt_status_{_ps_code}"): continue` (списывая `RetryBudget` по `FU-005` / `F-009`!). Также обнови строку в `FALLBACK_DECISION_TABLE` для `429/5xx`, чтобы было ясно, что при полученных заголовках ответа `prompt` (`headers_at`) срабатывает `serve_retry` через `allow_retry`.

### 2. `RW-002` (`F-005`): Гарантия первого статуса `<= 1.0 с` (`AC-005`) при задержке старта `0.4–0.6 с`
- В `Handler._stream_sse` (`server.py:5947-5959`, `:6119-6121`, `:6179`, `:6228-6245`):
  - Проблема: `status_timer` заводится на `req_t0 + 0.65s`, но на строке `6121` сразу после `spawn_limiter.acquire()` вызывается `status_timer.cancel()`, а затем `watchdog_state["status_next"]` на строке `6179` выставляется в `attempt_start + FIRST_STATUS_DELAY_S`. Если `spawn_limiter.acquire` занял `0.5 с`, `status_timer` отменяется в `0.5 с` (ещё не сработав!), а `status_next` сдвигается на `0.5 + 0.65 = 1.15 с > 1.0 с`!
  - Исправление:
    1) Не отменяй `status_timer` сразу после `spawn_limiter.acquire` на первой попытке (либо отменяй его только внутри `emit_synthetic` / `send_text` / `emit_tool_call` / `finally`, когда первый видимый чанк реально отправлен), **И**
    2) На первой попытке (`attempts.total_spawns == 1`) инициализируй:
       ```python
       req_t0 = attempts.deadline - TIMEOUT_S
       first_status_due = req_t0 + FIRST_STATUS_DELAY_S
       ```
       и в `watchdog_state["status_next"]` ставь:
       ```python
       "status_next": (
           first_status_due
           if attempts.total_spawns <= 1 and not status_fired_at[0]
           else attempt_start + FIRST_STATUS_DELAY_S
       ),
       ```
       А в `send_keepalive` (`server.py:6231-6245`), когда `watchdog_state["first_token_at"] is None`: если `not first_visible.is_set()` и `not status_fired_at[0]`, отправляй `STATUS_INITIAL` (через `_initial_status()`, который потокобезопасно под `status_lock` ставит `first_visible.set()` и `status_fired_at[0] = time.monotonic()`) и ставь `watchdog_state["status_next"] = now_s + STATUS_WAITING_INTERVAL_S`!
    - Тогда при любой задержке старта (`0.0 с`, `0.5 с`, `0.85 с`) ровно один `STATUS_INITIAL` гарантированно уйдёт в `t0 + 0.65 с <= 1.0 с` без дублей!

### 3. `RW-003` (`F-007`) и `FU-001` (`F-002`): Единый разделитель `[мост] Повтор попытки` на legacy-пути `run` с проверкой `thinking_enabled`
- В `Handler._stream_sse`:
  - На строке `6463-6465` (ветка `if watchdog_state.get("reason"):` -> `if attempts.allow_retry(reason_w):`):
    оберни вызов `emit_synthetic(...)` условием `if thinking_enabled:` (закрывает `F-002`).
  - На ветках `unmapped` (`server.py:6512-6529`) и `incomplete_step` (`server.py:6552-6569`) на legacy-пути `run`:
    перед `continue` (когда повтор разрешён через `attempts.allow_retry(...)`) добавь:
    ```python
    if thinking_enabled and (attempt_reasonings or attempt_texts):
        emit_synthetic(
            f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n"
        )
    ```
    (или централизуй эмиссию разделителя в начале следующей итерации `while True:` при `attempts.total_spawns > 0 and thinking_enabled and had_prior_visible_output` — убедившись, что между любыми двумя попытками `watchdog` / `unmapped` / `incomplete` при `thinking_enabled=True` эмитится **ровно один** разделитель `[мост] Повтор попытки`, а при `thinking_enabled=False` — **ноль** разделителей).

### 4. `RW-004` (`F-011`): Обновление `last_token_at` при завершённом нативном вызове в `_serve_one_attempt`
- В `_serve_one_attempt` (`server.py:3486-3506` и `:3531-3535`):
  - При `etype == "tool_event"`:
    - На строке `3486`: при `etype_raw == "session.tool.input.delta"` обновляй `last_token_at = time.monotonic()` (а если `result["first_token_at"] is None`, также можешь обновить `last_token_at = time.monotonic()`).
    - На строках `3500-3506` (когда `done is not None`): обязательно обновляй `last_token_at = time.monotonic()` (независимо от того, был ли `first_token_at` уже установлен или устанавливается сейчас!).
  - На строках `3525-3535` (в `step_finish`, когда завершаются `done = tool_state.complete(...)`): также обновляй `last_token_at = time.monotonic()`.

### 5. Сопутствующие улучшения `FU-003` (`F-006`), `FU-004` (`F-008`), `FU-006` (`F-010`)
- **`FU-003` (`F-006`):** В `Handler._handle_chat_json` на ветке `if result.get("transient_error"):` (`server.py:6854-6881`):
  перед добавлением текста в `contents` пропусти `"".join(texts)` через `ToolCallParser` и `_strip_broken_tool_blocks` (если `emulate_tools`), примени `_dedup_retry_text(_prior_content, ...)` при наличии `_prior_content`, добавь очищенный текст в `contents`, и перед `continue` на строке `6871` обнови `_prior_content = "\n\n".join(c for c in contents if c)`.
- **`FU-006` (`F-010`):** В `finally` функции `_serve_one_attempt` (`server.py:3574-3594`) при вызовах `_serve_http(..., "POST", f"/api/session/{session_id}/interrupt", ..., timeout=0.25)` и `DELETE` передавай `deadline=time.monotonic() + 0.35` (чтобы капающее по байту тело не могло продлевать чтение до бесконечности, и управление гарантированно переходило к `lease.cleanup()`).
- **`FU-004` (`F-008`):** В `tests/test_realtime_reasoning.py` в `test_ac026_realtime_chunks_before_upstream_end` запиши массив времён отправки каждой дельты в `FakeServe` (`sent_times`) и массив времён получения чанков клиентом (`recv_times`), и проверь попарно, что каждая дельта доходит до клиента за `< 0.25 с` от момента её отправки апстримом (`recv_t - sent_t < 0.25`).

---

## Новые регрессионные тесты в `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
Добавь детерминированные unit-тесты на все исправления Цикла 5:
1. `test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback`:
   - В режиме `auto` `FakeServe` отправляет HTTP-заголовки ответа на `/api/session/.../prompt` (`200 OK` с обрывом соединения при чтении тела, и отдельно `429 Too Many Requests` до модельных токенов): проверяется, что ни в SSE, ни в JSON `Run.execute` / `_spawn_with_stdin` **не вызываются**, запрос остаётся на `serve-retry` (или возвращает ошибку `serve` при исчерпании попыток), а `serve_health.record_success()` не вызывается.
   - При зависшем теле после заголовков `401 Unauthorized` `_serve_one_attempt` немедленно классифицирует `ServeSecurityError` по заголовкам (`FU-002`).
2. `test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s`:
   - На legacy-пути `run` `spawn_limiter.acquire` задерживает старт на `0.50 с` (меньше `0.65 с`), после чего процесс молчит: первый видимый чанк `[мост]` приходит не позднее `1.0 с` от начала запроса (`AC-005`), начальный статус `STATUS_INITIAL` эмитится ровно один раз.
3. `test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate`:
   - На legacy-пути `run` при повторе по `watchdog`, `unmapped` и `incomplete` recovery при `thinking on` эмитится ровно один разделитель `[мост] Повтор попытки` между попытками, а при `thinking off` (`effort="off"`) — ноль синтетических разделителей (`F-002` + `F-007`).
4. `test_c5_rw004_native_call_updates_last_token_at_no_premature_stall`:
   - В `_serve_one_attempt` первый завершённый `native_call` (`session.tool.called`) обновляет `last_token_at`, так что последующая пауза меньше `STALL_TIMEOUT_S` не вызывает ложный `stall_timeout`.
5. `test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates`:
   - В `Handler._handle_chat_json` при `transient_error` после преамбулы и частичного tool-блока преамбула нормализуется, сырой tool-блок вырезается и при повторе преамбула не дублируется в итоговом JSON `content`.

---

## Пошаговый порядок выполнения `coder-07`
1. Создай `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.before.json` (`iteration: 1`, `plan_kind: "delta"`, `parent_plan: ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-06.json"`, `trigger_ids: ["RW-001", "RW-002", "RW-003", "RW-004"]`, шаги `RP-01..RP-05` со статусом `"PENDING"`) и провалидируй:
   ```bash
   python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.before.json" --phase before
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
4. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-07.json` (`phase: "after"`, все шаги `"DONE"`), `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-07.json` (`round_id: "coder-07"`, `iteration: 1`, `status: "DONE"`, `next_role: "reviewer"`), скопируй в `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json` и `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/coder.json`, и провалидируй оба файла через `validate_role_plan.py --phase after` и `validate_handoff.py coder`.

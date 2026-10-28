# Бриф Coder (раунд `coder-02` — дельта-доводка после Clean-Room L2 и `reverse-spec`): `zen-realtime-reasoning`

Скилл реализации (ровно один путь по канону):
`/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature-implementation.md`

Входы даны выше и ниже; на диск за ними вне рабочего клона не ходи; стартовый корень поиска ∈ `{$HOME, /Users/<user>, /}` запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни `ASK`.
**ВАЖНО:** Не трать ходы на длинные `sed` чтения `server.py` и `test_realtime_reasoning.py` — все точные строки и сниппеты уже приведены ниже! Сразу пиши `plans/coder-02.before.json`, применяй точечные замены в Python, проверяй `VER-004` + целевой `pytest` и пиши `plans/coder-02.json` + `handoffs/coder-02.json`.

## Уже известно
- `repo_root`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning`
- `branch`: `feature/zen-realtime-reasoning`
- `run_dir`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025`
- `architecture_packet`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (mtime `2026-10-26 16:38 MSK`, `ARCH_GATE_PASS` + `ARCH_PANEL_PASS`)
- `coder_target_files` (СТРОГИЙ БЕЛЫЙ СПИСОК — другие файлы в `bridges/` и корне репо трогать ЗАПРЕЩЕНО):
  1. `bridges/opencode-zen-bridge/server.py`
  2. `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
  3. `bridges/opencode-zen-bridge/tests/test_step_interruption.py` (уже зелёный, менять не требуется)

## Шаг 1. План `before` (ДО первой правки кода)
Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-02.before.json` (`schema_version: "1.0"`, `role: "coder"`, `task_id: "analyst-teamlead-zen-realtime-reasoning-20261025"`, `run_id: "analyst-teamlead-zen-realtime-reasoning-20261025"`, `iteration: 2`, `plan_kind: "delta"`, `steps` со статусом `"PENDING"`, `deviations: []`, `stop_conditions: [...]`, `inputs_read: [...]`) и проверь:
```bash
python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" \
  /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-02.before.json \
  --expected-role coder --expected-stage before
```

## Шаг 2. Точные замены в `bridges/opencode-zen-bridge/server.py`
Замороженные функции `_run_env`, `_stream_google_sse`, `_execute_google_once` НЕ ТРОГАТЬ ни на один байт!

### 2.1. `FIRST_STATUS_DELAY_S = 0.65` (строка 1336)
Замени:
```python
FIRST_STATUS_DELAY_S = 0.30
```
на:
```python
FIRST_STATUS_DELAY_S = 0.65
```

### 2.2. Keep-alive параметр `conn` в `_serve_http` и условие в `_ServeLease.cleanup` (строки 2392–2455)
В `_serve_http` добавь необязательный параметр `conn: http.client.HTTPConnection | None = None`: если `conn is not None`, используй его без `conn.close()` в `finally` (а если `conn is None`, создавай и закрывай как раньше).
В `_ServeLease.cleanup` (строка 2450) замени:
```python
        if self.helper.poll() is None or True:
```
на:
```python
        if self.helper.poll() is None or _pid_alive(self.pgid):
```

### 2.3. Удержание 1 управляющего `control_conn` и проверка `status in (400, 404, 422)` в `_serve_one_attempt` (строки 2734–3081)
В `_serve_one_attempt`:
- Создай `control_conn: list[http.client.HTTPConnection | None] = [None]` и локальную функцию `_ctrl_http(method: str, path: str, body: dict[str, object] | None = None, timeout: float = 3.0) -> tuple[int, dict[str, object]]`, которая переиспользует `control_conn[0]` (создавая `http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)` при `None` и переоткрывая один раз при `(OSError, http.client.HTTPException)`), а в `finally:` `_serve_one_attempt` закрывает `control_conn[0]`.
- Используй `_ctrl_http` для управляющих вызовов в основном потоке (`GET /api/session/active`, `POST /api/session`, `POST .../form/.../cancel`, `POST .../permission/.../reply`, `POST .../interrupt`, `DELETE /api/session/...`). Для `_prompt_worker` (в отдельном потоке) оставь отдельный вызов `_serve_http(port, password, ...)`.
- На `GET /api/session/active`, `POST /api/session` и `sse_resp.status` добавь проверку:
  ```python
  if status in (400, 404, 422):
      raise ServeSecurityError(f"serve invalid request HTTP {status}")
  ```
  (и для `sse_resp.status in (400, 404, 422)` аналогично `raise ServeSecurityError(f"serve event HTTP {sse_resp.status}")`).

### 2.4. Повторы `unmapped` и `incomplete_step` в `_run_serve_stream_attempts` (строки 4781–4869)
В `_run_serve_stream_attempts`:
- Добавь `unmapped_retries = 0`, `incomplete_retries = 0` перед циклом `while True:`, а внутри цикла `unmapped_in_attempt: list[str] = []` и `emitted_tools_in_attempt = [0]`.
- В `on_tool(payload: dict[str, object]) -> None`:
  ```python
  part = _as_dict(payload.get("part"))
  mapped = _native_call_as_dsh(payload, tools) if emulate_tools else []
  if not mapped and emulate_tools and part.get("tool"):
      unmapped_in_attempt.append(str(part.get("tool")))
  for call in mapped:
      emitted_tools_in_attempt[0] += 1
      emit_tool_call(call)
  ```
  Также если `ToolCallParser` эмитит вызов из текста, учитывай это (например, сравнивая длину `collected_texts` или передавая обёртку `on_parsed_tool` вокруг `emit_tool_call`, которая увеличивает `emitted_tools_in_attempt[0]`).
- После `res.serve_health.record_success()` (строка 4866):
  - Добавь `usage_cur = result["usage"]` и накопление `self._serve_stream_usage` по ключам `("input", "output", "cached", "reasoning")`.
  - Если `emulate_tools and emitted_tools_in_attempt[0] == 0`:
    - Если `unmapped_in_attempt`:
      - Если `unmapped_retries < NATIVE_RETRY_LIMIT and attempts.allow_retry("unmapped")`: увеличь `unmapped_retries += 1`, обнови `current_prompt = _rewrite_tool_tags_for_model(_unavailable_tools_prompt(current_prompt, "".join(result["texts"]), unmapped_in_attempt, tools or [], model), model)` и `continue`.
      - Иначе вызови `emit_content(f"\n\n[opencode-zen-bridge: модель вызывала недоступный встроенный инструмент ({', '.join(unmapped_in_attempt)}); повторы исчерпаны]")` и `return True`.
    - Иначе вычисли:
      ```python
      signal = _incomplete_step_signal(
          "".join(result["texts"]),
          "".join(result["reasonings"]),
          tools or [],
          False,
          int(usage_cur.get("output") or 0),
          int(usage_cur.get("reasoning") or 0),
          tool_choice=None,
      )
      if signal and incomplete_retries < NATIVE_RETRY_LIMIT and attempts.allow_retry("incomplete_step"):
          incomplete_retries += 1
          attempts.signal = signal
          current_prompt = _rewrite_tool_tags_for_model(
              _incomplete_tool_step_prompt(
                  prompt, "".join(collected_texts), tools or [], None, model
              ),
              model,
          )
          continue
      ```

### 2.5. Учёт `attempts.attempt_done(True, False)` в `_serve_json_serve` (строки 5704–5706)
В `_serve_json_serve` замени:
```python
                if reason in ("first_event_timeout", "invalid_serve_event"):
                    res.serve_health.record_failure()
```
на:
```python
                if reason in ("first_event_timeout", "invalid_serve_event"):
                    res.serve_health.record_failure()
                else:
                    attempts.attempt_done(True, False)
```

## Шаг 3. Добавление 3 тестов в `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
1. В `FAKE_SERVE` в `do_POST` для `self.path == "/api/session"`:
   - если `os.environ.get("FAKE_SERVE_SESSION_STATUS") == "503"`, вызывай `self.send_json(503, {"error": "unavailable"}); return`
   - если `os.environ.get("FAKE_SERVE_SESSION_STATUS") == "400"`, вызывай `self.send_json(400, {"error": "bad request"}); return`
2. В `server._SERVE_ALLOWLIST` уже есть `"OPENCODE_ZEN_BRIDGE_TRANSPORT"`, либо в тесте временно расширяй `server._SERVE_ALLOWLIST` через `mock.patch.object(server, "_SERVE_ALLOWLIST", (*server._SERVE_ALLOWLIST, "FAKE_SERVE_SESSION_STATUS"))` и `server._STANDALONE_ENV_ALLOWLIST`.
3. В `TestServeTransportAndFakeServe` добавь 3 теста:
   - `test_auto_fallback_to_run_and_sticky_degradation(self) -> None`:
     Проверяет, что при `OPENCODE_ZEN_BRIDGE_TRANSPORT="auto"`, `server.SERVE_TEST_ELIGIBLE = True` и `FAKE_SERVE_SESSION_STATUS="503"` запрос в `auto` откатывается на `run` (ответ приходит от ветки `run` в `FAKE_SERVE`: `"Поздний ответ"`), а после 3 таких запросов `self.bridge.httpd.resilience.serve_health.is_degraded()` равен `True`.
   - `test_foreign_listener_rejected_and_startup_reaper(self) -> None`:
     Проверяет, что при `mock.patch.object(server, "_lsof_listener_pid", return_value=999998)` вызов `server._spawn_serve("att_foreign", server._serve_env(MODEL))` выбрасывает `server.ServeUnavailable` с `"foreign listener"`, и что `server._startup_reaper(lease_dir)` удаляет `lease-dead.json` с `{"parent_pid": 999999, "helper_pid": 0, "pgid": 0}`, оставляя `lease-alive.json` с `{"parent_pid": os.getpid(), "helper_pid": 0, "pgid": 0}`.
   - `test_serve_400_fails_closed_without_health_increment(self) -> None`:
     Проверяет, что при `FAKE_SERVE_SESSION_STATUS="400"` и `OPENCODE_ZEN_BRIDGE_TRANSPORT="serve"` запрос возвращает SSE error chunk (`"serve security failure"`), а `self.bridge.httpd.resilience.serve_health._failures` (или `is_degraded()`) остаётся `0` / `False`.

## Шаг 4. Форматирование и проверка `VER-004` + целевой `pytest`
1. Отформатируй изменённые диапазоны `server.py` (с `--range=1325:1-3085:999` и `--range=4745:1-5815:999`) и `tests/test_realtime_reasoning.py` через `uvx --from ruff==0.17.2 ruff format --config ruff.toml`.
2. Запусти команду `VER-004` из `architecture-packet.json` (проверка `ruff format --check`, `ruff check`, `basedpyright==1.40.2`, frozen sha256 `_run_env`, `_stream_google_sse`, `_execute_google_once`) и убедись, что она выходит с `0`.
3. Запусти:
```bash
cd /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge && \
  uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py tests/test_step_interruption.py tests/test_go_model_routing.py
```

## Шаг 5. План `after` и handoff (`coder-02`)
1. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-02.json` (все шаги `"DONE"`) и проверь:
```bash
python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" \
  /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-02.json \
  --expected-role coder --expected-stage after
```
2. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-02.json` (`round_id: "coder-02"`, `iteration: 2`, `role_plan.path: ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-02.json"`, `role_plan.sha256: "<sha256 plans/coder-02.json>"`, `role_plan.phase: "after"`), скопируй его в `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json` и проверь:
```bash
python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_handoff.py" \
  coder /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-02.json \
  --repo-root /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning
```

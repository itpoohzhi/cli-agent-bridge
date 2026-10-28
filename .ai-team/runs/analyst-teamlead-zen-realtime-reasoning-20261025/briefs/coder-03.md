# Бриф Coder (раунд `coder-03` — 1-строчный фикс базы отсчёта `status_next` в `_serve_one_attempt`): `zen-realtime-reasoning`

Скилл реализации (ровно один путь по канону):
`/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md`

Входы даны выше и ниже; на диск за ними вне рабочего клона не ходи; стартовый корень поиска ∈ `{$HOME, /Users/<user>, /}` запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни `ASK`.
**ВАЖНО:** Это минимальная однострочная правка! НЕ читай файлы целиком через `sed`/`cat` и НЕ прогоняй медленный 83-секундный сьют — прогони ТОЛЬКО 2 целевых теста (`test_slow_serve_gets_status_and_no_status_on_fast` и `test_stream_go_model_success_with_fake_launcher`, ~3 с) + `VER-004` (~5 с)!

## Уже известно
- `repo_root`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning`
- `branch`: `feature/zen-realtime-reasoning`
- `run_dir`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025`
- `prior_findings`:
  - В Clean-Room L2 (`l2-green-ver001-pytest.log`) 399 из 400 тестов прошли (`test_go_model_routing.py` полностью зелёный!).
  - Упал ровно 1 тест: `tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_slow_serve_gets_status_and_no_status_on_fast` с `AssertionError: 1.04001908400096 not less than or equal to 1.0`.
  - Причина: в `_serve_one_attempt` (`server.py` строка 2890) написано `status_next = prompt_send_start + FIRST_STATUS_DELAY_S`, а `prompt_send_start` берётся ПОСЛЕ `_spawn_serve`, `GET /api/session/active`, `POST /api/session` и `GET /api/event` (~0.38–0.42 с). Поэтому `0.40 + 0.65 = 1.05 с > 1.0 с` от начала HTTP-запроса `t0`!
  - Если заменить строку 2890 на `status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25)`, то:
    1. Медленный `serve` (`__slow__`, задержка 1.4 с) получает первый статус `[мост]` ровно через `max(0.65, 0.40 + 0.25) = 0.65 с <= 1.0 с` от начала запроса `t0`.
    2. Быстрый `serve` (первая дельта приходит через `~0.02–0.05 с` после `prompt_send_start`) завершает ожидание первого токена задолго до `prompt_send_start + 0.25 с`, поэтому НЕ получает ложного статуса `[мост]`.
    3. Legacy `run` (`FIRST_STATUS_DELAY_S = 0.65`) вообще не затрагивается (`test_go_model_routing.py` остаётся зелёным).

## Шаг 1. Запиши `plans/coder-03.before.json` и проверь `--phase before`
Создай `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-03.before.json` (`iteration: 3`, `plan_kind: "delta"`, `phase: "before"`, `parent_plan: ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-02.json"`, `trigger_ids: ["L2-SLOW-SERVE-STATUS-T0"]`, шаги `RP-01..RP-03` со статусом `"PENDING"`) и проверь:
```bash
python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" \
  /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-03.before.json \
  --phase before
```

## Шаг 2. Однострочная правка в `bridges/opencode-zen-bridge/server.py` (строка 2890)
Замени в `bridges/opencode-zen-bridge/server.py`:
```python
        status_next = prompt_send_start + FIRST_STATUS_DELAY_S
```
на:
```python
        status_next = max(t0 + FIRST_STATUS_DELAY_S, prompt_send_start + 0.25)
```
И отформатируй только строки `2885:1-2895:999`:
```bash
uvx --from ruff==0.17.2 ruff format --config ruff.toml --no-cache --range=2885:1-2895:999 bridges/opencode-zen-bridge/server.py
```

## Шаг 3. Быстрая проверка (2 теста + `VER-004`)
```bash
cd /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge && \
  uvx pytest -q -p no:cacheprovider \
    tests/test_realtime_reasoning.py -k "test_slow_serve_gets_status_and_no_status_on_fast or test_ac026_realtime_chunks_before_upstream_end or test_frozen_slices_hashes" \
    tests/test_go_model_routing.py -k "test_stream_go_model_success_with_fake_launcher"
```

## Шаг 4. Запиши `plans/coder-03.json` (`--phase after`) и `handoffs/coder-03.json` + `coder.json`
1. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-03.json` (`phase: "after"`, шаги `"DONE"`), проверь `validate_role_plan.py --phase after` и вычисли его `sha256`.
2. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-03.json` (`round_id: "coder-03"`, `iteration: 3`, `role_plan.path: ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-03.json"`, `role_plan.sha256: "<sha256>"`, `role_plan.phase: "after"`), скопируй в `coder.json` и проверь:
```bash
python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_handoff.py" \
  coder /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-03.json \
  --role-plan /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-03.json \
  --root /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning
```

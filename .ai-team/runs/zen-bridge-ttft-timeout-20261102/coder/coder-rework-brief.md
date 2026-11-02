# Бриф Coder: Rework по замечаниям Совета Тимлидов (Cycle 1 -> 2)

Скилл роли: `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md`

Ты — Coder (`claude-sonnet-5-5-high` через `claude -p`).
Официальный артефакт `panel-rework-brief.json` выпущен ролью `panel-rework-summarizer`, полностью проверен и валидирован:
`/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/zen-bridge-ttft-timeout-20261102/handoff/panel-rework-brief.json`

## Задачи Coder по brief:

### 1. RW-002 (BLOCKING, F-002): Точка отсчёта TTFT на повторных попытках
- **Файл:** `bridges/opencode-zen-bridge/server.py`
- В стриминговом watchdog (строки ~8370–8385): убрать привязку TTFT к `request_t0` при отсутствии текста. Считать TTFT от начала текущей попытки (`attempt_start`), чтобы повторная попытка после очереди или сбоя старта не отсекалась мгновенно старым `request_t0`.
- В классе `Run` (строка ~6698): выровнять семантику точки отсчёта TTFT с началом попытки без деления по `total_spawns <= 1`.
- Добавить модульный тест на retry-сценарий (повторная попытка после задержки >25с не обрывается по TTFT).

### 2. RW-003 (BLOCKING, F-003): Защита Idle 15с при исполнении тулов
- **Файл:** `bridges/opencode-zen-bridge/server.py`
- В `_serve_one_attempt` (строка ~4825): проверка idle-таймаута (`now - last_token_at >= idle_timeout`) НЕ должна срабатывать, пока выполняется инструмент (когда есть активные вызовы в `tool_state.tools` / `pending_step_calls` или пока не завершён шаг тула). Либо во время ожидания работы тула обновлять активность или проверять `not tool_state.tools`.
- В стриминговом watchdog (строка ~8382): не обрывать по idle 15с во время выполнения инструмента/сабагента.
- Добавить тесты на длительное выполнение инструмента (>15с) без обрыва по Idle.

### 3. Неблокирующие улучшения (FU-001, FU-002):
- **FU-001 (F-004):** В `_zen_idle_timeout` и `_zen_total_timeout` (строки ~369, 376): убрать зависимость от `_zen_ttft_timeout >= TIMEOUT_S`. Проверять целевую модель напрямую (`model in models and len(prompt.encode('utf-8')) > threshold`), чтобы оператор мог независимо поднять TTFT, не теряя Idle/Total.
- **FU-002 (F-005):** В `_attempts_t0`: использовать ленивое вычисление default (`if hasattr(attempts, "t0"): return attempts.t0; return attempts.deadline - ...`).

### 4. RW-001 (BLOCKING, F-001): Актуализация и полнота package.md
- **Файл:** `.ai-team/runs/zen-bridge-ttft-timeout-20261102/teamlead/package.md`
- После внесения правок пересобрать Раздел 5 «Полный Git Diff» пакета так, чтобы он содержал 100% фактического `git diff` по всем файлам (`server.py` и `tests/test_bridges_speedup_resilience.py`), обновить статистику строк в Разделе 3 и матрицу тестов в Разделе 4.

## Критерии приёмки
1. Все тесты в `tests/test_bridges_speedup_resilience.py` проходят зелёным:
   `PYTHONPATH=. .venv/bin/pytest tests/test_bridges_speedup_resilience.py -v` (exit 0).
2. Смежные тесты проходят зелёным:
   `PYTHONPATH=. .venv/bin/pytest tests/test_request_attribution.py tests/test_bridge_strict.py -v` (exit 0).
3. Раздел 5 `package.md` полностью синхронизирован с реальным `git diff`.

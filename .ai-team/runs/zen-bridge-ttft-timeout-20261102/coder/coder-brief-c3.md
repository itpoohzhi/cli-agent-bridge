# Бриф Coder: Rework по замечаниям Совета Тимлидов (Cycle 2 -> 3)

Скилл роли: `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md`

Ты — Coder (`claude-sonnet-5-5-high` через `claude -p`).
Официальный артефакт `panel-rework-brief-c2.json` выпущен ролью `panel-rework-summarizer`, полностью проверен и валидирован:
`/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/zen-bridge-ttft-timeout-20261102/handoff/panel-rework-brief-c2.json`

## Задачи Coder по brief:

### 1. RW-001 (BLOCKING, F-007, F-013): Учёт tool-событий в TTFT serve-пути
- **Файл:** `bridges/opencode-zen-bridge/server.py`
- В `_serve_one_attempt` (строки ~5060–5080): при получении `etype == "tool_event"` (включая `session.tool.input.started`, `session.tool.input.delta`, `session.tool.called`):
  если `result["first_token_at"] is None`, устанавливать:
  `result["first_token_at"] = time.monotonic()`
  `result["ttft_ms"] = int(((result["first_token_at"] or 0.0) - t0) * 1000)`
- В условии проверки TTFT (строка ~4865):
  `if result["first_token_at"] is None and not tool_state.has_active() and now - prompt_send_start >= ttft_timeout:`
  (активный инструмент не должен обрываться по TTFT, если он уже начал генерацию/исполнение).
- Добавить модульный serve-тест, где модель сразу вызывает tool без предварительного reasoning, и подтвердить, что TTFT не обрывает генерацию аргументов инструмента.

### 2. RW-004 (BLOCKING, F-010, F-011, F-012): Устойчивая идентичность тулов в `_ToolActivity`
- **Файл:** `bridges/opencode-zen-bridge/server.py`
- В классе `_ToolActivity` (строка ~406): не коллапсировать параллельные/повторные вызовы одного инструмента. Использовать уникальный ключ: `callID or id or f"{tool}_{id(event)}"` или вести счетчик активных вызовов, чтобы завершение одного вызова не снимало защиту с остальных активных вызовов.

### 3. RW-002 (BLOCKING, F-002, F-015): Документирование константы в `test_passthrough_deadline_env`
- **Файл:** `tests/test_bridges_speedup_resilience.py` (строка 65)
- Добавить комментарий к `(10, 300, 420, 12)`: `# Note: DEFAULT_IDLE_TIMEOUT_S = 300.0 on HEAD in adapters/passthrough_adapter.py:92 (commit 0215805227)`.

### 4. Добавление негативных тестов (F-004, F-009, FU-002):
- **Файл:** `tests/test_bridges_speedup_resilience.py`
- Добавить негативный тест `test_zen_stream_ttft_timeout_returns_504`: эмулировать зависший провайдер (0 токенов за TTFT) и убедиться в возврате честного HTTP 504 / terminal SSE error с `timeout_error`.
- В тесте `test_zen_stream_idle_timeout_after_first_token` добавить проверку: при срабатывании Idle поток содержит сообщение об ошибке таймаута и не содержит успешного `data: [DONE]`.

### 5. RW-003 (BLOCKING, F-001, F-008, F-014): Очистка и пересборка package.md
- **Файл:** `.ai-team/runs/zen-bridge-ttft-timeout-20261102/teamlead/package.md`
- Полностью удалить из Раздела 4 любые упоминания нерелевантных тестов посторонних каталогов/модулей (не относящихся к diff).
- Оставить чистую матрицу тестов только трех файлов пакета и смежных контрактов:
  - `tests/test_bridges_speedup_resilience.py`
  - `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`
  - `tests/test_request_attribution.py`
  - `tests/test_bridge_strict.py`
  - `tests/test_opencode_zen_bridge.py`
  - `bridges/opencode-zen-bridge/tests/test_zen_catalog.py`
- Синхронизировать Раздел 5 «Полный Git Diff» с итоговым состоянием `git diff`.

## Критерии приёмки
1. `PYTHONPATH=. .venv/bin/pytest tests/test_bridges_speedup_resilience.py -v` (exit 0, 100% pass).
2. `PYTHONPATH=. .venv/bin/pytest bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py -k test_serve_long_tool_not_cut_by_idle -v` (exit 0).
3. `PYTHONPATH=. .venv/bin/pytest tests/test_request_attribution.py tests/test_bridge_strict.py tests/test_opencode_zen_bridge.py -v` (exit 0).
4. `package.md` содержит 100% чистый отчёт без посторонних логов.

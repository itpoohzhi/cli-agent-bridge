# Бриф реализации для роли Coder (Точечная доработка по замечаниям J3-001, J3-002, MINOR-2)

⚠️ **КРИТИЧЕСКАЯ ИНСТРУКЦИЯ (LEAF SUBAGENT / AGENT_SPAWN_DEPTH=1):**
- Вы — конечный исполнитель роли **Coder** (`ai-sdlc/coder`), запущенный главным оркестратором.
- **НЕ открывайте** новый контур `cel`, **НЕ запускайте** сабагентов.
- Скилл роли (ровно один путь): `/Users/aazhiry1/Мой диск/skils/ai-sdlc/coder/SKILL.md`.

## 1. Задача: 3 точечные правки в `bridges/agy-bridge/server.py` и `tests/test_agy_bridge_resilience.py`

В рабочем дереве `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning`:

### Правка 1 (`J3-001` / `F-005` — запрет эвристического раннего выхода `planner_final` в `_drain_post_eof`):
- В `bridges/agy-bridge/server.py` в методе `_TranscriptTail._drain_post_eof` (около строк 1954–2002):
  - Удалить ветку раннего выхода:
    ```python
    if self.final_planner and quiet >= 2:
        exit_kind = "planner_final"
        break
    ```
    и счётчик `quiet` (и обновить docstring `_drain_post_eof`: досрочный выход после `DRAIN_MIN_S` — ТОЛЬКО по `self.end_marker` (`exit_kind = "end_turn"`) или `self.stop_event.is_set()` (`exit_kind = "stop"`), а при `PLANNER_RESPONSE` без `END_TURN`/`TURN_COMPLETE` выдерживается полное окно `DRAIN_WINDOW_S = 0.35 s` (`exit_kind = "window"`)).
- В `tests/test_agy_bridge_resilience.py` (около строки 2389):
  - Обновить тест `test_ao03_planner_final_with_two_quiet_selects_exits_early` (оставить имя метода или добавить рядом/обновить тело, чтобы все существующие тесты проходили): проверить, что при `PLANNER_RESPONSE` и двух тихих `SELECT` без `END_TURN` раннего выхода `planner_final` НЕ происходит — выдерживается полное окно `DRAIN_WINDOW_S = 0.35 s` (`self.assertGreaterEqual(elapsed, 0.34)`, `self.assertIn("outcome=complete pending_steps=0 exit=window", log)`).

### Правка 2 (`J3-002` — жёсткое соблюдение потолка `MAX_STEPS_TRACKED = 128` в `_TranscriptTail._state`):
- В `bridges/agy-bridge/server.py` в методе `_TranscriptTail._state` (около строк 1663–1679):
  - Сейчас при `len(self.seen) >= MAX_STEPS_TRACKED` и пустом `evictable` вызывается только `self._sqlite_off("seen_cap")`, после чего `self.seen[idx] = state` увеличивает `len(self.seen)` сверх `MAX_STEPS_TRACKED` (128).
  - Исправить ветку `else:` так, чтобы после `self._sqlite_off("seen_cap")` также вытеснялся самый старый ключ `del self.seen[min(self.seen)]`, гарантируя инвариант `len(self.seen) <= MAX_STEPS_TRACKED` всегда.
- В `tests/test_agy_bridge_resilience.py`:
  - Добавить (или расширить) unit-тест `test_seen_cap_evicts_oldest_when_no_finalized_below_watermark`, проверяющий, что при заполнении `seen` более чем 128 шагами без вытесняемых финализированных шагов вызывается `_sqlite_off("seen_cap")` И `len(tail.seen) <= 128`.

### Правка 3 (`MINOR-2` — атомарное чтение `_agy_binary_identity()` под `_sqlite_guard_lock` в `_compat_promote`):
- В `bridges/agy-bridge/server.py` в функции `_compat_promote` (около строк 997–1006):
  - Перенести вызов `current = _agy_binary_identity()` внутрь блока `with _sqlite_guard_lock:`.

## 2. Проверки и обновление артефактов Coder
1. Прогнать `ruff check`, `ruff format --check` (при необходимости `ruff format`), `basedpyright bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py`, `pytest -q tests/test_agy_bridge_resilience.py` и `/usr/bin/python3 -m unittest discover -s tests -p "test_*agy*.py"`.
2. Обновить SHA-256 и описания в:
   - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/handoffs/coder-01.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/coder.json`
   - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/receipts/coder.json`
   и прогнать `validate_handoff.py` (`--role coder`).

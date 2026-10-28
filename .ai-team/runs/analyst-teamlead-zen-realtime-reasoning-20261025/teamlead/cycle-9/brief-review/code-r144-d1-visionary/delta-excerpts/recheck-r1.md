# Механический RECHECK после R1 Совета Тимлидов по коду (цикл 9, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Проверяемый артефакт: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202`)
- Длина файлов кандидата: `server.py` = `8295` строк, `tests/test_realtime_reasoning.py` = `3629` строк, `tests/test_step_interruption.py` = `1088` строк.
- Дельта `coder-12` (Цикл 9 относительно Цикла 8 `coder-11`): в `server.py` изменены только `_drain_serve_step_usage` / `_finish_serve_tool_step` (`3345-3530`), `_serve_accumulated_bytes` / лимит очереди (`3154-3175`, `3445-3460`), ре-чек дедлайна до `note_spawn` (`5540-5590`, `6770-6820`) и ветка `state == "timeout"` в JSON (`7945-7965`). Строки `_strip_interrupted` (`5708`, `5988`, `7005`), `_open_serve_events` (`3232-3240`) и `_LockedWfile.write` (`5835`) не менялись в Цикле 9 и присутствовали без замечаний в предыдущих циклах (`council.md` §3 «Diff-scope повторного цикла»).

RECHECK F-001 (skeptic skeptic-F-001, blocking): `server.py:3373` → `if data.get("sessionID") != session_id or (` | F-001
RECHECK F-002 (visionary visionary-F-001, blocking): `server.py:3373` → `if data.get("sessionID") != session_id or (` | **F-001 — [pre-existing] Потеря ошибок и управляющих событий при дочитывании шага.**
RECHECK F-003 (visionary visionary-F-002, blocking): `server.py:3390` → `on_tool(done[1])` | **F-002 — Неподтверждённые tool calls переживают неуспешную попытку.**
RECHECK F-004 (visionary visionary-F-003, blocking): `server.py:5708` → `rtext = _strip_interrupted(rtext)` | **F-003 — [pre-existing] Изменяются модельные байты reasoning.**
RECHECK F-005 (visionary visionary-F-004, non-blocking): проверка по полному тексту `package.md` (`candidate.diff` / `verification-traceability.md` / `execution-evidence.md`) | **F-004 — Устаревшие ссылки матрицы прослеживаемости.**
RECHECK F-006 (visionary visionary-F-005, blocking): `server.py:3232` → `"127.0.0.1",` | **F-005 — [pre-existing] Не выполняется бюджет вспомогательного I/O.**
RECHECK F-007 (visionary visionary-F-006, blocking): `server.py:3154` → `self.tools: dict[str, _ToolItem] = {}` | **F-006 — [pre-existing] Байтовый предел не охватывает накопление native-инструментов.**
RECHECK F-008 (visionary visionary-F-007, blocking): `server.py:5835` → `return int(self._inner.write(data) or 0)` | **F-007 — [pre-existing] Блокирующая запись клиенту обходит watchdog и общий deadline.**

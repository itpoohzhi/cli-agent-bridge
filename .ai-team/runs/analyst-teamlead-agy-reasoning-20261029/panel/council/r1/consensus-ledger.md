# Консенсус-леджер находок Совета Тимлидов по коду — до дебатов `D1` (после `R1` `panel/council/r1`)

- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/panel/council/r1` (`panel-proof.json` `verify_panel_proof exit=0`)
- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/package.md` (`sha256=7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b`)

---

## Карточки открытых находок R1 (вход для дебатов D1)

### F-001
- origin: Seat 3 (`gpt-6.1-sol-high` C3-001)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: При превышении `MAX_STEPS_TRACKED = 128` шагов в рамках одного хода и одновременном перезаписывании/уменьшении размера `transcript_full.jsonl` (`size < self._offset`) вытесненный из `self.seen` шаг текущего хода при повторном чтении транскрипта с нуля получит новый `_StepState` (`delivered_len=0`). По `EVD-031` один ход `agy` порождает `1–15` шагов (на порядок ниже `128`), `base_idx` отсекает прошлые ходы, при `seen_cap` SQLite отключается, а `transcript_full.jsonl` у `agy` append-only. Рекомендация RECHECK для D1: `AMEND F-001 — priority=non-blocking` (зафиксировать как неблокирующий остаточный риск / бэклог-улучшение `evicted_watermark` в разделе Б итогового вердикта).

### F-002
- origin: Seat 3 (`gpt-6.1-sol-high` C3-002)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: В `_read_transcript` (`server.py:1614-1624`) `self._offset` сдвигается после получения `\n`; если `agy` дописывает новые байты к незавершённой строке без `\n` на нескольких тиках, незавершённый префикс перечитывается с `self._offset`. В R1 классифицировано как `MAJOR` (`non-blocking`), общий объём выдачи ограничен `MAX_REASONING_BYTES_PER_TURN = 2 MiB`. Рекомендация RECHECK для D1: `AGREE F-002` / `AMEND F-002 — priority=non-blocking`.

### F-003
- origin: Seat 3 (`gpt-6.1-sol-high` C3-003)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: Проверка `_sqlite_permitted()` и вызов `interrupt_active_query()` в `_select_rows` (`server.py:1853-1859`) выполняются после возврата из `conn.execute(_STEPS_SQL, ...)` (где `busy_timeout = 50 ms` и `LIMIT 16` строк `<= 256 KiB` ограничивают время `SELECT` миллисекундами, а при закрытии хода `Run.close()` вызывает `interrupt_active_query()` из внешнего потока). В R1 классифицировано как `MAJOR` (`non-blocking`), `AO-09` подтверждает реакцию `<= 1.30 s` при норме `REQ-011 <= 5.0 s`. Рекомендация RECHECK для D1: `AGREE F-003` / `AMEND F-003 — priority=non-blocking`.

### F-004
- origin: Seat 3 (`gpt-6.1-sol-high` C3-004)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: Уточнить в итоговом вердикте Совета, что живая проверка `VER-011` (`L3`) выполняется строго после `ACCEPT` Совета и до открытия/вливания MR (по Шагу 5 `teamlead-gate`), а `VER-013` подтверждает отсутствие новых регрессий (`974` теста кандидата против `899` базовых при тех же `2` внешних baseline-падениях в `test_muse_bridge_killpg.py`). В R1 классифицировано как `MINOR` (`non-blocking`). Рекомендация RECHECK для D1: `AGREE F-004` / `AMEND F-004 — priority=non-blocking`.

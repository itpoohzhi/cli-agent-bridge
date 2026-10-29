# Перепроверка ссылок R1 (`recheck-r1.md`) — Совет Тимлидов по коду (`COUNCIL`, после `panel/council/r1`)

- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/panel/council/r1` (`panel-proof.json` `verify_panel_proof exit=0`, голоса R1: Seat 1 `gemini-4-argon-high` = `ACCEPT`, Seat 2 `muse-wonder-full-1.0` = `ACCEPT`, Seat 3 `gpt-6.1-sol-high` = `NEEDS_WORK`)
- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/package.md` (`sha256=7d4f3ee38549312817f33a0cc6b82ef02f69a62f9d764777b3d84d63e460838b`)

RECHECK F-001 (Seat 3 `C3-001` — составной теоретический сценарий: `>128` шагов в рамках одного хода + вытеснение из `seen` + усечение файла `transcript_full.jsonl` посередине того же хода `size < self._offset`):
Проверка по `bridges/agy-bridge/server.py:1609-1615, 1648-1650, 1667-1678` и `EVD-031`:
1) Фильтр `if idx is not None and idx < self.base_idx: return` (`server.py:1649`) отсекает все шаги предыдущих ходов сессии; словарь `self.seen` хранит только шаги текущего хода (`idx >= base_idx`). По `EVD-031` один ход `agy` создаёт `1–15` шагов (потолок `MAX_STEPS_TRACKED = 128` превышает реальное число шагов хода на порядок).
2) Даже при гипотетическом превышении 128 шагов внутри одного хода ветка `self._sqlite_off("seen_cap")` (`server.py:1676`) немедленно отключает чтение из SQLite, а `transcript_full.jsonl` у `agy` является строго append-only логом (ветка `size < self._offset` на строке `1609` срабатывает только если файл транскрипта был физически перезаписан/усечён внешним процессом одновременно с `>128` шагами одного хода).
3) Ни в одном из 97 тестов `VER-003`/`VER-012` и стресс-оракуле `VER-010` (`tc93`) расхождений дедупликации нет; сценарий `>128 шагов за один ход + одновременное усечение файла транскрипта` является теоретическим краевым случаем за пределами эксплуатационного профиля `agy`.
Рекомендация RECHECK для D1: `AMEND F-001 — priority=non-blocking` (зафиксировать как неблокирующий остаточный риск / бэклог-улучшение `min_evicted_idx` без блокировки приёмки).

RECHECK F-002 (Seat 3 `C3-002` — накопление `_buf` в `_read_transcript` при длительной неполной строке без `\n`):
В R1 судья Seat 3 уже присвоил этой находке неблокирующий класс `MAJOR` (`non-blocking`). Проверка по `server.py:1609-1628` и `2120-2125`: при неизменном размере файла строка `if size == self._offset: return` (`server.py:1614`) предотвращает повторное чтение; `agy` записывает JSONL-строку одной операцией записи с завершающим `\n`, а общий объём выдаваемого мышления на ход жёстко ограничен `MAX_REASONING_BYTES_PER_TURN = 2 MiB`.
Рекомендация RECHECK для D1: `AGREE F-002` / `AMEND F-002 — priority=non-blocking`.

RECHECK F-003 (Seat 3 `C3-003` — прерывание выполняющегося `SELECT` при переключении kill-switch `SQLITE_REASONING_ENABLED=false`):
В R1 судья Seat 3 уже присвоил этой находке неблокирующий класс `MAJOR` (`non-blocking`). Проверка по `server.py:1098-1102, 1508-1517, 1851-1877` и `VER-010` (`AO-09`, `tc93`): соединение открывается с `timeout=0.05` (`50 ms`) и `PRAGMA busy_timeout = 50`, запрос `_STEPS_SQL` читает `LIMIT 16` строк `<= 256 KiB` по первичному ключу (`p95 <= 5 ms`), проверка `_sqlite_permitted()` выполняется на каждой строке результата (`server.py:1854`) с вызовом `interrupt_active_query()`, а при закрытии хода `Run.close()` вызывает `interrupt_active_query()` из внешнего потока (`server.py:2305`). Время реакции kill-switch составляет `<= 1.30 s` при требовании `REQ-011 <= 5.0 s`.
Рекомендация RECHECK для D1: `AGREE F-003` / `AMEND F-003 — priority=non-blocking`.

RECHECK F-004 (Seat 3 `C3-004` — уточнение формулировки `VER-011` и `VER-013` в таблице трассируемости):
В R1 судья Seat 3 присвоил находке класс `MINOR` (`non-blocking`). В `verifier.json` и `reverse-spec.md` уже явно зафиксировано, что `VER-011` (`L3`) выполняется строго после `ACCEPT` Совета и до открытия/вливания MR, а `VER-013` подтверждает `0` новых регрессий при сравнении `974` тестов кандидата с `899` тестами базового коммита (`2` идентичных внешних baseline-падения в `test_muse_bridge_killpg.py`).
Рекомендация RECHECK для D1: `AGREE F-004` / `AMEND F-004 — priority=non-blocking`.

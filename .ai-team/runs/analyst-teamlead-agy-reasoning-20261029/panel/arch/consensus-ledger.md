# Consensus Ledger — Architecture Review Panel (`ARCH_PANEL` R1 + D1)

- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Artifact:** `architecture/architecture-packet.json` (`sha256=62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab`)
- **R1 Round Directory:** `panel/arch/r1` (`round_kind=blind`, `prior_ledger_sha256=bde31a070463c7a47da5cc474d16544616cb0170b76b793b7c7c67adae402fff`)
- **D1 Round Directory:** `panel/arch/r2` (`round_kind=d1`, `constrained_mode=3of3_derangement`)
- **D1 Seats:**
  - `Seat 1`: `gpt-6.1-sol-high` (`OpenAI`, `codex`) — `ОБЩИЙ ВЕРДИКТ: NEEDS WORK` (`POSITIONS: 10/10`, `FINDINGS_COMPLETE: 2`)
  - `Seat 2`: `gemini-4-argon-high` (`Google`, `agy`) — `ОБЩИЙ ВЕРДИКТ: PASS` (`POSITIONS: 10/10`, `FINDINGS_COMPLETE: 0`)
  - `Seat 3`: `muse-wonder-full-1.0` (`Meta`, `muse`) — `ОБЩИЙ ВЕРДИКТ: PASS` (`POSITIONS: 10/10`, `FINDINGS_COMPLETE: 0`)

## Summary Table (R1 -> D1)

| ID | Seat 1 (`gpt-6.1-sol-high`, OpenAI) | Seat 2 (`gemini-4-argon-high`, Google) | Seat 3 (`muse-wonder-full-1.0`, Meta) | Итоговый приоритет (outcome) | Статус (status) |
|---|---|---|---|---|---|
| F-001 | AMEND (non-blocking) | AMEND (non-blocking) | AMEND (non-blocking) | non-blocking | AGREED |
| F-002 | AMEND (non-blocking) | AMEND (non-blocking) | AMEND (non-blocking) | non-blocking | AGREED |
| F-003 | AMEND (non-blocking) | AMEND (non-blocking) | AMEND (non-blocking) | non-blocking | AGREED |
| F-004 | AGREE (non-blocking) | AGREE (non-blocking) | AMEND (non-blocking) | non-blocking | AGREED |
| F-005 | AMEND (non-blocking) | AMEND (non-blocking) | AMEND (non-blocking) | non-blocking | AGREED |
| F-006 | AGREE (blocking) | AMEND (non-blocking) | AMEND (non-blocking) | non-blocking | DOWNGRADED_BY_MAJORITY |
| F-007 | AMEND (non-blocking) | AMEND (non-blocking) | AMEND (non-blocking) | non-blocking | AGREED |
| F-008 | AGREE (blocking) | AMEND (non-blocking) | AMEND (non-blocking) | non-blocking | DOWNGRADED_BY_MAJORITY |
| F-009 | AGREE (non-blocking) | AGREE (non-blocking) | AGREE (non-blocking) | non-blocking | AGREED |
| F-010 | DISPUTE (invalid) | DISPUTE (invalid) | WITHDRAW (invalid) | excluded | WITHDRAWN |

### F-001
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `architecture/architecture-packet.json` (`AD-001.details.dedup_and_emit`, `AD-001.details.watermark_resume`, `AO-08`, `AO-12` vs `RISK-002`, `RISK-004`)
- issue: В ненормативных карточках `RISK-002` и `RISK-004` оставались старые формулировки («отдаёт только невыданный хвост» при divergence и «из транскрипта со статусом 8 при ошибке SQLite» на resume), тогда как нормативный `AD-001` замораживает выдачу шага при divergence и требует `turn_mode="OFF"` при неуспехе pre-spawn SQLite-якоря на resume.
- fix: Строго следовать нормативному `AD-001`, `AO-08` и `AO-12`: после divergence — ноль последующих эмитов этого шага из обоих источников (`diverged=True`); на resumed-ходе без успешного pre-spawn SQLite-якоря (`anchored=False`) — `turn_mode="OFF"` на весь ход.
- votes: R1 seat1=RAISE(blocking) | D1 seat1=AMEND(non-blocking) | D1 seat2=AMEND(non-blocking) | D1 seat3=AMEND(non-blocking)

### F-002
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `architecture/architecture-packet.json` (`AD-005`, `AO-01`, классификация схемной ошибки vs `cold-open`)
- issue: На первом `SELECT` распознанная схемная ошибка (`no such table: steps` / `no such column`) должна иметь приоритет над классификацией транзиентного `cold-open` и увеличивать `consecutive_failures` circuit breaker'а.
- fix: Проверять текст/тип схемной ошибки (`no such table` / `no such column`) ДО ветки `cold-open`: три хода с отсутствующей таблицей/колонкой переводят breaker в `OPEN`, а три хода с ещё не созданным файлом БД (`unable to open database file` до создания БД) оставляют breaker `CLOSED` (`AO-01`).
- votes: R1 seat1=RAISE(blocking) | D1 seat1=AMEND(non-blocking) | D1 seat2=AMEND(non-blocking) | D1 seat3=AMEND(non-blocking)

### F-003
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `architecture/architecture-packet.json` (`AD-001.details.seen_state`, `dedup_and_emit`, `compat`, `AO-10`, `AO-12`)
- issue: Уточнение инвариантов `seen_state`, `poll_watermark` и canary-поколения `binary_identity` при работе двух источников (SQLite и `transcript_full.jsonl`).
- fix: В Stage 3 `Coder` реализовать: (1) ранний выход `if state["finalized"]: continue/return` в обоих путях и обновление `delivered_*` при выдаче из транскрипта; (2) монотонное продвижение `poll_watermark` через непрерывный префикс завершённых (`status=3` / `finalized`) шагов (включая пустые/non-thinking шаги, чтобы окно `>16` шагов не стопорило `LIMIT 16`); (3) перевод `SHADOW -> LIVE` только при совпадении `turn_binary_identity == current_binary_identity` под `_sqlite_guard_lock` (`AO-10`, `AO-12`).
- votes: R1 seat1=RAISE(blocking) | D1 seat1=AMEND(non-blocking) | D1 seat2=AMEND(non-blocking) | D1 seat3=AMEND(non-blocking)

### F-004
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `architecture/architecture-packet.json` (`AD-001.details.watermark_resume`, `AD-004`, `_active_cid_owners`)
- issue: При получении свежего `cid` из события `init` регистрация владельца `_active_cid_owners[cid] = turn_id` должна выполняться атомарно под `_session_store_lock` до привязки SQLite-источника.
- fix: В `bind(cid)` / обработке `init` атомарно под `_session_store_lock` проверять и регистрировать `_active_cid_owners[cid] = turn_id` (при коллизии с чужим активным `turn_id` — не перезаписывать чужого владельца и переводить SQLite для текущего хода в `OFF`), а в `finally` освобождать только при `_active_cid_owners.get(cid) == turn_id`.
- votes: R1 seat1=RAISE(non-blocking) | D1 seat1=AGREE(non-blocking) | D1 seat2=AGREE(non-blocking) | D1 seat3=AMEND(non-blocking)

### F-005
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `architecture/architecture-packet.json` (`AD-002`, `_pump`, `_drain_post_eof`, `AO-03`, `AO-11`)
- issue: Терминальный путь `_pump` и финальный drain после EOF должны гарантировать ровно один терминальный кортеж `("done", ...)` и выдерживать полное окно `DRAIN_WINDOW_S = 0.35 s` без эвристического раннего выхода.
- fix: (1) Обернуть тело `_pump` в `try/finally`, гарантирующий ровно один идемпотентный вызов `_close_and_put_done(run, ...)` при любом исключении; (2) при вызове `conn.interrupt()` под локом соединения подавлять `sqlite3.ProgrammingError`/`OperationalError` на уже закрытом дескрипторе; (3) в `_drain_post_eof` выдерживать полное окно `DRAIN_WINDOW_S = 0.35 s` (с настраиваемым `AGY_BRIDGE_DRAIN_MIN` / `AGY_BRIDGE_TRANSCRIPT_GRACE`) без досрочного выхода по «PLANNER_RESPONSE + два пустых тика» (`AO-03`, `AO-11`).
- votes: R1 seat1=RAISE(blocking) | D1 seat1=AMEND(non-blocking) | D1 seat2=AMEND(non-blocking) | D1 seat3=AMEND(non-blocking)

### F-006
- priority: non-blocking
- status: DOWNGRADED_BY_MAJORITY
- outcome: non-blocking
- location: `architecture/architecture-packet.json` (`AD-006`, `AO-09`, `REQ-011`, kill-switch `SQLITE_REASONING_ENABLED`)
- issue: Обеспечение верхней границы времени реакции runtime kill-switch (`<= 2.0 s` в гейте L2 `VER-010`, `<= 5.0 s` по `REQ-011`).
- fix: Перепроверять `_is_sqlite_reasoning_enabled()` на каждой итерации и перед обработкой каждой строки `SELECT`; при обнаружении отключения флага немедленно вызывать `conn.interrupt()` под локом соединения, закрывать read-only соединение и писать диагностическую строку `sqlite-off reason=flag` (`AO-09`).
- votes: R1 seat1=RAISE(blocking) | D1 seat1=AGREE(blocking) | D1 seat2=AMEND(non-blocking) | D1 seat3=AMEND(non-blocking)

### F-007
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `tests/test_agy_bridge_resilience.py` (`VER-003..VER-012`)
- issue: Совместимость всех 52 новых тестов (`TC-*`, `AO-01..AO-12`, `tc93`) одновременно с `pytest==9.0.3` и `/usr/bin/python3 -m unittest`.
- fix: Оформить все 52 новых теста (`TC-01..12, 20, 21, 23, 24, 30..33, 40..44, 50, 51, 60..63, 70..72, 80..82, 91, 92`, `AO-01..AO-12`, `tc93` / `l2_harness`) как отдельные методы классов `unittest.TestCase` в `tests/test_agy_bridge_resilience.py` без `skip`, с содержательными проверками, стресс-профилем `16 x 256 KiB` в `tc93` и без `# type: ignore` / `# pyright: ignore`.
- votes: R1 seat1=RAISE(blocking) | D1 seat1=AMEND(non-blocking) | D1 seat2=AMEND(non-blocking) | D1 seat3=AMEND(non-blocking)

### F-008
- priority: non-blocking
- status: DOWNGRADED_BY_MAJORITY
- outcome: non-blocking
- location: `architecture/architecture-packet.json` (`AD-001.details.memory_bounds`, `AO-05`, `AC-004`)
- issue: Хранение чанков `reasoning` без квадратичных аллокаций и согласование лимита `MAX_REASONING_BYTES_PER_TURN = 2 MiB` с полнотой выдачи `AC-004`.
- fix: Накапливать чанки `reasoning` в `list[str]` с однократным `"".join` при формировании результата хода (`RSS <= 112 MiB` на 8 параллельных ходах в `VER-010`), соблюдать единый потолок `MAX_REASONING_BYTES_PER_TURN = 2 MiB` в `_emit_reasoning` (`AD-001.details.memory_bounds`, `AO-05`: сверх `2 MiB` `_emit_reasoning` возвращает `False`, логирует `reasoning-cap` и не ставит дельту в `Run.q`); инвариант побайтового равенства `AC-004` действует для всех префиксно-монотонных ходов (`ASM-001`) в пределах штатной огибающей `<= MAX_REASONING_BYTES_PER_TURN` (`2 MiB`), а при достижении защитного потолка `2 MiB` действует правило усечения `AO-05` (`reasoning-cap`).
- votes: R1 seat2=RAISE(blocking) | D1 seat1=AGREE(blocking) | D1 seat2=AMEND(non-blocking) | D1 seat3=AMEND(non-blocking)

### F-009
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `teamlead/verification-surface.json` (`architecture_packet_sha256`)
- issue: Синхронизация `architecture_packet_sha256` и команд `VER-001..VER-012` в `teamlead/verification-surface.json` с `architecture/architecture-packet.json`.
- fix: `architecture_packet_sha256 = "62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab"` и массив `verifications` (`VER-001..VER-012`) синхронизированы в `teamlead/verification-surface.json`.
- votes: R1 seat2=RAISE(non-blocking) | D1 seat1=AGREE(non-blocking) | D1 seat2=AGREE(non-blocking) | D1 seat3=AGREE(non-blocking)

### F-010
- priority: non-blocking
- status: WITHDRAWN
- outcome: excluded
- location: `panel/arch/r1` (текстовое примечание брифа R1)
- issue: Опечатка префикса в пояснительном тексте брифа R1 не относится к `architecture/architecture-packet.json`.
- fix: Исключено (`WITHDRAWN` / `DISPUTE (invalid)` единогласно `3/3` судьями в D1).
- votes: R1 seat2=RAISE(non-blocking) | D1 seat1=DISPUTE(invalid) | D1 seat2=DISPUTE(invalid) | D1 seat3=WITHDRAW(invalid)

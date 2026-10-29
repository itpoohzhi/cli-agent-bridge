# Итоговый вердикт Архитектурного Совета Тимлидов (`ARCH_PANEL`)

- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Артефакт:** `architecture/architecture-packet.json` (`sha256=62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab`)
- **Раунды:** `R1` (`panel/arch/r1`, слепой раунд) → `R2 / D1` (`panel/arch/r2`, анонимизированные дебаты `3of3_derangement`)
- **Состав жюри D1 (3 независимых семейства):**
  - `Seat 1`: `gpt-6.1-sol-high` (`OpenAI`, `codex`) — `NEEDS WORK` (`POSITIONS: 10/10`, `FINDINGS_COMPLETE: 2`)
  - `Seat 2`: `gemini-4-argon-high` (`Google`, `agy`) — `PASS` (`POSITIONS: 10/10`, `FINDINGS_COMPLETE: 0`)
  - `Seat 3`: `muse-wonder-full-1.0` (`Meta`, `muse`) — `PASS` (`POSITIONS: 10/10`, `FINDINGS_COMPLETE: 0`)
- **Итоговый статус панели:** **`PASS` (большинством 2/3 независимых семейств: `Google` + `Meta` за `PASS`, `blocking_open = 0`)**

---

## Раздел А. Принятые блокеры (`blocking`, открытые)

Открытых архитектурных блокеров нет (`0`). Архитектурный пакет `architecture/architecture-packet.json` (`sha256=62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab` — live-источник SQLite `conversations/<cid>.db` `mode=ro` + pure-Python wire-парсер поля `20.3` + дедупликация с `_TranscriptTail` + синхронное финальное дренирование + учёт выданного `reasoning` в `delivered` + изоляция горячих сессий для агентных запросов с `tools>0`) одобрен квалифицированным большинством `2/3` независимых семейств (`Google` + `Meta`).

---

## Раздел Б. Принятые `non-blocking` замечания (обязательные предохранители для этапа Stage 3 `Coder`)

Все 9 принятых `non-blocking` пунктов (`F-001..F-009`) из дебатов `D1` являются обязательными требованиями к реализации в `bridges/agy-bridge/server.py` и `tests/test_agy_bridge_resilience.py` строго в рамках одобренного `architecture/architecture-packet.json`:

1. **`F-001` (Приоритет нормативного `AD-001` при `divergence` и `resume`):** строго следовать `AD-001.details.dedup_and_emit`, `AD-001.details.watermark_resume`, `AO-08` и `AO-12`: при обнаружении непрефиксного снимка (`divergence`) шаг помечается `diverged=True` и его дальнейшая выдача замораживается на уже отданном префиксе (`0` последующих эмитов этого шага из обоих источников); на `resume`-ходе без успешного pre-spawn SQLite-якоря (`anchored=False`) устанавливается `turn_mode="OFF"` на весь ход.
2. **`F-002` (Приоритет схемной ошибки над `cold-open` в `AD-005` / `AO-01`):** на первом `SELECT` распознанная схемная ошибка (`no such table: steps` / `no such column`) проверяется ДО классификации транзиентного `cold-open` (`unable to open database file`) и инкрементирует `consecutive_failures` circuit breaker'а (3 таких хода переводят breaker в `OPEN`, тогда как 3 хода с ещё не созданным файлом БД оставляют breaker `CLOSED`).
3. **`F-003` (Инварианты `finalized`, `poll_watermark` и `binary_identity` в `AD-001` / `AO-10` / `AO-12`):** (а) выполнять ранний выход `if state["finalized"]: continue/return` в обоих путях (SQLite и транскрипт) и обновлять `delivered_*` при выдаче из транскрипта; (б) монотонно продвигать `poll_watermark` через непрерывный префикс завершённых (`status=3` / `finalized`) шагов (включая шаги без `thinking`), чтобы окно `>16` шагов не блокировало `LIMIT 16`; (в) переводить `SHADOW -> LIVE` только при совпадении `turn_binary_identity == current_binary_identity` под `_sqlite_guard_lock`.
4. **`F-004` (Атомарная регистрация `_active_cid_owners` при `init` в `AD-001` / `AD-004`):** при привязке `cid` из события `init` атомарно под `_session_store_lock` проверять и регистрировать `_active_cid_owners[cid] = turn_id` до старта чтения SQLite (при коллизии с чужим активным `turn_id` не перезаписывать владельца и отключать SQLite для текущего хода), а при закрытии хода удалять запись только если `_active_cid_owners.get(cid) == turn_id`.
5. **`F-005` (Терминальный `try/finally` в `_pump` и полное окно `DRAIN_WINDOW_S = 0.35 s` в `AD-002` / `AO-03` / `AO-11`):** (а) обернуть тело `_pump` в `try/finally`, гарантирующий ровно один идемпотентный вызов `_close_and_put_done(run, ...)`; (б) при вызове `conn.interrupt()` под локом соединения подавлять `sqlite3.ProgrammingError`/`OperationalError` на закрытом соединении; (в) выдерживать полное окно `DRAIN_WINDOW_S = 0.35 s` после EOF без эвристического раннего выхода по «PLANNER_RESPONSE + два пустых тика».
6. **`F-006` (Быстрое отключение по kill-switch `SQLITE_REASONING_ENABLED` в `AD-006` / `AO-09`):** перепроверять `_is_sqlite_reasoning_enabled()` на каждой итерации и перед обработкой каждой строки `SELECT`; при отключении немедленно вызывать `conn.interrupt()`, закрывать соединение и логировать `sqlite-off reason=flag` (укладываясь в `<= 2.0 s` в гейте `VER-010` и `<= 5.0 s` по `REQ-011`).
7. **`F-007` (Все 52 новых теста как методы `unittest.TestCase` в `tests/test_agy_bridge_resilience.py`):** оформить все 52 новых теста (`TC-01..12, 20, 21, 23, 24, 30..33, 40..44, 50, 51, 60..63, 70..72, 80..82, 91, 92`, `AO-01..AO-12`, `tc93` / `l2_harness`) как отдельные методы классов `unittest.TestCase` без `skip`, с содержательными проверками, стресс-профилем `16 x 256 KiB` в `tc93` и без `# type: ignore` / `# pyright: ignore`.
8. **`F-008` (Хранение чанков `reasoning` в `list[str]` и потолок `2 MiB` в `AD-001` / `AO-05`):** накапливать чанки `reasoning` в списке `list[str]` с однократным `"".join` в конце хода (удерживая `RSS <= 112 MiB` на 8 параллельных ходах в `VER-010`) и соблюдать единый потолок `MAX_REASONING_BYTES_PER_TURN = 2 MiB` в `_emit_reasoning` по `AD-001.details.memory_bounds` / `AO-05` (инвариант `AC-004` действует при `ASM-001` и суммарном объёме мышления хода `<= MAX_REASONING_BYTES_PER_TURN`, а сверх `2 MiB` действует явное защитное ограничение `AO-05` `reasoning-cap`).
9. **`F-009` (Синхронизация `teamlead/verification-surface.json`):** `architecture_packet_sha256` и команды `VER-001..VER-012` синхронизированы между `architecture/architecture-packet.json` и `teamlead/verification-surface.json`.

---

## Раздел В. Отклонённые / снятые замечания

- **`F-010` (`WITHDRAWN` / `excluded`, единогласно `3/3`):** замечание к тексту примечания в брифе R1 не относится к `architecture/architecture-packet.json` и отозвано всеми тремя судьями.

---

## Раздел Г. Особые мнения (Dissent)

- **`Seat 1` (`gpt-6.1-sol-high`, `OpenAI`) по `F-006` и `F-008`:** судья `Seat 1` предложил оставить `F-006` и `F-008` в статусе `blocking` до формального пересчёта дедлайна `SELECT` и памяти в тексте пакета. Большинством `2/3` независимых семейств (`Seat 2` `Google` + `Seat 3` `Meta`) `F-006` и `F-008` переведены в `non-blocking` контрактные предохранители Раздела Б, так как они полностью реализуются внутри уже спроектированных механизмов `AD-001`, `AD-002`, `AD-006` и верифицируются детерминированными оракулами `AO-05`, `AO-09` и стресс-гейтом `VER-010` (`tc93` / `l2_harness`).

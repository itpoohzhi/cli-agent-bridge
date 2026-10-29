# Консенсус-леджер находок Архитектурного Совета — до дебатов `D1` (после `R1` `panel/arch/r1`)

- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/panel/arch/r1` (`panel-proof.json` `verify_panel_proof exit=0`)
- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json` (`sha256=62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab`)

---

## Карточки открытых находок R1 (вход для дебатов D1)

### F-001
- origin: Seat 1 (`muse-wonder-full-1.0` F-001) + Seat 2 (`gpt-6.1-sol-high` F-002 ч. 2)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: В ненормативных карточках `RISK-002` и `RISK-004` остались старые формулировки («отдаёт только невыданный хвост» при divergence и «из транскрипта со статусом 8 при ошибке SQLite» на resume), тогда как нормативный `AD-001` (`dedup_and_emit`, `watermark_resume`, `AO-08`, `AO-12`) замораживает выдачу шага при divergence и требует `turn_mode="OFF"` при неуспехе pre-spawn SQLite-якоря на resume. Рекомендация RECHECK для D1: `AMEND F-001 — priority=non-blocking` (нормативный приоритет `AD-001` и `AO-08`/`AO-12` уже однозначен; передать как обязательный предохранитель в бриф Stage 3 `Coder`).

### F-002
- origin: Seat 1 (`muse-wonder-full-1.0` F-002)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: В `AD-005` и `AO-01` нужно явно зафиксировать, что распознанная схемная ошибка (`no such table: steps` / `no such column`) на первом `SELECT` имеет приоритет над классификацией `cold-open` и увеличивает `consecutive_failures` breaker'а. Рекомендация RECHECK для D1: `AMEND F-002 — priority=non-blocking` (обязательный предохранитель реализации в Stage 3 `Coder` и теста `AO-01`).

### F-003
- origin: Seat 1 (`muse-wonder-full-1.0` F-003) + Seat 2 (`gpt-6.1-sol-high` F-002 ч. 1, F-003)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: В `AD-001` (`seen_state`, `dedup_and_emit`, `compat`) зафиксировать для Stage 3 `Coder`: (1) обязательный ранний выход `if state["finalized"]: continue/return` в обоих путях и обновление `delivered_*` при выдаче из транскрипта; (2) монотонное продвижение `poll_watermark` через непрерывный префикс завершённых (`status=3` / `finalized`) шагов; (3) проверку совпадения `turn_binary_identity == current_binary_identity` при переводе `SHADOW -> LIVE`. Рекомендация RECHECK для D1: `AMEND F-003 — priority=non-blocking` (обязательный предохранитель реализации в Stage 3 `Coder`).

### F-004
- origin: Seat 1 (`muse-wonder-full-1.0` F-004)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: При получении свежего `cid` из события `init` атомарно регистрировать `_active_cid_owners[cid] = turn_id` под `_session_store_lock`. Рекомендация RECHECK для D1: `AGREE F-004` / `AMEND F-004 — priority=non-blocking`.

### F-005
- origin: Seat 1 (`muse-wonder-full-1.0` F-005) + Seat 2 (`gpt-6.1-sol-high` F-004)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: В `AD-002` (`_pump` и `_drain_post_eof`): (1) обернуть тело `_pump` в `try/finally`, гарантирующий ровно один вызов `_close_and_put_done(run, ...)` при любом исключении; (2) при вызове `conn.interrupt()` под локом соединения подавлять `sqlite3.ProgrammingError`/`OperationalError` на уже закрытом дескрипторе; (3) выдерживать полное окно `DRAIN_WINDOW_S = 0.35 s` после EOF без эвристического досрочного выхода. Рекомендация RECHECK для D1: `AMEND F-005 — priority=non-blocking` (обязательный предохранитель реализации в Stage 3 `Coder` для `AO-03` и `AO-11`).

### F-006
- origin: Seat 1 (`muse-wonder-full-1.0` F-006) + Seat 2 (`gpt-6.1-sol-high` F-005)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: В `AD-006` и `AO-09` оценка `1.30 s` описывает задержку пробуждения и обнаружения флага (`TTL 1.0 s + slice 0.25 s + busy_timeout 0.05 s`), а общий контракт времени реакции kill-switch равен `<= 5.0 s` (`REQ-011`, `QA-010`). Перепроверять `_is_sqlite_reasoning_enabled()` перед выдачей каждой строки и вызывать `conn.interrupt()` при отключении. Рекомендация RECHECK для D1: `AMEND F-006 — priority=non-blocking` (обязательный предохранитель реализации в Stage 3 `Coder`).

### F-007
- origin: Seat 1 (`muse-wonder-full-1.0` F-007) + Seat 2 (`gpt-6.1-sol-high` F-007, F-008)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: В `tests/test_agy_bridge_resilience.py` оформить все 52 новых теста (`TC-*`, `AO-01..AO-12`, `tc93`) как отдельные методы классов `unittest.TestCase` (чтобы и `pytest`, и `/usr/bin/python3 -m unittest` исполняли все 52 теста без `skip`), с содержательными проверками контрактов, стресс-профилем `16 x 256 KiB` в L2 и проверкой отсутствия `# type: ignore` / `# pyright: ignore`. Рекомендация RECHECK для D1: `AMEND F-007 — priority=non-blocking` (обязательное требование к Stage 3 `Coder` и `Verifier`).

### F-008
- origin: Seat 2 (`gpt-6.1-sol-high` F-001, F-006)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: Хранить чанки `reasoning` в списке `list[str]` с однократным `"".join` в конце хода (без квадратичных копий строк; при `<= 2 MiB` UTF-8 даже в UCS-4 память `<= 8 MiB` на ход, `<= 64 MiB` на 8 ходов, общий RSS `<= 112 MiB`), а лимит `2 MiB` применять только к live-буферизации из SQLite, сохраняя дочитывание финала из `transcript_full.jsonl` для `AC-004`. Рекомендация RECHECK для D1: `AMEND F-008 — priority=non-blocking` (обязательный предохранитель реализации в Stage 3 `Coder`).

### F-009
- origin: Seat 2 (`gpt-6.1-sol-high` F-009)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: Синхронизировать `architecture_packet_sha256` в `teamlead/verification-surface.json` с актуальным хешем пакета `62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab`. Рекомендация RECHECK для D1: `AGREE F-009` / `AMEND F-009 — priority=non-blocking`.

### F-010
- origin: Seat 2 (`gpt-6.1-sol-high` F-010)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: excluded
- text: В текстовом комментарии брифа R1 был указан старый префикс `146585...` при корректной таблице дайджестов (`048a8cdb...`) и валидном `manifest.json` (`verify_panel_proof exit=0`). Не является дефектом `architecture-packet.json`. Рекомендация RECHECK для D1: `WITHDRAW F-010` / `DISPUTE F-010 (invalid)`.

# Консенсус-леджер находок Архитектурного Совета — Cycle 1 (`a6`, после `R1` `panel/arch/r18` и `D1` `panel/arch/r21`)

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r18` (`panel-proof.json` `sha256=4308b386a0e057dcd05d449efd9e1d57aecae9d25b1371efb2855dbaedd85bf2`, `verify_panel_proof exit=0`)
- **Раунд D1:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r21` (`panel-proof.json` `sha256=2a413947ff12edbac1beff94c8d833d6a288a70d1410a0a5250c605a78a13cad`, `verify_panel_proof exit=0`)
- **Проверяемый артефакт (v6):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`sha256=88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b`)
- **Итог после D1:** `blocking_open = 0` (`F-001` понижен большинством `2/3` семей `Google` + `Meta` до `non-blocking` со статусом `AGREED`; `F-002` снят автором `WITHDRAWN` / `excluded`; `F-003` и `F-004` подтверждены `3/3` судьями как `non-blocking` со статусом `AGREED`).

---

## Сводная таблица позиций судей

| ID | Seat 1 (`skeptic`, `gemini-4-argon-high`, `Google`) | Seat 2 (`realist`, `grok-4.7-high`, `xAI`, R1 author) | Seat 3 (`visionary`, `muse-wonder-full-1.0`, `Meta`) | Итоговый приоритет (`outcome`) | Статус (`status`) |
|---|---|---|---|---|---|
| F-001 | AMEND (`priority=non-blocking`) | AMEND (`priority=blocking`) | AMEND (`priority=non-blocking`) | non-blocking | AGREED |
| F-002 | DISPUTE (`invalid`) | WITHDRAW | DISPUTE (`invalid`) | excluded | WITHDRAWN |
| F-003 | AGREE (`rev=1`, `non-blocking`) | AGREE (`AUTHOR`, `rev=1`) | AGREE (`rev=1`, `non-blocking`) | non-blocking | AGREED |
| F-004 | AGREE (`rev=1`, `non-blocking`) | AGREE (`AUTHOR`, `rev=1`) | AMEND (`priority=non-blocking`) | non-blocking | AGREED |

---

## Карточки находок

### F-001
- origin: skeptic · R1 · skeptic-F-001
- rev: 3
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR | D1 skeptic=AMEND(non-blocking) | D1 realist=AMEND(blocking) | D1 visionary=AMEND(non-blocking)
- dissent: realist d1 «AMEND F-001 — priority=blocking; locations=architecture-packet.json#AD-001,architecture-packet.json#VER-005,architecture-packet.json#THREAT-001,architecture-packet.json#EVD-079; fix=Оставить /tmp/opencode-zen-bridge-leases/ только как боевое значение по умолчанию аргумента lease_dir...» → arch-panel/cycle-1/a6/debate/r2/realist.md
- owner_decision: —
- amendments:
  - rev 1 (R1 skeptic `grok-4.7-high`): `priority=blocking` — свести запись lease, registry, startup reaper и THREAT-001 к единому позиционному `lease_dir`.
  - rev 2 (D1 realist `grok-4.7-high`): `priority=blocking` — оставить `/tmp/opencode-zen-bridge-leases/` только как боевой дефолт `lease_dir`, который parent кладёт в argv и сканирует в startup reaper.
  - rev 3 (D1 skeptic `gemini-4-argon-high` + visionary `muse-wonder-full-1.0`): `priority=non-blocking` — нормативные секции `helper_cli_contract.validation` (`architecture-packet.json:2767`) и `crash_recovery.creation` (`architecture-packet.json:2589`) уже обязывают helper писать исключительно в переданный позиционный `lease_dir`, а совместное выполнение `VER-005.clean_room_helper_oracle` и `orphan_oracles` однозначно задаёт в Stage 3 единый конфигурируемый `lease_dir` (с боевым дефолтом `/tmp/opencode-zen-bridge-leases/` по `architecture-packet.json:2568`); передаётся как обязательный non-blocking предохранитель в бриф Coder.
- text (дословно, R1 skeptic + D1 консенсус rev 3):
> F-001 [non-blocking] Единый конфигурируемый корень `lease_dir` (боевой дефолт `/tmp/opencode-zen-bridge-leases/`)
> - Якорь: architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.registry`, `details.crash_recovery.creation`, `details.helper_cli_contract`); architecture-packet.json#VER-005 (`clean_room_helper_oracle`, `orphan_oracles`); architecture-packet.json#THREAT-001; architecture-packet.json#EVD-079
> - Правило: REQ-008 / AC-011, T-LIFE/v1, THREAT-001; приёмка RW-002 («use only the passed isolated lease directory»)
> - Обязательный предохранитель для Coder (Stage 3): в `server.py` использовать единый конфигурируемый каталог `lease_dir` (с боевым дефолтом `/tmp/opencode-zen-bridge-leases/`), который родитель передаёт позиционным `argv` в `--serve-helper` и сканирует в `startup_reaper`; helper пишет исключительно `lease_dir/lease-<attempt_id>.json`; оракул `VER-005` с нестандартным `lease_dir` проверяет появление файла только там и снятие своей записи следующим стартом.
> - priority: non-blocking

### F-002
- origin: skeptic · R1 · skeptic-F-002
- rev: 1
- priority: non-blocking
- status: WITHDRAWN
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR | D1 skeptic=DISPUTE(invalid) | D1 realist=WITHDRAW | D1 visionary=DISPUTE(invalid)
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic — снято автором в D1):
> F-002 [withdrawn] Верхняя оценка FD parent 114 уже включает steady `6lifeline_w` (`parent_watchdog_pipes: 6` внутри steady `108`) и transient `6lifeline_r` (`108 + 6 = 114 <= 128`); отдельные `+6` write сверх `108` — двойной счёт (`WITHDRAW F-002` от автора `grok-4.7-high` и `DISPUTE (invalid)` от `gemini-4-argon-high` и `muse-wonder-full-1.0`).
> - priority: excluded

### F-003
- origin: skeptic · R1 · skeptic-F-003
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR | D1 skeptic=AGREE | D1 realist=AGREE | D1 visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-003 [sweep] Счётчик evidence в `semantic_checks` отстаёт от EVD-079
> - Якорь: architecture-packet.json#EVD-079 (`architecture-packet.json:4540`)
> - Правило: полнота `evidence[]` / `semantic_checks.evidence_refs`
> - Доказательство: строка «73 EVD records» соответствует диапазону до EVD-078 (64 записи EVD-001..064 плюс 9 записей EVD-070..078). EVD-079 в массиве есть, итог 74.
> - priority: non-blocking

### F-004
- origin: skeptic · R1 · skeptic-F-004
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR | D1 skeptic=AGREE | D1 realist=AGREE | D1 visionary=AMEND(non-blocking)
- dissent: —
- owner_decision: —
- amendments:
  - rev 1 (R1 skeptic `grok-4.7-high`, поддержано `gemini-4-argon-high` и `muse-wonder-full-1.0`): `priority=non-blocking` — запретить перенос тела пробы с `select(fd0) + proc.communicate()` в Stage 3; нормативный цикл `--serve-helper` в `server.py` обязан выполнять конкурентный неблокирующий дренаж `stdout` и `stderr` дочернего `opencode serve` в каждом тике цикла наблюдения за `fd 0`, а `VER-005` обязан включать тест с дочерним процессом, пишущим `>64 КиБ` в `stderr` до первого SSE-события.
- text (дословно, R1 skeptic):
> F-004 [sweep] Единственный вложенный код helper дренирует дочерние pipe после выхода, а норма требует дренаж в том же тике, что EOF
> - Якорь: architecture-packet.json#EVD-079 (`helper_cli_probe_source`, `candidate_patch_from_origin_dev`); architecture-packet.json#AD-001 (`helper_cli_contract.validation`)
> - Правило: AD-001 drain-инвариант; REQ-006 (ложный `first_event_timeout`)
> - Обязательный предохранитель для Coder (Stage 3): в `server.py` НЕ копировать тело пробы с `proc.communicate()` после `select([0])`; реализовать нормативный конкурентный неблокирующий дренаж `stdout` и `stderr` дочернего `opencode serve` в каждом тике цикла наблюдения за `fd 0`, и включить в `tests/test_realtime_reasoning.py` оракул `VER-005` с дочерним процессом, пишущим `>64 КиБ` в `stderr` до первого SSE.
> - priority: non-blocking

# Черновой консенсус-леджер находок Архитектурного Совета — Cycle 1 (`a6`, после `R1` `panel/arch/r18`)

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r18` (`panel-proof.json` `sha256=4308b386a0e057dcd05d449efd9e1d57aecae9d25b1371efb2855dbaedd85bf2`, `verify_panel_proof exit=0`)
- **Проверяемый артефакт (v6):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`sha256=88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b`)
- **Всего открытых находок после R1:** 4 (`F-001`..`F-004` от `skeptic` `grok-4.7-high`, `0` от `realist` `muse-wonder-full-1.0`, `0` от `visionary` `claude-sonnet-5-5-high`)

---

## Находки Seat 1 (`skeptic`, `grok-4.7-high`, `xAI`, `cursor-agent`)

### F-001
- origin: skeptic · R1 · skeptic-F-001
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-001 [blocking] Два корня lease: фиксированный `/tmp/opencode-zen-bridge-leases/` и позиционный `lease_dir`
> - Якорь: architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.registry`, `details.crash_recovery.creation`, `details.helper_cli_contract`); architecture-packet.json#VER-005 (`clean_room_helper_oracle`, `orphan_oracles`); architecture-packet.json#THREAT-001; architecture-packet.json#EVD-079
> - Правило: REQ-008 / AC-011, T-LIFE/v1, THREAT-001; приёмка RW-002 («use only the passed isolated lease directory»)
> - Доказательство: spawn требует создать `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json` и тут же «use only the passed isolated lease directory». Registry reaper — тот же `/tmp/opencode-zen-bridge-leases/`. EVD-079 передаёт `/private/tmp/zen-arch6-probe-work-jfgscb15/leases` и в теле пробы файл lease не пишет.
> - Ожидаемое исправление: один каталог — аргумент `lease_dir`; reaper и THREAT-001 ссылаются только на него; оракул с нестандартным каталогом проверяет и запись, и подбор при следующем старте.
> - Критерий проверки: в пакете нет второго обязательного пути; сценарий «parent мёртв, helper мёртв, lease остался» снимает только свой PGID.
> - priority: blocking

### F-002
- origin: skeptic · R1 · skeptic-F-002
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-002 [pre-existing][sweep] Верхняя оценка FD parent 114 не включает одновременно steady `lifeline_w` и transient `lifeline_r`
> - Якорь: architecture-packet.json#AD-001 (`details.resource_accounting.fd`); architecture-packet.json#VER-005 (`process_resource_oracle.resources.fd`)
> - Правило: C-MULT-I5, `FD_worker` 128
> - Доказательство: сумма полей baseline+clients+lanes+drains+ports+lsof+watchdog+lease = 108. Текст прибавляет только 6 transient read-концов и публикует 114. `lifeline_definition` отдельно держит 6 write-концов `lifeline_w` на всё время запроса. Пик 108+6+6 = 120.
> - Ожидаемое исправление: записать peak 120 и пересчитать запас до 128 (8, не 14). Envelope 128 не поднимать.
> - Критерий проверки: 120 ≤ 128 во всех копиях fd-абзаца; H3 меряет фактический пик, включая окно setup.
> - priority: non-blocking

### F-003
- origin: skeptic · R1 · skeptic-F-003
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-003 [sweep] Счётчик evidence в `semantic_checks` отстаёт от EVD-079
> - Якорь: architecture-packet.json#EVD-079
> - Правило: полнота `evidence[]` / `semantic_checks.evidence_refs`
> - Доказательство: строка «73 EVD records» соответствует диапазону до EVD-078 (64 записи EVD-001..064 плюс 9 записей EVD-070..078). EVD-079 в массиве есть, итог 74.
> - Ожидаемое исправление: заменить 73 на 74 и включить EVD-079 в перечень проверенных записей semantic_checks.
> - Критерий проверки: число объектов `evidence[]` с id `EVD-*` равно числу в semantic_checks.
> - priority: non-blocking

### F-004
- origin: skeptic · R1 · skeptic-F-004
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-004 [sweep] Единственный вложенный код helper дренирует дочерние pipe после выхода, а норма требует дренаж в том же тике, что EOF
> - Якорь: architecture-packet.json#EVD-079 (`helper_cli_probe_source`, `candidate_patch_from_origin_dev`); architecture-packet.json#AD-001 (`helper_cli_contract.validation`)
> - Правило: AD-001 drain-инвариант; REQ-006 (ложный `first_event_timeout`)
> - Доказательство: проба крутит `select` по fd 0 и только потом вызывает `proc.communicate()`. Контракт: «Drain-ready pipes concurrently with fd0 EOF/TERM and child poll, no child pipe wait delaying EOF». Докстринг помечает тело как не-Stage3, но diff лежит в пакете как `candidate_patch_from_origin_dev`.
> - Ожидаемое исправление: в репродукции пробы прямо написать, что копируется только ранний `if/else` импортов и замер RSS; тело с `communicate()` в Stage3 запрещено. Нормативный цикл — неблокирующее чтение stdout и stderr serve.
> - Критерий проверки: ревью Stage3 отвергает перенос `communicate()`-после-простоя; тест с дочерним процессом, пишущим >64 КиБ в stderr до первого SSE, не получает `first_event_timeout`, пока сокет событий жив.
> - priority: non-blocking

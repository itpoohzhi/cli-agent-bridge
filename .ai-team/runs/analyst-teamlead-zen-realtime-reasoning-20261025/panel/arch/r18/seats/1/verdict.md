PANEL-NONCE: 7f969f73649740f8
ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
WHY=RW-002 закрыл форму argv и ранний выход до тяжёлых импортов, но жизненный цикл lease остался с двумя корнями. В `AD-001.details.spawn` helper «сразу» пишет `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json`, а ниже в том же контракте и в `helper_cli_contract.validation` обязан использовать только переданный `lease_dir`. `crash_recovery.registry` и startup reaper смотрят фиксированный каталог `/tmp/opencode-zen-bridge-leases/`. Проба EVD-079 передаёт другой каталог (`.../leases`) и файл lease вообще не создаёт. Чтение A ломает clean-room VER-005 и даёт общую коллизию lease между тестами. Чтение B оставляет reaper слепым: после смерти parent и helper orphan `opencode serve` не находится. REQ-008 / AC-011 и THREAT-001 на этом пути не исполняются ни при одной из двух обязательных формулировок.
СОВЕТЫ (при FAIL):
- Оставить один корень lease: каталог из позиционного `lease_dir`. Удалить из spawn, `crash_recovery.registry`, `crash_recovery.creation`, startup reaper и THREAT-001 буквальный путь `/tmp/opencode-zen-bridge-leases/` как второй источник. Если этот путь нужен в бою, задать его только как значение аргумента, которое parent кладёт в argv, и записать то же значение в поле lease.
- Reaper сканирует только этот каталог (или указатель, лежащий внутри него). Оракул VER-005: при `lease_dir`, отличном от любого фиксированного `/tmp/...`, lease-файл появляется лишь там, и следующий старт моста снимает именно эту запись. Сценарий «helper убит, lease оставлен» обязан находить запись без догадки по глобальному имени.
- В normative-контракте helper оставить ранний барьер импортов. Тело `_run_serve_helper_cli` из `EVD-079.candidate_patch_from_origin_dev` пометить как пробу RSS, не как реализацию: цикл `select` только по fd 0 и последующий `communicate()` не дренирует stdout/stderr serve. Норма — неблокирующий дренаж обоих pipe в том же тике, что EOF/TERM, иначе заполнившийся stderr (порядка 64 КиБ) останавливает event loop `opencode serve` и сторож первого события срабатывает на живом апстриме.
- `attempt_id` для имени файла брать из `secrets` (непредсказуемый), режим каталога `0700`, `O_NOFOLLOW`, запись через atomic replace в переданном каталоге.

2. ПОЛНОТА: VERDICT=PASS
WHY=REQ-001..020, AC-001..026, AD-001..004, границы BND-001..004, CD-001..002, конверт 46 полей HL-ENV, гейты C-MULT/S-HERD/H-CPU/R-BULK/T-LIFE/O-EXIT/M-SEM, threat model, views с вопросом и ссылкой, и дельта a5 (RW-001, RW-002, FU-001, FU-002) в пакете присутствуют. Память v6 сведена: замер EVD-079 `ru_maxrss` 31.71875 МиБ, `helper_estimate` 36.0, слот 216, запас 15.2 ≥ 15, `Mem_shared_max` 1296, 1552.0 ≤ 1638.4, слоты 6 / waiters 12 / cap 3 / 2048 МиБ не сдвинуты, H3 остаётся NOT_RUN. argv без многоточия, `--config` у вызовов ruff, cycle 6 и `plans/architect-06.json` совпадают с allowlist. Расхождение «73 EVD» против фактических 74 — учётная ошибка, не дыра в контракте (F-003).

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
WHY=Выбранный путь укладывается в stdlib `ThreadingHTTPServer` и три файла кодера. Изолированная проба EVD-079 на Python 3.14.7 подняла цепочку parent → helper → fake serve: шесть аргументов, `OPENCODE_BIN` из argv, в `serve_env` его нет, тяжёлые модули не загружены, пик helper 31.72 МиБ < 36.0. VER-004 на копии (обычный и hostile `line-length=60`) дал exit 0, catalog 8/8, три frozen SHA без изменений, E402 сверх `import zen_catalog as zc` не появился. Ранний `SystemExit` до `reload_catalog()` наблюдаем. Оставшийся дефект lease — правка контракта, она не упирается в невозможный механизм. Stage3 и H0..H9 честно NOT_RUN.

4. РИСКИ: VERDICT=FAIL
WHY=При росте отказов (смерть parent, затем helper, шесть слотов) очистка смотрит не туда, куда helper пишет lease, поэтому группа `child_pgid` остаётся жить — тот же класс инцидента, что [F-30] / [F-14], уже после «исправленного» T-LIFE. Фиксированный каталог в `/tmp` общий для всех прогонов одного UID: параллельный VER-005 и чужой локальный процесс бьются в одно имя `lease-<attempt_id>.json`. Отдельно, уже внутри конверта: рост serve над idle 156.8 МиБ имеет 15.2 МиБ на слот; это согласовано с приёмкой RW-001 и режется H3 без waiver, само по себе бюджет не разъезжается. Пик FD в тексте занижен на концы lifeline (F-002): заявленные 114, одновременно живут steady `lifeline_w` и кратковременные `lifeline_r`, итог 120. Потолок 128 пока держит, запас 14 дескрипторов на бумаге и 8 по факту.
СОВЕТЫ (при FAIL):
- Свести lease, reaper и негативный оракул к одному `lease_dir`, как в советах критерия 1. Отдельный тест: SIGKILL parent после записи lease, убить helper, поднять мост, убедиться, что serve/helper/temp root этого attempt исчезли, а чужой PGID не получал сигнал.
- Пересчитать пик parent FD как 108 + 6 `lifeline_w` + 6 transient `lifeline_r` = 120 и записать 120 в `parent_upper_bound`, C-MULT-I5 и `fd_accounting`. Не поднимать envelope 128, пока 120 ≤ 128.
- H3 оставить NOT_RUN. Порог включения не ослаблять: слот > 216 МиБ или станция > 1638.4 МиБ блокирует H7. В замер H3 входит RSS serve под промптом ~103 КБ, не idle 156.8.
- Нормативный helper дренирует stderr/stdout serve без `communicate()` после простоя, иначе ложный `first_event_timeout` при болтливом дочернем процессе.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
WHY=AD-001 сравнивает больше двух живых вариантов и фиксирует причину выбора: A2 делит failure domain и не даёт доказанной смены egress; B упирается в 429 [F-24]/[F-25]; L не снимает RC-1 [F-17]/[F-18]; `--stdio` есть во флаге [EVD-078], публичной схемы IPC нет; `--port 0` без устойчивого объявления порта отвергнут. Нагрузка разобрана на выбранном дереве: 6 пар helper+serve, cap 3, spawn 1/с, память 216 МиБ на слот, при превышении H3 фича не включается. AD-002..004 тоже two-way (безусловный статус t=0, только TIMEOUT 1800, подъём потолка до 4).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
WHY=Пакет остаётся на фактическом stdlib-мосте `:9883`, без слоёв Litestar/FastAPI. Факты решений лежат в [F-01]..[F-49] и EVD-070..079. Публичная форма OpenAI SSE, порт, Google-срез (`_run_env` / `_stream_google_sse` / `_execute_google_once`) и запрет записи `opencode.db` сохранены; изоляция serve через `OPENCODE_DB=:memory:` при read-only auth для run/opencode-go указана. `dynamic_config.json` в git не создаётся, кодовый default false, H7 только после H3/H6. `muse-bridge`, DSH и `~/.dsh` архитектор не меняет. Статус APPROVED в пакете прямо назван внутренним кандидатом, не вердиктом совета; квитанция ARCH_GATE совпадает с sha256 пакета.

F-001 [blocking] Два корня lease: фиксированный `/tmp/opencode-zen-bridge-leases/` и позиционный `lease_dir`
- Якорь: architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.registry`, `details.crash_recovery.creation`, `details.helper_cli_contract`); architecture-packet.json#VER-005 (`clean_room_helper_oracle`, `orphan_oracles`); architecture-packet.json#THREAT-001; architecture-packet.json#EVD-079
- Правило: REQ-008 / AC-011, T-LIFE/v1, THREAT-001; приёмка RW-002 («use only the passed isolated lease directory»)
- Доказательство: spawn требует создать `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json` и тут же «use only the passed isolated lease directory». Registry reaper — тот же `/tmp/opencode-zen-bridge-leases/`. EVD-079 передаёт `/private/tmp/zen-arch6-probe-work-jfgscb15/leases` и в теле пробы файл lease не пишет.
- Ожидаемое исправление: один каталог — аргумент `lease_dir`; reaper и THREAT-001 ссылаются только на него; оракул с нестандартным каталогом проверяет и запись, и подбор при следующем старте.
- Критерий проверки: в пакете нет второго обязательного пути; сценарий «parent мёртв, helper мёртв, lease остался» снимает только свой PGID.
- priority: blocking

F-002 [pre-existing][sweep] Верхняя оценка FD parent 114 не включает одновременно steady `lifeline_w` и transient `lifeline_r`
- Якорь: architecture-packet.json#AD-001 (`details.resource_accounting.fd`); architecture-packet.json#VER-005 (`process_resource_oracle.resources.fd`)
- Правило: C-MULT-I5, `FD_worker` 128
- Доказательство: сумма полей baseline+clients+lanes+drains+ports+lsof+watchdog+lease = 108. Текст прибавляет только 6 transient read-концов и публикует 114. `lifeline_definition` отдельно держит 6 write-концов `lifeline_w` на всё время запроса. Пик 108+6+6 = 120.
- Ожидаемое исправление: записать peak 120 и пересчитать запас до 128 (8, не 14). Envelope 128 не поднимать.
- Критерий проверки: 120 ≤ 128 во всех копиях fd-абзаца; H3 меряет фактический пик, включая окно setup.
- priority: non-blocking

F-003 [sweep] Счётчик evidence в `semantic_checks` отстаёт от EVD-079
- Якорь: architecture-packet.json#EVD-079
- Правило: полнота `evidence[]` / `semantic_checks.evidence_refs`
- Доказательство: строка «73 EVD records» соответствует диапазону до EVD-078 (64 записи EVD-001..064 плюс 9 записей EVD-070..078). EVD-079 в массиве есть, итог 74.
- Ожидаемое исправление: заменить 73 на 74 и включить EVD-079 в перечень проверенных записей semantic_checks.
- Критерий проверки: число объектов `evidence[]` с id `EVD-*` равно числу в semantic_checks.
- priority: non-blocking

F-004 [sweep] Единственный вложенный код helper дренирует дочерние pipe после выхода, а норма требует дренаж в том же тике, что EOF
- Якорь: architecture-packet.json#EVD-079 (`helper_cli_probe_source`, `candidate_patch_from_origin_dev`); architecture-packet.json#AD-001 (`helper_cli_contract.validation`)
- Правило: AD-001 drain-инвариант; REQ-006 (ложный `first_event_timeout`)
- Доказательство: проба крутит `select` по fd 0 и только потом вызывает `proc.communicate()`. Контракт: «Drain-ready pipes concurrently with fd0 EOF/TERM and child poll, no child pipe wait delaying EOF». Докстринг помечает тело как не-Stage3, но diff лежит в пакете как `candidate_patch_from_origin_dev`.
- Ожидаемое исправление: в репродукции пробы прямо написать, что копируется только ранний `if/else` импортов и замер RSS; тело с `communicate()` в Stage3 запрещено. Нормативный цикл — неблокирующее чтение stdout и stderr serve.
- Критерий проверки: ревью Stage3 отвергает перенос `communicate()`-после-простоя; тест с дочерним процессом, пишущим >64 КиБ в stderr до первого SSE, не получает `first_event_timeout`, пока сокет событий жив.
- priority: non-blocking

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

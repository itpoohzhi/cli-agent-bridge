# Стенограмма дебатов Архитектурного Совета — Cycle 1 (`a6`)

## Раунд R1 (`panel/arch/r18`)

### Seat 1 (`skeptic`, `grok-4.7-high`)

> PANEL-NONCE: 7f969f73649740f8
> ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
> WHY=RW-002 закрыл форму argv и ранний выход до тяжёлых импортов, но жизненный цикл lease остался с двумя корнями. В `AD-001.details.spawn` helper «сразу» пишет `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json`, а ниже в том же контракте и в `helper_cli_contract.validation` обязан использовать только переданный `lease_dir`. `crash_recovery.registry` и startup reaper смотрят фиксированный каталог `/tmp/opencode-zen-bridge-leases/`. Проба EVD-079 передаёт другой каталог (`.../leases`) и файл lease вообще не создаёт. Чтение A ломает clean-room VER-005 и даёт общую коллизию lease между тестами. Чтение B оставляет reaper слепым: после смерти parent и helper orphan `opencode serve` не находится. REQ-008 / AC-011 и THREAT-001 на этом пути не исполняются ни при одной из двух обязательных формулировок.
> СОВЕТЫ (при FAIL):
> - Оставить один корень lease: каталог из позиционного `lease_dir`. Удалить из spawn, `crash_recovery.registry`, `crash_recovery.creation`, startup reaper и THREAT-001 буквальный путь `/tmp/opencode-zen-bridge-leases/` как второй источник. Если этот путь нужен в бою, задать его только как значение аргумента, которое parent кладёт в argv, и записать то же значение в поле lease.
> - Reaper сканирует только этот каталог (или указатель, лежащий внутри него). Оракул VER-005: при `lease_dir`, отличном от любого фиксированного `/tmp/...`, lease-файл появляется лишь там, и следующий старт моста снимает именно эту запись. Сценарий «helper убит, lease оставлен» обязан находить запись без догадки по глобальному имени.
> - В normative-контракте helper оставить ранний барьер импортов. Тело `_run_serve_helper_cli` из `EVD-079.candidate_patch_from_origin_dev` пометить как пробу RSS, не как реализацию: цикл `select` только по fd 0 и последующий `communicate()` не дренирует stdout/stderr serve. Норма — неблокирующий дренаж обоих pipe в том же тике, что EOF/TERM, иначе заполнившийся stderr (порядка 64 КиБ) останавливает event loop `opencode serve` и сторож первого события срабатывает на живом апстриме.
> - `attempt_id` для имени файла брать из `secrets` (непредсказуемый), режим каталога `0700`, `O_NOFOLLOW`, запись через atomic replace в переданном каталоге.
>
> 2. ПОЛНОТА: VERDICT=PASS
> WHY=REQ-001..020, AC-001..026, AD-001..004, границы BND-001..004, CD-001..002, конверт 46 полей HL-ENV, гейты C-MULT/S-HERD/H-CPU/R-BULK/T-LIFE/O-EXIT/M-SEM, threat model, views с вопросом и ссылкой, и дельта a5 (RW-001, RW-002, FU-001, FU-002) в пакете присутствуют. Память v6 сведена: замер EVD-079 `ru_maxrss` 31.71875 МиБ, `helper_estimate` 36.0, слот 216, запас 15.2 ≥ 15, `Mem_shared_max` 1296, 1552.0 ≤ 1638.4, слоты 6 / waiters 12 / cap 3 / 2048 МиБ не сдвинуты, H3 остаётся NOT_RUN. argv без многоточия, `--config` у вызовов ruff, cycle 6 и `plans/architect-06.json` совпадают с allowlist. Расхождение «73 EVD» против фактических 74 — учётная ошибка, не дыра в контракте (F-003).
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
> WHY=Выбранный путь укладывается в stdlib `ThreadingHTTPServer` и три файла кодера. Изолированная проба EVD-079 на Python 3.14.7 подняла цепочку parent → helper → fake serve: шесть аргументов, `OPENCODE_BIN` из argv, в `serve_env` его нет, тяжёлые модули не загружены, пик helper 31.72 МиБ < 36.0. VER-004 на копии (обычный и hostile `line-length=60`) дал exit 0, catalog 8/8, три frozen SHA без изменений, E402 сверх `import zen_catalog as zc` не появился. Ранний `SystemExit` до `reload_catalog()` наблюдаем. Оставшийся дефект lease — правка контракта, она не упирается в невозможный механизм. Stage3 и H0..H9 честно NOT_RUN.
>
> 4. РИСКИ: VERDICT=FAIL
> WHY=При росте отказов (смерть parent, затем helper, шесть слотов) очистка смотрит не туда, куда helper пишет lease, поэтому группа `child_pgid` остаётся жить — тот же класс инцидента, что [F-30] / [F-14], уже после «исправленного» T-LIFE. Фиксированный каталог в `/tmp` общий для всех прогонов одного UID: параллельный VER-005 и чужой локальный процесс бьются в одно имя `lease-<attempt_id>.json`. Отдельно, уже внутри конверта: рост serve над idle 156.8 МиБ имеет 15.2 МиБ на слот; это согласовано с приёмкой RW-001 и режется H3 без waiver, само по себе бюджет не разъезжается. Пик FD в тексте занижен на концы lifeline (F-002): заявленные 114, одновременно живут steady `lifeline_w` и кратковременные `lifeline_r`, итог 120. Потолок 128 пока держит, запас 14 дескрипторов на бумаге и 8 по факту.
> СОВЕТЫ (при FAIL):
> - Свести lease, reaper и негативный оракул к одному `lease_dir`, как в советах критерия 1. Отдельный тест: SIGKILL parent после записи lease, убить helper, поднять мост, убедиться, что serve/helper/temp root этого attempt исчезли, а чужой PGID не получал сигнал.
> - Пересчитать пик parent FD как 108 + 6 `lifeline_w` + 6 transient `lifeline_r` = 120 и записать 120 в `parent_upper_bound`, C-MULT-I5 и `fd_accounting`. Не поднимать envelope 128, пока 120 ≤ 128.
> - H3 оставить NOT_RUN. Порог включения не ослаблять: слот > 216 МиБ или станция > 1638.4 МиБ блокирует H7. В замер H3 входит RSS serve под промптом ~103 КБ, не idle 156.8.
> - Нормативный helper дренирует stderr/stdout serve без `communicate()` после простоя, иначе ложный `first_event_timeout` при болтливом дочернем процессе.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
> WHY=AD-001 сравнивает больше двух живых вариантов и фиксирует причину выбора: A2 делит failure domain и не даёт доказанной смены egress; B упирается в 429 [F-24]/[F-25]; L не снимает RC-1 [F-17]/[F-18]; `--stdio` есть во флаге [EVD-078], публичной схемы IPC нет; `--port 0` без устойчивого объявления порта отвергнут. Нагрузка разобрана на выбранном дереве: 6 пар helper+serve, cap 3, spawn 1/с, память 216 МиБ на слот, при превышении H3 фича не включается. AD-002..004 тоже two-way (безусловный статус t=0, только TIMEOUT 1800, подъём потолка до 4).
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
> WHY=Пакет остаётся на фактическом stdlib-мосте `:9883`, без слоёв Litestar/FastAPI. Факты решений лежат в [F-01]..[F-49] и EVD-070..079. Публичная форма OpenAI SSE, порт, Google-срез (`_run_env` / `_stream_google_sse` / `_execute_google_once`) и запрет записи `opencode.db` сохранены; изоляция serve через `OPENCODE_DB=:memory:` при read-only auth для run/opencode-go указана. `dynamic_config.json` в git не создаётся, кодовый default false, H7 только после H3/H6. `muse-bridge`, DSH и `~/.dsh` архитектор не меняет. Статус APPROVED в пакете прямо назван внутренним кандидатом, не вердиктом совета; квитанция ARCH_GATE совпадает с sha256 пакета.
>
> F-001 [blocking] Два корня lease: фиксированный `/tmp/opencode-zen-bridge-leases/` и позиционный `lease_dir`
> - Якорь: architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.registry`, `details.crash_recovery.creation`, `details.helper_cli_contract`); architecture-packet.json#VER-005 (`clean_room_helper_oracle`, `orphan_oracles`); architecture-packet.json#THREAT-001; architecture-packet.json#EVD-079
> - Правило: REQ-008 / AC-011, T-LIFE/v1, THREAT-001; приёмка RW-002 («use only the passed isolated lease directory»)
> - Доказательство: spawn требует создать `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json` и тут же «use only the passed isolated lease directory». Registry reaper — тот же `/tmp/opencode-zen-bridge-leases/`. EVD-079 передаёт `/private/tmp/zen-arch6-probe-work-jfgscb15/leases` и в теле пробы файл lease не пишет.
> - Ожидаемое исправление: один каталог — аргумент `lease_dir`; reaper и THREAT-001 ссылаются только на него; оракул с нестандартным каталогом проверяет и запись, и подбор при следующем старте.
> - Критерий проверки: в пакете нет второго обязательного пути; сценарий «parent мёртв, helper мёртв, lease остался» снимает только свой PGID.
> - priority: blocking
>
> F-002 [pre-existing][sweep] Верхняя оценка FD parent 114 не включает одновременно steady `lifeline_w` и transient `lifeline_r`
> - Якорь: architecture-packet.json#AD-001 (`details.resource_accounting.fd`); architecture-packet.json#VER-005 (`process_resource_oracle.resources.fd`)
> - Правило: C-MULT-I5, `FD_worker` 128
> - Доказательство: сумма полей baseline+clients+lanes+drains+ports+lsof+watchdog+lease = 108. Текст прибавляет только 6 transient read-концов и публикует 114. `lifeline_definition` отдельно держит 6 write-концов `lifeline_w` на всё время запроса. Пик 108+6+6 = 120.
> - Ожидаемое исправление: записать peak 120 и пересчитать запас до 128 (8, не 14). Envelope 128 не поднимать.
> - Критерий проверки: 120 ≤ 128 во всех копиях fd-абзаца; H3 меряет фактический пик, включая окно setup.
> - priority: non-blocking
>
> F-003 [sweep] Счётчик evidence в `semantic_checks` отстаёт от EVD-079
> - Якорь: architecture-packet.json#EVD-079
> - Правило: полнота `evidence[]` / `semantic_checks.evidence_refs`
> - Доказательство: строка «73 EVD records» соответствует диапазону до EVD-078 (64 записи EVD-001..064 плюс 9 записей EVD-070..078). EVD-079 в массиве есть, итог 74.
> - Ожидаемое исправление: заменить 73 на 74 и включить EVD-079 в перечень проверенных записей semantic_checks.
> - Критерий проверки: число объектов `evidence[]` с id `EVD-*` равно числу в semantic_checks.
> - priority: non-blocking
>
> F-004 [sweep] Единственный вложенный код helper дренирует дочерние pipe после выхода, а норма требует дренаж в том же тике, что EOF
> - Якорь: architecture-packet.json#EVD-079 (`helper_cli_probe_source`, `candidate_patch_from_origin_dev`); architecture-packet.json#AD-001 (`helper_cli_contract.validation`)
> - Правило: AD-001 drain-инвариант; REQ-006 (ложный `first_event_timeout`)
> - Доказательство: проба крутит `select` по fd 0 и только потом вызывает `proc.communicate()`. Контракт: «Drain-ready pipes concurrently with fd0 EOF/TERM and child poll, no child pipe wait delaying EOF». Докстринг помечает тело как не-Stage3, но diff лежит в пакете как `candidate_patch_from_origin_dev`.
> - Ожидаемое исправление: в репродукции пробы прямо написать, что копируется только ранний `if/else` импортов и замер RSS; тело с `communicate()` в Stage3 запрещено. Нормативный цикл — неблокирующее чтение stdout и stderr serve.
> - Критерий проверки: ревью Stage3 отвергает перенос `communicate()`-после-простоя; тест с дочерним процессом, пишущим >64 КиБ в stderr до первого SSE, не получает `first_event_timeout`, пока сокет событий жив.
> - priority: non-blocking
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `muse-wonder-full-1.0`)

> PANEL-NONCE: b92d65493268086b
> ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b
> 1. КОРРЕКТНОСТЬ: VERDICT=PASS
>    WHY=RW-002 закрыт замкнутым шестиаргументным argv и ранним `--serve-helper` до `reload_catalog/_DEFAULT_RESILIENCE` и тяжёлых импортов (`architecture-packet.json#AD-001`, `architecture-packet.json#EVD-079`); цепочка parent→helper→serve, listener proof `listener_pid==serve_pid`, fallback barrier и form-cancel до валидации схемы не противоречат [F-17]..[F-22], [F-36], [F-37]; публичный контракт :9883 и Google slices заморожены литеральными SHA в `VER-004`.
> 2. ПОЛНОТА: VERDICT=PASS
>    WHY=Покрыты REQ-001..REQ-020 и AC-001..AC-026 через VER-001..VER-005, включая GroupA без FakeServe и GroupB с шестью frozen fixture families, clean-room helper oracle, listener takeover negative, watchdog 20/60/60, stall heartbeat 15с и H0..H9 как NOT_RUN; FU-001/FU-002 закрыты явным `--config root/ruff.toml` и cycle6/architect-06; ADR-0005 честно deferred вне трёхфайлового allowlist, а не выдан за созданный.
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
>    WHY=Что нужно чтобы взлетело, определено исполнимо: Stage3a→3b в ровно трёх coder-файлах, только stdlib при Python 3.14.7/ruff 0.17.2/basedpyright 1.40.2/opencode v2.1.2; изолированные пробы EVD-075..EVD-079 показали закрытые ruff ranges, all3 errorCount=0/reportAny=125/catalog 8/8 и реальную цепочку с fake_serve_bin при пустом HOME; включение только H7 после H3/H6, default=false и runtime JSON без правок start.sh дают дешёвый откат даже если живой H3/H6 не пройдёт.
> 4. РИСКИ: VERDICT=PASS
>    WHY=RW-001 арифметически замкнут в MiB: helper observed 31.718750 < estimate 36.0 с резервом 4.281250 (`architecture-packet.json#EVD-079`), serve idle 156.8+36.0+probe 8.0=200.8, per-slot 216 с запасом 15.2≥15 под 103KB, 6*216+256=1552.0≤1638.4 при неизменных 6/12/cap3; главный остаточный риск — loaded serve RSS сверх idle и живая Zen permission совместимость — не замаскирован, а вынесен в блокирующие H3/H6 без waiver до H7, как и orphan/crash recovery, quota [F-23] и duplicate generation до delivered barrier.
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=Рассмотрены ≥2 альтернативы с причиной выбора C/A1: L не закрывает RC-1, A2 общий daemon теряет изоляцию и per-spawn env, B прямой Zen не подтверждён из-за 429 [F-24]/[F-25], `--stdio` без публичной схемы по EVD-078, `--port 0`, empty XDG и shared DB отклонены с фактами EVD-071; при росте нагрузки первым ломается именно per-slot RSS/SQLite contention, поэтому выбран OPENCODE_DB=:memory:, cap3, bulkhead 6/12 и H3 6×103KB×3 как стоп-гейт, а не повышение лимитов.
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Пакет соответствует фактическому автономному stdlib ThreadingHTTPServer стеку без навязывания Litestar/FastAPI, scope ограничен bridges/opencode-zen-bridge, frozen scope и чужие мосты/Google не трогаются, ARCH_GATE PASS для sha 88c02c37; независимая перепроверка seed: seed_input дословно совпал, SEED=5c2d1474, seed_hex=5c2d14744141c84ebad959ce30b22b52158558265cf65db5e7bfcc83ad76e9e0, ranked_order=[gpt-6.1-sol-high,muse-wonder-full-1.0,grok-4.7-high,claude-sonnet-5-5-high,gemini-4-argon-high] совпал с manifest r18 при исключённой авторской семье OpenAI.
> ОБЩИЙ ВЕРДИКТ: PASS


### Seat 3 (`visionary`, `claude-sonnet-5-5-high`)

> PANEL-NONCE: fb077b9e5d4f6cf5
> ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b
>
> **Closure check (verify-fixed, v5→v6):**
> - **RW-001 (память helper):** закрыт. `helper_estimate` повышен с 12.0 до 36.0 MiB. EVD-079 измерил реальный `--serve-helper` с полным шестиаргументным argv: peak 31.71875 MiB (`ps` и `ru_maxrss`, перевод в MiB указан). Резерв Stage 3 равен 4.28125 MiB.
>   - Арифметика сходится: 156.8+36+8=200.8; 216−200.8=15.2 ≥ 15; 6·216=1296; 1296+256=1552 ≤ 1638.4.
>   - Старые 12.0 / 12–14 MiB в действующих секциях не встречаются: `memory_ssot`, `capacity_formula`, QA-009, RISK-003, `H3_rollout_gate`, `rework_summary`.
>   - Ранний диспатчер стоит до тяжёлых импортов. E402 новых нет (EVD-076/077/079: 0 findings).
>   - Три замороженных SHA не изменены, VER-004 это проверяет.
> - **RW-002 (argv):** закрыт. Во всех секциях единый замкнутый argv из 6 позиционных аргументов. Есть `_run_serve_helper_cli(args: list[str]) -> int` с валидацией до spawn, `opencode_bin` приходит от родителя, `OPENCODE_BIN` в `serve_env` не попадает. Есть clean-room оракул (пустой HOME, monkeypatch `OPENCODE_BIN`, audit hook на `state/log/dynamic_config`). EVD-079 содержит 11 негативных argv-кейсов с exit=2.
> - **FU-001 (ruff):** закрыт. Явный `--config str(root/'ruff.toml')` стоит на каждом вызове. Есть проверка `formatted_copy.read_bytes()==files[0].read_bytes()`. Нормальный и «hostile XDG» прогоны оба exit 0.
> - **FU-002 (cycle 6):** закрыт. `cycle=6`, `role_plan` → `architect-06.json`, оба пути allowlist обновлены, адресат — a6/r15. Council PASS пакет не заявляет.
>
> 1. КОРРЕКТНОСТЬ: VERDICT=PASS
>    WHY=Внутренняя согласованность подтверждена по якорям `architecture-packet.json#EVD-079`, `#VER-005`, `#AD-001`, `rework_resolutions_a5`.
>    - Топология parent → helper(новая сессия) → serve (та же PGID) единообразна.
>    - Порядок «lease → handshake → lsof → READY» сохранён.
>    - FD-арифметика сходится: 36+18+18+12+6+6+6+6=108, +6 lifeline_r = 114 ≤ 128.
>    - Потоки: 1+18+6+6+6+12+6=55.
>    - Публичный контракт :9883, Google-маршрут и `_run_env` не тронуты.
>    - `contract_deltas` содержит только допустимые поведенческие изменения (CD-001/002) из брифа.
>
>    Замечание без блокировки: REQ-004 сужен grace-логикой до thinking-enabled slow-старта. Сужение явно оформлено в AD-002/CD-001 и проверяется в VER-005, а не скрыто.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 2. ПОЛНОТА: VERDICT=PASS
>    WHY=Покрыты REQ-001..020 с привязкой к VER-001..005. Есть 46 полей HL-ENV, гейты C-MULT/S-HERD/H-CPU/R-BULK, T-LIFE, O-EXIT и M-SEM (с двойным доказательством для N/A). Есть fallback decision table, threat model с 5 угрозами, матрицы верификации, rollout H0..H9 и откат без рестарта.
>    - Эталонные источники указаны: muse-bridge, F-40/F-41.
>    - Живые H0..H9, Stage 3 и H3/H6 честно помечены NOT_RUN. Это допустимо для архитектурной стадии.
>
>    Замечание без блокировки: ADR-0005 отложен вне замороженного allowlist. Основание записано в `deferred`.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
>    WHY=Ключевые механики подтверждены изолированными пробами на целевой машине (Python 3.14.7, ruff 0.17.2, basedpyright 1.40.2):
>    - минимальный helper-skeleton;
>    - полный VER-004 (exit 0, catalog 8/8, errors 0, reportAny 125);
>    - запись форматтера на копии без изменения замороженных срезов.
>
>    Объём сосредоточен в одном 4000+-строчном `server.py` плюс два тестовых файла, как требует allowlist. Стратегически это самый трудоёмкий кусок (helper, lease, reaper, terminal_quiescence, ServeHealth, динамический конфиг). Поставка поэтапная (Group A → Group B), kill-switch по умолчанию выключен (`default=false`), включение только после H3/H6.
>
>    Замечание без блокировки (стратегическое): резерв на код Stage 3 helper — 4.28 MiB (~13%), запас слота — 0.2 MiB сверх 15 MiB. Проба `drain/lease/SIGSTOP-quiescence` не нагружена, а оценки probe=8 MiB и serve idle=156.8 MiB не нагрузочные. Риск ловит гейт H3 (превышение блокирует H7 без waiver). Пакет это прямо фиксирует, поэтому это не дефект.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 4. РИСКИ: VERDICT=PASS
>    WHY=Заложены:
>    - листенер-takeover (listener_pid==serve_pid, PGID, 0 байт секретов чужому);
>    - parent-SIGKILL на пяти точках, helper/reaper, PID/PGID reuse;
>    - permission/form → reject/cancel → interrupt с барьером Step2;
>    - fail-closed на 401/403;
>    - раздельные `_ServeHealth` и `_UpstreamBreaker`;
>    - потолки cap=3, `_RetryBudget`, слоты 6/12;
>    - sanitization env на всех трёх ветках;
>    - явный non-exactly-once для окна «до заголовков prompt».
>
>    При росте нагрузки главные точки отказа названы:
>    - RSS на слот (216 MiB, H3);
>    - FD/потоки (поток-flood вне слотов, пакет это оговаривает);
>    - SQLite — снят `:memory:`;
>    - квота Zen и egress IP, ротация которого не доказана (RISK-002 честно сформулирован).
>
>    Остаточные риски: вся live-приёмка NOT_RUN, а реальная совместимость deny/ask_reject с Zen доказывается только H6. Это явно отражено в Q-002 и RISK-001.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=В AD-001 рассмотрены:
>    - L (только watchdog/status);
>    - A2 (общий демон);
>    - B (прямой Zen HTTP, 429 по F-24/F-25);
>    - `--port 0`;
>    - `serve --stdio` (EVD-078, без публичной схемы);
>    - общая БД + `_StartupGate`;
>    - пустой `XDG_DATA_HOME`;
>    - разделение 3a/3b.
>
>    Причины выбора A1+C указаны. Выбранный путь стратегически выигрывает: он единственный даёт настоящие `reasoning.delta` и `text.delta` (F-17..F-19) и оставляет обратимость через legacy `run`. Он открывает дальнейшее развитие — потоковый прогресс шагов, вынос transport-слоя, а при появлении доказанной квоты и миграцию на B или A2 — без смены публичного контракта.
>
>    Замечание без блокировки: дословное многократное дублирование helper-контракта (~15 копий) повышает риск будущего расхождения. Сейчас копии идентичны. Рекомендуется при реализации опираться на единственный источник `AD-001.details.helper_cli_contract`.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Пакет учитывает реальный stdlib-стек (`ThreadingHTTPServer`) и не навязывает Litestar/FastAPI. Он не меняет внешний контракт без указания в задаче и не выходит за scope: `muse-bridge`, `~/.dsh`, `opencode.db` и Google-маршрут не затрагиваются.
>    - `coder_target_files` — ровно три файла.
>    - Нет новых зависимостей и suppressions.
>    - Фичефлаг соответствует директиве GigaRC: код `default=false`, runtime-JSON, включение только на H7 после H3/H6.
>    - Пакет не заявляет Council PASS/ARCH_GATE_PASS; бюджет 5/5 сохранён.
>
>    СОВЕТЫ (при FAIL): не требуются.
>
> ОБЩИЙ ВЕРДИКТ: PASS


---

## Раунд D1 (`panel/arch/r21`)

### Seat 1 (`skeptic`, `gemini-4-argon-high`)

PANEL-NONCE: 95d0cb75ab743776
ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b
Подтверждение канона: общий канон ~/Мой диск/Context/AGENTS.md прочитан целиком (до <!-- КАНОН-КОНЕЦ -->); проектные файлы правил в рабочей папке отсутствуют.

AMEND F-001 — priority=non-blocking — причина: NEW: architecture-packet.json:2568, architecture-packet.json:2589, architecture-packet.json:2767, architecture-packet.json:1809, architecture-packet.json:1424 — проверил: architecture-packet.json:1811, architecture-packet.json:1874, architecture-packet.json:1987, architecture-packet.json:2568, architecture-packet.json:2589, architecture-packet.json:2591, architecture-packet.json:2767 — нормативные секции helper_cli_contract.validation (architecture-packet.json:2767) и crash_recovery.creation (architecture-packet.json:2589) уже обязывают helper писать исключительно в переданный позиционный lease_dir, проба EVD-079 (architecture-packet.json:1424, architecture-packet.json:1455, architecture-packet.json:1471) явно ограничена Stage-2 замером argv/импортов/RSS, а совместное выполнение оракулов VER-005 clean_room_helper_oracle (architecture-packet.json:1874) и orphan_oracles «restart bridge with retained lease -> safe startup reaper» (architecture-packet.json:1809, architecture-packet.json:2594) однозначно задаёт в Stage 3 единый конфигурируемый атрибут Server.lease_dir (с боевым дефолтом /tmp/opencode-zen-bridge-leases/ по architecture-packet.json:2568 и переопределением на tmp_path в тестах), который родитель передаёт в argv[7] и сканирует в startup_reaper; остаточный литерал /tmp/... во фразе v5 (architecture-packet.json:1811, architecture-packet.json:1987) — редакционный хвост, а не архитектурный блокер.
DISPUTE F-002 — класс: invalid — контр-evidence: NEW: architecture-packet.json:3633 ("steady108=36baseline+18clients+18HTTP+12helperdrains+6reserve+6probe pipes+6lifeline_w+6leasehandles;transient6lifeline_r=>114<=128"), architecture-packet.json:2728 ("parent_watchdog_pipes": 6), architecture-packet.json:2732-2734 — проверил: architecture-packet.json:1816-1830, architecture-packet.json:2722-2735, architecture-packet.json:3633, architecture-packet.json:3685-3699 — в расчёте 120 допущен двойной учёт 6 родительских дескрипторов lifeline_w: стационарная сумма steady=108 (36+18+18+12+6+6+6+6) уже включает слагаемое parent_watchdog_pipes=6 (architecture-packet.json:2728), которое в field_sources.FD_worker (architecture-packet.json:3633) прямо расшифровано как 6lifeline_w, поэтому пик при одновременном спавне с учётом 6 краткоживущих дескрипторов чтения transient_lifeline_read_ends равен строго 108+6=114 <= 128.
AGREE F-003 rev=1 — проверил: architecture-packet.json:1420-1557, architecture-packet.json:4540, architecture-packet.json:5333-5344 — в массиве evidence[] фактически присутствуют 74 записи EVD-* (64 записи EVD-001..EVD-064 и 10 записей EVD-070..EVD-079), тогда как в текстовой сводке semantic_checks.evidence_refs (architecture-packet.json:4540) осталась строка «73 EVD records» без упоминания EVD-079; неблокирующая учётная неточность подтверждена.
AGREE F-004 rev=1 — проверил: architecture-packet.json:1453-1456, architecture-packet.json:1471, architecture-packet.json:2767, architecture-packet.json:2769 — хотя нормативный контракт helper (architecture-packet.json:1453, architecture-packet.json:2767) уже требует конкурентного неблокирующего дренажа stdout/stderr дочернего serve в каждом тике цикла наблюдения за fd 0, а EVD-079 (architecture-packet.json:1455, architecture-packet.json:1471, architecture-packet.json:2769) явно помечен как изолированная Stage-2 проба RSS/argv, вложенный diff candidate_patch_from_origin_dev (architecture-packet.json:1456) использует select([0]) с последующим proc.communicate(); сохранение F-004 как non-blocking предохранителя для Stage 3 и VER-005 (чтобы кодер не перенёс тестовую заглушку вместо неблокирующего дренажа >64 КиБ stderr) обосновано.

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Блокеры переделки a5 закрыты верифицируемыми фактами: RW-002 устранён единым закрытым 6-аргументным контрактом `--serve-helper` (`attempt_id`, `port`, `opencode_bin`, `lease_dir`, `expected_ppid`, `expected_parent_lstart`) с ранним барьером `if sys.argv[1:2] == ["--serve-helper"]: raise SystemExit(_run_serve_helper_cli(sys.argv[2:]))` строго до тяжёлых импортов (`sqlite3`, `http.client`, `http.server`, `zen_catalog`) и до `reload_catalog()`/`_DEFAULT_RESILIENCE` (`architecture-packet.json:1450-1456`, `architecture-packet.json:2762-2770`, 11 негативных кейсов `exit=2`). Структурные границы `architecture-packet.json#BND-001`..`BND-004` и компонентные контракты `architecture-packet.json#CD-001`..`CD-002` ацикличны; `OPENCODE_BIN` передаётся только через позиционный `argv` без утечки в окружение `serve`, а секреты провайдеров вычищаются согласно `[F-08]` и `[F-28]`. Бюджет дескрипторов сходится без ошибок (`108` steady + `6` transient `lifeline_r` = `114 <= 128`, `architecture-packet.json:2722-2735`, `architecture-packet.json:3633`), а жизненный цикл lease непротиворечив при штатной трактовке `/tmp/opencode-zen-bridge-leases/` (`architecture-packet.json:2568`) как дефолта единого конфигурируемого `Server.lease_dir` (F-001 понижен до `non-blocking`).

2. ПОЛНОТА: VERDICT=PASS
   WHY=Пакет v6 содержит полную сквозную трассировку `REQ-001..020`, `AC-001..026`, `AD-001..004`, `QA-001..009`, `BND-001..004`, `CD-001..002`, `VIEW-001..004`, `RISK-001..012`, `THREAT-001..005`, `VER-001..005`, план эволюции и матрицу приёмки (`architecture-packet.json:4455-4625`). Секция `high_load_envelope` (`HL-ENV/v1`, все 46 обязательных полей без `null`/`TBD`, `architecture-packet.json:3510-3705`), гейты `C-MULT`, `S-HERD`, `H-CPU`, `R-BULK`, `T-LIFE`, `O-EXIT`, `M-SEM` и аудит 24 стоп-кодов полностью сведены. Математика памяти RW-001 синхронизирована во всех SSoT-секциях (`EVD-079` `architecture-packet.json:1427-1449`, `VER-005` `architecture-packet.json:1831-1850`, `AD-001` `architecture-packet.json:2736-2755`, `QA-009` `architecture-packet.json:3066`, `RISK-003` `architecture-packet.json:3230`, `H3_rollout_gate` `architecture-packet.json:3400`, `high_load_envelope` `architecture-packet.json:3708-3829`): живой замер `ru_maxrss=31.71875 MiB < helper_estimate=36.0 MiB`, слот `156.8+36.0+8.0=200.8 <= 216 MiB` (запас `15.2 >= 15.0 MiB` под промпты 103 КБ), `Mem_shared_max=6*216=1296 MiB`, `1296+256=1552.0 <= 1638.4 MiB` (`0.80*2048`), гейт `H3` честно оставлен в `NOT_RUN`. Пункты `FU-001` (явный `--config` для Ruff и проверка при враждебном `XDG_CONFIG_HOME`, `architecture-packet.json:1474-1499`) и `FU-002` (`cycle: 6`, `plans/architect-06.json`, `architecture-packet.json:6`, `architecture-packet.json:4443-4449`) закрыты; учётная опечатка `73` против `74` записей `EVD-*` (F-003) на полноту контракта не влияет.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Архитектура реализуема исключительно средствами стандартной библиотеки Python 3.14 (`ThreadingHTTPServer`, `subprocess`, `select`, `os`, `[F-01]`, `[F-02]`) в пределах трёх разрешённых файлов этапа Coder (`opencode_zen_bridge.py`, `test_bridge.py`, `test_bridge_integration.py`) без касания замороженного `zen_catalog.py` (`[F-05]`) и неизменных SHA-срезов (`1c51b28f...`, `5914c965...`, `88d794cc...`, `architecture-packet.json:1495-1498`). Чистая проба `EVD-079` (`architecture-packet.json:1420-1499`) подтвердила запуск цепочки parent -> `python3 -I` `--serve-helper` -> fake `serve` при пустом `HOME`, работоспособность `monkeypatch` для `OPENCODE_BIN`, отсутствие тяжёлых модулей в `sys.modules`, отсутствие новых `E402` и запас `4.28 MiB` между живым пиком `31.72 MiB` и оценкой `36.0 MiB` на дописывание lease/reaper и неблокирующего дренажа пайпов в Stage 3 (неблокирующие предохранители F-001 и F-004).

4. РИСКИ: VERDICT=PASS
   WHY=Поведение при росте нагрузки и каскадных сбоях детерминировано и ограничено жёсткими инвариантами: при всплеске параллельных запросов сверх `6` активных слотов и `12` ожидающих (`queue_wait_cap=5.0s`) либо сверх `3` одновременных спавнов (`spawn_gate=3` с джиттером) лишняя нагрузка немедленно отсекается кодами `429`/`503` без неконтролируемого порождения потоков или подпроцессов (`S-HERD`, `R-BULK`, `architecture-packet.json:3520-3555`, `architecture-packet.json:3850-3890`); мост не делает внутренних ретраев (`M_eff=1 <= 3`, `C-MULT`, `[F-14]`, `[F-26]`, `architecture-packet.json:3835-3848`), исключая шторм повторов в Zen API; при внезапной гибели родителя (`SIGKILL`, `[F-30]`) изолированный helper по EOF на `fd 0` и сверке `(expected_ppid, expected_parent_lstart)` гасит процессную группу `-child_pgid` каскадом `SIGTERM -> 2s -> SIGKILL`, а при гибели и родителя, и helper остаточный процесс снимается `startup_reaper` с проверкой `ps lstart` против переиспользования PID (`THREAT-001`, `RISK-001`, `architecture-packet.json:2565-2615`); зависание SSE-потока или обрыв клиента купируются `first_event_watchdog` (`45s`/`20s`), `idle_event_timeout`, `stream_wall_clock_cap` и немедленным освобождением слота при `BrokenPipeError` (`[F-13]`, `[F-29]`), а риск превышения памяти под реальным стримингом закрыт блокирующим гейтом выката `H3` до `H7` (`architecture-packet.json:3400`).

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=В каждом ключевом архитектурном решении `AD-001..004` (`architecture-packet.json:1975-2960`) сопоставлены минимум две реальные альтернативы с анализом отказов при росте нагрузки: в `AD-001` изолированный пер-запросный `opencode serve` с ранним `python3 -I` helper обоснованно выбран против общего долгоживущего пула `serve` (риск межзапросного смешения сессий и падения всех активных стримов при креше одного воркера, `[F-24]`), против прямого `opencode run --format json` (`0` событий `reasoning-delta` в `EVD-001..005`, `[F-17]`, `[F-22]`) и против helper с полным импортом моста (раздувание RSS до `~42-50 MiB` на слот против измеренных `31.72 MiB` в `EVD-079`); в `AD-002` связка SSE `/event` + `/session/{id}/prompt_async` выбрана против синхронного `/session/{id}/message`, буферизующего ответ до конца генерации и срывающего realtime TTFB при длинном reasoning (`REQ-001`); в `AD-003` ограниченный пул `6` слотов / `12` waiters / `3` spawn gate на `ThreadingHTTPServer` выбран против неограниченного thread/process-per-request (гарантированный OOM бюджета `2048 MiB` уже при `>=10` процессах `serve`) и против полного переписывания на `asyncio` (нарушение замороженных границ `do_not_change`); в `AD-004` пер-запросные изолированные `XDG_DATA_HOME`/`HOME` выбраны против общей SQLite-базы `~/.local/share/opencode`, деградирующей в `SQLITE_BUSY` при 6 параллельных стримах.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Архитектурный пакет v6 строго соблюдает все ограничения `do_not_change` из брифа переделки `panel-rework-brief-arch-a5.json` (`max_slots=6`, `waiters=12`, `spawn_gate=3`, `host_ram_budget_mib=2048`, статус `NOT_RUN` для `H3` и Stage-3 оракулов, неизменность `zen_catalog.py` `[F-05]` и публичного CLI моста `[F-04]` при внутреннем характере `--serve-helper`), укладывается в регламент `scope-and-contracts.md` (`cycle: 6`, `plans/architect-06.json`, соблюдение лимита `5/5` возвратов и allowlist артефактов без самоприсвоения вердикта Совета в `architecture-packet.json:4618-4619`) и опирается исключительно на подтверждённые факты репозитория и живых проб.
ОБЩИЙ ВЕРДИКТ: PASS

POSITIONS: 4/4
ANSWERS: 0/0


### Seat 2 (`realist`, `grok-4.7-high`)

PANEL-NONCE: c08aa01156283b2b
ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b
Подтверждение канона: общий канон ~/Мой диск/Context/AGENTS.md прочитан целиком (до <!-- КАНОН-КОНЕЦ -->); проектные файлы правил в рабочей папке отсутствуют.
AMEND F-001 — priority=blocking; locations=architecture-packet.json#AD-001,architecture-packet.json#VER-005,architecture-packet.json#THREAT-001,architecture-packet.json#EVD-079; fix=Оставить `/tmp/opencode-zen-bridge-leases/` только как боевое значение по умолчанию аргумента `lease_dir`, которое parent кладёт в argv и в поле lease. Helper пишет исключительно `lease_dir/lease-<attempt_id>.json`. Registry, startup reaper и THREAT-001 сканируют этот же каталог. Оракул VER-005 с иным `lease_dir` проверяет появление файла только там и снятие своей записи следующим стартом. — причина: NEW: architecture-packet.json#AD-001 (`details.spawn` требует создать `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json` и в том же контракте пишет `use only the passed isolated lease directory`; `details.crash_recovery.registry` фиксирует `/tmp/opencode-zen-bridge-leases/`; `details.helper_cli_contract.validation` требует только переданный каталог)
WITHDRAW F-002 — NEW: architecture-packet.json#AD-001 (`details.resource_accounting.fd`; `high_load_envelope.field_sources` для `FD_worker`) — проверил: architecture-packet.json#AD-001: steady 108 = 36+18+18+12+6+6+6+6, и слот `parent_watchdog_pipes` в формуле `FD_worker` уже назван `6lifeline_w`; transient `lifeline_r` +6 даёт `parent_upper_bound` 114 ≤ 128. Отдельные +6 write сверх 108 — двойной счёт.
1. КОРРЕКТНОСТЬ: VERDICT=FAIL
WHY=RW-002 закрыл шестиаргументный argv и ранний `--serve-helper` до тяжёлых импортов (`architecture-packet.json#AD-001`, `architecture-packet.json#EVD-079`), но жизненный цикл lease по-прежнему задаёт два обязательных корня. В `AD-001.details.spawn` helper «сразу» создаёт `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json`, а тот же spawn, `crash_recovery.creation` и `helper_cli_contract.validation` требуют писать только в переданный `lease_dir`. `crash_recovery.registry` и startup reaper смотрят фиксированный `/tmp/opencode-zen-bridge-leases/`. Clean-room EVD-079 передаёт другой каталог (`.../leases`) и файл lease не создаёт. Буквальное чтение A ломает VER-005 и сталкивает прогоны одного UID в одно имя. Буквальное чтение B оставляет reaper слепым: после смерти parent и helper orphan `opencode serve` не находится. REQ-008 / AC-011 и THREAT-001 на этом пути не исполняются ни одной из двух обязательных формулировок (F-001). Память v6, frozen SHA и ранний барьер импортов этому не противоречат.
СОВЕТЫ (при FAIL):
- Свести запись, registry, startup reaper и THREAT-001 к одному каталогу: позиционный `lease_dir`.
- Строку `/tmp/opencode-zen-bridge-leases/` оставить только как боевое значение по умолчанию, которое parent подставляет в argv и записывает в поле lease. Убрать из spawn и `crash_recovery.creation` второе обязательное создание файла по литеральному пути.
- Reaper сканирует только этот каталог. Оракул VER-005: при `lease_dir`, отличном от боевого пути, файл появляется лишь там, и следующий старт моста снимает именно эту запись и только свой PGID.
- На этом единственном каталоге сохранить уже заданные mode `0700`/`0600`, `O_NOFOLLOW` и atomic replace.
2. ПОЛНОТА: VERDICT=PASS
WHY=REQ-001..020, AC-001..026, AD-001..004, BND-001..004, CD-001..002, конверт 46 полей HL-ENV, гейты C-MULT/S-HERD/H-CPU/R-BULK/T-LIFE/O-EXIT/M-SEM, threat model и views с вопросом и ссылкой в пакете есть. Дельта a5 (RW-001, RW-002, FU-001, FU-002) закрыта по памяти, argv, `--config` ruff и cycle 6 / `plans/architect-06.json`. Замер EVD-079: `ru_maxrss` 31.71875 МиБ, `helper_estimate` 36.0, слот 216, запас 15.2 ≥ 15, `Mem_shared_max` 1296, 1552.0 ≤ 1638.4; слоты 6 / waiters 12 / cap 3 / 2048 МиБ не сдвинуты; H3 остаётся NOT_RUN. Расхождение «73 EVD» против 74 записей `evidence[]` — учётная строка `semantic_checks.evidence_refs`, сам EVD-079 в массиве есть (F-003). Это не дыра покрытия требований.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
WHY=Чтобы это взлетело, нужен один локальный контрактный правка lease (F-001) и затем Stage3a→3b ровно в трёх coder-файлах, только stdlib, на уже проверенном контуре Python 3.14.7 / ruff 0.17.2 / basedpyright 1.40.2 / opencode v2.1.2. Изолированная проба EVD-079 подняла parent → helper → fake serve: шесть аргументов, `OPENCODE_BIN` из argv, в `serve_env` его нет, тяжёлые модули не загружены, пик helper 31.72 МиБ < 36.0. VER-004 на копии (обычный и hostile `line-length=60`) дал exit 0, catalog 8/8, три frozen SHA без изменений. Нормативный дренаж stdout/stderr уже записан в `helper_cli_contract.validation`; тело пробы с `communicate()` помечено как не-Stage3 (F-004) и в объём полёта не входит. Включение только H7 после H3/H6, кодовый default false и runtime JSON без правки start.sh дают откат, если живой H3 или H6 не пройдёт. Объём — helper, lease, reaper, terminal_quiescence, ServeHealth и динамический конфиг внутри одного `server.py` плюс два тестовых файла, поставка Group A затем Group B. Stage3 и H0..H9 честно NOT_RUN. Механизм lease на stdlib реализуем; блокирует не отсутствие средства, а две обязательные формулировки каталога.
4. РИСКИ: VERDICT=FAIL
WHY=При смерти parent и затем helper очистка и запись смотрят в разные каталоги, поэтому группа `child_pgid` остаётся жить — тот же класс инцидента, что [F-30] / [F-14], уже на пути «исправленного» T-LIFE (F-001). Фиксированный каталог в `/tmp` общий для прогонов одного UID: параллельный VER-005 и соседний локальный процесс бьются в одно имя `lease-<attempt_id>.json`. Бюджет памяти на взлёт согласован и режется гейтом: serve idle 156.8 + helper 36.0 + probe 8.0 = 200.8, запас слота 15.2 ≥ 15, станция 1552.0 ≤ 1638.4; превышение слота 216 или станции 1638.4 блокирует H7 без waiver, H3 остаётся NOT_RUN. Пик FD parent в пакете 114 ≤ 128: `6lifeline_w` уже внутри steady 108 (F-002 снят как двойной счёт). Копирование `communicate()` из пробы даёт ложный `first_event_timeout` при stderr около 64 КиБ; нормативный контракт это уже запрещает, остаток — F-004, non-blocking.
СОВЕТЫ (при FAIL):
- Свести lease, reaper и негативный оракул к одному `lease_dir`, как в советах критерия 1. Боевой `/tmp/opencode-zen-bridge-leases/` передавать аргументом, а не вторым корнем.
- Отдельный тест: SIGKILL parent после записи lease, убить helper, поднять мост и убедиться, что serve, helper и temp root этого attempt исчезли, а чужой PGID сигнала не получал.
- H3 оставить NOT_RUN. Порог не ослаблять: слот > 216 МиБ или станция > 1638.4 МиБ блокирует H7. В замер H3 входит RSS serve под промптом ~103 КБ, вместе с helper и probe.
- В Stage3 переносить ранний барьер импортов и замер RSS. Цикл с `communicate()` после простоя не копировать: норматив — неблокирующее чтение stdout и stderr serve в том же тике, что EOF/TERM (F-004).
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
WHY=AD-001 сравнивает больше двух живых вариантов и фиксирует причину выбора C/A1. L не снимает RC-1 [F-17]/[F-18]. A2 делит failure domain и не даёт доказанной смены egress. B упирается в 429 [F-24]/[F-25]. `--stdio` есть во флаге [EVD-078], публичной схемы IPC нет. `--port 0` без устойчивого объявления порта, пустой XDG и общая БД отклонены по EVD-071. При росте нагрузки первым ломается per-slot RSS и SQLite contention, поэтому выбраны `OPENCODE_DB=:memory:`, cap 3, bulkhead 6/12 и стоп-гейт H3, а не подъём лимитов. AD-002..004 тоже two-way: безусловный статус t=0, только TIMEOUT 1800 и подъём потолка до 4 отвергнуты с причиной.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
WHY=Пакет остаётся на фактическом stdlib-мосте `:9883` (`ThreadingHTTPServer`), без слоёв Litestar/FastAPI. Факты решений лежат в [F-01]..[F-49] и EVD-070..079. Публичная форма OpenAI SSE, порт, Google-срез (`_run_env` / `_stream_google_sse` / `_execute_google_once`) и запрет записи `opencode.db` сохранены; изоляция serve через `OPENCODE_DB=:memory:` при read-only auth для run/opencode-go указана. `dynamic_config.json` в git не создаётся, кодовый default false, H7 только после H3/H6. `muse-bridge`, DSH и `~/.dsh` архитектор не меняет. Статус APPROVED назван внутренним кандидатом; квитанция ARCH_GATE совпадает с sha256 пакета. Сверка seed r21: seed_input дословно равен строке обязанности и manifest; seed_hex=66f3a17d3f2358141014ed0ad020434e133f42dc3f808e9d97e70a34249a981c (SEED=66f3a17d); ranked_order=[gpt-6.1-sol-high, grok-4.7-high, claude-sonnet-5-5-high, gemini-4-argon-high, muse-wonder-full-1.0] совпал с manifest r21 при исключённой авторской семье OpenAI.
ОБЩИЙ ВЕРДИКТ: NEEDS WORK
POSITIONS: 0/0
ANSWERS: 0/0


### Seat 3 (`visionary`, `muse-wonder-full-1.0`)

PANEL-NONCE: cbf4fd3f1254dc15
ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b
Подтверждение канона: общий канон ~/Мой диск/Context/AGENTS.md прочитан целиком (до <!-- КАНОН-КОНЕЦ -->); проектные файлы правил в рабочей папке отсутствуют.
AMEND F-001 — priority=non-blocking; locations=architecture-packet.json:1987,architecture-packet.json:2568,architecture-packet.json:2589,architecture-packet.json:2767; fix=В spawn/creation заменить литерал `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json` на `lease_dir/lease-<attempt_id>.json`, один раз определить родительское production-значение `lease_dir=/tmp/opencode-zen-bridge-leases`, reaper сканирует сконфигурированный lease_dir; оракул VER-005 с нестандартным lease_dir сохранить — причина: architecture-packet.json:1987 — родитель уже передаёт `str(lease_dir)` позиционным аргументом argv, а architecture-packet.json:2767 требует только переданный каталог; литерал совпадает с production-значением этого аргумента, поэтому это неоднозначность формулировки одного корня по значению, а не две одновременно действующие топологии и не стратегический блокер REQ-008
DISPUTE F-002 — класс: invalid — контр-evidence: architecture-packet.json:2722,architecture-packet.json:3633 — поле `parent_watchdog_pipes: 6` в сумме 108 прямо названо `6lifeline_w`; steady write-концы уже учтены, добавляются только 6 transient read-концов, итог 114≤128, повторное прибавление lifeline_w даёт двойной счёт
AGREE F-003 rev=1 — проверил: architecture-packet.json:4540 — в `semantic_checks.evidence_refs` осталось «73 EVD records» при фактических 74 записях EVD-001..EVD-079 из `evidence[]`; учётная правка 73→74 не меняет контракт
AMEND F-004 — priority=non-blocking; locations=architecture-packet.json:1453,architecture-packet.json:1455,architecture-packet.json:2767; fix=В репродукции EVD-079 одной строкой прямо запретить перенос тела пробы с `select(fd0)+communicate()` в Stage3 и сослаться на нормативный concurrent drain из helper_cli_contract; тест >64 КиБ stderr до первого SSE оставить в VER-005 — причина: architecture-packet.json:1455 — проба уже помечена «не реализация Stage 3», а architecture-packet.json:2767 нормативно требует непрерывно дренировать оба pipe в том же тике, что EOF/TERM; дефект только в риске буквального копирования пробы, не в выбранной архитектуре
1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Стратегически топология parent→helper→serve, единый шестиаргументный argv, lease→handshake→lsof→READY и listener_pid==serve_pid согласованы; по F-001 intended-контракт один: lease_dir передаётся родителем, production-значение совпадает с литералом, требуется только редакционная замена литерала на параметр до Coder, что не меняет ни топологии, ни REQ-008/AC-011 при штатном пути
2. ПОЛНОТА: VERDICT=PASS
   WHY=Покрыты REQ-001..REQ-020/AC-001..AC-026, HL-ENV, fallback barrier, threat model, VER-001..VER-005 и честные NOT_RUN для Stage3/H0..H9; единственная подтверждённая дыра полноты — счётчик F-003 «73» вместо 74 EVD, не влияющий на масштабируемость решения
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Это единственное решение в пакете, реально меняющее игру: настоящие reasoning/text delta median ~127/114 мс по [F-19] вместо одного блока в конце шага по [F-17]/[F-18]; механики подтверждены изолированными пробами EVD-075..EVD-079 на целевом стеке stdlib/Python 3.14.7 в ровно трёх файлах, kill-switch default=false даёт поэтапный обратимый ввод Stage3a→3b
4. РИСКИ: VERDICT=PASS
   WHY=Главные точки роста названы и ограничены: RSS helper измерен 31.71875<36.0 MiB, слот 216 MiB с запасом 15.2, станция 1552≤1638.4 MiB, FD по перепроверке F-002 равен 114≤128, cap 6/12/3 не поднят; loaded-RSS и живая Zen permission-совместимость не замаскированы, а вынесены в блокирующие H3/H6 без waiver до H7, orphan-риск закрывается lifeline/lease/reaper при уточнении формулировки F-001
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Рассмотрены более двух альтернатив с причинами: L не закрывает RC-1, A2 теряет изоляцию и per-spawn env, B не подтверждён при 429 [F-24]/[F-25], `--stdio` без публичной схемы, `--port 0`/shared DB/empty XDG отклонены по evidence; выбранный A1+C открывает дальнейший рост — потоковый прогресс шагов и возможную миграцию транспорта без смены публичного контракта :9883
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Пакет остаётся на фактическом stdlib ThreadingHTTPServer без навязанного Litestar/FastAPI, не меняет согласованный внешний OpenAI SSE-контракт и Google-маршрут, не выходит за scope bridges/opencode-zen-bridge, фичефлаг через runtime JSON с default=false соответствует kill-switch модели проекта
ОБЩИЙ ВЕРДИКТ: PASS
POSITIONS: 4/4
ANSWERS: 0/0


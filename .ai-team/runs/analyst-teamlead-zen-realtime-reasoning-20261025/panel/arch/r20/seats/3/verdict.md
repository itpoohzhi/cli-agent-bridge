PANEL-NONCE: 51ac5965c668cbf7
ARTIFACT-SHA256: 88c02c37a7ca0be3d317217f23289dba07ddc681d922db207c7680a779128b6b
Канон НЕ прочитан: проход запрещает инструменты, файл ~/Мой диск/Context/AGENTS.md в этом ходе не открыт.

WITHDRAW F-002 — NEW: architecture-packet.json:3633 — проверил: architecture-packet.json#AD-001 (`resource_accounting.fd`) и `field_sources.FD_worker`. Слагаемые steady108 уже содержат `6lifeline_w` (в объекте fd это `parent_watchdog_pipes: 6`); сверху только `transient_lifeline_read_ends: 6`, опубликованный пик 114 ≤ 128. Повторное прибавление write-концов даёт 120 двойным счётом и стратегический запас до envelope не съедает.
AMEND F-001 — priority=blocking; locations=architecture-packet.json:1987, architecture-packet.json:2568, architecture-packet.json:2589, architecture-packet.json:2767, architecture-packet.json:1874; fix=Один корень lease — позиционный `lease_dir`. Строка `/tmp/opencode-zen-bridge-leases/` допустима только как значение по умолчанию, которое parent кладёт в argv и в поле lease. Helper создаёт файл только в переданном каталоге. Reaper и THREAT-001 сканируют тот же каталог, не второй литеральный путь. VER-005 с нестандартным `lease_dir` проверяет запись и съём только там: parent мёртв, helper мёртв, lease остался — снимается только свой PGID. `attempt_id` из `secrets`, каталог 0700, `O_NOFOLLOW`, atomic replace. EVD-079 остаётся пробой RSS и lease не создаёт. — причина: NEW: architecture-packet.json:1987 одновременно требует создать `/tmp/opencode-zen-bridge-leases/lease-<attempt_id>.json` и «use only the passed isolated lease directory»; registry на :2568 закрепляет первый путь, clean-room на :1874 передаёт другой.
AGREE F-003 rev=1 — проверил: architecture-packet.json#EVD-079 есть в `evidence[]` (74 записи `EVD-001`..`EVD-079`); `semantic_checks.evidence_refs` по-прежнему говорит «73 EVD records». Учётная ошибка, дыры в контракте нет.
AGREE F-004 rev=1 — проверил: architecture-packet.json:1455 помечает тело пробы как не-Stage3 (`communicate()` после `select` по fd 0); architecture-packet.json:2767 уже требует дренаж stdout/stderr serve в том же тике, что EOF/TERM. Норма стратегически верная; риск — только если Stage3 скопирует пробу вместо нормы.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
WHY=Игра по-прежнему меняется выбором C/A1: настоящие `reasoning.delta`/`text.delta` при живом legacy `run`. RW-001, RW-002, FU-001 и FU-002 в v6 закрыты по замеру и argv. Ломает исполнимость отказа один дефект F-001: при росте до 6 слотов и смерти parent, затем helper, очистка и clean-room смотрят в разные корни lease. REQ-008/AC-011, T-LIFE/v1 и THREAT-001 на этом пути не сходятся ни к фиксированному `/tmp/opencode-zen-bridge-leases/`, ни к позиционному `lease_dir`. F-002 снимаю как двойной счёт FD. F-003 и F-004 вердикт корректности не переворачивают.
СОВЕТЫ (при FAIL):
- Свести spawn, `crash_recovery.registry`, `crash_recovery.creation`, `helper_cli_contract.validation`, startup reaper и THREAT-001 к одному каталогу — аргументу `lease_dir`.
- Оставить `/tmp/opencode-zen-bridge-leases/` только как default, который parent подставляет в argv и записывает в lease; helper этот литерал не хардкодит.
- Оракул VER-005: нестандартный `lease_dir` получает файл lease только там; следующий старт моста снимает эту запись и только свой PGID.
- `attempt_id` брать из `secrets`; каталог 0700; `O_NOFOLLOW`; запись atomic replace внутри переданного каталога.
- EVD-079 не превращать в реализацию lease: проба RSS остаётся пробой. Нормативный цикл helper — неблокирующий дренаж stdout и stderr serve в том же тике, что EOF/TERM (F-004).
- В `semantic_checks.evidence_refs` заменить 73 на 74 и включить EVD-079 (F-003). Транспорт, 6 слотов, 12 waiters, cap 3 и конверт 1638.4 MiB этим фиксом не двигать.

2. ПОЛНОТА: VERDICT=PASS
WHY=REQ-001..020 и AC-001..026 закрыты поверхностью VER-001..005, Group A без FakeServe и Group B с шестью frozen families. Конверт HL-ENV 46 полей, гейты C-MULT/S-HERD/H-CPU/R-BULK/T-LIFE/O-EXIT/M-SEM, threat model, views с вопросом и ссылкой, H0..H9 как NOT_RUN — на месте. Память v6 сходится: замер 31.71875 MiB, оценка 36.0, слот 216, запас 15.2 ≥ 15, shared 1296, 1552.0 ≤ 1638.4. Расхождение «73» против 74 записей EVD (F-003) — счётчик, не пропуск требования.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
WHY=Путь укладывается в stdlib `ThreadingHTTPServer` и три файла кодера. EVD-079 на Python 3.14.7 поднял parent → helper → fake serve: шесть аргументов, `OPENCODE_BIN` из argv, в `serve_env` его нет, пик helper 31.72 MiB < 36.0, тяжёлые модули не загружены. VER-004 обычный и hostile `line-length=60` дали exit 0, catalog 8/8, три frozen SHA целы. Запас Stage3 у helper 4.28 MiB узкий, и это сознательный стоп: живой H3 при слоте > 216 MiB или станции > 1638.4 MiB блокирует H7. F-001 чинится правкой контракта, отдельного механизма не требует. Stage3 и H0..H9 остаются NOT_RUN.

4. РИСКИ: VERDICT=FAIL
WHY=При росте отказов (смерть parent, затем helper, шесть слотов) F-001 оставляет группу `child_pgid` жить: reaper и helper расходятся по каталогу lease. Это тот же класс, что [F-30]/[F-14], уже на выбранном дереве A1. Под нагрузкой первым упирается RSS слота: idle serve 156.8 + helper 36.0 + probe 8.0 = 200.8, запас под промпт ~103 КБ всего 15.2 MiB; превышение режет H3 без waiver, бюджет сам не разъезжается. FD после снятия F-002: пик 114 ≤ 128. Квота Zen [F-23], недоказанная смена egress (RISK-002) и окно не-exactly-once до заголовков prompt названы и не маскируются.
СОВЕТЫ (при FAIL):
- Принять фикс F-001: один `lease_dir` для helper, reaper и негативного оракула. Отдельный сценарий — SIGKILL parent после записи lease, смерть helper, подъём моста: serve/helper/temp root этого attempt исчезли, чужой PGID сигнала не получал.
- H3 оставить NOT_RUN. Порог не ослаблять: слот > 216 MiB или станция > 1638.4 MiB блокирует H7. В замер входит RSS serve под промптом ~103 КБ, не idle 156.8.
- Пик parent FD держать как 114 (steady108, внутри них 6 `lifeline_w`, плюс 6 кратких `lifeline_r`). Envelope 128 не поднимать. H3 меряет фактический пик, включая окно setup.
- Нормативный helper дренирует stderr/stdout serve без `communicate()` после простоя, иначе ложный `first_event_timeout` на живом апстриме (F-004). Тело пробы EVD-079 в Stage3 не переносить.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
WHY=AD-001 держит больше двух живых вариантов и причину выбора. L не снимает RC-1 [F-17]/[F-18]. A2 сливает failure domain и не даёт доказанной смены egress. B упирается в 429 [F-24]/[F-25]. `--stdio` есть как флаг [EVD-078], публичной схемы IPC нет. `--port 0`, пустой XDG и общая БД отклонены по EVD-071. Выбранный A1/C единственный открывает настоящие дельты и оставляет откат на `run` без смены контракта :9883; дальше с него можно уйти на B или A2, когда квота и egress будут доказаны. При росте первым ломается per-slot RSS (стоп H3), затем lease-коллизия F-001, не потолок слотов: 6/12/cap3 трогать не нужно.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
WHY=Пакет стоит на фактическом stdlib-мосте `:9883` и не навязывает Litestar/FastAPI. Факты решений лежат в [F-01]..[F-49] и EVD-070..079. Публичная форма OpenAI SSE, порт, срезы `_run_env` / `_stream_google_sse` / `_execute_google_once` и запрет записи `opencode.db` сохранены; serve изолирован через `OPENCODE_DB=:memory:` при read-only auth для run/opencode-go. `dynamic_config.json` в git не создаётся, кодовый default false, H7 только после H3/H6. `muse-bridge`, DSH и `~/.dsh` архитектор не меняет. APPROVED в пакете — внутренний кандидат, не вердикт совета; квитанция ARCH_GATE совпадает с sha256 пакета. Сверка записи r20: seed_input байт-в-байт равен manifest, seed_hex записи `b43d517e1396f75404a74123527d59375751db22d261ecf52b3f5501d2519d39` (SEED-префикс `b43d517e`), ranked_order записи `[grok-4.7-high, claude-sonnet-5-5-high, muse-wonder-full-1.0, gpt-6.1-sol-high, gemini-4-argon-high]` совпадает с manifest; живой пересчёт SHA-256 в этом ходе не выполнялся, инструменты запрещены.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

PANEL-NONCE: 732c9af7809c5fe3
ARTIFACT-SHA256: a53012565332cab8140d26d43029b931ff6d6c1fe4c63612310567ecba6812b3
Канон прочитан: AGENTS.md, 431 строк

Нормативные разделы `AD-001.spawn`, `listener_ownership`, `crash_recovery`, `single_turn_control` и `fallback_decision_table` между собой согласованы. Пакет ломается там, где дельта v4 оставила второй, старый контракт: угрозы и недоказанный хвост гейта `ruff`. Хэш фикстур пересчитан: `frozen_fixture_sha256` совпадает с `json.dumps(..., sort_keys=True, separators=(",", ":"))` = `e7871cd2910fa8458ec3efd90e254cc51fcef97300e6541a7edd1cce6d14a7a3`. SHA-256 пакета на диске совпадает с квитанцией.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Дерево parent→helper→serve и отмена формы до проверки схемы заданы в AD-001, а `THREAT-001` и `THREAT-002` описывают прежнюю модель v3. Реализация по тексту угроз снова открывает окно смерти родителя и откладывает cancel до «validated event».
   СОВЕТЫ (при FAIL):
   - Переписать `architecture-packet.json#THREAT-001` под одно дерево: parent резервирует `127.0.0.1:0`, `helper_proc` с `start_new_session=True` (`child_pgid=helper_proc.pid`), `serve_proc` с `start_new_session=False` в той же группе; до Auth требовать `listener_pid==serve_pid`, `os.getpgid(listener_pid)==child_pgid`, `helper_proc.poll() is None`; `lsof` ≤0.35 с внутри ready 3.0 с; cleanup — `killpg(child_pgid)` на helper+serve+потомков; чужой PID не получает пароль и сигнал.
   - Удалить из `THREAT-001` формулировки `release-before-Popen` / `newPGID` / «own child only» / `bounded<=.25s`.
   - Заменить вложенный порядок в `architecture-packet.json#THREAT-002` на `event_contract` `safety_order`: при своём `data.form.sessionID` и непустом `data.form.id` cancel ≤0.25 с и interrupt ≤0.10 с до проверки title/fields; отсутствующий title — нормальная отмена, `ServeHealth+0`; нет id/session или ошибка cancel — fail-closed и `killpg` ≤1.2 с.
   - Поиск по пакету: живые вхождения `newPGID`, `release-before-Popen` и `of validated event` остаются только в историческом `rework_resolutions_a1`.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-002, RW-003 (в перечисленных секциях), FU-002…FU-006 и покрытие REQ-001…REQ-020 закрыты. Ветка модели угроз в дельту не попала: два нормативных порядка на одну и ту же границу доверия.
   СОВЕТЫ (при FAIL):
   - Считать `threat_model.threats[].mitigation` нормативным текстом и сверять его с `spawn`, `listener_ownership`, `single_turn_control`, `fallback_decision_table` при каждой дельте.
   - Добавить `THREAT-001` и `THREAT-002` в `packet_locations` RW-003 и FU-001.
   - Оставить исторические `rework_resolutions_a1` без правки смысла; текущий контракт — только секции cycle 4.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Команда VER-004 переведена на `--range={start}:1-{end}:999`, литеральные SHA и отсечение hunk записаны; отрицательные мутации трёх срезов на копии `server.py` дают `AssertionError`. Прогон форматтера из EVD-075 сделан на шестистрочном `/tmp/.../tmp_server.py`. У файла нет хвоста после диапазона и нет `_run_env` / Google-срезов, поэтому `frozen_slices_unchanged: true` не доказывает, что закрытый диапазон не захватывает замороженные функции реального `server.py` (4021 строка, максимум строки 152 < 999). Если синтаксис на большом файле всё ещё тянется до EOF, `--check` покрасит Stage3 из-за 3216 незаформатированных строк, не трогая продукт.
   СОВЕТЫ (при FAIL):
   - На изолированной копии текущего `bridges/opencode-zen-bridge/server.py` вставить один пробел в ранней строке и один пробел на строке непосредственно перед `def _run_env`; прогнать ровно `ruff==0.17.2 format --check --range={start}:1-{end}:999`.
   - Зафиксировать в EVD-075 argv, exit code и SHA-256 трёх срезов до и после; срезы должны остаться `1c51b28f…`, `5914c965…`, `88d794cc…`.
   - Контрольный отрицательный прогон старым `start:end` на той же копии должен показать, что форматтер хочет править хвост; этим доказывается, что тест видит исходный дефект.
   - Продуктовый `server.py` и worktree не менять; Stage3 all-3 оставить `NOT_RUN`.

4. РИСКИ: VERDICT=FAIL
   WHY=При росте до 6 слотов расчёт 156.8+12+8=176.8 MiB на слот и 1408≤1638.4 MiB — оценка; H3 честно блокирует включение, общий egress через georouter `:10830` (NO_PROXY) делит одну квоту Zen, pre-header fallback не exactly-once. Это принято и закрыто гейтом. Не закрыта подмена listener: `THREAT-001` по-прежнему пускает Auth после `getpgid==childPGID` без `listener_pid==serve_pid`, с бюджетом lsof 0.25 с вместо 0.35 с. Пароль может уйти не тому процессу, а лишний timeout быстрее откроет `_ServeHealth` DEGRADED.
   СОВЕТЫ (при FAIL):
   - В `THREAT-001` запретить Authorization, пока не доказаны `listener_pid==serve_pid`, живой helper и общий `child_pgid`; таймаут lsof выровнять на 0.35 с внутри ready 3.0 с.
   - VER-005: негативный тест «listener — чужой PID в той же группе» даёт 0 байт пароля и 0 сигналов чужому PGID.
   - Потолки 6/12/cap3 и H3 ≤1638.4 MiB не поднимать; при отказе H3 runtime JSON остаётся false.
   - Маркер попытки в argv helper поставить в первые байты команды, которые возвращает `ps`, иначе startup reaper увидит lease и не сможет подтвердить группу.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=AD-001 сравнивает C/A1 с A2 (общий демон, один failure domain и один proxy env), B (прямой Zen, 429 в [F-24]/[F-25]), L (watchdog без RC-1), `:memory:` против пустого XDG и общей БД, родительский порт против `--port 0`, одну ветку против отдельного MR 3a. При нагрузке A2 укладывается в память лучше (один serve ~439 MiB, [F-20]), но выбранный A1 изолирует падение и env ценой H3; B не выбран без PoC. Причина выбора указана.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Пакет v4, cycle 4, SHA совпадает с `ARCH_GATE` и `task.json`. Scope — три файла кодера, Google-срезы и `_run_env` заморожены, `muse-bridge` и `~/.dsh` не пишутся, default=false, H7 только после H3/H6, CD-001/CD-002 входят в REQ-004…006. Stage3 и H0…H9 помечены NOT_RUN. `approval.rationale` всё ещё зовёт совет «a3 (r4)»; маршрут задают `summary`, `handoff_state` и `independent_review` (a4).

SUB Корректность/логика: FAIL — architecture-packet.json#THREAT-001 против #AD-001.spawn; #THREAT-002 «of validated event» против #single_turn_control
SUB Корректность/граничные условия: PASS — negative_mutations формы, пять точек SIGKILL, две взаимоисключающие строки first_token_timeout, шаблон ожидания без «(10 с)»
SUB Корректность/обработка ошибок: PASS — fallback_decision_table: 401/403 fail-closed, счётчики 0/1 взаимоисключающие, сбой quiescence сохраняет lease
SUB Полнота/покрытие AC: PASS — REQ-001…020 и AC связаны с VER-001…005; 3 RW+6 FU a3 имеют packet_locations; F-009/F-011 в excluded
SUB Полнота/пропущенные ветки: FAIL — threat_model не обновлён вместе со spawn и порядком cancel
SUB Реализуемость: FAIL — EVD-075 ruff только на tmp_server.py из 6 строк; копия server.py есть лишь в hash-мутациях
SUB Риски/безопасность: FAIL — THREAT-001 пускает Auth без listener_pid==serve_pid
SUB Риски/данные: PASS — OPENCODE_DB=:memory:, allowlist на трёх ветках, lease 0600, секреты вне argv/лога; H3 NOT_RUN
SUB Риски/прод: PASS — 6 слотов упираются в RSS и одну квоту Zen; включение блокирует H3, потолки не растут
SUB Альтернативы: PASS — AD-001.alternatives: A2, B, L, варианты БД и порта, с причиной выбора C/A1
SUB Соответствие контексту: PASS — квитанция ARCH_GATE packet_sha256=a5301256…; coder_target_files из трёх путей; Non-Goals/Forbidden Scope handoff-architect.md §9–10

F-001
priority: blocking
locations: architecture-packet.json#THREAT-001
rule: RW-003 / T-LIFE/v1 / AD-001.details.spawn / listener_ownership
evidence: mitigation дословно «Parent bind loopback0/getport/release-before-Popen explicit port/newPGID; до Auth/prompt lsof listener PID->os.getpgid==childPGID, bounded<=.25s … cleanup own child only». Живой spawn v4: helper — session leader, serve в той же группе, proof `listener_pid==serve_pid`, lsof ≤0.35 с. Фразы `newPGID` и `release-before-Popen` в текущем контракте встречаются только здесь (второе `release-before-Popen` — исторический `rework_resolutions_a1/2`).
expected: mitigation = дерево v4 и proof до Auth; убрать singular child, newPGID и бюджет 0.25 с.
check: поиск по пакету не находит `newPGID` вне истории a1; текст THREAT-001 содержит `listener_pid==serve_pid` и `0.35`.

F-002
priority: blocking
locations: architecture-packet.json#THREAT-002
rule: FU-001 / EVD-073 / AD-001.details.single_turn_control / event_contract.safety_order
evidence: внутри mitigation остался порядок «form cancel within0.25s of validated event». Рядом `single_turn_control.order[1]` требует cancel до title/fields/schema. Второе вхождение «validated event» — `S-HERD-I1` (релиз startup gate), это другой смысл, его не трогать.
expected: вложенный order в THREAT-002 заменить на safety_order; отсутствующий title не увеличивает ServeHealth и не ждёт watchdog.
check: строка `of validated event` отсутствует в threat_model; негативная мутация «missing title → cancel ≤0.25 с, ServeHealth 0» одна и та же в THREAT-002, single_turn_control и VER-005.

F-003
priority: blocking
locations: architecture-packet.json#EVD-075, architecture-packet.json#VER-004
rule: RW-001 acceptance (прогон раннего hunk на копии текущего server.py)
evidence: оба argv ruff заканчиваются на `/tmp/zen-arch4-probe-ruff-swkgt3h8/tmp_server.py`; stdout unformatted показывает файл из строк 2–4 (`PROBE_ALPHA`). Hash-негативы идут на `/tmp/zen-arch4-probe-hashes-95n6ulqk/server.py` и не вызывают ruff. `frozen_slices_unchanged: true` относится к шестистрочному файлу.
expected: EVD-075 дополнить прогоном закрытого `--range` и контрольным старым `start:end` на копии продуктового server.py; три SHA неизменны, продукт не тронут.
check: в EVD есть argv с копией `bridges/opencode-zen-bridge/server.py`, exit code и те же три digest; в выводе ruff нет правки `_run_env` / `_stream_google_sse` / `_execute_google_once`.

F-004
priority: non-blocking
locations: architecture-packet.json#approval
rule: handoff_state / cycle 4 / внешний совет a4
evidence: `approval.rationale` заканчивается «кандидат для Архитектурного Совета a3 (r4)». `summary`, `independent_review.rationale` и `handoff_state` называют a4. Единственное вхождение «a3 (r4)».
expected: заменить цель совета в approval.rationale на внешний a4; status=APPROVED по-прежнему не Council PASS.
check: строка `a3 (r4)` отсутствует; approval не объявляет ARCH_GATE_PASS.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

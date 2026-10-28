# Консенсус-леджер находок Архитектурного Совета — Cycle 1 (`a4`, `panel/arch/r8`)

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Раунд:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r8`
- **Проверяемый артефакт (v4):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.v4.json` (`sha256=a53012565332cab8140d26d43029b931ff6d6c1fe4c63612310567ecba6812b3`)
- **PANEL PROOF:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r8/panel-proof.json` (`sha256=116dc3386736ec20986f8320759df0982c2182e0423c4ecf95ecdf5234938c30`, `verify_panel_proof exit=0`)
- **Голоса судей:** Seat 1 (`grok-4.7-high`, `xAI`) = `NEEDS WORK` (4 F-блока: `F-001..F-003` blocking, `F-004` non-blocking), Seat 2 (`gemini-4-argon-high`, `Google`) = `NEEDS WORK` (5/6 PASS + 1 F-блок `F-005` blocking по `importlib.import_module("zen_catalog")` vs `limits['reportAny']==125` в `VER-004`), Seat 3 (`claude-sonnet-5-5-high`, `Anthropic`) = `PASS` (6/6 PASS + 6 non-blocking `F-006..F-011`, где `F-006` независимо подтверждает `F-003` по прогону `EVD-075` на копии реального `server.py`) → cross-family majority `2/3 NEEDS WORK` (`3. РЕАЛИЗУЕМОСТЬ` FAIL у двух семейств `xAI` + `Google` → Класс A `NEEDS WORK`, возврат `Architect` через `panel-rework-summarizer`, бюджет `arch_panel_to_architect: 4/5`).
- **Примечание о режиме консенсуса:** разрешающая поправка `consensus-debate/v1` §11 в `~/Мой диск/Context/models.md` отсутствует (`select_round_seats.py` применяет per-round redraw), поэтому проход финализирован по леджеру R1 с полной фиксацией `dissent` места Seat 3 (`PASS`, `6/6 PASS`) и Seat 2 (`5/6 PASS`): 4 blocking (`F-001`, `F-002`, `F-003`, `F-005`), 6 non-blocking (`F-004`, `F-007..F-011`), 1 excluded дубль (`F-006` `duplicate_of:F-003`).
- **Всего находок в батче:** 11 (`F-001` .. `F-011`)

---

## Находки Seat 1 (`skeptic`, `grok-4.7-high`, `xAI`, `cursor-agent`)

### F-001
- origin: skeptic · R1 · seat1-F-001
- rev: 1
- priority: blocking
- status: CONSENTED
- outcome: blocking
- resolved_in: r8-majority
- votes: R1 skeptic(xAI)=AUTHOR
- dissent: visionary R1 PASS (6/6 PASS) → panel/arch/r8/seats/3/verdict.md; realist R1 по КОРРЕКТНОСТЬ/ПОЛНОТА/РИСКИ PASS → panel/arch/r8/seats/2/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-001
> priority: blocking
> locations: architecture-packet.json#THREAT-001
> rule: RW-003 / T-LIFE/v1 / AD-001.details.spawn / listener_ownership
> evidence: mitigation дословно «Parent bind loopback0/getport/release-before-Popen explicit port/newPGID; до Auth/prompt lsof listener PID->os.getpgid==childPGID, bounded<=.25s … cleanup own child only». Живой spawn v4: helper — session leader, serve в той же группе, proof `listener_pid==serve_pid`, lsof ≤0.35 с. Фразы `newPGID` и `release-before-Popen` в текущем контракте встречаются только здесь (второе `release-before-Popen` — исторический `rework_resolutions_a1/2`).
> expected: mitigation = дерево v4 и proof до Auth; убрать singular child, newPGID и бюджет 0.25 с.
> check: поиск по пакету не находит `newPGID` вне истории a1; текст THREAT-001 содержит `listener_pid==serve_pid` и `0.35`.

### F-002
- origin: skeptic · R1 · seat1-F-002
- rev: 1
- priority: blocking
- status: CONSENTED
- outcome: blocking
- resolved_in: r8-majority
- votes: R1 skeptic(xAI)=AUTHOR
- dissent: visionary R1 PASS (6/6 PASS) → panel/arch/r8/seats/3/verdict.md; realist R1 по КОРРЕКТНОСТЬ/ПОЛНОТА/РИСКИ PASS → panel/arch/r8/seats/2/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-002
> priority: blocking
> locations: architecture-packet.json#THREAT-002
> rule: FU-001 / EVD-073 / AD-001.details.single_turn_control / event_contract.safety_order
> evidence: внутри mitigation остался порядок «form cancel within0.25s of validated event». Рядом `single_turn_control.order[1]` требует cancel до title/fields/schema. Второе вхождение «validated event» — `S-HERD-I1` (релиз startup gate), это другой смысл, его не трогать.
> expected: вложенный order в THREAT-002 заменить на safety_order; отсутствующий title не увеличивает ServeHealth и не ждёт watchdog.
> check: строка `of validated event` отсутствует в threat_model; негативная мутация «missing title → cancel ≤0.25 с, ServeHealth 0» одна и та же в THREAT-002, single_turn_control и VER-005.

### F-003
- origin: skeptic · R1 · seat1-F-003
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r8-majority
- votes: R1 skeptic(xAI)=AUTHOR | R1 visionary(Anthropic)=F-1(non-blocking, та же причина)
- dissent: visionary R1 PASS (оформил ту же нехватку прогона EVD-075 на копии реального server.py как non-blocking F-1 / F-006) → panel/arch/r8/seats/3/verdict.md; realist R1 по RW-001 PASS → panel/arch/r8/seats/2/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-003
> priority: blocking
> locations: architecture-packet.json#EVD-075, architecture-packet.json#VER-004
> rule: RW-001 acceptance (прогон раннего hunk на копии текущего server.py)
> evidence: оба argv ruff заканчиваются на `/tmp/zen-arch4-probe-ruff-swkgt3h8/tmp_server.py`; stdout unformatted показывает файл из строк 2–4 (`PROBE_ALPHA`). Hash-негативы идут на `/tmp/zen-arch4-probe-hashes-95n6ulqk/server.py` и не вызывают ruff. `frozen_slices_unchanged: true` относится к шестистрочному файлу.
> expected: EVD-075 дополнить прогоном закрытого `--range` и контрольным старым `start:end` на копии продуктового server.py; три SHA неизменны, продукт не тронут.
> check: в EVD есть argv с копией `bridges/opencode-zen-bridge/server.py`, exit code и те же три digest; в выводе ruff нет правки `_run_env` / `_stream_google_sse` / `_execute_google_once`.

### F-004
- origin: skeptic · R1 · seat1-F-004
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r8-majority
- votes: R1 skeptic(xAI)=AUTHOR
- dissent: visionary R1 PASS (6/6 PASS) → panel/arch/r8/seats/3/verdict.md; realist R1 по КОРРЕКТНОСТЬ/ПОЛНОТА/РИСКИ PASS → panel/arch/r8/seats/2/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-004
> priority: non-blocking
> locations: architecture-packet.json#approval
> rule: handoff_state / cycle 4 / внешний совет a4
> evidence: `approval.rationale` заканчивается «кандидат для Архитектурного Совета a3 (r4)». `summary`, `independent_review.rationale` и `handoff_state` называют a4. Единственное вхождение «a3 (r4)».
> expected: заменить цель совета в approval.rationale на внешний a4; status=APPROVED по-прежнему не Council PASS.
> check: строка `a3 (r4)` отсутствует; approval не объявляет ARCH_GATE_PASS.

---

## Находки Seat 2 (`realist`, `gemini-4-argon-high`, `Google`, `agy`)

### F-005
- origin: realist · R1 · seat2-F-001
- rev: 1
- priority: blocking
- status: CONSENTED
- outcome: blocking
- resolved_in: r8-majority
- votes: R1 realist(Google)=AUTHOR
- dissent: visionary R1 PASS (3. РЕАЛИЗУЕМОСТЬ PASS) → panel/arch/r8/seats/3/verdict.md; skeptic R1 по RW-002 PASS → panel/arch/r8/seats/1/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> ### F-001: Предписанная в RW-002/EVD-076 замена `import zen_catalog as zc` на `importlib.import_module("zen_catalog")` поднимает `reportAny` до 142 и детерминированно валит `VER-004.command` (`limits['reportAny'] == 125`)
> - **Якоря**:
>   - `architecture-packet.json:1166` (`architecture-packet.json#VER-004`, `verification_surface[3].command`)
>   - `architecture-packet.json:1167,1172` (`architecture-packet.json#VER-004`, `verification_surface[3].expected` и `baseline_transition.new`)
>   - `architecture-packet.json:957-1005` (`architecture-packet.json#EVD-076`, `summary` и `source_transform`)
>   - `architecture-packet.json:1906,2688,2902,4632,4810` (`architecture-packet.json#AD-001` `details.typing`, `architecture-packet.json#RISK-008` `mitigation`, `verification_policy.strict_typing`, `rework_resolutions[1]` / `rework_resolutions_a3[1]`)
>   - `bridges/opencode-zen-bridge/server.py:67-165` (`import zen_catalog as zc` на `:67` и обращения `zc.*` на `:69,109,112,113,121,159,165`)
> - **Нарушенное правило**: внутренняя выполнимость и непротиворечивость верификационного контракта (`REQ-001`, `REQ-002`, `REQ-003`, `REQ-017`, `VER-004`, `AD-001.details.typing`, `handoff/panel-rework-brief-arch-a3.json` `RW-002`): предписанная пакетом трансформация кода для `Stage 3 Coder` обязана проходить собственный исполняемый гейт `VER-004.command` без `# type: ignore`, `Any` и расширения `scope.coder_target_files`.
> - **Цитата и доказательство из артефакта**:
>   - В `architecture-packet.json:998` (`EVD-076.source_transform`) и `architecture-packet.json:1906` (`AD-001.details.typing`, а также `:1167,1172,2688,2902`) пакет обязывает Coder выполнить: `"zc = importlib.import_module(\"zen_catalog\") with import importlib replaces static relative import; guard proc is not None before both final stream .returncode reads. EVD-076 observed errorCount0 without # type: ignore"`, и одновременно фиксирует `"server Any<=125each"` / `"Existing Any<=125 and nonAny/total720+194 ceilings retained, no suppressions"`.
>   - В `architecture-packet.json:1166` исполняемый скрипт `VER-004.command` жёстко проверяет по-правиловые потолки на `files[0]` (`server.py`) и запрещает подавления:
>     `limits = {'reportExplicitAny':125,'reportAny':125,...}`
>     `counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))`
>     `assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)`
>   - На базовом `bridges/opencode-zen-bridge/server.py` (`HEAD == origin/dev`) запуск `uvx --from basedpyright==1.40.2 basedpyright --project <tmp_proj.json> --outputjson` из `cwd=bridges/opencode-zen-bridge` с `extraPaths=[str(bridge.resolve())]` даёт `errorCount=3` (`L131 reportConstantRedefinition`, `L3666` и `L3667 reportOptionalMemberAccess`), `warningCount=564`, `reportAny=125`, `reportExplicitAny=125` (строка `server.py:67` `import zen_catalog as zc` даёт `0` ошибок `basedpyright`, так как `bridges/opencode-zen-bridge/__init__.py` отсутствует, а единственное замечание `ruff` `E402` на этой строке уже явно разрешено в `VER-004.command`: `assert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings)`).
>   - При точном применении `EVD-076.source_transform` (`zc = importlib.import_module("zen_catalog")`) `basedpyright==1.40.2` выводит для `zc` тип `types.ModuleType` (`ModuleType.__getattr__(self, name: str) -> Any`), превращая все обращения `zc.*` в существующем коде `server.py` в `Any`. Именно эти `+17` предупреждений образуют рост `warningCount` с `564` до `581` в `EVD-076` (`architecture-packet.json:976`), при котором **`counts['reportAny']` вырастает со `125` до `142`** (`{'reportAny': 142, 'reportExplicitAny': 125, ...}`) и детерминированно обрушивает `VER-004.command` по `AssertionError` (`142 > 125`). В `EVD-076` проверялся только `summary` (`errorCount=0, warningCount=581`), без запуска по-правилового ассерта `limits` из `VER-004.command`.
> - **Ожидаемое исправление**:
>   1. **Предпочтительный вариант (без роста `reportAny` и без изменения `limits`)**: удалить требование замены на `zc = importlib.import_module("zen_catalog")` из `architecture-packet.json:998,1167,1172,1906,2688,2902,4632,4810`, сохранив в `bridges/opencode-zen-bridge/server.py:67` существующий `import zen_catalog as zc` (уже разрешённый правилом `E402` в `VER-004.command`) вместе с `CATALOG_SOURCE = "static"`, типизированным `_set_catalog_source(source: str) -> None` (`globals()["CATALOG_SOURCE"] = source`) и двумя проверками `proc is not None` перед чтением `proc.returncode` (`server.py:3666-3667`), что на реальной структуре `bridges/opencode-zen-bridge/` даёт `errorCount=0`, `warningCount=564`, `reportAny=125 <= 125`.
>   2. **Альтернативный вариант**: если `importlib.import_module("zen_catalog")` сохраняется намеренно, типизировать фасад доступа к `zen_catalog` через `typing.Protocol`/узкие обёртки без `Any`, `cast` и `# type: ignore` с подтверждением `counts['reportAny'] <= 125`, либо явно согласовать потолок `limits['reportAny']` (`142`) в `VER-004.command` и текстовых разделах `VER-004`/`AD-001.details.typing` при сохранении запрета `reportAny` в изменённых диапазонах `ranges`.
> - **Критерий проверки**: в `EVD` пакета приведён прогон полного набора проверок `VER-004.command` (`basedpyright==1.40.2` `errorCount == 0` + `all(n <= limits[rule])` с распечаткой `dict(counts)` + проверка отсутствия `reportAny`/`reportExplicitAny`/`reportUnusedCallResult` в `changed_ranges` + `ruff==0.17.2 check` + `tests.test_catalog_mode`) на изолированной копии, воспроизводящей реальную раскладку `bridges/opencode-zen-bridge/` (без лишнего `__init__.py` в корне моста), с exit code `0`.
> - **Приоритет**: `priority: blocking`

---

## Находки Seat 3 (`visionary`, `claude-sonnet-5-5-high`, `Anthropic`, `claude-p`)

### F-006
- origin: visionary · R1 · seat3-F-1
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: excluded
- resolved_in: r8-majority
- votes: R1 visionary(Anthropic)=AUTHOR | R1 skeptic(xAI)=F-003(blocking)
- dissent: duplicate_of:F-003 — совпадает по корневой причине с blocking F-003 (Seat 1 xAI: прогон EVD-075 на копии реального server.py вместо 6-строчного tmp_server.py)
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-1 [non-blocking] RW-001 acceptance подтверждён неполно.
> - locations: architecture-packet.json#EVD-075; rework_resolutions_a3 RW-001.verification.
> - Критерий RW-001 требует «реальный прогон раннего synthetic hunk на копии текущего server.py». В EVD-075 форматтер запускался на 6-строчном синтетическом `tmp_server.py` (`--range=1:1-6:999`), а не на копии боевого файла. Литеральные хэши и негативные мутации сняты на `server.py`-копии, это в порядке.
> - Исправление: добавить в EVD прогон `--check --range` с ранним hunk на изолированной копии настоящего `server.py`. Записать rc и неизменность трёх хэшей.
> - Проверка: EVD содержит `argv` с путём копии боевого файла.

### F-007
- origin: visionary · R1 · seat3-F-2
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r8-majority
- votes: R1 visionary(Anthropic)=AUTHOR
- dissent: visionary R1 ОБЩИЙ ВЕРДИКТ: PASS (оформлено автором как non-blocking улучшение)
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-2 [non-blocking] Проверка «до и после форматтера» в VER-004 не проверяет запись форматтера.
> - locations: architecture-packet.json#VER-004 (`command`: второй `assert_frozen()` после цикла `ruff format --check`; `expected`: «Before and after formatter»).
> - `--check` ничего не пишет, поэтому повторный `assert_frozen()` тавтологичен. Реальный риск возникает, когда Coder выполняет `ruff format --range` с записью и диапазон расширяется до enclosing-узла.
> - Исправление: в VER-004 прогонять `ruff format --range` без `--check` на временной копии кандидата. Затем сравнивать три литеральных хэша и отсутствие hunk-пересечений.
> - Проверка: мутация, дающая расширение диапазона на замороженную функцию, краснит гейт.

### F-008
- origin: visionary · R1 · seat3-F-3
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r8-majority
- votes: R1 visionary(Anthropic)=AUTHOR
- dissent: visionary R1 ОБЩИЙ ВЕРДИКТ: PASS (оформлено автором как non-blocking улучшение)
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-3 [non-blocking] Не оценена альтернатива `opencode serve --stdio` (стратегическая).
> - locations: architecture-packet.json#AD-001.alternatives; [F-30] (дочерний `opencode serve --stdio --port 0` существует, PID 11488).
> - Альтернативы по порту рассмотрены только как `--port 0` со stdout-анонсом. Транспорт через stdio, который `run --standalone` уже использует, мог бы убрать резервирование порта, `lsof`, listener-ownership и пароль, то есть заметную часть сложности RW-003. Пригодность протокола извне не доказана и не опровергнута.
> - Исправление: добавить в `alternatives` вариант `serve --stdio` с доказательным отказом или с проверкой в provider-free preflight Stage3. Менять выбор A1 не требуется.
> - Проверка: в `alternatives` есть запись со ссылкой на evidence.

### F-009
- origin: visionary · R1 · seat3-F-4
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r8-majority
- votes: R1 visionary(Anthropic)=AUTHOR
- dissent: visionary R1 ОБЩИЙ ВЕРДИКТ: PASS (оформлено автором как non-blocking улучшение)
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-4 [non-blocking] Helper-код живёт строкой `_SERVE_HELPER_CODE` вне покрытия `ruff` и `basedpyright`.
> - locations: architecture-packet.json#AD-001.details.spawn; #VER-004; #T_LIFE_v1.
> - Самая хрупкая логика (SIGSTOP-quiescence, lease, EOF-цикл) не попадает под VER-004, где «0 ошибок, 0 Any» заявлено для кода. Проверяется только fault-injection в VER-005.
> - Исправление: описать запуск helper как режим того же `server.py` (`python -I server.py --serve-helper`). Тогда код типизируется и линтуется в рамках трёх файлов. Либо явно задокументировать исключение и усилить VER-005 тестами функций helper.
> - Проверка: тело helper присутствует в диагностике basedpyright, либо исключение записано в пакете.

### F-010
- origin: visionary · R1 · seat3-F-5
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r8-majority
- votes: R1 visionary(Anthropic)=AUTHOR
- dissent: visionary R1 ОБЩИЙ ВЕРДИКТ: PASS (оформлено автором как non-blocking улучшение)
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-5 [non-blocking] Формулировки про env-переменные противоречат друг другу.
> - locations: architecture-packet.json#AD-001.details.configuration (`OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` как «Существующий env override»; `feature_flag_context`: «без … новых env-переменных»); #AD-001 (новые TRANSPORT, SERVE_PERMISSION_POLICY, SERVE_DISABLE_FILE); #AD-003 (watchdog-пороги).
> - В evidence ledger нет подтверждения, что переменная `…REALTIME_SERVE_ENABLED` существует в базовом коде. При этом пакет добавляет минимум три новых env/файловых поверхности.
> - Исправление: либо сослаться на `[F-NN]`/строку кода, где env существует, либо назвать её новой. Уточнить фразу «без новых env» до «без новых env для самого флага».
> - Проверка: текст пакета не содержит противоречия.

### F-011
- origin: visionary · R1 · seat3-F-6
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r8-majority
- votes: R1 visionary(Anthropic)=AUTHOR
- dissent: visionary R1 ОБЩИЙ ВЕРДИКТ: PASS (оформлено автором как non-blocking улучшение)
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-6 [non-blocking] Хэш fixtures смешан с редакционной метаданной.
> - locations: architecture-packet.json#AD-001.details.event_contract (`frozen_fixture_sha256` в v4 изменён при неизменных wire и canonical, `fixture_digest_revision_a3`).
> - Сериализуется весь `frozen_v2_1_2_fixtures`, включая `negative_mutations` и `safety_order`, поэтому правка текста меняет «иммутабельный» оракул. Значение `e7871cd2…` я проверить не могу: не вижу вычисления.
> - Исправление: считать digest только по `wire` и `canonical`, метаданные хэшировать отдельно. Либо зафиксировать, что digest включает метаданные.
> - Проверка: правка текста мутаций не меняет wire-digest.

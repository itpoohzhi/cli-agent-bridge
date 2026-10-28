# Консенсус-леджер находок Архитектурного Совета — Cycle 1 (`a3`: `R1` `panel/arch/r4` + `D1` `panel/arch/r7`)

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r4` (`panel-proof.json` `sha256=abddbe7d2b8b60086143ec49356c231f21f0d03ec05c51c06b7aaa3b0da6e9f9`, `verify_panel_proof exit=0`)
- **Раунд D1:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r7` (`panel-proof.json` `sha256=7c44c53c8aa7241d3f38809941e88b565f58b5531d967903864f540b05507387`, `verify_panel_proof exit=0`)
- **Проверяемый артефакт (v3):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.v3.json` (`sha256=8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608`)
- **Голоса судей D1 (`panel/arch/r7`):** Seat 1 (`claude-sonnet-5-5-high`, `Anthropic`) = `NEEDS WORK`, Seat 2 (`muse-wonder-full-1.0`, `Meta`) = `NEEDS WORK`, Seat 3 (`gemini-4-argon-high`, `Google`) = `NEEDS WORK` → единогласно `3/3 NEEDS WORK`.
- **Примечание о режиме консенсуса:** разрешающая поправка `consensus-debate/v1` §11 в `~/Мой диск/Context/models.md` отсутствует (`select_round_seats.py` применяет `debate_roster_mode=rotated`, ротировав `grok-4.7-high` из R1). В `D1` (`r7`) все `3/3` судьи единогласно закрыли `AGREED` по всем трём истинным блокерам (`F-001`, `F-002`, `F-003`) и четырём non-blocking (`F-005..F-008`), а оставшиеся 4 позиции (`F-004`, `F-009`, `F-010`, `F-011`) финализированы по правилам потолка §6 (`council-consensus.md`) с дословной фиксацией `dissent` и `amendments` (`r2_late=0`).
- **Всего находок в батче:** 11 (`F-001` .. `F-011`): `AGREED` = 7 (`3` blocking: `F-001..F-003`; `4` non-blocking: `F-005..F-008`), `CONSENTED` non-blocking = 2 (`F-004`, `F-010`), `CONSENTED` excluded = 2 (`F-009` `duplicate_of:F-003`, `F-011` `invalid_after_recheck`).

---

### F-001
- origin: skeptic · R1 · skeptic-F-01
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic(xAI)=AUTHOR; D1 skeptic(Anthropic)=AGREE(rev=1), realist(Meta)=AGREE(rev=1), visionary(Google)=AGREE(rev=1)
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-01. priority=blocking. Якорь: architecture-packet.json#VER-004. Правило: RW-001, acceptance «воспроизводимые команды» и «без выдуманных CLI-флагов»; одновременно VER-005/`immutable_run_env`. Evidence: команда вызывает `ruff format --check --range {start}:{end}`. У ruff==0.17.2 формат такой: `<start_line>:<start_column>-<end_line>:<end_column>`; конец необязателен и тогда форматируется документ до EOF. Прогон: `--range 1:2` переписал весь файл; `--range 4:99` переписал хвост после точки старта. Ранний hunk в `server.py` поэтому требует формат замороженного тела (3216 строк diff, hash `_run_env` `1c51b28f…` → другой). Ожидание: закрытый диапазон и отказ гейта, если diff форматтера задевает `_run_env` или Google-функции. Проверка: synthetic early hunk на текущем `server.py` не помечает эти срезы unformatted.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AGREE F-001 rev=1 — проверил: architecture-packet.json#VER-004. Команда вызывает `ruff format --check --range f'{start}:{end}'`. По RECHECK F-001 у ruff==0.17.2 формат `<start_line>:<start_column>-<end_line>:<end_column>`, конец необязателен, и без него форматируется весь документ до EOF. Строка `5:9` значит «строка 5, колонка 9, до конца файла». Гейт захватывает замороженные `_run_env` и срезы Google-direct и противоречит RW-001. Остаётся blocking.
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): AGREE F-001 rev=1 — NEW: собственный прогон `ruff format --help` (ruff 0.17.2): формат `--range` — `<start_line>:<start_column>-<end_line>:<end_column>`, конец необязателен и тогда форматируется до EOF; проверил: architecture-packet.json#VER-004 — команда передаёт `--range {start}:{end}`, то есть line:start_column без конца, поэтому ранний hunk тянет проверку на хвост файла с замороженными `_run_env`/Google-срезами (EVD-072: 3216 строк diff).
> - D1 visionary (`gemini-4-argon-high`, `Google`): AGREE F-001 rev=1 — проверил: architecture-packet.json:999 — В `ruff==0.17.2` аргумент `--range {start}:{end}` задаёт строку и столбец начала без верхней границы, поэтому проверка захватывает `server.py` до EOF, включая замороженный `_run_env` и запрещённый Google-срез.

### F-002
- origin: skeptic · R1 · skeptic-F-02
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic(xAI)=AUTHOR; D1 skeptic(Anthropic)=AGREE(rev=1), realist(Meta)=AGREE(rev=1), visionary(Google)=AGREE(rev=1)
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-02. priority=blocking. Якорь: architecture-packet.json#AD-001 (`details.typing`), дубль в VER-004. Правило: REQ-003/AC-004, `coder_target_files`, FU-002 (17 модулей не править). Evidence: пакет требует «Rename mutable internal CATALOG_SOURCE to lower-case». Вне allowlist `tests/test_catalog_mode.py:64` делает `self.assertEqual(server.CATALOG_SOURCE, "static")`, строка 93 печатает `server.CATALOG_SOURCE`. Переименование атрибута роняет VER-001/VER-002; сохранение имени оставляет `reportConstantRedefinition`, а VER-004 требует `errorCount==0`. Ожидание: одно из двух явных решений в пакете — не переименовывать атрибут, либо добавить в allowlist только этот файл и две ссылки. Проверка: после Stage3 `test_catalog_mode` зелёный и basedpyright `errorCount==0` без `type: ignore`.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AGREE F-002 rev=1 — проверил: `bridges/opencode-zen-bridge/tests/test_catalog_mode.py:64` (`self.assertEqual(server.CATALOG_SOURCE, "static")`) и `:93` (`server.CATALOG_SOURCE` в команде). Файл вне `coder_target_files`. Пакет требует переименовать `CATALOG_SOURCE` (AD-001#typing, VER-004). Переименование ломает REQ-003/AC-004, а VER-004 при этом требует `errorCount==0`. Остаётся blocking. Решение должно быть явным: либо не переименовывать, либо добавить в allowlist только этот файл и две ссылки.
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): AGREE F-002 rev=1 — NEW: собственный grep `tests/test_catalog_mode.py`: строка 64 `server.CATALOG_SOURCE`, строка 93 `server.CATALOG_SOURCE`; проверил: architecture-packet.json#AD-001 (`details.typing`) — пакет требует переименовать `CATALOG_SOURCE` в lower-case, а файл вне `coder_target_files` (только 3 файла) читает старое имя, сохранение имени оставляет `reportConstantRedefinition` при требовании `errorCount==0` в VER-004.
> - D1 visionary (`gemini-4-argon-high`, `Google`): AGREE F-002 rev=1 — проверил: bridges/opencode-zen-bridge/tests/test_catalog_mode.py:64 — Переименование `CATALOG_SOURCE` в нижний регистр в `server.py` ломает внешние чтения `server.CATALOG_SOURCE` в `tests/test_catalog_mode.py:64,93` вне `coder_target_files`, а сохранение `global CATALOG_SOURCE` не проходит `basedpyright==1.40.2` (`reportConstantRedefinition`).

### F-003
- origin: skeptic · R1 · skeptic-F-03
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic(xAI)=AUTHOR; D1 skeptic(Anthropic)=AGREE(rev=1), realist(Meta)=AGREE(rev=1), visionary(Google)=AGREE(rev=1)
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-03. priority=blocking. Якоря: architecture-packet.json#AD-001 `details.spawn`, `details.listener_ownership`, `details.crash_recovery`. Правило: T-LIFE/v1, RW-006. Evidence: spawn задаёт `Popen([OPENCODE_BIN, serve, --hostname, 127.0.0.1, --port, str(port)], stdin=DEVNULL, start_new_session=True)`. `crash_recovery.creation` задаёт другое дерево: «spawn under lease-named stdlib helper which publishes child identity atomically». Прямой `Popen` serve не публикует pid до отдельной записи lease; reaper при пустом pid убивать по имени не может. Ожидание: один текст дерева процессов и тот же учёт helper/FD. Проверка: VER-005 hard kill в щели после старта до READY даёт 0 своих serve и 0 чужих сигналов.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AGREE F-003 rev=1 — проверил: architecture-packet.json#AD-001. Раздел `spawn` задаёт прямой `Popen(serve, start_new_session=True)` и `child_pgid`. Раздел `crash_recovery.creation` задаёт запуск serve под stdlib-helper, который публикует идентичность ребёнка. Не определено, чьи `proc` и PGID использует `proc.poll()`, сравнение `os.getpgid(listener)==child_pgid` и `killpg`. Окно между `Popen` и записью lease при SIGKILL остаётся неоднозначным, это ядро RW-006. Находка F-009 (visionary) дублирует её содержание. Для consensus-ledger предлагаю оставить blocking: разрешать противоречие между разделами на этапе Coder нельзя. Фикс: одно дерево процессов, где helper — родитель serve и публикует pid/pgid/lstart до READY. Ту же топологию использовать в учёте потоков и FD и в оракуле VER-005 «hard kill после `Popen` до READY».
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): AGREE F-003 rev=1 — проверил: architecture-packet.json#AD-001 (`details.spawn` против `details.crash_recovery.creation`) — `spawn` задаёт прямой `Popen([OPENCODE_BIN,serve,...],start_new_session=True)`, а `crash_recovery` — запуск под stdlib-helper, который публикует pid; два дерева процессов, при прямом дереве щель spawn→lease оставляет serve без pid для reaper (RW-006, T-LIFE/v1).
> - D1 visionary (`gemini-4-argon-high`, `Google`): AGREE F-003 rev=1 — проверил: architecture-packet.json:1184, architecture-packet.json:1775 — В `AD-001.details.spawn` задан прямой `Popen` процесса `opencode serve` с обновлением lease после старта, а в `crash_recovery.creation` — несовместимый запуск `serve` под stdlib-хелпером, из-за чего `proc.poll()` и `child_pgid` в `listener_ownership` теряют однозначный объект проверки.

### F-004
- origin: skeptic · R1 · skeptic-F-04
- rev: 2
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: ceiling
- votes: R1 skeptic(xAI)=AUTHOR(blocking); D1 skeptic(Anthropic)=AMEND(rev=2,non-blocking), realist(Meta)=AGREE(rev=1,blocking), visionary(Google)=DISPUTE(invalid)
- dissent: realist (D1): AGREE F-004 rev=1 — проверил: architecture-packet.json#EVD-073 и #AD-001 (`event_contract` negative_mutations) — EVD-073 фиксирует `title`/`required` как необязательные поля Form.Info, а мутация требует «missing form.id/fields/title -> invalid_serve_event», поэтому валидная форма без `title` не попадёт в cancel ≤0.25 с и зависнет до watchdog (RW-003). | visionary (D1): DISPUTE F-004 — класс: invalid — контр-evidence: architecture-packet.json:829, architecture-packet.json:1506 — В схеме `opencode` v2.1.2 (`EVD-073`) опциональность `title` относится только к элементам `Form.Field`, тогда как в корневом `Form.Info` поле `title` обязательно, а при `invalid_serve_event` адаптер немедленно прерывает попытку и выполняет `finally`-очистку (`<=1.2s`, `architecture-packet.json:1866,1996`) без 60-секундного ожидания watchdog.
- owner_decision: —
- amendments: rev 2 (D1 skeptic Anthropic): AMEND F-004 — priority=non-blocking; locations=architecture-packet.json#AD-001 (`event_contract.form.created / form.cancelled.negative_mutations`), architecture-packet.json#EVD-073; fix=для `form.created` с валидным вложенным `data.form.sessionID` собственной сессии и `data.form.id` любая последующая schema-ошибка не откладывает cancel. Сразу уходит `cancel` ≤0.25 с либо fail-closed kill собственного PGID без ожидания watchdog. Какие поля Form.Info обязательны, зафиксировать по EVD-073. — причина: NEW: architecture-packet.json#EVD-073 (`Form.Info={id,sessionID,title,metadata?,fields}`). Необязателен только `metadata`, а «title/required optional» относится к полю внутри `fields`. Исходная посылка F-004 «title у Form.Info необязателен» неверна, и мутация «missing title → invalid_serve_event» согласована с источником. Остаётся риск «вопрос висит до watchdog»: `invalid_serve_event` уже ведёт к cleanup и kill, но порядок «cancel раньше invalid» не зафиксирован. Это non-blocking.
- text (дословно, R1 skeptic):
> F-04. priority=blocking. Якоря: architecture-packet.json#AD-001 `event_contract` negative_mutations формы; architecture-packet.json#EVD-073. Правило: RW-003, REQ-012, THREAT-002. Evidence: мутация «missing form.id/fields/title -> invalid_serve_event». EVD-073: у Form.Info `title` необязателен, session id лежит в `data.form.sessionID`. Форма без title становится protocol failure и не идёт в cancel ≤0.25 с, то есть вопрос снова ждёт watchdog. Ожидание: обязательны id, вложенный sessionID и fields; отсутствие title не мешает cancel и не увеличивает `_ServeHealth`. Проверка: FakeServe шлёт `form.created` без title, cancel уходит ≤0.25 с, Step2 в сокет не попадает.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AMEND F-004 — priority=non-blocking; locations=architecture-packet.json#AD-001 (`event_contract.form.created / form.cancelled.negative_mutations`), architecture-packet.json#EVD-073; fix=для `form.created` с валидным вложенным `data.form.sessionID` собственной сессии и `data.form.id` любая последующая schema-ошибка не откладывает cancel. Сразу уходит `cancel` ≤0.25 с либо fail-closed kill собственного PGID без ожидания watchdog. Какие поля Form.Info обязательны, зафиксировать по EVD-073. — причина: NEW: architecture-packet.json#EVD-073 (`Form.Info={id,sessionID,title,metadata?,fields}`). Необязателен только `metadata`, а «title/required optional» относится к полю внутри `fields`. Исходная посылка F-004 «title у Form.Info необязателен» неверна, и мутация «missing title → invalid_serve_event» согласована с источником. Остаётся риск «вопрос висит до watchdog»: `invalid_serve_event` уже ведёт к cleanup и kill, но порядок «cancel раньше invalid» не зафиксирован. Это non-blocking.
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): AGREE F-004 rev=1 — проверил: architecture-packet.json#EVD-073 и #AD-001 (`event_contract` negative_mutations) — EVD-073 фиксирует `title`/`required` как необязательные поля Form.Info, а мутация требует «missing form.id/fields/title -> invalid_serve_event», поэтому валидная форма без `title` не попадёт в cancel ≤0.25 с и зависнет до watchdog (RW-003).
> - D1 visionary (`gemini-4-argon-high`, `Google`): DISPUTE F-004 — класс: invalid — контр-evidence: architecture-packet.json:829, architecture-packet.json:1506 — В схеме `opencode` v2.1.2 (`EVD-073`) опциональность `title` относится только к элементам `Form.Field`, тогда как в корневом `Form.Info` поле `title` обязательно, а при `invalid_serve_event` адаптер немедленно прерывает попытку и выполняет `finally`-очистку (`<=1.2s`, `architecture-packet.json:1866,1996`) без 60-секундного ожидания watchdog.

### F-005
- origin: skeptic · R1 · skeptic-F-05
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic(xAI)=AUTHOR; D1 skeptic(Anthropic)=AGREE(rev=1), realist(Meta)=AGREE(rev=1), visionary(Google)=AGREE(rev=1)
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-05. priority=non-blocking. Якоря: architecture-packet.json#AD-002 `status_protocol_examples.waiting` и `details.lifecycle`. Правило: FU-005, REQ-004/AC-005. Evidence: шаблон `"[мост] Ожидание первого токена (10 с)…\n"`, lifecycle — `"[мост] Ожидание первого токена…"` каждые 5.0 с, без счётчика. Ожидание: одна байтовая строка в шаблоне, lifecycle и VER-005. Проверка: тест падает при второй строке.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AGREE F-005 rev=1 — проверил: architecture-packet.json#status_protocol_examples (`waiting`: «[мост] Ожидание первого токена (10 с)…\n») против AD-002#lifecycle («[мост] Ожидание первого токена…» каждые 5.0 с, без счётчика). Это два разных байтовых шаблона. Non-blocking.
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): AGREE F-005 rev=1 — проверил: architecture-packet.json#AD-002 — `status_protocol_examples.waiting` содержит «(10 с)», а `details.lifecycle` задаёт ту же строку без счётчика каждые 5.0 с; две разные байтовые строки статуса при требовании FU-005 о совпадении REQ и оракулов.
> - D1 visionary (`gemini-4-argon-high`, `Google`): AGREE F-005 rev=1 — проверил: architecture-packet.json:1933, architecture-packet.json:3474 — Пример в `status_protocol_examples.waiting` содержит счётчик `(10 с)`, которого нет в нормативной спецификации `AD-002.details.lifecycle`, что создаёт двусмысленность эталонной строки для тестов.

### F-006
- origin: skeptic · R1 · skeptic-F-06
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic(xAI)=AUTHOR; D1 skeptic(Anthropic)=AGREE(rev=1), realist(Meta)=AGREE(rev=1), visionary(Google)=AGREE(rev=1)
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-06. priority=non-blocking. Якоря: architecture-packet.json#AD-001 `fallback_decision_table` и `transport_health.counted_failures`. Правило: FU-004, RISK-012. Evidence: таблица объявлена авторитетной и для `first_token_timeout` содержит только «valid protocol and model silence» → ServeHealth 0, UpstreamBreaker 1. `counted_failures` отдельно считает `first_token_timeout` счётчиком `_ServeHealth`, если доказан дефект протокола. Строки на этот случай в таблице нет. Ожидание: отдельная строка таблицы с ServeHealth +1 и UpstreamBreaker 0. Проверка: VER-005 параметризует обе причины и видит ровно один инкремент нужного счётчика.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AGREE F-006 rev=1 — проверил: architecture-packet.json#AD-001 (`fallback_decision_table`). Строка `first_token_timeout/stall` существует только для случая «valid protocol and model silence» (ServeHealth 0, UpstreamBreaker 1). `transport_health.counted_failures` отдельно считает `first_token_timeout` при доказанном protocol/capability-дефекте. Строки на этот случай нет, хотя таблица названа авторитетной в AD-003#retry. Non-blocking.
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): AGREE F-006 rev=1 — проверил: architecture-packet.json#AD-001 (`fallback_decision_table` против `transport_health`) — в объявленной авторитетной таблице для `first_token_timeout` есть только ветка «валидный протокол, тишина модели» (ServeHealth 0), а protocol-caused ветка с ServeHealth +1 из `counted_failures` в таблицу не вынесена (FU-004).
> - D1 visionary (`gemini-4-argon-high`, `Google`): AGREE F-006 rev=1 — проверил: architecture-packet.json:1687, architecture-packet.json:1826 — Правило `AD-001.details.transport_health.counted_failures` учитывает `first_token_timeout` в `_ServeHealth` при доказанном дефекте протокола, но в `fallback_decision_table` представлена только строка с молчанием модели при валидном протоколе.

### F-007
- origin: skeptic · R1 · skeptic-F-07
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic(xAI)=AUTHOR; D1 skeptic(Anthropic)=AGREE(rev=1), realist(Meta)=AGREE(rev=1), visionary(Google)=AGREE(rev=1)
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-07. [sweep] priority=non-blocking. Якорь: architecture-packet.json#AD-003 `details.cleanup`. Правило: привязка утверждения к факту ledger. Evidence: cleanup ссылается на EVD-056 для убийства потомков после выхода leader. EVD-056 — это `WORKTREE_UNCHANGED`. Факт про `_stop_proc` и потомков — EVD-055. Ожидание: заменить ссылку на EVD-055, норматив killpg не менять. Проверка: в пакете нет утверждения, которое опирается на EVD-056 как на поведение процессов.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AGREE F-007 rev=1 — проверил: architecture-packet.json#AD-003 (`details.cleanup`) ссылается на «EVD-056» для убийства потомков. EVD-056 — `WORKTREE_UNCHANGED`, а факт про `_stop_proc` и потомков — EVD-055, он есть в `evidence_ids` AD-003. Non-blocking.
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): AGREE F-007 rev=1 — проверил: architecture-packet.json#AD-003 (`details.cleanup`) и #EVD-056 — cleanup ссылается на EVD-056 (`WORKTREE_UNCHANGED`) как на факт об убийстве потомков, тогда как этот факт — EVD-055 про `_stop_proc`; норматив killpg не меняется, ошибка только в ссылке.
> - D1 visionary (`gemini-4-argon-high`, `Google`): AGREE F-007 rev=1 — проверил: architecture-packet.json:703, architecture-packet.json:709, architecture-packet.json:1996 — В `AD-003.details.cleanup` указана ссылка `EVD-056` (`WORKTREE_UNCHANGED`) вместо корректного `EVD-055` (утечка дочерних процессов после выхода лидера группы в `_stop_proc`).

### F-008
- origin: skeptic · R1 · skeptic-F-08
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic(xAI)=AUTHOR; D1 skeptic(Anthropic)=AGREE(rev=1), realist(Meta)=AGREE(rev=1), visionary(Google)=AGREE(rev=1)
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-08. [sweep] priority=non-blocking. Якоря: architecture-packet.json#AD-001 `listener_ownership`; `resilience_gates` C-MULT-I5 oracle. Правило: RW-004 (один lsof на горячем пути) против явного reconnect. Evidence: горячий путь permission/form/interrupt/DELETE — ровно один lsof на spawn. Тот же пакет разрешает один повторный proof ≤0.35 с при обрыве control. Оракул «exactly one lsof per successful spawn including permission/form/interrupt/DELETE» не отделяет этот recovery. Ожидание: счётчик 1 обязателен для reply/interrupt/DELETE; второй lsof допустим только в явном reconnect и не входит в бюджеты 0.25 с и 0.20 с. Проверка: spy VER-005 различает эти два сценария.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AGREE F-008 rev=1 — проверил: architecture-packet.json#C-MULT-I5 (`oracle`: «one lsof per successful spawn including permission/form/interrupt/DELETE») против AD-001#listener_ownership (reconnect с повторным proof ≤0.35 с). Оракул не отделяет явный reconnect от горячего пути. Non-blocking.
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): AGREE F-008 rev=1 — проверил: architecture-packet.json#AD-001 (`listener_ownership`) — пакет одновременно требует ровно один `lsof` на spawn в оракуле C-MULT-I5 и разрешает повторный proof ≤0.35 с при reconnect control-сокета; счётчик оракула не отделяет recovery от горячего пути reply/interrupt/DELETE (RW-004).
> - D1 visionary (`gemini-4-argon-high`, `Google`): AGREE F-008 rev=1 — проверил: architecture-packet.json:1531, architecture-packet.json:2920 — Оракул теста `C-MULT-I5` требует строго один вызов `lsof` на успешный spawn, не отделяя штатный Keep-Alive путь от аварийного однократного control-reconnect в `listener_ownership`, где допустим повторный `lsof`.

### F-009
- origin: visionary · R1 · visionary-F-001
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: excluded
- resolved_in: ceiling
- votes: R1 visionary(Anthropic)=AUTHOR(non-blocking; в D1 подтвердил дубль F-003); D1 realist(Meta)=DISPUTE(duplicate_of:F-003), visionary(Google)=DISPUTE(duplicate_of:F-003)
- dissent: duplicate_of:F-003 — realist (D1): DISPUTE F-009 — класс: duplicate_of:F-003 — контр-evidence: architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.creation`, `details.listener_ownership`) — те же якоря и тот же дефект двух деревьев процессов и неопределённости PGID/`proc.poll()`, что и F-003, только с priority=non-blocking; отдельный фикс не нужен, закрывается одним изменением с F-003. | visionary (D1): DISPUTE F-009 — класс: duplicate_of:F-003 — контр-evidence: architecture-packet.json:1184, architecture-packet.json:1526, architecture-packet.json:1775 — Замечание фиксирует ту же самую коллизию двух деревьев процессов (прямой `Popen` `opencode serve` против запуска через stdlib-хелпер и неоднозначность `proc.poll()`/`child_pgid`), которая уже отражена как `blocking` в `F-003`.
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> - **F-001** (non-blocking, 3. РЕАЛИЗУЕМОСТЬ)
>   - **Anchor:** architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.creation`, `details.listener_ownership`).
>   - **Дефект:** `spawn` описывает прямой `Popen([OPENCODE_BIN,serve,...], start_new_session=True)` и сохранение `child_pgid`. `crash_recovery.creation` говорит, что serve запускается под helper, который публикует идентичность ребёнка. Не зафиксировано, чьи `proc`/PGID использует `proc.poll()`, `os.getpgid(listener)==child_pgid` и `killpg`: serve или helper.
>   - **Исправление:** одной фразой задать топологию (helper-родитель или прямой serve плюс отдельный watchdog) и привязать `proc.poll()` и сравнение PGID к конкретному процессу.
>   - **Проверка:** оракул VER-005 GroupB явно проверяет PGID listener = PGID записанного serve при обеих ветках запуска.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AUTHOR (R1 visionary; в F-003 отметил дубль F-009)
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): DISPUTE F-009 — класс: duplicate_of:F-003 — контр-evidence: architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.creation`, `details.listener_ownership`) — те же якоря и тот же дефект двух деревьев процессов и неопределённости PGID/`proc.poll()`, что и F-003, только с priority=non-blocking; отдельный фикс не нужен, закрывается одним изменением с F-003.
> - D1 visionary (`gemini-4-argon-high`, `Google`): DISPUTE F-009 — класс: duplicate_of:F-003 — контр-evidence: architecture-packet.json:1184, architecture-packet.json:1526, architecture-packet.json:1775 — Замечание фиксирует ту же самую коллизию двух деревьев процессов (прямой `Popen` `opencode serve` против запуска через stdlib-хелпер и неоднозначность `proc.poll()`/`child_pgid`), которая уже отражена как `blocking` в `F-003`.

### F-010
- origin: visionary · R1 · visionary-F-002
- rev: 2
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: ceiling
- votes: R1 visionary(Anthropic)=AUTHOR(non-blocking); D1 realist(Meta)=AMEND(rev=2,non-blocking), visionary(Google)=AGREE(rev=1,non-blocking)
- dissent: realist (D1 AMEND): AMEND F-010 — priority=non-blocking; locations=architecture-packet.json#AD-001 (`feature_flag_context`), architecture-packet.json#EVD-074, evolution H0/H4/H5; fix=оставить только явную запись в H4/H5, что синхронизация копирует только `server.py` и не трогает `dynamic_config.json`/`disable-serve`, а требование подтверждения владельца снять — причина: architecture-packet.json#Q-003 (RESOLVED, `decision_required_human=false`) и EVD-074 фиксируют compliant-дельту cycle3b (`default=false`, runtime JSON только на H7 после H3/H6); стирание JSON при sync ведёт в безопасный `false`, а не в преждевременное включение, поэтому это уточнение протокола, а не блокер политики. | visionary (D1 AGREE rev=1): AGREE F-010 rev=1 — проверил: architecture-packet.json:873, architecture-packet.json:2507 — Шаг выката `H4` синхронизирует `server.py` в каталог `~/.dsh/bridges/opencode-zen-bridge/`, где хранятся живые `dynamic_config.json` и `disable-serve`, без явного запрета на синхронизацию директории с удалением runtime-файлов (`--delete`).
- owner_decision: —
- amendments: rev 2 (D1 realist Meta): AMEND F-010 — priority=non-blocking; locations=architecture-packet.json#AD-001 (`feature_flag_context`), architecture-packet.json#EVD-074, evolution H0/H4/H5; fix=оставить только явную запись в H4/H5, что синхронизация копирует только `server.py` и не трогает `dynamic_config.json`/`disable-serve`, а требование подтверждения владельца снять — причина: architecture-packet.json#Q-003 (RESOLVED, `decision_required_human=false`) и EVD-074 фиксируют compliant-дельту cycle3b (`default=false`, runtime JSON только на H7 после H3/H6); стирание JSON при sync ведёт в безопасный `false`, а не в преждевременное включение, поэтому это уточнение протокола, а не блокер политики.
- text (дословно, R1 visionary):
> - **F-002** (non-blocking, 6. СООТВЕТСТВИЕ КОНТЕКСТУ)
>   - **Anchor:** architecture-packet.json#ASM-003, #Q-003, #AD-001 (`feature_flag_context`).
>   - **Дефект:** эквивалентность локального `dynamic_config.json` фичефлагу GigaRC канона объявлена автором пакета. Подтверждения владельца нет, статус ASM-003 — ASSUMED. Развёрнутый JSON лежит рядом с `server.py` в `~/.dsh`, и синхронизация каталога с удалением может его стереть.
>   - **Исправление:** оставить решение внешнему Совету a3 и владельцу. В H4/H5 зафиксировать, что синхронизация копирует только `server.py` и не трогает `dynamic_config.json` и `disable-serve`.
>   - **Проверка:** H0 после sync читает файл обратно.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AUTHOR (R1 visionary; в F-003 отметил дубль F-009)
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): AMEND F-010 — priority=non-blocking; locations=architecture-packet.json#AD-001 (`feature_flag_context`), architecture-packet.json#EVD-074, evolution H0/H4/H5; fix=оставить только явную запись в H4/H5, что синхронизация копирует только `server.py` и не трогает `dynamic_config.json`/`disable-serve`, а требование подтверждения владельца снять — причина: architecture-packet.json#Q-003 (RESOLVED, `decision_required_human=false`) и EVD-074 фиксируют compliant-дельту cycle3b (`default=false`, runtime JSON только на H7 после H3/H6); стирание JSON при sync ведёт в безопасный `false`, а не в преждевременное включение, поэтому это уточнение протокола, а не блокер политики.
> - D1 visionary (`gemini-4-argon-high`, `Google`): AGREE F-010 rev=1 — проверил: architecture-packet.json:873, architecture-packet.json:2507 — Шаг выката `H4` синхронизирует `server.py` в каталог `~/.dsh/bridges/opencode-zen-bridge/`, где хранятся живые `dynamic_config.json` и `disable-serve`, без явного запрета на синхронизацию директории с удалением runtime-файлов (`--delete`).

### F-011
- origin: visionary · R1 · visionary-F-003
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: excluded
- resolved_in: ceiling
- votes: R1 visionary(Anthropic)=AUTHOR(non-blocking); D1 realist(Meta)=DISPUTE(invalid), visionary(Google)=DISPUTE(invalid)
- dissent: invalid_after_recheck — realist (D1): DISPUTE F-011 — класс: invalid — контр-evidence: architecture-packet.json#EVD-071, `high_load_envelope.operational_profile.p99_criteria`, `evolution.H3_rollout_gate` — предлагаемый фиск уже дословно заложен: H3 измеряет суммарный RSS serve+helper+lsof против 1638.4 MiB, normal p99 ≤180 с и degraded ≤231.6 с по выборке ≥100, при FAIL включение запрещено и лимиты не повышаются; дефекта пакета, требующего дельты, нет, это напоминание держать гейт без смягчения. | visionary (D1): DISPUTE F-011 — класс: invalid — контр-evidence: architecture-packet.json:2514, architecture-packet.json:2802, architecture-packet.json:2815 — Замер фактического RSS всех 6 слотов (`<=1638.4 MiB`), nearest-rank `p99` на выборке `>=100` запросов (`<=231.6s` degraded / `<=180.0s` normal) и удержание `serve` выключенным без повышения лимитов при нарушении порога уже нормативно прописаны в `H3_rollout_gate`, `operational_profile.p99_criteria` и `memory_closure_check`.
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> - **F-003** (non-blocking, 4. РИСКИ)
>   - **Anchor:** architecture-packet.json#high_load_envelope (`operational_profile.p99_criteria`, `memory_closure_check`), #EVD-071.
>   - **Дефект:** запас памяти на слот в простое всего ~35 MiB (192 − 156.8) на serve плюс helper плюс lsof. Деградированный профиль 231.6 с превышает SLA 180 с. Оба признаны оценками.
>   - **Исправление:** H3 обязан фиксировать фактический суммарный RSS и p99 по выборке ≥100 в нормальном и деградированном профиле. При превышении serve остаётся выключенным, лимиты не повышаются. Это уже заложено, пункт нужно держать без смягчения.
>   - **Проверка:** H3 сравнивает суммарный RSS с 1638.4 MiB, а p99 — с 180 с и 231.6 с.
- позиции D1 (`panel/arch/r7`, дословно):
> - D1 skeptic (`claude-sonnet-5-5-high`, `Anthropic`): AUTHOR (R1 visionary; в F-003 отметил дубль F-009)
> - D1 realist (`muse-wonder-full-1.0`, `Meta`): DISPUTE F-011 — класс: invalid — контр-evidence: architecture-packet.json#EVD-071, `high_load_envelope.operational_profile.p99_criteria`, `evolution.H3_rollout_gate` — предлагаемый фиск уже дословно заложен: H3 измеряет суммарный RSS serve+helper+lsof против 1638.4 MiB, normal p99 ≤180 с и degraded ≤231.6 с по выборке ≥100, при FAIL включение запрещено и лимиты не повышаются; дефекта пакета, требующего дельты, нет, это напоминание держать гейт без смягчения.
> - D1 visionary (`gemini-4-argon-high`, `Google`): DISPUTE F-011 — класс: invalid — контр-evidence: architecture-packet.json:2514, architecture-packet.json:2802, architecture-packet.json:2815 — Замер фактического RSS всех 6 слотов (`<=1638.4 MiB`), nearest-rank `p99` на выборке `>=100` запросов (`<=231.6s` degraded / `<=180.0s` normal) и удержание `serve` выключенным без повышения лимитов при нарушении порога уже нормативно прописаны в `H3_rollout_gate`, `operational_profile.p99_criteria` и `memory_closure_check`.

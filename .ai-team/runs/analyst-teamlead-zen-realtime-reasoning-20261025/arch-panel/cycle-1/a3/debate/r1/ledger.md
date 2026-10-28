# Черновой консенсус-леджер находок Архитектурного Совета — Cycle 1 (`a3`, после `R1` `panel/arch/r4`)

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r4` (`panel-proof.json` `sha256=abddbe7d2b8b60086143ec49356c231f21f0d03ec05c51c06b7aaa3b0da6e9f9`, `verify_panel_proof exit=0`)
- **Проверяемый артефакт (v3):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`sha256=8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608`)
- **Всего открытых находок после R1:** 11 (`F-001`..`F-008` от `skeptic`, `0` от `realist`, `F-009`..`F-011` от `visionary`)

---

## Находки Seat 1 (`skeptic`, `grok-4.7-high`, `xAI`, `cursor-agent`)

### F-001
- origin: skeptic · R1 · skeptic-F-01
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
> F-01. priority=blocking. Якорь: architecture-packet.json#VER-004. Правило: RW-001, acceptance «воспроизводимые команды» и «без выдуманных CLI-флагов»; одновременно VER-005/`immutable_run_env`. Evidence: команда вызывает `ruff format --check --range {start}:{end}`. У ruff==0.17.2 формат такой: `<start_line>:<start_column>-<end_line>:<end_column>`; конец необязателен и тогда форматируется документ до EOF. Прогон: `--range 1:2` переписал весь файл; `--range 4:99` переписал хвост после точки старта. Ранний hunk в `server.py` поэтому требует формат замороженного тела (3216 строк diff, hash `_run_env` `1c51b28f…` → другой). Ожидание: закрытый диапазон и отказ гейта, если diff форматтера задевает `_run_env` или Google-функции. Проверка: synthetic early hunk на текущем `server.py` не помечает эти срезы unformatted.

### F-002
- origin: skeptic · R1 · skeptic-F-02
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
> F-02. priority=blocking. Якорь: architecture-packet.json#AD-001 (`details.typing`), дубль в VER-004. Правило: REQ-003/AC-004, `coder_target_files`, FU-002 (17 модулей не править). Evidence: пакет требует «Rename mutable internal CATALOG_SOURCE to lower-case». Вне allowlist `tests/test_catalog_mode.py:64` делает `self.assertEqual(server.CATALOG_SOURCE, "static")`, строка 93 печатает `server.CATALOG_SOURCE`. Переименование атрибута роняет VER-001/VER-002; сохранение имени оставляет `reportConstantRedefinition`, а VER-004 требует `errorCount==0`. Ожидание: одно из двух явных решений в пакете — не переименовывать атрибут, либо добавить в allowlist только этот файл и две ссылки. Проверка: после Stage3 `test_catalog_mode` зелёный и basedpyright `errorCount==0` без `type: ignore`.

### F-003
- origin: skeptic · R1 · skeptic-F-03
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
> F-03. priority=blocking. Якоря: architecture-packet.json#AD-001 `details.spawn`, `details.listener_ownership`, `details.crash_recovery`. Правило: T-LIFE/v1, RW-006. Evidence: spawn задаёт `Popen([OPENCODE_BIN, serve, --hostname, 127.0.0.1, --port, str(port)], stdin=DEVNULL, start_new_session=True)`. `crash_recovery.creation` задаёт другое дерево: «spawn under lease-named stdlib helper which publishes child identity atomically». Прямой `Popen` serve не публикует pid до отдельной записи lease; reaper при пустом pid убивать по имени не может. Ожидание: один текст дерева процессов и тот же учёт helper/FD. Проверка: VER-005 hard kill в щели после старта до READY даёт 0 своих serve и 0 чужих сигналов.

### F-004
- origin: skeptic · R1 · skeptic-F-04
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
> F-04. priority=blocking. Якоря: architecture-packet.json#AD-001 `event_contract` negative_mutations формы; architecture-packet.json#EVD-073. Правило: RW-003, REQ-012, THREAT-002. Evidence: мутация «missing form.id/fields/title -> invalid_serve_event». EVD-073: у Form.Info `title` необязателен, session id лежит в `data.form.sessionID`. Форма без title становится protocol failure и не идёт в cancel ≤0.25 с, то есть вопрос снова ждёт watchdog. Ожидание: обязательны id, вложенный sessionID и fields; отсутствие title не мешает cancel и не увеличивает `_ServeHealth`. Проверка: FakeServe шлёт `form.created` без title, cancel уходит ≤0.25 с, Step2 в сокет не попадает.

### F-005
- origin: skeptic · R1 · skeptic-F-05
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
> F-05. priority=non-blocking. Якоря: architecture-packet.json#AD-002 `status_protocol_examples.waiting` и `details.lifecycle`. Правило: FU-005, REQ-004/AC-005. Evidence: шаблон `"[мост] Ожидание первого токена (10 с)…\n"`, lifecycle — `"[мост] Ожидание первого токена…"` каждые 5.0 с, без счётчика. Ожидание: одна байтовая строка в шаблоне, lifecycle и VER-005. Проверка: тест падает при второй строке.

### F-006
- origin: skeptic · R1 · skeptic-F-06
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
> F-06. priority=non-blocking. Якоря: architecture-packet.json#AD-001 `fallback_decision_table` и `transport_health.counted_failures`. Правило: FU-004, RISK-012. Evidence: таблица объявлена авторитетной и для `first_token_timeout` содержит только «valid protocol and model silence» → ServeHealth 0, UpstreamBreaker 1. `counted_failures` отдельно считает `first_token_timeout` счётчиком `_ServeHealth`, если доказан дефект протокола. Строки на этот случай в таблице нет. Ожидание: отдельная строка таблицы с ServeHealth +1 и UpstreamBreaker 0. Проверка: VER-005 параметризует обе причины и видит ровно один инкремент нужного счётчика.

### F-007
- origin: skeptic · R1 · skeptic-F-07
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
> F-07. [sweep] priority=non-blocking. Якорь: architecture-packet.json#AD-003 `details.cleanup`. Правило: привязка утверждения к факту ledger. Evidence: cleanup ссылается на EVD-056 для убийства потомков после выхода leader. EVD-056 — это `WORKTREE_UNCHANGED`. Факт про `_stop_proc` и потомков — EVD-055. Ожидание: заменить ссылку на EVD-055, норматив killpg не менять. Проверка: в пакете нет утверждения, которое опирается на EVD-056 как на поведение процессов.

### F-008
- origin: skeptic · R1 · skeptic-F-08
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
> F-08. [sweep] priority=non-blocking. Якоря: architecture-packet.json#AD-001 `listener_ownership`; `resilience_gates` C-MULT-I5 oracle. Правило: RW-004 (один lsof на горячем пути) против явного reconnect. Evidence: горячий путь permission/form/interrupt/DELETE — ровно один lsof на spawn. Тот же пакет разрешает один повторный proof ≤0.35 с при обрыве control. Оракул «exactly one lsof per successful spawn including permission/form/interrupt/DELETE» не отделяет этот recovery. Ожидание: счётчик 1 обязателен для reply/interrupt/DELETE; второй lsof допустим только в явном reconnect и не входит в бюджеты 0.25 с и 0.20 с. Проверка: spy VER-005 различает эти два сценария.

---

## Находки Seat 3 (`visionary`, `claude-sonnet-5-5-high`, `Anthropic`, `claude-p`)

### F-009
- origin: visionary · R1 · visionary-F-001
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> - **F-001** (non-blocking, 3. РЕАЛИЗУЕМОСТЬ)
>   - **Anchor:** architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.creation`, `details.listener_ownership`).
>   - **Дефект:** `spawn` описывает прямой `Popen([OPENCODE_BIN,serve,...], start_new_session=True)` и сохранение `child_pgid`. `crash_recovery.creation` говорит, что serve запускается под helper, который публикует идентичность ребёнка. Не зафиксировано, чьи `proc`/PGID использует `proc.poll()`, `os.getpgid(listener)==child_pgid` и `killpg`: serve или helper.
>   - **Исправление:** одной фразой задать топологию (helper-родитель или прямой serve плюс отдельный watchdog) и привязать `proc.poll()` и сравнение PGID к конкретному процессу.
>   - **Проверка:** оракул VER-005 GroupB явно проверяет PGID listener = PGID записанного serve при обеих ветках запуска.

### F-010
- origin: visionary · R1 · visionary-F-002
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> - **F-002** (non-blocking, 6. СООТВЕТСТВИЕ КОНТЕКСТУ)
>   - **Anchor:** architecture-packet.json#ASM-003, #Q-003, #AD-001 (`feature_flag_context`).
>   - **Дефект:** эквивалентность локального `dynamic_config.json` фичефлагу GigaRC канона объявлена автором пакета. Подтверждения владельца нет, статус ASM-003 — ASSUMED. Развёрнутый JSON лежит рядом с `server.py` в `~/.dsh`, и синхронизация каталога с удалением может его стереть.
>   - **Исправление:** оставить решение внешнему Совету a3 и владельцу. В H4/H5 зафиксировать, что синхронизация копирует только `server.py` и не трогает `dynamic_config.json` и `disable-serve`.
>   - **Проверка:** H0 после sync читает файл обратно.

### F-011
- origin: visionary · R1 · visionary-F-003
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> - **F-003** (non-blocking, 4. РИСКИ)
>   - **Anchor:** architecture-packet.json#high_load_envelope (`operational_profile.p99_criteria`, `memory_closure_check`), #EVD-071.
>   - **Дефект:** запас памяти на слот в простое всего ~35 MiB (192 − 156.8) на serve плюс helper плюс lsof. Деградированный профиль 231.6 с превышает SLA 180 с. Оба признаны оценками.
>   - **Исправление:** H3 обязан фиксировать фактический суммарный RSS и p99 по выборке ≥100 в нормальном и деградированном профиле. При превышении serve остаётся выключенным, лимиты не повышаются. Это уже заложено, пункт нужно держать без смягчения.
>   - **Проверка:** H3 сравнивает суммарный RSS с 1638.4 MiB, а p99 — с 180 с и 231.6 с.

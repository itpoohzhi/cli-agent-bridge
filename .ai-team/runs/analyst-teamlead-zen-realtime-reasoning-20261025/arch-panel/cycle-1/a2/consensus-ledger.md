# Консенсус-леджер находок Архитектурного Совета — Cycle 1 (`a2`, `panel/arch/r3`)

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Раунд:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r3`
- **Проверяемый артефакт (v2):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.v2.json` (`sha256=c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d`)
- **PANEL PROOF:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r3/panel-proof.json` (`sha256=552c04b1069c6b7a4b907284c8638c7301dc00ec13e661d3964810323b785ddc`, `verify_panel_proof exit=0`)
- **Голоса судей:** Seat 1 (`gemini-4-argon-high`, `Google`) = `NEEDS WORK`, Seat 2 (`claude-sonnet-5-5-high`, `Anthropic`) = `NEEDS WORK`, Seat 3 (`muse-wonder-full-1.0`, `Meta`) = `PASS` → cross-family majority `2/3 NEEDS WORK` (включая усиленный критерий `4. РИСКИ` ×1.5 FAIL у двух семейств → Класс A `NEEDS WORK`, возврат `Architect` через `panel-rework-summarizer`)
- **Примечание о режиме консенсуса:** разрешающая поправка `consensus-debate.md` §11 в `~/Мой диск/Context/models.md` отсутствует (`select_round_seats.py` применяет per-round redraw и anti-repeat window §1.2), поэтому проход финализирован по леджеру R1 (`8` blocking: `F-001..F-005` от Seat 1 + `F-006, F-007, F-009` от Seat 2, из которых `F-009` подтверждает `F-001` от второго семейства, а `F-007` пересекается с `F-002`; `8` non-blocking: `F-008, F-010..F-016`).
- **Всего находок в батче:** 16 (`F-001` .. `F-016`)

---

## Находки Seat 1 (`skeptic`, `gemini-4-argon-high`, `Google`, `agy`)

### F-001
- origin: skeptic · R1 · seat1-F-01
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r3-majority
- votes: R1 skeptic=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> - **F-01** (`priority: blocking`, критерии: `3. РЕАЛИЗУЕМОСТЬ`, `2. ПОЛНОТА`, `6. СООТВЕТСТВИЕ КОНТЕКСТУ`)
>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/verification_surface/3` `VER-004`, `#/decisions/0/details/immutable_run_env`, `#/verification_surface/4` `VER-005`, `#/scope/forbidden`); [server.py](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L66-L67), [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1093-L1131); [pyrightconfig.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/pyrightconfig.json); [ruff.toml](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/ruff.toml).
>   - **Нарушенное правило**: реализуемость и непротиворечивость замороженной `verification_surface` (`aisdlc-gcge/skills/architecture.md` §Python verification surface, `REQ-003`, `RW-002`, `RW-012`, `FU-004`).
>   - **Доказательство**:
>     1. Скрипт `VER-004` запускается из `cwd = repo_root` (`cwd=None`), где лежат корневые `/server.py`, `/tests/` и `pyrightconfig.json` (`"extraPaths": ["tools"]`). Прямой запуск `uvx --from basedpyright==1.40.2 basedpyright --outputjson bridges/opencode-zen-bridge/server.py bridges/opencode-zen-bridge/tests/test_step_interruption.py` даёт **`errorCount == 80`** (`2` в `server.py`, включая `import zen_catalog as zc` на строке 67 при дефисном каталоге `opencode-zen-bridge`, и `78` в `test_step_interruption.py`, где `import server` статически резолвится в корневой `/server.py`, в котором отсутствуют `ALLOWED_MODELS`, `OPENCODE_BIN`, `DEFAULTWORKDIR`, `_strip_interrupted`, `ToolCallParser.has_open_tool_call`). Аналогично упадёт и новый `tests/test_realtime_reasoning.py`, при том что `tests/_fake_cli.py`, `tests/_fixtures.py`, `tests/_http.py` вне `coder_target_files`, а `# pyright: ignore` и изменение `pyrightconfig.json` запрещены `VER-004.expected` и `scope.forbidden`.
>     2. Корневой `ruff.toml` использует стандартный `line-length = 88`. В [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1093-L1131) 11 строк имеют длину 90–108 символов: прогон `uvx --from ruff==0.17.2 ruff format` меняет `sha256` байтового среза `_run_env` с замороженного `1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` на `85c9c344b339f188a7c97b802e431297aab0ef5b4bdd6ecaba46902962eeb104` (ломая `VER-005`) и переписывает ~1 250 строк `server.py` (`4021 -> 4976`), включая прямой Google route, трогать который запрещено `scope.forbidden` (`"прямой Google route и test_google_direct.py"`), тогда как `# fmt: off` запрещён `VER-004.expected` (`"без type-ignore/disable/изменения конфигов"`).
>   - **Ожидаемое исправление**: (а) в `VER-004` запускать `basedpyright` с `cwd="bridges/opencode-zen-bridge"` и сгенерированным во временном файле `/tmp` конфигом `--project` (указывающим `root` на `bridges/opencode-zen-bridge` без мутации репозитория), чтобы `server`, `zen_catalog` и `tests.*` резолвились строго внутри моста; (б) для `ruff format` проверять форматирование нового файла `tests/test_realtime_reasoning.py` целиком, а для legacy `server.py` и `test_step_interruption.py` — только изменённые ханки `git diff` (не трогая `_run_env` и Google-direct), либо заменить побайтовый SHA-256 среза `_run_env` на канонический AST-хэш при явном исключении Google-direct из форматирования.
>   - **Критерий верификации**: команда `VER-004` на текущем `test_step_interruption.py` резолвит `bridges/opencode-zen-bridge/server.py` (`0` ошибок отсутствующих атрибутов корневого `/server.py`), а одновременное прохождение `VER-004` и `VER-005` сохраняет `immutable_run_env` и нулевой `git diff` по функциям Google-direct в `server.py`.

### F-002
- origin: skeptic · R1 · seat1-F-02
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r3-majority
- votes: R1 skeptic=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> - **F-02** (`priority: blocking`, критерии: `1. КОРРЕКТНОСТЬ`, `2. ПОЛНОТА`, `4. РИСКИ`, `5. АЛЬТЕРНАТИВЫ`, `6. СООТВЕТСТВИЕ КОНТЕКСТУ`)
>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/decisions/0/details/data_isolation`, `#/decisions/0/details/fallback_barrier`, `#/rework_resolutions/5` `RW-006`, `#/rework_resolutions/14` `FU-001`); [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1099-L1104); [opencode-go.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/opencode-go.json).
>   - **Нарушенное правило**: сохранение работоспособности существующих моделей моста (`REQ-002` публичный контракт `/v1/models` + `/v1/chat/completions`, `RW-006`/`FU-001` изоляция без регрессий, оценка штатных альтернатив `5. АЛЬТЕРНАТИВЫ`).
>   - **Доказательство**: для не-Google моделей маршрута `opencode-go/*` (`glm-5.1`, `kimi-k2.5`, `minimax-m2.5`, `minimax-m2.7`; см. [test_go_model_routing.py](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_go_model_routing.py#L55-L120)) `_run_env` передаёт `OPENCODE_CONFIG=.../opencode-go.json` с `baseURL = "http://127.0.0.1:10830/go/v1"` без `apiKey`. В бинарнике `~/.opencode/bin/opencode` v2.1.2 (`@112656461`, `@121011124`, `@123591903`) учётные данные провайдера `opencode-go` загружаются из `XDG_DATA_HOME/opencode/auth.json` и импортируются миграцией `20260805200742_import_legacy_credentials` в таблицу `credential`. Установка пустого `env["XDG_DATA_HOME"] = tempfile.mkdtemp(prefix="zen-serve-data-")` на каждый `serve` spawn лишает `opencode serve` ключа `opencode-go`, вызывая `ProviderAuthError` (`provider.auth` -> 401), а правило `AD-001.details.fallback_barrier` (`"HTTP401/403/auth/... -> fail-closed без fallback"`) запрещает откат на `opencode run`. Одновременно в самом бинарнике `opencode` v2.1.2 (`@114651600`, `@122016915`) реализован штатный флаг `OPENCODE_DB=":memory:"`, отключающий файловую `opencode.db` и чтение `opencode-next.db` без создания/удаления SQLite на каждый запрос.
>   - **Ожидаемое исправление**: задать в `_serve_env(model_id)` `env["OPENCODE_DB"] = ":memory:"` (оценив и зафиксировав это в `AD-001.details.data_isolation`); если дополнительно изолируется `XDG_DATA_HOME`, обеспечить для ветки `ALLOWED_MODELS[model_id].get("base_url")` (`opencode-go/*`) сохранение read-only доступа к `auth.json` (симлинк/чтение без мутации общей `opencode.db`) либо явную маршрутизацию, исключающую ложный 401 `fail-closed`.
>   - **Критерий верификации**: в `VER-005` добавлен тест `_serve_env` для обеих групп моделей (`standalone` Zen и `opencode-go/*`), подтверждающий отсутствие записи в `~/.local/share/opencode/opencode.db`, наличие `OPENCODE_DB=":memory:"` (или эквивалентной сохранности `auth.json` для `opencode-go/*`) и успешный прогон без 401 `ProviderAuthError`.

### F-003
- origin: skeptic · R1 · seat1-F-03
- rev: 1
- priority: blocking
- status: CONSENTED
- outcome: blocking
- resolved_in: r3-majority
- votes: R1 skeptic=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> - **F-03** (`priority: blocking`, критерии: `1. КОРРЕКТНОСТЬ`, `2. ПОЛНОТА`, `4. РИСКИ`)
>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/decisions/0/details/tool_policy`, `#/decisions/0/details/session_flow`, `#/decisions/0/details/session_wire`, `#/decisions/0/details/event_contract`, `#/decisions/3/details/step`, `#/threat_model/threats/1` `THREAT-002`).
>   - **Нарушенное правило**: полный отказ от выполнения/блокировки встроенных инструментов CLI в пользу клиента DSH и сохранение нативного маппинга инструментов (`REQ-011`, `REQ-012`, `AC-016`, `AC-017`, `THREAT-002`).
>   - **Доказательство**: сверка с бинарником `~/.opencode/bin/opencode` v2.1.2 вскрывает три неучтённые механики:
>     1. Интерактивные встроенные инструменты (`question`/forms, остающиеся включёнными из-за `EVD-050`/`F-08`) публикуют событие `form.created` (`@114605908`, `@115254160`), а не `permission.asked`; сам нативный клиент `opencode run` (`@122625575`, функция `J`) немедленно вызывает `client.session.form.cancel({sessionID, formID})`. В пакете v2 `form.created` отсутствует — вызов `question` приведёт к 60-секундному зависанию сессии до watchdog.
>     2. В нативном клиенте `opencode run` (`@122625575`, функция `se`) сразу после `permission.reply(..., decision: "reject")` вызывается `client.session.interrupt({sessionID})`, поскольку сам по себе `decision: "reject"` в `opencode serve` переводит инструмент в `session.tool.failed` и продолжает агентный цикл во **второй шаг LLM (Step 2)**, стримя клиенту нерелевантный текст отказа и тратя квоту Zen, если вызов не был смаплен в DSH `tool_calls`.
>     3. В редьюсере `opencode` v2.1.2 (`@115409671`, `@121654561`) событие `session.tool.failed` допустимо напрямую из состояния `status === "streaming"` (без предварительного `session.tool.called`), где входные аргументы содержатся только в строке `session.tool.input.ended.data.text`, тогда как `event_contract["session.tool.*"]` опирается на `called(input, executed)`.
>   - **Ожидаемое исправление**: (1) добавить в `tool_policy`, `session_wire` и `event_contract` обработку `form.created` -> немедленный `POST /api/session/{id}/form/{formID}/cancel` по control lane (`<=0.25 s`, `fail-closed` при ошибке); (2) указать fallback парсинга JSON-аргументов из `session.tool.input.ended.data.text`, если `session.tool.called` не пришёл до `failed`/`step.ended`; (3) зафиксировать правило single-turn прерывания: после любого `permission.asked -> reject` (или `form.created -> cancel`) мост не допускает запуска Step 2 в `opencode serve` — либо возвращает смапленный DSH `tool_calls` на границе шага и вызывает `interrupt`, либо немедленно шлёт `POST /api/session/{id}/interrupt` и применяет существующую логику `_incomplete_step_signal` / unmapped-tool recovery.
>   - **Критерий верификации**: `FakeServe` в `VER-005` проверяет: (а) `form.created` отменяется за `<=0.25 s` без 60-секундного таймаута; (б) маппируемый нативный tool call восстанавливает аргументы как из `session.tool.called.data.input`, так и из `session.tool.input.ended.data.text`; (в) после `decision: "reject"` второй шаг генерации (`Step 2`) не стримит побочный текст в клиентский сокет.

### F-004
- origin: skeptic · R1 · seat1-F-04
- rev: 1
- priority: blocking
- status: CONSENTED
- outcome: blocking
- resolved_in: r3-majority
- votes: R1 skeptic=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> - **F-04** (`priority: blocking`, критерии: `1. КОРРЕКТНОСТЬ`, `4. РИСКИ`, `5. АЛЬТЕРНАТИВЫ`)
>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/decisions/0/details/listener_ownership`, `#/decisions/0/details/tool_policy`, `#/decisions/0/details/session_wire/cleanup`, `#/decisions/2/details/cleanup`, `#/resilience_gates/C_MULT`).
>   - **Нарушенное правило**: замыкание бюджетов времени на вспомогательных и cleanup-вызовах и учёт порождаемых подпроцессов (`R-BULK-I1`, `T-LIFE/v1`, `C-MULT/v1`, `REQ-001` AC-002 `<=250 ms`, `RW-003`).
>   - **Доказательство**: `AD-001.details.listener_ownership` требует запускать `lsof -nP -a -iTCP:<port> -sTCP:LISTEN -Fp` «до первого Auth и повторно до отправки Auth на каждом новом TCP соединении». На целевом Mac измеренное время одного вызова `lsof` составляет **`68.1 ms`**, а при 6 параллельных вызовах (`H3`) — **`82.0..88.1 ms`** на каждый вызов в отсутствие прочей нагрузки. При этом `session_wire.cleanup.aggregate_api_budget_s = 0.20` (`AD-003.cleanup`: `interrupt` `<=0.10 s` + `DELETE` `<=0.10 s`), а `permission_reply` имеет общий бюджет `<=0.25 s`. Открытие нового TCP-соединения с предварительным `lsof` (~85 мс) оставляет `<15 мс` на TCP+HTTP и гарантированно срывает `0.10 s` бюджет `interrupt`/`DELETE` под нагрузкой, а также порождает 24–30 неучтённых в `_SpawnRateLimiter` подпроцессов `lsof` на волну из 6 запросов.
>   - **Ожидаемое исправление**: выполнять `lsof -nP -a -iTCP:<port> -sTCP:LISTEN -Fp` и проверку `os.getpgid(listener_pid) == child_pgid` **однократно** после привязки порта на фазе `SPAWN -> READY`; далее использовать постоянное `HTTP/1.1 Keep-Alive` control-соединение (плюс одно `SSE`-соединение и одно `prompt`-соединение, открытые сразу после проверки владения), проверяя перед отправкой `Authorization` живость собственного процесса `proc.poll() is None` (пока дочерний процесс жив и держит `LISTEN` сокет на `127.0.0.1:<port>`, перехват порта другим процессом на macOS/POSIX невозможен; повторный `lsof` допустим только при переоткрытии упавшего control-сокета в пределах явного бюджета `>=0.30 s`).
>   - **Критерий верификации**: в `VER-005` spy на запуск `lsof` подтверждает ровно `1` вызов `lsof` на успешный `serve` spawn (включая сценарий с `permission.asked -> reply` и финальным `interrupt`/`DELETE`), а негативный тест подмены listener до `READY` по-прежнему даёт `0` отправленных байт `Authorization`/промпта.

### F-005
- origin: skeptic · R1 · seat1-F-05
- rev: 1
- priority: blocking
- status: CONSENTED
- outcome: blocking
- resolved_in: r3-majority
- votes: R1 skeptic=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> - **F-05** (`priority: blocking`, критерии: `2. ПОЛНОТА`, `4. РИСКИ`, `6. СООТВЕТСТВИЕ КОНТЕКСТУ`)
>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/threat_model/threats/2` `THREAT-003`, `#/decisions/0/details/tool_policy`, `#/decisions/0/details/immutable_run_env`); [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1093-L1131).
>   - **Нарушенное правило**: защита секретов родительского окружения от утечки в дочерний HTTP-сервер (`THREAT-003`, `4. РИСКИ/безопасность`).
>   - **Доказательство**: `THREAT-003` утверждает: `"_run_env whitelist как legacy, password добавляется только child env... _serve_env wrapper не меняет _run_env"`. Однако чтение [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1095-L1131) показывает, что строка 1095 копирует полный `env = dict(os.environ)`, а фильтрация по `_STANDALONE_ENV_ALLOWLIST` выполняется **только** внутри `elif _uses_standalone(model_id):` (строка 1108). В ветке `if ALLOWED_MODELS.get(model_id, {}).get("base_url"):` (`opencode-go/*`, строки 1099–1103) и в ветке `else:` (`CATALOG_MODE="static"`, строки 1127–1130) возвращается полный нефильтрованный `os.environ` родителя (включая `OPENCODE_ZEN_BRIDGE_API_KEY`, `OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY` с логином/паролем и любые секреты окружения моста), который `_serve_env` передаст в HTTP-демон `opencode serve`.
>   - **Ожидаемое исправление**: оставив `_run_env` побайтово неизменной, в обёртке `_serve_env(model_id)` явно фильтровать результирующий словарь окружения по белому списку допустимых переменных для всех веток моделей (либо гарантированно вычищать `OPENCODE_ZEN_BRIDGE_*`, `*_API_KEY`, `*_TOKEN`, `*_SECRET` и посторонние переменные родителя до добавления одноразового `OPENCODE_SERVER_PASSWORD`).
>   - **Критерий верификации**: негативный тест secret-sentinel в `VER-005` проверяет `_serve_env(model_id)` на всех трёх ветках (`standalone`, `opencode-go/*` с `base_url`, `CATALOG_MODE="static"`) и подтверждает отсутствие родительских секретов (`OPENCODE_ZEN_BRIDGE_API_KEY`, произвольного `SECRET_SENTINEL`) в окружении дочернего `opencode serve`.

---

## Находки Seat 2 (`realist`, `claude-sonnet-5-5-high`, `Anthropic`, `claude-p`)

### F-006
- origin: realist · R1 · seat2-F-1
- rev: 1
- priority: blocking
- status: CONSENTED
- outcome: blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-1** [РИСКИ, blocking]
> - Anchor: architecture-packet.json#AD-001 (`details.spawn`: `stdin=DEVNULL`, `start_new_session=True`), #T_LIFE_v1; [F-14], [F-30].
> - Правило: T-LIFE/v1 (отсутствие осиротевших процессов).
> - Evidence: legacy `opencode run` завершается при закрытии stdin/pipe. `opencode serve` — долгоживущий сервер, и со `stdin=DEVNULL` сам не завершится. Дочерний процесс в новой сессии не попадает под зачистку launchd при перезапуске или SIGKILL моста. Оракул T-LIFE покрывает только отмену внутри живого процесса: 50 отмен, нули счётчиков. Rollout включает перезапуск LaunchAgent (H0, H9).
> - Исправление: добавить реестр владения (pid, pgid, время старта и метка владельца в имени temp-каталога или env). На старте моста добавить зачистку сирот и каталогов `zen-serve-data-*`, с проверкой по `ps` перед kill. Либо parent-death watchdog у дочернего процесса.
> - Проверка: тест в VER-005 «жёсткий kill родителя → следующий запуск моста убирает serve и каталоги»; в H0/H9 после `kickstart -k` ноль процессов `serve`.

### F-007
- origin: realist · R1 · seat2-F-2
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-2** [РИСКИ/РЕАЛИЗУЕМОСТЬ, blocking]
> - Anchor: #AD-001 (`details.data_isolation`), #ASM-001, #RISK-003, #EVD-063.
> - Evidence: замеры [F-19]/[F-20] (старт 109 мс, первая дельта 1.8 с, RSS 152 MiB) сняты с общим каталогом данных. В цикле 2 opencode не запускался (EVD-063). Поведение `serve` при пустом `XDG_DATA_HOME` не проверено: нужны первичные миграции SQLite, состояние и auth. Влияние на 109 мс и ready≤3 с неизвестно. Не могу проверить.
> - Исправление: до заморозки или первой задачей Coder выполнить дешёвый спайк без вызова провайдера и без расхода квоты Zen. Запустить `serve` с пустым `XDG_DATA_HOME` и сохранённым `OPENCODE_MODELS_PATH`, проверить `GET /api/info` и `/api/session/active`, записать время старта, RSS и созданные файлы. Добавить результат в evidence. При провале иметь запасное решение: общая БД плюс `_StartupGate`.
> - Проверка: EVD с цифрами спайка; VER-005 использует их как калибровку ready-бюджета.

### F-008
- origin: realist · R1 · seat2-F-3
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-3** [РИСКИ/АЛЬТЕРНАТИВЫ, non-blocking]
> - Anchor: #AD-001 (`details.listener_ownership`, `details.transport_health.counted_failures`); [F-30].
> - Evidence: owner-proof идёт через `lsof` с лимитом 0.25 с, повторяется на каждом новом TCP-соединении. Отказ или таймаут `lsof` даёт `ServeUnavailable`. В `counted_failures` он не перечислен. При таймаутах под 6 параллельными запросами каждый запрос тратит spawn и токен retry и уходит на `run`, а деградации не наступает. Subprocess `lsof` не учтён в потоках, FD и cap. [F-30] показывает, что `opencode` сам запускает `serve --port 0` как дочерний процесс; альтернатива «порт сообщает собственный дочерний процесс через его pipe» не рассмотрена. Выдаёт ли `serve` порт в stdout, не могу проверить.
> - Исправление: классифицировать отказ owner-proof и учитывать его в `_ServeHealth`. Кэшировать проверку на keep-alive соединение. Учесть `lsof` в `thread_accounting`/FD. Занести альтернативу `--port 0` + объявление порта в AD-001 как рассмотренную.
> - Проверка: оракул VER-005 «`lsof` timeout ×3 → DEGRADED, без лишних Popen».

### F-009
- origin: realist · R1 · seat2-F-4
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-4** [РЕАЛИЗУЕМОСТЬ, blocking]
> - Anchor: #VER-004 (`limits`), #RISK-008, #EVD-052/053.
> - Evidence: сумма `limits` равна 125+125+39+70+48+35+2+27+81+3+3+2+2+1+1 = 564, то есть ровно базовым 564 предупреждениям. Запаса нет ни по одному правилу для ~1000+ строк нового кода: правила вне словаря получают лимит 0. Pre-existing E402 и 2 error-сайта (`zen_catalog` import, `CATALOG_SOURCE`) должны быть исправлены без `type-ignore`/конфигов; достижимость не проверена, а import-механизм связан с деплоем. `ruff format --check` на базовой линии для `server.py` и `test_step_interruption.py` не запускался (EVD-052/053 — только check и basedpyright); возможен реформат всего файла и шум в diff, что противоречит AGENTS.md п. 4.
> - Исправление: до заморозки записать в evidence read-only базовые результаты `ruff format --check` и `basedpyright` по всем 3 файлам. Определить допустимый способ исправить import `zen_catalog`. Либо отдельный предварительный коммит/стадия 3a для долга. Либо явно заложить запас по правилам, не отменяя `errorCount==0`.
> - Проверка: EVD с базовыми числами; VER-004 воспроизводим на чистом клоне до начала Stage 3.

### F-010
- origin: realist · R1 · seat2-F-5
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-5** [РЕАЛИЗУЕМОСТЬ, non-blocking, снять до заморозки]
> - Anchor: #VER-002; [F-45].
> - Evidence: [F-45] фиксирует `python3 -m unittest discover` как «17 ошибок импорта». Пакет утверждает `exit 0` из cwd моста без базового прогона. Правка 17 существующих модулей вне allowlist, значит при сохранении ошибок VER-002 недостижим. Не могу проверить, что ошибки были только из-за cwd.
> - Исправление: прогнать baseline VER-002 из cwd моста и записать в evidence. При красном — скорректировать или убрать VER-002.
> - Проверка: EVD «VER-002 baseline = N tests OK» до freeze.

### F-011
- origin: realist · R1 · seat2-F-6
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-6** [РИСКИ, non-blocking]
> - Anchor: #AD-001 (`details.protocol_compatibility`).
> - Evidence: совместимость требует `version==2.1.2` плюс exact-проекцию схемы. Любое обновление бинарника (mtime/size) делает serve недоступным, и мост молча деградирует на `run` до нового Architect-дельта. `/health` (неизменный) это не показывает.
> - Исправление: допускать версии по совпадению хэша проекции схемы или allowlist в конфиге, выводить статус транспорта в лог O-EXIT. Изменение `/health` вне контракта — не требовать.
> - Проверка: тест «смена mtime при той же проекции → serve остаётся; при другой → run + явная запись в O-EXIT».

### F-012
- origin: realist · R1 · seat2-F-7
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-7** [КОРРЕКТНОСТЬ, non-blocking]
> - Anchor: #AD-001 (`details.fallback_barrier`), #AD-003 (`details.retry`), #R-BULK-I3.
> - Evidence: при `first_event_timeout` (20 с от `prompt_send_start`) до получения заголовков POST не сказано: это «ServeUnavailable → run fallback» или «явный retry на serve» и считается ли попытка в `_ServeHealth`. Именно эта граница была предметом RW-001.
> - Исправление: добавить в AD-001 таблицу решений «фаза × событие → действие (fallback/retry/fail) × счётчик health».
> - Проверка: VER-005, параметризованный по фазам барьера.

### F-013
- origin: realist · R1 · seat2-F-8
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-8** [КОРРЕКТНОСТЬ/ПОЛНОТА, non-blocking]
> - Anchor: #REQ-004, #REQ-005, #AD-002 (`details.eligibility`, `details.lifecycle`), #CD-001.
> - Evidence: REQ-004/AC-005 остались безусловными («даже при полностью молчащем апстриме»), а AD-002 сужает их до режима с thinking и grace 0.30 с. Для REQ-006/013/016 текст в v2 обновлён, для REQ-004 — нет. Порог «настоящего stall» для heartbeat «Ожидание продолжения» не задан (в тексте «можно»).
> - Исправление: обновить acceptance REQ-004 и зафиксировать числовой порог и обязательность heartbeat после первого токена.
> - Проверка: VER-005-оракулы совпадают с текстом REQ.

### F-014
- origin: realist · R1 · seat2-F-9
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-9** [РЕАЛИЗУЕМОСТЬ, non-blocking]
> - Anchor: #operational_profile (`threads_per_worker_upper_bound`, `FD_worker`), #SLA_p99_s.
> - Evidence: потоки: 6 handlers, но ThreadingHTTPServer держит потоки и для ожидающих (до 6+12=18); `lsof` не учтён. FD считает 12 дренажей, потоки — 6. Худший случай 3×first_token 60 с плюс вспомогательные 51.6 с превышает SLA 180 с (признано в `estimate_status`).
> - Исправление: исправить расчёт потоков и FD (включая ожидающих и `lsof`); сформулировать допустимый p99 для худшего случая как проверяемый критерий.
> - Проверка: пересчёт в HL-ENV-01.

### F-015
- origin: realist · R1 · seat2-F-10
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-10** [СООТВЕТСТВИЕ КОНТЕКСТУ/РИСКИ, non-blocking]
> - Anchor: #AD-001 (`feature_flag_context`), `approval.status=NOT_REQUIRED`, #ASM-003/#ASM-004, `evolution.rollout`.
> - Evidence: дефолт `true` отступает от командного канона (удалённый флаг, дефолт `false`). Основание — только rework-бриф, и подтверждения владельца в `approval` нет. ASM-003/004 «VALIDATED» только ссылкой на бриф. Безопасность выката держится на ручном порядке: файл `disable-serve` должен существовать до синхронизации и рестарта, иначе serve включится на проде до H3/H6.
> - Исправление: зафиксировать в `approval` или в evidence явное решение владельца. Сделать precondition в H0: «файл существует, проверка перед `launchctl kickstart`». Пересмотреть статусы ASM.
> - Проверка: протокол H0 содержит проверку наличия файла как блокирующий шаг.

### F-016
- origin: realist · R1 · seat2-F-11
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r3-majority
- votes: R1 realist=AUTHOR
- dissent: visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-11** [АЛЬТЕРНАТИВЫ/РЕАЛИЗУЕМОСТЬ, non-blocking]
> - Anchor: #AD-001 (`alternatives`: L), `handoff-architect.md` §4 («поэтапная поставка возможна: L затем A1/B/C»).
> - Evidence: RC-2/RC-3 (watchdog, статусы, killpg, баз. тесты, O-EXIT) закрывают инцидент 780–856 с независимо от serve. Пакет сливает их с serve-транспортом в одну поставку внутри одного `server.py`.
> - Исправление: разбить исполнение на стадии: 3a (RC-2/RC-3 плюс исправление базовых тестов и долг VER-004) с независимым VER, затем 3b (serve за флагом). Альтернативу «поэтапно» записать как рассмотренную.
> - Проверка: VER-005 разделён на группы, стадия 3a проходит без FakeServe.

# Консенсус-леджер находок Архитектурного Совета — Cycle 1 (`a1`)

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Раунд:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r1`
- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`sha256=e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02`)
- **PANEL PROOF:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r1/panel-proof.json` (`sha256=0d289c87c1527829aebb117f921ac8f69a2262a84886a6336cc681f50564a5cb`, `verify_panel_proof exit=0`)
- **Голоса судей:** 3/3 `NEEDS WORK` (единогласно Класс A → возврат `Architect` через `panel-rework-summarizer`)
- **Всего находок в батче:** 24 (`F-001` .. `F-024`)

---

## Находки Seat 1 (`skeptic`, `grok-4.7-high`, `xAI`, `cursor-agent`)

### F-001
- **source_seat:** Seat 1 (`grok-4.7-high`, `skeptic`, orig `F1`)
- **status:** AGREED (blocking)
- **criterion:** КОРРЕКТНОСТЬ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`, `#R-BULK-I1`, `#high_load_envelope`)
- **rule:** `R-BULK-I1` (`T_crit_aux` по всем попыткам ≤ 0.30×SLA); `REQ-001`
- **evidence:** «create+event-subscription+prompt-send<=.2s»; «53.7s<=.30×180=54s»; «Начиная с попытки отправки prompt … silent fallback запрещён». F-19: `execution.started` 233 мс при ready около 109 мс.
- **expected_fix:** `create+subscribe >= 2.0 с`; `prompt POST` по остатку first-event; `run` fallback только до заголовков ответа `POST`; `R-BULK-I1` пересчитан и записан.
- **acceptance:** `VER-005` FakeClock, медленный create без заголовков POST → один `run`, `Popen<=3`; с заголовками POST → `run` нет; статическая сумма `<=54` с.
- **priority:** blocking

### F-002
- **source_seat:** Seat 1 (`grok-4.7-high`, `skeptic`, orig `F2`)
- **status:** AGREED (blocking)
- **criterion:** РИСКИ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`, `#RISK-001`, `#EVD-050`)
- **rule:** `REQ-012`; `THREAT-002`
- **evidence:** «Основная безопасная конфигурация — scoped … permission={"*":"deny"}»; «HTTP 401/403 … fail-closed, никакого ослабления policy через run»; `EVD-050`: `deny` может вызвать Zen 403.
- **expected_fix:** по умолчанию `ask` и немедленный программный `reject` (никогда `allow`); `deny` как выбираемая env-политика для проверки на H6; без ослабления в `allow`.
- **acceptance:** `VER-005`, запрос permission всегда получает `reject`; `deny` и `ask_reject` оба покрыты в `FakeServe`; при принятии prompt 403 остаётся fail-closed без silent fallback на `run`.
- **priority:** blocking

### F-003
- **source_seat:** Seat 1 (`grok-4.7-high`, `skeptic`, orig `F3`)
- **status:** AGREED (blocking)
- **criterion:** ПОЛНОТА
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`, `#THREAT-001`)
- **rule:** `THREAT-001`; отсутствие границы доверия на loopback
- **evidence:** «--port, ephemeral»; «если API не даёт port=0 … reserve-bind(0), release, spawn с ограниченным retry race».
- **expected_fix:** порт выбирает родитель через `bind 127.0.0.1:0` / `getsockname`; `spawn` с явным `--port`; Basic Auth и prompt отправляются только после проверки принадлежности слушателя порту дочернему процессу/PGID.
- **acceptance:** `VER-005`, чужой PID на том же порту → ноль байт пароля и промпта с секретами утекает в чужой процесс, попытка завершается ошибкой внутри ready-бюджета.
- **priority:** blocking

### F-004
- **source_seat:** Seat 1 (`grok-4.7-high`, `skeptic`, orig `F4`)
- **status:** AGREED (blocking)
- **criterion:** ПОЛНОТА
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`)
- **rule:** `REQ-001`, `REQ-010`, `REQ-014`; проверяемость `VER-005`
- **evidence:** «Конкретные field paths подтверждает Coder по v2 schema в FakeServe contract test». F-19/F-22 фиксируют имена событий и эндпоинты, не пути полей.
- **expected_fix:** в `AD-001.event_contract` вложен замороженный минимальный JSON-фикстур `opencode serve` v2.1.2 для reasoning delta, text delta, `step.ended` tokens (`input`/`output`/`cached`/`reasoning`), tool/permission lifecycle и `execution.failed`.
- **acceptance:** `VER-005` падает, если адаптер или `FakeServe` расходится с замороженным фикстуром на любом из этих конвертов.
- **priority:** blocking

### F-005
- **source_seat:** Seat 1 (`grok-4.7-high`, `skeptic`, orig `F5`)
- **status:** AGREED (blocking)
- **criterion:** ПОЛНОТА
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#REQ-013`, `#AD-001`, `#RISK-002`)
- **rule:** `REQ-013` MUST; Forbidden Scope (конфиг georouter не трогать); `[F-15]`, `[F-27]`
- **evidence:** statement «Ротация чистых IP на каждый новый запуск»; `AC-018` проверяет `_next_standalone_proxy`. `[F-15]`: loopback мимо прокси. `[F-27]`: `baseURL=http://127.0.0.1:10830/v1`.
- **expected_fix:** уточнить трактовку `REQ-013` и `AD-001` drivers в пакете под фактическую гарантию `AC-018` (сохранение per-spawn ротации прокси-окружения `_next_standalone_proxy`, как у `run`, с честной фиксацией в `RISK-002`, что loopback `georouter` не идёт через `HTTP_PROXY` дочернего процесса).
- **acceptance:** в пакете нет ложного утверждения, что env `serve` сам переключает IP внутри `georouter`; `AC-018` остаётся проверкой последовательности записей пула `_next_standalone_proxy`.
- **priority:** blocking

### F-006
- **source_seat:** Seat 1 (`grok-4.7-high`, `skeptic`, orig `F6`)
- **status:** AGREED (blocking)
- **criterion:** РИСКИ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#high_load_envelope`, `#C-MULT-I1`, `#RISK-003`)
- **rule:** `HL-ENV-01` memory closure; `C-MULT-I1`; устойчивость при 6 параллельных запросах
- **evidence:** «6×192MiB=1152MiB»; `[F-20]`: долгий `serve` RSS 439 МиБ (тогда как короткоживущий `serve` 152 МиБ); «opencode_local_db=10 — design logical-child share … НЕ доказанный sqlite pool»; `[F-28]`: `opencode.db` 2.27 ГБ.
- **expected_fix:** устранить конкуренцию за общую `opencode.db` `2.27 GB` через эфемерный per-spawn `XDG_DATA_HOME` (удаляемый в `finally`) и/или зафиксировать жёсткий rollout-гейт H3 с проверкой фактического RSS одноразового `serve` (`1×parent + M×child <= 0.8×Mem_limit_per_pod`) и отсутствия `database is locked`.
- **acceptance:** в `high_load_envelope`, `C-MULT-I1` и `evolution` зафиксированы изоляция SQLite / rollout-гейт H3 по RSS и блокировкам БД.
- **priority:** blocking

---

## Находки Seat 2 (`realist`, `gemini-4-argon-high`, `Google`, `agy`)

### F-007
- **source_seat:** Seat 2 (`gemini-4-argon-high`, `realist`, orig `1/9`)
- **status:** AGREED (blocking, дублирует корневую причину с `F-002` и `F-018`)
- **criterion:** РЕАЛИЗУЕМОСТЬ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1000` (`#AD-001`, `#RISK-001`, `#Q-002`, `#EVD-050`)
- **rule:** `REQ-012`, `REQ-003` (`AC-004`), `aisdlc-gcge/skills/architecture.md`
- **evidence:** `AD-001:1000` делает `permission={"*":"deny"}` основной конфигурацией без env-переключателя, хотя `EVD-050` (`server.py:224-231`, `[F-08]`) фиксирует Zen `403`, а изменение `_run_env(model_id)` сломает неизменяемый `tests/test_run_env.py`.
- **expected_fix:** сделать основным режимом для `serve` `permission={"*":"ask"}` + немедленный авто-отказ `reject` через `POST /api/session/{id}/permission/{requestID}/reply`, ввести `OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject|deny` (default `ask_reject`), выделить `_serve_env(...)` поверх неизменного `_run_env(model_id)` и покрыть оба режима в `FakeServe`.
- **acceptance:** `tests/test_run_env.py` проходит без правок; оба режима `ask_reject` и `deny` специфицированы и покрыты в `VER-005`.
- **priority:** blocking

### F-008
- **source_seat:** Seat 2 (`gemini-4-argon-high`, `realist`, orig `2/9`)
- **status:** AGREED (blocking, расширяет `F-001`)
- **criterion:** РЕАЛИЗУЕМОСТЬ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:997` (`#AD-001`, `#high_load_envelope`, `#R-BULK-I1`)
- **rule:** `aisdlc-gcge/agents/architecture.md` §3.4 `R-BULK-I1` и реалистичность NFR-бюджетов
- **evidence:** `SERVE_READY_TIMEOUT_S=0.50` (с выгрузкой `281 KB` `/openapi.json`) и `session_setup_budget_s=0.20` меньше одиночного замера `233.06 ms` (`[F-19]`), при промптах `103 KB` (`[F-30]`) и `opencode.db` `2.27 GB` (`[F-28]`); семантика `delivery` у `POST /api/session/{id}/prompt` и передача `model`/`variant` не зафиксированы.
- **expected_fix:** использовать `GET /api/session/active` для readiness; объединить pre-spawn admission (`_StartupGate` + `_SpawnRateLimiter <= 5.0 s`) и поднять `ready_budget_s=3.0 s`, `session_setup_budget_s=2.0 s` (`15 + 3×(5.0 + 3.0 + 2.0 + 1.2) + 3 = 51.6 s <= 54.0 s`); зафиксировать точный wire-контракт `POST /api/session` (`model`/`variant`) и `POST /api/session/{id}/prompt` (`delivery` / параллельное чтение `/api/event`).
- **acceptance:** `R-BULK-I1 <= 54.0 s` при `ready_budget_s >= 2.5 s` и `session_setup_budget_s >= 2.0 s`; wire-контракт `session` и `prompt` полностью определён в `AD-001`.
- **priority:** blocking

### F-009
- **source_seat:** Seat 2 (`gemini-4-argon-high`, `realist`, orig `3/9`)
- **status:** AGREED (blocking)
- **criterion:** КОРРЕКТНОСТЬ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1119` (`#AD-003`, `#REQ-006`, `#verification_acceptance_matrix:2481`)
- **rule:** `REQ-006` (`AC-008`: 20 с до первого события транспорта) и `REQ-016` (`AC-021`: `first_event_ms`)
- **evidence:** `architecture-packet.json:1119` и `:2481` разрешают гасить `first_event` локальным HTTP readiness `serve` (`~109 ms`), из-за чего зависание после `POST /prompt` без единого SSE-события ждёт `60 s` (`first_token_timeout`) вместо `20 s` (`first_event_timeout`).
- **expected_fix:** развести `SERVE_READY_TIMEOUT_S` (до промпта -> `ServeUnavailable`) и часы `first_event` (`FIRST_EVENT_TIMEOUT_S=20.0`), которые на пути `serve` удовлетворяются только первым валидным SSE-событием созданной сессии после отправки промпта (`session.execution.started` / `session.step.started` / `session.reasoning.started`).
- **acceptance:** сценарий `VER-005` «HTTP readiness прошёл и `POST /prompt` принят, но SSE-событий сессии нет» завершается по `first_event_timeout` за `FIRST_EVENT_TIMEOUT_S + 2 s`.
- **priority:** blocking

### F-010
- **source_seat:** Seat 2 (`gemini-4-argon-high`, `realist`, orig `4/9`)
- **status:** AGREED (blocking)
- **criterion:** РЕАЛИЗУЕМОСТЬ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:980` (`#AD-001`, `#REQ-003`, `#REQ-019`, `#evolution`)
- **rule:** `REQ-001`, `REQ-003`, `REQ-019` и выполнимость живой приёмки `H0..H9`
- **evidence:** `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` имеет `default: false`, но неизменяемый `start.sh` читает из `~/.dsh/.env` только 3 ключа API и не пробрасывает флаги в LaunchAgent, поэтому после синхронизации `server.py` на `:9883` (`REQ-019`) `serve` не включится, а kill-switch через `~/.dsh/.env` не сработает.
- **expected_fix:** установить `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` в `default: true` при `OPENCODE_ZEN_BRIDGE_TRANSPORT=auto` (по прецеденту `STEP_RECOVERY=1` и `muse-bridge`: shebang-фильтр для fake-CLI автоматически сохраняет `run` на всех 378 существующих тестах, а `TRANSPORT=run` / `REALTIME_SERVE_ENABLED=0` и опциональный stat-файл kill-switch дают $O(1)$ отключение).
- **acceptance:** после синхронизации `server.py` на `:9883` `serve`-транспорт активен для нативного бинарника `opencode` без ручной правки `start.sh`, все 378 fake-CLI тестов зелёные, документированный kill-switch работает мгновенно.
- **priority:** blocking

### F-011
- **source_seat:** Seat 2 (`gemini-4-argon-high`, `realist`, orig `5/9`)
- **status:** AGREED (blocking)
- **criterion:** КОРРЕКТНОСТЬ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1000` (`#AD-001`)
- **rule:** трассируемость всех ссылок `F-NN` к `analysis/zen-realtime-reasoning/evidence-ledger.md` (`F-01..F-49`)
- **evidence:** `architecture-packet.json:1000` ссылается на несуществующий `F-50` (в реестре 49 фактов `F-01..F-49`).
- **expected_fix:** заменить `F-50` на `EVD-050` (`bridges/opencode-zen-bridge/server.py:224-231`, `[F-08]`).
- **acceptance:** поиск `F-\d+` по `architecture-packet.json` возвращает только идентификаторы `F-01..F-49` (и ссылки на внутренние findings при необходимости помечены иначе).
- **priority:** blocking

### F-012
- **source_seat:** Seat 2 (`gemini-4-argon-high`, `realist`, orig `6/9`)
- **status:** AGREED (blocking, `[pre-existing]`)
- **criterion:** СООТВЕТСТВИЕ КОНТЕКСТУ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1684` (`#high_load_envelope`, `#HL-ENV-01`)
- **rule:** Неснимаемый стоп-код `HL-ENV-01` в `aisdlc-gcge/agents/architecture.md` §3.0 (строки 18–20 таблицы: единицы `MiB`)
- **evidence:** поля `Mem_limit_per_pod`, `Mem_rss_worker_max`, `Mem_shared_max` записаны в сырых байтах (`2147483648`, `268435456`, `1207959552`) вместо предписанных таблицей §3.0 единиц `MiB` (`2048`, `256`, `1152`).
- **expected_fix:** записать `Mem_limit_per_pod: 2048`, `Mem_rss_worker_max: 256`, `Mem_shared_max: 1152` в единицах `MiB` и согласовать `units`, `memory_closure_check` и `HL-ENV-01.substitution`.
- **acceptance:** все 46 полей `required_hl_env_fields` строго соответствуют единицам таблицы §3.0 `aisdlc-gcge/agents/architecture.md`, неравенство `1*256 + 1152 <= 0.80*2048` выполнено в `MiB`.
- **priority:** blocking

### F-013
- **source_seat:** Seat 2 (`gemini-4-argon-high`, `realist`, orig `7/9`)
- **status:** AGREED (blocking)
- **criterion:** ПОЛНОТА
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:886` (`#VER-004`, `#scope`)
- **rule:** `aisdlc-gcge/AGENTS.md` п. 5 (`ruff format --check`, `ruff check`, `basedpyright` обязательны для всех изменяемых файлов)
- **evidence:** `VER-004` проверяет `ruff check` только на `server.py` и `tests/test_realtime_reasoning.py`, пропуская изменяемый `tests/test_step_interruption.py`, и запускает `basedpyright` только на `server.py`.
- **expected_fix:** расширить `VER-004` проверками `ruff format --check`, `ruff check` и `basedpyright` (0 ошибок `severity=="error"`) на все 3 файла из `scope.coder_target_files` (`server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`).
- **acceptance:** команда `VER-004` покрывает все 3 целевых файла форматтером, линтером и тайпчекером и завершается с `exit 0`.
- **priority:** blocking

### F-014
- **source_seat:** Seat 2 (`gemini-4-argon-high`, `realist`, orig `8/9`)
- **status:** CONSENTED (non-blocking, усиливает митигацию `F-006`)
- **criterion:** РИСКИ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:996` (`#AD-001`, `#RISK-003`)
- **rule:** Модификатор режима `architecture` (снижение ресурсной конкуренции при росте нагрузки)
- **evidence:** 6 процессов `opencode serve` и фоновый сервис PID 43288 конкурируют за общую `~/.local/share/opencode/opencode.db` (`2.27 GB`, `[F-28]`).
- **expected_fix:** зафиксировать в `AD-001` / `RISK-003` решение по per-spawn временному `XDG_DATA_HOME` (с удалением в `finally`) при сохранении `OPENCODE_MODELS_PATH`, чтобы исключить `SQLITE_BUSY` на `opencode.db` `2.27 GB`.
- **acceptance:** в `AD-001` и `RISK-003` явно описана изоляция `XDG_DATA_HOME` и очистка временного каталога в `finally`.
- **priority:** non-blocking

### F-015
- **source_seat:** Seat 2 (`gemini-4-argon-high`, `realist`, orig `9/9`)
- **status:** CONSENTED (non-blocking)
- **criterion:** ПОЛНОТА
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1648` (`#materialization`, `#deferred`)
- **rule:** `aisdlc-gcge/AGENTS.md` п. 13 и `aisdlc-gcge/skills/architecture.md` («ADR и proposals»)
- **evidence:** `materialization` пуст, а в `deferred` не указана причина переноса выпуска `docs/adr/0005-*` за пределы текущего скоупа `handoff-architect.md` §10.
- **expected_fix:** добавить в `deferred[]` явную запись об оформлении `docs/adr/0005-zen-serve-realtime-reasoning.md` и обновлении `docs/adr/INDEX.md` отдельной задачей вне замороженного скоупа `handoff-architect.md` §10.
- **acceptance:** в `deferred[]` пакета присутствует явная запись про `ADR-0005` с обоснованием границ скоупа.
- **priority:** non-blocking

---

## Находки Seat 3 (`visionary`, `claude-sonnet-5-5-high`, `Anthropic`, `claude-p`)

### F-016
- **source_seat:** Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `1/9`)
- **status:** AGREED (duplicate of `F-011`)
- **criterion:** КОРРЕКТНОСТЬ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1000` (`#AD-001`)
- **rule:** трассируемость `F-NN` к `evidence-ledger.md`
- **evidence:** `AD-001.details.tool_policy` опирается на несуществующий `F-50` вместо `EVD-050` + `[F-08]`.
- **expected_fix:** заменить `F-50` на `EVD-050` + `[F-08]`.
- **acceptance:** все `F-NN` в пакете присутствуют в `evidence-ledger.md`.
- **priority:** blocking

### F-017
- **source_seat:** Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `2/9`)
- **status:** AGREED (blocking)
- **criterion:** ПОЛНОТА
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-002`)
- **rule:** `REQ-005` (`AC-006`) и `[F-37]` (`latestCompletedParagraphFirstLine`)
- **evidence:** статусные дельты `[мост]` оканчиваются `
`, но если предыдущая модельная дельта `reasoning_content` не оканчивалась `
`, heartbeat/retry-статус приклеится к недописанной строке модели и нарушит отображение и разделение строк.
- **expected_fix:** перед отправкой синтетической статусной дельты `[мост]`, если последний отправленный байт модельного `reasoning_content` не `
`, вставлять ведущий `
` как часть синтетического статуса (`
[мост] ...
`), чтобы модельные байты при фильтрации синтетических чанков оставались побайтно неизменными (`AC-006`).
- **acceptance:** `VER-005` проверяет вставку статусной дельты после модельного чанка без завершающего `
`: строка `[мост]` отделена переводом строки, а конкатенация модельных чанков побайтно равна оригиналу.
- **priority:** blocking

### F-018
- **source_seat:** Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `3/9`)
- **status:** AGREED (duplicate of `F-007`)
- **criterion:** ПОЛНОТА
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1000` (`#AD-001`, `#Q-002`)
- **rule:** `REQ-012`, `[F-08]`
- **evidence:** не определены переменная окружения, дефолт и fail-closed поведение для выбора между `ask_reject` и `deny`.
- **expected_fix:** ввести явный env-селектор политики инструментов `serve` с совместимым с Zen дефолтом `ask_reject` и fail-closed поведением.
- **acceptance:** селектор описан в `AD-001` и проверяется в `FakeServe`.
- **priority:** blocking

### F-019
- **source_seat:** Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `4/9`)
- **status:** AGREED (blocking)
- **criterion:** РИСКИ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`, `#AD-003`, `#R-BULK-I3`)
- **rule:** устойчивость к деградации `serve`-транспорта без блокировки всего моста (`REQ-003`)
- **evidence:** если после апгрейда `opencode` изменится схема событий `serve` или SSE-подписка перестанет присылать события после `POST /prompt`, `first_event_timeout`/`first_token_timeout` за 5 запросов откроет общий `_UpstreamBreaker` моста, хотя legacy `opencode run` остаётся полностью рабочим.
- **expected_fix:** ввести в `AD-001`/`AD-003` отдельный индикатор здоровья `serve`-транспорта (`_ServeHealth` со sticky TTL авто-деградации на `run` для последующих запросов при серии специфичных для `serve` сбоев `first_event_timeout` / `invalid_serve_event`, не открывая общий `_UpstreamBreaker` модели).
- **acceptance:** `VER-005` проверяет, что серия специфичных для `serve` сбоев переводит следующий запрос на `run` по sticky TTL и не открывает общий `_UpstreamBreaker`.
- **priority:** blocking

### F-020
- **source_seat:** Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `5/9`)
- **status:** CONSENTED (non-blocking)
- **criterion:** РИСКИ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-002`, `#risks`)
- **rule:** полнота реестра рисков (`[F-33]`, `[F-38]`, `[F-39]`)
- **evidence:** строки `[мост]` сохраняются в журнале сессии DSH и при смене провайдера в середине чата (например, на `deepseek-account`) могут попасть во входящий `reasoning_content` другого провайдера.
- **expected_fix:** зафиксировать в `risks` принятый остаточный риск межпровайдерского реплея `reasoning_content` при ручном переключении модели в середине сессии DSH и минимизацию длины/частоты статусов `[мост]`.
- **acceptance:** риск и митигация явно отражены в `risks[]` пакета.
- **priority:** non-blocking

### F-021
- **source_seat:** Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `6/9`)
- **status:** CONSENTED (non-blocking, покрывается расширением `VER-004` в `F-013`)
- **criterion:** ПОЛНОТА
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:886` (`#VER-004`)
- **rule:** `aisdlc-gcge/skills/architecture.md` Python overlay (`ruff format --check`)
- **evidence:** `VER-004` не включает `ruff format --check` на изменённых файлах.
- **expected_fix:** включить `ruff format --check` на целевых файлах в `VER-004`.
- **acceptance:** `VER-004` содержит `ruff format --check`.
- **priority:** non-blocking

### F-022
- **source_seat:** Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `7/9`)
- **status:** CONSENTED (non-blocking)
- **criterion:** РЕАЛИЗУЕМОСТЬ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:886` (`#VER-004`, `#AD-001`)
- **rule:** соблюдение правил типизации `python-standards.md` без раздувания `Any`
- **evidence:** новый код `serve`-клиента и парсера JSON в `server.py` должен использовать `TypedDict` / `object` с явным сужением типов (`isinstance`), чтобы не увеличивать счётчики `reportAny`/`reportExplicitAny` `basedpyright`.
- **expected_fix:** зафиксировать в `AD-001` / `VER-004` требование типизировать новый код через `object` + type-narrowing / `TypedDict` без роста `reportAny`/`reportExplicitAny`.
- **acceptance:** `VER-004` проверяет невозрастание baseline предупреждений `reportAny`/`reportExplicitAny` в `server.py`.
- **priority:** non-blocking

### F-023
- **source_seat:** Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `8/9`)
- **status:** CONSENTED (non-blocking)
- **criterion:** СООТВЕТСТВИЕ КОНТЕКСТУ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#evolution`, `#AD-001`)
- **rule:** быстрый операционный kill-switch без рестарта сервиса
- **evidence:** env-флаг требует перезапуска процесса моста для переключения на живом `:9883`; `stat()` легковесного файла-переключателя (например, `~/.dsh/bridges/opencode-zen-bridge/disable-serve` или env-пути) даёт мгновенный kill-switch без рестарта LaunchAgent.
- **expected_fix:** предусмотреть опциональный файл-флаг отключения `serve` (`OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE`, проверка `Path.exists()` на входе запроса за $O(1)$) в дополнение к env-переменной, чтобы в проде `:9883` можно было мгновенно выключить `serve` на `H9` без рестарта сервиса.
- **acceptance:** в `AD-001.details.configuration` и `evolution.rollback` описан мгновенный kill-switch без рестарта и его проверка в `VER-005`.
- **priority:** non-blocking

### F-024
- **source_seat:** Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `9/9`)
- **status:** CONSENTED (non-blocking, закрывается перебалансировкой `R-BULK-I1` в `F-008`)
- **criterion:** РЕАЛИЗУЕМОСТЬ
- **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#R-BULK-I1`)
- **rule:** устойчивость запаса `R-BULK-I1`
- **evidence:** запас `53.7` против `54.0` с составляет всего `0.3` с.
- **expected_fix:** перебалансировать подбюджеты `R-BULK-I1` (единый pre-spawn admission `<= 5.0` с + реалистичные `ready=3.0` с и `session_setup=2.0` с → сумма `51.6 <= 54.0` с, запас `2.4` с).
- **acceptance:** сумма `R-BULK-I1` записана с явной формулой и запасом `>= 2.0` с.
- **priority:** non-blocking

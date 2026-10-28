# Протокол дебатов Архитектурного Совета — Cycle 1 (`a5`: `R1` `r10` → `D1` `r14`)

- **Артефакт (v5):** `architecture/architecture-packet.json` (`sha256=15ea67e3215ceea9e84b9d79853677f4be86b959e87a21f24830d0c895f62657`)
- **R1 (`panel/arch/r10`):** `panel-proof.json` `sha256=bb81268bdfa8ff2e30f08cdf814f56573d799b191f2d6ed319f11b76fb8a4f0f` (`exit=0`) — `2/3 PASS` + `1/3 NEEDS WORK` (`F-001..F-004` от `gemini-4-argon-high`).
- **D1 (`panel/arch/r14`):** `panel-proof.json` `sha256=90d0582405eb709f1ae1808072c4cc4d13adbe405c32bde7f87de8fb4676e97f` (`exit=0`) — единогласный `3/3 NEEDS WORK` (`POSITIONS: 4/4` у всех трёх судей, `0` новых находок, сходимость в `D1`).

## D1 — Seat 1 (`skeptic`, `grok-4.7-high`, `xAI`)
```text
PANEL-NONCE: 7c889f8131db8fd9
ARTIFACT-SHA256: 15ea67e3215ceea9e84b9d79853677f4be86b959e87a21f24830d0c895f62657
Канон прочитан: AGENTS.md, 430 строк. В корне репозитория моста `AGENTS.md`, `.agents/AGENTS.md` и `CLAUDE.md` нет.

NEW: `python3 -I` с импортом `bridges/opencode-zen-bridge/server.py` дал `ru_maxrss` 25.66 МиБ; тот же интерпретатор только со stdlib (`os/json/time/signal/subprocess/pathlib`) — 17.86 МиБ. `rank_slots` в `select_round_seats.py:235-237` сортирует по SHA-256(`seed_hex#slot`).
ARG: R1 skeptic, F-001: «фактический RSS процесса 27 504 KiB = 26.86 MiB» и «156.8 + 26.86 + 8.0 = 191.66 MiB».

AMEND F-001 — priority=blocking; locations=architecture-packet.json:1613, architecture-packet.json:2509, architecture-packet.json:3156, architecture-packet.json:3429, architecture-packet.json:3468, architecture-packet.json:1589, bridges/opencode-zen-bridge/server.py:163; fix=Связка с F-002: перехват `--serve-helper` до `sqlite3`/`http.server`/`zen_catalog` и до `reload_catalog()` на server.py:163. Замер EVD для этой команды обязателен. Цифру 12.0 МиБ и цель 12–14 МиБ убрать: пол импорта уже 25.66 МиБ, голый stdlib-процесс уже 17.86 МиБ. `helper_estimate` во всех таблицах равен этому замеру плюс запас на код Stage3. Потолок слота 192 МиБ оставить только если `156.8 + helper_estimate + 8` имеет запас ≥12 МиБ; иначе поднять `per_slot_ceiling` и `Mem_shared_max=6*потолок` так, чтобы `6*потолок+256 ≤ 1638.4`, не трогая число слотов 6/12 и `Mem_limit_per_pod` 2048. Синхронно править VER-005, AD-001.resource_accounting, QA-009, RISK-003, H3 `fixed192MiB` и `estimate_status` — причина: NEW замер 25.66/17.86 МиБ против `helper_estimate: 12.0` на architecture-packet.json:1613 и :3468 и формулы `156.8+helper~12+probe~8=176.8` на :3156

AGREE F-002 rev=1 — проверил: architecture-packet.json:1589 и :1756 — `helper_proc=Popen([sys.executable, "-I", str(Path(__file__).resolve()), "--serve-helper", attempt_id, str(port), ...], env=serve_env)`, дальше `Popen([OPENCODE_BIN, "serve", ...], env=serve_env)`; allowlist `serve_env_sanitization` не содержит `OPENCODE_BIN` и запрещает широкий `OPENCODE_*`; bridges/opencode-zen-bridge/server.py:52 читает `OPENCODE_BIN` из окружения, иначе `~/.opencode/bin/opencode` (этот прогон напечатал именно этот путь); server.py:66-67 и :163 (`sys.path.insert`, `import zen_catalog as zc`, `reload_catalog()`) выполняются до любого `if __name__`; architecture-packet.json#EVD-077 разбирает только `attempt_id, port_text = args[:2]`

AGREE F-003 rev=1 — проверил: architecture-packet.json:1498 — `ruff format --no-cache --range=...` по копии в `/tmp` без `--config`. Отдельный файл во вложенном каталоге подхватил родительский `/tmp/.../ruff.toml` и упал на разборе конфига (`unknown field line-length`), то есть Ruff идёт от каталога файла вверх, а не от `cwd` репозитория

AGREE F-004 rev=1 — проверил: architecture-packet.json:7 `"cycle": 5`, :12 `plans/architect-05.json`, :19-21 allowlist всё ещё `plans/architect-04.before.json` и `plans/architect-04.json`

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001..004 и FU-001..006 в тексте v5 закрыты, но FU-004 оставил два противоречия внутри выбранного дерева. F-001: `helper_estimate` 12.0 МиБ на architecture-packet.json:1613, :2509 и :3468 относится к прежнему тонкому интерпретатору, а точка входа — полный `server.py`. Замер этого хода: импорт модуля 25.66 МиБ, stdlib-пол 17.86 МиБ; `156.8+25.66+8=190.46` при жёстком слоте 192 МиБ на :3156. F-002: хвост argv записан как `...` (architecture-packet.json:1589), `serve_env` вырезает `OPENCODE_BIN`, а дочерний процесс заново вычисляет server.py:52 и до диспетчера вызывает `reload_catalog()` (server.py:163). Подмена `server.OPENCODE_BIN` в родителе до хелпера не доходит.
   СОВЕТЫ (при FAIL):
   - Перехват `--serve-helper` поставить до тяжёлых импортов и до `reload_catalog()`; в этом режиме не открывать `logs/bridge.log` и `state/zen-catalog.json` репозитория.
   - Заменить `...` на замкнутый argv: после `attempt_id` и `port` идут путь `OPENCODE_BIN`, каталог lease и идентичность родителя. Хелпер запускает `serve` по этому пути и не кладёт `OPENCODE_BIN` в `serve_env`.
   - Пересчитать `helper_estimate` от нового замера (пол не ниже 17.86 МиБ даже у раннего выхода). Потолок 192 МиБ сохранить только при запасе ≥12 МиБ на слот; иначе поднять слот внутри `6*потолок+256 ≤ 1638.4` во всех таблицах памяти и в тексте H3.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=REQ-001..020 и AC-001..026 по-прежнему сидят на VER-001..005 и H0..H9. Дыра — межпроцессный контракт, добавленный в v5. EVD-077 принимает два аргумента, а spawn/THREAT-001/crash_recovery оставляют хвост `...` и не задают ветку «не исполнять серверную инициализацию модуля». Очищенный `serve_env` не несёт ни путь бинарника, ни каталог lease.
   СОВЕТЫ (при FAIL):
   - Одна сигнатура `_run_serve_helper_cli(args)` во всех секциях: AD-001.spawn, crash_recovery.creation, startup_reaper, VER-004, VER-005, THREAT-001, EVD-077.
   - Явное правило: режим `--serve-helper` не вызывает `reload_catalog()`, не создаёт `_DEFAULT_RESILIENCE` и не пишет в пути репозитория.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Кодер по буквальному пакету не собирает clean-room VER-005. Песочница без домашнего каталога и с `monkeypatch` `OPENCODE_BIN` на FakeServe передаёт хелперу `serve_env` без этой переменной; хелпер берёт `~/.opencode/bin/opencode` (server.py:52). Одновременно загрузка всего модуля до диспетчера даёт ~26 МиБ ещё до кода Stage3, и H3 с правилом «превышение 192 МиБ/слот — отказ, не waiver» (architecture-packet.json:3156) останавливает включение. F-003 не блокирует сам по себе: write-mode `ruff format` копии в `/tmp` без `--config` берёт конфиг от каталога файла.
   СОВЕТЫ (при FAIL):
   - Прокинуть разрешённый родителем путь бинарника позиционным аргументом и проверять цепочку parent → helper → fake при пустом `HOME`.
   - Ранний выход хелпера плюс новый EVD RSS; потолок слота править только если замер раннего выхода не оставляет ≥12 МиБ под 192.
   - Во все вызовы `ruff format` и `ruff check` внутри VER-004 добавить `--config` на корневой `ruff.toml`.

4. РИСКИ: VERDICT=FAIL
   WHY=На шести слотах связка уже в простое: serve 156.8 МиБ (EVD-071) + хелпер 25.66 МиБ + probe 8 МиБ = 190.46 МиБ при потолке 192 и запрете waiver на H3. Промпт ~103 КБ и код Stage3 этот остаток съедают; выкат остаётся на `run`, и RC-1 ([F-17], [F-18]) не снимается. Пачка ретраев до трёх спавнов на запрос каждый раз импортирует модуль и вызывает `reload_catalog()` внутри ready 3.0 с. Контур секретов и чужого listener (THREAT-001), cancel формы до схемы (THREAT-002) и `:memory:` (EVD-071) этим не отменяются. При росте выше шести слотов срабатывает bulkhead 503; общий egress Zen через loopback georouter по-прежнему не меняет IP вместе с proxy env ([F-15], [F-27]).
   СОВЕТЫ (при FAIL):
   - Убрать серверный рантайм из хелпера ранним `--serve-helper` и заново снять RSS пары helper+serve до Stage3.
   - Если ранний выход не умещается в 192 МиБ с запасом ≥12 МиБ, поднять слотовый потолок внутри 1638.4 МиБ во всех формулах, не поднимая 6 слотов и не объявляя H3 пройденным.
   - Подтвердить, что `reload_catalog()` и пути логов репозитория в процессе хелпера не вызываются.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=AD-001 сравнивает больше двух вариантов с причиной выбора. L (watchdog и статус на `run`) закрывает RC-2/RC-3 и не даёт дельт ([F-17], [F-18]). A2 (общий демон) делит один failure domain и один env; ротация egress не доказана ([F-15], [F-27], [F-20]). B (прямой HTTP к Zen) упёрся в 429 ([F-24], [F-25]). `serve --stdio` оставлен внутренним IPC `run` (EVD-078, [F-30]): публичной схемы для внешнего клиента нет, выбран HTTP+SSE по [F-19]..[F-22]. Пустая `XDG_DATA_HOME` и общая SQLite 2.27 ГБ отвергнуты. Дефекты F-001 и F-002 сидят внутри уже выбранного C/A1. При шести параллельных запросах ломается запас 192 МиБ/слот и окно ready 3 с из-за полного импорта хелпера; общий дневной лимит Zen на одном egress IP при этом не разводится proxy env.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=SEED=`be646343`, `seed_hex=be6463432c21e491a5ae52e8ec324fd62dff956eae5a419301060548791628f2` совпадает с `panel/arch/r14/manifest.json`; `ranked_order` по `rank_slots(seed_hex#slot)` = `grok-4.7-high`, `gemini-4-argon-high`, `claude-sonnet-5-5-high`, `gpt-6.1-sol-high`, `muse-wonder-full-1.0` — совпадает. Пакет держит три `coder_target_files`, побайтовые SHA `_run_env` / `_stream_google_sse` / `_execute_google_once`, публичный контракт `:9883` и Google-маршрут, `default=false` и H7 только после H3/H6. F-004 — гигиена allowlist цикла 4 при `cycle` 5; продуктовые границы из-за неё не сдвигаются. Stage3 и H0..H9 остаются NOT_RUN.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
POSITIONS: 4/4
ANSWERS: 0/0
```

## D1 — Seat 2 (`visionary`, `claude-sonnet-5-5-high`, `Anthropic`)
```text
PANEL-NONCE: 9c60709a5b7c477d
ARTIFACT-SHA256: 15ea67e3215ceea9e84b9d79853677f4be86b959e87a21f24830d0c895f62657
Подтверждаю: общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до `<!-- КАНОН-КОНЕЦ -->`; проектные файлы правил рабочей папки отсутствуют, оценка выполнена по приложенным артефактам брифа.
AGREE F-001 rev=1 — проверил: [architecture-packet.json](/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:3468) — `helper_estimate: 12.0` при `per_slot_ceiling: 192`, а RECHECK F-001 даёт фактический RSS импорта полного `server.py` `26.89 MiB`; стратегический выбор A1 при этом сохраняется, но запас слота `156.8+26.89+8.0=191.69 MiB` почти исчерпан ещё до нагрузки и кода Stage 3
AGREE F-002 rev=1 — проверил: [architecture-packet.json](/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1756) — вызов `--serve-helper` записан с буквальным `...`, скелет [architecture-packet.json#EVD-077](/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1313) разбирает только `attempt_id, port_text`, а `serve_env_sanitization` вырезает `OPENCODE_BIN`; RECHECK F-002 подтверждает безусловный `reload_catalog()` на строке 163 и пересчёт `OPENCODE_BIN` в дочернем процессе
AGREE F-003 rev=1 — проверил: [architecture-packet.json#VER-004](/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1498) — write-mode `ruff format --range` по копии в `/tmp` выполняется без явного `--config`, что делает гейт зависимым от пользовательского конфига хоста
AGREE F-004 rev=1 — проверил: [architecture-packet.json](/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:19) — при `cycle: 5` и `role_plan=plans/architect-05.json` в `architect_write_allowlist` остались пути `architect-04*.json`

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Смена позиции R1 PASS обоснована ARG: skeptic R1 «оценка helper_estimate = 12.0 MiB не обновлена после отказа от python3 -I -c в пользу загрузки всего server.py (~26.86 MiB фактического RSS)» и NEW: RECHECK F-001 `26.89 MiB`, RECHECK F-002 строки 52, 163 `server.py`. Стратегическое ядро C/A1 по-прежнему меняет игру и устраняет RC-1 настоящими дельтами [F-19], но арифметика HL-ENV и межпроцессный контракт helper в v5 внутренне противоречивы: F-001, F-002.
   СОВЕТЫ (при FAIL): 1) Пересчитать `helper_estimate` по замеру реального `--serve-helper` или вынести ранний перехват флага до тяжёлых импортов и `reload_catalog()`; синхронно исправить все таблицы памяти, QA-009, RISK-003 и H3. 2) Заменить `...` в argv helper на замкнутую типизированную схему с явной передачей разрешённого родителем `opencode_bin`, lease/state путей и идентичности родителя. 3) Запретить серверную инициализацию `reload_catalog()`, `_DEFAULT_RESILIENCE` и доступ к боевым `LOG_PATH`/`CATALOG_STATE_PATH` в режиме `--serve-helper`. 4) Добавить воспроизводимые EVD-замеры RSS helper и clean-room тест цепочки parent→helper→FakeServe в VER-005.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=Покрытие REQ-001..REQ-020 и AC-001..AC-026 полное, но новый внутренний интерфейс FU-004 неполон: состав аргументов после `attempt_id, port` не заморожен, передача `OPENCODE_BIN`/FakeServe и изоляция верхнеуровневых побочных эффектов не определены — F-002. Для долгосрочной эволюции канонический адаптер `(etype,payload)` достаточен, однако coder не должен додумывать протокол helper.
   СОВЕТЫ (при FAIL): 1) Зафиксировать точную сигнатуру `_run_serve_helper_cli(args: list[str]) -> int` без многоточий во всех секциях AD-001, crash_recovery, THREAT-001, VER-004 и VER-005. 2) Описать валидацию каждого позиционного аргумента и поведение при пустом/неисполняемом `opencode_bin`. 3) Явно задать, что helper не использует модульную константу `OPENCODE_BIN` и не добавляет её в `serve_env` дочернего serve. 4) Обновить allowlist цикла по F-004.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=При буквальной реализации v5 clean-room VER-005 с подменой `server.OPENCODE_BIN` на FakeServe [F-43] потеряет переопределение в helper, а бюджет `192 MiB/слот` на H3 окажется без запаса уже в простое — F-001, F-002; дополнительно VER-004 негерметичен по конфигу Ruff — F-003. Это локальный дефект выбранной реализации helper, а не опровержение масштабируемого ядра ephemeral serve.
   СОВЕТЫ (при FAIL): 1) Передавать `opencode_bin` явным argv и доказать цепочку с пустым временным HOME без `~/.opencode/bin/opencode`. 2) Обеспечить ранний выход helper до тяжёлой инициализации либо поднять `per_slot_ceiling` в пределах станционного конверта `1638.4 MiB` с запасом не менее 12–15 MiB. 3) Добавить `--config <root>/ruff.toml` во все вызовы Ruff в VER-004 и проверку идемпотентности временной копии. 4) Повторно прогнать полный VER-004 на изолированной копии и записать argv, cwd, exit code и `dict(counts)`.
4. РИСКИ: VERDICT=FAIL
   WHY=Усиленный критерий режима architecture: при росте до 6 параллельных слотов и промптов 103 КБ именно память связки serve+helper станет первым пределом масштаба; заниженная оценка helper скрывает риск детерминированного провала H3 без права waiver и навсегда оставляет продукт на буферизующем `run` — F-001. Безопасность listener, permission/form и секретов закрыта, но эксплуатационный риск выката не закрыт.
   СОВЕТЫ (при FAIL): 1) До Stage 3 приложить EVD с фактическим RSS helper+serve в простое и под репрезентативной нагрузкой. 2) Перебалансировать `Mem_shared_max`, `per_slot_ceiling` и H3 внутри `1638.4 MiB` без поднятия слотов, waiters и cap3. 3) Устранить повторный дисковый I/O `reload_catalog()` в каждом helper при шторме ретраев. 4) Сохранить правило: превышение H3 запрещает H7, а не ослабляет гейт.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Стратегически выбор C/A1 по-прежнему опережает альтернативы: L не устраняет RC-1 [F-17][F-18], A2 объединяет failure domain и env, B не подтверждён из-за 429 [F-24][F-25], `--stdio` не имеет публичной внешней схемы против проверенного HTTP/SSE [F-19]..[F-22]. Находки F-001/F-002 касаются способа запуска helper внутри выбранного A1 и не делают ни одну отвергнутую альтернативу лучше; каноническая граница сохраняет будущую заменяемость транспорта.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Пакет сохраняет публичный контракт :9883, Google-маршрут, ровно три coder_target_files, default=false и включение только H7 после H3/H6; чужие задачи и мосты не затрагиваются. F-004 — только неблокирующая неактуальность метаданных allowlist и не меняет продуктовых границ.
ОБЩИЙ ВЕРДИКТ: NEEDS WORK
POSITIONS: 4/4
ANSWERS: 0/0
```

## D1 — Seat 3 (`realist`, `muse-wonder-full-1.0`, `Muse`)
```text
PANEL-NONCE: 15525270f75e8108
ARTIFACT-SHA256: 15ea67e3215ceea9e84b9d79853677f4be86b959e87a21f24830d0c895f62657

В R1 я поставил PASS без этих проверок: смотрел только, что `zen_catalog` импортируется под `-I`. Теперь перепроверил сам, ниже результаты.

AMEND F-001 — priority=non-blocking; locations=architecture-packet.json#EVD-077, architecture-packet.json#VER-005, architecture-packet.json#AD-001, architecture-packet.json#H3_rollout_gate, architecture-packet.json#QA-009, architecture-packet.json#RISK-003; fix=пересчитать `helper_estimate` по реальному замеру (~27 MiB) во всех местах пакета, либо вынести перехват `--serve-helper` до тяжёлых импортов и подтвердить замер новым EVD — причина: факт верный, но он не ломает жёсткий гейт. Мой замер: `python3 -I` с импортом `server.py` даёт 27.08 MiB (`ru_maxrss`), голый stdlib — 16.66 MiB. Оценка 12.0 MiB занижена. При этом 156.8+27.1+8.0≈191.9 всё ещё ≤192 MiB на слот. Блокирующий критерий H3 — сумма RSS ≤1638.4 MiB, а по дизайну это 6*192+256=1408 MiB, запас есть. Это неточная оценка в документе, которую Coder исправит без смены архитектуры. Запас на слот при этом уходит в ~0.1 MiB.

AGREE F-002 rev=1 — проверил: `server.py:52` (`OPENCODE_BIN = os.environ.get("OPENCODE_BIN", ~/.opencode/bin/opencode)`), `server.py:54-55` (`LOG_PATH`/`WORKSPACE` от каталога скрипта), `server.py:66-67` и безусловный `reload_catalog()` на `server.py:163`; `tests/test_step_interruption.py:160` подменяет атрибут модуля `server.OPENCODE_BIN = str(fake)`, а не окружение. Helper запускается как отдельный процесс `python -I server.py` с `env=serve_env`. Белый список `serve_env` (AD-001.details.serve_env_sanitization) не содержит `OPENCODE_BIN` и `OPENCODE_ZEN_BRIDGE_*`, то есть переопределения тестов и FakeServe до helper не доходят. Внутри helper `Popen([OPENCODE_BIN, ...])` берёт путь по умолчанию. Хвост argv `...` остаётся неопределённым, а скелет в EVD-077 разбирает только `args[:2]`. В clean-room (`QA-008`) такого бинарника нет, так что VER-005 не соберётся без допущений Coder. Побочные эффекты верхнего уровня (`reload_catalog`, привязка путей) тоже исполняются в helper. Это блокирует: нужен замкнутый позиционный контракт argv (разрешённый `opencode_bin` и прочее, что родитель передаёт явно) и режим `--serve-helper` без серверной инициализации.

AGREE F-003 rev=1 — проверил: `VER-004.command` форматирует копию в `/tmp/zen-arch5-probe-format-*/server.py` без `--config`. Ruff ищет конфиг от каталога файла, то есть вне репозитория `ruff.toml` не находится. Non-blocking: проверка может дать расхождение на хосте с пользовательским конфигом.

AGREE F-004 rev=1 — проверил: `cycle=5` и `role_plan=plans/architect-05.json`, а `scope.architect_write_allowlist` всё ещё содержит `plans/architect-04*.json`. Это неактуальные метаданные, не влияющие на продукт. Non-blocking.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Контракт запуска helper (`-I server.py --serve-helper`) при очищенном `serve_env` теряет путь к бинарнику serve и переопределения FakeServe (F-002). Остальное (RW-001..004, FU-001..006) закрыто проверяемым текстом пакета.
   СОВЕТЫ: зафиксировать позиционный argv helper и передавать `opencode_bin` явно (F-002); не вызывать `reload_catalog()` и серверную инициализацию в режиме `--serve-helper` (F-002); пересчитать `helper_estimate` (F-001).

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Спецификация `--serve-helper` неполна: хвост `...`, скелет в EVD-077 разбирает два аргумента, не описана передача `opencode_bin` и параметров lease (F-002). Покрытие REQ и AC полное.
   СОВЕТЫ: замкнутая схема argv единообразно в AD-001.spawn, crash_recovery, VER-004, VER-005 и THREAT-001 (F-002).

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Coder не может выполнить VER-005 в clean-room без домысливания протокола передачи бинарника (F-002). Бюджет памяти реалистично укладывается в 1638.4 MiB; на слот остаётся ~0.1 MiB запаса против ожидавшихся 15 (F-001, non-blocking).
   СОВЕТЫ: см. F-002; для F-001 пересчитать оценки или перенести dispatcher выше тяжёлых импортов и сделать замер EVD; добавить `--config ruff.toml` в VER-004 (F-003).

4. РИСКИ: VERDICT=PASS
   WHY=Риски и угрозы закрыты митигациями (listener proof, ask_reject, `_ServeHealth`, lease и reaper). Занижение оценки памяти не меняет рисковую картину: гейт H3 по сумме RSS остаётся и блокирует включение (F-001, non-blocking).

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Рассмотрено больше двух вариантов (L, A1/C, A2, B, `--port 0`, `--stdio`, пустой XDG, общая БД) с причинами выбора на основе [F-17]..[F-28], [F-24], [F-25], EVD-071 и EVD-078.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Периметр три файла Coder, замороженные `_run_env`, Google-срезы и публичный контракт :9883 соблюдены, `contract_deltas` обоснованы REQ-004..009 и REQ-016. Устаревшая запись в `scope.architect_write_allowlist` — гигиена метаданных (F-004, non-blocking).

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
POSITIONS: 4/4
ANSWERS: 0/0
```

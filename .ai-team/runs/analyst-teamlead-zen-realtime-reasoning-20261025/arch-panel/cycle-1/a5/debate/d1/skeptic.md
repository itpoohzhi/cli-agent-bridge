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

Skill: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md

Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

Ты — внешний исполнитель роли **Coder** (`muse-wonder-1.0`, effort `high`) в изолированном клоне проекта `cli-agent-bridge`.

## Уже известно
- `repo_root`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning`
- `branch`: `feature/zen-realtime-reasoning` (от `origin/dev` `7eda27f9d82732bab726a420e31ea2adc15c2c39`)
- `run_dir`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025`
- `target_files` (ЕДИНСТВЕННЫЕ 3 продуктовых и тестовых пути для модификации/создания по `coder_target_files` утверждённого `architecture-packet.json`):
  1. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py`
  2. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py` (новый файл тестов)
  3. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_step_interruption.py`
  (НЕ менять `tests/test_zen_bridge.py`, `tests/test_catalog_mode.py`, `tests/test_run_env.py`, `tests/test_google_direct.py`, `zen_catalog.py`, `start.sh` и НЕ создавать `dynamic_config.json` в git-репозитории!)
- `prior_findings` (прочитай точечно только перечисленные входы, повторный поиск по репозиторию не нужен):
  - Утверждённый пакет архитектуры (`v6`, `APPROVED`, прошёл `ARCH_GATE_PASS` и `ARCH_PANEL_PASS`): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json`
  - Брифы доработки архитектурного совета:
  - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief-arch-a1.json`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief-arch-a2.json`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief-arch-a3.json`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief-arch-a4.json`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief-arch-a5.json`
  - Замороженная поверхность верификации: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-surface.json`
  - Аналитический пакет и требования `REQ-001..REQ-020` / `AC-001..AC-026` / `HL-ENV/v1`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/analysis/zen-realtime-reasoning/handoff-architect.md`
  - База фактов `[F-01]..[F-49]`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/analysis/zen-realtime-reasoning/evidence-ledger.md`
  - Матрица тестов `QA-001..QA-047` и `VER-001..VER-007`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/analysis/zen-realtime-reasoning/handoff-qa.md`
  - Существующий тест каталога (ТОЛЬКО для чтения, чтобы не сломать `server.CATALOG_SOURCE` и `ast.parse(..., feature_version=(3, 9))` из `test_zen_catalog.py`): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_catalog_mode.py`, `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_zen_catalog.py`
  - Эталон serve-транспорта в соседнем мосту (ТОЛЬКО для чтения при необходимости, менять запрещено): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/muse-bridge/server.py`
  - Профильные стандарты команды:
    - `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md`
    - `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/code.md`
    - `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/python-standards.md`
    - `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/testing.md`
    - `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/security.md`
    - `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/error-handling.md`
    - `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/logging.md`
    - `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/scope-and-contracts.md`

Входы даны выше; на диск за ними не ходи мимо указанных путей; стартовый корень поиска ∈ {$HOME, /Users/aazhiry1, /} запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни ASK.
Входы: прочти ОДНИМ сообщением все необходимые файлы выше параллельными вызовами Read, не по одному и не волнами.

## ПРАВИЛА ПАРАЛЛЕЛИЗМА
1. ПАРАЛЛЕЛЬНАЯ РАБОТА С ФАЙЛАМИ (строго): все независимые операции — Read/Grep/Glob/ls/web_fetch, Edit/Write РАЗНЫХ файлов, cp/diff/wc/проверки — одним сообщением.
   Перед ходом составь полный список файлов, правок и проверок, известных из задачи/брифа, и выполни ОДНИМ батчем.
2. Диагностику склеивай в одну составную команду (`a; echo ===; b`), если каждая <10 с.
3. Длинное (сборки, тесты, установки, docker, git fetch/push, сеть без -m, запуск моделей) — в фон; пока идёт, делай следующую независимую работу.
4. Два писателя в один файл запрещены.
5. Прочитал — не перечитывай: вывод инструмента остаётся в истории.
6. В отчёте перечисли, что шло фоном и что параллельно.

## Жёсткие запреты (Forbidden Scope) и критические технические страховки
1. НЕ менять никакие файлы вне 3 разрешённых путей (`bridges/opencode-zen-bridge/server.py`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py`) и разрешённых артефактов роли Coder в `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-01*.json`, `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-01.json`, `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json`.
2. НЕ трогать `~/.dsh/bridges/...`, `start.sh`, `zen_catalog.py`, `tests/test_catalog_mode.py`, LaunchAgent, общую `opencode.db`, `~/.config/opencode/`, `bridges/muse-bridge/`, `tests/test_run_env.py`, `tests/test_google_direct.py` и прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`).
3. **КРИТИЧЕСКИЙ ЗАПРЕТ НА FULL-FILE `ruff format server.py` и точный синтаксис `--range` в `ruff==0.17.2`:**
   - Полный `ruff format server.py` переформатирует 3216 строк legacy-кода, мутирует `def _run_env` (нарушая инвариант `sha256 == 1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`) и мутирует замороженные `_stream_google_sse` (`5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3`) / `_execute_google_once` (`88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6`)!
   - В `ruff==0.17.2` запись `--range START:END` трактует `END` как номер столбца без конечной строки и форматирует весь документ до EOF! Правильный закрытый диапазон в `ruff==0.17.2` (и в `VER-004.command`) — **`--range=START:1-END:999`**! Форматируй целиком ТОЛЬКО новый файл `tests/test_realtime_reasoning.py`, а на `server.py` и `tests/test_step_interruption.py` используй строго `--range=START:1-END:999` по своим изменённым ханкам (`git diff -U0 origin/dev --`), никогда не пересекая строки `def _run_env`, `def _stream_google_sse` и `def _execute_google_once`!
4. **КРИТИЧЕСКАЯ СОВМЕСТИМОСТЬ `import zen_catalog as zc` + ранний перехват `--serve-helper` (`RW-001` + `RW-002`) + `CATALOG_SOURCE` + Python 3.9 AST (`VER-004` + `test_catalog_mode.py` + `test_zen_catalog.py`):**
   - **НЕ заменяй** `import zen_catalog as zc` на `importlib.import_module("zen_catalog")`! (`importlib.import_module` даёт `ModuleType` с `__getattr__ -> Any`, поднимает `reportAny` со `125` до `142` и валит `VER-004.command`!).
   - Строго реализуй ранний перехват `--serve-helper` из `v6` (`architecture-packet.json`): вверху `server.py` размещаются только минимальные stdlib-импорты, необходимые для `_run_serve_helper_cli`, затем определение `_run_serve_helper_cli`, и ветвление `if sys.argv[1:2] == ["--serve-helper"]: raise SystemExit(_run_serve_helper_cli(sys.argv[2:]))` с веткой `else:`, внутри которой импортируются тяжёлые модули (`http.client`, `sqlite3`, `from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer`, `sys.path.insert(0, str(Path(__file__).resolve().parent))`, `import zen_catalog as zc`) — так `--serve-helper` завершается **ДО** импорта `sqlite3`/`http.client`/`http.server`/`zen_catalog` и **ДО** `reload_catalog()` / `_DEFAULT_RESILIENCE` (соблюдая RSS-бюджет `H3`), при этом `ruff check --config ruff.toml` не выдаёт `E402` на импортах внутри `else:`, а `basedpyright==1.40.2` сужает поток управления через `raise SystemExit(...)` (`NoReturn`) и видит все символы связанными (`errorCount == 0`, `reportAny <= 125`)!
   - Сохрани на верхнем уровне модуля `CATALOG_SOURCE = "static"`, а обновление выполняй через типизированную функцию `def _set_catalog_source(source: str) -> None: globals()["CATALOG_SOURCE"] = source` + поставь проверки `proc is not None` перед обоими чтениями `proc.returncode`.
   - Соблюдай совместимость синтаксиса `server.py` с `ast.parse(..., feature_version=(3, 9))` из существующего `tests/test_zen_catalog.py` (в `server.py` есть `from __future__ import annotations`, поэтому `X | Y` в аннотациях допустим, но НЕ используй `match/case` или runtime `isinstance(x, A | B)` — пиши `isinstance(x, (A, B))`!).
5. **КРИТИЧЕСКОЕ ПРАВИЛО `form.created` (`safety_order` из `v6`):**
   - Как только получено событие `form.created` с вложенным `data.form.sessionID == active_session_id` и непустым строковым `data.form.id`, **немедленно** защёлкивай single-turn/Step2 барьер и отправляй `POST /api/form/{id}/cancel` (`<= 0.25s`) и `POST /api/session/{sessionID}/interrupt` (`<= 0.10s`) **ДО** проверки `title`, `fields` и схемы! Отсутствующий `title` при успешных `cancel+interrupt` даёт штатную отмену и `ServeHealth +0` без ожидания watchdog; отсутствие `id`/`sessionID` или ошибка `cancel` ведут в fail-closed выход и `killpg(child_pgid) <= 1.2s`.
6. **КРИТИЧЕСКАЯ ТОПОЛОГИЯ, ЗАКРЫТЫЙ ARGV ХЕЛПЕРА `--serve-helper` И ПРОТОКОЛ ПРИЁМКИ СОВЕТА `a6` (`v6` `AD-001` / `RW-001` / `RW-002` + `F-001`, `F-004` из `arch-panel/cycle-1/a6/final-panel-verdict.md`):**
   - Запускай дочерний лидер группы `helper_proc` строго по закрытому 6-аргументному контракту argv из `v6` (`architecture-packet.json`: `[sys.executable, "-I", str(Path(__file__).resolve()), "--serve-helper", attempt_id, str(port), str(OPENCODE_BIN), str(lease_dir), str(os.getpid()), parent_lstart]`), где `str(OPENCODE_BIN)` резолвится в родительском процессе моста (это сохраняет работоспособность `monkeypatch.setattr(server, "OPENCODE_BIN", str(fake_serve_bin))` в clean-room `VER-005` с пустым `HOME` БЕЗ добавления `OPENCODE_BIN` в `serve_env`!).
   - **`F-001` (Единый конфигурируемый `lease_dir`):** в `server.py` должен быть ровно ОДИН конфигурируемый каталог `lease_dir` (с боевым значением по умолчанию `/tmp/opencode-zen-bridge-leases/`, например модульная константа `LEASE_DIR = Path("/tmp/opencode-zen-bridge-leases")` или атрибут сервера, переопределяемый в тестах), который родитель передаёт позиционным `argv` в `--serve-helper` и который сканирует `startup_reaper`. Сам `--serve-helper` обязан писать lease-файл ИСКЛЮЧИТЕЛЬНО в переданный позиционный `lease_dir / f"lease-{attempt_id}.json"` (никогда не хардкодить литерал `/tmp/opencode-zen-bridge-leases/` внутри `--serve-helper`!). В `tests/test_realtime_reasoning.py` (`VER-005`) обязательно проверь оракул с кастомным `lease_dir` (`tmp_path / "leases"`): файл появляется только там, а следующий старт `startup_reaper` с этим `lease_dir` снимает именно эту запись и только свой `child_pgid`.
   - **`F-004` (Конкурентный неблокирующий дренаж пайпов в `--serve-helper`, запрет `proc.communicate()` после `select([0])`):** НЕ копируй тело архитектурной пробы `EVD-079` с `select([0])` и последующим `proc.communicate()`! В боевом `--serve-helper` Stage 3 цикл наблюдения обязан в каждом тике конкурентно и неблокирующе дренировать `stdout` и `stderr` дочернего `opencode serve` (включая их в `select`/`selectors` вместе с `fd 0` и перенаправляя прочитанные чанки в `sys.stderr`), чтобы запись `>64 КиБ` в `stderr` до первого SSE-события никогда не блокировала дочерний `opencode serve` и не задерживала обработку EOF на `fd 0`. В `tests/test_realtime_reasoning.py` (`VER-005`) обязательно включи тест с дочерним процессом, пишущим `>64 КиБ` в `stderr` до первого SSE-события.
   - До отправки `Authorization` или `prompt` требуй одновременно `listener_pid == serve_pid`, `os.getpgid(listener_pid) == child_pgid` и `helper_proc.poll() is None` (при чужом PID в той же или иной группе — `0` байт пароля/промпта и `0` сигналов чужому PGID!).
7. НЕ использовать `typing.Any`, `typing.cast` или `# type: ignore` в новом/изменённом коде (используй `object`, `TypedDict`, `Protocol`, конкретные контейнеры; проверяй отсутствие `reportUnusedCallResult` в изменённных диапазонах).
8. НЕ делать `git commit`, `git push`, `gh pr create` — коммит создаёт оркестратор после Кодового Совета.
9. НЕ добавлять никаких сторонних runtime-зависимостей вне стандартной библиотеки Python (`pyproject.toml` не менять).
10. НЕ вызывать `security find-generic-password` и не писать секреты/пароли/ключи в логи и тесты.
11. Все новые docstrings и комментарии в коде и тестах — строго **на русском языке**, идентификаторы — на английском.
12. В тестах изменение `os.environ` — только через `monkeypatch` или `try...finally` с гарантированным восстановлением.

## Порядок работы (строго по шагам)

### Шаг 1. План роли ДО правок (`plans/coder-01.before.json`)
До любого изменения файлов в `bridges/opencode-zen-bridge/` создай файл `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-01.before.json` (`schema_version`, `role: "coder"`, `task_id: "analyst-teamlead-zen-realtime-reasoning-20261025"`, `iteration: 1`, 2–5 шагов, все шаги в статусе `"PENDING"`) и провалидируй командой:
```bash
python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" --phase before "/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-01.before.json"
```

### Шаг 2. TDD Red → Green: сначала тесты (`tests/test_realtime_reasoning.py`)
Внимательно прочитай утверждённый `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`v6`) и реализуй все требования, контракты и оракулы (`Group A` и `Group B` из `VER-005`) сначала в новом тестовом модуле `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`:
1. **Чистый Red→Green оракул (`REQ-001`, `AC-001`, `AC-002`, `REQ-020`, `AC-026`):**
   - **КРИТИЧЕСКИ ВАЖНО ДЛЯ CLEAN-ROOM L2 RED GATE:** при копировании одного файла `tests/test_realtime_reasoning.py` на непропатченный `origin/dev` этот модуль НЕ должен падать на уровне `import` с `ImportError`/`AttributeError`! Поведенческий тест `AC-026` должен запускаться через публичный HTTP `POST /v1/chat/completions` (с `monkeypatch.setattr(server, "DYNAMIC_CONFIG_PATH", cfg_path, raising=False)` + `monkeypatch.setenv("OPENCODE_ZEN_BRIDGE_TRANSPORT", "serve")`) и на непропатченном `origin/dev` падать именно `AssertionError` по таймингу прихода чанков (`first_reasoning_t < upstream_end_t`), а для юнит-тестов новых внутренних функций используй `getattr(server, ...)` с явным `assert hasattr(server, ...)` внутри самих тестовых функций!
   - Запусти `tests/test_realtime_reasoning.py` ДО правки `server.py` (в фоне!) и сохрани фактический вывод падения (RED) для `plans/coder-01.json`!
2. **Полное покрытие оракулов `VER-005` из `architecture-packet.json` (`v6`):**
   - `DYNAMIC_CONFIG_PATH` (`dynamic_config.json`, дефолт `false`), kill-switch `disable-serve`, `_ServeHealth` sticky TTL без открытия `_UpstreamBreaker`, барьер доставки `DELIVERED` и таблица `fallback_decision_table` (включая обе строки `first_token_timeout`: тишина модели vs protocol/capability дефект);
   - быстрый старт `[мост] Ожидание первого токена…\n` (`< 1.0s`), отсутствие `[мост]` на быстрых дельтах, ведущий `\n` после незавершённой дельты (`AC-006`) и исключение `reasoning_content` из `_messages_to_prompt` (`AC-007`);
   - побайтовая неизменность `def _run_env` (`1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`), `def _stream_google_sse` (`5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3`), `def _execute_google_once` (`88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6`), `OPENCODE_DB=":memory:"` + санитизированный allowlist `_serve_env(model_id)` на всех 3 ветках маршрутизации с сохранением стандартного `XDG_DATA_HOME` (без утечки `OPENCODE_BIN` в `serve_env`), а также тест `FakeServe` через `monkeypatch.setattr(server, "OPENCODE_BIN", str(fake_serve_bin))` при пустом `HOME` (`RW-002`);
   - единое дерево `parent -> server.py --serve-helper <attempt_id> ... -> opencode serve`, проверка раннего выхода `--serve-helper` без импорта `zen_catalog`/`sqlite3` и без вызова `reload_catalog()` + удержание RSS хелпера в бюджете `v6` (`RW-001` / `H3`), 5 точек инжекции `SIGKILL` родителя + `terminal_quiescence` + startup lease reaper (`0` сирот и `0` сигналов чужим PGID), негативные тесты `listener_pid` (чужой PID в той же группе и чужой PID в иной группе → `0` байт пароля/промпта и `0` сигналов чужому PGID), `1× lsof` на штатном Keep-Alive пути vs `2-й lsof` только на явном control reconnect;
   - замороженные фикстуры v2.1.2 (сверка `frozen_fixture_sha256` по формуле `{name: {"wire": ..., "canonical": ...}}`), `ask_reject|deny`, `form.created` `safety_order` (`cancel <= 0.25s` + `interrupt <= 0.10s` до проверки `title`/`fields`, включая мутацию `missing title -> ServeHealth 0` и `missing id/sessionID -> fail-closed killpg <= 1.2s`), fallback `session.tool.input.ended.data.text`, раздельные watchdogs, `client_gone <= 5s`, `ToolCallParser`, прокси-ротация, маскирование секретов и `O-EXIT/v1`.

### Шаг 3. Реализация в `server.py` и починка `test_step_interruption.py` (`REQ-017`) + статического долга `VER-004`
1. Реализуй весь контракт утверждённого `architecture-packet.json` (`v6`) в `bridges/opencode-zen-bridge/server.py` без `Any`, сохраняя `import zen_catalog as zc` в `else:`-ветке раннего перехвата `--serve-helper`, не меняя `def _run_env` и не задевая `_stream_google_sse` / `_execute_google_once`.
2. Приведи в зелёное 3 pre-existing падения в `bridges/opencode-zen-bridge/tests/test_step_interruption.py` (`REQ-017`, `AC-022`, `AC-023`, плюс `AC-016` на потоковых дельтах).

### Шаг 4. Полный прогон замороженной поверхности верификации (`VER-001..VER-005` из `architecture-packet.json` и `teamlead/verification-surface.json`)
Выполни **дословно** исполняемую команду `VER-004.command` из `architecture-packet.json` (`v6`), а также `VER-001`, `VER-002`, `VER-003`, `VER-005` и обратный порядок тестовых файлов (`AC-023`) в фоне — добейся `exit_code == 0` по КАЖДОЙ проверке! Проверь `git status --short` / `git diff --name-only` (ровно 3 целевых файла в `bridges/opencode-zen-bridge/`, никаких временных файлов в репо!).

### Шаг 5. Финализация артефактов роли Coder (`plans/coder-01.json`, `handoffs/coder-01.json`, `coder.json`)
1. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/coder-01.json` (все шаги `"DONE"` с фактическим `evidence`) и провалидируй `validate_role_plan.py --phase after`.
2. Запиши `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-01.json` (схема `1.1`, точный `sha256` от `plans/coder-01.json`) и провалидируй `validate_handoff.py coder`.
3. Скопируй валидный `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoffs/coder-01.json` в `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/coder.json`.

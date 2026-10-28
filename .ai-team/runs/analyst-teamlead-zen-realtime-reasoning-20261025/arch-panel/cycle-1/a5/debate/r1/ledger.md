# Черновой консенсус-леджер находок Архитектурного Совета — Cycle 1 (`a5`, после `R1` `panel/arch/r10`)

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r10` (`panel-proof.json` `sha256=bb81268bdfa8ff2e30f08cdf814f56573d799b191f2d6ed319f11b76fb8a4f0f`, `verify_panel_proof exit=0`)
- **Проверяемый артефакт (v5):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`sha256=15ea67e3215ceea9e84b9d79853677f4be86b959e87a21f24830d0c895f62657`)
- **Всего открытых находок после R1:** 4 (`F-001`..`F-004` от `skeptic` `gemini-4-argon-high`, `0` от `realist` `grok-4.7-high`, `0` от `visionary` `muse-wonder-full-1.0`)

---

## Находки Seat 1 (`skeptic`, `gemini-4-argon-high`, `Google`, `agy`)

### F-001
- origin: skeptic · R1 · skeptic-F-001
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
> F-001 [blocking] Необновлённый расчёт памяти хелпера (helper_estimate = 12.0 MiB) противоречит переходу FU-004 на запуск полного server.py --serve-helper (~26.86 MiB RSS в простое) и срывает фиксированный потолок 192 MiB/слот гейта H3
> - priority: blocking
> - Якорь: architecture-packet.json:1313 (#EVD-077), architecture-packet.json:1589 (#VER-005), architecture-packet.json:1613-1618 (#VER-005), architecture-packet.json:1756 (#AD-001), architecture-packet.json:2509-2514 (#AD-001), architecture-packet.json:2822 (#QA-009), architecture-packet.json:2983-2986 (#RISK-003), architecture-packet.json:3152-3160 (#H3_rollout_gate / evolution.H3_rollout_gate), architecture-packet.json:3371 (high_load_envelope.capacity_formula.Mem_shared_max), architecture-packet.json:3429 (high_load_envelope.memory_ssot.estimate_status), architecture-packet.json:3468-3473 (high_load_envelope.memory_ssot.slot_breakdown), architecture-packet.json:3488 (high_load_envelope.memory_ssot.runtime_gate), architecture-packet.json:3592 (high_load_envelope.operational_profile.fd_and_threads.substitution), architecture-packet.json:4234-4235, architecture-packet.json:4256; [F-29] (architecture-packet.json:506-510).
> - Правило: Внутренняя арифметическая согласованность бюджета ресурсов (high_load_envelope.memory_ssot) и выполнимость эксплуатационного гейта evolution.H3_rollout_gate («fixed192MiB combined/slot», «Exceedance fails H3, not waiver»).
> - Доказательство (цитата и факт): В дельте v4->v5 (FU-004) запуск вспомогательного процесса изменён с `python3 -I -c _SERVE_HELPER_CODE` на `helper_proc=Popen([sys.executable, "-I", str(Path(__file__).resolve()), "--serve-helper", attempt_id, str(port), ...])` с точкой входа внизу `server.py` внутри `if __name__ == "__main__":` после выполнения всех импортов и кода верхнего уровня (`architecture-packet.json:1313, 1589, 1756`). При этом во всех расчётах памяти оставлена прежняя цифра голого интерпретатора: `"helper_estimate": 12.0`, `"combined_with_probe_estimate": 176.8`, `"per_slot_ceiling": 192` и `"Serve idle156.8+helper~12+probe~8=176.8 ... fixed192MiB combined/slot"` (`architecture-packet.json:1613-1618, 2509-2514, 3156, 3468-3473`). Прямой read-only замер на целевой рабочей станции (`python3 -I -B` с импортом текущего 4021-строчного `bridges/opencode-zen-bridge/server.py`, включающего `sqlite3`, `http.server`, `urllib`, `zen_catalog` и вызов `reload_catalog()`, под очищенным окружением) показывает фактический RSS процесса **27 504 KiB = 26.86 MiB** (`ru_maxrss = 28 147 712 B = 26.84 MiB`; ср. также `[F-29]` = 22 MiB RSS простаивающего моста). Подстановка реального холостого RSS хелпера ещё до добавления ~1000 строк кода Stage 3 даёт `156.8 + 26.86 + 8.0 = 191.66 MiB` на слот (остаток `0.34 MiB` до жёсткого потолка `192 MiB`), что на реальной проверке `H3` (`6` параллельных запросов с промптами по `103 KB`, запрет waiver при превышении `192 MiB/slot`) гарантированно приведёт к провалу гейта и блокировке включения фичефлага `H7`.
> - Ожидаемое исправление: Выполнить одно из двух согласованных архитектурных действий (или их комбинацию): (а) разместить быстрый перехват `--serve-helper` и stdlib-функцию `_run_serve_helper_cli` в верхней части `server.py` до импорта `sqlite3`, `http.server`, `zen_catalog` (сохранив `import zen_catalog as zc` на исходной позиции для основного режима или удержав единственный E402 без смещения замороженных функций) и до `reload_catalog()` / `_DEFAULT_RESILIENCE`, подтвердив новым замером `EVD`, что реальный RSS `python3 -I server.py --serve-helper` укладывается в заявленную оценку; либо (б) обновить `helper_estimate` до честной величины с запасом на Stage 3 (не менее `30–32 MiB`) и пересчитать `per_slot_ceiling` (например, `210 MiB/slot`: `6 * 210 + 256 = 1516 MiB <= 1638.4 MiB`) синхронно во всех 14 перечисленных местах пакета.
> - Критерий проверки: Воспроизводимый замер `EVD` для команды `sys.executable -I bridges/opencode-zen-bridge/server.py --serve-helper ...` показывает `actual_helper_rss_mib <= helper_estimate`, а сумма `156.8 + helper_estimate + 8.0` имеет не менее `12–15 MiB` запаса под `per_slot_ceiling` для нагрузки `103 KB` во всех секциях (`VER-005`, `AD-001`, `QA-009`, `RISK-003`, `H3_rollout_gate`, `high_load_envelope`, `rework_summary`).

### F-002
- origin: skeptic · R1 · skeptic-F-002
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
> F-002 [blocking] Потеря переопределения OPENCODE_BIN, неспецифицированный хвост argv («...») и неизолированные побочные эффекты верхнего уровня server.py при запуске дочернего helper_proc с очищенным serve_env
> - priority: blocking
> - Якорь: architecture-packet.json:1113 (#EVD-076), architecture-packet.json:1313 (#EVD-077), architecture-packet.json:1498-1499 (#VER-004), architecture-packet.json:1553 (#VER-005), architecture-packet.json:1589 (#VER-005), architecture-packet.json:1629 (#VER-005), architecture-packet.json:1643 (#VER-005), architecture-packet.json:1756 (#AD-001), architecture-packet.json:2257 (#AD-001), architecture-packet.json:2286-2317 (#AD-001.details.serve_env_sanitization), architecture-packet.json:2358 (#AD-001.details.crash_recovery.creation), architecture-packet.json:2360 (#AD-001.details.crash_recovery.startup_reaper), architecture-packet.json:2525 (#AD-001), architecture-packet.json:3041 (#RISK-008), architecture-packet.json:3107 (#THREAT-001), architecture-packet.json:3123 (#THREAT-003), architecture-packet.json:3255, architecture-packet.json:3839, architecture-packet.json:4962, architecture-packet.json:5086, architecture-packet.json:5357, architecture-packet.json:5481; [F-43] (architecture-packet.json:619-620); bridges/opencode-zen-bridge/server.py:52-55, 163, 293.
> - Правило: Замкнутость межпроцессного контракта `parent -> helper_proc -> serve_proc`, воспроизводимость clean-room верификации без домашнего каталога владельца (`QA-008`, `AC-023`, `VER-005`) и запрет побочных обращений к путям репозитория/боевого стейта из изолированных тестов (`THREAT-003`).
> - Доказательство (цитата и факт): В `AD-001.details.spawn` (`architecture-packet.json:1756`) и `VER-005.details.process_resource_oracle.topology` (`architecture-packet.json:1589`) указано: `helper_proc=Popen([sys.executable, "-I", str(Path(__file__).resolve()), "--serve-helper", attempt_id, str(port), ...], stdin=lifeline_r, stdout=PIPE, stderr=PIPE, start_new_session=True, close_fds=True, env=serve_env)` и далее внутри хелпера: `It launches serve_proc=Popen([OPENCODE_BIN,"serve","--hostname","127.0.0.1","--port",str(port)], stdin=DEVNULL, start_new_session=False, close_fds=True, env=serve_env, ...)`. Одновременно `AD-001.details.serve_env_sanitization` (`architecture-packet.json:2286-2317`) фильтрует `serve_env` по строгому белому списку из 27 ключей с запретом `"No broad OPENCODE_* or FAKE_* wildcard"`, вырезая как `OPENCODE_BIN`, так и все `OPENCODE_ZEN_BRIDGE_*` (`OPENCODE_ZEN_BRIDGE_LOG`, `OPENCODE_ZEN_BRIDGE_CATALOG_STATE`). В результате в новом процессе `helper_proc`: (1) строка `server.py:52` (`OPENCODE_BIN = os.environ.get("OPENCODE_BIN", str(Path.home() / ".opencode" / "bin" / "opencode"))`) всегда вычисляется в `~/.opencode/bin/opencode`, теряя и in-process подмену `server.OPENCODE_BIN = str(fake)` (используемую существующими тестами по `[F-43]` и `FakeServe` в `VER-005`), и env-переменную `OPENCODE_BIN` родителя, тогда как скелет `_run_serve_helper_cli(args: list[str])` в `EVD-077` (`architecture-packet.json:1313`) принимает лишь `attempt_id, port_text = args[:2]`, оставляя остальные аргументы неспецифицированным многоточием `...`; (2) так как диспетчер `--serve-helper` расположен внизу `server.py` внутри `if __name__ == "__main__":`, каждый запуск `helper_proc` под очищенным `serve_env` выполняет `server.py:54-55` и `server.py:163` (`reload_catalog()`), обращаясь к путям внутри дерева кода `HERE / "state" / "zen-catalog.json"` и выставляя `LOG_PATH = HERE / "logs" / "bridge.log"` вопреки тестовой изоляции.
> - Ожидаемое исправление: Полностью убрать неоднозначное `...` из спецификации `argv` хелпера и зафиксировать точный типизированный список позиционных параметров `--serve-helper`, включающий вычисленный в родителе путь исполняемого файла `str(OPENCODE_BIN)` и путь изолированного каталога lease/state (например: `[sys.executable, "-I", str(Path(__file__).resolve()), "--serve-helper", attempt_id, str(port), str(OPENCODE_BIN), str(lease_dir), str(os.getpid()), parent_lstart]`, где `--serve-helper <attempt_id> <port>` остаются первыми аргументами для `startup_reaper`). В `_run_serve_helper_cli` явно валидировать непустой путь `opencode_bin` и передавать его в `Popen([opencode_bin, "serve", ...])`, не опираясь на модульную константу `OPENCODE_BIN` и не добавляя `OPENCODE_BIN` в `serve_env` (чтобы не загрязнять окружение `opencode serve`). Одновременно защитить верхний уровень `server.py` от выполнения `reload_catalog()` и серверной инициализации при запуске с `sys.argv[1:2] == ["--serve-helper"]`.
> - Критерий проверки: В `VER-005` clean-room тест с `monkeypatch.setattr(server, "OPENCODE_BIN", str(fake_serve_bin))` и `HOME` во временном пустом каталоге (без `~/.opencode/bin/opencode`) успешно поднимает реальную цепочку `parent -> helper_proc -> fake_serve_bin`, не читает `bridges/opencode-zen-bridge/state/zen-catalog.json` и не пишет в `bridges/opencode-zen-bridge/logs/bridge.log`; сигнатура `_run_serve_helper_cli` без многоточий зафиксирована единообразно во всех секциях пакета.

### F-003
- origin: skeptic · R1 · skeptic-F-003
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
> F-003 [non-blocking] Прогон write-mode ruff format по временной копии server.py в /tmp внутри VER-004.command не передаёт явный --config ruff.toml
> - priority: non-blocking
> - Якорь: architecture-packet.json:1498-1499 (#VER-004); plans/architect-05.json:90.
> - Правило: Детерминированность и независимость верификационной команды `VER-004` от пользовательского окружения хоста (`QA-008`, `AC-023`).
> - Доказательство (цитата и факт): В `VER-004.command` (`architecture-packet.json:1498`) добавлен блок проверки реальной записи форматтера: `with tempfile.TemporaryDirectory(prefix='zen-arch5-probe-format-', dir='/tmp') as format_dir: formatted_copy = Path(format_dir) / 'server.py' ... run([*ruff,'format','--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)`. Ruff разрешает конфигурационный файл от директории целевого файла вверх (`/tmp/...` -> `/tmp` -> `/`), игнорируя `cwd=root`, и при отсутствии `ruff.toml` в `/tmp` откатывается на пользовательский конфиг хоста (`~/.config/ruff/ruff.toml` или `~/Library/Application Support/ruff/ruff.toml`), о чём сам Архитектор упоминал в `plans/architect-05.json:90`. Кроме того, последовательное применение диапазонов `ranges[files[0]]` к изменяемому на месте `formatted_copy` при несовпадении пользовательских настроек длины строки может сместить номера строк следующих ханков.
> - Ожидаемое исправление: Передавать явный аргумент `'--config', str(root / 'ruff.toml')` во все вызовы `ruff format` и `ruff check` внутри `VER-004.command` и дополнительно проверять `assert formatted_copy.read_bytes() == files[0].read_bytes()`, подтверждая полную идемпотентность уже отформатированного кандидата.
> - Критерий проверки: Выполнение `VER-004.command` с искусственным пользовательским конфигом Ruff в `XDG_CONFIG_HOME` (например, `line-length = 60`) даёт идентичный результат и `exit 0` за счёт жёсткой привязки к `root / 'ruff.toml'`.

### F-004
- origin: skeptic · R1 · skeptic-F-004
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
> F-004 [pre-existing][sweep][non-blocking] Устаревшие пути плана цикла a4 в списке scope.architect_write_allowlist при cycle=5 и role_plan=plans/architect-05.json
> - priority: non-blocking
> - Якорь: architecture-packet.json:7, architecture-packet.json:11-15, architecture-packet.json:19-23 (#scope).
> - Правило: Согласованность метаданных области записи Архитектора (`scope.architect_write_allowlist`) с текущим циклом пакета (`cycle`, `role_plan`).
> - Доказательство (цитата и факт): В шапке пакета указаны `"cycle": 5` (`architecture-packet.json:7`) и `"role_plan": {"path": "plans/architect-05.json", ...}` (`architecture-packet.json:11-14`), однако пятью строками ниже в `scope.architect_write_allowlist` (`architecture-packet.json:19-23`) остались пути предыдущего цикла: `".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-04.before.json"` и `".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-04.json"`.
> - Ожидаемое исправление: Обновить записи плана в `scope.architect_write_allowlist` на актуальный цикл (`architect-06.before.json` / `architect-06.json` при выпуске следующей редакции пакета либо шаблон `plans/architect-*.json`).
> - Критерий проверки: Номер цикла в `scope.architect_write_allowlist` совпадает с `cycle` и `role_plan.path` в шапке `architecture-packet.json`.

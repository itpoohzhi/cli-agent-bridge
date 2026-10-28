Skill: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md

Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

Ты — внешний исполнитель роли **Architect** (`gpt-6.1-sol`, effort `high`) в изолированном клоне `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning` (ветка `feature/zen-realtime-reasoning`). Это точечная финализация твоего пакета v3 (`architect-cycle-3b`), чтобы он прошёл `validate_architecture_packet.py --phase approved` без выдумывания согласия человека и без исключений из канона фичефлагов.

## Уже известно
- `repo_root`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning`
- `run_dir`: `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025`
- Разрешённые для записи файлы (ТОЛЬКО эти три пути; продуктовые файлы менять СТРОГО ЗАПРЕЩЕНО):
  1. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-03.before.json` (уже существует и валиден — не удаляй)
  2. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-03.json`
  3. `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json`
- Факт проверки валидатора на твоём текущем `architecture-packet.json` (`343 156` байт):
  - ВСЕ структурные секции, `HL-ENV/v1` (46 полей), 24 гейта, `evidence`, `assumptions`, `verification_surface`, `quality_scenarios`, `boundaries`, `views`, `risks`, `threat_model`, `open_questions` и `role_plan` уже валидны!
  - ЕДИНСТВЕННАЯ причина отказа `validate_architecture_packet.py --phase approved`: `FAIL: approval.status must be APPROVED` (строка 425 `validate_architecture_packet.py`), потому что в `AD-001` оставлен кодовый `default=true` и из-за `FU-007` выставлено `AD-001.approval_required = true` при `approval.status = "PENDING"`.
  - В `approval.rationale` ты сам точно сформулировал развязку: *«either explicit exception receipt or approved compliant flag delta»*.

Входы даны выше; на диск за ними не ходи мимо указанных путей; стартовый корень поиска ∈ {$HOME, /Users/aazhiry1, /} запрещён.

## ПРАВИЛА ПАРАЛЛЕЛИЗМА
- Все чтения нужных участков `architecture-packet.json` и `plans/architect-03.json` выполни за один батч; продуктовый код повторно исследовать не нужно — меняются только секции фичефлага/выката/`AD-001`/`approval` в `architecture-packet.json` и `role_plan.sha256` после обновления `plans/architect-03.json`.

## Задание: применить compliant flag delta (`default=false` в коде + локальный `dynamic_config.json`)

Чтобы одновременно закрыть **и** `FU-007` (`a2`, командный канон `AGENTS.md`: фичефлаг с кодовым дефолтом `false` до включения в динамическом конфиге, мгновенный kill-switch без рестарта и без новых env-переменных), **и** `RW-009` (`a1`, активация на `:9883` после деплоя без правки замороженного `start.sh` и сохранение зелёными 378 fake-CLI тестов `REQ-003`/`AC-004`), внеси в `architecture-packet.json` следующую согласованную дельту:

1. **Локальный динамический конфиг фичефлагов `DYNAMIC_CONFIG_PATH = Path(__file__).resolve().parent / "dynamic_config.json"` (stdlib-аналог `dynamic_config.py` / GigaRC для автономного локального моста без внешних зависимостей):**
   - Ключ `"REALTIME_SERVE_ENABLED": bool`, **кодовый дефолт = `false`**, когда файл `dynamic_config.json` отсутствует, не читается, содержит битый JSON или небулево значение (при ошибке чтения — fail-safe в `false` и диагностический warning в лог без секретов).
   - Чтение на каждый запрос через кэш по `(st_mtime_ns, st_size)` (`os.stat` $O(1)$, без переоткрытия файла при неизменном `mtime_ns`, без рестарта LaunchAgent и без добавления env-переменных в замороженный `start.sh`).
   - Приоритет выбора транспорта в `OPENCODE_ZEN_BRIDGE_TRANSPORT=auto` (при сохранении обратной совместимости с `REQ-003`):
     1. Явный kill-switch: `OPENCODE_ZEN_BRIDGE_TRANSPORT=run` ИЛИ `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` в `{"0", "false", "no", "off"}` ИЛИ наличие файла `disable-serve` (`OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE`) ИЛИ открытый sticky TTL деградации в `_ServeHealth` → строго `run`;
     2. Явный `OPENCODE_ZEN_BRIDGE_TRANSPORT=serve` → `serve` (без тихого фоллбэка на `run`);
     3. В режиме `auto`: `serve` выбирается тогда и только тогда, когда `"REALTIME_SERVE_ENABLED": true` в `DYNAMIC_CONFIG_PATH` (`dynamic_config.json`) (либо явно передано `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED=1/true` в окружении процесса), и бинарник `OPENCODE_BIN` проходит проверку нативного `opencode` (не текстовый fake-CLI со скриптом `#!`, если только в тесте не включён явный тестовый override). При отсутствии `dynamic_config.json` кодовый дефолт `REALTIME_SERVE_ENABLED` равен **`false`** (прежнее поведение `opencode run --format json`).
2. **Почему это полностью закрывает `AC-004`, `AC-026`, `RW-009` и `FU-007` без исключений и без human waiver:**
   - **378 существующих тестов (`AC-004`):** в клоне репозитория `bridges/opencode-zen-bridge/dynamic_config.json` отсутствует (и не коммитится в git), поэтому по кодовому дефолту `false` все 378 существующих fake-CLI тестов идут по прежнему пути `run` гарантированно и без хрупких допущений.
   - **Чистый Red→Green оракул `AC-026` (`VER-005` / Clean-Room L2):** в `tests/test_realtime_reasoning.py` тест создаёт временный `tmp_path / "dynamic_config.json"` с `{"REALTIME_SERVE_ENABLED": true}` и устанавливает `monkeypatch.setattr(server, "DYNAMIC_CONFIG_PATH", cfg_path, raising=False)` (важно `raising=False`, чтобы при копировании одного `test_realtime_reasoning.py` на непропатченный `origin/dev` тест не падал с `AttributeError`, а реально выполнял `POST /v1/chat/completions` и падал **RED** именно на поведенческом утверждении реалтайм-интервалов чанков, а на новом коде проходил **GREEN**!). Переключение `"REALTIME_SERVE_ENABLED": false` в том же `cfg_path` на лету проверяет мгновенный runtime kill-switch без рестарта `Server`.
   - **Безопасный dark-launch и активация на `:9883` без правки `start.sh` (`H0..H9`, `REQ-019`, `RW-009`, `FU-007`):**
     - При синхронизации `~/.dsh/bridges/opencode-zen-bridge/server.py` и `launchctl kickstart` (`H4/H5`) файл `~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json` ещё отсутствует (или содержит `{"REALTIME_SERVE_ENABLED": false}` — precondition `H0`), поэтому мост стартует в **тёмном режиме (`run`)** с нулевым окном гонки до прохождения проверок!
     - Только ПОСЛЕ успешного прохождения `H3` (проверка 6 параллельных слотов RSS/FD с `OPENCODE_DB=":memory:"`) и `H6` (живая проверка permission/tool изоляции на кандидате) шаг `H7` атомарно (`tempfile` + `os.replace`, права `0600`) записывает `{"REALTIME_SERVE_ENABLED": true}` в `~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json` — `serve` мгновенно активируется на `:9883` без правки `start.sh` и без повторного рестарта LaunchAgent!
     - Мгновенный откат (`evolution.rollback`): атомарная запись `{"REALTIME_SERVE_ENABLED": false}` в `~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json` (или удаление файла / создание `disable-serve`) за `<1 мс` возвращает `run` без рестарта моста.
3. **Обнови метаданные согласования и трассировки в `architecture-packet.json`:**
   - В `AD-001` (и везде в `AD-001.consequences`, `AD-001.details.configuration`, `evolution.rollout`, `evolution.rollback`, `ASM-003`, `rework_traceability` по `FU-007` и `RW-009` в истории): приведи описание к этой схеме (`default=false` в коде + runtime `dynamic_config.json` с атомарным включением на шаге `H7` после `H3/H6`), убери противоречия вида «default=true retained».
   - Поскольку отступления от канона `default=false` больше нет и все решения `AD-001..AD-005` являются обратимыми `two-way` внутри периметра задачи, установи в `AD-001`: `"approval_required": false`, а в корневом блоке `approval`:
     ```json
     "approval": {
       "status": "NOT_REQUIRED",
       "decision_ids": [],
       "approved_by": null,
       "evidence_ref": null,
       "rationale": "FU-007 закрыт без исключений из канона: кодовый дефолт REALTIME_SERVE_ENABLED переведён в false, а включение на :9883 выполняется через локальный runtime dynamic_config.json (stat mtime_ns кэш без рестарта и без правки start.sh) строго на шаге H7 после прохождения H3/H6. Все AD обратимы (two-way); status=APPROVED означает валидированный архитектурный пакет-кандидат для Архитектурного Совета a3 (r4), а не вердикт Совета."
     }
     ```
   - Убедись, что `coder_target_files` и `protected_paths` разрешают только кодовые файлы в репозитории (`bridges/opencode-zen-bridge/server.py`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`; файл `dynamic_config.json` в git-репозиторий НЕ добавляется!).
4. **Обнови `plans/architect-03.json` и проверь оба валидатора до выхода:**
   - Допиши/обнови финальный шаг в `plans/architect-03.json`, прогони:
     `python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" --phase after ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-03.json"`
   - Запиши новый точный `sha256` файла `plans/architect-03.json` в `architecture-packet.json` -> `role_plan.sha256`.
   - Обязательно выполни:
     `python3 "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/architect-software-product/scripts/validate_architecture_packet.py" ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json" --phase approved --run-dir ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025" --role-plan ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-03.json"`
     и убедись, что команда завершилась с `exit 0` и строкой `PASS: architecture packet is valid for approved; sha256=...`!

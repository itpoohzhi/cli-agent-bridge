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

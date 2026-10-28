# feat(opencode-zen-bridge): потоковые reasoning и progress для DSH Desktop

## Проблема и результат

DSH Desktop получает `delta.reasoning_content` и текст по мере появления событий
OpenCode Zen для DeepSeek V4.1 Flash, вместо ожидания финализированного reasoning
от `opencode run`. Во время долгого шага виден progress в том же reasoning-потоке.

Ветка: `feature/zen-realtime-reasoning`; целевая ветка PR: `dev`.
Jira KEY не задан; ссылка на карточку не выдумывается.

## Изменения

- На запрос/попытку создаётся изолированный эфемерный `opencode serve`
  на `127.0.0.1:<ephemeral>` с отдельной сессией, lease и ограниченным временем жизни.
- HTTP 200 и начальный assistant SSE отправляются до ожидания модельного ответа;
  ранние статусы выводятся в `delta.reasoning_content` после grace-периода `.65 s`:
  `[мост] Подключение к модели…`, `[мост] Ожидание первого токена…`,
  `[мост] Ожидание продолжения…`. Текст модели сохраняется отдельно от progress.
- Канонические `session.reasoning.delta` / `session.text.delta` передаются потоково;
  `session.tool.*` и `session.step.ended` обеспечивают tool-step finalization и usage.
- Возврат на `opencode run` допускается только до монотонного барьера `delivered_any`:
  после доставки модельного reasoning/text/tool-чанка повторная выдача запрещена.
- `permission.asked` и `form.created` обрабатываются fail-closed:
  reject/cancel + interrupt, без ожидания пользовательского разрешения.
- Ранний `_run_serve_helper_cli` запускается до тяжёлых импортов; helper получает
  отдельную POSIX-сессию через `start_new_session=True`, следит за lifeline родителя;
  `_startup_reaper` проверяет ownership, PID/PPID, PGID и `lstart` по lease.
- Ограничены строки SSE, очередь, накопленные данные, HTTP body и число native tools:
  `_MAX_SSE_LINE_BYTES=1 MiB`, `_MAX_SERVE_QUEUE_BYTES=16 MiB`,
  `_MAX_SERVE_ACCUMULATED_BYTES=16 MiB`, `_MAX_SERVE_HTTP_BODY_BYTES=8 MiB`,
  `_MAX_SERVE_NATIVE_TOOLS=128`; `_AuxIoBudget` разделяет бюджет `54.0 s`.
- `_dedup_retry_text` исключает повтор уже доставленного текста при retry;
  `O-EXIT/v1` фиксирует transport/history, first event, TTFT и причину выхода.
- `coder-16` дополнительно внёс RW-001..RW-004: безопасное завершение control-вызовов,
  побайтовую склейку reasoning, отмену при disconnect и ранние timestamps между retry.

Продуктовый scope: [server.py], [test_realtime_reasoning.py], [test_step_interruption.py].
Архитектура и ограничения зафиксированы в [architecture packet].

## Совместимость и включение

- `_run_env`, `_stream_google_sse`, `_execute_google_once` побайтово совпадают
  с `origin/dev`; замороженные SHA проверены в [VER-004].
- Внешних runtime-зависимостей не добавлено: используется stdlib Python 3.14.
- Serve по умолчанию выключен. В режиме `auto` локальный `dynamic_config.json`
  читает boolean `REALTIME_SERVE_ENABLED`, отсутствие/ошибка дают `false`.
  Это локальный stdlib-аналог удалённого feature flag; runtime JSON не входит в PR.
- Расхождения исходного брифа: `OPENCODE_ZEN_REALTIME_REASONING_ENABLED` кодом
  не читается, GigaRC SDK не подключён; `_early_reaper_main` и прямой `os.setsid`
  отсутствуют — используются helper/reaper и `start_new_session=True` выше.
  Запрошенные строки «⏳ Запуск сессии opencode…», «⏳ Модель размышляет…»,
  «⏳ Продолжаю выполнение шага…» заменены фактическими `[мост]`-статусами.

## Проверки и решение по ревью

- [pytest]: `rc=0`, **511 passed + 3387 subtests**, `422.76 s`.
- [unittest]: `rc=0`, **Ran 511 tests**, `387.846 s`, `OK`.
- [VER-004]: `rc=0`, Ruff `0.17.2` lint трёх файлов; единственное исключение —
  наследуемый E402 у `import zen_catalog as zc`. Format `--check` выполнен по
  изменённым диапазонам legacy-файлов; новый тест проверен целиком ([format log]).
- Basedpyright `1.40.2` в [VER-004]: 3 файла, **0 errors / 764 warnings**
  (server: 591); это проверка с установленными лимитами legacy warnings.
  Там же 8 catalog-mode tests завершились `OK` и подтверждены frozen-byte contracts.
- Эти цифры относятся к сохранённым L2-прогонам; подготовка описания не запускала
  новые тесты и не подтверждает полный повтор suite после последних RW-исправлений.
- Архитектурный `ARCH_PANEL_PASS` подтверждён [архитектурным итогом] для v6:
  R1 `panel/arch/r18` → D1 `panel/arch/r21`, `blocking_open=0`.
  Указанный в брифе путь `panel/arch/a6/r1` отсутствует и не считается проверенным.
- Код проходил циклы 1–12 (`panel/council/r22..r266`). [r245 proof] — `PASS`
  проверки квитанции, голоса **2 ACCEPT / 1 NEEDS_WORK**; [r266 proof] — `PASS`
  проверки квитанции, голоса **3 NEEDS_WORK**. Proof PASS не означает ACCEPT голосов.
- [Итоговый ledger]: владелец **2026-10-28 02:51 MSK** остановил Совет,
  утвердил F-001..F-005 как `non-blocking (pre-existing)`; RW-001..RW-004 внесены
  `coder-16`. Ledger фиксирует **ACCEPT, blocking_open=0** по решению владельца,
  без утверждения единогласия моделей и без нового ревью-вердикта этого описания.

## Живая проверка после установки

ПРОВЕРЕНО ЛЁГКИМ: сохранённые L2-прогоны и VER-004 выше.
ПРОВЕРЕНО ТЯЖЁЛЫМ: не выполнено; [verifier receipt] содержит `DEFERRED_L3`.
НЕ ПРОВЕРЕНО: бизнес-сценарий существующего рабочего чата DSH Desktop и H0–H9.

- В существующем чате DSH Desktop выбрать DeepSeek V4.1 Flash / OpenCode Zen:
  измерить headers, assistant SSE и первый progress, исключить долгую немую паузу.
- Проверить реальные reasoning/text/tool/usage и tool-step finalization;
  на permission/form подтвердить reject/cancel + interrupt без продолжения операции.
- Повторить запросы последовательно и параллельно, затем retry с частичным ответом:
  проверить отсутствие дублирования, разрывы соединения и отсутствие orphan-процессов.
- На рабочем размере истории проверить RSS/CPU/FD, тайминги, proxy/egress и нагрузку
  до 6 параллельных запросов; эти проверки пока не заявлены выполненными.

## Откат

- В режиме `auto`, без forced `serve` и env override `true`, записать
  `{"REALTIME_SERVE_ENABLED": false}` в runtime `dynamic_config.json`:
  следующие запросы используют `run`, перезапуск моста не нужен.
- При принудительном `serve` использовать disable-файл из
  `OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE` (дефолт
  `~/.dsh/bridges/opencode-zen-bridge/disable-serve`): проверка выше forced `serve`.
- Альтернатива: `OPENCODE_ZEN_BRIDGE_TRANSPORT=run` в окружении запуска
  и перезапуск процесса моста. Env меняется при старте; это отличается от JSON.
- Откат транспорта не отменяет уже идущие запросы и общие legacy watchdog/status
  изменения; завершение текущих слотов и старые чаты проверить отдельно.

[server.py]: bridges/opencode-zen-bridge/server.py
[test_realtime_reasoning.py]: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py
[test_step_interruption.py]: bridges/opencode-zen-bridge/tests/test_step_interruption.py
[architecture packet]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json
[pytest]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver001-pytest.log
[unittest]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver002-unittest.log
[VER-004]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-packet.log
[format log]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/l2-green-ver004-ruff-format-new.log
[архитектурным итогом]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/final-panel-verdict.md
[r245 proof]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/council-r245-proof.json
[r266 proof]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/council-r266-proof.json
[Итоговый ledger]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/final-panel-verdict.md
[verifier receipt]: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/verifier.json

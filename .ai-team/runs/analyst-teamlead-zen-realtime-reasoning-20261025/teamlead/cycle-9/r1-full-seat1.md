PANEL-NONCE: 76d8c83e10e731a7
ARTIFACT-SHA256: 35adea8bc3197709e42854cde111e17b0cdaba1febb6fa6f0f8e9ff7f52bd202

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-002 закрыт: до `note_spawn` (`server.py:6813`, `server.py:5583`) локальный дедлайн и уход клиента возвращают `attempt_done(False, False)` (`server.py:2540-2552`, `server.py:6778`, `server.py:6794`, `server.py:5545`, `server.py:5563`), резерв лимитера возвращается, JSON-ветка `state=="timeout"` отдаёт 502 до пустого `upstream_failed` (`server.py:7945-7964`). FU-001 и FU-002 закрыты лимитами 16 МиБ и зелёным L2 (`VER-002` 480 OK, `VER-001` 480 passed). Оракулы приёмки RW-001 (два вызова, idless, отсутствие `step.ended` → неуспех) в коде есть (`server.py:3498-3523`). Дыра в том же дренаже: после первого `tool.called` главный цикл блокируется в `_finish_serve_tool_step` (`server.py:4001-4019`), а `_drain_serve_step_usage` забирает очередь и обрабатывает только `tool_event` и `step_finish` (`server.py:3377-3401`). `reasoning`/`text`, `permission` и `form.created` за этот интервал до 1 с снимаются с очереди и пропадают. REQ-001 и REQ-012 на этом окне не выполняются.
   СОВЕТЫ (при FAIL):
   - В `_drain_serve_step_usage` (`server.py:3377-3401`) для событий той же сессии вызвать те же действия, что основной цикл: `permission` → reject+interrupt (`server.py:3940-3958`), `form.created` своей сессии → cancel+interrupt до разбора схемы (`server.py:3881-3904`), `error` → записать `result["error"]` и выйти неуспехом, `reasoning`/`text` → `on_reasoning`/`on_text` и байтовый бюджет.
   - Событие чужой сессии по-прежнему пропускать. Неподтверждённый конец шага по-прежнему `ServeProtocolError("incomplete tool step without step.ended")`.
   - Регрессия: между `session.tool.called` и `session.step.ended` приходят `session.reasoning.delta` и `permission.asked`; дельта есть в SSE и JSON, permission получает reject, `finish_reason=tool_calls` только после `step.ended`.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Ветка «между первым native-вызовом и `session.step.ended`» не покрыта: дренаж молча забирает всё, кроме инструмента и `step_finish`. Через полгода это читается как полный разбор шага, а теряется и текст модели, и запрет встроенного инструмента.
   СОВЕТЫ (при FAIL):
   - Добавить в `tests/test_realtime_reasoning.py` сценарий SSE и JSON: `tool.called` → `reasoning.delta` → `permission.asked` → `step.ended`. Ожидание: reasoning в ответе, reject permission, один tool_call, usage шага.
   - Отдельный сценарий: `tool.called` → `form.created` своей сессии без `step.ended`. Ожидание: cancel+interrupt и ошибка, без `finish_reason=tool_calls`.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Правка локальная в уже существующем дренаже, новых зависимостей нет (`pyproject.toml` `dependencies = []`), выкат и kill-switch `run` не меняются. L2 на кандидате зелёный (`code-gate.json` status=PASS, 480 passed). VER-006/VER-007 законно `DEFERRED_L3`.

4. РИСКИ: VERDICT=FAIL
   WHY=L2 red→green и полный набор зелёные: `L2-RED-sensitivity` rc=1 на `origin/dev`, `VER-001`/`VER-005`/`AC-023` rc=0, frozen `_run_env` sha256 `1c51b28f…` совпал, diff ровно из трёх файлов конверта. Дыра безопасности и потери данных тестами не поймана: `permission.asked` в окне дренажа не получает reject, дельта размышления не доходит до клиента. Это прямой обход изоляции встроенных инструментов (REQ-012) на новом транспорте.
   СОВЕТЫ (при FAIL):
   - В дренаже не снимать с очереди событие, для которого нет обработчика; permission/form обрабатывать fail-closed, как в основном цикле.
   - Закрепить это регрессией из совета по ПОЛНОТЕ и прогнать её в том же L2-контуре, что `VER-005`.
   - Не ослаблять `MAX_TOTAL_SPAWNS=3` и не считать зелёный suite доказательством этой ветки: её в текущих 101 тестах нет.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Добор веток в `_drain_serve_step_usage` достаточен. Переписывать `_serve_one_attempt` или транспорт не требуется. Раздувания относительно согласованного окна 1 с нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Публичные маршруты `/health`, `/v1/models`, `/v1/chat/completions` и поле `transport=opencode-zen-cli` не добавлены и не переименованы (`server.py:8123-8137`). Замороженные `_run_env`, `_stream_google_sse`, `_execute_google_once` побайтово совпали с `origin/dev` (VER-004). Внешних runtime-зависимостей нет. Нарушение REQ-001/REQ-012 учтено в корректности, это не слом слоёв и не выход за три файла конверта.

F-001
priority: blocking
file: bridges/opencode-zen-bridge/server.py:3373, bridges/opencode-zen-bridge/server.py:3377, bridges/opencode-zen-bridge/server.py:3392, bridges/opencode-zen-bridge/server.py:3401, bridges/opencode-zen-bridge/server.py:4001, bridges/opencode-zen-bridge/server.py:4008
rule: REQ-001, REQ-012, RW-001 blast-radius (окно дочитывания шага)
evidence: после `on_tool` цикл входит в `_finish_serve_tool_step` и единственный читатель очереди — `_drain_serve_step_usage`. Там после фильтра сессии обрабатываются только `mapped[0] == "tool_event"` и `mapped[0] == "step_finish"`; иное событие не возвращается в очередь и не передаётся в `on_reasoning`/`on_text` и не проходит reject/cancel, которые основной цикл делает для `permission` (`server.py:3940-3958`) и `form.created` (`server.py:3881-3904`).
expected: в том же окне `min(1.0, deadline-now)` доставлять reasoning/text той же сессии, на `permission`/`form.created` выполнять тот же fail-closed, на `error` завершать попытку ошибкой; `step.ended` по-прежнему обязателен для `terminal=tool_calls`.
check: SSE и JSON, последовательность `tool.called` → `reasoning.delta` → `permission.asked` → `step.ended`: дельта видна клиенту, в FakeServe записан reject, финальный `finish_reason=tool_calls` один, usage шага сохранён. Вторая последовательность с `form.created` без `step.ended`: нет `finish_reason=tool_calls`, в логе `invalid_serve_event` или security failure, есть cancel.

SUB Корректность/логика: FAIL — server.py:3377-3401 отбрасывает reasoning/text и permission между tool.called и step.ended (REQ-001, REQ-012)
SUB Корректность/граничные условия: FAIL — server.py:4008 окно `_STEP_DRAIN_WINDOW_S=1.0` является единственным потребителем очереди на границе шага
SUB Корректность/обработка ошибок: FAIL — server.py:3377-3401 не вызывает reject/cancel для permission и form, в отличие от server.py:3940 и server.py:3881
SUB Полнота/покрытие AC: PASS — REQ-002..REQ-020 и AC-026 закрыты L2: red rc=1, green VER-001/VER-005 rc=0; дыра AC на границе шага вынесена в пропущенные ветки
SUB Полнота/пропущенные ветки: FAIL — нет ветки дренажа для reasoning/permission/form/error (server.py:3377-3401); оракул c9_rw001 эту очередь не шлёт
SUB Реализуемость/общее: PASS — правка в одном хелпере, stdlib, kill-switch run сохранён, VER-006/VER-007 DEFERRED_L3 по конверту
SUB Риски/безопасность: FAIL — REQ-012: permission.asked в дренаже не получает reject (server.py:3377 против server.py:3940)
SUB Риски/данные: FAIL — REQ-001: reasoning/text той же сессии в окне дренажа удаляются из очереди (server.py:3377-3401)
SUB Риски/прод: PASS — при отказе до барьера доставки остаётся fallback на run; лимиты очереди 16 МиБ и cleanup группы на месте (server.py:3450, server.py:4087)
SUB Риски/regression red→green: PASS — l2-red.log rc=1 (AC-026: 1 чанк на origin/dev), l2-green-ver005 rc=0 (101 passed)
SUB Риски/Full Suite (L2): PASS — VER-001 480 passed, VER-002 Ran 480 OK, AC-023 reversed rc=0 (execution-evidence.md)
SUB Риски/scope-diff: PASS — candidate-manifest ровно server.py, test_realtime_reasoning.py, test_step_interruption.py; frozen sha256 совпал
SUB Альтернативы/общее: PASS — достаточно дописать обработчики в `_drain_serve_step_usage`, без смены транспорта
SUB Соответствие контексту/общее: PASS — публичный HTTP-контракт и frozen Google/`_run_env` не изменены (server.py:8123, VER-004)

[sweep] Отдельный F-блок на ранний `on_tool` до `step.ended` не заведён: клиентский контракт исполнения — `finish_reason=tool_calls`, неуспешный путь его не ставит (`server.py:3521` только после подтверждения), оракул eof/window это проверяет.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

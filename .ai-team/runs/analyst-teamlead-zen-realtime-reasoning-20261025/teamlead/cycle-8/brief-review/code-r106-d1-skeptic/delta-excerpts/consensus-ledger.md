# Черновой леджер совещания Совета Тимлидов по коду (цикл 8, после R1 r99, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `4` (`F-001..F-004`: `skeptic` `нет (0 находок, ACCEPT)`, `realist` `F-001..F-004`, `visionary` `нет (0 находок, PASS)`).
- Открытых blocking (`OPEN_BLOCKING`): `4`; открытых non-blocking: `0`.

### F-001
- origin: realist · R1 · realist-F-001
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> F-001
> priority: blocking
> locations: bridges/opencode-zen-bridge/server.py:3355, bridges/opencode-zen-bridge/server.py:3371, bridges/opencode-zen-bridge/server.py:3885, bridges/opencode-zen-bridge/server.py:3893
> rule: REQ-011, REQ-014; feature.md §2 и §5 — захват потока с независимым сигналом полноты.
> evidence: После первого native-вызова устанавливается `terminal="tool_calls"`; дочитывание ограничено `time.monotonic() + 0.15`. Истечение окна возвращает управление без подтверждения `session.step.ended`. Дополнительные tool-события обрабатываются только при истинном `assistant_message_id`. Поэтому второй вызов того же шага, пришедший через 200 мс, теряется; при отсутствии ID сообщения он игнорируется даже внутри окна. Ответ при этом может завершиться успешно с неполным набором инструментов и оценочным usage.
> expected_fix: Сохранить ограниченное ожидание, но различать подтверждённое завершение шага и истечение окна. Получать идентификатор закрываемого сообщения либо завершать неоднозначный сценарий явно; не объявлять неполный набор успешным.
> verification: SSE и JSON: два вызова одного шага с задержкой второго более 150 мс; отдельный сценарий без `assistantMessageID`; проверить полный набор, usage и исключение следующего шага.

### F-002
- origin: realist · R1 · realist-F-002
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> F-002 [pre-existing]
> priority: blocking
> locations: bridges/opencode-zen-bridge/server.py:1580, bridges/opencode-zen-bridge/server.py:3580, bridges/opencode-zen-bridge/server.py:3593, bridges/opencode-zen-bridge/server.py:3850, bridges/opencode-zen-bridge/server.py:3862
> rule: HL-ENV-01, C-MULT-I2 — замыкание памяти и ограничение очередей.
> evidence: Очередь ограничена 4096 объектами, отдельная SSE-строка — 1 МиБ. Только полезная нагрузка заполненной очереди допускает около 4 ГиБ на попытку до накладных расходов Python. Это превышает весь бюджет 2 ГиБ из HL-ENV; шесть слотов увеличивают предел. Накопители reasoning/text дополнительно сохраняют обработанный вывод. Расчёт `64 MiB + 1152 MiB` эту память не учитывает.
> expected_fix: Ввести общий байтовый бюджет очереди и накопленного ответа, согласовать его с числом слотов и HL-ENV; при превышении останавливать попытку с явной причиной и cleanup.
> verification: Детерминированный тест заполнения крупными событиями проверяет точную байтовую границу, отсутствие дальнейшего накопления и освобождение ресурсов.

### F-003
- origin: realist · R1 · realist-F-003
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> F-003 [sweep]
> priority: blocking
> locations: bridges/opencode-zen-bridge/server.py:5438, bridges/opencode-zen-bridge/server.py:7749, bridges/opencode-zen-bridge/server.py:7821, bridges/opencode-zen-bridge/server.py:7942
> rule: REQ-016 / AC-021; O-EXIT/v1 — точная причина раннего отказа.
> evidence: При исчерпании дедлайна перед legacy spawn возвращается `state="timeout"`. `_serve_json` отдельно обрабатывает три фазовых watchdog, но общий `timeout` попадает в пустой результат и заменяется на `upstream_failed`. Это подтверждено приложенным `l2-green-ver002-unittest.log`: сценарий FU-002 завершается с `total_spawns=0`, `duration_s=0.09`, `exit_reason=upstream_failed`, хотя причиной был локальный дедлайн.
> expected_fix: Обрабатывать общий `timeout` терминально до разбора результата, сохранять `exit_reason=timeout`, прежний HTTP 502 и нейтральный учёт Circuit Breaker.
> verification: Расширить FU-002 проверкой реального O-EXIT sink: ровно одно событие с `timeout`, ноль запусков, ноль отказов breaker и возвращённый резерв.

### F-004
- origin: realist · R1 · realist-F-004
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> F-004 [pre-existing]
> priority: blocking
> locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:411, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:881, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2423, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2754, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2825, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2983, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3277, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3404
> rule: agents/testing.md — прямой запрет новых `unittest.TestCase`, `setUp`, `tearDown`.
> evidence: Новый тестовый модуль построен на `unittest.TestCase`, включая наследников `_AttemptCase`. Запуск этих классов через pytest не устраняет нарушение. Ограничение stdlib рантайма не мешает использовать pytest из существующих dev-зависимостей.
> expected_fix: Перенести новый модуль на pytest-функции и fixtures с гарантированным teardown; сохранить все поведенческие оракулы и изоляцию окружения.
> verification: Полный pytest и обратный порядок остаются зелёными; AC-026 сохраняет поведенческий RED на baseline. Согласовать verification-surface, поскольку unittest-discover после переноса больше не исполняет этот модуль.

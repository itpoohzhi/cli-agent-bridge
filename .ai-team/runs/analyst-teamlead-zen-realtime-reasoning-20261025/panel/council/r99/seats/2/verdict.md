PANEL-NONCE: b2896eeb90a0f629
ARTIFACT-SHA256: 1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8

Общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком в приложенном тексте до `<!-- КАНОН-КОНЕЦ -->`. Проектные файлы правил с диска пока не прочитаны; использую приложенные стандарты. Проверяю закрытие замечаний и ограничения ресурсов; тесты судья не запускает.

RW-001 и RW-002 закрыты кодом и регрессиями. Для RW-003 разделены общий дедлайн и фазовые отказы. В полном diff проверяю ещё два практических ограничения: полноту инструментального шага в окне 150 мс и верхнюю границу памяти SSE-очереди. L3 остаётся законно отложенным до ACCEPT.

PANEL-NONCE: b2896eeb90a0f629
ARTIFACT-SHA256: 1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8

Verify-Fixed: RW-001 — PASS; RW-002 — PASS; RW-003 — PASS для обеих serve-веток. FU-002 — PASS по отмене запуска и возврату резерва; FU-003 — PASS: приложенный RED достигает сокетного AssertionError AC-026. FU-001 закрыт для немедленно поступивших событий с `assistantMessageID`, но полнота инструментального шага остаётся ограниченной — F-001.

F-001
priority: blocking
locations: bridges/opencode-zen-bridge/server.py:3355, bridges/opencode-zen-bridge/server.py:3371, bridges/opencode-zen-bridge/server.py:3885, bridges/opencode-zen-bridge/server.py:3893
rule: REQ-011, REQ-014; feature.md §2 и §5 — захват потока с независимым сигналом полноты.
evidence: После первого native-вызова устанавливается `terminal="tool_calls"`; дочитывание ограничено `time.monotonic() + 0.15`. Истечение окна возвращает управление без подтверждения `session.step.ended`. Дополнительные tool-события обрабатываются только при истинном `assistant_message_id`. Поэтому второй вызов того же шага, пришедший через 200 мс, теряется; при отсутствии ID сообщения он игнорируется даже внутри окна. Ответ при этом может завершиться успешно с неполным набором инструментов и оценочным usage.
expected_fix: Сохранить ограниченное ожидание, но различать подтверждённое завершение шага и истечение окна. Получать идентификатор закрываемого сообщения либо завершать неоднозначный сценарий явно; не объявлять неполный набор успешным.
verification: SSE и JSON: два вызова одного шага с задержкой второго более 150 мс; отдельный сценарий без `assistantMessageID`; проверить полный набор, usage и исключение следующего шага.

F-002 [pre-existing]
priority: blocking
locations: bridges/opencode-zen-bridge/server.py:1580, bridges/opencode-zen-bridge/server.py:3580, bridges/opencode-zen-bridge/server.py:3593, bridges/opencode-zen-bridge/server.py:3850, bridges/opencode-zen-bridge/server.py:3862
rule: HL-ENV-01, C-MULT-I2 — замыкание памяти и ограничение очередей.
evidence: Очередь ограничена 4096 объектами, отдельная SSE-строка — 1 МиБ. Только полезная нагрузка заполненной очереди допускает около 4 ГиБ на попытку до накладных расходов Python. Это превышает весь бюджет 2 ГиБ из HL-ENV; шесть слотов увеличивают предел. Накопители reasoning/text дополнительно сохраняют обработанный вывод. Расчёт `64 MiB + 1152 MiB` эту память не учитывает.
expected_fix: Ввести общий байтовый бюджет очереди и накопленного ответа, согласовать его с числом слотов и HL-ENV; при превышении останавливать попытку с явной причиной и cleanup.
verification: Детерминированный тест заполнения крупными событиями проверяет точную байтовую границу, отсутствие дальнейшего накопления и освобождение ресурсов.

F-003 [sweep]
priority: blocking
locations: bridges/opencode-zen-bridge/server.py:5438, bridges/opencode-zen-bridge/server.py:7749, bridges/opencode-zen-bridge/server.py:7821, bridges/opencode-zen-bridge/server.py:7942
rule: REQ-016 / AC-021; O-EXIT/v1 — точная причина раннего отказа.
evidence: При исчерпании дедлайна перед legacy spawn возвращается `state="timeout"`. `_serve_json` отдельно обрабатывает три фазовых watchdog, но общий `timeout` попадает в пустой результат и заменяется на `upstream_failed`. Это подтверждено приложенным `l2-green-ver002-unittest.log`: сценарий FU-002 завершается с `total_spawns=0`, `duration_s=0.09`, `exit_reason=upstream_failed`, хотя причиной был локальный дедлайн.
expected_fix: Обрабатывать общий `timeout` терминально до разбора результата, сохранять `exit_reason=timeout`, прежний HTTP 502 и нейтральный учёт Circuit Breaker.
verification: Расширить FU-002 проверкой реального O-EXIT sink: ровно одно событие с `timeout`, ноль запусков, ноль отказов breaker и возвращённый резерв.

F-004 [pre-existing]
priority: blocking
locations: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:411, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:881, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2423, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2754, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2825, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2983, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3277, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3404
rule: agents/testing.md — прямой запрет новых `unittest.TestCase`, `setUp`, `tearDown`.
evidence: Новый тестовый модуль построен на `unittest.TestCase`, включая наследников `_AttemptCase`. Запуск этих классов через pytest не устраняет нарушение. Ограничение stdlib рантайма не мешает использовать pytest из существующих dev-зависимостей.
expected_fix: Перенести новый модуль на pytest-функции и fixtures с гарантированным teardown; сохранить все поведенческие оракулы и изоляцию окружения.
verification: Полный pytest и обратный порядок остаются зелёными; AC-026 сохраняет поведенческий RED на baseline. Согласовать verification-surface, поскольку unittest-discover после переноса больше не исполняет этот модуль.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 и RW-002 исправлены; обнаружена потеря точной причины локального дедлайна в legacy JSON — F-003.
   СОВЕТЫ (при FAIL): выполнить F-003 и проверить терминальное событие в журнале.

   SUB Корректность/логика: PASS — ранний 429/503 повторяется через serve при сохранении запрета run (`server.py:6132`; регрессия `tests/test_realtime_reasoning.py:934`).
   SUB Корректность/граничные условия: FAIL — поздний второй native-вызов и отсутствие ID сообщения приводят к неполному результату, F-001 (`server.py:3371`, `server.py:3893`).
   SUB Корректность/обработка ошибок: FAIL — локальный timeout классифицируется как upstream_failed, F-003 (`server.py:7942`; сырой лог VER-002).

2. ПОЛНОТА: VERDICT=FAIL
   WHY=FU-001 подтверждён только для событий, укладывающихся в окно; независимый сигнал завершения шага не обязателен. Остальные требования имеют реализацию и L2-свидетельства; REQ-019 / AC-025 законно отложены.
   СОВЕТЫ (при FAIL): выполнить F-001; добавить проверки задержанного завершения и отсутствующего ID сообщения.

   SUB Полнота/покрытие AC: FAIL — AC-016/AC-019 не доказывают сохранение полного позднего инструментального шага, F-001 (`server.py:3893`; тест `test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded`).
   SUB Полнота/пропущенные ветки: FAIL — без `assistantMessageID` drain не обрабатывает дополнительные tool-события, F-001 (`server.py:3371`).

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Транспорт практически доступен: OpenCode v2.1.2, локальная авторизация, ротация прокси и in-memory DB подтверждены. Однако допустимая память очередей не помещается в заявленный бюджет. После исправлений остаются выкатка с откатом и живой L3; подтверждённой оценки срока этого этапа пакет не содержит.
   СОВЕТЫ (при FAIL): выполнить F-002, пересчитать память для максимального параллелизма, затем пройти H0..H9 и VER-006/VER-007.

   SUB Реализуемость/общее: FAIL — допустимая очередь одной попытки превышает бюджет всего процесса, F-002 (`server.py:1580`, `server.py:3580`; HL-ENV-01).

4. РИСКИ: VERDICT=FAIL
   WHY=Clean-room Full Suite и статический гейт подтверждены. Они не закрывают выявленные риски потери вызовов и превышения памяти. Отсрочку живой проверки не считаю дефектом данного pre-ACCEPT этапа.
   СОВЕТЫ (при FAIL): выполнить F-001/F-002; после изменений повторить L2 и сохранить L3 обязательным условием открытия MR.

   SUB Риски/безопасность: PASS — случайный пароль, loopback, ограниченное env, reject/cancel и маскирование ошибок реализованы (`server.py:1864`; REQ-012, REQ-015, VER-005).
   SUB Риски/данные: FAIL — возможен успешный ответ с потерянными native-вызовами и usage, F-001 (`server.py:3355`, `server.py:3893`).
   SUB Риски/прод: FAIL — ограничение количества событий не обеспечивает бюджет памяти, F-002 (`server.py:3580`; HL-ENV-01).
   SUB Риски/regression red→green: PASS — AC-026 на origin/dev достигает `AssertionError: 1 not greater than or equal to 5`; кандидат зелёный (`execution-evidence.md`, L2-RED и VER-005).
   SUB Риски/Full Suite (L2): PASS — 478 тестов компонента, 894 теста корневого набора и обратный порядок зелёные; basedpyright: 0 ошибок (`execution-evidence.md`, VER-001..004, AC-023).
   SUB Риски/scope-diff: PASS — ровно три разрешённых файла; frozen-функции совпадают побайтно (`candidate-manifest.json`; VER-004).

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve с резервным run оправдан подтверждёнными ограничениями CLI и необходимостью ротации IP. Переписывать архитектуру для исправлений не требуется.

   SUB Альтернативы/общее: PASS — общий демон осложняет ротацию, прямой Zen HTTP не доказан; выбранный транспорт имеет рабочий прецедент (`handoff-architect.md` §4; REQ-003/REQ-013).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Публичные HTTP/SSE-границы и Google-direct сохранены; новые runtime-зависимости отсутствуют. Новый тестовый модуль нарушает прямо приложенное правило testing.md — F-004.
   СОВЕТЫ (при FAIL): выполнить F-004, сохранив оракулы; обновить свидетельства проверок после переноса.

   SUB Соответствие контексту/общее: FAIL — новый модуль использует запрещённый TestCase lifecycle, F-004 (`tests/test_realtime_reasoning.py:411`, `:881`, `:2423`, `:2754`, `:2825`, `:2983`, `:3277`, `:3404`; agents/testing.md).

Self-sweep: повторно проверены все 14 подкатегорий; добавлен F-003. REQ-001..REQ-020 и AC-001..AC-026 сопоставлены с кодом и свидетельствами; исключения перечислены выше. Non-Goals и Forbidden Scope по предоставленному diff соблюдены. Тесты судьёй не запускались.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

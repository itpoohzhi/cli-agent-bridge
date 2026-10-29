# Stage 2 Architect — agy-universal-image-fallback-20261029

Архитектурный кандидат сформирован. Механические проверки схемы/целостности прошли; продуктовая реализация, независимая архитектурная панель и production-приёмка не выполнялись.

## Артефакты

- `~/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/plans/architect-01.json` — завершённый role plan, schema1.0, RP01..04 DONE; SHA256 `4be065fb9f0cf884fbb8ee3f5c2810403d1f0b02cfa9e5d5e2791786741f1176`.
- `~/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/architecture/architecture-packet.json` — AP/v1 (schema_version1.0), AD001..005; SHA256 `f6c7a59500b8ece3b756c115b82eea5fd6de42de2825a7ed93b34345b4c49e6b`.
- `~/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/teamlead/verification-surface.json` — VER001..010, точные исполняемые команды, владельцы Verifier/Teamlead, идентичны встроенной frozen surface Packet.
- `~/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/task.json` — исходный task envelope отсутствовал, создан минимальный с architecture_gate; allowed_files только server/test, forbidden_paths, хеши packet/surface/protected_paths и contract_hash `7b28fc98c0fb08836e50a3c4d4c3753c5795f8c9c2ea9cc03051ebb61afabf96`.
- `~/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/receipts/arch-gate.json` — фактическая квитанция механического gate, status PASS.
- `~/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/architect/validation-results.json` — точные argv/stdout/stderr/exit_code четырёх проверок; отдельные stdout/stderr logs рядом.
- `~/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/fingerprints/projection-proof.json` — воспроизводимое обоснование исключения разрешённого каталога прогонов из ОБОИХ исходных fingerprints; originals сохранены.
- Дополнительные служебные файлы только внутри этого run: `plans/architect-01.initial.json`, `fingerprints/architect-before.product.json`, `fingerprints/architect-after.product.json`, `architect/build_packet.py` (генератор run JSON, не продуктовая реализация), этот summary.

## Содержание решения

AD001: независимый IMAGE_FALLBACK_ENABLED, env AGY_IMAGE_FALLBACK_ENABLED, strict boolean JSON/defaultfalse/TTL1s/reset в _reset_sqlite_guards_for_tests. Четыре состояния universal/input, полный safety validator, optimistic admission любого catalog model/валидного effort без proof/SHA gate. Оба production-флага должны стать true на release; Stage2 runtime/config не менял.

AD002: classification type+payload keys ДО text, все указанные image/audio/video/file/document/inlineData/fileData варианты и snake_case, dict-content, несерилизация неизвестных объектов, placeholders и fixed-point normalization. Предвычисленный ctx.stripped_full_prompt, очистка prompt И full_prompt; непустые media-only сообщения. Снятые media никогда не возвращаются через hot/cold full history.

AD003: collect -> post-slot/spool -> runtime attempt1. Runtime guard находится перед ранним hot continue и общим retry, учитывает реально доставленные text/tool_calls/SSE reasoning. Cleanup до text constructor; CAS инвалидирует только ожидаемый CID, _cid_release(cid,turn_id) снимает только собственное владение. Полный cold text context и отсутствие прежнего --resume/add-dir. Одна text попытка2 даже при пустом generic bucket через ограниченный request reserve, со штатным jitter; никогда третья.

AD004: fleet неизменен. `/health.images` и `/v1/models.images` остаются boolean; effective true для всех catalog при universal+input. Отдельный additive image_fallback object объясняет optimistic policy/staging/limits/model list. Safe bounded _log_token поверх существующего _log, точный event format без auth/payload/URL/prompt/path.

AD005: append-only UniversalImageFallbackTests test_uf01_..test_uf10_; весь исходный test blob неизменен. Трассировка SCN-uf01..10/B01..02/R01..02/I01, REQ01..06, CON01..06, INV01..12, RISK01..08, ASSUMP01..02 и AC01..08. VER006 проверяет0deleted относительно обоих baseline, точный prefix и запускает test_images_strict.py. VER007 проверяет все40 прежних ID+10uf с asserts; VER003 выполняет Universal+Image*+AcceptanceOracleTests, VER005 полный suite. Эти будущие продуктовые команды Stage2 не запускал.

## Фактические результаты

- validate_role_plan.py initial --phase before: exit0.
- validate_role_plan.py final --phase after: exit0.
- validate_architecture_packet.py --phase approved: exit0.
- validate_arch_gate.py с фактическим актуальным CLI: exit0, stdout `PASS: ARCH_GATE; receipt=…`.
- Все10 frozen commands разобраны как shell argv, Python -c тела прошли ast.parse; каждый command обёрнут run-guarded. Это проверка синтаксиса команд, НЕ выполнение будущих uf-тестов.
- Связанные packet/role_plan/verification_surface/protected_paths/contract_hash проверены; отрицательные in-memory mutants (неверный role hash, Coder как владелец VER, неизвестные risk/quality VER refs) отвергнуты настоящим Packet validator.
- Вне `.ai-team/runs/` совпали все168 файлов, включая неизменные5 Stage1 inputs и product/test. Product fingerprint `ba4cbc096d7c16f55db824df6cd3250e42d2d29a95815ef5e24600a5e04a2941` совпал с проекциями обоих ORIGINAL before manifests.

## Отличия брифа от фактической среды

1. Путь teamlead-with-architect и валидаторов содержит `ai-sdlc/universal/`. Коротких путей из брифа нет. Ничего в каталоге skills не создавалось и не исправлялось.
2. Актуальный role validator принимает позиционный PLAN и --phase before|after. Аргументы --plan/--before-fingerprint/--repo отсутствуют. Предоставленный architect-01.before.json — fingerprint schema2.0, а не role plan; он сохранён. Создан отдельный initial role plan и сверена продуктовая проекция предоставленного fingerprint.
3. Актуальный arch validator требует --packet/--run-dir/--role-plan/--repo-root/--fingerprint-before/--fingerprint-after/--task/--receipt. Он печатает PASS: ARCH_GATE, а не ARCH_GATE_VALID. Точный вывод сохранён без wrapper или подмены.
4. Переданные fingerprints включают `.ai-team/runs/`, где родитель пишет логи. Проверка напрямую этих manifests отвергла бы разрешённые артефакты. Из оригинальных manifests исключён ТОЛЬКО разрешённый run-каталог, digest пересчитан; product baseline НЕ переснимался. Исходные before-файлы сохранены, дельта product0.
5. Test baseline фактически6008 строк/249933байта, а не6009 строк. Сохраняется ВСЯ исходная последовательность байтов, включая main guard; никакие строки не заменяются.
6. health.images в реальном коде — boolean; поэтому fallback_enabled добавляется в отдельный image_fallback, а не меняет тип старого поля. Проверены test_ao01, test_ao06_health и ao10.
7. _cid_release принимает(cid,turn_id); _run_once не имеет local conv_id. Новый текстовый Run получает conversation_id пустым для нового CLI разговора, а не фиктивный UUID в --resume. В коде нет log.info/_log_token: sanitizer новый, sink остаётся штатный _log.

## Границы приёмки

`status=APPROVED` в AP — финализированный автором дизайн для структурного механического gate. Это НЕ ACCEPT коллегии и НЕ доказательство ресурcной готовности. Обязательная внешняя3семейная architecture panel ещё не запускалась; Coder запрещён до её валидного panel-proof. Независимый panel vote или receipt здесь не фабриковался.

Все46 HL-ENV полей перечислены с источниками/unknown,21 стоп-код остаются NOT_PROVEN. Отсутствуют контрактные/измеренные production quota,RPS,p99,CPU/RSS/FD/ports; memory closure и нагрузочная приёмка BLOCKED_UNMEASURED_PRODUCTION. Они не объявлены PASS и не сняты как техдолг. W в каноническом envelope — процессы, а не4 CLI slots; Stage1 неоднозначность исправлена явным unknown. Перед downstream утверждением resource gates требуется реальное доказательство или валидная transitive N/A; механический schema validator эти измерения не проверяет.

Owner reserve — явное исключение для media degradation: generic строгий budget сохраняется, но all-image-fail traffic может дать2N CLI executions. Нельзя переносить на него прежнюю общую формулу0.2N+3. Это включено в production capacity блокеры.

ВОПРОСЫ ВЛАДЕЛЬЦУ: ASSUMP01 —200 только при настоящем успешном text backend, независимые ошибки не маскируются; ASSUMP02 — позитивный decodable raster corpus без нового pixel decoder. Оба явно continuable. Для обещаний production capacity нужны реальные SLA/квоты/нагрузочный профиль; неизвестные значения не угаданы.

ПРОВЕРЕНО ЛЁГКИМ: role/packet/ARCH_GATE validators exit0, хеши/command syntax/negative schema oracles и неизменность всех файлов вне прогонов.
ПРОВЕРЕНО ТЯЖЁЛЫМ: не выполнялось — это Stage2 design-only, без продуктовой правки и без запуска production request.
НЕ ПРОВЕРЕНО: реализация/новые uf-тесты/full product suite, внешние architecture/code panels, production flags/deploy, существующий DSH image→text fallback→history turn, нагрузочные21гейты. Продуктовая фича не сдана.

Фон: установок/сборок/продуктовых тестов/LLM транспортов/сетевых вызовов в Stage2 не запускалось. Выполнены только мгновенные локальные чтения и валидаторы. Push/MR/merge и записи в Jira/Outline/KB не выполнялись: это ограниченный подэтап с записью только run-artifacts.

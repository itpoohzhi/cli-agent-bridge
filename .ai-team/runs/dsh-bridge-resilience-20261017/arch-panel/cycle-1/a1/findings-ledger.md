# Леджер замечаний Архитектурного Совета (Arch Panel r1)

### F-001
- source: claude-sonnet-5-5-high (k=1, Скептик)
- file: architecture-packet.json#AD-001
- line_hint: architecture-packet.json#contracts
- priority: blocking
- criterion: contracts_and_invariants
- text: Отсутствует явный эндпоинт отмены хода (POST /v1/turns/<turn_id>/cancel или DELETE /v1/turns/<turn_id>). При закрытии вкладки или нажатии Stop в DSH ход переходит в RUNNING_DETACHED и продолжает выполняться в фоне до 3600 с, удерживая семафор MAX_CONCURRENT=2 и блокируя мост ошибкой 503 bridge busy.

### F-002
- source: claude-sonnet-5-5-high (k=1, Скептик), muse-wonder-full-1.0 (k=3, Визионер)
- file: architecture-packet.json#security
- line_hint: architecture-packet.json#threat_model
- priority: blocking
- criterion: security_and_secrets
- text: threat_model.required ошибочно указан как false при добавлении сетевых эндпоинтов GET /v1/turns/<turn_id>(/stream), отдающих reasoning, content и tool_calls. Не зафиксирована валидация turn_id против path traversal (regex ^[a-zA-Z0-9_-]{1,64}$), привязка к клиенту/Bearer-токену и права 0600 на сохраняемые файлы состояния.

### F-003
- source: claude-sonnet-5-5-high (k=1, Скептик), muse-wonder-full-1.0 (k=3, Визионер)
- file: architecture-packet.json#contracts
- line_hint: architecture-packet.json#turn_key
- priority: blocking
- criterion: contracts_and_invariants
- text: Неоднозначный состав ключа дедупликации turn_key. Необходимо явно зафиксировать состав turn_key (model_id, session_id/rid, digest истории сообщений, workspace), чтобы избежать ошибочного подключения к завершённому ходу при перегенерации или новом запросе.

### F-004
- source: claude-sonnet-5-5-high (k=1, Скептик)
- file: architecture-packet.json#risks
- line_hint: architecture-packet.json#RISK-004
- priority: blocking
- criterion: risks_and_degradation
- text: Поведение при аварийном завершении и рестарте: при SIGKILL процесса моста потомки с start_new_session=True остаются сиротами. Необходим механизм очистки/уборки сирот (orphan reaper) на старте хаба по сохранённому children.json.

### F-005
- source: claude-sonnet-5-5-high (k=1, Скептик)
- file: architecture-packet.json#AD-003
- line_hint: arch-spec.md#6.2
- priority: blocking
- criterion: risks_and_degradation
- text: Утечка активности в ProcessWatchdog: спящий дочерний процесс (sleep, bash в ожидании stdin) сбрасывает idle_timeout до абсолютного дедлайна 3600 с. Watchdog должен проверять реальное приращение CPU-времени (cputime) и протокольные события.

### F-006
- source: claude-sonnet-5-5-high (k=1, Скептик), muse-wonder-full-1.0 (k=3, Визионер)
- file: architecture-packet.json#contracts
- line_hint: arch-spec.md#4.2
- priority: blocking
- criterion: contracts_and_invariants
- text: Не определена семантика gap replay при переполнении буфера 10 МиБ: если клиент запрашивает from_seq, который уже вытеснен из кольцевого буфера, сервер должен возвращать явную ошибку 410 Gone / GAP_DETECTED со ссылкой на актуальный seq, а не молча пропускать события.

### F-007
- source: claude-sonnet-5-5-high (k=1, Скептик)
- file: architecture-packet.json#contracts
- line_hint: arch-spec.md#5.3
- priority: blocking
- criterion: risks_and_degradation
- text: Сигналы и drain: обработчик SIGTERM/SIGINT в основном потоке не должен выполнять блокирующие вызовы или захватывать locks во избежание дедлока с serve_forever. Обработчик обязан устанавливать threading.Event, а процедура shutdown/drain должна инициироваться в отдельном потоке.

### F-008
- source: claude-sonnet-5-5-high (k=1, Скептик), muse-wonder-full-1.0 (k=3, Визионер)
- file: architecture-packet.json#proposals
- line_hint: arch-spec.md#2.1
- priority: blocking
- criterion: implementation_and_test_plan
- text: Поставка и импорт core.* для bridges/muse-bridge/server.py: зафиксировать явный механизм доступности общего пакета core (через PYTHONPATH, pip install -e или симлинк в ~/.dsh/bridges/muse-bridge/core).

### F-009
- source: claude-sonnet-5-5-high (k=1, Скептик)
- file: architecture-packet.json#implementation_and_test_plan
- line_hint: architecture-packet.json#rollout
- priority: blocking
- criterion: implementation_and_test_plan
- text: Отсутствие фичефлагов для безопасного отката: добавить переменные окружения DSH_BRIDGE_DETACHED_ENABLED, DSH_BRIDGE_WATCHDOG_ENABLED, DSH_BRIDGE_DRAIN_ENABLED с возможностью отключения при регрессии.

### F-010
- source: claude-sonnet-5-5-high (k=1, Скептик), muse-wonder-full-1.0 (k=3, Визионер)
- file: architecture-packet.json#proposals
- line_hint: architecture-packet.json#AD-001
- priority: non_blocking
- criterion: problem_and_boundaries
- text: Рассинхронизация нумерации архитектурных решений AD-001..AD-005 между брифом Совета и пакетом архитектора: выровнять сопоставление REQ -> AD -> VER.

### F-011
- source: muse-wonder-full-1.0 (k=3, Визионер)
- file: architecture-packet.json#contracts
- line_hint: architecture-packet.json#BufferedTurnEvent
- priority: blocking
- criterion: contracts_and_invariants
- text: Закрытый перечень kind в BufferedTurnEvent: разрешить passthrough неизвестных видов событий и добавить явное поле schema_version: "1.0" для снимков состояния на диске.

### F-012
- source: muse-wonder-full-1.0 (k=3, Визионер)
- file: architecture-packet.json#contracts
- line_hint: arch-spec.md#3.2
- priority: non_blocking
- criterion: contracts_and_invariants
- text: Стандартизация заголовков и SSE: зафиксировать единый HTTP-заголовок X-Turn-Id и передачу id в каждом SSE-событии для совместимости со стандартным Last-Event-ID.

### F-013
- source: muse-wonder-full-1.0 (k=3, Визионер)
- file: architecture-packet.json#problem_and_boundaries
- line_hint: arch-spec.md#2.2
- priority: non_blocking
- criterion: problem_and_boundaries
- text: Зависимость TurnSessionManager от core.tool_emulation: устранить прямую связь общего менеджера сессий от эмуляции инструментов, сохранив чистую границу абстракции.

### F-014
- source: muse-wonder-full-1.0 (k=3, Визионер)
- file: architecture-packet.json#risks
- line_hint: arch-spec.md#6.3
- priority: non_blocking
- criterion: risks_and_degradation
- text: Поведение при сбое или таймауте команды ps на Darwin: специфицировать fail-closed для idle-watchdog (сброс таймера только при подтверждённой активности или fallback на протокольные события).

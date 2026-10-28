# Черновой леджер совещания Совета Тимлидов по коду (цикл 4, после R1 r30, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `13` (`F-001..F-013`: `skeptic` `0 находок (ACCEPT)`, `realist` `F-001..F-002`, `visionary` `F-003..F-013`).
- Открытых blocking (`OPEN_BLOCKING`): `11`; открытых non-blocking: `2`.

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
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3265-3266, bridges/opencode-zen-bridge/server.py:3330-3333, bridges/opencode-zen-bridge/server.py:3341-3345, bridges/opencode-zen-bridge/server.py:5512-5517, bridges/opencode-zen-bridge/server.py:5577-5584, bridges/opencode-zen-bridge/server.py:6779-6790, bridges/opencode-zen-bridge/server.py:6840-6845
> rule: RW-001 action; FALLBACK_DECISION_TABLE phase=DELIVERED event «first_event_timeout20s after headers, no valid execution SSE» action=serve_retry; REQ-009 (повторный запуск — второе исполнение prompt)
> evidence: `prompt_status["headers_at"] = time.monotonic()` пишется в `_on_headers` до чтения тела. Дальше `_delivered_now = bool(result["texts"] or result["reasonings"] or result["native_calls"])` и `result["delivered"] = _delivered_now` для 429/5xx. При ошибке тела: `if isinstance(_prompt_err, str) and not (result["texts"] or result["reasonings"] or result["native_calls"]): raise ServeUnavailable(...)`. В SSE: `except ServeUnavailable` → `if not force_serve and not delivered_any[0]: return False`. В JSON тот же `return False` по `_j_delivered`. Развилки `prompt_status` 429/5xx в SSE и JSON тоже возвращают `False` в `run`, когда `delivered` ложен.
> expected: Если `headers_at` уже есть, не бросать `ServeUnavailable` и не ставить `delivered=False`. Вернуть результат с `delivered=True` и `exit_reason` для serve-retry (429/5xx — тот же барьер). `STATUS_INITIAL` барьер не ставит. Исключение, которое всё же вышло после подтверждённого prompt, не переводит запрос на `run` и не вызывает `record_success()`.
> check: Режим `auto`, заголовки ответа prompt получены, затем обрыв тела или HTTP 429/5xx до первого токена модели. `Run.execute` и `_spawn_with_stdin` не вызываются. Клиент получает один serve-retry или терминальную SSE/502 ошибку. `record_success()` не вызывается.

### F-002
- origin: realist · R1 · realist-F-002
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> F-002
> priority: non-blocking
> criterion: ПОЛНОТА
> locations: bridges/opencode-zen-bridge/server.py:6463-6464
> rule: FU-010 (non-blocking follow-up)
> evidence: На legacy-пути после watchdog `emit_synthetic(f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n")` вызывается без `thinking_enabled`. На serve разделитель гейтится `thinking` (`server.py:5492`), периодические статусы keepalive тоже (`server.py:6228`).
> expected: Эмиссию разделителя на legacy-retry обернуть тем же `thinking_enabled`, что и `STATUS_WAITING` / `STATUS_CONTINUATION`.
> check: `reasoning_effort=off` на пути `run`, watchdog даёт retry: в SSE нет строки «Повтор попытки». MUST это не ломает; в агрегирующий FAIL не входит.

### F-003
- origin: visionary · R1 · visionary-F-001
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-001 — priority=blocking; RW-001 закрыт частично.
>    - locations: `bridges/opencode-zen-bridge/server.py:2604`, `:3266`, `:3284`, `:3345`, `:5514`, `:6789`.
>    - Правило: RW-001; монотонный барьер доставки; запрет fallback после подтверждения prompt.
>    - Evidence: `headers_at` записывается своевременно, но ветка `_prompt_err` выбрасывает `ServeUnavailable`. Исключение не переносит этот признак наружу. Обработчики SSE и JSON проверяют модельные данные и прежний барьер, а не подтверждение текущего prompt.
>    - Сценарий: prompt принят, получены HTTP 200 headers, затем соединение сброшено при чтении тела до появления модельных дельт. Ошибка возникает раньше first-event watchdog; разрешается fallback в run.
>    - Исправление: передавать подтверждение доставки в общий контекст попыток непосредственно при получении заголовков либо сохранять его в типизированном результате исключения.
>    - Проверка: HTTP-фейк подтверждает prompt и обрывает тело; в SSE и JSON `Run` не запускается, повтор остаётся serve либо завершается явной ошибкой.

### F-004
- origin: visionary · R1 · visionary-F-002
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-002 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/server.py:2604`, `:2608`, `:2617`, `:3266`, `:3280`, `:3306`, `:3324`.
>    - Правило: FALLBACK_DECISION_TABLE — HTTP 400/401/403/404/422 завершаются fail-closed без протокольного retry и инкремента ServeHealth.
>    - Evidence: callback заголовков передаёт только время. `prompt_status["status"] = st` выполняется после полного тела ответа. Если сервер уже прислал 401, но задерживает тело, основной цикл видит только `headers_at` и может вернуть `first_event_timeout`.
>    - Исправление: публиковать HTTP-статус одновременно с заголовками; терминальные 4xx классифицировать до чтения тела.
>    - Проверка: каждый из 400/401/403/404/422 с незавершающимся телом даёт один терминальный отказ, без run, serve-retry и изменения ServeHealth.

### F-005
- origin: visionary · R1 · visionary-F-003
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-003 — priority=blocking; RW-002 закрыт частично.
>    - locations: `bridges/opencode-zen-bridge/server.py:5948`, `:6121`, `:6173`, `:6179`, `:6242`.
>    - Правило: REQ-004, AC-005 — первая видимая реакция не позднее 1,0 с.
>    - Evidence: защитный таймер отменяется сразу после лимитера, а следующий срок статуса считается заново: `attempt_start + FIRST_STATUS_DELAY_S`.
>    - Сценарий: gate/limiter задержал старт примерно на 0,5 с, затем молчащий процесс запущен до срабатывания таймера 0,65 с. Таймер отменён; следующий статус возможен лишь примерно через 1,15 с плюс интервал опроса.
>    - Исправление: сохранять защитный таймер до первого видимого чанка либо использовать единый абсолютный срок первого статуса.
>    - Проверка: задержки старта по обе стороны 0,65 с, включая 0,4–0,6 с; первый статус ≤1,0 с, начальный статус ровно один.

### F-006
- origin: visionary · R1 · visionary-F-004
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-004 — priority=blocking; FU-002 закрыт частично.
>    - locations: `bridges/opencode-zen-bridge/server.py:6713`, `:6855`, `:6870`, `:6897`, `:6900`, `:6907`, `:6930`, `:6954`.
>    - Правило: REQ-010/REQ-011; сохранение канонической обработки текста и инструментов при recovery.
>    - Evidence: transient-ветка выполняет `contents.extend(texts)` до `ToolCallParser` и очистки блоков. Перед `continue` она также не обновляет `_prior_content`; это делается только в других retry-ветках.
>    - Сценарий: первая попытка отдаёт преамбулу и transient error; recovery повторяет преамбулу перед корректным tool-call. JSON сохраняет обе копии. Сырой фрагмент tool-блока из неуспешной попытки также попадает непосредственно в накопитель `content`.
>    - Исправление: пропускать частичные попытки через ту же нормализацию, что успешные; перед recovery фиксировать нормализованный префикс для дедупликации.
>    - Проверка: преамбула встречается один раз; сырой tool-блок отсутствует в `content`; итоговые вызовы инструментов совпадают с SSE.

### F-007
- origin: visionary · R1 · visionary-F-005
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-005 — priority=blocking; [pre-existing], FU-010 закрыт частично.
>    - locations: `bridges/opencode-zen-bridge/server.py:6183`, `:6463`, `:6500`, `:6521`, `:6545`, `:6554`.
>    - Правило: REQ-009, AC-014; согласованное отключение синтетических reasoning-статусов.
>    - Evidence: watchdog-retry вызывает `emit_synthetic` без проверки `thinking_enabled`. Ветви unmapped/incomplete recovery не имеют соответствующей единой точки разделителя после уже отданного reasoning.
>    - Исправление: централизовать legacy-разделитель перед фактической повторной попыткой; учитывать наличие предыдущего reasoning и thinking-флаг.
>    - Проверка: watchdog, unmapped и incomplete recovery — ровно один разделитель между попытками при thinking on; ноль синтетических разделителей при thinking off.

### F-008
- origin: visionary · R1 · visionary-F-006
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-006 — priority=non-blocking; недостаточная доказательность AC-002.
>    - locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:151`, `:597`, `:613`, `:616`.
>    - Правило: AC-002; `testing.md` — независимый эталон измеряемого свойства.
>    - Evidence: оракул измеряет интервалы клиентских чанков и сравнивает их с независимой отметкой завершения апстрима. Он не сопоставляет время прихода каждой upstream-дельты с её записью клиенту. Постоянная задержка всех дельт более 250 мс может сохранить проверяемые интервалы.
>    - Исправление: добавить идентификаторы дельт и независимые отметки upstream-arrival/client-receive; до этого обозначать AC-002 как INCONCLUSIVE.
>    - Проверка: искусственная задержка пересылки 300 мс делает проверку AC-002 красной.

### F-009
- origin: visionary · R1 · visionary-F-007
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-007 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/server.py:5578`, `:5581`, `:5600`, `:5605`, `:6087`, `:6096`, `:6841`, `:6844`, `:6854`, `:6858`, `:7058`, `:7063`.
>    - Правило: REQ-009; R-BULK-I2 — общий Token-Bucket Retry Budget; сохранение Full Jitter.
>    - Evidence: после prompt 429/5xx либо transient provider error ветка до доставки возвращает `False` раньше `attempts.allow_retry()`. Внешний handler запускает run, проверяя потолок запусков, но не разрешение на повтор.
>    - Следствие: при пустом Retry Budget запрос всё равно получает дополнительный upstream-запуск. Такой fallback не отражается как retry; это видно и в приложенном логе с `total_spawns=2 retries=0`.
>    - Исправление: перед сменой транспорта после upstream-отказа провести повтор через общий admission с бюджетом, breaker и jitter. Локальный pre-upstream отказ отделить от provider failure.
>    - Проверка: при исчерпанном бюджете 429/5xx/transient failure не запускают run; при доступном бюджете списывается один retry и применяется один backoff.

### F-010
- origin: visionary · R1 · visionary-F-008
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-008 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/server.py:2585`, `:2608`, `:2648`, `:2731`, `:2799`, `:2825`, `:3101`, `:3196`, `:3204`, `:3574`, `:3585`, `:3606`.
>    - Правило: `feature.md` — ограничение каждого звена I/O, включая cleanup; R-BULK-I1; REQ-008/AC-011.
>    - Evidence: `_spawn_serve` не принимает deadline/cancellation; handshake и listener получают новые локальные сроки. SSE subscribe использует отдельный timeout=5. Cleanup вызывает `_serve_http` без абсолютного deadline, а при `deadline is None` каждая порция тела получает заново полный timeout.
>    - Следствие: медленно поступающее незавершающееся тело cleanup-ответа может удержать выполнение до `lease.cleanup()` неограниченно долго. Короткий socket timeout не ограничивает длительность всей операции. Предельный setup также не обеспечивает детекцию отключения клиента ≤5 с.
>    - Исправление: передать deadline/cancellation через setup; назначить отдельный абсолютный cleanup deadline и лимит тела; гарантировать переход к остановке группы после исчерпания cleanup-бюджета.
>    - Проверка: задержанные handshake/listener/SSE headers, истёкший deadline до spawn и непрерывно капающее cleanup-тело; после отмены группа отсутствует в пределах AC-011.

### F-011
- origin: visionary · R1 · visionary-F-009
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-009 — priority=blocking; [pre-existing], сопутствующий FU-007.
>    - locations: `bridges/opencode-zen-bridge/server.py:3296`, `:3316`, `:3486`, `:3502`.
>    - Правило: REQ-007/AC-009 — stall отсчитывается от последнего полезного события.
>    - Evidence: готовый native-вызов устанавливает `first_token_at`, но не обновляет `last_token_at`. До первого токена tool-input delta также не обновляет этот срок.
>    - Сценарий: при first-token timeout больше stall timeout native-вызов завершается после длительной подготовки аргументов. Следующая итерация немедленно объявляет stall, хотя полезный вызов только что получен.
>    - Исправление: обновлять последнюю активность при завершённом native-вызове и явно определить семантику активности аргументов.
>    - Проверка: управляемые часы, поздний первый native-вызов, затем паузы STALL−ε/ST­­ALL+ε; преждевременного stall нет.

### F-012
- origin: visionary · R1 · visionary-F-010
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-010 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394`, `:556`, `:1303`, `:1592`, `:1663`, `:1761`, `:1867`.
>    - Правило: приложенный `agents/testing.md` — использовать pytest, не использовать `unittest.TestCase`, `setUp`, `tearDown`.
>    - Evidence: пять базовых классов прямо наследуют `unittest.TestCase`; ещё два наследуют `_AttemptCase`. Это новый файл кандидата, а не неизменяемый legacy-модуль.
>    - Исправление: перевести новый модуль на pytest-функции/фикстуры с сохранением всех assertions, FakeServe и процессных сценариев. Async/Litestar-зависимости для этого не нужны.
>    - Проверка: все нынешние сценарии и подслучаи сохранены; полный pytest и проверка порядка зелёные.

### F-013
- origin: visionary · R1 · visionary-F-011
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-011 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394`, `:556`, `:1303`, `:1663`, `:1761`, `:1867`.
>    - Правило: `testing.md` §7.2 и Serial Lane — временные/ресурсные измерения выносятся в `measured`/`heavy`; unit-оракулы переходов используют управляемые часы.
>    - Evidence: обычные тесты проверяют реальные сроки первого статуса, интервалы SSE, wall-clock watchdog и окна SIGTERM/SIGKILL. В новом модуле отсутствует выделение этих сценариев в measured/heavy-контур.
>    - Исправление: маркировать измерительные и ресурсные сценарии, запускать их последовательно; логические проверки дедлайнов и автоматов дополнить FakeClock. Сокетный AC-026 сохранить как отдельное реальное измерение.
>    - Проверка: обычный параллельный набор не содержит измерений latency/cleanup; отдельный serial lane действительно исполняется и имеет приложенный лог.

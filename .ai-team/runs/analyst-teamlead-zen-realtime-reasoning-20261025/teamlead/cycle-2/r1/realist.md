PANEL-NONCE: 58afef6847a0e4b3
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

Общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком в сообщении до `<!-- КАНОН-КОНЕЦ -->`. Проектный `AGENTS.md`, `feature.md` и перечисленные профильные стандарты прочитаны в приложенном пакете; файлы рабочей папки не открывались. Тесты не запускал.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL  
   WHY=Выбранный транспорт осуществим, но исправления не обеспечивают корректное завершение по deadline, устойчивое чтение SSE после паузы, обработку ошибок prompt независимо от SSE и общий потолок запусков в JSON-пути. Сохранились нарушения одношаговой обработки инструментов и семантики повторов. См. F-001–F-008, F-018, F-022.  
   СОВЕТЫ (при FAIL): обработать все неуспешные исходы до ветки успеха; исправить SSE-reader; развести получение HTTP-заголовков и чтение тела; сделать барьер доставки необратимым; проверять общий бюджет перед каждым запуском обоих транспортов; завершать шаг после текстовых и native tool calls; восстановить разделение попыток и дедупликацию.

2. ПОЛНОТА: VERDICT=FAIL  
   WHY=Заявление «RW-001..RW-032 закрыты» не подтверждается кодом и оракулами. Новый модуль содержит 29 зелёных тестов, однако существенная часть обязательных сценариев отсутствует либо проверяет вспомогательную структуру вместо конечного поведения. Первая реакция legacy-пути при ожидании startup gate также не укладывается в AC-005. См. F-015, F-019.  
   СОВЕТЫ (при FAIL): добавить перечисленные в F-019 поведенческие проверки; исправить legacy-статус до ожиданий; пересобрать traceability по конкретным тестам и проверяемым утверждениям, сохранив `INCONCLUSIVE` там, где прямого свидетельства нет.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL  
   WHY=Зависимости доступны: Python stdlib, установленный OpenCode v2.1.2, loopback API и существующий прокси-пул. Оценка памяти допускает шесть serve-процессов, но эксплуатацию блокируют незамкнутые пути освобождения ресурсов, удержание startup gate, неполная уборка потомков и ошибки обнаружения отключения клиента. См. F-009–F-014, F-016–F-017.  
   СОВЕТЫ (при FAIL): обеспечить единое владение ресурсами от создания временного каталога; освобождать gate в `finally`; завершать и проверять всю группу процессов; исправить проверку RST и идентичности PID; отменять фоновые таймеры. Оценочно потребуется 2–4 инженерных дня на исправления и 0,5–1 день на проверку после стабилизации; это оценка, зависящая от воспроизводимости отказов и доступности Zen.

4. РИСКИ: VERDICT=FAIL  
   WHY=Full Suite L2 действительно зелёный: 408 тестов компонента и 894 теста корневого набора. Это не устраняет конкретные риски: потерю SSE после штатной паузы, ложный успех при timeout, осиротевшие процессы, повтор принятого prompt и недоучёт upstream-сбоев. Red-прогон не доказывает чувствительность именно временного оракула AC-026. См. F-001–F-004, F-011–F-013, F-016, F-018–F-019.  
   СОВЕТЫ (при FAIL): закрыть эти дефекты regression-тестами с управляемыми часами и отказами; проверить конечные сокеты, процессы и журналы; после ACCEPT выполнить предусмотренный L3. Отсрочка VER-006/VER-007 сама по себе замечанием не является.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS  
   WHY=Короткоживущий serve с резервным run оправдан подтверждёнными ограничениями CLI и необходимостью ротации IP. Возврат к одному legacy-пути не закроет RC-1, общий демон усложнит ротацию, прямой Zen пока не подтверждён. Замена самописного JSON-парсера стандартным `json.loads` устраняет прежнее неоправданное усложнение. Полная смена архитектуры для исправления перечисленных дефектов не требуется.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL  
   WHY=Границы трёх файлов, stdlib-only и замороженные функции соблюдены; изменений публичных HTTP-маршрутов не обнаружено. Однако новый тестовый код использует прямо запрещённые приложенным `testing.md` конструкции `unittest.TestCase`/`setUp`/`tearDown`; обязательные проверки жизненного цикла и дедлайнов также закрыты неполно. См. F-009–F-012, F-019, F-021. Требования Litestar/async к автономному `ThreadingHTTPServer` механически не применяю.  
   СОВЕТЫ (при FAIL): перевести новый тестовый модуль на pytest-фикстуры; сохранить согласованную изоляцию окружения; закрыть применимые `T-LIFE`, `C-MULT-I4`, `R-BULK-I1/I3` поведенческими оракулами.

Обозначения далее: `S` — `bridges/opencode-zen-bridge/server.py`; `T` — `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`; `I` — `bridges/opencode-zen-bridge/tests/test_step_interruption.py`. `PASS по коду` означает подтверждённое исправление реализации; отсутствие прямого regression-оракула отмечено отдельно.

Проверка устранения замечаний:

- RW-001 — PARTIAL: gate, limiter и передача proxy добавлены (`S:5092`, `S:6203`), но освобождение gate некорректно, прокси выбирается дважды; F-010, F-022.
- RW-002 — PASS по коду: побайтовый handshake ограничен остатком трёх секунд (`S:2544`). Прямой тест частичной строки без LF — INCONCLUSIVE.
- RW-003 — FAIL: `0700` и UID добавлены, но идентичность helper не проверяется по времени запуска; F-016.
- RW-004 — PASS по коду: `tool_choice` передаётся в оба serve-пути и recovery (`S:5274`, `S:5593`, `S:6482`). Прямой serve regression — INCONCLUSIVE.
- RW-005 — PASS: самописный парсер удалён; стандартный JSON, суррогаты и ошибка разбора проверяются (`S:1625`, `T:778`).
- RW-006 — FAIL: после эскалации не остаётся полноценного бюджета подтверждения смерти группы; F-012.
- RW-007 — PASS по коду: `if text_value:` сохраняет пробельные дельты (`S:3178`, `S:3189`); unit-оракул маппера имеется (`T:806`).
- RW-008 — FAIL: deadline передан, но возвращённый `timeout` допускается в ветку успеха; F-001.
- RW-009 — FAIL: повторное чтение буферизованного HTTP-response после socket timeout не восстанавливает поток; F-002.
- RW-010 — PARTIAL: timeout существующего control-сокета обновляется, cleanup-запросы ограничены (`S:2377`, `S:3268`); общий lifecycle-бюджет не доказан, F-012.
- RW-011 — FAIL: timer добавлен только в serve-оркестрацию, не отменяется и конкурирует с другим механизмом статусов; legacy ожидание gate не покрыто; F-014, F-015.
- RW-012 — PASS по коду: watchdog вызывается и при поступлении stdout (`S:1187`). Прямые тесты непрерывных служебных событий — INCONCLUSIVE.
- RW-013 — FAIL: SSE fallback защищён, JSON fallback способен выполнить четвёртый запуск; F-005.
- RW-014 — PASS по коду: успешный serve вызывает `attempt_done(False, True)` в обоих режимах; unit перехода breaker зелёный (`T:817`). Проверка через сам serve-handler — INCONCLUSIVE.
- RW-015 — FAIL: HTTP-результат проверяется только после получения элемента SSE-очереди, барьер доставки не соответствует зафиксированной таблице; F-003, F-004.
- RW-016 — PARTIAL: transient-классификация добавлена, но upstream breaker учитывает эти отказы непоследовательно; F-004, F-018.
- RW-017 — FAIL: завершение шага реализовано для native calls, но не для вызовов, распарсенных из text; F-006.
- RW-018 — FAIL: разделитель есть не на всех retry-ветках; JSON не дедуплицирует одинаковые вызовы из двух каналов; F-007, F-008.
- RW-019 — FAIL: исключения до создания `_ServeLease` находятся вне cleanup-блока; F-009.
- RW-020 — PARTIAL: stop-aware очередь и ограниченный join добавлены (`S:2944`, `S:3259`); завершение prompt-thread до возврата не подтверждено. Матрица переполнения/отмены отсутствует; F-019.
- RW-021 — PASS: helper stderr дренируется в `deque(maxlen=64)` (`S:2595`).
- RW-022 — PASS по коду: внутрипроцессное резервирование портов и положительная ownership-проверка добавлены (`S:2486`, `S:2583`). Конкурентный оракул — INCONCLUSIVE.
- RW-023 — FAIL: helper проверяет непосредственный serve-процесс вместо всей группы; F-011.
- RW-024 — FAIL: RST/ошибки сокета по-прежнему превращаются в `False`; JSON дополнительно не обрабатывает возвращённый `client_gone`; F-001, F-013.
- RW-025 — FAIL: требуемая поведенческая матрица не добавлена полностью; F-019.
- RW-026 — PASS в согласованном статическом гейте: блоковые отключения удалены, VER-004 подтверждает ноль ошибок и ноль диагностик нового файла.
- RW-027 — PASS по коду: лишний `pop` удалён, восстановление окружения сохранено (`T:354`, `T:851`).
- RW-028 — PARTIAL: сокетный замер сохранён, но детерминированных watchdog-оракулов нет; F-019.
- RW-029 — PASS по коду: чужой явный `sessionID` фильтруется до диспетчеризации (`S:3086`); прямой тест фильтра в живом цикле — INCONCLUSIVE.
- RW-030 — PASS по коду: request-level метрики не затираются последующими попытками (`S:5137`, `S:5809`, `S:6243`). Retry-оракул метрик — INCONCLUSIVE.
- RW-031 — PASS: указанные служебные события с пустым `data` игнорируются (`S:1779`, `T:787`).
- RW-032 — PASS: окружение сохраняется и восстанавливается через `patch.dict` (`I:206`, `I:222`).

Сопутствующие пункты:

- FU-001 — PASS по коду: разрешающий `len(head) == 4` удалён (`S:1738`).
- FU-002 — PASS по коду: статус определяется типом tool-события (`S:2758`); тест не проверяет само значение статуса.
- FU-003 — PASS: комментарий описывает ограниченный буфер без логирования (`S:2594`).
- FU-004 — PARTIAL, non-blocking: SSE исправлен для части watchdog-ретраев; JSON и другие ветки продолжают терять usage; F-020.
- FU-005 — допустимо отложен на PR_DESCRIPTION/эксплуатационный handoff после Совета.
- FU-006 — косметические hunks остались; согласованный non-blocking follow-up, оснований для FAIL нет.
- FU-007 — общая классификация полностью не выделена; согласованный non-blocking follow-up. Конкретные поведенческие расхождения отражены отдельными findings.
- FU-008 — PASS: ожидания трёх запусков объяснены docstring (`I:435`, `I:444`).
- FU-009 — PASS по коду: tool input delta продлевает stall-часы после первого токена (`S:3199`).

Поштучная проверка требований:

- REQ-001 — FAIL: SSE может перестать читать дельты после штатной паузы; F-002.
- REQ-002 — PASS по структуре: публичные маршруты, порт и OpenAI-оболочки сохранены.
- REQ-003 — PASS по переключению: run сохранён, kill-switch имеется; ошибки fallback отдельно отражены в F-004/F-005.
- REQ-004 — FAIL: первая реакция legacy после gate/spawn не гарантирована; F-015.
- REQ-005 — PARTIAL: пробельные дельты восстановлены, replay исключает reasoning; полнота побайтовой проверки всех сценариев не доказана, F-019.
- REQ-006 — PARTIAL: watchdog реализован; уборка и временной бюджет отказов не закрыты, F-009/F-012.
- REQ-007 — FAIL: SSE-reader не переживает паузу до watchdog; F-002.
- REQ-008 — FAIL: RST, ранние утечки и потомки после смерти родителя; F-009/F-011–F-013/F-016.
- REQ-009 — FAIL: JSON spawn cap, delivery barrier, retry-разделители и breaker; F-004/F-005/F-007/F-018.
- REQ-010 — PASS по коду: существующий инкрементальный parser переиспользован; разрезанный tool tag проверяется (`T:583`).
- REQ-011 — FAIL: текстовый tool call не закрывает serve-шаг; F-006.
- REQ-012 — PASS по реализации политики: `ask_reject`/`deny`, reject и interrupt предусмотрены. Полная проверка parity — INCONCLUSIVE, F-019.
- REQ-013 — FAIL: двойное продвижение прокси-пула нарушает ротацию; F-022.
- REQ-014 — PARTIAL: нормальный usage отображается, failed-attempt usage учитывается не полностью; F-020, non-blocking.
- REQ-015 — INCONCLUSIVE по AC-020: пароль случайный, env ограничен; прямого log-оракула нет, F-019.
- REQ-016 — PASS по наличию полей и сохранению первого наблюдения; полная матрица исходов не подтверждена.
- REQ-017 — PASS: полный и обратный прогоны зелёные.
- REQ-018 — PASS: frozen hashes и неизменённый Google Direct подтверждены VER-004.
- REQ-019 — DEFERRED_L3: законно отложено до ACCEPT.
- REQ-020 — FAIL по качеству оракула: независимого сигнала окончания апстрима нет; F-019.

Поштучная проверка AC:

- AC-001 — INCONCLUSIVE: соседние клиентские интервалы `<500 мс` тест не проверяет.
- AC-002 — INCONCLUSIVE: независимых upstream timestamps для overhead `≤250 мс` нет.
- AC-003 — PASS: существующий формат сохранён, L2 зелёный.
- AC-004 — PASS: legacy-набор проходит.
- AC-005 — FAIL: ожидание legacy gate/spawn не покрыто первой реакцией; F-015.
- AC-006 — PARTIAL: эталонный reasoning проверен; полная матрица дельт и повторов отсутствует.
- AC-007 — PASS: исключение `reasoning_content` из prompt проверяется.
- AC-008 — INCONCLUSIVE: имеющийся тест проверяет суммарное время `<25 с`, не требуемую границу отдельной попытки.
- AC-009 — FAIL: пауза ломает reader раньше штатного stall-watchdog; F-002.
- AC-010 — FAIL: тот же дефект препятствует корректному ожиданию первого токена; F-002.
- AC-011 — FAIL: смерть всей группы и соблюдение бюджета не гарантированы; F-011/F-012.
- AC-012 — FAIL: RST может не обнаруживаться штатным checker; F-013.
- AC-013 — FAIL: JSON fallback допускает четвёртый запуск; F-005.
- AC-014 — FAIL: нет разделителя на всех переходах между попытками; F-007.
- AC-015 — PASS по переиспользованному parser и существующим тестам; отдельный serve-сценарий разрезанного тега зелёный.
- AC-016 — FAIL: всей step-interruption матрицы на serve нет, текстовый tool-call terminal неполон; F-006/F-019.
- AC-017 — INCONCLUSIVE: native `bash` проверен, parity unmapped-повтора и завершения не проверена.
- AC-018 — FAIL: при пуле из двух записей фактический proxy может повторяться; F-022.
- AC-019 — PASS для канонического отображения fixture; итоговый multi-attempt usage — PARTIAL, F-020.
- AC-020 — INCONCLUSIVE: проверки отсутствия пароля и apiKey в `bridge.log` нет.
- AC-021 — PASS по наличию полей; сквозная матрица всех исходов неполна.
- AC-022 — PASS: 408 passed в компоненте.
- AC-023 — PASS: обратный порядок также даёт 408 passed.
- AC-024 — PASS: Google Direct frozen и тесты зелёные.
- AC-025 — DEFERRED_L3.
- AC-026 — FAIL по оракулу: сравнение с окончанием клиентского ответа допускает буферизованную доставку; F-019.

Границы проверены по отдельности:

- Non-Goals 1 — публичные маршруты, порт и оболочка SSE сохранены.
- Non-Goals 2 — DSH, `app.asar`, профиль и ReasoningRow не изменены.
- Non-Goals 3 — отдельной переработки текста ради UI-превью нет; сохранение данных требует дополнительных оракулов.
- Non-Goals 4 — состав моделей и правила effort не переработаны.
- Non-Goals 5 — другие мосты и общие конфиги не изменены.
- Non-Goals 6 — внешних runtime-зависимостей не добавлено.
- Forbidden Scope 1 — кандидат ограничен тремя разрешёнными файлами.
- Forbidden Scope 2 — реальных секретов в diff не обнаружено; runtime-проверка журналов остаётся INCONCLUSIVE.
- Forbidden Scope 3 — живой контур законно не изменялся до ACCEPT.
- Forbidden Scope 4 — вызовов `security find-generic-password` нет.
- Forbidden Scope 5 — прямой правки общей БД/state нет; используется `OPENCODE_DB=:memory:`.
- Forbidden Scope 6 — кандидат на feature-ветке; свидетельства запрещённого коммита или merge нет.

Все findings одного прохода:

**F-001 — priority=blocking — незавершённая попытка может считаться успешной.**  
locations: `bridges/opencode-zen-bridge/server.py:3252`, `bridges/opencode-zen-bridge/server.py:5151`, `bridges/opencode-zen-bridge/server.py:6249`.  
Правило: RW-008, RW-024, `R-BULK-I1`, `O-EXIT/v1`. Evidence: producer возвращает `exit_reason="timeout"`, но оба consumer проверяют ограниченный список без `timeout`; JSON также не обрабатывает `client_gone`. Затем достижимы `record_success()` и успешный ответ с частичными данными.  
Исправление: обработать все неуспешные исходы до success-ветки; ограничить setup I/O остатком общего deadline. Проверка: истёкший deadline и JSON disconnect никогда не вызывают success, HTTP 200 или успешный SSE finish.

**F-002 — priority=blocking — SSE не восстанавливается после socket timeout.**  
locations: `bridges/opencode-zen-bridge/server.py:2941`, `bridges/opencode-zen-bridge/server.py:2955`.  
Правило: RW-009, REQ-007, AC-009/010. Evidence: после timeout на `sse_resp.readline()` выполняется `continue`. У буферизованного SocketIO timeout оставляет состояние, при котором дальнейшее чтение вызывает `OSError: cannot read from timed out object`; этот OSError снова проглатывается. Возможен быстрый цикл ошибок до watchdog.  
Исправление: использовать чтение, допускающее возобновление после ожидания готовности, без poisoning буферизованного response. Проверка: пауза более 5 секунд, но меньше watchdog, затем новые дельты доставляются в той же попытке.

**F-003 — priority=blocking — HTTP-ошибка prompt зависит от наличия SSE-события.**  
locations: `bridges/opencode-zen-bridge/server.py:3053`, `bridges/opencode-zen-bridge/server.py:3057`.  
Правило: RW-015, обработка ошибок независимо от канала данных. Evidence: `queue.Empty` делает `continue` до проверки `prompt_status`. Если prompt уже вернул 401/429/5xx, а SSE молчит, ошибка может быть перекрыта watchdog.  
Исправление: проверять результат prompt на каждой итерации до ожидания очереди. Проверка: каждый предусмотренный HTTP-status классифицируется при пустой SSE-очереди.

**F-004 — priority=blocking — барьер доставки не является необратимым.**  
locations: `bridges/opencode-zen-bridge/server.py:2385`, `bridges/opencode-zen-bridge/server.py:2997`, `bridges/opencode-zen-bridge/server.py:3063`, `bridges/opencode-zen-bridge/server.py:5208`, `bridges/opencode-zen-bridge/server.py:6280`.  
Правило: `FALLBACK_DECISION_TABLE`, REQ-009, RW-015/016. Evidence: `headers_at` устанавливается после полного `resp.read()`, а не получения заголовков; HTTP-ветка заново вычисляет delivered по накопленному контенту. SSE transient-ветка учитывает text, но игнорирует уже выданный reasoning. Поэтому принятый prompt может перейти в fallback.  
Исправление: фиксировать согласованный delivery latch при заголовках/валидном execution-событии и никогда не сбрасывать его; отдельно учитывать клиентскую эмиссию. Проверка: headers-only, execution-only и reasoning-only сценарии не допускают запрещённого fallback. Противоречие текста RW-015 и таблицы относительно prompt 400/404/422 следует явно разрешить в конверте, не скрывать кодом.

**F-005 — priority=blocking — общий потолок запусков не защищает JSON fallback.**  
locations: `bridges/opencode-zen-bridge/server.py:6194`, `bridges/opencode-zen-bridge/server.py:6230`, `bridges/opencode-zen-bridge/server.py:6498`, `bridges/opencode-zen-bridge/server.py:4704`.  
Правило: RW-013, AC-013, `R-BULK-I2`. Evidence: после двух serve retries третья попытка может вернуть `ServeUnavailable`; auto возвращает `False`, затем JSON-путь запускает `Run` без предварительного `can_spawn()`. Сам `_execute_once()` создаёт процесс до `note_spawn()`.  
Исправление: единая проверка бюджета непосредственно перед каждым фактическим запуском. Проверка: две retries → третий setup failure → fallback дают максимум три запуска.

**F-006 — priority=blocking — текстовый tool call не закрывает serve-шаг.**  
locations: `bridges/opencode-zen-bridge/server.py:3236`, `bridges/opencode-zen-bridge/server.py:5000`, `bridges/opencode-zen-bridge/server.py:5030`.  
Правило: RW-017, REQ-011. Evidence: parser может уже эмитировать клиенту tool call, но `_serve_one_attempt()` при `step_finish` проверяет только `result["native_calls"]`. Для вызова из `<tool_invoke>` список пуст, чтение следующего шага продолжается.  
Исправление: передать в транспорт сигнал наличия распарсенного tool call и завершать попытку на соответствующем step boundary. Проверка: text tool call → step_finish → STEP2; STEP2 клиенту не передаётся.

**F-007 — priority=blocking — не все повторы reasoning разделены статусом.**  
locations: `bridges/opencode-zen-bridge/server.py:5211`, `bridges/opencode-zen-bridge/server.py:5228`, `bridges/opencode-zen-bridge/server.py:5255`, `bridges/opencode-zen-bridge/server.py:5281`.  
Правило: RW-018, AC-014. Evidence: transient recovery, unmapped и обычный incomplete recovery выполняют `continue` без общего разделителя; он добавлен только в отдельных watchdog/HTTP-ветках.  
Исправление: единая эмиссия ровно одного retry-разделителя перед следующей попыткой после reasoning. Проверка: все причины повторов сохраняют reasoning и дают ровно один разделитель.

**F-008 — priority=blocking — JSON способен вернуть одинаковый инструмент дважды [pre-existing].**  
locations: `bridges/opencode-zen-bridge/server.py:6323`, `bridges/opencode-zen-bridge/server.py:6344`, `bridges/opencode-zen-bridge/server.py:6372`.  
Правило: RW-018, parity с существующим `emit_tool_call`. Evidence: parsed calls и mapped native calls независимо добавляются в `tool_calls_all` с разными случайными ID; `_seen_tc` вычисляется, но не используется. Одинаковые name/arguments из двух каналов становятся двумя клиентскими вызовами.  
Исправление: дедуплицировать по семантическому ключу name/arguments. Проверка: одинаковый вызов в text и native даёт один `tool_call` в JSON.

**F-009 — priority=blocking — ранние ошибки запуска обходят уборку.**  
locations: `bridges/opencode-zen-bridge/server.py:1713`, `bridges/opencode-zen-bridge/server.py:2476`, `bridges/opencode-zen-bridge/server.py:2505`, `bridges/opencode-zen-bridge/server.py:2508`, `bridges/opencode-zen-bridge/server.py:2835`.  
Правило: RW-019, `T-LIFE/v1`, `C-MULT-I4`. Evidence: state-dir создаётся до `_spawn_serve`; резервирование порта, `os.pipe()` и helper `Popen()` происходят до общего cleanup-блока. При ошибке `Popen` закрывается только read-end pipe.  
Исправление: единый exception-safe владелец state-dir, порта, обоих FD и процесса с начала создания ресурсов. Проверка: инъекция отказов mkdir/pipe/Popen/handshake не оставляет FD, портов, каталогов или процессов.

**F-010 — priority=blocking — startup gate удерживается дольше startup-фазы.**  
locations: `bridges/opencode-zen-bridge/server.py:5092`, `bridges/opencode-zen-bridge/server.py:5136`, `bridges/opencode-zen-bridge/server.py:6203`, `bridges/opencode-zen-bridge/server.py:6243`.  
Правило: RW-001, `S-HERD-I1`, `C-MULT-I4`. Evidence: SSE освобождает gate после всей `_serve_one_attempt()`, JSON на обычном возврате вообще не вызывает release. Это создаёт ненужные ожидания и переходы в fail-open по таймеру gate.  
Исправление: освобождать gate после подтверждённого startup/первого события и гарантированно в `finally`. Проверка: длинная генерация первого запроса не удерживает startup gate для второго.

**F-011 — priority=blocking — после смерти родителя могут остаться внуки serve.**  
locations: `bridges/opencode-zen-bridge/server.py:195`, `bridges/opencode-zen-bridge/server.py:232`.  
Правило: RW-023, REQ-008, `T-LIFE/v1`. Evidence: helper эскалирует только если непосредственный `serve_proc` ещё жив; lease удаляется, если этот процесс завершился. Если serve завершился после TERM, а его потомок TERM игнорирует, эскалация пропускается и lease теряется.  
Исправление: проверять всех остальных членов собственной группы независимо от состояния прямого потомка; сохранять свидетельство до их завершения. Проверка: смерть родителя + завершившийся serve + TERM-resistant grandchild не оставляют сирот.

**F-012 — priority=blocking — бюджет cleanup исчерпан до проверки результата SIGKILL.**  
locations: `bridges/opencode-zen-bridge/server.py:2432`, `bridges/opencode-zen-bridge/server.py:2444`, `bridges/opencode-zen-bridge/server.py:2450`, `bridges/opencode-zen-bridge/server.py:2470`.  
Правило: RW-006/010, AC-011. Evidence: TERM-ожидание расходует весь `_deadline`; после SIGKILL повторный цикл использует тот же истёкший deadline. Cleanup может вернуться с живой группой, уже установив `_closed=True`, и удалить state-dir.  
Исправление: заранее разделить общий бюджет на TERM, KILL и подтверждение; не считать уборку завершённой при живой группе. Проверка: игнорирующая TERM группа подтверждённо отсутствует до возврата в пределах AC-011.

**F-013 — priority=blocking — RST не считается отключением клиента [pre-existing].**  
locations: `bridges/opencode-zen-bridge/server.py:4938`, `bridges/opencode-zen-bridge/server.py:4955`.  
Правило: RW-024, REQ-008. Evidence: `ConnectionResetError` является `OSError`; checker возвращает `False` для всех `OSError/ValueError`. JSON во время генерации ничего не пишет клиенту, поэтому альтернативного быстрого обнаружения нет.  
Исправление: отличать EAGAIN/EWOULDBLOCK от RST/EBADF и других терминальных ошибок; включить ошибку `os.dup` в эту классификацию. Проверка: FIN и RST в SSE/JSON вызывают `client_gone` и cleanup в заданном бюджете.

**F-014 — priority=blocking — статусный timer не принадлежит жизненному циклу запроса.**  
locations: `bridges/opencode-zen-bridge/server.py:3042`, `bridges/opencode-zen-bridge/server.py:5079`, `bridges/opencode-zen-bridge/server.py:5087`.  
Правило: RW-011, `T-LIFE/v1`, целостность SSE. Evidence: отдельный daemon timer пишет непосредственно в `wfile`, не отменяется на terminal/fallback и работает одновременно со статусами основного serve-цикла. Возможны два initial-status и конкурентные записи с модельными чанками.  
Исправление: один владелец SSE-записей, общее состояние первого статуса, отмена timer при любом завершении. Проверка: ранний tool-only terminal, fallback и модельная дельта около порога не дают поздних/двойных статусов или повреждения кадра.

**F-015 — priority=blocking — legacy не гарантирует первый видимый статус за секунду [pre-existing].**  
locations: `bridges/opencode-zen-bridge/server.py:5649`, `bridges/opencode-zen-bridge/server.py:5716`, `bridges/opencode-zen-bridge/server.py:5743`.  
Правило: RW-011, REQ-004, AC-005. Evidence: часы статуса legacy создаются после gate/limiter/spawn; служебный статус отправляется только при чтении feed. Ожидание gate может занять пять секунд до начала этих часов.  
Исправление: запустить request-level статусный механизм до startup-ожиданий. Проверка: занятый gate и молчащий CLI всё равно дают видимый reasoning/status не позже 1,0 секунды.

**F-016 — priority=blocking — защита reaper от переиспользования helper PID неполна.**  
locations: `bridges/opencode-zen-bridge/server.py:78`, `bridges/opencode-zen-bridge/server.py:2639`, `bridges/opencode-zen-bridge/server.py:2660`.  
Правило: RW-003, ownership lifecycle. Evidence: `helper_lstart` записан epoch-числом, а reaper явно пропускает сравнение decimal timestamps с живым `ps lstart`. Наличие `--serve-helper` в argv не доказывает, что это helper данной попытки.  
Исправление: сохранять и проверять сопоставимую идентичность процесса/группы до сигналов. Проверка: lease со старым временем и переиспользованным PID другого helper не вызывает сигналов.

**F-017 — priority=blocking — ранняя helper-ветка обращается к неимпортированному errno.**  
locations: `bridges/opencode-zen-bridge/server.py:99`, `bridges/opencode-zen-bridge/server.py:240`, `bridges/opencode-zen-bridge/server.py:245`.  
Правило: корректная обработка ошибок, RW-023. Evidence: helper завершается до импорта `errno` из `else`, но `_fd_ready()` использует `errno.EAGAIN/EWOULDBLOCK` при OSError. Эта ветка завершится `NameError`.  
Исправление: импортировать требуемый stdlib-модуль до helper dispatch. Проверка: OSError на lifeline проверяет нужный исход без NameError.

**F-018 — priority=blocking — transient upstream-события обходят Circuit Breaker.**  
locations: `bridges/opencode-zen-bridge/server.py:5180`, `bridges/opencode-zen-bridge/server.py:5207`, `bridges/opencode-zen-bridge/server.py:6265`, `bridges/opencode-zen-bridge/server.py:6278`.  
Правило: RW-015/016, REQ-009, `R-BULK-I3`. Evidence: `attempt_done(True, False)` вызывается для HTTP 429, но отсутствует на ветках transient SSE error и prompt 5xx. Полученные `transient_error=True` и retry сами по себе breaker не обновляют.  
Исправление: централизовать учёт исхода попытки, ровно один раз увеличивая соответствующий health/breaker. Проверка: серии 429/5xx/transport SSE failures открывают upstream breaker, не повышая serve-health за модельный отказ.

**F-019 — priority=blocking — оракулы не подтверждают заявленную полноту исправлений.**  
locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:489`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:508`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:587`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:639`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:787`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:830`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:863`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:873`.  
Правило: RW-025/028, REQ-020, `testing.md` «Зелёный прогон ≠ корректно», §7.2. Evidence: `upstream_end_t = elapsed` означает конец клиентского ответа; даже буферизованный ответ проходит сравнение. Proxy проверяется через `callable`, fallback — чтением декларативной таблицы, foreign-session — маппером. Red AC-026 падает в `setUp` из-за отсутствия `DYNAMIC_CONFIG_PATH`.  
Исправление: добавить независимый upstream-end/timestamps; проверки интервалов и overhead; три serve-watchdog и legacy first-token/stall; JSON serve/retries; FIN/RST; cleanup/parent death/PID reuse; частичный handshake; конкурентные старты/порты; реальную ротацию; secret-log oracle; disable-file; HTTP-status/health/breaker матрицу; step-interruption на serve; terminal после text tool call; retry-разделители и dedup; сохранение первых метрик. Детерминированные переходы проверять FakeClock.  
Проверка: каждый указанный дефект воспроизводится своим тестом, а traceability ссылается на конкретное утверждение, не на зелёный модуль целиком.

**F-020 — priority=non-blocking — usage не всех попыток попадает в итог.**  
locations: `bridges/opencode-zen-bridge/server.py:5167`, `bridges/opencode-zen-bridge/server.py:5228`, `bridges/opencode-zen-bridge/server.py:6259`, `bridges/opencode-zen-bridge/server.py:6284`.  
Правило: FU-004, REQ-014 SHOULD. Evidence: SSE суммирует usage на части watchdog-retry, JSON делает `continue` без аккумуляции, transient recovery также пропускает учёт.  
Исправление: суммировать usage завершённых шагов перед каждым retry. Проверка: две попытки с известными tokens дают их сумму. Сохраняю согласованный non-blocking приоритет.

**F-021 — priority=blocking — новый тестовый код нарушает явный запрет TestCase.**  
locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:773`; также классы legacy/serve нового модуля с `setUp/tearDown` — [pre-existing] относительно дельты цикла.  
Правило: приложенный `agents/testing.md`: «Не использовать unittest.TestCase, setUp, tearDown». Evidence: новый `TestReworkUnits(unittest.TestCase)` продолжает запрещённую структуру; runtime-ограничение stdlib не запрещает pytest из dev-зависимостей.  
Исправление: новый модуль оформить pytest-тестами и фикстурами; сохранить изоляцию env и ресурсов. Проверка: новый модуль не содержит TestCase/setUp/tearDown, полный pytest остаётся зелёным.

**F-022 — priority=blocking — прокси-пул продвигается дважды на одну serve-попытку.**  
locations: `bridges/opencode-zen-bridge/server.py:1696`, `bridges/opencode-zen-bridge/server.py:2831`, `bridges/opencode-zen-bridge/server.py:5119`, `bridges/opencode-zen-bridge/server.py:6228`.  
Правило: RW-001, REQ-013, AC-018. Evidence: вызывающий код сначала вычисляет `_next_standalone_proxy()`, затем `_serve_one_attempt()` вызывает `_serve_env()` → замороженный `_run_env()`, который для standalone снова выбирает proxy. После этого второй выбор затирается первым. Для пула `[A,B]` фактически используемый proxy последовательных попыток может быть `[A,A]`.  
Исправление: оставить ровно одну точку потребления прокси-пула на попытку, не меняя frozen `_run_env`. Проверка: пул из двух записей, две реальные попытки → разные фактически переданные proxy, счётчик выбора равен числу попыток.

**F-023 — priority=non-blocking — диагностическая история lsof растёт без ограничения [pre-existing].**  
locations: `bridges/opencode-zen-bridge/server.py:1433`, `bridges/opencode-zen-bridge/server.py:2347`.  
Правило: ограниченность runtime-буферов, `HL-ENV-01`. Evidence: каждый lookup добавляет порт в глобальный `_LSOF_CALLS`, очистки или предела нет; polling повторяет добавления.  
Исправление: убрать production-историю, заменить счётчиком либо ограниченным буфером; тестам использовать внешний spy. Проверка: размер диагностического состояния не растёт с числом запросов.

Повторный self-sweep выполнен по всем 14 подкатегориям; обнаруженные замечания включены выше.

1. SUB Корректность/логика: FAIL — timeout/client_gone допускаются в success, JSON fallback превышает cap (`S:3252`, `S:6249`, `S:6498`; F-001/F-005).
2. SUB Корректность/граничные условия: FAIL — пауза SSE и пул из двух proxy нарушают ожидаемое поведение (`S:2955`, `S:2831`; F-002/F-022).
3. SUB Корректность/обработка ошибок: FAIL — prompt-status зависит от SSE-очереди, delivery latch неустойчив (`S:3053`, `S:3063`; F-003/F-004).
4. SUB Полнота/покрытие AC: FAIL — AC-001/002/026 не имеют независимого временного оракула (`T:489`; F-019).
5. SUB Полнота/пропущенные ветки: FAIL — JSON retries, disconnect, watchdog и lifecycle-матрица не покрыты (`T:450`, `T:773`; RW-025, F-019).
6. SUB Реализуемость/общее: FAIL — ранние утечки, удержание gate и неполная уборка группы (`S:2508`, `S:6203`, `S:2444`; F-009–F-012).
7. SUB Риски/безопасность: FAIL — reaper не доказывает идентичность helper перед сигналом (`S:2639`, `S:2660`; F-016).
8. SUB Риски/данные: FAIL — возможны потеря поздних дельт и дубли JSON tool calls (`S:2955`, `S:6323`, `S:6344`; F-002/F-008).
9. SUB Риски/прод: FAIL — RST и смерть родителя не гарантируют своевременную остановку работы (`S:4955`, `S:195`, `S:232`; F-011/F-013).
10. SUB Риски/regression red→green: FAIL — общий RED есть, но AC-026 падает на setup, а его временное утверждение допускает буферизацию (`T:469`, `T:489`; execution-evidence.md, F-019).
11. SUB Риски/Full Suite (L2): PASS — независимый компонентный прогон: 408 passed; корневой: 894 passed, 5 skipped; обратный порядок: 408 passed (execution-evidence.md, VER-001/003/AC-023).
12. SUB Риски/scope-diff: PASS — ровно три разрешённых файла; frozen `_run_env` и Google Direct совпадают (candidate-manifest.json, VER-004).
13. SUB Альтернативы/общее: PASS — serve/run оправдан подтверждёнными ограничениями CLI; самописный JSON удалён (`S:1653`; F-17–F-25 ledger, RW-005).
14. SUB Соответствие контексту/общее: FAIL — новый TestCase нарушает прямое правило testing.md; lifecycle-инварианты неполны (`T:773`, `S:2508`; F-009/F-021).

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

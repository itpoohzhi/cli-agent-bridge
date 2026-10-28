# Стенограмма дебатов Совета Тимлидов по коду — Cycle 3 (run `analyst-teamlead-zen-realtime-reasoning-20261025`)

## Раунд R1 (`panel/council/r25`)

### Seat 1 (`skeptic`, `gpt-6.1-sol-high`)

PANEL-NONCE: 22385c2472cad260
ARTIFACT-SHA256: 674edaca247fa44fb9639f81a52dbfe62235889400a00a99eec3f6c321db2b82

Предоставленный канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до `<!-- КАНОН-КОНЕЦ -->`; приложенные правила AI-SDLC прочитаны. Проверю закрытие замечаний и весь кандидат по 14 подкатегориям. Тесты не запускаю; результаты беру из независимых логов L2.

SHA-256 `server.py` совпал с манифестом кандидата. Основные исправления видны в коде, но барьер доставки закрыт не полностью: исключение `ServeUnavailable` на следующей попытке всё ещё допускает fallback после уже выданного reasoning. Также проверяю ожидание spawn-limiter и точность оракулов задержки; зелёный Full Suite принимаю как факт.

PANEL-NONCE: 22385c2472cad260
ARTIFACT-SHA256: 674edaca247fa44fb9639f81a52dbfe62235889400a00a99eec3f6c321db2b82

Предоставленный канон `~/Мой диск/Context/AGENTS.md` прочитан до `<!-- КАНОН-КОНЕЦ -->`, приложенные стандарты AI-SDLC прочитаны целиком. В корне репозитория `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` отсутствуют. SHA-256 прочитанного `server.py` совпадает с кандидатом: `55b68dd38334cbcd8882266c9a5e2134594f90ba304db220550c06ea4736b7d5`. Тесты не запускал.

Ниже `server.py` и `tests/*` — пути относительно `bridges/opencode-zen-bridge/`. Контрсценарии получены анализом кода; фактические результаты прогонов — исключительно из `execution-evidence.md`. Для дополнительных находок использована консервативная метка `[pre-existing]`: точная межцикловая дельта отсутствует, окончательная атрибуция `late_miss` требует её сверки.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Исправлены основные дефекты предыдущего цикла, но барьер доставки обходится исключениями, native-инструменты используют несовместимый преобразователь аргументов, а JSON-повторы теряют накопленный результат.
   СОВЕТЫ (при FAIL): выполнить F-001, F-002, F-005, F-007, F-009 и F-011; добавить регрессионные сценарии для каждой указанной ветки.

   **F-001 — барьер доставки остаётся немонотонным.**
   - priority: blocking.
   - locations: `server.py:2406`, `server.py:2407`, `server.py:3062`, `server.py:3112`, `server.py:5198`, `server.py:5229`, `server.py:5294`, `server.py:6431`, `server.py:6486`.
   - Правило: RW-009, RW-012, REQ-009, `FALLBACK_DECISION_TABLE`.
   - Evidence: `headers_at` устанавливается после завершения `resp.read()`. Для prompt HTTP 429/5xx доставка определяется наличием модельного вывода. Обработчики `except ServeUnavailable` возвращают fallback без проверки предыдущей доставки.
   - Контрсценарий: первая попытка отдала reasoning и завершилась stall; следующая падает при запуске с `ServeUnavailable`; `auto` переходит на run вопреки установленному барьеру. Отдельно: prompt-заголовки получены, тело задержано — код продолжает считать доставку неподтверждённой.
   - Исправление: фиксировать получение заголовков непосредственно после `getresponse()`; хранить общий latch запроса; проверять его во всех возвратах fallback, включая исключения и отказ limiter; после барьера использовать serve-retry либо явную ошибку.
   - Проверка: сценарии «reasoning → retry → ServeUnavailable», «headers → задержанное тело» и «429/5xx без токенов» в SSE и JSON; отсутствие запрещённого run-fallback.

   **F-002 — первый статус теряется при ожидании spawn-limiter.**
   - priority: blocking.
   - locations: `server.py:5808`, `server.py:5811`, `server.py:5812`.
   - Правило: RW-017, REQ-004, AC-005.
   - Evidence: `status_timer.cancel()` выполняется до `spawn_limiter.acquire()`, тогда как `send_keepalive` начнёт работать только после запуска процесса.
   - Контрсценарий: startup gate получен сразу, limiter задержал запуск больше секунды — непустого reasoning-чанка за установленный срок нет. Ограничение прямо признано в `coder.json`.
   - Исправление: сохранять таймер до первого видимого вывода либо непрерывно обслуживать статусы во всех ожиданиях.
   - Проверка: занятый limiter при свободном startup gate; первый статус ≤1 секунды, ровно один `STATUS_INITIAL`.

   **F-005 [pre-existing] — JSON-повторы теряют частичный вывод.**
   - priority: blocking.
   - locations: `server.py:6477`, `server.py:6499`, `server.py:6514`, `server.py:6527`, `server.py:6528`.
   - Правило: REQ-011; `testing.md`, полнота результата и recovery.
   - Evidence: retry выполняется до переноса `reasonings` и `texts` в итоговые накопители; recovery-prompt получает `"".join(contents)`, не содержащий текста текущей неуспешной попытки.
   - Контрсценарий: попытка вернула полезный префикс и stall; следующая продолжила ответ — итоговый JSON содержит только продолжение. Reasoning неуспешной попытки также исчезает.
   - Исправление: определить единый порядок фиксации частичного результата, dedup и построения recovery-prompt до перехода к повтору.
   - Проверка: текст и reasoning первой попытки сохраняются согласно контракту; продолжение не теряется и не дублируется при watchdog и transient-error.

   **F-007 [pre-existing] — native serve-путь обходит существующий адаптер схем инструментов.**
   - priority: blocking.
   - locations: `server.py:2832`, `server.py:2849`, `server.py:2852`; эталон — `server.py:686`, `server.py:707`, `server.py:725`.
   - Правило: REQ-011, REQ-012, AC-017; `code.md`, DRY и единая семантика.
   - Evidence: `_native_call_as_dsh` выбирает имя/алиас и возвращает исходные `args`. Legacy `_native_to_tool_calls` дополнительно вызывает `_fit_args`, преобразует list/ls и разворачивает multiedit.
   - Следствие: одинаковое событие через run и serve даёт разные аргументы либо разный набор вызовов. Совпадение имени инструмента не доказывает совместимость его JSON-схемы.
   - Исправление: использовать общий существующий преобразователь native-вызовов; сохранить проверку обязательных полей, переименование аргументов и one-to-many преобразования.
   - Проверка: одинаковые native-фикстуры read/edit/list/multiedit дают одинаковые `tool_calls` в run/serve, SSE/JSON.

   **F-009 [pre-existing] — watchdog не распространяется на запасной JSON/run-путь.**
   - priority: blocking.
   - locations: `server.py:4732`, `server.py:4824`.
   - Правило: REQ-006, REQ-007, REQ-008; переключаемый legacy-путь REQ-003.
   - Evidence: `Run._execute_once()` вызывает `self.feed.lines(deadline)` без idle callback; туда не передаётся детектор отключения клиента.
   - Следствие: `stream:false` с `TRANSPORT=run` либо после fallback продолжает ждать молчащий CLI до общего `TIMEOUT_S`, несмотря на новые пороги первого события/токена.
   - Исправление: подключить общий watchdog и cancellation-контекст к JSON/run, не меняя замороженный `_run_env`.
   - Проверка: молчание, отсутствие токена, stall и отключение клиента в JSON/run завершаются по соответствующим порогам.

   **F-011 [pre-existing] — очистка interruption-маркеров зависит от границы дельты.**
   - priority: blocking.
   - locations: `server.py:823`, `server.py:5127`, `server.py:5145`.
   - Правило: REQ-011; совместимость накопленного потокового пути.
   - Evidence: `_strip_interrupted` применяет регулярное выражение к каждой отдельной дельте.
   - Контрсценарий: `"I was interrupted right "` и `"before making tool calls."` поступают раздельно — маркер уходит клиенту целиком, хотя при подаче одним блоком удаляется.
   - Исправление: сделать очистку инкрементальной с ограниченным удержанием потенциального префикса либо выполнять её на уровне адаптера, сохраняющего границы логического сообщения.
   - Проверка: перебрать все разрезы обоих `_INTERRUPTED_RE`-маркеров; результат совпадает с обработкой целого сообщения.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Матрица прослеживаемости завышает доказанность AC-001/002/016/026. Повреждённый UTF-8 конфигурации также не соответствует заявленной безопасной деградации.
   СОВЕТЫ (при FAIL): исправить F-010 и F-012; заменить агрегированные заявления PASS точными ссылками на поведенческие оракулы.

   **F-010 [pre-existing] — повреждённая кодировка dynamic config прерывает запрос.**
   - priority: blocking.
   - locations: `server.py:1700`, `server.py:1704`.
   - Правило: REQ-003; fail-open конфигурации, `python-standards.md §3`.
   - Evidence: `read_text("utf-8")` может выбросить `UnicodeDecodeError`, обработчик ловит только `OSError`.
   - Следствие: повреждённый файл не приводит к `enabled=False`, как повреждённый JSON; исключение выходит из выбора транспорта.
   - Исправление: обрабатывать ошибку декодирования как недействительный конфиг, выбирать run и выдавать безопасную диагностику.
   - Проверка: невалидные UTF-8 байты при работающем Server не рвут запрос; последующее исправление файла восстанавливает переключение.

   **F-012 [pre-existing] — временной оракул не доказывает заявленные пределы и полноту.**
   - priority: blocking.
   - locations: `tests/test_realtime_reasoning.py:545`, `tests/test_realtime_reasoning.py:567`, `tests/test_realtime_reasoning.py:580`, `tests/test_realtime_reasoning.py:582`, `tests/test_realtime_reasoning.py:583`.
   - Правило: REQ-001, REQ-020, AC-001, AC-002, AC-026; `feature.md`, независимый сигнал полноты.
   - Evidence: проверяется интервал `<1.0`, хотя AC-001 требует `<0.5`; накладные расходы ≤250 мс не измеряются. `upstream_end_t = elapsed` — конец клиентского чтения, а не независимая отметка завершения апстрима.
   - RED действительно имеет `rc=1`, но конкретный AC-026 на baseline падает в `setUp` из-за отсутствия `DYNAMIC_CONFIG_PATH`, до временных assertions. Это подтверждает несовместимость старой реализации с новым API теста, но не чувствительность к буферизации.
   - Исправление: добавить независимые отметки отправки/завершения FakeServe, проверять оба численных предела и полный набор дельт; отдельно показать RED на реализации, которая принимает те же события, но буферизует их. Для AC-016 перенести матрицу interruption-сценариев на serve, а не ссылаться на зелёный legacy-модуль.
   - Проверка: намеренная буферизация и превышение каждого порога отдельно делают соответствующий тест красным.

   **F-017 — пояснения подавлений типов исправлены частично.**
   - priority: non-blocking.
   - locations: `tests/test_realtime_reasoning.py:324`, `tests/test_realtime_reasoning.py:325`, `tests/test_realtime_reasoning.py:1150`, `tests/test_realtime_reasoning.py:1154`.
   - Правило: FU-009; `python-standards.md §1`, запрет подавлений без конкретного объяснения.
   - Evidence: комментарии про «динамический JSON ответа моста» используются также для сужения bytes и результатов `patch.start()/stop()`.
   - Исправление: описать конкретное несоответствие typeshed/динамического значения для каждого подавления.
   - Проверка: причина соответствует подавляемому правилу и выражению; диагностик нового файла по-прежнему 0.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Остались разрывы владения ресурсами и общего дедлайна: подготовка окружения находится вне обработки отказов запуска, а контроль клиента начинается после нескольких блокирующих операций.
   СОВЕТЫ (при FAIL): выполнить F-003, F-004 и F-008; проверять весь жизненный цикл запроса, включая подготовку и cleanup.

   **F-003 [pre-existing] — общий deadline/cancellation не охватывает всю цепочку I/O.**
   - priority: blocking.
   - locations: `server.py:2395`, `server.py:2407`, `server.py:2910`, `server.py:2935`, `server.py:2956`, `server.py:2984`, `server.py:3059`, `server.py:3080`, `server.py:3347`, `server.py:3357`, `server.py:3368`.
   - Правило: `feature.md §2`; R-BULK-I1, T-LIFE/v1, REQ-008.
   - Evidence: setup использует фиксированные 3/5 секунд, `_ctrl_http` повторяет вызов; проверка клиента начинается лишь в основном цикле. Prompt имеет отдельный timeout 65 секунд. `resp.read()` ограничен socket timeout, но не абсолютным сроком всей операции.
   - Контрсценарий: два последовательных трёхсекундных control-вызова при уже отключившемся клиенте превышают требование обнаружения ≤5 секунд. Ответ, поступающий малыми порциями, способен продлевать чтение тела. Проверка только `_ServeLease.cleanup` не доказывает общий бюджет отмены.
   - Исправление: передавать единый абсолютный deadline и cancellation во все фазы; ограничивать операции остатком бюджета; обеспечить закрытие prompt-соединения и подтверждённое завершение reader/prompt-потоков; рассчитывать cleanup целиком.
   - Проверка: отключение и истечение срока на SPAWN/READY/CREATE/SUBSCRIBE/PROMPT/CLEANUP; после срока новые операции не стартуют, группа исчезает в AC-011.

   **F-004 — RW-004 не закрывает ошибку создания state-dir.**
   - priority: blocking.
   - locations: `server.py:1738`, `server.py:2891`, `server.py:2897`, `server.py:2929`.
   - Правило: RW-004; REQ-008; штатная классификация локального отказа.
   - Evidence: `tempfile.mkdtemp()` вызывается в `_serve_env` до `_spawn_serve` и до защищённого блока попытки.
   - Следствие: ENOSPC/EACCES выходит как обычный `OSError`, а не `ServeUnavailable`; SSE может классифицировать локальный отказ как уход клиента вместо предусмотренного fallback.
   - Исправление: включить создание окружения/state-dir в единую транзакцию запуска, переводить локальные ошибки в `ServeUnavailable`, освобождать уже выделенные ресурсы.
   - Проверка: fault injection на `mkdtemp`, генерацию окружения, pipe и Popen; штатная ошибка/fallback, отсутствие FD/port/state leftovers.

   **F-008 [pre-existing] — legacy cleanup считает смерть лидера смертью группы.**
   - priority: blocking.
   - locations: `server.py:1115`, `server.py:1116`, `server.py:1118`, `server.py:1119`.
   - Правило: REQ-008, AC-011, T-LIFE/v1.
   - Evidence: `_stop_proc` немедленно возвращается, если `proc.poll() is not None`; после TERM ожидает только непосредственный процесс.
   - Контрсценарий: run-лидер завершился, потомок продолжает жить и держать stdout. Watchdog вызывает `_stop_proc`, который ничего не завершает.
   - Исправление: проверять живость принадлежащей запросу группы независимо от лидера; после TERM подтверждать смерть группы и эскалировать при оставшихся членах.
   - Проверка: лидер завершился раньше потомка, потомок игнорирует TERM; группа отсутствует в установленный срок.

4. РИСКИ: VERDICT=FAIL
   WHY=Full Suite L2 зелёный, однако остаются потери usage, обход маскирования новых ошибок и недоказанные свойства временных тестов.
   СОВЕТЫ (при FAIL): выполнить F-006, F-013 и F-014; дополнить проверки, сохранив полный L2 и законную отсрочку L3.

   **F-006 [pre-existing] — SSE теряет usage некоторых повторов.**
   - priority: blocking.
   - locations: `server.py:5298`, `server.py:5319`, `server.py:5333`, `server.py:5351`.
   - Правило: REQ-014, AC-019; паритет SSE/JSON.
   - Evidence: usage суммируется на успехе и watchdog-retry, но переходы по prompt-status и transient-error выполняются до общей аккумуляции.
   - Контрсценарий: попытка получила `step.ended` с tokens, затем transient-error; recovery успешен — финальный SSE usage не включает первую попытку. JSON уже начисляет эти tokens до классификации.
   - Исправление: начислять usage каждой завершившейся попытки ровно один раз до ветвления.
   - Проверка: одинаковые попытки дают одинаковые итоговые input/output/cached/reasoning в SSE и JSON для всех retry-причин.

   **F-013 [pre-existing] — измерительные проверки находятся в обычном компонентном контуре.**
   - priority: blocking.
   - locations: `tests/test_realtime_reasoning.py:424`, `tests/test_realtime_reasoning.py:437`, `tests/test_realtime_reasoning.py:567`, `tests/test_realtime_reasoning.py:687`, `tests/test_realtime_reasoning.py:875`, `tests/test_realtime_reasoning.py:1281`, `tests/test_realtime_reasoning.py:1342`, `tests/test_realtime_reasoning.py:1401`.
   - Правило: `testing.md §7.2`, Serial Lane.
   - Evidence: реальные `monotonic`/sleep-проверки имеют жёсткие пороги и запускаются обычным полным suite без measured/heavy-маркеров.
   - Риск: нагрузка машины превращает проверку корректности в зависимость от планировщика; особенно узкое окно cleanup 3.9–4.9 секунды.
   - Исправление: переходы автоматов и бюджеты проверять FakeClock; реальные измерения выделить в measured/heavy и запускать отдельным последовательным гейтом.
   - Проверка: обычный suite детерминирован; отдельный измерительный гейт сохраняет AC-001/002/005/011/026 и включён в приёмку.

   **F-014 [pre-existing] — новые upstream-ошибки обходят маскирование.**
   - priority: blocking.
   - locations: `server.py:5347`, `server.py:6523`; принимающий helper — `server.py:1928`.
   - Правило: REQ-015; `security.md`, защита секретов; существующее `_mask_secrets`.
   - Evidence: `err.get('message')` напрямую вставляется в `_error_payload`; этот helper сохраняет message без очистки.
   - Риск: upstream transport/provider exception с токеном или credential попадает в клиентский SSE/JSON и далее может сохраняться потребителем. Legacy stderr-путь предварительно использует `_clean_err`.
   - Исправление: применять единый redaction к новым внешним диагностическим сообщениям до ответа/логирования; не передавать сырые исключения.
   - Проверка: sentinel-ключ, serve-password и proxy credentials в provider error отсутствуют в SSE, JSON и логах.

   **F-015 [pre-existing] — независимый лог уже содержит ResourceWarning.**
   - priority: non-blocking, вне разрешённого тестового файла.
   - locations: `tests/test_cli_failure.py:267`.
   - Правило: testing.md, гарантированная очистка ресурсов.
   - Evidence: `l2-green-ver002-unittest.log` содержит два `ResourceWarning: unclosed file` для прямого вызова `Run(...)._execute_once()`.
   - Исправление: отдельным follow-up гарантировать `Run.close()` в тесте либо контекстное владение объектом.
   - Проверка: соответствующий сценарий проходит без ResourceWarning. Это замечание не отменяет зафиксированный `rc=0` полного L2.

   **F-016 [pre-existing] — FU-004 закрыт не для всех tool-only завершений.**
   - priority: non-blocking.
   - locations: `server.py:3284`, `server.py:3307`.
   - Правило: FU-004, REQ-016.
   - Evidence: TTFT выставляется при завершении tool lifecycle, но fallback-сборка native-вызова на `step_finish` не устанавливает `first_token_at`/`ttft_ms`.
   - Исправление: использовать общую точку регистрации первого готового native-вызова и обновлять часы активности.
   - Проверка: tool input без `called/failed/success`, завершённый через `step.ended`, имеет числовой TTFT в конечном O-EXIT sink.

   Свидетельства L2 принимаю: 431 passed в компоненте, 894 passed и 5 skipped в корневом suite, обратный порядок зелёный, статический гейт — 0 ошибок. Подтверждения проверки дочерних crash-выходов через `run-guarded` или эквивалентный аудит в пакете нет: этот отдельный аспект **INCONCLUSIVE**, фактический crash не утверждаю.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve с сохранением run обоснован реальными дельтами, ротацией прокси и изоляцией `OPENCODE_DB=:memory:`. Прямой HTTP-вариант не доказан, общий демон конфликтует с ротацией. Оснований требовать смену выбранной архитектуры нет. Выявленные проблемы устраняются локально; обязательное переиспользование native-конвертера описано в F-007.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Периметр трёх файлов и stdlib соблюдён, замороженные функции сохранены. Однако транспортный адаптер дублирует семантику инструментов, а состояния доставки, повторов и ресурсов распределены между несколькими обработчиками и расходятся с декларативной таблицей.
   СОВЕТЫ (при FAIL): исправить F-001/F-003/F-007 через общие точки классификации и преобразования; сохранить существующие публичные схемы и разрешённый периметр. Перестройка проекта на Litestar/async и добавление runtime-зависимостей не требуются.

   **Verify-Fixed — каждый RW:**

   - RW-001: PASS — ранний `errno`; helper-оракулы, `server.py:20`, `tests/test_realtime_reasoning.py:1499`.
   - RW-002: PASS — timeout/client_gone обработаны до успеха в SSE/JSON; тест `:904`.
   - RW-003: PARTIAL — проверка результата перенесена перед очередью, 400/404/422 fail-closed; задержка тела скрывает уже полученный статус, F-001.
   - RW-004: FAIL — pipe/Popen очищаются, но mkdtemp остаётся снаружи, F-004.
   - RW-005: PASS — helper проверяет оставшихся членов группы; тест `:1532`.
   - RW-006: PASS — FIN/RST/закрытый fd и проверка перед JSON; тест `:1436`.
   - RW-007: PARTIAL — требуемые поведенческие сценарии добавлены; временная чувствительность и полная serve-матрица ещё не доказаны, F-012.
   - RW-008: PASS — блокирующий reader с внешним watchdog сохраняет паузу 1.4 секунды; тест `:1304`.
   - RW-009: FAIL — latch обходится исключениями и поздней фиксацией headers, F-001.
   - RW-010: PASS — общий spawn cap перед fallback run; тест `:1004`.
   - RW-011: PASS — текстовый tool-call закрывает step; тест `:1354`.
   - RW-012: PARTIAL — единый разделитель обычных serve-retry есть; обход через fallback остаётся, F-001.
   - RW-013: PASS — общий semantic-key dedup JSON; тест `:978`.
   - RW-014: PASS — callback освобождает gate до генерации, finally сохраняется; тест `:1314`.
   - RW-015: PASS — lease cleanup имеет отдельные окна TERM/KILL; тест `:1401`. Полный cancellation-бюджет — F-003.
   - RW-016: PASS — общий lock, Event, отмена таймера в finally; `server.py:4952`, `:6321`.
   - RW-017: PARTIAL — startup-gate contention покрыт; spawn-limiter оставляет немое окно, F-002.
   - RW-018: PASS — transient/429/5xx/timeout передаются в `attempt_done` с сохранением существующей request-level семантики breaker.
   - RW-019: PASS — один вызов `_run_env` на serve-попытку; оракулы `:1026`, `:1361`.

   **Сопутствующие FU:**

   - FU-001: PASS — неиспользуемая переменная заменена рабочим semantic-key dedup.
   - FU-002: PASS — JSON начисляет usage до retry-веток, `server.py:6452`.
   - FU-003: PASS — helper lstart сверяется в reaper.
   - FU-004: PARTIAL — F-016.
   - FU-005: PASS — совместимость pytest/unittest сохранена; прежнее согласованное решение не переоткрываю.
   - FU-006: PASS — `_LSOF_CALLS` ограничен `deque(maxlen=64)`.
   - FU-007: PASS — UID/symlink-проверки каталога и lease добавлены.
   - FU-008: PASS — массовое форматирование legacy не выполнено, frozen-срезы сохранены.
   - FU-009: PARTIAL — F-017.

   **Поштучная сверка требований и AC:**

   - REQ-001: PARTIAL. AC-001 — INCONCLUSIVE: предел теста 1 секунда вместо 500 мс, F-012. AC-002 — INCONCLUSIVE: независимого измерения ≤250 мс нет.
   - REQ-002: PASS по форме публичных HTTP/SSE схем. AC-003 — зелёные существующие проверки формата; семантическая регрессия аргументов инструментов отдельно блокируется F-007.
   - REQ-003: PARTIAL. AC-004 — PASS, полный legacy suite зелёный; повреждённый UTF-8 kill-switch — F-010.
   - REQ-004: FAIL. AC-005 — не обеспечен на ожидании limiter, F-002.
   - REQ-005: PARTIAL. AC-006 — нормальные дельты сохранены, фрагментированные interruption-маркеры обрабатываются иначе, F-011. AC-007 — PASS, reasoning истории исключён из prompt.
   - REQ-006: PARTIAL. AC-008 — serve/SSE watchdog реализован, JSON/run отсутствует, F-009; строгий бюджет обнаружения и cleanup полностью не доказан, F-003.
   - REQ-007: PARTIAL. AC-009 — stall реализован для serve/SSE. AC-010 — first-token реализован для serve/SSE. JSON/run остаётся без обоих, F-009.
   - REQ-008: FAIL. AC-011 — есть helper/lease-оракулы, но legacy группа и полный путь отмены не закрыты, F-003/F-008. AC-012 — ранний socket detector исправлен, setup-фазы не покрыты.
   - REQ-009: PARTIAL. AC-013 — PASS, потолок трёх запусков сохранён. AC-014 — обычные serve-retry имеют один разделитель; исключительный fallback нарушает барьер, F-001.
   - REQ-010: PASS по сохранённому инкрементальному парсеру и split-tool сценарию. AC-015 — существующие parser-проверки зелёные, сам `ToolCallParser` не переписан.
   - REQ-011: FAIL. AC-016 — полная interruption-матрица на новом транспорте не предъявлена; найдены F-005/F-007/F-011.
   - REQ-012: FAIL по эквивалентности native mapping. AC-017 — bash happy path есть, общего паритета с legacy нет, F-007. Ask/reject и отмена формы сами по себе обоснованы.
   - REQ-013: PASS для ротации, gate, limiter и bulkhead. AC-018 — один сдвиг пула на попытку подтверждён оракулами; проблемы deadline выделены отдельно.
   - REQ-014: PARTIAL. AC-019 — базовое отображение tokens есть, суммарный SSE usage на ошибочных попытках неверен, F-006.
   - REQ-015: PARTIAL. AC-020 — случайный пароль и allowlist реализованы; отдельный log-redaction оракул не предъявлен, новые клиентские ошибки обходят маскирование, F-014.
   - REQ-016: PARTIAL. AC-021 — поля присутствуют в O-EXIT; tool-only TTFT неполон, F-016.
   - REQ-017: PASS. AC-022 — полный компонентный suite зелёный. AC-023 — обратный порядок также зелёный.
   - REQ-018: PASS. AC-024 — Google-тесты зелёные, обе функции побайтово неизменны.
   - REQ-019: DEFERRED_L3. AC-025 — законно отложен до ACCEPT, отказа по этому основанию нет.
   - REQ-020: PARTIAL. AC-026 — сокетный тест существует и зелёный; RED `rc=1` подтверждён, но независимый temporal-oracle требует исправления F-012.

   **Границы:**

   - Non-Goal 1: публичные пути, порт и формы SSE сохранены; native-аргументы требуют исправления F-007.
   - Non-Goal 2: DSH, профиль и `ReasoningRow` не изменены.
   - Non-Goal 3: специальной модификации reasoning ради превью нет; фрагментация очистки — F-011.
   - Non-Goal 4: модель, каталог и выбор effort не заменены.
   - Non-Goal 5: другие мосты и общие конфиги не изменены.
   - Non-Goal 6: внешние runtime-зависимости не добавлены.
   - Forbidden Scope 1: кандидат ограничен тремя разрешёнными файлами.
   - Forbidden Scope 2: хардкода рабочих секретов не найдено; обход redaction — F-014.
   - Forbidden Scope 3: боевой деплой законно отложен.
   - Forbidden Scope 4: вызовов `security find-generic-password` в представленном исполнении нет.
   - Forbidden Scope 5: `OPENCODE_DB=:memory:`; прямой правки общей БД нет.
   - Forbidden Scope 6: коммит/merge в защищённую ветку не предъявлен и судьёй не выполнялся.

   Применимость стандартов: async/Litestar/SQLAlchemy/Redis-специфичные требования здесь N/A. JSON stdlib допустим для автономного моста. Обязательные общие свойства deadline, cancellation, владения группой, redaction и независимой проверки полноты применимы и отражены в находках. Локальное создание изолированной serve-сессии соответствует выбранному транспорту; требование общего демона не навязывается.

   **SUB-строки, проход 1–14:**

   SUB Корректность/логика: FAIL — исключительный fallback обходит latch доставки; native mapping расходится с legacy (`server.py:5229`, `server.py:2832`; F-001/F-007).
   
   SUB Корректность/граничные условия: FAIL — ожидание limiter и разрезанный interruption-маркер нарушают требования (`server.py:5811`, `server.py:5127`; F-002/F-011).
   
   SUB Корректность/обработка ошибок: FAIL — mkdtemp не классифицируется как ServeUnavailable, повреждённый UTF-8 выходит наружу (`server.py:1738`, `server.py:1700`; F-004/F-010).
   
   SUB Полнота/покрытие AC: FAIL — AC-001/002/026 не доказаны независимым временным оракулом (`tests/test_realtime_reasoning.py:580`, `:582`; F-012).
   
   SUB Полнота/пропущенные ветки: FAIL — JSON/run не имеет watchdog; JSON retry теряет текущий вывод (`server.py:4824`, `server.py:6477`; F-005/F-009).
   
   SUB Реализуемость/общее: FAIL — setup/cleanup не подчинены общему deadline/cancellation (`server.py:2935`, `server.py:3347`; F-003).
   
   SUB Риски/безопасность: FAIL — сырые provider messages обходят redaction (`server.py:5347`, `server.py:6523`; F-014).
   
   SUB Риски/данные: FAIL — частичный JSON-результат и SSE usage теряются на повторах (`server.py:6527`, `server.py:5333`; F-005/F-006).
   
   SUB Риски/прод: FAIL — смерть run-лидера оставляет группу вне cleanup (`server.py:1115`; F-008).
   
   SUB Риски/regression red→green: FAIL — RED rc=1 валиден, но AC-026 падает в setup и не доказывает чувствительность к буферизации (`tests/test_realtime_reasoning.py:545`; F-012).
   
   SUB Риски/Full Suite (L2): PASS — независимые VER-001/002/003/003b/004/005 и AC-023 зелёные (`execution-evidence.md`; полный компонентный и корневой прогоны).
   
   SUB Риски/scope-diff: PASS — ровно три разрешённых файла, frozen hashes совпадают (`candidate-manifest.json`, `receipts/code-gate.json`).
   
   SUB Альтернативы/общее: PASS — serve даёт измеренные дельты, run сохраняет откат, общий демон затрудняет ротацию (`handoff-architect.md §4`, F-19/F-40).
   
   SUB Соответствие контексту/общее: FAIL — новый native-адаптер дублирует и сужает существующую семантику; таблица fallback расходится с обработчиками (`server.py:2832`, `server.py:5294`; F-001/F-007).

   Self-sweep выполнен по всем 14 подкатегориям. L3 не подменён L2 и не использован как основание FAIL. Стилевых требований сменить архитектуру без воспроизводимого дефекта не выставлено.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `grok-4.7-high`)

PANEL-NONCE: c212c4c89ca22820
ARTIFACT-SHA256: 674edaca247fa44fb9639f81a52dbfe62235889400a00a99eec3f6c321db2b82
Канон прочитан: AGENTS.md, 430 строк

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Цикл 3 закрывает RW-001..RW-008 и RW-010..RW-019: `errno` до ветки `--serve-helper`; `timeout`/`client_gone` до `record_success()`; `prompt_status` 400/404/422 как `ServeSecurityError` до `events.get`; уборка старта; SIGKILL группы и окно 4+2 с; `_client_gone_check` на RST; пауза SSE 1.4 с без ложного EOF; `can_spawn` в JSON; текстовый `tool_calls` на `step_finish`; один разделитель на return-ретрае; дедуп JSON по `_call_key`; `_StartupGate` по готовности и в `finally`; замок `wfile` и `cancel` таймера; `attempt_done(True, False)` на транзиентных 429/5xx; один шаг пула прокси. Публичный маршрут не добавлен, замороженные `_run_env` / `_stream_google_sse` / `_execute_google_once` совпали с sha256 из гейта, потолок `MAX_TOTAL_SPAWNS=3` сохранён (REQ-017: оракулы ждут 3 запуска). RW-009 закрыт только на возврате результата: `_delivered_now` на `server.py:5257-5279` читает `delivered_any`. Ветки исключения и лимитера этот latch не читают и после уже отданного клиенту reasoning уходят в тихий `opencode run` без строки «[мост] Повтор попытки».
   СОВЕТЫ: (1) В `except ServeUnavailable` и при отказе `spawn_limiter` на serve (SSE и JSON) перед `return False` смотреть монотонный latch: SSE — `delivered_any[0]`, JSON — уже накопленные `contents` / `reasonings_all` / `tool_calls_all`. (2) Если модельный чанк уже ушёл клиенту, оставаться на serve-retry или завершать `_sse_error` / HTTP 502, эмитить ровно один разделитель, не вызывать `record_success()`, не продолжать тот же ответ через `opencode run`. (3) Синтетический `[мост]` по-прежнему не ставит latch: иначе fallback после INITIAL на 0.65 с недостижим. (4) Регрессионный тест: попытка 1 отдаёт reasoning, попытка 2 бросает `ServeUnavailable`; соседний кейс — timeout лимитера на попытке 2. Ожидание: нет spawn `run`, ровно один разделитель или терминальная ошибка.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=AC-001..AC-013, AC-015..AC-024 и AC-026 на возвратном пути и в L2 закрыты (VER-001: 431 passed). AC-014 («ровно одна статусная строка между попытками», без тихого fallback после отданного размышления) не выполняется на исключении и на лимитере: разделитель стоит только на `server.py:5206-5210`, то есть после проверки лимитера и вне `except ServeUnavailable`. Follow-up, не второй блокер: при `TRANSPORT=run` таймер статуса отменяется на `server.py:5809-5811` до `spawn_limiter.acquire` (`SPAWN_WAIT_MAX_S=5.0` на `:565`), поэтому при насыщенном лимитере первый `[мост]` может выйти позже 1.0 с; кейс StartupGate из RW-017 зелёный. Follow-up: JSON step-recovery при `transient_error` собирает промпт из `contents` (`server.py:6511-6520`), а `contents` дописывается только после успеха; SSE берёт уже отданный `collected_texts`. DSH ходит `stream:true` (F-35).
   СОВЕТЫ: (1) Закрыть AC-014 на всех четырёх `return False` из F-001. (2) Follow-up: не гасить защитный таймер до выхода из `spawn_limiter.acquire`, не дублируя `STATUS_INITIAL` и не ломая быстрый путь `test_go_model_routing`. (3) Follow-up: в JSON-recovery передавать в `_incomplete_tool_step_prompt` текст текущей попытки (`texts`), как SSE передаёт `collected_texts`.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Короткоживущий `opencode serve` на запрос поднимается stdlib-процессами (helper, lease, Basic-пароль на попытку, `OPENCODE_DB=:memory:`), без новых runtime-зависимостей. Kill-switch рабочий: `_select_transport` (`server.py:1761-1788`) по умолчанию `auto`, файл `~/.dsh/bridges/opencode-zen-bridge/disable-serve`, override env и `dynamic_config.json` (нет файла = serve выключен). Группа убивается в `finally`, reaper на старте сверяет uid и symlink. L2 зелёный (431 тест, ruff/basedpyright 0 errors). Живой прогон против настоящего `opencode serve` законно отложен (`VER-006`/`VER-007` = `DEFERRED_L3` до ACCEPT). Внедрение после F-001 операционно то же: один Python-процесс, потолок 3 spawn, откат на `run`.

4. РИСКИ: VERDICT=FAIL
   WHY=Full suite L2 зелёный и порядок-независимый: VER-001 `rc=0` (431 passed, 3173 subtests), VER-002 unittest 431 OK, AC-023 reversed `rc=0`, RED на `origin/dev` `rc=1` (новых символов нет). Секрет serve — `secrets.token_hex(16)`, в лог не пишется; allowlist срезает произвольный env; 401/403/400 fail-closed без инкремента health. Дыра F-001 тестом не ловится: `test_retry_separator_once_and_delivery_barrier_is_monotonic` подменяет `_serve_one_attempt` возвратами `stall_timeout` / `first_event_timeout` и не бросает `ServeUnavailable` и не упирается в лимитер. После частичной доставки это тихий второй транспорт в том же SSE и потеря JSON-накопления. Скрытый долг возвратного пути (watchdog, cap, dedup, gate) этим прогоном закрыт.
   СОВЕТЫ: (1) Добавить в `tests/test_realtime_reasoning.py` два оракула к F-001: `ServeUnavailable` на второй попытке после reasoning и отказ `spawn_limiter` на второй попытке. (2) Проверять отсутствие вызова `Run`/`opencode run`, ровно один разделитель либо терминальную ошибку, и что `record_success` не вызван. (3) Оставить зелёными текущие 431 тест и замороженные sha256.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбор — вариант A1 архитектора (serve на запрос) с откатом на `run`, как в `muse-bridge` (F-40). Общий демон A2 ломает ротацию IP, прямой Zen без заголовков дал 429 (F-24, F-25). Объём helper/lease оправдан REQ-008 (нет осиротевших `opencode serve`). Замена блокирующего `readline`+`shutdown` на `select`+`recv` (RW-008) поведенчески не нужна: пауза 1.4 с в L2 зелёная. Переписывания ради стиля нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Дельта ровно в трёх файлах конверта: `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`. Новых зависимостей нет (`dependencies = []`). Google-срез и `_run_env` побайтово те же (`run_env_sha256=1c51b28f…`, `google_direct_unchanged=true`). Синтетические строки `[мост] …\n` заданы REQ-004/REQ-005, в промпт реплея не попадают. `json` стандартной библиотеки здесь обязателен: orjson/Litestar/Redis в этом мосте вне задачи. Пересчёт сида: `seed_input` дословен, `SHA-256` = `1ab7cac3f5917dc822365018f78bb6d7eecd50b5554c42571b5e59b929621e22`, `SEED=1ab7cac3`, совпало с `manifest.json` r25. `ranked_order` по пулу `table["setups"]["default"]` не могу проверить: таблица слотов в пакет раунда не вложена; опубликованный порядок в манифесте — `grok-4.7-high`, `gpt-6.1-sol-high`, `claude-sonnet-5-5-high`, `muse-wonder-full-1.0`, `gemini-4-argon-high`.

F-001
priority: blocking
criteria: КОРРЕКТНОСТЬ, ПОЛНОТА, РИСКИ
locations: bridges/opencode-zen-bridge/server.py:5198-5201, bridges/opencode-zen-bridge/server.py:5229-5234, bridges/opencode-zen-bridge/server.py:6407-6409, bridges/opencode-zen-bridge/server.py:6431-6434
rule: RW-009, REQ-009, AC-014
evidence: Latch ставится только модельным чанком (`delivered_any[0] = True` в `on_reasoning` / `_text_seen`, `server.py:5112-5124` и `:5185-5191`). Возврат результата это учитывает (`_delivered_now` включает `delivered_any[0]`, `:5257-5279`). Исключение и лимитер — нет. SSE-лимитер: `if not _limiter_ok: … if not force_serve: return False` (`:5198-5201`), разделитель на `:5206-5210` уже не исполняется. SSE: `except ServeUnavailable: … if not force_serve: return False` (`:5229-5234`) без чтения `delivered_any`. Те же `return False` в JSON на `:6407-6409` и `:6431-6434`. Сценарий: попытка 1 отдала reasoning и ушла в `stall_timeout` (serve-retry), попытка 2 падает на spawn/ready/create/prompt с `ServeUnavailable` до своих токенов. Клиент уже видел мысль; тот же SSE продолжается через `opencode run` без «[мост] Повтор попытки».
expected: Если latch уже установлен, не возвращать fallback на `run`: serve-retry или терминальная ошибка, ровно один разделитель, без `record_success()`. Синтетический статус latch не ставит.
check: Тест с reasoning на попытке 1 и `ServeUnavailable` либо timeout лимитера на попытке 2; нет четвёртого и нет legacy-spawn поверх уже отданного reasoning; один разделитель или `_sse_error`/502.

SUB Корректность/логика: FAIL — evidence (bridges/opencode-zen-bridge/server.py:5229-5234, RW-009: `return False` мимо `delivered_any`)
SUB Корректность/граничные условия: FAIL — evidence (server.py:5198-5201 и :6431-6434: fallback после уже отданной попытки и при отказе лимитера)
SUB Корректность/обработка ошибок: FAIL — evidence (server.py:5229-5234: `ServeUnavailable` не терминал и не retry, а тихий run)
SUB Полнота/покрытие AC: FAIL — evidence (AC-014 / REQ-009: разделитель только на server.py:5206-5210, ветки F-001 его пропускают)
SUB Полнота/пропущенные ветки: FAIL — evidence (server.py:5257-5279 читает latch, :5229-5234 и :5198-5201 — нет)
SUB Реализуемость/общее: PASS — evidence (server.py:1761-1788 kill-switch; L2 VER-001 rc=0; VER-006/007 DEFERRED_L3)
SUB Риски/безопасность: PASS — evidence (fail-closed 401/403/400, пароль `token_hex(16)`, allowlist без произвольного env, AC-020)
SUB Риски/данные: PASS — evidence (`OPENCODE_DB=:memory:`, lease uid/symlink, usage `input/output/cached/reasoning`)
SUB Риски/прод: PASS — evidence (дефолт serve выключен, reaper+killpg, живой :9883 не мутируется до ACCEPT)
SUB Риски/regression red→green: FAIL — evidence (tests/test_realtime_reasoning.py `test_retry_separator_once_and_delivery_barrier_is_monotonic` подменяет возврат, не `ServeUnavailable` и не лимитер)
SUB Риски/Full Suite (L2): PASS — evidence (execution-evidence.md VER-001 rc=0, 431 passed; AC-023 reversed rc=0; RED rc=1 на origin/dev)
SUB Риски/scope-diff: PASS — evidence (candidate-manifest.json: ровно 3 файла; code-gate `google_direct_unchanged=true`; dependencies=[])
SUB Альтернативы/общее: PASS — evidence (A1 архитектора + fallback muse-bridge F-40; потолок spawn=3 сохранён)
SUB Соответствие контексту/общее: PASS — evidence (REQ-004 требует `[мост]`; frozen sha256 MATCH; seed_hex `1ab7cac3f5917dc822365018f78bb6d7eecd50b5554c42571b5e59b929621e22` MATCH; ranked_order по пулу слотов не могу проверить)

ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `claude-sonnet-5-5-high`)

PANEL-NONCE: 6fb09ef7bad10ab6
ARTIFACT-SHA256: 674edaca247fa44fb9639f81a52dbfe62235889400a00a99eec3f6c321db2b82

**Verify-fixed цикла 3.** RW-001..RW-008 и RW-010..RW-019 закрыты по diff и поведенческим оракулам (errno до ветки helper, timeout/client_gone не успех, ранняя проверка prompt_status, атомарный `_spawn_serve`, SIGKILL группы, окна cleanup 4.0 + 2.0 с, замок `wfile`, один сдвиг пула прокси и т.д.). RW-009 закрыт не полностью: см. F-02.

Строк в diff нет, поэтому `file:line` даны как функция и `@@`-ханк. Точные номера строк не могу проверить.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Есть два дефекта поведения. Watchdog первого токена на legacy-пути убивает легитимно долгое размышление (F-01). Монотонный барьер доставки (RW-009) не соблюдается на ветке `ServeUnavailable` (F-02).
   СОВЕТЫ (при FAIL):
   - Исправить F-01: на legacy-пути для `first_token_timeout` учитывать только токены. Либо поднять порог, либо считать `step_start` признаком живости.
   - Исправить F-02: проверять `delivered_any[0]` в ветке `ServeUnavailable`.
   - Закрыть F-03, F-04 и F-12.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Не покрыта ветка «`ServeUnavailable` после частичной доставки». Тесты RW-009 проверяют только возвращаемые результаты, не исключение. FakeServe пишет тот же автор, что и клиент, поэтому реальные контракты permission reply и form cancel не подтверждены (F-06). Нескольких веток из таблицы нет в тестах: HTTP 401/403, TTL деградации, disable-файл.
   СОВЕТЫ (при FAIL):
   - Добавить тест на `ServeUnavailable` на попытке 2 после reasoning в попытке 1.
   - Усилить слабые тесты (`test_transport_matrix`, `test_elf_magic_and_tool_status`, `test_helper_argv_validation_and_lease_dir`).
   - После ACCEPT записать реальный wire-фикстур `opencode serve` v2.1.2 для permission, form и tool-событий.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Решение собирается в рамках stdlib и 3 целевых файлов. Clean-room L2 зелёный: 431 passed, unittest OK, обратный порядок OK, `_run_env` и Google-функции побайтово неизменны. Serve по умолчанию выключен, kill-switch есть (`dynamic_config.json`, disable-файл, `TRANSPORT=run`). Рост `server.py` до около 7000 строк и встроенный супервизор процессов — долг сопровождения, но не блокер.
   СОВЕТЫ (при FAIL): —

4. РИСКИ: VERDICT=FAIL
   WHY=Регрессия на пути по умолчанию (F-01). Дублирование контента при fallback после доставки (F-02). Накладные расходы `lsof`/`ps` на запуск (F-07). Изменения legacy-пути без фичефлага (F-08).
   СОВЕТЫ (при FAIL):
   - Закрыть F-01 и F-02.
   - Заменить поллинг `lsof` на ожидание handshake или `bind`-проверку.
   - Выделить легаси-watchdog и статусы под отключаемый флаг.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбор A1 (serve на запрос, fallback на run, прецедент muse-bridge) обоснован Arch Panel и фактами F-19..F-22. Цена: примерно 110 мс и 152 MiB RSS на запрос и свой супервизор. A2 (общий демон) и B (прямой HTTP) отклонены обоснованно: ротация IP и 429. Стратегически стоит вынести транспорт в отдельный модуль (non-blocking).
   СОВЕТЫ (при FAIL): —

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Нарушены принципы проекта по non-blocking пунктам. Тесты содержат wall-clock-проверки (testing.md, F-09). Неотносящийся reformat legacy-кода раздувает diff (F-10, scope-diff). Комментарии `pyright: ignore` с неверными причинами (F-11). Расхождение декларативной таблицы с обработчиками (F-05).
   СОВЕТЫ (при FAIL):
   - Убрать wall-clock-допуски через инъекцию `FakeClock` или допуски на порядок.
   - Откатить косметические правки legacy-кода.
   - Исправить причины в ignore-комментариях.

**F-блоки**

F-01 [blocking] КОРРЕКТНОСТЬ / Риски-прод.
- Locations: `server.py::Handler._stream_sse.send_keepalive` (проверка `first_token_timeout`, `FIRST_TOKEN_TIMEOUT_S=60`); `watchdog_state["first_token_at"]`.
- Правило: REQ-007, REQ-009, F-17/F-18/F-32, R-BULK-I2.
- Evidence: legacy `opencode run` отдаёт reasoning и text одним блоком в конце шага (F-17/F-18). Первый «токен» наступает только по окончании всего размышления. Легитимные запросы длятся до 85.65 с (F-32). Порог 60 с от `attempt_start` убьёт такой запрос и потратит до 3 запусков. Путь `run` — default при `REALTIME_SERVE_ENABLED=false`.
- Fix: на legacy-пути не применять `first_token_timeout` к размышлению. Либо поднять порог до значения выше наблюдаемого максимума, либо считать токеном `step_start` и stdout-активность.
- Критерий: тест с fake-CLI, молчащим 65 с после `step_start` и затем отдающим ответ, завершается успехом без ретрая.

F-02 [blocking] КОРРЕКТНОСТЬ / Полнота-ветки. RW-009 не закрыт.
- Locations: `Handler._run_serve_stream_attempts`, `except ServeUnavailable` (ветка `if not force_serve: return False`); `Handler._serve_json_serve` (аналогично); `tests/test_realtime_reasoning.py::test_retry_separator_once_and_delivery_barrier_is_monotonic`.
- Правило: RW-009, REQ-009/AC-014.
- Evidence: после доставки `reasoning` или `text` клиенту ветка `ServeUnavailable` на следующей попытке не проверяет `delivered_any[0]` и возвращает `False`. Legacy-цикл стартует заново: `dedup[0]` создаётся только при `incomplete_retry`, поэтому reasoning и text отправляются повторно.
- Fix: при `delivered_any[0]` не делать fallback на run. Вместо этого вызвать `allow_retry` или отдать SSE-ошибку.
- Критерий: тест с мок-`_serve_one_attempt`, где 1-я попытка отдаёт reasoning, а 2-я бросает `ServeUnavailable`. Клиент не получает повторного текста и не уходит на run.

F-03 [non-blocking] ПОЛНОТА / Корректность-границы.
- Locations: `_run_serve_stream_attempts` (`on_status(f"[мост] Повтор попытки …")`); `_stream_sse` (`emit_synthetic(... Повтор попытки ...)`).
- Evidence: разделитель повтора не зависит от `thinking_enabled`, а статусы ожидания зависят. При `effort=off` после текста клиент получит `reasoning_content` «[мост]…».
- Fix: гейтить разделитель по `thinking`.
- Критерий: при `effort=off` в потоке нет `[мост]`.

F-04 [non-blocking] КОРРЕКТНОСТЬ-границы.
- Locations: `_serve_one_attempt`, ветка `form.created` (`terminal="cancelled"`); обработчики вызывают `serve_health.record_success()`.
- Evidence: отмена формы без текста и tool_calls в SSE завершается `finish_reason=stop` с пустым ответом и записывается как успех. JSON-путь даёт 502.
- Fix: единая политика: ошибка либо явный маркер, `record_success` не вызывать.
- Критерий: SSE и JSON ведут себя одинаково.

F-05 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ / Обработка ошибок.
- Locations: `FALLBACK_DECISION_TABLE`; алиасы `_find_listener_pid`, `parse_serve_event`, `_dynamic_config_enabled`, `_ToolInputAccumulator`; `test_serve_health_and_fallback_table`.
- Evidence: таблица не исполняется. Строка «HTTP 429/5xx → serve_retry» расходится с кодом: при отсутствии модельного вывода код уходит в `run`. Тест проверяет только поля таблицы.
- Fix: сделать таблицу единственным источником решений либо удалить её и мёртвые алиасы. Перевести тест на проверку поведения.

F-06 [non-blocking] ПОЛНОТА / покрытие AC.
- Locations: `tests/test_realtime_reasoning.py` (FakeServe; `test_transport_matrix`, `test_elf_magic_and_tool_status`, `test_helper_argv_validation_and_lease_dir`).
- Evidence: эндпоинты `permission/{id}/reply` и `form/{id}/cancel` не входят в проверенный F-22. Тест только валидирует собственную подделку. Названия тестов шире assertions.
- Fix: до heavy-приёмки зафиксировать реальные ответы serve v2.1.2. Усилить указанные тесты.

F-07 [non-blocking] РИСКИ-прод.
- Locations: `_spawn_serve` (цикл `_lsof_listener_pid` с шагом 50 мс до 3 с), `_parent_lstart`, `_run_serve_helper_cli._group_members`.
- Evidence: каждая попытка запускает `ps` и `lsof` как подпроцессы. На macOS `lsof` стоит сотни мс и добавляет задержку к TTFT. Это противоречит цели отзывчивости.
- Fix: ждать handshake без `lsof`-поллинга либо делать один `lsof` после handshake.

F-08 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ (директива про фичефлаги).
- Locations: `send_keepalive` (watchdog и статусы), `_StdoutFeed.lines(on_idle)`, `O-EXIT/v1`.
- Evidence: поведение legacy-пути меняется без флага. Отключение только через экстремальные env-пороги. `dynamic_config.json` локальный, не удалённый GigaRC.
- Применимость GigaRC к автономному stdlib-мосту не могу проверить.
- Fix: единый флаг и kill-switch для legacy-watchdog и статусов.

F-09 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ (testing.md, wall-clock).
- Locations: `test_lease_cleanup_confirms_sigkill_in_separate_window` (`>=3.9`/`<=4.9` с), `test_ac026_realtime_chunks_before_upstream_end`, `test_slow_upstream_gets_initial_status_before_1s`, `test_initial_status_before_1s_under_startup_gate_contention`.
- Evidence: проверки реального времени flaky в CI. Файл идёт 81 с.
- Fix: `FakeClock` либо широкие допуски; жёсткие тайминги вынести под marker measured.

F-10 [non-blocking] РИСКИ-scope-diff.
- Locations: `server.py` — `Run.execute`, `Run._execute_once`, `_UpstreamBreaker`, `_RequestAttempts.__init__`, `_PrefixDedup.push`, `CATALOG_*`, `_drain_stderr`; `tests/test_step_interruption.py` (`r'''` → `r"""`).
- Evidence: косметический reformat кода вне задачи (FU-008 требует минимального diff). Растёт blast radius и риск конфликтов.
- Fix: откатить стилистические правки вне функциональных ханков.

F-11 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ (FU-009 не закрыт).
- Locations: `tests/test_realtime_reasoning.py` (`_write_exe`, `_Bridge.post_*`, `test_fake_rt_mode_preset_preserved`: `# pyright: ignore[...] — причина: ответ моста — динамический JSON`).
- Evidence: одна и та же причина вставлена на несвязанные строки (`path.write_text`, `patcher.start()`).
- Fix: точные причины либо типизировать вместо ignore.

F-12 [non-blocking] [sweep] КОРРЕКТНОСТЬ-данные.
- Locations: `_ServeToolState.complete` (статус `completed` при `"called"` в типе события); `_serve_env` (`mkdtemp` в тесте `test_serve_env_sanitized_all_branches` без удаления).
- Evidence: `session.tool.called` означает вызов, а не выполнение. Тест оставляет `zen-serve-state-*` в tmp.
- Fix: статус из реального исхода; очистка каталога в тесте.

SUB Корректность/логика: FAIL — `send_keepalive`: `first_token_timeout` на legacy (F-01)
SUB Корректность/граничные условия: FAIL — разделитель повтора без `thinking`, пустой успех при cancelled form (F-03, F-04)
SUB Корректность/обработка ошибок: FAIL — `except ServeUnavailable` обходит барьер доставки (F-02)
SUB Полнота/покрытие AC: FAIL — FakeServe без реальных wire-фикстур, слабые тесты (F-06)
SUB Полнота/пропущенные ветки: FAIL — `ServeUnavailable` после частичной доставки не покрыта (F-02)
SUB Реализуемость/общее: PASS — stdlib, 3 файла, kill-switch, 431 passed в clean-room
SUB Риски/безопасность: PASS — loopback Basic-пароль, allowlist env, проверка uid/симлинков lease и `--serve-helper` в команде, listener-ownership
SUB Риски/данные: PASS — `OPENCODE_DB=:memory:` и изолированный state-dir, общая БД не затронута
SUB Риски/прод: FAIL — F-01 на пути по умолчанию, `lsof`-оверхед (F-07), нет флага (F-08)
SUB Риски/regression red→green: PASS — `red_sensitivity_rc=1`, 47 failed на origin/dev (часть падений — отсутствие символов; поведенческая часть подтверждена только в coder.json)
SUB Риски/Full Suite (L2): PASS — `receipts/code-gate.json`: pytest 431 passed, unittest OK, обратный порядок OK
SUB Риски/scope-diff: FAIL — косметический reformat legacy-кода (F-10)
SUB Альтернативы/общее: PASS — A1 с fallback по прецеденту muse-bridge (F-19..F-22, F-40)
SUB Соответствие контексту/общее: FAIL — wall-clock-тесты, неверные ignore-причины, дрейф таблицы (F-05, F-09, F-11)

ОБЩИЙ ВЕРДИКТ: NEEDS WORK


---

## Раунд D1 (`panel/council/r29`)

### Seat 1 (`skeptic`, `gpt-6.1-sol-high`)

PANEL-NONCE: b0f4b813abae6706
ARTIFACT-SHA256: 674edaca247fa44fb9639f81a52dbfe62235889400a00a99eec3f6c321db2b82

Предоставленный канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до `<!-- КАНОН-КОНЕЦ -->`. Проектные правила AI-SDLC прочитаны в приложенных обёртках; дополнительные файлы рабочей папки не открывал. Тесты не запускал, результаты принимаю только из независимого `execution-evidence.md`. Ниже пути относительно `bridges/opencode-zen-bridge/`.

DISPUTE F-018 — класс: duplicate_of:F-001 — контр-evidence: `server.py:5198–5201`, `:5229–5234`, `:6407–6409`, `:6431–6434` — подтверждаю дефект: исключение и отказ лимитера допускают fallback без проверки накопленной доставки. Это тот же root cause, уже включённый в F-001, а не отдельный блокер.

DISPUTE F-019 — класс: invalid — контр-evidence: REQ-007 прямо задаёт настраиваемый watchdog первого токена с рабочим порогом 60 секунд; `server.py:5979–6008` различает событие и токен. Максимальная длительность завершённого запроса 85,65 секунды из F-32 не доказывает отсутствие токенов первые 60 секунд конкретной попытки. Предлагаемое признание `step_start` токеном противоречит этому различию. Политику legacy-порога можно пересмотреть отдельно по замерам, но предъявленного нарушения согласованного требования нет.

DISPUTE F-020 — класс: duplicate_of:F-001 — контр-evidence: `server.py:5229–5234`, `:6431–6434` — ветка `ServeUnavailable` действительно обходит общий барьер; это уже F-001 и тот же дефект, что F-018.

DISPUTE F-021 — класс: invalid — контр-evidence: REQ-009/AC-014 требуют отдельного разделителя повторов; `server.py:5206–5210`, `:6140–6144` реализуют его отдельно от периодических статусов. В приложенных требованиях нет общего запрета служебного `reasoning_content` при `effort=off`. Несогласованная политика отображения сама по себе не доказывает дефект; условие «никакого `[мост]` при off» нельзя добавлять как установленный AC.

AGREE F-022 rev=1 — проверил: `server.py:5350–5351`, `:6526–6528` — отменённая форма проходит в ветку успеха, а JSON дополнительно проверяет наличие итогового текста/инструментов и возвращает 502 при пустом результате. Различие SSE/JSON подтверждается кодом. Сохраняю non-blocking: запрет исполнения формы выполнен; требуемый клиентский исход отмены отдельно не определён.

DISPUTE F-023 — класс: duplicate_of:F-001 — контр-evidence: `server.py:3112`, `:5294–5298`, `:6486–6490` — расхождение таблицы и обработки prompt HTTP 429/5xx уже включено в F-001 как нарушение барьера доставки. Неисполняемость декларативной таблицы и наличие алиасов отдельно не доказывают дефекта. Удаление таблицы не исправит неправильный переход.

AMEND F-024 — priority=non-blocking; locations=`tests/test_realtime_reasoning.py:1129`, `tests/test_realtime_reasoning.py:1170`; fix=добавить фактическую проверку disable-файла, сигнатуры бинаря и значения tool-status либо сузить названия тестов; реальный form/permission wire проверить в предусмотренном L3 — причина: assertions уже названных тестов уже их описаний. Однако F-22 **содержит** `/permission/{requestID}/reply`; тезис об отсутствии этого endpoint в проверенном перечне неверен. Проверка реального источника законно отложена до ACCEPT и не становится дополнительным блокером L2.

DISPUTE F-025 — класс: invalid — контр-evidence: `server.py:2612–2634`, F-20 и `execution-evidence.md` — вызовы `ps`/`lsof` присутствуют, но отдельного замера их стоимости и нарушения AC из-за них нет. Утверждение про «сотни миллисекунд» в этом прогоне не подтверждено. Handshake сообщает PID, но не доказывает владение TCP-слушателем; заменять им ownership-проверку без эквивалентной защиты нельзя. Измерение допустимо как последующая оптимизация.

DISPUTE F-026 — класс: invalid — контр-evidence: `verification-traceability.md`, строка REQ-003/AC-004, прямо фиксирует `REALTIME_SERVE_ENABLED` в локальном `dynamic_config.json`; `server.py:1761–1788` реализует этот согласованный переключатель. REQ-006/007 отдельно требуют watchdog для сохранённого пути. Специальный конверт этой задачи предусматривает локальный механизм; требование заменить его GigaRC либо дополнительно отключать весь legacy-watchdog не установлено этим конвертом. Нельзя одновременно требовать сохранить согласованное решение и считать его наличие самостоятельным дефектом.

DISPUTE F-027 — класс: duplicate_of:F-013 — контр-evidence: `tests/test_realtime_reasoning.py:424`, `:437`, `:567`, `:1401` — те же реальные часы, жёсткие пороги и отсутствие measured/heavy-разделения уже перечислены в F-013. Приоритет исходного замечания сохраняю blocking: `testing.md §7.2` прямо требует детерминированных компонентных оракулов и отдельного измерительного контура.

DISPUTE F-028 — класс: invalid — контр-evidence: `receipts/code-gate.json`, `VER-004-packet-command` — диапазонное форматирование изменённых ханков является частью утверждённого гейта; замороженные функции побайтово сохранены. Несколько косметических изменений внутри трёх разрешённых файлов не доказывают выхода за task envelope или неоправданного переписывания функций. Оснований для FAIL по scope-diff нет.

DISPUTE F-029 — класс: duplicate_of:F-017 — контр-evidence: `tests/test_realtime_reasoning.py:325`, `:1150`, `:1154` — несоответствие пояснений подавляемым выражениям уже зафиксировано F-017. Сохраняю non-blocking и требование исправить конкретные пояснения.

AMEND F-030 — priority=non-blocking; locations=`server.py:1738`; fix=в `test_serve_env_sanitized_all_branches` гарантированно удалять созданный `_serve_env` каталог через cleanup/finally — причина: тест получает `XDG_STATE_HOME`, но не передаёт его владельцу `_ServeLease` и не удаляет самостоятельно. Вторую претензию про `called → completed` исключить из этого блока: это другой root cause; наблюдаемое нарушение клиентского результата не показано, а `_native_call_as_dsh` не использует это поле статуса для формирования вызова.

AMEND F-001 — priority=blocking; locations=`server.py:2406`, `:2407`, `:3062`, `:3112`, `:5198`, `:5206`, `:5229`, `:5294`, `:6407`, `:6431`, `:6486`; fix=фиксировать prompt headers непосредственно после `getresponse()`, сохранять общий latch и проверять его во всех fallback-ветках; добавить сценарии исключения и отказа лимитера после доставки — ARG: Реалист/R1 «разделитель стоит только на `server.py:5206-5210`, то есть после проверки лимитера и вне `except ServeUnavailable`». Собственная проверка `server.py:5206–5229`: при исключении внутри следующей попытки разделитель **уже отправлен**; прежнее утверждение о его обязательном отсутствии уточняю. При отказе лимитера разделитель действительно пропускается. Основной дефект запрещённого fallback после доставки остаётся. Синтетический initial status не должен сам запрещать предусмотренный pre-delivery fallback.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL  
   WHY=RW-009 остаётся незакрытым на исключениях и отказе лимитера. Также сохраняются подтверждённые расхождения native mapping, восстановления JSON и обработки разрезанных interruption-маркеров. F-019 дополнительным блокером не является.  
   СОВЕТЫ (при FAIL): исправить F-001, F-002, F-005, F-007, F-009, F-011; проверить одинаковые результаты run/serve и SSE/JSON на соответствующих сценариях.

2. ПОЛНОТА: VERDICT=FAIL  
   WHY=Зелёный suite не подтверждает численные пределы AC-001/002 и независимый temporal-oracle AC-026. Повреждённый UTF-8 конфигурации остаётся необработанной веткой. Недостающие assertions F-024 — отдельный non-blocking follow-up.  
   СОВЕТЫ (при FAIL): закрыть F-010 и F-012; добавить независимые upstream timestamps и проверки чувствительности к буферизации, уточнить матрицу доказательств.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL  
   WHY=Архитектура короткоживущего serve осуществима, однако F-003/F-004 оставляют подготовку и часть I/O вне общего deadline/cancellation; F-008 сохраняет ошибочное отождествление смерти legacy-лидера со смертью группы.  
   СОВЕТЫ (при FAIL): распространить единый бюджет и отмену на всю цепочку, включить создание state-dir в обработку отказов запуска, завершать принадлежащую запросу группу независимо от лидера.

4. РИСКИ: VERDICT=FAIL  
   WHY=Независимый Full Suite L2 принимаю: 431 тест компонента, 894 корневых теста, обратный порядок и статические проверки зелёные. Это не устраняет конкретные дефекты аккумуляции usage, redaction и измерительных оракулов. Фактический crash не утверждаю; отдельный аудит дочерних crash-исходов остаётся INCONCLUSIVE.  
   СОВЕТЫ (при FAIL): закрыть F-006, F-013, F-014; проверить usage на всех retry-причинах, sentinel-секреты в конечных ответах и логах, выделить реальные измерения в отдельный последовательный гейт.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS  
   WHY=Serve на попытку обоснован реалтайм-дельтами, ротацией прокси и изоляцией БД. Оснований требовать общий демон, прямой HTTP или удаление ownership-проверки нет. Исправления возможны внутри выбранной архитектуры.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL  
   WHY=Периметр трёх файлов, stdlib и frozen-срезы соблюдены. Блокируют конкретные нарушения единой семантики native-инструментов и классификации fallback, F-007/F-001. Претензии к локальному флагу, косметическому форматированию и неподтверждённой стоимости `lsof` не принимаю как самостоятельные блокеры.  
   СОВЕТЫ (при FAIL): переиспользовать существующий native-конвертер, согласовать обработчики с установленным барьером доставки; сохранить разрешённый периметр и законную отсрочку VER-006/007 до ACCEPT.

POSITIONS: 13/13
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `claude-sonnet-5-5-high`)

PANEL-NONCE: 510e49830a314d32
ARTIFACT-SHA256: 674edaca247fa44fb9639f81a52dbfe62235889400a00a99eec3f6c321db2b82

AGREE F-001 rev=1 — проверил: server.py:2406-2407 (`getresponse()`, затем `resp.read()`, `headers_at` ставится после чтения тела) и `except ServeUnavailable` → `return False` на server.py:5229-5234, 6431-6434. Тот же корень, что у моей F-018.
AGREE F-002 rev=1 — проверил: server.py:5808-5812, `status_timer.cancel()` стоит до `spawn_limiter.acquire` (лимит 1/с, ожидание до `SPAWN_WAIT_MAX_S=5.0`). На legacy-пути (путь по умолчанию) первый `[мост]` выходит позже 1.0 с, это нарушает REQ-004 (MUST). Правка в одну строку: отменять таймер после spawn. В R1 я относил это к follow-up, но довод "дёшево исправить, а REQ-004 MUST" перевешивает.
AMEND F-003 — priority=non-blocking; locations=server.py:2395, 2910, 2935, 2956, 2984, 3059; fix=пробросить абсолютный deadline и проверку `is_client_gone` в фазы SPAWN/READY/CREATE/SUBSCRIBE — причина: каждая фаза ограничена таймаутом 3-5 с. `lease.cleanup()` убивает группу, а это размыкает prompt-сокет и поток prompt, утечки нет. Худший случай (зависший serve при ушедшем клиенте) занимает 6-15 с. AC-011/012 измеряют обычный цикл, где проверка клиента идёт каждые 20 мс.
AGREE F-004 rev=1 — проверил: server.py:1738 (`tempfile.mkdtemp` в `_serve_env`) вызывается до `_spawn_serve`, значит до защищённого блока. RW-004 acceptance прямо называет `OSError` в `mkdtemp`. ENOSPC/EACCES уходит наружу как `OSError`; в SSE это перехватывает `except (BrokenPipeError, ConnectionResetError, OSError)` и пишет "client gone", fallback пропускается. Исправление: обернуть `_serve_env` в `except OSError → ServeUnavailable`.
AMEND F-005 — priority=non-blocking; locations=server.py:6477-6528; fix=на ветке transient_error дописывать `texts` и `reasonings` неуспешной попытки в `contents` перед построением recovery-промпта — причина: в JSON-режиме клиенту ничего не отправлялось, и при штатном повторе полным ответом потерь нет. Теряется только префикс на редкой ветке recovery после ошибки посреди ответа. DSH ходит с `stream:true` (F-35), REQ/AC на это нет.
AMEND F-006 — priority=non-blocking; locations=server.py:5298-5351; fix=начислять `result["usage"]` до ветвления, как в JSON — причина: REQ-014 имеет приоритет SHOULD, а AC-019 проверяет usage одной попытки. На ветке prompt_status `step.ended` обычно не приходит. Расхождение только на transient_error после `step.ended`.
AGREE F-007 rev=1 — проверил: `_native_call_as_dsh` (server.py:2832) возвращает `[{"name":…,"arguments": args}]` без преобразования, а legacy-цикл в `Run._execute_once` и в `_stream_sse` вызывает `_native_to_tool_calls(tool, input, tools)` (server.py:686-725). REQ-012/AC-017 требуют паритет с legacy. Внутренности `_fit_args` в пакете не вложены, разницу в аргументах для read/edit/list/multiedit не могу проверить. Но обход общего адаптера виден по самому diff, а правка дешёвая: переиспользовать `_native_to_tool_calls`.
AMEND F-008 — priority=non-blocking; locations=server.py:1115-1119; fix=перед выходом по `poll() is not None` проверять живость группы через `killpg(pgid, 0)` — причина: `_stop_proc` не входит в дельту, в candidate.diff нет ханка в этом участке. Сценарий требует, чтобы лидер `opencode run` вышел раньше потомка `serve --stdio`, evidence такого нет. Watchdog срабатывает при живом лидере.
AMEND F-009 — priority=non-blocking; locations=server.py:4732, 4824; fix=передать idle-callback и `is_client_gone` в `Run._execute_once` — причина: JSON/run-путь в дельте не менялся, а потолок 1800 с существует давно. REQ-006/007 не оговаривают stream/JSON; в architecture-packet это не могу проверить. Все AC (AC-005/008/009/010) идут через SSE, DSH использует `stream:true` (F-35). Serve-JSON watchdog уже покрыт общим `_serve_one_attempt`.
AGREE F-010 rev=1 — проверил: server.py:1700, `read_text("utf-8")` может бросить `UnicodeDecodeError`, а `except OSError` его не ловит. В режиме `auto` `_read_dynamic_config_enabled` вызывается на каждый запрос, поэтому битый файл ломает все запросы, а не только выключает serve. Kill-switch должен деградировать до `run`. Исправление: `except (OSError, ValueError)`.
AMEND F-011 — priority=non-blocking; locations=server.py:823, 5127, 5145; fix=инкрементальная очистка с удержанием хвоста либо вынос в адаптер — причина: в serve `result["texts"]` пополняется сырой дельтой до `on_text`, поэтому `_incomplete_step_signal` и recovery срабатывают по целому тексту (server.py:3252). Утечка косметическая: маркер виден в выводе. Удержание хвоста — новый риск для последнего ответа.
AMEND F-012 — priority=non-blocking; locations=tests/test_realtime_reasoning.py:567-583; fix=заменить `<1.0` на `<0.5` (FakeServe шлёт каждые 0.12 с), оставить проверку разброса ≥0.15 с и порядок "reasoning раньше content" — причина: эти проверки красные при полной буферизации, то есть тест чувствителен к RED, а смещение пороков от AC-001 правится одной строкой. AC-002 без независимой отметки апстрима остаётся пробелом для живого прогона VER-006. Перенос матрицы AC-016 на serve выношу в follow-up.
AMEND F-013 — priority=non-blocking; locations=tests/test_realtime_reasoning.py:424, 567, 1401; fix=маркеры measured/heavy вынести отдельной задачей — причина: в репозитории таких маркеров нет, а `pyproject.toml` вне конверта (`allowed_envelope_changes.configs: []`). FakeClock неприменим к тестам с настоящими процессами. Стабильность подтверждена шестью зелёными прогонами L2 (VER-001/002/003/003b/005 и AC-023 reversed).
CONFLICT F-012↔F-013 — F-012 ужесточает числовые пороги AC-001/002, F-013 выносит реальные тайминги из обычного suite. Маркеров в репозитории нет, а `pyproject.toml` вне конверта, поэтому одновременно оба фикса не выполнить. Компромисс: порог `<0.5` в обычном тесте (запас более 4× к 0.12 с), маркеры отдельной задачей.
AMEND F-014 — priority=non-blocking; locations=server.py:5347, 6523; fix=пропускать `err.get('message')` через `_clean_err` до `_error_payload` — причина: сообщение уходит только клиенту на 127.0.0.1 и в `_log` не пишется. AC-020 проверяет `bridge.log`, пароль serve в событиях ошибок не встречается. Реального утечного сообщения в evidence нет; исправление тривиально, берём в ту же правку.
DISPUTE F-015 — класс: out_of_scope — контр-evidence: tests/test_cli_failure.py:267 не входит в три файла конверта (candidate-manifest.json); ResourceWarning возникает в прямом вызове `Run(...)._execute_once()` из неизменённого legacy-теста и на origin/dev присутствовал до дельты. Для кандидата это не дефект.
AGREE F-016 rev=1 — проверил: в ветке `step_finish` (server.py:3284-3307) вызовы собираются через `tool_state.complete`, но `first_token_at` и `ttft_ms` ставятся только в ветке `session.tool.called/failed/success`. Телеметрия, non-blocking.
AGREE F-017 rev=1 — проверил: `test_fake_rt_mode_preset_preserved` содержит `_ = patcher.start()  # pyright: ignore[reportAny] — причина: ответ моста — динамический JSON…`, это причина не по делу. Non-blocking.
DISPUTE F-020 — класс: duplicate_of:F-001 — контр-evidence: тот же `except ServeUnavailable → return False` (server.py:5229-5234, 6431-6434), тот же корень и то же исправление (проверять latch до fallback). Уточнение про повторную отдачу reasoning/text после fallback на run входит в сценарий F-001.
AMEND F-019 — priority=non-blocking; locations=server.py:send_keepalive (проверка `first_token_timeout`, `FIRST_TOKEN_TIMEOUT_S`); fix=для legacy-пути дефолт порога выше наблюдаемого максимума (например 180 с) либо считать токеном активность `step_start` — причина: REQ-007 допускает 60 с, а порог настраивается через env. В legacy reasoning и text приходят в конце шага (F-17/F-18), поэтому порог равен максимальной длительности шага. Риск реален (максимум запроса 85.65 с, F-32), но числа порогов остаются открытым OPEN-11; решать владельцу и проверять на H-лестнице VER-006.
AGREE F-021 rev=1 — проверил: разделитель `[мост] Повтор попытки` выдаётся через `on_status`/`emit_synthetic` без проверки `thinking_enabled`, статусы ожидания эту проверку имеют (server.py:5206-5210, `_stream_sse` ветка `emit_synthetic`). Косметика при `effort=off`, non-blocking.
AGREE F-022 rev=1 — проверил: ветка `form.created` задаёт `terminal="cancelled"` и `break`, затем идёт успешный путь `record_success()` и SSE `finish_reason=stop` с пустым телом. JSON даёт 502 на "serve produced no text". Нужна единая политика. Non-blocking: событие редкое, так как permission policy режет инструменты.
AGREE F-023 rev=1 — проверил: `FALLBACK_DECISION_TABLE` в коде только данные, обработчики захардкожены. Строка "429/5xx → serve_retry" расходится с ветками `prompt_status`, где без вывода идёт `return False` (fallback на run). Алиасы `_find_listener_pid`, `parse_serve_event`, `_dynamic_config_enabled`, `_ToolInputAccumulator` не исполняются. Non-blocking: привести таблицу к фактическому поведению.
AGREE F-024 rev=1 — проверил: в FakeServe эндпоинты `permission/{id}/reply` и `form/{id}/cancel` реализует автор клиента, в F-22 они не подтверждены wire-захватом. `test_transport_matrix` не создаёт disable-файл (reverse-spec §4.4). Реальные ответы v2.1.2 нужно записать в VER-006 после ACCEPT. Non-blocking.
AGREE F-025 rev=1 — проверил: `_spawn_serve` поллит `lsof` с шагом 50 мс до 3 с, `_parent_lstart` и `_group_members` запускают `ps`. Выигрыш ownership-проверки (RW из цикла 1) важнее. Добавляет сотни мс к `first_event_ms` до первой дельты, укладывается в цель 3.0 с, а точное значение даст живой прогон. Non-blocking.
AMEND F-026 — priority=non-blocking; locations=server.py:send_keepalive, `_StdoutFeed.lines(on_idle)`; fix=один env-переключатель для legacy-watchdog и статусов — причина: REQ-003 требует kill-switch для нового транспорта (есть: `dynamic_config.json`, disable-файл, `TRANSPORT=run`). Упрочнение legacy (вариант L в handoff) включено по умолчанию, отключается только через пороги env. Применимость директивы GigaRC к автономному stdlib-мосту без `gc_pytools` не могу проверить.
DISPUTE F-027 — класс: duplicate_of:F-013 — контр-evidence: те же wall-clock тесты (`test_lease_cleanup…`, `test_ac026…`, `test_initial_status_before_1s…`) и то же решение; позиции по ним см. F-012, F-013.
AGREE F-028 rev=1 — проверил: в candidate.diff есть чисто форматные ханки вне функциональной дельты (`Run.execute`, `_UpstreamBreaker`, `_RequestAttempts.__init__`, `_PrefixDedup.push`, `CATALOG_*`, `r'''→r"""` в test_step_interruption). FU-008 просит минимальный diff. Откатить форматные ханки совместимо с VER-004: он проверяет только изменённые диапазоны. Поведение они не меняют, non-blocking.
DISPUTE F-029 — класс: duplicate_of:F-017 — контр-evidence: та же проблема неточных причин в комментариях `pyright: ignore` (FU-009), те же места (`_write_exe`, `_Bridge.post_*`, `test_fake_rt_mode_preset_preserved`).
AGREE F-030 rev=1 — проверил: `_ServeToolState.complete` присваивает `completed`, если в типе события есть "called", а `session.tool.called` означает готовый вызов, не выполнение. Поле status ни одним потребителем не читается (`_native_call_as_dsh` берёт только `part.tool` и `input`). Тест `test_serve_env_sanitized_all_branches` вызывает `_serve_env`, он создаёт `zen-serve-state-*` в tmp, и каталог не удаляется. Оба пункта non-blocking.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Цикл 3 закрывает RW-001..RW-008 и RW-010..RW-019, в L2 431 тест зелёный. Остались четыре дефекта. F-001 (с F-018, F-020): барьер доставки обходится ветками `ServeUnavailable` и отказа limiter. F-004: `mkdtemp` вне защищённого блока, а RW-004 acceptance его называет. F-007: serve-путь не использует общий `_native_to_tool_calls` (REQ-012/AC-017). F-010: битый UTF-8 в dynamic config ломает каждый запрос в режиме `auto`.
   СОВЕТЫ: (1) F-001: во всех `return False` по `ServeUnavailable` и отказу limiter (SSE и JSON) проверять latch доставки, при установленном latch делать serve-retry или терминальную ошибку, эмитить ровно один разделитель, `record_success` не вызывать. (2) F-004: обернуть `_serve_env` в `except OSError → ServeUnavailable`. (3) F-007: вызывать `_native_to_tool_calls(tool, input, tools)` вместо `_native_call_as_dsh` либо делегировать ему аргументы. (4) F-010: `except (OSError, ValueError)` в `_read_dynamic_config_enabled`.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=AC-014 (ровно один разделитель, без тихого fallback после отданного reasoning) не выполняется на исключении и на limiter (F-001). AC-005 (первый `[мост]` ≤1.0 с) не выполняется на legacy-пути при ожидании `spawn_limiter` (F-002). Остальные AC доказаны L2; пробелы AC-002 и AC-016 на serve записываю в follow-up (F-012).
   СОВЕТЫ: (1) Закрыть F-001 на всех четырёх `return False`. (2) F-002: отменять `status_timer` после spawn, а не до `spawn_limiter.acquire`; один `STATUS_INITIAL` сохраняется через `status_fired_at`. (3) Тест на F-002: занятый limiter при свободном startup gate, первый статус ≤1.0 с. (4) Тест на F-001: `ServeUnavailable` и timeout limiter на второй попытке после reasoning на первой.

3. РЕАЛИЗУЕМОСТЬ: PASS
   WHY=Решение собирается stdlib и тремя файлами. Serve по умолчанию выключен, kill-switch есть (`TRANSPORT=run`, disable-файл, `dynamic_config.json`). Группа убивается в `finally`, reaper на старте сверяет uid и симлинки. L2 зелёный (VER-001 431 passed, AC-023 reversed), VER-006/007 законно отложены. F-003, F-008, F-009, F-025 оставляю follow-up: каждая ограничена таймаутами или лежит вне дельты.

4. РИСКИ: VERDICT=FAIL
   WHY=Full suite L2 зелёный и порядок-независимый, `_run_env` и Google-срезы совпали по sha256. Регрессионные оракулы не покрывают F-001: тест подменяет возвраты `_serve_one_attempt`, но не бросает `ServeUnavailable` и не упирается в limiter. Остаются F-002, F-004, F-010 как дефекты на пути по умолчанию.
   СОВЕТЫ: (1) Добавить красные-до-фикса тесты на F-001, F-002, F-004 (fault injection на `mkdtemp`), F-010 (невалидный UTF-8 при работающем Server). (2) Оставить 431 тест и замороженные sha256 зелёными. (3) F-005, F-006, F-014, F-019 взять в ту же правку, если не раздувают дельту.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=A1 (короткоживущий serve на запрос) с откатом на run и прецедентом muse-bridge обоснован фактами F-19..F-27 и F-40. A2 ломает ротацию IP, прямой Zen без заголовков даёт 429 (F-24/F-25). Переписывания ради стиля нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Дельта ровно в трёх файлах конверта, `dependencies = []`, `_run_env` и Google-функции побайтово неизменны. Синтетические `[мост]` заданы REQ-004/005. Seed r29 пересчитан в R1 для r25: `seed_input` дословен, SHA-256 совпал с `manifest.json`; `ranked_order` по таблице слотов не могу проверить, она в пакет не вложена. Non-blocking: F-017, F-023, F-026, F-028.

POSITIONS: 29/29
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `grok-4.7-high`)

PANEL-NONCE: fd5495d33df1f1d6
ARTIFACT-SHA256: 674edaca247fa44fb9639f81a52dbfe62235889400a00a99eec3f6c321db2b82
Канон прочитан: AGENTS.md, 430 строк

AGREE F-001 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:5229-5234` — `except ServeUnavailable` делает `return False` и не читает `delivered_any`. То же на лимитере `:5198-5201` и в JSON `:6407-6409`, `:6431-6434`. `headers_at` пишется после `resp.read()` (`:2406-2407`, запись `:3062`). Возвратный путь таймаутов latch учитывает (`:5257-5279`).
AMEND F-002 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5808-5814; fix=держать защитный таймер до первого видимого чанка либо отдавать статус во время ожидания spawn_limiter, не дублируя STATUS_INITIAL — причина: RECHECK: `:5808` это `gate.acquire()`, `status_timer.cancel()` стоит на `:5811` до `spawn_limiter.acquire` (`:5812`). Дыра AC-005 реальна, если лимитер держит дольше 1 с (`SPAWN_WAIT_MAX_S=5`); приёмка RW-017 закрывает StartupGate, RPS низкий.
AMEND F-003 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2387,bridges/opencode-zen-bridge/server.py:3059,bridges/opencode-zen-bridge/server.py:3079; fix=follow-up: прокинуть остаток deadline в control/prompt — причина: окна 3 с и prompt 65 с уже есть; client-gone начинается в основном цикле (`:3079`). Сквозная обвязка каждого HTTP-вызова шире инцидента SSE. Немой потолок 1800 с на SSE закрывают watchdog.
AGREE F-004 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:1738` — `tempfile.mkdtemp` внутри `_serve_env` до защищённого try `_spawn_serve`. ENOSPC/EACCES выходит обычным `OSError`, а не `ServeUnavailable`. RW-004 прямо называл mkdtemp.
AMEND F-005 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6477,bridges/opencode-zen-bridge/server.py:6514,bridges/opencode-zen-bridge/server.py:6527; fix=до continue переносить texts/reasonings текущей попытки в накопители и строить recovery-prompt из них — причина: `allow_retry`+`continue` на `:6477` раньше `reasonings_all.extend` (`:6527`); промпт берёт `"".join(contents)` (`:6514`). DSH ходит `stream:true` (F-35); SSE чанки уже ушли. Это паритет JSON, не немой Think.
AMEND F-006 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5298,bridges/opencode-zen-bridge/server.py:5319,bridges/opencode-zen-bridge/server.py:5333,bridges/opencode-zen-bridge/server.py:5351; fix=начислять usage ровно один раз до любого continue — причина: ветки prompt_status и transient уходят в continue до аккумуляции (`:5351`); watchdog-ветка начисляет раньше. JSON начисляет до классификации (`:6451`). REQ-014 — SHOULD.
AGREE F-007 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:2832-2853` — `_native_call_as_dsh` после совпадения имени/алиаса возвращает сырые `args`. Эталон `_native_to_tool_calls` (`:686-726`) вызывает `_fit_args` (`:639`), сводит list/ls и разворачивает multiedit. REQ-012/AC-017. Тесты закрывают bash, не read/edit/list/multiedit.
AGREE F-008 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:1115` — `_stop_proc` сразу возвращается, если `proc.poll() is not None`, и дальше ждёт только лидера. Новый watchdog зовёт его на client_gone, first_event, first_token и stall (`:5903`, `:5909`, `:5917`, `:5922`). Лидер run уже вышел — внуки группы остаются. Serve-дерево чистит `_ServeLease.cleanup`; дыра на legacy run, это путь по умолчанию, пока serve выключен.
AMEND F-009 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:4732,bridges/opencode-zen-bridge/server.py:4824; fix=follow-up: idle-callback и client-gone в JSON/run, не трогая замороженный `_run_env` — причина: `feed.lines(deadline)` без idle. Инцидент и F-35 — SSE. Пороги 20/60 с на `stream:false` меняют поведение вне SSE AC.
AGREE F-010 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:1700-1704` — `read_text("utf-8")` ловит только `OSError`. Битый JSON даёт `False` (fail-open). Битый UTF-8 (`UnicodeDecodeError`) выходит из выбора транспорта. REQ-003.
AGREE F-011 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:823` — `_strip_interrupted` делает `sub` на аргументе целиком и вызывается на каждой дельте (`:5127`, `:5145`). Маркер, разрезанный между дельтами, уходит клиенту; целая строка снимается. REQ-011.
AMEND F-012 — priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:545,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:580; fix=follow-up: независимые метки конца апстрима, интервал соседних reasoning <500 мс и накладные ≤250 мс; RED на реализации с тем же API, которая буферизует — причина: setUp на origin/dev падает без `DYNAMIC_CONFIG_PATH` (`red_sensitivity_rc=1` валиден и не доказывает чувствительность к буферизации). Тест меряет <1.0 с; AC-001 требует <500 мс, AC-002 не измерен. Медиана дельт апстрима ~127 мс (F-19). Продуктового отказа этот оракул не показывает.
AMEND F-013 — priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:424,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:1401; fix=follow-up: автомат на FakeClock, wall-clock под marker measured — причина: пороги `monotonic`/sleep, включая окно cleanup 3.9–4.9 с, идут в обычном suite. L2 на целевой машине `rc=0`, флака не воспроизведена. Факт верен и вердикт на нём не держится.
AGREE F-014 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:5347` и `:6523` — `err.get('message')` попадает в `_error_payload` без `_clean_err`/`_mask_secrets`. Legacy stderr идёт через `_clean_err`. REQ-015 MUST.
DISPUTE F-015 — класс: out_of_scope — контр-evidence: `tests/test_cli_failure.py:267` вне трёх файлов `allowed_envelope_changes` — два `ResourceWarning` в VER-002 есть, L2 `rc=0`. Forbidden Scope запрещает править чужой тестовый модуль. В NEEDS WORK не идёт.
AGREE F-016 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3284-3288` — TTFT ставится на called/failed/success; сборка на `step_finish` (`:3304-3309`) зовёт `on_tool` и не ставит `first_token_at`/`ttft_ms`. FU-004/REQ-016. Ключи O-EXIT есть; tool-only `step.ended` может оставить ttft пустым.
AGREE F-017 rev=1 — проверил: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:324` и `:1150`/`:1154` — одна причина «динамический JSON ответа моста» стоит на `write_text` и `patcher.start()`. FU-009 частично. `basedpyright` errorCount=0 на новом файле.
AGREE F-018 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:5198-5201`, `:5229-5234`, `:6407-6409`, `:6431-6434` — те же `return False` мимо latch, что и F-001. Разделитель только `:5206-5210`, после проверки лимитера и вне `except`. `test_retry_separator_once_and_delivery_barrier_is_monotonic` подменяет возвраты и не бросает `ServeUnavailable`, в лимитер не упирается. Синтетический `[мост]` latch не ставит: иначе fallback после INITIAL на 0.65 с недостижим. `delivered_any` ставится только модельным чанком.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001..RW-008 и RW-010..RW-019 на возвратном пути закрыты. RW-009 закрыт только там: после уже отданного reasoning ветки `ServeUnavailable` и `spawn_limiter` возвращают fallback на `run` без разделителя (F-001, F-018). На пути по умолчанию (`REALTIME_SERVE_ENABLED` выключен) `send_keepalive` (`server.py:5911-5917`) ставит `first_token_timeout` через 60 с после первого события, до первого токена. Legacy `opencode run` отдаёт reasoning одним блоком в конце шага (F-17/F-18); наблюдаемый максимум deepseek 85.65 с (F-32), так что здоровый длинный think убивается и тратит до `MAX_TOTAL_SPAWNS=3` (леджер F-019). Новый `_native_call_as_dsh` обходит `_fit_args`/multiedit (F-007). `_strip_interrupted` режет маркер только внутри одной дельты (F-011). `mkdtemp` вне транзакции старта (F-004). Битый UTF-8 dynamic config рвёт выбор транспорта (F-010).
   СОВЕТЫ (при FAIL):
   - Перед каждым `return False` в SSE и JSON (исключение и лимитер) читать монотонный latch. Если модельный чанк уже ушёл — serve-retry или терминальная ошибка, ровно один разделитель, без `record_success()`. Синтетический `[мост]` latch не ставит. Регрессия: попытка 1 отдаёт reasoning, попытка 2 бросает `ServeUnavailable` либо упирается в лимитер; `Run` не стартует.
   - На legacy-пути не применять `first_token_timeout` к ещё идущему размышлению: поднять порог выше наблюдаемого максимума либо считать живостью `step_start` и активность stdout. Тест: fake-CLI молчит 65 с после `step_start` и затем отдаёт ответ без ретрая.
   - Провести native serve через `_native_to_tool_calls`. Ловить `UnicodeDecodeError` в чтении dynamic config как `enabled=False`. Включить `mkdtemp` в защищённый старт и переводить `OSError` в `ServeUnavailable`. Снимать interruption-маркер с удержанием ограниченного префикса на границе дельт.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=AC-014 («ровно одна статусная строка между попытками», без тихого fallback после отданного размышления) не выполнен и не покрыт на исключении и на лимитере: разделитель стоит только на `server.py:5206-5210` (F-001, F-018). Оракул интервалов (F-012) и wall-clock (F-013) — follow-up, сами по себе полноту не валят.
   СОВЕТЫ (при FAIL):
   - Добавить два оракула к F-001/F-018: reasoning на попытке 1, затем `ServeUnavailable` либо timeout лимитера на попытке 2. Ожидание: нет spawn `run`, ровно один разделитель или `_sse_error`/502, `record_success` не вызван. Те же ветки в JSON.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Короткоживущий `opencode serve` на запрос собирается stdlib-процессами в трёх файлах конверта, без новых runtime-зависимостей. Kill-switch рабочий: `_select_transport` (`server.py:1761-1788`), дефолт `auto`, нет файла `dynamic_config.json` — serve выключен, есть disable-файл и `TRANSPORT=run`. Clean-room L2 зелёный: VER-001 431 passed, unittest OK, обратный порядок OK, замороженные `_run_env` / Google-функции побайтово те же. VER-006/VER-007 законно `DEFERRED_L3` до ACCEPT. Рост `server.py` и встроенный супервизор — долг сопровождения, не блокер и не повод переписывать транспорт.

4. РИСКИ: VERDICT=FAIL
   WHY=Full Suite L2 зелёный (VER-001 `rc=0`, AC-023 reversed `rc=0`, RED на origin/dev `rc=1`) и красным его не считаю. После частичной доставки тот же SSE молча продолжается через `opencode run`, а `dedup` на этом пути не включён (F-001, F-018); тест барьера этот путь не ловит. Сырое `message` провайдера уходит клиенту (F-014). Порог 60 с на дефолтном run убивает легитимный длинный ответ (F-019, `server.py:5911-5917`). Смерть лидера run оставляет группу (F-008, `server.py:1115`).
   СОВЕТЫ (при FAIL):
   - Закрыть latch-тесты из совета по КОРРЕКТНОСТИ.
   - Прогонять новые provider/serve ошибки через `_clean_err`/`_mask_secrets` до SSE, JSON и лога.
   - В `_stop_proc` проверять живость группы независимо от `proc.poll()` и эскалировать SIGKILL, если члены группы живы.
   - Починить legacy `first_token_timeout`, как в совете по КОРРЕКТНОСТИ.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=A1 (serve на запрос) с откатом на `run` — тот транспорт, который даёт дельты reasoning каждые ~110–130 мс (F-19) и сохраняет ротацию IP. Общий демон A2 ротацию ломает. Прямой Zen без заголовков дал 429 (F-24, F-25). Прецедент — muse-bridge, serve основной, exec запасной (F-40). Объём helper/lease оправдан REQ-008. Найденные дефекты чинятся локально. Выноса транспорта в отдельный модуль как условия merge не требую.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Дельта ровно в трёх файлах конверта, `dependencies = []`, публичные маршруты и форма SSE не переименованы, `_run_env` sha256 `1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`, `google_direct_unchanged=true`. Стиль (wall-clock, причины pyright, декларативная таблица, косметический reformat) остаётся non-blocking и контекст не валит. Директива GigaRC к этому автономному stdlib-мосту не применяется: удалённого контура конфигурации в задаче нет. Независимый пересчёт сида: `seed_input` дословен, `seed_hex=fda258e9f4461e4dcde8c3f063c7e77bf692abe616b69916f7c712e79f06a461` MATCH манифесту r29, `SEED=fda258e9`. `ranked_order` по `rank_slots` (`SHA-256(seed_hex#slot_id)`) MATCH: grok-4.7-high, gpt-6.1-sol-high, claude-sonnet-5-5-high, muse-wonder-full-1.0, gemini-4-argon-high.

POSITIONS: 18/18
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


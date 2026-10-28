PANEL-NONCE: 7fcad6fc649838f0
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

Канон `~/Мой диск/Context/AGENTS.md` прочитан целиком в сообщении до `<!-- КАНОН-КОНЕЦ -->`; проектный `AGENTS.md`, `feature.md` и профильные стандарты прочитаны в приложенных обёртках. Файлы рабочей папки не открывал, тесты не запускал. Ниже используются номера сводного леджера.

DISPUTE F-001 — класс: duplicate_of:F-030 — контр-evidence: `bridges/opencode-zen-bridge/server.py:98`, `:99`, `:239`, `:244` — подтверждаю дефект: ранний helper обращается к `errno`, импортируемому только после его завершающего dispatch. Этот root cause уже полностью зарегистрирован в F-030.

DISPUTE F-002 — класс: duplicate_of:F-014 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3254`, `:5150`, `:5237`, `:6247`, `:6307` — возвращённый `timeout` действительно проходит мимо обработки отказов к `record_success()`. F-014 содержит тот же дефект обоих consumers и дополнительно необработанный JSON `client_gone`.

DISPUTE F-003 — класс: duplicate_of:F-016 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3022`, `:3053`, `:3055`, `:3061` — HTTP-результат prompt проверяется после `events.get()`, а `queue.Empty` возвращает управление к watchdog. Это тот же дефект зависимости контрольного канала от SSE, описанный в F-016.

DISPUTE F-004 — класс: invalid — контр-evidence: `bridges/opencode-zen-bridge/server.py:6359`, `:6371`, `:6378` — перед веткой unmapped-retry стоит `if not emulate_tools or tool_calls_all: break`. Поэтому сценарий «уже добавленные tool calls сохраняются через этот retry» показанным кодом исключён. Неиспользуемый `_seen_tc` сам по себе его не доказывает. Отдельный дефект дублирования одинакового вызова из text/native в одной попытке остаётся в F-021.

DISPUTE F-005 — класс: duplicate_of:F-023 — контр-evidence: `bridges/opencode-zen-bridge/server.py:6203`, `:6231`, `:6239`, `:6243` — JSON освобождает startup gate на отдельных исключениях, но не после обычного возврата попытки. F-023 уже охватывает этот путь и удержание gate на протяжении всей SSE-генерации.

DISPUTE F-006 — класс: duplicate_of:F-022 — контр-evidence: `bridges/opencode-zen-bridge/server.py:1718`, `:2493`, `:2502`, `:2505`, `:2531`, `:2599` — state-dir, резерв порта и pipe создаются до exception-safe владельца; при отказе `Popen` закрывается только read-end. Все перечисленные утечки охвачены F-022.

AMEND F-007 — priority=blocking; locations=bridges/opencode-zen-bridge/server.py:197,bridges/opencode-zen-bridge/server.py:231,bridges/opencode-zen-bridge/server.py:232; fix=проверять и завершать остальных членов собственной группы независимо от состояния непосредственного serve-процесса; удалять lease только после подтверждения отсутствия этих потомков — причина: проверка `not _pid_alive(-os.getpgrp())` внутри живого helper никогда не станет истинной, поскольку сам helper принадлежит группе. Дефект подтверждён, но предложенный предикат исправления необходимо заменить. Сценарий оставшегося TERM-resistant внука уже отражён также в F-024.

DISPUTE F-008 — класс: duplicate_of:F-026 — контр-evidence: `bridges/opencode-zen-bridge/server.py:4938`, `:4954`, `:4955`, `:6224` — передача checker в JSON добавлена, но RST по-прежнему попадает в общий `OSError → False`. F-026 содержит этот дефект и необходимость классификации ошибки `os.dup`.

DISPUTE F-009 — класс: duplicate_of:F-032 — контр-evidence: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:112`, `:115`, `:502`, `:591`, `:640`, `:830`, `:871`, `:881` — подтверждаю перечисленные пробелы: необращённые watchdog-режимы, проверка таблицы вместо переходов, `callable` вместо ротации, отсутствие JSON/disconnect/log-оракулов. F-032 включает их и независимый сигнал завершения апстрима.

AGREE F-010 rev=1 — проверил: `bridges/opencode-zen-bridge/tests/test_cli_failure.py:267` и сырой лог `execution-evidence.md`, `VER-002-unittest` — два `ResourceWarning` действительно присутствуют при итоговом `rc=0`. Это отдельный non-blocking follow-up вне разрешённых файлов; оснований объявлять весь выполненный L2 красным или аварийным нет.

DISPUTE F-011 — класс: duplicate_of:F-033 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5166`, `:6260`, `:6271`, `:6281` — JSON retry-ветки пропускают накопление usage, SSE делает это лишь частично. Это тот же согласованный non-blocking остаток FU-004 / REQ-014 SHOULD.

DISPUTE F-012 — класс: duplicate_of:F-029 — контр-evidence: `bridges/opencode-zen-bridge/server.py:75`, `:2644`, `:2645`, `:2660` — epoch-значение helper действительно исключено из сравнения с `ps lstart`; проверка подстроки argv идентичность попытки не заменяет. F-029 уже учитывает это как незакрытый обязательный RW-003 с blocking-приоритетом.

AMEND F-013 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3215,bridges/opencode-zen-bridge/server.py:3216; fix=согласовать определение первого токена для native tool completion и применять его одинаково к watchdog-часам и ttft_ms — причина: REQ-007 определяет первый токен как reasoning/text, тогда как реализация дополнительно устанавливает `first_token_at` на native completion без `ttft_ms`. Подтверждена внутренняя непоследовательность, но обязательность числового TTFT именно для tool-only ответа из AC-021 не следует.

DISPUTE F-037 — класс: duplicate_of:F-015 — контр-evidence: `bridges/opencode-zen-bridge/server.py:2941`, `:2955` — повторное чтение буферизованного response после socket timeout и проглатывание последующего `OSError` уже описаны в F-015. Уточнение: порог 0,5 с действует, только если `sse_conn.sock` доступен и `settimeout` выполнен; иначе остаётся исходный timeout 5 с. Формулировку «любая пауза дольше 0,5 с» без этого условия не подтверждаю.

DISPUTE F-038 — класс: duplicate_of:F-014 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3254`, `:5150`, `:6247`, `:6307` — общий timeout и JSON `client_gone` действительно не отделены от успешного результата. Это полностью совпадает с F-014.

DISPUTE F-039 — класс: duplicate_of:F-022 — контр-evidence: `bridges/opencode-zen-bridge/server.py:1718`, `:2505`, `:2526`, `:2531`, `:2835` — ранний spawn расположен вне общего cleanup; его `OSError` может выйти в обработку клиентского отключения вместо `ServeUnavailable`. Совпадает с корневой причиной F-022.

DISPUTE F-040 — класс: duplicate_of:F-023 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5092`, `:5136`, `:6203`, `:6243` — startup gate освобождается слишком поздно в SSE и не освобождается обычным JSON-путём. Это тот же lifecycle-дефект F-023. Критерий «старты менее чем через секунду» следует заменить проверкой освобождения gate: допустимый интервал дополнительно определяется spawn-limiter.

DISPUTE F-041 — класс: duplicate_of:F-017 — контр-evidence: `bridges/opencode-zen-bridge/server.py:2385`, `:2997`, `:3063`, `:5208` — фиксация headers после чтения тела и пересчёт delivered по контенту уже входят в F-017. Сопутствующая зависимость проверки HTTP-status от очереди отдельно зарегистрирована в F-016.

DISPUTE F-042 — класс: duplicate_of:F-027 — контр-evidence: `bridges/opencode-zen-bridge/server.py:3042`, `:5079`, `:5087` — неотменяемый timer, второй источник initial-status и отдельный писатель в `wfile` уже охвачены F-027. Подтверждён риск позднего/двойного статуса; повреждение байтов кадра требует отдельного воспроизведения и не является необходимым основанием этого блокера.

DISPUTE F-043 — класс: duplicate_of:F-032 — контр-evidence: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:491`, `:502`, `:508`, `:591`, `:640`, `:787`, `:871` — пробелы поведенческой матрицы совпадают с F-032. При этом утверждение об отсутствии сокетного serve-замера первого статуса некорректно: `test_slow_serve_gets_status_and_no_status_on_fast` такой замер содержит; он не проверяет последующую полноту модельного ответа.

AMEND F-044 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:1388,bridges/opencode-zen-bridge/server.py:2476; fix=проверять существующий lease-каталог через lstat: владелец, права и отсутствие symlink; при нарушении прекращать использование каталога до чтения lease и записи файлов — причина: фиксированный путь сам по себе не доказывает эксплуатацию, но `mkdir(exist_ok=True)` и игнорирование ошибки `chmod` не подтверждают доверенность уже существующего каталога. Перенос в конкретный пользовательский путь не обязателен для устранения этой проблемы.

DISPUTE F-045 — класс: invalid — контр-evidence: `FALLBACK_DECISION_TABLE`, строка «HTTP400/404/422 invalid request → fail_closed», и `bridges/opencode-zen-bridge/server.py:2882` — предлагаемое переключение любого pre-prompt 404 в fallback противоречит приложенной таблице. Проверка версии может быть отдельным развитием, но несовместимость будущей версии не является доказанным дефектом поддерживаемого v2.1.2.

AMEND F-046 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2167,bridges/opencode-zen-bridge/server.py:4585,bridges/opencode-zen-bridge/tests/test_step_interruption.py:69; fix=по возможности сократить только необязательные косметические hunks, сохранив диапазонное форматирование и frozen-срезы — причина: FU-006 уже согласован как non-blocking. Требование вернуть `CATALOG_SOURCE="init"` исключаю: `VER-004-packet-command` прямо требует `"static"` и `_set_catalog_source`, а проверка прошла. Нарушение публичного HTTP-контракта этим изменением не доказано.

AMEND F-047 — priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:290,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:294,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:306; fix=для подавлений Unknown/Any указывать конкретный источник неопределённого типа и основание безопасности либо заменять подавление типизированным адаптером; намеренный доступ тестов к private API объяснять отдельно — причина: одинаковая причина действительно не объясняет разные диагностические классы. Однако выполненные условия RW-026 — отсутствие блокового отключения, пояснения и зелёный согласованный VER-004 — не позволяют автоматически объявить весь статический гейт недействительным.

DISPUTE F-048 — класс: duplicate_of:F-030 — контр-evidence: `bridges/opencode-zen-bridge/server.py:98`, `:99`, `:239`, `:244` — тот же ранний доступ к неимпортированному `errno`; самостоятельного root cause сверх F-030 нет.

DISPUTE F-049 — класс: duplicate_of:F-033 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5166`, `:6260`, `:6281` — недоучёт usage неуспешных попыток уже зарегистрирован в F-033. Неиспользуемый `_seen_tc` не доказывает дублирование через retry из-за предшествующего `break`; отдельное same-attempt дублирование остаётся F-021.

DISPUTE F-050 — класс: duplicate_of:F-017 — контр-evidence: `bridges/opencode-zen-bridge/server.py:5207`, `:5208` — reasoning-only доставка исключена из `_delivered_err`, что уже охвачено F-017; отсутствие разделителя охвачено F-020. Дедуплицировать reasoning нельзя: AC-014 требует сохранять его полностью и разделять попытки одной статусной строкой.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL  
   WHY=Остаются ложный успех при timeout/JSON disconnect, неустойчивый delivery barrier, зависимость prompt-status от SSE и нарушения восстановления инструментальных шагов: F-014–F-021, F-030–F-031. Дубли в леджере не увеличивают число самостоятельных дефектов.  
   СОВЕТЫ (при FAIL): обработать терминальные отказы до success; исправить возобновляемое SSE-чтение; проверять HTTP-результат независимо от очереди; сделать delivery latch необратимым; защитить каждый spawn общим бюджетом; закрывать шаг после текстовых tool calls; обеспечить разделители и семантический dedup инструментов.

2. ПОЛНОТА: VERDICT=FAIL  
   WHY=RW-025/028 закрыты неполно: тесты не доказывают интервалы AC-001, overhead AC-002, независимое завершение апстрима AC-026 и матрицу отказов нового транспорта. Сохраняется проблема первой реакции legacy при startup-ожидании: F-028, F-032.  
   СОВЕТЫ (при FAIL): добавить независимые upstream timestamps/end-marker; проверки трёх watchdog, JSON/retries, FIN/RST, lifecycle, proxy rotation, secrets, переключателей и serve step-recovery; заменить обобщённые PASS traceability ссылками на конкретные утверждения.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL  
   WHY=Транспорт технически доступен на целевой машине, внешние runtime-зависимости не нужны. Внедрение блокируют утечки раннего запуска, удержание gate, неполное завершение потомков и исчерпание cleanup-бюджета до подтверждения SIGKILL: F-022–F-025. Архитектуру целиком менять не требуется.  
   СОВЕТЫ (при FAIL): замкнуть владение ресурсами с момента их создания; освобождать startup gate после startup и в `finally`; разделить бюджеты TERM/KILL/проверки; подтвердить отсутствие потомков после смерти родителя. Оценка: 2–4 инженерных дня на исправления и 0,5–1 день на повторную проверку; доступность Zen влияет на срок L3.

4. РИСКИ: VERDICT=FAIL  
   WHY=Независимый Full Suite L2 принимаю: 408 тестов компонента, 894 корневых теста и обратный порядок зелёные. Но остаются риски потери дельт, повторной доставки, продолжения работы после RST и сигнализации чужому переиспользованному helper PID: F-015, F-017, F-026–F-029, F-031–F-032. Общий RED не доказывает чувствительность временного оракула AC-026, падающего в setup.  
   СОВЕТЫ (при FAIL): закрыть перечисленные дефекты направленными regression-оракулами; проверять конечные сокеты, группы процессов и журнал; сохранить F-010 отдельным non-blocking follow-up. VER-006/007 законно отложены до ACCEPT и самостоятельным блокером не являются.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS  
   WHY=Короткоживущий serve с резервным run соответствует подтверждённым возможностям OpenCode и необходимости ротации IP. Legacy-only не обеспечивает RC-1, общий демон усложняет ротацию, прямой Zen не подтверждён. Исправления lifecycle и классификации можно выполнить внутри выбранного решения.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL  
   WHY=Три файла конверта, stdlib-only, frozen-функции и публичные оболочки соблюдены. Однако прямой запрет нового `unittest.TestCase` остаётся нарушенным в F-034; обязательные lifecycle/deadline-оракулы неполны в F-022–F-025/F-032. Косметические hunks и пояснения подавлений сохраняю non-blocking.  
   СОВЕТЫ (при FAIL): оформить новый тестовый модуль pytest-фикстурами с гарантированной изоляцией; закрыть применимые проверки владения, освобождения ресурсов и дедлайнов. Не расширять исправления на DSH, другие мосты и замороженные функции.

POSITIONS: 27/27
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK

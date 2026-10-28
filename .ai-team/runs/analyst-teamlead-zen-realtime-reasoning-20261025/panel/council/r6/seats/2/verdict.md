PANEL-NONCE: 58a5b1f4742ef973
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

Роль: Реалист, Цикл 2, режим `code`. Результаты тестов беру только из `execution-evidence.md` (L2 clean-room: 408 passed, rc=0 по VER-001/002/003/003b/005/AC-023). Номера строк `server.py` приблизительные (≈), восстановлены по hunk-ам `candidate.diff`.

Verify-fixed по `RW-001..RW-032`:

| Статус | Пункты |
|---|---|
| Закрыты | RW-001 (gate/limiter/proxy на спавне), RW-002 (дедлайн рукопожатия), RW-005 (`json.loads` + склейка суррогатов), RW-007 (пробельные дельты), RW-009 по замыслу (но см. F-01), RW-010 (`conn.timeout`, `interrupt`/`DELETE` ≤0.25 с), RW-012, RW-013, RW-014, RW-016, RW-017, RW-020, RW-021, RW-022, RW-026 формально, RW-027, RW-028, RW-029, RW-030, RW-031, RW-032 |
| Не закрыты или закрыты частично | RW-003, RW-004 (в JSON-пути проброс есть, остальное ок), RW-006, RW-008, RW-011, RW-015, RW-018, RW-019, RW-023, RW-024, RW-025 |

Блокирующие остатки описаны в F-01…F-12.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Заявленное исправление RW-008 не работает: `exit_reason="timeout"` ставится, но обработчики его не проверяют, и запрос завершается как успех. RW-015 реализован не по таблице. SSE-читатель устроен так, что на реальном HTTP/1.1-сервере после первой паузы >0.5 с он перестаёт читать (F-01). `_client_gone_check` не обнаруживает RST (RW-024 не закрыт).
   СОВЕТЫ (при FAIL):
   - F-01: убрать `settimeout(0.5)` на сокете, из которого читает `HTTPResponse.readline`. Читать из `sse_conn.sock` через `select`/`recv` с собственной буферизацией, либо пересоздавать чтение после таймаута.
   - F-02: обработать `exit_reason=="timeout"` и `"client_gone"` в stream- и JSON-обработчиках как отказ.
   - F-03: классифицировать `prompt_status` независимо от очереди SSE и не ставить `delivered=True` по non-200.
   - F-06: возвращать `True` в `_client_gone_check` при `ConnectionResetError`/`EBADF`.
   - F-07: импортировать `errno` в helper-ветке.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-025 (поведенческие оракулы на каждый REQ/AC) не выполнен. Нет тестов на serve-watchdog (`first_event`/`first_token`/`stall`), JSON-путь serve, `client_gone`, ротацию прокси, AC-020 (пароль не в логах), disable-файл, живой успех helper, поведение `FALLBACK_DECISION_TABLE`. Оракул AC-026 тавтологичен (F-09, F-10). Ветки `delivered`, `timeout`, `client_gone` в JSON обработаны неполно (F-02, F-03, F-18).
   СОВЕТЫ (при FAIL):
   - Добавить тесты по списку F-10.
   - Для AC-026 ввести независимую метку завершения апстрима (файл или событие от FakeServe) и сравнивать с ней.
   - Сделать FakeServe HTTP/1.1 keep-alive (`protocol_version="HTTP/1.1"`).

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Живой путь не доказан. На реальном `opencode serve` (HTTP/1.1) читатель упрётся в F-01 при первой паузе, а на тестовом HTTP/1.0 фейке этот дефект невидим. `_StartupGate` в JSON-пути не освобождается, в stream-пути держится всю попытку (F-04). VER-006/007 законно отложены, но тесты ничего не доказывают про реальный wire.
   СОВЕТЫ (при FAIL):
   - Исправить F-01 и F-04.
   - Добавить интеграционный тест с HTTP/1.1 chunked/keep-alive SSE и паузой >1 с.
   - После ACCEPT пройти лестницу H0..H9 именно с реальным `opencode` v2.1.2.

4. РИСКИ: VERDICT=FAIL
   WHY=Утечки при раннем отказе `_spawn_serve` (порт, `state_dir`, lifeline fd) и не-`ServeUnavailable` исключение (F-05). Helper удаляет lease по смерти только прямого потомка и может упасть на `NameError: errno` (F-07, F-08). Предсказуемый `/tmp`-каталог lease без проверки владельца (F-14). Таймер статуса пишет в сокет после завершения попытки (F-11). Red-чувствительность теста — это `AttributeError` на отсутствующих символах, а не поведенческий провал.
   СОВЕТЫ (при FAIL): F-04, F-05, F-07, F-08, F-09, F-11, F-14.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Гибрид serve→run с kill-switch и общим потолком спавнов соответствует прецеденту muse-bridge (F-40/41) и решению Архитектора. Более простого пути к реалтайму на здоровом вызове нет: `run --format json` дельты не отдаёт (F-17/18). Раздутость кода и косметический churn оформлены как non-blocking (F-13, F-16).
   СОВЕТЫ (при FAIL): —

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Изменены ровно 3 разрешённых файла. Замороженные `_run_env`, `_stream_google_sse`, `_execute_google_once` побайтово неизменны (`code-gate.json`). Публичный HTTP/OpenAI-контракт сохранён, а `[мост]`-статусы санкционированы REQ-004/005. Внешних зависимостей нет, чужих KEY нет. Замечания по KISS и стилю — non-blocking (F-13, F-15, F-16).
   СОВЕТЫ (при FAIL): —

SUB Корректность/логика: FAIL — F-01 `_serve_one_attempt` `_reader`/`settimeout(0.5)`; F-02 `exit_reason="timeout"` не обрабатывается; F-03 порядок классификации `prompt_status`
SUB Корректность/граничные условия: FAIL — F-01 пауза SSE >0.5 с; F-06 `_client_gone_check` не детектирует RST/EBADF (≈4936)
SUB Корректность/обработка ошибок: FAIL — F-05 `Popen` OSError вне `ServeUnavailable` (≈2510); F-02 `timeout` засчитан как успех
SUB Полнота/покрытие AC: FAIL — F-09, F-10: AC-009/010/011/012/018/020/026 без поведенческих оракулов (RW-025)
SUB Полнота/пропущенные ветки: FAIL — F-03 таблица (400/404/422 → fail_closed, 429 → serve_retry); F-18 `client_gone` в JSON не обработан (≈6190–6260)
SUB Реализуемость/общее: FAIL — F-04 `_StartupGate` (JSON ≈6205, stream ≈5100); F-01 нет проверки на HTTP/1.1
SUB Риски/безопасность: FAIL — F-14 `/tmp/opencode-zen-bridge-leases` без проверки владельца/симлинка, security.md §9
SUB Риски/данные: PASS — потерь данных нет; потеря usage при watchdog-ретраях JSON — только REQ-014 SHOULD (F-17, non-blocking)
SUB Риски/прод: FAIL — F-01/F-04/F-11; legacy `first_token` 60 с против буферизованного reasoning (F-13)
SUB Риски/regression red→green: FAIL — `l2-red.log`: 24 красных — это `AttributeError`; AC-026 тавтологичен (F-09)
SUB Риски/Full Suite (L2): PASS — `execution-evidence.md`: VER-001 408 passed rc=0, VER-002 OK, VER-003/003b rc=0, AC-023 rc=0
SUB Риски/scope-diff: PASS — 3 файла, замороженные срезы неизменны, контракт не менялся; косметический churn — non-blocking (F-12)
SUB Альтернативы/общее: PASS — гибрид оправдан (F-40/41); более простого пути к реалтайму нет
SUB Соответствие контексту/общее: PASS — граница слоёв и внешний контракт сохранены; KISS/стиль — non-blocking (F-15, F-16)

F-блоки:

F-01 [blocking] SSE-читатель умирает после первой паузы >0.5 с на реальном HTTP/1.1
- Место: `server.py` ≈2940 (`sse_conn.sock.settimeout(0.5)`), ≈2950–2985 (`_reader`); `tests/test_realtime_reasoning.py` FAKE_SERVE (`http.server`, HTTP/1.0).
- Правило: REQ-006/007, AC-009/010, RW-009, python-standards §5.
- Evidence: после `getresponse()` на `will_close`-ответе `conn.sock=None`, поэтому на HTTP/1.0 фейке ветка `settimeout(0.5)` не выполняется. На реальном `opencode serve` (HTTP/1.1, F-19: пауза execution.started→reasoning.delta ≈1.5 с) таймаут применяется. После первого `TimeoutError` файловый объект `SocketIO` помечается timed-out, и все следующие `readline()` бросают `OSError`. Эти исключения глотаются `except (TimeoutError, OSError): continue` без `sleep`. Итог: цикл крутится вхолостую, события больше не приходят, и попытка падает по `first_token_timeout`/`stall_timeout`.
- Подтверждение косвенное: прогон `__slow__` проходит только потому, что соединение остаётся с исходным таймаутом 5 с. Не могу проверить на реальном бинаре, вердикт PLAUSIBLE.
- Исправление: читать из сокета через `select`/`recv` с собственным разбором SSE-строк; либо не ставить короткий таймаут на сокете, под которым буферизованный `readline`, и завершать чтение по `stop_event` закрытием сокета.
- Проверка: тест с HTTP/1.1 keep-alive/chunked FakeServe, где между `execution.started` и первой дельтой пауза 1.5 с; стрим завершается успешно, CPU не крутится.

F-02 [blocking] `timeout` и `client_gone` обрабатываются как успех (RW-008 не закрыт)
- Место: `server.py` ≈3280 (`result["exit_reason"]="timeout"`), ≈5140 stream-цепочка, ≈6215 JSON-цепочка.
- Правило: REQ-006/009, R-BULK-I1, RW-008.
- Evidence: списки `("first_event_timeout","first_token_timeout","stall_timeout","invalid_serve_event")` не содержат `"timeout"`. Выполнение доходит до `res.serve_health.record_success()` / `attempt_done(False, True)` и до успешного `[DONE]` с частичным или пустым текстом. В JSON-пути `client_gone` не проверяется вообще, и запрос завершается как `upstream_failed`.
- Исправление: ввести обработку `timeout` (ошибка клиенту `exit_reason="timeout"`, без `record_success`) и `client_gone` (`xs["exit_reason"]="client_gone"`, return) в обоих путях.
- Проверка: FakeServe без terminal до сжатого deadline даёт SSE-error и `exit_reason=timeout`; `serve_health.failures` не обнуляется.

F-03 [blocking] Классификация HTTP-статуса prompt не соответствует `FALLBACK_DECISION_TABLE` (RW-015)
- Место: `server.py` ≈3056–3075 (`prompt_status` после `events.get`), ≈5180–5200, ≈6225.
- Правило: REQ-009, R-BULK-I3.
- Evidence (1): проверка стоит после успешного `events.get()`, а при `queue.Empty` цикл делает `continue`. Prompt-ответ 429/5xx без SSE-событий обнаруживается только через 20 с по `first_event_timeout`, причём `delivered=bool(headers_at)`, а `headers_at` ставится и для non-200. Итог: бессмысленный `serve_retry` вместо классификации.
- Evidence (2): 400/404/422 на prompt уходят в fallback на `run` (по таблице должен быть `fail_closed`), 429 до доставки — в fallback (по таблице `serve_retry` + breaker). Таблица в коде декларативна и ничего не исполняет.
- Исправление: проверять `prompt_status` в каждой итерации цикла до `events.get`; `delivered` вычислять по наличию валидного execution-события или 2xx-заголовков; привести ветки к таблице (или поправить таблицу).
- Проверка: FakeServe отвечает на prompt 429/422/503 без событий; результат за <1 с и ожидаемое действие по таблице.

F-04 [blocking] `_StartupGate` не освобождается/держится всю попытку
- Место: `server.py` ≈6205–6245 (`_gate_j`), ≈5100–5160 (`gate`).
- Правило: REQ-013, S-HERD-I1, T-LIFE.
- Evidence: в `_serve_json_serve` `release()` вызывается только в `except`/при отказе limiter, на нормальном пути его нет. В stream-пути `release()` выполняется после возврата `_serve_one_attempt`, то есть после всей генерации. Legacy освобождал замок на первую stdout-строку (F-10). При конкурентных запросах второй ждёт `STARTUP_WAIT_S=5` с, затем идёт fail-open. Реализацию `_StartupGate` в пакете не вижу.
- Исправление: освобождать gate сразу после проверки готовности serve (после рукопожатия/`/api/session/active`), либо передать `on_ready`-колбэк в `_serve_one_attempt`; в JSON добавить `try/finally`.
- Проверка: два одновременных serve-запроса (stream и JSON) стартуют без пятисекундной задержки; после завершения `_StartupGate` свободен.

F-05 [blocking] Утечки ресурсов и неверный тип исключения при раннем отказе `_spawn_serve` (RW-019 не закрыт)
- Место: `server.py` ≈2476–2540 (`Popen` до создания `lease`), ≈2476 «no free serve port», ≈2800 `_serve_env` (`mkdtemp`).
- Правило: T-LIFE/v1, REQ-008, error-handling.md.
- Evidence: `OSError` из `Popen` (ENOMEM/EMFILE/нет бинаря) вылетает до `_ServeLease`. Оставшиеся `lifeline_w`, порт в `_ACTIVE_SERVE_PORTS` и `zen-serve-state-*` не освобождаются. Исключение не `ServeUnavailable`, обработчик его не ловит, оно попадает в `except OSError` как «client gone mid-stream». При «no free serve port» `state_dir` из `_serve_env` тоже не удаляется.
- Исправление: обернуть `mkdtemp`/порт/`Popen` в один `try/except BaseException` с освобождением порта, закрытием pipe и `rmtree`; транслировать `OSError` в `ServeUnavailable`.
- Проверка: `mock.patch(subprocess.Popen, side_effect=OSError)`; после вызова нет `zen-serve-state-*`, порт не в `_ACTIVE_SERVE_PORTS`, fd не растут, в auto — fallback на `run`.

F-06 [blocking] `_client_gone_check` не обнаруживает RST/EBADF (RW-024 не закрыт)
- Место: `server.py` ≈4936–4955 (`_client_gone_check`).
- Правило: REQ-008, AC-011.
- Evidence: функция в Цикле 2 не менялась; `except (OSError, ValueError): return False`. `recv(MSG_PEEK)` при RST бросает `ConnectionResetError`, и клиент считается живым. В Цикле 2 правка внесена в `_fd_ready` helper-а, то есть не туда.
- Исправление: `ConnectionResetError`/`BrokenPipeError`/`EBADF` → `True`; `EAGAIN`/`EWOULDBLOCK` → `False`.
- Проверка: клиент делает `SO_LINGER(1,0)`+close; `client_gone` фиксируется ≤5 с, процессы группы отсутствуют ≤7 с.

F-07 [blocking] Helper: `errno` не импортирован (NameError)
- Место: `server.py` ≈70–100 (`_fd_ready`), импорты ≈243 (ветка `else` после `raise SystemExit`).
- Правило: T-LIFE/v1, python-standards §3.
- Evidence: `--serve-helper` завершается через `raise SystemExit` до `else`-ветки, где импортируются `errno`, `collections` и др. Правка Цикла 2 добавила `errno.EAGAIN` в `_fd_ready`. При любом `OSError` из `select` (например EBADF на закрытом fd 0) будет `NameError`. Первый вызов `_fd_ready()` стоит вне `try`, так что helper падает без уборки lease.
- Исправление: `import errno` на верх helper-блока до диспетчеризации; `BlockingIOError` уже перехвачен.
- Проверка: тест с закрытым stdin helper-а (`os.close(0)` либо `select` с мок-OSError); helper завершается с rc≠NameError и удаляет lease.

F-08 [blocking] Helper удаляет lease по смерти только прямого потомка (RW-023/RW-003 не закрыты)
- Место: `server.py` ≈180–235 (`finally` helper-а).
- Правило: REQ-008, T-LIFE/v1.
- Evidence: SIGKILL-эскалация выполняется лишь если `serve_proc.poll() is None`, а `lease_path.unlink()` — если `serve_proc.poll() is not None`. Внуки `opencode serve` в той же группе, игнорирующие SIGTERM, переживают helper, и lease при этом стёрт, так что reaper их уже не найдёт. Именно этот путь единственный при смерти моста.
- Исправление: после SIGTERM проверять смерть всей группы (`ps -g` или `killpg(...,0)` по оставшимся не-helper PID) в бюджете, эскалировать до SIGKILL всей группы и удалять lease только после этого.
- Проверка: фейк-serve, порождающий внука с `SIG_IGN` на SIGTERM; после закрытия lifeline группа пуста ≤7 с, lease удалён только потом.

F-09 [blocking] Оракул AC-026/REQ-020 тавтологичен; red — тривиальный
- Место: `tests/test_realtime_reasoning.py::test_ac026_realtime_chunks_before_upstream_end`; `l2-red.log`.
- Правило: REQ-020/AC-026, testing.md («тест должен воспроизводить баг»), RW-025.
- Evidence: `upstream_end_t = elapsed` — это конец клиентского потока. Для буферизующей реализации (все чанки в конце) `first_t` всё равно `< elapsed`, а `last-first<2.0` тоже выполняется, так что тест зелёный и на сломанном поведении. Red на `origin/dev` — это `AttributeError` из `setUp` на `server.DYNAMIC_CONFIG_PATH`, а не поведенческий провал.
- Исправление: FakeServe пишет метку времени последней дельты/завершения в файл; тест сравнивает приход первого `reasoning_content`-чанка с этой меткой (разрыв ≥ N×0.12 с до конца апстрима); дополнительно проверить интервал между соседними чанками <0.5 с.
- Проверка: тест краснеет на реализации, которая буферизует поток до terminal.

F-10 [blocking] Нет поведенческих оракулов на заявленные REQ/AC (RW-025)
- Место: `tests/test_realtime_reasoning.py` целиком.
- Правило: testing.md, AC-009/010/011/012/013/018/020/021, REQ-008/013/015.
- Evidence: отсутствуют тесты на `first_event`/`first_token`/`stall` в serve и на JSON-путь serve; нет `client_gone`/cleanup группы, ротации прокси (`test_spawn_cap...` проверяет только `callable`), AC-020 (пароль не в `bridge.log`), disable-файла, успешного helper с 6 аргументами и lease, `FALLBACK_DECISION_TABLE` как поведения. Часть тестов пустая по смыслу: `test_elf_magic_and_tool_status` не проверяет ELF, `test_native_tool_and_permission_reject` не проверяет reject.
- Исправление: добавить по одному детерминированному тесту на каждый перечисленный пункт (`__never_event__`, `__silent__`, `stall` уже есть в FakeServe, но не используются) и усилить пустые.
- Проверка: каждый оракул красный на `origin/dev` по поведению и зелёный на кандидате.

F-11 [blocking] Таймер первого статуса не отменяется, пишет вне основного потока, дублирует статус
- Место: `server.py` ≈5090–5110 (`_initial_status_timer`), `_serve_one_attempt` ≈3035 (`STATUS_INITIAL` второй раз).
- Правило: REQ-005, AC-005/014, T-LIFE/v1.
- Evidence: поток живёт, пока не пройдёт `wait(0.65)` либо `_model_seen`. Для tool-only/быстрого ответа (в evidence: duration 0.35 с, `tools=1`, `_model_seen` не ставится) он пишет `[мост]`-чанк после финального `[DONE]` или конкурентно с основным потоком. На повторных попытках `_t0_req` в прошлом, и «Подключение к модели…» эмитится сразу при каждом заходе. Начальный статус дублируется внутри `_serve_one_attempt`. Запись в `wfile` из двух потоков не сериализована.
- Исправление: один источник начального статуса (внутри попытки, один раз на запрос); таймер отменять `Event` в `finally`; запись в `wfile` под общим замком; не эмитить `STATUS_INITIAL` на ретраях.
- Проверка: tool-only ответ <0.65 с и `[мост]` после `[DONE]` отсутствует; ровно один `STATUS_INITIAL` на запрос.

F-12 [non-blocking] Косметический churn (FU-006 не выполнен)
- Место: `server.py` (`_RequestAttempts`, `Run._execute_once`, `_stream_sse`, `_UpstreamBreaker`, `CATALOG_*`), `tests/test_step_interruption.py:67` (`r'''`→`r"""`).
- Правило: AGENTS.md п.4 («минимально достаточные»).
- Evidence: многие hunk-и — переформатирование без смены поведения; ревью и blame усложнены.
- Исправление: откатить форматирование вне затронутых функций или вынести отдельным коммитом.
- Проверка: `git diff --stat` по legacy-функциям без поведенческих изменений уменьшается.

F-13 [non-blocking] Legacy `first_token_timeout=60 с` против буферизованного reasoning
- Место: `server.py` ≈1393–1397 (константы), ≈5440 (`send_keepalive`).
- Правило: REQ-007, OPEN-11, F-17/F-32.
- Evidence: legacy-`run` отдаёт reasoning одним блоком в конце шага, а наблюдаемый max запроса 85.65 с. Здоровый долгий шаг без токенов >60 с будет убит и повторён, что расходует потолок 3 спавнов.
- Исправление: отдельный (больший) default для legacy либо считать `step_start` признаком живости для first-token legacy; задокументировать env.
- Проверка: legacy-fake с `step_start` и задержкой 70 с проходит при настроенном пороге.

F-14 [blocking] Предсказуемый `/tmp`-каталог lease без проверки владельца
- Место: `server.py` ≈1387 (`LEASE_DIR`), ≈2476 (`mkdir`/`chmod` с `except OSError: pass`), ≈2600–2650 (reaper).
- Правило: security.md §9 («predictable path = race»), T-LIFE/v1.
- Evidence: каталог можно предсоздать чужим пользователем/симлинком; `chmod` падает молча, lease пишутся туда. Reaper берёт `owner_uid` из содержимого файла, а не из `st_uid`.
- Исправление: каталог в `0700`-пользовательском месте (`tempfile.gettempdir()`/`~/Library/Caches`) с проверкой `lstat` (не симлинк, `st_uid==getuid()`, права `0700`); reaper использует `st_uid` файла.
- Проверка: тест с foreign-owned/симлинк-каталогом даёт отказ и fallback на `run`.

F-15 [non-blocking] Неверная magic-константа Mach-O
- Место: `server.py` ≈1735 (`_is_native_opencode_bin`).
- Правило: python-standards §8/§6.
- Evidence: `b"\xfa\xed"` — ошибочная сигнатура (big-endian начинается с `\xfe\xed`); fat-бинарь (`\xca\xfe`) тихо отвергается, и serve навсегда выключен.
- Исправление: набор `{CF FA ED FE, CE FA ED FE, CA FE BA BE}` + ELF.
- Проверка: параметризованный тест по сигнатурам.

F-16 [non-blocking] KISS/сопровождаемость
- Место: `server.py` `_serve_one_attempt` (~400 строк), `_run_serve_stream_attempts` (~300), алиасы `parse_serve_event`/`_find_listener_pid`/`_ToolInputAccumulator`/`_dynamic_config_enabled`, неиспользуемая `_seen_tc` (≈6395), задублированные блоки `first_event_ms`/`ttft_ms` (≈5115, ≈5125), `FALLBACK_DECISION_TABLE`, не управляющая поведением.
- Правило: python-standards §6/§7, testing.md.
- Evidence: через полгода таблица и код разойдутся; алиасы существуют только ради поиска тестами.
- Исправление: выделить фазы (spawn / handshake / event-loop / classification), удалить алиасы и мёртвый код, либо сделать таблицу данными для классификатора.
- Проверка: размер функций <~60 строк, ruff/basedpyright без новых предупреждений.

F-17 [non-blocking] Потеря usage на ретраях JSON-watchdog
- Место: `server.py` ≈6215–6260.
- Правило: REQ-014 (SHOULD), AC-019.
- Evidence: на `continue` по watchdog/prompt_status usage неуспешной попытки не накапливается (в stream — только в одной ветке).
- Исправление: накапливать `result["usage"]` перед каждым `continue`.
- Проверка: тест с двумя попытками, где usage суммируется.

F-18 [non-blocking] `_serve_json_serve`: `client_gone` в JSON даёт `upstream_failed`
- Место: `server.py` ≈6190–6260, ≈6420.
- Правило: REQ-016 (O-EXIT).
- Evidence: при пустом результате ответ — «serve produced no text» с `exit_reason=upstream_failed`, хотя клиент ушёл.
- Исправление: см. F-02 (общая обработка `client_gone`).
- Проверка: `O-EXIT` содержит `client_gone`.

F-19 [non-blocking] [sweep] Дренаж stderr helper-а стартует после проверки listener-а
- Место: `server.py` ≈2570–2600.
- Правило: REQ-008, HL-ENV-01.
- Evidence: Попытка читать stderr начинается после `_lsof_listener_pid`-цикла (до 3 с). Тихий `opencode` не страдает, но шумный ранний вывод (≥64 КиБ) блокирует helper/serve, а ownership-проверка падает на таймауте. Размер одной строки в `deque(maxlen=64)` не ограничен.
- Исправление: запускать дренирующий поток сразу после `Popen`; ограничить длину строк.
- Проверка: фейк с 200 КиБ stderr до listener-а проходит рукопожатие.

F-20 [non-blocking] [sweep] Шаблонные `pyright: ignore` в новом тестовом модуле (RW-026)
- Место: `tests/test_realtime_reasoning.py` (~60 строк).
- Правило: python-standards запрет №9.
- Evidence: везде одна и та же формальная «причина: тест проверяет приватный/динамический API…»; фактического объяснения по месту нет. Для `reportPrivateUsage` приемлемо, но не для `reportUnnecessaryIsInstance`/`reportUnknown*`.
- Исправление: оставить только действительно необходимые ignore и убрать остальное явными аннотациями; объяснять причину индивидуально.
- Проверка: `basedpyright` без роста подавлений.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 20

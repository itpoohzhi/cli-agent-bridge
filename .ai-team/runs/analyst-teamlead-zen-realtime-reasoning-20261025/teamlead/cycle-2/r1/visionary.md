PANEL-NONCE: 9b7ea843db2c0ac7
ARTIFACT-SHA256: 2d0d7f1d6497ff00ecaf12bada3461971b497877a4619e28fee098123ad26e80

Все изменения в Цикле 2 суждены заново. У `server.py` в кандидате нет абсолютных номеров строк, поэтому в F-блоках привязка идёт к функции и фрагменту diff.

**Сверка SEED (критерий 6):** `seed_hex` = `4222bc6fb25df1ccb65e0dca4ccd65c56ebd69d0f7b014fea07252fe8d2720db`, `SEED` = `4222bc6f`. Пересчёт SHA-256 от дословной `seed_input` совпал с манифестом. `ranked_order` при ранжировании `SHA-256(seed_hex#slot_id)` совпал: claude-sonnet-5-5-high, gemini-4-argon-high, gpt-6.1-sol-high, grok-4.7-high, muse-wonder-full-1.0.

**Verify-fixed по RW-001..RW-032 (кратко):**
- Закрыты:
  - RW-002, RW-005, RW-007;
  - RW-013 (`can_spawn`), RW-014, RW-021, RW-024 (`_client_gone_check` в JSON-пути);
  - RW-027, RW-029, RW-030, RW-031, RW-032.
- Не закрыты или закрыты формально:
  - RW-001: тест ротации прокси сводится к `callable(...)`;
  - RW-008: `timeout` не классифицируется вызывающим кодом;
  - RW-009: фикс уведомлением через `settimeout(0.5)` с `continue` ломает чтение SSE (F-01);
  - RW-011: статусный таймер дублирует статусы и пишет без синхронизации (F-06);
  - RW-015: HTTP-статус `prompt` не доходит до классификации по таблице (F-05);
  - RW-018: AC-014 нарушается дублирующим статусом (F-06);
  - RW-019: утечки до создания lease (F-03);
  - RW-020: `join` потоков есть, но спин читателя остаётся (F-01);
  - RW-025: поведенческие оракулы не добавлены (F-07);
  - RW-026: подавления `pyright` заменены шаблонными (F-11);
  - RW-028: порог первого статуса не ужесточён.

Результаты L2 взяты из `execution-evidence.md`:
- RED: rc=1, 24 из 29 тестов падают на `origin/dev`.
- GREEN: pytest 408 passed, unittest OK, прогон в обратном порядке OK.
- Замороженные функции совпали.

Тесты я не запускал. `VER-006` и `VER-007` помечены `DEFERRED_L3`, живое поведение против реального `opencode serve` не проверено.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Читатель SSE ломается при любой паузе апстрима дольше 0,5 с (F-01). Истечение общего дедлайна и `client_gone` в JSON-пути трактуются как успех (F-02). Таблица `FALLBACK_DECISION_TABLE` и фактические переходы расходятся (F-05).
   СОВЕТЫ (при FAIL):
   - F-01: убрать короткий `settimeout` у SSE-сокета. Использовать блокирующее чтение и закрывать сокет из основного потока по `stop_event`. Либо ждать `select` на сокете до `readline`.
   - F-02: добавить в обработку результата ветки `timeout` и `client_gone`.
   - F-05: опрашивать `prompt_status` на каждой итерации цикла, а не только после получения события.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Нет поведенческих оракулов для AC-001, AC-002, AC-020, serve-watchdog'ов, JSON-пути serve, `client_gone` и ротации прокси (F-07). Не обработаны пути `timeout` и `client_gone` в JSON (F-02).
   СОВЕТЫ (при FAIL):
   - Добавить тесты по списку из F-07.
   - Закрыть ветки из F-02.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Спин-цикл читателя на любой ошибке сокета сжигает ядро и скрывает EOF (F-01). `_StartupGate` держится весь `_serve_one_attempt` и вообще не освобождается в JSON-пути при успехе (F-04). Локальный отказ `Popen` уходит в общий `except OSError` как «client gone» (F-03).
   СОВЕТЫ (при FAIL):
   - Освобождать gate сразу после готовности serve или первого события, как делает legacy-путь на первой строке stdout.
   - Конвертировать `OSError` в `ServeUnavailable`.
   - Выдавать sentinel `None` при любой фатальной ошибке сокета.

4. РИСКИ: VERDICT=FAIL
   WHY=Утечки `lifeline_w`, порта в `_ACTIVE_SERVE_PORTS` и каталога состояния при раннем отказе (F-03). Предсказуемый каталог lease в `/tmp` (F-08). Узкие места бюджета ресурсов не подтверждены нагрузочным прогоном (L3 отложен).
   СОВЕТЫ (при FAIL):
   - Обернуть всё от `mkdtemp` до `_ServeLease` в единый `try`.
   - Перенести каталог lease под пользовательский каталог и проверять владельца и права через `lstat`.
   - Провести живой L3 до приёмки.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбор «serve на запрос плюс откат на run» повторяет прецедент muse-bridge (ADR-0004) и сохраняет kill-switch. Прямой HTTP-SSE к Zen без заголовков CLI дал 429, поэтому не годится. Замечание о дублировании механизмов статусов оформлено как дефект F-06, а не как вопрос выбора пути.
   СОВЕТЫ (при FAIL): нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Сверка SEED: `seed_hex` = `4222bc6f…720db`, `SEED` = `4222bc6f`, `ranked_order` совпал с манифестом; независимый пересчёт совпал, в роли места №1 расхождений не нашёл. Замечания по соответствию правилам проекта:
   - около 100 одинаковых `# pyright: ignore[...] — причина: <шаблон>` в новом тестовом файле (F-11);
   - format-only правки в унаследованном коде и смена `CATALOG_SOURCE` (F-10);
   - единый механизм ошибок для 404 без проверки версии (F-09).
   Внешний HTTP-контракт моста сохранён.
   СОВЕТЫ (при FAIL):
   - Убрать шаблонные подавления и типизировать нормально.
   - Сократить format-only hunks в `server.py`.
   - Пересмотреть `CATALOG_SOURCE`.

**F-блоки**

F-01 [blocking, КОРРЕКТНОСТЬ/РЕАЛИЗУЕМОСТЬ]
- Место: `server.py::_serve_one_attempt._reader`, примерно после выставления `sse_conn.sock.settimeout(0.5)`.
- Правило: REQ-001, REQ-006, REQ-007, RW-009, RW-020, T-LIFE/v1.
- Evidence: `except (TimeoutError, OSError): ... continue`. В CPython после первого `socket.timeout` объект `SocketIO` помечается `_timeout_occurred`, и любое следующее чтение бросает `OSError("cannot read from timed out object")`. Читатель уходит в бесконечный холостой цикл на 100% CPU и больше не выдаёт событий; EOF-sentinel `None` не ставится. По `F-19` пауза между `execution.started` (233 мс) и первой дельтой размышления (1811 мс) превышает 0,5 с. Тесты этого не ловят: `test_slow_serve_gets_status_and_no_status_on_fast` проверяет только наличие статуса, а `test_ac026` использует интервалы 0,12 с. Утверждение основано на моём знании реализации CPython и не подтверждено запуском.
- Исправление:
  - не использовать короткий таймаут чтения на сокете, у которого после этого продолжается `readline`;
  - читать блокирующе, а завершение инициировать закрытием сокета из основного потока;
  - при любой иной фатальной `OSError` ставить `None` и выходить;
  - не допускать цикла без ожидания.
- Критерий: новый тест с FakeServe, у которого между `server.connected` и первой дельтой пауза 1,5 с, получает все дельты. Второй тест роняет сокет сервера и обнаруживает EOF не позже чем через 1 с.

F-02 [blocking, КОРРЕКТНОСТЬ/ПОЛНОТА]
- Место: `server.py::Handler._run_serve_stream_attempts` и `_serve_json_serve`, ветки после `_serve_one_attempt`.
- Правило: REQ-006, REQ-009, RW-008.
- Evidence: `_serve_one_attempt` возвращает `exit_reason="timeout"` и `"client_gone"` без `terminal`. Вызывающий код обрабатывает только `first_event_timeout`, `first_token_timeout`, `stall_timeout`, `invalid_serve_event`, статусы `prompt` и `client_gone` в потоковом пути. Результат `timeout` проваливается в `res.serve_health.record_success()`, `attempts.attempt_done(False, True)` и `finish_reason=stop` с `[DONE]`. В JSON-пути `client_gone` тоже падает в этот успех.
- Исправление: явно обработать `timeout` (ошибка клиенту, `exit_reason=timeout`, без `record_success`) и `client_gone` в JSON-пути.
- Критерий: тест с дедлайном 1 с и молчащим serve даёт `exit_reason=timeout` и не вызывает `record_success`.

F-03 [blocking, РЕАЛИЗУЕМОСТЬ/РИСКИ]
- Место: `server.py::_serve_one_attempt` (`_serve_env` с `mkdtemp`, затем `_spawn_serve` вне `try`) и `_spawn_serve` (участок `Popen` до создания `_ServeLease`).
- Правило: RW-019, REQ-008, T-LIFE/v1, C-MULT-I4.
- Evidence:
  - отказ `Popen` (`OSError`) и `"no free serve port"` происходят до создания lease;
  - `lifeline_w` не закрывается, порт остаётся в `_ACTIVE_SERVE_PORTS` навсегда, каталог `zen-serve-state-*` не удаляется;
  - `OSError` не конвертируется в `ServeUnavailable`, а потоковый обработчик перехватывает его как «client gone mid-stream»: клиенту ни ошибки, ни отката на `run`.
- Исправление: один `try/finally` от `mkdtemp` до выхода из `_spawn_serve` с очисткой всего перечисленного. `OSError` при запуске превращать в `ServeUnavailable`.
- Критерий: тест с подменённым `Popen`, бросающим `OSError`, показывает откат на `run`, ноль утечек FD, пустой `_ACTIVE_SERVE_PORTS` и удалённый state-каталог.

F-04 [blocking, РЕАЛИЗУЕМОСТЬ/РИСКИ]
- Место: `server.py::_run_serve_stream_attempts` (`gate.acquire()`, `gate.release()` после `_serve_one_attempt`) и `_serve_json_serve` (`_gate_j`).
- Правило: S-HERD-I1, REQ-013, REQ-004.
- Evidence: legacy-путь освобождает gate на первой строке stdout (`F-10`). В serve-пути он удерживается на всё время попытки. В JSON-пути `_gate_j.release()` не вызывается при успешном возврате, а вызывается только при исключениях и отказе limiter. Остальные запросы ждут `STARTUP_WAIT_S=5` с и идут без замка. Это задержка запуска model-вызова при параллельной нагрузке. Внутреннее устройство `_StartupGate` в пакете не приложено, оценка условна.
- Исправление: освобождать gate после готовности serve или первого события, как legacy. Добавить `finally` в JSON-пути.
- Критерий: два параллельных запроса стартуют менее чем за 1 с друг от друга. Счётчик `acquire`/`release` в тесте равен.

F-05 [blocking, КОРРЕКТНОСТЬ]
- Место: `server.py::_serve_one_attempt` (проверка `prompt_status` после `events.get`) и `_serve_http`.
- Правило: RW-015, `FALLBACK_DECISION_TABLE`, REQ-009.
- Evidence:
  - классификация `_ps` выполняется только после успешного `events.get()`; при пустой очереди идёт `continue`, и ошибка HTTP может ждать до `first_event_timeout` (20 с);
  - `_serve_http` читает тело целиком, поэтому `headers_at` ставится после тела;
  - для 429/5xx `delivered` считается по наличию токенов, а таблица говорит «headers received → DELIVERED=true → serve_retry»;
  - в режиме auto такой отказ без токенов приводит к откату на `run` вопреки таблице.
- Исправление: проверять `prompt_status` в каждой итерации цикла, до `events.get`. Заводить `delivered` по получению заголовков ответа.
- Критерий: поведенческие тесты по строкам таблицы (429, 5xx, 400, 401) проверяют фактические переходы `serve_health` и `breaker`, а не поиск строки в таблице.

F-06 [blocking, ПОЛНОТА/РИСКИ]
- Место: `server.py::_run_serve_stream_attempts` (`_initial_status_timer`, `on_status`, `last_reasoning`).
- Правило: REQ-005, REQ-009 (AC-014), RW-011.
- Evidence:
  - `threading.Thread(target=_initial_status_timer)` пишет в `wfile` без синхронизации с основным потоком; при совпадении по времени кадры SSE могут перемешаться;
  - таймер не отменяется при завершении попытки: он может записать после `[DONE]`;
  - на повторе `_model_seen` новый, `_wait` отрицательный, поэтому `STATUS_INITIAL` выдаётся мгновенно в начале каждой попытки; вместе со строкой «Повтор попытки» между попытками уже две статусные строки, а не одна (AC-014);
  - внутри `_serve_one_attempt` `STATUS_INITIAL` выдаётся ещё раз (`_status_emitted[0]==0`);
  - `last_reasoning` читается из двух потоков и не обновляется после статуса.
- Исправление: единый замок на запись в `wfile`, единый источник статусов, отмена таймера в `finally`, `STATUS_INITIAL` ровно один раз на запрос.
- Критерий: тест на двух попытках получает ровно один `STATUS_INITIAL` и одну строку «Повтор попытки». Тест на гонку пишет только корректные кадры.

F-07 [blocking, ПОЛНОТА/РИСКИ]
- Место: `tests/test_realtime_reasoning.py` (`test_ac026...`, `test_serve_health_and_fallback_table`, `test_spawn_cap_and_proxy_rotation_helpers`, `test_native_tool_and_permission_reject`, `test_dynamic_config_switch_same_server`, `test_slow_serve_gets_status_and_no_status_on_fast`, `test_helper_argv_validation_and_lease_dir`).
- Правило: RW-025, REQ-020, AC-001, AC-002, AC-020, REQ-001..REQ-016.
- Evidence:
  - AC-001 не проверен: тест проверяет разброс < 2,0 с, а не интервал < 500 мс; AC-002 не проверен;
  - в FakeServe есть режимы `__never_event__` и `__silent__`, но тестов serve-watchdog'ов (`first_event_timeout`, `first_token_timeout`, `stall_timeout`) нет;
  - нет тестов JSON-пути serve, `client_gone`, отсутствия пароля в логах (AC-020), реальной ротации прокси (проверяется только `callable(...)`), поведения строк `FALLBACK_DECISION_TABLE`;
  - тест permission проверяет только наличие `bash`, но не reject и не interrupt;
  - тест «dynamic config» проверяет читатель, но не маршрут;
  - успешный запуск helper с 6 аргументами и размещением lease не тестируется;
  - тест на «чужой sessionID» проверяет маппер, а не отбрасывание в цикле;
  - на `AC-005`, `AC-026` нет теста на медленный апстрим со статусом на живом сокете в serve-пути (только `__slow__` без проверки контента);
  - не могу проверить, продвигается ли пул прокси дважды за попытку (в `_run_env` и при явной передаче `proxy_url`).
- Исправление: добавить перечисленные тесты как нетривиальные оракулы.
- Критерий: каждый REQ-001..REQ-020 и AC-001..AC-026 имеет прямой тест, красный на сломанной реализации.

F-08 [non-blocking, РИСКИ]
- Место: `server.py` (`LEASE_DIR`, `_spawn_serve`, `_run_serve_helper_cli`, `_startup_reaper`).
- Правило: `agents/security.md` (предсказуемые пути в `/tmp`), T-LIFE/v1.
- Evidence: `/tmp/opencode-zen-bridge-leases` создаётся с `mode=0o700`, но существующий каталог не проверяется на владельца и не-symlink; `OSError` у `os.chmod` игнорируется. `owner_uid` и PID берутся из содержимого файла и самоопределяемы.
- Исправление: хранить lease под пользовательским каталогом (например `~/.dsh/...`). Проверять `lstat` на владельца, режим и отсутствие symlink до записи и чтения.
- Критерий: тест с чужим или symlink-каталогом возвращает отказ.

F-09 [non-blocking, РЕАЛИЗУЕМОСТЬ]
- Место: `server.py::_serve_one_attempt` (ветки `status in (400, 404, 422)` на ready/create/event).
- Правило: R-BULK-I3, F-DEG.
- Evidence: любой 404 на `GET /api/session/active` трактуется как `ServeSecurityError` (fail-closed без отката на `run`, без sticky-деградации). Обновление `~/.opencode/bin/opencode` с изменением маршрутов API выключит весь serve-путь с ошибкой клиенту, а не с откатом.
- Исправление: проверка версии через `GET /api/info` до сессии. Несовместимость маршрута до доставки трактовать как `ServeUnavailable` с записью в `serve_health`. Оставить fail-closed для 401/403.
- Критерий: тест с FakeServe, у которого `/api/session/active` отвечает 404, получает откат на `run` и рост `serve_health`.

F-10 [non-blocking, scope-diff]
- Место: `server.py` (format-only hunks в `_UpstreamBreaker`, `Run._execute_once`, `Handler._stream_sse`, `_serve_json`, `_RequestAttempts` и др.; `CATALOG_SOURCE = "init"` → `"static"`, `_set_catalog_source`); `tests/test_step_interruption.py:67` (`r'''` → `r"""`).
- Правило: FU-006, `agents/scope-and-contracts.md` (минимально достаточные изменения), `agents/code.md`.
- Evidence: в дельте Цикла 1→2 reformatting только вырос. Изменено начальное значение публичной константы `CATALOG_SOURCE`.
- Исправление: откатить format-only hunks вне логики. Либо обосновать `CATALOG_SOURCE`, либо вернуть `init`.
- Критерий: `git diff --stat` не содержит правок строк, не связанных с serve/watchdog. Тест `test_catalog_mode` зелёный.

F-11 [non-blocking, СООТВЕТСТВИЕ КОНТЕКСТУ]
- Место: `tests/test_realtime_reasoning.py` (около 100 строк `# pyright: ignore[...] — причина: тест проверяет приватный/динамический API моста, тип уточнён аннотациями вокруг`).
- Правило: `python-standards.md` запрет №9, RW-026.
- Evidence: идентичная шаблонная «причина» не объясняет конкретное подавление. `VER-004` проверяет отсутствие `pyright: ignore` только в изменённых диапазонах `server.py` и `test_step_interruption.py`, а новый файл просто «ноль диагностик» благодаря подавлениям.
- Исправление: типизировать (`cast`, Protocol, публичные хелперы) вместо подавления. Оставшиеся подавления сопровождать конкретной причиной.
- Критерий: число подавлений в новом файле существенно меньше, у каждого осмысленная причина.

F-12 [non-blocking, КОРРЕКТНОСТЬ]
- Место: `server.py::_run_serve_helper_cli._fd_ready`.
- Правило: RW-023, T-LIFE/v1.
- Evidence: `errno` импортируется только в `else`-ветке (после раннего выхода helper), а `_fd_ready` использует `errno.EAGAIN` при `OSError` вне `BlockingIOError`. При `EBADF` на fd 0 получим `NameError` вместо чистого завершения.
- Исправление: импортировать `errno` в начале модуля.
- Критерий: тест с закрытым fd 0 завершает helper кодом 0 с чисткой группы.

F-13 [non-blocking, ПОЛНОТА]
- Место: `server.py::_run_serve_stream_attempts`, `_serve_json_serve` (ветки `prompt_status`, транзиентная ошибка, `invalid_serve_event`; мёртвая переменная `_seen_tc`).
- Правило: FU-004 (REQ-014), RW-018.
- Evidence: usage неуспешных попыток копится только в одной ветке потокового пути и нигде в JSON. `_seen_tc` вычисляется и не используется, комментарий над ним ничего не реализует.
- Исправление: накапливать usage по всем веткам `continue`. Удалить мёртвый код.
- Критерий: тест с двумя попытками получает сумму usage в финальном чанке.

F-14 [non-blocking, ПОЛНОТА] [sweep]
- Место: `server.py::_run_serve_stream_attempts` (`_delivered_err = bool(collected_texts or result.get("texts"))`).
- Правило: REQ-009 (AC-014), REQ-005.
- Evidence: доставка, состоящая только из размышления, не считается «доставленной». Транзитная ошибка после размышления уходит в откат на `run`, и клиент получает размышление повторно без разделителя `[мост]`.
- Исправление: учитывать `reasonings` в `_delivered_err`. При откате на `run` после выданного размышления вставлять одну статусную строку.
- Критерий: тест с ошибкой после трёх дельт размышления не дублирует их и выдаёт ровно один разделитель.

**Подкатегории (14):**

SUB Корректность/логика: FAIL — `server.py::_serve_one_attempt._reader` (F-01); обработка `timeout` (F-02).
SUB Корректность/граничные условия: FAIL — `settimeout(0.5)` против паузы 1,5–1,8 с (F-01, `F-19`); дедлайн (F-02).
SUB Корректность/обработка ошибок: FAIL — `Popen OSError` попадает в «client gone» (F-03); HTTP-статус `prompt` классифицируется с задержкой (F-05).
SUB Полнота/покрытие AC: FAIL — AC-001, AC-002, AC-020 и serve-watchdog'и без оракулов (F-07).
SUB Полнота/пропущенные ветки: FAIL — `timeout`/`client_gone` в JSON (F-02), статусы (F-06), размышление-только доставка (F-14).
SUB Реализуемость/общее: FAIL — спин читателя и удержание gate (F-01, F-04).
SUB Риски/безопасность: FAIL — предсказуемый `/tmp`-каталог lease с самоопределяемым `owner_uid` (F-08, non-blocking).
SUB Риски/данные: PASS — `OPENCODE_DB=:memory:`, allowlist окружения и случайный пароль (`_serve_env`, `execution-evidence.md` EVD-072).
SUB Риски/прод: FAIL — утечки FD/порта/каталога и неотменённый статусный поток (F-03, F-06); живой L3 отложен (`DEFERRED_L3`).
SUB Риски/regression red→green: PASS — `l2-red.log` rc=1, 24 падения на `origin/dev`; GREEN rc=0 (`code-gate.json`).
SUB Риски/Full Suite (L2): PASS — `l2-green-ver001/002/003/003b/ac023`: 408 passed, unittest OK, обратный порядок OK.
SUB Риски/scope-diff: FAIL — format-only hunks и смена `CATALOG_SOURCE` (F-10, non-blocking).
SUB Альтернативы/общее: PASS — прецедент muse-bridge ADR-0004, kill-switch сохранён, Google-маршрут побайтово неизменён (`code-gate.json`).
SUB Соответствие контексту/общее: FAIL — шаблонные `pyright: ignore` и унаследованный reformatting (F-09, F-10, F-11, non-blocking кроме части F-09 по версионной проверке).

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

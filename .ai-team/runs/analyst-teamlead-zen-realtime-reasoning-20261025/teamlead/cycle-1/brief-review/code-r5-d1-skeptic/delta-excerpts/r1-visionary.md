> PANEL-NONCE: 7ec7d741c844094d
> ARTIFACT-SHA256: 5b0d1dea0cf4996f6d744e0eb2d82176578091bad35c943dde722c09d3784df4
>
> **Позиция Визионера.** Стратегически кандидат правильный. Это гибрид C: `opencode serve` по SSE с откатом на `run`, как в `muse-bridge` (ADR-0004). Он единственный даёт реальные дельты размышления (F-19), kill-switch и расширяемую телеметрию `O-EXIT/v1`. Но в нынешнем виде он ломает доставку текста, ломает конкурентность и ухудшает дефолтный путь `run`. Номера строк в F-блоках приблизительные: они выведены из диапазонов VER-004 и названий функций, потому что в пакете есть только diff.
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=В `_serve_one_attempt` дельты reasoning и text с пустым `.strip()` не пересылаются клиенту. Параграфные `\n\n` и пробелы теряются, это нарушает AC-006 и ломает превью DSH по `\n` (F-01). Аллокация порта serve гоняется при параллельных запросах и может отправить пароль чужому serve, после чего ответ fail-closed с `ServeSecurityError` (F-02). Для serve не реализованы `_StartupGate` и `spawn_limiter` из REQ-013 (F-04). Статус ответа prompt игнорируется (F-05). Повтор после `delivered=True` дублирует контент и tool_calls (F-06). Сторож `FIRST_TOKEN_TIMEOUT_S=60` убивает легитимные шаги дефолтного пути `run` (F-03).
>    СОВЕТЫ:
>    - Пересылать любые непустые дельты без `strip`, а живость токенов считать отдельно (F-01).
>    - Выделять порты под замком до проверки владения слушателем или брать порт 0 (F-02).
>    - Не применять 60-секундные сторожа токенов к legacy-пути и вынести его поведение за флаг (F-03).
>    - Подключить `spawn_limiter` и `_StartupGate` к serve (F-04).
>    - Разбирать `prompt_status`, а `FALLBACK_DECISION_TABLE` либо сделать исполняемой, либо удалить (F-05).
>    - После отданного контента делать дедуп или не ретраить (F-06).
>
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=Нет тестов на AC-011 и AC-012, на serve-таймауты, на `_serve_json_serve` (+208 строк), на AC-018 и AC-020; фикстуры `__silent__` и `__never_event__` не используются (F-10). Первый статус `[мост]` ≤1.0 с (REQ-004) не гарантирован: `STATUS_INITIAL` не эмитируется, а ожидание gate и фаза spawn молчат (F-07). Матрица прослеживаемости ставит PASS «по VER-001» для требований без теста. Часть тестов тавтологична (F-13). Поддерживаемость страдает из-за функций по ~350 строк и дублирования stream/JSON (F-17).
>    СОВЕТЫ:
>    - Добавить тесты на watchdog, client_gone, kill orphans, JSON-serve, ротацию прокси и отсутствие пароля в логах.
>    - Эмитить `STATUS_INITIAL` сразу после role-чанка, до gate.
>    - Исправить матрицу прослеживаемости.
>    - Разбить `_serve_one_attempt` и вынести общую логику stream/JSON.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
>    WHY=Скрытые операционные издержки: гонка портов при `max_concurrent=6` (F-02), утечка tempdir и FD при сбое spawn (F-09), `lsof` и `ps` на каждую попытку, предсказуемый каталог в `/tmp` (F-14). Неподтверждённый реальный wire v2.1.2: событие с пустым `data` (на 161 мс в F-19 есть `integration.updated`) даёт `ServeProtocolError` с `delivered=True` (F-08).
>    СОВЕТЫ:
>    - Сериализовать запуск serve.
>    - Освобождать ресурсы в `finally` до создания lease.
>    - Снять реальные wire-фикстуры v2.1.2 и прогнать лестницу H0..H9 до включения флага.
>    - Ограничить права на lease-каталог.
>
> 4. РИСКИ: VERDICT=FAIL
>    WHY=Искажение данных клиента (F-01), регрессия дефолтного пути `run` (F-03), конкурентный отказ (F-02), риск 100% отказа serve на реальном wire (F-08). Полный набор зелёный (400 passed, `VER-001..003`, `AC-023`), но проверяет в основном фейки. Выявленные дефекты воспроизводимы только новыми тестами. Lease-каталог в `/tmp` без владельца и режима (F-14). Прямая мутация `os.environ` в `test_step_interruption.py` (F-21).
>    СОВЕТЫ:
>    - Закрыть F-01, F-02, F-03 и F-08 regression-тестами по схеме red→green.
>    - Поднять конкурентный тест на 6 запросов.
>    - Добавить live-замер на реальном `opencode` после сброса квоты.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=FAIL
>    WHY=Выбор архитектуры оправдан. Но реализация раздута: самописный `_JsonParser` на ~150 строк при импортированном stdlib `json` (F-11), тестовый хук `SERVE_TEST_ELIGIBLE` и вакуумная `_is_native_opencode_bin` в проде (F-15), мёртвая `FALLBACK_DECISION_TABLE` (F-05).
>    СОВЕТЫ:
>    - Заменить парсер на `json.loads` с явным `except`.
>    - Убрать тестовые хуки из продакшн-кода.
>    - Удалить декларативную таблицу или сделать её исполняемой.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
>    WHY=Нарушены python-standards: блоковое подавление pyright и `type: ignore` без обоснования (F-12), функции сильно длиннее ~40 строк и дубли (F-17), тавтологичные тесты (F-13), шум форматирования в немодифицируемых зонах (F-16). Публичный OpenAI-контракт и `_run_env`/Google-срезы не изменены, это соответствует Non-Goals.
>    СОВЕТЫ:
>    - Убрать подавления типов, типизировать тесты.
>    - Откатить косметические hunk'и.
>    - Декомпозировать serve-функции.
>    - Переименовать тесты, чьи ожидания изменены (F-18).
>
> **SUB-строки (14/14):**
> 1. SUB Корректность/логика: FAIL — `_serve_one_attempt` (server.py:~2360-3114) `if text_value.strip():` в ветках reasoning и text; `_spawn_serve`; повтор в `_run_serve_stream_attempts` (F-01, F-02, F-06)
> 2. SUB Корректность/граничные условия: FAIL — whitespace-дельты, события с пустым `data`, stall при длинном tool-input (F-01, F-08, F-20)
> 3. SUB Корректность/обработка ошибок: FAIL — `_prompt_worker` игнорирует статус и ошибку, `_loads_object` возвращает `{}` при ошибке, `_spawn_serve` пропускает не-`ServeUnavailable` OSError (F-05, F-09, F-11)
> 4. SUB Полнота/покрытие AC: FAIL — AC-011/012/018/020 без тестов; REQ-013 и REQ-004 не выполнены полностью (F-04, F-07, F-10)
> 5. SUB Полнота/пропущенные ветки: FAIL — не реализованы строки 429/5xx и ответ prompt из таблицы; нет дедупа при повторе (F-05, F-06)
> 6. SUB Реализуемость/общее: FAIL — гонка портов при `max_concurrent=6`, утечки, `lsof` на попытку (F-02, F-09)
> 7. SUB Риски/безопасность: FAIL — предсказуемый `/tmp/opencode-zen-bridge-leases` без 0700 и проверки `owner_uid`; пароль может уйти чужому слушателю (F-14, F-02)
> 8. SUB Риски/данные: FAIL — потеря `\n` и пробелов в `reasoning_content` и `content` (F-01)
> 9. SUB Риски/прод: FAIL — `FIRST_TOKEN_TIMEOUT_S=60` на буферизующем `run`, максимум наблюдения 85.65 с (F-03, F-08)
> 10. SUB Риски/regression red→green: PASS — `l2-red.log` rc=1 на `origin/dev`, зелёный на кандидате; слабость RED (падения по `AttributeError`) учтена в F-13
> 11. SUB Риски/Full Suite (L2): PASS — `receipts/code-gate.json` VER-001/002/003/003b/005 и AC-023 rc=0, 400 passed; VER-006/007 законно DEFERRED_L3
> 12. SUB Риски/scope-diff: FAIL — косметический реформат `Run.execute`, `_RequestAttempts`, `_UpstreamBreaker`, `_PrefixDedup` и др. (F-16)
> 13. SUB Альтернативы/общее: FAIL — самописный `_JsonParser`, тестовый хук в проде (F-11, F-15)
> 14. SUB Соответствие контексту: FAIL — python-standards #9, §6/§7, testing.md об `os.environ` (F-12, F-17, F-21)
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
>
> **F-блоки**
>
> F-01 [blocking] Whitespace-дельты не пересылаются клиенту
> - Locations: server.py:~2360-3114 (`_serve_one_attempt`, ветки `etype == "reasoning"` и `etype == "text"`).
> - Правило: REQ-005/AC-006 (текст модели не модифицируется), REQ-001; F-37 (превью требует `\n`).
> - Evidence: `if text_value.strip(): … on_reasoning(text_value)` и такое же условие для `on_text`.
> - Fix: пересылать любую непустую дельту без `strip`; `first_token_at` и `last_token_at` обновлять только по содержательным токенам.
> - Проверка: тест с дельтами `"\n\n"`, `" "`, `"\n"`: конкатенация побайтно равна эталону, в том числе внутри `<tool_invoke>`.
>
> F-02 [blocking] Гонка выбора порта serve и отправка пароля не тому serve
> - Locations: server.py:~2360-3114 (`_spawn_serve`, цикл `range(20000 + pid%20000, 60000)` с bind-проб и закрытием сокета); `_serve_one_attempt` (ready-проверка).
> - Правило: C-MULT-I3/I4; `scope-and-contracts` (не ломать конкурентные запросы); `security.md` §9.
> - Evidence: все потоки сканируют от одного кандидата, сокет закрывается до bind serve. Два запроса в окне ~110 мс получают один порт. Если `lsof` ещё не видит слушателя, `GET /api/session/active` попадает в чужой serve и возвращает 401. Это `ServeSecurityError` без fallback.
> - Fix: глобальный замок на выделение порта до проверки владения; либо `--port 0` с чтением реального порта; 401 на ready до DELIVERED считать `ServeUnavailable`.
> - Проверка: тест на 6 параллельных stream-запросов, ни одного `serve security failure`.
>
> F-03 [blocking] Регрессия дефолтного пути `run`: watchdog первого токена 60 с
> - Locations: server.py:5351-5474 (`send_keepalive`, `watchdog_state`); константы `FIRST_TOKEN_TIMEOUT_S`, `FIRST_EVENT_TIMEOUT_S`, `STALL_TIMEOUT_S`.
> - Правило: REQ-003 (прежний путь остаётся рабочим), REQ-002.
> - Evidence: F-17/F-18: `run` выдаёт reasoning и text одним блоком в конце шага. F-32: максимум `deepseek-v4.1-flash-free` 85.65 с. По умолчанию serve выключен, поэтому путь `run` основной. Шаг дольше 60 с убивается и повторяется до 3 раз. Статусы `[мост]` и watchdog на `run` работают вне переключателя транспорта.
> - Fix: для legacy использовать потолок не ниже прежнего поведения либо отдельные пороги с высоким дефолтом, `first_event` считать по `step_start`, watchdog первого токена оставить только для serve; поведение legacy за флагом.
> - Проверка: фейк-CLI с паузой 70 с до единого блока завершается успешно без ретраев.
>
> F-04 [blocking] REQ-013 не выполнен для serve
> - Locations: server.py:~2360-3114 (`_serve_one_attempt` / `_spawn_serve`); AC-018.
> - Правило: REQ-013 (`_StartupGate`, `SPAWN_RATE_PER_S`), R-BULK-I2.
> - Evidence: serve-путь не вызывает `gate.acquire()` и `res.spawn_limiter.acquire()`, теста на ротацию IP нет.
> - Fix: acquire `spawn_limiter` и gate перед `_spawn_serve`, release в `finally`.
> - Проверка: тест двух запусков с подменённым `_next_standalone_proxy` и ограничением частоты.
>
> F-05 [blocking] Результат prompt-POST игнорируется, `FALLBACK_DECISION_TABLE` мёртва
> - Locations: server.py:~2360-3114 (`_prompt_worker`, `prompt_status`); `FALLBACK_DECISION_TABLE` (server.py:~1450-1560).
> - Правило: `error-handling.md` (Identify→Assess), REQ-009.
> - Evidence: пишется `prompt_status["status"/"error"]`, проверяется только 401/403. 400/429/5xx и сетевая ошибка приводят к ожиданию 20 с. Строка таблицы про 429 и provider5xx не реализована, тест таблицы проверяет только `len ≥ 10`.
> - Fix: классифицировать статус prompt по таблице (retry с breaker+1, fail-closed на 400/404/422) или удалить таблицу.
> - Проверка: FakeServe отвечает 429 на prompt, затем retry без ожидания 20 с.
>
> F-06 [blocking] Повтор после отданного контента дублирует text и tool_calls
> - Locations: server.py:4734-4967 (`_run_serve_stream_attempts`, ветки `allow_retry`/`continue`); `_serve_json_serve`.
> - Правило: REQ-009/AC-014, REQ-010.
> - Evidence: legacy использует `_PrefixDedup`, serve нет. После `stall_timeout` при уже отданных text или tool_call повтор выдаёт тот же контент снова.
> - Fix: дедуп префикса либо запрет retry после отданного text или tool_call.
> - Проверка: тест stall после части текста и вызова инструмента, клиент не видит дублей.
>
> F-07 [blocking] Первый статус ≤1.0 с (REQ-004) не гарантирован
> - Locations: server.py:5351-5474 (`send_keepalive`); `_serve_one_attempt` (`status_next`, `STATUS_INITIAL`).
> - Правило: REQ-004/AC-005.
> - Evidence: `STATUS_INITIAL` объявлен и нигде не эмитируется. На legacy статусы идут только из цикла `feed.lines`, а до него `_StartupGate` держит до 5 с (STARTUP_WAIT_S) и `spawn_limiter`. На serve цикл статусов стартует после spawn, ready, create, subscribe.
> - Fix: эмитить `STATUS_INITIAL` сразу после role-чанка до gate и spawn при включённом thinking.
> - Проверка: удержать gate 3 с, первый чанк с `[мост]\n` приходит ≤1.0 с.
>
> F-08 [blocking] Реальный wire v2.1.2 не проверен: события с пустым `data`
> - Locations: server.py:~1800-1880 (`_map_serve_event`: `if not data: raise ServeProtocolError`); `_serve_one_attempt` (`except ServeProtocolError` → `delivered=True`).
> - Правило: R-BULK-I3, REQ-012; факт-карта F-19, VER-006 DEFERRED_L3.
> - Evidence: любое событие кроме `server.connected` с пустым `data` (в F-19 на 161 мс приходит `integration.updated`) даёт `invalid_serve_event`, `delivered=True` и retry вместо fallback. Все фикстуры синтетические.
> - Fix: игнорировать неизвестные события и пустой `data`, валидировать только известные типы; добавить фикстуры, снятые с реального serve; прогнать VER-006 на живом контуре до включения флага.
> - Проверка: тест, подающий heartbeat и `integration.updated` с пустым `data`, не прерывает попытку. Статус PLAUSIBLE.
>
> F-09 [blocking] Утечка tempdir и FD при сбое запуска serve
> - Locations: server.py:~2360-3114 (`_serve_env` → `mkdtemp`; `_spawn_serve`: `os.pipe`, `Popen` до создания `_ServeLease`; `lease_dir.mkdir`).
> - Правило: T-LIFE/v1, C-MULT-I4 (освобождение в `finally`).
> - Evidence: `zen-serve-state-*` удаляется только `lease.cleanup()`. При `ServeUnavailable("no free serve port")`, `OSError` от `Popen` (не перехватывается обработчиками) состояние и `lifeline_w` не освобождаются.
> - Fix: `try/finally` вокруг всего пути от `_serve_env`, закрытие обоих концов pipe, оборачивание OSError в `ServeUnavailable`.
> - Проверка: тест с подменённым `Popen` (OSError): нет `zen-serve-state-*` и FD после 50 итераций.
>
> F-10 [blocking] Пробелы покрытия AC и неточная матрица
> - Locations: tests/test_realtime_reasoning.py (весь модуль); verification-traceability.md (строки REQ-006..009, REQ-013..016).
> - Правило: testing.md (регресс на каждое требование), `council` «Полнота/покрытие AC».
> - Evidence: нет тестов на AC-011/AC-012, serve `first_event/first_token/stall`, `_serve_json_serve`, AC-018, AC-020; фикстуры `__silent__` и `__never_event__` не используются; все строки матрицы PASS ссылаются на общий VER-001.
> - Fix: добавить недостающие тесты и привязать каждую строку матрицы к конкретному тесту.
> - Проверка: матрица с именем теста на каждое REQ/AC.
>
> F-11 [blocking] Самописный `_JsonParser` / `_loads_object`, ошибки маскируются
> - Locations: server.py:~1560-1700 (`_JsonParser`, `_loads_object`), используется в `_read_dynamic_config_enabled`, `_spawn_serve`, `_serve_http`, `_reader`.
> - Правило: python-standards §6/§7 (KISS, DRY), §3 (не маскировать ошибки); `json` остаётся импортированным.
> - Evidence: ~150 строк разбора JSON при доступном `json.loads`; парсер возвращает `{}` на ошибку, `RecursionError` не ловится, битый SSE-кадр превращается в `invalid_serve_event`.
> - Fix: `json.loads` с явным `except (ValueError, RecursionError)` и логом.
> - Проверка: тест битого и глубоко вложенного кадра даёт управляемую ошибку.
>
> F-12 [blocking] Подавления типов без обоснования
> - Locations: tests/test_realtime_reasoning.py:2 (`# pyright: reportAny=false, …` на 10 правил); `# type: ignore[attr-defined]` в `test_watchdog_first_event_timeout` и `setUp`/`tearDown` группы B.
> - Правило: python-standards, запрет №9.
> - Evidence: VER-004 требует нуль диагностик в новом тест-файле, и он достигнут блоковым подавлением, а не типизацией.
> - Fix: типизировать, убрать блоковое подавление и ненужные `type: ignore`, оставить точечные с причиной.
> - Проверка: VER-004 без подавлений.
>
> F-13 [non-blocking] Тавтологичные и неустойчивые тесты
> - Locations: tests/test_realtime_reasoning.py: `test_serve_health_and_fallback_table` (`assertTrue(silence or rows)`), `test_helper_argv_validation_and_lease_dir`, `test_native_tool_and_permission_reject`, `test_slow_serve_gets_status_and_no_status_on_fast`, пороги `≤1.0` и `<2.0`.
> - Правило: testing.md («тест должен воспроизводить баг»).
> - Evidence: тавтология; тест для «lease_dir» проверяет только rc≠0 при 5 аргументах; в native-тесте не проверяется, что reject отправлен; в «fast» части нет утверждения; RED в 16 тестах из-за `AttributeError`, а не поведения; Coder сам видел 1.04 с против 1.0.
> - Fix: реальные утверждения, `FakeClock` или запас по порогам.
> - Проверка: тесты красные на мутациях.
>
> F-14 [non-blocking] Lease-каталог в `/tmp` без владельца и режима
> - Locations: server.py:~2360-3114 (`LEASE_DIR`, `_spawn_serve`, `_startup_reaper`).
> - Правило: `security.md` §9 (predictable path), `error-handling`.
> - Evidence: `mkdir(parents=True, exist_ok=True)` с umask по умолчанию, reaper не проверяет `owner_uid` и ориентируется на подстроку `--serve-helper`.
> - Fix: каталог 0700 под `~/.dsh/…` или `os.mkdir` с проверкой владельца, проверка `owner_uid` и `parent_start_ts`.
> - Проверка: тест reaper на чужой lease.
>
> F-15 [non-blocking] Тестовый хук и вакуумная проверка нативного бинаря
> - Locations: server.py:~1560-1700 (`SERVE_TEST_ELIGIBLE`, `_is_native_opencode_bin`: `or len(head) == 4`).
> - Evidence: условие истинно для любого файла ≥4 байт без `#!`; тестовый флаг в продакшн-модуле.
> - Fix: проверка реального формата Mach-O/ELF, подмена бинаря в тестах через патч.
> - Проверка: текстовый файл без shebang не считается нативным.
>
> F-16 [non-blocking] Косметический реформат чужих областей
> - Locations: server.py: `_UpstreamBreaker` (~2204), `_RequestAttempts` (~2230-2291), `_PrefixDedup`, `Run.execute/_execute_once` (4427-4530), `Handler._res`, `_log_exit`; test_step_interruption.py:67 (кавычки `FAKE_OPENCODE`).
> - Правило: AGENTS.md п.4 (минимальные изменения), scope-diff.
> - Evidence: reverse-spec §1 («чисто форматирующие перестановки»).
> - Fix: вынести форматирование в отдельный коммит или откатить hunk'и вне поведения.
> - Проверка: diff без форматирующих hunk'ов в немодифицированных функциях.
>
> F-17 [non-blocking] Размер функций и дубли
> - Locations: `_serve_one_attempt` (~350 строк), `_run_serve_stream_attempts` (~190), `_serve_json_serve` (~210) в server.py (+1900 строк, итог 6287).
> - Правило: python-standards §6/§7, SOLID/SRP.
> - Evidence: вложенные замыкания; одинаковая логика retry, fallback и native-маппинга в stream и JSON.
> - Fix: выделить класс попытки serve и общий retry-цикл.
> - Проверка: функции ≤ ~80 строк, одна реализация retry-логики.
>
> F-18 [non-blocking] Изменённый оракул `test_step_interruption.py`
> - Locations: tests/test_step_interruption.py: `test_unmapped_retries_do_not_exhaust_incomplete_budget_stream/json` (~413-450).
> - Правило: verification-surface (`oracle_change` аудитирует Verifier), REQ-017.
> - Evidence: ожидания «4 запуска, tool_calls» заменены на «3 запуска, `[]`, stop», имена тестов «do_not_exhaust» утверждают обратное, записи аудита `oracle_change` в `verifier.json` нет.
> - Fix: переименовать тесты, задокументировать изменение контракта потолка, зафиксировать аудит.
> - Проверка: запись в `verifier.json`.
>
> F-19 [non-blocking] Жизненный цикл потоков и очереди
> - Locations: server.py:~2360-3114 (`_reader` с блокирующим `events.put`, `_prompt_worker` timeout 65 с, `threading.Thread(daemon=True)` без join).
> - Правило: T-LIFE/v1, C-MULT-I2.
> - Evidence: при заполненной очереди 4096 читатель блокируется навсегда, при раннем выходе потоки не завершаются, пока не закроются сокеты.
> - Fix: `put` с таймаутом и сигналом остановки, join или cancel потоков в `finally`.
> - Проверка: тест утечки потоков после 50 запросов.
>
> F-20 [non-blocking] [sweep] Watchdog считает только reasoning/text/завершённый tool
> - Locations: server.py:~2360-3114 (`_serve_one_attempt`, `last_token_at`, `first_token_at`).
> - Evidence: `session.tool.input.delta` и `reasoning.started` не обновляют `last_token_at`; при длинной генерации аргументов инструмента срабатывает `stall_timeout` через 60 с.
> - Fix: считать tool-input дельты признаком живости.
> - Проверка: фикстура с долгим tool-input без text не даёт ложный stall.
>
> F-21 [blocking] [pre-existing] Прямая мутация `os.environ` в изменённом тестовом файле
> - Locations: tests/test_step_interruption.py:~188-192 (`setUp`: `os.environ["FAKE_OC_COUNTER"] = …`, `FAKE_OC_PLAN`).
> - Правило: testing.md («запрет мутации `os.environ` без изоляции»); файл изменён задачей, значит blocking по §3 Diff-scope.
> - Evidence: записи без `monkeypatch` и гарантированного отката.
> - Fix: `mock.patch.dict` или `monkeypatch`.
> - Проверка: порядок запуска не влияет на результат (AC-023 reversed).
>
> COVERAGE: 14/14 подкатегорий
> FINDINGS_COMPLETE: 21

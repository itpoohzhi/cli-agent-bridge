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

PANEL-NONCE: f9d4563399369705
ARTIFACT-SHA256: ee2da4f64befd741a513be9f257c63ac14d1662c4aa76f7d71c84d36ce45f794

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Все три блокирующих замечания Раунда 2 (F-203, F-208, F-211) закрыты в коде и покрыты тестами; заявленные в брифе проверки воспроизведены мной независимо (100 тестов OK, ruff OK). Остаточных дефектов уровня FAIL не нашёл; два неблокирующих примечания перечислены ниже.
   SUB 1/F-203: PASS — флаг вынесен на Handler (server.py:3629), сбрасывается на запрос и на попытку (server.py:5058, 3753); устанавливается при отказе живой записи (server.py:5148-5152); терминальные кадры, включая stop/usage/error/[DONE], мёртвому клиенту не отправляются (server.py:5171-5175), в ветке исключения dispatch то же самое (server.py:5159-5164); keepalive не шлётся при client_write_dead (server.py:3861-3868). Тесты TestClientWriteDeadSuppressesTerminalFrames, TestKeepaliveRespectsDeadClient — зелёные.
   SUB 1/F-208: PASS — неограниченная очередь и put без отбрасывания строго при sse_writer is None (server.py:2665-2669, 2742-2744); live_invalidated из-за размера очереди достижим только при sse_writer != None (server.py:2745-2754). Тесты TestRunQueueLiveOnlyLimit и TestNonStreamBurstBeyondQueueLimit (1100 событий, полный контент) — зелёные.
   SUB 1/F-211: PASS — ветка kind == "done" проверяет live_invalidated до parser.finish и fallback (server.py:3952-3964); терминальный сбой после live-префикса даёт валидный chat.completion.chunk с error и отдельный [DONE] (server.py:5093-5116, 5245-5252, 5257; исключение dispatch — server.py:5168-5169). Тесты TestLiveFailureEnvelopeAfterPrefix (4) и TestDoneKindHonorsLiveInvalidation (2) — зелёные.
   SUB 1/RW-009: PASS — живые записи и keepalive ограничены LIVE_WRITE_TIMEOUT_S=3с (server.py:134, 5124, 5140); после первого отказа записи новых попыток нет; вычисление и commit от читателя не зависят, L/T и слот P освобождаются по завершении _execute (server.py:4256-4264). TestImmediateLockRelease (нечитающий клиент, MAX_CONCURRENT=1, второй ход проходит) — зелёный.
   SUB 1/RW-205-префикс: PASS — сверка с реально отправленным префиксом до перезаписи слота (server.py:3134-3151), вызовы из complete-веток text и thinking (server.py:3304-3310, 3320-3326); 5 тестов на mismatch, укорочение, второй mid, валидное продолжение и отсутствие дублей — зелёные.
   ПРИМЕЧАНИЯ (не блокируют): в конверте ошибки code всегда "live_prefix_invalidated", включая случай delivery_budget (server.py:5109, 5245-5252) — совпадает с примером packet'а error_frame, но сужает словарь кодов; комментарий «сколько байт slot["text"]» (server.py:3108) при фактическом счёте в символах (server.py:3127-3130) — поведение корректно (леджер внутренне согласован), стоит поправить формулировку.

2. ПОЛНОТА: VERDICT=PASS
   WHY=Требования AD-001..AD-004 закрыты по существу, все четыре замечания F-203/F-208/F-211/F-212 имеют и код, и тесты; целевой набор из брифа воспроизведён мной с нуля (100/100 OK).
   SUB 2/AD-001: PASS — необратимый префикс, запрет retry после первого accepted payload через run._live_mids (server.py:4287-4294), при инвалидации — fail-close без success finish/usage (server.py:3419-3430).
   SUB 2/AD-002: PASS — strict_live включается ровно при живом sink (server.py:3801-3805), legacy по умолчанию (core/tool_emulation.py:298); 4 парных регрессии strict/live и legacy-фолбэк без изменений (tests/test_tool_parser.py).
   SUB 2/AD-003: PASS — bounded live-очередь 1024 (server.py:281, 2665-2669), неблокирующий producer (server.py:2745-2754), выпуск L/T независимо от drain (server.py:4256-4264); примечание по механизму — в критерии 6.
   SUB 2/AD-004: PASS — один finish (server.py:5205), usage только при ненулевых токенах (server.py:5214), finish_reason: null только live droid (server.py:5232), ровно один [DONE] (server.py:5257).
   SUB 2/F-212 (тесты): PASS — 32 теста / 17 классов (tests/test_live_stream.py:98-969): подавление кадров, non-stream >1024 событий, конверт сбоя после live-байт, overflow unit и e2e, UTF-8 бюджет, изоляция бэкендов.

3. ЧИТАЕМОСТЬ: VERDICT=PASS
   WHY=Стиль и комментарии соответствуют репозиторию; докстринги объясняют контракты AD/RW/F с привязкой к строкам решений; ruff на всех шести файлах патча — All checks passed (exit 0, мой запуск).
   SUB 3/server.py: PASS — комментарии привязаны к AD/RW (server.py:3697-3717, 3704-3716, 4040-4048, 2734-2741); имена take/_publish/_live_diff/_check_live_prefix однозначны.
   SUB 3/parser: PASS — LiveParserError с докстрингом режима (core/tool_emulation.py:277-294), режим в сигнатуре (core/tool_emulation.py:298), комментарии в feed/finish (core/tool_emulation.py:308-341).
   SUB 3/non-stream: PASS — прежние комментарии и границы сохранены (server.py:4287, 3434-3440), _serve_json не изменён (server.py:4966-5031).
   SUB 3/минорные формулировки: PASS (примечание) — расхождение слова «байт» с фактическим счётом символов в live-леджере (server.py:3108 против 3127-3130); на корректность не влияет.

4. ПРОИЗВОДИТЕЛЬНОСТЬ И БЕЗОПАСНОСТЬ: VERDICT=PASS
   WHY=Медленный сокет ограничен 3 с и после первого отказа запись прекращается; live-очередь ограничена с явным fail-close, non-stream без лимита и потерь; бюджеты считаются в байтах UTF-8 и возвращаются в finally.
   SUB 4/медленный сокет: PASS — LIVE_WRITE_TIMEOUT_S=3с на запись и keepalive (server.py:134, 5118-5127, 5129-5152); зависаний L/T нет (TestImmediateLockRelease, TestKeepaliveRespectsDeadClient).
   SUB 4/очереди: PASS — live 1024 с неблокирующим отбрасыванием и инвалидацией (server.py:281, 2745-2754); потеря терминального события компенсирована проверками live_invalidated при опустошении очереди, в коалесинге и на done (server.py:3840-3854, 3874-3876, 3954-3964); non-stream неограничен (server.py:2742-2744).
   SUB 4/UTF-8 бюджеты: PASS — резерв байтов до отправки куска (server.py:3766-3768, 5145), глобальный возврат в finally do_POST (server.py:4816-4820), превышение — delivery_budget 502 (server.py:4433-4441); TestUtf8DeliveryBudget — зелёные.
   SUB 4/коалесинг: PASS — группа ≤40 мс, немедленный сброс буфера при fail-close-виде (server.py:3873-3890), разделитель сообщений один раз на границе mid (server.py:3902-3907).
   SUB 4/AD-003-механизм: PASS (примечание) — фактическая реализация проще PROPOSED-части AD-003 (нет отдельного request-scoped writer thread, 1024-лимит считается по raw-дельтам, нет 8192 control slot и 16 MiB ingress; write deadline 3с строже предложенных 5с), но инварианты (bounded, неблокирующий RPC-producer, fail-close на overflow, release независимо от писателя) выполнены; рекомендация: ратифицировать фактический механизм поправкой к packet'у либо вынести worker-thread отдельным срезом (числа AD-003 уже открыты в ASM-004/Q-004).

5. ТЕСТИРУЕМОСТЬ: VERDICT=PASS
   WHY=Набор полный для всех четырёх замечаний, прогон детерминированный: я запустил целевые 100 тестов заново — Ran 100 tests in 41.685s, OK; 32 теста в live-файле и 4 парные регрессии парсера — часть прогона.
   SUB 5/набор и прогон: PASS — tests/test_live_stream.py: 32 теста / 17 классов (tests/test_live_stream.py:98-969); независимый прогон 5 файлов: 100 OK.
   SUB 5/покрытие замечаний: PASS — F-203: TestClientWriteDeadSuppressesTerminalFrames (tests/test_live_stream.py:706); F-208: TestRunQueueLiveOnlyLimit (:934) и TestNonStreamBurstBeyondQueueLimit (:969); F-211: TestLiveFailureEnvelopeAfterPrefix (:788), TestDoneKindHonorsLiveInvalidation (:899); плюс тайминговый TestIncrementalDelivery (:98).
   SUB 5/тайминги: PASS (примечание) — часть тестов опирается на реальные паузы и допуски (0.2с на опережение финала, elapsed<8с, паузы 0.3-0.5с); на загруженной машине возможна нестабильность, мой прогон стабилен; барьеры/маркеры снизят риск (не блокер).

6. СООТВЕТСТВИЕ АРХИТЕКТУРЕ: VERDICT=PASS
   WHY=Поведенческие требования AD-001..AD-004 выполнены, другие адаптеры и non-stream контракты не затронуты; единственное расхождение — упрощённый механизм PROPOSED-части AD-003 (см. примечание), что не меняет наблюдаемый контракт и уже принято панелью R2.
   SUB 6/AD-001 wire: PASS — конверт 1:1 с примером packet'а (server.py:5093-5116: object chat.completion.chunk, delta {}, finish_reason null, error type stream_error/code live_prefix_invalidated/param null), затем [DONE]; успешных finish/usage после ошибки нет (server.py:5245-5252, 5257).
   SUB 6/AD-002 изоляция: PASS — strict только Droid stream+sink (server.py:3801-3805); muse не тронут (патч меняет только adapters/droid_adapter.py:83 — проброс sink; adapters/muse_adapter.py:518-535 sink игнорирует, поведение прежнее).
   SUB 6/AD-004 изоляция usage: PASS — null-finish usage только у live droid (server.py:5184, 5232); muse сохраняет прежний finish_reason в usage-кадре (TestUsageFinishReasonByBackend).
   SUB 6/non-stream и прочие контракты: PASS — _serve_json не изменён, sink=None-путь прежний (server.py:3434-3440, 4287), ADAPTER_API=1 и fleet/schema не затрагиваются патчем.
   SUB 6/AD-003: PASS (примечание, см. критерий 4) — инварианты соблюдены, механизм упрощён относительно PROPOSED-секции; рекомендую поправку к packet'у или отдельный срез на worker-thread.

ОБЩИЙ ВЕРДИКТ: ACCEPT

Независимая верификация артефакта (мои факты, не пересказ брифа):
- SHA-256 патча совпал с манифестом: ee2da4f64befd741a513be9f257c63ac14d1662c4aa76f7d71c84d36ce45f794.
- Рабочее дерево соответствует патчу (git diff --stat: server.py +557, tests/test_live_stream.py +994 новый, tests/test_tool_parser.py +77, core/tool_emulation.py +23, adapters/droid_adapter.py +1, tests/fake_droid.py +14).
- Прогон: .venv/bin/python -m unittest tests/test_live_stream.py tests/test_tool_parser.py tests/test_cache_usage.py tests/test_rpc_core.py tests/test_bridge_http.py — Ran 100 tests in 41.685s, OK.
- Линт: .venv/bin/ruff check по шести файлам патча — All checks passed (exit 0).
- Не прогонял: basedpyright (в брифе Раунда 3 не заявлен) и живой DSH-прогон VER-008/009/012 — это runtime-гейт владельца, вне R3-панели.
- Примечание к рабочему дереву: присутствует не относящееся к артефакту изменение fleet.json (его нет ни в diff.patch, ни в diff-r2.patch, ни в diff-r3.patch) — на ревью и на прогон тестов не влияет.
> PANEL-NONCE: 8d610b4c7d17aad9
> ARTIFACT-SHA256: 2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb
>
> Канон `~/Мой диск/Context/AGENTS.md` прочитан до `<!-- КАНОН-КОНЕЦ -->`. В рабочей папке `AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md` отсутствуют; профильные правила прочитаны из пакета. SHA-256 трёх файлов кандидата совпали с манифестом. Тесты самостоятельно не запускались.
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=Решение существенно улучшает наблюдаемость долгих агентных ходов: настоящий поток дельт заменяет ожидание завершённого блока, сохраняя клиентский API. Однако барьер исполнения ещё допускает смену транспорта после подтверждённого начала генерации; legacy SSE неправильно учитывает watchdog в Circuit Breaker.
>
>    SUB Корректность/логика: FAIL — watchdog обрабатывается после `attempt_done`, который не учитывает причину watchdog (bridges/opencode-zen-bridge/server.py:6772).
>    SUB Корректность/граничные условия: FAIL — execution-событие без prompt-заголовков не устанавливает барьер доставки (bridges/opencode-zen-bridge/server.py:3345).
>    SUB Корректность/обработка ошибок: FAIL — исчерпанный watchdog JSON-пути превращается в `provider_fatal` (bridges/opencode-zen-bridge/server.py:7516).
>
>    СОВЕТЫ (при FAIL):
>
>    - Включить подтверждённое execution-событие в монотонный барьер запроса.
>    - Классифицировать watchdog до обновления breaker.
>    - Передавать точную причину watchdog в финальный `O-EXIT`.
>
>    F-001 [pre-existing]
>    priority: blocking
>    locations: `bridges/opencode-zen-bridge/server.py:3345`, `bridges/opencode-zen-bridge/server.py:3683`.
>    rule: `FALLBACK_DECISION_TABLE`, запрет fallback после valid execution SSE; REQ-009.
>    evidence: `_is_delivered()` учитывает только `headers_at`, тексты, reasoning и native calls. Получение `session.execution.started` устанавливает `first_event_at`, но не барьер. Если prompt-заголовки ещё не пришли, а SSE затем закрывается, результат может остаться `delivered=False`, разрешая переход в `run` после уже начавшегося исполнения.
>    исправление: включить валидное событие выполнения своей сессии в барьер; сохранять его между попытками в SSE и JSON.
>    проверка: FakeServe задерживает prompt-заголовки, отправляет execution.started своей сессии и закрывает SSE; `Run.execute` и `_spawn_with_stdin` не вызываются, допустимы только serve-retry либо ошибка.
>
>    F-002 [pre-existing]
>    priority: blocking
>    locations: `bridges/opencode-zen-bridge/server.py:6772`, `bridges/opencode-zen-bridge/server.py:6776`, `bridges/opencode-zen-bridge/server.py:6779`.
>    rule: REQ-009; `R-BULK-I3`, сохранение Circuit Breaker.
>    evidence: `transient_failure` вычисляется без `watchdog_state["reason"]`. Убитый watchdog процесс имеет отрицательный rc и не считается retryable CLI failure. При отсутствии вывода breaker не получает failure; после частичного вывода `attempt_done(False, True)` может зарегистрировать успех. Затем отдельная ветка всё равно повторяет запрос по watchdog.
>    исправление: включить watchdog в транзиентный исход до единственного вызова `attempt_done`; исключить success для такой попытки.
>    проверка: для трёх watchdog-причин, с выводом и без него, проверить инкремент failure, отсутствие success и открытие breaker после заданного числа отказов.
>
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=Матрицы recovery и fault injection значительно усилены. Основные исправления подтверждены независимым L2, однако точная диагностика нового JSON-watchdog не доходит до финального sink; стартовые фазовые бюджеты закрыты частично.
>
>    SUB Полнота/покрытие AC: FAIL — AC-021 формально имеет поля, но терминальная причина JSON-watchdog неверна; это видно в сыром логе (execution-evidence.md, `VER-002-unittest`, 09:47:32–09:47:36).
>    SUB Полнота/пропущенные ветки: FAIL — проверены короткие общие дедлайны, но отсутствует оракул отдельного startup-бюджета при длинном общем deadline (bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2278).
>
>    СОВЕТЫ (при FAIL):
>
>    - Проверять финальную строку `O-EXIT/v1`, включая точную причину и измеренные времена.
>    - Добавить сценарий капающих стартовых заголовков с длинным общим deadline.
>    - Сохранить уже закрытые regression-оракулы.
>
>    F-003
>    priority: blocking
>    locations: `bridges/opencode-zen-bridge/server.py:5486`, `bridges/opencode-zen-bridge/server.py:5505`, `bridges/opencode-zen-bridge/server.py:7516`.
>    rule: REQ-016, AC-021; `O-EXIT/v1`, точная машиночитаемая причина отказа.
>    evidence: watchdog устанавливает `fatal_error=True`, после чего JSON-handler записывает `exit_reason="provider_fatal"`. Сырой clean-room лог подтверждает это для `first_event_timeout`, `first_token_timeout`, `stall_timeout`. Измеренные `first_event_at`/`first_token_at` также не возвращаются в handler: итоговые поля остаются `None`.
>    исправление: передать времена и терминальное состояние из `Run` в handler; обработать watchdog до общего provider-fatal пути.
>    проверка: пройти реальный HTTP JSON-handler до логового sink; получить ровно одну строку `O-EXIT/v1` с соответствующей watchdog-причиной и корректными временами наступивших событий.
>
>    Verify-Fixed:
>
>    - RW-001: PASS для заявленных случаев «prompt headers → SSE error / общий timeout»; F-001 фиксирует отдельную незакрытую границу.
>    - RW-002: PASS — нижний предел 120 с удалён, regression-оракул есть.
>    - RW-003: PASS для остановки и повторов трёх фаз JSON/run; F-003 — дефект передачи результата.
>    - RW-004: PASS — пять serve-сценариев AC-016 и сравнение serve/run для AC-017 включены в traceability.
>    - RW-005: FAIL частично — общий deadline и отмена проброшены, собственный абсолютный бюджет startup HTTP-фазы не обеспечен; F-004.
>    - RW-006: PASS — ранний побайтовый дренаж stderr и предел 16 КиБ подтверждены сценарием 2 МиБ без LF.
>    - RW-007: PASS — абсолютный cleanup-deadline, `skip_body` и обязательный `lease.cleanup`.
>    - FU-001: PASS — пределы SSE-строки и HTTP-тела реализованы.
>    - FU-002: PASS для отрицательных и boolean token counts.
>    - FU-003: PASS — сквозной cleanup-оракул проверяет исчезновение группы за установленный бюджет.
>
>    Поштучная сверка требований:
>
>    - REQ-001: PASS — дельты доставляются инкрементально.
>    - REQ-002: PASS — публичные маршруты и форма ответов сохранены.
>    - REQ-003: PASS — run, аварийный файл и выключенный по умолчанию serve сохранены.
>    - REQ-004: PASS для проверенных SSE-сценариев ожидания.
>    - REQ-005: PASS для проверенных модельных дельт, статусов и реплея.
>    - REQ-006: FAIL на стартовых HTTP-фазах до запуска основного watchdog; F-004.
>    - REQ-007: PASS для фаз после запуска транспорта.
>    - REQ-008: PASS по представленным сценариям отмены и cleanup.
>    - REQ-009: FAIL — F-001, F-002.
>    - REQ-010: PASS — используется существующий инкрементальный parser.
>    - REQ-011: PASS — recovery и terminal tool_calls покрыты матрицей.
>    - REQ-012: PASS по коду ask→reject/interrupt и представленным оракулам; реальная политика остаётся частью L3.
>    - REQ-013: PASS — общий limiter/gate/bulkhead и ротация сохранены.
>    - REQ-014: частично подтверждено; ранний native terminal может потерять фактический usage, F-005.
>    - REQ-015: PASS — случайный пароль, allowlist и маскирование.
>    - REQ-016: FAIL — F-003.
>    - REQ-017: PASS — полный и обратный порядок зелёные.
>    - REQ-018: PASS — frozen-срезы и Google-тесты подтверждены.
>    - REQ-019: DEFERRED_L3, допустимо до ACCEPT.
>    - REQ-020: PASS — сокетный оракул и свидетельство RED→GREEN присутствуют.
>
>    Поштучная сверка AC: AC-001 PASS; AC-002 PASS; AC-003 PASS; AC-004 PASS; AC-005 PASS; AC-006 PASS на представленных фикстурах; AC-007 PASS; AC-008 частично, F-004; AC-009 PASS; AC-010 PASS; AC-011 PASS; AC-012 PASS на синтетическом сценарии, живое подтверждение DEFERRED_L3; AC-013 PASS; AC-014 PASS на проверенных recovery-ветках; AC-015 PASS; AC-016 PASS; AC-017 PASS; AC-018 PASS по проверкам ротации; AC-019 PASS для step-ended фикстуры, ограничение F-005; AC-020 PASS по представленному оракулу; AC-021 FAIL; AC-022 PASS; AC-023 PASS; AC-024 PASS; AC-025 DEFERRED_L3; AC-026 PASS.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
>    WHY=Короткоживущий serve сохраняет ротацию IP и изолирует отказы запросов; `:memory:` устраняет зависимость от большой SQLite-базы. Масштаб соответствует локальному мосту с ограниченным параллелизмом. Но старт всё ещё может занимать общий 1800-секундный бюджет вместо собственного окна фазы.
>
>    SUB Реализуемость/общее: FAIL — readiness/create/subscribe защищены общим deadline, но не собственным абсолютным пределом (bridges/opencode-zen-bridge/server.py:3375).
>
>    СОВЕТЫ (при FAIL):
>
>    - Вычислять абсолютный deadline каждой стартовой фазы.
>    - Ограничивать его остатком общего бюджета.
>    - Делить один фазовый бюджет между повторами управляющего вызова.
>    - Проверить капающие заголовки при длинном общем deadline.
>
>    F-004
>    priority: blocking
>    locations: `bridges/opencode-zen-bridge/server.py:3171`, `bridges/opencode-zen-bridge/server.py:3375`, `bridges/opencode-zen-bridge/server.py:3391`, `bridges/opencode-zen-bridge/server.py:3394`.
>    rule: RW-005; `feature.md` §2, `R-BULK-I1`, ограничение каждого I/O-шага собственным бюджетом и остатком deadline.
>    evidence: watcher подписки получает общий `deadline`; `_ctrl_http` передаёт `attempt_deadline`. `ready_deadline=now+3` проверяется только после возврата/ошибки `_ctrl_http`. Если заголовки поступают по байту быстрее socket timeout, readiness/create могут ждать до общего deadline; аналогично подписка обходит собственный first-event-порог. Основной watchdog начинается после этих операций.
>    исправление: передавать в watcher и HTTP-вызов `min(request_deadline, phase_started + phase_budget)`; readiness-повторы должны использовать общий для них фазовый deadline.
>    проверка: при общем deadline 30–60 с и фазовом бюджете 0,3 с peer капает корректные заголовки каждые 0,02 с; readiness/create/subscribe завершаются по фазовому бюджету с cleanup и корректной классификацией. Существующие тесты с общим deadline 0,9 с этот случай не различают.
>
> 4. РИСКИ: VERDICT=FAIL
>    WHY=Clean-room доказательства убедительны: 466 тестов компонента, 894 корневых теста, обратный порядок, статические проверки и frozen-хеши. Основной остаточный риск — усиление отказов из-за неверного breaker-учёта и повторное исполнение после допустимого execution-события. Зелёный набор этих веток не проверяет.
>
>    SUB Риски/безопасность: PASS — Basic-пароль генерируется через secrets, окружение ограничено, ошибки маскируются (bridges/opencode-zen-bridge/server.py:1830; REQ-015).
>    SUB Риски/данные: FAIL — смена транспорта после execution.started допускает повторное исполнение; F-001 (bridges/opencode-zen-bridge/server.py:3345).
>    SUB Риски/прод: FAIL — legacy SSE watchdog способен сбросить breaker как успешная попытка; F-002 (bridges/opencode-zen-bridge/server.py:6776).
>    SUB Риски/regression red→green: PASS — независимый RED rc=1 и GREEN rc=0 представлены (execution-evidence.md, `L2-RED-sensitivity`, `VER-005-dedicated-realtime-suite`).
>    SUB Риски/Full Suite (L2): PASS — 466 passed; корневой suite 894 passed, 5 skipped; обратный порядок 466 passed (execution-evidence.md, `VER-001`, `VER-003`, `AC-023`).
>    SUB Риски/scope-diff: PASS — ровно три разрешённых файла, frozen-функции совпали, зависимостей не добавлено (candidate-manifest.json; `VER-004-packet-command`).
>
>    СОВЕТЫ (при FAIL):
>
>    - Закрыть F-001..F-004 и добавить различающие поведенческие оракулы.
>    - Повторить L2 на новом кандидате.
>    - После ACCEPT выполнить предусмотренный L3 на реальном DSH, включая рабочий размер промпта, параллельные вызовы и отключение клиента.
>
>    F-005 [pre-existing]
>    priority: non-blocking
>    locations: `bridges/opencode-zen-bridge/server.py:3745`, `bridges/opencode-zen-bridge/server.py:3753`.
>    rule: REQ-014 / AC-019, сохранение фактического usage.
>    evidence: готовый native call при `emulate_tools=True` завершает попытку до последующего `session.step.ended`; фактические токены этого шага могут не попасть в результат, и ответ использует оценку.
>    исправление: ограниченно дождаться usage завершаемого шага либо явно сохранить признак оценочного usage; не допускать следующего модельного шага.
>    проверка: native called → step.ended с известными токенами; итоговый usage равен фикстуре и учитывается один раз. Приоритет non-blocking, поскольку REQ-014 имеет SHOULD.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=Выбор serve с резервным run оправдан подтверждённой невозможностью получить дельты из установленного run. Общий демон осложнил бы ротацию IP, прямой Zen HTTP не имеет подтверждённого рабочего пути авторизации. Исправление найденных дефектов возможно локально; переписывание транспортной архитектуры не требуется.
>
>    SUB Альтернативы/общее: PASS — A1 с fallback решает RC-1..RC-3 при сохранении существующих ограничителей; более дешёвый legacy-only вариант не даёт реалтайма (handoff-architect.md §4; F-17..F-25).
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Решение остаётся внутри автономного stdlib-моста. Новые Litestar/SQLAlchemy-слои и runtime-зависимости здесь не нужны. Изоляция транспорта открывает путь к дальнейшему развитию без изменения DSH, но не доказывает рост пропускной способности: ресурсная модель остаётся «процесс serve на попытку».
>
>    SUB Соответствие контексту/общее: PASS — разрешённый файловый конверт соблюдён, публичные границы и замороженные маршруты сохранены (candidate-manifest.json; scope-and-contracts.md §1–2; `VER-004`).
>
>    Non-Goals проверены поштучно: HTTP/порт/SSE — сохранены; DSH/профиль/ReasoningRow — не изменены; модельное reasoning ради превью не переписывается; модель/effort/каталог — не заменены; другие мосты и общие конфиги — не изменены; внешние runtime-зависимости — отсутствуют.
>
>    Forbidden Scope проверен поштучно: файлов вне конверта нет; записанных реальных секретов не обнаружено; боевой rollout отложен; запрещённого keychain-вызова нет; общая БД напрямую не изменяется; коммита в target и merge пакет не заявляет.
>
>    Независимая сверка: SEED=`f24bed3a`; seed_hex=`f24bed3aa414cb2b8ce5ca1bc587e03cf4d458ef3a96b860d3b6caa29e7753db`; ranked_order=`gpt-6.1-sol-high → grok-4.7-high → claude-sonnet-5-5-high → muse-wonder-full-1.0 → gemini-4-argon-high` — полностью совпадает с манифестом по алгоритму `select_round_seats.py`.
>
>    Self-sweep выполнен по всем 14 подкатегориям. Отсроченные VER-006/VER-007 не использованы как основание FAIL. Межцикловая git-дельта отдельно не приложена; точную атрибуцию новых замечаний в `late_miss` должен подтвердить оркестратор.
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
> COVERAGE: 14/14 подкатегорий
> FINDINGS_COMPLETE: 5

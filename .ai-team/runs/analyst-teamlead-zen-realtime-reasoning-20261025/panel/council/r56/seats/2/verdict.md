PANEL-NONCE: 56b00e2947af04e8
ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 закрыт для HTTP-ошибок prompt, но остался обход через ошибку выполнения из SSE: полученные заголовки не сохраняются в `delivered`, после чего разрешается переход на `run`. Также legacy SSE принудительно увеличивает настроенный first-token timeout до 120 секунд.

   СОВЕТЫ (при FAIL): сохранять барьер доставки независимо от способа завершения попытки; различать получение заголовков и выдачу модельного текста при выборе recovery; убрать нижнюю границу 120 секунд; добавить регрессионные сценарии F-001 и F-002.

   SUB Корректность/логика: FAIL — после принятых заголовков SSE-ошибка может разрешить повтор через другой транспорт (`server.py:3552`, `server.py:5619`, `server.py:6911`; RW-001).
   SUB Корректность/граничные условия: FAIL — значение FIRST_TOKEN_TIMEOUT_S меньше 120 секунд не соблюдается на legacy SSE (`server.py:6235`; REQ-007).
   SUB Корректность/обработка ошибок: FAIL — ветка `etype == "error"` не переносит подтверждение доставки prompt в результат (`server.py:3553`; FALLBACK_DECISION_TABLE).

2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-002, RW-003 и RW-004 принимаются по коду и включённым в зелёный L2 регрессионным тестам. Однако legacy JSON получил только проверку отключения клиента, без трёх требуемых watchdog. Свидетельство AC-016 также неполно: существующие сценарии step interruption исполняются через fake-CLI legacy-пути, а не все повторены на serve. Отдельного сравнительного сценария AC-017 для unmapped recovery нового транспорта в пакете нет.

   СОВЕТЫ (при FAIL): добавить watchdog в JSON-путь `Run`; обеспечить одинаковую классификацию таймаутов в SSE и JSON; прогнать существующую матрицу step interruption на обоих транспортах; добавить serve-сценарий unmapped → повтор → итоговый `finish_reason`.

   SUB Полнота/покрытие AC: FAIL — AC-016 и AC-017 не подтверждены требуемой матрицей нового транспорта (`tests/test_step_interruption.py:171`, `server.py:1911`; F-004).
   SUB Полнота/пропущенные ветки: FAIL — JSON legacy контролирует client_gone, но не first-event/first-token/stall (`server.py:5094`; REQ-006, REQ-007).

   Verify-Fixed:

   - RW-001 — **FAIL, частично исправлен**: HTTP 200 + обрыв тела и HTTP 429/503 покрыты; SSE execution failure после заголовков остаётся F-001.
   - RW-002 — **PASS**: защитный таймер сохраняется; тест задержки лимитера на 0,5 секунды проверяет единственный статус до секунды (`server.py:5964`; `tests/test_realtime_reasoning.py:504`).
   - RW-003 — **PASS** для трёх заданных recovery-веток и thinking on/off (`tests/test_realtime_reasoning.py:526`).
   - RW-004 — **PASS**: native input delta и готовый вызов обновляют активность (`server.py:3502`, `server.py:3512`; тест `:1826`).
   - FU-001 — **PASS**, совместно с RW-003.
   - FU-002 — **PASS**: статус публикуется из callback заголовков; зависшее тело 401 покрыто тестом `:1836`.
   - FU-003 — **PASS** для указанного частичного tool-блока и дедупликации преамбулы, тест `:1339`.
   - FU-004 — **PASS**: независимые времена отправки и получения каждой дельты, тест `:682`.
   - FU-005 — **PARTIAL**: HTTP-ветки используют RetryBudget; обход F-001 сохраняется.
   - FU-006 — **PARTIAL**: cleanup получил аргументы deadline, но старт их не получает, а блокирующие HTTP-фазы не обеспечивают жёсткий абсолютный предел — F-005, F-007.
   - FU-007 — **принято в backlog**, переписывание unittest в этом цикле не требуется.

   Поштучная сверка требований и AC:

   - REQ-001 — PASS; AC-001 — PASS; AC-002 — PASS: socket oracle с независимыми timestamp, тест `:682`, VER-005.
   - REQ-002 — PASS; AC-003 — PASS: публичные пути и формат сохранены; существующие проверки зелёные.
   - REQ-003 — PASS; AC-004 — PASS: выключенный serve сохраняет legacy; полный компонентный набор — 451 passed.
   - REQ-004 — PASS в заявленном окне после открытия SSE; AC-005 — PASS для проверенных задержек gate/limiter, тест `:504`.
   - REQ-005 — PASS на представленных оракулах; AC-006 — PASS; AC-007 — PASS: модельные дельты сверяются, reasoning истории исключён, тесты `:682`, `:572`.
   - REQ-006 — FAIL; AC-008 — FAIL для legacy JSON, F-003.
   - REQ-007 — FAIL; AC-009 — FAIL для legacy JSON; AC-010 — FAIL для legacy JSON и настроек legacy SSE ниже 120 секунд, F-002/F-003.
   - REQ-008 — FAIL по границам стартовых и cleanup-фаз; AC-011 — FAIL; AC-012 — FAIL для этих сценариев, F-005/F-007.
   - REQ-009 — FAIL по сохранению delivery/retry-инварианта, F-001; AC-013 — PASS по общему потолку; AC-014 — PASS на проверенной матрице разделителей.
   - REQ-010 — PASS; AC-015 — PASS: существующий parser и новые разрезанные tool-дельты, тест `:793`, полный L2.
   - REQ-011 — INCONCLUSIVE в полном объёме; AC-016 — FAIL по полноте проверки serve, F-004.
   - REQ-012 — INCONCLUSIVE по требуемой эквивалентности unmapped recovery; AC-017 — FAIL по доказательству, F-004. Наличие ask/reject обработки подтверждено.
   - REQ-013 — PASS по коду сохранённой ротации и защит; AC-018 — PASS по композиции frozen `_run_env` и проверке одного обращения к пулу на попытку.
   - REQ-014 — PASS; AC-019 — PASS по отображению полей usage и проверке суммирования попыток.
   - REQ-015 — PASS на проверенных каналах; AC-020 — PASS: маскирование SSE/JSON/log, тест `:1388`.
   - REQ-016 — PASS; AC-021 — PASS: обязательные поля присутствуют в реальных строках O-EXIT приложенного L2.
   - REQ-017 — PASS; AC-022 — PASS; AC-023 — PASS: полный и обратный порядок — 451 passed.
   - REQ-018 — PASS; AC-024 — PASS: frozen SHA и неизменённый Google-набор подтверждены VER-004.
   - REQ-019 — DEFERRED_L3; AC-025 — DEFERRED_L3: законная отсрочка до ACCEPT.
   - REQ-020 — PASS; AC-026 — PASS на кандидате: проверяется получение дельт до завершения FakeServe; baseline sensitivity имеет rc=1.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Выбранный транспорт технически осуществим на подтверждённом окружении: Python stdlib, установленный opencode v2.1.2, POSIX process groups, ps/lsof. In-memory DB устраняет зависимость попытки от общей SQLite. Но rollout пока блокируют неполная отмена старта и взаимная блокировка диагностических пайпов при большом стартовом выводе.

   СОВЕТЫ (при FAIL): передавать deadline и отмену через весь startup; проверять остаток бюджета до запуска helper; запускать stderr-дренаж сразу после Popen; добавить fault injection на отмену setup и многомегабайтный stderr до открытия порта.

   SUB Реализуемость/общее: FAIL — старт не получает общий deadline/cancellation, а дренаж stderr начинается только после появления listener (`server.py:2731`, `server.py:2844`; F-005/F-006).

   Практическая оценка оставшейся работы — примерно **2–3 инженерных дня** на исправления и расширение матрицы проверок, затем живой rollout. Это оценка, а не подтверждённый срок. Для L3 нужны существующий чат DSH, доступный upstream и проверка пикового RSS при шести параллельных запросах: измеренный idle RSS не доказывает рабочий максимум.

4. РИСКИ: VERDICT=FAIL
   WHY=Clean-room свидетельства достаточны для признания выполненных прогонов зелёными: компонентный pytest/unittest — 451 тест, корневой pytest — 894 passed и 5 skipped, статический гейт — 0 ошибок типов. Однако эти результаты не покрывают найденные сценарии. Особенно существенно, что cleanup может задержать killpg: deadline проверяется между блокирующими HTTP-операциями, которые сами могут удерживаться капающим ответом.

   СОВЕТЫ (при FAIL): обеспечить прерывание HTTP-фазы по абсолютному deadline; для cleanup не ждать ненужное тело ответа; добавить капающие заголовки/chunk framing и проверить освобождение группы/слота; дополнить тесты F-001..F-006. VER-006/VER-007 выполнять после ACCEPT; их законная отсрочка сама по себе не является замечанием.

   SUB Риски/безопасность: PASS — случайный пароль, loopback Basic auth, allowlist окружения и маскирование проверены (`server.py:1848`; тест `:1388`; REQ-015).
   SUB Риски/данные: PASS — проверены отображение usage, суммирование попыток и дедупликация JSON tool calls (`tests/test_realtime_reasoning.py:1106`; VER-005).
   SUB Риски/прод: FAIL — startup и cleanup имеют сценарии превышения бюджета и удержания ресурсов (`server.py:2604`, `server.py:2610`, `server.py:2799`; F-005/F-007).
   SUB Риски/regression red→green: PASS — baseline sensitivity rc=1 и кандидат 72 passed подтверждены execution-evidence; это не заменяет недостающие оракулы F-004.
   SUB Риски/Full Suite (L2): PASS — компонентные 451 passed, корневые 894 passed, обратный порядок 451 passed (`execution-evidence.md`, VER-001/002/003, AC-023).
   SUB Риски/scope-diff: PASS — ровно три разрешённых файла, frozen функции совпадают (`candidate-manifest.json`; VER-004).

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve с общей системой бюджетов и legacy kill-switch оправдан подтверждённой недоступностью дельт в `opencode run`. Прямой Zen HTTP остаётся недоказанным вариантом, а общий демон усложняет сохранение ротации IP. Найденные дефекты исправляются внутри выбранной схемы; оснований требовать новую архитектуру или переписывание моста нет.

   SUB Альтернативы/общее: PASS — A1 сохраняет ротацию и использует проверенный SSE API; исправления локальны (`handoff-architect.md` §4; F-17..F-25).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Границы автономного stdlib-моста соблюдены, но требования сквозных deadline и проверки всех recovery-сценариев выполнены не полностью. Это конкретные нарушения feature.md и приёмочных критериев, а не претензия к стилю или требование перенести мост на Litestar.

   СОВЕТЫ (при FAIL): закрыть F-004/F-005/F-007 поведенческими оракулами; исправить прослеживаемость, чтобы PASS не опирался на тесты другого транспорта; повторить полный clean-room L2 после исправлений.

   SUB Соответствие контексту/общее: FAIL — остаточный deadline не передан в startup, cleanup не имеет гарантированного абсолютного предела (`server.py:3101`, `server.py:2604`, `server.py:2610`; feature.md §2, R-BULK-I1).

   Non-Goals проверены поштучно: HTTP-контракт — PASS; отсутствие правок DSH/профиля — PASS; отсутствие новой переработки reasoning ради превью — PASS; сохранение моделей/effort — PASS; отсутствие правок других мостов и общих конфигов — PASS; отсутствие внешних runtime-зависимостей — PASS.

   Forbidden Scope проверен по пакету: файловый allowlist — PASS; отсутствие реальных секретов в diff — PASS; отсутствие преждевременного rollout — PASS; запрещённая keychain-команда не использовалась в представленных командах — PASS; прямая правка общей opencode.db отсутствует — PASS; коммит/merge защищённых веток не заявлен — PASS.

Все замечания после повторного self-sweep:

**F-001 — остаток RW-001, priority=blocking**

- **locations:** `bridges/opencode-zen-bridge/server.py:3553`, `bridges/opencode-zen-bridge/server.py:5564`, `bridges/opencode-zen-bridge/server.py:5619`, `bridges/opencode-zen-bridge/server.py:6846`, `bridges/opencode-zen-bridge/server.py:6911`.
- **Правило:** RW-001, FALLBACK_DECISION_TABLE/DELIVERED, REQ-009.
- **Evidence:** ветка SSE ошибки устанавливает `error`, `transient_error`, `terminal="failed"` и выходит, сохранив исходное `delivered=False`. При HTTP 200 headers, затем `session.execution.failed` с transient error до токенов оба внешних цикла разрешают fallback на `run`.
- **Исправление:** сохранять подтверждение доставки на всех выходах; отдельно учитывать наличие модельного вывода, чтобы headers-only transient failure корректно проходил serve-retry через общий бюджет.
- **Критерий проверки:** auto, SSE и JSON: prompt headers → transient SSE failure до токенов; `run` не вызывается, RetryBudget учитывается, успешного учёта нет.

**F-002 [pre-existing] — priority=blocking**

- **locations:** `bridges/opencode-zen-bridge/server.py:6235`.
- **Правило:** REQ-007, AC-010.
- **Evidence:** `max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` игнорирует заданные значения ниже 120 секунд, включая дефолтные 60.
- **Исправление:** применять настроенный порог без скрытого увеличения.
- **Критерий проверки:** legacy SSE получает служебное событие, затем молчит; first-token timeout срабатывает по заданному порогу и получает правильную классификацию.

**F-003 [pre-existing] — priority=blocking**

- **locations:** `bridges/opencode-zen-bridge/server.py:5094`, `bridges/opencode-zen-bridge/server.py:5104`, `bridges/opencode-zen-bridge/server.py:5118`.
- **Правило:** REQ-006, REQ-007; AC-008..AC-010.
- **Evidence:** JSON callback `on_idle` проверяет только `is_client_gone`; время первого события, первого токена и последнего токена здесь не отслеживается. Молчащий legacy JSON продолжает ждать общий TIMEOUT_S.
- **Исправление:** добавить три watchdog и их классификацию/учёт повторов в JSON legacy.
- **Критерий проверки:** `TRANSPORT=run`, `stream=false`: отсутствие событий, события без токенов и пауза после токена завершаются соответствующими timeout с остановкой группы.

**F-004 [pre-existing] — priority=blocking**

- **locations:** `bridges/opencode-zen-bridge/tests/test_step_interruption.py:171`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py:181`, `bridges/opencode-zen-bridge/server.py:1911`.
- **Правило:** AC-016, AC-017; testing.md — проверять требуемое поведение и полноту.
- **Evidence:** существующая матрица устанавливает shebang fake-CLI в OPENCODE_BIN; auto выбирает для него `run`. Новые serve-тесты покрывают отдельные сценарии, но не все сценарии существующей матрицы и не требуемое сравнение unmapped recovery.
- **Исправление:** параметризовать поведенческую матрицу транспортами либо добавить эквивалентную serve-матрицу без ослабления assertions.
- **Критерий проверки:** каждый сценарий AC-016 проверен на serve-дельтах; AC-017 сравнивает unmapped-повтор и итоговый finish_reason с legacy. В traceability приведены конкретные test IDs.

**F-005 [pre-existing] — priority=blocking**

- **locations:** `bridges/opencode-zen-bridge/server.py:2731`, `bridges/opencode-zen-bridge/server.py:2799`, `bridges/opencode-zen-bridge/server.py:2825`, `bridges/opencode-zen-bridge/server.py:3101`, `bridges/opencode-zen-bridge/server.py:3196`.
- **Правило:** FU-006; REQ-008; feature.md §2; R-BULK-I1.
- **Evidence:** `_spawn_serve` не принимает deadline/cancellation и создаёт самостоятельные окна ожидания. Подписка `/api/event` также использует отдельный timeout=5. Просроченный request deadline не запрещает предварительный запуск helper.
- **Исправление:** передавать остаток общего бюджета через startup и subscribe; проверять отмену между ожиданиями; cancellation/deadline не превращать в ServeUnavailable с последующим fallback.
- **Критерий проверки:** при истёкшем deadline helper не запускается; отмена на handshake/listener/subscribe обнаруживается в пределах REQ-008, процессы и слоты освобождаются.

**F-006 [pre-existing] — priority=blocking**

- **locations:** `bridges/opencode-zen-bridge/server.py:181`, `bridges/opencode-zen-bridge/server.py:2826`, `bridges/opencode-zen-bridge/server.py:2844`.
- **Правило:** управление ресурсами и независающий I/O, feature.md §2, T-LIFE/v1.
- **Evidence:** helper синхронно пересылает вывод serve в собственный stderr, но родитель начинает читать его только после проверки listener. Вывод до bind, превышающий суммарную ёмкость пайпов, блокирует helper и serve; listener не появляется.
- **Исправление:** запускать родительский stderr-дренаж сразу после Popen, до handshake/listener; хранить ограниченный объём диагностических байтов.
- **Критерий проверки:** fake serve пишет несколько MiB до открытия порта, включая вариант без LF; startup завершается, память ограничена, после cleanup нет оставшихся процессов и FD. Текущий тест на 70 KB эту границу не доказывает.

**F-007 [pre-existing] — priority=blocking**

- **locations:** `bridges/opencode-zen-bridge/server.py:2604`, `bridges/opencode-zen-bridge/server.py:2610`, `bridges/opencode-zen-bridge/server.py:3595`, `bridges/opencode-zen-bridge/server.py:3607`.
- **Правило:** FU-006; feature.md §2 — timeout на каждом шаге, включая cleanup; REQ-008.
- **Evidence:** deadline проверяется перед `getresponse()`/`read1()`. Чтение HTTP-заголовков и chunk framing внутри этих операций может выполнять несколько recv. Капающие байты чаще socket timeout удерживают операцию дольше абсолютного deadline; до `lease.cleanup()` исполнение не доходит.
- **Исправление:** обеспечить жёсткое прерывание текущей HTTP-фазы по deadline; в cleanup не читать ненужное тело ответа. Сохранить ограниченный путь к killpg независимо от поведения control API.
- **Критерий проверки:** interrupt/DELETE с капающими заголовками и chunked framing не удерживают cleanup за установленным бюджетом; группа исчезает в пределах AC-011, слот возвращается.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

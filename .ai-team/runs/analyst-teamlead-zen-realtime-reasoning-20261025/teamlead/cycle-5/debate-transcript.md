# Стенограмма дебатов Совета Тимлидов по коду — Cycle 5 (run `analyst-teamlead-zen-realtime-reasoning-20261025`)

## Раунд R1 (`panel/council/r56`)

### Seat 1 (`skeptic`, `muse-wonder-full-1.0`)

PANEL-NONCE: 05162baa598974a7
ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 закрыт не на всех путях выхода (F-001): SSE-ошибка `etype="error"` (server.py:3553) и общий `timeout` (server.py:3565) не переносят `prompt_status["headers_at"]` в `result["delivered"]`, поэтому в auto при transient-ошибке без модельного вывода возможен тихий fallback на `opencode run` и второй вызов Zen после уже принятого prompt (потребители — server.py:5614-5618 SSE и server.py:6888-6911 JSON). Отдельно legacy-путь игнорирует порог первого токена ниже 120 с (F-002, server.py:6235).
   СОВЕТЫ (при FAIL): 1) В `_serve_one_attempt` устанавливать `result["delivered"]=True` при `headers_at is not None` на ветках `error` и `timeout` (как сделано для `first_event_timeout` server.py:3309); 2) убрать `max(...,120.0)` в legacy `send_keepalive`, использовать ровно `FIRST_TOKEN_TIMEOUT_S`; 3) добавить регрессионные тесты: headers получены → SSE `session.execution.failed` (transient) без токенов и headers получены → deadline `timeout` — в обоих случаях ни в SSE, ни в JSON не вызываются `Run.execute`/`_spawn_with_stdin`, нет `record_success()`; legacy-тест с `FIRST_TOKEN_TIMEOUT_S=0.8` и служебными событиями без токенов даёт `first_token_timeout`, а не ожидание 120 с.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=Verify-fixed: RW-002 PASS (абсолютный `threading.Timer` первого статуса, оракул задержки лимитера 0.5 с), RW-003/FU-001 PASS (разделители watchdog/unmapped/incomplete только при thinking), RW-004 PASS (`last_token_at` при native-вызове), FU-002/FU-003/FU-004 PASS по оракулам coder.json и clean-room L2. Но RW-001 закрыт частично: ветки error/timeout после headers не покрыты оракулом (F-001), а AC-010 на legacy-пути при пороге 60 с фактически не выполняется (F-002); FU-006 подтверждён только наличием `deadline=`, оракула капающего cleanup-тела нет (F-005, coder.json прямо признаёт пробел).
   СОВЕТЫ (при FAIL): 1) Добавить оракулы из F-001/F-002 выше (обе ветки × SSE+JSON); 2) добавить оракул FU-006: interrupt/DELETE с медленно капающим телом ответа — суммарная уборка попытки и смерть группы укладываются в бюджет AC-011 (≤7 с); 3) после исправления прогнать полный L2 (VER-001/002/003) заново.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Clean-room L2 PASS: 451 passed на VER-001 pytest, VER-002 unittest, VER-003 root PYTHONPATH и reversed AC-023 (execution-evidence.md, code-gate.json status=PASS); 0 внешних зависимостей вне Python 3.14 stdlib; kill-switch через env/disable-файл/dynamic_config с дефолтом run. VER-006/007 законно DEFERRED_L3 до ACCEPT, блокером реализуемости не считаю.
4. РИСКИ: VERDICT=FAIL
   WHY=F-002 удваивает время немой деградации legacy-пути (120 с вместо конфигурируемых 60 с по REQ-007) до ретрая. F-001 создаёт риск двойного расхода квоты Zen и двойной генерации при уже принятом prompt. Дополнительно: неограниченный размер SSE-строки и тела управляющего ответа (F-003, server.py:3235,2613), неполная валидация usage (F-004, server.py:1949: `cache.read` принимает bool как int, отрицательные токены не отсекаются), худший случай cleanup может превысить 7 с AC-011 (F-005: join 2×0.5 с на server.py:3584 + два последовательных deadline по 0.35 с на server.py:3595,3607 до lease.cleanup с окнами 4+2 с). Секреты, permission reject, allowlist окружения и маскирование ошибок замечаний не вызвали.
   СОВЕТЫ (при FAIL): 1) Исправить F-001/F-002 (blocking, см. п.1); 2) ограничить размер одной SSE-строки (`readline(limit)`) и тела `_serve_http` именованной константой с протокольной ошибкой при превышении; 3) в `_map_serve_event` отсекать bool и отрицательные значения для всех токенов включая `cache.read`; 4) начинать `lease.cleanup()` (закрытие lifeline/SIGTERM) до или параллельно HTTP interrupt/DELETE либо доказать тестом суммарный бюджет ≤7 с в худшем случае.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбранный гибрид A1+fallback соответствует прецеденту muse-bridge (F-40,F-41) и факт-карте (run дельт не даёт F-17/F-18, serve даёт F-19); более дешёвый путь L реалтайм не закрывает (RC-1). Неоправданного переписывания без необходимости не вижу; массовое переформатирование legacy в diff — non-blocking замечание к ревьюируемости, при замороженных срезах и зелёном Full Suite FAIL по этому критерию на цикле 5 не ставлю.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Ровно 3 файла из конверта (candidate-manifest.json), замороженные `_run_env`/`_stream_google_sse`/`_execute_google_once` побайтно совпали (code-gate.json `google_direct_unchanged=True`, sha проверены гейтом), публичный контракт /health, /v1/models, /v1/chat/completions и SSE-форма сохранены, чужих KEY и файлов вне bridges/opencode-zen-bridge в diff нет. Стиль unittest в новом модуле расходится с testing.md, но FU-007 Советом прошлого цикла сознательно оставлен non-blocking, а обязательный гейт VER-002 — unittest discover; FAIL не ставлю.

SUB Корректность/логика: FAIL — F-001 (server.py:3553,3565, правило RW-001/FALLBACK_DECISION_TABLE DELIVERED), F-002 (server.py:6235, REQ-007)
SUB Корректность/граничные условия: FAIL — server.py:6235 `max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` против REQ-007/AC-010 (порог 60 с, env-настраиваемый)
SUB Корректность/обработка ошибок: FAIL — server.py:3553-3556 ветка `etype=="error"` не ставит `result["delivered"]` при полученном `headers_at` (server.py:3266)
SUB Полнота/покрытие AC: FAIL — AC-010 на legacy не выполняется при дефолте 60 с (server.py:6235); остальные AC подтверждены verification-traceability.md PASS
SUB Полнота/пропущенные ветки: FAIL — error/timeout после prompt headers без модельного вывода не покрыты оракулом (reverse-spec.md §4.5 п.2; server.py:5618,6911)
SUB Реализуемость/общее: PASS — code-gate.json status=PASS, VER-001..005 и AC-023 rc=0, 451 passed (execution-evidence.md)
SUB Риски/безопасность: PASS — _serve_env allowlist + OPENCODE_DB=":memory:" + случайный пароль (server.py, _SERVE_ALLOWLIST), _error_payload/_mask_secrets маскирование, permission reject+interrupt, нет хардкода секретов в diff
SUB Риски/данные: FAIL — F-004 server.py:1949 `isinstance(read_obj, int)` пропускает bool; отрицательные tokens.* не отсекаются (_map_serve_event)
SUB Риски/прод: FAIL — F-003 server.py:3235 `sse_resp.readline()` без лимита и server.py:2613 `raw.extend(chunk)` без потолка тела; F-005 худший cleanup >7 с (server.py:3584,3595,3607)
SUB Риски/regression red→green: PASS — code-gate.json red_sensitivity_rc=1 на origin/dev, кандидат 451 passed; оракулы test_c5_* в tests/test_realtime_reasoning.py
SUB Риски/Full Suite (L2): PASS — VER-001 pytest (451), VER-002 unittest, VER-003 root, reversed — все rc=0 (execution-evidence.md)
SUB Риски/scope-diff: PASS — candidate-manifest.json: ровно 3 файла coder_target_files, frozen-slice sha256 MATCH, 0 новых внешних зависимостей
SUB Альтернативы/общее: PASS — вариант C (serve+fallback) обоснован F-17..F-19 и прецедентом muse-bridge F-40; L не закрывает RC-1
SUB Соответствие контексту/общее: PASS — REQ-002 публичный контракт сохранён, REQ-018 Google-direct не тронут (google_direct_unchanged=True), Forbidden Scope не нарушен

F-001 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:3553, server.py:3565 (корень), server.py:5614-5618, server.py:6888-6911 (потребители) | правило=RW-001 (headers_at включается в delivered на всех путях выхода), FALLBACK_DECISION_TABLE phase=DELIVERED, REQ-009 | evidence=`elif etype == "error": result["error"] = payload; result["transient_error"] = ...; break` — без `result["delivered"] = bool(prompt_status.get("headers_at"))`, в отличие от server.py:3309; та же недостановка на `result["exit_reason"] = "timeout"` | исправление=ставить delivered из headers_at на ветках error и timeout | проверка=новый тест в auto: prompt headers 200 получены, затем transient SSE-error без токенов (и отдельно deadline-timeout) — Run.execute/_spawn_with_stdin не вызваны ни в SSE, ни в JSON, record_success не вызван
F-002 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:6235 | правило=REQ-007/AC-010 (first_token_timeout с env-порогом, дефолт 60 с) | evidence=`> max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` в legacy send_keepalive | исправление=убрать пол 120.0, сравнивать ровно с FIRST_TOKEN_TIMEOUT_S (как serve-путь server.py:3316) | проверка=legacy-тест: первое событие есть, токенов нет, FIRST_TOKEN_TIMEOUT_S=0.8 — попытка завершается first_token_timeout за ~0.8 с, а не за 120 с
F-003 | priority=non-blocking | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3235, server.py:2613 | правило=C-MULT-I2 (ограниченные буферы горячего пути), security.md §6 (ограничение размера ответа) | evidence=`line = sse_resp.readline()` без limit; `raw.extend(chunk)` в цикле _serve_http без потолка | исправление=именованные константы лимита строки SSE и тела управляющего ответа, при превышении — ServeProtocolError/ServeUnavailable | проверка=тест с SSE-строкой и телом больше лимита: попытка завершается протокольной ошибкой, RSS очереди ограничен
F-004 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:1949 | правило=REQ-014/AC-019 (usage совпадает по полям), python-standards §3 (валидация на границе) | evidence=`if not tokens or not isinstance(read_obj, int)` — bool является int в Python; для tokens.input/output/reasoning проверяется только not bool, знак не проверяется | исправление=единая проверка `isinstance(v,int) and not isinstance(v,bool) and v>=0` для всех четырёх полей | проверка=unit-тесты _map_serve_event с cache.read=true и отрицательными tokens дают ServeProtocolError
F-005 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3584, server.py:3595, server.py:3607 | правило=REQ-008/AC-011 (0 сирот ≤7 с после закрытия сокета), feature.md (таймаут на каждом шаге цепочки I/O включая cleanup в finally), FU-006 | evidence=последовательно: два join(timeout=0.5), interrupt deadline +0.35, DELETE deadline +0.35, затем lease.cleanup с окнами SIGTERM 4 с + SIGKILL-подтверждение 2 с — худший случай >7 с; coder.json признаёт отсутствие оракула капающего cleanup-тела | исправление=закрывать lifeline/посылать SIGTERM группе до HTTP-cleanup либо ужать последовательные бюджеты; добавить сквозной оракул худшего случая | проверка=FakeServe, игнорирующий interrupt и капающий тело: после закрытия клиентского сокета группа процессов отсутствует ≤7 с

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 5


### Seat 2 (`realist`, `gpt-6.1-sol-high`)

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
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 7


### Seat 3 (`visionary`, `grok-4.7-high`)

PANEL-NONCE: d3bb3ab877289505
ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Цикл 5 закрывает ровно ту архитектуру, которая меняет игру: короткоживущий `opencode serve` на попытку отдаёт дельты, которых `opencode run` v2.1.2 не выдаёт, ротация IP и kill-switch с дефолтом `run` сохраняются, публичный SSE-конверт остаётся. Verify-fixed по имени приёмки: RW-001 на обрыве тела prompt и на HTTP 429/5xx (заголовки входят в `delivered`, `ServeUnavailable` после `headers_at` не бросается, L2: `exit_reason=prompt_error|prompt_status_429|prompt_status_503`, `transport=serve`); RW-002 (абсолютный срок `STATUS_INITIAL`, оракул 0.5 с ≤ 1.0 с); RW-003/FU-001 (один разделитель watchdog/unmapped/incomplete только при thinking); RW-004 (`last_token_at` на `session.tool.input.delta` и на завершённом native-вызове). Дыра — соседняя ветка того же инварианта. `FALLBACK_DECISION_TABLE` (server.py:1701-1708) для prompt с уже полученными заголовками требует `serve_retry`, а не `fallback_to_run`. Ветки `first_event_timeout` (server.py:3309) и `_prompt_err` (server.py:3349-3357) этот флаг ставят. Ветка `etype == "error"` (server.py:3552-3556) пишет `error` / `transient_error` / `terminal="failed"` и выходит без `result["delivered"]`. `_is_transient_stream_error` (server.py:976-980) считает транзиентными `status is None`, 408, 429 и `>= 500`, то есть `session.execution.failed` / `provider.free-limit` после HTTP 200 prompt. Внешний SSE-барьер (server.py:5564-5570, 5618-5622) и JSON-барьер (server.py:6846-6855, 6911-6912) смотрят только `result["delivered"]`, тексты и native-вызовы. При `TRANSPORT=auto`, заголовках prompt и ошибке модели до первого токена запрос уходит в `opencode run` и шлёт тот же prompt в Zen второй раз. Отдельно legacy SSE поднимает порог первого токена до `max(FIRST_TOKEN_TIMEOUT_S, 120)` (server.py:6235) при дефолте 60 с и при AC-010.
   СОВЕТЫ (при FAIL):
   - В `bridges/opencode-zen-bridge/server.py:3552` перед `break` выставить `result["delivered"]` из `prompt_status["headers_at"]` или уже накопленных `texts` / `reasonings` / `native_calls`, тем же предикатом, что `_prompt_err` на server.py:3349-3357.
   - На server.py:5618 и server.py:6911 не возвращать fallback в `run`, пока этот флаг истинен: `serve-retry` через `attempts.allow_retry` либо терминальная SSE/502, без `Run.execute`, без `_spawn_with_stdin`, без `record_success()`.
   - Оракул: prompt HTTP 200 с `headers_at`, затем `session.execution.failed` (429 / timeout / eof) до первого токена, `TRANSPORT=auto`, и stream, и JSON.
   - На server.py:6235 убрать немой пол `120.0` либо завести отдельную legacy-переменную и покрыть тестом: `FIRST_TOKEN_TIMEOUT_S=60` и событие без токена дают `first_token_timeout` около 60 с, а не около 120 с.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=REQ-001..REQ-020 и AC-001..AC-026 на потоковом пути и на serve закрыты матрицей `verification-traceability.md` и зелёным L2 (451 pytest, 451 unittest, обратный порядок AC-023, VER-005 72). Статусы `[мост]` отделены префиксом и `\n`, `_messages_to_prompt` (server.py:3940) берёт только `_render_turn`, исторический `reasoning_content` в промпт не входит (AC-007, оракул зелёный). Google-срез и `_run_env` заморожены, `google_direct_unchanged=true`. Пропущенная ветка REQ-006/REQ-007: `Run.execute` для non-stream JSON (server.py:5094-5100, 5147) умеет только `client_gone`. Часы `first_event_timeout` / `first_token_timeout` / `stall_timeout` есть в `_serve_one_attempt` (server.py:3305-3324) и в legacy SSE `send_keepalive` (server.py:6225-6246), на JSON-прогоне их нет, потолок остаётся `TIMEOUT_S=1800`. Это прямой MUST, не спор о стиле. DSH ходит со `stream:true` (F-35), поэтому прод-потребитель закрыт, а JSON-ручка моста — нет.
   СОВЕТЫ (при FAIL):
   - В цикле чтения `Run.execute` завести тот же `_WatchdogState`, что у legacy SSE: нет события транспорта до `FIRST_EVENT_TIMEOUT_S` → убийство группы и `first_event_timeout`; нет токена до порога → `first_token_timeout`; пауза после токена дольше `STALL_TIMEOUT_S` → `stall_timeout`; всё внутри `MAX_TOTAL_SPAWNS`.
   - Регрессия: `stream:false`, фейковый CLI без stdout, выход с `first_event_timeout` заметно раньше 1800 с, процесс группы мёртв.
   - Либо явная фраза в конверте, что REQ-006/REQ-007 относятся только к SSE и serve. Пока её нет, ветка обязана работать.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Сопровождать это можно. Транспорт по умолчанию `run`, пока нет boolean `REALTIME_SERVE_ENABLED` или явного `TRANSPORT=serve`; disable-файл и override `0` остаются аварийными выключателями. На попытку один helper, одна группа, `OPENCODE_DB=:memory:`, lease `0700`, порт из процесса, `finally` делает interrupt/DELETE с дедлайном 0.35 с и `killpg`. Idle serve ~152 MiB при слоте 6 укладывается в оценку HL-ENV из конверта. Зависимости рантайма вне stdlib не добавлены. `ps`/`lsof` уже есть на целевом хосте (факт-карта). VER-006/VER-007 законно `DEFERRED_L3` до ACCEPT: живой `:9883` этим диффом не мутируется. Операционная цена — холодный serve на запрос и reaper при старте, она и есть способ сохранить ротацию IP.

4. РИСКИ: VERDICT=PASS
   WHY=Секреты: пароль serve — `secrets.token_hex`, в lease не пишется; `_mask_secrets` и `_error_payload` режут Bearer, `OPENCODE_SERVER_PASSWORD` и userinfo прокси; оракул RW-008 зелёный. Инструменты: дефолт `ask_reject`, `permission.asked` → reject+interrupt, `form.created` отменяется до разбора схемы, 401/403/400/404/422 — `ServeSecurityError` без fallback. Данные: `OPENCODE_DB=:memory:`, usage копится по попыткам, повтор шага с `assistantMessageID` подавляется (server.py:3521-3529). Прод-контур L2 зелёный, живой heavy-path отложен регламентом. Red→green: `L2-RED-sensitivity` rc=1 на `origin/dev` (76 падений на отсутствии символов), VER-005 rc=0 на кандидате. Full suite: pytest 451, unittest 451, порядок AC-023, VER-003/003b. Scope: ровно 3 файла манифеста, 0 новых runtime-зависимостей, замороженные срезы совпали. Дыра F-001 этим набором не поймана: существующие оракулы бьют в HTTP-статус prompt, а не в `session.execution.failed` после заголовков. Это дыра логики, чинится вместе с F-001, набор L2 сам по себе регрессию не прячет.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve на запрос — тот вариант, который одновременно даёт реалтайм (RC-1) и оставляет ротацию чистого IP на spawn (F-15, дневной лимит Zen). Общий демон дешевле по RSS и хуже по квоте: один IP на все запросы. Прямой HTTP к Zen на фактах анализа получил 429 без заголовков CLI. Откат на `run` до барьера доставки повторяет прецедент muse-bridge и нужен как kill-switch REQ-003. Объём `server.py` — след REQ-001..REQ-016 в одном файле конверта, не переписывание ради переписывания. Дешёвый путь «только watchdog и статусы на legacy» реалтайм размышления не даёт (F-17, F-18).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Граница задачи удержана: изменены `bridges/opencode-zen-bridge/server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`. Чужие мосты, DSH, каталог Zen, `zen_catalog.py` и Google-маршрут не тронуты. `sha256(_run_env)=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`, `google_direct_unchanged=true`. Публичные пути `/health`, `/v1/models`, `/v1/chat/completions` и форма OpenAI SSE сохранены; синтетические строки `[мост]` — явное требование REQ-004/REQ-005, не самовольный контракт. `CATALOG_SOURCE="static"` зафиксирован VER-004. Оракул `test_step_interruption` приведён к `MAX_TOTAL_SPAWNS=3` по REQ-017, потолок не ослаблен. Stdlib-only, `dependencies=[]`. Сверка сида: `seed_hex=9fc56e2918ce7c0cd76640cf97f8f8026b36f1f1f4870d9f746f7517a49c3ee2` совпал с манифестом r56, `SEED=9fc56e29`; `ranked_order` совпал с манифестом r56: grok-4.7-high, gpt-6.1-sol-high, muse-wonder-full-1.0, claude-sonnet-5-5-high, gemini-4-argon-high.

SUB Корректность/логика: FAIL — server.py:3552 не ставит `delivered` с `headers_at` на `etype=="error"`, server.py:5619 и server.py:6911 уходят в `run` (FALLBACK_DECISION_TABLE server.py:1701, REQ-009)
SUB Корректность/граничные условия: FAIL — server.py:6235 `max(FIRST_TOKEN_TIMEOUT_S, 120.0)` глушит дефолт 60 с на legacy SSE (REQ-007, AC-010)
SUB Корректность/обработка ошибок: PASS — server.py:3329-3332 и server.py:3349-3357: 401/403/400/404/422 → `ServeSecurityError`, обрыв тела после заголовков → `prompt_error` без `ServeUnavailable` (RW-001, L2 `prompt_error`)
SUB Полнота/покрытие AC: PASS — verification-traceability.md REQ-001..020 / AC-001..026, L2 VER-001 rc=0, VER-005 rc=0, VER-006/007 DEFERRED_L3
SUB Полнота/пропущенные ветки: FAIL — server.py:5094-5100 и server.py:5147: JSON `Run.execute` без `first_event_timeout`/`first_token_timeout`/`stall_timeout` (REQ-006, REQ-007) [pre-existing]
SUB Реализуемость/общее: PASS — kill-switch дефолт `run` (server.py:1888-1910), lease+killpg в `finally`, 0 зависимостей вне stdlib, живой деплой не мутирован
SUB Риски/безопасность: PASS — server.py:1898 пароль `token_hex`, маскирование `_mask_secrets`/`_error_payload`, permission reject и form cancel до схемы, оракул секретов зелёный (REQ-015)
SUB Риски/данные: PASS — `OPENCODE_DB=:memory:` в `_serve_env`, usage по попыткам, дедуп шага по `assistantMessageID` server.py:3521-3529
SUB Риски/прод: PASS — code-gate.json L2 PASS, слот 6 и idle serve 152 MiB в оценке HL-ENV, H0..H9 отложены до ACCEPT
SUB Риски/regression red→green: PASS — execution-evidence.md L2-RED rc=1 (76 failed на origin/dev), VER-005 rc=0 (72 passed)
SUB Риски/Full Suite (L2): PASS — VER-001 451 pytest, VER-002 451 unittest, AC-023 reversed rc=0, VER-003/003b rc=0
SUB Риски/scope-diff: PASS — candidate-manifest.json ровно 3 файла, frozen sha256 совпали, `dependencies=[]`
SUB Альтернативы/общее: PASS — per-request serve сохраняет ротацию IP (F-15) и даёт дельты, которых нет у `opencode run` (F-17, F-18); общий демон и прямой Zen этой цели не закрывают
SUB Соответствие контексту/общее: PASS — 3 файла конверта, REQ-002/REQ-018, seed_hex r56 совпал (`9fc56e29…3ee2`)

F-001
priority: blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:3552, bridges/opencode-zen-bridge/server.py:3556, bridges/opencode-zen-bridge/server.py:5564, bridges/opencode-zen-bridge/server.py:5618, bridges/opencode-zen-bridge/server.py:5619, bridges/opencode-zen-bridge/server.py:6846, bridges/opencode-zen-bridge/server.py:6911
rule: FALLBACK_DECISION_TABLE phase=PROMPT_RESPONSE (server.py:1701-1708), инвариант RW-001 «headers_at запрещает run», REQ-009
evidence: `elif etype == "error": result["error"] = payload; result["transient_error"] = _is_transient_stream_error(payload); result["terminal"] = "failed"; break` — флага `delivered` нет. Классификатор (server.py:976-980) возвращает True для 429, `status is None` и `status >= 500`. Снаружи: `_delivered_err = _delivered_now or bool(collected_texts)` и `if not _delivered_err and not force_serve: return False` с `transport_history=["serve","run"]`. JSON: `if not _delivered_j and not force_serve: return False`.
expected: на `etype=="error"` выставить `result["delivered"]` из `prompt_status["headers_at"]` или уже отданных токенов/вызовов; при истине — `serve_retry` или терминальная ошибка, без второго upstream-prompt.
check: `TRANSPORT=auto`, заголовки prompt 200, затем `session.execution.failed` (free-limit/timeout/eof) до токена, stream и JSON: `Run.execute` и `_spawn_with_stdin` не вызываются, `record_success()` не вызывается, `allow_retry` не больше одного раза на попытку.

F-002
priority: blocking
criterion: КОРРЕКТНОСТЬ
locations: bridges/opencode-zen-bridge/server.py:6231, bridges/opencode-zen-bridge/server.py:6235
rule: REQ-007, AC-010
evidence: `now_s - attempt_start > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` при дефолте `FIRST_TOKEN_TIMEOUT_S=60`. Serve-путь сравнивает с сырым порогом (server.py:3314-3316). На legacy SSE событие без токена живёт до 120 с, сколько бы ни стояло в окружении ниже 120.
expected: сравнение с `float(FIRST_TOKEN_TIMEOUT_S)` на обоих транспортах, либо отдельная переменная с явным именем и тем же дефолтом, что в конверте.
check: `FIRST_TOKEN_TIMEOUT_S=60`, legacy SSE, есть событие и нет токена: `exit_reason=first_token_timeout` около 60 с плюс допуск, не около 120 с.

F-003
priority: blocking
criterion: ПОЛНОТА
locations: bridges/opencode-zen-bridge/server.py:5094, bridges/opencode-zen-bridge/server.py:5100, bridges/opencode-zen-bridge/server.py:5147
rule: REQ-006, REQ-007, AC-008, AC-009, AC-010
evidence: [pre-existing] `on_idle` в `Run.execute` ставит только `state = "client_gone"` и зовёт `_stop_proc`. Ветка `etype == "error"` (server.py:5147) не классифицирует молчание. Часы первого события, первого токена и паузы в этом методе отсутствуют; их копии живут в SSE (server.py:6225-6246) и в `_serve_one_attempt` (server.py:3305-3324). Non-stream JSON упирается в `TIMEOUT_S=1800`.
expected: те же три причины выхода и убийство группы внутри общего потолка спавнов на JSON-прогоне `opencode run`.
check: `stream:false`, фейковый CLI без stdout: завершение с `first_event_timeout` за порог плюс единицы секунд, процессов группы нет. Аналогично первый токен и пауза после токена.

[sweep] Повторный проход 1–14: новые корни сверх F-001..F-003 не найдены. RW-002/RW-003/RW-004 и FU-002..FU-006 подтверждены кодом и зелёными оракулами L2. FU-007 (оставить unittest) — вне FAIL. `_strip_interrupted` на reasoning режет только маркер обрыва, тот же приём уже на legacy-пути, AC-006 не ломает.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 14/14 подкатегорий
FINDINGS_COMPLETE: 3


---

## Раунд D1 (`panel/council/r65`)

### Seat 1 (`skeptic`, `muse-wonder-full-1.0`)

PANEL-NONCE: 8edbe335478431d7
ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4

DISPUTE F-006 — класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:3553 — тот же корень, место и суть, что F-001: ветка `etype == "error"` не переносит `headers_at` в `delivered`; separate blocking не нужен, фикс и оракул F-001 покрывают SSE и JSON.
DISPUTE F-007 — класс: duplicate_of:F-002 — контр-evidence: bridges/opencode-zen-bridge/server.py:6235 — дословно та же строка `max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` и то же правило REQ-007/AC-010, что F-002.
AGREE F-008 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5094 — `on_idle` в `Run.execute` проверяет только `is_client_gone` и зовёт `_stop_proc`; часов first-event/first-token/stall в non-stream JSON нет, потолок остаётся `TIMEOUT_S=1800`, в отличие от legacy SSE server.py:6225 и serve server.py:3305 — REQ-006/REQ-007 на JSON-ветке не выполнены.
AMEND F-009 — priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_step_interruption.py:171, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:793; fix=добавить эквивалентную serve-матрицу step-interruption и сравнение unmapped recovery с legacy как follow-up усиление оракулов AC-016/AC-017, без блокировки цикла — причина: bridges/opencode-zen-bridge/server.py:1911 и serve-циклы переиспользуют те же `_incomplete_step_signal`/`_native_to_tool_calls`, отдельные serve-сценарии (tool_text, native, tool_choice recovery) уже зелёны в L2; воспроизводимого дефекта кода находка не показывает, это пробел полноты тестов, а не доказанный сбой.
AMEND F-010 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2731, bridges/opencode-zen-bridge/server.py:2825, bridges/opencode-zen-bridge/server.py:3101; fix=передать остаток deadline и `is_client_gone` в `_spawn_serve` и подписку `/api/event` как follow-up, не запускать helper при уже истёкшем deadline — причина: bridges/opencode-zen-bridge/server.py:2799 — стартовые окна ограничены собственными таймаутами handshake/listener по 3 с и завершаются `ServeUnavailable` с уборкой lease, то есть зависания без предела нет; дефект — лишние секунды и лишний spawn при истёкшем бюджете, не потерянный запрос и не сироты.
AMEND F-011 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:181, bridges/opencode-zen-bridge/server.py:2844; fix=запускать родительский дренаж stderr helper сразу после `Popen`, до handshake/listener, как follow-up — причина: bridges/opencode-zen-bridge/server.py:2826 — при выводе до bind сверх ёмкости пайпов родитель упирается в listener-таймаут 3 с и уходит в `ServeUnavailable` с `lease.cleanup()`, а не висит бесконечно; реальный `opencode serve` мегабайты до bind не пишет, сценарий — fault-injection граница, не прод-блокер.
DISPUTE F-012 — класс: duplicate_of:F-005 — контр-evidence: bridges/opencode-zen-bridge/server.py:3595 — те же cleanup-места interrupt/DELETE и та же суть, что F-005: суммарный худший случай уборки может превысить бюджет AC-011, оракула капающего тела нет (coder.json это признаёт); отдельный blocking поверх F-005 задвоит один фикс — жёсткий путь к `killpg` независимо от control API.
DISPUTE F-013 — класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:3552 — та же ветка `etype == "error"`, тот же инвариант RW-001 и те же потребители server.py:5619/6911, что F-001.
DISPUTE F-014 — класс: duplicate_of:F-002 — контр-evidence: bridges/opencode-zen-bridge/server.py:6235 — тот же `max(FIRST_TOKEN_TIMEOUT_S, 120.0)` и правило REQ-007/AC-010, что F-002.
DISPUTE F-015 — класс: duplicate_of:F-008 — контр-evidence: bridges/opencode-zen-bridge/server.py:5094 — тот же отсутствующий watchdog в `Run.execute` для non-stream JSON и те же REQ-006/REQ-007, что F-008, который я принял как канонический.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=F-001 (дубли F-006, F-013): ветки `error` server.py:3553 и `timeout` server.py:3565 не ставят `delivered` из `headers_at`, в auto возможен второй вызов Zen через `run` после принятого prompt. F-002 (дубли F-007, F-014): legacy SSE глушит порог первого токена полом 120 с при дефолте 60 с.
   СОВЕТЫ (при FAIL): ставить `delivered` из `headers_at` на всех выходах `_serve_one_attempt`; убрать `max(...,120.0)` на server.py:6235; регрессионные тесты headers→transient SSE-error и headers→timeout в SSE и JSON без `Run.execute`/`_spawn_with_stdin`/`record_success()`.
2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-002, RW-003/FU-001, RW-004, FU-002, FU-003, FU-004 закрыты и подтверждены L2. RW-001 закрыт частично (F-001). Принимаю F-008 коллег: REQ-006/REQ-007 не реализованы на legacy non-stream JSON. F-009 понизил до non-blocking: матрица AC-016/AC-017 на serve неполна, но дефекта кода не доказано.
   СОВЕТЫ (при FAIL): добавить три watchdog с классификацией в `Run.execute` внутри `MAX_TOTAL_SPAWNS`; тесты `stream:false` на тишину, события без токенов и паузу после токена с остановкой группы; оракулы F-001.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Clean-room L2 PASS (451 pytest/unittest, обратный порядок, VER-004), 0 зависимостей вне stdlib, kill-switch с дефолтом `run`. Не согласен с FAIL реалиста по этому критерию: F-010 и F-011 ограничены существующими таймаутами старта и уборкой lease, понизил их до non-blocking. VER-006/VER-007 законно DEFERRED_L3.
4. РИСКИ: VERDICT=FAIL
   WHY=F-001 — риск двойного расхода квоты и двойной генерации; F-002 и F-008 — немая деградация 120 с на legacy SSE и до 1800 с на legacy JSON. Non-blocking хвосты прежние: F-003 неограниченные SSE-строка и тело `_serve_http`, F-004 валидация usage (bool/отрицательные токены), F-005 (дубль F-012) худший cleanup дольше 7 с AC-011.
   СОВЕТЫ (при FAIL): исправить F-001, F-002, F-008 как blocking; F-003/F-004/F-005/F-010/F-011 — follow-up одним проходом с оракулами: лимиты буферов именованными константами, единая проверка токенов `int and not bool and >=0`, `killpg` до HTTP-cleanup или доказательство бюджета ≤7 с, дренаж stderr сразу после `Popen`, deadline в `_spawn_serve`.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Гибрид короткоживущий serve + fallback обоснован F-17..F-19 и прецедентом muse-bridge F-40; путь L реалтайм не даёт, общий демон теряет ротацию IP, прямой Zen не доказан (F-24, F-25). Все принятые находки чинятся внутри выбранной архитектуры, переписывание не требуется.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Ровно 3 файла конверта, замороженные срезы и Google-direct не тронуты (`google_direct_unchanged=True`), публичный контракт сохранён, Forbidden Scope не нарушен. Не согласен с FAIL реалиста по этому критерию: пробелы deadline — это корректность и полнота внутри задачи (F-008, F-010), а не выход за контекст или смена контракта.

POSITIONS: 10/10
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 2 (`realist`, `grok-4.7-high`)

PANEL-NONCE: 5f4c8610f7fae22d
ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4

AGREE F-001 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3552` — ветка `elif etype == "error"` пишет `error` / `transient_error` / `terminal="failed"` и делает `break`, не ставя `result["delivered"]`; `server.py:3563` так же ставит `exit_reason="timeout"` без `delivered`. `server.py:3309` и `server.py:3349` для `first_event_timeout` и обрыва тела prompt этот флаг ставят. Потребители `server.py:5619` и `server.py:6911` при `delivered=False` и отсутствии токенов возвращают fallback на `run`.
AGREE F-002 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:6235` — legacy SSE сравнивает `now_s - attempt_start > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)`. Serve-путь `server.py:3314` сравнивает с сырым `FIRST_TOKEN_TIMEOUT_S`. Порог ниже 120 с, включая дефолт 60 с, на legacy не действует (REQ-007, AC-010).
AGREE F-003 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3235` — `sse_resp.readline()` без лимита; `server.py:2613` — `raw.extend(chunk)` без потолка тела. Приоритет non-blocking оставляю: это локальный serve моста, а не смена контракта; blocking-дыра доставки — F-001.
AGREE F-004 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:1949` — `isinstance(read_obj, int)` пропускает `bool`; для `input`/`output`/`reasoning` отсекается только `bool`, знак не проверяется. Накопление через `_as_int` обнуляет `bool`, отрицательные целые проходят. Приоритет non-blocking верный.
AGREE F-005 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3584`, `server.py:3595`, `server.py:3607` — два `join(0.5)`, затем interrupt и DELETE с `deadline=monotonic()+0.35`, и только потом `lease.cleanup()`. Спроектированная сумма с окнами SIGTERM/SIGKILL может превысить 7 с AC-011. Оставляю non-blocking: прошлый цикл понизил FU-006 до non-blocking; неограниченное капание `getresponse`/`read1` уже blocking в F-012 и этот фикс не отменяет.
AGREE F-013 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3552` и `server.py:3556` — тот же выход `etype=="error"` без `delivered`; `server.py:5618` и `server.py:6911` уходят в `run`. Это тот же корень, что F-001; F-001 полнее, потому что покрывает и `timeout` на `server.py:3563`.
AGREE F-014 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:6231` и `server.py:6235` — тот же пол `120.0`, что F-002.
AGREE F-015 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:5094` — `on_idle` в JSON `Run.execute` ставит только `client_gone` и зовёт `_stop_proc`. Часов первого события, первого токена и паузы нет; `server.py:5147` классифицирует ошибку провайдера, не молчание. REQ-006/REQ-007 и AC-008..AC-010 не ограничены SSE. Тот же корень, что открытый F-008.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 закрыт для HTTP-статуса prompt и обрыва тела после заголовков (`server.py:3309`, `server.py:3349`), но не для SSE-ошибки выполнения и дедлайна попытки. F-001 и F-013: при `headers_at` и `session.execution.failed` либо `timeout` до токенов `delivered` остаётся False, и auto вызывает `run`. F-002 и F-014: legacy SSE глушит `FIRST_TOKEN_TIMEOUT_S` полом 120 с.
   СОВЕТЫ (при FAIL): на `server.py:3552` и `server.py:3563` ставить `result["delivered"]` из `prompt_status["headers_at"]` или уже отданных токенов; при истине — `serve-retry` через `allow_retry` либо терминальная ошибка, без `Run.execute`, `_spawn_with_stdin` и `record_success()` (`server.py:5619`, `server.py:6911`). На `server.py:6235` сравнивать ровно с `FIRST_TOKEN_TIMEOUT_S`. Оракулы: auto, stream и JSON, заголовки prompt 200, затем transient SSE-error и отдельно deadline-timeout; legacy SSE с порогом 0.8 с и событием без токена даёт `first_token_timeout`.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-002, RW-003, RW-004 и FU-001..FU-004 остаются закрытыми. F-015: non-stream JSON не классифицирует `first_event_timeout`, `first_token_timeout` и `stall_timeout` и ждёт `TIMEOUT_S`. Открытый F-009: матрица `test_step_interruption.py` идёт через shebang fake-CLI и выбирает `run`, поэтому AC-016 и AC-017 на serve не доказаны целиком.
   СОВЕТЫ (при FAIL): в `Run.execute` завести те же три watchdog и убийство группы внутри `MAX_TOTAL_SPAWNS` (`server.py:5094`). Прогнать сценарии AC-016 на serve-дельтах и сравнить unmapped-повтор и `finish_reason` с legacy (F-009).

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Транспорт на stdlib и `opencode` v2.1.2 осуществим, kill-switch по умолчанию `run`. Выкат блокируют открытые F-010 и F-011: `_spawn_serve` (`server.py:2731`) не принимает deadline и отмену и держит свои окна handshake/listener; дренаж stderr родителя стартует только после проверки listener (`server.py:2844`), а helper пишет stderr синхронно (`server.py:181`).
   СОВЕТЫ (при FAIL): протащить остаток дедлайна и отмену через startup и подписку `/api/event`; отмена не должна становиться `ServeUnavailable` с fallback. Запускать дренаж stderr сразу после `Popen` и ограничить его байтами. Оракул: несколько MiB до bind, в том числе без LF; истёкший deadline не запускает helper.

4. РИСКИ: VERDICT=FAIL
   WHY=L2 зелёный: 451 pytest, 451 unittest, корневой прогон и обратный порядок, RED sensitivity rc=1. Это не закрывает F-001: второй вызов Zen после уже принятого prompt. Открытый F-012: `getresponse` (`server.py:2604`) и `read1` (`server.py:2610`) могут удерживать cleanup дольше абсолютного deadline, и `lease.cleanup` не достигается. F-003, F-004 и F-005 оставляю non-blocking. Секреты, allowlist и маскирование по проверенным оракулам держатся.
   СОВЕТЫ (при FAIL): закрыть F-001 регрессией без второго upstream. Прерывать текущую HTTP-фазу по deadline и в cleanup не читать ненужное тело; группа исчезает в пределах AC-011, слот возвращается (F-012). VER-006/VER-007 остаются DEFERRED_L3 до ACCEPT.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve на попытку с откатом на `run` до барьера доставки закрывает отсутствие дельт у `opencode run` и сохраняет ротацию IP. Прямой Zen HTTP по фактам анализа не доказан, общий демон её ломает. Дефекты F-001..F-015 чинятся внутри этой схемы; переписывания транспорта не требуется.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Конверт удержан: три разрешённых файла, замороженные `_run_env` и Google-срез, публичные пути и форма SSE, без чужих KEY и без внешних зависимостей. Не выполнен прямой пункт feature.md: таймаут на каждом шаге цепочки, включая cleanup. F-010 не передаёт дедлайн в старт, F-012 не гарантирует абсолютный предел HTTP-фазы до `killpg`.
   СОВЕТЫ (при FAIL): протащить `remaining deadline` в `_spawn_serve` и в `_serve_http` так, чтобы фаза обрывалась по бюджету, а не только проверялась между блокирующими `recv`. Повторить clean-room L2 после правки.

POSITIONS: 8/8
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


### Seat 3 (`visionary`, `gpt-6.1-sol-high`)

PANEL-NONCE: de1e516a8a57b72d
ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4

AGREE F-001 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:3553,3565,5619,6911 — ветки SSE-error и общего timeout не сохраняют полученные prompt headers в `delivered`; внешние циклы могут разрешить fallback. Барьер следует сохранять независимо от причины выхода. После headers допустим serve-retry через общий бюджет либо терминальная ошибка.

AGREE F-002 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:6235 — `max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` действительно игнорирует настроенный порог ниже 120 секунд, включая дефолтные 60 секунд. Это нарушение REQ-007/AC-010.

AGREE F-003 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:3235,2613 — `readline()` не ограничивает размер строки, `raw.extend(chunk)` не ограничивает совокупный размер тела. Приоритет non-blocking принимаю: сам факт отсутствия байтового потолка подтверждён, эксплуатационное превышение памяти пакетом не доказано. Нужны лимиты размеров и негативные оракулы; переполнение очереди по числу элементов эту границу не закрывает.

AGREE F-004 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:1949,1954 — `cache.read` принимает `bool`, остальные счётчики исключают `bool`, но не отрицательные числа. Приоритет non-blocking принимаю: корректные фикстуры usage проходят, дефект относится к обработке некорректного wire-ввода. Исправление — единый предикат неотрицательного целого для четырёх полей.

AMEND F-005 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3584,3595,3607; fix=добавить сквозной оракул времени от закрытия клиентского сокета до исчезновения группы; при необходимости начинать остановку группы до HTTP-cleanup — причина: сумма `join + HTTP + 4 + 2` показывает возможный бюджет завершения cleanup, но последние две секунды предназначены для подтверждения смерти после SIGKILL и сами по себе не доказывают, что процессы живут дольше семи секунд. Отдельный доказуемый обход абсолютного deadline учитывается в F-012.

DISPUTE F-006 — класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:3553,5619,6911 — тот же корень: потеря барьера prompt headers на SSE-error и последующий fallback. Исправление и оракул совпадают; отдельного дефекта здесь нет.

DISPUTE F-007 — класс: duplicate_of:F-002 — контр-evidence: bridges/opencode-zen-bridge/server.py:6235 — та же нижняя граница 120 секунд, то же нарушение REQ-007/AC-010.

AGREE F-008 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:5094,5104,5118 — legacy JSON проверяет отключение клиента, но не ведёт часы первого события, первого токена и паузы. REQ-006/REQ-007 не ограничены только SSE. Требуются три watchdog с остановкой группы, классификацией и сохранением общего бюджета попыток. Замечание [pre-existing], blocking в изменённом файле задачи.

AGREE F-009 rev=1 — проверил: bridges/opencode-zen-bridge/tests/test_step_interruption.py:171,181 и bridges/opencode-zen-bridge/server.py:1911 — существующая матрица использует shebang fake-CLI, который в auto выбирает legacy. Новые serve-тесты проверяют отдельные recovery-сценарии, но не доказывают требование AC-016 «все сценарии» и сравнительный unmapped-сценарий AC-017. Нужна эквивалентная матрица serve с конкретными test IDs в traceability. Замечание [pre-existing], blocking.

AGREE F-010 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:2731,2799,2825,3101,3196 — `_spawn_serve` не получает deadline/cancellation, а подписка использует самостоятельный timeout. Предварительная проверка клиента в `_serve_one_attempt` не контролирует последующие setup-фазы. Требуется передавать остаток бюджета и отмену через весь старт, исключив запуск helper при истёкшем deadline и fallback после отмены. Замечание [pre-existing], blocking.

AGREE F-011 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:181,2826,2844 — helper синхронно пишет в stderr, родитель начинает его дренировать после проверки listener. Большой вывод serve до bind способен заполнить оба пайпа и сорвать старт исправного транспорта. Дренаж следует запускать сразу после Popen; ограничивать нужно байты, поскольку одна строка может быть произвольного размера. Оракул — несколько MiB без LF до bind. Замечание [pre-existing], blocking.

AGREE F-012 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:2604,2610,3595,3607 — проверка deadline перед `getresponse()`/`read1()` не прерывает выполняемое внутри них чтение заголовков или chunk framing. При поступлении байтов чаще socket timeout абсолютный срок может истечь внутри операции. В cleanup это задерживает переход к `lease.cleanup()`. Нужен независимый механизм прерывания текущего I/O и остановки группы; ненужное cleanup-тело читать не следует. Замечание [pre-existing], blocking.

WITHDRAW F-013 — ARG: realist/R1 «сохранять подтверждение доставки на всех выходах»; проверил: bridges/opencode-zen-bridge/server.py:3553,3565,5619,6911 — снимаю отдельную запись как дубль F-001, который дополнительно охватывает общий timeout. Сам дефект и blocking-позицию сохраняю через F-001.

WITHDRAW F-014 — ARG: skeptic/R1 «убрать пол 120.0, сравнивать ровно с FIRST_TOKEN_TIMEOUT_S»; проверил: bridges/opencode-zen-bridge/server.py:6235 — снимаю отдельную запись как дубль F-002. Дефект остаётся blocking.

WITHDRAW F-015 — ARG: realist/R1 «добавить три watchdog и их классификацию/учёт повторов в JSON legacy»; проверил: bridges/opencode-zen-bridge/server.py:5094,5104,5118 — снимаю отдельную запись как дубль F-008. Дефект остаётся blocking.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Архитектура устраняет принципиальное ограничение legacy: serve предоставляет настоящие дельты без изменения клиентской SSE-схемы. Однако F-001 сохраняет обход delivery-инварианта, а F-002 нарушает конфигурируемую границу ожидания.
   СОВЕТЫ (при FAIL): сохранять барьер доставки на всех выходах; исключить run-fallback после headers; применять FIRST_TOKEN_TIMEOUT_S без скрытого пола; добавить оракулы SSE-error/timeout после headers для SSE и JSON и legacy first-token timeout.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-002, RW-003/FU-001 и RW-004 принимаются: абсолютный таймер, разделители thinking on/off и обновление native-активности подтверждены кодом и зелёным L2. FU-002..FU-004 также подтверждены. RW-001/FU-005 закрыты частично — F-001; FU-006 закрыт частично — F-010/F-012. FU-007 сохраняется в backlog. F-008 и F-009 оставляют непокрытые ветки требований.
   СОВЕТЫ (при FAIL): добавить watchdog legacy JSON; выполнить требуемую serve-матрицу AC-016/AC-017; дополнить сценарии delivery, startup cancellation и cleanup; обновить traceability по фактическим оракулам.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Короткоживущий serve сохраняет ротацию IP и изоляцию состояния; stdlib и in-memory DB соответствуют целевому хосту. Но F-010/F-011 способны срывать старт и удерживать ресурсы. Это препятствует надёжной эксплуатации выбранной схемы.
   СОВЕТЫ (при FAIL): провести deadline/cancellation через startup и subscribe; начать stderr-дренаж до handshake/listener; проверить большой стартовый вывод без LF и отмену на каждой setup-фазе.

4. РИСКИ: VERDICT=FAIL
   WHY=Валидные L2-прогоны признаю зелёными: компонентные pytest/unittest — 451 тест, корневой pytest — 894 passed, обратный порядок проходит, ошибок типов нет. Они не опровергают F-001/F-010/F-011/F-012. F-012 особенно существенен: зависший cleanup удерживает группу и слот. F-003/F-004/F-005 сохраняю как non-blocking. VER-006/VER-007 законно DEFERRED_L3.
   СОВЕТЫ (при FAIL): гарантировать независимое прерывание блокирующего I/O и остановку группы; добавить капающие HTTP-заголовки/chunk framing и проверки освобождения ресурсов; после исправлений повторить полный clean-room L2. Байтовые лимиты и валидацию usage учесть как согласованные follow-up.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Решение существенно меняет отзывчивость: доступен поток генерации, который legacy CLI принципиально скрывает. Общий демон осложняет ротацию IP, прямой Zen HTTP остаётся недоказанным, одни статусы и watchdog реалтайм не обеспечивают. Найденные дефекты исправляются внутри выбранной архитектуры; оснований требовать её замены нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Три разрешённых файла, frozen-срезы, stdlib-only и Non-Goals соблюдены; самовольного изменения публичного HTTP-контракта не установлено. Однако F-010/F-012 нарушают применимые требования feature.md §2 и R-BULK-I1 о сквозном ограничении I/O; F-009 не закрывает обязательные AC выбранного транспорта.
   СОВЕТЫ (при FAIL): обеспечить общий deadline и отмену на всей цепочке, включая cleanup; подтвердить AC-016/AC-017 serve-оракулами; затем повторить L2. Живую приёмку проводить после ACCEPT по установленному порядку.
   SEED-CHECK: независимо вычислено seed_hex=37c1ac06204c40dc152305bc9eca22bfff241059e553ab54fc4f1ac49e736ef5, SEED=37c1ac06; ranked_order по фактической функции rank_slots с полным seed_hex совпадает: gpt-6.1-sol-high → grok-4.7-high → muse-wonder-full-1.0 → claude-sonnet-5-5-high → gemini-4-argon-high.

POSITIONS: 12/12
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK


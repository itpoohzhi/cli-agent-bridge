# Консенсус-леджер Совета Тимлидов по коду (`consensus-ledger.md` / `findings-ledger.md`) — Cycle 5, run `analyst-teamlead-zen-realtime-reasoning-20261025`

- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4`)
- **Раунд R1 (`panel/council/r56`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r56/panel-proof.json sha256=886a24492839e5ff9a6a160e975070d9bab30224425ecfb6bae55938a6ed9efa verify_panel_proof exit=0`
- **Раунд D1 (`panel/council/r65`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r65/panel-proof.json sha256=e849230a4b0f3ba56e506d6d380c97fe1e6f63fb99aeac89e8986210458fe276 verify_panel_proof exit=0`
- **Всего находок R1:** `15` (`F-001` .. `F-015`), новых находок в D1 (`r2_late`): `0`.
- **Итог дебатов D1:** `AGREED blocking` = `7` (`RW-001..RW-007`), `AGREED non-blocking` = `3` (`FU-001..FU-003`), `WITHDRAWN / REJECTED_BY_MAJORITY excluded` = `5` (`5` межсудейских дублей `duplicate_of`). Открытых `OPEN` или `CONFLICT` нет (`0`).

## Сводная таблица статусов (`F-001` .. `F-015`)

| ID | skeptic | realist | visionary | priority | status |
|---|---|---|---|---|---|
| F-001 | AUTHOR | AGREE | AGREE | blocking | AGREED |
| F-002 | AUTHOR | AGREE | AGREE | blocking | AGREED |
| F-003 | AUTHOR | AGREE | AGREE | non-blocking | AGREED |
| F-004 | AUTHOR | AGREE | AGREE | non-blocking | AGREED |
| F-005 | AUTHOR | AGREE | AMEND | non-blocking | AGREED |
| F-006 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-007 | DISPUTE | AUTHOR | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-008 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-009 | AMEND | AUTHOR | AGREE | blocking | AGREED |
| F-010 | AMEND | AUTHOR | AGREE | blocking | AGREED |
| F-011 | AMEND | AUTHOR | AGREE | blocking | AGREED |
| F-012 | DISPUTE | AUTHOR | AGREE | blocking | AGREED |
| F-013 | DISPUTE | AGREE | WITHDRAW | withdrawn | WITHDRAWN |
| F-014 | DISPUTE | AGREE | WITHDRAW | withdrawn | WITHDRAWN |
| F-015 | DISPUTE | AGREE | WITHDRAW | withdrawn | WITHDRAWN |

---

## Карточки находок (`F-001` .. `F-015`)

### F-001
- origin: skeptic · R1 · skeptic-F-001
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-001 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:3553, server.py:3565 (корень), server.py:5614-5618, server.py:6888-6911 (потребители) | правило=RW-001 (headers_at включается в delivered на всех путях выхода), FALLBACK_DECISION_TABLE phase=DELIVERED, REQ-009 | evidence=`elif etype == "error": result["error"] = payload; result["transient_error"] = ...; break` — без `result["delivered"] = bool(prompt_status.get("headers_at"))`, в отличие от server.py:3309; та же недостановка на `result["exit_reason"] = "timeout"` | исправление=ставить delivered из headers_at на ветках error и timeout | проверка=новый тест в auto: prompt headers 200 получены, затем transient SSE-error без токенов (и отдельно deadline-timeout) — Run.execute/_spawn_with_stdin не вызваны ни в SSE, ни в JSON, record_success не вызван

### F-002
- origin: skeptic · R1 · skeptic-F-002
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-002 | priority=blocking | критерий=КОРРЕКТНОСТЬ | locations=bridges/opencode-zen-bridge/server.py:6235 | правило=REQ-007/AC-010 (first_token_timeout с env-порогом, дефолт 60 с) | evidence=`> max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` в legacy send_keepalive | исправление=убрать пол 120.0, сравнивать ровно с FIRST_TOKEN_TIMEOUT_S (как serve-путь server.py:3316) | проверка=legacy-тест: первое событие есть, токенов нет, FIRST_TOKEN_TIMEOUT_S=0.8 — попытка завершается first_token_timeout за ~0.8 с, а не за 120 с

### F-003
- origin: skeptic · R1 · skeptic-F-003
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-003 | priority=non-blocking | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3235, server.py:2613 | правило=C-MULT-I2 (ограниченные буферы горячего пути), security.md §6 (ограничение размера ответа) | evidence=`line = sse_resp.readline()` без limit; `raw.extend(chunk)` в цикле _serve_http без потолка | исправление=именованные константы лимита строки SSE и тела управляющего ответа, при превышении — ServeProtocolError/ServeUnavailable | проверка=тест с SSE-строкой и телом больше лимита: попытка завершается протокольной ошибкой, RSS очереди ограничен

### F-004
- origin: skeptic · R1 · skeptic-F-004
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-004 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:1949 | правило=REQ-014/AC-019 (usage совпадает по полям), python-standards §3 (валидация на границе) | evidence=`if not tokens or not isinstance(read_obj, int)` — bool является int в Python; для tokens.input/output/reasoning проверяется только not bool, знак не проверяется | исправление=единая проверка `isinstance(v,int) and not isinstance(v,bool) and v>=0` для всех четырёх полей | проверка=unit-тесты _map_serve_event с cache.read=true и отрицательными tokens дают ServeProtocolError

### F-005
- origin: skeptic · R1 · skeptic-F-005
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AMEND
- dissent: visionary d1 «AMEND F-005 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3584,3595,3607; fix=добавить сквозной оракул времени от закрытия клиентского сокета до исчезновения группы; п» → teamlead/cycle-5/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3584,3595,3607; fix=добавить сквозной оракул времени от закрытия клиентского сокета до исчезновения группы; при необходимости начинать остановку груп (teamlead/cycle-5/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> F-005 | priority=non-blocking [sweep] | критерий=РИСКИ | locations=bridges/opencode-zen-bridge/server.py:3584, server.py:3595, server.py:3607 | правило=REQ-008/AC-011 (0 сирот ≤7 с после закрытия сокета), feature.md (таймаут на каждом шаге цепочки I/O включая cleanup в finally), FU-006 | evidence=последовательно: два join(timeout=0.5), interrupt deadline +0.35, DELETE deadline +0.35, затем lease.cleanup с окнами SIGTERM 4 с + SIGKILL-подтверждение 2 с — худший случай >7 с; coder.json признаёт отсутствие оракула капающего cleanup-тела | исправление=закрывать lifeline/посылать SIGTERM группе до HTTP-cleanup либо ужать последовательные бюджеты; добавить сквозной оракул худшего случая | проверка=FakeServe, игнорирующий interrupt и капающий тело: после закрытия клиентского сокета группа процессов отсутствует ≤7 с

### F-006
- origin: realist · R1 · realist-F-001
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=DISPUTE
- dissent: skeptic d1 «DISPUTE F-006 класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:3553 — тот же корень, место и суть, что F-001: ветка `etype == "error"` не переносит `headers_at` » → teamlead/cycle-5/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-006 класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:3553,5619,6911 — тот же корень: потеря барьера prompt headers на SSE-error и последующий fallback.» → teamlead/cycle-5/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-001 — остаток RW-001, priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:3553`, `bridges/opencode-zen-bridge/server.py:5564`, `bridges/opencode-zen-bridge/server.py:5619`, `bridges/opencode-zen-bridge/server.py:6846`, `bridges/opencode-zen-bridge/server.py:6911`.
> - **Правило:** RW-001, FALLBACK_DECISION_TABLE/DELIVERED, REQ-009.
> - **Evidence:** ветка SSE ошибки устанавливает `error`, `transient_error`, `terminal="failed"` и выходит, сохранив исходное `delivered=False`. При HTTP 200 headers, затем `session.execution.failed` с transient error до токенов оба внешних цикла разрешают fallback на `run`.
> - **Исправление:** сохранять подтверждение доставки на всех выходах; отдельно учитывать наличие модельного вывода, чтобы headers-only transient failure корректно проходил serve-retry через общий бюджет.
> - **Критерий проверки:** auto, SSE и JSON: prompt headers → transient SSE failure до токенов; `run` не вызывается, RetryBudget учитывается, успешного учёта нет.

### F-007
- origin: realist · R1 · realist-F-002
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=DISPUTE
- dissent: skeptic d1 «DISPUTE F-007 класс: duplicate_of:F-002 — контр-evidence: bridges/opencode-zen-bridge/server.py:6235 — дословно та же строка `max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` и то же правило REQ-007/AC» → teamlead/cycle-5/debate/d1/skeptic.md ; visionary d1 «DISPUTE F-007 класс: duplicate_of:F-002 — контр-evidence: bridges/opencode-zen-bridge/server.py:6235 — та же нижняя граница 120 секунд, то же нарушение REQ-007/AC-010.» → teamlead/cycle-5/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-002 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:6235`.
> - **Правило:** REQ-007, AC-010.
> - **Evidence:** `max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` игнорирует заданные значения ниже 120 секунд, включая дефолтные 60.
> - **Исправление:** применять настроенный порог без скрытого увеличения.
> - **Критерий проверки:** legacy SSE получает служебное событие, затем молчит; first-token timeout срабатывает по заданному порогу и получает правильную классификацию.

### F-008
- origin: realist · R1 · realist-F-003
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-003 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:5094`, `bridges/opencode-zen-bridge/server.py:5104`, `bridges/opencode-zen-bridge/server.py:5118`.
> - **Правило:** REQ-006, REQ-007; AC-008..AC-010.
> - **Evidence:** JSON callback `on_idle` проверяет только `is_client_gone`; время первого события, первого токена и последнего токена здесь не отслеживается. Молчащий legacy JSON продолжает ждать общий TIMEOUT_S.
> - **Исправление:** добавить три watchdog и их классификацию/учёт повторов в JSON legacy.
> - **Критерий проверки:** `TRANSPORT=run`, `stream=false`: отсутствие событий, события без токенов и пауза после токена завершаются соответствующими timeout с остановкой группы.

### F-009
- origin: realist · R1 · realist-F-004
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AMEND, realist=AUTHOR, visionary=AGREE
- dissent: skeptic d1 «AMEND F-009 priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_step_interruption.py:171, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:793; fix=добавить экв» → teamlead/cycle-5/debate/d1/skeptic.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_step_interruption.py:171, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:793; fix=добавить эквивалентную serve-матрицу step-interrupti (teamlead/cycle-5/debate/d1/skeptic.md)
- text (дословно, R1 realist):
> **F-004 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/tests/test_step_interruption.py:171`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py:181`, `bridges/opencode-zen-bridge/server.py:1911`.
> - **Правило:** AC-016, AC-017; testing.md — проверять требуемое поведение и полноту.
> - **Evidence:** существующая матрица устанавливает shebang fake-CLI в OPENCODE_BIN; auto выбирает для него `run`. Новые serve-тесты покрывают отдельные сценарии, но не все сценарии существующей матрицы и не требуемое сравнение unmapped recovery.
> - **Исправление:** параметризовать поведенческую матрицу транспортами либо добавить эквивалентную serve-матрицу без ослабления assertions.
> - **Критерий проверки:** каждый сценарий AC-016 проверен на serve-дельтах; AC-017 сравнивает unmapped-повтор и итоговый finish_reason с legacy. В traceability приведены конкретные test IDs.

### F-010
- origin: realist · R1 · realist-F-005
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AMEND, realist=AUTHOR, visionary=AGREE
- dissent: skeptic d1 «AMEND F-010 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2731, bridges/opencode-zen-bridge/server.py:2825, bridges/opencode-zen-bridge/server.py:3101; fix=передать ос» → teamlead/cycle-5/debate/d1/skeptic.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2731, bridges/opencode-zen-bridge/server.py:2825, bridges/opencode-zen-bridge/server.py:3101; fix=передать остаток deadline и `is_client_gone` в `_sp (teamlead/cycle-5/debate/d1/skeptic.md)
- text (дословно, R1 realist):
> **F-005 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:2731`, `bridges/opencode-zen-bridge/server.py:2799`, `bridges/opencode-zen-bridge/server.py:2825`, `bridges/opencode-zen-bridge/server.py:3101`, `bridges/opencode-zen-bridge/server.py:3196`.
> - **Правило:** FU-006; REQ-008; feature.md §2; R-BULK-I1.
> - **Evidence:** `_spawn_serve` не принимает deadline/cancellation и создаёт самостоятельные окна ожидания. Подписка `/api/event` также использует отдельный timeout=5. Просроченный request deadline не запрещает предварительный запуск helper.
> - **Исправление:** передавать остаток общего бюджета через startup и subscribe; проверять отмену между ожиданиями; cancellation/deadline не превращать в ServeUnavailable с последующим fallback.
> - **Критерий проверки:** при истёкшем deadline helper не запускается; отмена на handshake/listener/subscribe обнаруживается в пределах REQ-008, процессы и слоты освобождаются.

### F-011
- origin: realist · R1 · realist-F-006
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AMEND, realist=AUTHOR, visionary=AGREE
- dissent: skeptic d1 «AMEND F-011 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:181, bridges/opencode-zen-bridge/server.py:2844; fix=запускать родительский дренаж stderr helper сразу после » → teamlead/cycle-5/debate/d1/skeptic.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:181, bridges/opencode-zen-bridge/server.py:2844; fix=запускать родительский дренаж stderr helper сразу после `Popen`, до handshake/listener, как foll (teamlead/cycle-5/debate/d1/skeptic.md)
- text (дословно, R1 realist):
> **F-006 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:181`, `bridges/opencode-zen-bridge/server.py:2826`, `bridges/opencode-zen-bridge/server.py:2844`.
> - **Правило:** управление ресурсами и независающий I/O, feature.md §2, T-LIFE/v1.
> - **Evidence:** helper синхронно пересылает вывод serve в собственный stderr, но родитель начинает читать его только после проверки listener. Вывод до bind, превышающий суммарную ёмкость пайпов, блокирует helper и serve; listener не появляется.
> - **Исправление:** запускать родительский stderr-дренаж сразу после Popen, до handshake/listener; хранить ограниченный объём диагностических байтов.
> - **Критерий проверки:** fake serve пишет несколько MiB до открытия порта, включая вариант без LF; startup завершается, память ограничена, после cleanup нет оставшихся процессов и FD. Текущий тест на 70 KB эту границу не доказывает.

### F-012
- origin: realist · R1 · realist-F-007
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=AGREE
- dissent: skeptic d1 «DISPUTE F-012 класс: duplicate_of:F-005 — контр-evidence: bridges/opencode-zen-bridge/server.py:3595 — те же cleanup-места interrupt/DELETE и та же суть, что F-005: суммарный худший случай уборк» → teamlead/cycle-5/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-007 [pre-existing] — priority=blocking**
>
> - **locations:** `bridges/opencode-zen-bridge/server.py:2604`, `bridges/opencode-zen-bridge/server.py:2610`, `bridges/opencode-zen-bridge/server.py:3595`, `bridges/opencode-zen-bridge/server.py:3607`.
> - **Правило:** FU-006; feature.md §2 — timeout на каждом шаге, включая cleanup; REQ-008.
> - **Evidence:** deadline проверяется перед `getresponse()`/`read1()`. Чтение HTTP-заголовков и chunk framing внутри этих операций может выполнять несколько recv. Капающие байты чаще socket timeout удерживают операцию дольше абсолютного deadline; до `lease.cleanup()` исполнение не доходит.
> - **Исправление:** обеспечить жёсткое прерывание текущей HTTP-фазы по deadline; в cleanup не читать ненужное тело ответа. Сохранить ограниченный путь к killpg независимо от поведения control API.
> - **Критерий проверки:** interrupt/DELETE с капающими заголовками и chunked framing не удерживают cleanup за установленным бюджетом; группа исчезает в пределах AC-011, слот возвращается.

### F-013
- origin: visionary · R1 · visionary-F-001
- rev: 1
- priority: blocking
- status: WITHDRAWN
- outcome: withdrawn
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AGREE, visionary=WITHDRAW
- dissent: skeptic d1 «DISPUTE F-013 класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:3552 — та же ветка `etype == "error"`, тот же инвариант RW-001 и те же потребители server.py:5619/» → teamlead/cycle-5/debate/d1/skeptic.md ; visionary d1 «WITHDRAW F-013 ARG: realist/R1 «сохранять подтверждение доставки на всех выходах»; проверил: bridges/opencode-zen-bridge/server.py:3553,3565,5619,6911 — снимаю отдельную запись как дубль F-001, к» → teamlead/cycle-5/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-001
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3552, bridges/opencode-zen-bridge/server.py:3556, bridges/opencode-zen-bridge/server.py:5564, bridges/opencode-zen-bridge/server.py:5618, bridges/opencode-zen-bridge/server.py:5619, bridges/opencode-zen-bridge/server.py:6846, bridges/opencode-zen-bridge/server.py:6911
> rule: FALLBACK_DECISION_TABLE phase=PROMPT_RESPONSE (server.py:1701-1708), инвариант RW-001 «headers_at запрещает run», REQ-009
> evidence: `elif etype == "error": result["error"] = payload; result["transient_error"] = _is_transient_stream_error(payload); result["terminal"] = "failed"; break` — флага `delivered` нет. Классификатор (server.py:976-980) возвращает True для 429, `status is None` и `status >= 500`. Снаружи: `_delivered_err = _delivered_now or bool(collected_texts)` и `if not _delivered_err and not force_serve: return False` с `transport_history=["serve","run"]`. JSON: `if not _delivered_j and not force_serve: return False`.
> expected: на `etype=="error"` выставить `result["delivered"]` из `prompt_status["headers_at"]` или уже отданных токенов/вызовов; при истине — `serve_retry` или терминальная ошибка, без второго upstream-prompt.
> check: `TRANSPORT=auto`, заголовки prompt 200, затем `session.execution.failed` (free-limit/timeout/eof) до токена, stream и JSON: `Run.execute` и `_spawn_with_stdin` не вызываются, `record_success()` не вызывается, `allow_retry` не больше одного раза на попытку.

### F-014
- origin: visionary · R1 · visionary-F-002
- rev: 1
- priority: blocking
- status: WITHDRAWN
- outcome: withdrawn
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AGREE, visionary=WITHDRAW
- dissent: skeptic d1 «DISPUTE F-014 класс: duplicate_of:F-002 — контр-evidence: bridges/opencode-zen-bridge/server.py:6235 — тот же `max(FIRST_TOKEN_TIMEOUT_S, 120.0)` и правило REQ-007/AC-010, что F-002.» → teamlead/cycle-5/debate/d1/skeptic.md ; visionary d1 «WITHDRAW F-014 ARG: skeptic/R1 «убрать пол 120.0, сравнивать ровно с FIRST_TOKEN_TIMEOUT_S»; проверил: bridges/opencode-zen-bridge/server.py:6235 — снимаю отдельную запись как дубль F-002. Дефект» → teamlead/cycle-5/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-002
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:6231, bridges/opencode-zen-bridge/server.py:6235
> rule: REQ-007, AC-010
> evidence: `now_s - attempt_start > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)` при дефолте `FIRST_TOKEN_TIMEOUT_S=60`. Serve-путь сравнивает с сырым порогом (server.py:3314-3316). На legacy SSE событие без токена живёт до 120 с, сколько бы ни стояло в окружении ниже 120.
> expected: сравнение с `float(FIRST_TOKEN_TIMEOUT_S)` на обоих транспортах, либо отдельная переменная с явным именем и тем же дефолтом, что в конверте.
> check: `FIRST_TOKEN_TIMEOUT_S=60`, legacy SSE, есть событие и нет токена: `exit_reason=first_token_timeout` около 60 с плюс допуск, не около 120 с.

### F-015
- origin: visionary · R1 · visionary-F-003
- rev: 1
- priority: blocking
- status: WITHDRAWN
- outcome: withdrawn
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AGREE, visionary=WITHDRAW
- dissent: skeptic d1 «DISPUTE F-015 класс: duplicate_of:F-008 — контр-evidence: bridges/opencode-zen-bridge/server.py:5094 — тот же отсутствующий watchdog в `Run.execute` для non-stream JSON и те же REQ-006/REQ-007, » → teamlead/cycle-5/debate/d1/skeptic.md ; visionary d1 «WITHDRAW F-015 ARG: realist/R1 «добавить три watchdog и их классификацию/учёт повторов в JSON legacy»; проверил: bridges/opencode-zen-bridge/server.py:5094,5104,5118 — снимаю отдельную запись как» → teamlead/cycle-5/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-003
> priority: blocking
> criterion: ПОЛНОТА
> locations: bridges/opencode-zen-bridge/server.py:5094, bridges/opencode-zen-bridge/server.py:5100, bridges/opencode-zen-bridge/server.py:5147
> rule: REQ-006, REQ-007, AC-008, AC-009, AC-010
> evidence: [pre-existing] `on_idle` в `Run.execute` ставит только `state = "client_gone"` и зовёт `_stop_proc`. Ветка `etype == "error"` (server.py:5147) не классифицирует молчание. Часы первого события, первого токена и паузы в этом методе отсутствуют; их копии живут в SSE (server.py:6225-6246) и в `_serve_one_attempt` (server.py:3305-3324). Non-stream JSON упирается в `TIMEOUT_S=1800`.
> expected: те же три причины выхода и убийство группы внутри общего потолка спавнов на JSON-прогоне `opencode run`.
> check: `stream:false`, фейковый CLI без stdout: завершение с `first_event_timeout` за порог плюс единицы секунд, процессов группы нет. Аналогично первый токен и пауза после токена.

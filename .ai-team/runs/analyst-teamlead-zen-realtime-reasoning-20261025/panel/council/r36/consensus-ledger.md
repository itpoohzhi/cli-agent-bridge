# Консенсус-леджер Совета Тимлидов по коду (`consensus-ledger.md` / `findings-ledger.md`) — Cycle 4, run `analyst-teamlead-zen-realtime-reasoning-20261025`

- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=25fcec1e8fb299ee624f57e742f6b88fe3c44700babf3ca4176179c737870568`)
- **Раунд R1 (`panel/council/r30`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r30/panel-proof.json sha256=5934173fa7eb3af2f9e52cbb60399bcdfc821e01814b3d3c5035c525d24b4ca5 verify_panel_proof exit=0`
- **Раунд D1 (`panel/council/r36`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r36/panel-proof.json sha256=d0d7b5122be31df99c4d783de308ea1a92af561cf292c68d24b3d880aa8f4bef verify_panel_proof exit=0`
- **Всего находок R1:** `13` (`F-001` .. `F-013`), новых находок в D1 (`r2_late`): `0`.
- **Итог дебатов D1:** `AGREED blocking` = `4` (`RW-001..RW-004`), `AGREED non-blocking` = `7` (`FU-001..FU-007`), `WITHDRAWN / REJECTED_BY_MAJORITY excluded` = `2` (`1` межсудейский дубль `duplicate_of:F-001` и `1` отклонённый `out_of_scope`). Открытых `OPEN` или `CONFLICT` нет (`0`).

## Сводная таблица статусов (`F-001` .. `F-013`)

| ID | skeptic | realist | visionary | priority | status |
|---|---|---|---|---|---|
| F-001 | AGREE | AUTHOR | AGREE | blocking | AGREED |
| F-002 | AGREE | AUTHOR | AGREE | non-blocking | AGREED |
| F-003 | DISPUTE | DISPUTE | WITHDRAW | withdrawn | WITHDRAWN |
| F-004 | AMEND | AMEND | AUTHOR | non-blocking | AGREED |
| F-005 | AGREE | AGREE | AUTHOR | blocking | AGREED |
| F-006 | AMEND | AMEND | AUTHOR | non-blocking | AGREED |
| F-007 | AMEND | AMEND | AMEND | blocking | AGREED |
| F-008 | AGREE | AGREE | AUTHOR | non-blocking | AGREED |
| F-009 | AMEND | AMEND | AUTHOR | non-blocking | AGREED |
| F-010 | AMEND | AMEND | AUTHOR | non-blocking | AGREED |
| F-011 | AMEND | AGREE | AUTHOR | blocking | AGREED |
| F-012 | DISPUTE | AMEND | AUTHOR | non-blocking | AGREED |
| F-013 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |

---

## Карточки находок (`F-001` .. `F-013`)

### F-001
- origin: realist · R1 · realist-F-001
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
> F-001
> priority: blocking
> criterion: КОРРЕКТНОСТЬ
> locations: bridges/opencode-zen-bridge/server.py:3265-3266, bridges/opencode-zen-bridge/server.py:3330-3333, bridges/opencode-zen-bridge/server.py:3341-3345, bridges/opencode-zen-bridge/server.py:5512-5517, bridges/opencode-zen-bridge/server.py:5577-5584, bridges/opencode-zen-bridge/server.py:6779-6790, bridges/opencode-zen-bridge/server.py:6840-6845
> rule: RW-001 action; FALLBACK_DECISION_TABLE phase=DELIVERED event «first_event_timeout20s after headers, no valid execution SSE» action=serve_retry; REQ-009 (повторный запуск — второе исполнение prompt)
> evidence: `prompt_status["headers_at"] = time.monotonic()` пишется в `_on_headers` до чтения тела. Дальше `_delivered_now = bool(result["texts"] or result["reasonings"] or result["native_calls"])` и `result["delivered"] = _delivered_now` для 429/5xx. При ошибке тела: `if isinstance(_prompt_err, str) and not (result["texts"] or result["reasonings"] or result["native_calls"]): raise ServeUnavailable(...)`. В SSE: `except ServeUnavailable` → `if not force_serve and not delivered_any[0]: return False`. В JSON тот же `return False` по `_j_delivered`. Развилки `prompt_status` 429/5xx в SSE и JSON тоже возвращают `False` в `run`, когда `delivered` ложен.
> expected: Если `headers_at` уже есть, не бросать `ServeUnavailable` и не ставить `delivered=False`. Вернуть результат с `delivered=True` и `exit_reason` для serve-retry (429/5xx — тот же барьер). `STATUS_INITIAL` барьер не ставит. Исключение, которое всё же вышло после подтверждённого prompt, не переводит запрос на `run` и не вызывает `record_success()`.
> check: Режим `auto`, заголовки ответа prompt получены, затем обрыв тела или HTTP 429/5xx до первого токена модели. `Run.execute` и `_spawn_with_stdin` не вызываются. Клиент получает один serve-retry или терминальную SSE/502 ошибку. `record_success()` не вызывается.

### F-002
- origin: realist · R1 · realist-F-002
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=AGREE, realist=AUTHOR, visionary=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> F-002
> priority: non-blocking
> criterion: ПОЛНОТА
> locations: bridges/opencode-zen-bridge/server.py:6463-6464
> rule: FU-010 (non-blocking follow-up)
> evidence: На legacy-пути после watchdog `emit_synthetic(f"[мост] Повтор попытки {attempts.total_spawns + 1}/{attempts.max_total}…\n")` вызывается без `thinking_enabled`. На serve разделитель гейтится `thinking` (`server.py:5492`), периодические статусы keepalive тоже (`server.py:6228`).
> expected: Эмиссию разделителя на legacy-retry обернуть тем же `thinking_enabled`, что и `STATUS_WAITING` / `STATUS_CONTINUATION`.
> check: `reasoning_effort=off` на пути `run`, watchdog даёт retry: в SSE нет строки «Повтор попытки». MUST это не ломает; в агрегирующий FAIL не входит.

### F-003
- origin: visionary · R1 · visionary-F-001
- rev: 1
- priority: blocking
- status: WITHDRAWN
- outcome: withdrawn
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=WITHDRAW
- dissent: skeptic d1 «DISPUTE F-003 класс: duplicate_of:F-001 — контр-evidence: bridges/opencode-zen-bridge/server.py:3345 — та же ветка `_prompt_err`, тот же root cause (потеря `headers_at` в исключении) и тот же фи» → teamlead/cycle-4/debate/d1/skeptic.md ; realist d1 «DISPUTE F-003 класс: duplicate_of:F-001 — контр-evidence: `server.py:3265-3266`, `server.py:3330-3333`, `server.py:3341-3345`, `server.py:5512-5517`, `server.py:5577-5584`, `server.py:6779-6790`» → teamlead/cycle-4/debate/d1/realist.md ; visionary d1 «WITHDRAW F-003 ARG: realist/R1 «Ошибка транспорта prompt поднимает `ServeUnavailable`, не глядя на `headers_at`»; проверил: `bridges/opencode-zen-bridge/server.py:3341-3345,5512-5517,6779-6790` —» → teamlead/cycle-4/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-001 — priority=blocking; RW-001 закрыт частично.
>    - locations: `bridges/opencode-zen-bridge/server.py:2604`, `:3266`, `:3284`, `:3345`, `:5514`, `:6789`.
>    - Правило: RW-001; монотонный барьер доставки; запрет fallback после подтверждения prompt.
>    - Evidence: `headers_at` записывается своевременно, но ветка `_prompt_err` выбрасывает `ServeUnavailable`. Исключение не переносит этот признак наружу. Обработчики SSE и JSON проверяют модельные данные и прежний барьер, а не подтверждение текущего prompt.
>    - Сценарий: prompt принят, получены HTTP 200 headers, затем соединение сброшено при чтении тела до появления модельных дельт. Ошибка возникает раньше first-event watchdog; разрешается fallback в run.
>    - Исправление: передавать подтверждение доставки в общий контекст попыток непосредственно при получении заголовков либо сохранять его в типизированном результате исключения.
>    - Проверка: HTTP-фейк подтверждает prompt и обрывает тело; в SSE и JSON `Run` не запускается, повтор остаётся serve либо завершается явной ошибкой.

### F-004
- origin: visionary · R1 · visionary-F-002
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AMEND, visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-004 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3266,bridges/opencode-zen-bridge/server.py:3280; fix=публиковать HTTP-статус в `on_headers` одновременно с `h» → teamlead/cycle-4/debate/d1/skeptic.md ; realist d1 «AMEND F-004 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2604-2606, bridges/opencode-zen-bridge/server.py:3265-3266, bridges/opencode-zen-bridge/server.py:3280, bridg» → teamlead/cycle-4/debate/d1/realist.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3266,bridges/opencode-zen-bridge/server.py:3280; fix=публиковать HTTP-статус в `on_headers` одновременно с `headers_at` и классифицировать 400/401/40 (teamlead/cycle-4/debate/d1/skeptic.md) ; realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2604-2606, bridges/opencode-zen-bridge/server.py:3265-3266, bridges/opencode-zen-bridge/server.py:3280, bridges/opencode-zen-bridge/server.py:3302-33 (teamlead/cycle-4/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-002 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/server.py:2604`, `:2608`, `:2617`, `:3266`, `:3280`, `:3306`, `:3324`.
>    - Правило: FALLBACK_DECISION_TABLE — HTTP 400/401/403/404/422 завершаются fail-closed без протокольного retry и инкремента ServeHealth.
>    - Evidence: callback заголовков передаёт только время. `prompt_status["status"] = st` выполняется после полного тела ответа. Если сервер уже прислал 401, но задерживает тело, основной цикл видит только `headers_at` и может вернуть `first_event_timeout`.
>    - Исправление: публиковать HTTP-статус одновременно с заголовками; терминальные 4xx классифицировать до чтения тела.
>    - Проверка: каждый из 400/401/403/404/422 с незавершающимся телом даёт один терминальный отказ, без run, serve-retry и изменения ServeHealth.

### F-005
- origin: visionary · R1 · visionary-F-003
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-003 — priority=blocking; RW-002 закрыт частично.
>    - locations: `bridges/opencode-zen-bridge/server.py:5948`, `:6121`, `:6173`, `:6179`, `:6242`.
>    - Правило: REQ-004, AC-005 — первая видимая реакция не позднее 1,0 с.
>    - Evidence: защитный таймер отменяется сразу после лимитера, а следующий срок статуса считается заново: `attempt_start + FIRST_STATUS_DELAY_S`.
>    - Сценарий: gate/limiter задержал старт примерно на 0,5 с, затем молчащий процесс запущен до срабатывания таймера 0,65 с. Таймер отменён; следующий статус возможен лишь примерно через 1,15 с плюс интервал опроса.
>    - Исправление: сохранять защитный таймер до первого видимого чанка либо использовать единый абсолютный срок первого статуса.
>    - Проверка: задержки старта по обе стороны 0,65 с, включая 0,4–0,6 с; первый статус ≤1,0 с, начальный статус ровно один.

### F-006
- origin: visionary · R1 · visionary-F-004
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AMEND, visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-006 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6855,bridges/opencode-zen-bridge/server.py:6713; fix=пропускать transient-части через ToolCallParser/очистку » → teamlead/cycle-4/debate/d1/skeptic.md ; realist d1 «AMEND F-006 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6855-6856, bridges/opencode-zen-bridge/server.py:6870, bridges/opencode-zen-bridge/server.py:6930, bridges/op» → teamlead/cycle-4/debate/d1/realist.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6855,bridges/opencode-zen-bridge/server.py:6713; fix=пропускать transient-части через ToolCallParser/очистку и обновлять `_prior_content` перед recov (teamlead/cycle-4/debate/d1/skeptic.md) ; realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6855-6856, bridges/opencode-zen-bridge/server.py:6870, bridges/opencode-zen-bridge/server.py:6930, bridges/opencode-zen-bridge/server.py:6954; fix=пе (teamlead/cycle-4/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-004 — priority=blocking; FU-002 закрыт частично.
>    - locations: `bridges/opencode-zen-bridge/server.py:6713`, `:6855`, `:6870`, `:6897`, `:6900`, `:6907`, `:6930`, `:6954`.
>    - Правило: REQ-010/REQ-011; сохранение канонической обработки текста и инструментов при recovery.
>    - Evidence: transient-ветка выполняет `contents.extend(texts)` до `ToolCallParser` и очистки блоков. Перед `continue` она также не обновляет `_prior_content`; это делается только в других retry-ветках.
>    - Сценарий: первая попытка отдаёт преамбулу и transient error; recovery повторяет преамбулу перед корректным tool-call. JSON сохраняет обе копии. Сырой фрагмент tool-блока из неуспешной попытки также попадает непосредственно в накопитель `content`.
>    - Исправление: пропускать частичные попытки через ту же нормализацию, что успешные; перед recovery фиксировать нормализованный префикс для дедупликации.
>    - Проверка: преамбула встречается один раз; сырой tool-блок отсутствует в `content`; итоговые вызовы инструментов совпадают с SSE.

### F-007
- origin: visionary · R1 · visionary-F-005
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AMEND, visionary=AMEND
- dissent: skeptic d1 «AMEND F-007 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6463; fix=обернуть legacy-разделитель в `thinking_enabled`, как в F-002 — причина: panel-rework-brief FU-010 » → teamlead/cycle-4/debate/d1/skeptic.md ; realist d1 «AMEND F-007 priority=blocking; locations=bridges/opencode-zen-bridge/server.py:6529, bridges/opencode-zen-bridge/server.py:6560-6569; fix=перед повтором unmapped и incomplete на legacy `run` э» → teamlead/cycle-4/debate/d1/realist.md ; visionary d1 «AMEND F-007 priority=blocking; locations=`bridges/opencode-zen-bridge/server.py:6463-6464,6500,6521,6545,6554`; fix=централизовать разделитель legacy-повтора после уже выданного reasoning пере» → teamlead/cycle-4/debate/d1/visionary.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6463; fix=обернуть legacy-разделитель в `thinking_enabled`, как в F-002 — причина: panel-rework-brief FU-010 — этот же дефект прошлый цикл закрывал к (teamlead/cycle-4/debate/d1/skeptic.md) ; realist d1: priority=blocking; locations=bridges/opencode-zen-bridge/server.py:6529, bridges/opencode-zen-bridge/server.py:6560-6569; fix=перед повтором unmapped и incomplete на legacy `run` эмитить ровно одну строку `[мост] Повтор  (teamlead/cycle-4/debate/d1/realist.md) ; visionary d1: priority=blocking; locations=`bridges/opencode-zen-bridge/server.py:6463-6464,6500,6521,6545,6554`; fix=централизовать разделитель legacy-повтора после уже выданного reasoning перед фактическим следующим запуском; провер (teamlead/cycle-4/debate/d1/visionary.md)
- text (дословно, R1 visionary):
> F-005 — priority=blocking; [pre-existing], FU-010 закрыт частично.
>    - locations: `bridges/opencode-zen-bridge/server.py:6183`, `:6463`, `:6500`, `:6521`, `:6545`, `:6554`.
>    - Правило: REQ-009, AC-014; согласованное отключение синтетических reasoning-статусов.
>    - Evidence: watchdog-retry вызывает `emit_synthetic` без проверки `thinking_enabled`. Ветви unmapped/incomplete recovery не имеют соответствующей единой точки разделителя после уже отданного reasoning.
>    - Исправление: централизовать legacy-разделитель перед фактической повторной попыткой; учитывать наличие предыдущего reasoning и thinking-флаг.
>    - Проверка: watchdog, unmapped и incomplete recovery — ровно один разделитель между попытками при thinking on; ноль синтетических разделителей при thinking off.

### F-008
- origin: visionary · R1 · visionary-F-006
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AGREE, realist=AGREE, visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-006 — priority=non-blocking; недостаточная доказательность AC-002.
>    - locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:151`, `:597`, `:613`, `:616`.
>    - Правило: AC-002; `testing.md` — независимый эталон измеряемого свойства.
>    - Evidence: оракул измеряет интервалы клиентских чанков и сравнивает их с независимой отметкой завершения апстрима. Он не сопоставляет время прихода каждой upstream-дельты с её записью клиенту. Постоянная задержка всех дельт более 250 мс может сохранить проверяемые интервалы.
>    - Исправление: добавить идентификаторы дельт и независимые отметки upstream-arrival/client-receive; до этого обозначать AC-002 как INCONCLUSIVE.
>    - Проверка: искусственная задержка пересылки 300 мс делает проверку AC-002 красной.

### F-009
- origin: visionary · R1 · visionary-F-007
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AMEND, visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-009 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5581,bridges/opencode-zen-bridge/server.py:6844; fix=явно решить в FALLBACK_DECISION_TABLE, списывает ли смен» → teamlead/cycle-4/debate/d1/skeptic.md ; realist d1 «AMEND F-009 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3330-3333, bridges/opencode-zen-bridge/server.py:5577-5584, bridges/opencode-zen-bridge/server.py:5597-5605, » → teamlead/cycle-4/debate/d1/realist.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5581,bridges/opencode-zen-bridge/server.py:6844; fix=явно решить в FALLBACK_DECISION_TABLE, списывает ли смена транспорта Retry Budget, и при положит (teamlead/cycle-4/debate/d1/skeptic.md) ; realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3330-3333, bridges/opencode-zen-bridge/server.py:5577-5584, bridges/opencode-zen-bridge/server.py:5597-5605, bridges/opencode-zen-bridge/server.py:68 (teamlead/cycle-4/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-007 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/server.py:5578`, `:5581`, `:5600`, `:5605`, `:6087`, `:6096`, `:6841`, `:6844`, `:6854`, `:6858`, `:7058`, `:7063`.
>    - Правило: REQ-009; R-BULK-I2 — общий Token-Bucket Retry Budget; сохранение Full Jitter.
>    - Evidence: после prompt 429/5xx либо transient provider error ветка до доставки возвращает `False` раньше `attempts.allow_retry()`. Внешний handler запускает run, проверяя потолок запусков, но не разрешение на повтор.
>    - Следствие: при пустом Retry Budget запрос всё равно получает дополнительный upstream-запуск. Такой fallback не отражается как retry; это видно и в приложенном логе с `total_spawns=2 retries=0`.
>    - Исправление: перед сменой транспорта после upstream-отказа провести повтор через общий admission с бюджетом, breaker и jitter. Локальный pre-upstream отказ отделить от provider failure.
>    - Проверка: при исчерпанном бюджете 429/5xx/transient failure не запускают run; при доступном бюджете списывается один retry и применяется один backoff.

### F-010
- origin: visionary · R1 · visionary-F-008
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AMEND, visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-010 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3574,bridges/opencode-zen-bridge/server.py:2799; fix=дать cleanup-вызовам абсолютный deadline и лимит тела, а» → teamlead/cycle-4/debate/d1/skeptic.md ; realist d1 «AMEND F-010 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2585-2588, bridges/opencode-zen-bridge/server.py:3574-3590, bridges/opencode-zen-bridge/server.py:3606; fix=н» → teamlead/cycle-4/debate/d1/realist.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3574,bridges/opencode-zen-bridge/server.py:2799; fix=дать cleanup-вызовам абсолютный deadline и лимит тела, а `_spawn_serve` — остаток дедлайна запро (teamlead/cycle-4/debate/d1/skeptic.md) ; realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2585-2588, bridges/opencode-zen-bridge/server.py:3574-3590, bridges/opencode-zen-bridge/server.py:3606; fix=на interrupt/DELETE передать абсолютный п (teamlead/cycle-4/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-008 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/server.py:2585`, `:2608`, `:2648`, `:2731`, `:2799`, `:2825`, `:3101`, `:3196`, `:3204`, `:3574`, `:3585`, `:3606`.
>    - Правило: `feature.md` — ограничение каждого звена I/O, включая cleanup; R-BULK-I1; REQ-008/AC-011.
>    - Evidence: `_spawn_serve` не принимает deadline/cancellation; handshake и listener получают новые локальные сроки. SSE subscribe использует отдельный timeout=5. Cleanup вызывает `_serve_http` без абсолютного deadline, а при `deadline is None` каждая порция тела получает заново полный timeout.
>    - Следствие: медленно поступающее незавершающееся тело cleanup-ответа может удержать выполнение до `lease.cleanup()` неограниченно долго. Короткий socket timeout не ограничивает длительность всей операции. Предельный setup также не обеспечивает детекцию отключения клиента ≤5 с.
>    - Исправление: передать deadline/cancellation через setup; назначить отдельный абсолютный cleanup deadline и лимит тела; гарантировать переход к остановке группы после исчерпания cleanup-бюджета.
>    - Проверка: задержанные handshake/listener/SSE headers, истёкший deadline до spawn и непрерывно капающее cleanup-тело; после отмены группа отсутствует в пределах AC-011.

### F-011
- origin: visionary · R1 · visionary-F-009
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AGREE, visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-011 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3502; fix=при завершении native-вызова обновлять `last_token_at = time.monotonic()` рядом с установкой `first» → teamlead/cycle-4/debate/d1/skeptic.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3502; fix=при завершении native-вызова обновлять `last_token_at = time.monotonic()` рядом с установкой `first_token_at` — причина: bridges/opencode-z (teamlead/cycle-4/debate/d1/skeptic.md)
- text (дословно, R1 visionary):
> F-009 — priority=blocking; [pre-existing], сопутствующий FU-007.
>    - locations: `bridges/opencode-zen-bridge/server.py:3296`, `:3316`, `:3486`, `:3502`.
>    - Правило: REQ-007/AC-009 — stall отсчитывается от последнего полезного события.
>    - Evidence: готовый native-вызов устанавливает `first_token_at`, но не обновляет `last_token_at`. До первого токена tool-input delta также не обновляет этот срок.
>    - Сценарий: при first-token timeout больше stall timeout native-вызов завершается после длительной подготовки аргументов. Следующая итерация немедленно объявляет stall, хотя полезный вызов только что получен.
>    - Исправление: обновлять последнюю активность при завершённом native-вызове и явно определить семантику активности аргументов.
>    - Проверка: управляемые часы, поздний первый native-вызов, затем паузы STALL−ε/ST­­ALL+ε; преждевременного stall нет.

### F-012
- origin: visionary · R1 · visionary-F-010
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AMEND, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-012 класс: invalid — контр-evidence: bridges/opencode-zen-bridge/tests/test_step_interruption.py (весь существующий набор из 17 модулей на `unittest.TestCase`) и `verification-surface.» → teamlead/cycle-4/debate/d1/skeptic.md ; realist d1 «AMEND F-012 priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394; fix=не переписывать модуль на pytest-функции в этом цикле; оставить follow-up — п» → teamlead/cycle-4/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394; fix=не переписывать модуль на pytest-функции в этом цикле; оставить follow-up — причина: файл действительно наследует `un (teamlead/cycle-4/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-010 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394`, `:556`, `:1303`, `:1592`, `:1663`, `:1761`, `:1867`.
>    - Правило: приложенный `agents/testing.md` — использовать pytest, не использовать `unittest.TestCase`, `setUp`, `tearDown`.
>    - Evidence: пять базовых классов прямо наследуют `unittest.TestCase`; ещё два наследуют `_AttemptCase`. Это новый файл кандидата, а не неизменяемый legacy-модуль.
>    - Исправление: перевести новый модуль на pytest-функции/фикстуры с сохранением всех assertions, FakeServe и процессных сценариев. Async/Litestar-зависимости для этого не нужны.
>    - Проверка: все нынешние сценарии и подслучаи сохранены; полный pytest и проверка порядка зелёные.

### F-013
- origin: visionary · R1 · visionary-F-011
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-013 класс: out_of_scope — контр-evidence: `verification-surface.json` L3 «Repo has no pytest heavy/measured markers (entire component suite runs in L2)» и REQ-020/AC-026 — сокетное изм» → teamlead/cycle-4/debate/d1/skeptic.md ; realist d1 «DISPUTE F-013 класс: invalid — контр-evidence: REQ-020 / AC-026 и FU-006 — сокетный red→green обязан жить в обычном наборе: на `origin/dev` он красный (`red_sensitivity_rc=1`), на кандидате зелё» → teamlead/cycle-4/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-011 — priority=blocking; [pre-existing].
>    - locations: `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:394`, `:556`, `:1303`, `:1663`, `:1761`, `:1867`.
>    - Правило: `testing.md` §7.2 и Serial Lane — временные/ресурсные измерения выносятся в `measured`/`heavy`; unit-оракулы переходов используют управляемые часы.
>    - Evidence: обычные тесты проверяют реальные сроки первого статуса, интервалы SSE, wall-clock watchdog и окна SIGTERM/SIGKILL. В новом модуле отсутствует выделение этих сценариев в measured/heavy-контур.
>    - Исправление: маркировать измерительные и ресурсные сценарии, запускать их последовательно; логические проверки дедлайнов и автоматов дополнить FakeClock. Сокетный AC-026 сохранить как отдельное реальное измерение.
>    - Проверка: обычный параллельный набор не содержит измерений latency/cleanup; отдельный serial lane действительно исполняется и имеет приложенный лог.

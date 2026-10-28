# Консенсус-леджер Совета Тимлидов по коду (`consensus-ledger.md` / `findings-ledger.md`) — Cycle 3, run `analyst-teamlead-zen-realtime-reasoning-20261025`

- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=674edaca247fa44fb9639f81a52dbfe62235889400a00a99eec3f6c321db2b82`)
- **Раунд R1 (`panel/council/r25`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r25/panel-proof.json sha256=17afed5226245529b0b6799092d0b72a91a2b6fc1756678932b7e5f62569342c verify_panel_proof exit=0`
- **Раунд D1 (`panel/council/r29`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r29/panel-proof.json sha256=a0c74367f7ba0804ca04d1b3b2bee29301586bbc4fcf3984cca9b257ebfd76d5 verify_panel_proof exit=0`
- **Всего находок R1:** `30` (`F-001` .. `F-030`), новых находок в D1 (`r2_late`): `0`.
- **Итог дебатов D1:** `AGREED blocking` = `8` (`RW-001..RW-008`), `AGREED non-blocking` = `15` (`FU-001..FU-015`), `REJECTED_BY_MAJORITY excluded` = `7` (`6` межсудейских дублей `duplicate_of` + `1` отклонённый `out_of_scope`). Открытых `OPEN` или `CONFLICT` нет (`0`).

## Сводная таблица статусов (`F-001` .. `F-030`)

| ID | skeptic | realist | visionary | priority | status |
|---|---|---|---|---|---|
| F-001 | AMEND | AGREE | AGREE | blocking | AGREED |
| F-002 | AUTHOR | AGREE | AMEND | blocking | AGREED |
| F-003 | AUTHOR | AMEND | AMEND | non-blocking | AGREED |
| F-004 | AUTHOR | AGREE | AGREE | blocking | AGREED |
| F-005 | AUTHOR | AMEND | AMEND | non-blocking | AGREED |
| F-006 | AUTHOR | AMEND | AMEND | non-blocking | AGREED |
| F-007 | AUTHOR | AGREE | AGREE | blocking | AGREED |
| F-008 | AUTHOR | AMEND | AGREE | blocking | AGREED |
| F-009 | AUTHOR | AMEND | AMEND | non-blocking | AGREED |
| F-010 | AUTHOR | AGREE | AGREE | blocking | AGREED |
| F-011 | AUTHOR | AMEND | AGREE | blocking | AGREED |
| F-012 | AUTHOR | AMEND | AMEND | non-blocking | AGREED |
| F-013 | AUTHOR | AMEND | AMEND | non-blocking | AGREED |
| F-014 | AUTHOR | AMEND | AGREE | blocking | AGREED |
| F-015 | AUTHOR | DISPUTE | DISPUTE | excluded | REJECTED_BY_MAJORITY |
| F-016 | AUTHOR | AGREE | AGREE | non-blocking | AGREED |
| F-017 | AUTHOR | AGREE | AGREE | non-blocking | AGREED |
| F-018 | DISPUTE | AUTHOR | AGREE | excluded | REJECTED_BY_MAJORITY |
| F-019 | DISPUTE | AMEND | AUTHOR | non-blocking | AGREED |
| F-020 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-021 | DISPUTE | AGREE | AUTHOR | non-blocking | AGREED |
| F-022 | AGREE | AGREE | AUTHOR | non-blocking | AGREED |
| F-023 | DISPUTE | AGREE | AUTHOR | non-blocking | AGREED |
| F-024 | AMEND | AGREE | AUTHOR | non-blocking | AGREED |
| F-025 | DISPUTE | AGREE | AUTHOR | non-blocking | AGREED |
| F-026 | DISPUTE | AMEND | AUTHOR | non-blocking | AGREED |
| F-027 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-028 | DISPUTE | AGREE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-029 | DISPUTE | DISPUTE | AUTHOR | excluded | REJECTED_BY_MAJORITY |
| F-030 | AMEND | AGREE | AUTHOR | excluded | REJECTED_BY_MAJORITY |

---

## Карточки находок (`F-001` .. `F-030`)

### F-001
- origin: skeptic · R1 · skeptic-F-001
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AMEND, realist=AGREE, visionary=AGREE
- dissent: skeptic d1 «AMEND F-001 priority=blocking; locations=`server.py:2406`, `:2407`, `:3062`, `:3112`, `:5198`, `:5206`, `:5229`, `:5294`, `:6407`, `:6431`, `:6486`; fix=фиксировать prompt headers непосредстве» → teamlead/cycle-3/debate/d1/skeptic.md
- owner_decision: —
- amendments: skeptic d1: priority=blocking; locations=`server.py:2406`, `:2407`, `:3062`, `:3112`, `:5198`, `:5206`, `:5229`, `:5294`, `:6407`, `:6431`, `:6486`; fix=фиксировать prompt headers непосредственно после `getresponse()`, сохранять общ (teamlead/cycle-3/debate/d1/skeptic.md)
- text (дословно, R1 skeptic):
> **F-001 — барьер доставки остаётся немонотонным.**
>    - priority: blocking.
>    - locations: `server.py:2406`, `server.py:2407`, `server.py:3062`, `server.py:3112`, `server.py:5198`, `server.py:5229`, `server.py:5294`, `server.py:6431`, `server.py:6486`.
>    - Правило: RW-009, RW-012, REQ-009, `FALLBACK_DECISION_TABLE`.
>    - Evidence: `headers_at` устанавливается после завершения `resp.read()`. Для prompt HTTP 429/5xx доставка определяется наличием модельного вывода. Обработчики `except ServeUnavailable` возвращают fallback без проверки предыдущей доставки.
>    - Контрсценарий: первая попытка отдала reasoning и завершилась stall; следующая падает при запуске с `ServeUnavailable`; `auto` переходит на run вопреки установленному барьеру. Отдельно: prompt-заголовки получены, тело задержано — код продолжает считать доставку неподтверждённой.
>    - Исправление: фиксировать получение заголовков непосредственно после `getresponse()`; хранить общий latch запроса; проверять его во всех возвратах fallback, включая исключения и отказ limiter; после барьера использовать serve-retry либо явную ошибку.
>    - Проверка: сценарии «reasoning → retry → ServeUnavailable», «headers → задержанное тело» и «429/5xx без токенов» в SSE и JSON; отсутствие запрещённого run-fallback.

### F-002
- origin: skeptic · R1 · skeptic-F-002
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AGREE, visionary=AMEND
- dissent: visionary d1 «AMEND F-002 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5808-5814; fix=держать защитный таймер до первого видимого чанка либо отдавать статус во время ожидания spawn» → teamlead/cycle-3/debate/d1/visionary.md
- owner_decision: —
- amendments: visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5808-5814; fix=держать защитный таймер до первого видимого чанка либо отдавать статус во время ожидания spawn_limiter, не дублируя STATUS_INITIAL — п (teamlead/cycle-3/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> **F-002 — первый статус теряется при ожидании spawn-limiter.**
>    - priority: blocking.
>    - locations: `server.py:5808`, `server.py:5811`, `server.py:5812`.
>    - Правило: RW-017, REQ-004, AC-005.
>    - Evidence: `status_timer.cancel()` выполняется до `spawn_limiter.acquire()`, тогда как `send_keepalive` начнёт работать только после запуска процесса.
>    - Контрсценарий: startup gate получен сразу, limiter задержал запуск больше секунды — непустого reasoning-чанка за установленный срок нет. Ограничение прямо признано в `coder.json`.
>    - Исправление: сохранять таймер до первого видимого вывода либо непрерывно обслуживать статусы во всех ожиданиях.
>    - Проверка: занятый limiter при свободном startup gate; первый статус ≤1 секунды, ровно один `STATUS_INITIAL`.

### F-003
- origin: skeptic · R1 · skeptic-F-003
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AMEND
- dissent: realist d1 «AMEND F-003 priority=non-blocking; locations=server.py:2395, 2910, 2935, 2956, 2984, 3059; fix=пробросить абсолютный deadline и проверку `is_client_gone` в фазы SPAWN/READY/CREATE/SUBSCRIBE — » → teamlead/cycle-3/debate/d1/realist.md ; visionary d1 «AMEND F-003 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2387,bridges/opencode-zen-bridge/server.py:3059,bridges/opencode-zen-bridge/server.py:3079; fix=follow-up: пр» → teamlead/cycle-3/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=server.py:2395, 2910, 2935, 2956, 2984, 3059; fix=пробросить абсолютный deadline и проверку `is_client_gone` в фазы SPAWN/READY/CREATE/SUBSCRIBE — причина: каждая фаза ограничена таймауто (teamlead/cycle-3/debate/d1/realist.md) ; visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:2387,bridges/opencode-zen-bridge/server.py:3059,bridges/opencode-zen-bridge/server.py:3079; fix=follow-up: прокинуть остаток deadline в control/promp (teamlead/cycle-3/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> **F-003 [pre-existing] — общий deadline/cancellation не охватывает всю цепочку I/O.**
>    - priority: blocking.
>    - locations: `server.py:2395`, `server.py:2407`, `server.py:2910`, `server.py:2935`, `server.py:2956`, `server.py:2984`, `server.py:3059`, `server.py:3080`, `server.py:3347`, `server.py:3357`, `server.py:3368`.
>    - Правило: `feature.md §2`; R-BULK-I1, T-LIFE/v1, REQ-008.
>    - Evidence: setup использует фиксированные 3/5 секунд, `_ctrl_http` повторяет вызов; проверка клиента начинается лишь в основном цикле. Prompt имеет отдельный timeout 65 секунд. `resp.read()` ограничен socket timeout, но не абсолютным сроком всей операции.
>    - Контрсценарий: два последовательных трёхсекундных control-вызова при уже отключившемся клиенте превышают требование обнаружения ≤5 секунд. Ответ, поступающий малыми порциями, способен продлевать чтение тела. Проверка только `_ServeLease.cleanup` не доказывает общий бюджет отмены.
>    - Исправление: передавать единый абсолютный deadline и cancellation во все фазы; ограничивать операции остатком бюджета; обеспечить закрытие prompt-соединения и подтверждённое завершение reader/prompt-потоков; рассчитывать cleanup целиком.
>    - Проверка: отключение и истечение срока на SPAWN/READY/CREATE/SUBSCRIBE/PROMPT/CLEANUP; после срока новые операции не стартуют, группа исчезает в AC-011.

### F-004
- origin: skeptic · R1 · skeptic-F-004
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
> **F-004 — RW-004 не закрывает ошибку создания state-dir.**
>    - priority: blocking.
>    - locations: `server.py:1738`, `server.py:2891`, `server.py:2897`, `server.py:2929`.
>    - Правило: RW-004; REQ-008; штатная классификация локального отказа.
>    - Evidence: `tempfile.mkdtemp()` вызывается в `_serve_env` до `_spawn_serve` и до защищённого блока попытки.
>    - Следствие: ENOSPC/EACCES выходит как обычный `OSError`, а не `ServeUnavailable`; SSE может классифицировать локальный отказ как уход клиента вместо предусмотренного fallback.
>    - Исправление: включить создание окружения/state-dir в единую транзакцию запуска, переводить локальные ошибки в `ServeUnavailable`, освобождать уже выделенные ресурсы.
>    - Проверка: fault injection на `mkdtemp`, генерацию окружения, pipe и Popen; штатная ошибка/fallback, отсутствие FD/port/state leftovers.

### F-005
- origin: skeptic · R1 · skeptic-F-005
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AMEND
- dissent: realist d1 «AMEND F-005 priority=non-blocking; locations=server.py:6477-6528; fix=на ветке transient_error дописывать `texts` и `reasonings` неуспешной попытки в `contents` перед построением recovery-пром» → teamlead/cycle-3/debate/d1/realist.md ; visionary d1 «AMEND F-005 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6477,bridges/opencode-zen-bridge/server.py:6514,bridges/opencode-zen-bridge/server.py:6527; fix=до continue п» → teamlead/cycle-3/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=server.py:6477-6528; fix=на ветке transient_error дописывать `texts` и `reasonings` неуспешной попытки в `contents` перед построением recovery-промпта — причина: в JSON-режиме клиенту нич (teamlead/cycle-3/debate/d1/realist.md) ; visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6477,bridges/opencode-zen-bridge/server.py:6514,bridges/opencode-zen-bridge/server.py:6527; fix=до continue переносить texts/reasonings текущей попыт (teamlead/cycle-3/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> **F-005 [pre-existing] — JSON-повторы теряют частичный вывод.**
>    - priority: blocking.
>    - locations: `server.py:6477`, `server.py:6499`, `server.py:6514`, `server.py:6527`, `server.py:6528`.
>    - Правило: REQ-011; `testing.md`, полнота результата и recovery.
>    - Evidence: retry выполняется до переноса `reasonings` и `texts` в итоговые накопители; recovery-prompt получает `"".join(contents)`, не содержащий текста текущей неуспешной попытки.
>    - Контрсценарий: попытка вернула полезный префикс и stall; следующая продолжила ответ — итоговый JSON содержит только продолжение. Reasoning неуспешной попытки также исчезает.
>    - Исправление: определить единый порядок фиксации частичного результата, dedup и построения recovery-prompt до перехода к повтору.
>    - Проверка: текст и reasoning первой попытки сохраняются согласно контракту; продолжение не теряется и не дублируется при watchdog и transient-error.

### F-006
- origin: skeptic · R1 · skeptic-F-006
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AMEND
- dissent: realist d1 «AMEND F-006 priority=non-blocking; locations=server.py:5298-5351; fix=начислять `result["usage"]` до ветвления, как в JSON — причина: REQ-014 имеет приоритет SHOULD, а AC-019 проверяет usage о» → teamlead/cycle-3/debate/d1/realist.md ; visionary d1 «AMEND F-006 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5298,bridges/opencode-zen-bridge/server.py:5319,bridges/opencode-zen-bridge/server.py:5333,bridges/opencode-z» → teamlead/cycle-3/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=server.py:5298-5351; fix=начислять `result["usage"]` до ветвления, как в JSON — причина: REQ-014 имеет приоритет SHOULD, а AC-019 проверяет usage одной попытки. На ветке prompt_status `st (teamlead/cycle-3/debate/d1/realist.md) ; visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5298,bridges/opencode-zen-bridge/server.py:5319,bridges/opencode-zen-bridge/server.py:5333,bridges/opencode-zen-bridge/server.py:5351; fix=начислять  (teamlead/cycle-3/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> **F-006 [pre-existing] — SSE теряет usage некоторых повторов.**
>    - priority: blocking.
>    - locations: `server.py:5298`, `server.py:5319`, `server.py:5333`, `server.py:5351`.
>    - Правило: REQ-014, AC-019; паритет SSE/JSON.
>    - Evidence: usage суммируется на успехе и watchdog-retry, но переходы по prompt-status и transient-error выполняются до общей аккумуляции.
>    - Контрсценарий: попытка получила `step.ended` с tokens, затем transient-error; recovery успешен — финальный SSE usage не включает первую попытку. JSON уже начисляет эти tokens до классификации.
>    - Исправление: начислять usage каждой завершившейся попытки ровно один раз до ветвления.
>    - Проверка: одинаковые попытки дают одинаковые итоговые input/output/cached/reasoning в SSE и JSON для всех retry-причин.

### F-007
- origin: skeptic · R1 · skeptic-F-007
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
> **F-007 [pre-existing] — native serve-путь обходит существующий адаптер схем инструментов.**
>    - priority: blocking.
>    - locations: `server.py:2832`, `server.py:2849`, `server.py:2852`; эталон — `server.py:686`, `server.py:707`, `server.py:725`.
>    - Правило: REQ-011, REQ-012, AC-017; `code.md`, DRY и единая семантика.
>    - Evidence: `_native_call_as_dsh` выбирает имя/алиас и возвращает исходные `args`. Legacy `_native_to_tool_calls` дополнительно вызывает `_fit_args`, преобразует list/ls и разворачивает multiedit.
>    - Следствие: одинаковое событие через run и serve даёт разные аргументы либо разный набор вызовов. Совпадение имени инструмента не доказывает совместимость его JSON-схемы.
>    - Исправление: использовать общий существующий преобразователь native-вызовов; сохранить проверку обязательных полей, переименование аргументов и one-to-many преобразования.
>    - Проверка: одинаковые native-фикстуры read/edit/list/multiedit дают одинаковые `tool_calls` в run/serve, SSE/JSON.

### F-008
- origin: skeptic · R1 · skeptic-F-008
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE
- dissent: realist d1 «AMEND F-008 priority=non-blocking; locations=server.py:1115-1119; fix=перед выходом по `poll() is not None` проверять живость группы через `killpg(pgid, 0)` — причина: `_stop_proc` не входит в» → teamlead/cycle-3/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=server.py:1115-1119; fix=перед выходом по `poll() is not None` проверять живость группы через `killpg(pgid, 0)` — причина: `_stop_proc` не входит в дельту, в candidate.diff нет ханка в эт (teamlead/cycle-3/debate/d1/realist.md)
- text (дословно, R1 skeptic):
> **F-008 [pre-existing] — legacy cleanup считает смерть лидера смертью группы.**
>    - priority: blocking.
>    - locations: `server.py:1115`, `server.py:1116`, `server.py:1118`, `server.py:1119`.
>    - Правило: REQ-008, AC-011, T-LIFE/v1.
>    - Evidence: `_stop_proc` немедленно возвращается, если `proc.poll() is not None`; после TERM ожидает только непосредственный процесс.
>    - Контрсценарий: run-лидер завершился, потомок продолжает жить и держать stdout. Watchdog вызывает `_stop_proc`, который ничего не завершает.
>    - Исправление: проверять живость принадлежащей запросу группы независимо от лидера; после TERM подтверждать смерть группы и эскалировать при оставшихся членах.
>    - Проверка: лидер завершился раньше потомка, потомок игнорирует TERM; группа отсутствует в установленный срок.

### F-009
- origin: skeptic · R1 · skeptic-F-009
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AMEND
- dissent: realist d1 «AMEND F-009 priority=non-blocking; locations=server.py:4732, 4824; fix=передать idle-callback и `is_client_gone` в `Run._execute_once` — причина: JSON/run-путь в дельте не менялся, а потолок 1» → teamlead/cycle-3/debate/d1/realist.md ; visionary d1 «AMEND F-009 priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:4732,bridges/opencode-zen-bridge/server.py:4824; fix=follow-up: idle-callback и client-gone в JSON/run, не тр» → teamlead/cycle-3/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=server.py:4732, 4824; fix=передать idle-callback и `is_client_gone` в `Run._execute_once` — причина: JSON/run-путь в дельте не менялся, а потолок 1800 с существует давно. REQ-006/007 не о (teamlead/cycle-3/debate/d1/realist.md) ; visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:4732,bridges/opencode-zen-bridge/server.py:4824; fix=follow-up: idle-callback и client-gone в JSON/run, не трогая замороженный `_run_env` — причина:  (teamlead/cycle-3/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> **F-009 [pre-existing] — watchdog не распространяется на запасной JSON/run-путь.**
>    - priority: blocking.
>    - locations: `server.py:4732`, `server.py:4824`.
>    - Правило: REQ-006, REQ-007, REQ-008; переключаемый legacy-путь REQ-003.
>    - Evidence: `Run._execute_once()` вызывает `self.feed.lines(deadline)` без idle callback; туда не передаётся детектор отключения клиента.
>    - Следствие: `stream:false` с `TRANSPORT=run` либо после fallback продолжает ждать молчащий CLI до общего `TIMEOUT_S`, несмотря на новые пороги первого события/токена.
>    - Исправление: подключить общий watchdog и cancellation-контекст к JSON/run, не меняя замороженный `_run_env`.
>    - Проверка: молчание, отсутствие токена, stall и отключение клиента в JSON/run завершаются по соответствующим порогам.

### F-010
- origin: skeptic · R1 · skeptic-F-010
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
> **F-010 [pre-existing] — повреждённая кодировка dynamic config прерывает запрос.**
>    - priority: blocking.
>    - locations: `server.py:1700`, `server.py:1704`.
>    - Правило: REQ-003; fail-open конфигурации, `python-standards.md §3`.
>    - Evidence: `read_text("utf-8")` может выбросить `UnicodeDecodeError`, обработчик ловит только `OSError`.
>    - Следствие: повреждённый файл не приводит к `enabled=False`, как повреждённый JSON; исключение выходит из выбора транспорта.
>    - Исправление: обрабатывать ошибку декодирования как недействительный конфиг, выбирать run и выдавать безопасную диагностику.
>    - Проверка: невалидные UTF-8 байты при работающем Server не рвут запрос; последующее исправление файла восстанавливает переключение.

### F-011
- origin: skeptic · R1 · skeptic-F-011
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE
- dissent: realist d1 «AMEND F-011 priority=non-blocking; locations=server.py:823, 5127, 5145; fix=инкрементальная очистка с удержанием хвоста либо вынос в адаптер — причина: в serve `result["texts"]` пополняется сы» → teamlead/cycle-3/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=server.py:823, 5127, 5145; fix=инкрементальная очистка с удержанием хвоста либо вынос в адаптер — причина: в serve `result["texts"]` пополняется сырой дельтой до `on_text`, поэтому `_inco (teamlead/cycle-3/debate/d1/realist.md)
- text (дословно, R1 skeptic):
> **F-011 [pre-existing] — очистка interruption-маркеров зависит от границы дельты.**
>    - priority: blocking.
>    - locations: `server.py:823`, `server.py:5127`, `server.py:5145`.
>    - Правило: REQ-011; совместимость накопленного потокового пути.
>    - Evidence: `_strip_interrupted` применяет регулярное выражение к каждой отдельной дельте.
>    - Контрсценарий: `"I was interrupted right "` и `"before making tool calls."` поступают раздельно — маркер уходит клиенту целиком, хотя при подаче одним блоком удаляется.
>    - Исправление: сделать очистку инкрементальной с ограниченным удержанием потенциального префикса либо выполнять её на уровне адаптера, сохраняющего границы логического сообщения.
>    - Проверка: перебрать все разрезы обоих `_INTERRUPTED_RE`-маркеров; результат совпадает с обработкой целого сообщения.

### F-012
- origin: skeptic · R1 · skeptic-F-012
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AMEND
- dissent: realist d1 «AMEND F-012 priority=non-blocking; locations=tests/test_realtime_reasoning.py:567-583; fix=заменить `<1.0` на `<0.5` (FakeServe шлёт каждые 0.12 с), оставить проверку разброса ≥0.15 с и порядо» → teamlead/cycle-3/debate/d1/realist.md ; visionary d1 «AMEND F-012 priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:545,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:580; fix=follow-up: н» → teamlead/cycle-3/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=tests/test_realtime_reasoning.py:567-583; fix=заменить `<1.0` на `<0.5` (FakeServe шлёт каждые 0.12 с), оставить проверку разброса ≥0.15 с и порядок "reasoning раньше content" — причина:  (teamlead/cycle-3/debate/d1/realist.md) ; visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:545,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:580; fix=follow-up: независимые метки конца апстрима, интерва (teamlead/cycle-3/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> **F-012 [pre-existing] — временной оракул не доказывает заявленные пределы и полноту.**
>    - priority: blocking.
>    - locations: `tests/test_realtime_reasoning.py:545`, `tests/test_realtime_reasoning.py:567`, `tests/test_realtime_reasoning.py:580`, `tests/test_realtime_reasoning.py:582`, `tests/test_realtime_reasoning.py:583`.
>    - Правило: REQ-001, REQ-020, AC-001, AC-002, AC-026; `feature.md`, независимый сигнал полноты.
>    - Evidence: проверяется интервал `<1.0`, хотя AC-001 требует `<0.5`; накладные расходы ≤250 мс не измеряются. `upstream_end_t = elapsed` — конец клиентского чтения, а не независимая отметка завершения апстрима.
>    - RED действительно имеет `rc=1`, но конкретный AC-026 на baseline падает в `setUp` из-за отсутствия `DYNAMIC_CONFIG_PATH`, до временных assertions. Это подтверждает несовместимость старой реализации с новым API теста, но не чувствительность к буферизации.
>    - Исправление: добавить независимые отметки отправки/завершения FakeServe, проверять оба численных предела и полный набор дельт; отдельно показать RED на реализации, которая принимает те же события, но буферизует их. Для AC-016 перенести матрицу interruption-сценариев на serve, а не ссылаться на зелёный legacy-модуль.
>    - Проверка: намеренная буферизация и превышение каждого порога отдельно делают соответствующий тест красным.

### F-013
- origin: skeptic · R1 · skeptic-F-013
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AMEND
- dissent: realist d1 «AMEND F-013 priority=non-blocking; locations=tests/test_realtime_reasoning.py:424, 567, 1401; fix=маркеры measured/heavy вынести отдельной задачей — причина: в репозитории таких маркеров нет, » → teamlead/cycle-3/debate/d1/realist.md ; visionary d1 «AMEND F-013 priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:424,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:1401; fix=follow-up: » → teamlead/cycle-3/debate/d1/visionary.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=tests/test_realtime_reasoning.py:424, 567, 1401; fix=маркеры measured/heavy вынести отдельной задачей — причина: в репозитории таких маркеров нет, а `pyproject.toml` вне конверта (`allowe (teamlead/cycle-3/debate/d1/realist.md) ; visionary d1: priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:424,bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:1401; fix=follow-up: автомат на FakeClock, wall-clock под mar (teamlead/cycle-3/debate/d1/visionary.md)
- text (дословно, R1 skeptic):
> **F-013 [pre-existing] — измерительные проверки находятся в обычном компонентном контуре.**
>    - priority: blocking.
>    - locations: `tests/test_realtime_reasoning.py:424`, `tests/test_realtime_reasoning.py:437`, `tests/test_realtime_reasoning.py:567`, `tests/test_realtime_reasoning.py:687`, `tests/test_realtime_reasoning.py:875`, `tests/test_realtime_reasoning.py:1281`, `tests/test_realtime_reasoning.py:1342`, `tests/test_realtime_reasoning.py:1401`.
>    - Правило: `testing.md §7.2`, Serial Lane.
>    - Evidence: реальные `monotonic`/sleep-проверки имеют жёсткие пороги и запускаются обычным полным suite без measured/heavy-маркеров.
>    - Риск: нагрузка машины превращает проверку корректности в зависимость от планировщика; особенно узкое окно cleanup 3.9–4.9 секунды.
>    - Исправление: переходы автоматов и бюджеты проверять FakeClock; реальные измерения выделить в measured/heavy и запускать отдельным последовательным гейтом.
>    - Проверка: обычный suite детерминирован; отдельный измерительный гейт сохраняет AC-001/002/005/011/026 и включён в приёмку.

### F-014
- origin: skeptic · R1 · skeptic-F-014
- rev: 2
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=AMEND, visionary=AGREE
- dissent: realist d1 «AMEND F-014 priority=non-blocking; locations=server.py:5347, 6523; fix=пропускать `err.get('message')` через `_clean_err` до `_error_payload` — причина: сообщение уходит только клиенту на 127.» → teamlead/cycle-3/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=server.py:5347, 6523; fix=пропускать `err.get('message')` через `_clean_err` до `_error_payload` — причина: сообщение уходит только клиенту на 127.0.0.1 и в `_log` не пишется. AC-020 пров (teamlead/cycle-3/debate/d1/realist.md)
- text (дословно, R1 skeptic):
> **F-014 [pre-existing] — новые upstream-ошибки обходят маскирование.**
>    - priority: blocking.
>    - locations: `server.py:5347`, `server.py:6523`; принимающий helper — `server.py:1928`.
>    - Правило: REQ-015; `security.md`, защита секретов; существующее `_mask_secrets`.
>    - Evidence: `err.get('message')` напрямую вставляется в `_error_payload`; этот helper сохраняет message без очистки.
>    - Риск: upstream transport/provider exception с токеном или credential попадает в клиентский SSE/JSON и далее может сохраняться потребителем. Legacy stderr-путь предварительно использует `_clean_err`.
>    - Исправление: применять единый redaction к новым внешним диагностическим сообщениям до ответа/логирования; не передавать сырые исключения.
>    - Проверка: sentinel-ключ, serve-password и proxy credentials в provider error отсутствуют в SSE, JSON и логах.

### F-015
- origin: skeptic · R1 · skeptic-F-015
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 skeptic=AUTHOR; D1 skeptic=AUTHOR, realist=DISPUTE, visionary=DISPUTE
- dissent: realist d1 «DISPUTE F-015 класс: out_of_scope — контр-evidence: tests/test_cli_failure.py:267 не входит в три файла конверта (candidate-manifest.json); ResourceWarning возникает в прямом вызове `Run(...)._e» → teamlead/cycle-3/debate/d1/realist.md ; visionary d1 «DISPUTE F-015 класс: out_of_scope — контр-evidence: `tests/test_cli_failure.py:267` вне трёх файлов `allowed_envelope_changes` — два `ResourceWarning` в VER-002 есть, L2 `rc=0`. Forbidden Scope » → teamlead/cycle-3/debate/d1/visionary.md
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> **F-015 [pre-existing] — независимый лог уже содержит ResourceWarning.**
>    - priority: non-blocking, вне разрешённого тестового файла.
>    - locations: `tests/test_cli_failure.py:267`.
>    - Правило: testing.md, гарантированная очистка ресурсов.
>    - Evidence: `l2-green-ver002-unittest.log` содержит два `ResourceWarning: unclosed file` для прямого вызова `Run(...)._execute_once()`.
>    - Исправление: отдельным follow-up гарантировать `Run.close()` в тесте либо контекстное владение объектом.
>    - Проверка: соответствующий сценарий проходит без ResourceWarning. Это замечание не отменяет зафиксированный `rc=0` полного L2.

### F-016
- origin: skeptic · R1 · skeptic-F-016
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
> **F-016 [pre-existing] — FU-004 закрыт не для всех tool-only завершений.**
>    - priority: non-blocking.
>    - locations: `server.py:3284`, `server.py:3307`.
>    - Правило: FU-004, REQ-016.
>    - Evidence: TTFT выставляется при завершении tool lifecycle, но fallback-сборка native-вызова на `step_finish` не устанавливает `first_token_at`/`ttft_ms`.
>    - Исправление: использовать общую точку регистрации первого готового native-вызова и обновлять часы активности.
>    - Проверка: tool input без `called/failed/success`, завершённый через `step.ended`, имеет числовой TTFT в конечном O-EXIT sink.

### F-017
- origin: skeptic · R1 · skeptic-F-017
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
> **F-017 — пояснения подавлений типов исправлены частично.**
>    - priority: non-blocking.
>    - locations: `tests/test_realtime_reasoning.py:324`, `tests/test_realtime_reasoning.py:325`, `tests/test_realtime_reasoning.py:1150`, `tests/test_realtime_reasoning.py:1154`.
>    - Правило: FU-009; `python-standards.md §1`, запрет подавлений без конкретного объяснения.
>    - Evidence: комментарии про «динамический JSON ответа моста» используются также для сужения bytes и результатов `patch.start()/stop()`.
>    - Исправление: описать конкретное несоответствие typeshed/динамического значения для каждого подавления.
>    - Проверка: причина соответствует подавляемому правилу и выражению; диагностик нового файла по-прежнему 0.

### F-018
- origin: realist · R1 · realist-F-001
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 realist=AUTHOR; D1 skeptic=DISPUTE, realist=AUTHOR, visionary=AGREE
- dissent: skeptic d1 «DISPUTE F-018 класс: duplicate_of:F-001 — контр-evidence: `server.py:5198–5201`, `:5229–5234`, `:6407–6409`, `:6431–6434` — подтверждаю дефект: исключение и отказ лимитера допускают fallback без» → teamlead/cycle-3/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> F-001
> priority: blocking
> criteria: КОРРЕКТНОСТЬ, ПОЛНОТА, РИСКИ
> locations: bridges/opencode-zen-bridge/server.py:5198-5201, bridges/opencode-zen-bridge/server.py:5229-5234, bridges/opencode-zen-bridge/server.py:6407-6409, bridges/opencode-zen-bridge/server.py:6431-6434
> rule: RW-009, REQ-009, AC-014
> evidence: Latch ставится только модельным чанком (`delivered_any[0] = True` в `on_reasoning` / `_text_seen`, `server.py:5112-5124` и `:5185-5191`). Возврат результата это учитывает (`_delivered_now` включает `delivered_any[0]`, `:5257-5279`). Исключение и лимитер — нет. SSE-лимитер: `if not _limiter_ok: … if not force_serve: return False` (`:5198-5201`), разделитель на `:5206-5210` уже не исполняется. SSE: `except ServeUnavailable: … if not force_serve: return False` (`:5229-5234`) без чтения `delivered_any`. Те же `return False` в JSON на `:6407-6409` и `:6431-6434`. Сценарий: попытка 1 отдала reasoning и ушла в `stall_timeout` (serve-retry), попытка 2 падает на spawn/ready/create/prompt с `ServeUnavailable` до своих токенов. Клиент уже видел мысль; тот же SSE продолжается через `opencode run` без «[мост] Повтор попытки».
> expected: Если latch уже установлен, не возвращать fallback на `run`: serve-retry или терминальная ошибка, ровно один разделитель, без `record_success()`. Синтетический статус latch не ставит.
> check: Тест с reasoning на попытке 1 и `ServeUnavailable` либо timeout лимитера на попытке 2; нет четвёртого и нет legacy-spawn поверх уже отданного reasoning; один разделитель или `_sse_error`/502.

### F-019
- origin: visionary · R1 · visionary-F-01
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AMEND, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-019 класс: invalid — контр-evidence: REQ-007 прямо задаёт настраиваемый watchdog первого токена с рабочим порогом 60 секунд; `server.py:5979–6008` различает событие и токен. Максимальн» → teamlead/cycle-3/debate/d1/skeptic.md ; realist d1 «AMEND F-019 priority=non-blocking; locations=server.py:send_keepalive (проверка `first_token_timeout`, `FIRST_TOKEN_TIMEOUT_S`); fix=для legacy-пути дефолт порога выше наблюдаемого максимума (» → teamlead/cycle-3/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=server.py:send_keepalive (проверка `first_token_timeout`, `FIRST_TOKEN_TIMEOUT_S`); fix=для legacy-пути дефолт порога выше наблюдаемого максимума (например 180 с) либо считать токеном акт (teamlead/cycle-3/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-01 [blocking] КОРРЕКТНОСТЬ / Риски-прод.
> - Locations: `server.py::Handler._stream_sse.send_keepalive` (проверка `first_token_timeout`, `FIRST_TOKEN_TIMEOUT_S=60`); `watchdog_state["first_token_at"]`.
> - Правило: REQ-007, REQ-009, F-17/F-18/F-32, R-BULK-I2.
> - Evidence: legacy `opencode run` отдаёт reasoning и text одним блоком в конце шага (F-17/F-18). Первый «токен» наступает только по окончании всего размышления. Легитимные запросы длятся до 85.65 с (F-32). Порог 60 с от `attempt_start` убьёт такой запрос и потратит до 3 запусков. Путь `run` — default при `REALTIME_SERVE_ENABLED=false`.
> - Fix: на legacy-пути не применять `first_token_timeout` к размышлению. Либо поднять порог до значения выше наблюдаемого максимума, либо считать токеном `step_start` и stdout-активность.
> - Критерий: тест с fake-CLI, молчащим 65 с после `step_start` и затем отдающим ответ, завершается успехом без ретрая.

### F-020
- origin: visionary · R1 · visionary-F-02
- rev: 1
- priority: blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-020 класс: duplicate_of:F-001 — контр-evidence: `server.py:5229–5234`, `:6431–6434` — ветка `ServeUnavailable` действительно обходит общий барьер; это уже F-001 и тот же дефект, что F-» → teamlead/cycle-3/debate/d1/skeptic.md ; realist d1 «DISPUTE F-020 класс: duplicate_of:F-001 — контр-evidence: тот же `except ServeUnavailable → return False` (server.py:5229-5234, 6431-6434), тот же корень и то же исправление (проверять latch до » → teamlead/cycle-3/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-02 [blocking] КОРРЕКТНОСТЬ / Полнота-ветки. RW-009 не закрыт.
> - Locations: `Handler._run_serve_stream_attempts`, `except ServeUnavailable` (ветка `if not force_serve: return False`); `Handler._serve_json_serve` (аналогично); `tests/test_realtime_reasoning.py::test_retry_separator_once_and_delivery_barrier_is_monotonic`.
> - Правило: RW-009, REQ-009/AC-014.
> - Evidence: после доставки `reasoning` или `text` клиенту ветка `ServeUnavailable` на следующей попытке не проверяет `delivered_any[0]` и возвращает `False`. Legacy-цикл стартует заново: `dedup[0]` создаётся только при `incomplete_retry`, поэтому reasoning и text отправляются повторно.
> - Fix: при `delivered_any[0]` не делать fallback на run. Вместо этого вызвать `allow_retry` или отдать SSE-ошибку.
> - Критерий: тест с мок-`_serve_one_attempt`, где 1-я попытка отдаёт reasoning, а 2-я бросает `ServeUnavailable`. Клиент не получает повторного текста и не уходит на run.

### F-021
- origin: visionary · R1 · visionary-F-03
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AGREE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-021 класс: invalid — контр-evidence: REQ-009/AC-014 требуют отдельного разделителя повторов; `server.py:5206–5210`, `:6140–6144` реализуют его отдельно от периодических статусов. В при» → teamlead/cycle-3/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-03 [non-blocking] ПОЛНОТА / Корректность-границы.
> - Locations: `_run_serve_stream_attempts` (`on_status(f"[мост] Повтор попытки …")`); `_stream_sse` (`emit_synthetic(... Повтор попытки ...)`).
> - Evidence: разделитель повтора не зависит от `thinking_enabled`, а статусы ожидания зависят. При `effort=off` после текста клиент получит `reasoning_content` «[мост]…».
> - Fix: гейтить разделитель по `thinking`.
> - Критерий: при `effort=off` в потоке нет `[мост]`.

### F-022
- origin: visionary · R1 · visionary-F-04
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
> F-04 [non-blocking] КОРРЕКТНОСТЬ-границы.
> - Locations: `_serve_one_attempt`, ветка `form.created` (`terminal="cancelled"`); обработчики вызывают `serve_health.record_success()`.
> - Evidence: отмена формы без текста и tool_calls в SSE завершается `finish_reason=stop` с пустым ответом и записывается как успех. JSON-путь даёт 502.
> - Fix: единая политика: ошибка либо явный маркер, `record_success` не вызывать.
> - Критерий: SSE и JSON ведут себя одинаково.

### F-023
- origin: visionary · R1 · visionary-F-05
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AGREE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-023 класс: duplicate_of:F-001 — контр-evidence: `server.py:3112`, `:5294–5298`, `:6486–6490` — расхождение таблицы и обработки prompt HTTP 429/5xx уже включено в F-001 как нарушение ба» → teamlead/cycle-3/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-05 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ / Обработка ошибок.
> - Locations: `FALLBACK_DECISION_TABLE`; алиасы `_find_listener_pid`, `parse_serve_event`, `_dynamic_config_enabled`, `_ToolInputAccumulator`; `test_serve_health_and_fallback_table`.
> - Evidence: таблица не исполняется. Строка «HTTP 429/5xx → serve_retry» расходится с кодом: при отсутствии модельного вывода код уходит в `run`. Тест проверяет только поля таблицы.
> - Fix: сделать таблицу единственным источником решений либо удалить её и мёртвые алиасы. Перевести тест на проверку поведения.

### F-024
- origin: visionary · R1 · visionary-F-06
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AGREE, visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-024 priority=non-blocking; locations=`tests/test_realtime_reasoning.py:1129`, `tests/test_realtime_reasoning.py:1170`; fix=добавить фактическую проверку disable-файла, сигнатуры бинаря» → teamlead/cycle-3/debate/d1/skeptic.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=`tests/test_realtime_reasoning.py:1129`, `tests/test_realtime_reasoning.py:1170`; fix=добавить фактическую проверку disable-файла, сигнатуры бинаря и значения tool-status либо сузить назв (teamlead/cycle-3/debate/d1/skeptic.md)
- text (дословно, R1 visionary):
> F-06 [non-blocking] ПОЛНОТА / покрытие AC.
> - Locations: `tests/test_realtime_reasoning.py` (FakeServe; `test_transport_matrix`, `test_elf_magic_and_tool_status`, `test_helper_argv_validation_and_lease_dir`).
> - Evidence: эндпоинты `permission/{id}/reply` и `form/{id}/cancel` не входят в проверенный F-22. Тест только валидирует собственную подделку. Названия тестов шире assertions.
> - Fix: до heavy-приёмки зафиксировать реальные ответы serve v2.1.2. Усилить указанные тесты.

### F-025
- origin: visionary · R1 · visionary-F-07
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AGREE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-025 класс: invalid — контр-evidence: `server.py:2612–2634`, F-20 и `execution-evidence.md` — вызовы `ps`/`lsof` присутствуют, но отдельного замера их стоимости и нарушения AC из-за них» → teamlead/cycle-3/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-07 [non-blocking] РИСКИ-прод.
> - Locations: `_spawn_serve` (цикл `_lsof_listener_pid` с шагом 50 мс до 3 с), `_parent_lstart`, `_run_serve_helper_cli._group_members`.
> - Evidence: каждая попытка запускает `ps` и `lsof` как подпроцессы. На macOS `lsof` стоит сотни мс и добавляет задержку к TTFT. Это противоречит цели отзывчивости.
> - Fix: ждать handshake без `lsof`-поллинга либо делать один `lsof` после handshake.

### F-026
- origin: visionary · R1 · visionary-F-08
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AMEND, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-026 класс: invalid — контр-evidence: `verification-traceability.md`, строка REQ-003/AC-004, прямо фиксирует `REALTIME_SERVE_ENABLED` в локальном `dynamic_config.json`; `server.py:1761–» → teamlead/cycle-3/debate/d1/skeptic.md ; realist d1 «AMEND F-026 priority=non-blocking; locations=server.py:send_keepalive, `_StdoutFeed.lines(on_idle)`; fix=один env-переключатель для legacy-watchdog и статусов — причина: REQ-003 требует kill-s» → teamlead/cycle-3/debate/d1/realist.md
- owner_decision: —
- amendments: realist d1: priority=non-blocking; locations=server.py:send_keepalive, `_StdoutFeed.lines(on_idle)`; fix=один env-переключатель для legacy-watchdog и статусов — причина: REQ-003 требует kill-switch для нового транспорта (есть: `dyna (teamlead/cycle-3/debate/d1/realist.md)
- text (дословно, R1 visionary):
> F-08 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ (директива про фичефлаги).
> - Locations: `send_keepalive` (watchdog и статусы), `_StdoutFeed.lines(on_idle)`, `O-EXIT/v1`.
> - Evidence: поведение legacy-пути меняется без флага. Отключение только через экстремальные env-пороги. `dynamic_config.json` локальный, не удалённый GigaRC.
> - Применимость GigaRC к автономному stdlib-мосту не могу проверить.
> - Fix: единый флаг и kill-switch для legacy-watchdog и статусов.

### F-027
- origin: visionary · R1 · visionary-F-09
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-027 класс: duplicate_of:F-013 — контр-evidence: `tests/test_realtime_reasoning.py:424`, `:437`, `:567`, `:1401` — те же реальные часы, жёсткие пороги и отсутствие measured/heavy-раздел» → teamlead/cycle-3/debate/d1/skeptic.md ; realist d1 «DISPUTE F-027 класс: duplicate_of:F-013 — контр-evidence: те же wall-clock тесты (`test_lease_cleanup…`, `test_ac026…`, `test_initial_status_before_1s…`) и то же решение; позиции по ним см. F-01» → teamlead/cycle-3/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-09 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ (testing.md, wall-clock).
> - Locations: `test_lease_cleanup_confirms_sigkill_in_separate_window` (`>=3.9`/`<=4.9` с), `test_ac026_realtime_chunks_before_upstream_end`, `test_slow_upstream_gets_initial_status_before_1s`, `test_initial_status_before_1s_under_startup_gate_contention`.
> - Evidence: проверки реального времени flaky в CI. Файл идёт 81 с.
> - Fix: `FakeClock` либо широкие допуски; жёсткие тайминги вынести под marker measured.

### F-028
- origin: visionary · R1 · visionary-F-10
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=AGREE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-028 класс: invalid — контр-evidence: `receipts/code-gate.json`, `VER-004-packet-command` — диапазонное форматирование изменённых ханков является частью утверждённого гейта; замороженны» → teamlead/cycle-3/debate/d1/skeptic.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-10 [non-blocking] РИСКИ-scope-diff.
> - Locations: `server.py` — `Run.execute`, `Run._execute_once`, `_UpstreamBreaker`, `_RequestAttempts.__init__`, `_PrefixDedup.push`, `CATALOG_*`, `_drain_stderr`; `tests/test_step_interruption.py` (`r'''` → `r"""`).
> - Evidence: косметический reformat кода вне задачи (FU-008 требует минимального diff). Растёт blast radius и риск конфликтов.
> - Fix: откатить стилистические правки вне функциональных ханков.

### F-029
- origin: visionary · R1 · visionary-F-11
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=DISPUTE, realist=DISPUTE, visionary=AUTHOR
- dissent: skeptic d1 «DISPUTE F-029 класс: duplicate_of:F-017 — контр-evidence: `tests/test_realtime_reasoning.py:325`, `:1150`, `:1154` — несоответствие пояснений подавляемым выражениям уже зафиксировано F-017. Сохр» → teamlead/cycle-3/debate/d1/skeptic.md ; realist d1 «DISPUTE F-029 класс: duplicate_of:F-017 — контр-evidence: та же проблема неточных причин в комментариях `pyright: ignore` (FU-009), те же места (`_write_exe`, `_Bridge.post_*`, `test_fake_rt_mod» → teamlead/cycle-3/debate/d1/realist.md
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> F-11 [non-blocking] СООТВЕТСТВИЕ КОНТЕКСТУ (FU-009 не закрыт).
> - Locations: `tests/test_realtime_reasoning.py` (`_write_exe`, `_Bridge.post_*`, `test_fake_rt_mode_preset_preserved`: `# pyright: ignore[...] — причина: ответ моста — динамический JSON`).
> - Evidence: одна и та же причина вставлена на несвязанные строки (`path.write_text`, `patcher.start()`).
> - Fix: точные причины либо типизировать вместо ignore.

### F-030
- origin: visionary · R1 · visionary-F-12
- rev: 1
- priority: non-blocking
- status: REJECTED_BY_MAJORITY
- outcome: excluded
- resolved_in: d1
- votes: R1 visionary=AUTHOR; D1 skeptic=AMEND, realist=AGREE, visionary=AUTHOR
- dissent: skeptic d1 «AMEND F-030 priority=non-blocking; locations=`server.py:1738`; fix=в `test_serve_env_sanitized_all_branches` гарантированно удалять созданный `_serve_env` каталог через cleanup/finally — причи» → teamlead/cycle-3/debate/d1/skeptic.md
- owner_decision: —
- amendments: skeptic d1: priority=non-blocking; locations=`server.py:1738`; fix=в `test_serve_env_sanitized_all_branches` гарантированно удалять созданный `_serve_env` каталог через cleanup/finally — причина: тест получает `XDG_STATE_HOME`, но н (teamlead/cycle-3/debate/d1/skeptic.md)
- text (дословно, R1 visionary):
> F-12 [non-blocking] [sweep] КОРРЕКТНОСТЬ-данные.
> - Locations: `_ServeToolState.complete` (статус `completed` при `"called"` в типе события); `_serve_env` (`mkdtemp` в тесте `test_serve_env_sanitized_all_branches` без удаления).
> - Evidence: `session.tool.called` означает вызов, а не выполнение. Тест оставляет `zen-serve-state-*` в tmp.
> - Fix: статус из реального исхода; очистка каталога в тесте.

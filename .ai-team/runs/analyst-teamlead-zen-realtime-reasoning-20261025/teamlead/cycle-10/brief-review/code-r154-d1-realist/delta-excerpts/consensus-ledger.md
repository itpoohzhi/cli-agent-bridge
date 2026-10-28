# Черновой леджер совещания Совета Тимлидов по коду (цикл 10, после R1 r149, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `13` (`F-001..F-013`: `skeptic` `F-001..F-004`, `realist` `F-005..F-013`, `visionary` `нет (0 находок, ACCEPT)`).
- Открытых blocking (`OPEN_BLOCKING`): `12`; открытых non-blocking: `1`.

### F-001
- origin: skeptic · R1 · skeptic-F-001
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-001
> priority: blocking
> критерий: КОРРЕКТНОСТЬ / ПОЛНОТА
> locations: bridges/opencode-zen-bridge/server.py:3563, bridges/opencode-zen-bridge/server.py:4318, bridges/opencode-zen-bridge/server.py:7961, bridges/opencode-zen-bridge/server.py:8121
> правило: REQ-001 (дельты текста уходят клиенту по мере прихода); RW-001 (обработка text в окне дренажа до `session.step.ended`)
> evidence: `if text_cb is not None and not emulate_tools:` после `result["texts"].append(text_value)`. При эмуляции callback не вызывается. SSE передаёт `text_cb=on_text` (`server.py:4318`); JSON собирает ответ из `texts.append` (`server.py:7961`) и `content_raw = "".join(texts)` (`server.py:8121`).
> ожидаемое исправление: отдавать текстовые дельты дренажа клиенту (callback или один сброс после подтверждённого `step.ended`), не оставляя их только во внутреннем `result["texts"]`.
> критерий проверки: SSE и JSON с инструментами; последовательность `tool.called` → text «хвост» → `step.ended`; в ответе есть «хвост» и ровно один tool_call, `finish_reason=tool_calls`.

### F-002
- origin: skeptic · R1 · skeptic-F-002
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-002
> priority: blocking
> критерий: КОРРЕКТНОСТЬ / СООТВЕТСТВИЕ КОНТЕКСТУ
> locations: bridges/opencode-zen-bridge/server.py:1587, bridges/opencode-zen-bridge/server.py:4045, bridges/opencode-zen-bridge/server.py:4051, bridges/opencode-zen-bridge/server.py:4053, bridges/opencode-zen-bridge/server.py:4064
> правило: R-BULK-I1 (обрыв по остатку бюджета; сумма aux ≤ 0.30×SLA); feature.md, таймаут на каждом шаге I/O; FU-002 (`_AUX_IO_BUDGET_S = 54.0` на prompt до заголовков)
> evidence: `_AUX_IO_BUDGET_S = 54.0`. Prompt: `_serve_http(..., timeout=65.0, deadline=attempt_deadline)`. Списание в `finally` после ожидания: `aux.debit_seconds(...)`. Дедлайн фазы не `aux.deadline`.
> ожидаемое исправление: стартовать prompt только при ненулевом остатке aux; `deadline=min(attempt_deadline, aux.deadline(...))`; не проводить ожидание длиннее остатка 54 с.
> критерий проверки: остаток aux = 1 с, зависший prompt; попытка завершается по бюджету быстрее 2 с; `spent_s <= 54`.

### F-003
- origin: skeptic · R1 · skeptic-F-003
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-003
> priority: blocking
> критерий: РЕАЛИЗУЕМОСТЬ / РИСКИ
> locations: bridges/opencode-zen-bridge/server.py:1586, bridges/opencode-zen-bridge/server.py:6251, bridges/opencode-zen-bridge/server.py:7004, bridges/opencode-zen-bridge/server.py:7032, bridges/opencode-zen-bridge/server.py:7038, bridges/opencode-zen-bridge/server.py:7047
> правило: RW-005 / feature.md §2 (конечный таймаут записи клиенту и прерывание зависшего сокета); REQ-008 / AC-011 (группа и слот освобождаются не позже 7 с)
> evidence: `_DOWNSTREAM_WRITE_TIMEOUT_S = 5.0`, `timeout = 300`. До обёртки: `self.wfile.write(first_chunk.encode("utf-8"))`. Таймер: `with wfile_lock:` и `_ = raw_wfile.write(...)`; `except (OSError, ValueError): pass` без `_downstream_client_gone`.
> ожидаемое исправление: обе записи вести через `_LockedWfile`; при ошибке помечать клиента ушедшим и вызывать `abort_socket`. [sweep] role-чанк на `server.py:7004` того же класса, что и статус.
> критерий проверки: клиент перестаёт читать при полном окне до первого токена модели; слот `in_use==0`, группа serve отсутствует быстрее 7 с.

### F-004
- origin: skeptic · R1 · skeptic-F-004
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-004
> priority: blocking
> критерий: КОРРЕКТНОСТЬ / СООТВЕТСТВИЕ КОНТЕКСТУ
> locations: bridges/opencode-zen-bridge/server.py:6194, bridges/opencode-zen-bridge/server.py:6196
> правило: python-standards, запрет 1 (`except Exception: pass` блокирует merge)
> evidence: `try: self._on_client_gone()` / `except Exception: pass` в новом `_LockedWfile._mark_client_gone`.
> ожидаемое исправление: ловить ожидаемый тип сбоя callback, писать `_log` без секретов и всё равно завершать `abort_socket`.
> критерий проверки: callback, бросающий `RuntimeError`, не обрывает abort; в `bridge.log` есть маскированная запись, сокет закрыт.

### F-005
- origin: realist · R1 · realist-F-001
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-001 — priority=blocking**
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3562`, `bridges/opencode-zen-bridge/server.py:3563`.
>    - **Правило:** RW-001; REQ-001; `feature.md`, независимая проверка полноты потокового захвата.
>    - **Evidence:** текст добавляется в `result["texts"]`, но callback вызывается только при `not emulate_tools`. Дренаж после native-вызова при эмуляции работает с `emulate_tools=True`. Поэтому последовательность `tool.called → text.delta → step.ended` сохраняет текст внутри результата попытки, но не передаёт его потребителю. JSON-путь также собирает итоговый текст через переданный callback.
>    - **Исправление:** передавать текст текущего шага через соответствующий parser/callback без утечки tool-тегов и без повторной публикации.
>    - **Критерий проверки:** SSE- и JSON-оракулы указанной последовательности содержат весь обычный текст ровно один раз; SSE доставляет его до завершения апстрима.

### F-006
- origin: realist · R1 · realist-F-002
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-002 [sweep] — priority=blocking**
>    - **locations:** `bridges/opencode-zen-bridge/server.py:6751`, `bridges/opencode-zen-bridge/server.py:8171`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:1593`.
>    - **Правило:** REQ-003, REQ-011; проверка радиуса изменений RW-003.
>    - **Evidence:** обе успешные serve-ветки передают в `_incomplete_step_signal` исходный reasoning. Детектор на `server.py:1062`–`1065` считает interruption-маркер признаком незавершённости независимо от готового текста ответа. Legacy-пути перед классификацией используют очищенную копию. Новый тест сохранности маркеров отключает `STEP_RECOVERY_ENABLED`, поэтому эту разницу не проверяет.
>    - **Исправление:** согласовать recovery-классификацию serve/run, сохранив исходные байты reasoning в ответе.
>    - **Критерий проверки:** при доступных tools, обычном `tool_choice`, готовом приветствии и reasoning с interruption-маркером serve/run дают одинаковое число попыток; reasoning остаётся неизменным. Проверить SSE и JSON при включённом recovery.
>    - **Происхождение:** возможная предыстория JSON-ветки требует классификации оркестратором по дельте цикла; дефект находится в изменённом задачей файле.

### F-007
- origin: realist · R1 · realist-F-003
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-003 — priority=blocking**
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3237`, `bridges/opencode-zen-bridge/server.py:3679`, `bridges/opencode-zen-bridge/server.py:3704`.
>    - **Правило:** RW-004; `HL-ENV-01`.
>    - **Evidence:** состояние удерживает произвольные `name` и ключи `call_id`, но `_serve_tool_state_bytes` считает только `text` и `input`. Например, 128 событий с разными короткими ID и именами по 900 КиБ удержат около 112,5 МиБ имён при нулевом учтённом объёме аргументов. Каждое событие укладывается в предел SSE-строки; лимит 16 МиБ не срабатывает.
>    - **Исправление:** включить все удерживаемые строковые поля в бюджет либо задать отдельные обоснованные пределы ID/name.
>    - **Критерий проверки:** превышение совокупного размера через ID/name в main и drain даёт управляемый protocol error, cleanup и отсутствие опубликованных pending-вызовов.

### F-008
- origin: realist · R1 · realist-F-004
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-004 — priority=blocking**
>    - **locations:** `bridges/opencode-zen-bridge/server.py:3294`, `bridges/opencode-zen-bridge/server.py:3857`, `bridges/opencode-zen-bridge/server.py:3900`, `bridges/opencode-zen-bridge/server.py:4053`, `bridges/opencode-zen-bridge/server.py:4063`.
>    - **Правило:** FU-002; `R-BULK-I1`; `feature.md`, ограничения всей цепочки I/O.
>    - **Evidence:** prompt получает `deadline=attempt_deadline` и timeout 65 секунд; время списывается постфактум. Остаток aux-бюджета не ограничивает эту фазу. Получение execution-события до HTTP-заголовков позволяет ждать первый токен до 60 секунд даже при малом остатке aux. Permission/form control-вызовы также не списываются как aux-фазы; подписка учитывается до заголовков, а не до первого SSE.
>    - **Исправление:** ограничить ожидание prompt-заголовков остатком aux, своевременно завершать и списывать фазу; учесть управляющие вызовы и установленную границу готовности подписки. Модельное чтение после завершения aux-фазы учитывать отдельно.
>    - **Критерий проверки:** управляемые часы и реальные точки вызова HTTP подтверждают общий предел 54 секунды через несколько попыток; при нулевом остатке следующий I/O не начинается. Тест одного класса `_AuxIoBudget` этого не доказывает.

### F-009
- origin: realist · R1 · realist-F-005
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-005 — priority=blocking**
>    - **locations:** `bridges/opencode-zen-bridge/server.py:6997`, `bridges/opencode-zen-bridge/server.py:7004`, `bridges/opencode-zen-bridge/server.py:7038`, `bridges/opencode-zen-bridge/server.py:7046`.
>    - **Правило:** RW-005; `feature.md` §2, timeout на каждом шаге I/O, включая завершение.
>    - **Evidence:** заголовки и role-чанк отправляются до установки `_LockedWfile`. Таймер пишет напрямую через `raw_wfile`, удерживая общий замок, без установки собственного ограниченного timeout. Обязательной независимой отмены этой записи нет. Сокетный тест большого потока проверяет последующие записи через обёртку.
>    - **Исправление:** установить ограничение до первой записи; таймер должен использовать общий механизм ограниченной записи без повторного захвата того же замка. Обеспечить cleanup при его ошибке.
>    - **Критерий проверки:** инъекция блокировки/ошибки отдельно в отправку заголовков, role и initial-status завершается ограниченно; замок и bulkhead-слот освобождаются, группа serve остановлена.
>    - **Классификация цикла:** неполное устранение RW-005; начальные точки записи существовали ранее.

### F-010
- origin: realist · R1 · realist-F-006
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-006 — priority=blocking**
>    - **locations:** `bridges/opencode-zen-bridge/server.py:6196`.
>    - **Правило:** `agents/python-standards.md` §3 и запрет №1; `agents/code.md`, «Возвраты и ошибки».
>    - **Evidence:** новый `_mark_client_gone` содержит `except Exception: pass`.
>    - **Исправление:** убрать подавление либо обработать конкретный ожидаемый сбой с диагностикой, гарантируя shutdown/cleanup независимо от результата callback.
>    - **Критерий проверки:** ошибка callback наблюдаема и не препятствует закрытию сокета и освобождению ресурсов.

### F-011
- origin: realist · R1 · realist-F-007
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-007 [pre-existing] — priority=blocking**
>    - **locations:** `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:412`, `:882`, `:2911`, `:3328`, `:3399`, `:3659`, `:3953`, `:4080`.
>    - **Правило:** `agents/testing.md`: «Не использовать unittest.TestCase, setUp, tearDown».
>    - **Evidence:** новый тестовый модуль построен на шести прямых классах `unittest.TestCase` и двух производных от `_AttemptCase`.
>    - **Исправление:** перенести новый модуль на pytest с фикстурами и гарантированным восстановлением состояния. Сохранить legacy-проверки и полный запуск новых оракулов в L2.
>    - **Критерий проверки:** новый модуль не использует TestCase/setUp/tearDown; все его сценарии собираются и выполняются без сокращения проверок.

### F-012
- origin: realist · R1 · realist-F-008
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-008 [pre-existing] — priority=blocking**
>    - **locations:** `bridges/opencode-zen-bridge/server.py:1829`, `bridges/opencode-zen-bridge/server.py:1907`.
>    - **Правило:** общий канон, «Все фичи — через фичефлаги GigaRC».
>    - **Evidence:** `_read_dynamic_config_enabled` читает локальный JSON; `_select_transport` допускает включение env override и принудительным `TRANSPORT=serve`. В пакете нет связи этого состояния с удалённым GigaRC. Локальная изменяемость сама по себе требование удалённого управления не выполняет.
>    - **Исправление:** подключить источник GigaRC существующим совместимым способом; локальный файл может служить снимком, если доказаны доставка состояния и приоритет удалённого отключения.
>    - **Критерий проверки:** на том же процессе изменение удалённого флага меняет выбор новых запросов без рестарта; отсутствие/некорректность состояния сохраняет прежний путь.

### F-013
- origin: realist · R1 · realist-F-009
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-009 [pre-existing] — priority=non-blocking**
>    - **locations:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-traceability.md:23`, `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/verification-traceability.md:32`.
>    - **Правило:** FU-001; достоверность прослеживаемости.
>    - **Evidence:** первая строка описывает `_map_serve_event` как обработчик `message.part.updated`, хотя реализован протокол `session.*`. Вторая описывает политику как `deny`, хотя default — `ask_reject`.
>    - **Исправление:** указать фактические события, default-политику и различие обработки permission в main/drain.
>    - **Критерий проверки:** каждое указанное событие и поведение однозначно сопоставляется с актуальным символом и оракулом.

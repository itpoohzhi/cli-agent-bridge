> PANEL-NONCE: c5117c81b27ac594
> ARTIFACT-SHA256: bf242262f19cce9383401e2c9988677fa6cdcb64fb5045bf8ab3cb1e44249cfc
> Канон прочитан: AGENTS.md, 430 строк
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
>    WHY=RW-002, RW-003, RW-004 и оракулы RW-001 (form.created, permission reject, классификация 401/429) закрыты регрессиями и зелёным L2. В том же дренаже `_drain_serve_step_usage` при `emulate_tools=True` текст шага пишется только в `result["texts"]` и не уходит в `text_cb`, поэтому клиент SSE и JSON его не получает (`server.py:3563-3564`, потребители `server.py:4318`, `server.py:7961`, `server.py:8121`). Это дыра REQ-001 на пути DSH, где эмуляция инструментов включена. Отклонение RW-001 «успешный reject без interrupt» принято: `test_c10_rw001_drain_permission_reject_continues_and_reasoning_delivered` фиксирует `interrupted=no`, отказ reject по-прежнему fail-closed.
>    СОВЕТЫ (при FAIL): В `_drain_serve_step_usage` передавать текстовые дельты в `text_cb` и при `emulate_tools=True`, либо буферизовать их и один раз отдать клиенту после подтверждённого `session.step.ended`. Добавить SSE- и JSON-оракул: `tool.called` → `session.text.delta` «хвост» → `step.ended`; в ответе есть «хвост» и один `tool_call`.
>
> 2. ПОЛНОТА: VERDICT=FAIL
>    WHY=Именованные оракулы RW-001..RW-005 и FU-002 на своих сценариях есть, L2 их проходит. Ветка текста внутри окна дренажа не покрыта: тесты проверяют reasoning, permission, form и ошибку, а `content` между `tool.called` и `step.ended` теряется. FU-002 измеряет класс `_AuxIoBudget` (20+20+14), но не фазу prompt.
>    СОВЕТЫ (при FAIL): Добавить оракул текста в дренаже (SSE и JSON, `MAX_TOTAL_SPAWNS=1`). Добавить оракул prompt: при остатке aux 1 с `_serve_http` prompt обрывается по `aux.deadline`, `spent_s` не превышает 54.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
>    WHY=Транспорт serve с откатом до барьера доставки сопровождается: stdlib, cleanup группы, слот bulkhead, L2 491 passed. Скрытая цена: защитный статус и первый SSE-чанк пишутся мимо `_LockedWfile`. Таймер держит `wfile_lock` и пишет в `raw_wfile` (`server.py:7032-7046`); сокет ещё с `Handler.timeout = 300` (`server.py:6251`, запись до обёртки `server.py:7004-7005`). Медленный клиент, который уже заполнил окно, удерживает слот и группу serve до 300 с, пока обёрнутые записи ждут тот же замок.
>    СОВЕТЫ (при FAIL): Первый role-чанк и `_initial_status` писать через `_LockedWfile` (таймаут `min(5 с, остаток дедлайна)`). Ошибку записи переводить в `_downstream_client_gone` и `abort_socket`. Оракул: `SO_RCVBUF` меньше status-чанка, клиент читает только заголовки, слот `in_use==0` и группа мертвы быстрее 7 с.
>
> 4. РИСКИ: VERDICT=FAIL
>    WHY=Потеря текста дренажа — потеря данных ответа (F-001). Обход downstream-таймаута — риск продакшена на слоте и AC-011 (F-003). `except Exception: pass` в новом `_mark_client_gone` глушит сбой уведомления (`server.py:6194-6197`, python-standards запрет 1). RED→green и полный L2 при этом зелёные и scope ровно из трёх файлов: это не отменяет три дефекта дельты. Живой слот VER-006/VER-007 не проверялся: по конверту это `DEFERRED_L3`.
>    СОВЕТЫ (при FAIL): Закрыть F-001 и F-003 тестами выше. В `_mark_client_gone` ловить конкретный тип и логировать через `_log` без секретов, затем продолжать abort. Не ослаблять `MAX_TOTAL_SPAWNS=3` и не расширять diff за `bridges/opencode-zen-bridge/`.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=Короткоживущий `opencode serve` с откатом на `opencode run` до барьера доставки — необходимый путь RC-1: CLI v2.1.2 не отдаёт `*.delta`. Объём `server.py` и `tests/test_realtime_reasoning.py` совпадает с матрицей REQ/AC и оракулами цикла 10, а не с переписыванием без нужды. Замечания к архитектуре без нового дефекта в этот критерий не идут.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
>    WHY=Граница задачи соблюдена: три файла манифеста, Google-срезы `_run_env` / `_stream_google_sse` / `_execute_google_once` неизменны, новых runtime-зависимостей нет, публичная форма SSE сохранена, статусы `[мост]` заданы REQ-004/005. Прямой запрет стандарта нарушен: prompt ждёт до `timeout=65.0` с `deadline=attempt_deadline` и списывает aux только после факта (`server.py:4045-4068`) при `_AUX_IO_BUDGET_S = 54.0` (`server.py:1587`). Это R-BULK-I1 и feature.md (таймаут на каждом шаге цепочки, включая prompt до заголовков). Плюс `except Exception: pass` (`server.py:6196`). Пересчёт сида: `seed_hex=7c6a33965f4e229d17395ee75644eba2f2a706b54aca5a066d4c8d765958bb99` (SEED `7c6a3396`) совпадает с манифестом r149; `ranked_order` совпадает: grok-4.7-high, gpt-6.1-sol-high, muse-wonder-full-1.0, gemini-4-argon-high, claude-sonnet-5-5-high.
>    СОВЕТЫ (при FAIL): В `_prompt_worker` передавать `deadline=aux.deadline(attempt_deadline)`, не стартовать поток при `aux.exhausted()`, списывать только фактически ограниченное ожидание. Заменить `except Exception: pass` на конкретное исключение с `_log`.
>
> F-001
> priority: blocking
> критерий: КОРРЕКТНОСТЬ / ПОЛНОТА
> locations: bridges/opencode-zen-bridge/server.py:3563, bridges/opencode-zen-bridge/server.py:4318, bridges/opencode-zen-bridge/server.py:7961, bridges/opencode-zen-bridge/server.py:8121
> правило: REQ-001 (дельты текста уходят клиенту по мере прихода); RW-001 (обработка text в окне дренажа до `session.step.ended`)
> evidence: `if text_cb is not None and not emulate_tools:` после `result["texts"].append(text_value)`. При эмуляции callback не вызывается. SSE передаёт `text_cb=on_text` (`server.py:4318`); JSON собирает ответ из `texts.append` (`server.py:7961`) и `content_raw = "".join(texts)` (`server.py:8121`).
> ожидаемое исправление: отдавать текстовые дельты дренажа клиенту (callback или один сброс после подтверждённого `step.ended`), не оставляя их только во внутреннем `result["texts"]`.
> критерий проверки: SSE и JSON с инструментами; последовательность `tool.called` → text «хвост» → `step.ended`; в ответе есть «хвост» и ровно один tool_call, `finish_reason=tool_calls`.
>
> F-002
> priority: blocking
> критерий: КОРРЕКТНОСТЬ / СООТВЕТСТВИЕ КОНТЕКСТУ
> locations: bridges/opencode-zen-bridge/server.py:1587, bridges/opencode-zen-bridge/server.py:4045, bridges/opencode-zen-bridge/server.py:4051, bridges/opencode-zen-bridge/server.py:4053, bridges/opencode-zen-bridge/server.py:4064
> правило: R-BULK-I1 (обрыв по остатку бюджета; сумма aux ≤ 0.30×SLA); feature.md, таймаут на каждом шаге I/O; FU-002 (`_AUX_IO_BUDGET_S = 54.0` на prompt до заголовков)
> evidence: `_AUX_IO_BUDGET_S = 54.0`. Prompt: `_serve_http(..., timeout=65.0, deadline=attempt_deadline)`. Списание в `finally` после ожидания: `aux.debit_seconds(...)`. Дедлайн фазы не `aux.deadline`.
> ожидаемое исправление: стартовать prompt только при ненулевом остатке aux; `deadline=min(attempt_deadline, aux.deadline(...))`; не проводить ожидание длиннее остатка 54 с.
> критерий проверки: остаток aux = 1 с, зависший prompt; попытка завершается по бюджету быстрее 2 с; `spent_s <= 54`.
>
> F-003
> priority: blocking
> критерий: РЕАЛИЗУЕМОСТЬ / РИСКИ
> locations: bridges/opencode-zen-bridge/server.py:1586, bridges/opencode-zen-bridge/server.py:6251, bridges/opencode-zen-bridge/server.py:7004, bridges/opencode-zen-bridge/server.py:7032, bridges/opencode-zen-bridge/server.py:7038, bridges/opencode-zen-bridge/server.py:7047
> правило: RW-005 / feature.md §2 (конечный таймаут записи клиенту и прерывание зависшего сокета); REQ-008 / AC-011 (группа и слот освобождаются не позже 7 с)
> evidence: `_DOWNSTREAM_WRITE_TIMEOUT_S = 5.0`, `timeout = 300`. До обёртки: `self.wfile.write(first_chunk.encode("utf-8"))`. Таймер: `with wfile_lock:` и `_ = raw_wfile.write(...)`; `except (OSError, ValueError): pass` без `_downstream_client_gone`.
> ожидаемое исправление: обе записи вести через `_LockedWfile`; при ошибке помечать клиента ушедшим и вызывать `abort_socket`. [sweep] role-чанк на `server.py:7004` того же класса, что и статус.
> критерий проверки: клиент перестаёт читать при полном окне до первого токена модели; слот `in_use==0`, группа serve отсутствует быстрее 7 с.
>
> F-004
> priority: blocking
> критерий: КОРРЕКТНОСТЬ / СООТВЕТСТВИЕ КОНТЕКСТУ
> locations: bridges/opencode-zen-bridge/server.py:6194, bridges/opencode-zen-bridge/server.py:6196
> правило: python-standards, запрет 1 (`except Exception: pass` блокирует merge)
> evidence: `try: self._on_client_gone()` / `except Exception: pass` в новом `_LockedWfile._mark_client_gone`.
> ожидаемое исправление: ловить ожидаемый тип сбоя callback, писать `_log` без секретов и всё равно завершать `abort_socket`.
> критерий проверки: callback, бросающий `RuntimeError`, не обрывает abort; в `bridge.log` есть маскированная запись, сокет закрыт.
>
> SUB Корректность/логика: FAIL — evidence (bridges/opencode-zen-bridge/server.py:3563, REQ-001: text_cb пропущен при emulate_tools)
> SUB Корректность/граничные условия: FAIL — evidence (bridges/opencode-zen-bridge/server.py:4051, R-BULK-I1: timeout=65 при бюджете 54 с на server.py:1587)
> SUB Корректность/обработка ошибок: FAIL — evidence (bridges/opencode-zen-bridge/server.py:6196, python-standards запрет 1; server.py:7047 глушит OSError статуса)
> SUB Полнота/покрытие AC: FAIL — evidence (bridges/opencode-zen-bridge/server.py:3563, REQ-001: текст дренажа не входит в content на server.py:8121)
> SUB Полнота/пропущенные ветки: FAIL — evidence (bridges/opencode-zen-bridge/server.py:4045, FU-002: prompt не режется aux.deadline)
> SUB Реализуемость/общее: FAIL — evidence (bridges/opencode-zen-bridge/server.py:7032, RW-005: raw_wfile под wfile_lock при Handler.timeout=300 на server.py:6251)
> SUB Риски/безопасность: PASS — evidence (bridges/opencode-zen-bridge/server.py:1586, пароль serve из secrets, маскирование _mask_secrets; утечки секрета в дельте нет)
> SUB Риски/данные: FAIL — evidence (bridges/opencode-zen-bridge/server.py:3563, текст дренажа не попадает в collected_texts/texts)
> SUB Риски/прод: FAIL — evidence (bridges/opencode-zen-bridge/server.py:7038, запись статуса без _DOWNSTREAM_WRITE_TIMEOUT_S=5.0)
> SUB Риски/regression red→green: PASS — evidence (receipts/l2-red.log rc=1, AC-026 на origin/dev; VER-005 l2-green-ver005-dedicated.log rc=0, 112 passed)
> SUB Риски/Full Suite (L2): PASS — evidence (receipts/code-gate.json status=PASS; l2-green-ver001-pytest.log «491 passed»)
> SUB Риски/scope-diff: PASS — evidence (teamlead/candidate-manifest.json: ровно server.py, tests/test_realtime_reasoning.py, tests/test_step_interruption.py; google_direct_unchanged=True)
> SUB Альтернативы/общее: PASS — evidence (handoff-architect.md RC-1 / F-17: opencode run не отдаёт *.delta; serve — заданный транспорт)
> SUB Соответствие контексту/общее: FAIL — evidence (bridges/opencode-zen-bridge/server.py:4045, R-BULK-I1 и feature.md; server.py:6196, python-standards запрет 1; seed_hex 7c6a33965f4e229d17395ee75644eba2f2a706b54aca5a066d4c8d765958bb99 совпал с r149)
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK

PANEL-NONCE: d3fa411f4e0cae9e
ARTIFACT-SHA256: bf242262f19cce9383401e2c9988677fa6cdcb64fb5045bf8ab3cb1e44249cfc
Канон прочитан: AGENTS.md, 430 строк. В корне репозитория `AGENTS.md`, `.agents/AGENTS.md` и `CLAUDE.md` нет. Тесты не запускал: L2 беру из `execution-evidence.md` и `receipts/code-gate.json`.

AMEND F-001 — priority=blocking; locations=bridges/opencode-zen-bridge/server.py:3562, bridges/opencode-zen-bridge/server.py:3563, bridges/opencode-zen-bridge/server.py:6573, bridges/opencode-zen-bridge/server.py:7961, bridges/opencode-zen-bridge/server.py:8121; fix=В `_drain_serve_step_usage` вызывать `text_cb` и при `emulate_tools=True`: SSE попадает в `_text_seen` и `ToolCallParser`, JSON — в список `texts`, из которого собирается `content_raw`. Публикацию native tool_call по-прежнему держать до подтверждённого `session.step.ended`. — причина: bridges/opencode-zen-bridge/server.py:3563 (`if text_cb is not None and not emulate_tools:` после `result["texts"].append` на 3562). Живой SSE-callback — `_text_seen` на 6573, JSON-callback — `texts.append` на 7961, клиентский текст JSON — `"".join(texts)` на 8121. Строка 4318 этим вызовом не является.

AGREE F-002 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:4051 — `_serve_http` prompt идёт с `timeout=65.0` и `deadline=attempt_deadline` (4053); `_AUX_IO_BUDGET_S = 54.0` на 1587; `aux.debit_seconds` только в `finally` после ожидания (4063–4068). Остаток aux фазу не обрезает.

AGREE F-003 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:7004 — role-чанк пишется в `self.wfile` до обёртки `_LockedWfile` (7012); `self.end_headers()` на 6997; таймер на 7032 держит `wfile_lock` и пишет в `raw_wfile` (7038); `except (OSError, ValueError): pass` на 7047 не ставит `_downstream_client_gone`. `Handler.timeout = 300` на 6251, `_DOWNSTREAM_WRITE_TIMEOUT_S = 5.0` на 1586 действует только внутри обёртки.

AGREE F-004 rev=1 — проверил: bridges/opencode-zen-bridge/server.py:6196 — в новом `_LockedWfile._mark_client_gone` стоит `except Exception:` и `pass` (6197). Это запрет №1 `agents/python-standards.md` (строка 38): глушение без диагноза, не внешняя точка входа.

WITHDRAW F-005 — NEW: bridges/opencode-zen-bridge/server.py:3563 — проверил: bridges/opencode-zen-bridge/server.py:3563. Тот же gate, что у F-001; отдельный блок удваивает одну дыру.

WITHDRAW F-009 — ARG: skeptic/R1 «До обёртки: self.wfile.write(first_chunk.encode("utf-8")). Таймер: with wfile_lock: и _ = raw_wfile.write(...)» — проверил: bridges/opencode-zen-bridge/server.py:7004. Тот же обход `_LockedWfile`, что закрывает F-003.

WITHDRAW F-010 — ARG: skeptic/R1 «try: self._on_client_gone() / except Exception: pass» — проверил: bridges/opencode-zen-bridge/server.py:6196. Тот же запрет, что F-004.

WITHDRAW F-011 — NEW: recheck-r1.md (класс на `unittest.TestCase` с цикла 1, чтобы одновременно проходили VER-001 pytest и VER-002 `unittest discover`; запрет `testing.md` относится к Litestar-async профилю) — проверил: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:412. Воспроизводимого дефекта нет; переписывание модуля ради стиля — неоправданное раздувание.

WITHDRAW F-012 — NEW: recheck-r1.md (инвариант 0 зависимостей вне stdlib, `gc_pytools.gigarc` в окружении моста нет, флаг утверждён архитектурой и не входит в дельту цикла 10; канон называет `dynamic_config.py` рядом с GigaRC) — проверил: bridges/opencode-zen-bridge/server.py:1829. Отсутствие или не-boolean `REALTIME_SERVE_ENABLED` возвращает false (1835). Подключение пакета нарушило бы Non-Goals.

AMEND F-008 — priority=blocking; locations=bridges/opencode-zen-bridge/server.py:2472, bridges/opencode-zen-bridge/server.py:3331, bridges/opencode-zen-bridge/server.py:3996; fix=Списывать в `_AuxIoBudget` ожидание подписки до первого SSE-события либо до `first_event_timeout`. Фазу prompt не дублировать: она в F-002. Ожидание первого токена после execution-события — модельный стриминг, в aux-бюджет не входит. — причина: NEW: bridges/opencode-zen-bridge/server.py:2472 (докстринг: «подписка до первого SSE») против возврата `_open_serve_events` сразу после HTTP-заголовков на 3331 и списания только этого вызова на 3996.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-002 (pending native до `step.ended`), байты reasoning (RW-003) и классификация form/permission/error в дренаже на коде и L2 закрыты. Текст того же окна при `emulate_tools=True` остаётся только в `result["texts"]` и не доходит до SSE и JSON (F-001, `server.py:3563`, потребители `6573`, `7961`, `8121`). Успешные serve-ветки по-прежнему отдают в `_incomplete_step_signal` сырой reasoning (`server.py:6751`, `server.py:8169`), тогда как детектор на `server.py:1062` считает interruption-маркер признаком незавершённости, а legacy перед классификацией передаёт очищенную копию (`server.py:7678`, `server.py:8473`). Оракул сохранности маркеров выключает `STEP_RECOVERY_ENABLED`. Это открытый F-006.
   СОВЕТЫ (при FAIL): Вызывать `text_cb` из дренажа и при эмуляции инструментов, проведя текст через тот же parser, что обычные дельты. В SSE и JSON добавить последовательность `tool.called` → текстовый хвост → `step.ended`: хвост в ответе ровно один раз, один tool_call, `finish_reason=tool_calls`. В serve SSE и JSON передавать в `_incomplete_step_signal` очищенную копию reasoning, клиенту оставляя исходные байты. Оракул при включённом recovery, доступных tools и готовом приветствии с маркером в reasoning: serve и run делают одинаковое число попыток.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Именованные оракулы RW-001..RW-005 и FU-002 на своих сценариях есть, clean-room L2 их проходит (491 passed). Ветка текста внутри дренажа не покрыта (F-001). Оракул `_AuxIoBudget` на управляемых часах не проводит реальный prompt через остаток 54 с (F-002) и не доводит подписку до первого SSE (F-008). Оракул маркеров не включает recovery (F-006). F-013 (неточные имена событий в `verification-traceability.md`) остаётся non-blocking и критерий сам по себе не роняет.
   СОВЕТЫ (при FAIL): Добавить оракулы F-001, F-002, F-006 и F-008 в `tests/test_realtime_reasoning.py`. Поправить описания протокола в traceability (F-013) одним проходом с кодом. После правок повторить полный clean-room L2. VER-006 и VER-007 остаются DEFERRED_L3 до ACCEPT.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Короткоживущий `opencode serve` на stdlib, с ротацией прокси, `:memory:` и откатом на `run` до барьера доставки, внедряется: новых runtime-пакетов нет, kill-switch есть, L2 зелёный. Внедрению мешают незамкнутые лимиты. Prompt может ждать 65 с при бюджете 54 с (F-002). Подписка списывается до заголовков, а не до первого SSE (F-008, `server.py:3331`). Имена и `call_id` в `_ServeToolState` не входят в байтовый бюджет: `_serve_tool_state_bytes` считает `text` и `input` (`server.py:3676`), а `name` пишется на `server.py:3237` (F-007). Первые записи клиенту обходят таймаут 5 с и упираются в `Handler.timeout = 300` (F-003).
   СОВЕТЫ (при FAIL): Стартовать prompt только при ненулевом остатке aux и передавать `deadline=aux.deadline(attempt_deadline)`. Списывать подписку до первого SSE-события. Включить `name` и ключи `call_id` в общий UTF-8 потолок либо задать отдельные пределы; превышение в main и drain даёт `ServeProtocolError`, cleanup и пустой pending. Первые заголовки, role-чанк и `_initial_status` вести через `_LockedWfile` с `min(5 с, остаток дедлайна)`; ошибка записи ставит `_downstream_client_gone` и вызывает `abort_socket` без повторного захвата того же замка. Локальные оракулы и повтор L2 — ориентир 1–2 рабочих дня; живая лестница H0..H9 идёт после ACCEPT и зависит от квоты.

4. РИСКИ: VERDICT=FAIL
   WHY=Независимый L2 подтверждён: pytest и unittest 491, корневой прогон 894 passed / 5 skipped, realtime-набор 112 passed, AC-023 в обратном порядке rc=0, VER-004 без ошибок типов, frozen-срезы совпали, RED AC-026 на `origin/dev` rc=1. Это не закрывает потерю текста дренажа (F-001), обход downstream-таймаута на слоте и группе (F-003, REQ-008 / AC-011) и обход байтового потолка tool state (F-007). Пароль serve, allowlist и fail-closed 401/403 на проверенных ветках в порядке; отдельного секрета в этих дырах нет. Флейк `foreign listener` из первого unittest Coder в clean-room L2 не воспроизвёлся.
   СОВЕТЫ (при FAIL): Регрессии F-001, F-002, F-003, F-007 и F-008 в том же тестовом модуле, затем полный L2. Сокетный оракул: клиент перестаёт читать при полном окне до первого токена; слот `in_use==0` и группа serve отсутствуют быстрее 7 с. Не ослаблять `MAX_TOTAL_SPAWNS=3` и не расширять diff за `bridges/opencode-zen-bridge/`.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve с откатом на `opencode run` до барьера доставки закрывает RC-1: CLI v2.1.2 не отдаёт `*.delta`, общий демон ломает ротацию IP, прямой Zen без заголовков CLI даёт 429. Замечания чинятся внутри этого транспорта. Снятие F-011 и F-012 убирает переписывание тестов на pytest и ввод пакета вне stdlib.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Граница задачи соблюдена: три файла манифеста, `_run_env` / Google-direct побайтово те же, публичная форма SSE и порт 9883 сохранены, DSH и чужие мосты не тронуты, живой `~/.dsh` до ACCEPT не менялся. Прямые нарушения остаются. `except Exception: pass` в новом коде (F-004, `python-standards.md` запрет №1, `server.py:6196`). Prompt не ограничен остатком aux на каждом шаге I/O (F-002, `feature.md` и R-BULK-I1, `server.py:4051`). F-011 и F-012 сняты и этот критерий не роняют.
   СОВЕТЫ (при FAIL): В `_mark_client_gone` ловить ожидаемый сбой callback, писать `_log` без секретов и всё равно доходить до `shutdown`/`close`. Обрезать prompt дедлайном aux, как в совете к реализуемости.

POSITIONS: 4/4
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK

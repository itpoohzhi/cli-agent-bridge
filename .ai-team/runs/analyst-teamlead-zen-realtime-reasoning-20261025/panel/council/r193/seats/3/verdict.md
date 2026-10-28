PANEL-NONCE: 10fba3b6335a717b
ARTIFACT-SHA256: 1b2f1af3c71f0f56d62d0b42049fe3c03d1f41ab2bd9615a979d3a7ba2d4652f

AMEND F-001 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:4231,bridges/opencode-zen-bridge/server.py:4288,bridges/opencode-zen-bridge/server.py:4440,bridges/opencode-zen-bridge/server.py:4447; fix=сетевой отказ reject/cancel/interrupt в основном цикле переводить в ServeSecurityError с cleanup, отдельно оставив client_gone и deadline — NEW: council.md:452-455; проверил: server.py:4440, server.py:3534, server.py:4453. ARG: skeptic R1 «pre-existing/вне дельты RW-001..006 … blocking по §3 не дают». HTTP-статус по-прежнему поднимает ServeSecurityError (server.py:4238, server.py:4295); drain на OSError уже fail-closed (server.py:3534); finally вызывает cleanup (server.py:4453). Ветка prompt_error вне дельты coder-14.
AMEND F-002 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5868,bridges/opencode-zen-bridge/server.py:8099,bridges/opencode-zen-bridge/server.py:8184; fix=перед continue сохранять reasoning и нормализованный текст попытки; неподтверждённые native calls не публиковать — NEW: council.md:452-455; проверил: server.py:8099, server.py:8071, server.py:8184. ARG: recheck-r1 «неизменённый код прошлых циклов не переоценивается заново без прямой регрессии от дельты coder-14». Serve JSON суммирует usage до continue (server.py:8071) и теряет текст/reasoning на watchdog/prompt-status; SSE уже отдал первую попытку. Это не регрессия RW-005.
AMEND F-003 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:1581,bridges/opencode-zen-bridge/server.py:4362; fix=ждать step.ended в пределах deadline и stall-watchdog, продлевая ожидание по активности событий и удерживая pending до подтверждения — NEW: council.md:452-455; проверил: server.py:1581, server.py:4362. Окно 1.0 с не в дельте coder-14 и не сдвинуто доставкой text_cb. Следующий цикл может расширить окно без смены транспорта.
AMEND F-004 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:8223,bridges/opencode-zen-bridge/server.py:8261,bridges/opencode-zen-bridge/server.py:6806,bridges/opencode-zen-bridge/server.py:8519; fix=при исчерпании unmapped в serve JSON добавлять то же уведомление и finish_reason=stop, что legacy JSON и serve SSE — NEW: council.md:452-455; проверил: server.py:8223, server.py:6806, server.py:8519. SSE уже пишет уведомление и выходит (server.py:6806); расхождение только у JSON и вне дельты цикла 11.

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=RW-001..RW-006 закрыты: text_cb в дренаже (server.py:3562), остаток aux на prompt/подписке/control (server.py:4053, server.py:4080), _LockedWfile до заголовков и role (server.py:7071), маскированный лог callback и abort в finally (server.py:6242), классификатор получает очищенную копию reasoning (server.py:6810), UTF-8 call_id и name входят в байтовый бюджет (server.py:3680). Повторная проверка F-001..F-004 подтвердила ветки, и по council.md:452-455 они остаются non-blocking follow-up вне дельты coder-14.
2. ПОЛНОТА: VERDICT=PASS
   WHY=AC-001..AC-024 и AC-026 закрыты оракулами L2 (execution-evidence.md VER-001..VER-005, AC-023, rc=0). AC-025, VER-006 и VER-007 законно DEFERRED_L3. Края F-002..F-004 (JSON-retry, окно дренажа, unmapped JSON) записаны как non-blocking и не входят в дельту цикла 11.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Короткоживущий serve на попытку даёт дельты reasoning вместо блока в конце CLI-шага, сохраняет stdlib, bulkhead, ротацию прокси и OPENCODE_DB=:memory:. До REALTIME_SERVE_ENABLED и нативного бинаря запрос остаётся на opencode run. Живая выкладка H0..H9 ждёт ACCEPT.
4. РИСКИ: VERDICT=PASS
   WHY=Clean-room L2: RED на origin/dev rc=1 по AC-026, на кандидате 502 pytest, 502 unittest, обратный порядок 502, VER-004 0 ошибок. Барьер доставки, MAX_TOTAL_SPAWNS=3, aux 54 с и cleanup группы действуют. F-001 после cleanup не оставляет живую группу; F-003 — прежний предел окна, не регрессия этого цикла.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Serve на запрос с откатом на run сохраняет ротацию IP и kill-switch. Общий демон отдал бы один egress. Дельта цикла 11 точечная, без нового слоя и без зависимости вне stdlib. Локальные правки F-001..F-004 не требуют смены транспорта.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Ровно три файла конверта, публичный SSE сохранён, замороженные _run_env/_stream_google_sse/_execute_google_once совпали, google_direct_unchanged=True. Пересчёт сида: seed_input дословно, seed_hex=195ef447aa7d195e3f3c4499bc3aca386eb0b5f095f8be883090430980228006, SEED=195ef447, ranked_order совпал: grok-4.7-high, muse-wonder-full-1.0, gpt-6.1-sol-high, gemini-4-argon-high, claude-sonnet-5-5-high.

POSITIONS: 0/0
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: ACCEPT

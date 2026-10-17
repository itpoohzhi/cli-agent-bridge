2026-10-15 05:44 MSK | OPEN-07 (политика approval для неинтерактивного моста) | владелец выбрал в чате: «Авторазрешение (allowAll)» | вопрос и варианты: denyUnmatched(рек.)/allowAll/передача пользователю DSH/сначала узнать payload | риск принят владельцем: модель получает свободу действий в рамках того, что не отключено флагами serve (--disable-write --disable-shell остаются; sandbox не отключать)
2026-10-15 13:39 MSK | находки арх-панели F-002, F-003, F-004, F-006 (OBJECT автора при C1, PAUSED_OWNER) | владелец выбрал в чате по каждой: «blocking (Рекомендуется)» | опции: blocking / non-blocking / excluded | итог: все четыре blocking, входят в instructions для Architect delta

## Решение владельца 2026-10-15 ~18:15 MSK — арх-панель cycle-1, проход a2 (PAUSED_OWNER, ответы AskUserQuestion, явные)
- F-001 (барьер повтора / ненаблюдаемое действие, ASM-010 vs AD-003): **blocking**
- F-002 (таймаут live-записи после захвата _wlock, AD-004/BND-004): **blocking**
- F-003 (бюджет 1800 с без резерва на cleanup/выдачу, grace после cancel): **non-blocking** (учесть в брифе Coder)
- F-004 (потеря reasoning при расхождении snapshot, CD-001): **non-blocking** (учесть в брифе Coder)
- F-005 (откат denyUnmatched обходится exec --yolo, AD-006/AD-007): **blocking**
Итог: вердикт a2 = NEEDS WORK (3 blocking: F-001, F-002, F-005) → panel-rework-summarizer → Architect delta a3 (arch_panel_to_architect: использовано 1, будет 2 из 5).

## Решения оркестратора по директиве владельца «хватит спрашивать, делай сам как принято в индустрии» (2026-10-15 ~22:50 MSK) — вопросы Architect a3
- Q-010 (at-least-once для ненаблюдаемых действий): НЕТ. Принято решение Architect: по умолчанию `MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE=pre-action` (повтор только до записи `turn/start`). Переключение на `observed-items` — без изменения кода, только после живого аудита ASM-010 (закрытие тяжёлым путём) и отдельной записи здесь. Обоснование: неидемпотентные побочные эффекты по индустриальной практике не повторяют; write/shell отключены флагами serve (EVD-005), остаточный риск — web/MCP.
- Q-009 (обход -32030 клиентским approve): НЕТ (exec-fallback по AD-006, при denyUnmatched — без exec).
- Q-001 (selective deny по protectedWrite/judgeEscalated): после сбора живых payload; сейчас только логирование.
- Q-004 (summary только в конце хода): решается спайком VER-013 до реализации AD-004; при NOT_MET REQ-MUSE-004 сообщается как не выполнено.

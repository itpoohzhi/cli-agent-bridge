# VERDICT (арх-панель, cycle 1, проход a1) — NEEDS WORK

Панель: arch, пул default (3 судьи на раунд; слот Architect muse-wonder-full-1.0 исключён из судей, SK-A-12). Раунды: R1 (r1), D1 (r4), D2 (r6), D3 (r7), C1 (r8); недействительные/отменённые раунды: r2 (aborted), r3 (invalid, V07), r5 (invalid, V03 квота agy). Все действительные раунды: panel-proof PASS.

## Вердикт по леджеру (council-consensus §7)

Класс A (дефект): `blocking_open` = 8: F-001, F-002, F-003, F-004, F-005, F-006, F-007, F-011 → **NEEDS WORK**. OPEN/OWNER_PENDING нет; пауза владельца пройдена (решения записаны). Событие автомата: ARCH_PANEL_NEEDS_WORK → panel-rework-summarizer → Architect (delta-пакет) → ARCH_GATE → новый проход a2.

Как совет договорился (цикл 1, проход a1): раундов дебатов 3, согласие C1: да; находок 21: согласовано 0, с согласием несогласных 17, решено владельцем 4, снято 0.

| F-id | Суть (первая строка F-блока дословно) | Позиции R1→D1→D2→D3→C1 (по ролям) | Итог (status, outcome, resolved_in) | Особое мнение / OBJECT |
|---|---|---|---|---|
| F-001 | ### F-01 — Противоречивые правила внутреннего serve→exec fallback | R1:Реа=AUTHOR → D1:Виз=A,Ске=A → C1:Виз=C | CONSENTED, blocking, c1 | — |
| F-002 | ### F-02 — Общий бюджет не включает очередь и не гарантирует соблюдение клиентского таймаута | R1:Реа=AUTHOR → D1:Виз=M,Ске=A → D2:Ске=A,Виз=M → D3:Реа=A,Ске=M,Виз=M → C1:Реа=O,Ске=C | OWNER_DECIDED, blocking, owner | Реалист C1 «OBJECT F-002 — дефект: architecture-packet.json#AD-003, #QA-004, #EVD-013, #EVD-016; arch-spec.md §3.3 — ожидание слота до 1800 с плюс выполнение до 1800 с превышают клиентские 1900 с. Очередь существ» → deba |
| F-003 | ### F-03 — Отсутствие SSE-контента не доказывает безопасность повторения инструментальных действий | R1:Реа=AUTHOR → D1:Виз=M,Ске=A → D2:Ске=A,Виз=M → D3:Реа=A,Ске=M,Виз=M → C1:Реа=O,Ске=C | OWNER_DECIDED, blocking, owner | Реалист C1 «OBJECT F-003 — дефект: architecture-packet.json#AD-003, #THREAT-001, #THREAT-004 — отсутствие SSE-контента и подтверждённая смерть процесса не исключают уже выполненного внешнего действия. При allowAl» → deba |
| F-004 | ### F-04 — Синхронный live-sink не имеет ограниченного времени записи | R1:Реа=AUTHOR → D1:Виз=M,Ске=A → D2:Ске=A,Виз=M → D3:Реа=A,Ске=M,Виз=M → C1:Реа=O,Ске=C | OWNER_DECIDED, blocking, owner | Реалист C1 «OBJECT F-004 — дефект: architecture-packet.json#BND-002, #BND-004, #AD-004; arch-spec.md §4.2 — новый синхронный sink связывает чтение MSP с неограниченной записью SSE под `_wlock`. Подключённый клиен» → deba |
| F-005 | ### F-05 — Инвариант live-конкатенации требует неописанного правила завершённости summary | R1:Реа=AUTHOR → D1:Виз=M(invalid),Ске=A → D2:Ске=A,Виз=A → C1:Ске=C | CONSENTED, blocking, c1 | — |
| F-006 | ### F-06 — Терминальная approval-деградация не замкнута как состояние | R1:Реа=AUTHOR → D1:Виз=M,Ске=A → D2:Ске=A,Виз=M → D3:Реа=A,Ске=M,Виз=M → C1:Реа=O,Ске=C | OWNER_DECIDED, blocking, owner | Реалист C1 «OBJECT F-006 — дефект: architecture-packet.json#AD-002, #QA-001; arch-spec.md §2.4 — предел «не более 10 approval/decide» противоречит дополнительному отказному decide после исчерпания лимита. После d» → deba |
| F-007 | ### F-07 — Тяжёлый gate допускает приёмку без достижения REQ-MUSE-004 | R1:Реа=AUTHOR → D1:Виз=A,Ске=A → C1:Виз=C | CONSENTED, blocking, c1 | — |
| F-008 | ### F-08 — Полнота аудита авторазрешений обещана сильнее, чем спроектирована | R1:Реа=AUTHOR → D1:Виз=A,Ске=A → C1:Виз=C | CONSENTED, non-blocking, c1 | — |
| F-009 | **F-1 [blocking] AD-006 обходит потолок режима approval, который держит сервер** | R1:Ске=AUTHOR → D1:Виз=M,Реа=D → D2:Реа=M,Ске=A,Виз=D → D3:Реа=A,Ске=W,Виз=A → C1:Реа=C | CONSENTED, non-blocking, c1 | Реалист D1 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-009, architecture-packet.json#AD-006, docs/adr/0003-muse»; Визионер D2 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-009, arc |
| F-010 | **F-2 [blocking] ApprovalPolicy одобряет любой запрос и не различает признаки эскалации** | R1:Ске=AUTHOR → D1:Виз=M,Реа=D → D2:Реа=M,Ске=A,Виз=D → D3:Реа=A,Ске=W,Виз=A → C1:Реа=C | CONSENTED, non-blocking, c1 | Реалист D1 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-009, architecture-packet.json#THREAT-001, architecture-p»; Визионер D2 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-009, arc |
| F-011 | **F-3 [blocking] После `turn/cancel` мост ждёт до дедлайна 1800 с и держит слот** | R1:Ске=AUTHOR → D1:Виз=A,Реа=A → C1:Реа=C | CONSENTED, blocking, c1 | — |
| F-012 | **F-4 [blocking] Инвариант «конкатенация live-дельт = буферизованный reasoning» определён не полностью** | R1:Ске=AUTHOR → D1:Виз=M,Реа=A → D2:Реа=A,Ске=A,Виз=D → D3:Реа=A,Виз=D → C1:Виз=C | CONSENTED, excluded, c1 | Визионер D2 «— класс: duplicate_of:F-005 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#CD-001, architec»; Визионер D3 «— класс: duplicate_of:F-005 — контр-evidence: architecture-packet.json# |
| F-013 | **F-5 [non-blocking] Деградация approval без exec-fallback ухудшает исход для spark** | R1:Ске=AUTHOR → D1:Виз=A,Реа=A → C1:Реа=C | CONSENTED, non-blocking, c1 | — |
| F-014 | **F-6 [non-blocking] Конфликт REQ-004 и REQ-003 по окну повтора не взвешен альтернативой** | R1:Ске=AUTHOR → D1:Виз=A,Реа=A → C1:Реа=C | CONSENTED, non-blocking, c1 | — |
| F-015 | **F-7 [non-blocking] Расхождение пределов попыток между QA-004 и спецификацией** | R1:Ске=AUTHOR → D1:Виз=A,Реа=A → C1:Реа=C | CONSENTED, non-blocking, c1 | — |
| F-016 | **F-8 [non-blocking] `protected_paths` слишком узок** | R1:Ске=AUTHOR → D1:Виз=M(invalid),Реа=A → C1:Реа=C | CONSENTED, non-blocking, c1 | — |
| F-017 | **F-9 [non-blocking] Грязное дерево `dev`: правки REQ-MUSE-001 и новые правки попадут в один MR** | R1:Ске=AUTHOR → D1:Виз=A,Реа=A → C1:Реа=C | CONSENTED, non-blocking, c1 | — |
| F-018 | **F-10 [non-blocking] Аудит-лог пишет `choiceId` и `toolName` как свободные строки** | R1:Ске=AUTHOR → D1:Виз=A,Реа=A → C1:Реа=C | CONSENTED, non-blocking, c1 | — |
| F-019 | **F-11 [non-blocking] Нет анализа нагрузки при деградации транспорта** | R1:Ске=AUTHOR → D1:Виз=A,Реа=A → C1:Реа=C | CONSENTED, non-blocking, c1 | — |
| F-020 | **F-12 [non-blocking] Нет операционного рубильника для `allowAll`** | R1:Ске=AUTHOR → D1:Виз=M,Реа=A → D2:Реа=A,Ске=A,Виз=M → D3:Реа=A,Виз=M → C1:Реа=C,Ске=C | CONSENTED, non-blocking, c1 | — |
| F-021 | **F-13 [non-blocking] [sweep] Источник текста транзиентной ошибки на serve-пути не подтверждён** | R1:Ске=AUTHOR → D1:Виз=A(invalid),Реа=A → C1:Реа=C | CONSENTED, non-blocking, c1 | — |

Решение владельца по OBJECT: F-002, F-003, F-004, F-006 → blocking (owner-decisions.md, 2026-10-15 13:39 MSK).

Счётчики: раундов дебатов 3; находок по статусам: CONSENTED 17, OWNER_DECIDED 4; r2_late: 0 (новых blocking в D-раундах не вводилось).

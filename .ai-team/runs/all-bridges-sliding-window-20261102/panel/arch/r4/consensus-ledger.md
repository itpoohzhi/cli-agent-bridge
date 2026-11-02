# consensus-ledger.md — снимок после C1 (prior-ledger следующего раунда)

- round_dir: r4
- artifact_sha256: 8425114cd2bef4c3cefc42daa7a33de1d7caad86d1b73381e7e322550ea414b1

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=47eff65f9975dbb9 verdict_sha256=44d87ff96633e1810750ef28ab6a5c4d28ce9241fdbb517527ef6a5fada70abe
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=cc64b8ab2c063d38 verdict_sha256=d96ba5901374d589a590be6f9d7b702627c4eb8ba72b367b10a030b467d4fab5
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=3ef4a742d8a59f80 verdict_sha256=c8e92950f6c8a5c85c679ff030f3e55d78f980c9be78ca0c0bd5ebd31439816c

## Находки

### F-001
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-001 NON_BLOCKING — Неточность формулировки EVD-002 и невалидируемый парсинг соседних таймаутов в opencode-zen-bridge

### F-002
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-002 NON_BLOCKING — Несоответствие команды верификации в VER-004 решению AD-003 для opencode-zen-bridge

### F-003
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-003 NON_BLOCKING — При возврате child_exited в check() проверка idle_timeout_s пропускается до срабатывания effective_cap_s

### F-008
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-008 BLOCKER-OPINION — План оставляет статический дедлайн активного потока Zen

### F-009
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'CONSENT', 'seat_3': 'AGREE'}
- text: RW-009 BLOCKER-OPINION — Синхронный опрос процессов задерживает выдачу SSE

### F-010
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-010 BLOCKER-OPINION — План проверок не доказывает основной результат

### F-004
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-004 NON_BLOCKING — Zen уже поддерживает настройку STALL_TIMEOUT_S через env

### F-005
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-005 NON_BLOCKING — VER-004 проверяет другой компонент

### F-011
- class: BLOCKER-SAFETY
- status: ESCALATED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-011 BLOCKER-SAFETY — Обязательные тесты верификации не существуют, подтверждение решений AD-001/AD-002 невозможно

### F-012
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-012 BLOCKER-OPINION — Заявленные изменения claude-p-bridge в коде отсутствуют, пакет описывает проект, но помечен как подтверждённый

### F-013
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'CONSENT', 'seat_2': 'CONSENT', 'seat_3': 'DISPUTE'}
- text: RW-013 BLOCKER-OPINION — ASM-002 переоценивает защиту: whitelist без привязки к потребителю не исключает утечку, а AD-002 не определяет границу

### F-014
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'CONSENT', 'seat_2': 'CONSENT', 'seat_3': 'DISPUTE'}
- text: RW-014 BLOCKER-OPINION — AD-001 вшивает интеграцию вотчдога в обработчик конкретного моста

### F-015
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-015 NON_BLOCKING — Zen STALL_TIMEOUT_S: заявленный хелпер не применён, а текущий код уязвим к невалидному значению

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — parse_live_write_timeout: каскад нужно строить через общий резолвер параметров

### F-007
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-007 NON_BLOCKING — Нет зонтичного контракта настроек для «всех мостов»


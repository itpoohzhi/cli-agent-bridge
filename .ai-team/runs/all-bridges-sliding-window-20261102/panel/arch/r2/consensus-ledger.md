# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: 8425114cd2bef4c3cefc42daa7a33de1d7caad86d1b73381e7e322550ea414b1

## Места

- seat 1: slot=claude-sonnet-5-5-high family=Anthropic nonce=8ea63032c8f7aede verdict_sha256=655f26d9cf088ee8e46b6a305d1b1437e17d60ed8b17410e1e2e4f59e29eb297
- seat 2: slot=gemini-4-argon-high family=Google nonce=3ab8668791aabac7 verdict_sha256=157e3b022500255c976755729b1f5cf9d1626bbef3982561426b0e1f53051705
- seat 3: slot=gpt-6.1-sol-medium family=OpenAI nonce=0b71e7113134a66a verdict_sha256=bb5a9d7e0d0baccd66fb42c4586bff2160995590ca5c499a8e73417aca033a47

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
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
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
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AMEND'}
- text: RW-013 BLOCKER-OPINION — ASM-002 переоценивает защиту: whitelist без привязки к потребителю не исключает утечку, а AD-002 не определяет границу

### F-014
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AMEND', 'seat_2': 'DISPUTE', 'seat_3': 'AMEND'}
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


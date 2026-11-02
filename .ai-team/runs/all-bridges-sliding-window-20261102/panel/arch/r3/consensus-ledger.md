# consensus-ledger.md — снимок после D2 (prior-ledger следующего раунда)

- round_dir: r3
- artifact_sha256: 8425114cd2bef4c3cefc42daa7a33de1d7caad86d1b73381e7e322550ea414b1

## Места

- seat 1: slot=gpt-6.1-sol-high family=OpenAI nonce=a60e4e1018db647d verdict_sha256=b52dab5ab2202e7c68ea58c135a46a818d5f18c651c7cc3c5da9a0bf11c1312b
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=a28c2b38dfb81f22 verdict_sha256=a5d7536ee06af8f2c44dc36bda65a8e6b73413e417478e60a8795ef821e92125
- seat 3: slot=gemini-4-argon-high family=Google nonce=198135ccfeda476b verdict_sha256=9d65245e89ee8e695ce01de131da990f6cfa6ef74d6083686205841773e1055b

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
- votes: {'seat_1': 'AMEND', 'seat_2': 'AMEND', 'seat_3': 'DISPUTE'}
- text: RW-013 BLOCKER-OPINION — ASM-002 переоценивает защиту: whitelist без привязки к потребителю не исключает утечку, а AD-002 не определяет границу

### F-014
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'DISPUTE', 'seat_2': 'DISPUTE', 'seat_3': 'DISPUTE'}
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


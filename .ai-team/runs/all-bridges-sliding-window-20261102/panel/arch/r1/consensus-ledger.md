# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: 8425114cd2bef4c3cefc42daa7a33de1d7caad86d1b73381e7e322550ea414b1

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=e9fceddb2b31791a verdict_sha256=cea28d363f1698bcb38222f26c2b1f173ca0ccb4f80b8bdc31b1c0a38729f25f
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=f3817f835b503eb5 verdict_sha256=d9b59dd814a70955842e3c0a3ae7cb5b879db83c1a29ee7ac5ad1647c9a4fe27
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=6ea8828584e73ac9 verdict_sha256=33a6221b79dd0bdae81bfc83e5a5a12fbeb65805e5f6dffccd66f166a7e234b4

## Находки

### F-001
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-001 NON_BLOCKING — Неточность формулировки EVD-002 и невалидируемый парсинг соседних таймаутов в opencode-zen-bridge

### F-002
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-002 NON_BLOCKING — Несоответствие команды верификации в VER-004 решению AD-003 для opencode-zen-bridge

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — При возврате child_exited в check() проверка idle_timeout_s пропускается до срабатывания effective_cap_s

### F-008
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-008 BLOCKER-OPINION — План оставляет статический дедлайн активного потока Zen

### F-009
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-009 BLOCKER-OPINION — Синхронный опрос процессов задерживает выдачу SSE

### F-010
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-010 BLOCKER-OPINION — План проверок не доказывает основной результат

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — Zen уже поддерживает настройку STALL_TIMEOUT_S через env

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — VER-004 проверяет другой компонент

### F-011
- class: BLOCKER-SAFETY
- status: OPEN
- votes: {}
- text: RW-011 BLOCKER-SAFETY — Обязательные тесты верификации не существуют, подтверждение решений AD-001/AD-002 невозможно

### F-012
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-012 BLOCKER-OPINION — Заявленные изменения claude-p-bridge в коде отсутствуют, пакет описывает проект, но помечен как подтверждённый

### F-013
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-013 BLOCKER-OPINION — ASM-002 переоценивает защиту: whitelist без привязки к потребителю не исключает утечку, а AD-002 не определяет границу

### F-014
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-014 BLOCKER-OPINION — AD-001 вшивает интеграцию вотчдога в обработчик конкретного моста

### F-015
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-015 NON_BLOCKING — Zen STALL_TIMEOUT_S: заявленный хелпер не применён, а текущий код уязвим к невалидному значению

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — parse_live_write_timeout: каскад нужно строить через общий резолвер параметров

### F-007
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-007 NON_BLOCKING — Нет зонтичного контракта настроек для «всех мостов»


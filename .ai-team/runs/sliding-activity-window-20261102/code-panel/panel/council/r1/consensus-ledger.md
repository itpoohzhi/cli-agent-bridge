# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: 9ea833eaa5cf7579802e170f25ad5b1da3f3b5477de1aed1134370b052b65f4e

## Места

- seat 1: slot=muse-wonder-full-1.0 family=Meta nonce=bf66edbf17df9d90 verdict_sha256=dca048bcaa6c0562119ac879383846d59c38dc56756bf71a7c583d54f3e5cff6
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=f7dab26d35b4419f verdict_sha256=995c05d66d2bf6e3d3a59d75d9ab5f60091194eb002dff465a99194c5c5bfecb
- seat 3: slot=gemini-4-argon-high family=Google nonce=509c608fa156103f verdict_sha256=25150355c74c9d60bd767a4d5a0e8394c80f0fd0872f38b5c8d07b8e8641082c

## Находки

### F-001
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-001 BLOCKER-OPINION — До первого полезного токена окно продлевает любой байт upstream, а не полезный чанк

### F-002
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-002 BLOCKER-OPINION — Скользящее окно скрыто упирается в сокетный таймаут, привязанный к старому total-дедлайну; сквозного доказательства фикса нет

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — `BRIDGE_SAFETY_CAP_S` уже занята другим подсистемным капом, алиас поддержан асимметрично

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — «Абсолютный» safety cap не абсолютен: точка отсчёта и кооперативное срабатывание

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — Манифест пакета расходится с фактическим артефактом и его состоянием в git

### F-006
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-006 BLOCKER-OPINION — Старый total timeout продолжает ограничивать чтение сокета

### F-007
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-007 BLOCKER-OPINION — Upstream keepalive продлевает ожидание первого полезного токена

### F-008
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-008 NON_BLOCKING — Дуализм `last_upstream` и `last_progress` ослабляет защиту TTFT от пустых/сервисных кадров апстрима

### F-009
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-009 NON_BLOCKING — Таймаут сокета `conn.sock` при входе в SSE остаётся привязанным к `total_timeout_s`

### F-010
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-010 NON_BLOCKING — Унификация константы окружения `BRIDGE_SAFETY_CAP_S` и legacy-алиаса с ядром


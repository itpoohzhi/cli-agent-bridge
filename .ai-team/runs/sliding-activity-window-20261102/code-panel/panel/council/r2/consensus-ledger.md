# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: 9ea833eaa5cf7579802e170f25ad5b1da3f3b5477de1aed1134370b052b65f4e

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=a21b06ccf477d666 verdict_sha256=4e440445782185b05a065254581cd2168c56aa5c650b0e85e90d9184e78c8b6a
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=5de0bdc4555c0812 verdict_sha256=729ba80531ccf7ce8ddb5b36cad4bdb1a0bb21a05f5ca8ffb5acd9397a1e9069
- seat 3: slot=gpt-6.1-sol-high family=OpenAI nonce=e6dafd1e1016b8c2 verdict_sha256=e0ea95aad9b5b0930aa4a1b2f8f8208f582161f11590b89f0d7fe3b0675e302f

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — До первого полезного токена окно продлевает любой байт upstream, а не полезный чанк

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — Скользящее окно скрыто упирается в сокетный таймаут, привязанный к старому total-дедлайну; сквозного доказательства фикса нет

### F-003
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-003 NON_BLOCKING — `BRIDGE_SAFETY_CAP_S` уже занята другим подсистемным капом, алиас поддержан асимметрично

### F-004
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-004 NON_BLOCKING — «Абсолютный» safety cap не абсолютен: точка отсчёта и кооперативное срабатывание

### F-005
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-005 NON_BLOCKING — Манифест пакета расходится с фактическим артефактом и его состоянием в git

### F-006
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'DISPUTE', 'seat_3': 'AGREE'}
- text: RW-006 BLOCKER-OPINION — Старый total timeout продолжает ограничивать чтение сокета

### F-007
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-007 BLOCKER-OPINION — Upstream keepalive продлевает ожидание первого полезного токена

### F-008
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-008 NON_BLOCKING — Дуализм `last_upstream` и `last_progress` ослабляет защиту TTFT от пустых/сервисных кадров апстрима

### F-009
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-009 NON_BLOCKING — Таймаут сокета `conn.sock` при входе в SSE остаётся привязанным к `total_timeout_s`

### F-010
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-010 NON_BLOCKING — Унификация константы окружения `BRIDGE_SAFETY_CAP_S` и legacy-алиаса с ядром


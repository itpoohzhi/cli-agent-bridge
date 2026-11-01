# consensus-ledger.md — снимок после C1 (prior-ledger следующего раунда)

- round_dir: r3
- artifact_sha256: 8388cb5255cf009fe8abcf6e83db6729f25cb1f635cbb37bb653bda6112b4908

## Места

- seat 1: slot=claude-sonnet-5-5-high family=Anthropic nonce=efa8b23b4a4f1283 verdict_sha256=a49fbf02d9eb3158e2ffcadddefad94513f74a810ee1d11e3a889cf6205bc6ca
- seat 2: slot=gemini-4-argon-high family=Google nonce=b5b1986343f7d2c8 verdict_sha256=fa92235a24ec4610d00cc48a0ea4f9e5935eddff0ad0fb5bc40a9ef0c666e88a
- seat 3: slot=gpt-6.1-sol-high family=OpenAI nonce=ffe893ce9b4312ea verdict_sha256=5044264981742ab04cc949c4f1b9038a3b2cb3fc76789b767b53162e4760cf07

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — Предложенная схема теряет существующий флаг stream resilience

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — План обновления тестов пропускает независимое ожидание length

### F-003
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-003 NON_BLOCKING — Предложенная очистка env нарушает восстановление окружения тестов

### F-004
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-004 NON_BLOCKING — номера строк в пакете неверны, правки точек вызова могут промахнуться

### F-005
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-005 NON_BLOCKING — расхождение в плане тестов: заявлено 10 обновляемых тестов, перечислено 9

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — смена дефолта на `stop` ухудшает диагностику усечённого ответа


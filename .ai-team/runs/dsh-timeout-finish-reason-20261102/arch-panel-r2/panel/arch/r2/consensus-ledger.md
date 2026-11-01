# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: 8388cb5255cf009fe8abcf6e83db6729f25cb1f635cbb37bb653bda6112b4908

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=211d145c5dd7fff6 verdict_sha256=2575e30f5ca84a3bda9bdabbaa4485dccab279d0352fd53e1603962cfe73451b
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=2d8553dda78bf17b verdict_sha256=cf7033c61aa518f9cbd3f87fb31fc36def683a04795c2746ae621823eb85ccbd
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=3b4c949b67a4b51d verdict_sha256=9c62b2accb9970fba6f35ffa0c1d4f67be207e98a763047c8ca45c54188515dd

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


# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: 8388cb5255cf009fe8abcf6e83db6729f25cb1f635cbb37bb653bda6112b4908

## Места

- seat 1: slot=gpt-6.1-sol-high family=OpenAI nonce=463d62448f667fe7 verdict_sha256=058ad2908dd8d23aa9f63e4e31fd5e97ee48ac54e8e2033e5b8913fb28a3e069
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=e6bf403bc625b23d verdict_sha256=8bbdc1a6c2f49e6b04fcd4e598932dd09a7585479c57221496d62d487050e93c
- seat 3: slot=gemini-4-argon-high family=Google nonce=1d176a8def37e25e verdict_sha256=e8ae446e5290a6213446936330a8ce5ccb9a275b0f4e11fa7ff1deaffdc189c6

## Находки

### F-001
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-001 BLOCKER-OPINION — Предложенная схема теряет существующий флаг stream resilience

### F-002
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-002 BLOCKER-OPINION — План обновления тестов пропускает независимое ожидание length

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — Предложенная очистка env нарушает восстановление окружения тестов

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — номера строк в пакете неверны, правки точек вызова могут промахнуться

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — расхождение в плане тестов: заявлено 10 обновляемых тестов, перечислено 9

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — смена дефолта на `stop` ухудшает диагностику усечённого ответа


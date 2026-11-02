# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: f11926370796cb83074b1ddfce74de7ba251ee15b25a83a6621cb07ebaee77aa

## Места

- seat 1: slot=claude-sonnet-5-5-high family=Anthropic nonce=2dfb4a758ba18ee3 verdict_sha256=82ec5ef6e8d5daff92b32dc37870407dfaee4c34533bf44bcaaca18ddf043e17
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=70eb2df40a2f1f9c verdict_sha256=70483d4b550197a6dd3712d6c8d520b5e02fdd24516bd33b1b9318e57cbffea4
- seat 3: slot=gemini-4-argon-high family=Google nonce=e1767303ca69960d verdict_sha256=b935e6f99a52be7da2b8c43fa736fea3c9637adcb80d12ddb9729b0d5d699924

## Находки

### F-001
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-001 BLOCKER-OPINION — `ResilienceLease.__exit__` не освобождает слот пробы, если исход не записан

### F-002
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-002 BLOCKER-OPINION — классификация сбоев смешивает ошибки клиента и бэкенда, брейкер может открыть один клиент

### F-003
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-003 BLOCKER-OPINION — повтор по условию «байты не отданы» не защищает от повторного выполнения побочных эффектов

### F-004
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-004 BLOCKER-OPINION — жёстко зашитые лимиты нарушают `AGENTS.md` п.4

### F-005
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-005 BLOCKER-OPINION — порядок захвата брейкера и Bulkhead не определён, слот пробы может утечь

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — утверждение RW-006 об изоляции через `_conn_sem` неверно в общем случае

### F-007
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-007 NON_BLOCKING — в пакете нет точки вызова `RetryPolicy` и определения `bytes_delivered` для стрима

### F-008
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-008 NON_BLOCKING — потокобезопасность `ResilienceLease` и реестра

### F-009
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-009 NON_BLOCKING — пробелы в плане тестов


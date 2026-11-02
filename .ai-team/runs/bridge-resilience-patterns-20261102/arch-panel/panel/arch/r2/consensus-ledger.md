# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: f11926370796cb83074b1ddfce74de7ba251ee15b25a83a6621cb07ebaee77aa

## Места

- seat 1: slot=gpt-6.1-sol-high family=OpenAI nonce=52fa8797a546c616 verdict_sha256=e2a8ff3942e45131df0939475b51737498705d409edcfb92b5151fe9cfb8a128
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=4754ef93cf402564 verdict_sha256=1aa08bd84f22fc1393dbc4e8896eeae4aa2725b7423910299e75f1c635a22466
- seat 3: slot=gemini-3.8-flash-high family=Google nonce=0b73237871295a0e verdict_sha256=56f184b80d517a5e2d4632d8549947e3ccc6be56a51093a31d8fadf7fccdccad

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — `ResilienceLease.__exit__` не освобождает слот пробы, если исход не записан

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — классификация сбоев смешивает ошибки клиента и бэкенда, брейкер может открыть один клиент

### F-003
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-003 BLOCKER-OPINION — повтор по условию «байты не отданы» не защищает от повторного выполнения побочных эффектов

### F-004
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AMEND', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-004 BLOCKER-OPINION — жёстко зашитые лимиты нарушают `AGENTS.md` п.4

### F-005
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-005 BLOCKER-OPINION — порядок захвата брейкера и Bulkhead не определён, слот пробы может утечь

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — утверждение RW-006 об изоляции через `_conn_sem` неверно в общем случае

### F-007
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-007 NON_BLOCKING — в пакете нет точки вызова `RetryPolicy` и определения `bytes_delivered` для стрима

### F-008
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-008 NON_BLOCKING — потокобезопасность `ResilienceLease` и реестра

### F-009
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-009 NON_BLOCKING — пробелы в плане тестов


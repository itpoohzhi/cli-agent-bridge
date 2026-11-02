# consensus-ledger.md — снимок после C1 (prior-ledger следующего раунда)

- round_dir: r4
- artifact_sha256: f11926370796cb83074b1ddfce74de7ba251ee15b25a83a6621cb07ebaee77aa

## Места

- seat 1: slot=claude-sonnet-5-5-high family=Anthropic nonce=9277d4fd7baf8f5c verdict_sha256=490d2c0f4ac2cecd8e2d63e6834152d47ab83730111b42f592d0ad778e82b3d0
- seat 2: slot=gemini-4-argon-high family=Google nonce=8a2f76cb48283e15 verdict_sha256=2ef03ffc41e803693d111979e9bc081e7ba0a48d7602af7b29abb913a2d94876
- seat 3: slot=gemini-3.8-flash-high family=Google nonce=123bcb9be80bfda3 verdict_sha256=eeff54256ed44bc14ecfce9bc7331c3f65b91feaf0ab30a077ac9199cd23c9cc

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'CONSENT', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — `ResilienceLease.__exit__` не освобождает слот пробы, если исход не записан

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'CONSENT', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — классификация сбоев смешивает ошибки клиента и бэкенда, брейкер может открыть один клиент

### F-003
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'CONSENT', 'seat_3': 'AGREE'}
- text: RW-003 BLOCKER-OPINION — повтор по условию «байты не отданы» не защищает от повторного выполнения побочных эффектов

### F-004
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AGREE', 'seat_2': 'CONSENT', 'seat_3': 'CONSENT'}
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


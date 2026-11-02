# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: 8b703e9c4d5d73321cc4cf48a02a801ddc4f4e47d9c325c9a21a5e75d5c38cf6

## Места

- seat 1: slot=claude-sonnet-5-5-high family=Anthropic nonce=51520967746e7b93 verdict_sha256=776069b2a0dec2f1c1cecdf124bc8b5d940b58db54b146bf6e156339a81e1794
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=e10dce6b1e4b7b17 verdict_sha256=109598722e4d93f70940933bc8ca3fdbe005c1dccae7dd13fe2f6c3bdb3ce6da
- seat 3: slot=gemini-3.8-flash-high family=Google nonce=a085febd61579897 verdict_sha256=c2c8d5d59e5a537d45e0ac8e25ffb96c3fe2d2074e8534c1e1394de3eb2cc3e7

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — `RetryPolicy` в `core/resilience.py` не подключён ни к фасаду, ни к адаптерам (мёртвый код), а в `server.py` остался droid-специфичный хардкод ретраев

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — Mid-stream сбои и обрывы upstream в passthrough SSE фиксируются как `record_success()`, сбрасывая сбои и закрывая `HALF_OPEN`

### F-003
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AMEND', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-003 BLOCKER-OPINION — Для CLI-маршрутов (`droid`, `muse`) `adapter.preflight()` и создание `ManagedTurn` выполняются в `do_POST` до `RESILIENCE.acquire()`

### F-004
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AMEND', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-004 BLOCKER-OPINION — `RESILIENCE` в `server.py` инициализируется без `backend_limits` из `fleet.json`, а горячая смена ёмкости `Bulkhead` сбрасывает учёт активных слотов

### F-005
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-005 BLOCKER-OPINION — Потеря реального исхода бэкенда и преждевременное освобождение пробы `HALF_OPEN` в `_serve_sse_body` при `detach_on_disconnect` и `_client_write_dead`

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — Расхождение дефолтных задержек `RetryPolicy` между ADR-0020 и `core/resilience.py`


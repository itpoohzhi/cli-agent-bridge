# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: 8b703e9c4d5d73321cc4cf48a02a801ddc4f4e47d9c325c9a21a5e75d5c38cf6

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=f684c73b59115da6 verdict_sha256=66c5be2ff873fd043ab682222e08ea30542d2d6b4e6c6ce7311d3a6f8fe50f8e
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=74637a59ec3d5e04 verdict_sha256=6399566ebc2cb9d48b14da8e5c3a7ef0e434b92a44fe8cd181e5c79189f50866
- seat 3: slot=gpt-6.1-sol-high family=OpenAI nonce=d4bcc838c66e4c78 verdict_sha256=822e371e7bcc1c1346d4eaabe88990c37a32c782e09e183ce95fa55548e19e46

## Находки

### F-001
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-001 BLOCKER-OPINION — `RetryPolicy` в `core/resilience.py` не подключён ни к фасаду, ни к адаптерам (мёртвый код), а в `server.py` остался droid-специфичный хардкод ретраев

### F-002
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-002 BLOCKER-OPINION — Mid-stream сбои и обрывы upstream в passthrough SSE фиксируются как `record_success()`, сбрасывая сбои и закрывая `HALF_OPEN`

### F-003
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-003 BLOCKER-OPINION — Для CLI-маршрутов (`droid`, `muse`) `adapter.preflight()` и создание `ManagedTurn` выполняются в `do_POST` до `RESILIENCE.acquire()`

### F-004
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-004 BLOCKER-OPINION — `RESILIENCE` в `server.py` инициализируется без `backend_limits` из `fleet.json`, а горячая смена ёмкости `Bulkhead` сбрасывает учёт активных слотов

### F-005
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-005 BLOCKER-OPINION — Потеря реального исхода бэкенда и преждевременное освобождение пробы `HALF_OPEN` в `_serve_sse_body` при `detach_on_disconnect` и `_client_write_dead`

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — Расхождение дефолтных задержек `RetryPolicy` между ADR-0020 и `core/resilience.py`


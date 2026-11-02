# consensus-ledger.md — снимок после C1 (prior-ledger следующего раунда)

- round_dir: r3
- artifact_sha256: 8b703e9c4d5d73321cc4cf48a02a801ddc4f4e47d9c325c9a21a5e75d5c38cf6

## Места

- seat 1: slot=gpt-6.1-sol-high family=OpenAI nonce=7884b439e7e06a53 verdict_sha256=aec0eb97ed2e3d8480dadddb0ada4bbc7ab3b2ce55eb5ce1d4d016514967821d
- seat 2: slot=gemini-4-argon-high family=Google nonce=03b3d61304fc4db2 verdict_sha256=a179702fcd126ad1fc04460bef3ee78292117e745c899aa8f8749da55b589c6b
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=7217c83cb9b68763 verdict_sha256=0264ebbadb76a12b97db3b841c0fa6139c9c5300478542447e4e3d6abfe0b407

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
- status: ESCALATED
- votes: {'seat_1': 'OBJECT', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-003 BLOCKER-OPINION — Для CLI-маршрутов (`droid`, `muse`) `adapter.preflight()` и создание `ManagedTurn` выполняются в `do_POST` до `RESILIENCE.acquire()`

### F-004
- class: BLOCKER-OPINION
- status: ESCALATED
- votes: {'seat_1': 'OBJECT', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
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


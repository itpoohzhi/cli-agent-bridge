# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: 5ea11245c3546b12f1de9c303b0ace2ae267e271d264f328fe4565e904c024a9

## Места

- seat 1: slot=gpt-6.1-sol-high family=OpenAI nonce=fc2cf7de3b81dc95 verdict_sha256=c9afbbb22c61dad8b4ad98cba8df3e1b57cbff0f5139bc6fc126c64cebcb1c16
- seat 2: slot=gemini-4-argon-high family=Google nonce=559afb9e4c78f372 verdict_sha256=c67d937a8d84fabb31aab8a6cfc309a3f2a7b62ebcc2f19955c55dcc290f398c
- seat 3: slot=muse-wonder-full-1.0 family=Meta nonce=0ba22084d5ffae69 verdict_sha256=b355a8050ba74717cbafa46ec26d62dde26112f3614d3f06758f47fb1b6fd976

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — «Полный Git Diff» пакета неполон: код вне пакета не представлен к ревью

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — Три разных семантики точки отсчёта TTFT; retry без текста убивается мгновенно

### F-003
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AGREE', 'seat_2': 'DISPUTE', 'seat_3': 'AMEND'}
- text: RW-003 BLOCKER-OPINION — Idle 15с убивает легитимное долгое исполнение тула/сабагента в serve- и stream-путях

### F-004
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-004 NON_BLOCKING — Idle и Total не конфигурируются независимо: оба гейтятся значением TTFT

### F-005
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-005 NON_BLOCKING — `_attempts_t0`: eager-вычисление default в `getattr` ломает заявленную совместимость с заглушками

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — Удержание admission-слота вырослo в 7,2 раза; trickle-стрим держит слот и процесс 180с

### F-007
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-007 NON_BLOCKING — Новая проверка затеняет существующие `first_token_timeout`/`stall_timeout`, размывая телеметрию причин


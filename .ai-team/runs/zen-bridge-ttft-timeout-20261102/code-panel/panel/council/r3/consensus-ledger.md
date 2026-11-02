# consensus-ledger.md — снимок после D2 (prior-ledger следующего раунда)

- round_dir: r3
- artifact_sha256: 5ea11245c3546b12f1de9c303b0ace2ae267e271d264f328fe4565e904c024a9

## Места

- seat 1: slot=claude-sonnet-5-5-high family=Anthropic nonce=5223583453e293b4 verdict_sha256=aa7feb73071431b57e465e42a60a11f1556b0be29e9a02b35a1a1a553c0228f5
- seat 2: slot=muse-wonder-full-1.0 family=Meta nonce=e60bc87b7d218ef7 verdict_sha256=86c1102c64592f6d89d47c11f229326fde472b555b8bebf961bdbc08e5e8e1a6
- seat 3: slot=gpt-6.1-sol-high family=OpenAI nonce=a9e7fc67854ebeec verdict_sha256=903d99f741ea6d5d380035635622fb4486f1ab694d2836296110cf276631a4c8

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
- votes: {'seat_1': 'AMEND', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
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


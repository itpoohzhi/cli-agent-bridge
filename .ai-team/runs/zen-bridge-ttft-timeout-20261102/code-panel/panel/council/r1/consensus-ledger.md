# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: 5ea11245c3546b12f1de9c303b0ace2ae267e271d264f328fe4565e904c024a9

## Места

- seat 1: slot=muse-wonder-full-1.0 family=Meta nonce=0e56d41e3e3e0b0e verdict_sha256=1464d1c5ddea866084760dc3b42c89c07303c844d699fdc7b1ded049afac7d16
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=08d4cffbf1c5bc96 verdict_sha256=01d4bd230253a047e1abb343b88494cab7cce0fd334e27021e59ce41856a35a6
- seat 3: slot=gemini-4-argon-high family=Google nonce=2a5472681c63596e verdict_sha256=d04fbe38cdafe46a1dd7bd447e16d8a44f2c02cb9cc3d7c5d4799731eded2e6e

## Находки

### F-001
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-001 BLOCKER-OPINION — «Полный Git Diff» пакета неполон: код вне пакета не представлен к ревью

### F-002
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-002 BLOCKER-OPINION — Три разных семантики точки отсчёта TTFT; retry без текста убивается мгновенно

### F-003
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-003 BLOCKER-OPINION — Idle 15с убивает легитимное долгое исполнение тула/сабагента в serve- и stream-путях

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — Idle и Total не конфигурируются независимо: оба гейтятся значением TTFT

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — `_attempts_t0`: eager-вычисление default в `getattr` ломает заявленную совместимость с заглушками

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — Удержание admission-слота вырослo в 7,2 раза; trickle-стрим держит слот и процесс 180с

### F-007
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-007 NON_BLOCKING — Новая проверка затеняет существующие `first_token_timeout`/`stall_timeout`, размывая телеметрию причин


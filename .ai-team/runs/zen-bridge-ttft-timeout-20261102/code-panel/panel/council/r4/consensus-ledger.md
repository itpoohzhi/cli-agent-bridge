# consensus-ledger.md — снимок после C1 (prior-ledger следующего раунда)

- round_dir: r4
- artifact_sha256: 5ea11245c3546b12f1de9c303b0ace2ae267e271d264f328fe4565e904c024a9

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=8543f92085eb73cd verdict_sha256=eebdf19bf06e2f3eb63ca2efca303f31bdba18b0bfea3ee68ad0248a9af5fcdb
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=dcdaabf3818399ff verdict_sha256=5f460d1bbf29857f688023effdba677aae7045939bbe353251ad48fb21da6c7f
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=2753a7e89ee3c451 verdict_sha256=37840d4e44fc446c8b44e9d5b923dd518bb9e3d38a7fe0566c9be01cb833c322

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'CONSENT', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — «Полный Git Diff» пакета неполон: код вне пакета не представлен к ревью

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — Три разных семантики точки отсчёта TTFT; retry без текста убивается мгновенно

### F-003
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'CONSENT', 'seat_2': 'CONSENT', 'seat_3': 'AGREE'}
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


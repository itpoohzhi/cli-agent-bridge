# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: 0be90ffb4493dbe585bad077f3ebd0ba73d8c4b03a1b563b080d9e1ba2ac8f3d

## Места

- seat 1: slot=gpt-6.1-sol-high family=OpenAI nonce=b7fc1a0265337c35 verdict_sha256=92ba8b9c9c8f1fa73b4704a0b4657b49c3038f8ddf5c9981c47e20acf11c31db
- seat 2: slot=gemini-4-argon-high family=Google nonce=79dd1ae3dd1325bd verdict_sha256=50d0809de6bd30a9ff75ef1c0e56b9b8ebd050f05b5790cc73a3f58955c7c149
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=50f1e1a0002ba919 verdict_sha256=72ce70a7e79a967d6c22c6bf036ea05c18ea2fca72fe4067365be1dc6ef50fdc

## Находки

### F-001
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-001 BLOCKER-OPINION — Вотчдог обрывает ход при наличии полезных событий в очереди

### F-002
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-002 BLOCKER-OPINION — Заявленное устранение настенных лимитов не выполнено сквозным образом

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — В `_get_positive_float` невалидное непустое значение первичного ключа не передаёт управление `fallback_name`

### F-007
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-007 NON_BLOCKING — Однократное чтение `_DSH_ENV` при импорте модуля `claude-p-bridge`

### F-008
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-008 NON_BLOCKING — каскад `_get_setting` не соответствует заявленному в пакете порядку

### F-009
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-009 NON_BLOCKING — общий механизм настроек размещён в адаптере моста, а не в `core/`

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — границы 1.0–300.0 в `parse_live_write_timeout` зашиты константами

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — `record_activity` вызывается только для `text`, `thinking` и `result`

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — устаревшее имя `DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S` оставлено без плана вывода из обращения


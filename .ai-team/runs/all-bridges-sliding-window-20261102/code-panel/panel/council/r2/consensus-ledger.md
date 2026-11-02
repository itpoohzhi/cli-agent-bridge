# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: 0be90ffb4493dbe585bad077f3ebd0ba73d8c4b03a1b563b080d9e1ba2ac8f3d

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=91c8d98e02449258 verdict_sha256=7bc01c8cee7c12a44052b8569408dfd80392eff50c5e3b1ae1d10ecbed62aaae
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=d92911bb20d4fa06 verdict_sha256=1fef69552d9ec15be597dc1136aa26e225d28c9a1d570669a338b5d6333004c6
- seat 3: slot=muse-wonder-full-1.0 family=Meta nonce=c05a9975e59222cc verdict_sha256=c751516ca08d096c4067051b96eff0058cce2287393dc42be72986b5a20e33a8

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'DISPUTE', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — Вотчдог обрывает ход при наличии полезных событий в очереди

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AMEND'}
- text: RW-002 BLOCKER-OPINION — Заявленное устранение настенных лимитов не выполнено сквозным образом

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — В `_get_positive_float` невалидное непустое значение первичного ключа не передаёт управление `fallback_name`

### F-007
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-007 NON_BLOCKING — Однократное чтение `_DSH_ENV` при импорте модуля `claude-p-bridge`

### F-008
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-008 NON_BLOCKING — каскад `_get_setting` не соответствует заявленному в пакете порядку

### F-009
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-009 NON_BLOCKING — общий механизм настроек размещён в адаптере моста, а не в `core/`

### F-003
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-003 NON_BLOCKING — границы 1.0–300.0 в `parse_live_write_timeout` зашиты константами

### F-004
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-004 NON_BLOCKING — `record_activity` вызывается только для `text`, `thinking` и `result`

### F-005
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-005 NON_BLOCKING — устаревшее имя `DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S` оставлено без плана вывода из обращения


# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: a63c0fc62f291f23726fcd23dd621d2a9bb658e2fc95dccc5ded54b1367e1707

## Места

- seat 1: slot=muse-wonder-full-1.0 family=Meta nonce=8e4fe5d0bba6afa9 verdict_sha256=476058f1f46593fbc53f2bf852db89a21c025944b61f6cfe5bbe63149beebce1
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=c4d2b5d960981141 verdict_sha256=4ecf649eb3188b95e831f0b762d783e79bf23004a565fd48bfee7591533f6035
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=929bff02c44b2f19 verdict_sha256=d35fa8e2f52d3687d55ba39bc81ee78cb562a6742aca3078a3e7d9924c0c0c22

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AMEND'}
- text: RW-001 BLOCKER-OPINION — ротация по "Request quota exhausted" сработает только для транзиентных ошибок, а пакет это не доказывает

### F-002
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-002 NON_BLOCKING — таблица `_IMAGE_FORMATS` с `b"RIFF"` и `b"GIF8"` расходится со «строгим» сниффом

### F-003
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-003 NON_BLOCKING — подстрока `quota exhausted` слишком широкая, а два других маркера избыточны

### F-004
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-004 NON_BLOCKING — новые форматы расширяют поверхность атаки на декодеры нижестоящего CLI

### F-005
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-005 NON_BLOCKING — нет подтверждения прогона и несоответствие по файлам тестов

### F-007
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'DISPUTE', 'seat_3': 'AGREE'}
- text: RW-007 BLOCKER-OPINION — кортеж `_IMAGE_FORMATS` в пакете противоречит заявленному строгому sniff

### F-008
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AMEND'}
- text: RW-008 BLOCKER-OPINION — не зафиксирована точка входа инцидента; путь через хаб пакетом не чинится

### F-009
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-009 BLOCKER-OPINION — матрица верификации расходится с существующими тестами и даст ложную зелень

### F-010
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AMEND'}
- text: RW-010 BLOCKER-OPINION — новый маркер квоты недостижим, если ошибка Zen не классифицирована как transient

### F-011
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-011 NON_BLOCKING — подписочная квота приравнена к per-IP, маркеры избыточны

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — читаемость WebP/GIF downstream и документация не закрыты

### F-012
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-012 NON_BLOCKING — Дублирование таблиц сигнатур и логики MIME-сниффинга между `server.py` и `core/tool_emulation.py`

### F-013
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-013 NON_BLOCKING — Неиспользуемое поле сигнатуры `magic` в кортеже `_IMAGE_FORMATS` после перехода на составные сигнатуры

### F-014
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-014 NON_BLOCKING — Избыточность частных подстрок квоты при наличии общего маркера `"quota exhausted"` в `_is_free_quota_error`


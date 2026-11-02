# consensus-ledger.md — снимок после D2 (prior-ledger следующего раунда)

- round_dir: r3
- artifact_sha256: a63c0fc62f291f23726fcd23dd621d2a9bb658e2fc95dccc5ded54b1367e1707

## Места

- seat 1: slot=gpt-6.1-sol-high family=OpenAI nonce=d914d92c0195f942 verdict_sha256=7bfb396f2afb35aaae3f3fd2f2a6691e025f19c31c308f104f6768da0c4924da
- seat 2: slot=gemini-4-argon-high family=Google nonce=eb55f899f5e907e7 verdict_sha256=c306a30b01b2bf1103dabd7518c5aeccbbc41a9c782909e8f60e048e744510d2
- seat 3: slot=muse-wonder-full-1.0 family=Meta nonce=412abc6c48ed4382 verdict_sha256=32b9479747c04f210ad0e97cf12485de5db7845bc01ebf22978d6bcfaff66683

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
- votes: {'seat_1': 'AGREE', 'seat_2': 'DISPUTE', 'seat_3': 'AGREE'}
- text: RW-008 BLOCKER-OPINION — не зафиксирована точка входа инцидента; путь через хаб пакетом не чинится

### F-009
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-009 BLOCKER-OPINION — матрица верификации расходится с существующими тестами и даст ложную зелень

### F-010
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
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


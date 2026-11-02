# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: a63c0fc62f291f23726fcd23dd621d2a9bb658e2fc95dccc5ded54b1367e1707

## Места

- seat 1: slot=claude-sonnet-5-5-high family=Anthropic nonce=e39753df3abb604b verdict_sha256=3797495830763b73485d0ebd05a56213ca19a969cd2b706f1be49e287dd5b51b
- seat 2: slot=muse-wonder-full-1.0 family=Meta nonce=86286ac453e81ddb verdict_sha256=5fb7610864c95927e6ecef1869d98aa597f17a5e0ebeaf91d059eb9002a62fef
- seat 3: slot=gemini-4-argon-high family=Google nonce=e3bf0ebdb3692fca verdict_sha256=d1bf2da80722ef51ff5552036e4e1fdf1870a91d64789b99ad3f0522031f0cbc

## Находки

### F-001
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-001 BLOCKER-OPINION — ротация по "Request quota exhausted" сработает только для транзиентных ошибок, а пакет это не доказывает

### F-002
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-002 NON_BLOCKING — таблица `_IMAGE_FORMATS` с `b"RIFF"` и `b"GIF8"` расходится со «строгим» сниффом

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — подстрока `quota exhausted` слишком широкая, а два других маркера избыточны

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — новые форматы расширяют поверхность атаки на декодеры нижестоящего CLI

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — нет подтверждения прогона и несоответствие по файлам тестов

### F-007
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-007 BLOCKER-OPINION — кортеж `_IMAGE_FORMATS` в пакете противоречит заявленному строгому sniff

### F-008
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-008 BLOCKER-OPINION — не зафиксирована точка входа инцидента; путь через хаб пакетом не чинится

### F-009
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-009 BLOCKER-OPINION — матрица верификации расходится с существующими тестами и даст ложную зелень

### F-010
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-010 BLOCKER-OPINION — новый маркер квоты недостижим, если ошибка Zen не классифицирована как transient

### F-011
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-011 NON_BLOCKING — подписочная квота приравнена к per-IP, маркеры избыточны

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — читаемость WebP/GIF downstream и документация не закрыты

### F-012
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-012 NON_BLOCKING — Дублирование таблиц сигнатур и логики MIME-сниффинга между `server.py` и `core/tool_emulation.py`

### F-013
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-013 NON_BLOCKING — Неиспользуемое поле сигнатуры `magic` в кортеже `_IMAGE_FORMATS` после перехода на составные сигнатуры

### F-014
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-014 NON_BLOCKING — Избыточность частных подстрок квоты при наличии общего маркера `"quota exhausted"` в `_is_free_quota_error`


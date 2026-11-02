# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: b07eff26038e56e4eecdacfb46657cef17dbc4441031e6a7ffbdac36a1d9d759

## Места

- seat 1: slot=claude-sonnet-5-5-high family=Anthropic nonce=1693a7be4bfd7389 verdict_sha256=122fc58b839fd8f4798cfb033d93bf7360e8b5db1fcd07d8c2e70695ff85e697
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=e1ed9eb54a837317 verdict_sha256=e76d4feed0452d02f9f83cd778550bcbfdf0e4d988ce6fe22bf40b05575dcbb7
- seat 3: slot=gemini-4-argon-high family=Google nonce=efcfeb3f9feaa0ac verdict_sha256=b4d721ab8ce8d7b27b21cb910d182f2a85193c475a655a9274be9c746abf9caa

## Находки

### F-001
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-001 NON_BLOCKING — квота-маркер при любом HTTP-статусе (в т.ч. 401/403) уводит аккаунтную квоту в ротацию прокси

### F-002
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-002 NON_BLOCKING — широкий substring-матч и избыточная тройная проверка

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — таблица `_IMAGE_FORMATS` и `_sniff_image_mime` расходятся

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — изменение рантайм-поведения без фичефлага GigaRC

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — Новый вариант ошибки квоты проверен только на уровне классификатора

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — Тесты новых форматов подтверждают сигнатуры, но не чтение изображения моделью

### F-007
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-007 NON_BLOCKING — Декларативная таблица `_IMAGE_FORMATS` хранит укороченный префикс `magic`, который не используется в `_sniff_image_mime`


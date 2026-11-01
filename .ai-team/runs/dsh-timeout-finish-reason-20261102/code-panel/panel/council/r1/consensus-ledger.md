# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: 4de1d2af7f5114cd3545b1a03858579ed99fd4f35c5841f56c2cd6e820a532f0

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=c275dd66d20697e9 verdict_sha256=e3205507b210da712deaffd97b1d3690b06b5e2b967705de3f69fb26e94b86d5
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=4bb14f045f75c988 verdict_sha256=0ae6a39c3dce0a94792ae77ed5e96ff648549cc28399684de95d2d2e42bc88b4
- seat 3: slot=gpt-6.1-sol-high family=OpenAI nonce=19d02a386e971322 verdict_sha256=63ba5eb81af566df0e95b866fd9e70fab85ce719617d2957a0ecf25dbb87571c

## Находки

### F-001
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-001 NON_BLOCKING — Секция «Scope of Changes» в ревью-пакете приводит упрощённый псевдо-diff для `_parse_runtime_flags`

### F-002
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-002 NON_BLOCKING — Невалидный строковый `graceful_timeout_finish_reason` в `dynamic_config.json` тихо нормализуется в `"stop"` без сохранения previous `last-known-good` этого поля

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — Невалидное значение env молча уходит в fallback на config/default

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — Нормализация значения продублирована в двух местах

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — Полный набор тестов проекта не подтверждён

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — Тяжёлый путь проверки не показан


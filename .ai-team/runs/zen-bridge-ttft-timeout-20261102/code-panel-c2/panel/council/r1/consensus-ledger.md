# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: 50eaf21d2d799b7469d428a6ba845ba4e8771643e10fc252c63e0be1d83914c0

## Места

- seat 1: slot=claude-sonnet-5-5-high family=Anthropic nonce=d2c66f07f2dde5bb verdict_sha256=1361a41f60b74b5b4a8e2a9b9d000f514ca564cb34cab3a6eae45ffceb88a1c3
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=4d194e0b4a45796c verdict_sha256=580e847df4e0ce0e1d25c618360766c99dfd41770f78426bfce647aa450b1cf4
- seat 3: slot=muse-wonder-1.0 family=Meta nonce=f610b11f268eb88b verdict_sha256=5c7f803182299f8616052f7fb421b08c81ab28d951841dffb27b507ea1f1c8c4

## Находки

### F-001
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-001 BLOCKER-OPINION — в широком прогоне 7 регрессий и массовое падение `test_tool_emulation.py` остались без причины

### F-002
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-002 BLOCKER-OPINION — в `test_passthrough_deadline_env` изменён существующий ассерт, не относящийся к задаче

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — в serve-пути TTFT не освобождается для активного tool

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — нет тестов самого отказа: срабатывание TTFT и Idle, 504 и terminal SSE error

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — защита от Idle для tool в `opencode run` опирается на события `running`/`pending`, подтверждённые только фейками

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — устаревшие сообщения лога и нет GigaRC-флага для изменения поведения

### F-007
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-007 BLOCKER-OPINION — Serve обрывает активный tool по TTFT, если перед ним не было текста

### F-008
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-008 BLOCKER-OPINION — Отсутствует проверка полного кандидата изолированно от посторонних изменений

### F-009
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-009 NON_BLOCKING — Idle-тест не проверяет обязательную ошибку SSE

### F-010
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-010 BLOCKER-OPINION — Конфигурируемость таймаутов молча ограничена глобальным `TIMEOUT_S`, единый конфиг-объект отсутствует

### F-011
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-011 BLOCKER-OPINION — Три пути таймаутов дублируют логику с расходящейся семантикой вместо одного механизма

### F-012
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-012 BLOCKER-OPINION — Идентичность активного tool в `_ToolActivity` коллапсирует параллельные вызовы одного инструмента

### F-013
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-013 BLOCKER-OPINION — Понятие «первый токен» различается между путями: tool-событие завершает TTFT в Run/Stream, но не в serve

### F-014
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-014 BLOCKER-OPINION — Пакет не изолирован и не воспроизводим на чистом дереве: широкий прогон содержит необъяснённые регрессии

### F-015
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-015 NON_BLOCKING — В zen-дифф включён несвязанный сдвиг ожидания passthrough-таймаута


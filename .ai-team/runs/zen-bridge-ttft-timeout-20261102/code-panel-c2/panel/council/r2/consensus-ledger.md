# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: 50eaf21d2d799b7469d428a6ba845ba4e8771643e10fc252c63e0be1d83914c0

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=67d6fdc1ac086a69 verdict_sha256=e4e039eb74da3cf05e39d66596e7c6de1a2a17673516f15a1c0497f6b6c68b51
- seat 2: slot=muse-wonder-1.0 family=Meta nonce=4d065046d299177c verdict_sha256=6181b45e06575ae3836473c604099f05e61e41f192c1b46ec74a9051a276e4f8
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=6e641a1442abfe5c verdict_sha256=04b960178dffc5498be4e7144ecd2984a81661a501c8fe67fe89febdde8155af

## Находки

### F-001
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-001 BLOCKER-OPINION — в широком прогоне 7 регрессий и массовое падение `test_tool_emulation.py` остались без причины

### F-002
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-002 BLOCKER-OPINION — в `test_passthrough_deadline_env` изменён существующий ассерт, не относящийся к задаче

### F-003
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-003 NON_BLOCKING — в serve-пути TTFT не освобождается для активного tool

### F-004
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-004 NON_BLOCKING — нет тестов самого отказа: срабатывание TTFT и Idle, 504 и terminal SSE error

### F-005
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-005 NON_BLOCKING — защита от Idle для tool в `opencode run` опирается на события `running`/`pending`, подтверждённые только фейками

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — устаревшие сообщения лога и нет GigaRC-флага для изменения поведения

### F-007
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-007 BLOCKER-OPINION — Serve обрывает активный tool по TTFT, если перед ним не было текста

### F-008
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-008 BLOCKER-OPINION — Отсутствует проверка полного кандидата изолированно от посторонних изменений

### F-009
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-009 NON_BLOCKING — Idle-тест не проверяет обязательную ошибку SSE

### F-010
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AMEND'}
- text: RW-010 BLOCKER-OPINION — Конфигурируемость таймаутов молча ограничена глобальным `TIMEOUT_S`, единый конфиг-объект отсутствует

### F-011
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AGREE', 'seat_2': 'DISPUTE', 'seat_3': 'AMEND'}
- text: RW-011 BLOCKER-OPINION — Три пути таймаутов дублируют логику с расходящейся семантикой вместо одного механизма

### F-012
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AMEND'}
- text: RW-012 BLOCKER-OPINION — Идентичность активного tool в `_ToolActivity` коллапсирует параллельные вызовы одного инструмента

### F-013
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-013 BLOCKER-OPINION — Понятие «первый токен» различается между путями: tool-событие завершает TTFT в Run/Stream, но не в serve

### F-014
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-014 BLOCKER-OPINION — Пакет не изолирован и не воспроизводим на чистом дереве: широкий прогон содержит необъяснённые регрессии

### F-015
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-015 NON_BLOCKING — В zen-дифф включён несвязанный сдвиг ожидания passthrough-таймаута


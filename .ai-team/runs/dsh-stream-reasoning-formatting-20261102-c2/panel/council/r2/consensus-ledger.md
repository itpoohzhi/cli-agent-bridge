# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: af59adc83bc9e4e7cf153c51733d7855b1b70dbc500dbed663f7ec6987958bf3

## Места

- seat 1: slot=muse-wonder-full-1.0 family=Meta nonce=7225e9081ce88021 verdict_sha256=bdfa4cb61d038a435f735b97e3cfe085cc8c798c65eefe9442a856b34402b0df
- seat 2: slot=claude-sonnet-5-5-high family=Anthropic nonce=e20a8d83c3838e78 verdict_sha256=92af45a03dd5dbffc4c6dae4340b3ab5673020fc2d893fe0c00f2d5860eedc8c
- seat 3: slot=gpt-6.1-sol-high family=OpenAI nonce=cb93adb804ebc2ca verdict_sha256=33a5a9adcac9bc02cc9b612831918ab27e5f66e13dda10f679216a94c0eb77e2

## Находки

### F-001
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-001 NON_BLOCKING — Изоляция преамбул инструментов в `_TranscriptTail._emit_record` зависит от включённого `emit_content` (`planner_content_streaming_enabled`)

### F-002
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-002 NON_BLOCKING — В `Run.reconcile_result` при выдаче дельты-суффикса не обновляется `_content_emitted_wire`

### F-003
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-003 NON_BLOCKING — Хардкод дефолтных параметров таймаута и `max_tokens` в `scripts/smoke_models.py` без env-переменных

### F-004
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-004 NON_BLOCKING — Сквозной тест L2 `test_e2e_subagent_tool_preambles_isolated_to_reasoning` не проверяет вызов `on_activity`

### F-008
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-008 BLOCKER-OPINION — stdout обходит изоляцию tool-преамбул

### F-009
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-009 BLOCKER-OPINION — L3 признаёт оборванные и ошибочные потоки успешными

### F-010
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-010 BLOCKER-OPINION — шаги без индекса по-прежнему склеиваются

### F-011
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-011 BLOCKER-OPINION — заявленный L2 не проверяет сквозной SSE и непрерывность родителя

### F-005
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-005 BLOCKER-OPINION — универсальный L3 пропускает часть моделей канона

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — новый wire-буфер многократно копируется под общей блокировкой

### F-012
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-012 BLOCKER-OPINION — Поддерживаемый контрактом `step_index=None` обходит оба новых механизма: склейка строк сохраняется, преамбулы reasoning теряются

### F-013
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-013 NON_BLOCKING — Три источника правды о выданном контенте вместо одного; `Run.reconcile_result` неидемпотентен, логика разделителя продублирована

### F-014
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-014 NON_BLOCKING — `_scan` делает полный проход по всем снимкам на каждый чанк вопреки задокументированному инварианту «обхода всей истории нет»

### F-015
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-015 NON_BLOCKING — Контракт активации не описан: при холодных дефолтах весь набор REQ-001..003 выключен, дефолты `isolate` рассогласованы между слоями, проводка `Run` тестами не покрыта

### F-016
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-016 NON_BLOCKING — L3-смоук не валидирует `[DONE]` на успешном пути и не имеет общего дедлайна чтения SSE

### F-017
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-017 NON_BLOCKING — Агент-агностическая логика дедупликации и форматирования осела в монолите конкретного моста вопреки системному принципу проекта

### F-007
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-007 NON_BLOCKING — «Универсальный» смоук-раннер хрупко привязан к текущей форме `models.md` и к раскладке DSH


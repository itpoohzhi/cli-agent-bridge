# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: af59adc83bc9e4e7cf153c51733d7855b1b70dbc500dbed663f7ec6987958bf3

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=40e462cf89575fed verdict_sha256=bdfcefafde662e591136a0d9b6b0a41cf4f562074ebac4f19f6cdbf3a7d84374
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=172f5142579e057f verdict_sha256=4c2e09a29412a8d7b52d0386fe5cbdbe83933e4a52633df5cd4385fbb1225f5b
- seat 3: slot=muse-wonder-full-1.0 family=Meta nonce=8136c4e54f368f8f verdict_sha256=1ec3bebdea7e52e034916ec3d3eef7fd7ec0f90076e24859dbc3bb307aee30b6

## Находки

### F-001
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-001 NON_BLOCKING — Изоляция преамбул инструментов в `_TranscriptTail._emit_record` зависит от включённого `emit_content` (`planner_content_streaming_enabled`)

### F-002
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-002 NON_BLOCKING — В `Run.reconcile_result` при выдаче дельты-суффикса не обновляется `_content_emitted_wire`

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — Хардкод дефолтных параметров таймаута и `max_tokens` в `scripts/smoke_models.py` без env-переменных

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — Сквозной тест L2 `test_e2e_subagent_tool_preambles_isolated_to_reasoning` не проверяет вызов `on_activity`

### F-008
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-008 BLOCKER-OPINION — stdout обходит изоляцию tool-преамбул

### F-009
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-009 BLOCKER-OPINION — L3 признаёт оборванные и ошибочные потоки успешными

### F-010
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-010 BLOCKER-OPINION — шаги без индекса по-прежнему склеиваются

### F-011
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-011 BLOCKER-OPINION — заявленный L2 не проверяет сквозной SSE и непрерывность родителя

### F-005
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-005 BLOCKER-OPINION — универсальный L3 пропускает часть моделей канона

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — новый wire-буфер многократно копируется под общей блокировкой

### F-012
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-012 BLOCKER-OPINION — Поддерживаемый контрактом `step_index=None` обходит оба новых механизма: склейка строк сохраняется, преамбулы reasoning теряются

### F-013
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-013 NON_BLOCKING — Три источника правды о выданном контенте вместо одного; `Run.reconcile_result` неидемпотентен, логика разделителя продублирована

### F-014
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-014 NON_BLOCKING — `_scan` делает полный проход по всем снимкам на каждый чанк вопреки задокументированному инварианту «обхода всей истории нет»

### F-015
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-015 NON_BLOCKING — Контракт активации не описан: при холодных дефолтах весь набор REQ-001..003 выключен, дефолты `isolate` рассогласованы между слоями, проводка `Run` тестами не покрыта

### F-016
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-016 NON_BLOCKING — L3-смоук не валидирует `[DONE]` на успешном пути и не имеет общего дедлайна чтения SSE

### F-017
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-017 NON_BLOCKING — Агент-агностическая логика дедупликации и форматирования осела в монолите конкретного моста вопреки системному принципу проекта

### F-007
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-007 NON_BLOCKING — «Универсальный» смоук-раннер хрупко привязан к текущей форме `models.md` и к раскладке DSH


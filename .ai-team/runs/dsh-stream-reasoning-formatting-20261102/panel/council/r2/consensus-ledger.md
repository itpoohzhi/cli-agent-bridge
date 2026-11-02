# consensus-ledger.md — снимок после D1 (prior-ledger следующего раунда)

- round_dir: r2
- artifact_sha256: 678bb0ebdcca35b3a903fa81e9522f320ffdb8b956edb176c5c679015991a7f6

## Места

- seat 1: slot=muse-wonder-full-1.0 family=Meta nonce=eec80131ad6729bd verdict_sha256=e5537cfcd4c789b9f6a15f02d4a10609d3c1a88c1e5cad8a41d41075f0d5f479
- seat 2: slot=gpt-6.1-sol-high family=OpenAI nonce=f4f7ed7aa3a0323b verdict_sha256=462ed206354fb66914cd90cf7210e28aee8a5f00ed79345cc6af2d118fb65743
- seat 3: slot=claude-sonnet-5-5-high family=Anthropic nonce=0d69974e46492317 verdict_sha256=48a98a8ed816829e20c05662b8679e5d4f8edff149a799983a4e643152e5c0a2

## Находки

### F-001
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-001 NON_BLOCKING — Повторная эмиссия преамбулы в reasoning_content при множественных записях PLANNER_RESPONSE одного шага

### F-002
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-002 NON_BLOCKING — Асимметрия изоляции преамбул между каналами transcript и stdout и сброс _last_step_index при step_index=None

### F-003
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-003 NON_BLOCKING — Локализация общей логики нормализации стриминга в мосте agy-bridge вместо универсального ядра core/

### F-004
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-004 NON_BLOCKING — Хардкод параметров запроса и узкое регулярное выражение маскирования секретов в scripts/smoke_models.py

### F-005
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-005 NON_BLOCKING — Обход конструктора Run.__init__ через object.__new__ в синтетическом E2E-тесте L2

### F-009
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AGREE'}
- text: RW-009 BLOCKER-OPINION — в диффе есть недокументированный fallback повторной выдачи финального текста без теста и без строки в матрице VER

### F-010
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-010 BLOCKER-OPINION — изоляция преамбул включена по умолчанию, обходит дедупликацию арбитра, путь выключения не протестирован

### F-011
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-011 NON_BLOCKING — `_content_emitted_wire` хранит вторую полную копию стрима с квадратичной конкатенацией

### F-012
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-012 NON_BLOCKING — `_scan` заменяет bisect полным сканом с сортировкой на каждый вызов

### F-013
- class: BLOCKER-OPINION
- status: OPEN
- votes: {'seat_1': 'AGREE', 'seat_2': 'AMEND', 'seat_3': 'AMEND'}
- text: RW-013 BLOCKER-OPINION — L3-смоук не измеряет заявленный TTFT и даёт PASS без живой проверки

### F-006
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-006 NON_BLOCKING — «сквозной e2e L2» фактически юнит-уровень и дублирует L1

### F-007
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-007 NON_BLOCKING — заявленный скоуп пакета уже фактического диффа рабочего дерева

### F-008
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-008 NON_BLOCKING — тихая смена семантики graceful-finish и неточность метаданных пакета

### F-014
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-014 BLOCKER-OPINION — Изоляция reasoning не охватывает stdout

### F-015
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-015 BLOCKER-OPINION — Разделители и реконсиляция используют разные представления текста

### F-016
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-016 BLOCKER-OPINION — Повторное чтение транскрипта дублирует преамбулы в reasoning

### F-017
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-017 BLOCKER-OPINION — Заявленный L2 не проверяет сквозной контракт SSE

### F-018
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-018 BLOCKER-OPINION — Отсутствие канона моделей маскируется успешной проверкой

### F-019
- class: BLOCKER-OPINION
- status: RESOLVED
- votes: {'seat_1': 'AGREE', 'seat_2': 'AGREE', 'seat_3': 'AGREE'}
- text: RW-019 BLOCKER-OPINION — L3 не измеряет TTFT и не проверяет streaming/reasoning

### F-020
- class: NON_BLOCKING
- status: RESOLVED
- votes: {}
- text: RW-020 NON_BLOCKING — Префиксный поиск теперь просматривает всю историю снимков


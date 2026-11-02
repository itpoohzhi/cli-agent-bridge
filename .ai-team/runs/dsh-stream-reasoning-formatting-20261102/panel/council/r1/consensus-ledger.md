# consensus-ledger.md — снимок после R1 (prior-ledger следующего раунда)

- round_dir: r1
- artifact_sha256: 678bb0ebdcca35b3a903fa81e9522f320ffdb8b956edb176c5c679015991a7f6

## Места

- seat 1: slot=gemini-4-argon-high family=Google nonce=4bdcd91f9c96c9c9 verdict_sha256=eaaede14c0df6d120571438874ebcc574559a4403986250fc48d8ae3ab339257
- seat 2: slot=muse-wonder-full-1.0 family=Meta nonce=b08b7ffeb1d8bd5d verdict_sha256=ef70a38a47d1a72a4fc366c1a2153880a8f2c18d34d59802564c7142b30de5c5
- seat 3: slot=gpt-6.1-sol-high family=OpenAI nonce=4db6e0dc5aa091b3 verdict_sha256=a8f62f8b366afd30071c0a2d2e95bc83d10a212c8b8256dd00bfb5c8fe87eb3d

## Находки

### F-001
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-001 NON_BLOCKING — Повторная эмиссия преамбулы в reasoning_content при множественных записях PLANNER_RESPONSE одного шага

### F-002
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-002 NON_BLOCKING — Асимметрия изоляции преамбул между каналами transcript и stdout и сброс _last_step_index при step_index=None

### F-003
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-003 NON_BLOCKING — Локализация общей логики нормализации стриминга в мосте agy-bridge вместо универсального ядра core/

### F-004
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-004 NON_BLOCKING — Хардкод параметров запроса и узкое регулярное выражение маскирования секретов в scripts/smoke_models.py

### F-005
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-005 NON_BLOCKING — Обход конструктора Run.__init__ через object.__new__ в синтетическом E2E-тесте L2

### F-009
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-009 BLOCKER-OPINION — в диффе есть недокументированный fallback повторной выдачи финального текста без теста и без строки в матрице VER

### F-010
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-010 BLOCKER-OPINION — изоляция преамбул включена по умолчанию, обходит дедупликацию арбитра, путь выключения не протестирован

### F-011
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-011 NON_BLOCKING — `_content_emitted_wire` хранит вторую полную копию стрима с квадратичной конкатенацией

### F-012
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-012 NON_BLOCKING — `_scan` заменяет bisect полным сканом с сортировкой на каждый вызов

### F-013
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-013 BLOCKER-OPINION — L3-смоук не измеряет заявленный TTFT и даёт PASS без живой проверки

### F-006
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-006 NON_BLOCKING — «сквозной e2e L2» фактически юнит-уровень и дублирует L1

### F-007
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-007 NON_BLOCKING — заявленный скоуп пакета уже фактического диффа рабочего дерева

### F-008
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-008 NON_BLOCKING — тихая смена семантики graceful-finish и неточность метаданных пакета

### F-014
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-014 BLOCKER-OPINION — Изоляция reasoning не охватывает stdout

### F-015
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-015 BLOCKER-OPINION — Разделители и реконсиляция используют разные представления текста

### F-016
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-016 BLOCKER-OPINION — Повторное чтение транскрипта дублирует преамбулы в reasoning

### F-017
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-017 BLOCKER-OPINION — Заявленный L2 не проверяет сквозной контракт SSE

### F-018
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-018 BLOCKER-OPINION — Отсутствие канона моделей маскируется успешной проверкой

### F-019
- class: BLOCKER-OPINION
- status: OPEN
- votes: {}
- text: RW-019 BLOCKER-OPINION — L3 не измеряет TTFT и не проверяет streaming/reasoning

### F-020
- class: NON_BLOCKING
- status: OPEN
- votes: {}
- text: RW-020 NON_BLOCKING — Префиксный поиск теперь просматривает всю историю снимков


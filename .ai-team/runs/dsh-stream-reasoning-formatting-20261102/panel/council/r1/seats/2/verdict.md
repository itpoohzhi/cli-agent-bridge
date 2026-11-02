PANEL-NONCE: b08b7ffeb1d8bd5d
ARTIFACT-SHA256: 678bb0ebdcca35b3a903fa81e9522f320ffdb8b956edb176c5c679015991a7f6

Шляпа: РЕАЛИСТ. Независимо перепроверено: целевые тесты зелёны (`.venv/bin/pytest`: L2 3/3, три L1-теста стриминга 3/3, `GracefulTimeoutFinishReasonTests` 7/7), `--dry-run` смоука даёт 20 записей. Полный FULL-L1 (346, 3:40) не перепрогонялся — только сверено число собранных тестов (346). Дефектов класса BLOCKER-SAFETY не доказано.

### F-001 BLOCKER-OPINION — в диффе есть недокументированный fallback повторной выдачи финального текста без теста и без строки в матрице VER
Handler при `last_result_diverged` досылает `sep + final_text` целиком поверх уже выданных `pieces` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py:6264), [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py:6282)). В пакете (§1, VER-001..006) этот механизм не упомянут. Прямого теста ветки нет: поиск по тестам даёт только общий комментарий ([test_agy_bridge_resilience.py](/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_agy_bridge_resilience.py:4367)). Это ровно класс дефекта «дубль контента», который пакет чинит, — без regression-теста на дивергенцию с частично выданным текстом принимать нельзя. Минимум: тест Handler-уровня + строка VER, либо вынести fallback отдельным изменением.

### F-002 BLOCKER-OPINION — изоляция преамбул включена по умолчанию, обходит дедупликацию арбитра, путь выключения не протестирован
Дефолт `True` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py:2956), [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py:5242)) при том, что соседние флаги политики дефолтятся в `False`. При изоляции текст идёт напрямую в `self.emit(..., content + "\n\n")` мимо `_ContentArbiter` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py:4552)): повторная запись того же шага с выросшим `content` продублирует преамбулу в reasoning полностью, а не суффиксом. Тестов с флагом OFF и с повторным `_emit_record` одного шага нет (grep по обоим тестовым файлам пуст). Эксплуатационно нужен хотя бы тест kill-switch `AGY_ISOLATE_TOOL_PREAMBLES_TO_REASONING=0`.

### F-003 NON_BLOCKING — `_content_emitted_wire` хранит вторую полную копию стрима с квадратичной конкатенацией
Каждая выдача делает `emitted_wire + sep + suffix` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py:5331)), хотя для сепаратора нужны только последние 2 символа, а полный текст уже хранит арбитр ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py:3808)). На длинных ответах — лишние память и O(n²) копирований под `_emit_lock`. Замена на хвост из 2 символов — однострочное упрощение, стоит сделать до мержа.

### F-004 NON_BLOCKING — `_scan` заменяет bisect полным сканом с сортировкой на каждый вызов
`candidates = [t for t in texts ...]` + `sort` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py:3929)) вместо прежнего `bisect_left`. Корректность правдоподобна и покрыта тестами, но оценка стоимости при большом числе шагов не приведена. Для реалиста приемлемо при текущих лимитах шагов, но это сознательная деградация сложности — зафиксировать в описании или вернуть bisect-диапазон по префиксу кандидата.

### F-005 BLOCKER-OPINION — L3-смоук не измеряет заявленный TTFT и даёт PASS без живой проверки
Пакет заявляет «замер TTFT», но запрос нестриминговый (`"stream": False`) и меряется полное время ответа ([smoke_models.py](/Users/aazhiry1/work/src/cli-agent-bridge/scripts/smoke_models.py:119)). Ключ захардкожен `test-smoke-key` ([smoke_models.py](/Users/aazhiry1/work/src/cli-agent-bridge/scripts/smoke_models.py:110)) — против реального хаба `--live` предсказуемо упадёт по auth. При отсутствии `models.md` подставляется выдуманный список моделей ([smoke_models.py](/Users/aazhiry1/work/src/cli-agent-bridge/scripts/smoke_models.py:44)), и `--dry-run` всё равно печатает PASS. VER-005 — только dry-run; живой прогон, который [AGENTS.md](/Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md) делает обязательным гейтом, никем не показан. Гейт в нынешнем виде — театр: либо честный `--live` с env-ключом и стрим-TTFT, либо понизить статус L3 до «валидатор конфига».

### F-006 NON_BLOCKING — «сквозной e2e L2» фактически юнит-уровень и дублирует L1
Тесты собирают `Run` через `object.__new__` с ручным `setattr` ([test_stream_formatting_and_subagents.py](/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_stream_formatting_and_subagents.py:46)) и моками emit; SSE/Handler/wire-формат `reasoning_content` не проверяются. Три сценария повторяют L1-тесты из resilience-файла — двойная цена поддержки при рефакторинге `Run.__init__`. Честнее назвать L2 сценарными юнит-тестами и добавить один настоящий SSE-тест через Handler.

### F-007 NON_BLOCKING — заявленный скоуп пакета уже фактического диффа рабочего дерева
Пакет называет 5 файлов, но в [AGENTS.md](/Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md) тем же диффом добавлен не относящийся к REQ-007 п.5 про агент-агностичность (VER-006 грепает только заголовок регламента), а рабочее дерево содержит 27 изменённых файлов и неотслеживаемые `scripts/` и новый тест (`git diff --stat HEAD`). Приёмка «пакета» без изолированного коммита/ветки рискует утащить чужие прогоны. Нужен отдельный коммит ровно по списку §3.

### F-008 NON_BLOCKING — тихая смена семантики graceful-finish и неточность метаданных пакета
Невалидный непустой env теперь перебивает валидный `dynamic_config` в `stop` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py:3085)) — раньше проваливался к конфигу; в пакете это подано как «сброс в дефолт» без секции рисков/отката (её в пакете нет вовсе). Заявленные «13 подтестов» не бьются с фактом: 7 тестов / 94 subtests. На код не влияет, на доверие к матрице — влияет.

Итог реалиста: ядро исправлений (REQ-001..004) минимально, правдоподобно и подтверждено целевыми тестами. Блокируют приёмку не алгоритмы, а эксплуатационная обвязка: недокументированный fallback без теста (F-001), включённая по умолчанию изоляция без теста выключения и дедупа (F-002) и недоказанный живой L3 при обязательном гейте в AGENTS.md (F-005). Все три закрываются малыми доработками без перепроектирования.

VERDICT: NEEDS WORK

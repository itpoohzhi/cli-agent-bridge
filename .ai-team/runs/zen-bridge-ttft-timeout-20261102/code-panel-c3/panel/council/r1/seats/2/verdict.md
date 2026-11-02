PANEL-NONCE: 0e9aac6336ea2165
ARTIFACT-SHA256: e26ce551c7ff8ed5ab8220c339660271f43e1af0c9a20062d99a34cc854bdc30

### F-001 NON_BLOCKING — Три параллельные реализации одного предиката уже разошлись в гвардах
Доказательство: serve-путь проверяет TTFT с явным `not tool_state.has_active()` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:4873)), Run-путь дополнительно требует `not subagent_started_at` только для Idle ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:6789)), а стрим-Handler такого гварда не имеет и полагается на `_ToolActivity` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:8430)). Функционально пути сейчас эквивалентны за счёт установки `first_token_at` по tool-событиям, но любая будущая правка в одном месте молча разойдётся с двумя другими. Это цена 193 строк в трёх местах, а не дефект текущего поведения.

### F-002 NON_BLOCKING — В логах не различить, какой именно таймаут сработал
Доказательство: все три пути сводят исход к одному `exit_reason = "timeout"` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:4881)) и одному логу `opencode run split timeout (ttft/idle)` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:6795)). При разборе прод-инцидента «режет TTFT или Idle» придётся воспроизводить локально. Одна строка лога с типом таймаута закрыла бы вопрос.

### F-003 NON_BLOCKING — Конфигурация читается в двух разных режимах, оператор об этом не предупреждён
Доказательство: `TIMEOUT_S` заморожен на импорте модуля ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:335)), а `BRIDGE_ZEN_TTFT/IDLE/TOTAL_TIMEOUT_S` перечитываются из `os.environ` на каждый запрос ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:364)). Правка первых без рестарта не подхватится, вторых — подхватится. Работает, но при эксплуатации легко принять за «env не применился». Стартовый лог эффективных значений отсутствует.

### F-004 NON_BLOCKING — Молчаливая капа `total_timeout` значением `TIMEOUT_S`
Доказательство: `_zen_total_timeout` возвращает `min(TIMEOUT_S, ...)` ([server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:382)). Оператор, выставивший `BRIDGE_ZEN_TOTAL_TIMEOUT_S` выше глобального лимита, не получит ни ошибки, ни предупреждения. При дефолтном `TIMEOUT_S=1800` не мешает, но это скрытый приоритет одной env над другой.

### F-005 NON_BLOCKING — В пакет втянут несвязанный фикс теста passthrough-адаптера
Доказательство: правка ожидания `(10, 60, 420, 12)` → `(10, 300, 420, 12)` в [test_bridges_speedup_resilience.py](/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_bridges_speedup_resilience.py:60) чинит тест, красный уже на HEAD (`DEFAULT_IDLE_TIMEOUT_S = 300.0` в адаптере), и к TTFT/Idle zen-bridge отношения не имеет. Сама правка корректна, но «50 PASSED» в матрице частично обеспечены не фичей, а починкой чужого теста; для минимальности диффа это стоило вынести отдельно.

### F-006 NON_BLOCKING — Матрица верификации снята в грязном дереве, а не на чистом диффе из 3 файлов
Доказательство: сам пакет признаёт падения полного `test_realtime_reasoning.py`, воспроизводящиеся из-за «незакоммиченных правок вне diff пакета» (раздел 4 пакета). То есть 181 зелёный тест получен в окружении, которое получатель пакета воспроизвести не может. Таргетные сьюты фичи при этом покрывают все три пути (serve/Run/stream) позитивно и негативно, поэтому риск низкий, но чистая пересборка `git stash` → прогон матрицы стоила бы одного шага.

VERDICT: PASS

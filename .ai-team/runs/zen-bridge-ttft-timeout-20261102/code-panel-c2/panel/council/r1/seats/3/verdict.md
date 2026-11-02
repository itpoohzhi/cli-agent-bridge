PANEL-NONCE: f610b11f268eb88b
ARTIFACT-SHA256: 50eaf21d2d799b7469d428a6ba845ba4e8771643e10fc252c63e0be1d83914c0

### F-001 BLOCKER-OPINION — Конфигурируемость таймаутов молча ограничена глобальным `TIMEOUT_S`, единый конфиг-объект отсутствует
Доказательство: [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:335) задаёт `TIMEOUT_S` из env один раз при импорте, а [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:359) — [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:386): каждый из TTFT/Idle/Total обрезается через `min(TIMEOUT_S, ...)`. Операторское `BRIDGE_ZEN_TOTAL_TIMEOUT_S` выше `TIMEOUT_S` молча не сработает. Это скрытая связь вместо явного per-request конфига и противоречит заявленной полной конфигурируемости без хардкода.

### F-002 BLOCKER-OPINION — Три пути таймаутов дублируют логику с расходящейся семантикой вместо одного механизма
Доказательство: serve-путь использует `>=` и `_ServeToolState.has_active()` в [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:4865); `Run.on_idle` использует `>` плюс дополнительное условие `not subagent_started_at` в [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:6772); стриминговый watchdog использует `>` без subagent-условия в [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:8414). Общим вынесен только idle-предикат [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:394). Следующий таймаут или модель придётся править в трёх местах с риском нового расхождения.

### F-003 BLOCKER-OPINION — Идентичность активного tool в `_ToolActivity` коллапсирует параллельные вызовы одного инструмента
Доказательство: [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:411) — ключ строится как `callID or id or tool or "tool"`. Параллельные вызовы одного tool без стабильного id делят один ключ: завершение одного снимает idle-защиту для остальных ещё running вызовов. Для расширяемых tool/сабагентных протоколов это неустойчивая идентичность.

### F-004 BLOCKER-OPINION — Понятие «первый токен» различается между путями: tool-событие завершает TTFT в Run/Stream, но не в serve
Доказательство: в `Run` tool-событие выставляет `first_token_at` в [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:6838); в стриме — в [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:8513); в serve `first_token_at` выставляется только для reasoning/text в [server.py](/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py:4203). Метрика TTFT и момент перехода TTFT→Idle несопоставимы между транспортами.

### F-005 BLOCKER-OPINION — Пакет не изолирован и не воспроизводим на чистом дереве: широкий прогон содержит необъяснённые регрессии
Доказательство: сам пакет (раздел 4) фиксирует 25 упавших тестов широкого прогона, из них 7 проходят на `HEAD`, но падают на рабочем дереве, причина «не исследовалась», а `test_tool_emulation.py` исключён с массовыми падениями без разбора. При заявленных в разделе 3 только 3 файлах это означает, что вердикт по матрице из 132 тестов нельзя перенести на чистый коммит этого diff.

### F-006 NON_BLOCKING — В zen-дифф включён несвязанный сдвиг ожидания passthrough-таймаута
Доказательство: [test_bridges_speedup_resilience.py](/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_bridges_speedup_resilience.py:59) меняет дефолтный `idle_timeout_s` с 60 на 300 без соответствующего изменения источника в заявленных 3 файлах пакета. Это drive-by правка чужого контракта внутри zen-пакета; её место — отдельный пакет.

VERDICT: NEEDS WORK

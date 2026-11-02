PANEL-NONCE: 509c608fa156103f
ARTIFACT-SHA256: 9ea833eaa5cf7579802e170f25ad5b1da3f3b5477de1aed1134370b052b65f4e

Подтверждаю: прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`) и проектный файл правил `/Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md`.

Начинаю независимую проверку пакета `sliding-activity-window-20261102` (раунд R1, роль: ВИЗИОНЕР). Читаю целевые файлы из манифеста кандидата для верификации архитектурной согласованности, расширяемости и контрактов.
Дочитываю оставшиеся части `adapters/passthrough_adapter.py` и `tests/test_stream_resilience.py`, а также проверяю файл стоп-гейтов `hl-resilience-gates.md`.
PANEL-NONCE: 509c608fa156103f
ARTIFACT-SHA256: 9ea833eaa5cf7579802e170f25ad5b1da3f3b5477de1aed1134370b052b65f4e

Подтверждаю: прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`) и проектный файл правил `/Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md`.

## Независимая экспертиза R1 (Шляпа: ВИЗИОНЕР)

Решение устраняет корневую причину обрыва длительных стримов на 420-й секунде (`DEFAULT_TOTAL_TIMEOUT_S`) в `PassthroughAdapter`: после подтверждения SSE-стриминга (`resp.status == 200` и `text/event-stream`) управление временем жизни соединения корректно передаётся от статического настенного таймера к скользящему окну `_TimedSseReader` (`idle_timeout_s` + аварийный потолок `safety_cap_s`), а генерация собственных `: keepalive` отделена от входного потока апстрима (`last_input` vs `last_upstream`/`last_progress`).

Блокирующих замечаний нет. Ниже зафиксированы неблокирующие точки роста для долгосрочной архитектурной целостности.

### F-001 NON_BLOCKING — Дуализм `last_upstream` и `last_progress` ослабляет защиту TTFT от пустых/сервисных кадров апстрима
- **Доказательство:** [passthrough_adapter.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L666-L725), [passthrough_adapter.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L895-L910).
- **Суть:** В [relay_sse](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L895) задекларирован инвариант `Role/usage — служебные кадры: TTFT защищён до первого полезного токена` (`reader.last_progress` остаётся `None` до первого содержательного `delta`). Однако в [`_TimedSseReader.readline`](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L723-L724) любая непустая строка от апстрима (включая входящие комментарии `: ping` или пустые кадры `role: assistant`) обновляет `self.last_upstream = time.monotonic()`. Поскольку до первого полезного токена `activity_base` берёт `self.last_upstream` ([строки 699–703](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L699-L703)), апстрим, шлющий только сервисные кадры без токенов, будет продлевать `idle_remaining` вплоть до `safety_cap_s`. В свою очередь, после первого полезного токена (`last_progress is not None`) поле `last_upstream` перестаёт участвовать в расчёте `activity_base`. Инициализация `last_progress = self.start_time` и опора `activity_base` исключительно на семантический прогресс (при сохранении `last_input` для каденса keepalive) сделает модель состояния проще и строже.

### F-002 NON_BLOCKING — Таймаут сокета `conn.sock` при входе в SSE остаётся привязанным к `total_timeout_s`
- **Доказательство:** [passthrough_adapter.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L1364-L1367), [passthrough_adapter.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L1429).
- **Суть:** В [`PassthroughAdapter._open`](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L1429) на сокет выставляется `conn.sock.settimeout(min(self.limits.read_timeout_s, remaining))`, где `remaining` ограничено `total_timeout_s`. При дефолтах (`total_timeout_s=420`, `idle_timeout_s=300`) это безопасно, но если оператор настроит `BRIDGE_TOTAL_TIMEOUT_S` меньше `BRIDGE_IDLE_TIMEOUT_S` (например, жесткий бюджет на non-stream/TTFT и широкое окно ожидания в стриме), блокирующий `readline` в фоновом потоке упадёт по `socket.timeout` раньше, чем истечёт `idle_timeout_s`. При переходе в `streaming.set()` целесообразно переключать `conn.sock.settimeout(self.limits.read_timeout_s)`.

### F-003 NON_BLOCKING — Унификация константы окружения `BRIDGE_SAFETY_CAP_S` и legacy-алиаса с ядром
- **Доказательство:** [passthrough_adapter.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L78-L91), [passthrough_adapter.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/passthrough_adapter.py#L230-L232), [test_stream_resilience.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_stream_resilience.py#L575-L582).
- **Суть:** В `AdaptiveTimeoutController` и `TurnSessionManager` поддерживается прозрачный фолбэк `BRIDGE_SAFETY_CAP_S` -> `DROID_DSH_BRIDGE_SAFETY_CAP_S`, тогда как `PassthroughLimits.from_env` читает строковый литерал `"BRIDGE_SAFETY_CAP_S"` напрямую без вынесения в `ENV_SAFETY_CAP_S` и без legacy-фолбэка. Выравнивание констант обеспечит полную симметрию конфигурации между ядром и адаптером.

VERDICT: ACCEPT

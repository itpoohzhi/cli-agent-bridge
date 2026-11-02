PANEL-NONCE: 40e462cf89575fed
ARTIFACT-SHA256: af59adc83bc9e4e7cf153c51733d7855b1b70dbc500dbed663f7ec6987958bf3

Подтверждаю: прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`) и проектный файл правил [AGENTS.md](file:///Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md).

## Независимый аудит пакета приёмки (Cycle 2, роль: СКЕПТИК, раунд R1)

Проведена сквозная ревизия изменений в [server.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py), [test_stream_formatting_and_subagents.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_stream_formatting_and_subagents.py), [smoke_models.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/scripts/smoke_models.py) и [AGENTS.md](file:///Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md). Замечания предыдущего цикла (`RW-009..RW-019`) устранены корректно; критических дефектов безопасности (`BLOCKER-SAFETY`) и архитектурных блокеров (`BLOCKER-OPINION`) не обнаружено. Ниже зафиксированы неблокирующие замечания по краевым случаям.

### F-001 NON_BLOCKING — Изоляция преамбул инструментов в `_TranscriptTail._emit_record` зависит от включённого `emit_content` (`planner_content_streaming_enabled`)
- **Доказательство:** [`_TranscriptTail._emit_record`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py#L4551-L4563) и [`Run.__init__`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py#L5246-L5250).
- **Суть:** Ветка `if has_tools and isolate_tools:` вложена внутрь `if emit_content is not None and isinstance(content, str) and content.strip():` (`server.py:4551`). При кодовом дефолте `planner_content_streaming_enabled = False` (`server.py:2950`) колбэк `emit_content` в `Run.__init__` передаётся как `None` (`server.py:5246`), из-за чего преамбула инструмента из `PLANNER_RESPONSE` не направляется в `self.emit` (`reasoning_content`), хотя флаг `isolate_tool_preambles_to_reasoning` по умолчанию `True` (`server.py:2956`). Кроме того, при `idx is None` ключ дедупликации `key_idx = -1` (`server.py:4556`) схлопывает все шаги без `step_index` в один элемент `self._preambles_emitted`.

### F-002 NON_BLOCKING — В `Run.reconcile_result` при выдаче дельты-суффикса не обновляется `_content_emitted_wire`
- **Доказательство:** [`Run.reconcile_result`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py#L5345-L5361).
- **Суть:** На строках `server.py:5353-5355` при условии `text.startswith(emitted_wire)` метод возвращает недостающий хвост `text[len(emitted_wire):]`, но не дописывает его в `self._content_emitted_wire`. В штатном цикле [`Handler._execute`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge/server.py#L6281) `reconcile_result` вызывается однократно на терминальном событии `done`, поэтому к ошибке в рантайме это не приводит, но при повторном вызове `reconcile_result` вернёт тот же суффикс повторно.

### F-003 NON_BLOCKING — Хардкод дефолтных параметров таймаута и `max_tokens` в `scripts/smoke_models.py` без env-переменных
- **Доказательство:** [`smoke_test_model`](file:///Users/aazhiry1/work/src/cli-agent-bridge/scripts/smoke_models.py#L98-L122) и [`main`](file:///Users/aazhiry1/work/src/cli-agent-bridge/scripts/smoke_models.py#L210-L215).
- **Суть:** В нарушение п. 4 проектного `AGENTS.md` (запрет на хардкод эксплуатационных параметров без настройки через env) значения `timeout_s = 20.0` (`smoke_models.py:98`), `--timeout default=15.0` (`smoke_models.py:213`) и `"max_tokens": 15` (`smoke_models.py:120`) заданы литералами без чтения из `os.environ`.

### F-004 NON_BLOCKING — Сквозной тест L2 `test_e2e_subagent_tool_preambles_isolated_to_reasoning` не проверяет вызов `on_activity`
- **Доказательство:** [`SyntheticE2EAgentStreamTests.test_e2e_subagent_tool_preambles_isolated_to_reasoning`](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_stream_formatting_and_subagents.py#L150-L161).
- **Суть:** В [AGENTS.md](file:///Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md#L69) для уровня L2 заявлен инвариант скользящего окна активности (Sliding Activity Window), однако в L2-тесте при инициализации `_TranscriptTail` передаётся `on_activity=None` (`test_stream_formatting_and_subagents.py:158`). Рекомендуется передавать mock-колбэк и проверять его срабатывание на эмиссии чанков.

VERDICT: ACCEPT

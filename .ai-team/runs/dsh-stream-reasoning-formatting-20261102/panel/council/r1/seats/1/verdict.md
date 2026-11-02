PANEL-NONCE: 4bdcd91f9c96c9c9
ARTIFACT-SHA256: 678bb0ebdcca35b3a903fa81e9522f320ffdb8b956edb176c5c679015991a7f6

Подтверждаю: прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`) и проектный файл правил `/Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md`. Выполняю независимую ревизию пакета приёмки `dsh-stream-reasoning-formatting-20261102` в роли СКЕПТИК (раунд R1): проверяю затронутые файлы и точные строки изменений.
Продолжаю проверку `bridges/agy-bridge/server.py`: извлекаю точные номера строк и реализацию `_parse_runtime_flags`, `_ContentArbiter._scan`, `_TranscriptTail._emit_record` и `Run.offer_content`.
Читаю целевые блоки `bridges/agy-bridge/server.py` (строки 2950–3050, 3900–4020, 4490–4650, 5290–5390) с нумерацией строк для детального аудита инвариантов.
Читаю строки 3900–4000 (`_ContentArbiter._scan`) и 4500–4640 (`_TranscriptTail._emit_record`) файла `bridges/agy-bridge/server.py`.
Проверяю строки 4520–4565 (`_TranscriptTail._emit_record`), а также вызовы `offer_content` и инициализацию `_TranscriptTail` в `bridges/agy-bridge/server.py`.
Проверяю вызов `offer_content` из `_pump` (строки 5460–5520) и функцию `_new_flag` (строки 3040–3090) в `bridges/agy-bridge/server.py`.
Проверяю реализацию `_ContentArbiter.reconcile_result` и смежную логику в `bridges/agy-bridge/server.py` (строки 3995–4075).
PANEL-NONCE: 4bdcd91f9c96c9c9
ARTIFACT-SHA256: 678bb0ebdcca35b3a903fa81e9522f320ffdb8b956edb176c5c679015991a7f6

Подтверждаю: прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`) и проектный файл правил `/Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md`.

Независимая экспертиза пакета `dsh-stream-reasoning-formatting-20261102` (шляпа: **СКЕПТИК**, раунд **R1**). Обязательные проверки L1/L2/L3 проходят, доказанных дефектов безопасности (`BLOCKER-SAFETY`) и блокеров приёмки (`BLOCKER-OPINION`) не выявлено. Зафиксированы следующие архитектурные и эксплуатационные замечания (`NON_BLOCKING`):

### F-001 NON_BLOCKING — Повторная эмиссия преамбулы в reasoning_content при множественных записях PLANNER_RESPONSE одного шага
- **Доказательство:** `bridges/agy-bridge/server.py:4550-4552`
- **Детали:** В `_TranscriptTail._emit_record` при `has_tools and isolate_tools` преамбула `content + "\n\n"` отправляется напрямую через `self.emit(idx if idx is not None else 0, content + "\n\n", None)` в обход пошагового трекера дельт `_StepState` (`delivered_len` / `delivered_sha` в `_apply_final` на `bridges/agy-bridge/server.py:4562`) и в обход `_ContentArbiter`. Если для одного `step_index` в `transcript.jsonl` записывается несколько промежуточных снимков `PLANNER_RESPONSE` с `tool_calls` (или происходит перезапись `_in_rewrite`), преамбула будет продублирована в `reasoning_content` целиком, а не суффиксом.

### F-002 NON_BLOCKING — Асимметрия изоляции преамбул между каналами transcript и stdout и сброс _last_step_index при step_index=None
- **Доказательство:** `bridges/agy-bridge/server.py:5321-5330`, `bridges/agy-bridge/server.py:5485-5491`
- **Детали:** Изоляция преамбул шагов с `tool_calls` реализована только в `_TranscriptTail._emit_record` (`bridges/agy-bridge/server.py:4551`). Если включён `content_streaming` (`AGY_PLANNER_CONTENT_STREAMING_ENABLED=true`), поток `Run._pump` (`bridges/agy-bridge/server.py:5487`) передаёт `step_update` (`kind == "agent_response"`) из `stdout` напрямую в `offer_content` до появления информации о `tool_calls`. Кроме того, в `Run.offer_content` (`bridges/agy-bridge/server.py:5321,5330`) при поступлении фрагмента с `step_index=None` поле `self._last_step_index` перезаписывается в `None`, из-за чего на следующем нумерованном шаге условие `last_idx is not None and last_idx != step_index` не сработает и разделитель `\n\n` между шагами будет пропущен.

### F-003 NON_BLOCKING — Локализация общей логики нормализации стриминга в мосте agy-bridge вместо универсального ядра core/
- **Доказательство:** `bridges/agy-bridge/server.py:3918-3943`, `bridges/agy-bridge/server.py:4548-4556`, `bridges/agy-bridge/server.py:5318-5332`, `AGENTS.md:14-21`
- **Детали:** Пункт 5 проектного `AGENTS.md` («Системное, агент-агностическое решение по умолчанию») предписывает выносить нормализацию стриминга, разделение границ шагов и санитизацию/изоляцию сервисных преамбул при вызовах инструментов в универсальное ядро (`core/`). Сейчас `_ContentArbiter`, разграничение `\n\n` и флаг `isolate_tool_preambles_to_reasoning` реализованы локально внутри `bridges/agy-bridge/server.py`.

### F-004 NON_BLOCKING — Хардкод параметров запроса и узкое регулярное выражение маскирования секретов в scripts/smoke_models.py
- **Доказательство:** `scripts/smoke_models.py:93-100`, `scripts/smoke_models.py:106-116`, `scripts/smoke_models.py:185-187`, `scripts/smoke_models.py:209-211`, `AGENTS.md:13`
- **Детали:** В `scripts/smoke_models.py:106-115` параметры `timeout_s: float = 15.0`, `api_key: str = "test-smoke-key"` и `"max_tokens": 10` зашиты в коде без чтения переменных окружения (например, `SMOKE_TIMEOUT_S`, `SMOKE_MAX_TOKENS`, `HUB_API_KEY`), а `main()` (`scripts/smoke_models.py:209-211`) не передаёт `api_key` в `smoke_test_model`, что нарушает п. 4 `AGENTS.md` о полной конфигурируемости через env. Кроме того, `mask_secret` (`scripts/smoke_models.py:95-100`) маскирует только `Bearer [a-zA-Z0-9_\-\.]{8,}`, пропуская токены с символами `+/=:` и ключи в заголовках/URL без префикса `Bearer`.

### F-005 NON_BLOCKING — Обход конструктора Run.__init__ через object.__new__ в синтетическом E2E-тесте L2
- **Доказательство:** `tests/test_stream_formatting_and_subagents.py:51-63`
- **Детали:** В `test_e2e_multi_step_markdown_boundary_separation` экземпляр `srv.Run` создаётся через `object.__new__(srv.Run)` с ручной установкой 13 приватных полей через `setattr`. Такой подход хрупок к изменениям `Run.__init__` (`bridges/agy-bridge/server.py:5210-5243`) и не тестирует реальную инициализацию полей `_last_step_index` и `_content_emitted_wire` конструктором `Run`.

VERDICT: ACCEPT

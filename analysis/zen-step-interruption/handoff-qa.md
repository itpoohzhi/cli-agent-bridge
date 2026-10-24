# Handoff to QA / Verifier: Тестовые сценарии для `opencode-zen-bridge`

## 1. Позитивные сценарии (Positive)
- **QA-POS-01 (Парсинг `<tool_invoke>` и `<tool_call>`):** Проверить, что `ToolCallParser` (в потоковом режиме по чанкам) и `_parse_tool_call_blocks` (в пакетном режиме) одинаково извлекают `name` и `arguments` как из `<tool_invoke>...</tool_invoke>`, так и из `<tool_call>...</tool_call>`, а `_build_tool_Constraint` instrucтирует модель использовать `<tool_invoke>` (`[F-05]`, `[F-08]`).
- **QA-POS-02 (Маппинг встроенного тула `"shell"` OpenCode v2.1.2):** Проверить, что `NATIVE_TOOL_ALIASES` отображает `"shell"` в клиентский инструмент `Execute` / `Bash` / `run_command` (`[F-05]`).
- **QA-POS-03 (Успешный дозапрос при проглоченном `<tool_call>`):** Когда попытка 1 возвращает короткую преамбулу (`len=138..168`) и `step_finish` с `output_tokens=506, reasoning_tokens=156` (`non_reasoning_output=350`, дельта `>= 35`) без `tool_calls`, мост автоматически запускает попытку 2 с `_incomplete_tool_step_prompt` и возвращает клиенту `finish_reason="tool_calls"` без дублирования преамбулы в SSE (`[F-07]`, `[F-09]`).

## 2. Негативные сценарии и защита от ложных срабатываний (Negative)
- **QA-NEG-01 (Отсутствие ложного дозапроса на коротком финальном ответе с большим `reasoning`):** Когда модель возвращает короткий финальный ответ (`"Готово, все проверки пройдены."` или `"Ответ: 42."`) без признаков намерения вызвать инструмент, при этом `step_finish` содержит `tokens={"output": 400, "reasoning": 385}` (где `output` включает `reasoning`, `non_reasoning_output = 15 < 35`), `_is_incomplete_tool_step` ОБЯЗАН вернуть `False`, а мост — завершиться с `finish_reason="stop"` с первой попытки (`[F-09]`, `OPEN-01`).
- **QA-NEG-02 (Отсутствие ложного дозапроса на длинном структурированном ответе):** Если видимый текст длиннее `420` символов или содержит кодовые блоки ``` / таблицы `| col |` и заканчивается двоеточием в конце абзаца без проглоченных токенов и без маркера прерывания, `_is_incomplete_tool_step` возвращает `False`.

## 3. Граничные условия (Boundary)
- **QA-BND-01 (Порог `SWALLOWED_TOKENS_MIN = 35`):** Проверить границу `non_reasoning_output - visible_est == 34` (`False`, если текст — обычный ответ) и `== 35` (`True` при `len(visible_text) <= 600`) (`[F-02]`, `[F-08]`, `[F-09]`).
- **QA-BND-02 (Исчерпание `NATIVE_RETRY_LIMIT = 2`):** Если все `1 + NATIVE_RETRY_LIMIT` (3) попыток возвращают только преамбулу без `tool_calls`, мост прекращает ретраи и корректно возвращает накопленный текст с `finish_reason="stop"` (`[F-03]`, `[F-15]`).

## 4. Сценарии отказов (Failure Modes)
- **QA-FAIL-01 (Обрыв провайдера `ECONNRESET` посреди стрима):** При приходе события `etype == "error"` (`read ECONNRESET`) после частичного текста `Run._execute_once` и `Handler._stream_sse` немедленно останавливают `proc` (`_stop_proc`), отбрасывают синтетическое продолжение `"I was interrupted right before making tool calls."` (`_strip_interrupted_notice`) и выполняют дозапрос вызова тула (`[F-04]`, `[F-09]`, `[F-12]`).
- **QA-FAIL-02 (Таймаут и SSE keepalive при зависшем `stdout`):** При молчании `proc.stdout` дольше `KEEPALIVE_INTERVAL_S` (`15s`) в SSE-поток отправляется комментарий `: keepalive\n\n`, а при превышении `TIMEOUT_S` `_StdoutFeed` разблокирует ожидание и завершает процесс (`[F-06]`, `[F-15]`).

## 5. Регрессионный контур (Regression)
- **QA-REG-01:** Полный прогон существующего набора тестов моста `bridges/opencode-zen-bridge/tests/` (`350+` unit/property тестов) и корневого набора `tests/` (`219` тестов) без единого падения.

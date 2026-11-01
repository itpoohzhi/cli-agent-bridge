# 0020 — Универсальный Repetition Guard и нормализация вызовов invoke

## Status

Proposed, Draft Revision 3, 2026-11-01 (EYE-35048); approval PENDING panel review.

## Контекст

При обращении к модели Claude Code (`claude-haiku-5-5`) через шлюз `cli-agent-bridge` зафиксирован инцидент:
модель сорвалась в авторегрессионный цикл зацикливания служебного маркера `\n\n_placeholder`, повторив его 17 644 раза (247 КБ) до исчерпания `max_tokens: 64000` ([F-01]). После системного продолжения по лимиту токенов модель переключилась на сырой внутренний XML-формат вызова Anthropic (`<invoke:bash><invoke name="bash">...<parameter name="description">...`) вместо контрактного `<tool_call>` ([F-02]).

В текущем срезе ветки `dev` единственный парсер вызовов — `ToolCallParser` в `core/tool_emulation.py:518`. Он настроен исключительно на тег `<tool_call>` и не содержит защиты от циклов повторения. В результате любые иные конструкции, включая зацикленный текст и блоки `<invoke name="...">`, попадают в `content` как обычный текст, что приводит к утечке сотен килобайт мусора в пользовательский интерфейс DeepSeek Harness.

Согласно проектному правилу [AGENTS.md](~/Мой диск/Context/AGENTS.md) («Главный архитектурный принцип: универсальность и независимость от вендоров»), все исправления протоколов, стриминга и санитизации вызовов инструментов должны реализовываться системно и агент-агностически в универсальном ядре `core/` без правок вендорского кода и без специфичных костылей в адаптерах.

## Решение

### AD-001 — Контракт RepetitionGuard в core/ (соблюдение BND-001)
В `core/tool_emulation.py` добавляется вспомогательный класс `RepetitionGuard`:
1. **Инвариант BND-001 (ядро не читает окружение):** Ядро `core/` не обращается к `os.environ`. В `core/tool_emulation.py` фиксируются только константы по умолчанию:
   - `DEFAULT_MAX_REPETITION_REPEATS = 20`
   - `DEFAULT_MAX_REPETITION_TOKEN_LEN = 64`
   - `REPETITION_MIN_REPEATS = 3`
   - `REPETITION_MAX_REPEATS_CAP = 1000`
2. **Чтение конфигурации:** Переменные окружения читаются исключительно на слое адаптеров/сервера (`server.py`, `adapters/passthrough_adapter.py`):
   - `BRIDGE_REPETITION_MAX_REPEATS` (int 3..1000, fallback `DEFAULT_MAX_REPETITION_REPEATS`)
   - `BRIDGE_REPETITION_MAX_TOKEN_LEN` (int 8..512, fallback `DEFAULT_MAX_REPETITION_TOKEN_LEN`)
   Параметры передаются в конструктор `ToolCallParser(..., max_repetition_repeats=..., max_repetition_token_len=..., repetition_guard_enabled=...)`.
3. **Алгоритм детекции и предотвращение ложных срабатываний:**
   - Анализируются непустые строки и токены длиной 1..`max_token_len`.
   - **Исключения (False Positive Protection):** Guard игнорирует:
     - блоки внутри Markdown-кода (`_code_context(..., final=...) == "code"` — листинги, diff, таблицы ASCII);
     - чисто пробельные последовательности и пустые строки (`\n`, `\r\n`, пробелы, табы);
     - стандартные разделители синтаксиса Markdown (`---`, `===`, `***`).
   - Если один и тот же непробельный смысловой токен/строка (например, `_placeholder` или `\n\n_placeholder`) повторяется подряд более `max_repetition_repeats` раз:
     - В `strict_live=True` возбуждается `LiveParserError("upstream_repetition_loop: excessive token repetitions")`.
     - На уровне SSE-стриминга (`server.py` и `passthrough_adapter.py`) генерируется финальный error-фрейм `{"error": {"message": "upstream repetition loop detected", "type": "proxy_error", "code": 502}}`, после чего соединение немедленно закрывается без отправки терминального `[DONE]`.

### AD-002 — Интеграция парсинга формата Anthropic `<invoke>` в ToolCallParser
В `core/tool_emulation.py:ToolCallParser` добавляется распознавание блоков вызова инструментов Anthropic:
1. **Синтаксические формы:**
   - Стандартная форма: `<invoke name="TOOL_NAME"><parameter name="PARAM_NAME">VALUE</parameter>...</invoke>`
   - Префиксная форма: `<invoke:TOOL_NAME>...` (нормализуется к имени `TOOL_NAME`).
2. **Извлечение аргументов и сохранение типов:**
   - Парсер аккумулирует теги `<parameter name="...">` внутри блока `<invoke>`.
   - Значения параметров очищаются от краевых пробелов.
   - **Сохранение строковых типов:** Значения параметров остаются строками (`str`) по умолчанию (shell-команды вроде `true`, пути, флаги). Значение десериализуется через `json.loads` ТОЛЬКО если оно начинается с `{` или `[` (явный JSON-объект или список).
   - Собранный словарь аргументов валидируется и санитизируется через существующий механизм `sanitize_tool_call(call, tool_schemas, limits)`.
3. **Контракт вызова и проверка разрешенных инструментов:**
   - Вызов передаётся в существующий `on_tool_call` в виде стандартного плоского словаря:
     `{"id": "call_<hex24>", "name": TOOL_NAME, "arguments": args_dict}`
     без OpenAI-обёртки, сохраняя полную обратную совместимость со всеми потребителями `ToolCallParser`.
   - Если задан `allowed_tools` и вызванный инструмент в нём отсутствует:
     - В `strict_live=True` возбуждается `LiveParserError(f"unauthorized tool: {TOOL_NAME}")`.
     - В `strict_live=False` вызов отбрасывается без выполнения.

### AD-003 — Zero-Leakage сырого XML и изоляция в strict_live
1. Любые теги `<invoke>`, `</invoke>`, `<invoke:NAME>`, `<parameter>`, `</parameter>` задерживаются буфером парсера и ни при каких условиях не сбрасываются в `content`.
2. Если блок `<invoke>` оказывается повреждённым, незакрытым при EOF или содержит незарегистрированный инструмент:
   - В `strict_live=True` возбуждается `LiveParserError` (fail-closed, без утечки сырого XML).
   - В `strict_live=False` блок отбрасывается без сброса XML в контент.
3. Образцы тегов внутри блоков кода (` ``` ` и ` ` `) сохраняются в тексте благодаря проверке `_code_context`.

### AD-004 — Feature Flags (GigaRC) и интеграция в passthrough
1. **Динамические флаги GigaRC:**
   - `REPETITION_GUARD_ENABLED` (default `false`)
   - `INVOKE_NORMALIZATION_ENABLED` (default `false`)
   При значении `false` поведение парсера и passthrough-адаптера строго эквивалентно legacy-коду.
2. **Интеграция в passthrough_adapter.py:**
   В цикле `iter_sse_events` при наличии `delta.content` текст проверяется через экземпляр `RepetitionGuard(max_repeats=..., max_token_len=...)`. При обнаружении зацикливания вызывается сброс буферов choice и отправка `_error_frame(..., "upstream_repetition_loop", ...)`.
3. **Верификация:**
   Запуск автотестов выполняется стандартной командой репозитория:
   `PYTHONPATH=. .venv/bin/pytest tests/ -v`.

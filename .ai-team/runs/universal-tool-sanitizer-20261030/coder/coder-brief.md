# Coder Brief — ADR 0010 (universal-tool-sanitizer-20261030)

Скилл роли: `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md`

Ты — внешний сабагент роли `Coder` (модель `claude-sonnet-5-5`, effort `high`, транспорт `claude -p`).
Твоя задача — реализовать согласованное Советом Тимлидов архитектурное решение (ADR 0010: `docs/adr/0010-universal-tool-call-sanitization-bridge.md`) для универсальной санитизации аргументов tool_calls и распаковки `parallel` в шлюзе `cli-agent-bridge`.

## 1. Строгий контекст и инвариант
- В проекте действует жесткий архитектурный инвариант (см. `AGENTS.md`):
  Внешний вендорский софт (DeepSeek Harness, Claude Code, Cursor и др.) НЕ модифицируется — файлы `~/.dsh`, `app.asar`, `node_modules` и профили остаются полностью нетронутыми.
  Все изменения производятся исключительно в нашем коде `cli-agent-bridge`.

## 2. Что нужно реализовать

### А. В `core/tool_emulation.py`:
1. Реализовать чистые функции (без I/O):
   - `sanitize_tool_call(tool_call: ToolCall | dict, tool_schemas: dict[str, Any] | None = None) -> list[Any]`
   - `sanitize_tool_calls_list(tool_calls: list[Any], tool_schemas: dict[str, Any] | None = None) -> list[Any]`
   - Функции должны корректно работать как с экземплярами `ToolCall` (из `core.backend_adapter`), так и со стандартными словарями `dict` (`{"id": ..., "type": "function", "function": {"name": ..., "arguments": ...}}`), возвращая список объектов того же типа, что и входной элемент (если вход `ToolCall` -> список `ToolCall`, если `dict` -> список `dict`).
2. Логика санитизации одного вызова:
   а) **Распаковка `parallel`:**
      - Если имя вызова `parallel`: извлечь список подвызовов из `arguments.get("tool_uses")` или `arguments.get("calls")` или `arguments.get("tools")` (распарсить `arguments` из JSON-строки при необходимости).
      - Для каждого подвызова сформировать отдельный вызов инструмента: имя инструмента берется из `recipient_name` или `name` подвызова, аргументы — из `parameters` или `arguments` (сериализовать в JSON-строку при необходимости), ID генерируется заново: `f"call_{uuid.uuid4().hex[:24]}"`.
      - Рекурсивно применить `sanitize_tool_call` к каждому распакованному вызову и собрать плоский список `list`.
   б) **Санитизация аргументов (очистка пустых строк и fallback):**
      - Распарсить `arguments` в словарь `dict`. Если `arguments` не словарь и невалидный JSON — оставить как есть.
      - Если аргументы — словарь:
        - Поля маршрутизации `ROUTE_FIELDS = {"provider", "model", "reasoning_effort"}`:
          Если значение поля является строкой и `v.strip() == ""` -> УДАЛИТЬ это поле из словаря (чтобы потребитель унаследовал дефолтный маршрут).
        - Поле `justification`:
          Если значение поля является строкой и `v.strip() == ""`:
          - Если в аргументах присутствует ключ `sandbox_permissions` (не None и не пустой) -> заменить значение на fallback: `"Выполнение запрошенной операции"`.
          - Если `sandbox_permissions` отсутствует в аргументах -> УДАЛИТЬ поле `justification`.
        - Схемо-ориентированная очистка (если передан `tool_schemas` и найдена схема для имени инструмента):
          Из схемы извлечь список `required` полей: `schema.get("parameters", {}).get("required", [])`.
          Для любого другого строкового поля (не из `ROUTE_FIELDS` и не `justification`), если `v.strip() == ""` и имя поля НЕ входит в `required` -> УДАЛИТЬ его. Если входит в `required` -> сохранить пустую строку.
      - Сериализовать обновленный словарь обратно в JSON (`json.dumps(args, ensure_ascii=False)`).
   в) Скорректировать индексы `index` в возвращаемом списке вызовов, если это необходимо.
3. Реэкспортировать `sanitize_tool_call` и `sanitize_tool_calls_list` в `__all__` (или на уровне модуля), чтобы они были доступны для импорта.

### Б. В `server.py`:
1. Объявить feature-flag:
   `BRIDGE_SANITIZE_TOOL_CALLS = os.getenv("BRIDGE_SANITIZE_TOOL_CALLS", "true").lower() in ("true", "1", "yes")`
2. Импортировать `sanitize_tool_calls_list` из `core.tool_emulation`.
3. При формировании `tool_calls` для ответа:
   - В `POST /v1/chat/completions` (нестриминговый ответ, см. место где формируется `message["tool_calls"]`):
     Если `BRIDGE_SANITIZE_TOOL_CALLS` активен и `out.get("tool_calls")`:
     `out["tool_calls"] = sanitize_tool_calls_list(out["tool_calls"])`
   - В потоковом режиме (SSE), перед отправкой tool_calls клиенту:
     Убедиться, что `out["tool_calls"]` и события вызовов санитизированы до стриминга или при отправке.
   - Также в адаптерах при финализации хода (`finalize_turn` в `core/tool_emulation.py`), если вызовы формируются там: можно вызывать `sanitize_tool_calls_list` прямо в `finalize_turn`, если `emulate_tools` или при наличии вызовов!

### В. В `tests/test_tool_sanitizer.py`:
Написать модульные тесты на базе `unittest.TestCase`, покрывающие:
1. Удаление пустых `provider: ""`, `model: ""`, `reasoning_effort: ""` для вызова `subagent` (как для `ToolCall`, так и для `dict`).
2. Сохранение валидных непустых `provider="custom"`, `model="gpt-5"` и т.д.
3. Подстановка `justification="Выполнение запрошенной операции"`, когда задан `sandbox_permissions` и `justification` пустое.
4. Удаление `justification: ""`, когда `sandbox_permissions` отсутствует.
5. Распаковка инструмента `parallel`: вызов `parallel` с вложенными вызовами (`subagent`, `bash`) разворачивается в список вызовов верхнего уровня с новыми ID `call_*`, и к каждому применяется санитизация.
6. Сохранение пустой строки для полей, объявленных как `required` в переданной схеме, и удаление для опциональных полей.

## 3. Критерии приёмки
- Запуск: `python3 -m unittest tests/test_tool_sanitizer.py` завершается успешно (exit 0).
- Существующие тесты проекта не сломаны: `python3 -m unittest tests/test_bridge_strict.py` проходит успешно (exit 0).
- Код следует стилю проекта, строгой типизации и PEP 8.
- Файлы DSH / вендорские профили не затронуты.

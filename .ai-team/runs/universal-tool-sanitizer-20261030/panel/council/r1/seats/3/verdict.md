PANEL-NONCE: 50c6e7d91aa7227a
ARTIFACT-SHA256: f602786d011d752b1cf1a90e2241ecfa65c6dd6149bd9034a4f852156c94ddc2

Проверка выполнена только по тексту пакета. Код я не запускал и репозиторий не открывал. Дефектов безопасности и утечек не нашёл. Основные замечания: в дифф попала посторонняя смена контракта и расходятся ссылки на тесты в матрице трассировки.

### F-001 BLOCKER-OPINION — в дифф попала смена контракта reasoning_effort, которой нет в матрице трассировки
- `server.py` (блок `# (9) effort`, около строки 5210) заменяет ответ `400 unsupported_reasoning_effort` на молчаливый кламп вниз через новую `clamp_effort_downward`. Для неизвестного уровня подставляется `default_effort`.
- Эти изменения не относятся к задаче санитайзера. В матрице нет строки про effort-clamp, а в `tests/test_tool_sanitizer.py` нет тестов клампа.
- По всей видимости, это работа из другой задачи: в git status есть каталог `dsh-effort-downward-clamp-20261028`.
- Проектное правило «не менять согласованный внешний контракт без явной фразы в задаче» нарушено. «Не ломать обратную совместимость API» тоже.
- Нужно вынести кламп в отдельный MR или явно включить его в скоуп с ADR и тестами.

### F-002 BLOCKER-OPINION — ссылки на тесты в матрице трассировки не совпадают с фактическими тестами
- Матрица ссылается на `test_subagent_empty_strings_stripped`, `test_schema_required_preserved`, `test_parallel_unwrapped_to_multiple_calls`, `test_parallel_recursion_depth_limit`, `test_justification_with_sandbox_permissions` и `test_justification_without_sandbox_permissions`.
- В `tests/test_tool_sanitizer.py` таких имён нет. Там `test_empty_route_fields_removed_for_subagent`, `test_required_empty_kept_optional_empty_removed`, `test_parallel_unpacked_into_top_level_calls` и другие.
- Предел вложенности `_MAX_PARALLEL_DEPTH = 8` (`core/tool_emulation.py`, `_sanitize_call`) не покрыт ни одним тестом.
- Пункт F-005 (флаг) в матрице подтверждён файлом `test_tool_sanitizer.py`, но тестов серверной обвязки нет. Не проверены `BRIDGE_SANITIZE_TOOL_CALLS=false`, `add_call` в `server.py` и `_serve_json`.
- Для тестов `test_bridge_strict.py`, `fake_droid.py` и ADR в пакете нет диффа, хотя заявлен «Full Git Diff».

### F-003 NON_BLOCKING — схемо-зависимая очистка в продакшене мертва
- Ни один из вызовов `sanitize_tool_call(entry)`, `sanitize_tool_calls_list(...)` и `finalize_turn(..., sanitize=...)` не передаёт `tool_schemas`. Схемы передаются только в тестах.
- Реально работают только `ROUTE_FIELDS` и `justification`. Заявленное в F-001 удаление пустых необязательных строк по `required` в рантайме не срабатывает.
- Когда схемы всё же подключат, возникнет второй риск. Удаление пустых или пробельных необязательных строк (`new_str=""`, `separator=" "`) может поменять семантику вызова.

### F-004 NON_BLOCKING — `ROUTE_FIELDS` и `justification` удаляются безусловно, даже если поле `required`
- Ветка `key in ROUTE_FIELDS` в `_sanitize_arguments_dict` стоит раньше проверки `required`. Пустой `model`, `provider` или `justification` пропадает у любого инструмента, в том числе у клиентского, где поле обязательное.
- Для известной схемы нужно сначала проверять `required`.

### F-005 NON_BLOCKING — распаковка `parallel` не сверяется с заявленными клиентом инструментами и молча теряет элементы
- `_sanitize_call` разворачивает любой вызов с именем `*.parallel`. Если клиент сам объявил инструмент `parallel`, его вызов будет переписан.
- `_unpack_parallel` пропускает нераспознанные элементы (`not isinstance(item, dict)`, пустое имя) без сигнала. Из N запрошенных вызовов выполнится N−1.
- Имена вложенных вызовов не проверяются на существование в `tools` запроса.

### F-006 NON_BLOCKING — в `server.py` `add_call` теперь всегда ставит `item["index"]`, в том числе при выключенном флаге
- Строка `item["index"] = len(tool_calls)` выполняется и при `BRIDGE_SANITIZE_TOOL_CALLS=false`, поэтому выключенный флаг не возвращает прежнее поведение полностью. В non-stream-ответах у `tool_calls` может появиться ключ `index`, которого раньше не было. Это зависит от того, как `_serve_json` собирает ответ. В дифф эта часть не попала.

### F-007 NON_BLOCKING — флаг по умолчанию включён и задан через env
- `BRIDGE_SANITIZE_TOOL_CALLS` по умолчанию `true`, и это env-переменная. Директива канона требует для новых фич флаг удалённого конфига (`*_ENABLED`) с дефолтом `false`, то есть мгновенный kill-switch без рестарта.
- Если для этого проекта сделано исключение, его нужно записать в ADR 0010.

### F-008 NON_BLOCKING — тесты запущены через `unittest`, а проект требует `pytest tests/ -v`
- В пакете нет результата полного `pytest tests/ -v`, как требует `AGENTS.md`.

Положительное: чистые функции, не мутируют вход (есть тест на это). Невалидный JSON остаётся нетронутым. Повторный проход идемпотентен (есть тест). Вендорский код не затронут. 18 тестов по подсчёту совпадают с заявленными.

VERDICT: NEEDS WORK

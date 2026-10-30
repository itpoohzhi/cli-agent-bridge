PANEL-NONCE: 2d24a405688ea963
ARTIFACT-SHA256: f602786d011d752b1cf1a90e2241ecfa65c6dd6149bd9034a4f852156c94ddc2

AGREE RW-001 — проверил по диффу пакета: `server.py` меняет обработку `reasoning_effort` (вместо 400 теперь `clamp_effort_downward`, плюс правка докстринга), а это не относится ни к одному из F-001..F-007. В исходном `git status` изменены `tests/test_bridge_strict.py` и `tests/fake_droid.py`, но в «Full Git Diff» их нет, хотя строгий контракт под них переписан.

AGREE RW-002 — проверил по диффу: `finalize_turn.add_call` вызывает `sanitize_tool_call(entry)`, `Handler.add_call` в `server.py` делает то же, а `_serve_json` вызывает `sanitize_tool_calls_list(out["tool_calls"])`. Ни один вызов не передаёт `tool_schemas`, поэтому `_required_fields` всегда возвращает None. Ветка очистки по схеме работает только в юнит-тестах, в рантайме она мертва.

AGREE RW-003 — проверил `core/tool_emulation.py`, `_sanitize_arguments_dict`: проверка `key in ROUTE_FIELDS` и ветка `justification` идут раньше проверки `required`. Пустые `provider`/`model`/`reasoning_effort`/`justification` удаляются даже тогда, когда схема помечает их обязательными. Это противоречит заявлению F-001 «Required properties keep empty strings».

AGREE RW-004 — проверил `_sanitize_arguments_dict`: при пустом `justification` и непустом `sandbox_permissions` мост подставляет `JUSTIFICATION_FALLBACK`. Модель такого обоснования не давала, а оно предназначено для approval-промпта эскалации прав. Подстановка шаблонного текста вводит в заблуждение того, кто одобряет запрос, и не должна идти по умолчанию без явного решения владельца.

VERDICT: NEEDS WORK

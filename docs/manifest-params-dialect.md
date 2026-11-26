# Диалект параметров из манифеста: `backends.<id>.params`

REQ-004 (`thinking-ssot`). Диалект reasoning/thinking бэкенда живёт в манифесте провайдера
(`providers.d/<id>.yaml`, блок `params`), компилируется в `fleet.json` и читается рантаймом
passthrough из `adapter.config["params"]`. Захардкоженные карты провайдеров остаются только в
legacy-ветке.

## Схема `backends.<id>.params`

Закрытый набор ключей (`core/backend_params.py`, `validate_backend_params`; иначе
`backend_params_invalid`):

| Ключ | Тип | Смысл |
|---|---|---|
| `effort_field` | `reasoning_effort` \| `effort` \| `none` | поле тела, в которое попадает effort; `none` — бэкенд не принимает effort-поле |
| `effort_map` | `{уровень: строка \| объект}` | перевод логического уровня; объект-патч (напр. `off` -> `{"thinking": {"type": "disabled"}}`) подмешивается в тело |
| `adaptive_whitelist` | `[строка]` | параметры из `GLOBAL_WHITELIST`, разрешённые к адаптации по ответу апстрима |
| `strip_always` | `[строка]` | ключи тела, которые бэкенд никогда не принимает; снимаются всегда |

Оба компилятора (`core/compile_model_records.py`, `core/fleet_compiler.py`) сериализуют
`manifest.params` одним хелпером `extract_backend_params`; дефолтный диалект не пишется.
Загрузчик (`core/backend_adapter.py`) принимает `params` как известный ключ `backends.<id>`.

Пример (`opencode-go-claude`): `effort_field: reasoning_effort`, `adaptive_whitelist: [reasoning_effort]`,
`strip_always: [thinking]`.

## Конвейер (`core/manifest_dialect_dispatch.py`)

1. `params` отсутствует/невалиден — legacy-ветка (`_apply_legacy_passthrough_transforms`).
2. Логический уровень канонизируется (`core/logical_effort.py`): `thinking: {"type": "disabled"}`,
   `reasoning_effort: "off"|"none"` -> `off`. Если у диалекта есть `effort_map["off"]`, `off`
   переводится патчем (`neuralwatt`: `reasoning_effort: "none"`; `opencode-go`: `thinking: disabled`).
3. Кворумный вызов (`X-Subagent-Id` / `X-Review-Profile: zero-canon`): явный `thinking`/`effort`,
   который `strip_always` снял бы без перевода, — `ParamDegradedError`, ответ
   `422 param_degraded` + `X-Bridge-Degraded: <param>`. Перевод `thinking: disabled` в `off`
   деградацией не считается. Не кворумный вызов снимает ключ молча.
4. `normalize_params`; при `effort_field == "none"` и отсутствии записи в `effort_map` исходный
   ключ effort сохраняется; затем `strip_always`.
5. `clamp_thinking_budget` — только если после снятия `thinking` остался `{"type": "enabled"}`;
   снятый `thinking` не восстанавливается.

## Fail-closed effort (AD-006)

`clamp_effort_downward` не повышает уровень: известный уровень ниже `min(allowed)` ->
`EffortBelowFloorError` (подкласс `EffortValidationError`) -> HTTP 400 `unsupported_reasoning_effort`
(passthrough и `core/native_effort.py`); алиас ниже floor не регистрируется (предупреждение в журнале).

## Флаг и откат

`BRIDGE_MANIFEST_PARAMS_NORMALIZE_ENABLED` (дефолт `true`). `false`/`0` — мгновенный возврат к
legacy-ветке, побайтно совпадающей с прежним поведением (тест
`test_rollback_flag_is_byte_identical_to_legacy`). Флаг читается динамически, рестарт не нужен.
Откат не требует правок `fleet.json`.

## Проверки

`tests/test_backend_params_compile.py`, `tests/test_manifest_dialect_dispatch.py`,
`tests/test_manifest_dialect_models.py`, `tests/test_effort_floor_fail_closed.py`.

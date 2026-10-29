# Консолидированный реестр находок Раунда R1 (`panel/council/r1/consensus-ledger.md`)

- **Run ID:** `agy-image-input-fix-20261029`
- **Stage:** `council` (`mode=code`)
- **Round:** `r1`
- **Artifact:** `.ai-team/runs/agy-image-input-fix-20261029/teamlead/package.md` (`sha256=8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689`)
- **Итоги R1 (анонимизировано):**
  - **Judge A (Скептик):** `NEEDS_WORK` (`Блокеров: 0 | Существенных: 3 | Замечаний: 1`)
  - **Judge B (Реалист):** `ACCEPT` (`Блокеров: 0 | Существенных: 0 | Замечаний: 0`)
  - **Judge C (Визионер):** `ACCEPT` (`Блокеров: 0 | Существенных: 0 | Замечаний: 1`)

## Сводная таблица открытых пунктов для дебатов `D1` (`F-001..F-005`)

| ID | Источник (анонимно) | Исходный класс | Якорь | Формулировка находки | Результат `RECHECK` |
|---|---|---|---|---|---|
| `F-001` | Judge A (`C1`) | `MAJOR` | `server.py:3455-3480, 3762, 3809, 3825` | В потоковом режиме (`stream=true`) `_serve_sse` отправляет HTTP 200 и стартовый чанк до `_run_once`, поэтому отказ `F-002` (отключение флага во время ожидания слота) или `ImageSpoolError` передаются терминальным SSE-событием `data: {"error": ...}` поверх HTTP 200. | Первичная валидация `_collect_images` в `_prepare_turn` (`server.py:3762`) выполняется ДО `_serve_sse` и возвращает HTTP 400 JSON. Ранний старт SSE до `_acquire_slot()` нужен для отправки `: keepalive` во время ожидания слота. Рекомендация: `AMEND F-001 — priority=non-blocking`. |
| `F-002` | Judge A (`C2`) | `MAJOR` | `server.py:869, 944-961` | В `_stage_images` локальная переменная `raw` удерживает декодированные байты текущей картинки до следующей итерации / выхода из `_stage_images`. | До `_acquire_slot()` в `_collect_images` (`server.py:869`) выполняется `del raw` и хранится `b""` (0 байт в очереди слота). В `_stage_images` буфер одного файла освобождается сразу при выходе из функции до `Run()`. Рекомендация: `AMEND F-002 — priority=non-blocking`. |
| `F-003` | Judge A (`C3`) | `MAJOR` | `tests/test_agy_bridge_resilience.py:5247` | В `test_res01` проверяются параллельные слоты, FD и очистка `img-*`, но используются компактные фикстуры без жёсткого таймера латентности на 20 МБ. | Лимиты 20 МБ и отсечение до `b64decode` проверены в `test_img04`/`test_img05`/`test_f003`; отказ от жёсткого wall-clock таймера в `test_res01` исключает флаки под нагрузкой. Рекомендация: `AMEND F-003 — priority=non-blocking`. |
| `F-004` | Judge A (`C4`) | `MINOR` | `server.py:3914-3918` | В `_sweep_workspace` счётчик `removed` увеличивается после `shutil.rmtree(..., ignore_errors=True)` без перепроверки удаления. | Неблокирующее замечание `MINOR`. Рекомендация: `AGREE F-004` (`priority=non-blocking`). |
| `F-005` | Judge C (`MINOR`) | `MINOR` | `fleet.json:4-11` | В `technical_ref` строка `models_source`/`effort_ladders` упоминает `1.3.1` при `agy_version: "1.4.9"`. | Неблокирующее документационное замечание `MINOR`. Рекомендация: `AGREE F-005` (`priority=non-blocking`). |

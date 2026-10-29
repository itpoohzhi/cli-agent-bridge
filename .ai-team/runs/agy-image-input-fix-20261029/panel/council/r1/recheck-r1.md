# Факт-проверка находок Раунда R1 (`panel/council/r1/recheck-r1.md`)

- **Run ID:** `agy-image-input-fix-20261029`
- **Проверяемый артефакт:** `.ai-team/runs/agy-image-input-fix-20261029/teamlead/package.md` (`sha256=8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689`)

## RECHECK F-001 (Judge A `C1` — `MAJOR`: при `stream=true` отказы после ожидания слота `F-002` и `ImageSpoolError` уходят SSE-событием `error` поверх уже отправленного HTTP 200):
Проверка по `bridges/agy-bridge/server.py:3455-3480, 3762, 3805-3835`:
1) Вся первичная валидация `_collect_images` (включая проверку `_is_image_input_enabled()`, `_image_proof_reason()`, лимитов и сигнатур) выполняется в `_prepare_turn` (`server.py:3762`) **ДО** вызова `_serve_sse` и отправки заголовков HTTP 200. Поэтому 100% штатных отказов по картинкам и при `stream=false`, и при `stream=true` возвращают чистый HTTP 400 JSON до открытия SSE-потока.
2) В `_serve_sse` (`server.py:3809`) отправка заголовка HTTP 200 и стартового чанка роли `assistant` до `_run_once` (`_acquire_slot()`) — это намеренная базовая архитектура SSE-keepalive моста `agy-bridge` (во время ожидания свободного слота `MAX_PARALLEL=2` мост шлёт `: keepalive\n\n`, чтобы клиент DSH не оборвал соединение по таймауту заголовков). Если за время ожидания в очереди администратор переключил `IMAGE_INPUT_ENABLED=false` (`F-002`) или произошёл `ImageSpoolError`, `_serve_sse` (`server.py:3825-3833`) штатно отправляет терминальный SSE-фрейм `data: {"error": {"message": ..., "type": ..., "code": 400|500}}` и `data: [DONE]` — точно так же, как для `timeout`, `busy` и `upstream_failed`.
Рекомендация RECHECK для D1: `AMEND F-001 — priority=non-blocking` (штатное поведение SSE-стриминга после отправки стартового keepalive-чанка; не является блокером приёмки).

## RECHECK F-002 (Judge A `C2` — `MAJOR`: локальная переменная `raw` внутри цикла `_stage_images` удерживает ссылку на декодированные байты текущей картинки до конца итерации/функции):
Проверка по `bridges/agy-bridge/server.py:869, 944-961`:
1) В `_collect_images` (`server.py:869`) сразу после проверки сигнатур выполняется `del raw`, а в словарь сохраняется `"data": b""` — поэтому во время ожидания семафора `_acquire_slot()` в памяти удерживается **0 байт** декодированных картинок (главная цель `F-004`).
2) Внутри `_stage_images` (`server.py:944-961`) переменная `raw` создаётся поштучно для одного файла (`<= 20 MiB`), сразу записывается на диск в `with os.fdopen(fd, "wb") as f: f.write(raw)` и автоматически освобождается при выходе из `_stage_images` **ДО** запуска дочернего процесса `agy` (`Run(...)`). Одновременно в памяти никогда не находится более одного декодированного изображения.
Рекомендация RECHECK для D1: `AMEND F-002 — priority=non-blocking` (инвариант памяти до слота и до запуска `agy` выполнен; явный `del raw` внутри цикла `_stage_images` — косметическое микро-улучшение).

## RECHECK F-003 (Judge A `C3` — `MAJOR`: в `test_res01` проверяются конкурентность, слоты, FD и очистка `img-*`, но нет жёсткого таймера латентности на 20 МБ фикстуре):
Проверка по `tests/test_agy_bridge_resilience.py:5247` и `VER-003`/`VER-005`:
1) В `test_res01_concurrent_turns_bounded_by_slots_without_fd_or_dir_leaks` проверены: (а) ограничение одновременных запусков семафором `MAX_PARALLEL=2` (`peak <= 2`), (б) отсутствие утечек файловых дескрипторов (`fd_after <= fd_before`), (в) отсутствие оставшихся `img-*` каталогов после завершения конкурентной пачки.
2) Граничные размеры 20 МБ и отсечение до `b64decode` проверены детерминированными тестами `test_img04`, `test_img05` и `test_f003`, а полный прогон 146 тестов укладывается в ~115 с без флаков по CPU-таймингам.
Рекомендация RECHECK для D1: `AMEND F-003 — priority=non-blocking` (все функциональные и ресурсные инварианты `F-005`/`RES-01` доказаны).

## RECHECK F-004 (Judge A `C4` — `MINOR`: счётчик `removed` в `_sweep_workspace` инкрементируется после `shutil.rmtree(..., ignore_errors=True)`):
Проверка по `bridges/agy-bridge/server.py:3914-3918`:
Замечание изначально имеет неблокирующий класс `MINOR`.
Рекомендация RECHECK для D1: `AGREE F-004` (`priority=non-blocking`).

## RECHECK F-005 (Judge C `MINOR` — в `bridges/agy-bridge/fleet.json` комментарий `models_source`/`effort_ladders` упоминает `1.3.1` при `agy_version: "1.4.9"`):
Проверка по `bridges/agy-bridge/fleet.json:4-11`:
Замечание изначально имеет неблокирующий класс `MINOR` и относится к справочному комментарию в `technical_ref`.
Рекомендация RECHECK для D1: `AGREE F-005` (`priority=non-blocking`).

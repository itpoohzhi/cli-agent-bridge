# Консенсус-леджер находок Архитектурного Совета — после дебатов `D1` (`panel/arch/r2`)

- **Run ID:** `agy-image-input-fix-20261029`
- **Раунд D1:** `.ai-team/runs/agy-image-input-fix-20261029/panel/arch/r2` (`panel-proof.json` `sha256=b271adbfb7199a8ec6bd299975fea28f906231beb9ee2af5f9c7f7daccab4ab8` `verify_panel_proof exit=0`)
- **Проверяемый артефакт:** `.ai-team/runs/agy-image-input-fix-20261029/architecture/architecture-packet.json` (`sha256=ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466`)
- **Итог дебатов D1:** единогласно `3/3 PASS` (`Seat 1` `gemini-4-argon-high` = `PASS`, `Seat 2` `muse-wonder-full-1.0` = `PASS`, `Seat 3` `claude-sonnet-5-5-high` = `PASS`; `blocking_open = 0`).

---

## Статусы карточек находок F-001..F-010 после D1

### F-001
- origin: R1 Seat 1 (`muse-wonder-full-1.0` F-001) + R1 Seat 2 (`claude-sonnet-5-5-high` F-010)
- rev: 2
- priority: non-blocking
- status: AMENDED
- outcome: non-blocking
- votes: `Seat 1: AMEND non-blocking`, `Seat 2: AMEND non-blocking`, `Seat 3: AMEND non-blocking` (`3/3`)
- text: Обязательный гейт верификации L2/L3 (обе модели `gemini-4-argon`, `gemini-3.8-flash` и 4 формата `PNG`, `JPEG`, `GIF`, `WebP`) перед включением `IMAGE_INPUT_ENABLED=true` в `dynamic_config.json`; кодовый дефолт в `bridges/agy-bridge/server.py` строго `False` (fail-closed).

### F-002
- origin: R1 Seat 1 (`muse-wonder-full-1.0` F-002)
- rev: 2
- priority: non-blocking
- status: AMENDED
- outcome: non-blocking
- votes: `Seat 1: AMEND non-blocking`, `Seat 2: AMEND non-blocking`, `Seat 3: AMEND non-blocking` (`3/3`)
- text: В `Handler._run_once` сразу после `_acquire_slot()` непосредственно перед `_stage_images()` и запуском `Run` повторно проверять `_is_image_input_enabled()` и `_image_proof_reason(model_id, effort)`; при отказе возвращать HTTP 400 (`image_input_not_supported` / `unsupported_reasoning_effort`) с 0 `mkdir` и 0 `spawn`.

### F-003
- origin: R1 Seat 1 (`muse-wonder-full-1.0` F-003)
- rev: 2
- priority: non-blocking
- status: AMENDED
- outcome: non-blocking
- votes: `Seat 1: AMEND non-blocking`, `Seat 2: AMEND non-blocking`, `Seat 3: AMEND non-blocking` (`3/3`)
- text: В `_collect_images` проверять количество вложений (`<= 16`) и оценку верхней границы декодированного размера по длине base64-строки ДО вызова `base64.b64decode(..., validate=True)`, сохраняя канонические коды отказа (`too_many_images`, `image_too_large`, `images_too_large`, `invalid_image_base64`).

### F-004
- origin: R1 Seat 1 (`muse-wonder-full-1.0` F-005) + R1 Seat 2 (`claude-sonnet-5-5-high` F-002)
- rev: 2
- priority: non-blocking
- status: AMENDED
- outcome: non-blocking
- votes: `Seat 1: AMEND non-blocking`, `Seat 2: AMEND non-blocking`, `Seat 3: AMEND non-blocking` (`3/3`)
- text: Конструктивное ограничение памяти декодированных изображений до захвата слота: в `_collect_images` (до `_acquire_slot()`) валидировать каждое изображение по одному без удержания декодированных `bytes`-буферов в очереди ожидания слота (материализовать декодированные байты на диск внутри `_stage_images` только после захвата одного из 8 слотов и очищать буфер сразу после `os.write`), а также освобождать ссылки на сырое тело запроса до ожидания слота.

### F-005
- origin: R1 Seat 2 (`claude-sonnet-5-5-high` F-001, F-005)
- rev: 2
- priority: non-blocking
- status: AMENDED
- outcome: non-blocking
- votes: `Seat 1: AMEND non-blocking`, `Seat 2: AMEND non-blocking`, `Seat 3: AMEND non-blocking` (`3/3`)
- text: Включить в `tests/test_agy_bridge_resilience.py` детерминированный интеграционный L2/`RES-01` тест с фейковым `AGY_LAUNCHER`, проверяющий полный HTTP-путь, параллельные запросы при занятых слотах, отсутствие утечек FD (`0` незакрытых дескрипторов), латентность валидации+staging и удаление `img-*`.

### F-006
- origin: R1 Seat 1 (`muse-wonder-full-1.0` F-004) + R1 Seat 2 (`claude-sonnet-5-5-high` F-009)
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- votes: `Seat 1: AGREE non-blocking`, `Seat 2: AGREE non-blocking`, `Seat 3: AGREE non-blocking` (`3/3`)
- text: В `bridges/agy-bridge/server.py`: (1) санитизировать управляющие символы в `model` при записи в лог; (2) регистронезависимо разбирать `data:IMAGE/...;BASE64,` в `_parse_data_url`; (3) включить `(st_dev, st_ino, st_mtime_ns, st_size)` в ключ кэша `_file_sha256` и вычислять SHA-256 вне замка `_sha_cache_lock`; (4) использовать отдельный `_image_flag_lock` для кэша `IMAGE_INPUT_ENABLED`.

### F-007
- origin: R1 Seat 1 (`muse-wonder-full-1.0` F-006)
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- votes: `Seat 1: AGREE non-blocking`, `Seat 2: AGREE non-blocking`, `Seat 3: AGREE non-blocking` (`3/3`)
- text: В `_stage_images` оборачивать дескриптор `os.open` в `with os.fdopen(fd, "wb") as f:`, при ошибке записи немедленно удалять частично созданный `img_dir` до выброса `ImageSpoolError`, а при сбое `shutil.rmtree` в `finally:` или `_sweep_workspace` логировать `image_cleanup_error`.

### F-008
- origin: R1 Seat 2 (`claude-sonnet-5-5-high` F-003, F-004)
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- votes: `Seat 1: AGREE non-blocking`, `Seat 2: AGREE non-blocking`, `Seat 3: AGREE non-blocking` (`3/3`)
- text: В `/health` вычислять `images` с учётом `_image_proof_reason(...) is None`, включить `image_cleanup_error` и `image_sweep_removed` в `_LOG_EVENT_NAMES`, а на этапе L3 выполнить проверку отката флага `IMAGE_INPUT_ENABLED=false`.

### F-009
- origin: R1 Seat 1 (`muse-wonder-full-1.0` F-007) + R1 Seat 2 (`claude-sonnet-5-5-high` F-006, F-008)
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- votes: `Seat 1: AGREE non-blocking`, `Seat 2: AGREE non-blocking`, `Seat 3: AGREE non-blocking` (`3/3`)
- text: Оформить все 40 новых тестовых сценариев (`img01..10`, `hist01..10`, `life01..05`, `log01..02`, `res01..03`, `ao01..10`) в `tests/test_agy_bridge_resilience.py` как отдельные методы `unittest.TestCase` с содержательными поведенческими assertions, совместимые с `/usr/bin/python3` 3.9.6 и `pytest 9.0.3`.

### F-010
- origin: R1 Seat 2 (`claude-sonnet-5-5-high` F-007)
- rev: 2
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- votes: `Seat 1: AGREE non-blocking`, `Seat 2: AGREE non-blocking`, `Seat 3: AGREE non-blocking` (`3/3`)
- text: Массив `verifications` (`VER-001..VER-010`) и `architecture_packet_sha256` синхронизированы в `teamlead/verification-surface.json`.

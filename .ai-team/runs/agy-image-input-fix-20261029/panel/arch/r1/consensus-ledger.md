# Консенсус-леджер находок Архитектурного Совета — до дебатов `D1` (после `R1` `panel/arch/r1`)

- **Run ID:** `agy-image-input-fix-20261029`
- **Раунд R1:** `.ai-team/runs/agy-image-input-fix-20261029/panel/arch/r1` (`panel-proof.json` `sha256=3557117542145993bdabf8e419ba206d4249adf125e1dc0122b22f052223237b` `verify_panel_proof exit=0`)
- **Проверяемый артефакт:** `.ai-team/runs/agy-image-input-fix-20261029/architecture/architecture-packet.json` (`sha256=ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466`)

---

## Карточки открытых находок R1 (вход для дебатов D1)

### F-001
- origin: Seat 1 (`muse-wonder-full-1.0` F-001) + Seat 2 (`claude-sonnet-5-5-high` F-010)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: В `AD-001` для `gemini-4-argon` и `gemini-3.8-flash` заданы `status="confirmed"` и `efforts_proven=["low","medium","high"]`, тогда как до промоушена `IMAGE_INPUT_ENABLED=true` требуется подтверждение матрицы форматов/моделей. По `AD-001` кодовый дефолт `IMAGE_INPUT_ENABLED` равен `False` (fail-closed), поэтому до включения флага на этапе L3 image-запросы закрыты. Рекомендация RECHECK для D1: `AMEND F-001 — priority=non-blocking` (обязательный гейт верификации L2/L3 перед включением `IMAGE_INPUT_ENABLED=true` в `dynamic_config.json`).

### F-002
- origin: Seat 1 (`muse-wonder-full-1.0` F-002)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: Запрос с картинками может ожидать свободного слота в `_acquire_slot()` до 1800 с; если за это время `IMAGE_INPUT_ENABLED` выключен или бинарь `agy.real` обновился, нужна повторная проверка `_is_image_input_enabled()` и `_image_proof_reason(model_id, effort)` внутри `_run_once` сразу после `_acquire_slot()` перед `_stage_images()` и `spawn`. Рекомендация RECHECK для D1: `AMEND F-002 — priority=non-blocking` (обязательный предохранитель реализации в Stage 3 `Coder` + модульный тест с занятым слотом).

### F-003
- origin: Seat 1 (`muse-wonder-full-1.0` F-003)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: В `_collect_images` (`AD-002`) выполнять проверку числа картинок (`<= 16`) и оценку верхней границы размера из длины base64-строки ДО вызова `base64.b64decode(validate=True)`, чтобы не аллоцировать память на 17-й картинке или блобе `> 20 MiB`, сохраняя канонические коды отказа (`too_many_images`, `image_too_large`, `images_too_large`, `invalid_image_base64`). Рекомендация RECHECK для D1: `AMEND F-003 — priority=non-blocking` (обязательный предохранитель реализации в Stage 3 `Coder` + модульный тест).

### F-004
- origin: Seat 1 (`muse-wonder-full-1.0` F-005) + Seat 2 (`claude-sonnet-5-5-high` F-002)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: Конструктивное ограничение памяти декодированных изображений при очереди до 24 ожидающих запросов (`AD-005`, `HL-ENV-01`, `C-MULT-I2`): в `_collect_images` (до `_acquire_slot()`) валидировать каждое изображение по одному без удержания всех декодированных `bytes`-буферов в памяти на время ожидания слота (материализовать декодированные байты на диск внутри `_stage_images` только после захвата одного из 8 слотов и немедленно очищать буфер после `os.write`), а также освобождать ссылки на сырое тело запроса до ожидания слота. Рекомендация RECHECK для D1: `AMEND F-004 — priority=non-blocking` (обязательный предохранитель реализации в Stage 3 `Coder` + проверка в `RES-01`).

### F-005
- origin: Seat 2 (`claude-sonnet-5-5-high` F-001, F-005)
- rev: 1
- priority: blocking
- status: OPEN
- outcome: blocking
- text: Включить в `tests/test_agy_bridge_resilience.py` детерминированный интеграционный L2/RES-01 тест с фейковым `AGY_LAUNCHER`, проверяющий полный HTTP-путь, параллельные запросы при занятых слотах, удержание памяти/FD (`0` утечек дескрипторов), латентность валидации+staging и очистку `img-*`. Рекомендация RECHECK для D1: `AMEND F-005 — priority=non-blocking` (обязательное требование к Stage 3 `Coder` и `Verifier`).

### F-006
- origin: Seat 1 (`muse-wonder-full-1.0` F-004) + Seat 2 (`claude-sonnet-5-5-high` F-009)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: В `bridges/agy-bridge/server.py` (`AD-001`, `AD-002`, `AD-006`): (1) санитизировать управляющие символы в `model` при записи в лог; (2) регистронезависимо разбирать `data:IMAGE/...;BASE64,` в `_parse_data_url`; (3) включить `(st_dev, st_ino, st_mtime_ns, st_size)` в ключ кэша `_file_sha256` и вычислять SHA-256 вне замка `_sha_cache_lock`; (4) использовать отдельный `_image_flag_lock` вместо общего `_sqlite_guard_lock`. Рекомендация RECHECK для D1: `AGREE F-006` / `AMEND F-006 — priority=non-blocking`.

### F-007
- origin: Seat 1 (`muse-wonder-full-1.0` F-006)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: В `_stage_images` (`AD-005`) оборачивать дескриптор `os.open` в `with os.fdopen(fd, "wb") as f:`, при ошибке записи немедленно удалять частично созданный `img_dir` до выброса `ImageSpoolError`, а при сбое `shutil.rmtree` в `finally:` или `_sweep_workspace` логировать `image_cleanup_error`. Рекомендация RECHECK для D1: `AGREE F-007` / `AMEND F-007 — priority=non-blocking`.

### F-008
- origin: Seat 2 (`claude-sonnet-5-5-high` F-003, F-004)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: В `/health` вычислять `images` с учётом `_image_proof_reason(...) is None` (согласно `AD-001.details.health`), включить `image_cleanup_error` и `image_sweep_removed` в `_LOG_EVENT_NAMES`, а на этапе L3 выполнить проверку отката флага `IMAGE_INPUT_ENABLED=false`. Рекомендация RECHECK для D1: `AGREE F-008` / `AMEND F-008 — priority=non-blocking`.

### F-009
- origin: Seat 1 (`muse-wonder-full-1.0` F-007) + Seat 2 (`claude-sonnet-5-5-high` F-006, F-008)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: Оформить все 40 новых тестовых сценариев (`img01..10`, `hist01..10`, `life01..05`, `log01..02`, `res01..03`, `ao01..10`) в `tests/test_agy_bridge_resilience.py` как отдельные методы `unittest.TestCase` с содержательными поведенческими assertions, совместимые с `/usr/bin/python3` 3.9.6 и `pytest 9.0.3`, а в `VER-009` не полагаться на `sys.stdlib_module_names` при запуске на Python 3.9. Рекомендация RECHECK для D1: `AGREE F-009` / `AMEND F-009 — priority=non-blocking`.

### F-010
- origin: Seat 2 (`claude-sonnet-5-5-high` F-007)
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: non-blocking
- text: Массив `verifications` (`VER-001..VER-010`) и `architecture_packet_sha256` синхронизированы в `teamlead/verification-surface.json`. Рекомендация RECHECK для D1: `AGREE F-010 — priority=non-blocking`.

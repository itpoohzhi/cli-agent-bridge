# Итоговый вердикт Архитектурного Совета Тимлидов (`ARCH_PANEL`)

- **Run ID:** `agy-image-input-fix-20261029`
- **Артефакт:** `architecture/architecture-packet.json` (`sha256=ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466`)
- **Раунды:** `R1` (`panel/arch/r1`, слепой раунд) → `R2 / D1` (`panel/arch/r2`, анонимизированные дебаты `3of3_derangement`)
- **Состав жюри D1 (3 независимых семейства):**
  - `Seat 1`: `gemini-4-argon-high` (`Google`, `agy`) — `PASS` (`POSITIONS: 10/10`, `FINDINGS_COMPLETE: 0`)
  - `Seat 2`: `muse-wonder-full-1.0` (`Meta`, `muse`) — `PASS` (`POSITIONS: 10/10`, `FINDINGS_COMPLETE: 0`)
  - `Seat 3`: `claude-sonnet-5-5-high` (`Anthropic`, `claude-p`) — `PASS` (`POSITIONS: 10/10`, `FINDINGS_COMPLETE: 0`)
- **Итоговый статус панели:** **`PASS` (единогласно `3/3` независимых семейств: `Google` + `Meta` + `Anthropic` за `PASS`, `blocking_open = 0`)**

---

## Раздел А. Принятые блокеры (`blocking`, открытые)

Открытых архитектурных блокеров нет (`0`). Архитектурный пакет `architecture/architecture-packet.json` (`sha256=ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466`) одобрен единогласно `3/3` независимых семейств.

---

## Раздел Б. Принятые `non-blocking` замечания (обязательные предохранители для этапа Stage 3 `Coder` и `Verifier`)

Все 10 принятых `non-blocking` пунктов (`F-001..F-010`) из дебатов `D1` являются обязательными требованиями к реализации в `bridges/agy-bridge/server.py`, `bridges/agy-bridge/fleet.json` и `tests/test_agy_bridge_resilience.py`:

1. **`F-001` (Гейт промоушена `IMAGE_INPUT_ENABLED`):** кодовый дефолт `IMAGE_INPUT_ENABLED` в `bridges/agy-bridge/server.py` строго `False` (fail-closed); промоушен в `dynamic_config.json` (`true`) выполняется только после успешной верификации L2/L3.
2. **`F-002` (Повторная проверка флага и proof после `_acquire_slot()`):** в `Handler._run_once` сразу после `_acquire_slot()` непосредственно перед `_stage_images()` и запуском `Run` повторно проверять `_is_image_input_enabled()` и `_image_proof_reason(model_id, effort)` (при отказе — HTTP 400 без `mkdir` и без `spawn`).
3. **`F-003` (Предпроверка количества и длины base64 до `b64decode`):** в `_collect_images` проверять `count <= 16` и оценку декодированного размера по длине base64-строки ДО вызова `base64.b64decode(..., validate=True)`, сохраняя канонические коды отказа (`too_many_images`, `image_too_large`, `images_too_large`, `invalid_image_base64`).
4. **`F-004` (Конструктивное ограничение памяти до захвата слота):** в `_collect_images` (до `_acquire_slot()`) валидировать каждое изображение по одному без удержания декодированных `bytes`-буферов на время ожидания слота (декодировать/записывать байты на диск внутри `_stage_images` только после захвата одного из 8 слотов и очищать буфер сразу после записи файла).
5. **`F-005` (Интеграционный L2/`RES-01` тест в `tests/test_agy_bridge_resilience.py`):** включить тест с фейковым `AGY_LAUNCHER` на параллельные запросы при занятых слотах, `0` утечек FD, латентность валидации+staging и удаление `img-*`.
6. **`F-006` (Санитизация логов, регистронезависимый `data:` URL, `_file_sha256` и `_image_flag_lock`):** санитизировать управляющие символы в `model` для логов; разбирать `data:` URL регистронезависимо; включить `(st_dev, st_ino, st_mtime_ns, st_size)` в кэш `_file_sha256` и считать SHA-256 вне `_sha_cache_lock`; выделить отдельный `_image_flag_lock`.
7. **`F-007` (Безопасное закрытие `fd` и очистка в `_stage_images`):** записывать файлы через `with os.fdopen(fd, "wb") as f:`, при `OSError` немедленно удалять частичный `img_dir` до `ImageSpoolError`, а при ошибке `shutil.rmtree` логировать `image_cleanup_error`.
8. **`F-008` (`/health.images`, события очистки и проверка отката на L3):** учитывать `_image_proof_reason(...) is None` в `/health.images`, добавить `image_cleanup_error` и `image_sweep_removed` в `_LOG_EVENT_NAMES`, и проверить откат флага на L3.
9. **`F-009` (Все 40 тестов как методы `unittest.TestCase` с поведенческими assertions):** оформить все 40 сценариев (`img01..10`, `hist01..10`, `life01..05`, `log01..02`, `res01..03`, `ao01..10`) как методы `unittest.TestCase`, совместимые с `/usr/bin/python3` 3.9.6 и `pytest 9.0.3`.
10. **`F-010` (Синхронизация `teamlead/verification-surface.json`):** массив `verifications` (`VER-001..VER-010`) и `architecture_packet_sha256` синхронизированы.

---

## Раздел В. Отклонённые / снятые замечания

Нет (`0`).

---

## Раздел Г. Особые мнения (Dissent)

Особых мнений нет (`0` — единогласный вердикт `3/3 PASS`).

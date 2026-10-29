# Слепая обратная спецификация (`teamlead/reverse-spec.md`)

Документ реконструирован по итоговому `candidate.diff` (`bridges/agy-bridge/fleet.json`, `bridges/agy-bridge/server.py`, `tests/test_agy_bridge_resilience.py`).

## 1. Фактически изменённые файлы

1. **`bridges/agy-bridge/fleet.json` (изменён):**
   - В `technical_ref` обновлены `agy_version: "1.4.9"`, `agy_binary_path: "~/.local/bin/agy.real"`, `agy_binary_sha256: "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423"`.
   - В `image_limits` зафиксированы `max_images: 16`, `max_image_bytes: 20971520` (20 МБ), `max_total_image_bytes: 20971520` (20 МБ), `max_body_bytes: 33554432` (32 МБ) и канонический список `types: ["image/png", "image/jpeg", "image/gif", "image/webp"]`.
   - Для моделей `gemini-4-argon` и `gemini-3.8-flash` выставлены `input: ["text", "image"]` и объект `images` со `status: "confirmed"`, `method: "workspace-read"`, `verified_at: "2026-10-29"` и структурированным `proof` (`agy_binary_sha256`, `impl_version: 1`, `formats`, `efforts_proven: ["low", "medium", "high"]`, `command`).
   - Для остальных 4 моделей (`gemini-4-argon-thinking`, `claude-sonnet-4-6`, `claude-opus-4-6`, `gpt-5.4`) сохранены `input: ["text"]` и `images.status: "unsupported"`.

2. **`bridges/agy-bridge/server.py` (изменён):**
   - **Kill-Switch и Proof Gate (`AD-001`, `F-001`, `F-006`, `F-008`):**
     - Добавлены `IMPLEMENTED_METHODS = {"workspace-read": 1}`, `_image_flag_lock` и `_is_image_input_enabled()` с чтением `dynamic_config.json` (`IMAGE_INPUT_ENABLED`, TTL 1.0 s, fail-closed `False` по умолчанию) и переопределением через `AGY_IMAGE_INPUT_ENABLED`.
     - Добавлен потокобезопасный `_file_sha256(path)` с чтением бинаря чанками по 1 МБ вне `_sha_cache_lock` и ключом кэша `(st_dev, st_ino, st_mtime_ns, st_size)`.
     - Добавлен `_image_proof_reason(model_id, effort)` с проверкой `input`, `images.status`, `method in IMPLEMENTED_METHODS`, `proof.impl_version`, покрытия `IMAGE_LIMITS["types"]` в `proof.formats`, принадлежности `effort` к `proof.efforts_proven` и совпадения SHA-256 бинаря `agy`.
     - `_model_supports_images(model_id)` и `/health` (`images`) возвращают `True` только при включённом флаге и валидном proof.
   - **Валидация картинок до слота (`AD-002`, `F-003`, `F-006`):**
     - Быстрый выход `[]` при отсутствии `image_url` частей в `messages` (0 системных вызовов на текстовом трафике).
     - Строгий порядок проверок: kill-switch -> модель/статус/effort/proof -> количество `<= 16` до декодирования -> роль `user` -> схема `data:` (регистронезависимо) -> канонический MIME `IMAGE_LIMITS["types"]` -> предварительная оценка декодированного размера base64 до `b64decode` -> `base64.b64decode(..., validate=True)` -> проверка непустоты и сигнатур (`PNG`, `JPEG`, `GIF`, `WebP`) против MIME -> точный лимит одного файла и суммы.
   - **Многоходовая история и `--add-dir` (`AD-003`, `AD-004`):**
     - Глобальная 1-based нумерация маркеров `[image 1]..[image K]` по всей истории `messages`.
     - В `_get_resumed_turn_prompt` срез `messages[last_asst + 1:]` продолжает глобальную нумерацию `img_counter` и включает в `[attachments]` только `delta_images` (`msg_index > last_asst`), устраняя повторное прикрепление старых картинок на текстовом Turn 2 в горячей сессии, но сохраняя все `1..K` файлов на диске на случай холодного ретрая через `full_prompt`.
     - В `Run.__init__` аргумент `--add-dir <img_dir>` передаётся процессу `agy` без модификации `cwd` и ключа сессии `(model_id, cwd, effort)`.
   - **Жизненный цикл спула и уборка сирот (`AD-005`, `F-002`, `F-004`, `F-007`):**
     - В `_run_once` после `_acquire_slot()` повторно проверяются `_is_image_input_enabled()` и `_image_proof_reason()` (`F-002`).
     - Папка `img_dir` регистрируется в `_active_img_dirs` под `_active_lock` до `os.mkdir(img_dir, 0o700)`, файлы создаются с `0o600` (`O_CREAT|O_EXCL|O_WRONLY` + `with os.fdopen(...)`), буфер `img["data"]` немедленно очищается (`F-004`).
     - При ошибке записи выбрасывается `ImageSpoolError` (HTTP 500 `image_spool_error`, `0` spawn), а во внешнем `finally:` после `run.close()` папка `img_dir` гарантированно удаляется и снимается с учёта в `_active_img_dirs`.
     - `_sweep_workspace(cutoff_s=3600.0)` удаляет осиротевшие `img-*` старше 1 часа, пропуская активные папки и симлинки.
   - **Логирование (`AD-006`, `F-006`, `F-008`):**
     - В `_LOG_EVENT_NAMES` добавлены 15 событий картинок и effort; пользовательский `model` очищается от `\r\n\t`.

3. **`tests/test_agy_bridge_resilience.py` (строго аддитивно, `+2 205` строк, `0` удалений):**
   - Добавлены 52 новых тестовых метода (включая все 40 обязательных ID `img01..10`, `hist01..10`, `life01..05`, `log01..02`, `res01..03`, `ao01..10` и специальные тесты `test_f001..test_f007`).

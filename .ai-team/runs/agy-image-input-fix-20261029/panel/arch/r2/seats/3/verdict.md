PANEL-NONCE: 41f5cf3e1048563c
ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466

РАУНД: D1, место k=3 (`claude-sonnet-5-5-high`). Угол: эволюция, границы системы, контракты. Инструменты чтения не вызывались, суждение вынесено по встроенным материалам.

## Позиции по находкам

AMEND F-001 — priority=non-blocking; кодовый дефолт `IMAGE_INPUT_ENABLED=false` (AD-001) закрывает image-путь до промоушена. Обязательный контракт для Coder и Teamlead:
- `fleet.json` с `status="confirmed"` и `efforts_proven=[low,medium,high]` в репозитории — это целевое состояние, а не наблюдение (в `AD-001.promotion` сказано, что подтверждён только PNG/Argon/low).
- Флаг в `~/.dsh/bridges/agy-bridge/dynamic_config.json` включается только после матрицы 2 модели × 3 effort × 4 формата (24 комбинации) на L2/L3 с записанным evidence.
- Если Verifier не может доказать матрицу, `proof.efforts_proven`/`formats` в `fleet.json` сужаются до доказанного, либо флаг остаётся `false`.
- Границы не меняются: рантайм-файл `dynamic_config.json` не в git, `fleet.json` и `server.py` ставятся парой.

AMEND F-002 — priority=non-blocking; в `_run_once` сразу после `_acquire_slot()` и до `_stage_images()` обязательна повторная проверка `_is_image_input_enabled()` и `_image_proof_reason(model_id, effort)` при непустом `images`.
- Это закрывает окно очереди до 1800 с между HTTP-проверкой и staging.
- При отказе: код `image_input_not_supported`, слот освобождён, 0 `mkdir`, 0 spawn.
- Нужен тест с занятым слотом и сменой флага во время ожидания, включая смену бинаря.
- Контракт ответа не меняется: тот же 400 и то же событие журнала.

AMEND F-003 — priority=non-blocking; в `_collect_images` (AD-002) обязательна предпроверка до `base64.b64decode`.
- Сначала число частей `<=16`.
- Затем верхняя граница декодированного размера из длины base64: `len(payload)*3//4 + 2 > 20971520` ведёт к `image_too_large`, а накопленный итог ведёт к `images_too_large`.
- Это не должно менять порядок и семантику 13 шагов `ordered_validation` для корректных и некорректных входов. Если проверка по длине даёт отказ раньше, чем `invalid_image_base64` или `image_type_mismatch` в каноническом порядке, оценка применяется только как ранний отказ для заведомо слишком больших блобов, а таксономия сверяется тестами img/AO-02 на границах +1 байт.

AMEND F-004 — priority=non-blocking; блокирующим для продвижения остаётся только gate RES-01 / HL-ENV-01, который уже стоит в `production_promotion_blockers`. Дизайн-предохранитель обязателен для Coder:
- В `_collect_images` до слота каждое изображение проверяется по одному (strict base64, сигнатура, точный размер). После проверки декодированный буфер не удерживается за время ожидания слота: хранится проверенный b64 либо декодирование идёт потоково в `_stage_images` после слота.
- Ссылки на `raw_body` и `messages` освобождаются до `_run_once`, где это возможно.
- Внутри `_stage_images` буфер каждого файла освобождается сразу после `os.write`.
- Необходима правка `entry_shape` в AD-002: поле `data` (декодированные bytes) для pre-slot-фазы заменяется на проверенный источник, иначе дизайн внутренне расходится с этим предохранителем.
- `memory_closure_check` и `HL-ENV-01` остаются BLOCKED до измерения RES-01. Это условие промоушена, а не дефект парадигмы AD-001..AD-006.

AMEND F-005 — priority=non-blocking; в `tests/test_agy_bridge_resilience.py` обязателен детерминированный интеграционный L2/RES-01 тест с фейковым `AGY_LAUNCHER`.
- Он проверяет полный HTTP-путь и параллельную подачу при занятых слотах.
- Он проверяет отсутствие утечек FD, удаление `img-*` и измерение удержанной памяти включая ожидающих.
- Количество 10 записей `VER-001..VER-010` само по себе не доказывает наличие такого теста. Владелец проверки по `res01..res03` и AO-09 — Verifier.

AGREE F-006 — priority=non-blocking. Четыре уточнения входят в обязательный Раздел Б для Coder:
- Санитизация управляющих символов в `model` при логировании.
- Регистронезависимый разбор `data:` и `;base64` в `_parse_data_url`.
- Ключ кэша `_file_sha256` — `(st_dev, st_ino, st_mtime_ns, st_size)`, хеширование вне `_sha_cache_lock`. Текст `AD-001.sha_algorithm` пока содержит только `(mtime_ns, size)` и хеширует под замком, его нужно привести в соответствие.
- Отдельный `_image_flag_lock`. Это затрагивает контракт: `AD-001.flag.lock` и `BND-002` называют `_sqlite_guard_lock`, обе формулировки нужно согласовать с решением.

AGREE F-007 — priority=non-blocking. Обязательные предохранители в `_stage_images` и sweep:
- `with os.fdopen(fd, "wb")` для каждого файла.
- При `OSError` частичный `img_dir` удаляется до выброса `ImageSpoolError`.
- Ошибка `rmtree` пишется как `image_cleanup_error` (безопасный токен, без путей с пользовательскими данными и без payload).
- Sweep продолжает пропускать симлинки и активные каталоги.

AMEND F-008 — priority=non-blocking; RECHECK неточно цитирует контракт. Фактическая формула `AD-001.details.health.images` — `bool(_is_image_input_enabled() and any(m["images"]["status"]=="confirmed" ...))`, и учёта `_image_proof_reason` в ней нет (функции `_model_image_status_ok_and_proof_ok` в пакете нет).
- Контракт CD-003 должен быть изменён так, чтобы `/health.images` учитывал валидность proof хотя бы для одной целевой модели.
- Токены `image_cleanup_error` и `image_sweep_removed` добавляются в `_LOG_EVENT_NAMES` и в `log_tokens` AD-006 (сейчас 13 токенов, в `AO-08` указано "all13").
- L3 включает репетицию отката `IMAGE_INPUT_ENABLED=false`.
- Расширение аддитивное, существующие поля `/health` не меняются.

AGREE F-009 — priority=non-blocking. Все 40 тестов (`img/hist/life/log/res/ao`) оформляются поведенческими assert в `tests/test_agy_bridge_resilience.py`.
- Они проверяют коды ответа, текст промпта, `--add-dir` и состояние диска.
- Они совместимы с `/usr/bin/python3` 3.9.6 и pytest 9.0.3.
- В VER-009 нельзя полагаться на `sys.stdlib_module_names` на Python 3.9 (появился в 3.10): либо запуск на 3.10+, либо явный список. Эта правка принадлежит Verifier и Teamlead и не меняет парадигму.

AGREE F-010 — priority=non-blocking. `teamlead/verification-surface.json` синхронизирован: 10 записей и `architecture_packet_sha256=ddcbc69f…3466`, как в `architecture/architecture-packet.json`.

## Оценка по 6 критериям

1. **Полнота и следование требованиям: PASS.**
   - REQ-001..010 трассируются на AD, VER и QA.
   - Пробелы закрываются обязательными правками Раздела Б: ранний отказ по длине (F-003), повторный гейт после слота (F-002), поля `/health` (F-008).
2. **Корректность и безопасность: PASS с условиями.**
   - Только `data:` URL, нет сетевой загрузки.
   - Права 0700/0600 и `O_EXCL`, реестр активных каталогов до `mkdir`, пропуск симлинков в sweep, exact-token allowlist при сохранённом `_SECRET`.
   - Условия: F-002, F-006, F-007.
3. **Надёжность, ресурсы, деградация: PASS как дизайн, промоушен заблокирован.**
   - HL-ENV-01, C-MULT-I2/I5, H-CPU-I5 и R-BULK-I1 честно помечены BLOCKED и вынесены в `production_promotion_blockers`. Это условие выкатки, а не дефект архитектуры.
   - Конструктивное ограничение pre-slot буферов (F-004) обязательно к реализации. Расхождение `entry_shape.data` нужно устранить.
4. **Тестируемость и верифицируемость: PASS.**
   - Есть 10 VER, 10 AO, 40 именованных тестов и разделение владельцев (Verifier 6, Teamlead 4, Coder не владеет проверками).
   - Обязательны L2/RES-01 (F-005) и исправление VER-009 для Python 3.9 (F-009).
5. **Альтернативы и выбор: PASS.**
   - Отклонены прямой `image_url` в NDJSON, `cwd=img_dir` (ломает `sess_key` и относительные пути), spool до слота и удаление после каждой попытки.
   - Все AD двусторонние, откат одним флагом плюс откат пары `server.py` и `fleet.json`.
6. **Соответствие контексту и процессу: PASS.**
   - Зона записи Coder: ровно 3 файла (`server.py`, `fleet.json`, `tests/test_agy_bridge_resilience.py`).
   - `dynamic_config.json` не в git. Контракты эволюционируют аддитивно: `/health`, taxonomy, события журнала.
   - Жеребьёвка `select_round_seats.py` сверена: `seed_input` и таблица дайджестов согласованы, минимальный допустимый деранжмент `2ca12206…93e7` даёт k=1 gemini, k=2 muse, k=3 claude, автор OpenAI исключён. Вердикт по жеребьёвке: честная.

POSITIONS: 10/10
ANSWERS: 0/0
COVERAGE: 6/6 подкатегорий
FINDINGS_COMPLETE: 0
ОБЩИЙ ВЕРДИКТ: PASS

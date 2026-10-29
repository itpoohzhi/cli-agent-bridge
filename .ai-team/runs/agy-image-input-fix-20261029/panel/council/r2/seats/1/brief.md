You are Debate Judge Seat #1 (skeptic, slot=muse-wonder-full-1.0, family=Meta, transport=muse) of the Code Council Gate Round D1 (stage=council, round=r2) for run agy-image-input-fix-20261029.
PANEL-NONCE: cc8a078b61cb4c4f
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689
PRIOR-LEDGER-SHA256: 9ad7f7cade0079bbe1d64173b01239fdb463f5fe94c70c50d1230f3d0b5a6e69

# Бриф судьи Совета Тимлидов по коду — Раунд дебатов `D1` (`panel/council/r2`, Место #1 — skeptic)

⚠️ **КРИТИЧЕСКАЯ ИНСТРУКЦИЯ (LEAF JUDGE / AGENT_SPAWN_DEPTH=1):**
- Вы — конечный судья панели `teamlead-gate` (`mode: code`, `stage: council`, `round: r2` / дебаты `D1`, `seat: 1`).
- **НЕ запускайте** никаких субагентов, контуров `cel`, внешних скриптов или команд модификации.
- **НЕ вызывайте** инструменты чтения/поиска — **все материалы дебатов `D1` (`recheck-r1.md`, `consensus-ledger.md` с `F-001..F-005`, анонимизированные вердикты `R1`, код `fleet.json`/`server.py` с номерами строк и результаты чистой комнаты `VER-001..VER-010`) уже полностью встроены в этот бриф ниже**.
- **Первыми двумя строками вашего ответа ОБЯЗАНЫ быть дословно (без отступов, без markdown-блоков вокруг них):**
PANEL-NONCE: cc8a078b61cb4c4f
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689
- **Строка `ОБЩИЙ ВЕРДИКТ:` (самая последняя строка ответа!) ОБЯЗАНА принимать строго одно из канонических значений верификатора `verify_panel_proof.py` (`PoL-V12`):** `ACCEPT`, `PASS`, `NEEDS_WORK` или `RED_FLAG`.

---

## 1. Контекст раунда дебатов `D1` (`consensus-debate.md`)

- **run_id**: `agy-image-input-fix-20261029`
- **mode**: `code` | **stage**: `council` | **round**: `r2` (`D1`) | **seat**: `1` (`muse-wonder-full-1.0`, `Meta`, `muse`)
- **Шляпа (hat)**: Скептик (проверяет позиции по открытым находкам F-001..F-005 с учётом RECHECK и оценивает 14 подкатегорий mode=code)
- **seed_recheck_duty**: `да`
- **PANEL-NONCE**: `cc8a078b61cb4c4f`
- **ARTIFACT-SHA256**: `8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689`
- **PRIOR-LEDGER-SHA256**: `9ad7f7cade0079bbe1d64173b01239fdb463f5fe94c70c50d1230f3d0b5a6e69`
- **seed_input**: `agy-image-input-fix-20261029:council:r2:8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689:ed0bd09f85dfe7250ad24ae84bd8838c9771e37875cc46bb023858720cc8cf35`
- **seed_hex**: `cb76618c4724a457afb65fce66101025dc856c486839af28e9259380c6e2684d`
- **ranked_order**: `["claude-sonnet-5-5-high", "gpt-6.1-sol-high", "gemini-4-argon-high", "muse-wonder-full-1.0"]`
- **Правило жеребьёвки (`PoL-V13`)**: `seed_hex = sha256(seed_input)`, ранги `claude-sonnet-5-5-high=08167da83ceca67b, gpt-6.1-sol-high=2ac3589d275eefec, gemini-4-argon-high=50c060323fb0b1c3, muse-wonder-full-1.0=8fc61b01979e5589`, `3of3_derangement` относительно `r1`.
- **Открытые пункты для позиции судьи (`POSITIONS D1`)**: `F-001, F-002, F-003, F-004, F-005` (`N=5`).
  По каждому из 5 пунктов (`F-001..F-005`) укажите явную позицию:
  - `AMEND F-00X — priority=non-blocking; <обоснование>` или
  - `AGREE F-00X — priority=non-blocking; <обоснование>` или
  - `WITHDRAW F-00X — <обоснование>` или
  - `DISAGREE F-00X — <обоснование>`.
- Если после ваших позиций в `D1` открытых блокирующих находок не остаётся (`Блокеров: 0`), укажите `FINDINGS_COMPLETE: YES` и последней строкой ответа `ОБЩИЙ ВЕРДИКТ: ACCEPT`.

---

## 2. Строгий шаблон ответа судьи в раунде `D1`

```
PANEL-NONCE: cc8a078b61cb4c4f
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689

=== КАРТОЧКА СУДЬИ (РАУНД D1) ===
Место: #1 | Слот: muse-wonder-full-1.0 | Семейство: Meta | Транспорт: muse
Режим: code | Раунд: r2 (D1) | Шляпа: Скептик (проверяет позиции по открытым находкам F-001..F-005 с учётом RECHECK и оценивает 14 подкатегорий mode=code)
seed_recheck_duty: да
seed_recheck: <PASS / N/A>
PRIOR-LEDGER-SHA256: 9ad7f7cade0079bbe1d64173b01239fdb463f5fe94c70c50d1230f3d0b5a6e69
ПОЗИЦИИ ТРЕБУЮТСЯ ПО: F-001, F-002, F-003, F-004, F-005; N=5
ВОПРОСЫ К ТЕБЕ: нет (A=0)
Вердикт места: ACCEPT
Блокеров: <число> | Существенных: <число> | Замечаний: <число>

[POSITIONS D1]
- AMEND F-001 — priority=non-blocking; ...
- AMEND F-002 — priority=non-blocking; ...
- AMEND F-003 — priority=non-blocking; ...
- AGREE F-004 — priority=non-blocking; ...
- AGREE F-005 — priority=non-blocking; ...

POSITIONS: 5/5
ANSWERS: 0/0

[SUB COVERAGE]
| Подкатегория | Статус (PASS/CONCERN/BLOCKER) | Доказательство (файл:строки / тест / VER-ID) | Комментарий |
|---|---|---|---|
| SUB-CORRECT-01 | PASS | ... | ... |
| SUB-EDGE-02 | PASS | ... | ... |
| SUB-ARCH-03 | PASS | ... | ... |
| SUB-API-04 | PASS | ... | ... |
| SUB-ERR-05 | PASS | ... | ... |
| SUB-SEC-06 | PASS | ... | ... |
| SUB-CONC-07 | PASS | ... | ... |
| SUB-RES-08 | PASS | ... | ... |
| SUB-PERF-09 | PASS | ... | ... |
| SUB-TEST-10 | PASS | ... | ... |
| SUB-MAINT-11 | PASS | ... | ... |
| SUB-SIMP-12 | PASS | ... | ... |
| SUB-OBS-13 | PASS | ... | ... |
| SUB-DEPS-14 | PASS | ... | ... |

[FINDINGS]
Замечаний класса BLOCKER и MAJOR не обнаружено (находки F-001..F-005 классифицированы как non-blocking остаточные риски / бэклог).

[ОБОСНОВАНИЕ ВЕРДИКТА]
...

FINDINGS_COMPLETE: YES
ОБЩИЙ ВЕРДИКТ: ACCEPT
```

---

## 3. Материалы раунда `R1`: `recheck-r1.md`, `consensus-ledger.md` и анонимизированные вердикты `R1`

### 3.1. Перепроверка оркестратора (`panel/council/r1/recheck-r1.md`)
```markdown
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

```

### 3.2. Консенсус-леджер открытых находок R1 (`panel/council/r1/consensus-ledger.md`, `sha256=9ad7f7cade0079bbe1d64173b01239fdb463f5fe94c70c50d1230f3d0b5a6e69`)
```markdown
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

```

### 3.3. Анонимизированные вердикты судей Раунда R1

#### Анонимизированный вердикт R1 — Judge A (NEEDS_WORK, 0 BLOCKER, 3 MAJOR, 1 MINOR)
```markdown
Проверяю жеребьёвку и обработку отказов после ожидания слота. Изменений файлов и запусков субагентов не будет.

Жеребьёвка совпала с указанными хешами. Найден разрыв HTTP-контракта: SSE отправляет статус 200 до повторной проверки флага и записи файлов, поэтому поздние отказы 400/500 уходят только внутри потока. Также проверяю освобождение буфера и покрытие требований к ресурсам.


=== КАРТОЧКА СУДЬИ ===
Режим: code | Раунд: r1 | Шляпа: Скептик
seed_recheck_duty: да
seed_recheck: PASS (sha256(seed_input)==seed_hex, PoL-V13 selection contract verified)
package_path: /Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/teamlead/package.md
Вердикт места: NEEDS_WORK
Блокеров: 0 | Существенных: 3 | Замечаний: 1

[SUB COVERAGE]

- **SUB-CORRECT-01 — CONCERN.** AD-001..AD-006 преимущественно реализованы; HTTP-контракт поздних отказов и немедленное освобождение буфера требуют исправлений: C1, C2.
- **SUB-EDGE-02 — PASS.** `test_img03`, `test_img04`, `test_img06`, `test_img09`, `test_f003`, `test_f006`, `test_hist10`: количество, размеры, пустой ввод, MIME, регистр и пути покрыты.
- **SUB-ARCH-03 — PASS.** `test_hist03..05`, `test_ao04`, `test_ao05`: глобальная нумерация, фильтрация новых вложений, сохранение `cwd` и ключа сессии.
- **SUB-API-04 — CONCERN.** `server.py:3762`, `server.py:3809`: SSE фиксирует HTTP 200 до операций, способных вернуть требуемые 400/500. C1.
- **SUB-ERR-05 — CONCERN.** Непотоковые отказы покрыты `test_f002`, `test_life03`; соответствующий HTTP-контракт для SSE нарушается. C1.
- **SUB-SEC-06 — PASS.** Встроенный diff, `test_ao03`, `test_life05`, `test_log02`, VER-009: внешние URL отвергаются, права ограничены, симлинки пропускаются, диагностические значения санитизируются.
- **SUB-CONC-07 — PASS.** `test_f006_sha_cache…`, `test_f002`, `test_ao08`: отдельные замки, хеширование вне замка кэша, регистрация до создания каталога, повторный гейт после слота.
- **SUB-RES-08 — CONCERN.** `server.py:944`, `server.py:959`: локальный декодированный буфер сохраняется после записи. C2.
- **SUB-PERF-09 — CONCERN.** Быстрый текстовый путь и кэши реализованы; обязательная проверка латентности валидации и staging отсутствует. C3.
- **SUB-TEST-10 — CONCERN.** VER-003 сообщает 146 тестов и 142 подтеста, VER-007 — 40 ID, VER-006 — отсутствие удалений. Однако проверки C1–C3 отсутствуют.
- **SUB-MAINT-11 — PASS.** По пакету VER-001/002 проходят; VER-004 подтверждает отсутствие новых ошибок и предупреждений, ошибок в `server.py` нет.
- **SUB-SIMP-12 — PASS.** Решение использует существующий жизненный цикл запроса; существенного оверинжиниринга не выявлено.
- **SUB-OBS-13 — CONCERN.** События и динамические capabilities добавлены, но sweep сообщает об удалении даже при его неуспехе. C4.
- **SUB-DEPS-14 — PASS.** VER-009 и diff: новых внешних зависимостей нет.

[FINDINGS]

**C1 — MAJOR: поздние отказы image-входа нарушают заявленные HTTP-коды для SSE.**

Якоря: `bridges/agy-bridge/server.py:3762`, `:3809`, `:3179`, `:3825`.

`_serve_sse` отправляет HTTP 200 и начальный chunk до `_run_once`. Повторная проверка флага/proof и staging выполняются позже. Поэтому при `stream=true` отключение флага после ожидания слота даёт HTTP 200 с вложенным `error.code=400`; ошибка записи аналогично даёт HTTP 200 вместо 500.

Это противоречит явно заданному HTTP-контракту F-002 и SUB-API-04/SUB-ERR-05. Тесты `test_f002…` и `test_life03…` проверяют непотоковый вариант. Нужны согласование момента отправки заголовков с этим контрактом и регрессионные тесты обоих потоковых сценариев.

**C2 — MAJOR: очистка `img["data"]` не освобождает фактический буфер staging.**

Якоря: `bridges/agy-bridge/server.py:944`, `:958`, `:959`.

Декодированные байты находятся в локальной переменной `data`; поле `img["data"]` в штатном пути уже пустое. Присваивание этому полю `b""` оставляет локальный буфер живым. При следующей итерации предыдущий буфер сохраняется во время вычисления правой части следующего декодирования.

Следовательно, требование немедленного освобождения буфера после записи из F-004 не выполнено. Суммарный лимит изображений сохраняется; речь о нарушении конкретного ресурсного инварианта. Нужно освобождать фактическую ссылку после записи и проверять время жизни буфера, а не только содержимое словаря.

**C3 — MAJOR: обязательная проверка латентности F-005 отсутствует.**

Якорь: `tests/test_agy_bridge_resilience.py:5247`, `test_res01_concurrent_turns_bounded_by_slots_without_fd_or_dir_leaks`.

Тест проверяет конкурентность, дескрипторы и каталоги. Времена `t0/t1` фейкового launcher используются для определения одновременности процессов. Они не измеряют предшествующие валидацию и staging; утверждений об их латентности нет. Используются маленькие сигнатурные фикстуры.

Поэтому VER-003/005 не подтверждают заявленное выполнение этой части F-005. Требуется отдельное измерение валидации и staging на согласованном рабочем объёме с явным критерием приёмки.

**C4 — MINOR: sweep завышает число успешно удалённых каталогов.**

Якоря: `bridges/agy-bridge/server.py:3914`, `:3916`, `:3918`.

После `shutil.rmtree(..., ignore_errors=True)` счётчик увеличивается без проверки результата. При отказе удаления каталог останется, но функция вернёт успешное удаление и запишет `image_sweep_removed`. Следует считать подтверждённые удаления и отдельно отражать ошибки очистки.

[ОБОСНОВАНИЕ ВЕРДИКТА]

Жеребьёвка пересчитана: seed и ранги совпали. SHA-256 прочитанных `server.py` и тестового файла совпадают с манифестом кандидата.

Основные решения AD-001..AD-006 реализованы: вход выключен по умолчанию, валидация предшествует слоту, staging ограничен слотами, `cwd` сохранён, история нумеруется глобально, каталог очищается внешним `finally`. Однако C1–C3 оставляют незакрытыми существенные требования к API, ресурсам и проверке F-005.

VER-001..VER-009 приняты как предоставленные результаты чистой комнаты; повторно тесты не запускались. Отложенный VER-010 допустим для указанной последовательности этапов, но не доказывает живую приёмку и не разрешает включение флага.

FINDINGS_COMPLETE: YES
ОБЩИЙ ВЕРДИКТ: NEEDS_WORK
```

#### Анонимизированный вердикт R1 — Judge B (ACCEPT, 0 BLOCKER, 0 MAJOR, 0 MINOR)
```markdown
Подтверждение канона: общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком (до `<!-- КАНОН-КОНЕЦ -->`); проектных файлов правил (`AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md`) в рабочей папке не обнаружено.

=== КАРТОЧКА СУДЬИ ===
Режим: code | Раунд: r1 | Шляпа: Реалист (оценивает эксплуатационную надёжность, корректность слотов/спула, совместимость с DSH и agy 1.4.9)
seed_recheck_duty: нет
seed_recheck: N/A (seed_recheck_duty=нет)
package_path: /Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/teamlead/package.md
Вердикт места: ACCEPT
Блокеров: 0 | Существенных: 0 | Замечаний: 0

[SUB COVERAGE]
| Подкатегория | Статус (PASS/CONCERN/BLOCKER) | Доказательство (файл:строки / тест / VER-ID) | Комментарий |
|---|---|---|---|
| SUB-CORRECT-01 | PASS | `bridges/agy-bridge/fleet.json:11-31,58-120`, `bridges/agy-bridge/server.py:364-398,674-960,1042-1096,3176-3207,3628-3642`, `VER-003`, `VER-005` | Все требования `REQ-001..REQ-010`, `AC-001..AC-010`, архитектурные решения `AD-001..AD-006` и предохранители `F-001..F-010` реализованы в точном соответствии со спецификацией. |
| SUB-EDGE-02 | PASS | `bridges/agy-bridge/server.py:846-930`, `tests/test_agy_bridge_resilience.py:test_img01..test_img10,test_f003,test_f006`, `VER-003` | Проверены граничные случаи: 0 картинок (`[]` без syscalls), 16 vs 17 картинок до `b64decode`, лимит 20 МБ на всех остатках паддинга base64 (0/1/2), регистронезависимый `DATA:IMAGE/PNG;BASE64,`, несовпадение сигнатуры и MIME, пустой payload, пробелы и кириллица в `cwd`. |
| SUB-ARCH-03 | PASS | `bridges/agy-bridge/server.py:589-610,1042-1096,2512,2533-2534,3694`, `tests/test_agy_bridge_resilience.py:test_hist01..test_hist10`, `VER-003` | Сквозная 1-based нумерация `[image 1]..[image K]`, фильтрация `delta` в `_get_resumed_turn_prompt` без повторного прикрепления старых картинок на hot-ходу, сохранение всех `1..K` файлов для cold-ретрая и передача `--add-dir <img_dir>` без модификации `cwd` и `sess_key = (model_id, cwd, effort)`. |
| SUB-API-04 | PASS | `bridges/agy-bridge/server.py:3386-3394,3433-3436,3460-3474,3628-3641`, `tests/test_agy_bridge_resilience.py:test_img07,test_res02,test_ao01..test_ao03`, `VER-003` | Контракты `/v1/chat/completions`, `/v1/models` и `/health` соблюдены; коды HTTP 400/413/500 и поля `error.type`/`error.code` строго соответствуют канону. |
| SUB-ERR-05 | PASS | `bridges/agy-bridge/server.py:618-630,933-978,3176-3207,3386-3394`, `tests/test_agy_bridge_resilience.py:test_life01,test_life03,test_f002,test_f007`, `VER-003` | `ImageReject` возвращает HTTP 400 до `mkdir`/`spawn`; `ImageSpoolError` при сбое записи немедленно удаляет частичный `img_dir` и возвращает HTTP 500 `image_spool_error` с `0` `spawn`; ошибка `shutil.rmtree` при финализации логирует `image_cleanup_error`. |
| SUB-SEC-06 | PASS | `bridges/agy-bridge/server.py:267,638-640,880-881,949-960,3905`, `tests/test_agy_bridge_resilience.py:test_life05,test_log01,test_log02,test_f006`, `VER-009` | Отказ на `http://`/`https://`/`file://` URL, права `0700` на каталог и `0600` (`O_CREAT|O_EXCL|O_WRONLY`) на файлы, пропуск симлинков в `_sweep_workspace`, санитизация `[\x00-\x1f\x7f]` в `model`, отсутствие утечек base64/путей/ключей в ответах и логах. |
| SUB-CONC-07 | PASS | `bridges/agy-bridge/server.py:259-264,658-676,708-715,3176-3195,3911-3913`, `tests/test_agy_bridge_resilience.py:test_life04,test_res01,test_f002,test_f006`, `VER-003` | Выделен независимый `_image_flag_lock`, чтение 1 МБ чанков SHA-256 выполняется вне `_sha_cache_lock` (под `_sha_compute_lock`), регистрация `_active_img_dirs` под `_active_lock` происходит строго до `os.mkdir`, повторная проверка `_image_gate` выполняется после `_acquire_slot()` (`F-002`). |
| SUB-RES-08 | PASS | `bridges/agy-bridge/server.py:911,925,951-960,3327-3330,3889-3929`, `tests/test_agy_bridge_resilience.py:test_life01..test_life05,test_res01`, `VER-003` | Декодированные байты `raw` удаляются сразу после проверки в `_collect_images` (`F-004`), материализация на диск ограничена 8 слотами, дескриптор оборачивается в `with handle:` (`os.fdopen`) с закрытием `fd` при сбое, буферы `data`/`b64` очищаются сразу после записи, удаление `img_dir` гарантировано во внешнем `finally:` до освобождения слота. |
| SUB-PERF-09 | PASS | `bridges/agy-bridge/server.py:643-678,708-715,846-848,3943`, `tests/test_agy_bridge_resilience.py:test_img09,test_f006`, `VER-003` | Текстовые запросы выходят за `O(messages)` без единого системного вызова (`test_img09`), флаг кэшируется на `1.0 s`, SHA-256 бинаря (~190 МБ) кэшируется по `(st_dev, st_ino, st_mtime_ns, st_size)` и прогревается фоновым daemon-потоком в `main()`. |
| SUB-TEST-10 | PASS | `tests/test_agy_bridge_resilience.py:3803-6008`, `VER-003`, `VER-005`, `VER-006`, `VER-007` | 146 тестов (и 142 подтеста) проходят в `pytest 9.0.3` и `/usr/bin/python3` 3.9.6 `unittest`; `VER-007` подтверждает все 40 обязательных тестовых ID (`QA_ASSERT_COVERAGE_PASS 40`) плюс тесты `test_f001..test_f007`; `VER-006` подтверждает `0` удалённых строк в тестовом файле и прохождение `test_images_strict.py` (18/18). |
| SUB-MAINT-11 | PASS | `VER-001`, `VER-002`, `VER-004` | `ruff check` (`VER-001`) и `ruff format --check` (`VER-002`) — 0 ошибок; `basedpyright 1.40.2` (`VER-004`) — `0` ошибок в `server.py`, `0` новых ошибок и `0` новых предупреждений относительно базы (791 против 804 на baseline). |
| SUB-SIMP-12 | PASS | `bridges/agy-bridge/server.py`, `VER-008` | Изменения локализованы строго в 3 целевых файлах (`SCOPE_FROZEN_PASS`), без лишних абстракций, внешних обёрток и мёртвого кода. |
| SUB-OBS-13 | PASS | `bridges/agy-bridge/server.py:504-524,785,973,3433-3436,3469-3474,3918`, `tests/test_agy_bridge_resilience.py:test_log01,test_log02,test_res02`, `VER-003` | Все 15 диагностических токенов добавлены в `_LOG_EVENT_NAMES` и не маскируются `_SECRET`, а `/health` и `/v1/models` динамически отражают готовность image-входа с учётом флага и валидности proof. |
| SUB-DEPS-14 | PASS | `bridges/agy-bridge/server.py:65`, `VER-009` | Добавлен только стандартный модуль `base64`; внешних пакетов или сетевых клиентов нет (`IMAGE_STDLIB_SECURITY_PASS`). |

[FINDINGS]
Замечаний класса BLOCKER и MAJOR не обнаружено.

[ОБОСНОВАНИЕ ВЕРДИКТА]
С позиции эксплуатационной надёжности (шляпа Реалиста) реализация полностью закрывает все риски работы моста `agy-bridge` с `agy 1.4.9` и DSH:
1. **Безопасное управление слотами и памятью (`AD-002`, `AD-005`, `F-002`, `F-003`, `F-004`, `F-007`):** предпроверка количества (`<= 16`) и длины base64 выполняется до `b64decode`; во время ожидания семафора `_slots` декодированные байты не удерживаются в памяти (`del raw`, `data: b""`); сразу после `_acquire_slot()` повторно проверяется `_image_gate(model, effort)` до любого `mkdir`/`spawn`; файлы создаются атомарно с правами `0600` (`O_CREAT|O_EXCL|O_WRONLY`) в каталоге `0700`, зарегистрированном в `_active_img_dirs` до создания на диске; очистка каталога гарантирована во внешнем `finally:` после `run.close()` на всех терминальных путях и ретраях.
2. **Корректность многоходовых сессий и совместимость с `agy 1.4.9` (`AD-003`, `AD-004`):** каталог изображений передаётся через `--add-dir <img_dir>` без подмены рабочего каталога проекта `cwd` и без разрушения ключа сессии `sess_key = (model_id, cwd, effort)`. В горячих (`--conversation`) сессиях `_get_resumed_turn_prompt` передаёт в `[attachments]` только `delta`-изображения новых сообщений со сквозной глобальной нумерацией `[image N]`, а на диске материализуются все `1..K` изображений истории, что обеспечивает бесшовный откат с hot-попытки на cold `full_prompt` внутри того же хода.
3. **Fail-closed конфигурация и чистота верификации (`AD-001`, `F-001`, `VER-001..VER-009`):** по умолчанию `IMAGE_INPUT_ENABLED` в коде выключен (`False`), хеширование бинаря `agy.real` потокобезопасно и не блокирует текстовый трафик, а все проверки чистой комнаты L2 (`VER-001..VER-009`) завершены со статусом `PASS` (`exit_code=0`). Живая проверка L3 (`VER-010`) правомерно отложена до этапа после `ACCEPT` Совета Тимлидов.

FINDINGS_COMPLETE: YES
ОБЩИЙ ВЕРДИКТ: ACCEPT
```

#### Анонимизированный вердикт R1 — Judge C (ACCEPT, 0 BLOCKER, 0 MAJOR, 1 MINOR)
```markdown
=== КАРТОЧКА СУДЬИ ===
Режим: code | Раунд: r1 | Шляпа: Визионер (оценивает целостность архитектуры, эволюцию контракта fleet.json и полноту тестового покрытия)
seed_recheck_duty: нет
seed_recheck: N/A (seed_recheck_duty=нет)
package_path: /Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/teamlead/package.md
Вердикт места: ACCEPT
Блокеров: 0 | Существенных: 0 | Замечаний: 1

[SUB COVERAGE]
| Подкатегория | Статус (PASS/CONCERN/BLOCKER) | Доказательство (файл:строки / тест / VER-ID) | Комментарий |
|---|---|---|---|
| SUB-CORRECT-01 | PASS | server.py: `_collect_images`, `_image_proof_reason`, `_messages_to_prompt`; fleet.json `image_limits`/`images.proof`; `VER-003`, `VER-005`, `VER-007` | REQ-001..REQ-010, AC-001..AC-010, AD-001..AD-006 и F-001..F-010 трассированы и покрыты 146 тестами |
| SUB-EDGE-02 | PASS | `test_img01..test_img10`, `test_f003_*`, `test_f006_*`; `VER-003`, `VER-007` | Покрыты 0 картинок, 16/17, лимиты до `b64decode`, регистр `data:`, mismatch magic/MIME, пустой payload, пробелы и кириллица |
| SUB-ARCH-03 | PASS | server.py: `Run.__init__` `--add-dir`, `_get_resumed_turn_prompt` `delta_images`, `img_counter`; `test_hist01..test_hist10`, `test_ao04_*`, `test_ao05_*` | `cwd` и `sess_key=(model_id,cwd,effort)` не мутируются, нумерация `[image 1]..[image K]` глобальна, hot-ход не дублирует старые вложения |
| SUB-API-04 | PASS | server.py: `_error_body` `image_reject`/`image_spool_error`, `/health`, `/v1/models`; `test_ao01_*`, `test_ao03_*`, `test_res02_*` | Контракты 200/400/413/500 и поля `type`/`code` сохранены, `images` в `/health` и `/v1/models` динамичен |
| SUB-ERR-05 | PASS | server.py: `ImageReject` до слота, `ImageSpoolError` после слота, `_cleanup_img_dir`; `test_life03_*`, `test_ao03_*`, `test_f002_*` | Отказ валидации даёт 400 без `mkdir`/`spawn`, сбой спула даёт 500 `image_spool_error`, 0 spawn и очистку частичной папки |
| SUB-SEC-06 | PASS | server.py: отказ `http/https/file`, `0o700`/`0o600 O_EXCL`, `_sweep_workspace` skip symlink, `_safe_log_value`; `test_ao03_*`, `test_log02_*`, `VER-009` | Нет сетевых загрузок, base64 и путей в логах/ответах, управляющие символы в `model` санитизированы |
| SUB-CONC-07 | PASS | server.py: `_image_flag_lock`, SHA вне `_sha_cache_lock`, `_active_img_dirs` под `_active_lock` до `mkdir`, recheck после `_acquire_slot()`; `test_f002_*`, `test_f006_*`, `test_res01_*`, `test_ao08_*` | F-002 и F-006 реализованы, конкурентные ходы изолированы по каталогам и слотам |
| SUB-RES-08 | PASS | server.py: `with os.fdopen(fd,"wb")`, `img["data"]=b""`, внешний `finally` после `run.close()`, `_sweep_workspace(3600)`; `test_life01..test_life05` | Нет утечек FD и `img-*` на терминальных путях, ретраи делят один каталог хода |
| SUB-PERF-09 | PASS | server.py: fast path `[]`, кэш флага TTL 1.0 c, кэш SHA по `(st_dev,st_ino,st_mtime_ns,st_size)`; `test_img09_*`, `test_f001_*`, `test_f006_*` | Текстовый трафик без stat/hash/flag I/O, бинарь хешируется один раз чанками по 1 МиБ |
| SUB-TEST-10 | PASS | tests/test_agy_bridge_resilience.py +2205/−0; `VER-003` 146 passed, 142 subtests, `VER-005` OK, `VER-006` OK, `VER-007` `QA_ASSERT_COVERAGE_PASS 40` | Все 40 ID и F-001..F-007 оформлены как `unittest.TestCase`, совместимы с Python 3.9.6 и pytest 9.0.3 |
| SUB-MAINT-11 | PASS | `VER-001` ruff check 0, `VER-002` ruff format 0, `VER-004` basedpyright `server_py_errors=0 new_errors=0 new_warnings=0` | Единственная ошибка типов — предсуществующая в тесте на baseline, предупреждений стало меньше (791 против 804) |
| SUB-SIMP-12 | PASS | candidate.diff: только fleet.json, server.py, тесты; `VER-008` `SCOPE_FROZEN_PASS` | Нет мёртвого кода и лишних абстракций, метод один — `{"workspace-read": 1}` |
| SUB-OBS-13 | PASS | server.py: `_LOG_EVENT_NAMES` 15 токенов, `/health.images`, `/v1/models.images`; `test_log01_*`, `test_ao07_*`, `test_res02_*` | Причины отказа видны дословно без ослабления маскирования секретов, события очистки и sweep логируются |
| SUB-DEPS-14 | PASS | `VER-009` `IMAGE_STDLIB_SECURITY_PASS`; импорты только stdlib + `core` | Новых внешних зависимостей нет, сетевые вызовы в image-хелперах запрещены AST-гейтом |

[FINDINGS]
Замечаний класса BLOCKER и MAJOR не обнаружено.
- MINOR: bridges/agy-bridge/fleet.json — строка `effort_ladders`/`models_source` по-прежнему ссылается на `agy models 1.3.1` при `agy_version: "1.4.9"`; документационная несогласованность внутри `technical_ref`, на поведение и proof-гейт не влияет, желательно актуализировать при промоушене флага на L3.

[ОБОСНОВАНИЕ ВЕРДИКТА]
С позиции визионера архитектура целостна и расширяема без ломки контракта: AD-001 fail-closed флаг `IMAGE_INPUT_ENABLED=False` по умолчанию с отдельным `_image_flag_lock` и proof по SHA-256 бинаря, `impl_version`, форматам и effort; AD-002 строгая упорядоченная валидация до слота с предпроверкой количества и размера до `b64decode` (F-003, F-004); AD-003 глобальная нумерация и `delta_images` на hot resume; AD-004 `--add-dir` дискретным аргументом без затрагивания `cwd`/`sess_key`; AD-005 спул только после `_acquire_slot()` с повторной проверкой F-002, правами 0700/0600, `finally`-очисткой и sweep сирот; AD-006 15 немаскируемых событий без утечки payload. Эволюция fleet.json обратно совместима для 4 unsupported-моделей, а confirmed-статус двух целевых моделей строго связан с `IMPLEMENTED_METHODS={"workspace-read": 1}` в `_build_catalog`. F-001..F-010 закрыты кодом и тестами, включая F-005 конкурентный RES-01 и F-009 все 40 сценариев. Чистая комната L2: VER-001..VER-009 все PASS exit 0 (146 тестов, 142 подтеста, 0 удалений в тестах, 0 новых ошибок/предупреждений типов). VER-010 корректно отложен в DEFERRED_L3 до ACCEPT Совета, флаг остаётся выключенным, поэтому неполная живая матрица форматов/effort не блокирует приёмку кода, но блокирует промоушен флага до L2/L3.

FINDINGS_COMPLETE: YES
ОБЩИЙ ВЕРДИКТ: ACCEPT
```

---

## 4. Материалы пакета приёмки (`ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689`)

### 4.1. Манифесты, `coder.json` и результаты чистой комнаты L2 (`execution-evidence.md` + `evidence-manifest.sha256`)

#### `teamlead/candidate-manifest.json`
```json
{
  "schema_version": "1.0",
  "task_id": "agy-image-input-fix",
  "run_id": "agy-image-input-fix-20261029",
  "base_commit": "5a19559426de7508d525e2bd465eff648665a6a7",
  "diff_sha256": "d6e653d781484f7cf2dfbb136ecb6ae3a70c2bdec7b82c9ef0dd46caac7a9826",
  "files": [
    {
      "path": "bridges/agy-bridge/fleet.json",
      "sha256": "fe2564ea0eb1f17d681f8ccfb7224b4b44eb4c999cb5ac1cad518736a92b5baf",
      "role": "production"
    },
    {
      "path": "bridges/agy-bridge/server.py",
      "sha256": "3227e8ef769c5ebda5b4aa5647bbd651f4a9b28c784122c61c3e1f638be9e357",
      "role": "production"
    },
    {
      "path": "tests/test_agy_bridge_resilience.py",
      "sha256": "f318d60537ad862b11313d303644ace3ff5ae74e5d581ceeba86bcf7bddeeff5",
      "role": "test"
    }
  ]
}

```

#### `coder.json`
```json
{
  "schema_version": "1.0",
  "role": "coder",
  "task_id": "agy-image-input-fix",
  "run_id": "agy-image-input-fix-20261029",
  "iteration": 1,
  "role_plan": {
    "path": ".ai-team/runs/agy-image-input-fix-20261029/plans/coder-01.json",
    "sha256": "88349d4f55f8478e8fc4c9b4d138863cb1048aa7af1202d247ff3e1030b582ca"
  },
  "status": "DONE",
  "summary": "Workspace-read image input for agy-bridge implemented per AD-001..AD-006 and F-001..F-010 in fleet.json, server.py and additive tests: fail-closed flag (default off) + binary-SHA proof, ordered validation before slot, global [image N] numbering with delta attachments on hot resume, --add-dir without touching cwd/sess_key, slot-bounded 0700/0600 spool with recheck after slot and finally cleanup, orphan sweep, unmasked log tokens. All VER-001..009 green on the working tree (VER-008 verbatim needs a commit); L3/VER-010 NOT RUN; flag stays off until L2/L3.",
  "changed_files": [
    "bridges/agy-bridge/fleet.json",
    "bridges/agy-bridge/server.py",
    "tests/test_agy_bridge_resilience.py"
  ],
  "commands": [
    {
      "command": "uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "exit_code": 0
    },
    {
      "command": "uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "exit_code": 0
    },
    {
      "command": "uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py (compare vs baseline 5a19559: 0 new warnings; errorCount 1 == pre-existing baseline error)",
      "exit_code": 0
    },
    {
      "command": "PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py (146 passed)",
      "exit_code": 0
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p \"test_*agy*.py\" (146 tests OK)",
      "exit_code": 0
    },
    {
      "command": "git diff --numstat 5a19559426de7508d525e2bd465eff648665a6a7 -- tests/test_agy_bridge_resilience.py (2205 added, 0 deleted) + unittest/pytest tests/test_images_strict.py (18 passed)",
      "exit_code": 0
    },
    {
      "command": "VER-007 AST coverage: QA_ASSERT_COVERAGE_PASS 40",
      "exit_code": 0
    },
    {
      "command": "VER-008 equivalent on working tree (git diff --name-only BASE without HEAD): SCOPE_FROZEN_PASS",
      "exit_code": 0
    },
    {
      "command": "VER-009 AST stdlib/security: IMAGE_STDLIB_SECURITY_PASS",
      "exit_code": 0
    }
  ],
  "acceptance_coverage": [
    "AC-001 test_ao01 + test_f001 (targets accept, 4 unsupported models and flag-off reject before spawn, text works)",
    "AC-002 test_img01/02/04/05/06/07 + test_ao02 (4 MIME, 16 images, 17 rejected, limit boundaries with patched limits, body 413)",
    "AC-003 test_ao03 + test_f003 (all reject reasons HTTP 400 before spool/spawn, proof mismatch keeps text working)",
    "AC-004 test_hist01..10 + test_ao04 (cold, hot, explicit cid, hot->cold fallback, global numbering)",
    "AC-005 test_ao05 + test_hist10 (cwd/sess_key untouched, discrete --add-dir, spaces/Unicode)",
    "AC-006 test_life01..04 + test_ao06 (0700/0600, retries share one dir, cleanup on every terminal path, spool failure 500)",
    "AC-007 test_log01/02 + test_ao07 (verbatim reasons, no secret/payload in logs)",
    "AC-008 test_life05 + test_ao08 (sweep boundaries, active registry before mkdir, symlink safety)",
    "AC-009 test_res01..03 + test_ao09 (slots bound, FD/dir leaks, no retry after delivered reasoning, text/SSE intact, full existing suite green)",
    "AC-010 only repo-side pair consistency (test_ao10); live :9887 DSH L3 (VER-010) NOT RUN"
  ],
  "assumptions": [
    "Fleet proof values (efforts low/medium/high, 4 formats, impl_version 1) are the post-verification target state required by the brief; only PNG/Argon/low is proven live so far, therefore IMAGE_INPUT_ENABLED must stay false in runtime dynamic_config.json until the L2/L3 matrix passes.",
    "AGY_IMAGE_INPUT_ENABLED env follows the brief (1/true/yes/on enables, 0/false/no/off disables, anything else false); it is not set in start.sh/launchd.",
    "Peak process memory per image request (JSON string + base64 copy + transient decode) is not bounded by this change; RES-01 must measure it before promotion."
  ],
  "risks": [
    "VER-008 verbatim ('git diff --name-only BASE HEAD') fails until the three files are committed; same assertions pass on the working tree.",
    "basedpyright errorCount is 1 both on baseline and now (existing test line '[uri, uri + \"&immutable=1\"]'); 0 new warnings.",
    "Signature sniffing is not pixel decoding: corrupted images with a valid magic are accepted (documented by test_img10).",
    "Request body strings stay alive during the turn, so queued image requests hold ~2x base64 size until staging (RES-01).",
    "Runtime pair deployment, LaunchAgent restart and live DSH two-image + follow-up text check (VER-010) are not done."
  ],
  "open_questions": [],
  "next_role": "reviewer"
}

```

#### `teamlead/evidence-manifest.sha256`
```text
fe2564ea0eb1f17d681f8ccfb7224b4b44eb4c999cb5ac1cad518736a92b5baf  bridges/agy-bridge/fleet.json
3227e8ef769c5ebda5b4aa5647bbd651f4a9b28c784122c61c3e1f638be9e357  bridges/agy-bridge/server.py
f318d60537ad862b11313d303644ace3ff5ae74e5d581ceeba86bcf7bddeeff5  tests/test_agy_bridge_resilience.py
d6e653d781484f7cf2dfbb136ecb6ae3a70c2bdec7b82c9ef0dd46caac7a9826  .ai-team/runs/agy-image-input-fix-20261029/teamlead/candidate.diff
f56a5b3340f7a78ace9f6330f862a4cf9879d560b8d65c7c977f24b89e85790f  .ai-team/runs/agy-image-input-fix-20261029/teamlead/candidate-manifest.json
71ba04c4de89dc6d03c053813c11bef0071af2ee8e1e54775a4b96cc537d0c56  .ai-team/runs/agy-image-input-fix-20261029/teamlead/environment-manifest.json
4f4d583b6f648feb38362ebed83a1faca19fc286aea099d5ead74b7583f48834  .ai-team/runs/agy-image-input-fix-20261029/teamlead/execution-evidence.md
f96df3f3ac7e48a1482cc18afc462983825bba61f4be8ddf1057e1ee261abb8c  .ai-team/runs/agy-image-input-fix-20261029/teamlead/verification-traceability.md
1492d2974e858bb7daa642d67aecc90c1c654ef542a456bc48bfefc1c9f7ad98  .ai-team/runs/agy-image-input-fix-20261029/teamlead/reverse-spec.md
d24335c5652cc6b1e77709ef44e40cb0bb203555279d9e6d95286b5c56d16fde  .ai-team/runs/agy-image-input-fix-20261029/coder.json
32d994eeab4f279d30a23f0f01f5c3d0422a93b5504deaf6724facfa143909ec  .ai-team/runs/agy-image-input-fix-20261029/verifier.json

```

# Clean-Room L2 & Verifier Execution Evidence (`agy-image-input-fix-20261029`)

- **Generated At (UTC):** `2026-10-29T13:07:09.269120+00:00`
- **Base SHA:** `5a19559426de7508d525e2bd465eff648665a6a7`
- **Clean-Room Worktree:** `/var/folders/2f/c42p3_k11d9252tg83blw_mc0000gn/T/agy-image-cleanroom-limla3vr/wt`
- **`bridges/agy-bridge/fleet.json` SHA-256:** `fe2564ea0eb1f17d681f8ccfb7224b4b44eb4c999cb5ac1cad518736a92b5baf`
- **`bridges/agy-bridge/server.py` SHA-256:** `3227e8ef769c5ebda5b4aa5647bbd651f4a9b28c784122c61c3e1f638be9e357`
- **`tests/test_agy_bridge_resilience.py` SHA-256:** `f318d60537ad862b11313d303644ace3ff5ae74e5d581ceeba86bcf7bddeeff5`
- **`architecture/architecture-packet.json` SHA-256:** `ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466`
- **`teamlead/verification-surface.json` SHA-256:** `860cb91f65f95578f3c383652702cfa48a85877df16fccba3f62282fbe8034e9`

## Verification Gate Results (`VER-001..VER-010`)

| ID | Status | Exit Code | Duration (s) | Summary |
|---|---|---|---|---|
| `VER-001` | `PASS` | `0` | `0.15` | `All checks passed!` |
| `VER-002` | `PASS` | `0` | `0.13` | `2 files already formatted` |
| `VER-003` | `PASS` | `0` | `119.95` | `146 passed, 142 subtests passed in 119.29s (0:01:59)` |
| `VER-004` | `PASS` | `0` | `8.53` | `PASS: version 1.40.2 server_py_errors=0 new_errors=0 new_warnings=0 (warnings 791 vs baseline 804)` |
| `VER-005` | `PASS` | `0` | `114.67` | `OK` |
| `VER-006` | `PASS` | `0` | `10.18` | `OK` |
| `VER-007` | `PASS` | `0` | `0.16` | `QA_ASSERT_COVERAGE_PASS 40` |
| `VER-008` | `PASS` | `0` | `0.13` | `SCOPE_FROZEN_PASS` |
| `VER-009` | `PASS` | `0` | `0.13` | `IMAGE_STDLIB_SECURITY_PASS` |
| `VER-010` | `DEFERRED_L3` | `None` | `0.0` | `Deferred to Wave 6 live L3 verification on 127.0.0.1:9887 after Council ACCEPT` |

### VER-001 (`PASS`, `exit_code=0`, `0.15s`)
```bash
uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py
```
```text
All checks passed!
```

### VER-002 (`PASS`, `exit_code=0`, `0.13s`)
```bash
uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py
```
```text
2 files already formatted
```

### VER-003 (`PASS`, `exit_code=0`, `119.95s`)
```bash
PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py
```
```text
.......................................................................................... [ 61%]
........................................................ [100%]
146 passed, 142 subtests passed in 119.29s (0:01:59)
```

### VER-004 (`PASS`, `exit_code=0`, `8.53s`)
```bash
uvx basedpyright@1.40.2 --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py
```
```text
{
  "version": "1.40.2",
  "candidate_summary": {
    "filesAnalyzed": 2,
    "errorCount": 1,
    "warningCount": 791,
    "informationCount": 0,
    "timeInSec": 2.476
  },
  "baseline_summary": {
    "filesAnalyzed": 2,
    "errorCount": 1,
    "warningCount": 804,
    "informationCount": 0,
    "timeInSec": 2.164
  },
  "server_py_errors": 0,
  "new_errors_vs_baseline": 0,
  "new_warnings_vs_baseline": 0,
  "pre_existing_test_error": [
    {
      "file": "test_agy_bridge_resilience.py",
      "line": 2905,
      "rule": "reportOperatorIssue",
      "message": "Operator \"+\" not supported for types \"object\" and \"Literal['&immutable=1']\""
    }
  ]
}
PASS: version 1.40.2 server_py_errors=0 new_errors=0 new_warnings=0 (warnings 791 vs baseline 804)
```

### VER-005 (`PASS`, `exit_code=0`, `114.67s`)
```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_*agy*.py"
```
```text
[agy-bridge] 16:03:32 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60564 ua=-
[agy-bridge] 16:03:32 init conversation=73cfa943 tools=0 permission_mode=x
[agy-bridge] 16:03:32 turn_mode cid=73cfa943 mode=OFF
[agy-bridge] 16:03:32 sqlite-off cid=73cfa943 reason=flag
[agy-bridge] 16:03:32 drain cid=73cfa943 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:32 done model=gemini-4-argon rc=0 state=done conversation=73cfa943 turns=None tool_events=0 out_bytes=10 wall_s=0.7 err='' client=127.0.0.1:60564 ua=-
[agy-bridge] 16:03:32 exec model=gemini-3.8-flash effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60565 ua=-
[agy-bridge] 16:03:32 init conversation=41c3c935 tools=0 permission_mode=x
[agy-bridge] 16:03:32 turn_mode cid=41c3c935 mode=OFF
[agy-bridge] 16:03:32 sqlite-off cid=41c3c935 reason=flag
[agy-bridge] 16:03:33 drain cid=41c3c935 ms=353 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:33 done model=gemini-3.8-flash rc=0 state=done conversation=41c3c935 turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60565 ua=-
[agy-bridge] 16:03:33 image_reject detail=input_not_image
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-3.7-flash model_len=16 client=127.0.0.1:60568
[agy-bridge] 16:03:33 image_reject detail=input_not_image
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-3.6-flash model_len=16 client=127.0.0.1:60569
[agy-bridge] 16:03:33 image_reject detail=input_not_image
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-3.1-pro model_len=14 client=127.0.0.1:60570
[agy-bridge] 16:03:33 image_reject detail=input_not_image
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gpt-oss-120b model_len=12 client=127.0.0.1:60571
[agy-bridge] 16:03:33 image_reject detail=image_input_disabled
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-4-argon model_len=14 client=127.0.0.1:60572
[agy-bridge] 16:03:33 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=63 tools=0 resume=0 sess=plain client=127.0.0.1:60573 ua=-
[agy-bridge] 16:03:33 init conversation=c352d97e tools=0 permission_mode=x
[agy-bridge] 16:03:33 turn_mode cid=c352d97e mode=OFF
[agy-bridge] 16:03:33 sqlite-off cid=c352d97e reason=flag
[agy-bridge] 16:03:33 drain cid=c352d97e ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:33 done model=gemini-4-argon rc=0 state=done conversation=c352d97e turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60573 ua=-
[agy-bridge] 16:03:33 image_reject detail=image_input_disabled
[agy-bridge] 16:03:33 reject reason=image_input_not_supported model=gemini-4-argon model_len=14 client=127.0.0.1:60577
.[agy-bridge] 16:03:34 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=2801 tools=0 resume=0 sess=plain client=127.0.0.1:60579 ua=-
[agy-bridge] 16:03:34 init conversation=dc364503 tools=0 permission_mode=x
[agy-bridge] 16:03:34 turn_mode cid=dc364503 mode=OFF
[agy-bridge] 16:03:34 sqlite-off cid=dc364503 reason=flag
[agy-bridge] 16:03:34 drain cid=dc364503 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:35 done model=gemini-4-argon rc=0 state=done conversation=dc364503 turns=None tool_events=0 out_bytes=10 wall_s=0.6 err='' client=127.0.0.1:60579 ua=-
[agy-bridge] 16:03:35 image_reject detail=too_many_images
[agy-bridge] 16:03:35 reject reason=too_many_images model=gemini-4-argon model_len=14 client=127.0.0.1:60580
.[agy-bridge] 16:03:35 image_reject detail=remote_or_file_url
[agy-bridge] 16:03:35 reject reason=image_url_not_allowed model=gemini-4-argon model_len=14 client=127.0.0.1:60582
[agy-bridge] 16:03:35 image_reject detail=remote_or_file_url
[agy-bridge] 16:03:35 reject reason=image_url_not_allowed model=gemini-4-argon model_len=14 client=127.0.0.1:60583
[agy-bridge] 16:03:35 image_reject detail=remote_or_file_url
[agy-bridge] 16:03:35 reject reason=image_url_not_allowed model=gemini-4-argon model_len=14 client=127.0.0.1:60584
[agy-bridge] 16:03:35 image_reject detail=remote_or_file_url
[agy-bridge] 16:03:35 reject reason=image_url_not_allowed model=gemini-4-argon model_len=14 client=127.0.0.1:60585
[agy-bridge] 16:03:35 image_reject detail=unsupported_mime
[agy-bridge] 16:03:35 reject reason=unsupported_image_type model=gemini-4-argon model_len=14 client=127.0.0.1:60586
[agy-bridge] 16:03:35 image_reject detail=unknown_magic
[agy-bridge] 16:03:35 reject reason=unsupported_image_type model=gemini-4-argon model_len=14 client=127.0.0.1:60587
[agy-bridge] 16:03:35 image_reject detail=invalid_base64
[agy-bridge] 16:03:35 reject reason=invalid_image_base64 model=gemini-4-argon model_len=14 client=127.0.0.1:60588
[agy-bridge] 16:03:35 image_reject detail=empty_payload
[agy-bridge] 16:03:35 reject reason=invalid_image_base64 model=gemini-4-argon model_len=14 client=127.0.0.1:60589
[agy-bridge] 16:03:35 image_reject detail=invalid_base64
[agy-bridge] 16:03:35 reject reason=invalid_image_base64 model=gemini-4-argon model_len=14 client=127.0.0.1:60590
[agy-bridge] 16:03:35 image_reject detail=mime_mismatch
[agy-bridge] 16:03:35 reject reason=image_type_mismatch model=gemini-4-argon model_len=14 client=127.0.0.1:60591
[agy-bridge] 16:03:35 image_reject detail=mime_mismatch
[agy-bridge] 16:03:35 reject reason=image_type_mismatch model=gemini-4-argon model_len=14 client=127.0.0.1:60592
[agy-bridge] 16:03:35 image_reject detail=invalid_image_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60593
[agy-bridge] 16:03:35 image_reject detail=invalid_image_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60594
[agy-bridge] 16:03:35 image_reject detail=invalid_image_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60595
[agy-bridge] 16:03:35 image_reject detail=malformed_data_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60596
[agy-bridge] 16:03:35 image_reject detail=malformed_data_url
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60597
[agy-bridge] 16:03:35 image_reject detail=non_user_image
[agy-bridge] 16:03:35 reject reason=invalid_image_content model=gemini-4-argon model_len=14 client=127.0.0.1:60598
[agy-bridge] 16:03:35 image_reject detail=too_many_images
[agy-bridge] 16:03:35 reject reason=too_many_images model=gemini-4-argon model_len=14 client=127.0.0.1:60599
[agy-bridge] 16:03:35 image_reject detail=image_too_large
[agy-bridge] 16:03:35 reject reason=image_too_large model=gemini-4-argon model_len=14 client=127.0.0.1:60600
[agy-bridge] 16:03:35 image_reject detail=images_too_large
[agy-bridge] 16:03:35 reject reason=images_too_large model=gemini-4-argon model_len=14 client=127.0.0.1:60601
[agy-bridge] 16:03:35 image_reject detail=input_not_image
[agy-bridge] 16:03:35 reject reason=image_input_not_supported model=gpt-oss-120b model_len=12 client=127.0.0.1:60602
[agy-bridge] 16:03:35 image_proof_invalid model=gemini-4-argon reason=impl_version_mismatch
[agy-bridge] 16:03:35 image_reject detail=image_proof_invalid
[agy-bridge] 16:03:35 reject reason=image_input_not_supported model=gemini-4-argon model_len=14 client=127.0.0.1:60603
[agy-bridge] 16:03:35 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=22 tools=0 resume=0 sess=plain client=127.0.0.1:60604 ua=-
[agy-bridge] 16:03:35 init conversation=8fd64ba6 tools=0 permission_mode=x
[agy-bridge] 16:03:35 turn_mode cid=8fd64ba6 mode=OFF
[agy-bridge] 16:03:35 sqlite-off cid=8fd64ba6 reason=flag
[agy-bridge] 16:03:36 drain cid=8fd64ba6 ms=354 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:36 done model=gemini-4-argon rc=0 state=done conversation=8fd64ba6 turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60604 ua=-
..[agy-bridge] 16:03:36 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=1 resume=0 sess=agentic client=127.0.0.1:60610 ua=-
[agy-bridge] 16:03:36 init conversation=f824fb0b tools=0 permission_mode=x
[agy-bridge] 16:03:36 turn_mode cid=f824fb0b mode=OFF
[agy-bridge] 16:03:36 sqlite-off cid=f824fb0b reason=flag
[agy-bridge] 16:03:37 drain cid=f824fb0b ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:37 done model=gemini-4-argon rc=0 state=done conversation=f824fb0b turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60610 ua=-
.[agy-bridge] 16:03:37 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60613 ua=-
[agy-bridge] 16:03:37 init conversation=091751fb tools=0 permission_mode=x
[agy-bridge] 16:03:37 turn_mode cid=091751fb mode=OFF
[agy-bridge] 16:03:37 sqlite-off cid=091751fb reason=flag
[agy-bridge] 16:03:38 drain cid=091751fb ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:38 done model=gemini-4-argon rc=0 state=done conversation=091751fb turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:60613 ua=-
[agy-bridge] 16:03:38 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60614 ua=-
[agy-bridge] 16:03:38 init conversation=1e6dba27 tools=0 permission_mode=x
[agy-bridge] 16:03:38 turn_mode cid=1e6dba27 mode=OFF
[agy-bridge] 16:03:38 sqlite-off cid=1e6dba27 reason=flag
[agy-bridge] 16:03:38 drain cid=1e6dba27 ms=352 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:38 transient failure state=agy_error rc=1 err='boom', retry 1 client=127.0.0.1:60614 ua=-
[agy-bridge] 16:03:38 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60614 ua=-
[agy-bridge] 16:03:38 init conversation=3a4fd18a tools=0 permission_mode=x
[agy-bridge] 16:03:38 turn_mode cid=3a4fd18a mode=OFF
[agy-bridge] 16:03:38 sqlite-off cid=3a4fd18a reason=flag
[agy-bridge] 16:03:38 drain cid=3a4fd18a ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:38 done model=gemini-4-argon rc=1 state=agy_error conversation=3a4fd18a turns=None tool_events=0 out_bytes=0 wall_s=0.9 err='boom' client=127.0.0.1:60614 ua=-
..[agy-bridge] 16:03:39 exec model=gemini-4-argon effort=high effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain client=127.0.0.1:60634 ua=-
[agy-bridge] 16:03:39 init conversation=0b193fbb tools=0 permission_mode=x
[agy-bridge] 16:03:39 turn_mode cid=0b193fbb mode=OFF
[agy-bridge] 16:03:39 sqlite-off cid=0b193fbb reason=flag
[agy-bridge] 16:03:41 drain cid=0b193fbb ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 16:03:41 done model=gemini-4-argon rc=0 state=done conversation=0b193fbb turns=None tool_events=0 out_bytes=10 wall_s=1.6 err='' client=127.0.0.1:60634 ua=-
.[agy-bridge] 16:03:41 exec model=gemini-4-argon effort=low effort_source=default prompt_bytes=390 tools=0 resume=0 sess=plain tag
[agy-bridge] 16:03:41 done model=gemini-4-argon rc=1 state=agy_error conversation=- turns=None tool_events=0 out_bytes=0 wall_s=0.0 err='e' tag
[agy-bridge] 16:03:41 exec model=gemini-4-argon effort=low effort_source=default prompt_bytes=390 tools=0 resume=1 sess=agentic tag
[agy-bridge] 16:03:41 done model=gemini-4-argon rc=1 state=agy_error conversation=- turns=None tool_events=0 out_bytes=0 wall_s=0.0 err='e' tag
..[agy-bridge] 16:03:42 turn_mode cid=82188e72 mode=LIVE
[agy-bridge] 16:03:42 sqlite-open-fail cid=82188e72 err=OperationalErro
```

### VER-006 (`PASS`, `exit_code=0`, `10.18s`)
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import subprocess; d=subprocess.check_output(["git","diff","--numstat","5a19559426de7508d525e2bd465eff648665a6a7","--","tests/test_agy_bridge_resilience.py"],text=True).splitlines(); assert all(int(l.split()[1])==0 for l in d); subprocess.run(["/usr/bin/python3","-B","-m","unittest","discover","-s","tests","-p","test_images_strict.py"],check=True)'
```
```text
2026-10-29T13:05:26Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61032 ua=-
2026-10-29T13:05:26Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:26Z usage sess=- raw=0/0 cache_read=- rep=0/0 resumed=0 turns=0
2026-10-29T13:05:26Z done model=claude-sonnet-5-5 rc=1 state=client_gone sess=- resumed=0 turns=0 out_bytes=0 wall_s=0.0 err='' client=127.0.0.1:61032 ua=-
.2026-10-29T13:05:27Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61045 ua=-
2026-10-29T13:05:27Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z transient failure rc=1 err='', retry 1 client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z transient failure rc=1 err='', retry 2 client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z usage sess=- raw=0/0 cache_read=- rep=0/0 resumed=0 turns=0
2026-10-29T13:05:28Z done model=claude-sonnet-5-5 rc=1 state=done sess=- resumed=0 turns=0 out_bytes=0 wall_s=0.3 err='' client=127.0.0.1:61045 ua=-
2026-10-29T13:05:28Z http "POST /v1/chat/completions HTTP/1.1" 502 -
.2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z transient failure rc=1 err='Exec failed', retry 1 client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z transient failure rc=1 err='Exec failed', retry 2 client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:28Z usage sess=- raw=0/0 cache_read=- rep=0/0 resumed=0 turns=0
2026-10-29T13:05:28Z done model=claude-sonnet-5-5 rc=1 state=done sess=- resumed=0 turns=0 out_bytes=0 wall_s=0.5 err='Exec failed' client=127.0.0.1:61050 ua=-
2026-10-29T13:05:28Z http "POST /v1/chat/completions HTTP/1.1" 502 -
.2026-10-29T13:05:29Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61053 ua=-
2026-10-29T13:05:29Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:29Z usage sess=sid-a273 raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:29Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-a273 resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61053 ua=-
2026-10-29T13:05:29Z http "POST /v1/chat/completions HTTP/1.1" 200 -
..2026-10-29T13:05:30Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=491 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61057 ua=-
2026-10-29T13:05:30Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:30Z usage sess=sid-429f raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:30Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-429f resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61057 ua=-
2026-10-29T13:05:30Z http "POST /v1/chat/completions HTTP/1.1" 200 -
.2026-10-29T13:05:30Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=1353 images=16 image_bytes=1144 image_types=image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png,image/png client=127.0.0.1:61065 ua=-
2026-10-29T13:05:30Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:30Z usage sess=sid-04c5 raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:30Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-04c5 resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61065 ua=-
2026-10-29T13:05:30Z http "POST /v1/chat/completions HTTP/1.1" 200 -
.2026-10-29T13:05:31Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=1150 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61069 ua=-
2026-10-29T13:05:31Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:31Z usage sess=sid-5dd5 raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:31Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-5dd5 resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61069 ua=-
2026-10-29T13:05:31Z http "POST /v1/chat/completions HTTP/1.1" 200 -
...2026-10-29T13:05:32Z reject reason=too_many_images model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61076
2026-10-29T13:05:32Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:32Z reject reason=image_too_large model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61077
2026-10-29T13:05:32Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:32Z reject reason=images_too_large model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61078
2026-10-29T13:05:32Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:32Z exec model=claude-sonnet-5-5 effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=549 images=2 image_bytes=1400 image_types=image/png,image/png client=127.0.0.1:61079 ua=-
2026-10-29T13:05:32Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:32Z usage sess=sid-764a raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:32Z done model=claude-sonnet-5-5 rc=0 state=done sess=sid-764a resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61079 ua=-
2026-10-29T13:05:32Z http "POST /v1/chat/completions HTTP/1.1" 200 -
..2026-10-29T13:05:33Z reject reason=image_url_not_allowed model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61087
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=image_url_not_allowed model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61088
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=image_url_not_allowed model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61089
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61090
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61091
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_base64 model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61092
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_base64 model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61093
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=image_type_mismatch model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61094
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61095
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61096
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61097
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61098
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61099
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61100
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=unsupported_image_type model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61101
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61102
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61103
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:33Z reject reason=invalid_image_content model=claude-sonnet-5-5 model_len=17 client=127.0.0.1:61104
2026-10-29T13:05:33Z http "POST /v1/chat/completions HTTP/1.1" 400 -
.2026-10-29T13:05:34Z reject reason=image_input_not_supported model=gemini-3.8-flash model_len=16 client=127.0.0.1:61107
2026-10-29T13:05:34Z http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-29T13:05:34Z reject reason=image_input_not_supported model=glm-5.3 model_len=7 client=127.0.0.1:61108
2026-10-29T13:05:34Z http "POST /v1/chat/completions HTTP/1.1" 400 -
.2026-10-29T13:05:34Z exec model=deepseek-v4.1-flash effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=493 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:61110 ua=-
2026-10-29T13:05:34Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:34Z usage sess=sid-0e4e raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:34Z done model=deepseek-v4.1-flash rc=0 state=done sess=sid-0e4e resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61110 ua=-
2026-10-29T13:05:34Z http "POST /v1/chat/completions HTTP/1.1" 200 -
..2026-10-29T13:05:35Z exec model=deepseek-v4.1-flash effort=high effort_source=request autonomy=high autonomy_source=default prompt_bytes=17 client=127.0.0.1:61116 ua=-
2026-10-29T13:05:35Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T13:05:35Z usage sess=sid-a5fc raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T13:05:35Z done model=deepseek-v4.1-flash rc=0 state=done sess=sid-a5fc resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:61116 ua=-
2026-10-29T13:05:35Z http "POST /v1/chat/completions HTTP/1.1" 200 -
.2026-10-29T13:05:36Z exec model=deepseek-v4.1-flash effort=max effort_source=request autonomy=high autonomy_source=default prompt_bytes=493 images=1 image_bytes=64 ima
```

### VER-007 (`PASS`, `exit_code=0`, `0.16s`)
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import ast,re; from pathlib import Path; t=ast.parse(Path("tests/test_agy_bridge_resilience.py").read_text()); expected={f"{p}{i:02}" for p,n in [("img",10),("hist",10),("life",5),("log",2),("res",3),("ao",10)] for i in range(1,n+1)}; found=set();
for f in ast.walk(t):
 if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef)) and f.name.startswith("test_") and any(isinstance(a,ast.Assert) or isinstance(a,ast.Call) and isinstance(a.func,ast.Attribute) and isinstance(a.func.value,ast.Name) and a.func.value.id=="self" and a.func.attr.startswith("assert") for a in ast.walk(f)):
  found.update(k for k in expected if re.search(r"(?:^|_)"+k+r"(?:_|$)",f.name))
assert not expected-found,sorted(expected-found); print("QA_ASSERT_COVERAGE_PASS",len(expected))'
```
```text
QA_ASSERT_COVERAGE_PASS 40
```

### VER-008 (`PASS`, `exit_code=0`, `0.13s`)
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import subprocess,hashlib; from pathlib import Path; b="5a19559426de7508d525e2bd465eff648665a6a7"; expected={"bridges/agy-bridge/fleet.json","bridges/agy-bridge/server.py","tests/test_agy_bridge_resilience.py"}; names=subprocess.check_output(["git","diff","--name-only",b,"HEAD"],text=True).splitlines(); actual={n for n in names if not n.startswith((".ai-team/","analysis/"))}; assert actual==expected,(actual,expected); tracked=subprocess.check_output(["git","ls-files"],text=True).splitlines(); assert not any(Path(n).name=="dynamic_config.json" for n in tracked); frozen={'"'"'research-plan'"'"': '"'"'67f3bfffc4e9df6b95ee8571c34ded4a397ad164f86787b3b935fe51dcf1243a'"'"', '"'"'evidence-ledger'"'"': '"'"'aba34816b5cf6425d4fbf19187a09edd5f7158797e442d488d68626576f887a9'"'"', '"'"'open-questions'"'"': '"'"'63fe13ce25d80cb7bad68d25a57c8d1d6e58847b5b8be79dc395b555c55e5b76'"'"', '"'"'handoff-architect'"'"': '"'"'6c22f4a0ab4fc71d2e7cd88e1fe7d2df8c327193eb75bfc9d922af68a4710a8f'"'"', '"'"'handoff-qa'"'"': '"'"'007cdac728cdd6754c6617cd749ed3361f0d19c9e1adae16a3c31a90ee352cee'"'"'};
for n,h in frozen.items(): assert hashlib.sha256(Path("analysis/agy-image-input-fix",n+".md").read_bytes()).hexdigest()==h,n
print("SCOPE_FROZEN_PASS")'
```
```text
SCOPE_FROZEN_PASS
```

### VER-009 (`PASS`, `exit_code=0`, `0.13s`)
```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import ast,sys; from pathlib import Path; s=Path("bridges/agy-bridge/server.py").read_text(); t=ast.parse(s); allowed=set(getattr(sys,"stdlib_module_names",()))|{"core"}; assert allowed-{"core"},"Use Python >=3.10 for stdlib inventory"; roots={a.name.split(".")[0] for n in ast.walk(t) if isinstance(n,ast.Import) for a in n.names}|{n.module.split(".")[0] for n in ast.walk(t) if isinstance(n,ast.ImportFrom) and n.module}; assert roots<=allowed,roots-allowed; vals=[ast.literal_eval(n.value) for n in ast.walk(t) if isinstance(n,ast.Assign) and any(isinstance(a,ast.Name) and a.id=="IMPLEMENTED_METHODS" for a in n.targets)]; assert vals==[{"workspace-read":1}],vals; assert all(v in s for v in ["IMAGE_INPUT_ENABLED","AGY_IMAGE_INPUT_ENABLED","--add-dir"]); helpers={n.name:n for n in ast.walk(t) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}; todo=[n for n in helpers if "image" in n or "data_url" in n]; seen=set();
while todo:
 n=todo.pop()
 if n in seen: continue
 seen.add(n); f=helpers[n]
 for a in ast.walk(f):
  if isinstance(a,ast.Call):
   name=ast.unparse(a.func); assert not any(v in name for v in ["urlopen","urlretrieve","urllib.request","http.client","HTTPConnection","HTTPSConnection"]),name
   if isinstance(a.func,ast.Name) and a.func.id in helpers: todo.append(a.func.id)
print("IMAGE_STDLIB_SECURITY_PASS")'
```
```text
IMAGE_STDLIB_SECURITY_PASS
```

### VER-010 (`DEFERRED_L3`, `exit_code=None`, `0.0s`)
```bash
Manual L3 verification on :9887
```
```text
Deferred to Wave 6 live L3 verification on 127.0.0.1:9887 after Council ACCEPT
```


### 4.2. Матрица трассируемости (`verification-traceability.md`), обратная спецификация (`reverse-spec.md`) и вердикт `ARCH_PANEL`

# Матрица трассируемости верификации (`teamlead/verification-traceability.md`)

## Поштучная матрица `REQ-001..REQ-010`, `AC-001..AC-010`, `AD-001..AD-006`, `F-001..F-010`, `AO-01..AO-10` и `VER-001..VER-010`

| Требование (`REQ`/`AC`) | Архитектурное решение (`AD`/`F`) | Реализация в коде (`fleet.json` / `server.py`) | Автоматизированные тесты и гейты (`tests/test_agy_bridge_resilience.py` / `VER-*`) | Статус |
|---|---|---|---|---|
| `REQ-001` (`AC-001`) | `AD-001` (`F-001`, `F-006`, `F-008`) | `fleet.json`: `agy_version: "1.4.9"`, `agy_binary_sha256: "35605054..."`, `input: ["text","image"]` и `images.proof` для `gemini-4-argon` и `gemini-3.8-flash` (4 остальных модели `unsupported`). `server.py`: `_is_image_input_enabled()` (`dynamic_config.json` `IMAGE_INPUT_ENABLED` TTL 1.0 s под `_image_flag_lock` + `AGY_IMAGE_INPUT_ENABLED`, fail-closed `False`), `_file_sha256` (1 MiB чанки вне лока, кэш `(st_dev, st_ino, st_mtime_ns, st_size)`), `_image_proof_reason`, `_model_supports_images` в `/v1/models` и `/health` | `test_ao01_*`, `test_f001_*`, `test_img08_*`, `test_img09_*` (`VER-003`, `VER-005`, `VER-007`, `VER-009`) | `PASS` (`exit_code=0`) |
| `REQ-002` (`AC-002`) | `AD-002` (`F-003`) | `fleet.json`: `image_limits` (`max_images: 16`, `max_image_bytes: 20971520`, `max_total_image_bytes: 20971520`, `max_body_bytes: 33554432`, `types: ["image/png","image/jpeg","image/gif","image/webp"]`). `server.py`: pre-check `len(parts) <= 16` и оценка длины base64 до `b64decode`, проверка `len(raw) <= max_image_bytes` и суммы `<= max_total_image_bytes`, HTTP 413 на `max_body_bytes` | `test_img01_*`, `test_img02_*`, `test_img04_*`, `test_img05_*`, `test_img06_*`, `test_img07_*`, `test_ao02_*`, `test_f003_*` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-003` (`AC-003`) | `AD-002` (`F-003`, `F-006`) | Строгий 13-шаговый порядок валидации в `_collect_images`: fast exit `[]` при `0` `image_url`, проверка флага, статуса/proof/effort, количества, роли `user`, `data:` URL (регистронезависимо), MIME по каноническому `IMAGE_LIMITS["types"]`, pre-check размера, `b64decode(validate=True)`, magic-byte sniffing (`PNG`/`JPEG`/`GIF`/`WebP`) против MIME; при сбое proof текстовые запросы продолжают работать (`200 OK`) | `test_img03_*`, `test_img08_*`, `test_img09_*`, `test_img10_*`, `test_ao03_*`, `test_f003_*`, `test_f006_*` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-004` (`AC-004`) | `AD-003` | Глобальная 1-based нумерация `[image 1]..[image K]` через `_content_to_text(..., img_counter)`. В `_messages_to_prompt` — все `1..K` в `[attachments]`. В `_get_resumed_turn_prompt` — срез `messages[last_asst + 1:]` с сохранением глобальных индексов `img_counter` и фильтрацией `delta_images = [img for img in images if img["msg_index"] > last_asst]`: на текстовом Turn 2 после Turn 1 с картинками блок `[attachments]` не дублируется, а при сбое hot-сессии и fallback на cold `full_prompt` все `1..K` файлов доступны в `img_dir` | `test_hist01_*` .. `test_hist10_*`, `test_ao04_*` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-005` (`AC-005`) | `AD-004` | Передача `--add-dir <img_dir>` в `Run.__init__` дискретными элементами списка `cmd` без изменения `cwd` и `sess_key = (model_id, cwd, effort)`. Корректная работа с пробелами и кириллицей (`~/Мой диск/...`) | `test_hist10_*`, `test_ao05_*` (`VER-003`, `VER-005`, `VER-007`, `VER-009`) | `PASS` (`exit_code=0`) |
| `REQ-006` (`AC-006`) | `AD-005` (`F-002`, `F-004`, `F-007`) | Спул `img_dir` строго внутри `_run_once` ПОСЛЕ `_acquire_slot()` и повторной проверки `_is_image_input_enabled()` / `_image_proof_reason()` (`F-002`). Права `0700` на `img_dir` и `0600` (`O_CREAT|O_EXCL|O_WRONLY` + `with os.fdopen(...)`) на файлы, немедленная очистка `img["data"] = b""` (`F-004`), при `OSError` — `ImageSpoolError` -> HTTP 500 `image_spool_error` с очисткой частичной папки и `0` spawn (`F-007`), гарантированный `shutil.rmtree` во внешнем `finally:` после `run.close()` на всех ретраях | `test_life01_*` .. `test_life04_*`, `test_ao06_*`, `test_f002_*`, `test_f007_*` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-007` (`AC-007`) | `AD-006` (`F-006`, `F-008`) | Расширение `_LOG_EVENT_NAMES` на 15 точных токенов (`image_input_not_supported`, `unsupported_image_type`, `invalid_image_content`, `invalid_image_base64`, `image_url_not_allowed`, `image_type_mismatch`, `image_proof_invalid`, `images_too_large`, `image_too_large`, `too_many_images`, `image_spool_error`, `image_cleanup_error`, `image_sweep_removed`, `unsupported_reasoning_effort`, `invalid_reasoning_effort`), санитизация `\r\n\t` в `model` (`F-006`), отсутствие base64/байтов картинок и путей в HTTP-ответах и логах | `test_log01_*`, `test_log02_*`, `test_ao07_*`, `test_f006_*` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-008` (`AC-008`) | `AD-005` (`F-007`) | `_sweep_workspace(cutoff_s=3600.0)`: регистрация `str(img_dir)` в `_active_img_dirs` под `_active_lock` ДО `os.mkdir`, пропуск активных папок и симлинков (`entry.is_symlink()`), удаление осиротевших `img-*` старше 3600 с при старте и периодически | `test_life05_*`, `test_ao08_*` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-009` (`AC-009`) | `AD-001..AD-006` (`F-005`) | Отсутствие регрессий текстового/SSE/thinking контура, соблюдение `MAX_PARALLEL`, отсутствие утечек FD и `img-*` папок при конкурентных запросах с фейковым `AGY_LAUNCHER`, зелёный прогон всех существующих тестов (`VER-001..VER-009`) | `test_res01_*`, `test_res02_*`, `test_res03_*`, `test_ao09_*` (`VER-001..VER-009`) | `PASS` (`exit_code=0`) |
| `REQ-010` (`AC-010`) | `AD-001..AD-006` | Схема консистентности пары `fleet.json` + `server.py` (`test_ao10_*` PASS); живая выкатка в `~/.dsh/bridges/agy-bridge/` и проверка multi-turn сценария DSH на `127.0.0.1:9887` (`VER-010`) | `test_ao10_*` (`PASS`) + `VER-010` (`DEFERRED_L3` до `ACCEPT` Совета Тимлидов) | `PASS` / `DEFERRED_L3` |


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


### 4.3. Полный текст `bridges/agy-bridge/fleet.json`, целевые секции `bridges/agy-bridge/server.py` (с номерами строк) и реестр всех тестов `tests/test_agy_bridge_resilience.py`

#### `bridges/agy-bridge/fleet.json`
```json
L1:{
L2:  "schema_version": 2,
L3:  "catalogue": "agy-bridge-fleet",
L4:  "policy_ref": {
L5:    "path": "~/Мой диск/Context/models.md",
L6:    "sha256": "3141a93a6b7ac562055da02b82121b866f1633e791175db316e77bea7cc07c67",
L7:    "reviewed_at": "2026-10-12T21:15:03+03:00"
L8:  },
L9:  "default_model": "gemini-3.8-flash",
L10:  "technical_ref": {
L11:    "agy_version": "1.4.9",
L12:    "agy_binary_path": "~/.local/bin/agy.real",
L13:    "launcher_path": "~/.config/agy-launch/agy-cli.sh",
L14:    "launcher_egress": "xray HTTP 127.0.0.1:10815 (резерв hy2 :10811; прямой вызов запрещён — гео РФ)",
L15:    "models_source": "agy models (live, 1.3.1)",
L16:    "invocation": "printf NDJSON | launcher --input-format stream-json --output-format stream-json --dangerously-skip-permissions --model <BASE_MODEL_ID> --effort <EFFORT> --print-timeout=0",
L17:    "note": "effort-суффикс (-high/-medium/-low) в fleet.json БОЛЬШЕ НЕ часть id: id = база (`gemini-3.8-flash`), уровень — отдельная ось `--effort`, значение берётся из `efforts` модели. Мост передаёт `--effort` ВСЕГДА (в т.ч. при пустом reasoning_effort — `default_effort`): база без effort у agy отвергается (`--model \"gemini-3.8-flash\" requires --effort (available: low, medium, high)`).",
L18:    "effort_ladders": "agy models 1.3.1: gemini-4-argon = low|medium|high; gemini-3.8/3.7/3.6-flash = low|medium|high; gemini-3.1-pro = low|high; gpt-oss-120b = medium (только)",
L19:    "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423"
L20:  },
L21:  "image_limits": {
L22:    "max_images": 16,
L23:    "max_image_bytes": 20971520,
L24:    "max_total_image_bytes": 20971520,
L25:    "max_body_bytes": 33554432,
L26:    "types": [
L27:      "image/png",
L28:      "image/jpeg",
L29:      "image/gif",
L30:      "image/webp"
L31:    ]
L32:  },
L33:  "admission": {
L34:    "max_http_connections": 32,
L35:    "max_inflight_body_bytes": 67108864,
L36:    "overload_error": {
L37:      "http": 503,
L38:      "type": "overloaded"
L39:    },
L40:    "oversize_error": {
L41:      "http": 413,
L42:      "type": "payload_too_large"
L43:    }
L44:  },
L45:  "models": [
L46:    {
L47:      "id": "gemini-4-argon",
L48:      "name": "Gemini 4 Argon (agy)",
L49:      "efforts": [
L50:        "low",
L51:        "medium",
L52:        "high"
L53:      ],
L54:      "default_effort": "high",
L55:      "context_window": 1048576,
L56:      "max_tokens": 65536,
L57:      "input": [
L58:        "text",
L59:        "image"
L60:      ],
L61:      "images": {
L62:        "cli_registry": "implicit_supported",
L63:        "status": "confirmed",
L64:        "method": "workspace-read",
L65:        "verified_at": "2026-10-29",
L66:        "proof": {
L67:          "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423",
L68:          "impl_version": 1,
L69:          "formats": [
L70:            "image/png",
L71:            "image/jpeg",
L72:            "image/gif",
L73:            "image/webp"
L74:          ],
L75:          "efforts_proven": [
L76:            "low",
L77:            "medium",
L78:            "high"
L79:          ],
L80:          "command": "agy.real -p 'Read img-1.png' --add-dir <img_dir> --model <model> --effort <effort>"
L81:        }
L82:      }
L83:    },
L84:    {
L85:      "id": "gemini-3.8-flash",
L86:      "name": "Gemini 3.8 Flash (agy)",
L87:      "efforts": [
L88:        "low",
L89:        "medium",
L90:        "high"
L91:      ],
L92:      "default_effort": "high",
L93:      "context_window": 1048576,
L94:      "max_tokens": 65536,
L95:      "input": [
L96:        "text",
L97:        "image"
L98:      ],
L99:      "images": {
L100:        "cli_registry": "implicit_supported",
L101:        "status": "confirmed",
L102:        "method": "workspace-read",
L103:        "verified_at": "2026-10-29",
L104:        "proof": {
L105:          "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423",
L106:          "impl_version": 1,
L107:          "formats": [
L108:            "image/png",
L109:            "image/jpeg",
L110:            "image/gif",
L111:            "image/webp"
L112:          ],
L113:          "efforts_proven": [
L114:            "low",
L115:            "medium",
L116:            "high"
L117:          ],
L118:          "command": "agy.real -p 'Read img-1.png' --add-dir <img_dir> --model <model> --effort <effort>"
L119:        }
L120:      }
L121:    },
L122:    {
L123:      "id": "gemini-3.7-flash",
L124:      "name": "Gemini 3.7 Flash (agy)",
L125:      "efforts": [
L126:        "low",
L127:        "medium",
L128:        "high"
L129:      ],
L130:      "default_effort": "high",
L131:      "context_window": 1048576,
L132:      "max_tokens": 65536,
L133:      "input": [
L134:        "text"
L135:      ],
L136:      "images": {
L137:        "cli_registry": "explicit_unsupported",
L138:        "status": "unsupported",
L139:        "method": null,
L140:        "proof": "agy 1.3.1 stream-json принимает только текстовые блоки контента; image_url отвергается: error: stream input content block type \"image_url\" is not supported (only \"text\") — проверено 2026-10-07"
L141:      }
L142:    },
L143:    {
L144:      "id": "gemini-3.6-flash",
L145:      "name": "Gemini 3.6 Flash (agy)",
L146:      "efforts": [
L147:        "low",
L148:        "medium",
L149:        "high"
L150:      ],
L151:      "default_effort": "high",
L152:      "context_window": 1048576,
L153:      "max_tokens": 65536,
L154:      "input": [
L155:        "text"
L156:      ],
L157:      "images": {
L158:        "cli_registry": "explicit_unsupported",
L159:        "status": "unsupported",
L160:        "method": null,
L161:        "proof": "agy 1.3.1 stream-json принимает только текстовые блоки контента; image_url отвергается: error: stream input content block type \"image_url\" is not supported (only \"text\") — проверено 2026-10-07"
L162:      }
L163:    },
L164:    {
L165:      "id": "gemini-3.1-pro",
L166:      "name": "Gemini 3.1 Pro (agy)",
L167:      "efforts": [
L168:        "low",
L169:        "high"
L170:      ],
L171:      "default_effort": "high",
L172:      "context_window": 2097152,
L173:      "max_tokens": 65536,
L174:      "input": [
L175:        "text"
L176:      ],
L177:      "images": {
L178:        "cli_registry": "explicit_unsupported",
L179:        "status": "unsupported",
L180:        "method": null,
L181:        "proof": "agy 1.3.1 stream-json принимает только текстовые блоки контента; image_url отвергается: error: stream input content block type \"image_url\" is not supported (only \"text\") — проверено 2026-10-07"
L182:      }
L183:    },
L184:    {
L185:      "id": "gpt-oss-120b",
L186:      "name": "GPT-OSS 120B (agy)",
L187:      "efforts": [
L188:        "medium"
L189:      ],
L190:      "default_effort": "medium",
L191:      "context_window": 131072,
L192:      "max_tokens": 32768,
L193:      "input": [
L194:        "text"
L195:      ],
L196:      "images": {
L197:        "cli_registry": "explicit_unsupported",
L198:        "status": "unsupported",
L199:        "method": null,
L200:        "proof": "agy 1.3.1 stream-json принимает только текстовые блоки контента; image_url отвергается: error: stream input content block type \"image_url\" is not supported (only \"text\") — проверено 2026-10-07"
L201:      }
L202:    }
L203:  ]
L204:}
```

#### `bridges/agy-bridge/server.py` (L1..L1150 и L3100..конец)
```python
L1:#!/usr/bin/env python3
L2:"""OpenAI-совместимый мост к Antigravity CLI (`agy`) для DeepSeek Harness.
L3:
L4:Один запрос /v1/chat/completions = один headless-ход CLI через канонический
L5:лончер ~/.config/agy-launch/agy-cli.sh (egress-пиннинг: xray HTTP :10815,
L6:резерв hy2 :10811; прямой вызов запрещён — гео РФ):
L7:
L8:    printf '%s\\n' '<NDJSON>' | launcher \\
L9:        --input-format stream-json --output-format stream-json \\
L10:        --dangerously-skip-permissions \\
L11:        --model <MODEL_ID> --effort <EFFORT> --print-timeout=0
L12:
L13:Промпт уходит ИСКЛЮЧИТЕЛЬНО на stdin строкой NDJSON
L14:`{"event":"user","message":{"role":"user","content":[{"type":"text","text":...}]}}`.
L15:Флаг `-p` НЕ передаётся НИКОГДА: `agy -p --input-format stream-json`
L16:разбирается неверно (`-p` съедает следующий флаг). Это проверенный факт 1.3.1.
L17:
L18:Каталог моделей — `fleet.json` (env `AGY_BRIDGE_FLEET`): читается один раз при
L19:старте, структурно проверяется (нарушение класса I — отказ старта). `id` модели —
L20:БАЗА (`gemini-3.8-flash`), уровень мышления — отдельная ось `--effort`; значение
L21:берётся строго из `efforts` каталога (никаких клампов и алиасов) и передаётся
L22:ВСЕГДА: при пустом `reasoning_effort` подставляется `default_effort`, потому что
L23:agy отвергает базу без effort — `--model "gemini-3.8-flash" requires --effort
L24:(available: low, medium, high)` (проверено 2026-10-07 на 1.3.1).
L25:
L26:Инструменты (tools) НЕ эмулируются текстовым протоколом. `agy` 1.3.1 сам
L27:пробрасывает ~51 нативный инструмент (`run_command`, `write_to_file`, `view_file`
L28:и др.) и с `--dangerously-skip-permissions` реально их исполняет. Штатный режим
L29:моста:
L30:
L31:  * если запрос пришёл без `tools` — это текстовый ход (роль судьи/ревьюера);
L32:    `--dangerously-skip-permissions` всё равно передаётся (набор флагов не зависит
L33:    от tools), но шаг без инструментов их и не вызывает;
L34:  * если запрос пришёл с `tools` — мост работает как АГЕНТНЫЙ ход: модель сама
L35:    исполняет свои нативные инструменты, мост лишь ждёт финальный текст. Наружу
L36:    `delta.tool_calls` НЕ отдаются (см. README, раздел «Инструменты»).
L37:
L38:События NDJSON разбираются как: `step_update` (`agent_response` -> текст,
L39:`step_type: tool` -> трассировка в stderr, `state: DONE` -> завершение) и
L40:`result` (`response` -> финальный текст, `usage` -> токены, `status`/`error`).
L41:
L42:Мышление шагов (`reasoning_content`) идёт клиенту в реальном времени: пока шаг ещё
L43:генерируется (`status=8`), подполе 20.3 его `step_payload` растёт в SQLite разговора
L44:`~/.gemini/antigravity-cli/conversations/<cid>.db`. База открывается только на чтение
L45:(`mode=ro`), разбор wire-формата — на stdlib. Источник вспомогателен и fail-open:
L46:транскрипт `transcript_full.jsonl` остаётся минимальным источником. Включение — флаг
L47:`SQLITE_REASONING_ENABLED` в `dynamic_config.json` (по умолчанию выключен) и аварийный
L48:выключатель `AGY_SQLITE_REASONING_ENABLED=0`.
L49:
L50:Изображения (метод `workspace-read`): `image_url` в NDJSON парсер agy не принимает, поэтому
L51:проверенные data-URL (PNG/JPEG/GIF/WebP) кладутся файлами в `WORKSPACE/img-<uuid>` на время
L52:хода, каталог отдаётся CLI через `--add-dir`, а в промпте они идут как `[image N]` и блок
L53:`[attachments]` с абсолютными путями (модель читает их нативным view_file). Вход выключен по
L54:умолчанию: флаг `IMAGE_INPUT_ENABLED` в `dynamic_config.json` (env `AGY_IMAGE_INPUT_ENABLED`
L55:решает сразу) и proof модели в fleet.json (sha256 бинаря agy, версия метода, форматы, effort).
L56:Проверка идёт до слота и spawn; запись на диск — только после захвата слота, удаление — в finally.
L57:
L58:Секреты с диска не читаются: ключ авторизации берётся только из окружения
L59:AGY_BRIDGE_KEY (его подкладывает start.sh из ~/.dsh/.env); в окружение дочернего
L60:процесса ключ моста не передаётся. Прокси-переменные выставляет сам лончер.
L61:"""
L62:
L63:from __future__ import annotations
L64:
L65:import base64
L66:import hashlib
L67:import json
L68:import os
L69:import queue
L70:import random
L71:import re
L72:import select
L73:import shutil
L74:import signal
L75:import socket
L76:import sqlite3
L77:import subprocess
L78:import sys
L79:import threading
L80:import time
L81:import uuid
L82:from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
L83:from pathlib import Path
L84:from typing import Any, Callable, cast, final
L85:
L86:# Корень репозитория cli-agent-bridge: resolve() раскрывает симлинк деплоя
L87:# (~/.dsh/bridges/agy-bridge -> <repo>/bridges/agy-bridge), parents[2] = <repo>.
L88:_REPO_ROOT = Path(__file__).resolve().parents[2]
L89:if str(_REPO_ROOT) not in sys.path:
L90:    sys.path.insert(0, str(_REPO_ROOT))
L91:
L92:from core.watchdog import (  # noqa: E402
L93:    IDLE_TIMEOUT_S as _CORE_IDLE_TIMEOUT_S,
L94:    WATCHDOG_INTERVAL_S,
L95:    AdaptiveTimeoutController,
L96:)
L97:
L98:ROOT = Path(__file__).resolve().parent
L99:HOME = Path.home()
L100:HOST = os.environ.get("AGY_BRIDGE_HOST", "127.0.0.1")
L101:PORT = int(os.environ.get("AGY_BRIDGE_PORT", "9887"))
L102:AUTH_KEY = os.environ.get("AGY_BRIDGE_KEY", "").strip()
L103:LAUNCHER = os.environ.get(
L104:    "AGY_LAUNCHER", str(HOME / ".config" / "agy-launch" / "agy-cli.sh")
L105:)
L106:FLEET_PATH = Path(os.environ.get("AGY_BRIDGE_FLEET", "") or str(ROOT / "fleet.json"))
L107:ENV_MODEL = os.environ.get("AGY_BRIDGE_MODEL", "").strip()
L108:WORKSPACE = ROOT / "workspace"
L109:MAX_CONCURRENT = int(os.environ.get("AGY_BRIDGE_MAX_CONCURRENT", "4"))
L110:QUEUE_TIMEOUT_S = int(os.environ.get("AGY_BRIDGE_QUEUE_TIMEOUT", "900"))
L111:TIMEOUT_S = int(os.environ.get("AGY_BRIDGE_TIMEOUT", "1800"))
L112:KEEPALIVE_S = float(os.environ.get("AGY_BRIDGE_KEEPALIVE", "15"))
L113:# Первое событие agy приходит не мгновенно (инициализация CLI + MCP-серверов),
L114:# но и не через минуты; 120 с — с запасом на холодный egress.
L115:FIRST_TOKEN_TIMEOUT_S = float(os.environ.get("AGY_BRIDGE_FIRST_TOKEN_TIMEOUT", "120"))
L116:PRINT_TIMEOUT = os.environ.get("AGY_BRIDGE_PRINT_TIMEOUT", "0")
L117:
L118:
L119:def _env_float(name: str, default: float, low: float, high: float) -> float:
L120:    """Число из окружения, зажатое в [low, high]; невалидное значение -> default."""
L121:    raw = os.environ.get(name, "").strip()
L122:    try:
L123:        value = float(raw) if raw else default
L124:    except ValueError:
L125:        value = default
L126:    if value != value:
L127:        value = default
L128:    return min(high, max(low, value))
L129:
L130:
L131:# Мышление шагов agy: CLI кладёт его в транскрипт разговора пошагово, в середине
L132:# хода. Путь и имя файла фиксированы CLI (проверено на agy 1.3.1).
L133:BRAIN_DIR = Path(
L134:    os.environ.get("AGY_BRIDGE_BRAIN", "")
L135:    or str(HOME / ".gemini" / "antigravity-cli" / "brain")
L136:)
L137:TRANSCRIPT_NAME = "transcript_full.jsonl"
L138:TRANSCRIPT_POLL_S = float(os.environ.get("AGY_BRIDGE_TRANSCRIPT_POLL", "0.05"))
L139:TRANSCRIPT_READ_MAX = 4 * 1024 * 1024
L140:
L141:# Живой источник мышления: SQLite-база разговора agy (таблица `steps`, шаг
L142:# планировщика `step_type=15`, подполе 20.3 `step_payload` растёт в `status=8`).
L143:# База открывается только на чтение; транскрипт остаётся минимальным источником.
L144:CONV_DIR = Path(
L145:    os.environ.get("AGY_BRIDGE_CONVERSATIONS", "")
L146:    or str(HOME / ".gemini" / "antigravity-cli" / "conversations")
L147:)
L148:# Бинарь agy: его идентичность (mtime_ns, size) ключует семантический canary.
L149:AGY_BIN = os.environ.get("AGY_BRIDGE_AGY_BIN", "") or str(
L150:    HOME / ".local" / "bin" / "agy.real"
L151:)
L152:SQLITE_POLL_S = _env_float("AGY_BRIDGE_SQLITE_POLL", 0.5, 0.5, 2.0)
L153:# Рантайм-флаг SQLITE_REASONING_ENABLED лежит рядом с server.py (в git не коммитится).
L154:DYNAMIC_CONFIG_PATH = ROOT / "dynamic_config.json"
L155:FLAG_NAME = "SQLITE_REASONING_ENABLED"
L156:FLAG_TTL_S = 1.0
L157:# Процесс вышел: окно финального дренирования источников мышления. Env
L158:# AGY_BRIDGE_TRANSCRIPT_GRACE задаёт само окно, граница DRAIN_MAX_S жёсткая.
L159:DRAIN_MAX_S = 0.50
L160:DRAIN_WINDOW_S = _env_float("AGY_BRIDGE_TRANSCRIPT_GRACE", 0.35, 0.20, DRAIN_MAX_S)
L161:DRAIN_MIN_S = min(_env_float("AGY_BRIDGE_DRAIN_MIN", 0.15, 0.05, 0.25), DRAIN_WINDOW_S)
L162:DRAIN_POLL_STEP_S = 0.05
L163:JOIN_TIMEOUT_S = _env_float("AGY_BRIDGE_DRAIN_JOIN", 0.15, 0.05, 0.20)
L164:PROC_EXIT_WAIT_S = 0.05
L165:# Потолки памяти и работы одной итерации опроса.
L166:MAX_REASONING_BYTES_PER_TURN = 2 * 1024 * 1024
L167:MAX_STEP_BLOB_BYTES = 262144
L168:MAX_STEPS_TRACKED = 128
L169:SQLITE_ROW_LIMIT = 16
L170:# Константы схемы привязаны к agy 1.4.9 и подтверждаются canary.
L171:STEP_TYPE_PLANNER = 15
L172:STEP_STATUS_GENERATING = 8
L173:STEP_STATUS_DONE = 3
L174:# cid, из которого строится путь к базе, обязан быть hex-строкой с дефисами.
L175:_CID_RE = re.compile(r"[0-9A-Fa-f-]{8,64}")
L176:_STEP_INDEX_RE = re.compile(rb'"step_index"\s*:\s*(\d+)')
L177:# Процессные guardrails (AD-005): breaker, бюджеты, окно проб.
L178:BREAKER_FAILURES_TO_OPEN = 3
L179:BREAKER_COOLDOWN_S = 30.0
L180:BREAKER_PROBE_LEASE_S = 60.0
L181:RETRY_CAPACITY_TENTHS = 30
L182:RETRY_CREDIT_TENTHS = 2
L183:RETRY_COST_TENTHS = 10
L184:POLL_BUCKET_CAPACITY_TENTHS = 30
L185:POLL_BUCKET_REFILL_TENTHS_PER_S = 20
L186:POLL_BUCKET_COST_TENTHS = 10
L187:RETRY_PAUSE_CAP_S = 2.0
L188:
L189:# Effort-оси. `--effort` у agy принимает low|medium|high; id модели — база без уровня,
L190:# уровень всегда уходит отдельным флагом (см. модуль-docstring).
L191:EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
L192:CLI_EFFORT_LEVELS = ("low", "medium", "high")
L193:IMAGE_STATUSES = ("unsupported", "unverified", "probe", "confirmed")
L194:# Доставка изображений агенту: проверенные файлы в WORKSPACE/img-<uuid>, каталог отдаётся
L195:# через `--add-dir`, модель читает их нативным view_file. Прямой image_url в NDJSON
L196:# парсер agy не принимает (см. fleet.json, proof 1.3.1).
L197:IMPLEMENTED_METHODS = {"workspace-read": 1}
L198:METHOD_IMPL_VERSION = 1
L199:IMAGE_FLAG_NAME = "IMAGE_INPUT_ENABLED"
L200:IMAGE_PROBE = os.environ.get("AGY_IMAGE_PROBE", "").strip().lower() in (
L201:    "1",
L202:    "true",
L203:    "yes",
L204:)
L205:_EXT = {
L206:    "image/png": "png",
L207:    "image/jpeg": "jpg",
L208:    "image/gif": "gif",
L209:    "image/webp": "webp",
L210:}
L211:SHA_CHUNK_BYTES = 1024 * 1024
L212:DYNAMIC_CONFIG_MAX_BYTES = 65536
L213:SWEEP_INTERVAL_S = 600.0
L214:
L215:CWD_MAX_LEN = 4096
L216:
L217:# Ленивые горячие сессии: следующий запрос с тем же (модель, cwd, effort) продолжает
L218:# разговор agy через --conversation и шлёт только новые сообщения, а не всю историю.
L219:SESSION_IDLE_TTL_S = 45 * 60.0
L220:SESSION_MAX_TTL_S = 24 * 3600.0
L221:SESSION_MAX_TURNS = 30
L222:
L223:_started = time.time()
L224:_active: dict = {}
L225:_active_lock = threading.Lock()
L226:_slots = threading.BoundedSemaphore(MAX_CONCURRENT)
L227:_budget = None
L228:_last_ok = [0.0]
L229:_session_store_lock = threading.Lock()
L230:_session_store: dict[tuple[str, str, str], dict[str, Any]] = {}
L231:_in_flight_cids: set[str] = set()
L232:# Владение разговором: cid -> turn_id активного хода (под _session_store_lock).
L233:# Два живых хода никогда не читают один <cid>.db и не делят один cid.
L234:_active_cid_owners: dict[str, str] = {}
L235:
L236:# Процессное состояние SQLite-источника мышления. Один замок охватывает breaker,
L237:# бюджеты, compat-canary, кэш флага и счётчики /health; I/O под ним не выполняется.
L238:_sqlite_guard_lock = threading.Lock()
L239:_breaker_state: str = "CLOSED"
L240:_breaker_failures: int = 0
L241:_breaker_opened_at: float = 0.0
L242:_breaker_probe_gen: int = 0
L243:_breaker_active_probe_gen: int | None = None
L244:_breaker_probe_started_at: float = 0.0
L245:_retry_tenths: int = RETRY_CAPACITY_TENTHS
L246:_compat_ident: tuple[int, int] | None = None
L247:_compat_state: str = "SHADOW"
L248:_flag_value: bool = False
L249:_flag_key: tuple[int, int] | None = None
L250:_flag_checked_at: float | None = None
L251:_sqlite_divergence_count: int = 0
L252:_sqlite_drain_deadline_count: int = 0
L253:_sqlite_open_connections: int = 0
L254:_sqlite_max_open_connections: int = 0
L255:_rng: Callable[[], float] = random.random
L256:
L257:# Изображения: хеш бинаря agy (кэш по идентичности файла), отдельный от SQLite-флага
L258:# кэш IMAGE_INPUT_ENABLED и реестр активных каталогов img-* (под _active_lock).
L259:_sha_cache_lock = threading.Lock()
L260:_sha_compute_lock = threading.Lock()
L261:_sha_cache: dict[str, tuple[tuple[int, int, int, int], str]] = {}
L262:_image_flag_lock = threading.Lock()
L263:_image_flag_cache: tuple[float, bool] = (0.0, False)
L264:_active_img_dirs: set[str] = set()
L265:
L266:# Токеноподобные последовательности в логах: сам ключ моста и длинные hex/base64.
L267:_SECRET = re.compile(r"[A-Za-z0-9_\-]{24,}")
L268:_NOISE = re.compile(
L269:    r"NODE_TLS_REJECT_UNAUTHORIZED|--trace-warnings|^\(node:\d+\)", re.I
L270:)
L271:
L272:
L273:class FleetViolation(Exception):
L274:    """Нарушение класса I каталога моделей: старт запрещён."""
L275:
L276:    def __init__(self, reason: str, model: str = "-"):
L277:        super().__init__(reason)
L278:        self.reason = reason
L279:        self.model = model
L280:
L281:
L282:def _build_catalog(data: Any) -> dict:
L283:    """Проверить каталог (класс I) и вернуть нормализованный словарь."""
L284:    if not isinstance(data, dict):
L285:        raise FleetViolation("fleet_unreadable", "-")
L286:    if data.get("schema_version") != 2:
L287:        raise FleetViolation("schema_version_invalid", "-")
L288:    limits = data.get("image_limits")
L289:    if not isinstance(limits, dict):
L290:        raise FleetViolation("limits_invalid", "-")
L291:    # Целочисленность и неотрицательность. НОЛЬ по числовым лимитам изображений —
L292:    # законное значение: `max_images: 0` означает "изображений не принимаем вовсе".
L293:    # Так у agy: stream-json принимает только текстовые блоки контента
L294:    # (`error: stream input content block type "image_url" is not supported
L295:    # (only "text")` — проверено 2026-10-07 на 1.3.1). max_body_bytes — это лимит
L296:    # HTTP-тела запроса, он всегда > 0, поэтому проверяется отдельно.
L297:    for key in ("max_images", "max_image_bytes", "max_total_image_bytes"):
L298:        if (
L299:            not isinstance(limits.get(key), int)
L300:            or isinstance(limits.get(key), bool)
L301:            or limits[key] < 0
L302:        ):
L303:            raise FleetViolation("limits_invalid", "-")
L304:    if (
L305:        not isinstance(limits.get("max_body_bytes"), int)
L306:        or isinstance(limits.get("max_body_bytes"), bool)
L307:        or limits["max_body_bytes"] <= 0
L308:    ):
L309:        raise FleetViolation("limits_invalid", "-")
L310:    # Типы обязаны быть непустым списком только если изображения вообще принимаются.
L311:    if not isinstance(limits.get("types"), list) or (
L312:        limits["max_images"] > 0 and not limits["types"]
L313:    ):
L314:        raise FleetViolation("limits_invalid", "-")
L315:    admission = data.get("admission")
L316:    if not isinstance(admission, dict):
L317:        raise FleetViolation("admission_invalid", "-")
L318:    for key in ("max_http_connections", "max_inflight_body_bytes"):
L319:        if (
L320:            not isinstance(admission.get(key), int)
L321:            or isinstance(admission.get(key), bool)
L322:            or admission[key] <= 0
L323:        ):
L324:            raise FleetViolation("admission_invalid", "-")
L325:    raw_models = data.get("models")
L326:    if not isinstance(raw_models, list) or not raw_models:
L327:        raise FleetViolation("models_invalid", "-")
L328:    models = {}
L329:    order = []
L330:    for item in raw_models:
L331:        if not isinstance(item, dict):
L332:            raise FleetViolation("model_invalid", "-")
L333:        mid = item.get("id")
L334:        if not isinstance(mid, str) or not mid:
L335:            raise FleetViolation("model_invalid", "-")
L336:        if mid in models:
L337:            raise FleetViolation("duplicate_id", mid)
L338:        efforts = item.get("efforts")
L339:        if (
L340:            not isinstance(efforts, list)
L341:            or not efforts
L342:            or not all(isinstance(e, str) for e in efforts)
L343:            or any(e not in EFFORT_LEVELS for e in efforts)
L344:        ):
L345:            raise FleetViolation("efforts_invalid", mid)
L346:        if item.get("default_effort") not in efforts:
L347:            raise FleetViolation("default_effort_invalid", mid)
L348:        images = item.get("images")
L349:        if not isinstance(images, dict):
L350:            raise FleetViolation("status_invalid", mid)
L351:        status = images.get("status")
L352:        if status not in IMAGE_STATUSES:
L353:            raise FleetViolation("status_invalid", mid)
L354:        input_types = item.get("input")
L355:        if not isinstance(input_types, list) or not all(
L356:            isinstance(t, str) for t in input_types
L357:        ):
L358:            raise FleetViolation("status_inconsistent", mid)
L359:        if (
L360:            images.get("cli_registry") == "explicit_unsupported"
L361:            and status != "unsupported"
L362:        ):
L363:            raise FleetViolation("status_inconsistent", mid)
L364:        # unsupported/unverified — text-only. confirmed/probe допустимы только с
L365:        # реализованным методом доставки и входом image; proof проверяется на каждом
L366:        # image-запросе (`_image_proof_reason`), а не при старте.
L367:        if status in ("unsupported", "unverified"):
L368:            if images.get("method") is not None or input_types != ["text"]:
L369:                raise FleetViolation("status_inconsistent", mid)
L370:        if status == "probe" and not IMAGE_PROBE:
L371:            raise FleetViolation("probe_flag_missing", mid)
L372:        method = images.get("method")
L373:        proof = cast(object, images.get("proof"))
L374:        if status in ("confirmed", "probe"):
L375:            if method not in IMPLEMENTED_METHODS:
L376:                raise FleetViolation("method_not_implemented", mid)
L377:            if "image" not in input_types or "text" not in input_types:
L378:                raise FleetViolation("status_inconsistent", mid)
L379:            if status == "confirmed" and not isinstance(proof, dict):
L380:                raise FleetViolation("proof_invalid", mid)
L381:            if limits["max_images"] <= 0 or not limits["types"]:
L382:                raise FleetViolation("limits_invalid", mid)
L383:        elif method is not None and method not in IMPLEMENTED_METHODS:
L384:            raise FleetViolation("method_not_implemented", mid)
L385:        models[mid] = {
L386:            "id": mid,
L387:            "name": str(item.get("name") or mid),
L388:            "efforts": [str(e) for e in efforts],
L389:            "default_effort": str(item["default_effort"]),
L390:            "context_window": int(item.get("context_window") or 0),
L391:            "max_tokens": int(item.get("max_tokens") or 0),
L392:            "input": [str(t) for t in input_types],
L393:            "images": {
L394:                "status": str(status),
L395:                "cli_registry": str(images.get("cli_registry") or ""),
L396:                "method": method,
L397:                "proof": proof,
L398:            },
L399:        }
L400:        order.append(mid)
L401:    default_model = data.get("default_model")
L402:    if not isinstance(default_model, str) or default_model not in models:
L403:        raise FleetViolation("default_model_invalid", "-")
L404:    if ENV_MODEL and ENV_MODEL not in models:
L405:        raise FleetViolation("env_model_invalid", ENV_MODEL)
L406:    technical_ref_raw = cast(object, data.get("technical_ref"))
L407:    technical_ref = (
L408:        cast("dict[str, object]", technical_ref_raw)
L409:        if isinstance(technical_ref_raw, dict)
L410:        else {}
L411:    )
L412:    return {
L413:        "schema_version": data.get("schema_version"),
L414:        "catalogue": str(cast("dict[str, object]", data).get("catalogue") or ""),
L415:        "default_model": default_model,
L416:        "order": order,
L417:        "models": models,
L418:        "image_limits": {
L419:            "max_images": int(limits["max_images"]),
L420:            "max_image_bytes": int(limits["max_image_bytes"]),
L421:            "max_total_image_bytes": int(limits["max_total_image_bytes"]),
L422:            "max_body_bytes": int(limits["max_body_bytes"]),
L423:            "types": [str(t) for t in limits["types"]],
L424:            "max_types": [str(t).lower() for t in limits["types"]],
L425:        },
L426:        "admission": {
L427:            "max_http_connections": int(admission["max_http_connections"]),
L428:            "max_inflight_body_bytes": int(admission["max_inflight_body_bytes"]),
L429:        },
L430:        "technical_ref": dict(technical_ref),
L431:    }
L432:
L433:
L434:def _load_fleet() -> dict:
L435:    """Прочитать и проверить fleet.json; при нарушении класса I — отказ старта."""
L436:    catalog = None
L437:    try:
L438:        raw = FLEET_PATH.read_bytes()
L439:    except OSError:
L440:        raw = None
L441:    if raw is not None:
L442:        try:
L443:            catalog = _build_catalog(json.loads(raw.decode("utf-8")))
L444:        except FleetViolation:
L445:            raise
L446:        except (ValueError, UnicodeDecodeError):
L447:            catalog = None
L448:    if catalog is None or raw is None:
L449:        sys.stderr.write("fleet_invalid model=- reason=fleet_unreadable\n")
L450:        sys.stderr.flush()
L451:        raise SystemExit(1)
L452:    catalog["path"] = str(FLEET_PATH)
L453:    catalog["sha256"] = hashlib.sha256(raw).hexdigest()
L454:    return catalog
L455:
L456:
L457:try:
L458:    FLEET = _load_fleet()
L459:except FleetViolation as _violation:
L460:    sys.stderr.write(
L461:        f"fleet_invalid model={_violation.model} reason={_violation.reason}\n"
L462:    )
L463:    sys.stderr.flush()
L464:    raise SystemExit(1)
L465:
L466:MODEL_ID = ENV_MODEL or FLEET["default_model"]
L467:FLEET_MODELS = cast("dict[str, dict[str, object]]", cast(object, FLEET["models"]))
L468:IMAGE_LIMITS = cast("dict[str, object]", cast(object, FLEET["image_limits"]))
L469:
L470:
L471:def _log(msg: str) -> None:
L472:    sys.stderr.write(
L473:        "[agy-bridge] %s %s\n" % (time.strftime("%H:%M:%S"), _mask_secrets(msg))
L474:    )
L475:    sys.stderr.flush()
L476:
L477:
L478:def _idle_timeout_from_env() -> float:
L479:    """Порог неактивности хода, с; невалидное или неположительное значение -> дефолт core."""
L480:    raw = os.environ.get("AGY_BRIDGE_IDLE_TIMEOUT", "").strip()
L481:    if not raw:
L482:        return float(_CORE_IDLE_TIMEOUT_S)
L483:    try:
L484:        value = float(raw)
L485:    except ValueError:
L486:        value = 0.0
L487:    if not value > 0.0 or value != value or value == float("inf"):
L488:        _log(
L489:            f"AGY_BRIDGE_IDLE_TIMEOUT={raw!r} invalid, using {_CORE_IDLE_TIMEOUT_S:g}s"
L490:        )
L491:        return float(_CORE_IDLE_TIMEOUT_S)
L492:    return value
L493:
L494:
L495:def _is_watchdog_enabled() -> bool:
L496:    """Kill-switch адаптивного сторожа: BRIDGE_ENABLE_ADAPTIVE_WATCHDOG=0|false|no|off."""
L497:    raw = os.environ.get("BRIDGE_ENABLE_ADAPTIVE_WATCHDOG", "1").strip().lower()
L498:    return raw not in ("0", "false", "no", "off")
L499:
L500:
L501:# Имена диагностических событий и причин отказа (мышление, изображения) длиннее 24
L502:# символов, но секретами не являются: без исключения маска скрыла бы их в логах.
L503:# Только точное совпадение токена целиком, не префикс и не подстрока.
L504:_LOG_EVENT_NAMES = frozenset(
L505:    {
L506:        "sqlite_snapshot_divergence",
L507:        "sqlite_transcript_divergence",
L508:        "image_input_not_supported",
L509:        "unsupported_reasoning_effort",
L510:        "invalid_reasoning_effort",
L511:        "unsupported_image_type",
L512:        "invalid_image_content",
L513:        "invalid_image_base64",
L514:        "image_url_not_allowed",
L515:        "image_type_mismatch",
L516:        "image_proof_invalid",
L517:        "images_too_large",
L518:        "image_too_large",
L519:        "too_many_images",
L520:        "image_spool_error",
L521:        "image_cleanup_error",
L522:        "image_sweep_removed",
L523:    }
L524:)
L525:
L526:
L527:def _mask_token(match: re.Match[str]) -> str:
L528:    token = match.group(0)
L529:    return token if token in _LOG_EVENT_NAMES else "***"
L530:
L531:
L532:def _mask_secrets(text: str) -> str:
L533:    """Погасить токеноподобные последовательности и сам ключ моста."""
L534:    out = str(text)
L535:    if AUTH_KEY:
L536:        out = out.replace(AUTH_KEY, "***")
L537:    return _SECRET.sub(_mask_token, out)
L538:
L539:
L540:def _err_summary(err: Any, limit: int = 200) -> str:
L541:    text = " ".join(str(err or "").split())
L542:    return text[:limit]
L543:
L544:
L545:# Порог неактивности хода (без протокольных событий и без прироста CPU/потомков группы).
L546:IDLE_TIMEOUT_S = _idle_timeout_from_env()
L547:# Зачистка группы: сколько ждать после SIGTERM и сколько — reap лидера после SIGKILL.
L548:KILL_TERM_GRACE_S = 2.0
L549:KILL_WAIT_S = 5.0
L550:# После result ERROR процесс обязан выйти сам: сколько ждать done, прежде чем сдаться.
L551:RESULT_EXIT_GRACE_S = 5.0
L552:# События очереди, считающиеся активностью агента (result/done/pump_error — терминальные).
L553:_ACTIVITY_KINDS = frozenset({"init", "text", "reasoning", "tool_trace"})
L554:
L555:
L556:def _launch_env() -> dict:
L557:    """Окружение для `agy`. Ключ моста потомку не передаётся.
L558:
L559:    Прокси-переменные (HTTPS_PROXY/HTTP_PROXY/NO_PROXY) выставляет сам лончер
L560:    agy-cli.sh — мост их не дублирует и не переопределяет.
L561:    """
L562:    env = os.environ.copy()
L563:    env.pop("AGY_BRIDGE_KEY", None)
L564:    return env
L565:
L566:
L567:class LauncherUnavailable(Exception):
L568:    """Канонический лончер отсутствует или не исполняем."""
L569:
L570:
L571:def _launcher() -> str:
L572:    """Канонический лончер обязателен; запасного пути на голый бинарь нет.
L573:
L574:    Без лончера agy гео-заблокирован (РФ), поэтому «fallback на голый бинарник»
L575:    запрещён: это дало бы тихий отказ вместо честной ошибки.
L576:    """
L577:    if os.path.isfile(LAUNCHER) and os.access(LAUNCHER, os.X_OK):
L578:        return LAUNCHER
L579:    raise LauncherUnavailable(LAUNCHER)
L580:
L581:
L582:def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
L583:    hdr = handler.headers.get("Authorization", "")
L584:    if hdr.startswith("Bearer "):
L585:        return hdr[7:].strip() == AUTH_KEY
L586:    return handler.headers.get("x-api-key", "") == AUTH_KEY or hdr.strip() == AUTH_KEY
L587:
L588:
L589:def _flatten_content(content: Any, img_counter: list[int] | None = None) -> str:
L590:    """Контент сообщения в текст; с `img_counter` image-части дают маркеры `[image N]`."""
L591:    if content is None:
L592:        return ""
L593:    if isinstance(content, str):
L594:        return content
L595:    if isinstance(content, list):
L596:        parts: list[str] = []
L597:        for item in content:
L598:            if isinstance(item, str):
L599:                parts.append(item)
L600:            elif (
L601:                img_counter is not None
L602:                and isinstance(item, dict)
L603:                and item.get("type") == "image_url"
L604:            ):
L605:                img_counter[0] += 1
L606:                parts.append("[image %d]" % img_counter[0])
L607:            elif isinstance(item, dict) and "text" in item:
L608:                parts.append(str(item["text"]))
L609:        return "\n".join(p for p in parts if p)
L610:    return str(content)
L611:
L612:
L613:def _tool_choice_none(tool_choice: Any) -> bool:
L614:    return isinstance(tool_choice, str) and tool_choice.strip().lower() == "none"
L615:
L616:
L617:@final
L618:class ImageReject(ValueError):
L619:    """Отказ по изображениям: `reason` — деталь для журнала, `code` — тип HTTP 400."""
L620:
L621:    def __init__(self, reason: str, code: str = "image_input_not_supported") -> None:
L622:        super().__init__(reason)
L623:        self.reason = reason
L624:        self.code = code
L625:
L626:
L627:@final
L628:class ImageSpoolError(RuntimeError):
L629:    """Проверенные изображения не удалось материализовать на диск."""
L630:
L631:
L632:_B64_WS = re.compile(r"[ \t\r\n\f\v]")
L633:_STATUS_REASONS = frozenset(
L634:    {"status_unsupported", "status_probe", "model_unknown", "input_not_image"}
L635:)
L636:
L637:
L638:def _safe_log_value(value: object) -> str:
L639:    """Значение из запроса для строки журнала: управляющие символы -> `_`."""
L640:    return re.sub(r"[\x00-\x1f\x7f]", "_", str(value))
L641:
L642:
L643:def _file_sha256(path: object) -> str:
L644:    """SHA-256 файла чанками по 1 MiB; '' — файл недоступен или изменился при чтении.
L645:
L646:    Кэш по пути с идентичностью (st_dev, st_ino, st_mtime_ns, st_size): неизменный
L647:    бинарь (~190 MiB) хешируется один раз. Хеширование идёт вне `_sha_cache_lock`,
L648:    под отдельным замком единственного вычислителя.
L649:    """
L650:    resolved = os.path.expanduser(str(path))
L651:
L652:    def identity() -> tuple[int, int, int, int]:
L653:        info = os.stat(resolved)
L654:        return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)
L655:
L656:    try:
L657:        key = identity()
L658:        with _sha_cache_lock:
L659:            cached = _sha_cache.get(resolved)
L660:        if cached is not None and cached[0] == key:
L661:            return cached[1]
L662:        with _sha_compute_lock:
L663:            with _sha_cache_lock:
L664:                cached = _sha_cache.get(resolved)
L665:            if cached is not None and cached[0] == key:
L666:                return cached[1]
L667:            digest = hashlib.sha256()
L668:            with open(resolved, "rb") as handle:
L669:                for chunk in iter(lambda: handle.read(SHA_CHUNK_BYTES), b""):
L670:                    digest.update(chunk)
L671:            if identity() != key:
L672:                return ""
L673:            hexdigest = digest.hexdigest()
L674:            with _sha_cache_lock:
L675:                _sha_cache[resolved] = (key, hexdigest)
L676:            return hexdigest
L677:    except OSError:
L678:        return ""
L679:
L680:
L681:def _read_image_flag() -> bool:
L682:    """IMAGE_INPUT_ENABLED из dynamic_config.json: строго `true`, иначе False."""
L683:    try:
L684:        path = DYNAMIC_CONFIG_PATH
L685:        if not path.is_file() or path.stat().st_size > DYNAMIC_CONFIG_MAX_BYTES:
L686:            return False
L687:        data = cast(object, json.loads(path.read_text(encoding="utf-8")))
L688:    except (OSError, ValueError):
L689:        return False
L690:    if not isinstance(data, dict):
L691:        return False
L692:    return cast("dict[str, object]", data).get(IMAGE_FLAG_NAME) is True
L693:
L694:
L695:def _is_image_input_enabled() -> bool:
L696:    """Fail-closed выключатель image-входа (по умолчанию False).
L697:
L698:    Env `AGY_IMAGE_INPUT_ENABLED` (непустой) решает сразу: 0|false|no|off -> False,
L699:    1|true|yes|on -> True, любое иное значение -> False. Без env — флаг
L700:    `IMAGE_INPUT_ENABLED` в dynamic_config.json с кэшем TTL 1.0 с; не-boolean,
L701:    битый или отсутствующий файл дают False. Не зависит от SQLITE_REASONING_ENABLED.
L702:    """
L703:    global _image_flag_cache
L704:    env = os.environ.get("AGY_IMAGE_INPUT_ENABLED", "").strip().lower()
L705:    if env:
L706:        return env in ("1", "true", "yes", "on")
L707:    now = time.monotonic()
L708:    with _image_flag_lock:
L709:        checked_at, cached = _image_flag_cache
L710:        if checked_at > 0.0 and now - checked_at < FLAG_TTL_S:
L711:            return cached
L712:    value = _read_image_flag()
L713:    with _image_flag_lock:
L714:        _image_flag_cache = (now, value)
L715:    return value
L716:
L717:
L718:def _image_proof_reason(model_id: str, effort: str | None = None) -> str | None:
L719:    """None — image-вход модели доказан; иначе короткая причина (без секретов)."""
L720:    model = FLEET_MODELS.get(model_id)
L721:    if model is None:
L722:        return "model_unknown"
L723:    raw_images = model.get("images")
L724:    images = (
L725:        cast("dict[str, object]", raw_images) if isinstance(raw_images, dict) else {}
L726:    )
L727:    raw_input = model.get("input")
L728:    if not isinstance(raw_input, list) or "image" not in cast(
L729:        "list[object]", raw_input
L730:    ):
L731:        return "input_not_image"
L732:    status = images.get("status")
L733:    if status == "probe":
L734:        if not IMAGE_PROBE:
L735:            return "status_probe"
L736:    elif status != "confirmed":
L737:        return "status_unsupported"
L738:    method = images.get("method")
L739:    if not isinstance(method, str) or method not in IMPLEMENTED_METHODS:
L740:        return "method_not_implemented"
L741:    proof_raw = images.get("proof")
L742:    if not isinstance(proof_raw, dict):
L743:        return "proof_missing"
L744:    proof = cast("dict[str, object]", proof_raw)
L745:    if proof.get("impl_version") != IMPLEMENTED_METHODS[method]:
L746:        return "impl_version_mismatch"
L747:    formats_raw = proof.get("formats")
L748:    types_raw = IMAGE_LIMITS.get("types")
L749:    types = cast("list[object]", types_raw) if isinstance(types_raw, list) else []
L750:    if not isinstance(formats_raw, list) or not formats_raw:
L751:        return "formats_mismatch"
L752:    if not {str(t).lower() for t in types} <= {
L753:        str(f).lower() for f in cast("list[object]", formats_raw)
L754:    }:
L755:        return "formats_mismatch"
L756:    efforts_raw = proof.get("efforts_proven")
L757:    if not isinstance(efforts_raw, list):
L758:        return "efforts_missing"
L759:    if effort is not None and effort not in cast("list[object]", efforts_raw):
L760:        return "effort_not_proven"
L761:    expected = proof.get("agy_binary_sha256")
L762:    if not isinstance(expected, str) or len(expected) != 64:
L763:        return "binary_sha_missing"
L764:    actual = _file_sha256(AGY_BIN)
L765:    if not actual or actual != expected.lower():
L766:        return "binary_sha_mismatch"
L767:    return None
L768:
L769:
L770:def _model_supports_images(model_id: str) -> bool:
L771:    return _is_image_input_enabled() and _image_proof_reason(model_id) is None
L772:
L773:
L774:def _image_gate(model_id: str, effort: str | None) -> ImageReject | None:
L775:    """Флаг и proof для image-запроса: None — можно, иначе отказ (без I/O с телом)."""
L776:    if not _is_image_input_enabled():
L777:        return ImageReject("image_input_disabled")
L778:    reason = _image_proof_reason(model_id, effort)
L779:    if reason is None:
L780:        return None
L781:    if reason in _STATUS_REASONS:
L782:        return ImageReject(reason)
L783:    if reason == "effort_not_proven":
L784:        return ImageReject(reason, "unsupported_reasoning_effort")
L785:    _log("image_proof_invalid model=%s reason=%s" % (_safe_log_value(model_id), reason))
L786:    return ImageReject("image_proof_invalid")
L787:
L788:
L789:def _collect_image_parts(
L790:    messages: object,
L791:) -> list[tuple[int, int, dict[str, object]]]:
L792:    """Все image_url-части истории: (индекс сообщения с 0, сквозной номер с 1, часть)."""
L793:    found: list[tuple[int, int, dict[str, object]]] = []
L794:    if not isinstance(messages, list):
L795:        return found
L796:    number = 0
L797:    for msg_index, msg in enumerate(cast("list[object]", messages)):
L798:        if not isinstance(msg, dict):
L799:            continue
L800:        content = cast("dict[str, object]", msg).get("content")
L801:        if not isinstance(content, list):
L802:            continue
L803:        for item in cast("list[object]", content):
L804:            if isinstance(item, dict):
L805:                part = cast("dict[str, object]", item)
L806:                if part.get("type") == "image_url":
L807:                    number += 1
L808:                    found.append((msg_index, number, part))
L809:    return found
L810:
L811:
L812:def _sniff_image_type(raw: bytes) -> str | None:
L813:    """MIME по сигнатуре (не декодирование пикселей); None — формат неизвестен."""
L814:    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
L815:        return "image/png"
L816:    if raw.startswith(b"\xff\xd8\xff"):
L817:        return "image/jpeg"
L818:    if raw.startswith((b"GIF87a", b"GIF89a")):
L819:        return "image/gif"
L820:    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
L821:        return "image/webp"
L822:    return None
L823:
L824:
L825:def _limit(name: str, default: int) -> int:
L826:    value = IMAGE_LIMITS.get(name, default)
L827:    return value if isinstance(value, int) and not isinstance(value, bool) else default
L828:
L829:
L830:def _new_img_dir() -> Path:
L831:    """Путь (без обращений к диску) каталога изображений одного хода."""
L832:    return Path(os.path.abspath(str(WORKSPACE))) / ("img-" + uuid.uuid4().hex)
L833:
L834:
L835:def _collect_images(
L836:    messages: object, model_id: str, effort: str | None
L837:) -> list[dict[str, object]]:
L838:    """Проверить image-части всей истории; вернуть записи для prompt и spool.
L839:
L840:    Нет image-частей — `[]` сразу, без stat/хеша/флага. Порядок отказов: флаг и
L841:    proof -> число частей -> по каждой части: роль, форма, `data:` URL, MIME,
L842:    оценка размера base64 ДО decode, строгий base64, сигнатура, лимиты. Ничего не
L843:    пишется на диск и не запускается. Декодированные байты не удерживаются
L844:    (`data` пуст): в spool они пересоздаются из base64 уже после захвата слота.
L845:    """
L846:    parts = _collect_image_parts(messages)
L847:    if not parts:
L848:        return []
L849:    gate = _image_gate(model_id, effort)
L850:    if gate is not None:
L851:        raise gate
L852:    max_images = _limit("max_images", 16)
L853:    if max_images <= 0:
L854:        raise ImageReject("images_disabled")
L855:    if len(parts) > max_images:
L856:        raise ImageReject("too_many_images", "too_many_images")
L857:    max_bytes = _limit("max_image_bytes", 0)
L858:    max_total = _limit("max_total_image_bytes", 0)
L859:    allowed_raw = IMAGE_LIMITS.get("types")
L860:    allowed = {
L861:        str(t).lower()
L862:        for t in (
L863:            cast("list[object]", allowed_raw) if isinstance(allowed_raw, list) else []
L864:        )
L865:    }
L866:    msgs = cast("list[object]", messages)
L867:    img_dir = _new_img_dir()
L868:    entries: list[dict[str, object]] = []
L869:    total = 0
L870:    for msg_index, number, part in parts:
L871:        msg = cast("dict[str, object]", msgs[msg_index])
L872:        if msg.get("role") != "user":
L873:            raise ImageReject("non_user_image", "invalid_image_content")
L874:        ref = part.get("image_url")
L875:        url = (
L876:            cast("dict[str, object]", ref).get("url") if isinstance(ref, dict) else None
L877:        )
L878:        if not isinstance(url, str) or not url:
L879:            raise ImageReject("invalid_image_url", "invalid_image_content")
L880:        if url[:5].lower() != "data:":
L881:            raise ImageReject("remote_or_file_url", "image_url_not_allowed")
L882:        comma = url.find(",")
L883:        if comma < 0:
L884:            raise ImageReject("malformed_data_url", "invalid_image_content")
L885:        header = [h.strip().lower() for h in url[5:comma].split(";")]
L886:        mime = header[0]
L887:        if not mime or "base64" not in header[1:]:
L888:            raise ImageReject("malformed_data_url", "invalid_image_content")
L889:        if mime not in allowed or mime not in _EXT:
L890:            raise ImageReject("unsupported_mime", "unsupported_image_type")
L891:        payload = url[comma + 1 :]
L892:        if _B64_WS.search(payload) is not None:
L893:            payload = _B64_WS.sub("", payload)
L894:        if not payload:
L895:            raise ImageReject("empty_payload", "invalid_image_base64")
L896:        pad = 2 if payload.endswith("==") else (1 if payload.endswith("=") else 0)
L897:        if (len(payload) * 3) // 4 - pad > max_bytes:
L898:            raise ImageReject("image_too_large", "image_too_large")
L899:        try:
L900:            raw = base64.b64decode(payload, validate=True)
L901:        except Exception:
L902:            raise ImageReject("invalid_base64", "invalid_image_base64") from None
L903:        if not raw:
L904:            raise ImageReject("empty_image", "invalid_image_content")
L905:        actual = _sniff_image_type(raw)
L906:        if actual is None:
L907:            raise ImageReject("unknown_magic", "unsupported_image_type")
L908:        if actual != mime:
L909:            raise ImageReject("mime_mismatch", "image_type_mismatch")
L910:        size = len(raw)
L911:        del raw
L912:        if size > max_bytes:
L913:            raise ImageReject("image_too_large", "image_too_large")
L914:        if total + size > max_total:
L915:            raise ImageReject("images_too_large", "images_too_large")
L916:        total += size
L917:        ext = _EXT[mime]
L918:        entries.append(
L919:            {
L920:                "index": number,
L921:                "msg_index": msg_index,
L922:                "mime": mime,
L923:                "ext": ext,
L924:                "size": size,
L925:                "data": b"",
L926:                "b64": payload,
L927:                "path": img_dir / ("img-%d.%s" % (number, ext)),
L928:            }
L929:        )
L930:    return entries
L931:
L932:
L933:def _stage_images(img_dir: Path, images: list[dict[str, object]]) -> None:
L934:    """Материализовать проверенные изображения: каталог 0700, файлы 0600, O_EXCL.
L935:
L936:    Байты берутся из base64 здесь, после захвата слота, и сразу сбрасываются.
L937:    Любая ошибка ввода-вывода удаляет частичный каталог и даёт ImageSpoolError.
L938:    """
L939:    try:
L940:        os.makedirs(str(img_dir.parent), exist_ok=True)
L941:        os.mkdir(str(img_dir), 0o700)
L942:        for img in images:
L943:            held = img.get("data")
L944:            data = (
L945:                bytes(cast(bytes, held))
L946:                if held
L947:                else base64.b64decode(cast(str, img["b64"]), validate=True)
L948:            )
L949:            if len(data) != cast(int, img["size"]):
L950:                raise ValueError("size mismatch")
L951:            fd = os.open(str(img["path"]), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
L952:            try:
L953:                handle = os.fdopen(fd, "wb")
L954:            except BaseException:
L955:                os.close(fd)
L956:                raise
L957:            with handle:
L958:                _ = handle.write(data)
L959:            img["data"] = b""
L960:            _ = img.pop("b64", None)
L961:    except (OSError, ValueError) as exc:
L962:        shutil.rmtree(str(img_dir), ignore_errors=True)
L963:        raise ImageSpoolError(type(exc).__name__) from None
L964:
L965:
L966:def _cleanup_img_dir(img_dir: Path) -> None:
L967:    """Удалить каталог хода и снять его с реестра активных (ошибка видна в журнале)."""
L968:    try:
L969:        shutil.rmtree(str(img_dir))
L970:    except FileNotFoundError:
L971:        pass
L972:    except OSError as exc:
L973:        _log("image_cleanup_error err=%s" % type(exc).__name__)
L974:        shutil.rmtree(str(img_dir), ignore_errors=True)
L975:    finally:
L976:        with _active_lock:
L977:            _active_img_dirs.discard(str(img_dir))
L978:
L979:
L980:def _attachments_block(images: list[dict[str, object]]) -> str:
L981:    lines = [
L982:        "[attachments]",
L983:        "The user attached %d image file(s), accessible in the workspace directory"
L984:        % len(images)
L985:        + " via --add-dir:",
L986:    ]
L987:    for img in images:
L988:        lines.append(
L989:            "- [image %d] %s (%s, %d bytes)"
L990:            % (
L991:                cast(int, img["index"]),
L992:                str(img["path"]),
L993:                cast(str, img["mime"]),
L994:                cast(int, img["size"]),
L995:            )
L996:        )
L997:    lines.append(
L998:        "Read every attached image file listed above using your file/image inspection"
L999:        + " tool (e.g. view_file) before answering."
L1000:    )
L1001:    return "\n".join(lines)
L1002:
L1003:
L1004:def _render_message(
L1005:    msg: Any, counter: list, img_counter: list[int] | None = None
L1006:) -> str:
L1007:    """Сообщение OpenAI в текстовый блок промпта (роли не теряются)."""
L1008:    if not isinstance(msg, dict):
L1009:        return ""
L1010:    role = str(msg.get("role") or "user")
L1011:    name = msg.get("name")
L1012:    label = role if not name else "%s(%s)" % (role, name)
L1013:    body = _flatten_content(msg.get("content"), img_counter)
L1014:    lines = []
L1015:    calls = msg.get("tool_calls")
L1016:    if isinstance(calls, list):
L1017:        for call in calls:
L1018:            if not isinstance(call, dict):
L1019:                continue
L1020:            fn = call.get("function") if isinstance(call.get("function"), dict) else {}
L1021:            fname = str(fn.get("name") or "unknown")
L1022:            fargs = fn.get("arguments")
L1023:            if not isinstance(fargs, str):
L1024:                fargs = (
L1025:                    json.dumps(fargs, ensure_ascii=False) if fargs is not None else "{}"
L1026:                )
L1027:            lines.append(
L1028:                "[tool call %s] %s(%s)" % (call.get("id") or "call", fname, fargs)
L1029:            )
L1030:    if role == "tool":
L1031:        cid = msg.get("tool_call_id") or "call"
L1032:        lines.append("[tool result %s] %s" % (cid, body))
L1033:    elif body:
L1034:        lines.append(body)
L1035:    prepared = "\n".join(lines).strip()
L1036:    if not prepared:
L1037:        return ""
L1038:    counter[0] += 1
L1039:    return "### %d. %s\n%s" % (counter[0], label, prepared)
L1040:
L1041:
L1042:def _messages_to_prompt(
L1043:    messages: list,
L1044:    images: list[dict[str, object]] | None = None,
L1045:    img_start: int = 0,
L1046:) -> str:
L1047:    """Собрать единый текстовый промпт хода.
L1048:
L1049:    Секции протокола инструментов нет намеренно: agy исполняет СВОИ нативные
L1050:    инструменты, а не инструменты DSH (см. README, раздел «Инструменты»).
L1051:    Image-части получают сквозные маркеры `[image N]` (нумерация с `img_start + 1`),
L1052:    а `images` описываются блоком `[attachments]` с абсолютными путями файлов.
L1053:    """
L1054:    counter = [0]
L1055:    img_counter = [img_start]
L1056:    blocks: list[str] = []
L1057:    for msg in messages:
L1058:        rendered = _render_message(msg, counter, img_counter)
L1059:        if rendered:
L1060:            blocks.append(rendered)
L1061:    if images:
L1062:        blocks.append(_attachments_block(images))
L1063:    text = "\n\n".join(blocks).strip()
L1064:    if not text:
L1065:        text = "Reply with exactly: PONG"
L1066:    return text
L1067:
L1068:
L1069:def _get_resumed_turn_prompt(
L1070:    messages: list, images: list[dict[str, object]] | None = None
L1071:) -> str:
L1072:    """Промпт хода продолжения: сообщения после последнего assistant.
L1073:
L1074:    Маркеры сохраняют сквозные номера всей истории; `[attachments]` — только для
L1075:    изображений новых сообщений. Без assistant в истории — вся история целиком.
L1076:    """
L1077:    last_asst = -1
L1078:    for i in range(len(messages) - 1, -1, -1):
L1079:        if isinstance(messages[i], dict) and messages[i].get("role") == "assistant":
L1080:            last_asst = i
L1081:            break
L1082:    if last_asst >= 0 and last_asst + 1 < len(messages):
L1083:        new_msgs = messages[last_asst + 1 :]
L1084:        skipped = len(
L1085:            _collect_image_parts(cast("list[object]", messages[: last_asst + 1]))
L1086:        )
L1087:        delta = [
L1088:            img
L1089:            for img in (images or [])
L1090:            if cast(int, img.get("msg_index", 0)) > last_asst
L1091:        ]
L1092:        prompt = _messages_to_prompt(new_msgs, delta, skipped)
L1093:        if prompt:
L1094:            return prompt
L1095:    return _messages_to_prompt(messages, images)
L1096:
L1097:
L1098:def _session_claim(sess_key: tuple, turn_id: str = "") -> str:
L1099:    """Найти живую свободную сессию и занять её; '' — сессии нет.
L1100:
L1101:    Проверка и занятие идут под одним замком: два параллельных запроса не
L1102:    получат один и тот же conversation_id. При непустом `turn_id` владение cid
L1103:    регистрируется в `_active_cid_owners` в той же критической секции.
L1104:    """
L1105:    now = time.time()
L1106:    with _session_store_lock:
L1107:        entry = _session_store.get(sess_key)
L1108:        if entry is None:
L1109:            return ""
L1110:        if (
L1111:            now - entry["last_used"] > SESSION_IDLE_TTL_S
L1112:            or now - entry["created"] > SESSION_MAX_TTL_S
L1113:            or entry["turns"] >= SESSION_MAX_TURNS
L1114:        ):
L1115:            _session_store.pop(sess_key, None)
L1116:            return ""
L1117:        cid = cast(str, entry["cid"])
L1118:        if cid in _in_flight_cids:
L1119:            return ""
L1120:        owner = _active_cid_owners.get(cid)
L1121:        if owner is not None and owner != turn_id:
L1122:            return ""
L1123:        _in_flight_cids.add(cid)
L1124:        if turn_id:
L1125:            _active_cid_owners[cid] = turn_id
L1126:        return cid
L1127:
L1128:
L1129:def _session_invalidate(sess_key: tuple, cid: str) -> None:
L1130:    with _session_store_lock:
L1131:        entry = _session_store.get(sess_key)
L1132:        if entry is not None and entry["cid"] == cid:
L1133:            _session_store.pop(sess_key, None)
L1134:
L1135:
L1136:def _session_commit(sess_key: tuple, cid: str) -> None:
L1137:    now = time.time()
L1138:    with _session_store_lock:
L1139:        entry = _session_store.get(sess_key)
L1140:        if entry is not None and entry["cid"] == cid:
L1141:            entry["last_used"] = now
L1142:            entry["turns"] += 1
L1143:        else:
L1144:            _session_store[sess_key] = {
L1145:                "cid": cid,
L1146:                "last_used": now,
L1147:                "created": now,
L1148:                "turns": 1,
L1149:            }
L1150:
L3100:                        (str(result_ev.get("error") or "") or err)[:500],
L3101:                    )
L3102:                return state("done", rc, err)
L3103:
L3104:    def _log_done(
L3105:        self, model: str, out: dict[str, object], t0: float, tag: str
L3106:    ) -> None:
L3107:        """Одна строка done на каждом выходе _run_once (O-EXIT)."""
L3108:        conversation = str(out.get("conversation_id") or "-")[:8]
L3109:        out_bytes = len(str(out.get("text") or "").encode())
L3110:        _log(
L3111:            f"done model={model} rc={out.get('rc')} state={out.get('state')} "
L3112:            f"conversation={conversation} "
L3113:            f"turns={out.get('num_turns')} tool_events={out.get('tool_events')} "
L3114:            f"out_bytes={out_bytes} "
L3115:            f"wall_s={time.monotonic() - t0:.1f} "
L3116:            f"err={_err_summary(out.get('err'))!r} {tag}"
L3117:        )
L3118:
L3119:    def _run_once(
L3120:        self, ctx: dict, on_text, on_tool_trace, on_reasoning, keepalive
L3121:    ) -> dict:
L3122:        model = ctx["model"]
L3123:        effort = ctx["effort"]
L3124:        tag = ctx["tag"]
L3125:        t_enter = time.monotonic()
L3126:        reason = self._acquire_slot(keepalive)
L3127:        if reason:
L3128:            _log(f"no slot ({reason}) model={model} {tag}")
L3129:            if reason == "queue_timeout":
L3130:                self._log_reject("overloaded", model, ctx["model_len"])
L3131:            early: dict[str, object] = {
L3132:                "state": reason,
L3133:                "rc": 1,
L3134:                "text": "",
L3135:                "usage": {},
L3136:                "result": {},
L3137:                "err": "",
L3138:                "tool_calls": [],
L3139:                "tool_events": 0,
L3140:                "conversation_id": "",
L3141:                "num_turns": None,
L3142:                "duration_s": None,
L3143:            }
L3144:            self._log_done(
L3145:                cast(str, ctx["model"]), early, t_enter, cast(str, ctx["tag"])
L3146:            )
L3147:            return early
L3148:        t0 = time.monotonic()
L3149:        out: dict = {}
L3150:        typed_ctx = cast("dict[str, object]", ctx)
L3151:        images = cast("list[dict[str, object]]", typed_ctx.get("images") or [])
L3152:        img_dir = cast("Path | None", typed_ctx.get("img_dir")) if images else None
L3153:        img_registered = False
L3154:        try:
L3155:            try:
L3156:                _launcher()
L3157:            except LauncherUnavailable:
L3158:                self._log_reject("launcher_unavailable", model, ctx["model_len"])
L3159:                unavailable: dict[str, object] = {
L3160:                    "state": "launcher_unavailable",
L3161:                    "rc": 1,
L3162:                    "text": "",
L3163:                    "usage": {},
L3164:                    "result": {},
L3165:                    "err": "",
L3166:                    "tool_calls": [],
L3167:                    "tool_events": 0,
L3168:                    "conversation_id": "",
L3169:                    "num_turns": None,
L3170:                    "duration_s": None,
L3171:                }
L3172:                self._log_done(
L3173:                    cast(str, ctx["model"]), unavailable, t_enter, cast(str, ctx["tag"])
L3174:                )
L3175:                return unavailable
L3176:            if images and img_dir is not None:
L3177:                # Флаг и proof могли смениться, пока ход ждал слот: повторная проверка
L3178:                # до mkdir и spawn.
L3179:                gate = _image_gate(cast(str, model), cast(str, effort))
L3180:                if gate is not None:
L3181:                    self._log_reject(
L3182:                        gate.code, cast(str, model), cast(int, ctx["model_len"])
L3183:                    )
L3184:                    rejected = _terminal_state("image_reject", gate.code)
L3185:                    self._log_done(
L3186:                        cast(str, ctx["model"]),
L3187:                        rejected,
L3188:                        t_enter,
L3189:                        cast(str, ctx["tag"]),
L3190:                    )
L3191:                    return rejected
L3192:                # Реестр активных каталогов ПЕРЕД mkdir: sweep не тронет живой ход.
L3193:                with _active_lock:
L3194:                    _active_img_dirs.add(str(img_dir))
L3195:                img_registered = True
L3196:                try:
L3197:                    _stage_images(img_dir, images)
L3198:                except ImageSpoolError as exc:
L3199:                    _log(
L3200:                        "image_spool_error model=%s err=%s"
L3201:                        % (_safe_log_value(cast(str, model)), exc)
L3202:                    )
L3203:                    failed = _terminal_state("image_spool_error", str(exc))
L3204:                    self._log_done(
L3205:                        cast(str, ctx["model"]), failed, t_enter, cast(str, ctx["tag"])
L3206:                    )
L3207:                    return failed
L3208:            _retry_credit()
L3209:            for attempt in (1, 2):
L3210:                _log(
L3211:                    f"exec model={model} effort={effort} effort_source={ctx['effort_source']} "
L3212:                    f"prompt_bytes={len(ctx['prompt'].encode())} "
L3213:                    f"tools={ctx['tools_count']} resume={1 if ctx.get('conversation_id') else 0} "
L3214:                    f"sess={'agentic' if ctx.get('sess_key') else 'plain'} {tag}"
L3215:                )
L3216:                try:
L3217:                    run = Run(
L3218:                        ctx["prompt"],
L3219:                        model,
L3220:                        effort,
L3221:                        ctx["effort_source"],
L3222:                        ctx["cwd"],
L3223:                        tag,
L3224:                        conversation_id=ctx.get("conversation_id") or "",
L3225:                        turn_id=str(ctx.get("turn_id") or ""),
L3226:                        add_dir=img_dir if images else None,
L3227:                    )
L3228:                except LauncherUnavailable:
L3229:                    self._reject(
L3230:                        503,
L3231:                        "launcher_unavailable",
L3232:                        "canonical launcher is missing or not executable",
L3233:                        model=model,
L3234:                        model_len=ctx["model_len"],
L3235:                    )
L3236:                    out = {
L3237:                        "state": "launcher_unavailable",
L3238:                        "rc": 1,
L3239:                        "text": "",
L3240:                        "usage": {},
L3241:                        "result": {},
L3242:                        "err": "",
L3243:                        "tool_calls": [],
L3244:                        "tool_events": 0,
L3245:                        "conversation_id": "",
L3246:                        "num_turns": None,
L3247:                        "duration_s": None,
L3248:                    }
L3249:                    break
L3250:                except OSError as exc:
L3251:                    out = {
L3252:                        "state": "pump_error",
L3253:                        "rc": 1,
L3254:                        "text": "",
L3255:                        "usage": {},
L3256:                        "result": {},
L3257:                        "err": repr(exc),
L3258:                        "tool_calls": [],
L3259:                        "tool_events": 0,
L3260:                        "conversation_id": "",
L3261:                        "num_turns": None,
L3262:                        "duration_s": None,
L3263:                    }
L3264:                    break
L3265:                try:
L3266:                    out = self._execute(
L3267:                        run, on_text, on_tool_trace, on_reasoning, keepalive
L3268:                    )
L3269:                finally:
L3270:                    run.close()
L3271:                if out["state"] == "done":
L3272:                    break
L3273:                # Выдача клиенту: текст, tool_calls или уже отданное в поток мышление.
L3274:                # JSON-режим мышление клиенту ещё не отдавал — там повтор безопасен.
L3275:                delivered = bool(
L3276:                    out.get("text")
L3277:                    or out.get("tool_calls")
L3278:                    or (ctx.get("stream") and out.get("reasoning"))
L3279:                )
L3280:                if ctx.get("hot_resumed") and out["state"] != "client_gone":
L3281:                    # Горячая сессия сломалась: больше её не используем, а повтор
L3282:                    # идёт холодным вызовом с полной историей.
L3283:                    _session_invalidate(ctx["sess_key"], ctx["conversation_id"])
L3284:                    _cid_release(
L3285:                        str(ctx["conversation_id"]), str(ctx.get("turn_id") or "")
L3286:                    )
L3287:                    ctx["hot_resumed"] = False
L3288:                    ctx["conversation_id"] = ""
L3289:                    ctx["prompt"] = ctx["full_prompt"]
L3290:                    if out["state"] == "agy_error" and not delivered:
L3291:                        if not _retry_take():
L3292:                            _log(f"retry-budget-exhausted state={out['state']} {tag}")
L3293:                            break
L3294:                        _log(
L3295:                            f"hot session failed err={_err_summary(out.get('err'), 120)!r}, "
L3296:                            f"cold fallback {tag}"
L3297:                        )
L3298:                        continue
L3299:                # Транзиентный сбой до выдачи клиенту — один невидимый повтор.
L3300:                transient = (
L3301:                    out["state"] in ("agy_error", "pump_error", "done")
L3302:                    and not delivered
L3303:                )
L3304:                if not transient or attempt == 2:
L3305:                    break
L3306:                if not _retry_take():
L3307:                    _log(f"retry-budget-exhausted state={out['state']} {tag}")
L3308:                    break
L3309:                _log(
L3310:                    f"transient failure state={out['state']} rc={out.get('rc')} "
L3311:                    f"err={_err_summary(out.get('err'), 120)!r}, retry {attempt} {tag}"
L3312:                )
L3313:                time.sleep(_retry_pause_s(attempt))
L3314:            if (
L3315:                out.get("state") == "done"
L3316:                and out.get("conversation_id")
L3317:                and ctx.get("sess_key")
L3318:            ):
L3319:                _session_commit(ctx["sess_key"], str(out["conversation_id"]))
L3320:            if out.get("state") != "client_gone":
L3321:                _last_ok[0] = (
L3322:                    time.monotonic()
L3323:                    if (out.get("state") == "done" and out.get("rc") == 0)
L3324:                    else 0.0
L3325:                )
L3326:        finally:
L3327:            # Каталог изображений живёт весь ход (все попытки) и уходит до слота.
L3328:            if img_registered and img_dir is not None:
L3329:                _cleanup_img_dir(img_dir)
L3330:            _slots.release()
L3331:        self._log_done(
L3332:            cast(str, ctx["model"]),
L3333:            cast("dict[str, object]", out),
L3334:            t0,
L3335:            cast(str, ctx["tag"]),
L3336:        )
L3337:        return out
L3338:
L3339:    @staticmethod
L3340:    def _usage_payload(usage: dict) -> dict:
L3341:        """usage agy -> OpenAI-поля. thinking_tokens прибавляем к completion."""
L3342:        return {
L3343:            "prompt_tokens": usage.get("input_tokens", 0),
L3344:            "completion_tokens": usage.get("output_tokens", 0)
L3345:            + usage.get("thinking_tokens", 0),
L3346:            "total_tokens": usage.get("total_tokens", 0),
L3347:        }
L3348:
L3349:    @staticmethod
L3350:    def _error_body(out: dict) -> Any:
L3351:        st = out.get("state")
L3352:        if st == "timeout":
L3353:            return {
L3354:                "message": f"agy timed out after {TIMEOUT_S}s",
L3355:                "type": "timeout",
L3356:                "code": 504,
L3357:            }
L3358:        if st == "idle_timeout":
L3359:            return {
L3360:                "message": f"agy execution idle timeout after {IDLE_TIMEOUT_S:g}s "
L3361:                "(no activity or progress in process group)",
L3362:                "type": "idle_timeout",
L3363:                "code": 504,
L3364:            }
L3365:        if st == "first_token_timeout":
L3366:            return {
L3367:                "message": f"first_token_timeout: agy gave no event within "
L3368:                f"{FIRST_TOKEN_TIMEOUT_S:g}s",
L3369:                "type": "first_token_timeout",
L3370:                "code": 504,
L3371:            }
L3372:        if st == "queue_timeout":
L3373:            return {
L3374:                "message": f"bridge busy: queue full over {QUEUE_TIMEOUT_S}s",
L3375:                "type": "overloaded",
L3376:                "code": 503,
L3377:            }
L3378:        if st == "launcher_unavailable":
L3379:            return {
L3380:                "message": "canonical launcher is missing or not executable",
L3381:                "type": "launcher_unavailable",
L3382:                "code": 503,
L3383:            }
L3384:        if st == "client_gone":
L3385:            return {"message": "client gone", "type": "client_gone", "code": 499}
L3386:        if st == "image_reject":
L3387:            code = cast(str, out["err"]) or "image_input_not_supported"
L3388:            return {"message": f"image rejected: {code}", "type": code, "code": 400}
L3389:        if st == "image_spool_error":
L3390:            return {
L3391:                "message": "image spool failed",
L3392:                "type": "image_spool_error",
L3393:                "code": 500,
L3394:            }
L3395:        if st == "pump_error":
L3396:            return {
L3397:                "message": "bridge reader failed",
L3398:                "detail": str(out.get("err"))[:500],
L3399:                "type": "proxy_error",
L3400:                "code": 502,
L3401:            }
L3402:        if st == "agy_error":
L3403:            return {
L3404:                "message": str(out.get("err") or "agy reported an error")[:500],
L3405:                "type": "agy_error",
L3406:                "code": 502,
L3407:            }
L3408:        if out.get("rc") != 0 or not out.get("text"):
L3409:            return {
L3410:                "message": f"agy exited rc={out.get('rc')}",
L3411:                "detail": str(out.get("err"))[:500],
L3412:                "type": "proxy_error",
L3413:                "code": 502,
L3414:            }
L3415:        return None
L3416:
L3417:    # ---- HTTP --------------------------------------------------------------------
L3418:    def do_GET(self) -> None:  # noqa: N802
L3419:        path = self.path.split("?", 1)[0]
L3420:        if path in ("/health", "/v1/health"):
L3421:            with _active_lock:
L3422:                active = len(_active)
L3423:            health: dict[str, object] = {
L3424:                "ok": True,
L3425:                "transport": "agy-stream-json",
L3426:                "model": MODEL_ID,
L3427:                "active": active,
L3428:                "max_concurrent": MAX_CONCURRENT,
L3429:                "hot_sessions": len(_session_store),
L3430:                "tool_emulation": False,
L3431:                "tool_translation": False,
L3432:                "native_tools": True,
L3433:                "images": any(_model_supports_images(mid) for mid in FLEET_MODELS),
L3434:                "image_input_mode": (
L3435:                    "enabled" if _is_image_input_enabled() else "disabled"
L3436:                ),
L3437:                "uptime_s": int(time.time() - _started),
L3438:            }
L3439:            health.update(_sqlite_health_fields())
L3440:            self._send(200, health)
L3441:            return
L3442:        if not _auth_ok(self):
L3443:            self._send(
L3444:                401,
L3445:                {
L3446:                    "error": {
L3447:                        "message": "unauthorized",
L3448:                        "type": "auth_error",
L3449:                        "code": 401,
L3450:                    }
L3451:                },
L3452:            )
L3453:            return
L3454:        if path in ("/v1/models", "/models"):
L3455:            data = []
L3456:            order = [MODEL_ID] + [mid for mid in FLEET["order"] if mid != MODEL_ID]
L3457:            image_flags: list[bool] = []
L3458:            for mid in order:
L3459:                model = FLEET["models"][mid]
L3460:                supports = _model_supports_images(cast(str, mid))
L3461:                image_flags.append(supports)
L3462:                data.append(
L3463:                    {
L3464:                        "id": mid,
L3465:                        "object": "model",
L3466:                        "owned_by": "antigravity",
L3467:                        "created": 0,
L3468:                        "context_length": model["context_window"],
L3469:                        "images": supports,
L3470:                    }
L3471:                )
L3472:            self._send(
L3473:                200, {"object": "list", "data": data, "images": any(image_flags)}
L3474:            )
L3475:            return
L3476:        self._send(
L3477:            404,
L3478:            {
L3479:                "error": {
L3480:                    "message": f"not found: {path}",
L3481:                    "type": "not_found",
L3482:                    "code": 404,
L3483:                }
L3484:            },
L3485:        )
L3486:
L3487:    def do_POST(self) -> None:  # noqa: N802
L3488:        if not _auth_ok(self):
L3489:            # Непрочитанное тело иначе будет разобрано как следующий запрос keep-alive.
L3490:            self.close_connection = True
L3491:            self._send(
L3492:                401,
L3493:                {
L3494:                    "error": {
L3495:                        "message": "unauthorized",
L3496:                        "type": "auth_error",
L3497:                        "code": 401,
L3498:                    }
L3499:                },
L3500:            )
L3501:            return
L3502:        if self.headers.get_all("Transfer-Encoding") is not None:
L3503:            self._reject(400, "invalid_request", "Transfer-Encoding is not supported")
L3504:            return
L3505:        content_lengths = self.headers.get_all("Content-Length")
L3506:        length = 0
L3507:        if content_lengths is not None:
L3508:            values = [str(v).strip() for v in content_lengths]
L3509:            if len(set(values)) != 1 or not re.fullmatch(r"[0-9]+", values[0]):
L3510:                self._reject(400, "invalid_request", "invalid Content-Length")
L3511:                return
L3512:            length = int(values[0])
L3513:        if length > int((FLEET.get("image_limits") or {}).get("max_body_bytes") or 0):
L3514:            self._reject(
L3515:                413, "payload_too_large", "request body exceeds the bridge limit"
L3516:            )
L3517:            return
L3518:        reserved = 0
L3519:        budget = _budget
L3520:        if budget is not None and length:
L3521:            if not budget.reserve(length):
L3522:                self._reject(
L3523:                    503, "overloaded", "bridge overloaded: body budget exhausted"
L3524:                )
L3525:                return
L3526:            reserved = length
L3527:        use_cid = ""
L3528:        owned_cid = ""
L3529:        turn_id = uuid.uuid4().hex
L3530:        try:
L3531:            raw = self.rfile.read(length) if length else b""
L3532:            if len(raw) < length:
L3533:                self._reject(400, "invalid_request", "request body truncated")
L3534:                return
L3535:            try:
L3536:                req = json.loads(raw.decode("utf-8"))
L3537:            except (ValueError, UnicodeDecodeError):
L3538:                self._reject(400, "invalid_request", "invalid json")
L3539:                return
L3540:            if not isinstance(req, dict):
L3541:                self._reject(400, "invalid_request", "request must be a JSON object")
L3542:                return
L3543:            path = self.path.split("?", 1)[0]
L3544:            if path not in ("/v1/chat/completions", "/chat/completions"):
L3545:                self.close_connection = True
L3546:                self._send(
L3547:                    404,
L3548:                    {
L3549:                        "error": {
L3550:                            "message": f"not found: {path}",
L3551:                            "type": "not_found",
L3552:                            "code": 404,
L3553:                        }
L3554:                    },
L3555:                )
L3556:                return
L3557:            raw_model = req.get("model")
L3558:            model_len = len(raw_model) if isinstance(raw_model, str) else 0
L3559:            if raw_model is None:
L3560:                model_id = MODEL_ID
L3561:            elif isinstance(raw_model, str):
L3562:                candidate = raw_model.strip()
L3563:                model_id = candidate if candidate else MODEL_ID
L3564:            else:
L3565:                self._reject(
L3566:                    400,
L3567:                    "model_not_allowed",
L3568:                    "model must be a string from the catalogue",
L3569:                    "unknown",
L3570:                    model_len,
L3571:                )
L3572:                return
L3573:            if model_id not in FLEET["models"]:
L3574:                self._reject(
L3575:                    400,
L3576:                    "model_not_allowed",
L3577:                    "model is not in the catalogue",
L3578:                    "unknown",
L3579:                    model_len,
L3580:                )
L3581:                return
L3582:            model = FLEET["models"][model_id]
L3583:            raw_effort = req.get("reasoning_effort")
L3584:            if raw_effort is None:
L3585:                effort = model["default_effort"]
L3586:                effort_source = "default"
L3587:            elif isinstance(raw_effort, str):
L3588:                candidate = raw_effort.strip()
L3589:                if not candidate:
L3590:                    effort = model["default_effort"]
L3591:                    effort_source = "default"
L3592:                elif candidate in model["efforts"]:
L3593:                    effort = candidate
L3594:                    effort_source = "request"
L3595:                else:
L3596:                    self._reject(
L3597:                        400,
L3598:                        "unsupported_reasoning_effort",
L3599:                        "reasoning_effort is not allowed for this model",
L3600:                        model_id,
L3601:                        model_len,
L3602:                    )
L3603:                    return
L3604:            else:
L3605:                self._reject(
L3606:                    400,
L3607:                    "unsupported_reasoning_effort",
L3608:                    "reasoning_effort must be a string",
L3609:                    model_id,
L3610:                    model_len,
L3611:                )
L3612:                return
L3613:            if "reasoning" in req and req.get("reasoning") is not None:
L3614:                self._reject(
L3615:                    400,
L3616:                    "unsupported_parameter",
L3617:                    "reasoning parameter is not supported",
L3618:                    model_id,
L3619:                    model_len,
L3620:                )
L3621:                return
L3622:            messages_raw = cast(object, req.get("messages"))
L3623:            messages = (
L3624:                cast("list[object]", messages_raw)
L3625:                if isinstance(messages_raw, list)
L3626:                else []
L3627:            )
L3628:            try:
L3629:                images = _collect_images(
L3630:                    messages, cast(str, model_id), cast(str, effort)
L3631:                )
L3632:            except ImageReject as rejected:
L3633:                _log("image_reject detail=%s" % rejected.reason)
L3634:                self._reject(
L3635:                    400,
L3636:                    rejected.code,
L3637:                    f"image rejected: {rejected.code}",
L3638:                    model_id,
L3639:                    model_len,
L3640:                )
L3641:                return
L3642:            img_dir = cast(Path, images[0]["path"]).parent if images else None
L3643:            try:
L3644:                _launcher()
L3645:            except LauncherUnavailable:
L3646:                self._reject(
L3647:                    503,
L3648:                    "launcher_unavailable",
L3649:                    "canonical launcher is missing or not executable",
L3650:                    model_id,
L3651:                    model_len,
L3652:                )
L3653:                return
L3654:            raw_tools = req.get("tools")
L3655:            tools = (
L3656:                [t for t in raw_tools if isinstance(t, dict)]
L3657:                if isinstance(raw_tools, list)
L3658:                else []
L3659:            )
L3660:            tools_count = 0 if _tool_choice_none(req.get("tool_choice")) else len(tools)
L3661:            full_prompt = _messages_to_prompt(messages, images)
L3662:            extra = (
L3663:                req.get("extra_body") if isinstance(req.get("extra_body"), dict) else {}
L3664:            )
L3665:            cwd = str(extra.get("cwd") or "")
L3666:            if len(cwd) > CWD_MAX_LEN:
L3667:                cwd = ""
L3668:            conversation_id = str(
L3669:                extra.get("conversation_id") or req.get("conversation_id") or ""
L3670:            )
L3671:            # Горячие сессии — только агентным запросам с инструментами. Фоновые и
L3672:            # plain-запросы (в т. ч. генерация заголовка DSH, tools=0) стор не читают
L3673:            # и не пишут: ни claim, ни commit, ни invalidate.
L3674:            use_session_store = tools_count > 0
L3675:            sess_key: tuple[str, str, str] | None = (
L3676:                (cast(str, model_id), cwd, cast(str, effort))
L3677:                if use_session_store
L3678:                else None
L3679:            )
L3680:            is_resumed = False
L3681:            prompt = full_prompt
L3682:            if conversation_id:
L3683:                if _cid_acquire(conversation_id, turn_id):
L3684:                    owned_cid = conversation_id
L3685:                else:
L3686:                    # cid занят другим активным ходом: два хода не делят один разговор.
L3687:                    _log(f"cid-busy-fresh cid={conversation_id[:8]}")
L3688:                    conversation_id = ""
L3689:            elif sess_key is not None:
L3690:                use_cid = _session_claim(sess_key, turn_id)
L3691:                if use_cid:
L3692:                    conversation_id = use_cid
L3693:                    is_resumed = True
L3694:                    prompt = _get_resumed_turn_prompt(messages, images)
L3695:            ctx: dict[str, object] = {
L3696:                "turn_id": turn_id,
L3697:                "sess_key": sess_key,
L3698:                "hot_resumed": is_resumed,
L3699:                "full_prompt": full_prompt,
L3700:                "model": model_id,
L3701:                "model_len": model_len,
L3702:                "effort": effort,
L3703:                "effort_source": effort_source,
L3704:                "prompt": prompt,
L3705:                "cwd": cwd,
L3706:                "tools_count": tools_count,
L3707:                "conversation_id": conversation_id,
L3708:                "tag": (
L3709:                    f"client={self._client_tag()} "
L3710:                    f"ua={(self.headers.get('User-Agent') or '-')[:60]}"
L3711:                ),
L3712:                "stream": bool(req.get("stream")),
L3713:                "images": images,
L3714:                "img_dir": img_dir,
L3715:            }
L3716:            if ctx["stream"]:
L3717:                self._serve_sse(ctx)
L3718:            else:
L3719:                self._serve_json(ctx)
L3720:        finally:
L3721:            if use_cid:
L3722:                with _session_store_lock:
L3723:                    _in_flight_cids.discard(use_cid)
L3724:            _cid_release(use_cid or owned_cid, turn_id)
L3725:            if reserved and budget is not None:
L3726:                budget.release(reserved)
L3727:
L3728:    def _serve_json(self, ctx: dict) -> None:
L3729:        out = self._run_once(
L3730:            ctx, lambda _v: True, lambda _e: True, lambda _r: True, None
L3731:        )
L3732:        if out.get("state") == "client_gone":
L3733:            return
L3734:        err = self._error_body(out)
L3735:        if err is not None:
L3736:            self._send(err["code"], {"error": err})
L3737:            return
L3738:        usage = out.get("usage") or {}
L3739:        message = {"role": "assistant", "content": out["text"]}
L3740:        reasoning = out.get("reasoning") or ""
L3741:        if reasoning:
L3742:            # OpenAI-совместимое поле мышления: Harness читает его из сообщения
L3743:            # ассистента так же, как из дельты потока.
L3744:            message["reasoning_content"] = reasoning
L3745:        payload = {
L3746:            "id": f"chatcmpl-agy-{uuid.uuid4().hex[:12]}",
L3747:            "object": "chat.completion",
L3748:            "created": int(time.time()),
L3749:            "model": ctx["model"],
L3750:            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
L3751:            "usage": self._usage_payload(usage),
L3752:        }
L3753:        if out.get("conversation_id"):
L3754:            payload["conversation_id"] = out["conversation_id"]
L3755:        self._send(200, payload)
L3756:
L3757:    def _serve_sse(self, ctx: dict) -> None:
L3758:        completion_id = f"chatcmpl-agy-{uuid.uuid4().hex[:12]}"
L3759:        created = int(time.time())
L3760:        shown_model = ctx["model"]
L3761:        try:
L3762:            self.send_response(200)
L3763:            self.send_header("Content-Type", "text/event-stream")
L3764:            self.send_header("Cache-Control", "no-cache")
L3765:            self.send_header("X-Accel-Buffering", "no")
L3766:            self.end_headers()
L3767:            self.close_connection = True
L3768:        except (BrokenPipeError, ConnectionResetError, OSError):
L3769:            _log("client gone before headers")
L3770:            return
L3771:
L3772:        def chunk(
L3773:            delta: dict,
L3774:            finish=None,
L3775:            usage: dict | None = None,
L3776:            conversation_id: str = "",
L3777:        ) -> str:
L3778:            body: dict = {
L3779:                "id": completion_id,
L3780:                "object": "chat.completion.chunk",
L3781:                "created": created,
L3782:                "model": shown_model,
L3783:                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
L3784:            }
L3785:            if usage is not None:
L3786:                body["usage"] = usage
L3787:            if conversation_id:
L3788:                body["conversation_id"] = conversation_id
L3789:            return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"
L3790:
L3791:        def on_text(value: str) -> bool:
L3792:            return self._emit(chunk({"content": value}))
L3793:
L3794:        def on_reasoning(value: str) -> bool:
L3795:            # Мышление шага: Harness читает первое непустое из
L3796:            # reasoning_content|reasoning|reasoning_text — отдаём только первое.
L3797:            return self._emit(chunk({"reasoning_content": value}))
L3798:
L3799:        def on_tool_trace(_event: dict) -> bool:
L3800:            # Нативный инструмент agy исполняется внутри CLI и наружу не транслируется:
L3801:            # клиенту нечего добавлять к его же истории вызовов. Трассировка — в stderr.
L3802:            return True
L3803:
L3804:        def keepalive() -> bool:
L3805:            return self._emit(": keepalive\n\n")
L3806:
L3807:        if not self._emit(chunk({"role": "assistant", "content": ""})):
L3808:            return
L3809:        out = self._run_once(ctx, on_text, on_tool_trace, on_reasoning, keepalive)
L3810:        if out.get("state") == "client_gone":
L3811:            _log("client gone mid-stream, child killed")
L3812:            return
L3813:        err = self._error_body(out)
L3814:        if err is None:
L3815:            conv_id = str(out.get("conversation_id") or "")
L3816:            self._emit(chunk({}, "stop", conversation_id=conv_id))
L3817:            # Harness считает tok/s и % контекста только из usage в потоке
L3818:            # (dsh-llm-pi-ai toStreamChunks: usage-chunk -> session usage).
L3819:            # Шлём только при ненулевых токенах, чтобы пустой usage от agy
L3820:            # не превращался в ложные «0 tok/s / 0%».
L3821:            usage = self._usage_payload(out.get("usage") or {})
L3822:            if usage["prompt_tokens"] or usage["completion_tokens"]:
L3823:                self._emit(chunk({}, "stop", usage, conversation_id=conv_id))
L3824:        else:
L3825:            self._emit(
L3826:                "data: " + json.dumps({"error": err}, ensure_ascii=False) + "\n\n"
L3827:            )
L3828:        self._emit("data: [DONE]\n\n")
L3829:
L3830:
L3831:class Server(ThreadingHTTPServer):
L3832:    """HTTP-сервер с семафором числа соединений на уровне приёма."""
L3833:
L3834:    daemon_threads = True
L3835:    request_queue_size = 64
L3836:    allow_reuse_address = True
L3837:
L3838:    def __init__(self, *args: Any, **kwargs: Any):
L3839:        super().__init__(*args, **kwargs)
L3840:        self._conn_sem = threading.BoundedSemaphore(
L3841:            int(FLEET["admission"]["max_http_connections"])
L3842:        )
L3843:
L3844:    def _send_raw_503(self, request: socket.socket) -> None:
L3845:        body = json.dumps(
L3846:            {
L3847:                "error": {
L3848:                    "message": "bridge overloaded: connection limit",
L3849:                    "type": "overloaded",
L3850:                    "code": 503,
L3851:                },
L3852:            }
L3853:        ).encode("utf-8")
L3854:        head = (
L3855:            b"HTTP/1.1 503 Service Unavailable\r\n"
L3856:            b"Content-Type: application/json; charset=utf-8\r\n"
L3857:            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
L3858:            b"Connection: close\r\n\r\n"
L3859:        )
L3860:        request.sendall(head + body)
L3861:
L3862:    def process_request(
L3863:        self, request: socket.socket | tuple[bytes, socket.socket], client_address: Any
L3864:    ) -> None:
L3865:        if not self._conn_sem.acquire(blocking=False):
L3866:            try:
L3867:                peer = f"{client_address[0]}:{client_address[1]}"
L3868:            except (TypeError, IndexError):
L3869:                peer = "unknown"
L3870:            _log(f"reject reason=overloaded model=unknown model_len=0 client={peer}")
L3871:            sock = request if isinstance(request, socket.socket) else request[1]
L3872:            try:
L3873:                self._send_raw_503(sock)
L3874:            except OSError:
L3875:                pass
L3876:            self.shutdown_request(request)
L3877:            return
L3878:        super().process_request(request, client_address)
L3879:
L3880:    def process_request_thread(
L3881:        self, request: socket.socket | tuple[bytes, socket.socket], client_address: Any
L3882:    ) -> None:
L3883:        try:
L3884:            super().process_request_thread(request, client_address)
L3885:        finally:
L3886:            self._conn_sem.release()
L3887:
L3888:
L3889:def _sweep_workspace(cutoff_s: float = 3600.0) -> int:
L3890:    """Удалить каталоги ходов run-*/img-* старше cutoff_s (наследие упавших ходов).
L3891:
L3892:    Симлинки не разыменовываются и не удаляются; каталоги из `_active_img_dirs`
L3893:    (живые ходы) сохраняются при любом возрасте. Возвращает число удалённых img-*.
L3894:    """
L3895:    removed = 0
L3896:    now = time.time()
L3897:    try:
L3898:        entries = list(os.scandir(str(WORKSPACE)))
L3899:    except OSError:
L3900:        return 0
L3901:    for entry in entries:
L3902:        if not entry.name.startswith(("run-", "img-")):
L3903:            continue
L3904:        try:
L3905:            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
L3906:                continue
L3907:            if now - entry.stat(follow_symlinks=False).st_mtime <= cutoff_s:
L3908:                continue
L3909:        except OSError:
L3910:            continue
L3911:        with _active_lock:
L3912:            if os.path.abspath(entry.path) in _active_img_dirs:
L3913:                continue
L3914:        shutil.rmtree(entry.path, ignore_errors=True)
L3915:        if entry.name.startswith("img-"):
L3916:            removed += 1
L3917:    if removed:
L3918:        _log(f"image_sweep_removed count={removed}")
L3919:    return removed
L3920:
L3921:
L3922:def _sweep_loop() -> None:
L3923:    """Периодическая зачистка осиротевших каталогов (daemon-поток)."""
L3924:    while True:
L3925:        time.sleep(SWEEP_INTERVAL_S)
L3926:        try:
L3927:            _ = _sweep_workspace()
L3928:        except Exception as exc:  # noqa: BLE001 — поток зачистки не должен умирать
L3929:            _log(f"sweep_error err={type(exc).__name__}")
L3930:
L3931:
L3932:def main() -> None:
L3933:    global _budget
L3934:    if not AUTH_KEY:
L3935:        sys.stderr.write("AGY_BRIDGE_KEY is required; refusing to start\n")
L3936:        raise SystemExit(1)
L3937:    _budget = _ByteBudget(int(FLEET["admission"]["max_inflight_body_bytes"]))
L3938:    _reset_sqlite_guards_for_tests()  # чистое процессное состояние guardrails на старте
L3939:    WORKSPACE.mkdir(parents=True, exist_ok=True)
L3940:    _ = _sweep_workspace()
L3941:    threading.Thread(target=_sweep_loop, daemon=True).start()
L3942:    # Хеш бинаря agy считается заранее, чтобы первый image-ход не платил за него.
L3943:    threading.Thread(target=_file_sha256, args=(AGY_BIN,), daemon=True).start()
L3944:    _log(f"fleet_sha256={FLEET['sha256']} models={len(FLEET['order'])}")
L3945:    try:
L3946:        _launcher()
L3947:    except LauncherUnavailable:
L3948:        _log(f"launcher_missing path={LAUNCHER} (requests will fail with 503)")
L3949:    signal.signal(signal.SIGTERM, _kill_all)
L3950:    signal.signal(signal.SIGINT, _kill_all)
L3951:    api_key_present = "yes" if AUTH_KEY else "no"
L3952:    server = Server((HOST, PORT), Handler)
L3953:    _log(
L3954:        f"listen {HOST}:{PORT} model={MODEL_ID} max_concurrent={MAX_CONCURRENT} "
L3955:        f"queue_timeout={QUEUE_TIMEOUT_S}s timeout={TIMEOUT_S}s keepalive={KEEPALIVE_S}s "
L3956:        f"api_key={api_key_present}"
L3957:    )
L3958:    print(f"[agy-bridge] listening on http://{HOST}:{PORT}/v1", flush=True)
L3959:    server.serve_forever()
L3960:
L3961:
L3962:if __name__ == "__main__":
L3963:    main()
```

#### `tests/test_agy_bridge_resilience.py` (реестр классов/методов и L5240..L5330 `test_res01`)
```python
L81:class _FakeClock:
L94:class _TickQueue:
L113:class _SpyController:
L173:class _Sock:
L222:class IdleDetectionTests(unittest.TestCase):
L224:    def test_idle_timeout_detected_for_sleeping_process(self) -> None:
L245:    def test_cpu_delta_resets_idle_timer(self) -> None:
L262:    def test_on_activity_resets_idle_timer(self) -> None:
L284:    def test_ps_degraded_fail_closed(self) -> None:
L285:        class _DegradedPs(ProcessWatchdog):
L316:    def test_ps_degraded_stub_metrics_never_count_as_progress(self) -> None:
L329:class ExecuteLoopTests(unittest.TestCase):
L343:    def test_check_throttled_in_execute(self) -> None:
L364:    def test_all_activity_kinds_reach_controller(self) -> None:
L380:    def test_idle_timeout_returns_state_in_execute(self) -> None:
L388:    def test_child_exited_is_not_error(self) -> None:
L400:    def test_absolute_cap_maps_to_timeout(self) -> None:
L420:class KillSwitchTests(unittest.TestCase):
L421:    def test_flag_values(self) -> None:
L438:    def test_idle_timeout_env_validation(self) -> None:
L454:    def test_killswitch_disables_watchdog(self) -> None:
L502:class ErrorContractTests(unittest.TestCase):
L503:    def test_error_body_idle_timeout_http_504(self) -> None:
L523:    def test_sse_error_chunk_idle_timeout(self) -> None:
L544:    def test_json_mode_idle_timeout_is_504(self) -> None:
L557:class KillGroupTests(unittest.TestCase):
L558:    def test_kill_group_cleans_descendants_and_reaps_zombie(self) -> None:
L585:    def test_kill_group_reaps_when_group_already_gone(self) -> None:
L602:    def test_kill_group_escalates_to_sigkill(self) -> None:
L652:class FetchViaPlaywrightHotfixTests(unittest.TestCase):
L662:    def test_fetch_one_timeout_isolated(self) -> None:
L695:    def test_page_close_bounded(self) -> None:
L699:        class _HungPage:
L703:        class _BrokenPage:
L716:    def test_no_bare_page_close_left(self) -> None:
L912:class _DbWriter:
L934:class _Fixture:
L1159:class _Turn:
L1256:class WireParserTests(unittest.TestCase):
L1259:    def test_tc01_parser_positive_field_20_subfield_3(self) -> None:
L1263:    def test_tc02_multibyte_varint_length(self) -> None:
L1271:    def test_tc03_multibyte_tag_and_far_field_skipped(self) -> None:
L1276:    def test_tc04_cyrillic_and_cut_character(self) -> None:
L1288:    def test_tc05_invalid_utf8_replaced_without_exception(self) -> None:
L1293:    def test_tc06_varint_fields_before_field_20_skipped(self) -> None:
L1297:    def test_tc07_fixed64_field_skipped(self) -> None:
L1301:    def test_tc08_fixed32_field_skipped(self) -> None:
L1305:    def test_tc09_foreign_length_delimited_fields_ignored(self) -> None:
L1317:    def test_tc10_unsupported_wire_types_yield_nothing(self) -> None:
L1325:    def test_tc11_truncation_at_every_position_never_raises(self) -> None:
L1332:    def test_tc12_no_field_empty_and_none(self) -> None:
L1347:class SqliteLiveSourceTests(unittest.TestCase):
L1350:    def test_tc20_chunks_arrive_before_status_3(self) -> None:
L1366:    def test_tc21_step_without_thinking_emits_nothing(self) -> None:
L1377:    def test_tc23_faster_writer_than_poll_keeps_final_text(self) -> None:
L1392:    def test_tc24_multistep_order_follows_step_order(self) -> None:
L1407:class DedupTests(unittest.TestCase):
L1410:    def test_tc30_both_sources_same_final_text_emitted_once(self) -> None:
L1429:    def test_tc31_transcript_before_database_gives_no_duplicates(self) -> None:
L1446:    def test_tc32_non_prefix_snapshot_never_repeats_delivered_prefix(self) -> None:
L1465:    def test_tc33_cyrillic_and_ascii_steps_equal_final_text(self) -> None:
L1514:class FailOpenTests(unittest.TestCase):
L1517:    def test_tc40_missing_database_turn_uses_transcript(self) -> None:
L1531:    def test_tc41_closed_wal_database_is_not_a_failure(self) -> None:
L1549:    def test_tc42_exclusive_lock_skips_poll_without_hanging(self) -> None:
L1564:    def test_tc43_unknown_schema_means_no_thinking_and_done_turn(self) -> None:
L1583:    def test_tc44_garbage_file_is_handled_like_unknown_schema(self) -> None:
L1599:class ResumeTests(unittest.TestCase):
L1602:    def test_tc50_resumed_turn_emits_only_new_steps(self) -> None:
L1620:    def test_tc51_new_transcript_record_after_init_is_not_lost(self) -> None:
L1713:class FinalDrainTests(unittest.TestCase):
L1716:    def test_tc60_late_record_reaches_client_before_stop(self) -> None:
L1739:    def test_tc61_json_mode_contains_reasoning_content(self) -> None:
L1778:    def test_tc62_silent_sources_stop_within_one_second_of_eof(self) -> None:
L1796:    def test_tc63_record_after_the_window_is_dropped_without_hanging(self) -> None:
L1812:class DeliveredReasoningTests(unittest.TestCase):
L1825:    def test_tc70_quota_error_after_reasoning_runs_process_once(self) -> None:
L1834:    def test_tc71_hot_session_failure_after_reasoning_has_no_cold_retry(self) -> None:
L1852:    def test_tc72_failure_before_any_delivery_is_still_retried(self) -> None:
L1872:class _HttpBridge:
L1952:class SessionIsolationTests(unittest.TestCase):
L1955:    def test_tc80_background_request_does_not_steal_agentic_session(self) -> None:
L1978:    def test_tc81_background_request_during_agentic_turn_keeps_entry(self) -> None:
L2011:    def test_tc82_plain_dialogs_never_share_or_claim_sessions(self) -> None:
L2041:class SwitchAndObservabilityTests(unittest.TestCase):
L2044:    def test_tc91_disabled_flag_never_opens_a_database(self) -> None:
L2073:    def test_tc92_diagnostic_lines_carry_ids_but_never_thinking_text(self) -> None:
L2134:class _StubTail:
L2178:class BreakerAndBudgetTests(unittest.TestCase):
L2181:    def test_ao01_breaker_fsm_atomic_probe_and_stale_probe(self) -> None:
L2273:    def test_ao02_retry_budget_integer_tenths_and_full_jitter(self) -> None:
L2336:class DrainAndJoinTests(unittest.TestCase):
L2362:    def test_ao03_no_early_exit_without_authoritative_marker(self) -> None:
L2390:    def test_ao03_planner_final_with_two_quiet_selects_holds_full_window(self) -> None:
L2413:    def test_ao03_pending_step_gives_window_complete_and_counts_deadline(self) -> None:
L2423:    def test_ao03_time_budget_and_closed_queue_never_hold_late_reasoning(self) -> None:
L2457:    def test_ao03_hung_select_is_interrupted_before_the_final_join(self) -> None:
L2490:class ConnectionLifecycleTests(unittest.TestCase):
L2493:    def test_ao04_connections_are_paired_and_single_per_turn(self) -> None:
L2509:    def test_ao04_flag_off_and_stop_close_the_connection(self) -> None:
L2527:class PollEnvelopeTests(unittest.TestCase):
L2530:    def test_ao05_select_envelope_never_exceeds_three_plus_two_per_second(self) -> None:
L2553:    def test_ao05_unchanged_snapshot_skips_parser_same_size_does_not(self) -> None:
L2569:    def test_ao05_stop_inside_sixteen_rows_stops_the_parser(self) -> None:
L2591:    def test_ao05_row_limit_blob_limit_and_oversize_log(self) -> None:
L2610:    def test_ao05_flag_file_parsed_once_within_ttl_and_cap_two_mib(self) -> None:
L2646:class _StubRun:
L2665:class ExitLogAndHealthTests(unittest.TestCase):
L2709:    def test_ao06_single_done_line_on_every_exit_branch(self) -> None:
L2764:    def test_ao06_health_has_four_additive_fields_and_keeps_existing_ones(self) -> None:
L2830:class DatabasePathTests(unittest.TestCase):
L2833:    def test_ao07_invalid_cid_never_reaches_connect(self) -> None:
L2873:class ReadOnlyAndAnchorTests(unittest.TestCase):
L2876:    def test_read_only_fallback_retries_connect_and_query_only_errors(self) -> None:
L2912:    def test_read_only_fallback_is_blocked_by_either_sidecar(self) -> None:
L2927:    def test_closed_wal_without_sidecars_opens_and_anchors_resume(self) -> None:
L2959:    def test_ao08_every_connect_is_read_only_uri(self) -> None:
L3002:    def test_ao08_second_request_with_busy_cid_gets_fresh_conversation(self) -> None:
L3052:    def test_ao08_unanchored_resume_turns_sqlite_off_for_the_whole_turn(self) -> None:
L3087:    def test_ao08_stale_generating_row_of_a_failed_turn_is_never_redelivered(
L3113:class KillSwitchTests2(unittest.TestCase):
L3148:    def test_ao09_flag_off_mid_turn_stops_selects_within_1_30_seconds(self) -> None:
L3166:    def test_ao09_env_switch_never_opens_a_connection(self) -> None:
L3195:class CompatCanaryTests(unittest.TestCase):
L3214:    def test_ao10_unknown_binary_is_shadow_and_final_goes_out_whole(self) -> None:
L3230:    def test_ao10_turn_mode_is_fixed_at_start_despite_concurrent_promotion(
L3255:    def test_ao10_mismatch_in_shadow_and_divergence_in_live_demote_compat(self) -> None:
L3290:    def test_ao10_new_binary_identity_and_live_loss_return_to_shadow(self) -> None:
L3322:    def test_ao10_watermark_moves_past_sixteen_finished_steps(self) -> None:
L3337:class ExecuteDrainRetryTests(unittest.TestCase):
L3352:    def test_ao11_reasoning_after_result_error_reaches_out_before_retry_decision(
L3411:class DedupInvariantTests(unittest.TestCase):
L3414:    def test_ao12_snapshot_divergence_freezes_step_and_closes_polling(self) -> None:
L3442:    def test_ao12_transcript_divergence_never_glues_the_tail(self) -> None:
L3459:    def test_ao12_same_size_change_is_divergence_shorter_snapshot_is_ignored(
L3478:    def test_ao12_matching_prefix_final_adds_only_the_tail(self) -> None:
L3490:    def test_seen_cap_evicts_oldest_when_no_finalized_below_watermark(self) -> None:
L3506:    def test_ao12_seen_is_bounded_and_split_utf8_is_emitted_whole(self) -> None:
L3569:class L2HarnessTests(unittest.TestCase):
L3757:    def test_tc93_l2_harness_parallel_turns_resources_and_deadlines(self) -> None:
L3983:class _ImgEnv:
L4082:class _SnapRun:
L4246:class ImageValidationTests(unittest.TestCase):
L4249:    def test_img01_four_mimes_one_three_sixteen_accepted_and_staged(self) -> None:
L4286:    def test_img02_sixteen_mixed_mimes_keep_global_order(self) -> None:
L4307:    def test_img03_seventeen_images_rejected_before_any_decode(self) -> None:
L4323:    def test_img04_single_image_boundary_for_every_base64_padding(self) -> None:
L4341:    def test_img05_single_image_one_byte_over_limit_rejected_before_total(self) -> None:
L4350:    def test_img06_total_limit_boundary(self) -> None:
L4361:    def test_img07_http_body_limit_boundary(self) -> None:
L4392:    def test_img08_image_only_user_message_keeps_marker_and_attachment(self) -> None:
L4403:    def test_img09_text_only_history_has_zero_image_overhead(self) -> None:
L4441:    def test_img10_signature_check_is_not_pixel_decoding(self) -> None:
L4453:    def test_f003_count_and_base64_length_checked_before_b64decode(self) -> None:
L4475:    def test_f006_data_url_is_case_insensitive_and_log_values_are_sanitized(
L4500:    def test_f006_sha_cache_keyed_by_identity_and_hash_runs_outside_cache_lock(
L4509:            class _ProbeHash:
L4545:class ImageHistoryTests(unittest.TestCase):
L4548:    def test_hist01_cold_images_then_text_resends_full_history(self) -> None:
L4587:    def test_hist02_rejected_history_without_assistant_keeps_all_images(self) -> None:
L4612:    def test_hist03_hot_text_turn_after_images_has_no_new_attachments(self) -> None:
L4654:    def test_hist04_hot_new_image_keeps_global_index_and_correct_bytes(self) -> None:
L4682:    def test_hist05_hot_failure_falls_back_to_cold_with_all_files(self) -> None:
L4710:    def test_hist06_no_second_spawn_after_content_was_delivered(self) -> None:
L4726:    def test_hist07_explicit_conversation_id_and_automatic_hot_prompt_differ(
L4756:    def test_hist08_plain_and_background_requests_do_not_touch_agentic_session(
L4786:    def test_hist09_parallel_requests_with_other_cwd_and_model_stay_separate(
L4838:    def test_hist10_cwd_with_spaces_and_unicode_is_not_replaced_by_image_dir(
L4876:class ImageLifecycleTests(unittest.TestCase):
L4884:    def test_life01_dir_removed_on_every_terminal_path(self) -> None:
L4940:    def test_life02_retry_and_hot_cold_fallback_reuse_one_directory(self) -> None:
L4976:    def test_life03_spool_failure_returns_500_and_leaves_no_directory(self) -> None:
L5021:    def test_life04_parallel_turns_never_touch_each_others_directory(self) -> None:
L5080:    def test_life05_sweep_removes_only_stale_orphans(self) -> None:
L5140:class ImageLogTests(unittest.TestCase):
L5143:    def test_log01_every_reason_is_verbatim_and_masking_stays_strict(self) -> None:
L5173:    def test_log01_http_proof_and_effort_rejects_are_visible(self) -> None:
L5210:    def test_log02_auth_key_and_image_payload_never_reach_the_log(self) -> None:
L5240:            )
L5241:            self.assertEqual(len(env.records()), 1)
L5242:
L5243:
L5244:class ImageResourceTests(unittest.TestCase):
L5245:    """REQ-009/F-002/F-005: слоты, FD, повторная проверка после очереди, отказ без деградации."""
L5246:
L5247:    def test_res01_concurrent_turns_bounded_by_slots_without_fd_or_dir_leaks(
L5248:        self,
L5249:    ) -> None:
L5250:        with _ImgEnv() as env:
L5251:            env.fx.patch("_slots", threading.BoundedSemaphore(2))
L5252:            env.write_scen([{"sleep": 0.5}])
L5253:            bridge = _HttpBridge()
L5254:            codes: list[int] = []
L5255:            sampled: list[int] = []
L5256:            stop = threading.Event()
L5257:
L5258:            def sampler() -> None:
L5259:                while not stop.is_set():
L5260:                    sampled.append(len(env.img_dirs()))
L5261:                    time.sleep(0.02)
L5262:
L5263:            def worker(n: int) -> None:
L5264:                parts = [_png_part("r%da" % n), _png_part("r%db" % n)]
L5265:                codes.append(
L5266:                    bridge.post(_img_body([_img_msg(*parts, text="req-%d" % n)]))[0]
L5267:                )
L5268:
L5269:            watcher = threading.Thread(target=sampler)
L5270:            threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
L5271:            fd_before = _open_fds()
L5272:            try:
L5273:                watcher.start()
L5274:                for thread in threads:
L5275:                    thread.start()
L5276:                for thread in threads:
L5277:                    thread.join(120)
L5278:            finally:
L5279:                stop.set()
L5280:                watcher.join(10)
L5281:                bridge.close()
L5282:            self.assertEqual(codes, [200] * 8)
L5283:            self.assertLessEqual(
L5284:                max(sampled), 2
L5285:            )  # каталоги только у ходов, занявших слот
L5286:            recs = env.records()
L5287:            self.assertEqual(len(recs), 8)
L5288:            events = sorted(
L5289:                [(_float(r["t0"]), 1) for r in recs]
L5290:                + [(_float(r["t1"]), -1) for r in recs]
L5291:            )
L5292:            running = peak = 0
L5293:            for _t, delta in events:
L5294:                running += delta
L5295:                peak = max(peak, running)
L5296:            self.assertLessEqual(peak, 2)
L5297:            for rec in recs:
L5298:                found = re.search(r"req-(\d+)", _str(rec["prompt"]))
L5299:                self.assertIsNotNone(found)
L5300:                number = int(cast("re.Match[str]", found).group(1))
L5301:                expected = {
L5302:                    1: ("image/png", _img_raw("image/png", "r%da" % number)),
L5303:                    2: ("image/png", _img_raw("image/png", "r%db" % number)),
L5304:                }
L5305:                _expect_files(self, rec, expected)
L5306:            self.assertEqual(len({_add_dir_of(r) for r in recs}), 8)
L5307:            self.assertEqual(env.img_dirs(), [])
L5308:            self.assertEqual(env.active_dirs(), set())
L5309:            self.assertEqual(env.free_slots(), 2)
L5310:            deadline = time.monotonic() + 5
L5311:            while _open_fds() > fd_before and time.monotonic() < deadline:
L5312:                time.sleep(0.05)
L5313:            self.assertLessEqual(_open_fds(), fd_before)
L5314:
L5315:    def test_res02_disabled_or_unproven_image_path_leaves_text_untouched(self) -> None:
L5316:        with _ImgEnv() as env:
L5317:            bridge = _HttpBridge()
L5318:            try:
L5319:                env.flag(False)
L5320:                code, body = bridge.post(_img_body([_img_msg(_png_part("a"))]))
L5321:                self.assertEqual(
L5322:                    (code, _err(body)["type"]), (400, "image_input_not_supported")
L5323:                )
L5324:                self.assertEqual((env.records(), env.img_dirs()), ([], []))
L5325:                health = bridge.get("/health")[1]
L5326:                self.assertEqual(
L5327:                    (health["images"], health["image_input_mode"]), (False, "disabled")
L5328:                )
L5329:                text_code, _b = bridge.post(
L5330:                    _img_body([_txt_msg("user", "просто текст")])
L5367:    def test_res03_at_most_two_attempts_and_retry_budget_is_respected(self) -> None:
L5383:    def test_f002_flag_and_proof_are_rechecked_after_waiting_for_a_slot(self) -> None:
L5439:    def test_f001_flag_defaults_false_and_follows_env_then_strict_config(self) -> None:
L5617:class AcceptanceOracleTests(unittest.TestCase):
L5620:    def test_ao01_target_models_accept_images_unsupported_and_flag_off_reject(
L5682:    def test_ao02_mixed_formats_sixteen_accepted_and_seventeen_rejected_over_http(
L5706:    def test_ao03_every_reject_reason_is_400_before_spool_and_spawn(self) -> None:
L5743:    def test_ao04_global_numbering_for_cold_hot_and_fallback_prompts(self) -> None:
L5779:    def test_ao05_cwd_session_key_and_add_dir_argv(self) -> None:
L5803:    def test_ao06_modes_during_turn_and_cleanup_after_success_and_error(self) -> None:
L5826:    def test_ao07_reject_lines_follow_the_strict_template(self) -> None:
L5847:    def test_ao08_directory_is_registered_before_mkdir_and_survives_sweep(self) -> None:
L5887:    def test_ao09_delivered_reasoning_is_never_retried_with_images(self) -> None:
L5928:    def test_ao10_repo_fleet_and_server_form_one_consistent_pair(self) -> None:
```


---
PANEL-NONCE: cc8a078b61cb4c4f
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: cc8a078b61cb4c4f» и «ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689».

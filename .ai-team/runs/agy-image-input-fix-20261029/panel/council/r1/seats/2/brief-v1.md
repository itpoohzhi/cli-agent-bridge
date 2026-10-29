You are Judge Seat #2 (realist, slot=gemini-4-argon-high, family=Google, transport=agy) of the Code Council Gate (stage=council, round=r1) for run agy-image-input-fix-20261029.
PANEL-NONCE: 17aa3c514267dcb8
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689

# Бриф судьи Совета Тимлидов (Council Gate — Финальная приёмка кода, Раунд R1, Место #2 — realist)

⚠️ **КРИТИЧЕСКАЯ ИНСТРУКЦИЯ (LEAF JUDGE / AGENT_SPAWN_DEPTH=1):**
- Вы — конечный судья панели `teamlead-gate` (`mode: code`, `stage: council`, `round: r1`, `seat: 2`).
- **НЕ запускайте** никаких субагентов, контуров `cel`, внешних скриптов или команд модификации.
- **НЕ вызывайте** инструменты чтения/поиска без необходимости — **весь проверяемый пакет (`teamlead/package.md`, включая полный `candidate.diff`, манифесты, `coder.json`, результаты чистой комнаты `VER-001..VER-010`, `verification-traceability.md`, `reverse-spec.md`, вердикт `ARCH_PANEL` с таблицей `F-001..F-010`) уже полностью встроен в этот бриф ниже**. Вы можете сразу вынести вердикт по тексту этого брифа.
- **Первыми двумя строками вашего ответа ОБЯЗАНЫ быть дословно (без отступов, без markdown-блоков вокруг них):**
PANEL-NONCE: 17aa3c514267dcb8
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689
- **Строка `ОБЩИЙ ВЕРДИКТ:` (и `Вердикт места:`) ОБЯЗАНА принимать строго одно из канонических значений верификатора `verify_panel_proof.py` (`PoL-V12`):** `ACCEPT`, `PASS`, `NEEDS_WORK` или `RED_FLAG` (слова `REVISE` или `REJECT` верификатором `PoL-V12` запрещены!).
- Весь ответ — строго на **русском языке**.

---

## 1. Входной контракт места

- **run_id**: `agy-image-input-fix-20261029`
- **mode**: `code`
- **stage**: `council`
- **round**: `r1`
- **seat**: `2`
- **slot_id**: `gemini-4-argon-high`
- **family**: `Google`
- **transport**: `agy`
- **Шляпа (hat)**: Реалист (оценивает эксплуатационную надёжность, корректность слотов/спула, совместимость с DSH и agy 1.4.9)
- **seed_recheck_duty**: `нет`
- **PANEL-NONCE**: `17aa3c514267dcb8`
- **ARTIFACT-SHA256**: `8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689`
- **package_path**: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/teamlead/package.md`
- **seed_input**: `agy-image-input-fix-20261029:council:r1:8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689:2f71fff0c5b829b58581f463a400533781de9735e0670d3f26eee212d80c4d86`
- **seed_hex**: `173448a0264daa2efbfed7dc061ba27e7facf454aaed45293b2f03328c167bfb`
- **ranked_order**: `["muse-wonder-full-1.0", "gpt-6.1-sol-high", "gemini-4-argon-high", "claude-sonnet-5-5-high"]`
- **Правило жеребьёвки `select_round_seats.py` (`pol-manifest/2`, автоматически проверяется `verify_panel_proof.py` `PoL-V13`)**: `seed_hex = sha256(seed_input)`, ранг каждого слота вычисляется по формуле `sha256(f"{seed_hex.lower()}#{slot_id}")` (`muse-wonder-full-1.0=37b06a5edf6a50c0, gpt-6.1-sol-high=bdc5376d469a0572, gemini-4-argon-high=e7217972185152b2, claude-sonnet-5-5-high=ec7c42d813a3b705`), после исключения семейства автора кода `Anthropic` (`receipts/coder.json`).

Если `seed_recheck_duty: да`, укажите `seed_recheck: PASS (sha256(seed_input)==seed_hex, PoL-V13 selection contract verified)`. Если `seed_recheck_duty: нет`, укажите `seed_recheck: N/A (seed_recheck_duty=нет)`.

---

## 2. Обязательные 14 подкатегорий `mode=code` (все 14 должны быть в `[SUB COVERAGE]`)

1. `SUB-CORRECT-01` — Корректность бизнес-логики и соответствие `REQ-001..REQ-010`, `AC-001..AC-010`, `AD-001..AD-006`, `F-001..F-010`.
2. `SUB-EDGE-02` — Граничные случаи (0 картинок -> fast path `[]`, 16 vs 17 картинок, 20 МБ лимит до `b64decode`, регистронезависимый `data:IMAGE/PNG;BASE64,`, несовпадение magic bytes и MIME, пустой payload, кириллица и пробелы в путях).
3. `SUB-ARCH-03` — Архитектурная целостность (передача `--add-dir <img_dir>` без мутации `cwd` и `sess_key = (model_id, cwd, effort)`, глобальная 1-based нумерация `[image 1]..[image K]`, фильтрация `delta_images` в `_get_resumed_turn_prompt`).
4. `SUB-API-04` — Контракт HTTP API (`/v1/chat/completions`, `/v1/models`, `/health`, точные коды ошибок 400/413/500 и поля `type`/`code`).
5. `SUB-ERR-05` — Обработка ошибок (`ImageReject` -> HTTP 400 до `mkdir`/`spawn`, `ImageSpoolError` -> HTTP 500 `image_spool_error` с очисткой частичной папки и `0` `spawn`, `image_cleanup_error` в `finally`).
6. `SUB-SEC-06` — Безопасность (отказ от `http://`/`https://`/`file://`, права `0700` на `img_dir` и `0600` `O_CREAT|O_EXCL` на файлы, пропуск симлинков в `_sweep_workspace`, санитизация `\r\n\t` в `model`, отсутствие base64/путей в ответах и логах).
7. `SUB-CONC-07` — Конкурентность и блокировки (отдельный `_image_flag_lock`, чтение чанков SHA-256 вне `_sha_cache_lock`, регистрация `_active_img_dirs` под `_active_lock` до `os.mkdir`, повторная проверка флага и proof после `_acquire_slot()` по `F-002`).
8. `SUB-RES-08` — Управление ресурсами (контекстный менеджер `with os.fdopen(fd, "wb")`, немедленная очистка `img["data"] = b""` после записи по `F-004`, гарантированный `shutil.rmtree` во внешнем `finally:` после `run.close()`, `_sweep_workspace` старше 3600 с).
9. `SUB-PERF-09` — Производительность (0 системных вызовов на текстовых запросах, кэш флага `1.0 s`, кэш SHA-256 бинаря по `(st_dev, st_ino, st_mtime_ns, st_size)`).
10. `SUB-TEST-10` — Полнота и качество тестов (146 тестов и 142 подтеста в `tests/test_agy_bridge_resilience.py`, все 40 обязательных ID `VER-007` + `F-001..F-007`, 0 удалённых строк в `VER-006`).
11. `SUB-MAINT-11` — Читаемость, типизация (`basedpyright` 0 ошибок в `server.py`, 0 новых ошибок и 0 новых предупреждений в `VER-004`), форматирование (`ruff check` и `ruff format --check` 0 ошибок в `VER-001`/`VER-002`).
12. `SUB-SIMP-12` — Отсутствие оверинжиниринга и мёртвого кода.
13. `SUB-OBS-13` — Наблюдаемость и диагностика (15 событий в `_LOG_EVENT_NAMES`, динамическое поле `images` в `/health` и `/v1/models`).
14. `SUB-DEPS-14` — Зависимости (0 новых внешних пакетов, только Python stdlib + `core`, `VER-009` `PASS`).

---

## 3. Строгий шаблон ответа судьи

Первые две строки ответа ОБЯЗАНЫ быть:
```
PANEL-NONCE: 17aa3c514267dcb8
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689
```

Далее строго по разделам:
```
=== КАРТОЧКА СУДЬИ ===
Место: #2 | Слот: gemini-4-argon-high | Семейство: Google | Транспорт: agy
Режим: code | Раунд: r1 | Шляпа: Реалист (оценивает эксплуатационную надёжность, корректность слотов/спула, совместимость с DSH и agy 1.4.9)
seed_recheck_duty: нет
seed_recheck: <PASS / N/A>
package_path: /Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/teamlead/package.md
Вердикт места: ACCEPT | NEEDS_WORK | RED_FLAG
Блокеров: <число> | Существенных: <число> | Замечаний: <число>

[SUB COVERAGE]
| Подкатегория | Статус (PASS/CONCERN/BLOCKER) | Доказательство (файл:строки / тест / VER-ID) | Комментарий |
|---|---|---|---|
| SUB-CORRECT-01 | ... | ... | ... |
| SUB-EDGE-02 | ... | ... | ... |
| SUB-ARCH-03 | ... | ... | ... |
| SUB-API-04 | ... | ... | ... |
| SUB-ERR-05 | ... | ... | ... |
| SUB-SEC-06 | ... | ... | ... |
| SUB-CONC-07 | ... | ... | ... |
| SUB-RES-08 | ... | ... | ... |
| SUB-PERF-09 | ... | ... | ... |
| SUB-TEST-10 | ... | ... | ... |
| SUB-MAINT-11 | ... | ... | ... |
| SUB-SIMP-12 | ... | ... | ... |
| SUB-OBS-13 | ... | ... | ... |
| SUB-DEPS-14 | ... | ... | ... |

[FINDINGS]
(Если замечаний/блокеров нет — напишите `Замечаний класса BLOCKER и MAJOR не обнаружено.` Если есть — перечислите с якорями файл:строка и классом BLOCKER-SAFETY / BLOCKER-DESIGN / MAJOR / MINOR.)

[ОБОСНОВАНИЕ ВЕРДИКТА]
(Краткое резюме проверки реализации AD-001..AD-006, F-001..F-010, результатов чистой комнаты VER-001..VER-009 и соответствия ТЗ.)

FINDINGS_COMPLETE: YES
ОБЩИЙ ВЕРДИКТ: ACCEPT
```
*(или `NEEDS_WORK` / `RED_FLAG`, если найдены незакрытые блокеры; только одно из значений `ACCEPT`, `PASS`, `NEEDS_WORK`, `RED_FLAG`).*

---

## 4. Полный проверяемый пакет (`teamlead/package.md`, `ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689`)

# Пакет финальной приёмки Совета Тимлидов (`Council Package — agy-image-input-fix`)

## 1. Архитектурный вердикт и реестр `F-001..F-010`

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


## 2. Манифесты кандидата и окружения

### `teamlead/candidate-manifest.json`
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

### `teamlead/environment-manifest.json`
```json
{
  "schema": "environment-manifest/v1",
  "run_id": "agy-image-input-fix-20261029",
  "os": "macOS arm64",
  "python3": "Python 3.14.7",
  "sys_python3": "Python 3.9.6 (/usr/bin/python3)",
  "ruff": "ruff 0.17.3 (uvx ruff@0.17.3)",
  "basedpyright": "basedpyright 1.40.2 (uvx basedpyright@1.40.2)",
  "pytest": "pytest 9.0.3 (uvx --from pytest==9.0.3 pytest)",
  "agy_cli": "agy 1.4.9 (~/.local/bin/agy.real, sha256=35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423)"
}
```


## 3. Отчёт Coder (`coder.json`)
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


## 4. Трассируемость верификации (`verification-traceability.md`)

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


## 5. Обратная спецификация (`reverse-spec.md`)

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


## 6. Доказательства выполнения в чистой комнате L2 (`execution-evidence.md` + `evidence-manifest.sha256`)

### `teamlead/evidence-manifest.sha256`
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


## 7. Полный diff кандидата (`candidate.diff`)
```diff
diff --git a/bridges/agy-bridge/fleet.json b/bridges/agy-bridge/fleet.json
index 36085fe..4439f43 100644
--- a/bridges/agy-bridge/fleet.json
+++ b/bridges/agy-bridge/fleet.json
@@ -8,22 +8,26 @@
   },
   "default_model": "gemini-3.8-flash",
   "technical_ref": {
-    "agy_version": "1.3.1",
-    "agy_binary_path": "~/.local/bin/agy",
+    "agy_version": "1.4.9",
+    "agy_binary_path": "~/.local/bin/agy.real",
     "launcher_path": "~/.config/agy-launch/agy-cli.sh",
     "launcher_egress": "xray HTTP 127.0.0.1:10815 (резерв hy2 :10811; прямой вызов запрещён — гео РФ)",
     "models_source": "agy models (live, 1.3.1)",
     "invocation": "printf NDJSON | launcher --input-format stream-json --output-format stream-json --dangerously-skip-permissions --model <BASE_MODEL_ID> --effort <EFFORT> --print-timeout=0",
     "note": "effort-суффикс (-high/-medium/-low) в fleet.json БОЛЬШЕ НЕ часть id: id = база (`gemini-3.8-flash`), уровень — отдельная ось `--effort`, значение берётся из `efforts` модели. Мост передаёт `--effort` ВСЕГДА (в т.ч. при пустом reasoning_effort — `default_effort`): база без effort у agy отвергается (`--model \"gemini-3.8-flash\" requires --effort (available: low, medium, high)`).",
-    "effort_ladders": "agy models 1.3.1: gemini-4-argon = low|medium|high; gemini-3.8/3.7/3.6-flash = low|medium|high; gemini-3.1-pro = low|high; gpt-oss-120b = medium (только)"
+    "effort_ladders": "agy models 1.3.1: gemini-4-argon = low|medium|high; gemini-3.8/3.7/3.6-flash = low|medium|high; gemini-3.1-pro = low|high; gpt-oss-120b = medium (только)",
+    "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423"
   },
   "image_limits": {
-    "max_images": 0,
-    "max_image_bytes": 1,
-    "max_total_image_bytes": 1,
+    "max_images": 16,
+    "max_image_bytes": 20971520,
+    "max_total_image_bytes": 20971520,
     "max_body_bytes": 33554432,
     "types": [
-      "image/png"
+      "image/png",
+      "image/jpeg",
+      "image/gif",
+      "image/webp"
     ]
   },
   "admission": {
@@ -51,13 +55,30 @@
       "context_window": 1048576,
       "max_tokens": 65536,
       "input": [
-        "text"
+        "text",
+        "image"
       ],
       "images": {
-        "cli_registry": "explicit_unsupported",
-        "status": "unsupported",
-        "method": null,
-        "proof": "agy 1.3.1 stream-json принимает только текстовые блоки контента; image_url отвергается: error: stream input content block type \"image_url\" is not supported (only \"text\") — проверено 2026-10-07"
+        "cli_registry": "implicit_supported",
+        "status": "confirmed",
+        "method": "workspace-read",
+        "verified_at": "2026-10-29",
+        "proof": {
+          "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423",
+          "impl_version": 1,
+          "formats": [
+            "image/png",
+            "image/jpeg",
+            "image/gif",
+            "image/webp"
+          ],
+          "efforts_proven": [
+            "low",
+            "medium",
+            "high"
+          ],
+          "command": "agy.real -p 'Read img-1.png' --add-dir <img_dir> --model <model> --effort <effort>"
+        }
       }
     },
     {
@@ -72,13 +93,30 @@
       "context_window": 1048576,
       "max_tokens": 65536,
       "input": [
-        "text"
+        "text",
+        "image"
       ],
       "images": {
-        "cli_registry": "explicit_unsupported",
-        "status": "unsupported",
-        "method": null,
-        "proof": "agy 1.3.1 stream-json принимает только текстовые блоки контента; image_url отвергается: error: stream input content block type \"image_url\" is not supported (only \"text\") — проверено 2026-10-07"
+        "cli_registry": "implicit_supported",
+        "status": "confirmed",
+        "method": "workspace-read",
+        "verified_at": "2026-10-29",
+        "proof": {
+          "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423",
+          "impl_version": 1,
+          "formats": [
+            "image/png",
+            "image/jpeg",
+            "image/gif",
+            "image/webp"
+          ],
+          "efforts_proven": [
+            "low",
+            "medium",
+            "high"
+          ],
+          "command": "agy.real -p 'Read img-1.png' --add-dir <img_dir> --model <model> --effort <effort>"
+        }
       }
     },
     {
diff --git a/bridges/agy-bridge/server.py b/bridges/agy-bridge/server.py
index d41f514..f5d7405 100644
--- a/bridges/agy-bridge/server.py
+++ b/bridges/agy-bridge/server.py
@@ -47,6 +47,14 @@ agy отвергает базу без effort — `--model "gemini-3.8-flash" re
 `SQLITE_REASONING_ENABLED` в `dynamic_config.json` (по умолчанию выключен) и аварийный
 выключатель `AGY_SQLITE_REASONING_ENABLED=0`.
 
+Изображения (метод `workspace-read`): `image_url` в NDJSON парсер agy не принимает, поэтому
+проверенные data-URL (PNG/JPEG/GIF/WebP) кладутся файлами в `WORKSPACE/img-<uuid>` на время
+хода, каталог отдаётся CLI через `--add-dir`, а в промпте они идут как `[image N]` и блок
+`[attachments]` с абсолютными путями (модель читает их нативным view_file). Вход выключен по
+умолчанию: флаг `IMAGE_INPUT_ENABLED` в `dynamic_config.json` (env `AGY_IMAGE_INPUT_ENABLED`
+решает сразу) и proof модели в fleet.json (sha256 бинаря agy, версия метода, форматы, effort).
+Проверка идёт до слота и spawn; запись на диск — только после захвата слота, удаление — в finally.
+
 Секреты с диска не читаются: ключ авторизации берётся только из окружения
 AGY_BRIDGE_KEY (его подкладывает start.sh из ~/.dsh/.env); в окружение дочернего
 процесса ключ моста не передаётся. Прокси-переменные выставляет сам лончер.
@@ -54,6 +62,7 @@ AGY_BRIDGE_KEY (его подкладывает start.sh из ~/.dsh/.env); в 
 
 from __future__ import annotations
 
+import base64
 import hashlib
 import json
 import os
@@ -182,7 +191,26 @@ RETRY_PAUSE_CAP_S = 2.0
 EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
 CLI_EFFORT_LEVELS = ("low", "medium", "high")
 IMAGE_STATUSES = ("unsupported", "unverified", "probe", "confirmed")
-IMPLEMENTED_METHODS: dict = {}
+# Доставка изображений агенту: проверенные файлы в WORKSPACE/img-<uuid>, каталог отдаётся
+# через `--add-dir`, модель читает их нативным view_file. Прямой image_url в NDJSON
+# парсер agy не принимает (см. fleet.json, proof 1.3.1).
+IMPLEMENTED_METHODS = {"workspace-read": 1}
+METHOD_IMPL_VERSION = 1
+IMAGE_FLAG_NAME = "IMAGE_INPUT_ENABLED"
+IMAGE_PROBE = os.environ.get("AGY_IMAGE_PROBE", "").strip().lower() in (
+    "1",
+    "true",
+    "yes",
+)
+_EXT = {
+    "image/png": "png",
+    "image/jpeg": "jpg",
+    "image/gif": "gif",
+    "image/webp": "webp",
+}
+SHA_CHUNK_BYTES = 1024 * 1024
+DYNAMIC_CONFIG_MAX_BYTES = 65536
+SWEEP_INTERVAL_S = 600.0
 
 CWD_MAX_LEN = 4096
 
@@ -226,6 +254,15 @@ _sqlite_open_connections: int = 0
 _sqlite_max_open_connections: int = 0
 _rng: Callable[[], float] = random.random
 
+# Изображения: хеш бинаря agy (кэш по идентичности файла), отдельный от SQLite-флага
+# кэш IMAGE_INPUT_ENABLED и реестр активных каталогов img-* (под _active_lock).
+_sha_cache_lock = threading.Lock()
+_sha_compute_lock = threading.Lock()
+_sha_cache: dict[str, tuple[tuple[int, int, int, int], str]] = {}
+_image_flag_lock = threading.Lock()
+_image_flag_cache: tuple[float, bool] = (0.0, False)
+_active_img_dirs: set[str] = set()
+
 # Токеноподобные последовательности в логах: сам ключ моста и длинные hex/base64.
 _SECRET = re.compile(r"[A-Za-z0-9_\-]{24,}")
 _NOISE = re.compile(
@@ -324,17 +361,26 @@ def _build_catalog(data: Any) -> dict:
             and status != "unsupported"
         ):
             raise FleetViolation("status_inconsistent", mid)
-        # agy-мост изображений не принимает вовсе: max_images = 0, поэтому любая
-        # модель обязана быть text-only. Расширение — сначала proof-метод.
+        # unsupported/unverified — text-only. confirmed/probe допустимы только с
+        # реализованным методом доставки и входом image; proof проверяется на каждом
+        # image-запросе (`_image_proof_reason`), а не при старте.
         if status in ("unsupported", "unverified"):
             if images.get("method") is not None or input_types != ["text"]:
                 raise FleetViolation("status_inconsistent", mid)
-        if status == "confirmed":
-            raise FleetViolation("method_not_implemented", mid)
-        if status == "probe":
+        if status == "probe" and not IMAGE_PROBE:
             raise FleetViolation("probe_flag_missing", mid)
         method = images.get("method")
-        if method is not None and method not in IMPLEMENTED_METHODS:
+        proof = cast(object, images.get("proof"))
+        if status in ("confirmed", "probe"):
+            if method not in IMPLEMENTED_METHODS:
+                raise FleetViolation("method_not_implemented", mid)
+            if "image" not in input_types or "text" not in input_types:
+                raise FleetViolation("status_inconsistent", mid)
+            if status == "confirmed" and not isinstance(proof, dict):
+                raise FleetViolation("proof_invalid", mid)
+            if limits["max_images"] <= 0 or not limits["types"]:
+                raise FleetViolation("limits_invalid", mid)
+        elif method is not None and method not in IMPLEMENTED_METHODS:
             raise FleetViolation("method_not_implemented", mid)
         models[mid] = {
             "id": mid,
@@ -348,7 +394,7 @@ def _build_catalog(data: Any) -> dict:
                 "status": str(status),
                 "cli_registry": str(images.get("cli_registry") or ""),
                 "method": method,
-                "proof": images.get("proof"),
+                "proof": proof,
             },
         }
         order.append(mid)
@@ -418,6 +464,8 @@ except FleetViolation as _violation:
     raise SystemExit(1)
 
 MODEL_ID = ENV_MODEL or FLEET["default_model"]
+FLEET_MODELS = cast("dict[str, dict[str, object]]", cast(object, FLEET["models"]))
+IMAGE_LIMITS = cast("dict[str, object]", cast(object, FLEET["image_limits"]))
 
 
 def _log(msg: str) -> None:
@@ -450,10 +498,29 @@ def _is_watchdog_enabled() -> bool:
     return raw not in ("0", "false", "no", "off")
 
 
-# Имена диагностических событий источника мышления длиннее 24 символов, но секретами
-# не являются: без исключения маска скрыла бы их в логах.
+# Имена диагностических событий и причин отказа (мышление, изображения) длиннее 24
+# символов, но секретами не являются: без исключения маска скрыла бы их в логах.
+# Только точное совпадение токена целиком, не префикс и не подстрока.
 _LOG_EVENT_NAMES = frozenset(
-    {"sqlite_snapshot_divergence", "sqlite_transcript_divergence"}
+    {
+        "sqlite_snapshot_divergence",
+        "sqlite_transcript_divergence",
+        "image_input_not_supported",
+        "unsupported_reasoning_effort",
+        "invalid_reasoning_effort",
+        "unsupported_image_type",
+        "invalid_image_content",
+        "invalid_image_base64",
+        "image_url_not_allowed",
+        "image_type_mismatch",
+        "image_proof_invalid",
+        "images_too_large",
+        "image_too_large",
+        "too_many_images",
+        "image_spool_error",
+        "image_cleanup_error",
+        "image_sweep_removed",
+    }
 )
 
 
@@ -519,16 +586,24 @@ def _auth_ok(handler: BaseHTTPRequestHandler) -> bool:
     return handler.headers.get("x-api-key", "") == AUTH_KEY or hdr.strip() == AUTH_KEY
 
 
-def _flatten_content(content: Any) -> str:
+def _flatten_content(content: Any, img_counter: list[int] | None = None) -> str:
+    """Контент сообщения в текст; с `img_counter` image-части дают маркеры `[image N]`."""
     if content is None:
         return ""
     if isinstance(content, str):
         return content
     if isinstance(content, list):
-        parts = []
+        parts: list[str] = []
         for item in content:
             if isinstance(item, str):
                 parts.append(item)
+            elif (
+                img_counter is not None
+                and isinstance(item, dict)
+                and item.get("type") == "image_url"
+            ):
+                img_counter[0] += 1
+                parts.append("[image %d]" % img_counter[0])
             elif isinstance(item, dict) and "text" in item:
                 parts.append(str(item["text"]))
         return "\n".join(p for p in parts if p)
@@ -539,30 +614,403 @@ def _tool_choice_none(tool_choice: Any) -> bool:
     return isinstance(tool_choice, str) and tool_choice.strip().lower() == "none"
 
 
-def _has_image_parts(messages: Any) -> bool:
-    """Есть ли в истории запроса image-части (мост их не поддерживает)."""
-    if not isinstance(messages, list):
+@final
+class ImageReject(ValueError):
+    """Отказ по изображениям: `reason` — деталь для журнала, `code` — тип HTTP 400."""
+
+    def __init__(self, reason: str, code: str = "image_input_not_supported") -> None:
+        super().__init__(reason)
+        self.reason = reason
+        self.code = code
+
+
+@final
+class ImageSpoolError(RuntimeError):
+    """Проверенные изображения не удалось материализовать на диск."""
+
+
+_B64_WS = re.compile(r"[ \t\r\n\f\v]")
+_STATUS_REASONS = frozenset(
+    {"status_unsupported", "status_probe", "model_unknown", "input_not_image"}
+)
+
+
+def _safe_log_value(value: object) -> str:
+    """Значение из запроса для строки журнала: управляющие символы -> `_`."""
+    return re.sub(r"[\x00-\x1f\x7f]", "_", str(value))
+
+
+def _file_sha256(path: object) -> str:
+    """SHA-256 файла чанками по 1 MiB; '' — файл недоступен или изменился при чтении.
+
+    Кэш по пути с идентичностью (st_dev, st_ino, st_mtime_ns, st_size): неизменный
+    бинарь (~190 MiB) хешируется один раз. Хеширование идёт вне `_sha_cache_lock`,
+    под отдельным замком единственного вычислителя.
+    """
+    resolved = os.path.expanduser(str(path))
+
+    def identity() -> tuple[int, int, int, int]:
+        info = os.stat(resolved)
+        return (info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size)
+
+    try:
+        key = identity()
+        with _sha_cache_lock:
+            cached = _sha_cache.get(resolved)
+        if cached is not None and cached[0] == key:
+            return cached[1]
+        with _sha_compute_lock:
+            with _sha_cache_lock:
+                cached = _sha_cache.get(resolved)
+            if cached is not None and cached[0] == key:
+                return cached[1]
+            digest = hashlib.sha256()
+            with open(resolved, "rb") as handle:
+                for chunk in iter(lambda: handle.read(SHA_CHUNK_BYTES), b""):
+                    digest.update(chunk)
+            if identity() != key:
+                return ""
+            hexdigest = digest.hexdigest()
+            with _sha_cache_lock:
+                _sha_cache[resolved] = (key, hexdigest)
+            return hexdigest
+    except OSError:
+        return ""
+
+
+def _read_image_flag() -> bool:
+    """IMAGE_INPUT_ENABLED из dynamic_config.json: строго `true`, иначе False."""
+    try:
+        path = DYNAMIC_CONFIG_PATH
+        if not path.is_file() or path.stat().st_size > DYNAMIC_CONFIG_MAX_BYTES:
+            return False
+        data = cast(object, json.loads(path.read_text(encoding="utf-8")))
+    except (OSError, ValueError):
         return False
-    for msg in messages:
+    if not isinstance(data, dict):
+        return False
+    return cast("dict[str, object]", data).get(IMAGE_FLAG_NAME) is True
+
+
+def _is_image_input_enabled() -> bool:
+    """Fail-closed выключатель image-входа (по умолчанию False).
+
+    Env `AGY_IMAGE_INPUT_ENABLED` (непустой) решает сразу: 0|false|no|off -> False,
+    1|true|yes|on -> True, любое иное значение -> False. Без env — флаг
+    `IMAGE_INPUT_ENABLED` в dynamic_config.json с кэшем TTL 1.0 с; не-boolean,
+    битый или отсутствующий файл дают False. Не зависит от SQLITE_REASONING_ENABLED.
+    """
+    global _image_flag_cache
+    env = os.environ.get("AGY_IMAGE_INPUT_ENABLED", "").strip().lower()
+    if env:
+        return env in ("1", "true", "yes", "on")
+    now = time.monotonic()
+    with _image_flag_lock:
+        checked_at, cached = _image_flag_cache
+        if checked_at > 0.0 and now - checked_at < FLAG_TTL_S:
+            return cached
+    value = _read_image_flag()
+    with _image_flag_lock:
+        _image_flag_cache = (now, value)
+    return value
+
+
+def _image_proof_reason(model_id: str, effort: str | None = None) -> str | None:
+    """None — image-вход модели доказан; иначе короткая причина (без секретов)."""
+    model = FLEET_MODELS.get(model_id)
+    if model is None:
+        return "model_unknown"
+    raw_images = model.get("images")
+    images = (
+        cast("dict[str, object]", raw_images) if isinstance(raw_images, dict) else {}
+    )
+    raw_input = model.get("input")
+    if not isinstance(raw_input, list) or "image" not in cast(
+        "list[object]", raw_input
+    ):
+        return "input_not_image"
+    status = images.get("status")
+    if status == "probe":
+        if not IMAGE_PROBE:
+            return "status_probe"
+    elif status != "confirmed":
+        return "status_unsupported"
+    method = images.get("method")
+    if not isinstance(method, str) or method not in IMPLEMENTED_METHODS:
+        return "method_not_implemented"
+    proof_raw = images.get("proof")
+    if not isinstance(proof_raw, dict):
+        return "proof_missing"
+    proof = cast("dict[str, object]", proof_raw)
+    if proof.get("impl_version") != IMPLEMENTED_METHODS[method]:
+        return "impl_version_mismatch"
+    formats_raw = proof.get("formats")
+    types_raw = IMAGE_LIMITS.get("types")
+    types = cast("list[object]", types_raw) if isinstance(types_raw, list) else []
+    if not isinstance(formats_raw, list) or not formats_raw:
+        return "formats_mismatch"
+    if not {str(t).lower() for t in types} <= {
+        str(f).lower() for f in cast("list[object]", formats_raw)
+    }:
+        return "formats_mismatch"
+    efforts_raw = proof.get("efforts_proven")
+    if not isinstance(efforts_raw, list):
+        return "efforts_missing"
+    if effort is not None and effort not in cast("list[object]", efforts_raw):
+        return "effort_not_proven"
+    expected = proof.get("agy_binary_sha256")
+    if not isinstance(expected, str) or len(expected) != 64:
+        return "binary_sha_missing"
+    actual = _file_sha256(AGY_BIN)
+    if not actual or actual != expected.lower():
+        return "binary_sha_mismatch"
+    return None
+
+
+def _model_supports_images(model_id: str) -> bool:
+    return _is_image_input_enabled() and _image_proof_reason(model_id) is None
+
+
+def _image_gate(model_id: str, effort: str | None) -> ImageReject | None:
+    """Флаг и proof для image-запроса: None — можно, иначе отказ (без I/O с телом)."""
+    if not _is_image_input_enabled():
+        return ImageReject("image_input_disabled")
+    reason = _image_proof_reason(model_id, effort)
+    if reason is None:
+        return None
+    if reason in _STATUS_REASONS:
+        return ImageReject(reason)
+    if reason == "effort_not_proven":
+        return ImageReject(reason, "unsupported_reasoning_effort")
+    _log("image_proof_invalid model=%s reason=%s" % (_safe_log_value(model_id), reason))
+    return ImageReject("image_proof_invalid")
+
+
+def _collect_image_parts(
+    messages: object,
+) -> list[tuple[int, int, dict[str, object]]]:
+    """Все image_url-части истории: (индекс сообщения с 0, сквозной номер с 1, часть)."""
+    found: list[tuple[int, int, dict[str, object]]] = []
+    if not isinstance(messages, list):
+        return found
+    number = 0
+    for msg_index, msg in enumerate(cast("list[object]", messages)):
         if not isinstance(msg, dict):
             continue
-        content = msg.get("content")
+        content = cast("dict[str, object]", msg).get("content")
         if not isinstance(content, list):
             continue
-        for item in content:
-            if isinstance(item, dict) and item.get("type") == "image_url":
-                return True
-    return False
+        for item in cast("list[object]", content):
+            if isinstance(item, dict):
+                part = cast("dict[str, object]", item)
+                if part.get("type") == "image_url":
+                    number += 1
+                    found.append((msg_index, number, part))
+    return found
+
+
+def _sniff_image_type(raw: bytes) -> str | None:
+    """MIME по сигнатуре (не декодирование пикселей); None — формат неизвестен."""
+    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
+        return "image/png"
+    if raw.startswith(b"\xff\xd8\xff"):
+        return "image/jpeg"
+    if raw.startswith((b"GIF87a", b"GIF89a")):
+        return "image/gif"
+    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
+        return "image/webp"
+    return None
+
+
+def _limit(name: str, default: int) -> int:
+    value = IMAGE_LIMITS.get(name, default)
+    return value if isinstance(value, int) and not isinstance(value, bool) else default
+
 
+def _new_img_dir() -> Path:
+    """Путь (без обращений к диску) каталога изображений одного хода."""
+    return Path(os.path.abspath(str(WORKSPACE))) / ("img-" + uuid.uuid4().hex)
 
-def _render_message(msg: Any, counter: list) -> str:
+
+def _collect_images(
+    messages: object, model_id: str, effort: str | None
+) -> list[dict[str, object]]:
+    """Проверить image-части всей истории; вернуть записи для prompt и spool.
+
+    Нет image-частей — `[]` сразу, без stat/хеша/флага. Порядок отказов: флаг и
+    proof -> число частей -> по каждой части: роль, форма, `data:` URL, MIME,
+    оценка размера base64 ДО decode, строгий base64, сигнатура, лимиты. Ничего не
+    пишется на диск и не запускается. Декодированные байты не удерживаются
+    (`data` пуст): в spool они пересоздаются из base64 уже после захвата слота.
+    """
+    parts = _collect_image_parts(messages)
+    if not parts:
+        return []
+    gate = _image_gate(model_id, effort)
+    if gate is not None:
+        raise gate
+    max_images = _limit("max_images", 16)
+    if max_images <= 0:
+        raise ImageReject("images_disabled")
+    if len(parts) > max_images:
+        raise ImageReject("too_many_images", "too_many_images")
+    max_bytes = _limit("max_image_bytes", 0)
+    max_total = _limit("max_total_image_bytes", 0)
+    allowed_raw = IMAGE_LIMITS.get("types")
+    allowed = {
+        str(t).lower()
+        for t in (
+            cast("list[object]", allowed_raw) if isinstance(allowed_raw, list) else []
+        )
+    }
+    msgs = cast("list[object]", messages)
+    img_dir = _new_img_dir()
+    entries: list[dict[str, object]] = []
+    total = 0
+    for msg_index, number, part in parts:
+        msg = cast("dict[str, object]", msgs[msg_index])
+        if msg.get("role") != "user":
+            raise ImageReject("non_user_image", "invalid_image_content")
+        ref = part.get("image_url")
+        url = (
+            cast("dict[str, object]", ref).get("url") if isinstance(ref, dict) else None
+        )
+        if not isinstance(url, str) or not url:
+            raise ImageReject("invalid_image_url", "invalid_image_content")
+        if url[:5].lower() != "data:":
+            raise ImageReject("remote_or_file_url", "image_url_not_allowed")
+        comma = url.find(",")
+        if comma < 0:
+            raise ImageReject("malformed_data_url", "invalid_image_content")
+        header = [h.strip().lower() for h in url[5:comma].split(";")]
+        mime = header[0]
+        if not mime or "base64" not in header[1:]:
+            raise ImageReject("malformed_data_url", "invalid_image_content")
+        if mime not in allowed or mime not in _EXT:
+            raise ImageReject("unsupported_mime", "unsupported_image_type")
+        payload = url[comma + 1 :]
+        if _B64_WS.search(payload) is not None:
+            payload = _B64_WS.sub("", payload)
+        if not payload:
+            raise ImageReject("empty_payload", "invalid_image_base64")
+        pad = 2 if payload.endswith("==") else (1 if payload.endswith("=") else 0)
+        if (len(payload) * 3) // 4 - pad > max_bytes:
+            raise ImageReject("image_too_large", "image_too_large")
+        try:
+            raw = base64.b64decode(payload, validate=True)
+        except Exception:
+            raise ImageReject("invalid_base64", "invalid_image_base64") from None
+        if not raw:
+            raise ImageReject("empty_image", "invalid_image_content")
+        actual = _sniff_image_type(raw)
+        if actual is None:
+            raise ImageReject("unknown_magic", "unsupported_image_type")
+        if actual != mime:
+            raise ImageReject("mime_mismatch", "image_type_mismatch")
+        size = len(raw)
+        del raw
+        if size > max_bytes:
+            raise ImageReject("image_too_large", "image_too_large")
+        if total + size > max_total:
+            raise ImageReject("images_too_large", "images_too_large")
+        total += size
+        ext = _EXT[mime]
+        entries.append(
+            {
+                "index": number,
+                "msg_index": msg_index,
+                "mime": mime,
+                "ext": ext,
+                "size": size,
+                "data": b"",
+                "b64": payload,
+                "path": img_dir / ("img-%d.%s" % (number, ext)),
+            }
+        )
+    return entries
+
+
+def _stage_images(img_dir: Path, images: list[dict[str, object]]) -> None:
+    """Материализовать проверенные изображения: каталог 0700, файлы 0600, O_EXCL.
+
+    Байты берутся из base64 здесь, после захвата слота, и сразу сбрасываются.
+    Любая ошибка ввода-вывода удаляет частичный каталог и даёт ImageSpoolError.
+    """
+    try:
+        os.makedirs(str(img_dir.parent), exist_ok=True)
+        os.mkdir(str(img_dir), 0o700)
+        for img in images:
+            held = img.get("data")
+            data = (
+                bytes(cast(bytes, held))
+                if held
+                else base64.b64decode(cast(str, img["b64"]), validate=True)
+            )
+            if len(data) != cast(int, img["size"]):
+                raise ValueError("size mismatch")
+            fd = os.open(str(img["path"]), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
+            try:
+                handle = os.fdopen(fd, "wb")
+            except BaseException:
+                os.close(fd)
+                raise
+            with handle:
+                _ = handle.write(data)
+            img["data"] = b""
+            _ = img.pop("b64", None)
+    except (OSError, ValueError) as exc:
+        shutil.rmtree(str(img_dir), ignore_errors=True)
+        raise ImageSpoolError(type(exc).__name__) from None
+
+
+def _cleanup_img_dir(img_dir: Path) -> None:
+    """Удалить каталог хода и снять его с реестра активных (ошибка видна в журнале)."""
+    try:
+        shutil.rmtree(str(img_dir))
+    except FileNotFoundError:
+        pass
+    except OSError as exc:
+        _log("image_cleanup_error err=%s" % type(exc).__name__)
+        shutil.rmtree(str(img_dir), ignore_errors=True)
+    finally:
+        with _active_lock:
+            _active_img_dirs.discard(str(img_dir))
+
+
+def _attachments_block(images: list[dict[str, object]]) -> str:
+    lines = [
+        "[attachments]",
+        "The user attached %d image file(s), accessible in the workspace directory"
+        % len(images)
+        + " via --add-dir:",
+    ]
+    for img in images:
+        lines.append(
+            "- [image %d] %s (%s, %d bytes)"
+            % (
+                cast(int, img["index"]),
+                str(img["path"]),
+                cast(str, img["mime"]),
+                cast(int, img["size"]),
+            )
+        )
+    lines.append(
+        "Read every attached image file listed above using your file/image inspection"
+        + " tool (e.g. view_file) before answering."
+    )
+    return "\n".join(lines)
+
+
+def _render_message(
+    msg: Any, counter: list, img_counter: list[int] | None = None
+) -> str:
     """Сообщение OpenAI в текстовый блок промпта (роли не теряются)."""
     if not isinstance(msg, dict):
         return ""
     role = str(msg.get("role") or "user")
     name = msg.get("name")
     label = role if not name else "%s(%s)" % (role, name)
-    body = _flatten_content(msg.get("content"))
+    body = _flatten_content(msg.get("content"), img_counter)
     lines = []
     calls = msg.get("tool_calls")
     if isinstance(calls, list):
@@ -591,25 +1039,41 @@ def _render_message(msg: Any, counter: list) -> str:
     return "### %d. %s\n%s" % (counter[0], label, prepared)
 
 
-def _messages_to_prompt(messages: list) -> str:
+def _messages_to_prompt(
+    messages: list,
+    images: list[dict[str, object]] | None = None,
+    img_start: int = 0,
+) -> str:
     """Собрать единый текстовый промпт хода.
 
     Секции протокола инструментов нет намеренно: agy исполняет СВОИ нативные
     инструменты, а не инструменты DSH (см. README, раздел «Инструменты»).
+    Image-части получают сквозные маркеры `[image N]` (нумерация с `img_start + 1`),
+    а `images` описываются блоком `[attachments]` с абсолютными путями файлов.
     """
     counter = [0]
-    blocks = []
+    img_counter = [img_start]
+    blocks: list[str] = []
     for msg in messages:
-        rendered = _render_message(msg, counter)
+        rendered = _render_message(msg, counter, img_counter)
         if rendered:
             blocks.append(rendered)
+    if images:
+        blocks.append(_attachments_block(images))
     text = "\n\n".join(blocks).strip()
     if not text:
         text = "Reply with exactly: PONG"
     return text
 
 
-def _get_resumed_turn_prompt(messages: list) -> str:
+def _get_resumed_turn_prompt(
+    messages: list, images: list[dict[str, object]] | None = None
+) -> str:
+    """Промпт хода продолжения: сообщения после последнего assistant.
+
+    Маркеры сохраняют сквозные номера всей истории; `[attachments]` — только для
+    изображений новых сообщений. Без assistant в истории — вся история целиком.
+    """
     last_asst = -1
     for i in range(len(messages) - 1, -1, -1):
         if isinstance(messages[i], dict) and messages[i].get("role") == "assistant":
@@ -617,10 +1081,18 @@ def _get_resumed_turn_prompt(messages: list) -> str:
             break
     if last_asst >= 0 and last_asst + 1 < len(messages):
         new_msgs = messages[last_asst + 1 :]
-        prompt = _messages_to_prompt(new_msgs)
+        skipped = len(
+            _collect_image_parts(cast("list[object]", messages[: last_asst + 1]))
+        )
+        delta = [
+            img
+            for img in (images or [])
+            if cast(int, img.get("msg_index", 0)) > last_asst
+        ]
+        prompt = _messages_to_prompt(new_msgs, delta, skipped)
         if prompt:
             return prompt
-    return _messages_to_prompt(messages)
+    return _messages_to_prompt(messages, images)
 
 
 def _session_claim(sess_key: tuple, turn_id: str = "") -> str:
@@ -762,6 +1234,11 @@ def _reset_sqlite_guards_for_tests() -> None:
     global _compat_ident, _compat_state, _flag_value, _flag_key, _flag_checked_at
     global _sqlite_divergence_count, _sqlite_drain_deadline_count
     global _sqlite_open_connections, _sqlite_max_open_connections, _rng
+    global _image_flag_cache
+    with _image_flag_lock:
+        _image_flag_cache = (0.0, False)
+    with _sha_cache_lock:
+        _sha_cache.clear()
     with _sqlite_guard_lock:
         _breaker_state = "CLOSED"
         _breaker_failures = 0
@@ -2032,6 +2509,7 @@ class Run:
         tag: str,
         conversation_id: str = "",
         turn_id: str = "",
+        add_dir: Path | None = None,
     ):
         launcher = _launcher()
         WORKSPACE.mkdir(parents=True, exist_ok=True)
@@ -2051,6 +2529,9 @@ class Run:
             effort,
             "--print-timeout=" + str(PRINT_TIMEOUT),
         ]
+        # Изображения хода: каталог файлов отдельным аргументом, cwd не подменяется.
+        if add_dir is not None:
+            cmd += ["--add-dir", str(add_dir)]
         # RESUME: продолжение треда — отдельным флагом, промпт всё равно через stdin.
         self.run_cid = conversation_id or ""
         self.turn_id: str = turn_id or uuid.uuid4().hex
@@ -2372,6 +2853,23 @@ class _ByteBudget:
             self.used = max(0, self.used - amount)
 
 
+def _terminal_state(name: str, err: str = "") -> dict[str, object]:
+    """Итог хода без запуска agy (отказ до spawn)."""
+    return {
+        "state": name,
+        "rc": 1,
+        "text": "",
+        "usage": {},
+        "result": {},
+        "err": err,
+        "tool_calls": [],
+        "tool_events": 0,
+        "conversation_id": "",
+        "num_turns": None,
+        "duration_s": None,
+    }
+
+
 class Handler(BaseHTTPRequestHandler):
     protocol_version = "HTTP/1.1"
     server_version = "agy-bridge/1.0"
@@ -2412,8 +2910,8 @@ class Handler(BaseHTTPRequestHandler):
         self, reason: str, model: str = "unknown", model_len: int = 0
     ) -> None:
         _log(
-            f"reject reason={reason} model={model} model_len={model_len} "
-            f"client={self._client_tag()}"
+            f"reject reason={reason} model={_safe_log_value(model)} "
+            f"model_len={model_len} client={self._client_tag()}"
         )
 
     def _reject(
@@ -2649,6 +3147,10 @@ class Handler(BaseHTTPRequestHandler):
             return early
         t0 = time.monotonic()
         out: dict = {}
+        typed_ctx = cast("dict[str, object]", ctx)
+        images = cast("list[dict[str, object]]", typed_ctx.get("images") or [])
+        img_dir = cast("Path | None", typed_ctx.get("img_dir")) if images else None
+        img_registered = False
         try:
             try:
                 _launcher()
@@ -2671,6 +3173,38 @@ class Handler(BaseHTTPRequestHandler):
                     cast(str, ctx["model"]), unavailable, t_enter, cast(str, ctx["tag"])
                 )
                 return unavailable
+            if images and img_dir is not None:
+                # Флаг и proof могли смениться, пока ход ждал слот: повторная проверка
+                # до mkdir и spawn.
+                gate = _image_gate(cast(str, model), cast(str, effort))
+                if gate is not None:
+                    self._log_reject(
+                        gate.code, cast(str, model), cast(int, ctx["model_len"])
+                    )
+                    rejected = _terminal_state("image_reject", gate.code)
+                    self._log_done(
+                        cast(str, ctx["model"]),
+                        rejected,
+                        t_enter,
+                        cast(str, ctx["tag"]),
+                    )
+                    return rejected
+                # Реестр активных каталогов ПЕРЕД mkdir: sweep не тронет живой ход.
+                with _active_lock:
+                    _active_img_dirs.add(str(img_dir))
+                img_registered = True
+                try:
+                    _stage_images(img_dir, images)
+                except ImageSpoolError as exc:
+                    _log(
+                        "image_spool_error model=%s err=%s"
+                        % (_safe_log_value(cast(str, model)), exc)
+                    )
+                    failed = _terminal_state("image_spool_error", str(exc))
+                    self._log_done(
+                        cast(str, ctx["model"]), failed, t_enter, cast(str, ctx["tag"])
+                    )
+                    return failed
             _retry_credit()
             for attempt in (1, 2):
                 _log(
@@ -2689,6 +3223,7 @@ class Handler(BaseHTTPRequestHandler):
                         tag,
                         conversation_id=ctx.get("conversation_id") or "",
                         turn_id=str(ctx.get("turn_id") or ""),
+                        add_dir=img_dir if images else None,
                     )
                 except LauncherUnavailable:
                     self._reject(
@@ -2789,6 +3324,9 @@ class Handler(BaseHTTPRequestHandler):
                     else 0.0
                 )
         finally:
+            # Каталог изображений живёт весь ход (все попытки) и уходит до слота.
+            if img_registered and img_dir is not None:
+                _cleanup_img_dir(img_dir)
             _slots.release()
         self._log_done(
             cast(str, ctx["model"]),
@@ -2845,6 +3383,15 @@ class Handler(BaseHTTPRequestHandler):
             }
         if st == "client_gone":
             return {"message": "client gone", "type": "client_gone", "code": 499}
+        if st == "image_reject":
+            code = cast(str, out["err"]) or "image_input_not_supported"
+            return {"message": f"image rejected: {code}", "type": code, "code": 400}
+        if st == "image_spool_error":
+            return {
+                "message": "image spool failed",
+                "type": "image_spool_error",
+                "code": 500,
+            }
         if st == "pump_error":
             return {
                 "message": "bridge reader failed",
@@ -2883,7 +3430,10 @@ class Handler(BaseHTTPRequestHandler):
                 "tool_emulation": False,
                 "tool_translation": False,
                 "native_tools": True,
-                "images": False,
+                "images": any(_model_supports_images(mid) for mid in FLEET_MODELS),
+                "image_input_mode": (
+                    "enabled" if _is_image_input_enabled() else "disabled"
+                ),
                 "uptime_s": int(time.time() - _started),
             }
             health.update(_sqlite_health_fields())
@@ -2904,8 +3454,11 @@ class Handler(BaseHTTPRequestHandler):
         if path in ("/v1/models", "/models"):
             data = []
             order = [MODEL_ID] + [mid for mid in FLEET["order"] if mid != MODEL_ID]
+            image_flags: list[bool] = []
             for mid in order:
                 model = FLEET["models"][mid]
+                supports = _model_supports_images(cast(str, mid))
+                image_flags.append(supports)
                 data.append(
                     {
                         "id": mid,
@@ -2913,9 +3466,12 @@ class Handler(BaseHTTPRequestHandler):
                         "owned_by": "antigravity",
                         "created": 0,
                         "context_length": model["context_window"],
+                        "images": supports,
                     }
                 )
-            self._send(200, {"object": "list", "data": data})
+            self._send(
+                200, {"object": "list", "data": data, "images": any(image_flags)}
+            )
             return
         self._send(
             404,
@@ -3069,15 +3625,21 @@ class Handler(BaseHTTPRequestHandler):
                 if isinstance(messages_raw, list)
                 else []
             )
-            if _has_image_parts(messages):
+            try:
+                images = _collect_images(
+                    messages, cast(str, model_id), cast(str, effort)
+                )
+            except ImageReject as rejected:
+                _log("image_reject detail=%s" % rejected.reason)
                 self._reject(
                     400,
-                    "image_input_not_supported",
-                    "image rejected: image_input_not_supported",
+                    rejected.code,
+                    f"image rejected: {rejected.code}",
                     model_id,
                     model_len,
                 )
                 return
+            img_dir = cast(Path, images[0]["path"]).parent if images else None
             try:
                 _launcher()
             except LauncherUnavailable:
@@ -3096,7 +3658,7 @@ class Handler(BaseHTTPRequestHandler):
                 else []
             )
             tools_count = 0 if _tool_choice_none(req.get("tool_choice")) else len(tools)
-            full_prompt = _messages_to_prompt(messages)
+            full_prompt = _messages_to_prompt(messages, images)
             extra = (
                 req.get("extra_body") if isinstance(req.get("extra_body"), dict) else {}
             )
@@ -3129,7 +3691,7 @@ class Handler(BaseHTTPRequestHandler):
                 if use_cid:
                     conversation_id = use_cid
                     is_resumed = True
-                    prompt = _get_resumed_turn_prompt(messages)
+                    prompt = _get_resumed_turn_prompt(messages, images)
             ctx: dict[str, object] = {
                 "turn_id": turn_id,
                 "sess_key": sess_key,
@@ -3148,6 +3710,8 @@ class Handler(BaseHTTPRequestHandler):
                     f"ua={(self.headers.get('User-Agent') or '-')[:60]}"
                 ),
                 "stream": bool(req.get("stream")),
+                "images": images,
+                "img_dir": img_dir,
             }
             if ctx["stream"]:
                 self._serve_sse(ctx)
@@ -3322,15 +3886,47 @@ class Server(ThreadingHTTPServer):
             self._conn_sem.release()
 
 
-def _sweep_workspace() -> None:
-    """Удалить временные каталоги ходов старше часа (наследие упавших ходов)."""
-    cutoff = time.time() - 3600
-    for path in WORKSPACE.glob("run-*"):
+def _sweep_workspace(cutoff_s: float = 3600.0) -> int:
+    """Удалить каталоги ходов run-*/img-* старше cutoff_s (наследие упавших ходов).
+
+    Симлинки не разыменовываются и не удаляются; каталоги из `_active_img_dirs`
+    (живые ходы) сохраняются при любом возрасте. Возвращает число удалённых img-*.
+    """
+    removed = 0
+    now = time.time()
+    try:
+        entries = list(os.scandir(str(WORKSPACE)))
+    except OSError:
+        return 0
+    for entry in entries:
+        if not entry.name.startswith(("run-", "img-")):
+            continue
         try:
-            if path.is_dir() and path.stat().st_mtime < cutoff:
-                shutil.rmtree(str(path), ignore_errors=True)
+            if entry.is_symlink() or not entry.is_dir(follow_symlinks=False):
+                continue
+            if now - entry.stat(follow_symlinks=False).st_mtime <= cutoff_s:
+                continue
         except OSError:
-            pass
+            continue
+        with _active_lock:
+            if os.path.abspath(entry.path) in _active_img_dirs:
+                continue
+        shutil.rmtree(entry.path, ignore_errors=True)
+        if entry.name.startswith("img-"):
+            removed += 1
+    if removed:
+        _log(f"image_sweep_removed count={removed}")
+    return removed
+
+
+def _sweep_loop() -> None:
+    """Периодическая зачистка осиротевших каталогов (daemon-поток)."""
+    while True:
+        time.sleep(SWEEP_INTERVAL_S)
+        try:
+            _ = _sweep_workspace()
+        except Exception as exc:  # noqa: BLE001 — поток зачистки не должен умирать
+            _log(f"sweep_error err={type(exc).__name__}")
 
 
 def main() -> None:
@@ -3341,7 +3937,10 @@ def main() -> None:
     _budget = _ByteBudget(int(FLEET["admission"]["max_inflight_body_bytes"]))
     _reset_sqlite_guards_for_tests()  # чистое процессное состояние guardrails на старте
     WORKSPACE.mkdir(parents=True, exist_ok=True)
-    _sweep_workspace()
+    _ = _sweep_workspace()
+    threading.Thread(target=_sweep_loop, daemon=True).start()
+    # Хеш бинаря agy считается заранее, чтобы первый image-ход не платил за него.
+    threading.Thread(target=_file_sha256, args=(AGY_BIN,), daemon=True).start()
     _log(f"fleet_sha256={FLEET['sha256']} models={len(FLEET['order'])}")
     try:
         _launcher()
diff --git a/tests/test_agy_bridge_resilience.py b/tests/test_agy_bridge_resilience.py
index c018e30..929414a 100644
--- a/tests/test_agy_bridge_resilience.py
+++ b/tests/test_agy_bridge_resilience.py
@@ -14,6 +14,7 @@ kill-switch, контракт ошибки `idle_timeout` (HTTP 504 / SSE), за
 from __future__ import annotations
 
 import asyncio
+import base64
 import contextlib
 import hashlib
 import http.client
@@ -3799,5 +3800,2209 @@ class L2HarnessTests(unittest.TestCase):
             self.assertEqual(health[0]["sqlite_divergence_count"], 0)
 
 
+# ---- Image input (workspace-read): AD-001..AD-006, F-001..F-010 ---------------------
+
+_IMG_TARGETS = ("gemini-4-argon", "gemini-3.8-flash")
+_IMG_MIMES = ("image/png", "image/jpeg", "image/gif", "image/webp")
+_IMG_MAGIC: dict[str, bytes] = {
+    "image/png": b"\x89PNG\r\n\x1a\n",
+    "image/jpeg": b"\xff\xd8\xff\xe0",
+    "image/gif": b"GIF89a",
+    "image/webp": b"RIFF\x00\x00\x00\x00WEBP",
+}
+_IMG_EXT = {
+    "image/png": "png",
+    "image/jpeg": "jpg",
+    "image/gif": "gif",
+    "image/webp": "webp",
+}
+_IMG_CAP = 20971520
+_FAKE_IMG_SOURCE = """
+import hashlib, json, os, stat, sys, time, uuid
+
+argv = sys.argv[1:]
+scen = json.load(open(os.environ["FAKE_IMG_SCEN"]))
+raw_in = sys.stdin.read()
+try:
+    prompt = json.loads(raw_in)["message"]["content"][0]["text"]
+except Exception:
+    prompt = ""
+idx = 0
+while True:
+    try:
+        os.mkdir(os.path.join(scen["marks"], str(idx)))
+        break
+    except FileExistsError:
+        idx += 1
+rec = {"idx": idx, "argv": argv, "cwd": os.getcwd(), "prompt": prompt,
+       "t0": time.time(), "pid": os.getpid()}
+if "--add-dir" in argv:
+    d = argv[argv.index("--add-dir") + 1]
+    rec["dir"] = d
+    rec["dir_mode"] = stat.S_IMODE(os.stat(d).st_mode)
+    files = {}
+    for name in sorted(os.listdir(d)):
+        p = os.path.join(d, name)
+        with open(p, "rb") as fh:
+            data = fh.read()
+        files[name] = {"sha": hashlib.sha256(data).hexdigest(),
+                       "mode": stat.S_IMODE(os.stat(p).st_mode), "size": len(data)}
+    rec["files"] = files
+
+
+def save():
+    path = os.path.join(scen["recs"], "%d.json" % idx)
+    with open(path + ".tmp", "w") as fh:
+        json.dump(rec, fh)
+    os.replace(path + ".tmp", path)
+
+
+def emit(obj):
+    sys.stdout.write(json.dumps(obj) + "\\n")
+    sys.stdout.flush()
+
+
+spawns = scen.get("spawns") or [{}]
+beh = spawns[min(idx, len(spawns) - 1)]
+cid = argv[argv.index("--conversation") + 1] if "--conversation" in argv else beh.get("cid") or str(uuid.uuid4())
+save()
+emit({"event": "init", "conversation_id": cid, "init": {"tools": [], "permission_mode": "x"}})
+time.sleep(beh.get("sleep", 0))
+mode = beh.get("mode", "ok")
+if mode in ("ok", "text_then_error"):
+    emit({"event": "step_update", "step_update": {"step_type": "agent_response", "step_index": 9, "text_delta": "ответ"}})
+status = "ERROR" if mode in ("error", "text_then_error") else "OK"
+emit({"event": "result", "result": {"response": "" if status == "ERROR" else "ответ", "status": status,
+      "error": "boom" if status == "ERROR" else "", "conversation_id": cid,
+      "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}})
+rec["t1"] = time.time()
+save()
+sys.exit(1 if status == "ERROR" else 0)
+"""
+
+
+def _img_raw(mime: str, tag: str = "x", size: int = 0) -> bytes:
+    body = _IMG_MAGIC[mime] + tag.encode("ascii")
+    return body.ljust(size, b"\x00") if size else body
+
+
+def _img_url(mime: str, raw: bytes) -> str:
+    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode("ascii"))
+
+
+def _img_part(mime: str, raw: bytes) -> dict[str, object]:
+    return {"type": "image_url", "image_url": {"url": _img_url(mime, raw)}}
+
+
+def _img_msg(
+    *parts: dict[str, object], text: str = "", role: str = "user"
+) -> dict[str, object]:
+    content: list[dict[str, object]] = []
+    if text:
+        content.append({"type": "text", "text": text})
+    content.extend(parts)
+    return {"role": role, "content": content}
+
+
+def _txt_msg(role: str, text: str) -> dict[str, object]:
+    return {"role": role, "content": text}
+
+
+def _png_part(tag: str) -> dict[str, object]:
+    return _img_part("image/png", _img_raw("image/png", tag))
+
+
+def _collect(
+    messages: list[dict[str, object]],
+    model: str = "gemini-4-argon",
+    effort: str = "low",
+) -> list[dict[str, object]]:
+    return cast(
+        "list[dict[str, object]]",
+        _bfn("_collect_images")(messages, model, effort),
+    )
+
+
+def _reject_of(call: Callable[[], object]) -> tuple[str, str]:
+    """(reason, code) исключения ImageReject; иначе тест падает."""
+    reject_cls = cast("type[Exception]", _bval("ImageReject"))
+    try:
+        _ = call()
+    except reject_cls as exc:
+        return _str(_oval(exc, "reason")), _str(_oval(exc, "code"))
+    raise AssertionError("ImageReject expected")
+
+
+def _proof_of(model_id: str) -> dict[str, object]:
+    models = _dict(_bval("FLEET_MODELS"))
+    images = _dict(_dict(models[model_id])["images"])
+    return _dict(images["proof"])
+
+
+def _err(body: dict[str, object]) -> dict[str, object]:
+    return _dict(body["error"])
+
+
+def _img_body(
+    messages: list[dict[str, object]],
+    tools: bool = False,
+    cwd: str = "",
+    conv: str = "",
+    model: str = "gemini-4-argon",
+    stream: bool = False,
+) -> dict[str, object]:
+    body: dict[str, object] = {"model": model, "messages": messages, "stream": stream}
+    if tools:
+        body["tools"] = [
+            {"type": "function", "function": {"name": "x", "parameters": {}}}
+        ]
+    extra: dict[str, object] = {}
+    if cwd:
+        extra["cwd"] = cwd
+    if conv:
+        extra["conversation_id"] = conv
+    if extra:
+        body["extra_body"] = extra
+    return body
+
+
+def _small_limits(**limits: int) -> contextlib.AbstractContextManager[object]:
+    """Временно уменьшить image_limits (границы те же, память теста — нет)."""
+    return cast(
+        "contextlib.AbstractContextManager[object]",
+        mock.patch.dict(
+            _dict(_bval("IMAGE_LIMITS")), cast("dict[str, object]", limits)
+        ),
+    )
+
+
+def _restore_key(target: dict[str, object], key: str, value: object) -> None:
+    target[key] = value
+
+
+class _ImgEnv:
+    """Фикстура image-входа: флаг включён, proof подогнан под фиксчер-бинарь, фейковый agy."""
+
+    fx: _Fixture
+    fake: Path
+    marks: Path
+    recs: Path
+    scen: Path
+
+    def __init__(self) -> None:
+        self.fx = _Fixture()
+        self.fake = self.fx.tmp / "fake-img-agy.py"
+        self.marks = self.fx.tmp / "marks"
+        self.recs = self.fx.tmp / "recs"
+        self.scen = self.fx.tmp / "img-scenario.json"
+
+    def __enter__(self) -> _ImgEnv:
+        _ = self.fx.__enter__()
+        fx = self.fx
+        _ = self.fake.write_text(
+            "#!" + sys.executable + "\n" + _FAKE_IMG_SOURCE, encoding="utf-8"
+        )
+        self.fake.chmod(0o755)
+        self.marks.mkdir()
+        self.recs.mkdir()
+        fx.patch("LAUNCHER", str(self.fake))
+        fx.patch("_slots", threading.BoundedSemaphore(4))
+        fx.patch("_rng", _zero)
+        fx.set_env("FAKE_IMG_SCEN", str(self.scen))
+        fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
+        sha = hashlib.sha256(fx.agy_bin.read_bytes()).hexdigest()
+        for model_id in _IMG_TARGETS:
+            proof = _proof_of(model_id)
+            original = proof["agy_binary_sha256"]
+            proof["agy_binary_sha256"] = sha
+            _ = fx.stack.callback(_restore_key, proof, "agy_binary_sha256", original)
+        self.write_scen([{}])
+        self.flag(True)
+        return self
+
+    def __exit__(self, *_exc: object) -> None:
+        self.fx.__exit__()
+
+    def write_scen(self, spawns: list[dict[str, object]]) -> None:
+        body = {"marks": str(self.marks), "recs": str(self.recs), "spawns": spawns}
+        _ = self.scen.write_text(json.dumps(body), encoding="utf-8")
+
+    def flag(self, value: bool | None) -> None:
+        """IMAGE_INPUT_ENABLED в dynamic_config.json (None — файла нет) + сброс кэша."""
+        if value is None:
+            self.fx.config.unlink(missing_ok=True)
+        else:
+            _ = self.fx.config.write_text(
+                json.dumps({"IMAGE_INPUT_ENABLED": value}), encoding="utf-8"
+            )
+        setattr(_bridge(), "_image_flag_cache", (0.0, False))
+
+    def records(self) -> list[dict[str, object]]:
+        rows = [
+            _dict(cast(object, json.loads(p.read_text(encoding="utf-8"))))
+            for p in self.recs.glob("*.json")
+        ]
+        return sorted(rows, key=lambda r: _int(r["idx"]))
+
+    def img_dirs(self) -> list[Path]:
+        ws = Path(_str(str(_bval("WORKSPACE"))))
+        return sorted(ws.glob("img-*")) if ws.exists() else []
+
+    def free_slots(self) -> int:
+        slots = cast(threading.BoundedSemaphore, _bval("_slots"))
+        taken = 0
+        while slots.acquire(blocking=False):
+            taken += 1
+        for _i in range(taken):
+            _ = slots.release()
+        return taken
+
+    def active_dirs(self) -> set[str]:
+        return set(cast("set[str]", _bval("_active_img_dirs")))
+
+
+def _file_map(rec: dict[str, object]) -> dict[str, dict[str, object]]:
+    files = _dict(rec.get("files") or {})
+    return {name: _dict(info) for name, info in files.items()}
+
+
+def _argv_of(rec: dict[str, object]) -> list[str]:
+    return cast("list[str]", rec["argv"])
+
+
+def _add_dir_of(rec: dict[str, object]) -> str:
+    argv = _argv_of(rec)
+    return argv[argv.index("--add-dir") + 1]
+
+
+def _sha_hex(raw: bytes) -> str:
+    return hashlib.sha256(raw).hexdigest()
+
+
+class _SnapRun:
+    """Подмена Run: снимок каталога изображений в момент каждой попытки, процесс не стартует."""
+
+    attempts: list[dict[str, object]] = []
+    add_dir: object
+
+    def __init__(self, *_args: object, **kwargs: object) -> None:
+        add_dir = kwargs.get("add_dir")
+        self.add_dir = add_dir
+        snap: dict[str, object] = {"add_dir": None if add_dir is None else str(add_dir)}
+        if add_dir is not None and os.path.isdir(str(add_dir)):
+            root = str(add_dir)
+            snap["dir_mode"] = os.stat(root).st_mode & 0o777
+            files: dict[str, dict[str, object]] = {}
+            for name in sorted(os.listdir(root)):
+                path = os.path.join(root, name)
+                with open(path, "rb") as handle:
+                    data = handle.read()
+                files[name] = {
+                    "sha": _sha_hex(data),
+                    "mode": os.stat(path).st_mode & 0o777,
+                }
+            snap["files"] = files
+        _SnapRun.attempts.append(snap)
+
+    def close(self) -> None:
+        return None
+
+
+def _scripted_out(state: str, **over: object) -> dict[str, object]:
+    out: dict[str, object] = {
+        "rc": 0 if state == "done" else 1,
+        "text": "ok" if state == "done" else "",
+        "usage": {},
+        "result": {},
+        "err": "e",
+        "tool_calls": [],
+        "tool_events": 0,
+        "conversation_id": "",
+        "num_turns": None,
+        "duration_s": None,
+        "state": state,
+    }
+    out.update(over)
+    return out
+
+
+def _img_ctx(
+    messages: list[dict[str, object]],
+    model: str = "gemini-4-argon",
+    effort: str = "low",
+    over: dict[str, object] | None = None,
+) -> dict[str, object]:
+    images = _collect(messages, model, effort)
+    img_dir = cast(Path, images[0]["path"]).parent if images else None
+    prompt = _str(_bfn("_messages_to_prompt")(messages, images))
+    ctx = _ctx(
+        model=model,
+        model_len=len(model),
+        effort=effort,
+        prompt=prompt,
+        full_prompt=prompt,
+        images=images,
+        img_dir=img_dir,
+        stream=False,
+    )
+    ctx.update(over or {})
+    return ctx
+
+
+def _run_once_direct(
+    ctx: dict[str, object], execute: Callable[..., dict[str, object]] | None = None
+) -> dict[str, object]:
+    """Handler._run_once с подменой Run (_SnapRun) и, при желании, _execute."""
+    handler_cls = _bval("Handler")
+    with contextlib.ExitStack() as stack:
+        _ = stack.enter_context(mock.patch.object(_bridge(), "Run", _SnapRun))
+        _ = stack.enter_context(
+            mock.patch.object(_bridge(), "_launcher", _fake_launcher_path)
+        )
+        if execute is not None:
+            _ = stack.enter_context(mock.patch.object(handler_cls, "_execute", execute))
+        with _Sock() as sock:
+            handler = cast(object, _make_handler(sock))
+            setattr(handler, "client_address", ("127.0.0.1", 1))
+            return _dict(
+                _ofn(handler, "_run_once")(
+                    ctx, _text_sink, _tool_sink, _text_sink, None
+                )
+            )
+
+
+def _sequence_execute(
+    outs: list[dict[str, object]],
+) -> Callable[..., dict[str, object]]:
+    queue_outs = list(outs)
+
+    def execute(_self: object, _run: object, *_a: object) -> dict[str, object]:
+        return dict(queue_outs.pop(0) if len(queue_outs) > 1 else queue_outs[0])
+
+    return execute
+
+
+def _post_raw_headers(port: int, content_length: int) -> int:
+    """Только заголовки с заявленным Content-Length (без тела): HTTP-статус ответа."""
+    key = _str(_bval("AUTH_KEY"))
+    head = "\r\n".join(
+        [
+            "POST /v1/chat/completions HTTP/1.1",
+            "Host: x",
+            "Authorization: Bearer " + key,
+            "Content-Type: application/json",
+            "Content-Length: %d" % content_length,
+            "",
+            "",
+        ]
+    )
+    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
+        sock.sendall(head.encode("ascii"))
+        data = sock.recv(4096).decode("ascii", "replace")
+    return int(data.split(" ", 2)[1])
+
+
+def _sse_post(port: int, body: dict[str, object]) -> str:
+    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
+    headers = {
+        "Content-Type": "application/json",
+        "Authorization": "Bearer " + _str(_bval("AUTH_KEY")),
+    }
+    conn.request("POST", "/v1/chat/completions", body=json.dumps(body), headers=headers)
+    text = conn.getresponse().read().decode("utf-8")
+    conn.close()
+    return text
+
+
+def _get_auth(port: int, path: str) -> dict[str, object]:
+    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
+    headers = {"Authorization": "Bearer " + _str(_bval("AUTH_KEY"))}
+    conn.request("GET", path, headers=headers)
+    raw = conn.getresponse().read()
+    conn.close()
+    return _dict(cast(object, json.loads(raw.decode("utf-8"))))
+
+
+def _open_fds() -> int:
+    return len(os.listdir("/dev/fd"))
+
+
+def _expect_files(
+    test: unittest.TestCase,
+    rec: dict[str, object],
+    expected: dict[int, tuple[str, bytes]],
+) -> None:
+    """Файлы каталога изображений в момент spawn: имена, байты (sha) и права 0600."""
+    files = _file_map(rec)
+    names = {"img-%d.%s" % (n, _IMG_EXT[m]) for n, (m, _r) in expected.items()}
+    test.assertEqual(set(files), names)
+    for number, (mime, raw) in expected.items():
+        info = files["img-%d.%s" % (number, _IMG_EXT[mime])]
+        test.assertEqual(info["sha"], _sha_hex(raw))
+        test.assertEqual(info["mode"], 0o600)
+    test.assertEqual(rec["dir_mode"], 0o700)
+
+
+class ImageValidationTests(unittest.TestCase):
+    """AD-002: упорядоченная fail-closed проверка image-частей (IMG-01..IMG-10)."""
+
+    def test_img01_four_mimes_one_three_sixteen_accepted_and_staged(self) -> None:
+        with _ImgEnv() as env:
+            for mime in _IMG_MIMES:
+                for count in (1, 3, 16):
+                    with self.subTest(mime=mime, count=count):
+                        raws = [_img_raw(mime, "n%d" % i) for i in range(count)]
+                        msgs = [_img_msg(*[_img_part(mime, r) for r in raws])]
+                        images = _collect(msgs)
+                        numbers = [_int(i["index"]) for i in images]
+                        self.assertEqual(numbers, list(range(1, count + 1)))
+                        self.assertTrue(all(i["mime"] == mime for i in images))
+                        self.assertTrue(all(i["data"] == b"" for i in images))
+                        names = [Path(str(i["path"])).name for i in images]
+                        self.assertEqual(
+                            names,
+                            ["img-%d.%s" % (n, _IMG_EXT[mime]) for n in numbers],
+                        )
+                        parents = {Path(str(i["path"])).parent for i in images}
+                        self.assertEqual(len(parents), 1)
+                        self.assertTrue(Path(str(images[0]["path"])).is_absolute())
+            self.assertEqual(env.img_dirs(), [])  # проверка ничего не пишет на диск
+            raws = {m: _img_raw(m, "stage-" + m[-3:]) for m in _IMG_MIMES}
+            msgs = [_img_msg(*[_img_part(m, r) for m, r in raws.items()])]
+            images = _collect(msgs)
+            img_dir = Path(str(images[0]["path"])).parent
+            _ = _bfn("_stage_images")(img_dir, images)
+            try:
+                for number, mime in enumerate(_IMG_MIMES, start=1):
+                    path = img_dir / ("img-%d.%s" % (number, _IMG_EXT[mime]))
+                    self.assertEqual(path.read_bytes(), raws[mime])
+                    self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
+                self.assertEqual(os.stat(img_dir).st_mode & 0o777, 0o700)
+                self.assertTrue(all(i["data"] == b"" for i in images))
+                self.assertTrue(all("b64" not in i for i in images))
+            finally:
+                shutil.rmtree(img_dir, ignore_errors=True)
+
+    def test_img02_sixteen_mixed_mimes_keep_global_order(self) -> None:
+        with _ImgEnv():
+            seq = [
+                (_IMG_MIMES[i % 4], _img_raw(_IMG_MIMES[i % 4], "m%d" % i))
+                for i in range(16)
+            ]
+            parts = [_img_part(m, r) for m, r in seq]
+            msgs = [
+                _img_msg(*parts[:5], text="a"),
+                _txt_msg("assistant", "ok"),
+                _img_msg(*parts[5:11]),
+                _img_msg(*parts[11:], text="z"),
+            ]
+            images = _collect(msgs)
+            self.assertEqual([_int(i["index"]) for i in images], list(range(1, 17)))
+            self.assertEqual(
+                [_int(i["msg_index"]) for i in images], [0] * 5 + [2] * 6 + [3] * 5
+            )
+            self.assertEqual([i["mime"] for i in images], [m for m, _r in seq])
+            self.assertEqual([i["ext"] for i in images], [_IMG_EXT[m] for m, _r in seq])
+
+    def test_img03_seventeen_images_rejected_before_any_decode(self) -> None:
+        with _ImgEnv() as env:
+            msgs = [_img_msg(*[_png_part("c%d" % i) for i in range(17)])]
+            calls: list[int] = []
+            real = base64.b64decode
+
+            def spy(data: str, altchars: None = None, validate: bool = False) -> bytes:
+                calls.append(1)
+                return real(data, altchars, validate)
+
+            with mock.patch.object(base64, "b64decode", spy):
+                reason, code = _reject_of(lambda: _collect(msgs))
+            self.assertEqual((reason, code), ("too_many_images", "too_many_images"))
+            self.assertEqual(calls, [])
+            self.assertEqual(env.img_dirs(), [])
+
+    def test_img04_single_image_boundary_for_every_base64_padding(self) -> None:
+        # Лимиты уменьшены патчем: граница та же, но тест не раздувает RSS процесса.
+        with _ImgEnv(), _small_limits(max_image_bytes=1000, max_total_image_bytes=1000):
+            for size in range(997, 1004):  # все остатки по модулю 3 (паддинг 0/1/2)
+                with self.subTest(size=size):
+                    msgs = [
+                        _img_msg(
+                            _img_part("image/png", _img_raw("image/png", "b", size))
+                        )
+                    ]
+                    if size <= 1000:
+                        self.assertEqual(_int(_collect(msgs)[0]["size"]), size)
+                    else:
+                        self.assertEqual(
+                            _reject_of(lambda: _collect(msgs)),
+                            ("image_too_large", "image_too_large"),
+                        )
+
+    def test_img05_single_image_one_byte_over_limit_rejected_before_total(self) -> None:
+        with _ImgEnv(), _small_limits(max_image_bytes=1000, max_total_image_bytes=500):
+            raw = _img_raw("image/png", "big", size=1001)
+            msgs = [_img_msg(_img_part("image/png", raw))]
+            self.assertEqual(
+                _reject_of(lambda: _collect(msgs)),
+                ("image_too_large", "image_too_large"),
+            )
+
+    def test_img06_total_limit_boundary(self) -> None:
+        with _ImgEnv(), _small_limits(max_image_bytes=1000, max_total_image_bytes=1000):
+            first = _img_part("image/png", _img_raw("image/png", "a", size=500))
+            ok = _img_part("image/jpeg", _img_raw("image/jpeg", "b", size=500))
+            over = _img_part("image/jpeg", _img_raw("image/jpeg", "b", size=501))
+            self.assertEqual(len(_collect([_img_msg(first, ok)])), 2)
+            self.assertEqual(
+                _reject_of(lambda: _collect([_img_msg(first, over)])),
+                ("images_too_large", "images_too_large"),
+            )
+
+    def test_img07_http_body_limit_boundary(self) -> None:
+        with _ImgEnv() as env, _small_limits(max_body_bytes=8192):
+            bridge = _HttpBridge()
+            try:
+                head = b'{"messages":[{"role":"user","content":"'
+                tail = b'"}]}'
+                data = head + b"x" * (8192 - len(head) - len(tail)) + tail
+                self.assertEqual(len(data), 8192)
+                conn = http.client.HTTPConnection("127.0.0.1", bridge.port, timeout=60)
+                headers = {
+                    "Content-Type": "application/json",
+                    "Authorization": "Bearer " + _str(_bval("AUTH_KEY")),
+                }
+                conn.request("POST", "/v1/chat/completions", body=data, headers=headers)
+                self.assertEqual(conn.getresponse().status, 200)
+                conn.close()
+                self.assertEqual(_post_raw_headers(bridge.port, 8193), 413)
+            finally:
+                bridge.close()
+            self.assertEqual(
+                len(env.records()), 1
+            )  # 413 не дошёл ни до decode, ни до spawn
+        with _ImgEnv():
+            bridge = _HttpBridge()
+            try:
+                limit = _int(_dict(_bval("IMAGE_LIMITS"))["max_body_bytes"])
+                self.assertEqual(limit, 33554432)
+                self.assertEqual(_post_raw_headers(bridge.port, limit + 1), 413)
+            finally:
+                bridge.close()
+
+    def test_img08_image_only_user_message_keeps_marker_and_attachment(self) -> None:
+        with _ImgEnv():
+            msgs = [_img_msg(_png_part("only"))]
+            images = _collect(msgs)
+            prompt = _str(_bfn("_messages_to_prompt")(msgs, images))
+            self.assertNotIn("PONG", prompt)
+            self.assertIn("[image 1]", prompt)
+            self.assertIn("[attachments]", prompt)
+            self.assertIn(str(images[0]["path"]), prompt)
+            self.assertIn("(image/png, %d bytes)" % _int(images[0]["size"]), prompt)
+
+    def test_img09_text_only_history_has_zero_image_overhead(self) -> None:
+        with _ImgEnv() as env:
+            calls: list[str] = []
+
+            def spy_for(name: str) -> Callable[..., object]:
+                def spy(*_a: object, **_k: object) -> bool:
+                    calls.append(name)
+                    return False
+
+                return spy
+
+            msgs: list[dict[str, object]] = [
+                _txt_msg("user", "hi"),
+                {
+                    "role": "user",
+                    "content": [
+                        {"type": "text", "text": "a"},
+                        {"type": "mystery", "x": 1},
+                        cast(object, "plain"),
+                    ],
+                },
+            ]
+            with contextlib.ExitStack() as stack:
+                for name in (
+                    "_is_image_input_enabled",
+                    "_file_sha256",
+                    "_new_img_dir",
+                    "_image_proof_reason",
+                ):
+                    _ = stack.enter_context(
+                        mock.patch.object(_bridge(), name, spy_for(name))
+                    )
+                self.assertEqual(_collect(msgs), [])
+            self.assertEqual(calls, [])
+            prompt = _str(_bfn("_messages_to_prompt")(msgs))
+            self.assertEqual(prompt, "### 1. user\nhi\n\n### 2. user\na\nplain")
+            self.assertEqual(env.img_dirs(), [])
+
+    def test_img10_signature_check_is_not_pixel_decoding(self) -> None:
+        with _ImgEnv():
+            truncated = _IMG_MAGIC["image/png"] + b"\x00truncated-body"
+            msgs = [_img_msg(_img_part("image/png", truncated))]
+            images = _collect(
+                msgs
+            )  # сигнатура ок: файл принят, пиксели не декодируются
+            self.assertEqual(len(images), 1)
+            prompt = _str(_bfn("_messages_to_prompt")(msgs, images))
+            self.assertIn("view_file", prompt)
+            self.assertIn("Read every attached image file", prompt)
+
+    def test_f003_count_and_base64_length_checked_before_b64decode(self) -> None:
+        with _ImgEnv(), _small_limits(max_image_bytes=1000, max_total_image_bytes=1000):
+            calls: list[int] = []
+            real = base64.b64decode
+
+            def spy(data: str, altchars: None = None, validate: bool = False) -> bytes:
+                calls.append(1)
+                return real(data, altchars, validate)
+
+            huge = "data:image/png;base64," + "A" * 1336  # оценка 1002 B > лимита 1000
+            msgs = [_img_msg({"type": "image_url", "image_url": {"url": huge}})]
+            with mock.patch.object(base64, "b64decode", spy):
+                self.assertEqual(
+                    _reject_of(lambda: _collect(msgs)),
+                    ("image_too_large", "image_too_large"),
+                )
+                many = [_img_msg(*[_png_part("k%d" % i) for i in range(17)])]
+                self.assertEqual(
+                    _reject_of(lambda: _collect(many))[1], "too_many_images"
+                )
+            self.assertEqual(calls, [])
+
+    def test_f006_data_url_is_case_insensitive_and_log_values_are_sanitized(
+        self,
+    ) -> None:
+        with _ImgEnv() as env:
+            raw = _img_raw("image/png", "case")
+            url = "DATA:IMAGE/PNG;BASE64," + base64.b64encode(raw).decode("ascii")
+            msgs = [_img_msg({"type": "image_url", "image_url": {"url": url}})]
+            images = _collect(msgs)
+            self.assertEqual(images[0]["mime"], "image/png")
+            self.assertEqual(
+                _str(_bfn("_safe_log_value")("a\nb\tc\rd\x00e")), "a_b_c_d_e"
+            )
+            buffer = io.StringIO()
+            with _Sock() as sock, mock.patch.object(sys, "stderr", buffer):
+                handler = cast(object, _make_handler(sock))
+                setattr(handler, "client_address", ("127.0.0.1", 1))
+                _ = _ofn(handler, "_log_reject")(
+                    "image_too_large", "gem\nini\tfake\r", 3
+                )
+            lines = buffer.getvalue().splitlines()
+            self.assertEqual(len(lines), 1)
+            self.assertIn("model=gem_ini_fake_ ", lines[0])
+            self.assertIsNot(_bval("_image_flag_lock"), _bval("_sqlite_guard_lock"))
+            self.assertEqual(env.img_dirs(), [])
+
+    def test_f006_sha_cache_keyed_by_identity_and_hash_runs_outside_cache_lock(
+        self,
+    ) -> None:
+        with _ImgEnv() as env:
+            target = env.fx.tmp / "sha-subject.bin"
+            _ = target.write_bytes(b"first-content")
+            self.assertEqual(_bfn("_file_sha256")(target), _sha_hex(b"first-content"))
+            held: list[bool] = []
+
+            class _ProbeHash:
+                chunks: list[bytes]
+
+                def __init__(self) -> None:
+                    self.chunks = []
+
+                def update(self, data: bytes) -> None:
+                    held.append(bool(_ofn(_bval("_sha_cache_lock"), "locked")()))
+                    self.chunks.append(data)
+
+                def hexdigest(self) -> str:
+                    return hashlib.sha256(b"".join(self.chunks)).hexdigest()
+
+            replacement = env.fx.tmp / "sha-subject.new"
+            _ = replacement.write_bytes(b"second-content")
+            os.replace(replacement, target)  # другой inode/mtime при том же пути
+            probe_module = SimpleNamespace(sha256=_ProbeHash)
+            with mock.patch.object(_bridge(), "hashlib", probe_module):
+                digest = _bfn("_file_sha256")(target)
+            self.assertEqual(digest, _sha_hex(b"second-content"))
+            self.assertTrue(held)
+            self.assertFalse(any(held))
+            self.assertEqual(_bfn("_file_sha256")(env.fx.tmp / "absent.bin"), "")
+
+
+_IMG_RAW_A = _img_raw("image/png", "alpha")
+_IMG_RAW_B = _img_raw("image/jpeg", "bravo")
+_IMG_RAW_C = _img_raw("image/gif", "charlie")
+
+
+def _post_many(
+    bridge: _HttpBridge, bodies: list[dict[str, object]]
+) -> list[tuple[int, dict[str, object]]]:
+    return [bridge.post(body) for body in bodies]
+
+
+class ImageHistoryTests(unittest.TestCase):
+    """AD-003/AD-004: сквозная нумерация истории, cold/hot/explicit/fallback (HIST-01..10)."""
+
+    def test_hist01_cold_images_then_text_resends_full_history(self) -> None:
+        with _ImgEnv() as env:
+            turn1 = [
+                _img_msg(
+                    _img_part("image/png", _IMG_RAW_A),
+                    _img_part("image/jpeg", _IMG_RAW_B),
+                    text="смотри",
+                )
+            ]
+            turn2 = turn1 + [
+                _txt_msg("assistant", "вижу"),
+                _txt_msg("user", "а теперь текст"),
+            ]
+            bridge = _HttpBridge()
+            try:
+                results = _post_many(bridge, [_img_body(turn1), _img_body(turn2)])
+            finally:
+                bridge.close()
+            self.assertEqual([code for code, _b in results], [200, 200])
+            recs = env.records()
+            self.assertEqual(len(recs), 2)
+            for rec in recs:
+                _expect_files(
+                    self,
+                    rec,
+                    {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)},
+                )
+                prompt = _str(rec["prompt"])
+                for needle in (
+                    "[image 1]",
+                    "[image 2]",
+                    "[attachments]",
+                    "img-1.png",
+                    "img-2.jpg",
+                ):
+                    self.assertIn(needle, prompt)
+                self.assertNotIn("--conversation", _argv_of(rec))
+            self.assertEqual(env.img_dirs(), [])
+
+    def test_hist02_rejected_history_without_assistant_keeps_all_images(self) -> None:
+        with _ImgEnv() as env:
+            msgs = [
+                _img_msg(
+                    _img_part("image/png", _IMG_RAW_A),
+                    _img_part("image/jpeg", _IMG_RAW_B),
+                    text="скриншоты",
+                ),
+                _txt_msg("user", "следующий текстовый ход"),
+            ]
+            bridge = _HttpBridge()
+            try:
+                code, _body = bridge.post(_img_body(msgs))
+            finally:
+                bridge.close()
+            self.assertEqual(code, 200)
+            rec = env.records()[0]
+            _expect_files(
+                self, rec, {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)}
+            )
+            prompt = _str(rec["prompt"])
+            self.assertIn("[image 1]", prompt)
+            self.assertIn("[image 2]", prompt)
+            self.assertIn("следующий текстовый ход", prompt)
+
+    def test_hist03_hot_text_turn_after_images_has_no_new_attachments(self) -> None:
+        with _ImgEnv() as env:
+            cwd = env.fx.tmp / "proj"
+            cwd.mkdir()
+            turn1 = [
+                _img_msg(
+                    _img_part("image/png", _IMG_RAW_A),
+                    _img_part("image/jpeg", _IMG_RAW_B),
+                )
+            ]
+            turn2 = turn1 + [
+                _txt_msg("assistant", "ок"),
+                _txt_msg("user", "только текст"),
+            ]
+            bridge = _HttpBridge()
+            try:
+                code1, body1 = bridge.post(_img_body(turn1, tools=True, cwd=str(cwd)))
+                code2, _body2 = bridge.post(_img_body(turn2, tools=True, cwd=str(cwd)))
+            finally:
+                bridge.close()
+            self.assertEqual((code1, code2), (200, 200))
+            first, second = env.records()
+            argv = _argv_of(second)
+            self.assertEqual(
+                argv[argv.index("--conversation") + 1], body1["conversation_id"]
+            )
+            prompt = _str(second["prompt"])
+            self.assertIn("только текст", prompt)
+            self.assertNotIn("[attachments]", prompt)
+            self.assertNotIn("[image", prompt)
+            _expect_files(
+                self,
+                second,
+                {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)},
+            )
+            self.assertEqual(
+                os.path.realpath(_str(second["cwd"])), os.path.realpath(cwd)
+            )
+            store = cast("dict[tuple[str, str, str], object]", _bval("_session_store"))
+            self.assertEqual(list(store), [("gemini-4-argon", str(cwd), "high")])
+            self.assertNotEqual(_add_dir_of(first), _add_dir_of(second))
+
+    def test_hist04_hot_new_image_keeps_global_index_and_correct_bytes(self) -> None:
+        with _ImgEnv() as env:
+            turn1 = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
+            turn2 = turn1 + [
+                _txt_msg("assistant", "ок"),
+                _img_msg(_img_part("image/jpeg", _IMG_RAW_B), text="новая картинка"),
+            ]
+            bridge = _HttpBridge()
+            try:
+                _ = bridge.post(_img_body(turn1, tools=True))
+                code, _body = bridge.post(_img_body(turn2, tools=True))
+            finally:
+                bridge.close()
+            self.assertEqual(code, 200)
+            second = env.records()[1]
+            self.assertIn("--conversation", _argv_of(second))
+            prompt = _str(second["prompt"])
+            self.assertIn("[image 2]", prompt)
+            self.assertNotIn("[image 1]", prompt)
+            self.assertIn("- [image 2] ", prompt)
+            self.assertIn("(image/jpeg, %d bytes)" % len(_IMG_RAW_B), prompt)
+            self.assertNotIn("img-1.png (", prompt)
+            _expect_files(
+                self,
+                second,
+                {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)},
+            )
+
+    def test_hist05_hot_failure_falls_back_to_cold_with_all_files(self) -> None:
+        with _ImgEnv() as env:
+            env.write_scen([{"cid": _CID}, {"mode": "error"}, {"mode": "ok"}])
+            turn1 = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
+            turn2 = turn1 + [
+                _txt_msg("assistant", "ок"),
+                _img_msg(_img_part("image/jpeg", _IMG_RAW_B)),
+            ]
+            bridge = _HttpBridge()
+            try:
+                _ = bridge.post(_img_body(turn1, tools=True))
+                code, _body = bridge.post(_img_body(turn2, tools=True))
+            finally:
+                bridge.close()
+            self.assertEqual(code, 200)
+            recs = env.records()
+            self.assertEqual(len(recs), 3)  # ход 1 + hot-попытка + cold fallback
+            hot, cold = recs[1], recs[2]
+            self.assertIn("--conversation", _argv_of(hot))
+            self.assertNotIn("--conversation", _argv_of(cold))
+            expected = {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)}
+            _expect_files(self, hot, expected)
+            _expect_files(self, cold, expected)
+            self.assertEqual(_add_dir_of(hot), _add_dir_of(cold))
+            for needle in ("[image 1]", "[image 2]", "img-1.png", "img-2.jpg"):
+                self.assertIn(needle, _str(cold["prompt"]))
+            self.assertEqual(env.img_dirs(), [])
+
+    def test_hist06_no_second_spawn_after_content_was_delivered(self) -> None:
+        with _ImgEnv() as env:
+            env.write_scen([{"cid": _CID}, {"mode": "text_then_error"}])
+            turn1 = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
+            turn2 = turn1 + [_txt_msg("assistant", "ок"), _txt_msg("user", "ещё")]
+            bridge = _HttpBridge()
+            try:
+                _ = bridge.post(_img_body(turn1, tools=True))
+                code, body = bridge.post(_img_body(turn2, tools=True))
+            finally:
+                bridge.close()
+            self.assertEqual(code, 502)
+            self.assertEqual(_err(body)["type"], "agy_error")
+            self.assertEqual(len(env.records()), 2)
+            self.assertEqual(env.img_dirs(), [])
+
+    def test_hist07_explicit_conversation_id_and_automatic_hot_prompt_differ(
+        self,
+    ) -> None:
+        with _ImgEnv() as env:
+            history = [
+                _img_msg(_img_part("image/png", _IMG_RAW_A)),
+                _txt_msg("assistant", "ок"),
+                _img_msg(_img_part("image/jpeg", _IMG_RAW_B)),
+            ]
+            explicit_cid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
+            bridge = _HttpBridge()
+            try:
+                code, _b = bridge.post(_img_body(history, conv=explicit_cid))
+                self.assertEqual(code, 200)
+                _ = bridge.post(_img_body(history[:1], tools=True))
+                code2, _b2 = bridge.post(_img_body(history, tools=True))
+                self.assertEqual(code2, 200)
+            finally:
+                bridge.close()
+            explicit, _first, hot = env.records()
+            argv = _argv_of(explicit)
+            self.assertEqual(argv[argv.index("--conversation") + 1], explicit_cid)
+            expected = {1: ("image/png", _IMG_RAW_A), 2: ("image/jpeg", _IMG_RAW_B)}
+            _expect_files(self, explicit, expected)
+            for needle in ("[image 1]", "[image 2]", "img-1.png", "img-2.jpg"):
+                self.assertIn(needle, _str(explicit["prompt"]))
+            self.assertNotIn("[image 1]", _str(hot["prompt"]))
+            self.assertIn("[image 2]", _str(hot["prompt"]))
+            _expect_files(self, hot, expected)
+
+    def test_hist08_plain_and_background_requests_do_not_touch_agentic_session(
+        self,
+    ) -> None:
+        with _ImgEnv() as env:
+            env.write_scen([{"cid": _CID}, {"cid": _CID_B}, {}])
+            first = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
+            bridge = _HttpBridge()
+            try:
+                _ = bridge.post(_img_body(first, tools=True))
+                _ = bridge.post(
+                    _img_body([_img_msg(_img_part("image/jpeg", _IMG_RAW_B))])
+                )
+                follow = first + [
+                    _txt_msg("assistant", "ок"),
+                    _txt_msg("user", "дальше"),
+                ]
+                code, _b = bridge.post(_img_body(follow, tools=True))
+            finally:
+                bridge.close()
+            self.assertEqual(code, 200)
+            agentic1, plain, agentic2 = env.records()
+            self.assertNotIn("--conversation", _argv_of(plain))
+            argv = _argv_of(agentic2)
+            self.assertEqual(argv[argv.index("--conversation") + 1], _CID)
+            self.assertEqual(
+                len({_add_dir_of(r) for r in (agentic1, plain, agentic2)}), 3
+            )
+            store = cast("dict[object, dict[str, object]]", _bval("_session_store"))
+            self.assertEqual([entry["cid"] for entry in store.values()], [_CID])
+
+    def test_hist09_parallel_requests_with_other_cwd_and_model_stay_separate(
+        self,
+    ) -> None:
+        with _ImgEnv() as env:
+            env.write_scen([{"sleep": 0.8, "cid": _CID}, {"sleep": 0.8, "cid": _CID_B}])
+            dir_a = env.fx.tmp / "proj-a"
+            dir_b = env.fx.tmp / "proj-b"
+            dir_a.mkdir()
+            dir_b.mkdir()
+            bridge = _HttpBridge()
+            results: list[int] = []
+
+            def worker(cwd: Path, model: str, raw: bytes) -> None:
+                body = _img_body(
+                    [_img_msg(_img_part("image/png", raw))],
+                    tools=True,
+                    cwd=str(cwd),
+                    model=model,
+                )
+                results.append(bridge.post(body)[0])
+
+            threads = [
+                threading.Thread(
+                    target=worker, args=(dir_a, "gemini-4-argon", _IMG_RAW_A)
+                ),
+                threading.Thread(
+                    target=worker,
+                    args=(dir_b, "gemini-3.8-flash", _img_raw("image/png", "other")),
+                ),
+            ]
+            try:
+                for thread in threads:
+                    thread.start()
+                for thread in threads:
+                    thread.join(60)
+            finally:
+                bridge.close()
+            self.assertEqual(sorted(results), [200, 200])
+            recs = env.records()
+            self.assertEqual(len(recs), 2)
+            self.assertTrue(all("--conversation" not in _argv_of(r) for r in recs))
+            self.assertEqual(
+                {os.path.realpath(_str(r["cwd"])) for r in recs},
+                {os.path.realpath(dir_a), os.path.realpath(dir_b)},
+            )
+            self.assertEqual(len({_add_dir_of(r) for r in recs}), 2)
+            self.assertLess(
+                max(_float(r["t0"]) for r in recs), min(_float(r["t1"]) for r in recs)
+            )
+            store = cast("dict[tuple[str, str, str], object]", _bval("_session_store"))
+            self.assertEqual(len(store), 2)
+
+    def test_hist10_cwd_with_spaces_and_unicode_is_not_replaced_by_image_dir(
+        self,
+    ) -> None:
+        with _ImgEnv() as env:
+            proj = env.fx.tmp / "проект с пробелом"
+            proj.mkdir()
+            _ = (proj / "rel.txt").write_text("project-file", encoding="utf-8")
+            msgs = [_img_msg(_img_part("image/png", _IMG_RAW_A), text="файл")]
+            bridge = _HttpBridge()
+            try:
+                code, _b = bridge.post(_img_body(msgs, cwd=str(proj)))
+                code_missing, _b2 = bridge.post(
+                    _img_body(msgs, cwd="/nonexistent-agy-cwd/проект")
+                )
+            finally:
+                bridge.close()
+            self.assertEqual((code, code_missing), (200, 200))
+            rec, missing = env.records()
+            self.assertEqual(os.path.realpath(_str(rec["cwd"])), os.path.realpath(proj))
+            self.assertTrue((Path(_str(rec["cwd"])) / "rel.txt").is_file())
+            argv = _argv_of(rec)
+            self.assertEqual(argv.count("--add-dir"), 1)
+            add_dir = _add_dir_of(rec)
+            self.assertTrue(os.path.isabs(add_dir))
+            ws = os.path.realpath(_str(str(_bval("WORKSPACE"))))
+            self.assertTrue(os.path.realpath(add_dir).startswith(ws + os.sep))
+            self.assertNotEqual(os.path.realpath(add_dir), os.path.realpath(proj))
+            match = re.search(
+                r"- \[image 1\] (/[^\n]+?) \(image/png, \d+ bytes\)",
+                _str(rec["prompt"]),
+            )
+            self.assertIsNotNone(match)
+            attached = Path(cast("re.Match[str]", match).group(1))
+            self.assertEqual(attached.parent, Path(add_dir))
+            self.assertIn(attached.name, _file_map(rec))
+            self.assertEqual(os.path.realpath(_str(missing["cwd"])), ws)
+
+
+class ImageLifecycleTests(unittest.TestCase):
+    """AD-005: каталог изображений живёт ход, удаляется в finally, sweep (LIFE-01..05)."""
+
+    def _assert_clean(self, env: _ImgEnv, ctx: dict[str, object]) -> None:
+        self.assertFalse(os.path.exists(_str(str(ctx["img_dir"]))))
+        self.assertEqual(env.active_dirs(), set())
+        self.assertEqual(env.free_slots(), 4)
+
+    def test_life01_dir_removed_on_every_terminal_path(self) -> None:
+        with _ImgEnv() as env:
+            msgs = [_img_msg(_img_part("image/png", _IMG_RAW_A))]
+            scripted = {
+                "done": [_scripted_out("done")],
+                "agy_error": [_scripted_out("agy_error")],
+                "client_gone": [_scripted_out("client_gone")],
+            }
+            for name, outs in scripted.items():
+                with self.subTest(path=name):
+                    _SnapRun.attempts.clear()
+                    ctx = _img_ctx(msgs)
+                    out = _run_once_direct(ctx, _sequence_execute(outs))
+                    self.assertEqual(out["state"], name)
+                    self.assertGreaterEqual(len(_SnapRun.attempts), 1)
+                    for attempt in _SnapRun.attempts:
+                        self.assertEqual(
+                            _dict(attempt["files"])["img-1.png"],
+                            {"sha": _sha_hex(_IMG_RAW_A), "mode": 0o600},
+                        )
+                    self._assert_clean(env, ctx)
+            with self.subTest(path="exception"):
+                _SnapRun.attempts.clear()
+                ctx = _img_ctx(msgs)
+
+                def boom(_self: object, _run: object, *_a: object) -> dict[str, object]:
+                    raise RuntimeError("boom")
+
+                with self.assertRaises(RuntimeError):
+                    _ = _run_once_direct(ctx, boom)
+                self.assertEqual(len(_SnapRun.attempts), 1)
+                self._assert_clean(env, ctx)
+            with self.subTest(path="launcher_unavailable"):
+                _SnapRun.attempts.clear()
+                ctx = _img_ctx(msgs)
+                unavailable = cast("type[Exception]", _bval("LauncherUnavailable"))
+
+                def missing() -> str:
+                    raise unavailable("x")
+
+                with (
+                    mock.patch.object(_bridge(), "_launcher", missing),
+                    mock.patch.object(_bridge(), "Run", _SnapRun),
+                    _Sock() as sock,
+                ):
+                    handler = cast(object, _make_handler(sock))
+                    setattr(handler, "client_address", ("127.0.0.1", 1))
+                    out = _dict(
+                        _ofn(handler, "_run_once")(
+                            ctx, _text_sink, _tool_sink, _text_sink, None
+                        )
+                    )
+                self.assertEqual(out["state"], "launcher_unavailable")
+                self.assertEqual(_SnapRun.attempts, [])
+                self._assert_clean(env, ctx)
+
+    def test_life02_retry_and_hot_cold_fallback_reuse_one_directory(self) -> None:
+        with _ImgEnv() as env:
+            msgs = [
+                _img_msg(_img_part("image/png", _IMG_RAW_A)),
+                _txt_msg("assistant", "ок"),
+                _img_msg(_img_part("image/jpeg", _IMG_RAW_B)),
+            ]
+            variants: dict[str, dict[str, object]] = {
+                "transient_retry": {},
+                "hot_to_cold": {
+                    "hot_resumed": True,
+                    "conversation_id": _CID,
+                    "sess_key": ("gemini-4-argon", "", "low"),
+                    "turn_id": "turn-life02",
+                },
+            }
+            for name, over in variants.items():
+                with self.subTest(variant=name):
+                    _SnapRun.attempts.clear()
+                    ctx = _img_ctx(msgs, over=over)
+                    out = _run_once_direct(
+                        ctx,
+                        _sequence_execute(
+                            [_scripted_out("agy_error"), _scripted_out("done")]
+                        ),
+                    )
+                    self.assertEqual(out["state"], "done")
+                    self.assertEqual(len(_SnapRun.attempts), 2)
+                    first, second = _SnapRun.attempts
+                    self.assertEqual(first["add_dir"], second["add_dir"])
+                    self.assertEqual(first["files"], second["files"])
+                    self.assertEqual(
+                        set(_dict(second["files"])), {"img-1.png", "img-2.jpg"}
+                    )
+                    self._assert_clean(env, ctx)
+
+    def test_life03_spool_failure_returns_500_and_leaves_no_directory(self) -> None:
+        with _ImgEnv() as env:
+            real_open = os.open
+            created: list[str] = []
+
+            def failing_open(
+                path: str, flags: int, mode: int = 0o777, **kw: int
+            ) -> int:
+                if str(path).endswith("img-2.png"):
+                    raise OSError(28, "No space left on device")
+                if str(path).endswith(".png"):
+                    created.append(str(path))
+                return real_open(path, flags, mode, **kw)
+
+            msgs = [_img_msg(_png_part("one"), _png_part("two"), text="две")]
+            bridge = _HttpBridge()
+            buffer = io.StringIO()
+            try:
+                with (
+                    mock.patch.object(os, "open", failing_open),
+                    mock.patch.object(sys, "stderr", buffer),
+                ):
+                    code, body = bridge.post(_img_body(msgs))
+            finally:
+                bridge.close()
+            self.assertEqual(code, 500)
+            self.assertEqual(
+                _err(body),
+                {
+                    "message": "image spool failed",
+                    "type": "image_spool_error",
+                    "code": 500,
+                },
+            )
+            self.assertEqual(len(created), 1)  # img-1.png успел записаться, затем откат
+            self.assertEqual(env.records(), [])  # spawn не было
+            self.assertEqual(env.img_dirs(), [])
+            self.assertEqual(env.active_dirs(), set())
+            self.assertEqual(env.free_slots(), 4)
+            log = buffer.getvalue()
+            self.assertIn("image_spool_error model=gemini-4-argon err=OSError", log)
+            self.assertNotIn(
+                base64.b64encode(_img_raw("image/png", "one")).decode("ascii"), log
+            )
+
+    def test_life04_parallel_turns_never_touch_each_others_directory(self) -> None:
+        with _ImgEnv() as env:
+            ctx_a = _img_ctx([_img_msg(_png_part("turn-a"))])
+            ctx_b = _img_ctx([_img_msg(_png_part("turn-b"))])
+            dir_a = _str(str(ctx_a["img_dir"]))
+            dir_b = _str(str(ctx_b["img_dir"]))
+            self.assertNotEqual(dir_a, dir_b)
+            entered = threading.Event()
+            gate = threading.Event()
+
+            def execute(_self: object, run: object, *_a: object) -> dict[str, object]:
+                if _str(str(_oval(run, "add_dir"))) == dir_a:
+                    entered.set()
+                    _ = gate.wait(20)
+                return _scripted_out("done")
+
+            outs: dict[str, dict[str, object]] = {}
+            with contextlib.ExitStack() as stack:
+                _ = stack.enter_context(mock.patch.object(_bridge(), "Run", _SnapRun))
+                _ = stack.enter_context(
+                    mock.patch.object(_bridge(), "_launcher", _fake_launcher_path)
+                )
+                _ = stack.enter_context(
+                    mock.patch.object(_bval("Handler"), "_execute", execute)
+                )
+
+                def run_a() -> None:
+                    with _Sock() as sock:
+                        handler = cast(object, _make_handler(sock))
+                        setattr(handler, "client_address", ("127.0.0.1", 1))
+                        outs["a"] = _dict(
+                            _ofn(handler, "_run_once")(
+                                ctx_a, _text_sink, _tool_sink, _text_sink, None
+                            )
+                        )
+
+                thread = threading.Thread(target=run_a)
+                thread.start()
+                self.assertTrue(entered.wait(20))
+                with _Sock() as sock:
+                    handler = cast(object, _make_handler(sock))
+                    setattr(handler, "client_address", ("127.0.0.1", 2))
+                    outs["b"] = _dict(
+                        _ofn(handler, "_run_once")(
+                            ctx_b, _text_sink, _tool_sink, _text_sink, None
+                        )
+                    )
+                self.assertFalse(os.path.exists(dir_b))
+                self.assertEqual(env.active_dirs(), {dir_a})
+                self.assertEqual(
+                    Path(dir_a, "img-1.png").read_bytes(),
+                    _img_raw("image/png", "turn-a"),
+                )
+                gate.set()
+                thread.join(20)
+            self.assertEqual((outs["a"]["state"], outs["b"]["state"]), ("done", "done"))
+            self.assertFalse(os.path.exists(dir_a))
+            self.assertEqual(env.active_dirs(), set())
+
+    def test_life05_sweep_removes_only_stale_orphans(self) -> None:
+        with _ImgEnv() as env:
+            ws = Path(_str(str(_bval("WORKSPACE"))))
+            ws.mkdir(parents=True, exist_ok=True)
+            now = 1_700_000_000.0
+
+            def make(name: str, age: float) -> Path:
+                path = ws / name
+                path.mkdir()
+                _ = (path / "f.bin").write_bytes(b"x")
+                os.utime(path, (now - age, now - age))
+                return path
+
+            stale = make("img-stale", 3601)
+            exact = make("img-exact", 3600)
+            fresh = make("img-fresh", 10)
+            active = make("img-active", 7200)
+            old_run = make("run-old", 7200)
+            other = make("keep-me", 7200)
+            outside = env.fx.tmp / "outside-target"
+            outside.mkdir()
+            _ = (outside / "secret.txt").write_text("keep", encoding="utf-8")
+            os.utime(outside, (now - 9999, now - 9999))
+            link = ws / "img-link"
+            link.symlink_to(outside, target_is_directory=True)
+            registry = cast("set[str]", _bval("_active_img_dirs"))
+            registry.add(str(active))
+            try:
+                with mock.patch.object(time, "time", lambda: now):
+                    removed = _bfn("_sweep_workspace")()
+            finally:
+                registry.discard(str(active))
+            self.assertEqual(removed, 1)
+            self.assertFalse(stale.exists())
+            self.assertFalse(old_run.exists())
+            for survivor in (exact, fresh, active, other):
+                self.assertTrue(survivor.exists(), survivor.name)
+            self.assertTrue(link.is_symlink())
+            self.assertTrue((outside / "secret.txt").is_file())
+
+
+_LOG_REASONS = (
+    "image_input_not_supported",
+    "unsupported_reasoning_effort",
+    "invalid_reasoning_effort",
+    "unsupported_image_type",
+    "invalid_image_content",
+    "invalid_image_base64",
+    "image_url_not_allowed",
+    "image_type_mismatch",
+    "image_proof_invalid",
+    "images_too_large",
+    "image_too_large",
+    "too_many_images",
+    "image_spool_error",
+    "image_cleanup_error",
+    "image_sweep_removed",
+)
+
+
+class ImageLogTests(unittest.TestCase):
+    """AD-006: reason видны дословно, секреты и payload в журнал не попадают (LOG-01/02)."""
+
+    def test_log01_every_reason_is_verbatim_and_masking_stays_strict(self) -> None:
+        with _ImgEnv():
+            with _Sock() as sock:
+                handler = cast(object, _make_handler(sock))
+                setattr(handler, "client_address", ("127.0.0.1", 1))
+                for token in _LOG_REASONS:
+                    with self.subTest(reason=token):
+                        buffer = io.StringIO()
+                        with mock.patch.object(sys, "stderr", buffer):
+                            _ = _ofn(handler, "_log_reject")(
+                                token, "gemini-4-argon", 14
+                            )
+                        pattern = (
+                            r"^\[agy-bridge\] \d\d:\d\d:\d\d reject reason=%s " % token
+                            + r"model=gemini-4-argon model_len=14 client=127.0.0.1:1$"
+                        )
+                        self.assertRegex(buffer.getvalue().strip(), pattern)
+                buffer = io.StringIO()
+                with mock.patch.object(sys, "stderr", buffer):
+                    _ = _ofn(handler, "_log_reject")(
+                        "image_input_not_supportedXY", "m", 1
+                    )
+                    _ = _ofn(handler, "_log_reject")(
+                        "abcdefghijklmnopqrstuvwxyz012345", "m", 1
+                    )
+                text = buffer.getvalue()
+                self.assertNotIn("not_supportedXY", text)
+                self.assertNotIn("abcdefghijklmnopqrstuvwxyz012345", text)
+                self.assertEqual(text.count("reason=***"), 2)
+
+    def test_log01_http_proof_and_effort_rejects_are_visible(self) -> None:
+        with _ImgEnv() as env:
+            msgs = [_img_msg(_png_part("log"))]
+            bridge = _HttpBridge()
+            buffer = io.StringIO()
+            try:
+                with mock.patch.object(sys, "stderr", buffer):
+                    with mock.patch.dict(
+                        _proof_of("gemini-4-argon"), {"agy_binary_sha256": "0" * 64}
+                    ):
+                        code1, body1 = bridge.post(_img_body(msgs))
+                    with mock.patch.dict(
+                        _proof_of("gemini-4-argon"), {"efforts_proven": ["low"]}
+                    ):
+                        body = _img_body(msgs)
+                        body["reasoning_effort"] = "high"
+                        code2, body2 = bridge.post(body)
+            finally:
+                bridge.close()
+            self.assertEqual((code1, code2), (400, 400))
+            self.assertEqual(_err(body1)["type"], "image_input_not_supported")
+            self.assertEqual(_err(body2)["type"], "unsupported_reasoning_effort")
+            log = buffer.getvalue()
+            self.assertIn(
+                "image_proof_invalid model=gemini-4-argon reason=binary_sha_mismatch",
+                log,
+            )
+            self.assertRegex(
+                log,
+                r"reject reason=image_input_not_supported model=gemini-4-argon model_len=14 client=",
+            )
+            self.assertRegex(
+                log,
+                r"reject reason=unsupported_reasoning_effort model=gemini-4-argon model_len=14 client=",
+            )
+            self.assertEqual(env.records(), [])
+
+    def test_log02_auth_key_and_image_payload_never_reach_the_log(self) -> None:
+        with _ImgEnv() as env:
+            marker_raw = _IMG_MAGIC["image/jpeg"] + b"SECRET-PAYLOAD-MARKER-" * 8
+            marker_b64 = base64.b64encode(marker_raw).decode("ascii")
+            bad = _img_msg(
+                {
+                    "type": "image_url",
+                    "image_url": {"url": "data:image/png;base64," + marker_b64},
+                }
+            )
+            good = _img_msg(
+                _img_part("image/png", _img_raw("image/png", "SECRET-OK-MARKER-" * 8))
+            )
+            bridge = _HttpBridge()
+            buffer = io.StringIO()
+            try:
+                with mock.patch.object(sys, "stderr", buffer):
+                    code_bad, _b = bridge.post(_img_body([bad]))
+                    code_ok, _b2 = bridge.post(_img_body([good]))
+            finally:
+                bridge.close()
+            self.assertEqual((code_bad, code_ok), (400, 200))
+            log = buffer.getvalue()
+            self.assertIn("reject reason=image_type_mismatch", log)
+            self.assertNotIn(_str(_bval("AUTH_KEY")), log)
+            self.assertNotIn(marker_b64, log)
+            self.assertNotIn(marker_b64[:40], log)
+            self.assertNotIn("SECRET-PAYLOAD-MARKER", log)
+            self.assertNotIn(
+                base64.b64encode(b"SECRET-OK-MARKER-").decode("ascii")[:16], log
+            )
+            self.assertEqual(len(env.records()), 1)
+
+
+class ImageResourceTests(unittest.TestCase):
+    """REQ-009/F-002/F-005: слоты, FD, повторная проверка после очереди, отказ без деградации."""
+
+    def test_res01_concurrent_turns_bounded_by_slots_without_fd_or_dir_leaks(
+        self,
+    ) -> None:
+        with _ImgEnv() as env:
+            env.fx.patch("_slots", threading.BoundedSemaphore(2))
+            env.write_scen([{"sleep": 0.5}])
+            bridge = _HttpBridge()
+            codes: list[int] = []
+            sampled: list[int] = []
+            stop = threading.Event()
+
+            def sampler() -> None:
+                while not stop.is_set():
+                    sampled.append(len(env.img_dirs()))
+                    time.sleep(0.02)
+
+            def worker(n: int) -> None:
+                parts = [_png_part("r%da" % n), _png_part("r%db" % n)]
+                codes.append(
+                    bridge.post(_img_body([_img_msg(*parts, text="req-%d" % n)]))[0]
+                )
+
+            watcher = threading.Thread(target=sampler)
+            threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
+            fd_before = _open_fds()
+            try:
+                watcher.start()
+                for thread in threads:
+                    thread.start()
+                for thread in threads:
+                    thread.join(120)
+            finally:
+                stop.set()
+                watcher.join(10)
+                bridge.close()
+            self.assertEqual(codes, [200] * 8)
+            self.assertLessEqual(
+                max(sampled), 2
+            )  # каталоги только у ходов, занявших слот
+            recs = env.records()
+            self.assertEqual(len(recs), 8)
+            events = sorted(
+                [(_float(r["t0"]), 1) for r in recs]
+                + [(_float(r["t1"]), -1) for r in recs]
+            )
+            running = peak = 0
+            for _t, delta in events:
+                running += delta
+                peak = max(peak, running)
+            self.assertLessEqual(peak, 2)
+            for rec in recs:
+                found = re.search(r"req-(\d+)", _str(rec["prompt"]))
+                self.assertIsNotNone(found)
+                number = int(cast("re.Match[str]", found).group(1))
+                expected = {
+                    1: ("image/png", _img_raw("image/png", "r%da" % number)),
+                    2: ("image/png", _img_raw("image/png", "r%db" % number)),
+                }
+                _expect_files(self, rec, expected)
+            self.assertEqual(len({_add_dir_of(r) for r in recs}), 8)
+            self.assertEqual(env.img_dirs(), [])
+            self.assertEqual(env.active_dirs(), set())
+            self.assertEqual(env.free_slots(), 2)
+            deadline = time.monotonic() + 5
+            while _open_fds() > fd_before and time.monotonic() < deadline:
+                time.sleep(0.05)
+            self.assertLessEqual(_open_fds(), fd_before)
+
+    def test_res02_disabled_or_unproven_image_path_leaves_text_untouched(self) -> None:
+        with _ImgEnv() as env:
+            bridge = _HttpBridge()
+            try:
+                env.flag(False)
+                code, body = bridge.post(_img_body([_img_msg(_png_part("a"))]))
+                self.assertEqual(
+                    (code, _err(body)["type"]), (400, "image_input_not_supported")
+                )
+                self.assertEqual((env.records(), env.img_dirs()), ([], []))
+                health = bridge.get("/health")[1]
+                self.assertEqual(
+                    (health["images"], health["image_input_mode"]), (False, "disabled")
+                )
+                text_code, _b = bridge.post(
+                    _img_body([_txt_msg("user", "просто текст")])
+                )
+                self.assertEqual(text_code, 200)
+                sse = _sse_post(
+                    bridge.port, _img_body([_txt_msg("user", "поток")], stream=True)
+                )
+                self.assertIn("ответ", sse)
+                self.assertIn("data: [DONE]", sse)
+                env.flag(True)
+                health = bridge.get("/health")[1]
+                self.assertEqual(
+                    (health["images"], health["image_input_mode"]), (True, "enabled")
+                )
+                before = len(env.records())
+                with (
+                    mock.patch.dict(
+                        _proof_of("gemini-4-argon"), {"agy_binary_sha256": "f" * 64}
+                    ),
+                    mock.patch.dict(
+                        _proof_of("gemini-3.8-flash"), {"agy_binary_sha256": "f" * 64}
+                    ),
+                ):
+                    health = bridge.get("/health")[1]
+                    self.assertEqual(health["images"], False)
+                    code2, body2 = bridge.post(_img_body([_img_msg(_png_part("b"))]))
+                    self.assertEqual(
+                        (code2, _err(body2)["type"]), (400, "image_input_not_supported")
+                    )
+                    text2, _b2 = bridge.post(
+                        _img_body([_txt_msg("user", "текст при чужом бинаре")])
+                    )
+                    self.assertEqual(text2, 200)
+                self.assertEqual(len(env.records()), before + 1)
+                self.assertEqual(env.img_dirs(), [])
+            finally:
+                bridge.close()
+
+    def test_res03_at_most_two_attempts_and_retry_budget_is_respected(self) -> None:
+        with _ImgEnv() as env:
+            msgs = [_img_msg(_png_part("retry"))]
+            for budget, expected in ((30, 2), (0, 1)):
+                with self.subTest(budget_tenths=budget):
+                    _SnapRun.attempts.clear()
+                    setattr(_bridge(), "_retry_tenths", budget)
+                    ctx = _img_ctx(msgs)
+                    out = _run_once_direct(
+                        ctx, _sequence_execute([_scripted_out("agy_error")])
+                    )
+                    self.assertEqual(out["state"], "agy_error")
+                    self.assertEqual(len(_SnapRun.attempts), expected)
+                    self.assertFalse(os.path.exists(_str(str(ctx["img_dir"]))))
+            self.assertEqual(env.free_slots(), 4)
+
+    def test_f002_flag_and_proof_are_rechecked_after_waiting_for_a_slot(self) -> None:
+        with _ImgEnv() as env:
+            handler_cls = _bval("Handler")
+            real_acquire = cast(
+                Callable[..., str], getattr(handler_cls, "_acquire_slot")
+            )
+            real_mkdir = os.mkdir
+            mkdirs: list[str] = []
+            flips: list[Callable[[], None]] = []
+
+            def acquire_then_flip(self: object, keepalive: object) -> str:
+                result = real_acquire(self, keepalive)
+                flips.pop(0)()
+                return result
+
+            def spy_mkdir(path: str, mode: int = 0o777, **kw: int) -> None:
+                if "img-" in str(path):
+                    mkdirs.append(str(path))
+                real_mkdir(path, mode, **kw)
+
+            def disable_flag() -> None:
+                env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", "0")
+
+            def break_proof() -> None:
+                env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
+                _proof_of("gemini-4-argon")["agy_binary_sha256"] = "e" * 64
+
+            bridge = _HttpBridge()
+            buffer = io.StringIO()
+            try:
+                with (
+                    mock.patch.object(handler_cls, "_acquire_slot", acquire_then_flip),
+                    mock.patch.object(os, "mkdir", spy_mkdir),
+                    mock.patch.object(sys, "stderr", buffer),
+                ):
+                    for flip in (disable_flag, break_proof):
+                        env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
+                        flips.append(flip)
+                        code, body = bridge.post(
+                            _img_body([_img_msg(_png_part("late"))])
+                        )
+                        self.assertEqual(
+                            (code, _err(body)["type"]),
+                            (400, "image_input_not_supported"),
+                        )
+            finally:
+                bridge.close()
+            self.assertEqual(mkdirs, [])
+            self.assertEqual(env.records(), [])
+            self.assertEqual(env.img_dirs(), [])
+            self.assertEqual(env.free_slots(), 4)
+            self.assertIn(
+                "image_proof_invalid model=gemini-4-argon reason=binary_sha_mismatch",
+                buffer.getvalue(),
+            )
+
+    def test_f001_flag_defaults_false_and_follows_env_then_strict_config(self) -> None:
+        with _ImgEnv() as env:
+            is_enabled = _bfn("_is_image_input_enabled")
+            env.flag(None)
+            self.assertIs(is_enabled(), False)  # код по умолчанию fail-closed
+            for raw, expected in (
+                ("0", False),
+                ("off", False),
+                ("1", True),
+                ("yes", True),
+                ("maybe", False),
+            ):
+                with self.subTest(env=raw):
+                    env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", raw)
+                    self.assertIs(is_enabled(), expected)
+            env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
+            payloads = {
+                "true": ('{"IMAGE_INPUT_ENABLED": true}', True),
+                "string": ('{"IMAGE_INPUT_ENABLED": "true"}', False),
+                "int": ('{"IMAGE_INPUT_ENABLED": 1}', False),
+                "other_key": ('{"SQLITE_REASONING_ENABLED": true}', False),
+                "list": ("[true]", False),
+                "corrupt": ("{not json", False),
+                "huge": (
+                    '{"IMAGE_INPUT_ENABLED": true, "pad": "' + "x" * 70000 + '"}',
+                    False,
+                ),
+            }
+            for name, (text, expected) in payloads.items():
+                with self.subTest(config=name):
+                    _ = env.fx.config.write_text(text, encoding="utf-8")
+                    setattr(_bridge(), "_image_flag_cache", (0.0, False))
+                    self.assertIs(is_enabled(), expected)
+            _ = env.fx.config.write_text(
+                '{"IMAGE_INPUT_ENABLED": true}', encoding="utf-8"
+            )
+            setattr(_bridge(), "_image_flag_cache", (0.0, False))
+            self.assertIs(is_enabled(), True)
+            _ = env.fx.config.write_text(
+                '{"IMAGE_INPUT_ENABLED": false}', encoding="utf-8"
+            )
+            self.assertIs(is_enabled(), True)  # кэш TTL 1.0 с ещё действует
+            setattr(_bridge(), "_image_flag_cache", (0.0, False))
+            self.assertIs(is_enabled(), False)
+            _ = env.fx.config.write_text(
+                json.dumps(
+                    {"SQLITE_REASONING_ENABLED": True, "IMAGE_INPUT_ENABLED": False}
+                ),
+                encoding="utf-8",
+            )
+            setattr(_bridge(), "_image_flag_cache", (0.0, False))
+            self.assertIs(is_enabled(), False)  # SQLite-флаг image-вход не включает
+
+
+_UNSUPPORTED_MODELS = (
+    "gemini-3.7-flash",
+    "gemini-3.6-flash",
+    "gemini-3.1-pro",
+    "gpt-oss-120b",
+)
+
+
+def _bad_url_msg(url: object) -> list[dict[str, object]]:
+    return [_img_msg({"type": "image_url", "image_url": {"url": url}})]
+
+
+def _taxonomy_cases(
+    cap: int,
+) -> list[tuple[str, str, Callable[[], list[dict[str, object]]]]]:
+    png = _img_raw("image/png", "ok")
+    ok_b64 = base64.b64encode(png).decode("ascii")
+
+    def data(mime: str, raw: bytes) -> list[dict[str, object]]:
+        return [_img_msg(_img_part(mime, raw))]
+
+    def assistant_image() -> list[dict[str, object]]:
+        return [_img_msg(_png_part("role"), role="assistant")]
+
+    def string_image_url() -> list[dict[str, object]]:
+        return [
+            _img_msg({"type": "image_url", "image_url": _img_url("image/png", png)})
+        ]
+
+    return [
+        (
+            "remote_http",
+            "image_url_not_allowed",
+            lambda: _bad_url_msg("http://example.test/a.png"),
+        ),
+        (
+            "remote_https",
+            "image_url_not_allowed",
+            lambda: _bad_url_msg("https://example.test/a.png"),
+        ),
+        (
+            "file_url",
+            "image_url_not_allowed",
+            lambda: _bad_url_msg("file:///etc/passwd"),
+        ),
+        ("relative_path", "image_url_not_allowed", lambda: _bad_url_msg("img/a.png")),
+        (
+            "bmp_mime",
+            "unsupported_image_type",
+            lambda: _bad_url_msg("data:image/bmp;base64," + ok_b64),
+        ),
+        (
+            "unknown_magic",
+            "unsupported_image_type",
+            lambda: data("image/png", b"not-an-image-at-all"),
+        ),
+        (
+            "bad_alphabet",
+            "invalid_image_base64",
+            lambda: _bad_url_msg("data:image/png;base64,@@@@"),
+        ),
+        (
+            "empty_payload",
+            "invalid_image_base64",
+            lambda: _bad_url_msg("data:image/png;base64,"),
+        ),
+        (
+            "bad_padding",
+            "invalid_image_base64",
+            lambda: _bad_url_msg("data:image/png;base64,abc"),
+        ),
+        (
+            "png_as_jpeg",
+            "image_type_mismatch",
+            lambda: data("image/png", _img_raw("image/jpeg")),
+        ),
+        (
+            "gif_as_webp",
+            "image_type_mismatch",
+            lambda: data("image/webp", _img_raw("image/gif")),
+        ),
+        ("string_image_url", "invalid_image_content", string_image_url),
+        (
+            "url_missing",
+            "invalid_image_content",
+            lambda: [_img_msg({"type": "image_url", "image_url": {}})],
+        ),
+        ("url_not_string", "invalid_image_content", lambda: _bad_url_msg(42)),
+        (
+            "no_comma",
+            "invalid_image_content",
+            lambda: _bad_url_msg("data:image/png;base64"),
+        ),
+        (
+            "no_base64_param",
+            "invalid_image_content",
+            lambda: _bad_url_msg("data:image/png," + ok_b64),
+        ),
+        ("assistant_role", "invalid_image_content", assistant_image),
+        (
+            "too_many",
+            "too_many_images",
+            lambda: [_img_msg(*[_png_part("t%d" % i) for i in range(17)])],
+        ),
+        (
+            "one_byte_over",
+            "image_too_large",
+            lambda: data("image/png", _img_raw("image/png", "b", size=cap + 1)),
+        ),
+        (
+            "sum_over",
+            "images_too_large",
+            lambda: [
+                _img_msg(
+                    _img_part("image/png", _img_raw("image/png", "a", size=cap // 2)),
+                    _img_part(
+                        "image/jpeg", _img_raw("image/jpeg", "b", size=cap // 2 + 1)
+                    ),
+                )
+            ],
+        ),
+    ]
+
+
+class AcceptanceOracleTests(unittest.TestCase):
+    """AC-001..AC-010: приёмочные оракулы image-входа на уровне HTTP-обработчика (L1/L2)."""
+
+    def test_ao01_target_models_accept_images_unsupported_and_flag_off_reject(
+        self,
+    ) -> None:
+        with _ImgEnv() as env:
+            bridge = _HttpBridge()
+            try:
+                for model in _IMG_TARGETS:
+                    with self.subTest(model=model):
+                        before = len(env.records())
+                        code, _b = bridge.post(
+                            _img_body([_img_msg(_png_part(model))], model=model)
+                        )
+                        self.assertEqual(code, 200)
+                        rec = env.records()[before]
+                        self.assertIn("--add-dir", _argv_of(rec))
+                        self.assertEqual(set(_file_map(rec)), {"img-1.png"})
+                listing = _get_auth(bridge.port, "/v1/models")
+                flags = {
+                    _str(_dict(m)["id"]): _dict(m)["images"]
+                    for m in cast("list[object]", listing["data"])
+                }
+                self.assertEqual(
+                    {mid for mid, on in flags.items() if on}, set(_IMG_TARGETS)
+                )
+                self.assertIs(listing["images"], True)
+                self.assertIs(bridge.get("/health")[1]["images"], True)
+                spawned = len(env.records())
+                for model in _UNSUPPORTED_MODELS:
+                    with self.subTest(unsupported=model):
+                        code, body = bridge.post(
+                            _img_body([_img_msg(_png_part("u"))], model=model)
+                        )
+                        self.assertEqual(code, 400)
+                        self.assertEqual(
+                            _err(body),
+                            {
+                                "message": "image rejected: image_input_not_supported",
+                                "type": "image_input_not_supported",
+                                "code": 400,
+                            },
+                        )
+                self.assertEqual(len(env.records()), spawned)
+                env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", "0")
+                code_off, body_off = bridge.post(
+                    _img_body([_img_msg(_png_part("off"))])
+                )
+                self.assertEqual(
+                    (code_off, _err(body_off)["type"]),
+                    (400, "image_input_not_supported"),
+                )
+                code_text, _bt = bridge.post(
+                    _img_body([_txt_msg("user", "текст при выключенном флаге")])
+                )
+                self.assertEqual(code_text, 200)
+                self.assertEqual(len(env.records()), spawned + 1)
+                env.fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
+                env.flag(False)
+                code_cfg, _bc = bridge.post(_img_body([_img_msg(_png_part("cfg"))]))
+                self.assertEqual(code_cfg, 400)
+            finally:
+                bridge.close()
+
+    def test_ao02_mixed_formats_sixteen_accepted_and_seventeen_rejected_over_http(
+        self,
+    ) -> None:
+        with _ImgEnv() as env:
+            seq = [
+                (_IMG_MIMES[i % 4], _img_raw(_IMG_MIMES[i % 4], "h%d" % i))
+                for i in range(16)
+            ]
+            bridge = _HttpBridge()
+            try:
+                code, _b = bridge.post(
+                    _img_body([_img_msg(*[_img_part(m, r) for m, r in seq])])
+                )
+                self.assertEqual(code, 200)
+                code17, body17 = bridge.post(
+                    _img_body([_img_msg(*[_png_part("x%d" % i) for i in range(17)])])
+                )
+            finally:
+                bridge.close()
+            self.assertEqual((code17, _err(body17)["type"]), (400, "too_many_images"))
+            rec = env.records()[0]
+            _expect_files(self, rec, {n: seq[n - 1] for n in range(1, 17)})
+            self.assertEqual(len(env.records()), 1)
+
+    def test_ao03_every_reject_reason_is_400_before_spool_and_spawn(self) -> None:
+        with (
+            _ImgEnv() as env,
+            _small_limits(max_image_bytes=1000, max_total_image_bytes=1000),
+        ):
+            bridge = _HttpBridge()
+            try:
+                for name, reason, build in _taxonomy_cases(1000):
+                    with self.subTest(case=name):
+                        code, body = bridge.post(_img_body(build()))
+                        self.assertEqual(code, 400)
+                        self.assertEqual(
+                            _err(body),
+                            {
+                                "message": "image rejected: " + reason,
+                                "type": reason,
+                                "code": 400,
+                            },
+                        )
+                code, body = bridge.post(
+                    _img_body([_img_msg(_png_part("g"))], model="gpt-oss-120b")
+                )
+                self.assertEqual(_err(body)["type"], "image_input_not_supported")
+                self.assertEqual((env.records(), env.img_dirs()), ([], []))
+                with mock.patch.dict(_proof_of("gemini-4-argon"), {"impl_version": 99}):
+                    code_p, body_p = bridge.post(_img_body([_img_msg(_png_part("p"))]))
+                    code_t, _bt = bridge.post(_img_body([_txt_msg("user", "текст")]))
+                self.assertEqual(
+                    (code_p, _err(body_p)["type"], code_t),
+                    (400, "image_input_not_supported", 200),
+                )
+            finally:
+                bridge.close()
+            self.assertEqual(
+                len(env.records()), 1
+            )  # только текстовый ход дошёл до spawn
+
+    def test_ao04_global_numbering_for_cold_hot_and_fallback_prompts(self) -> None:
+        with _ImgEnv():
+            msgs = [
+                _img_msg(
+                    _img_part("image/png", _IMG_RAW_A),
+                    _img_part("image/jpeg", _IMG_RAW_B),
+                ),
+                _txt_msg("assistant", "ок"),
+                _img_msg(_img_part("image/gif", _IMG_RAW_C), text="новая"),
+            ]
+            images = _collect(msgs)
+            full = _str(_bfn("_messages_to_prompt")(msgs, images))
+            resumed = _str(_bfn("_get_resumed_turn_prompt")(msgs, images))
+            for n in (1, 2, 3):
+                self.assertIn("[image %d]" % n, full)
+            self.assertEqual(full.count("- [image "), 3)
+            self.assertIn("[image 3]", resumed)
+            self.assertNotIn("[image 1]", resumed)
+            self.assertNotIn("[image 2]", resumed)
+            self.assertEqual(resumed.count("- [image "), 1)
+            self.assertIn("img-3.gif (image/gif, %d bytes)" % len(_IMG_RAW_C), resumed)
+            followup = msgs + [
+                _txt_msg("assistant", "ещё"),
+                _txt_msg("user", "просто текст"),
+            ]
+            images2 = _collect(followup)
+            self.assertEqual([_int(i["index"]) for i in images2], [1, 2, 3])
+            hot = _str(_bfn("_get_resumed_turn_prompt")(followup, images2))
+            self.assertNotIn("[attachments]", hot)
+            self.assertNotIn("[image", hot)
+            self.assertIn("просто текст", hot)
+            self.assertEqual(
+                _str(_bfn("_get_resumed_turn_prompt")(msgs[:1], images[:2])),
+                _str(_bfn("_messages_to_prompt")(msgs[:1], images[:2])),
+            )
+
+    def test_ao05_cwd_session_key_and_add_dir_argv(self) -> None:
+        with _ImgEnv() as env:
+            cwd = env.fx.tmp / "каталог с пробелом"
+            cwd.mkdir()
+            bridge = _HttpBridge()
+            try:
+                code, _b = bridge.post(
+                    _img_body([_img_msg(_png_part("cwd"))], tools=True, cwd=str(cwd))
+                )
+            finally:
+                bridge.close()
+            self.assertEqual(code, 200)
+            rec = env.records()[0]
+            argv = _argv_of(rec)
+            self.assertEqual(os.path.realpath(_str(rec["cwd"])), os.path.realpath(cwd))
+            self.assertEqual(argv.count("--add-dir"), 1)
+            self.assertNotEqual(
+                os.path.realpath(_add_dir_of(rec)), os.path.realpath(cwd)
+            )
+            for flag in ("--dangerously-skip-permissions", "--model", "--effort"):
+                self.assertIn(flag, argv)
+            store = cast("dict[tuple[str, str, str], object]", _bval("_session_store"))
+            self.assertEqual(list(store), [("gemini-4-argon", str(cwd), "high")])
+
+    def test_ao06_modes_during_turn_and_cleanup_after_success_and_error(self) -> None:
+        with _ImgEnv() as env:
+            env.write_scen([{}, {"mode": "error"}])
+            bridge = _HttpBridge()
+            try:
+                code_ok, _b = bridge.post(_img_body([_img_msg(_png_part("ok"))]))
+                code_err, body_err = bridge.post(
+                    _img_body([_img_msg(_png_part("fail"))])
+                )
+            finally:
+                bridge.close()
+            self.assertEqual((code_ok, code_err), (200, 502))
+            self.assertEqual(_err(body_err)["type"], "agy_error")
+            recs = env.records()
+            self.assertGreaterEqual(len(recs), 2)
+            for rec in recs:
+                self.assertEqual(rec["dir_mode"], 0o700)
+                self.assertTrue(
+                    all(info["mode"] == 0o600 for info in _file_map(rec).values())
+                )
+            self.assertEqual(env.img_dirs(), [])
+            self.assertEqual(env.active_dirs(), set())
+
+    def test_ao07_reject_lines_follow_the_strict_template(self) -> None:
+        with _ImgEnv():
+            bridge = _HttpBridge()
+            buffer = io.StringIO()
+            try:
+                with mock.patch.object(sys, "stderr", buffer):
+                    for _name, _reason, build in _taxonomy_cases(1000)[:12]:
+                        _ = bridge.post(_img_body(build()))
+            finally:
+                bridge.close()
+            lines = [
+                ln for ln in buffer.getvalue().splitlines() if " reject reason=" in ln
+            ]
+            self.assertGreaterEqual(len(lines), 12)
+            for line in lines:
+                self.assertRegex(
+                    line,
+                    r"^\[agy-bridge\] \d\d:\d\d:\d\d reject reason=[a-z0-9_]+ model=gemini-4-argon model_len=14 client=127\.0\.0\.1:\d+$",
+                )
+                self.assertNotIn("reason=***", line)
+
+    def test_ao08_directory_is_registered_before_mkdir_and_survives_sweep(self) -> None:
+        with _ImgEnv() as env:
+            env.write_scen([{"sleep": 1.0}])
+            real_mkdir = os.mkdir
+            observed: list[bool] = []
+
+            def spy_mkdir(path: str, mode: int = 0o777, **kw: int) -> None:
+                if os.path.basename(str(path)).startswith("img-"):
+                    observed.append(
+                        str(path) in cast("set[str]", _bval("_active_img_dirs"))
+                    )
+                real_mkdir(path, mode, **kw)
+
+            bridge = _HttpBridge()
+            results: list[int] = []
+            with mock.patch.object(os, "mkdir", spy_mkdir):
+                thread = threading.Thread(
+                    target=lambda: results.append(
+                        bridge.post(_img_body([_img_msg(_png_part("sw"))]))[0]
+                    )
+                )
+                try:
+                    thread.start()
+                    deadline = time.monotonic() + 30
+                    while not env.records() and time.monotonic() < deadline:
+                        time.sleep(0.02)
+                    dirs = env.img_dirs()
+                    self.assertEqual(len(dirs), 1)
+                    removed = _bfn("_sweep_workspace")(
+                        -1.0
+                    )  # всё «старше» отсечки, кроме активного
+                    self.assertEqual(removed, 0)
+                    self.assertTrue(dirs[0].is_dir())
+                    thread.join(60)
+                finally:
+                    bridge.close()
+            self.assertEqual(results, [200])
+            self.assertEqual(observed, [True])
+            self.assertEqual(env.img_dirs(), [])
+
+    def test_ao09_delivered_reasoning_is_never_retried_with_images(self) -> None:
+        with _ImgEnv() as env:
+            msgs = [_img_msg(_png_part("rs"))]
+            for hot in (False, True):
+                with self.subTest(hot=hot):
+                    _SnapRun.attempts.clear()
+                    over: dict[str, object] = {"stream": True}
+                    if hot:
+                        over.update(
+                            hot_resumed=True,
+                            conversation_id=_CID,
+                            sess_key=("gemini-4-argon", "", "low"),
+                            turn_id="turn-ao09",
+                        )
+                    ctx = _img_ctx(msgs, over=over)
+                    out = _run_once_direct(
+                        ctx,
+                        _sequence_execute(
+                            [_scripted_out("agy_error", reasoning="мышление")]
+                        ),
+                    )
+                    self.assertEqual(out["state"], "agy_error")
+                    self.assertEqual(len(_SnapRun.attempts), 1)
+                    self.assertFalse(os.path.exists(_str(str(ctx["img_dir"]))))
+            bridge = _HttpBridge()
+            try:
+                health = bridge.get("/health")[1]
+            finally:
+                bridge.close()
+            for key in (
+                "ok",
+                "transport",
+                "native_tools",
+                "hot_sessions",
+                "max_concurrent",
+                "images",
+                "sqlite_reasoning_mode",
+            ):
+                self.assertIn(key, health)
+            self.assertEqual(env.free_slots(), 4)
+
+    def test_ao10_repo_fleet_and_server_form_one_consistent_pair(self) -> None:
+        # L3 (живой :9887 + DSH Desktop) этим тестом НЕ проверяется: нужен деплой пары.
+        with _Fixture() as fx:
+            fx.set_flag(None)
+            fx.set_env("AGY_IMAGE_INPUT_ENABLED", None)
+            self.assertEqual(_bval("IMPLEMENTED_METHODS"), {"workspace-read": 1})
+            self.assertEqual(_bval("METHOD_IMPL_VERSION"), 1)
+            catalog = _dict(_bval("FLEET"))
+            ref = _dict(catalog["technical_ref"])
+            self.assertEqual(ref["agy_version"], "1.4.9")
+            sha = _str(ref["agy_binary_sha256"])
+            limits = _dict(catalog["image_limits"])
+            self.assertEqual(
+                (
+                    limits["max_images"],
+                    limits["max_image_bytes"],
+                    limits["max_total_image_bytes"],
+                    limits["max_body_bytes"],
+                ),
+                (16, _IMG_CAP, _IMG_CAP, 33554432),
+            )
+            self.assertEqual(limits["types"], list(_IMG_MIMES))
+            models = _dict(catalog["models"])
+            for model_id, model in models.items():
+                info = _dict(model)
+                images = _dict(info["images"])
+                if model_id in _IMG_TARGETS:
+                    proof = _dict(images["proof"])
+                    self.assertEqual(
+                        (images["status"], images["method"], info["input"]),
+                        ("confirmed", "workspace-read", ["text", "image"]),
+                    )
+                    self.assertEqual(proof["agy_binary_sha256"], sha)
+                    self.assertEqual(proof["impl_version"], 1)
+                    self.assertEqual(proof["formats"], list(_IMG_MIMES))
+                    self.assertTrue(
+                        set(cast("list[str]", proof["efforts_proven"]))
+                        <= set(cast("list[str]", info["efforts"]))
+                    )
+                else:
+                    self.assertEqual(
+                        (images["status"], images["method"], info["input"]),
+                        ("unsupported", None, ["text"]),
+                    )
+            self.assertIs(_bfn("_is_image_input_enabled")(), False)
+            self.assertIs(_bfn("_model_supports_images")("gemini-4-argon"), False)
+            build = _bfn("_build_catalog")
+            violation = cast("type[Exception]", _bval("FleetViolation"))
+            raw = cast(
+                "dict[str, object]",
+                json.loads(
+                    Path(_str(_dict(catalog)["path"])).read_text(encoding="utf-8")
+                ),
+            )
+
+            def drop_method(model: dict[str, object]) -> None:
+                _dict(model["images"])["method"] = None
+
+            def drop_proof(model: dict[str, object]) -> None:
+                _dict(model["images"])["proof"] = None
+
+            def text_only_input(model: dict[str, object]) -> None:
+                model["input"] = ["text"]
+
+            mutations: list[tuple[str, Callable[[dict[str, object]], None], str]] = [
+                ("method_none", drop_method, "method_not_implemented"),
+                ("proof_missing", drop_proof, "proof_invalid"),
+                ("input_text_only", text_only_input, "status_inconsistent"),
+            ]
+            for label, mutate, reason in mutations:
+                with self.subTest(violation=label):
+                    broken = cast("dict[str, object]", json.loads(json.dumps(raw)))
+                    mutate(_dict(cast("list[object]", broken["models"])[0]))
+                    with self.assertRaises(violation) as caught:
+                        _ = build(broken)
+                    self.assertEqual(_oval(caught.exception, "reason"), reason)
+            self.assertEqual(_dict(build(raw))["default_model"], "gemini-3.8-flash")
+
+
 if __name__ == "__main__":
     unittest.main()
```


---
PANEL-NONCE: 17aa3c514267dcb8
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 17aa3c514267dcb8» и «ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689».

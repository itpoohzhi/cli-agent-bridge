You are Judge Seat #1 (skeptic, slot=gpt-6.1-sol-high, family=OpenAI, transport=codex) of the Code Council Gate (stage=council, round=r1) for run agy-image-input-fix-20261029.
PANEL-NONCE: d87c2af69dfa830d
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689

# Бриф судьи Совета Тимлидов (Council Gate — Финальная приёмка кода, Раунд R1, Место #1 — skeptic)

⚠️ **КРИТИЧЕСКАЯ ИНСТРУКЦИЯ (LEAF JUDGE / AGENT_SPAWN_DEPTH=1):**
- Вы — конечный судья панели `teamlead-gate` (`mode: code`, `stage: council`, `round: r1`, `seat: 1`).
- **НЕ запускайте** никаких субагентов, контуров `cel`, внешних скриптов или команд модификации.
- **НЕ вызывайте** инструменты чтения/поиска без необходимости — **весь проверяемый пакет (`teamlead/package.md`, включая полный `candidate.diff`, манифесты, `coder.json`, результаты чистой комнаты `VER-001..VER-010`, `verification-traceability.md`, `reverse-spec.md`, вердикт `ARCH_PANEL` с таблицей `F-001..F-010`) уже полностью встроен в этот бриф ниже**. Вы можете сразу вынести вердикт по тексту этого брифа.
- **Первыми двумя строками вашего ответа ОБЯЗАНЫ быть дословно (без отступов, без markdown-блоков вокруг них):**
PANEL-NONCE: d87c2af69dfa830d
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689
- **Строка `ОБЩИЙ ВЕРДИКТ:` (и `Вердикт места:`) ОБЯЗАНА принимать строго одно из канонических значений верификатора `verify_panel_proof.py` (`PoL-V12`):** `ACCEPT`, `PASS`, `NEEDS_WORK` или `RED_FLAG` (слова `REVISE` или `REJECT` верификатором `PoL-V12` запрещены!).
- Весь ответ — строго на **русском языке**.

---

## 1. Входной контракт места

- **run_id**: `agy-image-input-fix-20261029`
- **mode**: `code`
- **stage**: `council`
- **round**: `r1`
- **seat**: `1`
- **slot_id**: `gpt-6.1-sol-high`
- **family**: `OpenAI`
- **transport**: `codex`
- **Шляпа (hat)**: Скептик (ищет ошибки, гонки, утечки дескрипторов, нарушения F-001..F-010 и инвариантов)
- **seed_recheck_duty**: `да`
- **PANEL-NONCE**: `d87c2af69dfa830d`
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
PANEL-NONCE: d87c2af69dfa830d
ARTIFACT-SHA256: 8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689
```

Далее строго по разделам:
```
=== КАРТОЧКА СУДЬИ ===
Место: #1 | Слот: gpt-6.1-sol-high | Семейство: OpenAI | Транспорт: codex
Режим: code | Раунд: r1 | Шляпа: Скептик (ищет ошибки, гонки, утечки дескрипторов, нарушения F-001..F-010 и инвариантов)
seed_recheck_duty: да
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

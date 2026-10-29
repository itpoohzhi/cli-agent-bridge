# Consensus Ledger — Code Teamlead Council (`COUNCIL` R1 + D1)

- **Run ID:** `agy-image-input-fix-20261029`
- **Artifact:** `teamlead/package.md` (`sha256=8cc5276d7cbf0c55f1b3473b7e93a08a9248a577a41e96868d1cb6bb85aac689`)
- **R1 Round Directory:** `panel/council/r1` (`round_kind=blind`, `prior_ledger_sha256=9ad7f7cade0079bbe1d64173b01239fdb463f5fe94c70c50d1230f3d0b5a6e69`)
- **D1 Round Directory:** `panel/council/r2` (`round_kind=d1`, `constrained_mode=3of3_derangement`)
- **D1 Seats:**
  - `Seat 1`: `muse-wonder-full-1.0` (`Meta`, `muse`) — `ОБЩИЙ ВЕРДИКТ: ACCEPT` (`POSITIONS: 5/5`, `FINDINGS_COMPLETE: YES`)
  - `Seat 2`: `gpt-6.1-sol-high` (`OpenAI`, `codex`) — `ОБЩИЙ ВЕРДИКТ: NEEDS_WORK` (`POSITIONS: 5/5`, `FINDINGS_COMPLETE: YES`)
  - `Seat 3`: `gemini-4-argon-high` (`Google`, `agy`) — `ОБЩИЙ ВЕРДИКТ: ACCEPT` (`POSITIONS: 5/5`, `FINDINGS_COMPLETE: YES`)

## Summary Table (R1 -> D1)

| ID | Seat 1 (`muse-wonder-full-1.0`, Meta) | Seat 2 (`gpt-6.1-sol-high`, OpenAI) | Seat 3 (`gemini-4-argon-high`, Google) | Итоговый приоритет (outcome) | Статус (status) |
|---|---|---|---|---|---|
| F-001 | AMEND (non-blocking) | DISAGREE (blocking) | AMEND (non-blocking) | non-blocking | DOWNGRADED_BY_MAJORITY |
| F-002 | AMEND (non-blocking) | AMEND (non-blocking) | AMEND (non-blocking) | non-blocking | AGREED |
| F-003 | AMEND (non-blocking) | DISAGREE (blocking) | AMEND (non-blocking) | non-blocking | DOWNGRADED_BY_MAJORITY |
| F-004 | AGREE (non-blocking) | AGREE (non-blocking) | AGREE (non-blocking) | non-blocking | AGREED |
| F-005 | AGREE (non-blocking) | AGREE (non-blocking) | AGREE (non-blocking) | non-blocking | AGREED |

### F-001
- priority: non-blocking
- status: DOWNGRADED_BY_MAJORITY
- outcome: non-blocking
- location: `bridges/agy-bridge/server.py` (`_serve_sse`, `_run_once`, `L3179, L3628-L3641, L3762, L3809, L3825-L3828`)
- issue: В потоковом режиме (`stream=true`) при отключении флага `IMAGE_INPUT_ENABLED` во время ожидания слота (`F-002`) или при `ImageSpoolError` ответ уходит терминальным SSE-событием `data: {"error": {..., "code": 400|500}}` поверх уже отправленного HTTP 200.
- fix: Первичная валидация `_collect_images` в `do_POST` (`server.py:3628-3641`) выполняется до `_serve_sse` и возвращает чистый HTTP 400 JSON. Ранний старт SSE до `_acquire_slot()` необходим для отправки `: keepalive` во время ожидания слота. Квалифицированным большинством `2/3` независимых семейств (`Meta` + `Google`) переведено в `non-blocking` остаточный риск / бэклог (отдельный регрессионный тест позднего SSE-отказа).
- votes: R1 seat1=RAISE(blocking) | D1 seat1=AMEND(non-blocking) | D1 seat2=DISAGREE(blocking) | D1 seat3=AMEND(non-blocking)

### F-002
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `bridges/agy-bridge/server.py` (`_collect_images`, `_stage_images`, `L911, L925, L944-L961`)
- issue: Внутри цикла `_stage_images` локальная переменная `data` сохраняет ссылку на декодированные байты текущей картинки до следующей итерации / выхода из `_stage_images`.
- fix: До `_acquire_slot()` в `_collect_images` (`server.py:911, 925`) выполняется `del raw` и хранится `"data": b""` (0 байт декодированных картинок в очереди слота), а `_stage_images` завершается до запуска `Run(...)`. Единогласно (`3/3` независимых семейств: `Meta`, `OpenAI`, `Google`) переведено в `non-blocking`.
- votes: R1 seat1=RAISE(blocking) | D1 seat1=AMEND(non-blocking) | D1 seat2=AMEND(non-blocking) | D1 seat3=AMEND(non-blocking)

### F-003
- priority: non-blocking
- status: DOWNGRADED_BY_MAJORITY
- outcome: non-blocking
- location: `tests/test_agy_bridge_resilience.py` (`test_res01_concurrent_turns_bounded_by_slots_without_fd_or_dir_leaks`, `L5247-L5313`)
- issue: В `test_res01` проверяются параллельные слоты `MAX_PARALLEL=2`, отсутствие утечек FD и очистка `img-*`, но используются компактные фикстуры без отдельного измерения латентности на 20 МБ.
- fix: Границы 20 МБ и отсечение до `b64decode` детерминированно покрыты `test_img04`, `test_img05` и `test_f003`; отказ от жёсткого wall-clock таймера в `test_res01` исключает флаки в CI. Квалифицированным большинством `2/3` независимых семейств (`Meta` + `Google`) переведено в `non-blocking` (живой замер выполняется на этапе L3 `VER-010`).
- votes: R1 seat1=RAISE(blocking) | D1 seat1=AMEND(non-blocking) | D1 seat2=DISAGREE(blocking) | D1 seat3=AMEND(non-blocking)

### F-004
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `bridges/agy-bridge/server.py` (`_sweep_workspace`, `L3914-L3918`)
- issue: Счётчик `removed` в `_sweep_workspace` инкрементируется после `shutil.rmtree(..., ignore_errors=True)` без перепроверки факта удаления.
- fix: Единогласно (`3/3`) подтверждено как неблокирующее замечание наблюдаемости (`MINOR`, `non-blocking`).
- votes: R1 seat1=RAISE(non-blocking) | D1 seat1=AGREE(non-blocking) | D1 seat2=AGREE(non-blocking) | D1 seat3=AGREE(non-blocking)

### F-005
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- location: `bridges/agy-bridge/fleet.json` (`technical_ref`, `L15, L18`)
- issue: В справочных строках `models_source` и `effort_ladders` внутри `technical_ref` упоминается `1.3.1` при `agy_version: "1.4.9"`.
- fix: Единогласно (`3/3`) подтверждено как неблокирующее документационное замечание (`MINOR`, `non-blocking`), не влияющее на рантайм и проверку `images.proof`.
- votes: R1 seat3=RAISE(non-blocking) | D1 seat1=AGREE(non-blocking) | D1 seat2=AGREE(non-blocking) | D1 seat3=AGREE(non-blocking)

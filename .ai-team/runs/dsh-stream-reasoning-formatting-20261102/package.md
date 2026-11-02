# Пакет приёмки: Модернизация тестирования и исправление стриминга cli-agent-bridge (Cycle 2)

## Метаданные
- **Task ID:** `REQ-DSH-STREAM-REASONING-FORMATTING`
- **Run ID:** `dsh-stream-reasoning-formatting-20261102`
- **Cycle:** `2` (Rework по замечаниям Совета Тимлидов RW-009..RW-019)
- **Пресет:** `panel-analyst-teamlead`
- **Дата:** 2026-11-02
- **Статус:** `VERIFIED_READY_FOR_COUNCIL_CYCLE_2`

---

## 1. Суть выполненных доработок

1. **Устранение склеивания строк в стриминге (REQ-001 / ADR-1):**
   - В `Run.offer_content` добавлена проверка границ шагов: при смене шага планировщика (`_last_step_index != step_index`) и наличии ранее выданного текста буфер предваряется `\n\n`, если он не завершался переводом строки.
   - Исключено слияние предложений и токенов на границах действий (дефект «...данных.Проверяю вывод...»).

2. **Устранение лавины префиксов гейтов в арбитре (REQ-002 / ADR-2):**
   - В `_ContentArbiter._scan` исправлено префиксное сопоставление: кандидат сопоставляется только при точном равенстве `text == candidate` либо если входящий текст является истинным продолжением `text.startswith(candidate)`.
   - Шаг с валидным индексом (`idx is not None`) изолирован от ошибочного алиасинга с более длинным текстом чужого старого шага.
   - Полностью ликвидирована циклическая заморозка шагов и повторная эмиссия префиксов `[гейт оркестрации: активен...`.

3. **Семантическая изоляция Reasoning при вызовах инструментов (REQ-003 / ADR-3 / RW-016):**
   - В `_TranscriptTail._emit_record`: при наличии `tool_calls` преамбула шага направляется в `choices[0].delta.reasoning_content`.
   - Добавлен трекер `self._preambles_emitted: set[int]`: исключена повторная эмиссия преамбул в reasoning при перечитывании файла транскрипта (`_in_rewrite`).
   - Поле `choices[0].delta.content` остаётся чистым до получения финального ответа без вызовов инструментов.
   - Аккордеон мышления `<Think>` в UI DeepSeek Harness остаётся активным на протяжении всех промежуточных шагов агента.

4. **Синхронизация Wire и Reconcile без ложной дивергенции (RW-015 / F-002):**
   - В `Run.reconcile_result`: сверка финального текста выполняется относительно фактически отправленного в сокет потока `_content_emitted_wire` (с учётом разделителей `\n\n`). Исключено ложное срабатывание дивергенции арбитра (`last_result_diverged=True`) и повторный терминальный выброс полного текста ответа клиенту.

5. **Нормализация рантайм-флагов (REQ-004 / ADR-4):**
   - В `_parse_runtime_flags` поддержан алиас `AGY_GRACEFUL_TIMEOUT_FINISH_REASON`, нормализация `max_tokens` -> `length` и сброс невалидных значений в дефолтный `stop`. Все 13 подтестов `GracefulTimeoutFinishReasonTests` зелёные.

6. **Сквозной синтетический e2e сьют L2 (REQ-005 / ADR-5 / RW-017):**
   - В `tests/test_stream_formatting_and_subagents.py` реализовано 4 сквозных теста: проверка разграничения Markdown строк `\n\n`, защита от зацикливания префиксов, изоляция tool-преамбул в reasoning и тест дедупликации преамбул / синхронизации reconcile с wire (`test_e2e_reconcile_wire_sync_and_preamble_dedup`). 4/4 passed (0.02s).

7. **Универсальный смоук-раннер моделей L3 с TTFT и Fail-Fast (REQ-006 / ADR-6 / RW-018 / RW-019 / F-013):**
   - В `scripts/smoke_models.py` удалён фиктивный список моделей: скрипт строго падает с `FileNotFoundError` и кодом выхода 1 при отсутствии канона `models.md`.
   - Реализован потоковый смоук со стримингом (`stream=True`), чтением чанков SSE, замером TTFT по первому чанку `content`/`reasoning_content` и валидацией маркера завершения `[DONE]`. Проведено успешное живое тестирование на хаб-мосте `127.0.0.1:9882`.

8. **Регламент тестирования в AGENTS.md (REQ-007 / ADR-7):**
   - В `/Users/aazhiry1/work/src/cli-agent-bridge/AGENTS.md` зафиксирован трехуровневый регламент (L1 Unit / L2 Synthetic E2E / L3 Smoke Runner).

---

## 2. Матрица верификации (Verification Surface)

| ID | Требование | Метод проверки | Ожидание | Фактический результат |
|---|---|---|---|---|
| **VER-001** | REQ-001, REQ-004 | `pytest tests/test_agy_bridge_resilience.py -k test_step_boundary_newline_separation` | PASS | **PASS (0.16s)** |
| **VER-002** | REQ-002, REQ-004 | `pytest tests/test_agy_bridge_resilience.py -k test_arbiter_no_prefix_repetition_on_divergence` | PASS | **PASS (0.16s)** |
| **VER-003** | REQ-003, REQ-004, RW-016 | `pytest tests/test_agy_bridge_resilience.py -k test_tool_preamble_isolated_to_reasoning` | PASS | **PASS (0.16s)** |
| **VER-004** | REQ-005, RW-017 | `pytest tests/test_stream_formatting_and_subagents.py -v` | PASS | **PASS (4/4 passed, 0.02s)** |
| **VER-005** | REQ-006, RW-018 | `python3 scripts/smoke_models.py --dry-run` | PASS | **PASS (20 моделей валидировано)** |
| **VER-006** | RW-018 | `python3 scripts/smoke_models.py --models-md /nonexistent/models.md --dry-run` | FAIL (exit 1) | **PASS (FileNotFoundError, exit 1)** |
| **VER-007** | RW-019, F-013 | `python3 scripts/smoke_models.py --live --model claude-sonnet-5-5` | PASS (STREAM_OK) | **PASS (STREAM_OK, TTFT 2.14s..9.67s)** |
| **VER-008** | REQ-007 | `grep -q "Регламент комплексного тестирования" AGENTS.md` | PASS | **PASS (раздел зафиксирован)** |
| **FULL-L1** | Регрессия моста | `pytest tests/test_agy_bridge_resilience.py -q` | PASS | **PASS (346 passed, 737 subtests, 0:03:38)** |

---

## 3. Затронутые файлы
- `bridges/agy-bridge/server.py`
- `tests/test_stream_formatting_and_subagents.py`
- `scripts/smoke_models.py`
- `AGENTS.md`
- `analysis/bridge-testing-modernization/` (артефакты панели аналитиков)
- `.ai-team/runs/dsh-stream-reasoning-formatting-20261102/` (архитектурный пакет, спецификация и пакет приёмки)

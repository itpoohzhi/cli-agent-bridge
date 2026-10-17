# Бриф разработчика (Coder): Устранение замечаний Code Council R1 (Rework)

Ровно один путь скилла роли: `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md`

## Уже известно
- **repo_root:** `/Users/aazhiry1/work/src/cli-agent-bridge`
- **run_dir:** `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014`
- **branch:** `dev`
- **target_files:**
  - `bridges/muse-bridge/server.py`
  - `tests/test_muse_bridge_killpg.py`
  - Зеркало в DSH: `/Users/aazhiry1/.dsh/bridges/muse-bridge/server.py`
- **panel_rework_brief:**
  `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/handoff/panel-rework-brief.json`
- **spec_and_diff:**
  - `arch-spec.md` (в run_dir)
  - `code-diff.patch` (в run_dir)
- **prior_findings (Code Council R1):**
  - **F-001 (RW-001):** В `bridges/muse-bridge/server.py:941` поиск tool-ответов поглощает результаты всех эпизодов при повторном `tool_call_id`, теряя обязательный хвостовой assistant+tool эпизод.
  - **F-002 (RW-002):** В `server.py:289` усечение ошибки до 160 символов срезает маркер hard threshold при длинном префиксе, блокируя retry.
  - **F-003 (RW-003):** В `server.py:232` редакция секретов перед удалением отражённых сообщений ломает совпадение подстрок.
  - **F-004 (RW-004):** В `server.py:2267` перехват `ServeUnavailable` логирует исключение до очистки отражённого промпта.
  - **F-005 (FU-001):** Фаза C прунинга квадратична O(n^2) при повторной сборке промпта.
  - **F-006 (FU-002):** Развести оценку токенов прунинга от `usage.prompt_tokens`.

## Мост для субагентов
Входы даны выше; на диск за ними не ходи; стартовый корень поиска ∈ {$HOME, /Users/<user>, /} запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни ASK.

## Задачи реализации (строго по panel-rework-brief.json)

1. **RW-001 (Атомарность tool-связок внутри конкретного эпизода):**
   - В `bridges/muse-bridge/server.py` в функции `_partition_units`:
     При сборе `role == "tool"` для `assistant(tool_calls)` ограничить поиск текущим эпизодом (до следующего `assistant` или `user`), чтобы одинаковый `tool_call_id` из разных эпизодов не поглощал чужие результаты.
   - Гарантировать, что последний хвостовой эпизод `assistant(tool_calls) + tool` после последнего `user` всегда корректно сохраняется в обязательный блок (`tail_mandatory`).

2. **RW-002 (Детекция hard threshold до усечения ошибки):**
   - В `bridges/muse-bridge/server.py` в `_turn_diagnostics` и `ServeRun.execute`:
     Проверять наличие маркера `HARD_THRESHOLD_ERR_SUBSTR` (`context compaction replacement still exceeds the hard threshold`) по сырому/необрезанному тексту ошибки до усечения до 160/300 символов.
     Сохранять/пробрасывать флаг `is_hard_threshold` наружу в `ServeRun.execute` / `Handler`, чтобы длинный префикс Meta не маскировал превышение порога.

3. **RW-003 (Симметричное удаление отражённого промпта при наличии секретов):**
   - В `bridges/muse-bridge/server.py` в `_diagnostic_text` и на финальной границе очистки ошибки в `Handler`:
     Обеспечить удаление отражённых тел сообщений/промпта независимо от порядка редакции секретов: например, удалять как исходные строки, так и их версии после `_redact_secrets`, либо удалять отражённые части до и после маскирования. Ни приватный текст пользователя (`BODY_PRIVATE_CANARY`), ни секреты не должны оставаться в ответе 502, SSE-ошибке или логах.

4. **RW-004 (Безопасное логирование при ServeUnavailable fallback):**
   - В `bridges/muse-bridge/server.py` в строке 2267 (`except ServeUnavailable as exc:`):
     Санитизировать `exc` от отражённого промпта/сообщений перед вызовом `_log`, либо логировать безопасное фиксированное сообщение `_log("serve unavailable, fallback exec")` без сырого тела исключения.

5. **FU-001 (Оптимизация O(n) в Фазе C прунинга):**
   - В `_prune_messages` оптимизировать цикл Фазы C: предвычислять оценку токенов для каждого отрендеренного юнита, чтобы исключить квадратичную повторную сборку промпта на каждом шаге.

6. **FU-002 (Разделение метрик usage и бюджета прунинга):**
   - Убедиться, что `_estimate_tokens` используется строго для принятия решений о прунинге, а не раздувает клиентские метрики `usage.prompt_tokens`.

7. **Регрессионные тесты (tests/test_muse_bridge_killpg.py):**
   - Добавить тесты на каждый из пунктов RW-001..RW-004 (T-24..T-27):
     * Тест T-24: повторяющийся `tool_call_id` в разных эпизодах истории не теряет хвостовой эпизод.
     * Тест T-25: ошибка с префиксом >160 символов перед hard threshold маркером корректно триггерит context retry.
     * Тест T-26: сообщение с `BODY_PRIVATE_CANARY api_key=secret` не утекает в ошибку при отражении.
     * Тест T-27: при `ServeUnavailable` с отражённым телом лог не содержит приватного текста.

8. **Синхронизация и проверки:**
   - Скопировать обновлённый `bridges/muse-bridge/server.py` в `/Users/aazhiry1/.dsh/bridges/muse-bridge/server.py`.
   - Запустить тесты: `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py`.
   - Проверить линтеры: `ruff check bridges/muse-bridge/server.py tests/test_muse_bridge_killpg.py`.
   - Обновить `.ai-team/runs/muse-wonder-foreign-session-20261014/code-diff.patch`:
     `git diff bridges/muse-bridge/server.py tests/test_muse_bridge_killpg.py > .ai-team/runs/muse-wonder-foreign-session-20261014/code-diff.patch`.
   - Вывести краткий отчёт с подтверждением всех проверок.

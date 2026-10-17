# Бриф судьи Кодового Совета (COUNCIL-ACCEPT, раунд R2, место k=2)

ВАЖНО: Ты — листовой судья Кодового Совета (НЕ оркестратор). НЕ открывай контур `cel`, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов (`Task`, `invoke_subagent`, `muse`, `droid`, `claude`, `codex`) — прочитай оцениваемый diff и связанные артефакты и выдай финальный вердикт напрямую в этом ответе!

## Твоя роль и шляпа
- Место: `k=2`, модель/слот: `claude-sonnet-5-5-high` (`Anthropic`)
- Назначенная шляпа: **Визионер** — оценивай архитектурное соответствие, долговечность решений, чистоту API, масштабируемость и производительность (включая устранение O(n^2) задержек в Phase C и разведение клиентских метрик usage и бюджета прунинга).
- Оценивай решение по всем 6 критериям рубрики (шляпа задаёт твой главный фокус, но не сужает проверку).

## Задача и контекст изменений
Устранение сбоя Muse Wonder в чужих длинных сессиях DSH (`639915 >= 460800 tokens`) и доработка по результатам Code Council R1:
1. **`ADR-001.1`:** `context_length` в `ALLOWED_MODELS` и `contextWindow` в профилях `cordis.patch.yml` выставлены в `400_000`.
2. **`ADR-001.2` (включая фикс RW-001):** Защитный прунинг истории `_prune_messages`:
   - Обязательный контекст: все `system`/`developer`, первый и последний `user`, замыкающая связка `assistant(tool_calls)` + `tool`.
   - В `_partition_units` сбор ответов `role == "tool"` ограничен текущим эпизодом assistant; повторные `tool_call_id` не поглощают чужие результаты, сохраняя хвостовой эпизод (`test_t24`).
   - Оптимизация Фазы C прунинга до $O(n)$ с предвычислением размеров единиц (`FU-001`).
3. **`ADR-001.3` (включая фикс RW-002):**
   - Детекция маркера `HARD_THRESHOLD_ERR_SUBSTR` выполняется по сырому необрезанному потоку ошибки до усечения диагностики до 160/300 символов, пробрасывая признак `hard_threshold` для context retry (`test_t25`).
4. **`ADR-001.4` (включая фиксы RW-003, RW-004):**
   - Добавлен `_sanitize_reflected`: симметричное удаление отражённого промпта и сообщений до и после `_redact_secrets` (`test_t26`).
   - Санитизация `ServeUnavailable` перед логированием fallback exec (`test_t27`).
   - Разделение оценщика токенов прунинга и клиентских метрик `usage.prompt_tokens` (`FU-002`).
5. **Тесты:** 28 unit-тестов в `tests/test_muse_bridge_killpg.py` (T-00..T-27), все 67 тестов файла проходят успешно (`67 passed`).

## Входные артефакты на диске
1. Главный оцениваемый артефакт: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/code-diff.patch` (sha256: `7ffec7e0b134308ae412ef1861fc8ba5b2ec222be2f33c0b538a7d1f5e55006e`)
2. Архитектурная спецификация: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/arch-spec.md`
3. Handoff реворка R1: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/handoff/panel-rework-brief.json`
4. Исходный код: `/Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py`, `tests/test_muse_bridge_killpg.py`

## Рубрика оценки (6 обязательных критериев)
Оцени каждый из 6 критериев (`PASS` / `NEEDS_WORK` / `RED_FLAG`) с конкретным обоснованием:
1. **Корректность и логика изменений (`correctness_and_logic`)**
2. **Соответствие контрактам и архитектуре (`contracts_and_architecture`)**
3. **Граничные случаи и отказоустойчивость (`edge_cases_and_resilience`)**
4. **Безопасность и отсутствие утечек (`security_and_secrets`)**
5. **Качество кода и чистота (`code_quality_and_cleanliness`)**
6. **Тестовое покрытие и верификация (`tests_and_verification`)**

Выведи сводку субрибрик:
- `SUB code: PASS|CONCERN|FAIL — <1 строка>`
- `SUB security: PASS|CONCERN|FAIL — <1 строка>`
- `SUB tests: PASS|CONCERN|FAIL — <1 строка>`
- `SUB contracts: PASS|CONCERN|FAIL — <1 строка>`

## ЖЁСТКИЙ ФОРМАТ ОТВЕТА (проверяется автоматом `verify_panel_proof.py`)
1. **Первые две непустые строки твоего ответа ОБЯЗАНЫ быть дословно:**
```
PANEL-NONCE: c27783b8a1d7ccbb
ARTIFACT-SHA256: 7ffec7e0b134308ae412ef1861fc8ba5b2ec222be2f33c0b538a7d1f5e55006e
```
Никакого текста ДО этих двух строк!
2. В теле ответа дай содержательный разбор (не менее 600 символов собственного текста) со шляпой `Визионер`, все 6 пунктов рубрики и строки `SUB ...`. Для промежуточных оценок критериев пиши `Критерий N — PASS`.
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНЫ быть строго одной из трёх строк:**
`ОБЩИЙ ВЕРДИКТ: ACCEPT`
или
`ОБЩИЙ ВЕРДИКТ: NEEDS_WORK`
или
`ОБЩИЙ ВЕРДИКТ: RED_FLAG`

---
PANEL-NONCE: c27783b8a1d7ccbb
ARTIFACT-SHA256: 7ffec7e0b134308ae412ef1861fc8ba5b2ec222be2f33c0b538a7d1f5e55006e
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: c27783b8a1d7ccbb» и «ARTIFACT-SHA256: 7ffec7e0b134308ae412ef1861fc8ba5b2ec222be2f33c0b538a7d1f5e55006e».

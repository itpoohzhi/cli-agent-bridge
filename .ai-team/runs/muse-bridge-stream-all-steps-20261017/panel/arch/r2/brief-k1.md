# Бриф судьи Архитектурного Совета (ARCHITECTURE-REVIEW, раунд R2, место k=1)

ВАЖНО: Ты — листовой судья Архитектурного Совета (НЕ оркестратор). НЕ открывай контур `cel`, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов (`Task`, `invoke_subagent`, `muse`, `droid`, `claude`, `codex`) — прочитай артефакты из рабочего каталога и выдай финальный вердикт напрямую в этом ответе!

## Твоя роль и шляпа
- Место: `k=1`, модель/слот: `gemini-4-argon-high` (`Google`)
- Назначенная шляпа: **Реалист** — оценивай практическую осуществимость, соотношение затрат и выгод, эксплуатационную надёжность и соответствие кодовой базе `cli-agent-bridge`.
- Оценивай решение по всем 6 критериям рубрики (шляпа задаёт твой главный фокус, но не сужает проверку).

## Цель задачи, Red Lines
Задача `muse-bridge-stream-all-steps-20261017` (`S2`, тикет `EYE-33873`, пресет `analyst-teamlead`): обеспечить сквозной live-стриминг всех шагов рассуждений модели (`summary.0..N`) и индикаторов выполнения инструментов (`toolCall`) в мосте `bridges/muse-bridge/server.py` для DeepSeek Harness:
1. **`AD-001`:** Снятие искусственной заморозки live-стриминга (`_live_frozen`), непрерывная отправка всех дельт `summary.0..N` в `delta.reasoning_content` по мере поступления от Meta CLI ServeRun.
2. **`AD-002`:** Трансляция текстовых маркеров прогресса запуска (`\n\n[Вызов инструмента: {tool_name}]\n`) и завершения (`\n[Инструмент {tool_name} завершён]\n`) в `delta.reasoning_content` для немедленной видимости в UI DSH. Санитизация имени: `^[A-Za-z0-9_.:-]{1,64}$`.
3. **`AD-003`:** Опережающий сброс накопленного буфера reasoning перед отправкой кадра ошибки и закрытием соединения в `_send(502)` при таймаутах (`TIMEOUT_S = 1800 - 35 = 1765 с`) или сбоях.

## Устранённые замечания Раунда 1 (F1..F6)
- **F1 & F2:** Модель аккумулятора и изоляция блоков: в `ServeRun` дельты индексируются составным ключом `(item_id, idx)` в `self._reasoning_items`, исключая затирание при 150+ параллельных/последовательных вызовах инструментов.
- **F3:** Устойчивость к backpressure: сетевые ошибки live-стриминга reasoning не приводят к `_kill_current_run`; флаг `_live_degraded = True` деградирует live-вывод, сохраняя буфер для финального ответа.
- **F4:** Опережающий сброс reasoning перед ошибкой в `_send(502)` реализован через `get_accumulated_reasoning()` у текущего `_current_serve_run`.
- **F5:** Верификация в ADR исправлена: импорт моста через `sys.path.insert`, ожидание `passed` в `pytest`.
- **F6:** Имена инструментов санитизируются по строгому regex, маркеры не просачиваются в non-streaming ответы.

**Red lines (инварианты):**
- Модифицируется `bridges/muse-bridge/server.py` и регрессионные тесты в `tests/test_muse_bridge_killpg.py`; никаких внешних зависимостей вне stdlib Python; полная потокобезопасность под `self._wlock`; сохранение OpenAI-совместимого SSE контракта.

## Входные артефакты на диске (в рабочем каталоге)
1. Главный оцениваемый артефакт: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-stream-all-steps-20261017/architecture/architecture-packet.json` (sha256: `75eab5226b549adc06c133e6072c26054d825784ba7bf3c48db903ff61e0e172`)
2. Спецификация: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-stream-all-steps-20261017/architecture/arch-spec.md`
3. ADR: `/Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0004-muse-live-streaming-all-steps.md`
4. Материалы системного анализа: `/Users/aazhiry1/work/src/cli-agent-bridge/analysis/muse-bridge-stream-all-steps/handoff-architect.md`, `evidence-ledger.md`

## Рубрика оценки (6 обязательных критериев)
Оцени каждый из 6 критериев (`PASS` / `NEEDS_WORK` / `RED_FLAG`) с конкретным обоснованием:
1. **Проблема и границы (`problem_and_boundaries`)**
2. **Контракты и инварианты (`contracts_and_invariants`)**
3. **Риски, отказы и деградация (`risks_and_degradation`)**
4. **Безопасность и секреты (`security_and_secrets`)**
5. **Наблюдаемость и эксплуатация (`observability_and_ops`)**
6. **План реализации, миграции и тестов (`implementation_and_test_plan`)**

Выведи сводку субрибрик:
- `SUB architecture: PASS|CONCERN|FAIL — <1 строка>`
- `SUB security: PASS|CONCERN|FAIL — <1 строка>`
- `SUB performance: PASS|CONCERN|FAIL — <1 строка>`
- `SUB tests: PASS|CONCERN|FAIL — <1 строка>`

## ЖЁСТКИЙ ФОРМАТ ОТВЕТА (проверяется автоматом `verify_panel_proof.py`)
1. **Первые две непустые строки твоего ответа ОБЯЗАНЫ быть дословно:**
```
PANEL-NONCE: 59e92b5f5baad00d
ARTIFACT-SHA256: 75eab5226b549adc06c133e6072c26054d825784ba7bf3c48db903ff61e0e172
```
Никакого текста ДО этих двух строк!
2. В теле ответа дай содержательный разбор (не менее 600 символов собственного текста) со шляпой `Реалист`, все 6 пунктов рубрики и строки `SUB ...`. Для промежуточных оценок критериев пиши `Критерий N — PASS`.
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНА быть строго одной из трёх строк:**
`ОБЩИЙ ВЕРДИКТ: ACCEPT`
или
`ОБЩИЙ ВЕРДИКТ: NEEDS_WORK`
или
`ОБЩИЙ ВЕРДИКТ: RED_FLAG`

---
PANEL-NONCE: 59e92b5f5baad00d
ARTIFACT-SHA256: 75eab5226b549adc06c133e6072c26054d825784ba7bf3c48db903ff61e0e172
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 59e92b5f5baad00d» и «ARTIFACT-SHA256: 75eab5226b549adc06c133e6072c26054d825784ba7bf3c48db903ff61e0e172».

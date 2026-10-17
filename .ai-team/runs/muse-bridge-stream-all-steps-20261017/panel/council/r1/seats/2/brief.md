# Бриф судьи Кодового Совета (COUNCIL-REVIEW, раунд R1, место k=2)

ВАЖНО: Ты — листовой судья Кодового Совета (НЕ оркестратор). НЕ открывай контур `cel`, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов (`Task`, `invoke_subagent`, `muse`, `droid`, `claude`, `codex`) — прочитай артефакты из рабочего каталога и выдай финальный вердикт напрямую в этом ответе!

## Твоя роль и шляпа
- Место: `k=2`, модель/слот: `gemini-4-argon-high` (`Google`)
- Назначенная шляпа: **Визионер** — оценивай долгосрочную архитектурную чистоту, расширяемость для последующих моделей и инструментов, непротиворечивость контрактов SSE с DeepSeek Harness и клиентами OpenAI API.
- Оценивай решение по всем 6 критериям рубрики (шляпа задаёт твой главный фокус, но не сужает проверку).

## Цель задачи, Red Lines и реализация Coder
Задача `muse-bridge-stream-all-steps-20261017` (`S2`, тикет `EYE-33873`, пресет `analyst-teamlead`): обеспечить сквозной live-стриминг всех шагов рассуждений модели (`summary.0..N`) и индикаторов выполнения инструментов (`toolCall`) в мосте `bridges/muse-bridge/server.py` для DeepSeek Harness:
1. **`AD-001` (Reasoning Live Streaming):**
   - В `ServeRun` полностью снята искусственная заморозка стриминга (`self._live_frozen = True` удален).
   - Все поступающие блоки `summary.*` передаются в SSE поток `delta.reasoning_content` в реальном времени.
   - В `ServeRun` дельты индексируются составным ключом `(item_id, idx)` в `self._reasoning_items` под `self._acc_lock = threading.Lock()`, отслеживая инкрементальные длины в `self._item_lengths[(item_id, idx)]`.
2. **`AD-002` (Tool Call Markers & Санитизация):**
   - При старте инструмента отправляется маркер: `\n\n[Вызов инструмента: {tool_name}]\n` в `delta.reasoning_content`.
   - При завершении инструмента отправляется: `\n[Инструмент {tool_name} завершён]\n` в `delta.reasoning_content`.
   - Имя инструмента санитизируется регулярным выражением `^[A-Za-z0-9_.:-]{1,64}$`. При недопустимых символах выполняется замена на `_` либо fallback на `tool`.
   - Маркеры транслируются ТОЛЬКО при `stream: true`. В `stream: false` маркеры не добавляются.
   - Синхронизирован буфер отправленного текста `_live_sent_text` и финальный `reasoning` в `_send_sse`, исключая ложное срабатывание `reasoning_diverged` и повторную отправку полного текста рассуждений.
3. **`AD-003` (Early Flush перед 502 & Защита от backpressure):**
   - В `_send(502)` (таймаут `TIMEOUT_S = 1800 - 35 = 1765 с` или сбой процесса) через `self._current_serve_run.get_accumulated_reasoning()` опережающе сбрасывается весь неотправленный остаток мыслей в SSE перед отправкой кадра ошибки и закрытием соединения.
   - В `_sse_write(self, data: str, fatal: bool = True) -> bool`: для live-записи reasoning вызовы производятся с `fatal=False`. При задержке или ошибке сокета выставляется `self._live_degraded = True`, НЕ вызывая `_kill_current_run()`. Ход модели продолжается, а накопленный буфер отдается в финале.
4. **S4 (Ретраи):**
   - При создании нового `ServeRun` в повторной попытке (`run_attempt`) вызывается `_reset_live_for_attempt()`, сбрасывающий `_live_sent_text = ""` и `_live_degraded = False`.
5. **Тесты и качество кода:**
   - 122/122 unit-тестов зелёные в `tests/test_muse_bridge_killpg.py` (добавлено 10 новых регрессионных тестов).
   - Ruff linter: All checks passed.
   - Basedpyright: 0 errors.

**Red lines (инварианты):**
- Модифицируется `bridges/muse-bridge/server.py` и регрессионные тесты в `tests/test_muse_bridge_killpg.py`; никаких внешних зависимостей вне stdlib Python; полная потокобезопасность под `self._wlock` и `self._acc_lock`; сохранение OpenAI-совместимого SSE контракта.

## Входные артефакты на диске (в рабочем каталоге)
1. Главный оцениваемый артефакт (Council Package с полным git diff): `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-stream-all-steps-20261017/panel/council-package.md` (sha256: `69fac476bef77530cc378f4958f0706be96270bc92af1b230f473873608d7f80`)
2. Исходный код: `/Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py`
3. Набор тестов: `/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_muse_bridge_killpg.py`
4. Архитектурный ADR: `/Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0004-muse-live-streaming-all-steps.md`
5. Архитектурная спецификация: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-bridge-stream-all-steps-20261017/architecture/arch-spec.md`

## Рубрика оценки (6 обязательных критериев)
Оцени каждый из 6 критериев (`PASS` / `NEEDS_WORK` / `RED_FLAG`) с конкретным построчным обоснованием:
1. **Корректность (`correctness`)** — соответствие task envelope, точность реализации AD-001..AD-003, устранение дефектов S1..S6.
2. **Полнота (`completeness`)** — поддерживаемость, читабельность, покрытие edge-cases, отсутствие утечек состояния.
3. **Реализуемость (`feasibility`)** — эксплуатационная надёжность, отсутствие взаимоблокировок под замками `_acc_lock` и `_wlock`.
4. **Риски (`risks`)** — достаточность тестов (122 теста), риск регрессий существующего функционала (`killpg`, `ApprovalPolicy`, context compaction).
5. **Альтернативы (`alternatives`)** — простота и минимализм решения в рамках stdlib Python без лишних внешних зависимостей.
6. **Соответствие контексту (`context_conformance`)** — архитектурные границы, соблюдение OpenAI-совместимого контракта SSE и соглашений проекта.

Выведи сводку субрибрик:
- `SUB architecture: PASS|CONCERN|FAIL — <1 строка>`
- `SUB security: PASS|CONCERN|FAIL — <1 строка>`
- `SUB performance: PASS|CONCERN|FAIL — <1 строка>`
- `SUB tests: PASS|CONCERN|FAIL — <1 строка>`

## ЖЁСТКИЙ ФОРМАТ ОТВЕТА (проверяется автоматом `verify_panel_proof.py`)
1. **Первые две непустые строки твоего ответа ОБЯЗАНЫ быть дословно:**
```
PANEL-NONCE: 27f0c3f46acc8a01
ARTIFACT-SHA256: 69fac476bef77530cc378f4958f0706be96270bc92af1b230f473873608d7f80
```
Никакого текста ДО этих двух строк!
2. В теле ответа дай содержательный разбор (не менее 600 символов собственного текста) со шляпой `Визионер`, все 6 пунктов рубрики (пиши `Критерий N — PASS`) и строки `SUB ...`.
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНЫ быть строго одной из трёх строк:**
`ОБЩИЙ ВЕРДИКТ: ACCEPT`
или
`ОБЩИЙ ВЕРДИКТ: NEEDS_WORK`
или
`ОБЩИЙ ВЕРДИКТ: RED_FLAG`

---
PANEL-NONCE: 27f0c3f46acc8a01
ARTIFACT-SHA256: 69fac476bef77530cc378f4958f0706be96270bc92af1b230f473873608d7f80
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 27f0c3f46acc8a01» и «ARTIFACT-SHA256: 69fac476bef77530cc378f4958f0706be96270bc92af1b230f473873608d7f80».

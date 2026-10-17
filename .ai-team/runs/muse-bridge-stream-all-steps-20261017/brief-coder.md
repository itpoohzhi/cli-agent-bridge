# Бриф Coder (разработка фичи live-стриминга muse-bridge)

~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md

## Задача и контекст
Задача: `EYE-33873` (тикет `muse-bridge-stream-all-steps-20261017`, критичность S2).
Цель: обеспечить сквозной live-стриминг всех шагов рассуждений модели (`summary.0..N`) и индикаторов выполнения инструментов (`toolCall`) в мосте `bridges/muse-bridge/server.py` для DeepSeek Harness.
Модель: `muse-wonder-full-1.0` (`Meta`), effort: `high`.
Архитектурный совет R2 официально пройден с вердиктом PASS (квитанция `receipts/arch-panel.json`, `pol-receipt/1`, sha256 пакета `75eab5226b549adc06c133e6072c26054d825784ba7bf3c48db903ff61e0e172`).

## Входные артефакты
- ADR: `docs/adr/0004-muse-live-streaming-all-steps.md`
- Arch Spec: `.ai-team/runs/muse-bridge-stream-all-steps-20261017/architecture/arch-spec.md`
- Пакет: `.ai-team/runs/muse-bridge-stream-all-steps-20261017/architecture/architecture-packet.json`
- Исходный код моста: `bridges/muse-bridge/server.py`
- Тесты моста: `tests/test_muse_bridge_killpg.py`
- Замечания судьи-скептика: `.ai-team/runs/muse-bridge-stream-all-steps-20261017/panel/arch/r2/seats/2/verdict.md`

## Требования к реализации (AD-001..AD-003 и замечания S1..S6)
1. **AD-001 (Reasoning Live Streaming):**
   - В классе `ServeRun` полностью снять искусственную заморозку стриминга: удалить `self._live_frozen = True`.
   - Непрерывно отправлять все дельты рассуждений `summary.0..N` в реальном времени через `delta.reasoning_content`.
   - В `ServeRun` хранить дельты по составному ключу `(item_id, idx)` в `self._reasoning_items` под `self._acc_lock = threading.Lock()`. Отслеживать инкрементальные длины в `self._item_lengths[(item_id, idx)]`.

2. **AD-002 (Tool Call Markers & Санитизация):**
   - При старте инструмента отправлять маркер: `\n\n[Вызов инструмента: {tool_name}]\n` в `delta.reasoning_content`.
   - При завершении инструмента отправлять: `\n[Инструмент {tool_name} завершён]\n` в `delta.reasoning_content`.
   - Санитизировать `tool_name` регулярным выражением `^[A-Za-z0-9_.:-]{1,64}$`. Если имя недопустимо, пусто или None — заменять недопустимые символы на `_` или использовать fallback `tool`.
   - Маркеры транслировать ТОЛЬКО при `stream: true`. Не допускать их попадания в нестриминговые ответы.
   - Учесть замечание S2: синхронизировать буфер отправленного текста `_live_sent_text` и финальный `reasoning` в `_send_sse`, чтобы исключить ложное срабатывание `reasoning_diverged` и повторную отправку полного текста рассуждений.

3. **AD-003 (Early Flush перед 502 & Защита от backpressure S1):**
   - В `_send(502)` (таймаут `TIMEOUT_S = 1800 - 35 = 1765 с` или сбой процесса) через `self._current_serve_run.get_accumulated_reasoning()` опережающе сбрасывать весь неотправленный остаток мыслей в SSE перед отправкой кадра ошибки и закрытием соединения.
   - В `_sse_write(self, data: str, fatal: bool = True) -> bool`: для live-записи reasoning вызывать с `fatal=False`. При задержке или ошибке сокета выставлять `self._live_degraded = True`, НЕ вызывая `_kill_current_run()`. Ход модели продолжается, а накопленный буфер отдаётся в финале.

4. **S4 (Ретраи):**
   - При создании нового `ServeRun` в повторной попытке (`run_attempt`) сбрасывать `_live_sent_text = ""`, чтобы стрим не замирал на второй попытке.

5. **Тесты и качество:**
   - В `tests/test_muse_bridge_killpg.py` добавить модульные тесты для всех новых возможностей:
     - Непрерывный стриминг summary.0..N без заморозки
     - Маркеры вызова и завершения инструментов со строгой санитизацией
     - Опережающий сброс reasoning перед ошибкой 502
     - Нефатальная деградация live-записи при медленном сокете
   - Устранить 2 ошибки `basedpyright` в `tests/test_muse_bridge_killpg.py` (строки 1584, 1615: инициализировать `argv = []`).
   - Прогнать тесты `.venv/bin/python -m unittest tests/test_muse_bridge_killpg.py`, проверить `ruff check` (0 errors) и `basedpyright` (0 errors).

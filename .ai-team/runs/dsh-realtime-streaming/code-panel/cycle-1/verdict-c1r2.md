# ИТОГОВЫЙ ВЕРДИКТ КОДОВОЙ ПАНЕЛИ ТЕХЛИДОВ — Раунд 2
Дата: 2026-10-13 15:33 MSK
Раунд: Cycle 1 Round 2 (c1r2)
Фаза: CODE_PANEL
Артефакт: diff-r2.patch (SHA-256: `afe7157d62bef70a2c1f36d1162b5b838fdf6c59a6c19c2bb0b8c654a1963721`)
Panel Proof: `.ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/panel-proof-r2.json`
SHA-256 Panel Proof: `815671440eb6932bfd3df8a50983164ed7cc52f390954da35042a69437ca55bf`
Статус проверки: PASS (verify_panel_proof exit 0, все V01-V12 пройдены)

## Итоги голосования коллегии (3 независимых семейства)
- **Seat 1 (OpenAI, Визионер, gpt-6.1-sol-high, codex):** `NEEDS WORK`
- **Seat 2 (DeepSeek, Реалист, deepseek-v4.1-flash, droid):** `NEEDS WORK` (Rechecker, пересчёт жеребьёвки PASS)
- **Seat 3 (Google, Скептик, gemini-3.8-flash-high, droid):** `NEEDS WORK`

ИТОГОВЫЙ ВЕРДИКТ: **NEEDS WORK (3/3 единогласно)**

---

## Консенсус и сводка находок (Findings Ledger)

Коллегия судей признала успешное устранение замечаний RW-201 (короткий таймаут keepalive 3 с), RW-204 (ограничение producer потока), RW-205 (префиксная валидация `complete` по каждому mid/полю), RW-206 (UTF-8 бюджетирование и изоляция finish_reason: null для Droid), FU-207 (восстановление MAX_CONCURRENT в тестах), а также подтвердила детерминированное прохождение 90 тестов сьюта.

Однако все 3 судьи единогласно выявили критические дефекты реализации, требующие исправления Coder:

1. **F-203 (Повторное замечание, Блокирующее): Неполная изоляция `client_write_dead`**
   Флаг `client_write_dead` был объявлен внутри замыкания `_execute()`, но метод `Handler._serve_sse()` после выхода из `_execute()` не проверяет этот флаг и пытается записать в сокет терминальный `finish_reason: stop`, `usage` и `data: [DONE]\n\n`. При обрыве соединения клиенту рапортуется ложный успех.
   - **Действие Coder:** Пробросить `client_write_dead` в `_serve_sse()` (через `self._client_write_dead` или возврат в словаре `out`), и при `client_write_dead == True` полностью подавить отправку любых терминальных кадров success, usage и [DONE].

2. **F-208 (Блокирующее): Регрессия non-stream контракта из-за `Run.q` drop**
   Ограничение `RUN_QUEUE_MAXSIZE` и сброс с ошибкой `live_invalidated` применены для всех вызовов, включая non-stream (`sse_writer is None`). В non-stream режиме события отдаются залпом на terminal, и при >1024 событий запрос падает.
   - **Действие Coder:** Ограничение очереди и сброс должны активироваться строго при `sse_writer is not None` (живой стриминг). Для non-stream буферизованного режима `_publish` не должен отбрасывать события или инвалидировать ход.

3. **F-211 (Блокирующее): Wire-формат ошибки при сбое хода и обход `live_invalidated` на kind == "done"**
   Если после отправки live-префикса произошёл сбой выполнения (state == "error" или unhandled exception), мост обязан отдать клиенту валидный `chat.completion.chunk` с объектом ошибки и отдельный `[DONE]`. Событие `kind == "done"` не должно игнорировать флаг `live_invalidated`.

4. **F-212 (Non-blocking): Усиление тест-сьюта**
   Добавить явные тесты на подавление success-кадров в `_serve_sse` при сбое сокета, non-stream ход с >1024 событий, и видимый fail-close при сбое после отданного live-префикса.

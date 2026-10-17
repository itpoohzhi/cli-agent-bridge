# Бриф разработчика (Coder)

Скилл роли: `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md`

## Уже известно
- **repo_root:** `/Users/aazhiry1/work/src/cli-agent-bridge`
- **run_dir:** `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014`
- **branch:** `dev`
- **target_files:**
  - `bridges/muse-bridge/server.py`
  - `tests/test_muse_bridge_killpg.py`
  - `/Users/aazhiry1/.dsh/profiles/desktop/cordis.patch.yml`
  - `/Users/aazhiry1/.dsh/profiles/web/cordis.patch.yml`
- **spec_and_packet:**
  - `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/arch-spec.md` (sha256: `93b6fc42a3206d46482c5a09044666a45ac108e26542644dd552f09129b48c8f`)
  - `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/architecture-packet.json` (sha256: `04971a69473bc41b84edc528ceaba027dfbe2ff1f74a7e04449e0ed99745412a`)
- **prior_findings:**
  - Архитектурный Совет R2 вынес вердикт `ACCEPT` (2 ACCEPT, 1 NEEDS_WORK), квитанция `receipts/arch-panel.json` зафиксирована (`pol-receipt/1` PASS).
  - Сбой `muse turn failed (rc=1, state=terminal_failed): modelError: context compaction replacement still exceeds the hard threshold (639915 >= 460800 tokens)` воспроизводится при отправке >460800 токенов в Meta Muse CLI.

## Мост для субагентов
Входы даны выше; на диск за ними не ходи; стартовый корень поиска ∈ {$HOME, /Users/<user>, /} запрещён; ≥5 однотипных неудачных поисков подряд — стоп: смени инструмент/корень или верни ASK.

## Задача реализации
Реализовать исправление в соответствии с архитектурной спецификацией `arch-spec.md` (§6–§7):

1. **`ADR-001.1` (Единый источник лимитов контекста):**
   - В `bridges/muse-bridge/server.py` в словаре `ALLOWED_MODELS`:
     Для `muse-wonder-1.0` и `muse-wonder-full-1.0` установить `"context_length": 400_000` (безопасный буфер 60.8k относительно жесткого серверного лимита Meta 460.8k).
   - В `~/.dsh/profiles/desktop/cordis.patch.yml` и `~/.dsh/profiles/web/cordis.patch.yml`:
     Установить `contextWindow: 400000` для `muse-wonder-1.0` и `muse-wonder-full-1.0`.

2. **`ADR-001.2` (Защитный прунинг истории диалога):**
   - В `bridges/muse-bridge/server.py` реализовать функцию прунинга сообщений:
     * Порог срабатывания: `context_window` модели (`400_000`).
     * Целевой бюджет при прунинге: `320_000` токенов (гистерезис 80k токенов).
     * Обязательный контекст (не отбрасывается): ВСЕ `system` и `developer` сообщения из всей истории + первое сообщение `user` + последнее актуальное сообщение `user` (без дублирования, если первое и последнее совпадают) + последний блок `assistant(tool_calls)` + `tool`, если он идет после последнего `user`.
     * Атомарность инструментов: сообщения `role: "tool"` никогда не остаются без породившего их вызова `assistant(tool_calls)`.
     * Консервативная оценка токенов: `max(len(text)//3, len(text.encode('utf-8'))//3)` плюс накладные расходы на разметку моста и `_tools_section`.
     * Маркер пропуска: `[... earlier conversation turns compacted to stay within Muse context limit ...]`.
     * Если обязательный контекст сам по себе превышает лимит — модель не запускается, мост возвращает ошибку 502 с понятной диагностикой.

3. **`ADR-001.3` (Аварийный auto-retry при ошибке порога Meta):**
   - Если Meta возвращает ошибку с подстрокой `context compaction replacement still exceeds the hard threshold`:
     * Проверить, что контентные кадры SSE клиенту еще не отправлялись.
     * Ровно один повтор (`max_retries = 1`) с агрессивным срезом контекста до `200_000` токенов.
     * Отдельный счетчик контекстного повтора, не пересекающийся с сетевым retry.
     * При повторном отказе — возврат терминального HTTP 502 / SSE ошибки.

4. **`ADR-001.4` (Потокобезопасность, наблюдаемость и безопасность):**
   - Прунинг выполняется как чистая функция на локальной копии списка сообщений без удержания `self._wlock` (замок `_wlock` используется строго в `_sse_write`).
   - `_redact_secrets` применяется ко всем логам и ошибкам; тела сообщений не логируются.
   - Структурированное логирование события: `logger.info("muse_context_pruned: model=%s initial=%d target=%d dropped=%d is_retry=%s", ...)`.

5. **Тестирование (Regression tests red -> green):**
   - В `tests/test_muse_bridge_killpg.py` добавить тесты для прунинга (T-00..T-23):
     * Тест: сообщения до 400k токенов передаются без изменений.
     * Тест: сообщения >400k токенов прунятся до целевого бюджета ~320k.
     * Тест: сохранение обязательного контекста (`system`, `developer`, первый `user`, последний `user`).
     * Тест: атомарность пар `tool_calls` и `tool`.
     * Тест: корректная обработка кириллицы и многобайтовых UTF-8 символов.
     * Тест: перехват серверной ошибки порога и однократный auto-retry на 200k.
     * Тест: отказ без запуска, если обязательный контекст превышает лимит.
   - Запуск тестов: `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py`.
   - Проверка линтерами: `ruff check bridges/muse-bridge/server.py`.

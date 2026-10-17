# Бриф Архитектора (teamlead-with-architect, раунд R2)

## Задача
Обновить архитектурную спецификацию `arch-spec.md` и пакет `architecture-packet.json` в `.ai-team/runs/muse-wonder-foreign-session-20261014/` по результатам R1 и актуализированному handoff системного аналитика:

1. **Входные материалы:**
   - `/Users/aazhiry1/work/src/cli-agent-bridge/analysis/muse-wonder-foreign-session/handoff-architect.md`
   - `/Users/aazhiry1/work/src/cli-agent-bridge/analysis/muse-wonder-foreign-session/evidence-ledger.md`
   - Вердикты судей R1: `.ai-team/runs/muse-wonder-foreign-session-20261014/panel/arch/r1/seats/{2,3}/verdict.md`

2. **Требования к доработке спецификации (`arch-spec.md` и `architecture-packet.json`):**
   - **ADR-001.1 (Единый источник лимитов):**
     * Значение `contextWindow` и `context_length` в `ALLOWED_MODELS` и `cordis.patch.yml` устанавливается равным `400000`.
     * В `bridges/muse-bridge/server.py` лимит прунинга выводится динамически из конфигурации модели: `context_window = ALLOWED_MODELS.get(model, {}).get("contextWindow", 400_000)`.
   - **ADR-001.2 (Защитный прунинг и инварианты целостности):**
     * Обязательный контекст (mandatory set): ВСЕ `system` и `developer` сообщения из всей истории диалога, первое сообщение `user` (исходная постановка задачи) и последнее актуальное сообщение `user` (текущий запрос). Если первое и последнее совпадают — дублирование исключается.
     * Порог срабатывания: `context_window` (`400000`).
     * Целевой размер прунинга (гистерезис): `320000` токенов, что устраняет дребезг и смену префикса кэша на каждом последующем ходе диалога.
     * Инвариант атомарности инструментов: сообщения `role: "tool"` никогда не включаются в хвост без породившего их вызова `tool_calls` в сообщении `assistant`. Пары/группы инструментов отбираются атомарно.
     * Консервативная оценка токенов: `max(len(text) // 3, len(text.encode('utf-8')) // 3)` + запас на `_tools_section` и системную разметку моста.
     * Синтетический маркер пропуска: `[... earlier conversation turns compacted to stay within Muse context limit ...]`.
   - **ADR-001.3 (Жизненный цикл аварийного auto-retry):**
     * Срабатывание строго по ошибке сервера Meta: подстрока `context compaction replacement still exceeds the hard threshold`.
     * Допустимо ТОЛЬКО до отправки первого контентного чанка клиенту (в SSE — до `data: {"choices":[{"delta":{"content":...}}]}`).
     * Ровно один повтор (`max_retries = 1`) со срезом контекста до `200000` токенов.
     * При повторном сбое или если обязательный контекст превышает лимит — возврат терминального HTTP 502 / SSE ошибки с понятной диагностикой без утечки текста промпта.
   - **ADR-001.4 (Наблюдаемость, безопасность и потокобезопасность):**
     * `self._wlock` используется строго для синхронизации записи в SSE-сокет (`_sse_write`); функция прунинга `_messages_to_prompt` выполняется как чистая функция на локальной копии списка сообщений без удержания блокировок.
     * Применение `_redact_secrets` ко всем логам и диагностическим сообщениям; тела отброшенных и сокращенных сообщений в лог не пишутся.
     * Структурированный лог события прунинга: модель, токены до/после, количество пропущенных сообщений, причина (проактивная компакция vs retry).
   - **План тестирования и миграции:**
     * Детализированный список unit-тестов в `tests/test_muse_bridge_killpg.py` (пороги, кириллица, группы tool_calls, retry, отказ при превышении обязательного контекста).
     * Порядок синхронизации профилей DSH (`~/.dsh/profiles/{desktop,web}/cordis.patch.yml`) и живой проверки в сессии владельца (тяжелый путь).

3. **Результат:**
   - Обновленные файлы:
     * `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/arch-spec.md`
     * `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-foreign-session-20261014/architecture-packet.json`

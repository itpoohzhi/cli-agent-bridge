# ВЕРДИКТ АРХИТЕКТУРНОЙ ПАНЕЛИ ТЕХЛИДОВ (CYCLE 1 A2)

**Прогон:** `dsh-realtime-streaming`  
**Фаза:** `ARCH_PANEL` (arch cycle 1 a2)  
**Предмет:** `architecture-packet.json` (SHA-256: `50c615a487279f1c6a4e3ac630ea5c200db266284dc724abb97d387181ca6cff`)  
**Дата:** 2026-10-13 11:12 MSK  

## 1. Счётчики совещания
- Раундов дебатов: 1 (R1)
- Всего находок: 5
  - Blocking: 0
  - Non-blocking: 5 (F-101, F-102, F-103, F-104, F-106)
  - Excluded: 0
  - r2_late: 0
- Голоса судей:
  - Seat 1 (Якорь, Anthropic, `claude-sonnet-5-5`, Скептик): **NEEDS WORK** (особое мнение, 5 находок)
  - Seat 2 (Zhipu, `hermes-glm-5.3-max`, Реалист): **PASS** (SEED_RECHECK: PASS)
  - Seat 3 (DeepSeek, `deepseek-v4.1-flash`, Визионер): **PASS** (все 11 RW-001..011 FIXED)
- **Итоговый вердикт коллегии:** **PASS** (Большинство 2/3 разных семейств: Zhipu и DeepSeek)

## 2. Как совет договорился
Коллегия судей констатировала полное закрытие всех 11 блокирующих замечаний Совета Раунда 1 (RW-001..RW-011):
1. **Решение владельца (RW-001 / F-001):** Зафиксировано дословно (`EVD-017`), развилки AD-001/002 переведены в APPROVED, необратимый partial prefix без отзыва.
2. **Дедлайн cancellation fence (RW-002 / RW-006 / F-002 / F-006):** Численный fence (2+1+1 с) задан, SIGTERM/SIGKILL группы процессов, гарантированный возврат блокировок L/T в инварианте RW-009.
3. **Разделение режимов ToolCallParser (RW-003 / RW-007 / RW-011 / F-003 / F-007 / F-013):** Strict-live (0 тегов в live content) действует строго при `stream=true`; классический fallback для non-stream сохранён без регрессий.
4. **Plumbing в DroidAdapter (RW-004 / F-004):** Сигнатура `execute_turn(..., sse_writer=None)` передаёт `StreamSink` в RPC pump.
5. **Usage-чанк (RW-005 / F-005):** Формат кадра зафиксирован wire-примерами: `finish_reason: null`, честные `cached_tokens` без clamp, затем ровно один `[DONE]`.
6. **Владение компонентами (RW-008 / F-010):** Фасад владеет парсером; request worker владеет сокетом/очередью; коалесцирование 40 мс с немедленным flush перед terminal/error/DONE.
7. **Атомарный CAS attempt outcome (RW-009 / F-011):** Однократный переход статуса, стандартный OpenAI error chunk.
8. **Лимиты очереди slow reader (RW-010 / F-012):** Подсчёт лимита по байтам после коалесцирования, reserved control slot.

Замечания Скептика (F-101..F-106) квалифицированы коллегией по правилу консенсуса как non-blocking замечания (minority report) и передаются Coder как инженерные рекомендации при реализации:
- F-101: Не блокировать key навсегда при unconfirmed death, обеспечить recovery для tool continuation.
- F-102: Учесть гонку с checkpoint fsync при линеаризации отмены.
- F-103: Ограничить размер промежуточной очереди Run.q.
- F-104: Контролировать суммарный объем accumulator-буферов при параллельных ходах.
- F-106: Не удерживать lock очереди во время блокирующего `socket.send()`.

`blocking_open` пуст (0). Architecture Packet Редакции 2 утверждается коллегией (ARCH_PANEL_PASS). Разрешён переход к этапу реализации Coder.

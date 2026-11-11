# ADR-0024: Универсальная гарантия терминального фрейминга SSE (`finish_reason` + `[DONE]`), защита от повторных HTTP-заголовков и фильтрация `unknown_tool`

- **Статус:** Accepted
- **Дата:** 2026-11-10
- **Связанные артефакты:** `analysis/stream-drain-finish-reason/handoff-architect.md`, `specs/stream-drain-finish-reason/spec.md`

## 1. Контекст и проблема

В боевой эксплуатации DeepSeek Harness (`dsh`) поверх универсального шлюза `cli-agent-bridge` (`:9882`) зафиксированы три класса сбоев (`[F-01]..[F-30]`):
1. **`Stream ended without finish_reason` и дубль HTTP-заголовков в SSE:**
   - В `server.py` метод `Handler._serve_sse_body` не проверял флаг `self._headers_already_sent`, выставляемый коллбэком `_keepalive_cb` при ожидании слота в `QoSSlotManager.acquire_slot`, и повторно записывал `HTTP/1.1 200 OK` внутрь открытого SSE-потока (`[F-08]`).
   - При отказе `qos.acquire_slot` или `ResilienceError` после отправки keepalive-заголовков (`headers_sent[0] == True`) в поток писался плоский `data: {"error": ...}\n\n` без `choices[0].finish_reason` и без `data: [DONE]\n\n` (`[F-05]..[F-07]`).
   - При ошибке бэкенда с `live_sent[0] > 0` на не-Droid бэкендах (например, `Muse`, отправляющем в `write_live` только `reasoning_content`), `stream_error_frame` жёстко передавал `finish_reason=None`, подавляя `graceful_finish_reason()` (`"stop"`) (`[F-10]..[F-11]`).
   - В `core/turn_session_manager.py` метод `BufferedTurnEvent.to_sse_frame` для `kind == "error"` возвращал `finish_reason: null` без `data: [DONE]\n\n` (`[F-14]..[F-15]`).
2. **`Codex upstream stream failed via proxy endpoint ...: ClientPayloadError` в `adapters/passthrough_adapter.py`:**
   - При получении от upstream (`codex-lb`) JSON-события `{"error": ...}` без `choices` после уже открытых `choices` (`seen - finished`), либо `[DONE]` при `trusted_tools=False` и `seen - finished`, поток закрывался без `finish_reason` (`[F-17]..[F-20]`).
3. **`503: bridge is draining for restart` и спам `[Вызов инструмента: unknown_tool]`:**
   - В `core/lifecycle.py` `QoSSlotManager.acquire_slot` немедленно обрывал уже стоящие в очереди интерактивные запросы при выставлении `drain_event`, а `HubLifecycleManager` не имел настраиваемого окна удержания `BRIDGE_DRAIN_HOLD_TIMEOUT_S` (`[F-01]..[F-04]`).
   - В `adapters/muse_msp.py` при `item/started` без имени инструмента эмитировался `[Вызов инструмента: unknown_tool]\n`, а в `core/tool_emulation.py` `_sanitize_call` пропускал вызовы с пустым именем (`[F-22]..[F-25]`).

## 2. Решение

1. **Единое обрамление SSE и идемпотентность заголовков (`server.py`, `core/turn_session_manager.py`):**
   - В `Handler._serve_sse_body` пропускать `send_response(200)` / `end_headers()`, если `getattr(self, "_headers_already_sent", False)` уже истинно.
   - В `Handler._serve_resilient` при `headers_sent[0] == True` использовать `format_stream_error_sse(...)` (канонический `chat.completion.chunk` с `finish_reason="stop"` и `data: [DONE]\n\n`).
   - В `Handler._serve_sse_body` сохранять `finish_reason=None` только для отзыва живого `content`-префикса Droid (`live_prefix_invalidated` / `backend_kind == "droid"`), а для остальных бэкендов использовать дефолтный `graceful_finish_reason()`.
   - В `BufferedTurnEvent.to_sse_frame` (`kind == "error"`) формировать чанк через `build_stream_error_chunk` с `data: [DONE]\n\n`.
2. **Гарантия `finish_reason` в `adapters/passthrough_adapter.py`:**
   - В `relay_sse` на `[DONE]` проверять `acc.pending_choices() or (seen - finished)` независимо от `trusted_tools`.
   - При получении `chunk.get("error")` без `choices` при наличии незавершённых `seen - finished` или `acc.pending_choices()` эмитировать `_error_frame` (`finish_reason="stop"` + `data: [DONE]\n\n`).
3. **Graceful Drain Hold & QoS Grace (`core/lifecycle.py`, `server.py`):**
   - В `QoSSlotManager.acquire_slot` сохранять ожидающие интерактивные запросы при `drain_event.is_set()` в пределах `BRIDGE_DRAIN_QOS_GRACE_S` (по умолчанию `15.0` с).
   - В `HubLifecycleManager` добавить `wait_for_drain_hold(is_subagent=...)`, управляемый `BRIDGE_DRAIN_HOLD_TIMEOUT_S`.
4. **Фильтрация безымянных tool calls (`adapters/muse_msp.py`, `core/tool_emulation.py`, `core/turn_session_manager.py`):**
   - В `adapters/muse_msp.py` извлекать имя из `toolName`/`tool`/`name`; если имя вообще не передано и `BRIDGE_MUSE_SUPPRESS_UNKNOWN_TOOL=true`, не эмитировать баннер `unknown_tool`.
   - В `core/tool_emulation.py` (`_sanitize_call`) отбраковывать вызовы с пустым `name`, а в `TurnBuffer.feed_fsm_chunk` не добавлять пустой ключ `"name": ""` на чанках-продолжениях.

## 3. Последствия

- Все SSE-потоки гарантированно завершаются валидным `finish_reason` и `data: [DONE]\n\n`.
- Обратная совместимость существующих контрактов (`TestLiveFailureEnvelopeAfterPrefix`, `TestMspOracles`, `TestStreamRelay`) полностью сохранена.

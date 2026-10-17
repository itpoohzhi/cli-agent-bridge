# РОЛЬ: Coder (AI-SDLC Feature Implementation)
# СКИЛЛ: /Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md
# МОДЕЛЬ: claude-sonnet-5-5 (транспорт: Factory Droid `droid exec -m claude-sonnet-5 -r high`)

## Уже известно
- **repo_root**: `/Users/aazhiry1/work/src/cli-agent-bridge`
- **branch**: `dev`
- **run_id**: `dsh-realtime-streaming`
- **run_dir**: `/tmp/cel-runs/dsh-realtime-streaming/`
- **team_dir**: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-realtime-streaming/`
- **arch_packet**: `.ai-team/runs/dsh-realtime-streaming/architecture/architecture-packet.json` (SHA-256: `50c615a487279f1c6a4e3ac630ea5c200db266284dc724abb97d387181ca6cff`) и `.ai-team/runs/dsh-realtime-streaming/architecture/architecture-packet.md`
- **arch_verdict**: `.ai-team/runs/dsh-realtime-streaming/arch-panel/cycle-1/verdict-a2.md` (вердикт коллегии: PASS большинством 2/3)
- **prior_findings**:
  - Базовые тесты: `python3 -m unittest tests/test_rpc_core.py tests/test_bridge_http.py tests/test_cache_usage.py` зеленые (47 тестов, 24.2s).
  - Настоящая проблема: в `server.py` вызов `_dispatch` в `_serve_sse` буферизует все события хода до `_terminal`, и затем залпом сбрасывает их в сокет. Из-за этого `t_done - t_first ~ 0 ms`, и DeepSeek Harness Desktop насчитывает аномальные 179 000 tok/s.

## Задача
Реализовать честный потоковый SSE-стриминг (real-time streaming) от RPC pump Droid до клиента в соответствии с утвержденным Архитектурным Пакетом (редакция 2, AD-001, AD-002, AD-003, AD-004) и рекомендациями Совета техлидов (F-101..F-106).

## Целевые файлы
1. `adapters/droid_adapter.py`:
   - Поддержать проброс `sse_writer: Optional[StreamSink]` из `execute_turn(self, ctx: TurnContext, sse_writer: Optional[StreamSink] = None)` в `handler._run_once(legacy, ctx.keepalive, sse_writer=sse_writer)`.
2. `server.py`:
   - `_serve_sse`:
     - Создавать sink и связывать его с отдачей SSE-чанков в сокет HTTP-клиента по мере поступления дельт.
     - Коалесцирование дельт: квант 40 мс (немедленный сброс при смене типа reasoning/content/tool, при завершении или ошибке).
     - Передавать `sse_writer` через `_dispatch(ctx, keepalive, sse_writer=sink)`.
     - Non-stream путь (`_serve_json`) оставить полностью БЕЗ изменений (`sse_writer=None`).
   - `_dispatch` и `_run_once`:
     - Принимать опциональный `sse_writer` и передавать его в `_execute`.
     - Инвариант RW-009: Блокировки `L` (chat lock) и `T` (turn lock) должны освобождаться сразу по завершении вычисления и сохранения checkpoint, не удерживаясь медленным клиентом во время отправки оставшегося хвоста (decoupled delivery).
   - `Run._apply` и `_execute`:
     - При наличии `sse_writer`: отдавать дельты `reasoning` и `content` инкрементально по мере прихода JSON-RPC сообщений от Droid.
     - Strict-live режим ToolCallParser (AD-002): эмуляция tool calls при `stream=True` не должна пропускать сырые XML-теги `<tool_call>` в `content`. Если обнаружен префикс тега tool_call, он буферизуется до определения: либо валидный tool_call (уходит в SSE tool_call chunk), либо чистый текст.
     - Fail-close при нарушении инкрементальности (AD-001): если происходит retraction или сбой после того, как семантический префикс уже ушел клиенту, отправляется чанк с ошибкой (`type: "stream_error", code: "live_prefix_invalidated"`), затем `data: [DONE]\n\n`, без `finish_reason: "stop"` и без фейкового usage.
   - Usage и честный кэш:
     - В стриминге финальный чанк с usage отправляется перед `[DONE]`: `finish_reason: null`, честный `prompt_tokens_details.cached_tokens` без clamp (как утверждено в AD-004 и проверено в `test_cache_usage.py`).
   - Рекомендации Совета техлидов (F-101..F-106):
     - F-101: Не отравлять `chat_key` навсегда при нештатном завершении процесса, сохранять возможность восстановления сессии на следующем ходе (role=tool).
     - F-102: Дедлайн cancellation fence и сериализация с checkpoint fsync.
     - F-103: Ограничить размер промежуточной очереди `Run.q` (например, maxsize=1024), чтобы не накапливать unbounded память.
     - F-104: Ограничить суммарный объем live буферов в рамках `MAX_DELIVERY_BYTES`.
     - F-106: Не удерживать lock очереди во время блокирующего `socket.send()`.
3. `tests/test_live_stream.py`:
   - Написать новый набор unit-тестов, проверяющий:
     - Потоковую передачу дельт (sink вызывается инкрементально в процессе хода).
     - Замер времени: $t_{\text{done}} - t_{\text{first}} > 0$.
     - Работу ToolCallParser в режиме strict-live.
     - Корректную отправку usage чанка с честным кэшем.
     - Обработку fail-close при сбое после отправки префикса.
     - Освобождение блокировок `L`/`T` сразу после вычисления (RW-009).

## Ограничения
- Не ломать существующие тесты (`test_rpc_core.py`, `test_bridge_http.py`, `test_cache_usage.py`, `test_rpc_rework.py`).
- Не делать `git push` и не деплоить на remote.
- Все правки осуществлять локально в рабочей копии.

## Проверка перед сдачей
Выполнить:
`python3 -m unittest tests/test_rpc_core.py tests/test_bridge_http.py tests/test_cache_usage.py tests/test_live_stream.py`
Убедиться, что все тесты проходят (OK).
По окончании предоставить краткий отчет со списком измененных файлов и результатом тестов.

# РОЛЬ: Coder (AI-SDLC Rework Implementation)
# СКИЛЛ: /Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md
# МОДЕЛЬ: claude-sonnet-5-5 (транспорт: Factory Droid `droid exec -m claude-sonnet-5 -r high --auto high`)

## Задача
Устранить 6 блокирующих замечаний (RW-201..RW-206) и 1 рекомендацию (FU-207) из утвержденного брифа доработки Кодовой панели техлидов:
`.ai-team/runs/dsh-realtime-streaming/handoff/panel-rework-brief-code-c1.json`

## Входные артефакты
- Бриф: `.ai-team/runs/dsh-realtime-streaming/handoff/panel-rework-brief-code-c1.json`
- Леджер замечаний: `.ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/findings-ledger.md`
- Вердикт: `.ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/verdict-c1r1.md`

## Инструкции для реализации

### 1. RW-201 (server.py): Таймаут keepalive и защита RW-009
- В `Handler._execute` перед отправкой keepalive проверять `if client_write_dead[0]: continue` (не пытаться писать в заблокированный/мёртвый сокет).
- В `_serve_sse.keepalive` оборачивать запись в `LIVE_WRITE_TIMEOUT_S` (3 с), восстанавливая прежний таймаут сокета в `finally`, как это сделано для `_emit_tool_call` и текстовых дельт.
- При сбое keepalive (таймаут/BrokenPipe) выставлять `client_write_dead[0] = True`, освобождать ресурсы и не блокировать вычисление хода на 300 секунд.

### 2. RW-202 (server.py): Wire-формат чанка ошибки fail-close (AD-001)
- При `live_invalidated` (или сбое после отдачи префикса) в `_serve_sse` отправлять не плоский JSON, а валидный OpenAI `chat.completion.chunk`:
  ```python
  error_chunk = {
      "id": completion_id,
      "object": "chat.completion.chunk",
      "created": created,
      "model": shown_model,
      "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
      "error": {
          "message": err_msg or "Live attempt failed after provisional prefix",
          "type": "stream_error",
          "code": "live_prefix_invalidated",
          "param": None,
      },
  }
  self._emit("data: " + json.dumps(error_chunk, ensure_ascii=False) + "\n\n")
  self._emit("data: [DONE]\n\n")
  ```
- Никаких последующих вызовов finish или usage быть не должно!

### 3. RW-203 (server.py): Не маскировать сбой live-записи успешным финишем
- В `_serve_sse`, если произошёл сбой live-записи (`client_write_dead` установлен) или поток был инвалидирован, ЗАПРЕЩЕНО отправлять успешный `finish_reason: "stop"` / `tool_calls` и `usage`.
- Завершать поток либо чанком ошибки (RW-202), либо немедленным закрытием соединения, но НЕ притворяться перед клиентом, что ответ успешно доставлен целиком.
- При этом само вычисление хода и чекпоинт на сервере завершаются штатно, блокировки L и T освобождаются (RW-009).

### 4. RW-204 (server.py): Ограничение очереди Run.q (F-103)
- В `Run.__init__` инициализировать очередь с ограничением: `self.q = queue.Queue(maxsize=1024)`.
- В `_live_diff` (и при публикации других событий в `Run.q`) использовать `self.q.put_nowait(...)` или `put(..., timeout=0.1)`. При `queue.Full` перехватывать исключение, устанавливать `self.live_invalidated = True` и `self._last_error = "Run.q overflow"`.

### 5. RW-205 (server.py): Проверка префикса при complete / backfill
- В `Run._live_diff` хранить не только смещение `sent`, но и фактически отправленный текст `sent_prefix` для каждого `(mid, kind)`.
- При получении финального текста `create_message` или `complete` проверять:
  ```python
  if not text.startswith(sent_prefix):
      self.live_invalidated = True
      self._last_error = "non-prefix complete detected"
      return
  ```
- Если проверка пройдена, отправлять только суффикс `text[len(sent_prefix):]`.

### 6. RW-206 (server.py): Бюджетирование в байтах UTF-8 и изоляция Droid
- В `Handler._execute.add_content` и `add_reasoning` считать размер для `_DELIVERY_BUDGET.reserve(...)` в байтах: `len(piece.encode("utf-8"))`, а не символах `len(piece)`.
- В `_serve_sse` выставление `finish_reason: None` в кадре usage делать ТОЛЬКО для Droid live stream (когда `sse_writer is not None`), сохраняя прежний контракт для non-stream и других адаптеров.

### 7. FU-207 (tests/test_live_stream.py): Восстановление MAX_CONCURRENT
- В `TestImmediateLockRelease` сохранять исходное значение `server.MAX_CONCURRENT` и гарантированно восстанавливать его в `tearDown`.
- Обновить тесты под новый чанк ошибки (проверять `object == "chat.completion.chunk"` и `error.code == "live_prefix_invalidated"`).

## Требование к сдаче
Выполнить тесты:
`python3 -m unittest tests/test_live_stream.py tests/test_tool_parser.py tests/test_cache_usage.py tests/test_rpc_core.py tests/test_bridge_http.py`
Убедиться, что ВСЕ тесты проходят (OK).
Не коммитить в git remote, работать только локально.

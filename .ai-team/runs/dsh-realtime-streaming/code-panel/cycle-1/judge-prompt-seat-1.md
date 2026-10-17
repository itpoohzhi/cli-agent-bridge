# КОДОВАЯ ПАНЕЛЬ ТЕХЛИДОВ (Code Review Panel) — Раунд 1
Сиденье: 1
Слот: gpt-6.1-sol (OpenAI)
Шляпа: Реалист

Ты — Реалист. Твоя задача — оценить практичность, чистоту реализации, соответствие существующему коду server.py и adapters/droid_adapter.py, устойчивость к сбоям и реальным граничным условиям. Ключевой вопрос: «Работает ли это просто, надежно и без скрытых регрессий в проде?»


## Контекст задачи
- **Задача**: REQ-STREAM-001 — реализация real-time streaming в cli-agent-bridge для DeepSeek Harness Desktop.
- **Проблема As-Is**: В server.py весь вывод хода удерживался до terminal и затем отдавался клиенту залпом за ~0 мс, вызывая аномалию расчёта 179 000 tok/s.
- **Утвержденная архитектура**: Architecture Packet редакция 2 (AD-001..AD-004), утверждена Архитектурной панелью техлидов с вердиктом PASS.
- **Реализация Coder**: Выполнена моделью claude-sonnet-5-5 в server.py, adapters/droid_adapter.py, core/tool_emulation.py, tests/test_live_stream.py.


=== РЕЗУЛЬТАТЫ ТЕСТОВ ===
1. python3 -m unittest tests/test_live_stream.py tests/test_tool_parser.py tests/test_cache_usage.py tests/test_rpc_core.py tests/test_bridge_http.py
   Ran 76 tests in 33.7s: OK
2. tests/test_live_stream.py (8 тестов):
   - test_content_deltas_arrive_incrementally_before_done: PASS (t_first < t_done - 0.2s)
   - test_multiple_distinct_content_chunks_not_one_blob: PASS (>= 2 frames)
   - test_malformed_tool_call_block_fails_closed_without_leaking_raw_xml: PASS (live_prefix_invalidated, 0 XML)
   - test_well_formed_tool_call_is_unaffected: PASS
   - test_retract_after_live_delta_invalidates_the_turn: PASS
   - test_normal_turn_without_retraction_is_unaffected: PASS
   - test_usage_chunk_finish_reason_is_null_not_duplicated_stop: PASS
   - test_non_reading_client_does_not_prevent_commit_or_next_slot: PASS (RW-009 verified)



Оцени качество и корректность реализации real-time streaming в cli-agent-bridge по 6 критериям качества кода.
РЕЖИМ: code.

КРИТЕРИИ ОЦЕНКИ:
1. КОРРЕКТНОСТЬ:
   - Логика потоковой отдачи дельт в SSE по мере поступления Droid JSON-RPC.
   - Соблюдение инварианта RW-009: Блокировки L и T освобождаются сразу по завершении вычисления и сохранения чекпоинта, не удерживаясь медленным клиентом во время отдачи оставшегося хвоста.
   - Обработка сбоев и fail-close (AD-001): при retract/сбое после отдачи префикса отдается чанк с ошибкой, затем отдельный [DONE].
   - Strict-live режим ToolCallParser (AD-002): эмуляция tool_call при stream=True не пропускает сырые теги <tool_call> в content.
2. ПОЛНОТА:
   - Все ли требования Architecture Packet (AD-001..AD-004) и рекомендации Совета техлидов (F-101..F-106) реализованы.
   - Полнота тестового покрытия в tests/test_live_stream.py и tests/test_tool_parser.py.
3. ЧИТАЕМОСТЬ И СТИЛЬ:
   - Чистота кода в server.py, core/tool_emulation.py, adapters/droid_adapter.py.
   - Сохранение комментариев и отсутствие регрессий в non-stream режиме (_serve_json).
4. ПРОИЗВОДИТЕЛЬНОСТЬ И БЕЗОПАСНОСТЬ:
   - Таймаут записи клиенту (LIVE_WRITE_TIMEOUT_S) для защиты от зависших/медленных соединений.
   - Резервирование бюджета доставки (_DELIVERY_BUDGET) на каждый чанк перед записью.
   - Ограничение размера очередей и буферов.
5. ТЕСТИРУЕМОСТЬ:
   - Качество тестов в tests/test_live_stream.py (проверка t_first < t_done, strict-live, usage chunk, RW-009 decoupled delivery).
   - Все тесты проходят детерминированно.
6. СООТВЕТСТВИЕ АРХИТЕКТУРЕ:
   - Точное соответствие утвержденному Architecture Packet (редакция 2, SHA-256: 50c615a4...).
   - Не затронуты другие адаптеры и non-stream контракты.

ФОРМАТ ОТВЕТА (строго):
1. КОРРЕКТНОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
2. ПОЛНОТА: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
3. ЧИТАЕМОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
4. ПРОИЗВОДИТЕЛЬНОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
5. ТЕСТИРУЕМОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
6. СООТВЕТСТВИЕ АРХИТЕКТУРЕ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
ОБЩИЙ ВЕРДИКТ: ACCEPT|NEEDS WORK|RED FLAG

Внутри каждого критерия обязательно укажи SUB-строки:
SUB <критерий>/<подкатегория>: PASS|FAIL|N/A — evidence (file:line)
Каждый FAIL должен иметь четкий issue ID (F-NNN) и точную ссылку file:line.


=== ПРЕДЪЯВЛЕННЫЙ DIFF КЛИЕНТА ДЛЯ РЕВЬЮ ===
Файл: .ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/diff.patch (SHA-256: df43497ddc2758287e926ad7984b4a3f63cd46d896cb89213fd1285615f50832)

```diff
diff --git a/adapters/droid_adapter.py b/adapters/droid_adapter.py
index 3ca9777..b34b485 100644
--- a/adapters/droid_adapter.py
+++ b/adapters/droid_adapter.py
@@ -80,7 +80,7 @@ class DroidAdapter(BackendAdapter):
         legacy["rpc"]["items"] = [asdict(item) for item in ctx.rpc.items]
         legacy["images"] = [asdict(image) for image in ctx.images]
         handler = cast(Any, ctx.handler)
-        raw = handler._run_once(legacy, ctx.keepalive)
+        raw = handler._run_once(legacy, ctx.keepalive, sse_writer)
         usage = raw.get("usage") or {}
 
         def tool_call(call: dict) -> ToolCall:
diff --git a/core/tool_emulation.py b/core/tool_emulation.py
index b78ef4c..a0078db 100644
--- a/core/tool_emulation.py
+++ b/core/tool_emulation.py
@@ -274,17 +274,32 @@ def _parse_tool_call_block(inner: str) -> dict | None:
     return {"name": name.strip(), "arguments": arguments}
 
 
+class LiveParserError(Exception):
+    """Strict-live (AD-002): recognized `<tool_call>` блок невалиден либо не закрыт.
+
+    Поднимается только при `strict_live=True`; legacy-режим (stream=false либо
+    без sink) этот блок, как раньше, молча отдаёт текстом — исключение означает
+    fail-close всего live-хода (сырой XML клиенту не уходит).
+    """
+
+
 class ToolCallParser:
     """Поток текстовых дельт -> content и завершённые вызовы инструментов.
 
     Тег <tool_call> может прийти разорванным между дельтами: хвост, который может
     оказаться началом тега, удерживается и не уходит в content до разрешения.
+
+    `strict_live=True` (AD-002, только Droid stream=true с живым sink) запрещает
+    malformed/unclosed recognized-блокам уйти в content как текст: вместо
+    `_flush_all()`/raw-passthrough поднимается `LiveParserError`. `strict_live=False`
+    (умолчание, legacy nonstream/без sink) ведёт себя абсолютно без изменений.
     """
 
-    def __init__(self, on_content, on_tool_call):
+    def __init__(self, on_content, on_tool_call, strict_live: bool = False):
         self._buf = ""
         self._on_content = on_content
         self._on_tool_call = on_tool_call
+        self.strict_live = strict_live
 
     def feed(self, text: str) -> None:
         self._buf += text
@@ -298,6 +313,8 @@ class ToolCallParser:
             start = self._buf.find(TOOL_CALL_OPEN)
             if start == -1:
                 if final:
+                    if self.strict_live and self._pending_prefix():
+                        raise LiveParserError("unresolved tool_call prefix at finish")
                     self._flush_all()
                     return
                 keep = self._pending_prefix()
@@ -313,12 +330,16 @@ class ToolCallParser:
             end = self._find_close_outside_string(len(TOOL_CALL_OPEN))
             if end == -1:
                 if final:
+                    if self.strict_live:
+                        raise LiveParserError("unclosed tool_call block")
                     self._flush_all()  # незакрытый/невалидный блок отдаём текстом
                 return
             inner = self._buf[len(TOOL_CALL_OPEN) : end]
             self._buf = self._buf[end + len(TOOL_CALL_CLOSE) :]
             call = _parse_tool_call_block(inner)
             if call is None:
+                if self.strict_live:
+                    raise LiveParserError("malformed tool_call block")
                 self._emit(TOOL_CALL_OPEN + inner + TOOL_CALL_CLOSE)
             else:
                 self._on_tool_call(call)
diff --git a/server.py b/server.py
index 1404d7e..4d7bb12 100644
--- a/server.py
+++ b/server.py
@@ -83,6 +83,7 @@ from core.backend_adapter import (  # noqa: E402
     AdapterRegistry,
     FleetViolation,
     ImageAttachment,
+    StreamSink,
     Transcript,
     TranscriptItem,
     TurnContext,
@@ -91,6 +92,7 @@ from core.backend_adapter import (  # noqa: E402
 from core.tool_emulation import (  # noqa: E402,F401  - общая эмуляция tools (MB-REQ-007), реэкспорт имён
     TOOL_CALL_CLOSE,
     TOOL_CALL_OPEN,
+    LiveParserError,
     ToolCallParser,
     _attachments_section,
     _flatten_content,
@@ -126,6 +128,10 @@ MAX_CONCURRENT = int(os.environ.get("DROID_DSH_BRIDGE_MAX_CONCURRENT", "4"))
 QUEUE_TIMEOUT_S = int(os.environ.get("DROID_DSH_BRIDGE_QUEUE_TIMEOUT", "900"))
 TIMEOUT_S = int(os.environ.get("DROID_DSH_BRIDGE_TIMEOUT", "1800"))
 KEEPALIVE_S = float(os.environ.get("DROID_DSH_BRIDGE_KEEPALIVE", "15"))
+# RW-009 в живом ходе: запись живого куска клиенту ограничена этим таймаутом (а не 300с
+# socket-таймаута соединения) — зависший/нечитающий клиент не держит T/L (см. sse_writer в
+# _serve_sse и add_content/add_reasoning в Handler._execute).
+LIVE_WRITE_TIMEOUT_S = float(os.environ.get("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S", "3"))
 # Таймаут первого события stream-json от `droid exec` (с момента старта процесса).
 FIRST_TOKEN_TIMEOUT_S = float(
     os.environ.get("DROID_BRIDGE_FIRST_TOKEN_TIMEOUT_S", "90")
@@ -2636,7 +2642,13 @@ class Run:
     незакоммиченное; после успеха — прежняя гранулярность SSE.
     """
 
-    def __init__(self, plan: dict, proc: RpcProcess | None, holds_slot: bool):
+    def __init__(
+        self,
+        plan: dict,
+        proc: RpcProcess | None,
+        holds_slot: bool,
+        sse_writer: "StreamSink | None" = None,
+    ):
         self.plan = plan
         self.proc = proc
         self.slot_held = holds_slot
@@ -2671,6 +2683,12 @@ class Run:
         self._held_bytes = 0
         self._last_error = ""
         self._quarantined = 0
+        # Живой SSE-ход (AD-002/AD-003): sse_writer сам не вызывается отсюда (это дело _execute),
+        # сигнал используется только как флаг "эмитить text_delta/reasoning_delta в self.q по мере
+        # подтверждения дельт" вместо прежней пачки одним куском на terminal.
+        self.sse_writer = sse_writer
+        self._live_mids: set = set()  # mid, для которых клиенту уже ушёл хоть один байт живьём
+        self.live_invalidated = False  # AD-001: уже показанный mid потом retracted
         self.thread = threading.Thread(target=self._work, daemon=True)
         self.thread.start()
 
@@ -3050,10 +3068,32 @@ class Run:
                 "tc": 0,
                 "kc": 0,
                 "acc": ENTRY_OVERHEAD_BYTES,
+                "live_text": 0,  # сколько байт slot["text"] уже отдано live-ходу (sse_writer)
+                "live_thinking": 0,
             }
             self._order.append(mid)
         return self._msgs[mid]
 
+    def _live_diff(self, slot: dict, mid: str, field: str, kind: str) -> None:
+        """Живой ход (AD-002/RW-009): протолкнуть в self.q только НОВЫЙ хвост slot[field].
+
+        Вызывается после любого обновления slot["text"]/slot["thinking"] (дельта, complete с полным
+        текстом, backfill из create_message) — одинаково покрывает все три источника, отдавая клиенту
+        только то, что ещё не ушло. Применяется только когда sse_writer задан (живой SSE-ход);
+        для обычного (не-live) хода ничего не публикуется здесь — вывод копится до terminal, как раньше.
+        """
+        if self.sse_writer is None:
+            return
+        live_key = "live_" + field
+        sent = slot.get(live_key, 0)
+        text = slot[field]
+        if len(text) <= sent:
+            return
+        diff = text[sent:]
+        slot[live_key] = len(text)
+        self._live_mids.add(mid)
+        self.q.put((kind, (mid, diff)))
+
     def _progress(self) -> None:
         self.last_progress = time.monotonic()
         self.got_event = True
@@ -3150,8 +3190,10 @@ class Run:
             self._release_held(counted_id)
             if not slot["text"]:
                 self._set_slot_text(slot, "text", "tb", _message_text(message))
+                self._live_diff(slot, counted_id, "text", "text_delta")
             if not slot["thinking"]:
                 self._set_slot_text(slot, "thinking", "kb", _message_thinking(message))
+                self._live_diff(slot, counted_id, "thinking", "reasoning_delta")
             self._progress()
 
     @staticmethod
@@ -3202,10 +3244,12 @@ class Run:
             slot["tb"] += size
             slot["tc"] += size
             self._charge(size, slot)
+            self._live_diff(slot, mid, "text", "text_delta")
         elif ntype == "assistant_text_complete" and mid:
             slot = self._slot_for(mid)
             if isinstance(note.get("text"), str):
                 self._set_slot_text(slot, "text", "tb", note["text"])
+                self._live_diff(slot, mid, "text", "text_delta")
         elif ntype == "thinking_text_delta" and mid:
             delta = str(note.get("textDelta") or "")
             slot = self._slot_for(mid)
@@ -3214,11 +3258,17 @@ class Run:
             slot["kb"] += size
             slot["kc"] += size
             self._charge(size, slot)
+            self._live_diff(slot, mid, "thinking", "reasoning_delta")
         elif ntype == "thinking_text_complete" and mid:
             slot = self._slot_for(mid)
             if isinstance(note.get("text"), str):
                 self._set_slot_text(slot, "thinking", "kb", note["text"])
+                self._live_diff(slot, mid, "thinking", "reasoning_delta")
         elif ntype == "assistant_message_retracted" and mid:
+            if mid in self._live_mids:
+                # Клиенту уже ушёл live-байт этого сообщения, а droid его отозвал: честный live-ход
+                # не может сделать вид, что этого не было (AD-001) — весь ход фейлится явным сигналом.
+                self.live_invalidated = True
             slot = self._msgs.pop(mid, None)
             if slot is not None:
                 self._acc_bytes = max(0, self._acc_bytes - slot["acc"])
@@ -3306,13 +3356,29 @@ class Run:
                     )
                 )
             return True
+        if self.live_invalidated:
+            # AD-001: клиенту уже ушёл байт живого сообщения, которое droid потом отозвал, а ход
+            # всё же дошёл до успешного terminal — честный live-ход не может притвориться, что
+            # retract не было: явный fail-close вместо обычных result/usage/stop.
+            self.q.put(
+                (
+                    "live_invalidated",
+                    self._last_error
+                    or "a streamed message was retracted before the turn completed",
+                )
+            )
+            return True
         final_text = ""
         for mid in self._order:
             slot = self._msgs.get(mid) or {}
-            if slot.get("thinking"):
-                self.q.put(("reasoning", slot["thinking"]))
+            if self.sse_writer is None:
+                # Живой ход уже отдал text/reasoning по мере дельт (_live_diff); здесь — только
+                # обычная (не-live) гранулярность: целиком message-событием на terminal, как прежде.
+                if slot.get("thinking"):
+                    self.q.put(("reasoning", slot["thinking"]))
+                if slot.get("text"):
+                    self.q.put(("text", slot["text"]))
             if slot.get("text"):
-                self.q.put(("text", slot["text"]))
                 final_text = slot["text"]
         self.ok = True
         self.q.put(
@@ -3492,6 +3558,10 @@ class _ByteBudget:
 _DELIVERY_BUDGET = _ByteBudget(MAX_DELIVERY_BYTES)
 
 
+class _LiveBudgetExceeded(Exception):
+    """RW-011 в живом ходе: очередной кусок live-доставки не влез в бюджет памяти."""
+
+
 class Handler(BaseHTTPRequestHandler):
     protocol_version = "HTTP/1.1"
     timeout = 300
@@ -3561,14 +3631,27 @@ class Handler(BaseHTTPRequestHandler):
                     return "client_gone"
         return ""
 
-    def _execute(self, run: Run, keepalive, emulate_tools: bool) -> dict:
+    _FAIL_CLOSE_KINDS = ("stream_error", "pump_error", "live_invalidated")
+
+    def _execute(
+        self,
+        run: Run,
+        keepalive,
+        emulate_tools: bool,
+        sse_writer: "StreamSink | None" = None,
+    ) -> dict:
         """Гнать ход до конца; сквозной таймаут TIMEOUT_S на весь ход.
 
-        Клиенту во время вычисления пишется только keepalive (False — клиент ушёл). Вывод
-        НЕ доставляется здесь: он копится в out["events"] (content/reasoning/tool_call по
-        порядку) и уходит клиенту отдельным этапом после освобождения T/L и checkpoint
-        (RW-009). Размышления идут мимо ToolCallParser. При emulate_tools текстовый поток
-        проходит через ToolCallParser: блоки <tool_call> выделяются как вызовы.
+        Без sse_writer вывод копится в out["events"] и уходит клиенту отдельным этапом после
+        освобождения T/L (RW-009), как прежде. С sse_writer (живой SSE-ход, AD-001..AD-003)
+        content/reasoning_content уходят сюда же, по мере готовности text_delta/reasoning_delta
+        от Run — с коалесацией ~40мс (AD-003), чтобы не дробить кадры на один символ. Пока
+        дельта мессенджа копится, вперёд подсматривается один элемент очереди (pushback): смена
+        mid/вида завершает текущую группу, а fail-close вид (stream_error/pump_error/
+        live_invalidated) или уже выставленный run.live_invalidated — отбрасывает НЕотданный
+        буфер целиком и завершает ход ошибкой (ничего незакоммиченного клиенту не покажется).
+        Размышления идут мимо ToolCallParser. При emulate_tools текстовый поток проходит через
+        ToolCallParser (в живом ходе — в strict_live режиме: сырой `<tool_call>` не утечёт).
         Превышение deadline -> kill группы (в run.close()), state=timeout.
         """
         pieces = []
@@ -3578,6 +3661,8 @@ class Handler(BaseHTTPRequestHandler):
         result_ev = {}
         last_ka = time.monotonic()
         deadline = time.monotonic() + TIMEOUT_S
+        cur_mid = [None]  # mid последнего content-куска в pieces (разделитель "\n\n" между сообщениями)
+        pushback = None  # элемент очереди, подсмотренный при коалесации, но не обработанный сейчас
 
         def state(name: str, rc: int, err: str = "") -> dict:
             return {
@@ -3594,11 +3679,42 @@ class Handler(BaseHTTPRequestHandler):
                 "events": events,
             }
 
+        # RW-009 в живом ходе: зависший (не читающий, но не закрытый) клиент — write()
+        # с LIVE_WRITE_TIMEOUT_S сигналит об этом провалом sse_writer. Вычисление хода и
+        # commit чата НЕ прерываются (как и в небуферизованном старом пути — T/L освобождаются
+        # по расписанию _execute, независимо от клиента): просто дальнейшие попытки живой
+        # записи этому клиенту прекращаются (повторный таймаут на каждый кусок — бессмысленная
+        # трата времени, раз клиент уже не читает).
+        client_write_dead = [False]
+
         def add_content(text: str) -> None:
             if not text:
                 return
             pieces.append(text)
             events.append(("content", text))
+            if sse_writer is not None and not client_write_dead[0]:
+                for piece in _text_slices(text):
+                    # RW-011 в живом ходе: бюджет резервируется ДО фактической отдачи
+                    # куска — ничего незарезервированного клиенту не покажется.
+                    if not _DELIVERY_BUDGET.reserve(len(piece)):
+                        raise _LiveBudgetExceeded()
+                    self._delivery_reserved += len(piece)
+                    if not sse_writer("content", piece):
+                        client_write_dead[0] = True
+                        break
+
+        def add_reasoning(text: str) -> None:
+            if not text:
+                return
+            events.append(("reasoning", text))
+            if sse_writer is not None and not client_write_dead[0]:
+                for piece in _text_slices(text):
+                    if not _DELIVERY_BUDGET.reserve(len(piece)):
+                        raise _LiveBudgetExceeded()
+                    self._delivery_reserved += len(piece)
+                    if not sse_writer("reasoning", piece):
+                        client_write_dead[0] = True
+                        break
 
         def add_call(call: dict) -> None:
             entry = {
@@ -3613,7 +3729,18 @@ class Handler(BaseHTTPRequestHandler):
             tool_calls.append(entry)
             events.append(("tool_call", entry))
 
-        parser = ToolCallParser(add_content, add_call) if emulate_tools else None
+        parser = (
+            ToolCallParser(add_content, add_call, strict_live=sse_writer is not None)
+            if emulate_tools
+            else None
+        )
+
+        def take():
+            nonlocal pushback
+            if pushback is not None:
+                item, pushback = pushback, None
+                return item
+            return run.q.get(timeout=1.0)
 
         while True:
             if time.monotonic() > deadline:
@@ -3639,13 +3766,74 @@ class Handler(BaseHTTPRequestHandler):
             if _client_gone(self.connection):
                 return state("client_gone", 1)
             try:
-                kind, payload = run.q.get(timeout=1.0)
+                kind, payload = take()
             except queue.Empty:
                 if keepalive is not None and time.monotonic() - last_ka >= KEEPALIVE_S:
                     last_ka = time.monotonic()
                     if not keepalive():
                         return state("client_gone", 1)
                 continue
+            if kind in ("text_delta", "reasoning_delta"):
+                group_mid, buf0 = payload
+                buf = [buf0]
+                coalesce_deadline = time.monotonic() + 0.04
+                while True:
+                    if run.live_invalidated:
+                        break
+                    remaining = coalesce_deadline - time.monotonic()
+                    if remaining <= 0:
+                        break
+                    try:
+                        nxt_kind, nxt_payload = run.q.get(timeout=remaining)
+                    except queue.Empty:
+                        break
+                    if nxt_kind == kind and nxt_payload[0] == group_mid:
+                        buf.append(nxt_payload[1])
+                        continue
+                    pushback = (nxt_kind, nxt_payload)
+                    if nxt_kind in self._FAIL_CLOSE_KINDS:
+                        buf = None  # не наш показывать: ход фейлится, обработает pushback ниже
+                    break
+                if run.live_invalidated:
+                    return state(
+                        "live_invalidated",
+                        1,
+                        run._last_error
+                        or "a streamed message was retracted before the turn completed",
+                    )
+                if buf is None:
+                    continue
+                text = "".join(buf)
+                if kind == "text_delta":
+                    prefix = ""
+                    if cur_mid[0] != group_mid:
+                        if pieces:
+                            prefix = "\n\n"
+                        cur_mid[0] = group_mid
+                    text = prefix + text
+                    try:
+                        if parser is not None:
+                            parser.feed(text)
+                        else:
+                            add_content(text)
+                    except LiveParserError as exc:
+                        return state("live_invalidated", 1, str(exc)[:500])
+                    except _LiveBudgetExceeded:
+                        return state(
+                            "delivery_budget",
+                            1,
+                            "bridge overloaded: delivery memory budget exhausted",
+                        )
+                else:
+                    try:
+                        add_reasoning(text)
+                    except _LiveBudgetExceeded:
+                        return state(
+                            "delivery_budget",
+                            1,
+                            "bridge overloaded: delivery memory budget exhausted",
+                        )
+                continue
             if kind == "text":
                 # Событие message несёт ПОЛНЫЙ текст сообщения, не дельту:
                 # между сообщениями вставляем разделитель "\n\n" (как
@@ -3665,19 +3853,39 @@ class Handler(BaseHTTPRequestHandler):
                 return state("droid_error", 1, str(payload))
             elif kind == "pump_error":
                 return state("pump_error", 1, str(payload))
+            elif kind == "live_invalidated":
+                return state("live_invalidated", 1, str(payload))
             elif kind == "done":
                 rc, final_text = payload
                 if parser is not None:
-                    parser.finish()  # досбрасываем хвост незакрытого блока текстом
+                    try:
+                        parser.finish()  # досбрасываем хвост незакрытого блока текстом
+                    except LiveParserError as exc:
+                        return state("live_invalidated", 1, str(exc)[:500])
+                    except _LiveBudgetExceeded:
+                        return state(
+                            "delivery_budget",
+                            1,
+                            "bridge overloaded: delivery memory budget exhausted",
+                        )
                 # Fallback: события message не дали ни текста, ни вызовов, но итог
                 # есть в completion.finalText. Проводим его тем же путём (парсер +
                 # on_text), чтобы потоковый клиент не получил пустой ответ со stop.
                 if not pieces and not tool_calls and final_text:
-                    if parser is not None:
-                        parser.feed(final_text)
-                        parser.finish()
-                    else:
-                        add_content(final_text)
+                    try:
+                        if parser is not None:
+                            parser.feed(final_text)
+                            parser.finish()
+                        else:
+                            add_content(final_text)
+                    except LiveParserError as exc:
+                        return state("live_invalidated", 1, str(exc)[:500])
+                    except _LiveBudgetExceeded:
+                        return state(
+                            "delivery_budget",
+                            1,
+                            "bridge overloaded: delivery memory budget exhausted",
+                        )
                 time.sleep(0.05)
                 return state("done", rc, "".join(run.err_box))
 
@@ -3724,11 +3932,15 @@ class Handler(BaseHTTPRequestHandler):
             "events": [],
         }
 
-    def _run_once(self, ctx: dict, keepalive) -> dict:
+    def _run_once(
+        self, ctx: dict, keepalive, sse_writer: "StreamSink | None" = None
+    ) -> dict:
         """Ход запроса: порядок ресурсов L -> P -> T, до 3 попыток при транзиентном сбое.
 
-        Возвращает итог с буфером вывода (out["events"]); к моменту возврата T/L уже освобождены
-        и checkpoint записан — клиенту вывод отдаёт вызывающая ветка (RW-009).
+        Без sse_writer — прежнее поведение: вывод копится в out["events"] и уходит клиенту
+        отдельным этапом после освобождения T/L (RW-009). С sse_writer (живой SSE-ход)
+        content/reasoning_content уходят клиенту ПРЯМО во время _execute (AD-001..AD-003);
+        T/L всё равно освобождаются сразу по возврату _execute, независимо от скорости клиента.
         """
         model = ctx["model"]
         effort = ctx["effort"]
@@ -3900,7 +4112,10 @@ class Handler(BaseHTTPRequestHandler):
                         # Новая generation: SID известен только после initialize, PENDING пишется Run до первого add.
                         plan["before_add"] = functools.partial(_write_pending, chat)
                     new_run = Run(
-                        plan, chat.proc if plan["path"] == "hot" else None, holds_slot
+                        plan,
+                        chat.proc if plan["path"] == "hot" else None,
+                        holds_slot,
+                        sse_writer,
                     )
                     holds_slot = False
                 except Exception as exc:  # noqa: BLE001 - любая ошибка подготовки хода: ресурсы назад, штатный 502
@@ -3934,7 +4149,9 @@ class Handler(BaseHTTPRequestHandler):
                 run = new_run
                 open_attempt = (plan, run)
                 try:
-                    out = self._execute(run, keepalive, ctx["emulate_tools"])
+                    out = self._execute(
+                        run, keepalive, ctx["emulate_tools"], sse_writer
+                    )
                 finally:
                     try:
                         run.close()
@@ -3962,8 +4179,12 @@ class Handler(BaseHTTPRequestHandler):
                 open_attempt = None
                 if ok:
                     break
-                delivered = bool(out.get("text") or out.get("tool_calls"))
-                # Контент до terminal не отдаётся, поэтому delivered здесь — страховка.
+                # Без sse_writer контент до terminal не отдаётся, delivered здесь — страховка.
+                # С sse_writer часть контента могла уже уйти клиенту ЖИВЬЁМ до сбоя (run._live_mids
+                # непусто) — тихий повтор показал бы его клиенту повторно, поэтому тоже delivered.
+                delivered = bool(
+                    out.get("text") or out.get("tool_calls") or run._live_mids
+                )
                 if out["state"] != "done" or delivered or attempt == 3:
                     break
                 # Транзиентный сбой (rc!=0, клиенту ничего не выдано): повтор невидим;
@@ -4094,6 +4315,25 @@ class Handler(BaseHTTPRequestHandler):
                 "type": "droid_error",
                 "code": 502,
             }
+        if st == "live_invalidated":
+            # AD-001: часть уже отданного клиенту live-префикса оказалась незакоммиченной
+            # (retract после показа или незакрытый/сломанный <tool_call> в strict_live-парсере).
+            return {
+                "message": str(
+                    out.get("err") or "live stream prefix was invalidated mid-turn"
+                )[:500],
+                "type": "live_prefix_invalidated",
+                "code": 502,
+            }
+        if st == "delivery_budget":
+            # RW-011 в живом ходе: кусок, который привёл бы к превышению бюджета, отброшен
+            # ДО отдачи (см. add_content/add_reasoning) — то же тело ошибки, что и у
+            # _reserve_delivery, просто обнаружено раньше (на лету, а не постфактум).
+            return {
+                "message": "bridge overloaded: delivery memory budget exhausted",
+                "type": "proxy_error",
+                "code": 502,
+            }
         if st == "backend_error":
             return {
                 "message": f"{label} exec failed rc={out.get('rc')}",
@@ -4111,8 +4351,15 @@ class Handler(BaseHTTPRequestHandler):
         return None
 
     def _reserve_delivery(self, out: dict) -> Any:
-        """Резерв памяти ответа до выдачи (RW-011): None — взят, иначе тело ошибки 502 proxy_error."""
-        size = _delivery_size(out)
+        """Резерв памяти ответа до выдачи (RW-011): None — взят, иначе тело ошибки 502 proxy_error.
+
+        В живом ходе часть байт (content/reasoning) уже зарезервирована поштучно во время
+        _execute (см. add_content/add_reasoning) — здесь довносится только остаток
+        (например, аргументы tool_call), чтобы не резервировать один и тот же текст дважды.
+        """
+        size = _delivery_size(out) - self._delivery_reserved
+        if size <= 0:
+            return None
         if not _DELIVERY_BUDGET.reserve(size):
             _log(f"delivery_budget_exhausted bytes={size}")
             return {
@@ -4120,7 +4367,7 @@ class Handler(BaseHTTPRequestHandler):
                 "type": "proxy_error",
                 "code": 502,
             }
-        self._delivery_reserved = size
+        self._delivery_reserved += size
         return None
 
     # ---- HTTP --------------------------------------------------------------------
@@ -4538,8 +4785,15 @@ class Handler(BaseHTTPRequestHandler):
             return None
         return instr
 
-    def _dispatch(self, ctx: dict, keepalive) -> dict:
-        """Ход через адаптер бэкенда модели; общий разбор `<tool_call>` и итог в формате фасада."""
+    def _dispatch(
+        self, ctx: dict, keepalive, sse_writer: "StreamSink | None" = None
+    ) -> dict:
+        """Ход через адаптер бэкенда модели; общий разбор `<tool_call>` и итог в формате фасада.
+
+        sse_writer не None только у настоящего живого SSE-хода (_serve_sse): адаптеры, умеющие
+        отдавать content/reasoning по мере готовности (сейчас — droid), сами вызывают его из
+        своего пути выполнения. Остальные (muse) его просто игнорируют — поведение не меняется.
+        """
         adapter = BACKENDS.get(ctx["backend"])
         if adapter is None:
             return {
@@ -4568,7 +4822,9 @@ class Handler(BaseHTTPRequestHandler):
             client_gone=lambda: _client_gone(self.connection),
         )
         t0 = time.monotonic()
-        result = finalize_turn(adapter.execute_turn(turn, None), turn.emulate_tools)
+        result = finalize_turn(
+            adapter.execute_turn(turn, sse_writer), turn.emulate_tools
+        )
         # Только локальный HTTP-буфер: межмодульный seam уже вернул DTO.
         out = {
             "state": result.state,
@@ -4728,18 +4984,42 @@ class Handler(BaseHTTPRequestHandler):
         def keepalive() -> bool:
             return self._emit(": keepalive\n\n")
 
+        def sse_writer(kind: str, text: str) -> bool:
+            # AD-002/AD-003: честная живая доставка — content/reasoning_content уходят прямо
+            # отсюда, по мере готовности (с коалесацией ~40мс на стороне _execute), а не одним
+            # куском после полного хода. Разрыв соединения здесь — тот же сигнал, что у keepalive.
+            # RW-009: пишем с коротким таймаутом (не 300с socket-таймаута соединения) — клиент,
+            # который не читает SSE (окно забито), не держит T/L всю длину connection timeout;
+            # TimeoutError/socket.timeout — подвид OSError, _emit его уже превращает в False.
+            field = "content" if kind == "content" else "reasoning_content"
+            ok = True
+            prev_timeout = self.connection.gettimeout()
+            try:
+                self.connection.settimeout(LIVE_WRITE_TIMEOUT_S)
+                for piece in _text_slices(text) if text else [text]:
+                    if not self._emit(chunk({field: piece})):
+                        ok = False
+                        break
+            finally:
+                self.connection.settimeout(prev_timeout)
+            return ok
+
         if not self._emit(chunk({"role": "assistant", "content": ""})):
             return
-        out = self._dispatch(ctx, keepalive)
+        out = self._dispatch(ctx, keepalive, sse_writer)
         if out.get("state") == "client_gone":
             _log("client gone mid-stream, child killed")
             return
         err = self._error_body(out) or self._reserve_delivery(out)
         if err is None:
             # Доставка — отдельный этап: T/L уже свободны, checkpoint записан; обрыв клиента
-            # здесь ни на что, кроме самого ответа, не влияет.
+            # здесь ни на что, кроме самого ответа, не влияет. У droid content/reasoning уже ушли
+            # живьём из _execute (sse_writer выше): здесь остаются только tool_call-кадры.
+            live_backend = out.get("backend_kind") == "droid"
             for kind, value in out.get("events") or []:
                 if kind in ("content", "reasoning"):
+                    if live_backend:
+                        continue
                     field = "content" if kind == "content" else "reasoning_content"
                     # Большое событие выдаётся срезами: в памяти одновременно только один срез SSE-кадра.
                     delivered = (
@@ -4774,8 +5054,11 @@ class Handler(BaseHTTPRequestHandler):
                             "object": "chat.completion.chunk",
                             "created": created,
                             "model": shown_model,
+                            # AD-004: finish уже ушёл отдельным кадром выше; этот — чисто usage,
+                            # finish_reason здесь null (как у настоящего OpenAI stream_options.
+                            # include_usage), а не повтор "stop"/"tool_calls" на том же кадре.
                             "choices": [
-                                {"index": 0, "delta": {}, "finish_reason": finish}
+                                {"index": 0, "delta": {}, "finish_reason": None}
                             ],
                             "usage": _wire_usage(
                                 prompt_toks,
diff --git a/tests/test_live_stream.py b/tests/test_live_stream.py
new file mode 100644
index 0000000..b75e4f7
--- /dev/null
+++ b/tests/test_live_stream.py
@@ -0,0 +1,278 @@
+"""Честный живой SSE-стриминг droid (AD-001..AD-004): инкрементальная доставка,
+strict_live-парсер tool_call, fail-close на retract/malformed-блок, usage-чанк
+без повторного finish_reason, немедленное освобождение T/L независимо от клиента.
+
+Все сценарии идут через настоящий HTTP-сервер моста и настоящий fake-subprocess
+(tests/fake_droid.py), говорящий stream-jsonrpc. Реальный droid и сеть не используются.
+"""
+
+import json
+import socket
+import sys
+import time
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent))
+sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
+
+import server  # noqa: E402
+from bridge_testlib import TOOLS, wait_until  # noqa: E402
+from rpc_testlib import RpcCase  # noqa: E402
+
+BODY = {"model": "claude-sonnet-5-5"}
+
+
+def msg(text, role="user"):
+    return {"role": role, "content": text}
+
+
+class LiveStreamCase(RpcCase):
+    """RpcCase + сырой таймированный читатель SSE-ответа (нужен для t_first < t_done)."""
+
+    def _timed_sse(self, body: dict, deadline: float = 15.0):
+        """(список (t_recv, raw_frame), полный текст тела) — таймстемп на каждый "data: …" кадр.
+
+        Таймстемп кадра — момент, когда recv() впервые принёс байты, замыкающие его
+        законченной парой "\\n\\n": достаточно грубо, чтобы отличить "первый контент
+        пришёл заметно раньше финала" от "всё одним куском после полного хода" (AD-003).
+        """
+        payload = json.dumps(dict(body, stream=True)).encode()
+        sock = socket.create_connection(("127.0.0.1", self.port), timeout=deadline)
+        frames = []
+        try:
+            sock.sendall(self._raw_request(payload))
+            buf = b""
+            seen_header = False
+            emitted = 0
+            started = time.monotonic()
+            while time.monotonic() - started < deadline:
+                try:
+                    sock.settimeout(0.05)
+                    chunk = sock.recv(65536)
+                except socket.timeout:
+                    continue
+                except OSError:
+                    break
+                if not chunk:
+                    break
+                now = time.monotonic()
+                buf += chunk
+                if not seen_header:
+                    if b"\r\n\r\n" not in buf:
+                        continue
+                    seen_header = True
+                    buf = buf.split(b"\r\n\r\n", 1)[1]
+                parts = buf.decode("utf-8", "replace").split("\n\n")
+                complete = parts[:-1]  # последний элемент — возможно неполный хвост
+                for raw in complete[emitted:]:
+                    if raw.strip():
+                        frames.append((now, raw.strip()))
+                emitted = len(complete)
+                if raw_endswith_done(complete):
+                    break
+            full = buf.decode("utf-8", "replace")
+        finally:
+            sock.close()
+        return frames, full
+
+    @staticmethod
+    def _frame_json(raw: str):
+        if not raw.startswith("data: "):
+            return None
+        payload = raw[len("data: "):]
+        if payload == "[DONE]":
+            return None
+        try:
+            return json.loads(payload)
+        except ValueError:
+            return None
+
+
+def raw_endswith_done(parts) -> bool:
+    return any(p.strip() == "data: [DONE]" for p in parts)
+
+
+class TestIncrementalDelivery(LiveStreamCase):
+    """AD-002/AD-003: контент уходит по мере готовности, а не одним куском после полного хода."""
+
+    def test_content_deltas_arrive_incrementally_before_done(self):
+        """Между первым куском текста и финалом измеримая пауза -> t_first < t_done строго."""
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        {"op": "text", "text": "Hello there", "pause": 0.5},
+                        {"op": "text", "text": "World after the pause"},
+                    ]
+                }
+            ]
+        )
+        frames, full = self._timed_sse(dict(BODY, messages=[msg("hi")]))
+        self.assertIn("data: [DONE]", full)
+        content_times = [
+            t
+            for t, raw in frames
+            if (j := self._frame_json(raw)) is not None
+            and j.get("choices", [{}])[0].get("delta", {}).get("content")
+        ]
+        finish_times = [
+            t
+            for t, raw in frames
+            if (j := self._frame_json(raw)) is not None
+            and j.get("choices", [{}])[0].get("finish_reason")
+        ]
+        self.assertTrue(content_times, full)
+        self.assertTrue(finish_times, full)
+        # Контент пришёл раньше финала с заметным (не наносекундным) запасом: это
+        # и есть разница между "живьём по мере готовности" и "одним куском под конец".
+        self.assertLess(content_times[0], finish_times[0] - 0.2)
+
+    def test_multiple_distinct_content_chunks_not_one_blob(self):
+        """Хотя бы 2 разных SSE-кадра с контентом (не всё в одном финальном кадре)."""
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        {"op": "text", "text": "first part", "pause": 0.3},
+                        {"op": "text", "text": "second part"},
+                    ]
+                }
+            ]
+        )
+        frames, full = self._timed_sse(dict(BODY, messages=[msg("hi")]))
+        content_frames = [
+            raw
+            for _, raw in frames
+            if (j := self._frame_json(raw)) is not None
+            and j.get("choices", [{}])[0].get("delta", {}).get("content")
+        ]
+        self.assertGreaterEqual(len(content_frames), 2, full)
+
+
+class TestStrictLiveFailClose(LiveStreamCase):
+    """AD-001/AD-002: невалидный/незакрытый <tool_call> в живом ходе — ошибка, не текст с XML."""
+
+    def test_malformed_tool_call_block_fails_closed_without_leaking_raw_xml(self):
+        self.hub.script(
+            [{"steps": [{"op": "text", "text": server.TOOL_CALL_OPEN + "not json" + server.TOOL_CALL_CLOSE}]}]
+        )
+        status, stream = self._post(dict(BODY, stream=True, tools=TOOLS, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn("live_prefix_invalidated", stream)
+        self.assertNotIn("not json", stream)
+        self.assertNotIn(server.TOOL_CALL_OPEN, stream)
+        self.assertNotIn('"finish_reason": "stop"', stream)
+        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
+
+    def test_well_formed_tool_call_is_unaffected(self):
+        """Контрольная проба: валидный вызов живым ходом доходит как обычно (strict_live не мешает)."""
+        call = (
+            server.TOOL_CALL_OPEN
+            + '{"name": "get_weather", "arguments": {"city": "Berlin"}}'
+            + server.TOOL_CALL_CLOSE
+        )
+        self.hub.script([{"steps": [{"op": "text", "text": call}]}])
+        status, stream = self._post(dict(BODY, stream=True, tools=TOOLS, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn('"finish_reason": "tool_calls"', stream)
+        self.assertIn("get_weather", stream)
+        self.assertNotIn("live_prefix_invalidated", stream)
+
+
+class TestLiveInvalidatedOnRetraction(LiveStreamCase):
+    """AD-001: уже отданный клиенту живой префикс оказался незакоммиченным -> честный fail-close."""
+
+    def test_retract_after_live_delta_invalidates_the_turn(self):
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        {"op": "text", "text": "streamed-then-retracted"},
+                        {"op": "retract"},
+                        {"op": "error", "message": "backend changed its mind"},
+                    ],
+                    "reason": "model_request_rejected",
+                }
+            ]
+        )
+        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn("backend changed its mind", stream)
+        self.assertNotIn("streamed-then-retracted", stream)
+        self.assertNotIn('"finish_reason": "stop"', stream)
+        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
+
+    def test_normal_turn_without_retraction_is_unaffected(self):
+        """Контрольная проба: без retract ход завершается обычным stop, без live_invalidated."""
+        self.hub.script([{"steps": [{"op": "text", "text": "all good"}]}])
+        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn('"finish_reason": "stop"', stream)
+        self.assertNotIn("live_prefix_invalidated", stream)
+
+
+class TestHonestUsageChunk(LiveStreamCase):
+    """AD-004: отдельный usage-чанк после finish — finish_reason там null, не повтор stop/tool_calls."""
+
+    def test_usage_chunk_finish_reason_is_null_not_duplicated_stop(self):
+        self.hub.script(
+            [{"steps": [{"op": "text", "text": "hi"}], "usage": {"inputTokens": 10, "outputTokens": 5}}]
+        )
+        frames, full = self._timed_sse(dict(BODY, messages=[msg("hi")]))
+        usage_frames = [
+            self._frame_json(raw)
+            for _, raw in frames
+            if (j := self._frame_json(raw)) is not None and "usage" in j
+        ]
+        self.assertEqual(len(usage_frames), 1, full)
+        self.assertIsNone(usage_frames[0]["choices"][0]["finish_reason"])
+        # А более раннему кадру finish всё же есть: честный "stop" ушёл один раз, раньше.
+        stop_frames = [
+            self._frame_json(raw)
+            for _, raw in frames
+            if (j := self._frame_json(raw)) is not None
+            and j.get("choices", [{}])[0].get("finish_reason") == "stop"
+        ]
+        self.assertEqual(len(stop_frames), 1, full)
+
+
+class TestImmediateLockRelease(LiveStreamCase):
+    """RW-009 в живом ходе: клиент не читает SSE — вычисление, commit и слот P это не блокирует."""
+
+    def test_non_reading_client_does_not_prevent_commit_or_next_slot(self):
+        server.MAX_CONCURRENT = 1
+        big = "Y" * 2_000_000
+        self.hub.script(
+            [{"steps": [{"op": "text", "text": big}]}, {"steps": [{"op": "text", "text": "second"}]}]
+        )
+        sock = socket.socket()
+        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
+        sock.connect(("127.0.0.1", self.port))
+        payload = json.dumps(
+            dict(BODY, stream=True, prompt_cache_key="never-read", messages=[msg("go")])
+        ).encode()
+        try:
+            sock.sendall(self._raw_request(payload))
+            self.assertTrue(wait_until(lambda: len(self.hub.admissions()) >= 1, timeout=15))
+            time.sleep(0.5)  # вычисление успело закончиться; никто recv() на этом сокете не вызывал
+            # Вычисление заканчивается и чат коммитится READY, даже если никто не читает ответ.
+            self.assertTrue(
+                wait_until(
+                    lambda: self.chat_of("never-read").state in ("READY", "PERSISTED"),
+                    timeout=15,
+                )
+            )
+            # MAX_CONCURRENT=1: второй чат получит слот P только если первый его
+            # действительно вернул, а не держит из-за непрочитанной живой доставки.
+            status, body = self._post_json(
+                dict(BODY, prompt_cache_key="second-chat", messages=[msg("hi")])
+            )
+            self.assertEqual(status, 200)
+            self.assertEqual(body["choices"][0]["message"]["content"], "second")
+        finally:
+            sock.close()
+
+
+if __name__ == "__main__":
+    unittest.main(verbosity=2)
diff --git a/tests/test_tool_parser.py b/tests/test_tool_parser.py
index df2ad2a..77c7843 100644
--- a/tests/test_tool_parser.py
+++ b/tests/test_tool_parser.py
@@ -10,6 +10,7 @@ sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
 from server import (  # noqa: E402
     TOOL_CALL_CLOSE,
     TOOL_CALL_OPEN,
+    LiveParserError,
     ToolCallParser,
     _messages_to_prompt,
     _parse_tool_call_block,
@@ -147,6 +148,82 @@ class TestToolCallParser(unittest.TestCase):
             _parse_tool_call_block(inner), {"name": "t", "arguments": {"a": 1}}
         )
 
+    # -- AD-002: strict_live vs legacy, парные регрессии -----------------------------
+    # Legacy (strict_live=False, умолчание) не меняется ни байтом: malformed/unclosed
+    # блок, как и раньше, молча уходит в content как текст (test_invalid_block_falls_back_to_text/
+    # test_unclosed_block_flushed_as_text_on_finish выше). strict_live=True (живой SSE-ход
+    # droid) вместо этого поднимает LiveParserError — сырой `<tool_call>` клиенту не утекает.
+
+    def test_nonstream_malformed_xml_fallback_unchanged(self):
+        """Legacy (strict_live=False): невалидный блок — текстом, без исключения."""
+        c = Collector()
+        p = ToolCallParser(c.on_content, c.on_call, strict_live=False)
+        p.feed(TOOL_CALL_OPEN + "not json" + TOOL_CALL_CLOSE)
+        p.finish()
+        self.assertEqual(c.calls, [])
+        self.assertIn(TOOL_CALL_OPEN + "not json" + TOOL_CALL_CLOSE, "".join(c.content))
+
+    def test_nonstream_unclosed_xml_finish_fallback_unchanged(self):
+        """Legacy (strict_live=False): незакрытый блок на finish() — текстом, без исключения."""
+        c = Collector()
+        p = ToolCallParser(c.on_content, c.on_call, strict_live=False)
+        p.feed("tail " + TOOL_CALL_OPEN + '{"name": "t"')
+        p.finish()
+        self.assertEqual(c.calls, [])
+        self.assertIn('{"name": "t"', "".join(c.content))
+
+    def test_strict_live_malformed_xml_error_no_leak(self):
+        """strict_live=True: невалидный блок — LiveParserError, сырой XML не уходит в content."""
+        c = Collector()
+        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
+        with self.assertRaises(LiveParserError):
+            p.feed("Pre text " + TOOL_CALL_OPEN + "not json" + TOOL_CALL_CLOSE)
+        self.assertEqual(c.calls, [])
+        # Текст ДО блока — легитимный контент, его отдать можно (это не часть <tool_call>).
+        self.assertEqual("".join(c.content), "Pre text ")
+        self.assertNotIn("not json", "".join(c.content))
+        self.assertNotIn(TOOL_CALL_OPEN, "".join(c.content))
+
+    def test_strict_live_unclosed_xml_error_no_leak(self):
+        """strict_live=True: незакрытый блок на finish() — LiveParserError, не текст."""
+        c = Collector()
+        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
+        p.feed("tail " + TOOL_CALL_OPEN + '{"name": "t"')
+        with self.assertRaises(LiveParserError):
+            p.finish()
+        self.assertEqual(c.calls, [])
+        # "tail " до открывающего тега — легитимный текст, его отдать можно;
+        # а вот незакрытое содержимое самого блока наружу не ушло — вместо него исключение.
+        self.assertEqual("".join(c.content), "tail ")
+        self.assertNotIn('{"name": "t"', "".join(c.content))
+
+    def test_strict_live_unresolved_prefix_error_no_leak(self):
+        """strict_live=True: оборванный префикс открывающего тега на finish() — тоже ошибка."""
+        c = Collector()
+        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
+        p.feed("abc" + TOOL_CALL_OPEN[:5])  # разрыв прямо внутри тега, конца хода нет
+        with self.assertRaises(LiveParserError):
+            p.finish()
+        self.assertEqual(c.calls, [])
+        self.assertEqual("".join(c.content), "abc")
+        self.assertNotIn(TOOL_CALL_OPEN[:5], "".join(c.content)[3:])
+
+    def test_strict_live_well_formed_call_unaffected(self):
+        """strict_live=True не меняет поведение для валидного блока (только malformed/unclosed)."""
+        c = Collector()
+        p = ToolCallParser(c.on_content, c.on_call, strict_live=True)
+        p.feed(
+            "Pre "
+            + TOOL_CALL_OPEN
+            + '{"name": "get_weather", "arguments": {"city": "Berlin"}}'
+            + TOOL_CALL_CLOSE
+        )
+        p.finish()
+        self.assertEqual(
+            c.calls, [{"name": "get_weather", "arguments": {"city": "Berlin"}}]
+        )
+        self.assertEqual("".join(c.content), "Pre ")
+
 
 class TestToolsSection(unittest.TestCase):
     def test_protocol_and_schema_present(self):

```

# Пакет Кодового Совета (Council Package): Сквозной live-стриминг всех шагов рассуждений и действий модели в muse-bridge

**Тикет:** EYE-33873 (S2)
**Ветка:** `dev`
**Репозиторий:** `~/work/src/cli-agent-bridge`
**Модель Coder:** `muse-wonder-full-1.0` (транспорт: `muse exec`, Meta)
**Архитектурный совет (Arch-Panel):** APPROVED (PASS, receipts/arch-panel.json, sha256=0e4f8e735d60614b0d4f0fb6babeb5ea783575f1b08922b400298320d30730c2)
**Статус верификации:**
- Unit-тесты: `122 passed` (.venv/bin/python -m unittest tests/test_muse_bridge_killpg.py в 93.0s, OK)
- Ruff linter: `All checks passed!` (.venv/bin/ruff check bridges/muse-bridge/ tests/test_muse_bridge_killpg.py)
- Type checker: `0 errors, 2083 warnings, 0 notes` (.venv/bin/basedpyright bridges/muse-bridge/server.py tests/test_muse_bridge_killpg.py)

---

## 1. Резюме изменений (Executive Summary)

В рамках задачи EYE-33873 реализован сквозной live-стриминг всех шагов рассуждений модели (summary.0..N) и индикаторов выполнения инструментов (toolCall) в bridges/muse-bridge/server.py для DeepSeek Harness:

1. **AD-001 (Reasoning Live Streaming):**
   - В `ServeRun` полностью снята искусственная заморозка стриминга (`self._live_frozen = True` удален).
   - Все поступающие блоки `summary.*` передаются в SSE поток `delta.reasoning_content` в реальном времени.
   - В `ServeRun` дельты индексируются составным ключом `(item_id, idx)` в `self._reasoning_items` под `self._acc_lock = threading.Lock()`, отслеживая инкрементальные длины в `self._item_lengths[(item_id, idx)]`.

2. **AD-002 (Tool Call Markers & Санитизация):**
   - При старте инструмента отправляется маркер: `\n\n[Вызов инструмента: {tool_name}]\n` в `delta.reasoning_content`.
   - При завершении инструмента отправляется: `\n[Инструмент {tool_name} завершён]\n` в `delta.reasoning_content`.
   - Имя инструмента санитизируется регулярным выражением `^[A-Za-z0-9_.:-]{1,64}$`. При недопустимых символах выполняется замена на `_` либо fallback на `tool`.
   - Маркеры транслируются ТОЛЬКО при `stream: true`. В `stream: false` маркеры не добавляются.
   - Синхронизирован буфер отправленного текста `_live_sent_text` и финальный `reasoning` в `_send_sse`, исключая ложное срабатывание `reasoning_diverged` и повторную отправку полного текста рассуждений.

3. **AD-003 (Early Flush перед 502 & Защита от backpressure):**
   - В `_send(502)` (таймаут `TIMEOUT_S = 1800 - 35 = 1765 с` или сбой процесса) через `self._current_serve_run.get_accumulated_reasoning()` опережающе сбрасывается весь неотправленный остаток мыслей в SSE перед отправкой кадра ошибки и закрытием соединения.
   - В `_sse_write(self, data: str, fatal: bool = True) -> bool`: для live-записи reasoning вызовы производятся с `fatal=False`. При задержке или ошибке сокета выставляется `self._live_degraded = True`, НЕ вызывая `_kill_current_run()`. Ход модели продолжается, а накопленный буфер отдается в финале.

4. **S4 (Ретраи):**
   - При создании нового `ServeRun` в повторной попытке (`run_attempt`) вызывается `_reset_live_for_attempt()`, сбрасывающий `_live_sent_text = ""` и `_live_degraded = False`.

5. **Тесты и качество:**
   - В `tests/test_muse_bridge_killpg.py` добавлено 10 новых регрессионных тестов:
     - `LiveStreamingAllStepsTest`: `test_all_summary_steps_stream_live_without_freeze`, `test_stream_concat_includes_all_steps_via_http`
     - `ToolCallMarkersTest`: `test_sanitize_tool_name`, `test_tool_markers_only_in_stream`, `test_tool_marker_name_sanitized_in_stream`
     - `TimeoutReasoningFlushTest`: `test_flush_reasoning_before_502_error_frame`, `test_no_flush_for_503_without_run`, `test_slow_socket_live_write_degrades_without_kill`, `test_final_sse_delivers_buffer_after_live_degraded`, `test_reset_live_for_retry_attempt`
   - Исправлены 2 ошибки basedpyright (`argv: list[str] = []`).
   - Все 122 теста проходят успешно.

---

## 2. Статистика изменений (git diff --stat)

```
 bridges/muse-bridge/server.py    | 355 +++++++++++++++++++++++++++++++++------
 tests/test_muse_bridge_killpg.py | 200 +++++++++++++++++++++-
 2 files changed, 501 insertions(+), 54 deletions(-)

```

---

## 3. Полный diff изменений (git diff)

```diff
diff --git a/bridges/muse-bridge/server.py b/bridges/muse-bridge/server.py
index 881f42a..2b010b5 100644
--- a/bridges/muse-bridge/server.py
+++ b/bridges/muse-bridge/server.py
@@ -231,6 +231,24 @@ def _render_tool_token(value: Any) -> str:
     return f"redacted(len={len(text)})"
 
 
+_TOOL_MARKER_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
+_TOOL_MARKER_INVALID_RE = re.compile(r"[^A-Za-z0-9_.:-]")
+
+
+def _sanitize_tool_name(value: Any) -> str:
+    """Санитизация имени инструмента для live-маркеров reasoning (AD-002).
+
+    Допустимо только `^[A-Za-z0-9_.:-]{1,64}$`; недопустимые символы
+    заменяются на `_`, длина обрезается до 64, пустое/None — `tool`.
+    """
+    if not isinstance(value, str) or not value:
+        return "tool"
+    if _TOOL_MARKER_RE.match(value):
+        return value
+    cleaned = _TOOL_MARKER_INVALID_RE.sub("_", value)[:64]
+    return cleaned or "tool"
+
+
 class ApprovalPolicy:
     """Чистая политика решения по снимку approval (BND-001): без I/O.
 
@@ -1804,6 +1822,89 @@ class ServeRun:
         self.request_deadline = float("inf")
         self.turn_started_at: float | None = None
         self._live_frozen = False
+        # Сквозной live-стриминг всех шагов (ADR-0004): аккумулятор по
+        # составному ключу (item_id, idx), единый append-only stream-текст
+        # для live/final/flush (S2), доступ — только под _acc_lock (S3).
+        self._acc_lock = threading.Lock()
+        self._reasoning_items: dict[tuple[str, int], str] = {}
+        self._item_lengths: dict[tuple[str, int], int] = {}
+        self._reasoning_order: list[tuple[str, int]] = []
+        self._stream_text = ""
+        self._tool_names: dict[str, str] = {}
+        self._tool_started: set[str] = set()
+        self._tool_completed: set[str] = set()
+
+    def get_accumulated_reasoning(self) -> str:
+        """Потокобезопасный снимок накопленного reasoning (AD-003, S3).
+
+        Единый append-only stream-текст: дельты summary.* в порядке
+        поступления + live-маркеры инструментов (только при stream).
+        Тот же текст — база live, финала `_send_sse` и flush перед 502.
+        """
+        with self._acc_lock:
+            if self._stream_text:
+                return self._stream_text
+            return "\n\n".join(
+                self._reasoning_items[key]
+                for key in self._reasoning_order
+                if self._reasoning_items.get(key)
+            )
+
+    def _accumulate_reasoning(self, item_id: str, idx: int, piece: str) -> str:
+        """Добавить дельту в аккумулятор (item_id, idx); вернуть stream-текст."""
+        with self._acc_lock:
+            key = (item_id, idx)
+            is_new = key not in self._reasoning_items
+            self._reasoning_items[key] = self._reasoning_items.get(key, "") + piece
+            self._item_lengths[key] = len(self._reasoning_items[key])
+            if is_new:
+                self._reasoning_order.append(key)
+                if self._stream_text and not self._stream_text.endswith("\n"):
+                    self._stream_text += "\n\n"
+            self._stream_text += piece
+            return self._stream_text
+
+    def _accumulate_completed_summary(self, item_id: str, idx: int, full: str) -> str:
+        """Сверить завершённый summary[idx] с аккумулятором; дослать хвост."""
+        with self._acc_lock:
+            key = (item_id, idx)
+            existing = self._reasoning_items.get(key, "")
+            if full == existing:
+                return self._stream_text
+            is_new = key not in self._reasoning_items
+            self._reasoning_items[key] = full
+            self._item_lengths[key] = len(full)
+            if is_new:
+                self._reasoning_order.append(key)
+                if self._stream_text and not self._stream_text.endswith("\n"):
+                    self._stream_text += "\n\n"
+                self._stream_text += full
+            elif full.startswith(existing):
+                self._stream_text += full[len(existing) :]
+            return self._stream_text
+
+    def _emit_live(self) -> None:
+        """Отправить текущий stream-текст в live_sink; сбой не замораживает ход."""
+        sink = self.live_sink
+        if sink is None:
+            return
+        with self._acc_lock:
+            snapshot = self._stream_text
+        if not snapshot:
+            return
+        try:
+            sink(snapshot)
+        except Exception:  # noqa: BLE001, S110
+            pass
+
+    def _emit_tool_marker(self, item_id: str, marker: str) -> None:
+        """Дописать маркер инструмента в stream-текст и отправить live (AD-002)."""
+        del item_id
+        if self.live_sink is None:
+            return
+        with self._acc_lock:
+            self._stream_text += marker
+        self._emit_live()
 
     def close(self) -> None:
         """Убить группу процессов хода и коротко дождаться её ухода (идемпотентно)."""
@@ -2226,8 +2327,28 @@ class ServeRun:
                         f"tool_item kind={_render_tool_token(kind)} "
                         f"tool={_render_tool_token(item.get('toolName'))}"
                     )
-                if method == "item/completed" and kind == "reasoning":
-                    self._live_frozen = True
+                    # AD-002: live-маркеры инструментов только при stream
+                    # (live_sink ставится Handler только для stream=true).
+                    raw_tool = (
+                        item.get("toolName")
+                        or item.get("tool")
+                        or (kind if kind != "toolCall" else None)
+                    )
+                    safe_tool = _sanitize_tool_name(raw_tool)
+                    if iid and method == "item/started":
+                        self._tool_names[iid] = safe_tool
+                        if iid not in self._tool_started:
+                            self._tool_started.add(iid)
+                            self._emit_tool_marker(
+                                iid, f"\n\n[Вызов инструмента: {safe_tool}]\n"
+                            )
+                    elif iid and method == "item/completed":
+                        done_tool = self._tool_names.get(iid, safe_tool)
+                        if iid not in self._tool_completed:
+                            self._tool_completed.add(iid)
+                            self._emit_tool_marker(
+                                iid, f"\n[Инструмент {done_tool} завершён]\n"
+                            )
                 if (
                     method == "item/completed"
                     and turn_id is not None
@@ -2236,9 +2357,13 @@ class ServeRun:
                     if kind == "agentMessage" and isinstance(item.get("text"), str):
                         final_text = item["text"]
                     if kind == "reasoning" and isinstance(item.get("summary"), list):
-                        summaries.extend(
+                        completed_parts = [
                             str(p) for p in item["summary"] if isinstance(p, str)
-                        )
+                        ]
+                        summaries.extend(completed_parts)
+                        for c_idx, c_part in enumerate(completed_parts):
+                            self._accumulate_completed_summary(iid, c_idx, c_part)
+                        self._emit_live()
             elif method == "item/delta":
                 iid = str(params.get("itemId") or "")
                 field = str(params.get("field") or "text")
@@ -2249,7 +2374,8 @@ class ServeRun:
                     try:
                         idx = int(field.split(".", 1)[1])
                     except (IndexError, ValueError):
-                        idx = len(summary_parts)
+                        with self._acc_lock:
+                            idx = len([k for k in self._reasoning_items if k[0] == iid])
                     if not first_summary_logged[0]:
                         first_summary_logged[0] = True
                         _t0 = self.turn_started_at or _now0
@@ -2258,15 +2384,10 @@ class ServeRun:
                             f"after_s={time.monotonic() - _t0:.2f}"
                         )
                     summary_parts[idx] = summary_parts.get(idx, "") + piece
-                    if idx > 0:
-                        self._live_frozen = True
-                    elif not self._live_frozen and self.live_sink is not None:
-                        try:
-                            delivered = bool(self.live_sink(summary_parts.get(0, "")))
-                        except Exception:  # noqa: BLE001, S112
-                            delivered = False
-                        if not delivered:
-                            self._live_frozen = True
+                    # AD-001: заморозки нет — все summary.0..N стримятся
+                    # непрерывно; сбой live-записи ход не останавливает (S1).
+                    self._accumulate_reasoning(iid, idx, piece)
+                    self._emit_live()
                 elif (
                     kinds.get(iid, "agentMessage") == "agentMessage" and field == "text"
                 ):
@@ -2427,9 +2548,24 @@ class ServeRun:
                     pass
                 self.close()
                 serve_rc = self.proc.returncode
-            ordered = [
-                summary_parts[i] for i in sorted(summary_parts) if summary_parts[i]
-            ]
+            with self._acc_lock:
+                _items_snapshot = dict(self._reasoning_items)
+                _order_snapshot = list(self._reasoning_order)
+            if _items_snapshot:
+                _item_sequence: list[str] = []
+                for _key in _order_snapshot:
+                    if _key[0] not in _item_sequence:
+                        _item_sequence.append(_key[0])
+                ordered = [
+                    _items_snapshot[(_iid, _idx)]
+                    for _iid in _item_sequence
+                    for _idx in sorted(k[1] for k in _items_snapshot if k[0] == _iid)
+                    if _items_snapshot.get((_iid, _idx))
+                ]
+            else:
+                ordered = [
+                    summary_parts[i] for i in sorted(summary_parts) if summary_parts[i]
+                ]
             for part in ordered:
                 if part not in summaries:
                     summaries.append(part)
@@ -2518,6 +2654,11 @@ class Handler(BaseHTTPRequestHandler):
     _keepalive_stop: threading.Event | None = None
     _ka_thread: threading.Thread | None = None
     _live_sent_text: str = ""
+    _live_reasoning_sent: str = ""
+    _live_degraded: bool = False
+    _live_lock: threading.Lock = threading.Lock()
+    _current_serve_run: ServeRun | None = None
+    _stream: bool = False
     _write_deadline: float = float("inf")
     _exec_deadline: float = float("inf")
     _request_deadline: float = float("inf")
@@ -2539,6 +2680,11 @@ class Handler(BaseHTTPRequestHandler):
         self._keepalive_stop: threading.Event | None = None
         self._ka_thread: threading.Thread | None = None
         self._live_sent_text = ""
+        self._live_reasoning_sent = ""
+        self._live_degraded = False
+        self._live_lock = threading.Lock()
+        self._current_serve_run = None
+        self._stream = False
         self._write_deadline = float("inf")
         self._exec_deadline = float("inf")
         self._request_deadline = float("inf")
@@ -2546,32 +2692,63 @@ class Handler(BaseHTTPRequestHandler):
         self._req_done = None
         super().setup()
 
+    def _get_live_lock(self) -> threading.Lock:
+        """Замок live-состояния; лениво для Handler без setup() в тестах."""
+        lock = self.__dict__.get("_live_lock")
+        if lock is None:
+            lock = threading.Lock()
+            self._live_lock = lock
+        return lock
+
+    def _reset_live_for_attempt(self) -> None:
+        """Сброс live-префикса перед новым ServeRun в ретрае (S4)."""
+        with self._get_live_lock():
+            self._live_sent_text = ""
+            self._live_reasoning_sent = ""
+            self._live_degraded = False
+
+    def _note_write_failure(self, fatal: bool, message: str) -> bool:
+        """Сбой записи SSE: fatal — клиент ушёл+kill; иначе live-деградация (S1)."""
+        if not fatal:
+            if not getattr(self, "_live_degraded", False):
+                _log(f"live_degraded {message}")
+            self._live_degraded = True
+            return False
+        if not self._client_gone:
+            self._client_gone = True
+            self._delivery_failed = True
+            _log(message)
+            self._kill_current_run()
+        return False
+
     # ---- ранний SSE: заголовки сразу, keepalive во время хода ---------------------
     def _sse_write(
-        self, text: str, *, keepalive: bool = False, mark_content: bool = False
+        self,
+        data: str,
+        fatal: bool = True,
+        *,
+        keepalive: bool = False,
+        mark_content: bool = False,
     ) -> bool:
         """Один ограниченный бюджет L=min(s+LIVE_WRITE_TIMEOUT_S, W) (AD-004).
 
-        Ожидание замка, запись и flush делят единый остаток; исчерпание =
-        зависший клиент (client_gone + killpg). Действует на всех писателей.
+        Ожидание замка, запись и flush делят единый остаток. При
+        `fatal=True` исчерпание = зависший клиент (client_gone + killpg).
+        При `fatal=False` (live reasoning, S1) сбой лишь ставит
+        `_live_degraded`: ход ServeRun не убивается, буфер уйдёт в финале.
         """
+        text = data
         started = time.monotonic()
         w_deadline = getattr(self, "_write_deadline", float("inf"))
         limit = min(started + LIVE_WRITE_TIMEOUT_S, w_deadline)
         if limit <= started:
-            if not self._client_gone:
-                self._client_gone = True
-                self._delivery_failed = True
-                _log("delivery_deadline write budget exhausted before frame")
-                self._kill_current_run()
-            return False
+            return self._note_write_failure(
+                fatal, "delivery_deadline write budget exhausted before frame"
+            )
         if not self._wlock.acquire(timeout=max(0.0, limit - time.monotonic())):
-            if not self._client_gone:
-                self._client_gone = True
-                self._delivery_failed = True
-                _log("client gone mid-stream (sse lock wait budget)")
-                self._kill_current_run()
-            return False
+            return self._note_write_failure(
+                fatal, "client gone mid-stream (sse lock wait budget)"
+            )
         try:
             if self._sse_phase == "CLOSED" or self._client_gone:
                 return False
@@ -2612,12 +2789,7 @@ class Handler(BaseHTTPRequestHandler):
                         pass
             return True
         except (BrokenPipeError, ConnectionResetError, OSError):
-            if not self._client_gone:
-                self._client_gone = True
-                self._delivery_failed = True
-                _log("client gone mid-stream")
-                self._kill_current_run()
-            return False
+            return self._note_write_failure(fatal, "client gone mid-stream")
         finally:
             self._wlock.release()
 
@@ -2631,30 +2803,93 @@ class Handler(BaseHTTPRequestHandler):
         }
 
     def _sse_emit(
-        self, obj: dict, *, keepalive: bool = False, mark_content: bool = False
+        self,
+        obj: dict,
+        *,
+        keepalive: bool = False,
+        mark_content: bool = False,
+        fatal: bool = True,
     ) -> bool:
         return self._sse_write(
             "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n",
+            fatal,
             keepalive=keepalive,
             mark_content=mark_content,
         )
 
     def _live_reasoning_sink(self, full_text: str) -> bool:
-        """Sink ServeRun: публикует только прирост summary.0 до заморозки."""
+        """Sink ServeRun: публикует прирост всего stream-текста (summary.*+маркеры).
+
+        Запись нефатальна (S1): при сбое `_live_degraded=True`, ход жив,
+        повторные вызовы коротко возвращают True, буфер уйдёт в финале.
+        """
         if not full_text or not getattr(self, "_sse_open", False):
             return True
-        sent = getattr(self, "_live_sent_text", "")
-        if full_text == sent or not full_text.startswith(sent):
-            return True
-        delta = full_text[len(sent) :]
-        if not delta:
+        if getattr(self, "_live_degraded", False):
             return True
-        ok = self._sse_emit(
-            self._sse_chunk({"reasoning_content": delta}), mark_content=True
+        with self._get_live_lock():
+            sent = getattr(self, "_live_sent_text", "")
+            if full_text == sent or not full_text.startswith(sent):
+                return True
+            delta = full_text[len(sent) :]
+            if not delta:
+                return True
+            ok = self._sse_emit(
+                self._sse_chunk({"reasoning_content": delta}),
+                mark_content=True,
+                fatal=False,
+            )
+            if ok:
+                self._live_sent_text = full_text
+                self._live_reasoning_sent = full_text
+            else:
+                self._live_degraded = True
+            return ok
+
+    def _accumulated_reasoning(self) -> str:
+        """Накопленный reasoning текущего ServeRun или пустая строка."""
+        run = getattr(self, "_current_serve_run", None) or getattr(
+            self, "_current_run", None
         )
-        if ok:
-            self._live_sent_text = full_text
-        return ok
+        getter = getattr(run, "get_accumulated_reasoning", None)
+        if run is None or not callable(getter):
+            return ""
+        try:
+            acc = getter()
+        except Exception:  # noqa: BLE001
+            return ""
+        return acc if isinstance(acc, str) else ""
+
+    def _flush_reasoning_before_error(self) -> None:
+        """Опережающий сброс неотправленного reasoning перед 502 (AD-003)."""
+        if not (getattr(self, "_sse_open", False) or getattr(self, "_stream", False)):
+            return
+        acc = self._accumulated_reasoning()
+        if not acc:
+            return
+        with self._get_live_lock():
+            sent = getattr(self, "_live_sent_text", "")
+            if acc == sent or sent.startswith(acc):
+                return
+            if acc.startswith(sent):
+                tail = acc[len(sent) :]
+            else:
+                common = 0
+                for a_ch, b_ch in zip(sent, acc):
+                    if a_ch != b_ch:
+                        break
+                    common += 1
+                tail = acc[common:]
+            if not tail:
+                return
+            _log(f"flush_reasoning_before_502 chars={len(tail)}")
+            if self._sse_emit(
+                self._sse_chunk({"reasoning_content": tail}),
+                mark_content=True,
+                fatal=False,
+            ):
+                self._live_sent_text = acc if acc.startswith(sent) else sent + tail
+                self._live_reasoning_sent = self._live_sent_text
 
     def _force_close_connection(self) -> None:
         """Закрытие соединения надзором W без ожидания _wlock (a4)."""
@@ -2678,6 +2913,9 @@ class Handler(BaseHTTPRequestHandler):
             self._client_gone = True
             return False
         self._live_sent_text = ""
+        self._live_reasoning_sent = ""
+        self._live_degraded = False
+        self._stream = True
         self._sse_id = f"chatcmpl-muse-{uuid.uuid4().hex[:12]}"
         self._sse_created = int(time.time())
         self._sse_model = model
@@ -2785,6 +3023,8 @@ class Handler(BaseHTTPRequestHandler):
         if self._sse_open:
             # Заголовки 200 уже ушли: ошибка — кадром SSE, как у OpenAI-совместимых прокси.
             self._sse_stop_keepalive()
+            if int(code) == 502:
+                self._flush_reasoning_before_error()
             error = payload.get("error") if isinstance(payload, dict) else None
             if isinstance(error, dict):
                 error = dict(error)
@@ -2852,6 +3092,11 @@ class Handler(BaseHTTPRequestHandler):
         self._sse_stop_keepalive()
         chunk = self._sse_chunk
         reasoning = "\n\n".join(s for s in (summaries or []) if s)
+        # S2: единый stream-буфер ServeRun (с маркерами) авторитетен для
+        # live/final — сравнение с _live_sent_text не даёт ложного diverged.
+        accumulated = self._accumulated_reasoning()
+        if accumulated:
+            reasoning = accumulated
         live_sent = getattr(self, "_live_sent_text", "")
         if reasoning:
             if not live_sent:
@@ -2873,6 +3118,9 @@ class Handler(BaseHTTPRequestHandler):
                 chunk({"reasoning_content": tail}), mark_content=True
             ):
                 return
+            if tail:
+                self._live_sent_text = live_sent + tail
+                self._live_reasoning_sent = self._live_sent_text
         for tc in tool_calls:
             fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
             delta = {
@@ -3002,6 +3250,10 @@ class Handler(BaseHTTPRequestHandler):
         self._exec_deadline = _exec_deadline
         self._write_deadline = _write_deadline
         self._live_sent_text = ""
+        self._live_reasoning_sent = ""
+        self._live_degraded = False
+        self._current_serve_run = None
+        self._stream = req.get("stream") is True
         self._delivery_failed = False
         _req_done = threading.Event()
         self._req_done = _req_done
@@ -3223,6 +3475,8 @@ class Handler(BaseHTTPRequestHandler):
             if not ok_gate:
                 _log(f"new serve process blocked reason={gate_reason}")
                 return _blocked_out(f"new process blocked: {gate_reason}"), "blocked"
+            # S4: новый ServeRun (в т.ч. ретрай) стартует с чистого live-префикса.
+            self._reset_live_for_attempt()
             serve_run = ServeRun(model, attempt_prompt, effort, WORKSPACE)
             serve_run.exec_deadline = _exec_deadline
             serve_run.write_deadline = _write_deadline
@@ -3231,6 +3485,7 @@ class Handler(BaseHTTPRequestHandler):
                 serve_run.live_sink = self._live_reasoning_sink
             runs.append(serve_run)
             self._current_run = serve_run
+            self._current_serve_run = serve_run
             try:
                 attempt_out = serve_run.execute()
                 _update_agg(serve_run, attempt_out)
diff --git a/tests/test_muse_bridge_killpg.py b/tests/test_muse_bridge_killpg.py
index 0ddc128..7538209 100644
--- a/tests/test_muse_bridge_killpg.py
+++ b/tests/test_muse_bridge_killpg.py
@@ -1565,6 +1565,7 @@ class CliDisableFlagsAndApprovalFallbackTest(_BridgeScenario):
     """Реальные argv фейка; транспортный fallback до turn/start сохранён."""
 
     def test_serve_argv_allows_write_shell_by_default(self) -> None:
+        argv: list[str] = []
         install_protocol_wrapper(self, {"terminal": "completed"})
         for model in self.mod.ALLOWED_MODELS:
             with self.subTest(model=model):
@@ -1587,6 +1588,7 @@ class CliDisableFlagsAndApprovalFallbackTest(_BridgeScenario):
         # oracle_change (REQ-MUSE-002): approval больше не уходит в exec;
         # проверки exec-флагов сохранены на транспортном ServeUnavailable
         # (EOF рукопожатия до turn/start), approval-контракт — класс Approval.
+        argv: list[str] = []
         install_fake_msp(self, serve_plans=[{"handshake_eof": True}])
         for model in self.mod.ALLOWED_MODELS:
             with self.subTest(model=model):
@@ -3876,7 +3878,10 @@ class LiveReasoningTest(_BridgeScenario):
         handler._sse_open = True
         handler._live_sent_text = ""
         self.assertFalse(handler._live_reasoning_sink("thinking"))
-        self.assertTrue(handler._client_gone)
+        # oracle_change (ADR-0004/S1): live-запись нефатальна — деградация,
+        # а не client_gone/kill; ход продолжается, буфер уйдёт в финале.
+        self.assertTrue(handler._live_degraded)
+        self.assertFalse(handler._client_gone)
 
     def test_t_l05_model_retry_scheduled_log_only(self) -> None:
         plan = ok_plan(
@@ -3907,12 +3912,15 @@ class LiveReasoningTest(_BridgeScenario):
         install_fake_msp(self, serve_plans=[plan])
         status, body = bridge_request(self, turn_request(stream=True))
         self.assertEqual(status, 200, body)
-        self.assertEqual("".join(sse_deltas(body, "reasoning_content")), "ac\n\nb")
+        # oracle_change (ADR-0004/AD-001): без заморозки live — append-only
+        # stream в порядке поступления дельт; монотонность префикса сохранена,
+        # сортировка по idx остаётся только в финальных summaries.
+        self.assertEqual("".join(sse_deltas(body, "reasoning_content")), "a\n\nbc")
         plan = ok_plan({"summary": [1, "b"]}, {"summary": [0, "a"]})
         install_fake_msp(self, serve_plans=[plan])
         status, body = bridge_request(self, turn_request(stream=True))
         self.assertEqual(status, 200, body)
-        self.assertEqual("".join(sse_deltas(body, "reasoning_content")), "a\n\nb")
+        self.assertEqual("".join(sse_deltas(body, "reasoning_content")), "b\n\na")
 
     def test_t_l07_diverged_snapshot_sends_authoritative_full(self) -> None:
         handler = self.mod.Handler.__new__(self.mod.Handler)
@@ -3968,7 +3976,9 @@ class LiveReasoningTest(_BridgeScenario):
         started = time.monotonic()
         self.assertFalse(handler._live_reasoning_sink("thinking"))
         self.assertLess(time.monotonic() - started, 1.0)
-        self.assertTrue(handler._client_gone)
+        # oracle_change (ADR-0004/S1): таймаут live-записи — деградация, не kill.
+        self.assertTrue(handler._live_degraded)
+        self.assertFalse(handler._client_gone)
 
     def test_t_l08b_keepalive_blocking_first_bounds_sink(self) -> None:
         self.mod.LIVE_WRITE_TIMEOUT_S = 0.25
@@ -4041,5 +4051,187 @@ class LiveReasoningTest(_BridgeScenario):
         self.assertNotIn(b'"finish_reason": "stop"', writer.getvalue())
 
 
+class LiveStreamingAllStepsTest(_BridgeScenario):
+    """ADR-0004/AD-001: непрерывный стриминг summary.0..N без заморозки."""
+
+    def test_all_summary_steps_stream_live_without_freeze(self) -> None:
+        plan = ok_plan(
+            {"summary": [0, "step0-"]},
+            {"summary": [1, "step1-"]},
+            {"summary": [2, "step2"]},
+            {"summary": [0, "tail0"]},
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        snapshots: list[str] = []
+        run = self.mod.ServeRun("muse-spark-1.3", "p", "max", self.tmp / "workspace")
+        run.live_sink = lambda text: snapshots.append(text) or True
+        out = run.execute()
+        self.assertEqual(out["state"], "ok", out)
+        self.assertFalse(run._live_frozen)
+        # Аккумулятор по составному ключу (item_id, idx) + инкрементные длины.
+        self.assertEqual(run._reasoning_items[("r1", 0)], "step0-tail0")
+        self.assertEqual(run._reasoning_items[("r1", 1)], "step1-")
+        self.assertEqual(run._reasoning_items[("r1", 2)], "step2")
+        self.assertEqual(run._item_lengths[("r1", 0)], len("step0-tail0"))
+        self.assertEqual(run._item_lengths[("r1", 2)], len("step2"))
+        acc = run.get_accumulated_reasoning()
+        for piece in ("step0-", "step1-", "step2", "tail0"):
+            self.assertIn(piece, acc)
+        # Каждый снимок sink монотонно расширяет предыдущий, шаги 1..N видны
+        # до финала (не одним блоком в конце).
+        self.assertGreaterEqual(len(snapshots), 4)
+        for prev, cur in zip(snapshots, snapshots[1:]):
+            self.assertTrue(cur.startswith(prev), (prev, cur))
+        self.assertTrue(any("step1-" in s for s in snapshots[:-1]))
+
+    def test_stream_concat_includes_all_steps_via_http(self) -> None:
+        plan = ok_plan(
+            {"summary": [0, "a"]},
+            {"summary": [1, "b"]},
+            {"summary": [2, "c"]},
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200, body)
+        self.assertEqual("".join(sse_deltas(body, "reasoning_content")), "a\n\nb\n\nc")
+        self.assertNotIn("reasoning_diverged", self.mod.LOG_PATH.read_text())
+
+
+class ToolCallMarkersTest(_BridgeScenario):
+    """ADR-0004/AD-002: маркеры инструментов и строгая санитизация."""
+
+    def test_sanitize_tool_name(self) -> None:
+        sanitize = self.mod._sanitize_tool_name
+        self.assertEqual(sanitize("bash"), "bash")
+        self.assertEqual(sanitize("muse.bash:run-1_2"), "muse.bash:run-1_2")
+        self.assertEqual(sanitize("a/b c"), "a_b_c")
+        self.assertEqual(sanitize("x]\n[evil"), "x___evil")
+        self.assertEqual(sanitize(""), "tool")
+        self.assertEqual(sanitize(None), "tool")
+        self.assertEqual(sanitize(123), "tool")
+        self.assertEqual(len(sanitize("a" * 100)), 64)
+
+    def test_tool_markers_only_in_stream(self) -> None:
+        plan = ok_plan(
+            {"summary": [0, "think"]},
+            {"tool_item": {"kind": "toolCall", "toolName": "web_search"}},
+            {"summary": [0, "-done"]},
+        )
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200, body)
+        joined = "".join(sse_deltas(body, "reasoning_content"))
+        self.assertIn("\n\n[Вызов инструмента: web_search]\n", joined)
+        self.assertIn("\n[Инструмент web_search завершён]\n", joined)
+        self.assertLess(joined.index("[Вызов инструмента:"), joined.index("завершён]"))
+        self.assertIn("think", joined)
+        self.assertIn("-done", joined)
+        # S2: маркеры в live не вызывают ложный diverged и повторный полный текст.
+        self.assertNotIn("reasoning_diverged", self.mod.LOG_PATH.read_text())
+        self.assertEqual(joined.count("think"), 1)
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request())
+        self.assertEqual(status, 200, body)
+        self.assertNotIn("Вызов инструмента", body.decode("utf-8"))
+        self.assertEqual(json.loads(body)["reasoning_summaries"], ["think-done"])
+
+    def test_tool_marker_name_sanitized_in_stream(self) -> None:
+        plan = ok_plan({"tool_item": {"kind": "toolCall", "toolName": "a/b]evil name"}})
+        install_fake_msp(self, serve_plans=[plan])
+        status, body = bridge_request(self, turn_request(stream=True))
+        self.assertEqual(status, 200, body)
+        joined = "".join(sse_deltas(body, "reasoning_content"))
+        self.assertIn("[Вызов инструмента: a_b_evil_name]", joined)
+        self.assertNotIn("a/b]evil", joined)
+
+
+class TimeoutReasoningFlushTest(_BridgeScenario):
+    """ADR-0004/AD-003+S1/S4: flush перед 502, нефатальная деградация, ретрай."""
+
+    def _handler(self) -> Any:
+        handler = self.mod.Handler.__new__(self.mod.Handler)
+        handler._wlock = threading.Lock()
+        handler.wfile = io.BytesIO()
+        handler._sse_open = True
+        handler._stream = True
+        handler._live_sent_text = ""
+        handler._live_degraded = False
+        handler._client_gone = False
+        handler._write_deadline = float("inf")
+        return handler
+
+    def test_flush_reasoning_before_502_error_frame(self) -> None:
+        handler = self._handler()
+        handler._live_sent_text = "think-"
+        handler._current_serve_run = SimpleNamespace(
+            get_accumulated_reasoning=lambda: "think-more-and-more"
+        )
+        handler._send(502, {"error": {"message": "boom", "type": "proxy_error"}})
+        raw = handler.wfile.getvalue()
+        self.assertEqual(sse_deltas(raw, "reasoning_content"), ["more-and-more"])
+        text = raw.decode("utf-8")
+        self.assertLess(text.index("more-and-more"), text.index('"error"'))
+        self.assertIn("data: [DONE]", text)
+        self.assertEqual(handler._live_sent_text, "think-more-and-more")
+
+    def test_no_flush_for_503_without_run(self) -> None:
+        handler = self._handler()
+        handler._current_serve_run = None
+        handler._current_run = None
+        handler._send(503, {"error": {"message": "bridge busy"}})
+        self.assertEqual(sse_deltas(handler.wfile.getvalue(), "reasoning_content"), [])
+
+    def test_slow_socket_live_write_degrades_without_kill(self) -> None:
+        handler = self._handler()
+        killed: list[bool] = []
+        handler._current_run = SimpleNamespace(close=lambda: killed.append(True))
+
+        class TimeoutWriter(io.BytesIO):
+            def write(self, data):  # type: ignore[override]
+                raise TimeoutError("socket timeout")
+
+        handler.wfile = TimeoutWriter()
+        self.assertFalse(handler._sse_write("data: x\n\n", fatal=False))
+        self.assertTrue(handler._live_degraded)
+        self.assertFalse(handler._client_gone)
+        self.assertEqual(killed, [])
+        # Sink после деградации не блокирует reader повторными записями.
+        self.assertTrue(handler._live_reasoning_sink("thinking-more"))
+        # Фатальный режим по умолчанию сохраняет прежний контракт.
+        handler2 = self._handler()
+        killed2: list[bool] = []
+        handler2._current_run = SimpleNamespace(close=lambda: killed2.append(True))
+        handler2.wfile = TimeoutWriter()
+        self.assertFalse(handler2._sse_write("data: x\n\n"))
+        self.assertTrue(handler2._client_gone)
+        self.assertEqual(killed2, [True])
+
+    def test_final_sse_delivers_buffer_after_live_degraded(self) -> None:
+        handler = self._handler()
+        handler._live_degraded = True
+        handler._current_serve_run = SimpleNamespace(
+            get_accumulated_reasoning=lambda: "buffered-thoughts"
+        )
+        handler._send_sse("muse-spark-1.3", "hello", [], 1, 1, 0, ["buffered-thoughts"])
+        raw = handler.wfile.getvalue()
+        self.assertEqual(sse_deltas(raw, "reasoning_content"), ["buffered-thoughts"])
+        self.assertIn(b"data: [DONE]", raw)
+
+    def test_reset_live_for_retry_attempt(self) -> None:
+        handler = self._handler()
+        handler._live_sent_text = "old-prefix"
+        handler._live_reasoning_sent = "old-prefix"
+        handler._live_degraded = True
+        handler._reset_live_for_attempt()
+        self.assertEqual(handler._live_sent_text, "")
+        self.assertEqual(handler._live_reasoning_sent, "")
+        self.assertFalse(handler._live_degraded)
+        self.assertTrue(handler._live_reasoning_sink("fresh"))
+        self.assertEqual(
+            sse_deltas(handler.wfile.getvalue(), "reasoning_content"),
+            ["fresh"],
+        )
+
+
 if __name__ == "__main__":
     unittest.main(verbosity=2)

```

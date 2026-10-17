PANEL-NONCE: fbe08594653b46cf
Инструкция судье: первой строкой ответа повтори дословно строку «PANEL-NONCE: fbe08594653b46cf».

# КОДОВАЯ ПАНЕЛЬ ТЕХЛИДОВ (Code Review Panel) — Раунд 3
Сиденье: 3
Слот: gemini-3.8-flash-high (Google)
Шляпа: Реалист

Ты — Реалист. Твоя задача — оценить практичность, чистоту реализации, соответствие существующему коду server.py и adapters/droid_adapter.py, устойчивость к сбоям и реальным граничным условиям. Ключевой вопрос: «Работает ли это просто, надежно, без лишних усложнений и без скрытых регрессий в проде?»

ОБЯЗАТЕЛЬНЫЙ НЕЗАВИСИМЫЙ ПЕРЕСЧЁТ (анти-самосертификация):
Ты — судья с наименьшим рангом среди неякорных судей (gemini-3.8-flash-high). Ты ОБЯЗАН в самом начале своего вердикта привести блок:
```
=== НЕЗАВИСИМЫЙ ПЕРЕСЧЁТ ЖЕРЕБЬЁВКИ ===
seed_input: ee2da4f64befd741a513be9f257c63ac14d1662c4aa76f7d71c84d36ce45f794#dsh-realtime-streaming#c1#R3
seed_hex: ce8c3a41
ranked_order: deepseek-v4.1-flash, muse-spark-1.3, gemini-3.8-flash-high, hermes-glm-5.3-max, grok-4.7-high
seats: Seat 1: gpt-6.1-sol-high (OpenAI, Скептик), Seat 2: deepseek-v4.1-flash (DeepSeek, Визионер), Seat 3: gemini-3.8-flash-high (Google, Реалист)
hats: deepseek-v4.1-flash -> Визионер, gemini-3.8-flash-high -> Реалист, gpt-6.1-sol-high -> Скептик (k=1)
SEED_RECHECK: PASS
```


## Контекст задачи
- **Задача**: REQ-STREAM-001 — реализация real-time streaming в cli-agent-bridge для DeepSeek Harness Desktop.
- **Проблема As-Is**: В server.py весь вывод хода удерживался до terminal и затем отдавался клиенту залпом за ~0 мс, вызывая аномалию расчёта 179 000 tok/s.
- **Утвержденная архитектура**: Architecture Packet редакция 2 (AD-001..AD-004), утверждена Архитектурной панелью техлидов с вердиктом PASS.
- **Раунд 1 и Раунд 2**: Были выявлены замечания F-201..F-212.
- **Доработка Coder (Раунд 3)**: Выполнена моделью deepseek-v4.1-flash в server.py, tests/test_live_stream.py.


=== РЕАЛИЗОВАННЫЕ ДОРАБОТКИ ПО ЗАМЕЧАНИЯМ РАУНДА 2 (Findings Ledger F-203, F-208, F-211, F-212) ===
- RW-203 (F-203, Блокирующее): client_write_dead вынесен на уровень Handler (server.py:3629, 3753, 3771, 3785, 3863, 5058, 5151). В _serve_sse() (server.py:5171-5175) при client_write_dead == True полностью подавляется отправка терминальных success-кадров (stop, usage, [DONE]). Мёртвый сокет не удерживает слот и не получает ложного успеха.
- RW-208 (F-208, Блокирующее): Изоляция ограничения очереди Run.q strictly для live-стриминга. В server.py:2665-2669 и 2742-2754 лимит очереди RUN_QUEUE_MAXSIZE и overflow-инвалидация применяются ТОЛЬКО при sse_writer is not None. При sse_writer is None очередь неограничена и никогда не отбрасывает события (non-stream контракт гарантирован).
- RW-211 (F-211, Блокирующее): В ветке kind == "done" (server.py:3952-3964) проверяется run.live_invalidated и возвращается fail-close даже при rc=0. В _serve_sse() терминальный сбой хода после live-префикса (state=error, nonzero rc, exception) отдаёт ровно один валидный chat.completion.chunk с объектом error и отдельный [DONE] (server.py:5093-5113, 5145, 5156-5170, 5245-5252).
- FU-212 (F-212, Тестируемость): Добавлены 5 новых тест-классов (10 тестов, 22->32 в tests/test_live_stream.py), закрывающих все граничные условия сбоя сокета, non-stream burst >1024 событий, и wire-error конверта.



=== РЕЗУЛЬТАТЫ ТЕСТОВ (ДОРАБОТКА ПОСЛЕ РАУНДА 2) ===
1. Целевой набор (100 тестов):
   python3 -m unittest tests/test_live_stream.py tests/test_tool_parser.py tests/test_cache_usage.py tests/test_rpc_core.py tests/test_bridge_http.py
   Ran 100 tests in 41.800s: OK (100% PASS, 0 errors, 0 failures)
2. tests/test_live_stream.py (32 теста, расширен 5 новыми классами / 10 тестами):
   - Ran 32 tests in 16.550s: OK
   - Покрыты все замечания Раундов 1 и 2:
     * RW-201: Socket keepalive timeout (3с) и защита от зависания L/T.
     * RW-202: Wire-format error chunk со структурой OpenAI stream_error.
     * RW-203: client_write_dead вынесен на Handler, полное подавление внешних терминальных кадров (stop, usage, [DONE]) при сбое записи клиенту.
     * RW-204/RW-208: RUN_QUEUE_MAXSIZE (1024) и put_nowait действуют ТОЛЬКО при sse_writer is not None (живой стрим); non-stream buffered режим неограничен и никогда не отбрасывает события (проверено на >1024 событий).
     * RW-205: Strict-prefix валидация на complete по каждому mid и полю (content, reasoning).
     * RW-206: UTF-8 байтовое бюджетирование и изоляция finish_reason: null для Droid.
     * RW-211: Fail-close ветки kind == "done" при live_invalidated (даже при rc=0) и валидный chat.completion.chunk при терминальном сбое хода после отданного live-префикса.
     * FU-212: 10 явных тестов на все граничные условия подавления и fail-close.
3. Линтинг:
   .venv/bin/ruff check server.py tests/test_live_stream.py -> All checks passed!



Оцени качество и корректность доработанной реализации real-time streaming в cli-agent-bridge по 6 критериям качества кода.
РЕЖИМ: code (Раунд 3).

КРИТЕРИИ ОЦЕНКИ:
1. КОРРЕКТНОСТЬ:
   - Полностью ли устранены замечания F-203 (подавление терминальных кадров при client_write_dead в _serve_sse)?
   - Полностью ли устранено замечание F-208 (non-stream контракт без отбрасывания событий)?
   - Полностью ли устранено замечание F-211 (fail-close на kind == done при live_invalidated и error-chunk при терминальном сбое после live-префикса)?
   - Соблюдение инварианта RW-009: блокировки L и T освобождаются сразу по завершении вычисления, не удерживаясь клиентом.
2. ПОЛНОТА:
   - Все ли требования Architecture Packet (AD-001..AD-004) и Findings Ledger закрыты.
   - Полнота и глубина тестового покрытия в tests/test_live_stream.py (32 теста) и сьюте из 100 тестов.
3. ЧИТАЕМОСТЬ И СТИЛЬ:
   - Чистота кода в server.py, core/tool_emulation.py, adapters/droid_adapter.py.
   - Сохранение комментариев и отсутствие регрессий в non-stream режиме (_serve_json).
4. ПРОИЗВОДИТЕЛЬНОСТЬ И БЕЗОПАСНОСТЬ:
   - Защита от медленного сокета (LIVE_WRITE_TIMEOUT_S = 3с), отсутствие зависаний L/T.
   - Ограниченная очередь live-хода (1024) и неограниченная доставка non-stream.
   - Корректный подсчет байтов UTF-8 при бюджетировании доставки.
5. ТЕСТИРУЕМОСТЬ:
   - Качество 32 тестов в tests/test_live_stream.py. Все 100 целевых тестов проходят детерминированно.
6. СООТВЕТСТВИЕ АРХИТЕКТУРЕ:
   - Точное соответствие утвержденному Architecture Packet (редакция 2, SHA-256: 50c615a4...).
   - Не затронуты другие адаптеры (Muse сохраняет finish_reason: stop в usage) и non-stream контракты.

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


=== ПРЕДЪЯВЛЕННЫЙ DIFF КЛИЕНТА ДЛЯ РЕВЬЮ (РАУНД 3) ===
Файл: diff-r3.patch (SHA-256: ee2da4f64befd741a513be9f257c63ac14d1662c4aa76f7d71c84d36ce45f794)

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
index 1404d7e..46471c4 100644
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
@@ -269,6 +275,10 @@ MAX_INBOX_BYTES = int(os.environ.get("DROID_BRIDGE_MAX_INBOX_BYTES", str(4 << 20
 MAX_TURN_TEXT_BYTES = int(
     os.environ.get("DROID_BRIDGE_MAX_TURN_TEXT_BYTES", str(10 << 20))
 )
+# Промежуточная очередь Run.q (RW-204, F-103 Архитектурной панели): ограничена, чтобы
+# медленный потребитель (_execute) не давал producer (RPC-поток Run) копить события
+# без предела. Переполнение — не блокировка producer, а явный fail-close (Run._publish).
+RUN_QUEUE_MAXSIZE = int(os.environ.get("DROID_BRIDGE_RUN_QUEUE_MAXSIZE", "1024"))
 # Структурный предел строки RPC: число `{`/`[`/`,`/`:` вне строк. Строка из миллионов пустых объектов или
 # чисел укладывается в MAX_RPC_LINE_BYTES, но json.loads раздул бы её в сотни МиБ объектов (RW-014, RW-010):
 # отклоняется до разбора.
@@ -2636,12 +2646,27 @@ class Run:
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
         self.path = plan["path"]
-        self.q: queue.Queue = queue.Queue()
+        # RW-208 (AD-002/AD-003): лимит ёмкости очереди — только у живого SSE-хода
+        # (sse_writer задан): его producer публикует дельты по мере готовности и может
+        # обогнать consumer'а, отбрасывание здесь — осознанный fail-close. Non-stream копит
+        # вывод до terminal, очередь остаётся неограниченной (как до RW-204): terminal-пачка
+        # не теряется из-за размера.
+        self.q: queue.Queue = (
+            queue.Queue(maxsize=RUN_QUEUE_MAXSIZE)
+            if sse_writer is not None
+            else queue.Queue()
+        )
         self.err_box: list = proc.err_box if proc is not None else []
         self.got_event = False
         self.started = time.monotonic()
@@ -2671,6 +2696,14 @@ class Run:
         self._held_bytes = 0
         self._last_error = ""
         self._quarantined = 0
+        # Живой SSE-ход (AD-002/AD-003): sse_writer сам не вызывается отсюда (это дело _execute),
+        # сигнал используется только как флаг "эмитить text_delta/reasoning_delta в self.q по мере
+        # подтверждения дельт" вместо прежней пачки одним куском на terminal.
+        self.sse_writer = sse_writer
+        self._live_mids: set = (
+            set()
+        )  # mid, для которых клиенту уже ушёл хоть один байт живьём
+        self.live_invalidated = False  # AD-001: уже показанный mid потом retracted
         self.thread = threading.Thread(target=self._work, daemon=True)
         self.thread.start()
 
@@ -2681,16 +2714,16 @@ class Run:
         except _Cancelled:
             return
         except ModelMismatch as exc:
-            self.q.put(("stream_error", str(exc)[:500]))
+            self._publish(("stream_error", str(exc)[:500]))
         except RpcEof as exc:
-            self.q.put(("done", (exc.rc or 1, "")))
+            self._publish(("done", (exc.rc or 1, "")))
         except RpcError as exc:
-            self.q.put(("pump_error", str(exc)[:500]))
+            self._publish(("pump_error", str(exc)[:500]))
         except OSError as exc:
-            self.q.put(("pump_error", repr(exc)))
+            self._publish(("pump_error", repr(exc)))
         except Exception as exc:  # noqa: BLE001 - воркер не должен умирать молча: ход иначе висел бы до таймаута
             _log(f"session_rpc worker_error err={_err_summary(repr(exc), 160)!r}")
-            self.q.put(("pump_error", repr(exc)[:500]))
+            self._publish(("pump_error", repr(exc)[:500]))
         finally:
             if self.slot_held:
                 self.slot_held = False
@@ -2698,6 +2731,28 @@ class Run:
             if self.proc is not None:
                 self.proc.busy = False
 
+    def _publish(self, item: tuple) -> bool:
+        """Публикация в self.q без блокировки producer.
+
+        RW-204/RW-208: лимит RUN_QUEUE_MAXSIZE, неблокирующее отбрасывание при queue.Full
+        и инвалидация live_invalidated действуют только у живого SSE-хода (sse_writer задан).
+        Non-stream очередь неограниченна: событие не отбрасывается, live_invalidated из-за
+        размера очереди не выставляется.
+        """
+        if self.sse_writer is None:
+            self.q.put(item)  # неограниченная очередь: put не блокирует и не теряет события
+            return True
+        try:
+            self.q.put_nowait(item)
+            return True
+        except queue.Full:
+            self.live_invalidated = True
+            self._last_error = self._last_error or "Run.q overflow"
+            _log(
+                f"run_queue_overflow turn={self.active_turn or '-'} maxsize={self.q.maxsize}"
+            )
+            return False
+
     def _spawn(self) -> RpcProcess:
         holds = self.slot_held
         self.slot_held = False  # слот передан конструктору (при сбое он сам его вернёт)
@@ -3050,10 +3105,51 @@ class Run:
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
+        self._publish((kind, (mid, diff)))
+
+    def _check_live_prefix(self, slot: dict, field: str, new_text: str) -> bool:
+        """RW-205: complete/backfill обязан продолжать уже отправленный live-префикс поля.
+
+        Сравнение идёт с текстом, который РЕАЛЬНО ушёл в self.q (slot[field][:sent] до
+        перезаписи), а не просто с предыдущим slot[field]: несовпадающий или укороченный
+        complete после публикации префикса -> live_invalidated, без молчаливого среза и
+        без нового хвоста (вызывающая сторона не должна звать _set_slot_text/_live_diff).
+        """
+        if self.sse_writer is None:
+            return True
+        sent = slot.get("live_" + field, 0)
+        if sent == 0:
+            return True
+        if not new_text.startswith(slot[field][:sent]):
+            self.live_invalidated = True
+            self._last_error = self._last_error or "non-prefix complete detected"
+            return False
+        return True
+
     def _progress(self) -> None:
         self.last_progress = time.monotonic()
         self.got_event = True
@@ -3150,8 +3246,10 @@ class Run:
             self._release_held(counted_id)
             if not slot["text"]:
                 self._set_slot_text(slot, "text", "tb", _message_text(message))
+                self._live_diff(slot, counted_id, "text", "text_delta")
             if not slot["thinking"]:
                 self._set_slot_text(slot, "thinking", "kb", _message_thinking(message))
+                self._live_diff(slot, counted_id, "thinking", "reasoning_delta")
             self._progress()
 
     @staticmethod
@@ -3202,10 +3300,14 @@ class Run:
             slot["tb"] += size
             slot["tc"] += size
             self._charge(size, slot)
+            self._live_diff(slot, mid, "text", "text_delta")
         elif ntype == "assistant_text_complete" and mid:
             slot = self._slot_for(mid)
-            if isinstance(note.get("text"), str):
+            if isinstance(note.get("text"), str) and self._check_live_prefix(
+                slot, "text", note["text"]
+            ):
                 self._set_slot_text(slot, "text", "tb", note["text"])
+                self._live_diff(slot, mid, "text", "text_delta")
         elif ntype == "thinking_text_delta" and mid:
             delta = str(note.get("textDelta") or "")
             slot = self._slot_for(mid)
@@ -3214,11 +3316,19 @@ class Run:
             slot["kb"] += size
             slot["kc"] += size
             self._charge(size, slot)
+            self._live_diff(slot, mid, "thinking", "reasoning_delta")
         elif ntype == "thinking_text_complete" and mid:
             slot = self._slot_for(mid)
-            if isinstance(note.get("text"), str):
+            if isinstance(note.get("text"), str) and self._check_live_prefix(
+                slot, "thinking", note["text"]
+            ):
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
@@ -3299,23 +3409,39 @@ class Run:
         reason = str(note.get("reason") or "")
         if self.cancel.is_set() or reason not in ("completed", "permission_rejected"):
             if not self.cancel.is_set():
-                self.q.put(
+                self._publish(
                     (
                         "stream_error",
                         self._last_error or f"turn ended: {reason or 'unknown'}",
                     )
                 )
             return True
+        if self.live_invalidated:
+            # AD-001: клиенту уже ушёл байт живого сообщения, которое droid потом отозвал, а ход
+            # всё же дошёл до успешного terminal — честный live-ход не может притвориться, что
+            # retract не было: явный fail-close вместо обычных result/usage/stop.
+            self._publish(
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
+                    self._publish(("reasoning", slot["thinking"]))
+                if slot.get("text"):
+                    self._publish(("text", slot["text"]))
             if slot.get("text"):
-                self.q.put(("text", slot["text"]))
                 final_text = slot["text"]
         self.ok = True
-        self.q.put(
+        self._publish(
             (
                 "result",
                 {
@@ -3327,7 +3453,7 @@ class Run:
                 },
             )
         )
-        self.q.put(("done", (0, final_text)))
+        self._publish(("done", (0, final_text)))
         return True
 
     # -- завершение ----------------------------------------------------------------
@@ -3492,10 +3618,15 @@ class _ByteBudget:
 _DELIVERY_BUDGET = _ByteBudget(MAX_DELIVERY_BYTES)
 
 
+class _LiveBudgetExceeded(Exception):
+    """RW-011 в живом ходе: очередной кусок live-доставки не влез в бюджет памяти."""
+
+
 class Handler(BaseHTTPRequestHandler):
     protocol_version = "HTTP/1.1"
     timeout = 300
     _delivery_reserved = 0  # байты, взятые в _DELIVERY_BUDGET текущим запросом (RW-011)
+    _client_write_dead = False  # RW-203: живая запись отвергнута — терминал не шлём
 
     def log_message(self, fmt: str, *args: Any) -> None:
         _log("http " + (fmt % args))
@@ -3561,14 +3692,27 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3578,6 +3722,10 @@ class Handler(BaseHTTPRequestHandler):
         result_ev = {}
         last_ka = time.monotonic()
         deadline = time.monotonic() + TIMEOUT_S
+        cur_mid = [
+            None
+        ]  # mid последнего content-куска в pieces (разделитель "\n\n" между сообщениями)
+        pushback = None  # элемент очереди, подсмотренный при коалесации, но не обработанный сейчас
 
         def state(name: str, rc: int, err: str = "") -> dict:
             return {
@@ -3594,11 +3742,48 @@ class Handler(BaseHTTPRequestHandler):
                 "events": events,
             }
 
+        # RW-009 в живом ходе: зависший (не читающий, но не закрытый) клиент — write()
+        # с LIVE_WRITE_TIMEOUT_S сигналит об этом провалом sse_writer. Вычисление хода и
+        # commit чата НЕ прерываются (как и в небуферизованном старом пути — T/L освобождаются
+        # по расписанию _execute, независимо от клиента): просто дальнейшие попытки живой
+        # записи этому клиенту прекращаются (повторный таймаут на каждый кусок — бессмысленная
+        # трата времени, раз клиент уже не читает).
+        # RW-203: состояние живёт на Handler (а не в локальной переменной), чтобы внешний
+        # _serve_sse видел отказ и после возврата _execute; каждый ход начинает с чистого.
+        self._client_write_dead = False
+
         def add_content(text: str) -> None:
             if not text:
                 return
             pieces.append(text)
             events.append(("content", text))
+            if sse_writer is not None and not self._client_write_dead:
+                for piece in _text_slices(text):
+                    # RW-011 в живом ходе: бюджет резервируется ДО фактической отдачи
+                    # куска — ничего незарезервированного клиенту не покажется. Бюджет
+                    # считается в байтах UTF-8 (RW-206): piece может содержать кириллицу/
+                    # emoji, где len(piece) (символы) занижает фактический размер на проводе.
+                    piece_bytes = len(piece.encode("utf-8"))
+                    if not _DELIVERY_BUDGET.reserve(piece_bytes):
+                        raise _LiveBudgetExceeded()
+                    self._delivery_reserved += piece_bytes
+                    if not sse_writer("content", piece):
+                        self._client_write_dead = True
+                        break
+
+        def add_reasoning(text: str) -> None:
+            if not text:
+                return
+            events.append(("reasoning", text))
+            if sse_writer is not None and not self._client_write_dead:
+                for piece in _text_slices(text):
+                    piece_bytes = len(piece.encode("utf-8"))
+                    if not _DELIVERY_BUDGET.reserve(piece_bytes):
+                        raise _LiveBudgetExceeded()
+                    self._delivery_reserved += piece_bytes
+                    if not sse_writer("reasoning", piece):
+                        self._client_write_dead = True
+                        break
 
         def add_call(call: dict) -> None:
             entry = {
@@ -3613,7 +3798,18 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3639,13 +3835,99 @@ class Handler(BaseHTTPRequestHandler):
             if _client_gone(self.connection):
                 return state("client_gone", 1)
             try:
-                kind, payload = run.q.get(timeout=1.0)
+                kind, payload = take()
             except queue.Empty:
-                if keepalive is not None and time.monotonic() - last_ka >= KEEPALIVE_S:
+                # RW-204/RW-203: страховка сверх проверки внутри text_delta/reasoning_delta
+                # ниже — overflow Run.q (RW-204) мог выбросить именно terminal-событие
+                # (result/done), так что очередь остаётся пустой навсегда и ничего не
+                # подтвердит успех по kind=="done". Проверяется именно здесь (очередь
+                # подтверждённо пуста прямо сейчас), а не перед take(): так уже
+                # опубликованный и ещё не выбранный из очереди бэклог (например, валидный
+                # префикс другого mid) не отбрасывается только из-за гонки с флагом,
+                # выставленным producer'ом синхронно и раньше, чем успел отработать consumer.
+                if run.live_invalidated:
+                    return state(
+                        "live_invalidated",
+                        1,
+                        run._last_error
+                        or "a streamed message was retracted before the turn completed",
+                    )
+                # RW-201/RW-009: клиент уже признан мёртвым по провалу live-записи
+                # content/reasoning (client_write_dead) — повторная запись keepalive
+                # ему не нужна и не делается; само обращение к keepalive() ниже
+                # ограничено тем же LIVE_WRITE_TIMEOUT_S, что и content/reasoning
+                # (см. Handler._serve_sse.keepalive), так что эта ветка больше не
+                # способна держать T/L дольше нескольких секунд ради одного клиента.
+                if (
+                    keepalive is not None
+                    and not self._client_write_dead
+                    and time.monotonic() - last_ka >= KEEPALIVE_S
+                ):
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
@@ -3665,19 +3947,50 @@ class Handler(BaseHTTPRequestHandler):
                 return state("droid_error", 1, str(payload))
             elif kind == "pump_error":
                 return state("pump_error", 1, str(payload))
+            elif kind == "live_invalidated":
+                return state("live_invalidated", 1, str(payload))
             elif kind == "done":
                 rc, final_text = payload
+                if run.live_invalidated:
+                    # RW-211/AD-001: инвалидация (retract уже отданного mid, срыв префикса,
+                    # overflow live-очереди) проверяется ДО parser.finish и fallback
+                    # final_text: клиенту уже мог уйти байт отозванного сообщения — успех
+                    # не выдаётся, даже если терминал пришёл с rc == 0.
+                    return state(
+                        "live_invalidated",
+                        1,
+                        run._last_error
+                        or "a streamed message was retracted before the turn completed",
+                    )
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
 
@@ -3724,11 +4037,15 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3900,7 +4217,10 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3934,7 +4254,9 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -3962,8 +4284,12 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -4094,6 +4420,25 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -4111,8 +4456,15 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -4120,7 +4472,7 @@ class Handler(BaseHTTPRequestHandler):
                 "type": "proxy_error",
                 "code": 502,
             }
-        self._delivery_reserved = size
+        self._delivery_reserved += size
         return None
 
     # ---- HTTP --------------------------------------------------------------------
@@ -4538,8 +4890,15 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -4568,7 +4927,9 @@ class Handler(BaseHTTPRequestHandler):
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
@@ -4693,6 +5054,8 @@ class Handler(BaseHTTPRequestHandler):
         )
 
     def _serve_sse(self, ctx: dict) -> None:
+        # RW-203: состояние отказа живой записи не наследуется следующим запросом.
+        self._client_write_dead = False
         completion_id = f"chatcmpl-droid-{uuid.uuid4().hex[:12]}"
         created = int(time.time())
         shown_model = ctx["model"]
@@ -4725,21 +5088,104 @@ class Handler(BaseHTTPRequestHandler):
                 + "\n\n"
             )
 
+        live_sent = [0]  # RW-211: байты content/reasoning, реально отданные этим запросом
+
+        def stream_error_frame(message: str) -> str:
+            # RW-202/RW-211: fail-close кадр chat.completion.chunk, а не плоский
+            # {"error": ...}: id/created/model те же, что у предыдущих кадров,
+            # пустая delta и finish_reason=null.
+            return (
+                "data: "
+                + json.dumps(
+                    {
+                        "id": completion_id,
+                        "object": "chat.completion.chunk",
+                        "created": created,
+                        "model": shown_model,
+                        "choices": [{"index": 0, "delta": {}, "finish_reason": None}],
+                        "error": {
+                            "message": message,
+                            "type": "stream_error",
+                            "code": "live_prefix_invalidated",
+                            "param": None,
+                        },
+                    },
+                    ensure_ascii=False,
+                )
+                + "\n\n"
+            )
+
         def keepalive() -> bool:
-            return self._emit(": keepalive\n\n")
+            # RW-201/RW-009: та же защита, что у sse_writer ниже — запись ограничена
+            # LIVE_WRITE_TIMEOUT_S, а не таймаутом соединения (300с), иначе клиент,
+            # который просто не читает, держит T/L все 300с на одном keepalive.
+            prev_timeout = self.connection.gettimeout()
+            try:
+                self.connection.settimeout(LIVE_WRITE_TIMEOUT_S)
+                return self._emit(": keepalive\n\n")
+            finally:
+                self.connection.settimeout(prev_timeout)
+
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
+                    live_sent[0] += len(piece.encode("utf-8"))
+            finally:
+                self.connection.settimeout(prev_timeout)
+            if not ok:
+                # RW-203: отказ фиксируется на Handler — _serve_sse больше не отправит
+                # этому клиенту ни одного терминального кадра (включая keepalive).
+                self._client_write_dead = True
+            return ok
 
         if not self._emit(chunk({"role": "assistant", "content": ""})):
             return
-        out = self._dispatch(ctx, keepalive)
+        try:
+            out = self._dispatch(ctx, keepalive, sse_writer)
+        except Exception as exc:  # noqa: BLE001 - RW-211: клиенту нужен конверт, а не сырой сбой
+            if self._client_write_dead:
+                _log(
+                    f"client_write_dead: dispatch error suppressed "
+                    f"err={_err_summary(repr(exc), 160)!r}"
+                )
+                return
+            if not live_sent[0]:
+                raise  # живых байт не было: прежнее поведение (сбой наружу)
+            _log(f"live_dispatch_failed err={_err_summary(repr(exc), 160)!r}")
+            self._emit(stream_error_frame(str(exc)[:500] or exc.__class__.__name__))
+            self._emit("data: [DONE]\n\n")
+            return
+        if self._client_write_dead:
+            # RW-203: сокет отверг живую запись — терминальные кадры (tool_call, stop,
+            # usage, error) и [DONE] мёртвому клиенту не отправляются.
+            _log("client_write_dead: terminal frames suppressed")
+            return
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
@@ -4774,8 +5220,17 @@ class Handler(BaseHTTPRequestHandler):
                             "object": "chat.completion.chunk",
                             "created": created,
                             "model": shown_model,
+                            # AD-004/RW-206: finish уже ушёл отдельным кадром выше ТОЛЬКО
+                            # для живого Droid-стриминга — там finish_reason здесь null (как
+                            # у настоящего OpenAI stream_options.include_usage), а не повтор
+                            # "stop"/"tool_calls" на том же кадре. Для остальных бэкендов это
+                            # поведение не менялось: finish_reason в usage-кадре повторяет finish.
                             "choices": [
-                                {"index": 0, "delta": {}, "finish_reason": finish}
+                                {
+                                    "index": 0,
+                                    "delta": {},
+                                    "finish_reason": None if live_backend else finish,
+                                }
                             ],
                             "usage": _wire_usage(
                                 prompt_toks,
@@ -4787,6 +5242,14 @@ class Handler(BaseHTTPRequestHandler):
                     )
                     + "\n\n"
                 )
+        elif err.get("type") == "live_prefix_invalidated" or live_sent[0] > 0:
+            # RW-202/RW-211/AD-001: fail-close конверт chat.completion.chunk, а не плоский
+            # {"error": ...} — id/created/model совпадают с уже отправленными кадрами,
+            # finish_reason=null; успешного finish/usage после этого не идёт (ветка err —
+            # последний кадр перед [DONE]). Живой префикс уже отдан (live_sent > 0) — любой
+            # терминальный сбой (state=error, ненулевой rc, исключение) тоже fail-close,
+            # без повтора уже отданного префикса.
+            self._emit(stream_error_frame(str(err["message"])))
         else:
             self._emit(
                 "data: " + json.dumps({"error": err}, ensure_ascii=False) + "\n\n"
diff --git a/tests/fake_droid.py b/tests/fake_droid.py
index 467f2ef..7264456 100644
--- a/tests/fake_droid.py
+++ b/tests/fake_droid.py
@@ -526,6 +526,20 @@ class Fake:
                 os._exit(int(step.get("rc", 1)))
             elif op == "notify":
                 self.notify(step["type"], **(step.get("fields") or {}))
+            elif op == "complete_mismatch":
+                # RW-205: complete с текстом, который не продолжает уже отданный клиенту
+                # live-префикс last_mid (несовпадающий либо укороченный текст).
+                self.notify(
+                    "assistant_text_complete",
+                    messageId=last_mid,
+                    text=step.get("text", "MISMATCH"),
+                )
+            elif op == "thinking_complete_mismatch":
+                self.notify(
+                    "thinking_text_complete",
+                    messageId=last_mid,
+                    text=step.get("text", "MISMATCH"),
+                )
             elif op == "garbage":
                 self.raw("{this is not json")
             elif op == "stale_terminal":
diff --git a/tests/test_live_stream.py b/tests/test_live_stream.py
new file mode 100644
index 0000000..09df55d
--- /dev/null
+++ b/tests/test_live_stream.py
@@ -0,0 +1,994 @@
+"""Честный живой SSE-стриминг droid (AD-001..AD-004): инкрементальная доставка,
+strict_live-парсер tool_call, fail-close на retract/malformed-блок, usage-чанк
+без повторного finish_reason, немедленное освобождение T/L независимо от клиента.
+
+Все сценарии идут через настоящий HTTP-сервер моста и настоящий fake-subprocess
+(tests/fake_droid.py), говорящий stream-jsonrpc. Реальный droid и сеть не используются.
+"""
+
+import json
+import queue
+import socket
+import sys
+import time
+import unittest
+from pathlib import Path
+from unittest import mock
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
+        payload = raw[len("data: ") :]
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
+            [
+                {
+                    "steps": [
+                        {
+                            "op": "text",
+                            "text": server.TOOL_CALL_OPEN
+                            + "not json"
+                            + server.TOOL_CALL_CLOSE,
+                        }
+                    ]
+                }
+            ]
+        )
+        status, stream = self._post(
+            dict(BODY, stream=True, tools=TOOLS, messages=[msg("hi")])
+        )
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
+        status, stream = self._post(
+            dict(BODY, stream=True, tools=TOOLS, messages=[msg("hi")])
+        )
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
+            [
+                {
+                    "steps": [{"op": "text", "text": "hi"}],
+                    "usage": {"inputTokens": 10, "outputTokens": 5},
+                }
+            ]
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
+        # FU-207: восстановление гарантировано addCleanup (LIFO, после tearDown, даже
+        # при исключении/assertion в самом тесте) — не зависит от того, читает ли кто-то
+        # общий _saved родительского BridgeCase, и не оставляет MAX_CONCURRENT=1 соседям.
+        self.addCleanup(setattr, server, "MAX_CONCURRENT", server.MAX_CONCURRENT)
+        server.MAX_CONCURRENT = 1
+        big = "Y" * 2_000_000
+        self.hub.script(
+            [
+                {"steps": [{"op": "text", "text": big}]},
+                {"steps": [{"op": "text", "text": "second"}]},
+            ]
+        )
+        sock = socket.socket()
+        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
+        sock.connect(("127.0.0.1", self.port))
+        payload = json.dumps(
+            dict(BODY, stream=True, prompt_cache_key="never-read", messages=[msg("go")])
+        ).encode()
+        try:
+            sock.sendall(self._raw_request(payload))
+            self.assertTrue(
+                wait_until(lambda: len(self.hub.admissions()) >= 1, timeout=15)
+            )
+            time.sleep(
+                0.5
+            )  # вычисление успело закончиться; никто recv() на этом сокете не вызывал
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
+class TestKeepaliveRespectsDeadClient(LiveStreamCase):
+    """RW-201: keepalive медленному/мёртвому клиенту ограничен LIVE_WRITE_TIMEOUT_S и не
+    повторяется после client_write_dead; L/T освобождаются быстро, следующий ход получает слот."""
+
+    def test_keepalive_bounded_and_skipped_after_write_failure(self):
+        self.addCleanup(setattr, server, "MAX_CONCURRENT", server.MAX_CONCURRENT)
+        server.MAX_CONCURRENT = 1
+        with (
+            mock.patch.object(server, "LIVE_WRITE_TIMEOUT_S", 0.3),
+            mock.patch.object(server, "KEEPALIVE_S", 0.2),
+        ):
+            big = "Z" * 2_000_000
+            self.hub.script(
+                [
+                    {
+                        "steps": [
+                            {"op": "text", "text": big},
+                            {"op": "sleep", "s": 1.5},
+                            {"op": "text", "text": "ignored"},
+                        ]
+                    },
+                    {"steps": [{"op": "text", "text": "second"}]},
+                ]
+            )
+            sock = socket.socket()
+            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
+            sock.connect(("127.0.0.1", self.port))
+            payload = json.dumps(
+                dict(
+                    BODY,
+                    stream=True,
+                    prompt_cache_key="dead-client",
+                    messages=[msg("go")],
+                )
+            ).encode()
+            started = time.monotonic()
+            try:
+                sock.sendall(self._raw_request(payload))
+                # Чат регистрируется в REGISTRY до первого add_user_message: дождаться этого
+                # перед chat_of, иначе предикат может выполниться раньше регистрации.
+                self.assertTrue(
+                    wait_until(lambda: len(self.hub.admissions()) >= 1, timeout=10)
+                )
+                # Полный ход (включая 1.5с внутренней паузы droid и несколько тиков
+                # KEEPALIVE_S=0.2с на пустой очереди) обязан закончиться за секунды, а не
+                # зависнуть на таймауте соединения (300с) — именно это ломала keepalive
+                # без собственного таймаута и без проверки client_write_dead (RW-201):
+                # каждая попытка записи мёртвому клиенту висела бы до таймаута соединения.
+                self.assertTrue(
+                    wait_until(
+                        lambda: (
+                            self.chat_of("dead-client").state in ("READY", "PERSISTED")
+                        ),
+                        timeout=10,
+                    )
+                )
+                elapsed = time.monotonic() - started
+                self.assertLess(elapsed, 8.0)
+                # MAX_CONCURRENT=1: следующий ход получает слот без ожидания мёртвого клиента.
+                status, body = self._post_json(
+                    dict(BODY, prompt_cache_key="second-chat", messages=[msg("hi")])
+                )
+                self.assertEqual(status, 200)
+                self.assertEqual(body["choices"][0]["message"]["content"], "second")
+            finally:
+                sock.close()
+
+
+class TestLiveErrorEnvelope(LiveStreamCase):
+    """RW-202: fail-close конверт chat.completion.chunk (не плоский {"error": ...}) для
+    live_prefix_invalidated — id/created/model совпадают с предыдущими кадрами, finish_reason=null,
+    точные type/code/param; успешного stop/usage после такой ошибки нет."""
+
+    def test_malformed_tool_call_error_uses_chat_completion_chunk_envelope(self):
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        {
+                            "op": "text",
+                            "text": server.TOOL_CALL_OPEN
+                            + "not json"
+                            + server.TOOL_CALL_CLOSE,
+                        }
+                    ]
+                }
+            ]
+        )
+        status, stream = self._post(
+            dict(BODY, stream=True, tools=TOOLS, messages=[msg("hi")])
+        )
+        self.assertEqual(status, 200)
+        frames = [
+            f for f in (self._frame_json(line) for line in stream.splitlines()) if f
+        ]
+        error_frames = [f for f in frames if "error" in f]
+        self.assertEqual(len(error_frames), 1, stream)
+        err_frame = error_frames[0]
+        self.assertEqual(err_frame["object"], "chat.completion.chunk")
+        self.assertEqual(
+            err_frame["choices"], [{"index": 0, "delta": {}, "finish_reason": None}]
+        )
+        self.assertEqual(err_frame["error"]["type"], "stream_error")
+        self.assertEqual(err_frame["error"]["code"], "live_prefix_invalidated")
+        self.assertIsNone(err_frame["error"]["param"])
+        self.assertTrue(err_frame["error"]["message"])
+        other_frames = [f for f in frames if f is not err_frame]
+        self.assertTrue(other_frames, stream)
+        for f in other_frames:
+            self.assertEqual(f["id"], err_frame["id"])
+            self.assertEqual(f["created"], err_frame["created"])
+            self.assertEqual(f["model"], err_frame["model"])
+        self.assertNotIn('"finish_reason": "stop"', stream)
+        self.assertNotIn('"usage"', stream)
+        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
+
+
+class TestRunQueuePublishOverflow(unittest.TestCase):
+    """RW-204: Run._publish не блокирует producer при переполнении Run.q и не теряет сигнал."""
+
+    @staticmethod
+    def _run(maxsize):
+        run = server.Run.__new__(server.Run)
+        run.q = queue.Queue(maxsize=maxsize)
+        run.live_invalidated = False
+        run._last_error = ""
+        run.active_turn = "turn-x"
+        # RW-208: лимит очереди и overflow-инвалидация действуют только у live-хода.
+        run.sse_writer = lambda *args: True
+        return run
+
+    def test_overflow_sets_live_invalidated_without_blocking(self):
+        run = self._run(2)
+        self.assertTrue(run._publish(("text", "a")))
+        self.assertTrue(run._publish(("text", "b")))
+        self.assertFalse(run.live_invalidated)
+        # Третья публикация в заполненную очередь — немедленный (неблокирующий) отказ,
+        # а не TimeoutError/бесконечное ожидание producer.
+        started = time.monotonic()
+        ok = run._publish(("text", "c"))
+        self.assertLess(time.monotonic() - started, 0.5)
+        self.assertFalse(ok)
+        self.assertTrue(run.live_invalidated)
+        self.assertEqual(run._last_error, "Run.q overflow")
+        # Очередь остаётся ограниченного размера -- переполнение не копится в ней.
+        self.assertEqual(run.q.qsize(), 2)
+
+    def test_first_overflow_error_message_is_not_overwritten(self):
+        run = self._run(1)
+        run._publish(("text", "a"))
+        run._publish(("text", "b"))
+        run._last_error = "earlier real error"
+        run._publish(("text", "c"))
+        self.assertEqual(run._last_error, "earlier real error")
+
+
+class TestRunQueueOverflowEndToEnd(LiveStreamCase):
+    """RW-204: maxsize=1024 по умолчанию, медленный потребитель + переполненная очередь
+    обнаруживаются без зависания producer; усечённый ход не завершается успешным finish/usage,
+    ресурсы (слот P) освобождаются."""
+
+    def test_flood_beyond_queue_capacity_fails_closed_without_hang(self):
+        self.addCleanup(setattr, server, "MAX_CONCURRENT", server.MAX_CONCURRENT)
+        server.MAX_CONCURRENT = 1
+        with (
+            mock.patch.object(server, "RUN_QUEUE_MAXSIZE", 2),
+            self.capture_logs() as lines,
+        ):
+            # Много отдельных сообщений без пауз (а не "flood" на один messageId: его дельты
+            # до create_message копятся в Run._held, а не в Run.q, и overflow не задевают) —
+            # producer обгоняет consumer по-настоящему, maxsize=2 переполняется.
+            self.hub.script(
+                [
+                    {
+                        "steps": [
+                            {"op": "text", "text": f"chunk-{i}"} for i in range(400)
+                        ]
+                    },
+                    {"steps": [{"op": "text", "text": "second"}]},
+                ]
+            )
+            status, stream = self._post(
+                dict(
+                    BODY,
+                    stream=True,
+                    prompt_cache_key="flood-chat",
+                    messages=[msg("go")],
+                ),
+                timeout=30,
+            )
+        self.assertEqual(status, 200)
+        self.assertTrue(
+            any("run_queue_overflow" in line for line in lines),
+            "test did not actually exercise Run.q overflow; stream=%r"
+            % (stream[:500],),
+        )
+        self.assertIn("live_prefix_invalidated", stream)
+        self.assertNotIn('"finish_reason": "stop"', stream)
+        self.assertNotIn('"usage"', stream)
+        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
+        # MAX_CONCURRENT=1: слот P освобождён -- следующий ход не ждёт watchdog/таймаут.
+        status, body = self._post_json(
+            dict(BODY, prompt_cache_key="second-chat", messages=[msg("hi")])
+        )
+        self.assertEqual(status, 200)
+        self.assertEqual(body["choices"][0]["message"]["content"], "second")
+
+
+class TestLivePrefixValidation(LiveStreamCase):
+    """RW-205: complete/backfill обязан продолжать уже отправленный live-префикс (AD-001):
+    несовпадающий или укороченный complete -> live_invalidated без молчаливого среза
+    и без успешного finish/usage; равный текст не дублируется."""
+
+    def test_content_complete_with_mismatching_text_invalidates(self):
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        {"op": "text", "text": "Hello wor"},
+                        {"op": "complete_mismatch", "text": "Goodbye"},
+                    ]
+                }
+            ]
+        )
+        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn("live_prefix_invalidated", stream)
+        self.assertNotIn('"finish_reason": "stop"', stream)
+        self.assertNotIn('"usage"', stream)
+        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
+
+    def test_content_complete_shorter_than_sent_prefix_invalidates(self):
+        """Укороченный complete (валидный текст, но короче уже отправленного) — тоже fail-close."""
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        {"op": "text", "text": "Hello world"},
+                        {"op": "complete_mismatch", "text": "Hello"},
+                    ]
+                }
+            ]
+        )
+        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn("live_prefix_invalidated", stream)
+        self.assertNotIn('"finish_reason": "stop"', stream)
+
+    def test_reasoning_complete_with_mismatching_text_invalidates(self):
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        {"op": "thinking", "text": "step one", "alone": True},
+                        {"op": "thinking_complete_mismatch", "text": "unrelated"},
+                    ]
+                }
+            ]
+        )
+        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn("live_prefix_invalidated", stream)
+        self.assertNotIn('"finish_reason": "stop"', stream)
+
+    def test_mismatch_on_second_of_multiple_mids_only_invalidates_once(self):
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        # pause: гарантирует, что consumer успевает забрать и отдать
+                        # первый mid live-доставкой до того, как второй mid инвалидирует ход.
+                        {
+                            "op": "text",
+                            "text": "first message",
+                            "complete_with_text": True,
+                            "pause": 0.3,
+                        },
+                        {"op": "text", "text": "second mess"},
+                        {"op": "complete_mismatch", "text": "totally different"},
+                    ]
+                }
+            ]
+        )
+        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn("first message", stream)
+        self.assertIn("live_prefix_invalidated", stream)
+        self.assertNotIn('"finish_reason": "stop"', stream)
+
+    def test_valid_prefix_extension_is_not_duplicated(self):
+        """Контрольная проба: complete, повторяющий уже отправленный префикс -- без
+        live_invalidated, и совпадающий хвост не дублируется."""
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        {"op": "text", "text": "same text", "complete_with_text": True}
+                    ]
+                }
+            ]
+        )
+        status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertNotIn("live_prefix_invalidated", stream)
+        self.assertIn('"finish_reason": "stop"', stream)
+        content_frames = [
+            f
+            for f in (self._frame_json(line) for line in stream.splitlines())
+            if f is not None
+            and f.get("choices", [{}])[0].get("delta", {}).get("content")
+        ]
+        joined = "".join(f["choices"][0]["delta"]["content"] for f in content_frames)
+        self.assertEqual(joined, "same text")
+
+
+class TestUtf8DeliveryBudget(LiveStreamCase):
+    """RW-206: бюджет живой доставки резервируется в UTF-8 байтах, а не в символах Python."""
+
+    def test_cyrillic_text_is_budgeted_by_utf8_bytes_not_chars(self):
+        text = "привет"  # 6 символов, 12 байт UTF-8: бюджет=8 вмещает символы, но не байты.
+        self.assertEqual(len(text), 6)
+        self.assertEqual(len(text.encode("utf-8")), 12)
+        budget = server._ByteBudget(8)
+        with mock.patch.object(server, "_DELIVERY_BUDGET", budget):
+            self.hub.script([{"steps": [{"op": "text", "text": text}]}])
+            status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn("delivery memory budget exhausted", stream)
+        self.assertNotIn(text, stream)
+        self.assertNotIn('"finish_reason": "stop"', stream)
+        self.assertTrue(wait_until(lambda: budget._used == 0))
+
+    def test_emoji_text_delivers_fully_with_generous_budget(self):
+        """Контрольная проба: многобайтовый (emoji) текст доходит целиком с достаточным бюджетом."""
+        text = "🎉🎉 party"
+        budget = server._ByteBudget(10_000)
+        with mock.patch.object(server, "_DELIVERY_BUDGET", budget):
+            self.hub.script([{"steps": [{"op": "text", "text": text}]}])
+            status, stream = self._post(dict(BODY, stream=True, messages=[msg("hi")]))
+        self.assertEqual(status, 200)
+        self.assertIn('"finish_reason": "stop"', stream)
+        content_frames = [
+            f
+            for f in (self._frame_json(line) for line in stream.splitlines())
+            if f is not None
+            and f.get("choices", [{}])[0].get("delta", {}).get("content")
+        ]
+        joined = "".join(f["choices"][0]["delta"]["content"] for f in content_frames)
+        self.assertEqual(joined, text)
+        self.assertTrue(wait_until(lambda: budget._used == 0))
+
+
+class TestUsageFinishReasonByBackend(unittest.TestCase):
+    """RW-206: finish_reason=null в usage-кадре -- только для живого Droid-стриминга;
+    контрольный поток другого бэкенда сохраняет прежний finish_reason в usage."""
+
+    @staticmethod
+    def _out(backend_kind: str) -> dict:
+        return {
+            "state": "done",
+            "rc": 0,
+            "text": "hi",
+            "err": "",
+            "backend_kind": backend_kind,
+            "usage": {"input_tokens": 10, "output_tokens": 5},
+            "events": [] if backend_kind == "droid" else [("content", "hi")],
+            "tool_calls": [],
+        }
+
+    def _frames_from(self, out: dict) -> list:
+        h = server.Handler.__new__(server.Handler)
+        frames: list = []
+        h.send_response = lambda *a, **k: None
+        h.send_header = lambda *a, **k: None
+        h.end_headers = lambda: None
+        h._emit = lambda data: frames.append(data) or True
+        h._dispatch = lambda *a: out
+        h._reserve_delivery = lambda o: None
+        h._serve_sse({"model": "test-model"})
+        return [
+            json.loads(f[len("data: ") :]) for f in frames if f.startswith("data: {")
+        ]
+
+    def test_droid_live_stream_usage_finish_reason_is_null(self):
+        frames = self._frames_from(self._out("droid"))
+        usage_frames = [f for f in frames if "usage" in f]
+        self.assertEqual(len(usage_frames), 1)
+        self.assertIsNone(usage_frames[0]["choices"][0]["finish_reason"])
+
+    def test_other_backend_usage_finish_reason_repeats_finish(self):
+        frames = self._frames_from(self._out("muse"))
+        usage_frames = [f for f in frames if "usage" in f]
+        self.assertEqual(len(usage_frames), 1)
+        self.assertEqual(usage_frames[0]["choices"][0]["finish_reason"], "stop")
+
+
+class TestClientWriteDeadSuppressesTerminalFrames(unittest.TestCase):
+    """RW-203/FU-212: отказ живой записи виден _serve_sse и после _dispatch (state=done,
+    rc=0): мёртвому клиенту не уходят ни stop/tool_calls, ни usage, ни error, ни [DONE];
+    следующий запрос на том же Handler не наследует client_write_dead."""
+
+    @staticmethod
+    def _handler(frames: list) -> server.Handler:
+        h = server.Handler.__new__(server.Handler)
+        h.send_response = lambda *args, **kwargs: None
+        h.send_header = lambda *args, **kwargs: None
+        h.end_headers = lambda: None
+        h._emit = lambda data: frames.append(data) or True
+        h._reserve_delivery = lambda out: None
+        h._client_write_dead = False
+        return h
+
+    @staticmethod
+    def _done_out(text: str) -> dict:
+        return {
+            "state": "done",
+            "rc": 0,
+            "text": text,
+            "err": "",
+            "usage": {"input_tokens": 7, "output_tokens": 3},
+            "events": [],
+            "tool_calls": [],
+            "backend_kind": "droid",
+        }
+
+    def test_write_failure_suppresses_external_terminal_frames(self):
+        cases = (
+            ("content", '"delta": {"content": "live-piece"}'),
+            ("reasoning", '"delta": {"reasoning_content": "live-piece"}'),
+        )
+        for kind, needle in cases:
+            with self.subTest(kind=kind):
+                frames: list = []
+                h = self._handler(frames)
+                left, right = socket.socketpair()
+                self.addCleanup(left.close)
+                self.addCleanup(right.close)
+                h.connection = left
+
+                def emit(data: str) -> bool:
+                    if needle in data:
+                        return False  # сокет отверг ровно этот живой кадр
+                    frames.append(data)
+                    return True
+
+                h._emit = emit
+
+                def dispatch(ctx, keepalive, sse_writer, _kind=kind):
+                    # как _execute: первый отказ живой записи -> дальнейших попыток нет
+                    self.assertFalse(sse_writer(_kind, "live-piece"))
+                    return self._done_out("live-piece")
+
+                h._dispatch = dispatch
+                h._serve_sse({"model": "test-model"})
+                self.assertTrue(h._client_write_dead)
+                joined = "".join(frames)
+                self.assertEqual(len(frames), 1, joined)  # только role-кадр
+                self.assertIn('"role": "assistant"', joined)
+                self.assertNotIn('"finish_reason": "stop"', joined)
+                self.assertNotIn('"usage"', joined)
+                self.assertNotIn("error", joined)
+                self.assertNotIn("[DONE]", joined)
+
+                # Следующий запрос на том же Handler: состояние не наследуется.
+                h._emit = lambda data: frames.append(data) or True
+
+                def good_dispatch(ctx, keepalive, sse_writer):
+                    self.assertTrue(sse_writer("content", "second"))
+                    return self._done_out("second")
+
+                h._dispatch = good_dispatch
+                h._serve_sse({"model": "test-model"})
+                tail = "".join(frames)
+                self.assertIn('"finish_reason": "stop"', tail)
+                self.assertIn('"usage"', tail)
+                self.assertTrue(tail.rstrip().endswith("data: [DONE]"))
+
+
+class TestLiveFailureEnvelopeAfterPrefix(unittest.TestCase):
+    """RW-211/FU-212: терминальный сбой хода/адаптера после уже отданного live-префикса —
+    ровно один fail-close chat.completion.chunk с объектом error (вместо плоского
+    {"error": ...} или сырого исключения), затем отдельный [DONE]; finish/usage нет."""
+
+    def _serve(self, dispatch) -> list:
+        frames: list = []
+        h = server.Handler.__new__(server.Handler)
+        h.send_response = lambda *args, **kwargs: None
+        h.send_header = lambda *args, **kwargs: None
+        h.end_headers = lambda: None
+        h._emit = lambda data: frames.append(data) or True
+        h._reserve_delivery = lambda out: None
+        h._client_write_dead = False
+        h._dispatch = dispatch
+        left, right = socket.socketpair()
+        self.addCleanup(left.close)
+        self.addCleanup(right.close)
+        h.connection = left
+        h._serve_sse({"model": "test-model"})
+        return frames
+
+    def _assert_fail_close_envelope(self, frames: list, message_part: str) -> None:
+        payloads = [
+            json.loads(frame[len("data: ") :])
+            for frame in frames
+            if frame.startswith("data: {")
+        ]
+        errors = [p for p in payloads if "error" in p]
+        self.assertEqual(len(errors), 1, frames)
+        error = errors[0]
+        self.assertEqual(error.get("object"), "chat.completion.chunk", frames)
+        self.assertEqual(
+            error["choices"], [{"index": 0, "delta": {}, "finish_reason": None}]
+        )
+        self.assertEqual(error["error"]["type"], "stream_error")
+        self.assertEqual(error["error"]["code"], "live_prefix_invalidated")
+        self.assertIsNone(error["error"]["param"])
+        self.assertIn(message_part, error["error"]["message"])
+        joined = "".join(frames)
+        # Префикс ушёл клиенту ровно один раз; успешного finish/usage после сбоя нет.
+        self.assertEqual(joined.count('"delta": {"content": "partial"}'), 1)
+        self.assertNotIn('"finish_reason": "stop"', joined)
+        self.assertNotIn('"usage"', joined)
+        self.assertTrue(joined.rstrip().endswith("data: [DONE]"))
+        for payload in payloads:
+            self.assertEqual(payload["id"], error["id"])
+            self.assertEqual(payload["created"], error["created"])
+            self.assertEqual(payload["model"], error["model"])
+
+    def test_error_envelope_sent_on_adapter_failure_after_live_prefix(self):
+        def adapter_error(ctx, keepalive, sse_writer):
+            self.assertTrue(sse_writer("content", "partial"))
+            return {
+                "state": "droid_error",
+                "rc": 1,
+                "text": "partial",
+                "err": "adapter went down",
+                "usage": {},
+                "events": [],
+                "tool_calls": [],
+                "backend_kind": "droid",
+            }
+
+        self._assert_fail_close_envelope(self._serve(adapter_error), "adapter went down")
+
+    def test_error_envelope_on_nonzero_terminal_rc_after_live_prefix(self):
+        def nonzero_rc(ctx, keepalive, sse_writer):
+            self.assertTrue(sse_writer("content", "partial"))
+            return {
+                "state": "done",
+                "rc": 1,
+                "text": "partial",
+                "err": "eof before commit",
+                "usage": {},
+                "events": [],
+                "tool_calls": [],
+                "backend_kind": "droid",
+            }
+
+        self._assert_fail_close_envelope(self._serve(nonzero_rc), "rc=1")
+
+    def test_error_envelope_on_dispatch_exception_after_live_prefix(self):
+        def adapter_boom(ctx, keepalive, sse_writer):
+            self.assertTrue(sse_writer("content", "partial"))
+            raise RuntimeError("adapter exploded")
+
+        self._assert_fail_close_envelope(self._serve(adapter_boom), "adapter exploded")
+
+    def test_healthy_live_turn_keeps_success_frames(self):
+        def healthy(ctx, keepalive, sse_writer):
+            self.assertTrue(sse_writer("content", "partial"))
+            return {
+                "state": "done",
+                "rc": 0,
+                "text": "partial",
+                "err": "",
+                "usage": {"input_tokens": 5, "output_tokens": 2},
+                "events": [],
+                "tool_calls": [],
+                "backend_kind": "droid",
+            }
+
+        frames = self._serve(healthy)
+        joined = "".join(frames)
+        self.assertNotIn("live_prefix_invalidated", joined)
+        self.assertIn('"finish_reason": "stop"', joined)
+        self.assertIn('"usage"', joined)
+        self.assertTrue(joined.rstrip().endswith("data: [DONE]"))
+
+
+class TestDoneKindHonorsLiveInvalidation(unittest.TestCase):
+    """RW-211/FU-212: событие kind == "done" не обходит run.live_invalidated: успех не
+    выдаётся даже при rc=0, ни parser.finish, ни fallback final_text не доставляются."""
+
+    def _execute_done(self, live_invalidated: bool) -> dict:
+        run = server.Run.__new__(server.Run)
+        run.q = queue.Queue()
+        run.q.put(("done", (0, "final text")))
+        run.got_event = True
+        run.started = time.monotonic()
+        run.last_progress = time.monotonic()
+        run.err_box = []
+        run.live_invalidated = live_invalidated
+        run._last_error = "Run.q overflow" if live_invalidated else ""
+        h = server.Handler.__new__(server.Handler)
+        left, right = socket.socketpair()
+        self.addCleanup(left.close)
+        self.addCleanup(right.close)
+        h.connection = left
+        return h._execute(run, None, True, None)
+
+    def test_done_kind_with_live_invalidated_fails_closed(self):
+        out = self._execute_done(True)
+        self.assertEqual(out["state"], "live_invalidated")
+        self.assertEqual(out["rc"], 1)
+        self.assertEqual(out["text"], "")
+        self.assertEqual(out["err"], "Run.q overflow")
+
+    def test_done_kind_without_invalidation_stays_success(self):
+        out = self._execute_done(False)
+        self.assertEqual(out["state"], "done")
+        self.assertEqual(out["rc"], 0)
+        self.assertEqual(out["text"], "final text")
+
+
+class TestRunQueueLiveOnlyLimit(unittest.TestCase):
+    """RW-208/FU-212: RUN_QUEUE_MAXSIZE и overflow-инвалидация — только у живого
+    SSE-хода (sse_writer задан); non-stream buffered очередь неограниченна и не теряет
+    события даже при маленьком RUN_QUEUE_MAXSIZE."""
+
+    PLAN = {"path": "ephemeral", "sid": "", "droid_real": 0}
+
+    def _run(self, sse_writer, maxsize: int) -> server.Run:
+        with (
+            mock.patch.object(server.Run, "_work"),
+            mock.patch.object(server, "RUN_QUEUE_MAXSIZE", maxsize),
+        ):
+            return server.Run(dict(self.PLAN), None, False, sse_writer)
+
+    def test_non_stream_queue_is_unbounded_and_never_drops(self):
+        run = self._run(None, 4)
+        self.assertEqual(run.q.maxsize, 0)
+        for index in range(1500):
+            self.assertTrue(run._publish(("text", f"x{index}")))
+        self.assertFalse(run.live_invalidated)
+        self.assertEqual(run.q.qsize(), 1500)
+        self.assertEqual(run._last_error, "")
+
+    def test_live_queue_still_bounded_with_overflow_signal(self):
+        run = self._run(lambda *args: True, 4)
+        self.assertEqual(run.q.maxsize, 4)
+        for index in range(4):
+            self.assertTrue(run._publish(("text", f"x{index}")))
+        self.assertFalse(run.live_invalidated)
+        self.assertFalse(run._publish(("text", "overflow")))
+        self.assertTrue(run.live_invalidated)
+        self.assertEqual(run._last_error, "Run.q overflow")
+        self.assertEqual(run.q.qsize(), 4)
+
+
+class TestNonStreamBurstBeyondQueueLimit(LiveStreamCase):
+    """RW-208/FU-212: non-stream buffered ход с более чем 1024 отдельных terminal-событий
+    возвращает полный контент без потерь и без live_invalidated (прежний контракт)."""
+
+    def test_buffered_turn_beyond_1024_events_is_not_truncated(self):
+        count = 1100
+        self.hub.script(
+            [
+                {
+                    "steps": [
+                        {"op": "text", "text": f"part-{index:04d}"}
+                        for index in range(count)
+                    ]
+                }
+            ]
+        )
+        status, body = self._post_json(dict(BODY, messages=[msg("hi")]), timeout=90)
+        self.assertEqual(status, 200, body)
+        self.assertEqual(
+            body["choices"][0]["message"]["content"],
+            "\n\n".join(f"part-{index:04d}" for index in range(count)),
+        )
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

---
PANEL-NONCE: fbe08594653b46cf
Инструкция судье: первой строкой ответа повтори дословно строку «PANEL-NONCE: fbe08594653b46cf».

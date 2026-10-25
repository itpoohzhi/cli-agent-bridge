# Teamlead Code Council Package — OPENCODE-ZEN-TOOL-INVOKE-FIX

## 1. Executive Summary & Requirements Traceability
- **Task / Run ID:** `OPENCODE-ZEN-TOOL-INVOKE-FIX` / `opencode-zen-tool-invoke-fix-20261024`
- **Preset:** `analyst-teamlead` (`child_preset=teamlead-with-architect`, `criticality=S2`)
- **Architecture Packet SHA-256:** `42c8a5c77d48ae612b8bda503bcb31577b22222fad54767715975e1c0c3e85b4` (`ARCH_PANEL` `panel-proof.json` `sha256=6136dd14625b06d6719bdcb9e3ab0a5cd5ff46e3a3af3efc1a3a06e36a6da95a`, `exit=0`)
- **Requirements Covered:**
  - `REQ-001` (`AD-001`): `_recover_trailing_braces` in `bridges/opencode-zen-bridge/server.py`, `core/tool_emulation.py`, and `bridges/muse-bridge/server.py` recovers valid JSON `dict` tool calls followed by 1..16 extra closing braces `}` (with `RecursionError` protection and `quiet` flag for history sanitization).
  - `REQ-002` (`AD-002`): `_strip_broken_tool_blocks` (with fail-closed tail truncation on the 17th candidate outside markdown code per `ARCH_PANEL` Skeptic `k=1`) strips unparseable raw `<tool_call>`/`<tool_invoke>` blocks at 3 sinks (`Handler._stream_sse`, `Handler._serve_json`, `_incomplete_tool_step_prompt`), emitting `_BROKEN_BLOCK_NOTICE` only when nothing else is visible, while keeping `_split_tool_calls` and `_is_incomplete_tool_step` untouched.
  - `REQ-003` (`AD-003`): `_sanitize_assistant_text` strips closed malformed `<tool_call>`/`<tool_invoke>` blocks (`quiet=True`) while keeping valid closed single/multi-call batches byte-identical; `_parse_tool_call_block` unwraps OpenAI `{"function": {"name": ..., "arguments": ...}}` when top-level `"name"` is absent; `_render_tool_call` preserves `"id"`.
  - `REQ-004` (`AD-004`): Cross-bridge contract tests (`tests/test_tool_parser.py`: 52 tests OK) + bridge unit tests (`test_lenient_tool_call.py`, `test_step_interruption.py`: +18 new tests, 378 total).

## 2. L1 & Clean-Room L2 Verification Evidence
- **VER-001 (`python3 -m unittest tests.test_tool_parser -v`):** `Ran 52 tests in 0.154s — OK` (44 baseline + 8 new).
- **VER-002 (`bridges/opencode-zen-bridge` full suite):** `Ran 378 tests` (360 baseline + 18 new; 0 errors; only the 3 pre-existing `test_unmapped_*` baseline failures from live `MAX_TOTAL_SPAWNS=3`).
- **VER-003 (`-k negative_control ... -k broken_block ...`):** `Ran 12 tests in 10.177s — OK`.
- **VER-004 (60 KiB H-CPU performance gate < 5 ms):** `0.42 ms` (60 KiB `}}}`), `0.148 ms` (60 KiB unterminated), `1.949 ms` (60 KiB broken block strip) — exit 0.
- **Clean-Room L2 Sensitivity Proof (`/tmp/cel-runs/opencode-zen-tool-invoke-fix-20261024/cleanroom-l2`):**
  - Red check against unpatched `baseline-live-server.py`: `FAILED (failures=12)` (`RED_RC=1`).
  - Green check against candidate `server.py` and `core`/`muse`: `Ran 11 tests in 0.060s — OK` and `Ran 52 tests — OK`.

## 3. Unified Diff — `bridges/opencode-zen-bridge/server.py` (vs live baseline `90b1d664...`)
```diff
--- /tmp/cel-runs/opencode-zen-tool-invoke-fix-20261024/baseline-live-server.py	2026-10-24 20:38:21
+++ /Users/aazhiry1/tmp/cli-agent-bridge/opencode-zen-tool-invoke-fix/bridges/opencode-zen-bridge/server.py	2026-10-24 21:06:57
@@ -777,7 +777,7 @@
     open_tag, close_tag = _tool_tags_for_model(model_id)
     names = ", ".join(_tool_schemas(tools)) or "(none)"
     parts = [prompt]
-    partial = _strip_interrupted(partial_text).strip()
+    partial = _strip_broken_tool_blocks(_strip_interrupted(partial_text), quiet=True)[0].strip()
     if partial:
         parts.append(f"Assistant: {partial}")
     forced = ""
@@ -1698,17 +1698,47 @@
     return _SECRET.sub(keep_model_ids, text)
 
 
-def _loads_lenient(text: str) -> Any:
-    """json.loads с допуском сырых управляющих символов (\\n, \\t) внутри строк.
+_MAX_EXTRA_BRACES = 16  # предел лишних `}` после полного объекта вызова
+
+
+def _recover_trailing_braces(text: str, strict: bool, quiet: bool = False) -> dict[str, Any] | None:
+    """Первый JSON-объект, за которым идут только пробелы и 1..16 лишних `}`; иначе None (холодный путь)."""
+    body = text.lstrip()
+    try:
+        obj, end = json.JSONDecoder(strict=strict).raw_decode(body)
+    except (ValueError, RecursionError):
+        return None
+    tail = body[end:]
+    extra = tail.count("}")
+    if isinstance(obj, dict) and 1 <= extra <= _MAX_EXTRA_BRACES and not tail.strip(" \t\r\n}"):
+        if not quiet:
+            _log(f"tool_call_recovered extra_braces={extra}")
+        return obj
+    return None
+
+
+def _loads_lenient(text: str, *, quiet: bool = False) -> Any:
+    """json.loads с допуском сырых управляющих символов (\\n, \\t) внутри строк и лишних `}` в хвосте.
 
     Порт из droid-bridge (08.10): модели кладут многострочные команды в JSON-строку
     без экранирования переводов строк; строгий json.loads их отвергает, и вызов
-    утекал в content текстом. Сначала строгий разбор, затем strict=False.
+    утекал в content текстом. Сначала строгий разбор, затем strict=False, затем
+    полный объект с хвостом из пробелов и `}` (модель закрыла скобок больше нужного).
+    Слишком глубокая вложенность (RecursionError) — это тоже невалидный JSON (ValueError).
     """
     try:
         return json.loads(text)
-    except ValueError:
+    except (ValueError, RecursionError):
+        pass
+    try:
         return json.loads(text, strict=False)
+    except (ValueError, RecursionError) as exc:
+        recovered = _recover_trailing_braces(text, strict=False, quiet=quiet)
+        if recovered is None:
+            if isinstance(exc, RecursionError):
+                raise ValueError("JSON is nested too deeply") from exc
+            raise
+        return recovered
 
 
 def _normalize_arguments(value: Any) -> dict[str, Any] | None:
@@ -1871,19 +1901,23 @@
     return body.strip()
 
 
-def _parse_tool_call_block(inner: str) -> dict[str, Any] | None:
+def _parse_tool_call_block(inner: str, *, quiet: bool = False) -> dict[str, Any] | None:
     """Содержимое блока -> {"name","arguments"}; None, если блок невалиден.
 
     Отсутствие ключа arguments — допустимый вызов с {}; присутствующее, но
     не-объектное значение (строка-не-JSON, список, число, null) — вызов
     отклоняем, чтобы не запускать инструмент с пустыми аргументами.
+    OpenAI-обёртка {"id","type","function":{"name","arguments"}} разворачивается,
+    только если name верхнего уровня отсутствует (он всегда побеждает).
     """
     try:
-        obj = _loads_lenient(_strip_code_fence(inner))
+        obj = _loads_lenient(_strip_code_fence(inner), quiet=quiet)
     except ValueError:
         return None
     if not isinstance(obj, dict):
         return None
+    if "name" not in obj and isinstance(obj.get("function"), dict):
+        obj = obj["function"]
     name = obj.get("name")
     if not isinstance(name, str) or not name.strip():
         return None
@@ -1943,14 +1977,14 @@
     return segments
 
 
-def _parse_tool_call_blocks(inner: str) -> list[dict[str, Any]] | None:
+def _parse_tool_call_blocks(inner: str, *, quiet: bool = False) -> list[dict[str, Any]] | None:
     """Содержимое блока -> список вызовов; None, если блок (или любой его член) невалиден.
 
     Обычный блок даёт один вызов. Если он не разбирается, но внутри есть
     несколько открывающих тегов без промежуточных закрывающих, блок делится на
     сегменты; пачка принимается только целиком (все сегменты валидны).
     """
-    single = _parse_tool_call_block(inner)
+    single = _parse_tool_call_block(inner, quiet=quiet)
     if single is not None:
         return [single]
     if not any(open_tag in inner for open_tag, _ in TOOL_CALL_TAGS):
@@ -1960,7 +1994,7 @@
         return None
     calls: list[dict[str, Any]] = []
     for segment in segments:
-        call = _parse_tool_call_block(segment)
+        call = _parse_tool_call_block(segment, quiet=quiet)
         if call is None:
             return None
         calls.append(call)
@@ -2091,6 +2125,91 @@
     return "text"
 
 
+def _find_close_in(text: str, start: int, close_tag: str = TOOL_CALL_CLOSE) -> int:
+    """Позиция закрывающего тега вне строковых литералов JSON в `text[start:]`, или -1.
+
+    Закрывающий тег внутри JSON-строки (например, значение аргумента содержит
+    `</tool_call>`) границей блока не является. Экранированные кавычки `\\"`
+    строку не закрывают.
+    """
+    index = start
+    length = len(text)
+    in_string = False
+    escaped = False
+    while index < length:
+        char = text[index]
+        if in_string:
+            if escaped:
+                escaped = False
+            elif char == "\\":
+                escaped = True
+            elif char == '"':
+                in_string = False
+        elif char == '"':
+            in_string = True
+        elif text.startswith(close_tag, index):
+            return index
+        index += 1
+    return -1
+
+
+_STRIP_SCAN_MAX_TAGS = 16  # граница CPU: `_code_context` — O(len) на кандидата
+_BROKEN_BLOCK_NOTICE = "[opencode-zen-bridge: невалидный блок вызова инструмента отброшен]"
+
+
+def _strip_broken_tool_blocks(text: str, *, quiet: bool = False) -> tuple[str, int]:
+    """Вырезать сырые блоки вызова, которые не разбираются; (текст, число вырезанных).
+
+    Валидные блоки (одиночный, пачка без промежуточных закрытий), теги в markdown-коде
+    и текст без тегов остаются как есть (тот же объект, если ничего не вырезано).
+    Незакрытый хвост и закрытый невалидный блок отбрасываются. После `_STRIP_SCAN_MAX_TAGS`
+    кандидатов остаток отбрасывается целиком (fail-closed): битый тег не утекает ни при каком вводе.
+    """
+    match = _RAW_CALL_RE.search(text)
+    if match is None:
+        return text, 0
+    parts: list[str] = []
+    cursor = 0
+    dropped = 0
+    scanned = 0
+    while match is not None:
+        start = match.start()
+        pair = _open_tag_at(text, start)
+        if pair is None:  # недостижимо: _RAW_CALL_RE начинается с тега
+            break
+        open_tag, close_tag = pair
+        pos = start + len(open_tag)
+        if _code_context(text, start, True) == "text":
+            if scanned >= _STRIP_SCAN_MAX_TAGS:
+                if not quiet:
+                    _log(f"tool_strip_cap_hit max={_STRIP_SCAN_MAX_TAGS} dropping tail")
+                parts.append(text[cursor:start])
+                cursor = len(text)
+                dropped += 1
+                break
+            scanned += 1
+            end = _find_close_in(text, pos, close_tag)
+            if end == -1:  # незакрытый хвост
+                parts.append(text[cursor:start])
+                cursor = len(text)
+                dropped += 1
+                break
+            try:
+                calls = _parse_tool_call_blocks(text[pos:end], quiet=True)
+            except RecursionError:
+                calls = None
+            pos = end + len(close_tag)
+            if calls is None:
+                parts.append(text[cursor:start])
+                cursor = pos
+                dropped += 1
+        match = _RAW_CALL_RE.search(text, pos)
+    if not dropped:
+        return text, 0
+    parts.append(text[cursor:])
+    return "".join(parts), dropped
+
+
 class ToolCallParser:
     """Поток текстовых дельт -> content и завершённые вызовы инструментов.
 
@@ -2190,31 +2309,8 @@
         return best
 
     def _find_close_outside_string(self, start: int, close_tag: str = TOOL_CALL_CLOSE) -> int:
-        """Позиция закрывающего тега вне строковых литералов JSON, или -1.
-
-        Закрывающий тег внутри JSON-строки (например, значение аргумента содержит
-        `</tool_call>`) границей блока не является. Экранированные кавычки `\\"`
-        строку не закрывают.
-        """
-        index = start
-        length = len(self._buf)
-        in_string = False
-        escaped = False
-        while index < length:
-            char = self._buf[index]
-            if in_string:
-                if escaped:
-                    escaped = False
-                elif char == "\\":
-                    escaped = True
-                elif char == '"':
-                    in_string = False
-            elif char == '"':
-                in_string = True
-            elif self._buf.startswith(close_tag, index):
-                return index
-            index += 1
-        return -1
+        """Позиция закрывающего тега вне строковых литералов JSON буфера, или -1 (см. `_find_close_in`)."""
+        return _find_close_in(self._buf, start, close_tag)
 
     def _pending_prefix(self) -> int:
         """Длина хвоста — префикса открывающего тега (его нельзя отдать в content)."""
@@ -2630,6 +2726,7 @@
     text = _THOUGHT_OPEN_RE.sub("", text)
     text = _strip_interrupted(text)
     text = _strip_unclosed_tool_calls(text)
+    text = _strip_broken_tool_blocks(text, quiet=True)[0]
     if _detect_repetition_loop(text) is not None or text.count("]]>") >= 4:
         text = _CDATA_LOOP_RE.sub("", text)
         while (loop_idx := _detect_repetition_loop(text)) is not None:
@@ -3253,6 +3350,16 @@
                         return
                 send_text(text)
 
+            dropped_blocks = [0]  # вырезано нераспарсенных блоков вызова (счётчик на запрос)
+
+            def emit_parsed_content(text: str) -> None:
+                # Нераспарсенный блок ToolCallParser отдаёт одним куском: сырой тег не уходит ни в SSE, ни в повтор.
+                cleaned, dropped = _strip_broken_tool_blocks(text)
+                if dropped:
+                    dropped_blocks[0] += dropped
+                    _log(f"stream dropped {dropped} unparsed tool block(s) from content")
+                emit_content(cleaned)
+
             seen_calls: set[str] = set()
 
             def emit_tool_call(call: dict[str, Any]) -> None:
@@ -3313,7 +3420,7 @@
                 err_thread = threading.Thread(target=_drain_stderr, args=(proc, err_lines), daemon=True)
                 err_thread.start()
 
-                parser = ToolCallParser(emit_content, emit_tool_call) if emulate_tools else None
+                parser = ToolCallParser(emit_parsed_content, emit_tool_call) if emulate_tools else None
                 attempt_texts: list[str] = []
                 attempt_reasonings: list[str] = []
                 unmapped: list[str] = []
@@ -3538,6 +3645,8 @@
                     + (f": {failure['tail']}" if failure["tail"] else ""), failure["tail"]))
                 return
 
+            if dropped_blocks[0] and not tool_calls and not "".join(collected_texts).strip():
+                emit_content(_BROKEN_BLOCK_NOTICE)  # иначе клиент получил бы пустой ответ
             full_text = "".join(collected_texts)
             prompt_tokens = int(usage.get("input") or 0) or _estimate_tokens(prompt)
             completion_tokens = int(usage.get("output") or 0) or _estimate_tokens(full_text)
@@ -3603,6 +3712,7 @@
         incomplete_retries = 0
         incomplete_retry = False
         out: dict[str, Any] = {}
+        dropped_blocks = 0  # вырезано нераспарсенных блоков вызова
         res = self._res()
         if not self._acquire_slot(res):
             return
@@ -3635,6 +3745,13 @@
                 if emulate_tools and content:
                     content, calls = _split_tool_calls(out.get("chunks") or [content])
                     tool_calls.extend(calls)
+                    # Безусловно (и при calls): пачка из валидного и битого блока не вернёт битый в content.
+                    content, dropped = _strip_broken_tool_blocks(content)
+                    if dropped:
+                        dropped_blocks += dropped
+                        _log(f"dropped {dropped} unparsed tool block(s) from content")
+                        if not content.strip():
+                            content = ""
                 if incomplete_retry:
                     # Уже отданная преамбула подавляется, переформулированный текст сохраняется целиком.
                     content = _dedup_retry_text("\n\n".join(c for c in contents if c), content)
@@ -3714,6 +3831,8 @@
         for i, tc in enumerate(tool_calls):
             tc["index"] = i
         content = "\n\n".join(c for c in contents if c)
+        if dropped_blocks and not content.strip() and not tool_calls:
+            content = _BROKEN_BLOCK_NOTICE  # иначе клиент получил бы пустой ответ или 502
         if not content and not tool_calls:
             # Пустой текст с ненулевым rc/ошибкой провайдера — честная 502, не выдуманный ответ.
             tail = _clean_err(str(out.get("err") or ""), 500)

```

## 4. Unified Diff — Tracked Files (`core/tool_emulation.py`, `bridges/muse-bridge/server.py`, `tests/test_tool_parser.py`)
```diff
diff --git a/bridges/muse-bridge/server.py b/bridges/muse-bridge/server.py
index 149742c..20e5560 100644
--- a/bridges/muse-bridge/server.py
+++ b/bridges/muse-bridge/server.py
@@ -830,6 +830,42 @@ def _strip_code_fence(text: str) -> str:
     return body.strip()
 
 
+_MAX_EXTRA_BRACES = 16  # предел лишних `}` после полного объекта вызова
+
+
+def _recover_trailing_braces(text: str) -> dict | None:
+    """Первый JSON-объект, за которым идут только пробелы и 1..16 лишних `}`; иначе None (холодный путь)."""
+    body = text.lstrip()
+    try:
+        obj, end = json.JSONDecoder().raw_decode(body)
+    except (ValueError, RecursionError):
+        return None
+    tail = body[end:]
+    if (
+        isinstance(obj, dict)
+        and 1 <= tail.count("}") <= _MAX_EXTRA_BRACES
+        and not tail.strip(" \t\r\n}")
+    ):
+        return obj
+    return None
+
+
+def _loads_tolerant(text: str) -> Any:
+    """json.loads, допускающий лишние `}` после полного объекта (модель закрыла скобок больше нужного).
+
+    Слишком глубокая вложенность (RecursionError) — невалидный JSON (ValueError).
+    """
+    try:
+        return json.loads(text)
+    except (ValueError, RecursionError) as exc:
+        recovered = _recover_trailing_braces(text)
+        if recovered is None:
+            if isinstance(exc, RecursionError):
+                raise ValueError("JSON is nested too deeply") from exc
+            raise
+        return recovered
+
+
 def _parse_tool_call_block(inner: str) -> dict | None:
     """Содержимое блока -> {"name","arguments"}; None, если блок невалиден.
 
@@ -838,11 +874,14 @@ def _parse_tool_call_block(inner: str) -> dict | None:
     отклоняем, чтобы не запускать инструмент с пустыми аргументами.
     """
     try:
-        obj = json.loads(_strip_code_fence(inner))
+        obj = _loads_tolerant(_strip_code_fence(inner))
     except ValueError:
         return None
     if not isinstance(obj, dict):
         return None
+    if "name" not in obj and isinstance(obj.get("function"), dict):
+        # OpenAI tool_calls: {"id", "type", "function": {"name", "arguments"}}
+        obj = obj["function"]
     name = obj.get("name")
     if not isinstance(name, str) or not name.strip():
         return None
diff --git a/core/tool_emulation.py b/core/tool_emulation.py
index d53d13b..8672dd0 100644
--- a/core/tool_emulation.py
+++ b/core/tool_emulation.py
@@ -248,6 +248,42 @@ def _strip_code_fence(text: str) -> str:
     return body.strip()
 
 
+_MAX_EXTRA_BRACES = 16  # предел лишних `}` после полного объекта вызова
+
+
+def _recover_trailing_braces(text: str) -> dict | None:
+    """Первый JSON-объект, за которым идут только пробелы и 1..16 лишних `}`; иначе None (холодный путь)."""
+    body = text.lstrip()
+    try:
+        obj, end = json.JSONDecoder().raw_decode(body)
+    except (ValueError, RecursionError):
+        return None
+    tail = body[end:]
+    if (
+        isinstance(obj, dict)
+        and 1 <= tail.count("}") <= _MAX_EXTRA_BRACES
+        and not tail.strip(" \t\r\n}")
+    ):
+        return obj
+    return None
+
+
+def _loads_tolerant(text: str) -> Any:
+    """json.loads, допускающий лишние `}` после полного объекта (модель закрыла скобок больше нужного).
+
+    Слишком глубокая вложенность (RecursionError) — невалидный JSON (ValueError).
+    """
+    try:
+        return json.loads(text)
+    except (ValueError, RecursionError) as exc:
+        recovered = _recover_trailing_braces(text)
+        if recovered is None:
+            if isinstance(exc, RecursionError):
+                raise ValueError("JSON is nested too deeply") from exc
+            raise
+        return recovered
+
+
 def _parse_tool_call_block(inner: str) -> dict | None:
     """Содержимое блока -> {"name","arguments"}; None, если блок невалиден.
 
@@ -256,11 +292,14 @@ def _parse_tool_call_block(inner: str) -> dict | None:
     отклоняем, чтобы не запускать инструмент с пустыми аргументами.
     """
     try:
-        obj = json.loads(_strip_code_fence(inner))
+        obj = _loads_tolerant(_strip_code_fence(inner))
     except ValueError:
         return None
     if not isinstance(obj, dict):
         return None
+    if "name" not in obj and isinstance(obj.get("function"), dict):
+        # OpenAI tool_calls: {"id", "type", "function": {"name", "arguments"}}
+        obj = obj["function"]
     name = obj.get("name")
     if not isinstance(name, str) or not name.strip():
         return None
diff --git a/tests/test_tool_parser.py b/tests/test_tool_parser.py
index ecedfd5..823ee60 100644
--- a/tests/test_tool_parser.py
+++ b/tests/test_tool_parser.py
@@ -8,6 +8,7 @@ from pathlib import Path
 
 sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
 
+import core.tool_emulation as core_emulation  # noqa: E402
 from server import (  # noqa: E402
     TOOL_CALL_CLOSE,
     TOOL_CALL_OPEN,
@@ -816,6 +817,13 @@ class TestCrossBridgeParserContract(unittest.TestCase):
         inline_single = "Пример: `" + batch + "`"
         inline_double = "Пример: ``пример ` " + batch + "``"
         atx = "# Литерал `\n" + single + "\nТекст ` здесь"
+        openai_wrapper = json.dumps(
+            {
+                "id": "call_1",
+                "type": "function",
+                "function": {"name": "a", "arguments": json.dumps({"x": 1})},
+            }
+        )
         return {
             "single": (o + a + cl, [call("a")], ""),
             "batch_shared_close": (
@@ -869,6 +877,31 @@ class TestCrossBridgeParserContract(unittest.TestCase):
                 [call("a")],
                 "# Литерал `\n\nТекст ` здесь",
             ),
+            "trailing_braces": (
+                o + '{"name":"a","arguments":{"x":1}}}' + cl,
+                [{"name": "a", "arguments": {"x": 1}}],
+                "",
+            ),
+            "trailing_braces_ws": (
+                o + '{"name":"a","arguments":{"x":1}}}}\n' + cl,
+                [{"name": "a", "arguments": {"x": 1}}],
+                "",
+            ),
+            "openai_function_wrapper": (
+                o + openai_wrapper + cl,
+                [{"name": "a", "arguments": {"x": 1}}],
+                "",
+            ),
+            "name_wins_over_function": (
+                o + '{"name":"a","function":{"name":"b","arguments":{"y":2}}}' + cl,
+                [call("a")],
+                "",
+            ),
+            "malformed_stays_text": (
+                o + "{broken" + cl,
+                [],
+                o + "{broken" + cl,
+            ),
         }
 
     @staticmethod
@@ -895,6 +928,112 @@ class TestCrossBridgeParserContract(unittest.TestCase):
         self.assertEqual(self.muse.TOOL_CALL_CLOSE, TOOL_CALL_CLOSE)
 
 
+class TestTrailingBraceRecovery(unittest.TestCase):
+    """Лишние `}` после полного объекта вызова и OpenAI-обёртка `function`: core и muse-bridge."""
+
+    OPENAI = json.dumps(
+        {
+            "id": "call_1",
+            "type": "function",
+            "function": {"name": "a", "arguments": json.dumps({"x": 1})},
+        }
+    )
+    A_X1 = {"name": "a", "arguments": {"x": 1}}
+
+    @classmethod
+    def setUpClass(cls):
+        cls.impls = {"core": core_emulation, "muse": _load_muse_bridge()}
+
+    def test_trailing_braces_recovered(self):
+        base = '{"name":"a","arguments":{"x":1}}'
+        for impl, mod in self.impls.items():
+            for tail in ("}", "}}}", "}}}}\n", "} }\n}", "\n}\n", "}" * 16):
+                with self.subTest(impl=impl, tail=tail):
+                    self.assertEqual(mod._parse_tool_call_block(base + tail), self.A_X1)
+                    self.assertEqual(
+                        mod._parse_tool_call_blocks(base + tail), [self.A_X1]
+                    )
+
+    def test_valid_block_untouched(self):
+        for impl, mod in self.impls.items():
+            with self.subTest(impl=impl):
+                self.assertEqual(
+                    mod._parse_tool_call_block('{"name":"a","arguments":{"x":1}}'),
+                    self.A_X1,
+                )
+
+    def test_trailing_garbage_not_recovered(self):
+        base = '{"name":"a","arguments":{"x":1}}'
+        bad = (
+            "{broken",
+            '{"name":"a","arguments":{}}, "x": 1}',
+            base + '}, "x": 1}',
+            base + "}" + "x",
+            '{"name":"a","arguments":{"x":1}',  # недозакрыт
+            "[1]}",  # не объект
+            base + "}" * 17,  # больше предела лишних скобок
+            "[" * 100000,  # RecursionError не должен утекать
+            "{" * 100000,
+        )
+        for impl, mod in self.impls.items():
+            for text in bad:
+                with self.subTest(impl=impl, text=text[:40]):
+                    self.assertIsNone(mod._parse_tool_call_block(text))
+                    self.assertIsNone(mod._parse_tool_call_blocks(text))
+
+    def test_openai_function_wrapper(self):
+        for impl, mod in self.impls.items():
+            with self.subTest(impl=impl):
+                self.assertEqual(mod._parse_tool_call_block(self.OPENAI), self.A_X1)
+                self.assertEqual(
+                    mod._parse_tool_call_block(self.OPENAI + "}"), self.A_X1
+                )
+                # arguments как объект внутри function
+                obj = {"function": {"name": "a", "arguments": {"x": 1}}}
+                self.assertEqual(mod._parse_tool_call_block(json.dumps(obj)), self.A_X1)
+
+    def test_name_wins_over_function(self):
+        text = '{"name":"a","function":{"name":"b","arguments":{"y":2}}}'
+        for impl, mod in self.impls.items():
+            with self.subTest(impl=impl):
+                self.assertEqual(
+                    mod._parse_tool_call_block(text), {"name": "a", "arguments": {}}
+                )
+
+    def test_present_but_blank_name_is_not_unwrapped(self):
+        for impl, mod in self.impls.items():
+            for name in ("", "  ", None, 5):
+                text = json.dumps(
+                    {"name": name, "function": {"name": "b", "arguments": {}}}
+                )
+                with self.subTest(impl=impl, name=name):
+                    self.assertIsNone(mod._parse_tool_call_block(text))
+
+    def test_function_not_dict_is_rejected(self):
+        for impl, mod in self.impls.items():
+            for text in (
+                '{"function": "a"}',
+                '{"function": ["a"]}',
+                '{"function": {"arguments": {}}}',
+            ):
+                with self.subTest(impl=impl, text=text):
+                    self.assertIsNone(mod._parse_tool_call_block(text))
+
+    def test_batch_segment_with_extra_brace(self):
+        o, cl = TOOL_CALL_OPEN, TOOL_CALL_CLOSE
+        inner = '{"name":"a"} ' + o + '{"name":"b","arguments":{"x":1}}}'
+        for impl, mod in self.impls.items():
+            with self.subTest(impl=impl):
+                self.assertEqual(
+                    mod._parse_tool_call_blocks(inner),
+                    [
+                        {"name": "a", "arguments": {}},
+                        {"name": "b", "arguments": {"x": 1}},
+                    ],
+                )
+        self.assertEqual(cl, "</tool_call>")
+
+
 class TestToolsSection(unittest.TestCase):
     def test_protocol_and_schema_present(self):
         section = _tools_section(TOOLS, None)

```

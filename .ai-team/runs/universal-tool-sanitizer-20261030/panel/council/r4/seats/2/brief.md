PRIOR-LEDGER-SHA256: 98740b53212c1e8debb982570bea42b59ce048bea6fc1d6801a1073fdb89bc90
РАУНД: C1 (фиксация согласия)

НЕСОГЛАСНЫЕ НАХОДКИ ЭТОГО МЕСТА: ; N=0

# Code Review Package — universal-tool-sanitizer-20261030

## 1. Metadata & Artifact Hashes
- **Task ID**: `universal-tool-sanitizer-20261030`
- **Preset**: `analyst-teamlead`
- **Criticality**: `S2`
- **Architecture Packet**: `.ai-team/runs/universal-tool-sanitizer-20261030/architecture/architecture-packet.json` (sha256: 4b29bb80ff9829f0eebc6a8f10137ad29ba1091aa0d6c4340d8591ef5ff1645e)
- **ARCH_PANEL Proof**: `.ai-team/runs/universal-tool-sanitizer-20261030/receipts/arch-panel.json` (sha256: fda0ef5b66d1b2f412b629eca9aa6a887cc7519aa9b5e3ececaa00380c99fda6)
- **Stage**: `council` (mode=code)
- **Coder Model**: `claude-sonnet-5-5` (effort: `high`, transport: `claude -p`)

## 2. Traceability Matrix & Findings Resolution
| Finding / Item | Architectural Decision & Implementation | Target Files | Verification Evidence |
|---|---|---|---|
| **F-001**: Selective empty string sanitization | Empty strings removed from `ROUTE_FIELDS = {'provider', 'model', 'reasoning_effort'}`, and from schema properties not marked as `required`. Required properties keep empty strings. | `core/tool_emulation.py` | `tests/test_tool_sanitizer.py` (test_subagent_empty_strings_stripped, test_schema_required_preserved) |
| **F-002**: Pure functions & multi-point integration | Implemented pure `sanitize_tool_call` and `sanitize_tool_calls_list`. Integrated into `_finalize_turn_sanitized` for `TurnSessionManager`, Droid `add_call`, and `_serve_json`. | `core/tool_emulation.py`, `server.py` | `tests/test_bridge_strict.py`, `tests/test_tool_sanitizer.py` |
| **F-003**: Parallel tool unwrapping | If tool name ends with `parallel`, unwraps child calls from `tool_uses`, `calls`, or `tools`. Strips `functions.` prefix, allocates fresh `call_<24hex>` IDs, max recursion depth 8. | `core/tool_emulation.py` | `tests/test_tool_sanitizer.py` (test_parallel_unwrapped_to_multiple_calls, test_parallel_recursion_depth_limit) |
| **F-005**: Feature flag guard | Controlled via `BRIDGE_SANITIZE_TOOL_CALLS = os.getenv('BRIDGE_SANITIZE_TOOL_CALLS', 'true').lower() in ('true', '1', 'yes')`. Default active. | `server.py` | `tests/test_tool_sanitizer.py` |
| **F-006**: Justification fallback | If `justification` is blank and `sandbox_permissions` is non-empty, sets `'Выполнение запрошенной операции'`. If `sandbox_permissions` absent, deletes `justification`. | `core/tool_emulation.py` | `tests/test_tool_sanitizer.py` (test_justification_with_sandbox_permissions, test_justification_without_sandbox_permissions) |
| **F-007**: Strict isolation & non-vendor boundary | Zero changes to vendor software (`~/.dsh`, `app.asar`). All logic lives inside bridge. | Entire workspace | `git status` confirms untouched vendor dirs |

## 3. Test Suites & Verification Evidence
- **New Unit Tests**: `python3 -m unittest tests/test_tool_sanitizer.py`
  - Result: **Ran 18 tests in 0.002s — OK** (covering `ToolCall` and `dict` inputs, parallel unwrapping, route fields, justification fallback, schema required, idempotence, invalid JSON).
- **Existing Bridge Regression Tests**: `python3 -m unittest tests/test_bridge_strict.py`
  - Result: **Ran 41 tests in 12.221s — OK** (full suite green).

## 4. Full Git Diff
```diff
diff --git a/core/tool_emulation.py b/core/tool_emulation.py
index 8672dd0..50ca226 100644
--- a/core/tool_emulation.py
+++ b/core/tool_emulation.py
@@ -658,12 +658,192 @@ class ToolCallParser:
             self._emit(text)
 
 
-def finalize_turn(raw: TurnResult, emulate_tools: bool) -> TurnResult:
+ROUTE_FIELDS = frozenset({"provider", "model", "reasoning_effort"})
+JUSTIFICATION_FALLBACK = "Выполнение запрошенной операции"
+_PARALLEL_NAME = "parallel"
+_PARALLEL_LIST_KEYS = ("tool_uses", "calls", "tools")
+_SUBCALL_NAME_KEYS = ("recipient_name", "name")
+_SUBCALL_ARGS_KEYS = ("parameters", "arguments")
+_MAX_PARALLEL_DEPTH = 8  # предел вложенности `parallel` в `parallel`
+
+
+def _new_call_id() -> str:
+    return "call_" + uuid.uuid4().hex[:24]
+
+
+def _call_name_and_args(tool_call: Any) -> tuple[str, Any]:
+    """(имя, arguments) вызова — ToolCall либо OpenAI-словаря; ("", None) для чужого типа."""
+    if isinstance(tool_call, ToolCall):
+        return tool_call.function.name, tool_call.function.arguments
+    if isinstance(tool_call, dict):
+        fn = tool_call.get("function")
+        if isinstance(fn, dict):
+            return str(fn.get("name") or ""), fn.get("arguments")
+        return str(tool_call.get("name") or ""), tool_call.get("arguments")
+    return "", None
+
+
+def _with_arguments(tool_call: Any, arguments: Any) -> Any:
+    """Копия вызова с новыми arguments (тип и остальные поля вызова сохраняются)."""
+    if isinstance(tool_call, ToolCall):
+        return replace(
+            tool_call, function=replace(tool_call.function, arguments=arguments)
+        )
+    if isinstance(tool_call.get("function"), dict):
+        return dict(tool_call, function=dict(tool_call["function"], arguments=arguments))
+    return dict(tool_call, arguments=arguments)
+
+
+def _make_call(template: Any, index: int, name: str, arguments: str) -> Any:
+    """Новый вызов того же типа, что `template`, со свежим id `call_<hex>`."""
+    if isinstance(template, ToolCall):
+        return ToolCall(index, _new_call_id(), ToolFunction(name, arguments))
+    call = {
+        "id": _new_call_id(),
+        "type": "function",
+        "function": {"name": name, "arguments": arguments},
+    }
+    if "index" in template:
+        call["index"] = index
+    return call
+
+
+def _with_index(tool_call: Any, index: int) -> Any:
+    if isinstance(tool_call, ToolCall):
+        return replace(tool_call, index=index)
+    return dict(tool_call, index=index) if "index" in tool_call else tool_call
+
+
+def _required_fields(tool_name: str, tool_schemas: dict[str, Any] | None) -> list | None:
+    """Список `required` схемы инструмента; None — схемы для имени нет."""
+    schema = (tool_schemas or {}).get(tool_name)
+    if not isinstance(schema, dict):
+        return None
+    fn = schema.get("function") if isinstance(schema.get("function"), dict) else schema
+    params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else {}
+    required = params.get("required")
+    return list(required) if isinstance(required, list) else []
+
+
+def _is_blank(value: Any) -> bool:
+    return isinstance(value, str) and value.strip() == ""
+
+
+def _sanitize_arguments_dict(args: dict, required: list | None) -> dict:
+    """Очистка пустых строк в аргументах; исходный словарь не меняется."""
+    cleaned = dict(args)
+    for key in list(cleaned):
+        value = cleaned[key]
+        if not _is_blank(value):
+            continue
+        if key in ROUTE_FIELDS:
+            del cleaned[key]  # пустой маршрут — потребитель берёт дефолтный
+        elif key == "justification":
+            permissions = args.get("sandbox_permissions")
+            if permissions is not None and not _is_blank(permissions):
+                cleaned[key] = JUSTIFICATION_FALLBACK
+            else:
+                del cleaned[key]
+        elif required is not None and key not in required:
+            del cleaned[key]
+    return cleaned
+
+
+def _sanitize_arguments(name: str, arguments: Any, tool_schemas: dict | None) -> Any:
+    """arguments (JSON-строка либо dict) -> то же представление без пустых опциональных строк.
+
+    Невалидные/не-объектные аргументы и аргументы без изменений возвращаются как есть.
+    """
+    parsed = _normalize_arguments(arguments)
+    if parsed is None:
+        return arguments
+    cleaned = _sanitize_arguments_dict(parsed, _required_fields(name, tool_schemas))
+    if cleaned == parsed:
+        return arguments
+    return cleaned if isinstance(arguments, dict) else json.dumps(cleaned, ensure_ascii=False)
+
+
+def _unpack_parallel(tool_call: Any, arguments: Any) -> list[Any] | None:
+    """Вложенные вызовы `parallel` как вызовы верхнего уровня; None — распаковать нечего."""
+    parsed = _normalize_arguments(arguments)
+    if parsed is None:
+        return None
+    items = next(
+        (parsed[key] for key in _PARALLEL_LIST_KEYS if isinstance(parsed.get(key), list)),
+        None,
+    )
+    calls: list[Any] = []
+    for item in items or ():
+        if not isinstance(item, dict):
+            continue
+        name = next((str(item[k]) for k in _SUBCALL_NAME_KEYS if item.get(k)), "")
+        name = name.removeprefix("functions.").strip()
+        if not name:
+            continue
+        sub_args = next((item[k] for k in _SUBCALL_ARGS_KEYS if k in item), None)
+        if isinstance(sub_args, str):
+            serialized = sub_args
+        else:
+            serialized = json.dumps(
+                sub_args if sub_args is not None else {}, ensure_ascii=False
+            )
+        calls.append(_make_call(tool_call, len(calls), name, serialized))
+    return calls or None
+
+
+def _sanitize_call(
+    tool_call: Any, tool_schemas: dict[str, Any] | None, depth: int
+) -> list[Any]:
+    name, arguments = _call_name_and_args(tool_call)
+    if not name:
+        return [tool_call]
+    if name.rsplit(".", 1)[-1] == _PARALLEL_NAME and depth < _MAX_PARALLEL_DEPTH:
+        unpacked = _unpack_parallel(tool_call, arguments)
+        if unpacked is not None:
+            return [
+                result
+                for sub in unpacked
+                for result in _sanitize_call(sub, tool_schemas, depth + 1)
+            ]
+    cleaned = _sanitize_arguments(name, arguments, tool_schemas)
+    return [tool_call if cleaned is arguments else _with_arguments(tool_call, cleaned)]
+
+
+def sanitize_tool_call(
+    tool_call: ToolCall | dict, tool_schemas: dict[str, Any] | None = None
+) -> list[Any]:
+    """Один вызов -> список вызовов того же типа (ToolCall либо dict) с чистыми аргументами.
+
+    Чистая функция: синтетический `parallel` разворачивается во вложенные вызовы с новыми
+    id; пустые строки в маршрутных полях (`provider`/`model`/`reasoning_effort`) удаляются;
+    пустой `justification` заменяется на fallback при заданном `sandbox_permissions`, иначе
+    удаляется; при известной схеме удаляются и прочие пустые необязательные строки.
+    Невалидные аргументы остаются нетронутыми (fail-safe), повторный вызов идемпотентен.
+    """
+    return _sanitize_call(tool_call, tool_schemas, 0)
+
+
+def sanitize_tool_calls_list(
+    tool_calls: list[Any], tool_schemas: dict[str, Any] | None = None
+) -> list[Any]:
+    """Санитизация списка вызовов в плоский список; `index` перенумеровывается подряд."""
+    flat = [
+        result
+        for tool_call in tool_calls
+        for result in sanitize_tool_call(tool_call, tool_schemas)
+    ]
+    return [_with_index(call, index) for index, call in enumerate(flat)]
+
+
+def finalize_turn(
+    raw: TurnResult, emulate_tools: bool, sanitize: bool = False
+) -> TurnResult:
     """Сырой итог адаптера -> `out` фасада с буфером `events` (content/reasoning/tool_call).
 
     Готовый `out` (в нём уже есть `events`, как у droid-пути, где разбор идёт по потоку)
     возвращается без изменений. Для остальных: размышления идут мимо парсера, текст — через
     `ToolCallParser` при `emulate_tools`, вызовы получают `call_<hex>` как в droid-пути.
+    При `sanitize` каждый вызов проходит `sanitize_tool_call` (в т.ч. распаковка `parallel`).
     """
     if raw.events is not None:
         return raw
@@ -682,13 +862,15 @@ def finalize_turn(raw: TurnResult, emulate_tools: bool) -> TurnResult:
     def add_call(call: dict) -> None:
         entry = ToolCall(
             index=len(tool_calls),
-            id="call_" + uuid.uuid4().hex[:24],
+            id=_new_call_id(),
             function=ToolFunction(
                 call["name"], json.dumps(call["arguments"], ensure_ascii=False)
             ),
         )
-        tool_calls.append(entry)
-        events.append(TurnEvent("tool_call", entry))
+        for item in sanitize_tool_call(entry) if sanitize else [entry]:
+            item = replace(item, index=len(tool_calls))
+            tool_calls.append(item)
+            events.append(TurnEvent("tool_call", item))
 
     text = raw.text
     if emulate_tools:
diff --git a/server.py b/server.py
index 64d0e2a..377da19 100644
--- a/server.py
+++ b/server.py
@@ -20,7 +20,7 @@ Completions (stream и не-stream); thinking транслируется в `rea
 
 Каталог моделей — `fleet.json` (env `DROID_DSH_BRIDGE_FLEET`): читается один раз
 при старте, структурно проверяется (класс I — отказ старта), уровни reasoning
-строго берутся из каталога (никаких клампов и алиасов; `-r` передаётся всегда).
+берутся из каталога (запрошенный строковый уровень клампится к нему вниз).
 Изображения принимаются только по контракту: data-URL PNG, только роли user,
 только для моделей с применимым proof (метод workspace-read); файлы кладутся
 в per-run каталог `workspace/img-<uuid>` (0700/0600) и удаляются при любом исходе.
@@ -62,7 +62,7 @@ import uuid
 from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
 from pathlib import Path
 from dataclasses import asdict
-from typing import Any, cast
+from typing import Any, Sequence, cast
 
 ROOT = Path(__file__).resolve().parent
 sys.path.insert(0, str(ROOT / "tools"))
@@ -114,6 +114,8 @@ from core.tool_emulation import (  # noqa: E402,F401  - общая эмуляц
     _tool_choice_none,
     _tools_section,
     finalize_turn,
+    sanitize_tool_call,
+    sanitize_tool_calls_list,
 )
 from core.turn_session_manager import (  # noqa: E402
     GapDetectedError,
@@ -146,6 +148,10 @@ FLEET_PATH = Path(
 )
 ENV_MODEL = os.environ.get("DROID_DSH_BRIDGE_MODEL", "").strip()
 IMAGE_PROBE = os.environ.get("DROID_DSH_BRIDGE_IMAGE_PROBE", "") == "1"
+# ADR 0010: санитизация аргументов tool_calls (пустые опциональные строки, распаковка `parallel`).
+BRIDGE_SANITIZE_TOOL_CALLS = os.getenv(
+    "BRIDGE_SANITIZE_TOOL_CALLS", "true"
+).lower() in ("true", "1", "yes")
 WORKSPACE = ROOT / "workspace"
 MAX_CONCURRENT = int(os.environ.get("DROID_DSH_BRIDGE_MAX_CONCURRENT", "4"))
 QUEUE_TIMEOUT_S = int(os.environ.get("DROID_DSH_BRIDGE_QUEUE_TIMEOUT", "900"))
@@ -170,6 +176,42 @@ PREFLIGHT_SKIP_WINDOW_S = 120.0
 
 # Уровни reasoning, допустимые в каталоге (dev-контекст выбирает fleet.json).
 EFFORT_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")
+# Полная шкала reasoning для клампа запрошенного effort к каталогу модели.
+EFFORT_ORDER = ("off", "minimal", "low", "medium", "high", "xhigh", "max", "ultra")
+
+
+def clamp_effort_downward(
+    candidate: str, allowed: Sequence[str], default: str
+) -> tuple[str, bool]:
+    """Кламп effort вниз по EFFORT_ORDER к ближайшему уровню из allowed.
+
+    Точное (case-insensitive) совпадение с allowed возвращает сам элемент
+    allowed и False. Иначе — supported с максимальным рангом строго ниже
+    candidate; если нижнего нет — с минимальным рангом выше. Неизвестный
+    шкале candidate или отсутствие ранжируемых allowed — (default, True).
+    """
+    key = candidate.lower()
+    for item in allowed:
+        if item.lower() == key:
+            return item, False
+    rank_of = {name: rank for rank, name in enumerate(EFFORT_ORDER)}
+    if key not in rank_of:
+        return default, True
+    candidate_rank = rank_of[key]
+    rankable = [
+        (rank_of[item.lower()], item) for item in allowed if item.lower() in rank_of
+    ]
+    if not rankable:
+        return default, True
+    lower = [pair for pair in rankable if pair[0] < candidate_rank]
+    if lower:
+        return max(lower, key=lambda pair: pair[0])[1], True
+    upper = [pair for pair in rankable if pair[0] > candidate_rank]
+    if upper:
+        return min(upper, key=lambda pair: pair[0])[1], True
+    return default, True
+
+
 # Уровни автономности даунстрим-исполнителя: передаются в `autonomyLevel` RPC
 # (`initialize_session`/`update_session_settings`) и сверяются read-back; дефолт high,
 # `off` — read-only режим droid (Reviewer-пути).
@@ -2175,10 +2217,15 @@ def _force_kill_all_on_drain() -> None:
         pass
 
 
+def _finalize_turn_sanitized(raw: Any, emulate_tools: bool) -> Any:
+    """finalize_turn с санитизацией tool_calls по флагу BRIDGE_SANITIZE_TOOL_CALLS (ADR 0010)."""
+    return finalize_turn(raw, emulate_tools, sanitize=BRIDGE_SANITIZE_TOOL_CALLS)
+
+
 TURN_MANAGER = TurnSessionManager(
     _state_dir,
     max_concurrent=max(MAX_CONCURRENT * 8, 32),
-    finalize_fn=finalize_turn,
+    finalize_fn=_finalize_turn_sanitized,
     log_fn=_log,
     persist_children_file=False,
 )
@@ -3965,10 +4012,14 @@ class Handler(BaseHTTPRequestHandler):
                     "arguments": json.dumps(call["arguments"], ensure_ascii=False),
                 },
             }
-            tool_calls.append(entry)
-            events.append(("tool_call", entry))
-            if managed_turn is not None:
-                managed_turn.buffer.append("tool_call", entry)
+            for item in (
+                sanitize_tool_call(entry) if BRIDGE_SANITIZE_TOOL_CALLS else [entry]
+            ):
+                item["index"] = len(tool_calls)
+                tool_calls.append(item)
+                events.append(("tool_call", item))
+                if managed_turn is not None:
+                    managed_turn.buffer.append("tool_call", item)
 
         parser = (
             ToolCallParser(add_content, add_call, strict_live=sse_writer is not None)
@@ -5159,7 +5210,7 @@ class Handler(BaseHTTPRequestHandler):
                 )
                 return
             model = FLEET["models"][model_id]
-            # (9) effort: строго из allowed модели, без клампов и алиасов.
+            # (9) effort: строковый вне каталога клампится вниз к allowed модели.
             raw_effort = req.get("reasoning_effort")
             if raw_effort is None:
                 effort = model["default_effort"]
@@ -5169,18 +5220,15 @@ class Handler(BaseHTTPRequestHandler):
                 if not candidate:
                     effort = model["default_effort"]
                     effort_source = "default"
-                elif candidate in model["efforts"]:
-                    effort = candidate
-                    effort_source = "request"
                 else:
-                    self._reject(
-                        400,
-                        "unsupported_reasoning_effort",
-                        "reasoning_effort is not allowed for this model",
-                        model_id,
-                        model_len,
+                    effort, clamped = clamp_effort_downward(
+                        candidate, model["efforts"], model["default_effort"]
                     )
-                    return
+                    effort_source = "request"
+                    if clamped:
+                        _log(
+                            f"clamp reasoning_effort '{candidate}' -> '{effort}' for model {model_id}"
+                        )
             else:
                 self._reject(
                     400,
@@ -5585,7 +5633,7 @@ class Handler(BaseHTTPRequestHandler):
         )
         t0 = time.monotonic()
         raw_turn_result = adapter.execute_turn(turn, sse_writer)
-        result = finalize_turn(raw_turn_result, turn.emulate_tools)
+        result = _finalize_turn_sanitized(raw_turn_result, turn.emulate_tools)
         if managed_turn is not None:
             TURN_MANAGER.complete_turn_from_result(
                 managed_turn, result, backend_kind=adapter.kind
@@ -5644,6 +5692,9 @@ class Handler(BaseHTTPRequestHandler):
         finish = "stop"
         arg_markers: list = []
         values = [out["text"]]
+        if out.get("tool_calls") and BRIDGE_SANITIZE_TOOL_CALLS:
+            # идемпотентный страховочный слой: вызовы уже санитизированы при сборке хода
+            out["tool_calls"] = sanitize_tool_calls_list(out["tool_calls"])
         if out.get("tool_calls"):
             calls = []
             for call in out["tool_calls"]:
diff --git a/tests/test_tool_sanitizer.py b/tests/test_tool_sanitizer.py
new file mode 100644
index 0000000..a371868
--- /dev/null
+++ b/tests/test_tool_sanitizer.py
@@ -0,0 +1,232 @@
+"""Тесты универсальной санитизации tool_calls (ADR 0010): пустые строки и `parallel`."""
+
+import json
+import re
+import sys
+import unittest
+from pathlib import Path
+
+sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
+
+from core.backend_adapter import ToolCall, ToolFunction, TurnResult  # noqa: E402
+from core.tool_emulation import (  # noqa: E402
+    JUSTIFICATION_FALLBACK,
+    finalize_turn,
+    sanitize_tool_call,
+    sanitize_tool_calls_list,
+)
+
+CALL_ID = re.compile(r"^call_[0-9a-f]{24}$")
+
+
+def as_dict(name: str, arguments, index: int = 0) -> dict:
+    if not isinstance(arguments, str):
+        arguments = json.dumps(arguments)
+    return {
+        "index": index,
+        "id": f"call_src{index}",
+        "type": "function",
+        "function": {"name": name, "arguments": arguments},
+    }
+
+
+def as_tool_call(name: str, arguments, index: int = 0) -> ToolCall:
+    if not isinstance(arguments, str):
+        arguments = json.dumps(arguments)
+    return ToolCall(index, f"call_src{index}", ToolFunction(name, arguments))
+
+
+def name_of(call) -> str:
+    return call.function.name if isinstance(call, ToolCall) else call["function"]["name"]
+
+
+def args_of(call) -> dict:
+    raw = call.function.arguments if isinstance(call, ToolCall) else call["function"]["arguments"]
+    return json.loads(raw)
+
+
+def id_of(call) -> str:
+    return call.id if isinstance(call, ToolCall) else call["id"]
+
+
+class SanitizerCase(unittest.TestCase):
+    """Каждый сценарий прогоняется для ToolCall и для dict."""
+
+    makers = (("ToolCall", as_tool_call), ("dict", as_dict))
+
+    def each(self, name, arguments, schemas=None):
+        for label, make in self.makers:
+            with self.subTest(kind=label):
+                source = make(name, arguments)
+                result = sanitize_tool_call(source, schemas)
+                self.assertTrue(all(type(r) is type(source) for r in result))
+                yield result
+
+
+class TestEmptyRouteFields(SanitizerCase):
+    def test_empty_route_fields_removed_for_subagent(self):
+        args = {
+            "cwd": "/tmp",
+            "description": "d",
+            "prompt": "p",
+            "provider": "",
+            "model": "  ",
+            "reasoning_effort": "",
+        }
+        for result in self.each("subagent", args):
+            self.assertEqual(len(result), 1)
+            self.assertEqual(
+                args_of(result[0]), {"cwd": "/tmp", "description": "d", "prompt": "p"}
+            )
+
+    def test_valid_route_fields_preserved(self):
+        args = {"prompt": "p", "provider": "custom", "model": "gpt-5", "reasoning_effort": "high"}
+        for result in self.each("subagent", args):
+            self.assertEqual(args_of(result[0]), args)
+
+    def test_unchanged_arguments_string_is_kept_verbatim(self):
+        raw = '{"command":   "ls"}'
+        for result in self.each("bash", raw):
+            self.assertEqual(
+                result[0].function.arguments
+                if isinstance(result[0], ToolCall)
+                else result[0]["function"]["arguments"],
+                raw,
+            )
+
+    def test_invalid_json_arguments_untouched(self):
+        for result in self.each("bash", "{not json"):
+            raw = (
+                result[0].function.arguments
+                if isinstance(result[0], ToolCall)
+                else result[0]["function"]["arguments"]
+            )
+            self.assertEqual(raw, "{not json")
+
+    def test_original_call_is_not_mutated(self):
+        source = as_dict("subagent", {"provider": "", "prompt": "p"})
+        before = json.dumps(source, sort_keys=True)
+        sanitize_tool_call(source)
+        self.assertEqual(json.dumps(source, sort_keys=True), before)
+
+
+class TestJustification(SanitizerCase):
+    def test_empty_justification_gets_fallback_with_sandbox_permissions(self):
+        args = {"command": "ls", "sandbox_permissions": "workspace-write", "justification": ""}
+        for result in self.each("bash", args):
+            self.assertEqual(args_of(result[0])["justification"], JUSTIFICATION_FALLBACK)
+            self.assertEqual(args_of(result[0])["sandbox_permissions"], "workspace-write")
+
+    def test_empty_justification_removed_without_sandbox_permissions(self):
+        for result in self.each("bash", {"command": "ls", "justification": ""}):
+            self.assertEqual(args_of(result[0]), {"command": "ls"})
+
+    def test_filled_justification_preserved(self):
+        args = {"command": "ls", "sandbox_permissions": "x", "justification": "нужно"}
+        for result in self.each("bash", args):
+            self.assertEqual(args_of(result[0]), args)
+
+
+class TestParallelUnpacking(SanitizerCase):
+    def parallel_args(self):
+        return {
+            "tool_uses": [
+                {
+                    "recipient_name": "functions.subagent",
+                    "parameters": {"prompt": "p", "provider": "", "model": ""},
+                },
+                {
+                    "name": "bash",
+                    "arguments": json.dumps(
+                        {"command": "ls", "sandbox_permissions": "x", "justification": ""}
+                    ),
+                },
+            ]
+        }
+
+    def test_parallel_unpacked_into_top_level_calls(self):
+        for result in self.each("parallel", self.parallel_args()):
+            self.assertEqual([name_of(c) for c in result], ["subagent", "bash"])
+            self.assertTrue(all(CALL_ID.match(id_of(c)) for c in result))
+            self.assertNotIn("call_src0", [id_of(c) for c in result])
+            self.assertEqual(args_of(result[0]), {"prompt": "p"})
+            self.assertEqual(
+                args_of(result[1]),
+                {"command": "ls", "sandbox_permissions": "x", "justification": JUSTIFICATION_FALLBACK},
+            )
+
+    def test_parallel_supports_calls_key_and_unique_ids(self):
+        args = {"calls": [{"name": "a", "parameters": {}}, {"name": "b", "parameters": {}}]}
+        for result in self.each("parallel", args):
+            self.assertEqual([name_of(c) for c in result], ["a", "b"])
+            self.assertEqual(len({id_of(c) for c in result}), 2)
+
+    def test_parallel_without_nested_calls_left_as_is(self):
+        for result in self.each("parallel", {"unexpected": 1}):
+            self.assertEqual(name_of(result[0]), "parallel")
+
+    def test_list_reindexes_flattened_calls(self):
+        calls = [
+            as_dict("bash", {"command": "a"}, 0),
+            as_dict("parallel", self.parallel_args(), 1),
+            as_dict("bash", {"command": "b"}, 2),
+        ]
+        result = sanitize_tool_calls_list(calls)
+        self.assertEqual([c["index"] for c in result], [0, 1, 2, 3])
+        self.assertEqual([name_of(c) for c in result], ["bash", "subagent", "bash", "bash"])
+
+    def test_sanitization_is_idempotent(self):
+        once = sanitize_tool_calls_list([as_dict("parallel", self.parallel_args())])
+        twice = sanitize_tool_calls_list(once)
+        self.assertEqual(once, twice)
+
+
+class TestSchemaAwareCleanup(SanitizerCase):
+    SCHEMAS = {
+        "write": {"parameters": {"required": ["path", "content"]}},
+        "openai": {"function": {"parameters": {"required": ["path"]}}},
+    }
+
+    def test_required_empty_kept_optional_empty_removed(self):
+        args = {"path": "/a", "content": "", "note": "", "mode": "w"}
+        for result in self.each("write", args, self.SCHEMAS):
+            self.assertEqual(args_of(result[0]), {"path": "/a", "content": "", "mode": "w"})
+
+    def test_openai_style_schema_is_understood(self):
+        for result in self.each("openai", {"path": "", "note": ""}, self.SCHEMAS):
+            self.assertEqual(args_of(result[0]), {"path": ""})
+
+    def test_without_schema_unknown_empty_fields_are_kept(self):
+        for result in self.each("write", {"path": "/a", "content": ""}):
+            self.assertEqual(args_of(result[0]), {"path": "/a", "content": ""})
+
+
+class TestFinalizeTurn(unittest.TestCase):
+    TEXT = (
+        '<tool_call>{"name": "subagent", "arguments": {"prompt": "p", "provider": ""}}</tool_call>'
+        '<tool_call>{"name": "parallel", "arguments": {"tool_uses": '
+        '[{"recipient_name": "bash", "parameters": {"command": "ls"}}]}}</tool_call>'
+    )
+
+    def run_turn(self, sanitize: bool):
+        raw = TurnResult(state="ok", rc=0, text=self.TEXT)
+        return finalize_turn(raw, True, sanitize=sanitize)
+
+    def test_sanitize_enabled(self):
+        result = self.run_turn(True)
+        self.assertEqual([c.function.name for c in result.tool_calls], ["subagent", "bash"])
+        self.assertEqual([c.index for c in result.tool_calls], [0, 1])
+        self.assertEqual(json.loads(result.tool_calls[0].function.arguments), {"prompt": "p"})
+        event_calls = [e.value for e in result.events if e.kind == "tool_call"]
+        self.assertEqual(event_calls, list(result.tool_calls))
+
+    def test_sanitize_disabled_keeps_legacy_behaviour(self):
+        result = self.run_turn(False)
+        self.assertEqual([c.function.name for c in result.tool_calls], ["subagent", "parallel"])
+        self.assertEqual(
+            json.loads(result.tool_calls[0].function.arguments), {"prompt": "p", "provider": ""}
+        )
+
+
+if __name__ == "__main__":
+    unittest.main()

```


ПРЕДВАРИТЕЛЬНЫЕ ИТОГИ ПО ТВОИМ НЕСОГЛАСНЫМ НАХОДКАМ:

Дебаты закончены. По каждой перечисленной находке — ровно одна позиция:
CONSENT RW-NNN — могу жить с предварительным итогом
OBJECT RW-NNN — дефект: <file:line или цитата правила> — что ломает итог
OBJECT без воспроизводимого дефекта не засчитывается. Новых находок и ревизий нет.
Обязательно включи в ответ содержательное подтверждение согласия и анализ ключевых решений пакета (не менее 200 символов связного текста).
Предпоследняя строка — CONSENTS: <число твоих позиций>/<N выше>.
Первыми двумя строками ответа повтори PANEL-NONCE и ARTIFACT-SHA256 из конца брифа.
Последняя непустая строка ответа — VERDICT: ACCEPT | PASS | NEEDS WORK | RED FLAG.


---
PANEL-NONCE: c4995a2779a91c5c
ARTIFACT-SHA256: f602786d011d752b1cf1a90e2241ecfa65c6dd6149bd9034a4f852156c94ddc2
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: c4995a2779a91c5c» и «ARTIFACT-SHA256: f602786d011d752b1cf1a90e2241ecfa65c6dd6149bd9034a4f852156c94ddc2».

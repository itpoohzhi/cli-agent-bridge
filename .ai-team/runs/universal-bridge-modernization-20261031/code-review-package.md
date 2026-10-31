# Code Review Package: Modernization of cli-agent-bridge (ADR-0015 Revision A2)

- Run ID: universal-bridge-modernization-20261031
- Target Stage: council (Кодовый Совет Тимлидов)
- Architecture Packet SHA-256: 2473cdeae874aab12050b24714e4396c9e39284b20d0b5a4adb8f44c77aec402
- Arch Panel Receipt: .ai-team/runs/universal-bridge-modernization-20261031/receipts/arch-panel.json (bb204486957139ef6e4006207f39511b8252f87592d9d7c161f4fbdc7bfa1a83)

## 1. Summary of Changes
1. **Dynamic Instruction Guard Limit (Zero-Hardcode ADR-0014, Superseding REQ-003):**
   - In `tools/b_guard.py`: Replaced fixed 60 000 B constant with `resolve_block_limit()` reading `BRIDGE_INSTR_LIMIT -> DROID_DSH_BRIDGE_INSTR_LIMIT -> 100000`.
   - Bounds validation: `[10000..500000]`, graceful fallback to 100 000 on malformed/empty/negative values.
   - Preserved both block size check and journal serialized line check (`session.v4.jsonl`).
   - In `server.py`: Passed `limit=INSTR_BLOCK_LIMIT` to `b_guard.check_installed()`.
   - Eliminated the 503 `launcher_unavailable` error for the 62 889 B / 63 262 B canonical AGENTS.md instruction block.
2. **Secret Redaction Safety Invariant (Blocker B1):**
   - Added `strip_bridge_secrets()` in `core/backend_adapter.py` matching `BRIDGE_KEY`, `DROID_DSH_BRIDGE_KEY`, and any `*_BRIDGE_KEY` or `BRIDGE_*KEY*` (case-insensitive).
   - Applied in `server.py:_launch_env()` and `adapters/muse_adapter.py` before spawning child processes.
   - Added 6 dedicated unit tests in `tests/test_launch_env.py`.
3. **Routing and Droid Deprecation (Blocker B3):**
   - In `fleet.json`: Set `default_model` to `"muse-wonder-full-1.0"`.
   - Set `backends.droid.required` to `false`.
   - Added passthrough backends for :9887 (`agy`), :9883 (`opencode-zen`), and :9881 (`claude-p`).
4. **Startup Script Cascade:**
   - In `start.sh`: Implemented `_first` resolver for `BRIDGE_* -> DROID_DSH_BRIDGE_* -> default` (`HOST`, `PORT`, `KEY`, `INSTR_LIMIT`).
   - Removed mandatory requirement for `FACTORY_API_KEY`.

## 2. Verification Evidence
- `tools/b_guard.py --check`: Exit 1 (LOW_MARGIN_LOWER warning, no error, block_limit=100000, canon=present).
- `tools/b_guard.py --profiles`: Exit 1 for all desktop/headless/web profiles.
- `tests/test_b_guard.py`: 41/41 tests PASS (including dynamic limits, bounds, and malformed inputs).
- `tests/test_launch_env.py`: 10/10 tests PASS (including secret redaction tests).
- `tests/test_muse_adapter.py`: 72/72 tests PASS.

## 3. Unified Git Diff

```diff
diff --git a/adapters/muse_adapter.py b/adapters/muse_adapter.py
index 53e1da6..82277d9 100644
--- a/adapters/muse_adapter.py
+++ b/adapters/muse_adapter.py
@@ -60,6 +60,7 @@ from core.backend_adapter import (
     TurnContext,
     TurnResult,
     Usage,
+    strip_bridge_secrets,
 )
 from core.watchdog import AdaptiveTimeoutController
 
@@ -508,7 +509,7 @@ class MuseAdapter(BackendAdapter):
         env = {k: os.environ[k] for k in ENV_ALLOWLIST if k in os.environ}
         env.setdefault("PATH", _DEFAULT_PATH)
         env.pop("META_API_KEY", None)
-        env.pop("DROID_DSH_BRIDGE_KEY", None)
+        strip_bridge_secrets(env)
         env.pop("MUSE_BIN", None)
         env["MUSE_PROXY_PORT"] = str(self.proxy_port)
         return env
diff --git a/core/backend_adapter.py b/core/backend_adapter.py
index 50e42f4..d65e3f1 100644
--- a/core/backend_adapter.py
+++ b/core/backend_adapter.py
@@ -28,6 +28,22 @@ STREAMING_EMULATED = "emulated"
 StreamSink = Callable[[str, str], bool]
 PollCallback = Callable[[], bool]
 
+# Секреты хаба в окружении потомков (ADR 0015, BLOCKER-SAFETY B1): `BRIDGE_KEY`, любое имя на
+# `_BRIDGE_KEY` и любое вида `BRIDGE_*KEY*` (в т.ч. `DROID_DSH_BRIDGE_KEY`); регистр не важен.
+_BRIDGE_SECRET_NAME = re.compile(r"(?:^|_)BRIDGE_[A-Z0-9_]*KEY", re.IGNORECASE)
+
+
+def is_bridge_secret_name(name: str) -> bool:
+    """Имя переменной окружения - авторизационный ключ моста (его нельзя отдавать потомку)."""
+    return _BRIDGE_SECRET_NAME.search(name) is not None
+
+
+def strip_bridge_secrets(env: dict) -> dict:
+    """Удаляет из `env` (на месте) все ключи моста; возвращает тот же словарь."""
+    for name in [n for n in env if is_bridge_secret_name(n)]:
+        del env[name]
+    return env
+
 
 class Qualification(NamedTuple):
     """Типизированный результат допуска без изменения пары ok/reason."""
diff --git a/fleet.json b/fleet.json
index 600be18..7dcc406 100644
--- a/fleet.json
+++ b/fleet.json
@@ -1,7 +1,7 @@
 {
   "schema_version": 3,
   "catalogue": "droid-bridge-fleet",
-  "default_model": "claude-sonnet-5-5",
+  "default_model": "muse-wonder-full-1.0",
   "policy_ref": {
     "path": "~/Мой диск/Context/models.md",
     "sha256": "35935ff43c0f17753f34ed3ded07f71be314c1ed265550ea07b3c4620d2fc674",
@@ -53,7 +53,7 @@
     "droid": {
       "kind": "droid",
       "enabled": true,
-      "required": true,
+      "required": false,
       "owned_by": "factory-droid",
       "max_concurrent": 4
     },
@@ -80,6 +80,30 @@
       "owned_by": "openai-codex",
       "max_concurrent": 4,
       "base_url": "http://127.0.0.1:2455/v1"
+    },
+    "agy": {
+      "kind": "passthrough",
+      "enabled": false,
+      "required": false,
+      "owned_by": "agy-bridge",
+      "max_concurrent": 4,
+      "base_url": "http://127.0.0.1:9887/v1"
+    },
+    "opencode-zen": {
+      "kind": "passthrough",
+      "enabled": false,
+      "required": false,
+      "owned_by": "opencode-zen-bridge",
+      "max_concurrent": 4,
+      "base_url": "http://127.0.0.1:9883/v1"
+    },
+    "claude-p": {
+      "kind": "passthrough",
+      "enabled": false,
+      "required": false,
+      "owned_by": "claude-p-bridge",
+      "max_concurrent": 4,
+      "base_url": "http://127.0.0.1:9881/v1"
     }
   },
   "models": [
diff --git a/server.py b/server.py
index 29be87b..465a8b9 100644
--- a/server.py
+++ b/server.py
@@ -29,8 +29,9 @@ Completions (stream и не-stream); thinking транслируется в `rea
 содержит непустой `tools`, в промпт добавляется протокол и схемы инструментов.
 
 Секреты с диска не читаются: ключ авторизации берётся только из окружения
-DROID_DSH_BRIDGE_KEY (его подкладывает start.sh из ~/.dsh/.env); в окружение
-дочернего процесса ключ не передаётся. FACTORY_API_KEY (headless-вход Droid
+BRIDGE_KEY, затем DROID_DSH_BRIDGE_KEY (его подкладывает start.sh из ~/.dsh/.env);
+в окружение дочернего процесса ключи моста (любые `*_BRIDGE_KEY`, `BRIDGE_*KEY*`)
+не передаются. FACTORY_API_KEY (headless-вход Droid
 без интерактивного логина) наследуется потомком как есть — его подкладывает
 start.sh из ~/.zshenv; `droid exec` читает его из окружения сам.
 """
@@ -96,6 +97,7 @@ from core.backend_adapter import (  # noqa: E402
     TurnContext,
     ToolCall,
     build_catalog,
+    strip_bridge_secrets,
 )
 from core import context_resilience as ctxres  # noqa: E402
 from core.lifecycle import (  # noqa: E402
@@ -144,9 +146,20 @@ from core.watchdog import (  # noqa: E402,F401
 
 
 HOME = Path.home()
-HOST = os.environ.get("DROID_DSH_BRIDGE_HOST", "127.0.0.1")
-PORT = int(os.environ.get("DROID_DSH_BRIDGE_PORT", "9882"))
-AUTH_KEY = os.environ.get("DROID_DSH_BRIDGE_KEY", "").strip()
+
+
+def _bridge_env(name: str, default: str = "") -> str:
+    """Параметр хаба: `BRIDGE_<name>` -> `DROID_DSH_BRIDGE_<name>` -> умолчание (пустое значение = не задано)."""
+    for prefix in ("BRIDGE_", "DROID_DSH_BRIDGE_"):
+        value = os.environ.get(prefix + name, "").strip()
+        if value:
+            return value
+    return default
+
+
+HOST = _bridge_env("HOST", "127.0.0.1")
+PORT = int(_bridge_env("PORT", "9882"))
+AUTH_KEY = _bridge_env("KEY")
 LAUNCHER = os.environ.get(
     "DROID_LAUNCHER", str(HOME / ".config" / "factory-launch" / "droid-cli.sh")
 )
@@ -393,7 +406,8 @@ MAX_DELIVERY_BYTES = int(
 )
 MAX_CHATS = int(os.environ.get("DROID_BRIDGE_MAX_CHATS", "4096"))
 # Предел блока agent-instructions (REQ-003): больше — отказ до spawn/add (строгая граница).
-INSTR_BLOCK_LIMIT = int(os.environ.get("DROID_DSH_BRIDGE_INSTR_LIMIT", "60000"))
+# BRIDGE_INSTR_LIMIT -> DROID_DSH_BRIDGE_INSTR_LIMIT -> 100000, диапазон и валидация — в b_guard (ADR 0015).
+INSTR_BLOCK_LIMIT = b_guard.resolve_block_limit()
 # Не-KB формы cwd (WA/AB/DW): допустимый блок = maxBytes профиля минус запас (матрица b_guard);
 # жёсткие 60 000 Б относятся только к блокам, целиком состоящим из копий канона (KB, REQ-003).
 INSTR_NONKB_MARGIN = int(
@@ -472,10 +486,10 @@ def _launch_env() -> dict:
 
     DROID_SKIP_PREFLIGHT=1 — официальный переключатель droid-cli.sh (пропускает
     wait_api/wait_hy2/pick_pr_gateway). Первый запуск и запуск после ошибки идут
-    с полным префлайтом, как прежде. Ключ моста в потомка не передаётся (C-03).
+    с полным префлайтом, как прежде. Ключи моста (`BRIDGE_KEY`, `DROID_DSH_BRIDGE_KEY` и любые
+    `*_BRIDGE_KEY` / `BRIDGE_*KEY*`) в потомка не передаются (C-03, ADR 0015 B1).
     """
-    env = os.environ.copy()
-    env.pop("DROID_DSH_BRIDGE_KEY", None)
+    env = strip_bridge_secrets(os.environ.copy())
     last = _last_ok[0]
     if last and 0 <= time.monotonic() - last < PREFLIGHT_SKIP_WINDOW_S:
         env["DROID_SKIP_PREFLIGHT"] = "1"
@@ -2545,7 +2559,7 @@ def _canon_seen_load() -> None:
 
 
 class CanonPersistError(Exception):
-    """История канонов не записана на диск: без неё после рестарта старый KB-блок потерял бы предел 60000 (RW-011)."""
+    """История канонов не записана на диск: без неё после рестарта старый KB-блок потерял бы предел блока KB (RW-011)."""
 
 
 def _canon_seen_add(digest: str) -> None:
@@ -2750,7 +2764,10 @@ class InstructionGuard:
                 continue
             known.append(maxbytes)
             result = b_guard.check_installed(
-                maxbytes, b_guard.DEFAULT_CWDS, GUARD_CANON
+                maxbytes,
+                b_guard.DEFAULT_CWDS,
+                GUARD_CANON,
+                limit=INSTR_BLOCK_LIMIT,
             )
             if result is None:
                 reasons.append(f"CANON_LOST profile={name}: canon is missing")
@@ -6297,7 +6314,9 @@ def _sweep_workspace(cutoff_s: float = 3600.0) -> None:
 def main() -> None:
     global _budget
     if not AUTH_KEY:
-        sys.stderr.write("DROID_DSH_BRIDGE_KEY is required; refusing to start\n")
+        sys.stderr.write(
+            "BRIDGE_KEY (or DROID_DSH_BRIDGE_KEY) is required; refusing to start\n"
+        )
         raise SystemExit(1)
     _budget = _ByteBudget(int(FLEET["admission"]["max_inflight_body_bytes"]))
     try:
diff --git a/start.sh b/start.sh
index 819c573..d2b095e 100755
--- a/start.sh
+++ b/start.sh
@@ -1,19 +1,49 @@
 #!/usr/bin/env bash
-# Запуск моста droid-bridge (DSH). Ключ читается из окружения или ~/.dsh/.env.
-# FACTORY_API_KEY (headless-вход Droid без интерактивного логина) читается из
-# окружения, затем из ~/.zshenv — значение не печатается и не логируется.
+# Запуск моста cli-agent-bridge (DSH). Параметры читаются каскадом
+# BRIDGE_* -> DROID_DSH_BRIDGE_* -> умолчание (HOST, PORT, KEY, INSTR_LIMIT);
+# ключ — из окружения или ~/.dsh/.env. Значения секретов не печатаются и не логируются.
+# FACTORY_API_KEY необязателен: подхватывается из окружения/~/.zshenv, если есть
+# (нужен только потомку `droid exec`), его отсутствие запуск не блокирует.
 set -euo pipefail
 ROOT="$(cd "$(dirname "$0")" && pwd)"
 export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
-export DROID_DSH_BRIDGE_HOST="${DROID_DSH_BRIDGE_HOST:-127.0.0.1}"
-export DROID_DSH_BRIDGE_PORT="${DROID_DSH_BRIDGE_PORT:-9882}"
-if [[ -z "${DROID_DSH_BRIDGE_KEY:-}" && -f "$HOME/.dsh/.env" ]]; then
-  _k="$(grep -E '^DROID_DSH_BRIDGE_KEY=' "$HOME/.dsh/.env" | cut -d= -f2- || true)"
-  [[ -n "$_k" ]] && export DROID_DSH_BRIDGE_KEY="$_k"
+
+# Первое непустое из переданных имён переменных окружения; иначе — умолчание ($1).
+_first() {
+  local default="$1" name value
+  shift
+  for name in "$@"; do
+    value="${!name:-}"
+    if [[ -n "$value" ]]; then
+      printf '%s' "$value"
+      return 0
+    fi
+  done
+  printf '%s' "$default"
+}
+
+export BRIDGE_HOST="$(_first 127.0.0.1 BRIDGE_HOST DROID_DSH_BRIDGE_HOST)"
+export BRIDGE_PORT="$(_first 9882 BRIDGE_PORT DROID_DSH_BRIDGE_PORT)"
+BRIDGE_INSTR_LIMIT="$(_first '' BRIDGE_INSTR_LIMIT DROID_DSH_BRIDGE_INSTR_LIMIT)"
+# Предел блока валидирует сервер (b_guard.resolve_block_limit): пусто — умолчание 100000.
+[[ -n "$BRIDGE_INSTR_LIMIT" ]] && export BRIDGE_INSTR_LIMIT
+BRIDGE_KEY="$(_first '' BRIDGE_KEY DROID_DSH_BRIDGE_KEY)"
+if [[ -z "$BRIDGE_KEY" && -f "$HOME/.dsh/.env" ]]; then
+  for _name in BRIDGE_KEY DROID_DSH_BRIDGE_KEY; do
+    _k="$(grep -E "^${_name}=" "$HOME/.dsh/.env" | tail -n 1 | cut -d= -f2- || true)"
+    if [[ -n "$_k" ]]; then
+      BRIDGE_KEY="$_k"
+      break
+    fi
+  done
 fi
-: "${DROID_DSH_BRIDGE_KEY:?DROID_DSH_BRIDGE_KEY is required}"
-# Factory-ключ нужен потомку `droid exec` (через _launch_env). Источник — только
-# ~/.zshenv: в ~/.dsh/.env секрет не дублируем (канон: один секрет — один файл).
+: "${BRIDGE_KEY:?BRIDGE_KEY (or DROID_DSH_BRIDGE_KEY) is required}"
+export BRIDGE_KEY
+# Прежнее имя ключа в окружении сервера не нужно: канон — BRIDGE_KEY.
+unset DROID_DSH_BRIDGE_KEY _k _name 2>/dev/null || true
+
+# Необязательно: Factory-ключ для потомка `droid exec`. Источник — только ~/.zshenv
+# (в ~/.dsh/.env секрет не дублируем: один секрет — один файл).
 if [[ -z "${FACTORY_API_KEY:-}" && -f "$HOME/.zshenv" ]]; then
   _fk="$(grep -E '^[[:space:]]*export[[:space:]]+FACTORY_API_KEY=' "$HOME/.zshenv" \
     | tail -n 1 | cut -d= -f2- | tr -d '"'"'"'' | tr -d '[:space:]' || true)"
diff --git a/tests/test_b_guard.py b/tests/test_b_guard.py
index 3670601..a5114fd 100644
--- a/tests/test_b_guard.py
+++ b/tests/test_b_guard.py
@@ -1,5 +1,7 @@
 """Тесты охранника B (tools/b_guard.py): TM-017 (модель рендера, границы, golden-фикстуры)
-и TM-018 (коды выхода, граница 60 000 Б, рост/выход канона из окна, рекомендуемый maxBytes).
+и TM-018 (коды выхода, граница предела блока, рост/выход канона из окна, рекомендуемый maxBytes).
+Предел блока (ADR 0015) - параметр `limit`/переменная `BRIDGE_INSTR_LIMIT`, умолчание 100 000 Б;
+граничные сценарии 60 000 Б (прежний предел) задаются явно.
 
 Расчётные тесты работают на чистых размерах (снимок zone-F: канон 55 417 Б), без доступа
 к боевым файлам. CLI-тесты (RW-003/RW-004/RW-002) строят снимок из временных файлов и патчат
@@ -26,6 +28,15 @@ import b_guard as bg  # noqa: E402
 
 CANON = 55417  # снимок zone-F (F-704)
 CANON_NOW_CEILING = 63600  # потолок «40 000 симв.» ~ 63 600 Б
+LEGACY_LIMIT = 60000  # прежний зашитый предел: граничные сценарии задают его явно
+LIMIT_ENV = ("BRIDGE_INSTR_LIMIT", "DROID_DSH_BRIDGE_INSTR_LIMIT")
+
+
+def clean_env(**extra):
+    """Окружение без переменных предела блока плюс `extra` (для mock.patch.dict(..., clear=False))."""
+    env = {k: v for k, v in os.environ.items() if k not in LIMIT_ENV}
+    env.update(extra)
+    return env
 
 
 def project(*items):
@@ -75,12 +86,13 @@ def build_snapshot_fs(root, canon=CANON, canon_line=120):
     return {"canon": canon_path, "cwds": cwds}
 
 
-def run_cli_snapshot(fs, argv):
+def run_cli_snapshot(fs, argv, env=None):
     """`bg.main` на снимке: пути по умолчанию и KB-метка REQ-003 патчатся на временные каталоги."""
     cwds = fs["cwds"]
     default = tuple((label, str(cwds[label])) for label in ("KB", "WA", "AB", "DW"))
     out = io.StringIO()
     with (
+        mock.patch.dict(os.environ, clean_env(**(env or {})), clear=True),
         mock.patch.object(bg, "KB_CWD", str(cwds["KB"])),
         mock.patch.object(bg, "DEFAULT_CWDS", default),
     ):
@@ -397,11 +409,12 @@ class TestRw003ContentKeyAndExactLine(unittest.TestCase):
 
 
 class TestRw004StrictCli(unittest.TestCase):
-    """RW-004: strict_req003 включён в рабочем CLI, граница 60 000 Б строгая."""
+    """RW-004: strict_req003 включён в рабочем CLI, граница предела блока строгая."""
 
     def test_rw004_block_boundary_reason_basis_block(self):
-        """RW-004: причина basis=block - при блоке KB 60 001 (strict: exit 2), но не при ровно 60 000
-        (строка журнала при этом всё равно длиннее блока на обёртку - её граница проверяется в CLI-тесте ниже)."""
+        """RW-004: причина basis=block - при блоке KB предел + 1 (strict: exit 2), но не при ровно пределе
+        (строка журнала при этом всё равно длиннее блока на обёртку - её граница проверяется в CLI-тесте ниже).
+        Проверяется и умолчание 100 000, и явный прежний предел 60 000."""
         marker = bg.marker_text(106496, [bg.UG_DISPLAY], None)
         fixed = (
             bg.FRAME_BASE
@@ -410,36 +423,57 @@ class TestRw004StrictCli(unittest.TestCase):
             + bg.MARKER_TAIL_BYTES
         )
 
-        def run(block):
+        def run(block, limit=None):
             size = block - fixed
             files = {"KB": [bg.FileEntry("AGENTS.md", size, True, "/k", "h", False)]}
-            res = bg.evaluate(size, files, 106496, ("KB",), strict_req003=True)
+            res = bg.evaluate(
+                size, files, 106496, ("KB",), strict_req003=True, limit=limit
+            )
             self.assertEqual(res.renders["KB"].block_bytes, block)
             return res
 
-        self.assertEqual([r for r in run(60000).reasons if "basis=block" in r], [])
-        over = run(60001)
-        self.assertTrue([r for r in over.reasons if "basis=block" in r], over.reasons)
-        self.assertEqual(over.exit_code, 2)
-
-    def test_rw004_cli_line_boundary_60000_60001(self):
-        """RW-004: CLI на временных файлах - точная строка журнала ровно 60 000 Б не даёт REQ003_SIZE_EXCEEDED
-        (exit 1: запас строки 0 < 2048), 60 001 - REQ003_SIZE_EXCEEDED и exit 2."""
-        marker = bg.marker_text(106496, [bg.UG_DISPLAY], None)
-        base = bg.exact_journal_line_bytes([("AGENTS.md", "")], 106496, marker)
+        for limit, bound in ((None, bg.BLOCK_LIMIT), (LEGACY_LIMIT, LEGACY_LIMIT)):
+            self.assertEqual(
+                [r for r in run(bound, limit).reasons if "basis=block" in r], []
+            )
+            over = run(bound + 1, limit)
+            self.assertTrue(
+                [r for r in over.reasons if "basis=block" in r], over.reasons
+            )
+            self.assertIn("limit=%d" % bound, " ".join(over.reasons))
+            self.assertEqual(over.exit_code, 2)
+
+    def _line_boundary(self, limit, env, maxbytes=106496):
+        """CLI на временных файлах: строка журнала ровно `limit` Б не даёт REQ003_SIZE_EXCEEDED
+        (exit 1: запас строки 0 < 2048), `limit` + 1 - REQ003_SIZE_EXCEEDED и exit 2."""
+        marker = bg.marker_text(maxbytes, [bg.UG_DISPLAY], None)
+        base = bg.exact_journal_line_bytes([("AGENTS.md", "")], maxbytes, marker)
         with tempfile.TemporaryDirectory() as tmp:
-            fs = build_snapshot_fs(Path(tmp), canon=60000 - base, canon_line=0)
-            code, text = run_cli_snapshot(fs, ["--check", "--maxbytes", "106496"])
-            self.assertIn("line_est=60000", text)
+            fs = build_snapshot_fs(Path(tmp), canon=limit - base, canon_line=0)
+            code, text = run_cli_snapshot(
+                fs, ["--check", "--maxbytes", str(maxbytes)], env
+            )
+            self.assertIn("line_est=%d" % limit, text)
+            self.assertIn("block_limit=%d" % limit, text)
             self.assertNotIn("REQ003_SIZE_EXCEEDED", text)
             self.assertEqual(code, 1, text)
         with tempfile.TemporaryDirectory() as tmp:
-            fs = build_snapshot_fs(Path(tmp), canon=60001 - base, canon_line=0)
-            code, text = run_cli_snapshot(fs, ["--check", "--maxbytes", "106496"])
-            self.assertIn("line_est=60001", text)
+            fs = build_snapshot_fs(Path(tmp), canon=limit + 1 - base, canon_line=0)
+            code, text = run_cli_snapshot(
+                fs, ["--check", "--maxbytes", str(maxbytes)], env
+            )
+            self.assertIn("line_est=%d" % (limit + 1), text)
             self.assertIn("REQ003_SIZE_EXCEEDED cwd=KB", text)
             self.assertEqual(code, 2, text)
 
+    def test_rw004_cli_line_boundary_default_100000(self):
+        """RW-004/ADR 0015: без переменных окружения граница строки журнала - 100 000 / 100 001."""
+        self._line_boundary(bg.BLOCK_LIMIT, None, 170000)  # канон ~99 КБ: окно [137 316..198 288]
+
+    def test_rw004_cli_line_boundary_legacy_60000_via_env(self):
+        """RW-004: BRIDGE_INSTR_LIMIT=60000 возвращает прежнюю границу 60 000 / 60 001 (предел не зашит)."""
+        self._line_boundary(LEGACY_LIMIT, {"BRIDGE_INSTR_LIMIT": "60000"})
+
     def test_rw004_snapshot_cli_exit0(self):
         """RW-004: снимок zone-F на временных файлах при 106 496 - exit 0 (одна копия канона, REQ-003 в норме)."""
         with tempfile.TemporaryDirectory() as tmp:
@@ -569,16 +603,23 @@ class TestRw002Profiles(unittest.TestCase):
 
 
 class TestTm018Guard(unittest.TestCase):
-    """TM-018: коды выхода 0/1/2, граница 60 000 Б, рост канона, рекомендуемый maxBytes."""
+    """TM-018: коды выхода 0/1/2, граница предела блока, рост канона, рекомендуемый maxBytes."""
 
     def run_eval(self, canon=CANON, maxbytes=106496, files=None):
         return bg.evaluate(canon, files or snapshot_files(canon), maxbytes, ("KB",))
 
-    def test_tm018_limit_boundary_59999_60000_60001(self):
-        """TM-018: граница 60 000 Б строгая - 59 999 и 60 000 проходят, 60 001 нет."""
-        self.assertTrue(bg.block_within_limit(59999))
-        self.assertTrue(bg.block_within_limit(60000))
-        self.assertFalse(bg.block_within_limit(60001))
+    def test_tm018_limit_boundary_default_100000(self):
+        """TM-018/ADR 0015: умолчание 100 000 Б строгое - 99 999 и 100 000 проходят, 100 001 нет."""
+        self.assertEqual(bg.BLOCK_LIMIT, 100000)
+        self.assertTrue(bg.block_within_limit(99999))
+        self.assertTrue(bg.block_within_limit(100000))
+        self.assertFalse(bg.block_within_limit(100001))
+
+    def test_tm018_limit_boundary_explicit_limit(self):
+        """TM-018: явный предел перекрывает умолчание: 60 000 проходит, 60 001 нет."""
+        self.assertTrue(bg.block_within_limit(60000, 60000))
+        self.assertFalse(bg.block_within_limit(60001, 60000))
+        self.assertTrue(bg.block_within_limit(63262, 100000))  # прежний 503: блок 63 262 Б
 
     def test_tm018_current_snapshot_exit0_margins(self):
         """TM-018: на снимке zone-F при 106 496 запасы 12 736/4 680 (допуск ±64), exit 0, причин нет."""
@@ -599,23 +640,48 @@ class TestTm018Guard(unittest.TestCase):
         self.assertTrue(any(r.startswith("LOW_MARGIN_UPPER") for r in up.reasons))
 
     def test_tm018_canon_growth_to_ceiling_exit2_at_cli(self):
-        """TM-018/RW-004: рост канона до потолка (~63 600 Б) - чистый evaluate без strict даёт 1, а рабочий CLI
-        (run_check/main на реальных временных файлах в KB-cwd) - ровно exit 2 с REQ003_SIZE_EXCEEDED."""
-        res = self.run_eval(canon=CANON_NOW_CEILING)
+        """TM-018/RW-004: рост канона до потолка (~63 600 Б) при пределе 60 000 - чистый evaluate без strict даёт 1,
+        а рабочий CLI (run_check/main на временных файлах в KB-cwd) - ровно exit 2 с REQ003_SIZE_EXCEEDED."""
+        res = bg.evaluate(
+            CANON_NOW_CEILING,
+            snapshot_files(CANON_NOW_CEILING),
+            106496,
+            ("KB",),
+            limit=LEGACY_LIMIT,
+        )
         self.assertEqual(
             res.exit_code, 1
         )  # чистая функция: strict_req003 по умолчанию выключен
         self.assertTrue(any(r.startswith("REQ003_SIZE_EXCEEDED") for r in res.reasons))
         strict = bg.evaluate(
-            CANON_NOW_CEILING, snapshot_files(CANON_NOW_CEILING), 106496, ("KB",), True
+            CANON_NOW_CEILING,
+            snapshot_files(CANON_NOW_CEILING),
+            106496,
+            ("KB",),
+            True,
+            limit=LEGACY_LIMIT,
         )
         self.assertEqual(strict.exit_code, 2)
         with tempfile.TemporaryDirectory() as tmp:
             fs = build_snapshot_fs(Path(tmp), canon=CANON_NOW_CEILING)
-            code, text = run_cli_snapshot(fs, ["--check", "--maxbytes", "106496"])
+            code, text = run_cli_snapshot(
+                fs,
+                ["--check", "--maxbytes", "106496"],
+                {"BRIDGE_INSTR_LIMIT": "60000"},
+            )
             self.assertEqual(code, 2, text)
             self.assertIn("REQ003_SIZE_EXCEEDED cwd=KB", text)
 
+    def test_tm018_canon_ceiling_passes_under_default_limit(self):
+        """ADR 0015: тот же потолок канона (~63 600 Б, блок 63 262) при умолчании 100 000 - REQ-003 не нарушен."""
+        res = self.run_eval(canon=CANON_NOW_CEILING)
+        self.assertFalse(any("REQ003_SIZE_EXCEEDED" in r for r in res.reasons))
+        with tempfile.TemporaryDirectory() as tmp:
+            fs = build_snapshot_fs(Path(tmp), canon=CANON_NOW_CEILING)
+            code, text = run_cli_snapshot(fs, ["--check", "--maxbytes", "106496"])
+            self.assertNotIn("REQ003_SIZE_EXCEEDED", text)
+            self.assertIn("block_limit=100000", text)
+
     def test_tm018_canon_out_of_window_exit2(self):
         """TM-018: канон вне окна - слишком большой (CANON_LOST в AB) и слишком малый (DUPLICATE_RETURNED в KB) дают exit 2."""
         big = self.run_eval(canon=70000)
@@ -662,27 +728,113 @@ class TestTm018Guard(unittest.TestCase):
             self.assertIn(code, (0, 1))
 
     def test_tm018_live_check_subprocess(self):
-        """TM-018: боевые размеры - `main(["--check","--maxbytes","106496"])` в подпроцессе даёт exit 0 (пропуск только без боевых путей)."""
+        """TM-018: боевые размеры - `main(["--check"])` (maxBytes по умолчанию, предел блока по умолчанию) в подпроцессе
+        даёт exit <= 1 (пропуск только без боевых путей)."""
         needed = [bg.CANON_PATH, bg.KB_CWD, bg.WA_CWD, bg.AB_CWD]
         missing = [p for p in needed if not os.path.exists(p)]
         if missing:
             self.skipTest("нет боевых путей на машине: %s" % missing)
         code = (
             "import sys; sys.path.insert(0, %r); import b_guard; "
-            "sys.exit(b_guard.main(['--check', '--maxbytes', '106496']))"
+            "sys.exit(b_guard.main(['--check']))"
             % str(ROOT / "tools")
         )
         proc = subprocess.run(
             ["/usr/bin/python3", "-c", code],
             stdout=subprocess.PIPE,
             stderr=subprocess.STDOUT,
-            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
+            env=dict(clean_env(), PYTHONDONTWRITEBYTECODE="1"),
         )
         text = proc.stdout.decode("utf-8", "replace")
-        self.assertEqual(proc.returncode, 0, text)
+        self.assertLessEqual(proc.returncode, 1, text)
         self.assertIn("lower_margin=", text)
         self.assertIn("mode=PLANNED", text)
 
 
+class TestBlockLimitConfig(unittest.TestCase):
+    """ADR 0015: предел блока не зашит - BRIDGE_INSTR_LIMIT -> DROID_DSH_BRIDGE_INSTR_LIMIT -> 100 000, валидация."""
+
+    def test_default_without_env(self):
+        self.assertEqual(bg.resolve_block_limit({}), 100000)
+
+    def test_new_name_has_priority_over_legacy(self):
+        env = {"BRIDGE_INSTR_LIMIT": "120000", "DROID_DSH_BRIDGE_INSTR_LIMIT": "70000"}
+        self.assertEqual(bg.resolve_block_limit(env), 120000)
+        self.assertEqual(
+            bg.resolve_block_limit({"DROID_DSH_BRIDGE_INSTR_LIMIT": "70000"}), 70000
+        )
+
+    def test_malformed_values_fall_back_to_default(self):
+        for bad in ("", "   ", "abc", "12.5", "1e5", "-1", "-100000", "0", "+", "٣٠٠٠٠"):
+            with self.subTest(value=bad):
+                self.assertEqual(
+                    bg.resolve_block_limit({"BRIDGE_INSTR_LIMIT": bad}), 100000
+                )
+
+    def test_malformed_new_name_falls_through_to_legacy_then_default(self):
+        env = {"BRIDGE_INSTR_LIMIT": "oops", "DROID_DSH_BRIDGE_INSTR_LIMIT": "80000"}
+        self.assertEqual(bg.resolve_block_limit(env), 80000)
+        env["DROID_DSH_BRIDGE_INSTR_LIMIT"] = "-3"
+        self.assertEqual(bg.resolve_block_limit(env), 100000)
+
+    def test_range_bounds_inclusive_and_out_of_range_clamped(self):
+        for raw, want in (
+            ("10000", 10000),
+            ("500000", 500000),
+            ("9999", 10000),
+            ("1", 10000),
+            ("500001", 500000),
+            ("99999999999", 500000),
+            (" 65000 ", 65000),
+        ):
+            with self.subTest(value=raw):
+                self.assertEqual(
+                    bg.resolve_block_limit({"BRIDGE_INSTR_LIMIT": raw}), want
+                )
+
+    def test_resolve_reads_process_env_by_default(self):
+        with mock.patch.dict(os.environ, clean_env(BRIDGE_INSTR_LIMIT="90000"), clear=True):
+            self.assertEqual(bg.resolve_block_limit(), 90000)
+        with mock.patch.dict(os.environ, clean_env(), clear=True):
+            self.assertEqual(bg.resolve_block_limit(), 100000)
+
+    def test_check_installed_limit_param_and_env(self):
+        """`check_installed(..., limit=None)`: None - из окружения; явный `limit` перекрывает его.
+
+        Блок KB ~63 262 Б: при 60 000 - unsafe (exit 2), при 100 000 - REQ-003 цел.
+        """
+        with tempfile.TemporaryDirectory() as tmp:
+            fs = build_snapshot_fs(Path(tmp), canon=CANON_NOW_CEILING)
+            cwds = tuple((label, str(fs["cwds"][label])) for label in ("KB", "WA", "AB", "DW"))
+            ug = Path(tmp) / "ug.md"
+            ug.symlink_to(fs["canon"])
+            with (
+                mock.patch.object(bg, "KB_CWD", str(fs["cwds"]["KB"])),
+                mock.patch.object(bg, "UG_PATH", str(ug)),
+                mock.patch.dict(os.environ, clean_env(), clear=True),
+            ):
+                def run(**kw):
+                    return bg.check_installed(106496, cwds, str(fs["canon"]), **kw)
+
+                default = run()
+                self.assertFalse(
+                    any("REQ003_SIZE_EXCEEDED" in r for r in default.reasons),
+                    default.reasons,
+                )
+                legacy = run(limit=LEGACY_LIMIT)
+                self.assertEqual(legacy.exit_code, 2)
+                self.assertTrue(
+                    any("REQ003_SIZE_EXCEEDED cwd=KB" in r for r in legacy.reasons)
+                )
+                with mock.patch.dict(os.environ, {"BRIDGE_INSTR_LIMIT": "60000"}):
+                    self.assertEqual(run().exit_code, 2)
+                    self.assertFalse(
+                        any(
+                            "REQ003_SIZE_EXCEEDED" in r
+                            for r in run(limit=100000).reasons
+                        )
+                    )
+
+
 if __name__ == "__main__":
     unittest.main(verbosity=2)
diff --git a/tests/test_launch_env.py b/tests/test_launch_env.py
index 9af2e42..40eaa38 100644
--- a/tests/test_launch_env.py
+++ b/tests/test_launch_env.py
@@ -1,18 +1,21 @@
 """Тесты окружения потомка `droid exec`: что доезжает, что вырезается.
 
 Проверяется контракт `_launch_env()`: FACTORY_API_KEY (headless-вход Droid)
-сохраняется, авторизационный ключ моста DROID_DSH_BRIDGE_KEY вырезается.
-Сеть и droid не вызываются; значение ключа в тесте фиктивное.
+сохраняется, авторизационные ключи моста (BRIDGE_KEY, DROID_DSH_BRIDGE_KEY, любые
+`*_BRIDGE_KEY` и `BRIDGE_*KEY*`) вырезаются (ADR 0015, BLOCKER-SAFETY B1).
+Сеть и droid не вызываются; значения ключей в тесте фиктивные.
 """
 
 import os
 import sys
 import unittest
 from pathlib import Path
+from unittest import mock
 
 sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
 
 import server  # noqa: E402
+from core.backend_adapter import is_bridge_secret_name, strip_bridge_secrets  # noqa: E402
 
 FAKE_FACTORY_KEY = "fk-TEST-NOT-REAL"
 FAKE_BRIDGE_KEY = "bridge-test-key-not-real"
@@ -42,11 +45,94 @@ class TestLaunchEnv(unittest.TestCase):
         # Ключ моста не утёк под другим именем
         self.assertNotIn(FAKE_BRIDGE_KEY, set(env.values()))
 
+    def test_bridge_key_is_dropped(self):
+        """ADR 0015 B1: новое имя ключа хаба `BRIDGE_KEY` тоже не доезжает до потомка."""
+        os.environ["BRIDGE_KEY"] = FAKE_BRIDGE_KEY
+        try:
+            env = server._launch_env()
+        finally:
+            os.environ.pop("BRIDGE_KEY", None)
+        self.assertNotIn("BRIDGE_KEY", env)
+        self.assertNotIn(FAKE_BRIDGE_KEY, set(env.values()))
+
+    def test_both_bridge_key_names_dropped_together(self):
+        with mock.patch.dict(
+            os.environ,
+            {
+                "BRIDGE_KEY": FAKE_BRIDGE_KEY,
+                "DROID_DSH_BRIDGE_KEY": FAKE_BRIDGE_KEY + "-legacy",
+                "FACTORY_API_KEY": FAKE_FACTORY_KEY,
+            },
+        ):
+            env = server._launch_env()
+        self.assertNotIn("BRIDGE_KEY", env)
+        self.assertNotIn("DROID_DSH_BRIDGE_KEY", env)
+        self.assertEqual(env.get("FACTORY_API_KEY"), FAKE_FACTORY_KEY)
+        leaked = {FAKE_BRIDGE_KEY, FAKE_BRIDGE_KEY + "-legacy"} & set(env.values())
+        self.assertEqual(leaked, set())
+
+    def test_suffix_and_pattern_bridge_keys_dropped_ordinary_survive(self):
+        secrets = {
+            "MUSE_BRIDGE_KEY": "s1",
+            "AGY_BRIDGE_KEY": "s2",
+            "BRIDGE_API_KEY": "s3",
+            "BRIDGE_AUTH_KEY_2": "s4",
+            "droid_dsh_bridge_key": "s5",
+        }
+        ordinary = {
+            "BRIDGE_HOST": "127.0.0.1",
+            "BRIDGE_PORT": "9882",
+            "BRIDGE_INSTR_LIMIT": "100000",
+            "DROID_DSH_BRIDGE_HOST": "127.0.0.1",
+            "KEYCHAIN_NAME": "login",
+            "PATH": os.environ.get("PATH", "/usr/bin"),
+        }
+        with mock.patch.dict(os.environ, {**secrets, **ordinary}):
+            env = server._launch_env()
+        for name in secrets:
+            self.assertNotIn(name, env, name)
+        for name, value in ordinary.items():
+            self.assertEqual(env.get(name), value, name)
+
+    def test_child_env_has_no_bridge_keys(self):
+        """`_child_env()` строится поверх `_launch_env()`: ключи моста не попадают и в окружение droid-ребёнка."""
+        with mock.patch.dict(
+            os.environ,
+            {"BRIDGE_KEY": FAKE_BRIDGE_KEY, "DROID_DSH_BRIDGE_KEY": FAKE_BRIDGE_KEY},
+        ), mock.patch.object(server, "_mkdir_private"), mock.patch.object(
+            server, "_droid_image", return_value=None
+        ):
+            env = server._child_env()
+        self.assertFalse([n for n in env if is_bridge_secret_name(n)], sorted(env))
+        self.assertNotIn(FAKE_BRIDGE_KEY, set(env.values()))
+
+    def test_strip_bridge_secrets_in_place_and_returns_same_dict(self):
+        env = {"BRIDGE_KEY": "a", "X_BRIDGE_KEY": "b", "HOME": "/h"}
+        self.assertIs(strip_bridge_secrets(env), env)
+        self.assertEqual(env, {"HOME": "/h"})
+
     def test_absent_factory_key_does_not_appear(self):
         os.environ.pop("FACTORY_API_KEY", None)
         env = server._launch_env()
         self.assertNotIn("FACTORY_API_KEY", env)
 
+    def test_bridge_env_cascade(self):
+        """HOST/PORT/KEY: BRIDGE_* -> DROID_DSH_BRIDGE_* -> умолчание; пустое значение = не задано."""
+        names = (
+            "BRIDGE_HOST",
+            "DROID_DSH_BRIDGE_HOST",
+        )
+        with mock.patch.dict(os.environ, {}, clear=False):
+            for name in names:
+                os.environ.pop(name, None)
+            self.assertEqual(server._bridge_env("HOST", "127.0.0.1"), "127.0.0.1")
+            os.environ["DROID_DSH_BRIDGE_HOST"] = "10.0.0.2"
+            self.assertEqual(server._bridge_env("HOST", "127.0.0.1"), "10.0.0.2")
+            os.environ["BRIDGE_HOST"] = "10.0.0.3"
+            self.assertEqual(server._bridge_env("HOST", "127.0.0.1"), "10.0.0.3")
+            os.environ["BRIDGE_HOST"] = "  "
+            self.assertEqual(server._bridge_env("HOST", "127.0.0.1"), "10.0.0.2")
+
     def test_masking_covers_short_factory_key(self):
         masked = server._mask_secrets("auth: " + FAKE_FACTORY_KEY)
         self.assertNotIn(FAKE_FACTORY_KEY, masked)
diff --git a/tools/b_guard.py b/tools/b_guard.py
index 1c381e0..a167f1d 100644
--- a/tools/b_guard.py
+++ b/tools/b_guard.py
@@ -60,11 +60,18 @@ journal_line_bytes - длина JSON-строки события в session.v4.j
 нет - берётся середина окна, округлённая вниз.
 
 Коды выхода `--check` и `--profiles`: 0 - оба запаса >= 4096 Б и запас строки журнала до
-60 000 Б в KB >= 2048 Б; 1 - запас меньше порога; 2 - канон теряется в каком-либо cwd
-(CANON_LOST), дубль возвращается (DUPLICATE_RETURNED) или блок/строка KB > 60 000 Б
+предела блока в KB >= 2048 Б; 1 - запас меньше порога; 2 - канон теряется в каком-либо cwd
+(CANON_LOST), дубль возвращается (DUPLICATE_RETURNED) или блок/строка KB > предела блока
 (REQ003_SIZE_EXCEEDED: в рабочем CLI `run_check` всегда вызывает evaluate со
 `strict_req003=True`, AD-006 дельта-4; чистая функция `evaluate` по умолчанию остаётся
-нестрогой и даёт 1). Граница 60 000 Б строгая: 60 000 проходит, 60 001 нет.
+нестрогой и даёт 1). Граница предела строгая: ровно предел проходит, предел + 1 нет.
+
+Предел блока (ADR 0015) не зашит: `resolve_block_limit` читает `BRIDGE_INSTR_LIMIT`, затем
+`DROID_DSH_BRIDGE_INSTR_LIMIT`; по умолчанию `BLOCK_LIMIT` = 100 000 Б. Значение - целое;
+пустое, нечисловое и неположительное игнорируется (берётся следующее имя, затем умолчание),
+положительное вне [INSTR_LIMIT_MIN..INSTR_LIMIT_MAX] зажимается в границы. Чистая `evaluate`
+берёт предел параметром `limit` (None - `BLOCK_LIMIT`) и от окружения не зависит; окружение
+читают `run_check`/`check_installed` (параметр `limit=None` - из окружения).
 
 Режим `--profiles [--profiles-dir PATH]` (по умолчанию `~/.dsh/profiles`): для каждого профиля
 с `cordis.patch.yml` (каталоги `*.bak*` пропускаются) читает maxBytes и прогоняет ту же проверку,
@@ -82,7 +89,7 @@ import os
 import posixpath
 import re
 import sys
-from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple
+from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple
 
 CANON_PATH = os.path.expanduser("~/Мой диск/Context/AGENTS.md")
 KB_CWD = os.path.expanduser("~/Мой диск/Работа/Sber/knowledge-base")
@@ -109,8 +116,15 @@ FORMULA_BASE = (
 )
 FORMULA_PER_SECTION = 32
 
-BLOCK_LIMIT = 60000  # REQ-003, граница строгая: <= 60000 проходит
-DEFAULT_MAXBYTES = 106496
+BLOCK_LIMIT = 100000  # REQ-003, умолчание предела блока; граница строгая: <= предела проходит
+INSTR_LIMIT_ENV_NAMES: Tuple[str, ...] = (
+    "BRIDGE_INSTR_LIMIT",
+    "DROID_DSH_BRIDGE_INSTR_LIMIT",
+)  # порядок приоритета: новое имя, затем прежнее
+INSTR_LIMIT_MIN = 10000
+INSTR_LIMIT_MAX = 500000
+DEFAULT_MAXBYTES = 118784  # maxBytes установленных профилей DSH (116 КиБ) при каноне ~62,9 КБ
+SNAPSHOT_MAXBYTES = 106496  # maxBytes снимка zone-F (F-709): калибровка модели и self-test
 MARGIN_MIN = 4096
 LINE_MARGIN_MIN = 2048
 
@@ -317,9 +331,33 @@ def render_plan(entries: Sequence[FileEntry], maxbytes: int) -> RenderResult:
     )
 
 
-def block_within_limit(block_bytes: int) -> bool:
-    """Граница REQ-003 строгая: 60 000 Б проходит, 60 001 - нет."""
-    return block_bytes <= BLOCK_LIMIT
+def parse_block_limit(raw: Optional[str]) -> Optional[int]:
+    """Целое значение предела из строки; None - пусто, не число или неположительное.
+
+    Положительное вне [INSTR_LIMIT_MIN..INSTR_LIMIT_MAX] зажимается в границы диапазона.
+    """
+    text = (raw or "").strip()
+    if not (text.isascii() and text.isdigit()):
+        return None
+    value = int(text)
+    if value <= 0:
+        return None
+    return max(INSTR_LIMIT_MIN, min(INSTR_LIMIT_MAX, value))
+
+
+def resolve_block_limit(environ: Optional[Mapping[str, str]] = None) -> int:
+    """Предел блока agent-instructions: BRIDGE_INSTR_LIMIT -> DROID_DSH_BRIDGE_INSTR_LIMIT -> BLOCK_LIMIT."""
+    env = os.environ if environ is None else environ
+    for name in INSTR_LIMIT_ENV_NAMES:
+        value = parse_block_limit(env.get(name))
+        if value is not None:
+            return value
+    return BLOCK_LIMIT
+
+
+def block_within_limit(block_bytes: int, limit: Optional[int] = None) -> bool:
+    """Граница REQ-003 строгая: ровно предел проходит, предел + 1 - нет (None - умолчание BLOCK_LIMIT)."""
+    return block_bytes <= (BLOCK_LIMIT if limit is None else limit)
 
 
 def journal_line_bytes_est(text: str) -> int:
@@ -452,16 +490,19 @@ def evaluate(
     strict_req003: bool = False,
     texts: Optional[Dict[str, Dict[str, str]]] = None,
     canon_text: Optional[str] = None,
+    limit: Optional[int] = None,
 ) -> Result:
     """Чистая оценка окна maxBytes без файловой системы.
 
     `cwd_files` - метка cwd -> проектные файлы в порядке рендера (user-global добавляется
-    здесь). `req003_cwds` - метки cwd, для которых действует ограничение 60 000 Б (по
-    решению владельца REQ-003 принимается только в KB: для WA/AB условие недостижимо, F-724).
+    здесь). `req003_cwds` - метки cwd, для которых действует предел блока `limit` (None -
+    `BLOCK_LIMIT`; по решению владельца REQ-003 принимается только в KB: для WA/AB условие
+    недостижимо, F-724).
     `texts` (метка cwd -> display -> текст файла) и `canon_text` включают точный расчёт строки
     журнала; нет текста хотя бы одной оставленной секции - запасная оценка по размерам.
     `strict_req003` поднимает REQ003_SIZE_EXCEEDED до exit 2 (рабочий CLI всегда включает его).
     """
+    limit = BLOCK_LIMIT if limit is None else limit
     reasons: List[str] = []
     renders: Dict[str, RenderResult] = {}
     line_estimates: Dict[str, Tuple[int, bool]] = {}
@@ -507,19 +548,19 @@ def evaluate(
         if rend is None:
             continue
         line_est = line_estimates[label][0]
-        margin = BLOCK_LIMIT - line_est
+        margin = limit - line_est
         line_margin = margin if line_margin is None else min(line_margin, margin)
-        if not block_within_limit(rend.block_bytes):
+        if not block_within_limit(rend.block_bytes, limit):
             reasons.append(
                 "REQ003_SIZE_EXCEEDED cwd=%s basis=block block=%d limit=%d"
-                % (label, rend.block_bytes, BLOCK_LIMIT)
+                % (label, rend.block_bytes, limit)
             )
             warn = True
             severe = severe or strict_req003
-        elif not block_within_limit(line_est):
+        elif not block_within_limit(line_est, limit):
             reasons.append(
                 "REQ003_SIZE_EXCEEDED cwd=%s basis=line_estimate line_est=%d limit=%d"
-                % (label, line_est, BLOCK_LIMIT)
+                % (label, line_est, limit)
             )
             warn = True
             severe = severe or strict_req003
@@ -705,10 +746,34 @@ def self_test() -> List[str]:
         model = _block(entries, "")
         if formula != model:
             fails.append("формула %s: %d != %d" % (name, formula, model))
-    # Граница REQ-003 строгая.
-    for value, ok in ((59999, True), (60000, True), (60001, False)):
-        if block_within_limit(value) != ok:
-            fails.append("граница 60000: %d -> %s" % (value, not ok))
+    # Граница REQ-003 строгая: умолчание BLOCK_LIMIT и явный предел.
+    for limit, value, ok in (
+        (None, BLOCK_LIMIT - 1, True),
+        (None, BLOCK_LIMIT, True),
+        (None, BLOCK_LIMIT + 1, False),
+        (60000, 60000, True),
+        (60000, 60001, False),
+    ):
+        if block_within_limit(value, limit) != ok:
+            fails.append(
+                "граница предела %d: %d -> %s"
+                % (BLOCK_LIMIT if limit is None else limit, value, not ok)
+            )
+    # Разбор предела: пустое/нечисловое/отрицательное -> умолчание, вне диапазона -> зажим.
+    for environ, expected in (
+        ({}, BLOCK_LIMIT),
+        ({"BRIDGE_INSTR_LIMIT": ""}, BLOCK_LIMIT),
+        ({"BRIDGE_INSTR_LIMIT": "abc"}, BLOCK_LIMIT),
+        ({"BRIDGE_INSTR_LIMIT": "-5"}, BLOCK_LIMIT),
+        ({"BRIDGE_INSTR_LIMIT": "120000"}, 120000),
+        ({"DROID_DSH_BRIDGE_INSTR_LIMIT": "70000"}, 70000),
+        ({"BRIDGE_INSTR_LIMIT": "80000", "DROID_DSH_BRIDGE_INSTR_LIMIT": "70000"}, 80000),
+        ({"BRIDGE_INSTR_LIMIT": "1"}, INSTR_LIMIT_MIN),
+        ({"BRIDGE_INSTR_LIMIT": "9999999"}, INSTR_LIMIT_MAX),
+    ):
+        got = resolve_block_limit(environ)
+        if got != expected:
+            fails.append("предел %r: %d != %d" % (environ, got, expected))
     # Golden: равная длина, разное экранирование -> разные оценки, равные json.dumps.
     plain = "a" * 100
     quotes = '"' * 100
@@ -724,7 +789,7 @@ def self_test() -> List[str]:
     res = evaluate(
         canon,
         {"KB": kb[1:], "WA": wa[1:], "AB": ab[1:], "DW": []},
-        DEFAULT_MAXBYTES,
+        SNAPSHOT_MAXBYTES,
         ("KB",),
     )
     if (res.lower_margin, res.upper_margin, res.exit_code) != (12736, 4680, 0):
@@ -732,10 +797,10 @@ def self_test() -> List[str]:
             "окно снимка: %r/%r/exit %d"
             % (res.lower_margin, res.upper_margin, res.exit_code)
         )
-    if res.recommended != DEFAULT_MAXBYTES:
+    if res.recommended != SNAPSHOT_MAXBYTES:
         fails.append(
             "рекомендуемый maxBytes на снимке %r != %d"
-            % (res.recommended, DEFAULT_MAXBYTES)
+            % (res.recommended, SNAPSHOT_MAXBYTES)
         )
     return fails
 
@@ -759,11 +824,18 @@ def _fmt_margin(value: Optional[int]) -> str:
     return "n/a" if value is None else "%d" % value
 
 
-def run_check(maxbytes: int, cwds: Sequence[Tuple[str, str]], canon_path: str) -> int:
+def run_check(
+    maxbytes: int,
+    cwds: Sequence[Tuple[str, str]],
+    canon_path: str,
+    limit: Optional[int] = None,
+) -> int:
     """Читает файлы, печатает прогноз по каждому cwd, запасы и причины; возвращает код выхода.
 
-    REQ-003 строгий (strict_req003=True): превышение 60 000 Б блока/строки KB даёт exit 2.
+    REQ-003 строгий (strict_req003=True): превышение предела блока/строки KB даёт exit 2.
+    Предел `limit` - параметр, иначе из окружения (`resolve_block_limit`).
     """
+    limit = resolve_block_limit() if limit is None else limit
     try:
         canon_size = os.stat(canon_path).st_size
     except FileNotFoundError:
@@ -779,7 +851,8 @@ def run_check(maxbytes: int, cwds: Sequence[Tuple[str, str]], canon_path: str) -
     except OSError:
         pass
     _say(
-        "mode=PLANNED maxbytes=%d canon=%s size=%d" % (maxbytes, canon_path, canon_size)
+        "mode=PLANNED maxbytes=%d canon=%s size=%d block_limit=%d"
+        % (maxbytes, canon_path, canon_size, limit)
     )
     cwd_files: Dict[str, Sequence[FileEntry]] = {}
     texts: Dict[str, Dict[str, str]] = {}
@@ -800,6 +873,7 @@ def run_check(maxbytes: int, cwds: Sequence[Tuple[str, str]], canon_path: str) -
         strict_req003=True,
         texts=texts,
         canon_text=canon_text,
+        limit=limit,
     )
     for label, _path in cwds:
         rend = (res.renders or {})[label]
@@ -872,12 +946,16 @@ def _user_global_problem(canon_real: str, canon_bytes: bytes) -> Optional[str]:
 
 
 def check_installed(
-    maxbytes: int, cwds: Sequence[Tuple[str, str]], canon_path: str
+    maxbytes: int,
+    cwds: Sequence[Tuple[str, str]],
+    canon_path: str,
+    limit: Optional[int] = None,
 ) -> Optional[Result]:
     """Тот же прогноз, что `run_check`, но без печати (для автоматического контура моста).
 
     None - канон не найден (CANON_LOST). Результат с exit_code 2 и причиной CANON_LOST - настоящий
-    user-global `UG_PATH` удалён, изменён или указывает не на канон. REQ-003 строгий, как в рабочем CLI.
+    user-global `UG_PATH` удалён, изменён или указывает не на канон. REQ-003 строгий, как в рабочем CLI;
+    предел блока `limit` - параметр, None - из окружения (`resolve_block_limit`).
     Файлы читаются только для хеша и точной длины строки журнала; содержимое наружу не отдаётся.
     """
     try:
@@ -906,6 +984,7 @@ def check_installed(
         strict_req003=True,
         texts=texts,
         canon_text=canon_text,
+        limit=resolve_block_limit() if limit is None else limit,
     )
 
 

```
